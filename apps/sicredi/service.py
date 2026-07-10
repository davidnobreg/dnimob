"""
apps/sicredi/service.py
Camada de negócio da integração Sicredi.

Orquestra o SicrediClient (client.py) e o processamento de webhook.
Não fala HTTP direto — isso é responsabilidade do client.
"""
import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context

from .client import SicrediClient, SicrediAuthError, SicrediAPIError

logger = logging.getLogger('apps.sicredi')

# Movimentos de webhook que representam pagamento
MOVIMENTOS_LIQUIDACAO = {
	'LIQUIDACAO_PIX',
	'LIQUIDACAO_REDE',
	'LIQUIDACAO_COMPE_H5',
	'LIQUIDACAO_COMPE_H6',
	'LIQUIDACAO_COMPE_H8',
	'LIQUIDACAO_CARTORIO',
}
MOVIMENTO_ESTORNO = 'ESTORNO_LIQUIDACAO_REDE'


class WebhookAuthError(Exception):
	"""
	Webhook rejeitado por falha de autenticação: em produção (DEBUG=False),
	webhook_secret não configurado para o tenant, ou assinatura ausente/inválida.
	A view responde 401 nesse caso, em vez do 200 padrão do Sicredi.
	"""


# ── Config do tenant ──────────────────────────────────────────────────────────

def get_config_tenant():
	"""
	Retorna a ConfigSicredi ativa do tenant atual (ou None).
	ConfigSicredi vive no schema public; filtramos pelo schema_name corrente.
	"""
	from apps.tenants.models import ConfigSicredi
	return ConfigSicredi.objects.filter(
		schema_name=connection.schema_name, ativo=True
	).first()


# ── Teste de credenciais ──────────────────────────────────────────────────────

def testar_credenciais_sicredi(config) -> tuple[bool, str]:
	"""Tenta autenticar no Sicredi. Retorna (sucesso, mensagem)."""
	try:
		client = SicrediClient(config, schema_name=connection.schema_name)
		client.autenticar()
		return True, 'Credenciais válidas! Conexão com o Sicredi estabelecida.'
	except SicrediAuthError as e:
		return False, str(e)
	except Exception as e:  # noqa: BLE001 — defensivo, nunca derruba a view
		logger.exception('Erro inesperado ao testar credenciais Sicredi')
		return False, f'Erro inesperado ao testar conexão: {e}'


# ── Geração / cancelamento de boleto ──────────────────────────────────────────

def gerar_boleto_parcela(parcela):
	"""
	Gera o boleto da parcela no Sicredi. Usa a ConfigSicredi do tenant atual.
	Em falha, registra o erro no Boleto (status='erro') e relança.
	"""
	from apps.sicredi.models import Boleto

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	try:
		return client.criar_boleto(parcela)
	except (SicrediAuthError, SicrediAPIError) as e:
		# Marca o boleto como erro para a UI exibir o botão de reemissão
		Boleto.objects.update_or_create(
			parcela=parcela,
			defaults={
				'nosso_numero': getattr(parcela.boleto, 'nosso_numero', '') if hasattr(parcela, 'boleto') else f'ERRO-{parcela.pk}',
				'status': 'erro',
				'erro_mensagem': str(e),
			},
		)
		raise


def cancelar_boleto(boleto) -> tuple[bool, str]:
	"""Baixa (cancela) o boleto no Sicredi. Retorna (sucesso, mensagem)."""
	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	return client.baixar_boleto(boleto)


# ── Reconciliação ativa (consulta de boletos liquidados) ──────────────────────

