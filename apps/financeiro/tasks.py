"""
apps/financeiro/tasks.py
Tasks Celery do módulo financeiro.

disparar_todos_tenants é o ponto de entrada do Celery Beat: recebe o nome
de uma função interna e a executa para cada tenant ativo dentro do schema_context.
"""
import logging
from datetime import date, timedelta

from celery import shared_task
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)


# ── Dispatcher ────────────────────────────────────────────────────────────────

@shared_task(name='apps.financeiro.tasks.disparar_todos_tenants')
def disparar_todos_tenants(task_name: str, **kwargs):
	"""
	Itera todos os tenants ativos e executa a função identificada por task_name.
	Erros por tenant são logados sem interromper os demais.
	"""
	_DISPATCH = {
		'gerar_cobrancas_mensais':        _gerar_cobrancas_mensais,
		'registrar_boletos_pendentes':    _registrar_boletos_pendentes,
		'sincronizar_baixas_sicredi':     _sincronizar_baixas_sicredi,
		'marcar_inadimplencias':          _marcar_inadimplencias,
		'task_avisar_vencimento_amanha':  _avisar_vencimento_amanha,
		'task_avisar_vencimento_hoje':    _avisar_vencimento_hoje,
		'task_cobrar_inadimplentes':      _cobrar_inadimplentes,
		'task_avisar_contratos_vencendo': _avisar_contratos_vencendo,
	}

	fn = _DISPATCH.get(task_name)
	if not fn:
		logger.error('disparar_todos_tenants: task desconhecida "%s"', task_name)
		return

	TenantModel = get_tenant_model()
	tenants = TenantModel.objects.exclude(schema_name='public')

	for tenant in tenants:
		try:
			with schema_context(tenant.schema_name):
				fn(**kwargs)
		except Exception:
			logger.exception('Erro em %s para tenant %s', task_name, tenant.schema_name)


# ── Financeiro ────────────────────────────────────────────────────────────────

def _gerar_cobrancas_mensais():
	"""
	Dia 1 do mês: garante que todos os contratos ativos têm parcela para o mês
	corrente. Cobre casos onde o contrato foi ativado após a geração automática.
	"""
	from apps.contratos.models import Contrato, Parcela

	hoje = date.today()
	contratos_ativos = Contrato.objects.filter(
		status='ativo',
		data_inicio__lte=hoje,
		data_fim__gte=hoje,
	)

	criadas = 0
	for contrato in contratos_ativos:
		try:
			venc_dia = min(contrato.dia_vencimento, 28)
			venc = date(hoje.year, hoje.month, venc_dia)
		except ValueError:
			venc = date(hoje.year, hoje.month, 1)

		existe = Parcela.objects.filter(
			contrato=contrato,
			data_vencimento__year=hoje.year,
			data_vencimento__month=hoje.month,
		).exists()

		if not existe:
			proximo_num = (contrato.parcelas.count() or 0) + 1
			Parcela.objects.create(
				contrato=contrato,
				numero=proximo_num,
				data_vencimento=venc,
				valor=contrato.valor_aluguel,
				valor_condominio=contrato.valor_condominio,
				valor_iptu=contrato.valor_iptu,
			)
			criadas += 1

	if criadas:
		logger.info('gerar_cobrancas_mensais: %d parcela(s) criada(s)', criadas)


def _registrar_boletos_pendentes():
	"""
	Agenda geração de boleto no Sicredi para parcelas pendentes com vencimento
	nos próximos 5 dias que ainda não têm boleto emitido ou pago.
	"""
	from django.db import connection

	from apps.contratos.models import Parcela
	from apps.sicredi.tasks import gerar_boleto_parcela_task

	hoje = date.today()
	limite = hoje + timedelta(days=5)
	schema = connection.schema_name

	parcelas = Parcela.objects.filter(
		status='pendente',
		data_vencimento__range=(hoje, limite),
	).exclude(boleto__status__in=('emitido', 'pago'))

	for parcela in parcelas:
		gerar_boleto_parcela_task.apply_async(
			args=[schema, parcela.pk],
			queue='financeiro',
		)
		logger.debug('Boleto agendado: parcela %s venc. %s', parcela.pk, parcela.data_vencimento)


