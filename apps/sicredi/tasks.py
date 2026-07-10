"""
apps/sicredi/tasks.py
Tasks Celery da integração Sicredi. Fila: financeiro (ver CELERY_TASK_ROUTES).

Usa TenantTask como base: o 1º argumento é sempre o schema_name e a task
executa dentro do schema_context correspondente.
"""
import logging

from datetime import datetime

from celery import shared_task

from config.celery import TenantTask
from .client import SicrediAuthError, SicrediError
from .service import gerar_boleto_parcela, reconciliar_liquidados_dia

logger = logging.getLogger('apps.sicredi')


@shared_task(base=TenantTask, bind=True, max_retries=3)
def gerar_boleto_parcela_task(self, parcela_id):
	"""
	Gera o boleto de uma parcela no Sicredi.
	Chamada: gerar_boleto_parcela_task.apply_async(args=[schema_name, parcela_id]).
	Retry 3x com backoff exponencial (60s, 120s, 240s) em falhas de API.
	Erro de autenticação não faz retry (credenciais não se corrigem sozinhas).
	"""
	from apps.contratos.models import Parcela

	try:
		parcela = Parcela.objects.select_related('contrato').get(pk=parcela_id)
	except Parcela.DoesNotExist:
		logger.warning('Boleto task: parcela %s não existe', parcela_id)
		return None

	# Não reemite boleto já válido (evita duplicar em disparo manual + automático)
	boleto_existente = getattr(parcela, 'boleto', None)
	if boleto_existente and boleto_existente.status in ('emitido', 'pago'):
		return boleto_existente.nosso_numero

	try:
		boleto = gerar_boleto_parcela(parcela)
		return boleto.nosso_numero
	except SicrediAuthError as e:
		logger.error('Boleto task: autenticação falhou (sem retry) parcela=%s: %s', parcela_id, e)
		return None
	except SicrediError as e:
		retries = self.request.retries
		countdown = 60 * (2 ** retries)  # 60, 120, 240
		logger.warning('Boleto task: falha parcela=%s (tentativa %s/3), retry em %ss: %s',
		               parcela_id, retries + 1, countdown, e)
		raise self.retry(exc=e, countdown=countdown)


@shared_task(base=TenantTask, bind=True, max_retries=2)
def reconciliar_liquidados_dia_task(self, dia_str, cpf_cnpj_beneficiario_final=None):
	"""
	Reconciliação manual de boletos liquidados (consulta ativa Sicredi).

	NÃO está no CELERY_BEAT_SCHEDULE — chamar manualmente:
	reconciliar_liquidados_dia_task.apply_async(args=[schema, '2026-07-10']).
	Decisão de agendamento automático fica pra depois (ver
	docs/planos/reconciliacao-boletos-sicredi.md).

	`dia_str`: 'YYYY-MM-DD'. Aceita data retroativa (útil pra cobrir PIX de
	fim de semana, que só aparece na consulta do dia útil seguinte).
	"""
	dia = datetime.strptime(dia_str, '%Y-%m-%d').date()
	try:
		return reconciliar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=cpf_cnpj_beneficiario_final)
	except SicrediAuthError as e:
		logger.error('Reconciliação task: autenticação falhou (sem retry) dia=%s: %s', dia_str, e)
		return None
	except SicrediError as e:
		retries = self.request.retries
		countdown = 60 * (2 ** retries)  # 60, 120
		logger.warning('Reconciliação task: falha dia=%s (tentativa %s/2), retry em %ss: %s',
		               dia_str, retries + 1, countdown, e)
		raise self.retry(exc=e, countdown=countdown)