def reconciliar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None) -> dict:
	"""
	Reconciliação ativa: consulta a Sicredi pelos boletos liquidados no dia
	informado e corrige boletos que ficaram 'emitido' localmente porque o
	webhook falhou ou não chegou. Idempotente — boleto já 'pago' não é
	reprocessado.

	Reaproveita `_registrar_liquidacao` (mesma função usada pelo webhook) —
	não duplica a regra de negócio de marcar boleto+parcela como pagos.

	Retorna {'total', 'recuperados', 'nao_encontrados'}.
	"""
	from apps.sicredi.models import Boleto

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	itens = client.consultar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=cpf_cnpj_beneficiario_final)

	recuperados = 0
	nao_encontrados = 0

	for item in itens:
		nosso_numero = str(item.get('nossoNumero', '')).strip()
		if not nosso_numero:
			continue

		boleto = Boleto.objects.filter(nosso_numero=nosso_numero).first()
		if not boleto:
			nao_encontrados += 1
			logger.warning('Reconciliação Sicredi: boleto %s (dia=%s) não encontrado localmente', nosso_numero, dia)
			continue

		if boleto.status == 'pago':
			continue  # já consistente — webhook processou certo

		_registrar_liquidacao(nosso_numero, {
			'valorLiquidacao': item.get('valorLiquidado'),
			'dataPrevisaoPagamento': item.get('dataPagamento'),
		})
		recuperados += 1
		logger.warning('Reconciliação Sicredi: discrepância recuperada — boleto %s estava %s, webhook não processou',
		               nosso_numero, boleto.status)

	logger.info('Reconciliação Sicredi dia=%s: total=%s recuperados=%s nao_encontrados=%s',
	            dia, len(itens), recuperados, nao_encontrados)
	return {'total': len(itens), 'recuperados': recuperados, 'nao_encontrados': nao_encontrados}


# ── Webhook ───────────────────────────────────────────────────────────────────

def processar_webhook(payload: dict, raw_body: bytes = b'', assinatura: str = ''):
	"""
	Processa um evento de movimentação recebido do Sicredi.

	Identifica o tenant pelo `beneficiario` (codigo_beneficiario em ConfigSicredi),
	entra no schema correto e atualiza o Boleto + a Parcela. Os signals já
	existentes (financeiro + whatsapp) cuidam de Lancamento e confirmação.

	`raw_body`/`assinatura` são usados para a validação HMAC best-effort
	(ver `_assinatura_valida`) — a Sicredi não documenta oficialmente
	assinatura de webhook nesta versão da API, então isso é defesa em
	profundidade opcional, não um requisito confirmado pelo banco.
	"""
	from apps.tenants.models import ConfigSicredi

	beneficiario = str(payload.get('beneficiario', '')).strip()
	nosso_numero = str(payload.get('nossoNumero', '')).strip()
	movimento = payload.get('movimento', '')

	logger.info('Webhook Sicredi: beneficiario=%s nossoNumero=%s movimento=%s',
	            beneficiario, nosso_numero, movimento)

	if not beneficiario or not nosso_numero:
		logger.warning('Webhook Sicredi: payload sem beneficiario/nossoNumero')
		return

	# ConfigSicredi vive no public — lookup direto pelo codigo_beneficiario
	config = ConfigSicredi.objects.filter(codigo_beneficiario=beneficiario).first()
	if not config or not config.schema_name:
		logger.warning('Webhook Sicredi: beneficiario %s sem config/schema mapeado', beneficiario)
		return

	# Em produção (settings.SICREDI_WEBHOOK_SECRET_REQUIRED=True, derivado de
	# DEBUG=False — ver config/settings/base.py), webhook_secret é obrigatório:
	# sem ele — ou com assinatura ausente/inválida — a requisição é REJEITADA
	# (WebhookAuthError, a view responde 401), não apenas descartada em silêncio.
	# Em dev/teste mantém o comportamento antigo: secret opcional, só valida
	# se o tenant preencheu um; sem secret, aceita normalmente.
	if settings.SICREDI_WEBHOOK_SECRET_REQUIRED:
		if not config.webhook_secret:
			logger.warning('Webhook Sicredi: producao sem webhook_secret configurado para beneficiario %s — requisição rejeitada',
			               beneficiario)
			raise WebhookAuthError('webhook_secret não configurado para este tenant em produção')
		if not _assinatura_valida(raw_body, assinatura, config.webhook_secret):
			logger.warning('Webhook Sicredi: assinatura inválida/ausente para beneficiario %s — requisição rejeitada',
			               beneficiario)
			raise WebhookAuthError('assinatura inválida')
	elif config.webhook_secret and not _assinatura_valida(raw_body, assinatura, config.webhook_secret):
		logger.warning('Webhook Sicredi: assinatura inválida/ausente para beneficiario %s — payload descartado',
		               beneficiario)
		return

	with schema_context(config.schema_name):
		if movimento in MOVIMENTOS_LIQUIDACAO:
			_registrar_liquidacao(nosso_numero, payload)
		elif movimento == MOVIMENTO_ESTORNO:
			_registrar_estorno(nosso_numero, payload)
		else:
			logger.info('Webhook Sicredi: movimento %s ignorado', movimento)