def _sincronizar_baixas_sicredi():
	"""
	Marca boletos como 'vencido' quando a data de vencimento passou e o boleto
	ainda está emitido. A liquidação real chega via webhook do Sicredi.
	"""
	from apps.sicredi.models import Boleto

	hoje = date.today()
	atualizados = Boleto.objects.filter(
		status='emitido',
		parcela__data_vencimento__lt=hoje,
	).update(status='vencido')

	if atualizados:
		logger.info('sincronizar_baixas_sicredi: %d boleto(s) marcado(s) como vencido', atualizados)


def _marcar_inadimplencias():
	"""
	Marca parcelas vencidas como 'atrasado' e inquilinos com parcelas atrasadas
	como 'inadimplente'.
	"""
	from apps.contratos.models import Parcela
	from apps.inquilinos.models import Inquilino

	hoje = date.today()

	atualizadas = Parcela.objects.filter(
		status='pendente',
		data_vencimento__lt=hoje,
	).update(status='atrasado')

	if atualizadas:
		logger.info('marcar_inadimplencias: %d parcela(s) marcada(s) como atrasada', atualizadas)

	ids_inadimplentes = (
		Parcela.objects
		.filter(status='atrasado')
		.values_list('contrato__inquilino_id', flat=True)
		.distinct()
	)

	Inquilino.objects.filter(
		pk__in=ids_inadimplentes,
		status='ativo',
	).update(status='inadimplente')


# ── WhatsApp ──────────────────────────────────────────────────────────────────

def _avisar_vencimento_amanha():
	"""Envia lembrete de vencimento para parcelas que vencem amanhã."""
	from apps.contratos.models import Parcela
	from apps.whatsapp.services import notificar_lembrete_vencimento

	amanha = date.today() + timedelta(days=1)
	parcelas = Parcela.objects.filter(
		data_vencimento=amanha,
		status='pendente',
	).select_related('contrato__inquilino', 'contrato__imovel')

	for parcela in parcelas:
		try:
			notificar_lembrete_vencimento(parcela)
		except Exception:
			logger.exception('Erro ao notificar vencimento amanhã para parcela %s', parcela.pk)


def _avisar_vencimento_hoje():
	"""Envia lembrete de vencimento para parcelas que vencem hoje."""
	from apps.contratos.models import Parcela
	from apps.whatsapp.services import notificar_lembrete_vencimento

	hoje = date.today()
	parcelas = Parcela.objects.filter(
		data_vencimento=hoje,
		status='pendente',
	).select_related('contrato__inquilino', 'contrato__imovel')

	for parcela in parcelas:
		try:
			notificar_lembrete_vencimento(parcela)
		except Exception:
			logger.exception('Erro ao notificar vencimento hoje para parcela %s', parcela.pk)


def _cobrar_inadimplentes():
	"""Envia cobrança por WhatsApp para parcelas com status 'atrasado'."""
	from apps.contratos.models import Parcela
	from apps.whatsapp.services import notificar_parcela_vencida

	parcelas = Parcela.objects.filter(
		status='atrasado',
	).select_related('contrato__inquilino', 'contrato__imovel')

	for parcela in parcelas:
		try:
			notificar_parcela_vencida(parcela)
		except Exception:
			logger.exception('Erro ao cobrar inadimplente para parcela %s', parcela.pk)


def _avisar_contratos_vencendo():
	"""
	Loga contratos que vencem nos próximos 30 dias.
	Notificação específica pendente de implementação em whatsapp.services.
	"""
	from apps.contratos.models import Contrato

	hoje = date.today()
	limite = hoje + timedelta(days=30)

	contratos = Contrato.objects.filter(
		status='ativo',
		data_fim__range=(hoje, limite),
	).select_related('inquilino', 'imovel')

	for contrato in contratos:
		dias_restantes = (contrato.data_fim - hoje).days
		logger.info(
			'Contrato %s (inquilino: %s) vence em %d dia(s)',
			contrato.numero, contrato.inquilino.nome, dias_restantes,
		)