def _registrar_liquidacao(nosso_numero, payload):
	from apps.sicredi.models import Boleto

	try:
		boleto = Boleto.objects.select_related('parcela').get(nosso_numero=nosso_numero)
	except Boleto.DoesNotExist:
		logger.warning('Webhook Sicredi: boleto %s não encontrado', nosso_numero)
		return

	valor = _to_decimal(payload.get('valorLiquidacao'))
	data_pgto = _parse_data(payload.get('dataPrevisaoPagamento') or payload.get('dataEvento')) or timezone.now().date()

	boleto.status = 'pago'
	boleto.valor_pago = valor
	boleto.pago_em = data_pgto
	boleto.erro_mensagem = ''
	boleto.save(update_fields=['status', 'valor_pago', 'pago_em', 'erro_mensagem', 'atualizado_em'])

	parcela = boleto.parcela
	if parcela.status != 'pago':
		parcela.status = 'pago'
		parcela.data_pagamento = data_pgto
		parcela.save()  # dispara signals: Lancamento (financeiro) + WhatsApp confirmação
		logger.info('Webhook Sicredi: parcela %s marcada como paga', parcela.pk)


def _registrar_estorno(nosso_numero, payload):
	"""
	Estorno de LIQUIDACAO_REDE — só ocorre no mesmo dia do pagamento.
	Reverte parcela/boleto e cancela o Lancamento gerado.
	"""
	from apps.sicredi.models import Boleto
	from apps.financeiro.models import Lancamento

	try:
		boleto = Boleto.objects.select_related('parcela').get(nosso_numero=nosso_numero)
	except Boleto.DoesNotExist:
		logger.warning('Webhook Sicredi: estorno de boleto %s não encontrado', nosso_numero)
		return

	hoje = timezone.now().date()
	if boleto.pago_em and boleto.pago_em != hoje:
		logger.warning('Webhook Sicredi: estorno de %s fora do mesmo dia (pago_em=%s) — ignorado',
		               nosso_numero, boleto.pago_em)
		return

	boleto.status = 'emitido'
	boleto.valor_pago = None
	boleto.pago_em = None
	boleto.save(update_fields=['status', 'valor_pago', 'pago_em', 'atualizado_em'])

	parcela = boleto.parcela
	parcela.status = 'pendente'
	parcela.data_pagamento = None
	parcela.save()

	# Cancela o lançamento de receita criado na liquidação
	Lancamento.objects.filter(parcela=parcela, tipo='receita').update(status='cancelado')
	logger.info('Webhook Sicredi: estorno aplicado, parcela %s revertida', parcela.pk)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assinatura_valida(raw_body: bytes, assinatura: str, secret: str) -> bool:
	"""
	Valida assinatura HMAC-SHA256 do corpo bruto do webhook.

	BEST-EFFORT: a Sicredi não documenta oficialmente um header de
	assinatura para o webhook de cobrança nesta versão da API (v3.9.1).
	Esta validação é defesa em profundidade — só roda quando o tenant
	preenche `ConfigSicredi.webhook_secret` manualmente. Formato assumido:
	header com hex digest de HMAC-SHA256(secret, corpo_bruto), aceitando
	opcionalmente o prefixo "sha256=" (convenção comum em outros provedores,
	ex. GitHub/Stripe). Ajustar aqui se a Sicredi formalizar o mecanismo.
	"""
	if not assinatura or not raw_body:
		return False
	recebida = assinatura.strip()
	if recebida.startswith('sha256='):
		recebida = recebida[len('sha256='):]
	esperada = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(esperada, recebida)


def _to_decimal(valor):
	try:
		return Decimal(str(valor)) if valor not in (None, '') else None
	except (InvalidOperation, ValueError):
		return None


def _parse_data(valor):
	"""
	Converte a data do payload Sicredi para date.
	Aceita lista [ano, mes, dia, ...] ou string 'YYYY-MM-DD'.
	"""
	if not valor:
		return None
	if isinstance(valor, (list, tuple)) and len(valor) >= 3:
		try:
			return datetime(int(valor[0]), int(valor[1]), int(valor[2])).date()
		except (ValueError, TypeError):
			return None
	if isinstance(valor, str):
		try:
			return datetime.fromisoformat(valor[:10]).date()
		except ValueError:
			return None
	return None