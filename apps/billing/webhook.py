"""
apps/billing/webhook.py
Webhook público do Asaas — recebe eventos de pagamento/assinatura e
atualiza status_pagamento do Tenant correspondente.

Tenant vive no schema public (SHARED_APPS), então Tenant.objects.filter()
funciona direto, sem precisar de schema_context (esse só é necessário pra
entrar no schema de um tenant específico, não pra consultar o próprio
model Tenant).
"""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger('apps.billing')

# Eventos que atualizam status_pagamento
EVENTOS_STATUS = {
	'PAYMENT_CONFIRMED': 'ativo',
	'PAYMENT_RECEIVED': 'ativo',
	'PAYMENT_OVERDUE': 'inadimplente',
	'SUBSCRIPTION_DELETED': 'cancelado',
	'PAYMENT_DELETED': 'inadimplente',
	'PAYMENT_REFUNDED': 'inadimplente',
	'PAYMENT_CHARGEBACK_REQUESTED': 'inadimplente',
}


def _validar_token(request):
	"""
	Valida o token de autenticação do webhook enviado pelo Asaas no
	header 'asaas-access-token'.

	Em produção (ASAAS_WEBHOOK_TOKEN_REQUIRED=True), token vazio = rejeita.
	Em dev (DEBUG=True), token vazio = aceita (facilita testes locais).
	"""
	token_esperado = settings.ASAAS_WEBHOOK_TOKEN
	token_required = getattr(settings, 'ASAAS_WEBHOOK_TOKEN_REQUIRED', not settings.DEBUG)

	if not token_esperado:
		if token_required:
			logger.error(
				'ASAAS_WEBHOOK_TOKEN não configurado em produção — '
				'requisição rejeitada por segurança'
			)
			return False
		logger.warning('ASAAS_WEBHOOK_TOKEN não configurado — aceitando em modo dev')
		return True

	token_enviado = request.headers.get('asaas-access-token', '')
	return token_enviado == token_esperado


@csrf_exempt
@require_POST
def asaas_webhook(request):
	"""
	Recebe eventos do Asaas e atualiza status_pagamento do Tenant.

	URL pública: /asaas/webhook/
	Autenticação: token via header 'asaas-access-token'.
	"""
	if not _validar_token(request):
		logger.warning('Webhook Asaas: token inválido')
		return JsonResponse({'erro': 'Não autorizado'}, status=401)

	try:
		payload = json.loads(request.body)
	except json.JSONDecodeError:
		logger.error('Webhook Asaas: payload inválido')
		return JsonResponse({'erro': 'Payload inválido'}, status=400)

	evento = payload.get('event', '')
	subscription_id = (
		payload.get('payment', {}).get('subscription')
		or payload.get('subscription', {}).get('id')
		or ''
	)
	customer_id = (
		payload.get('payment', {}).get('customer')
		or payload.get('subscription', {}).get('customer')
		or ''
	)

	logger.info(
		'Webhook Asaas recebido: evento=%s subscription=%s customer=%s',
		evento, subscription_id, customer_id,
	)

	novo_status = EVENTOS_STATUS.get(evento)
	if not novo_status:
		logger.debug('Webhook Asaas: evento %s ignorado (não mapeado)', evento)
		return JsonResponse({'ok': True, 'ignorado': True})

	from apps.tenants.models import Tenant

	tenant = None
	if subscription_id:
		tenant = Tenant.objects.filter(asaas_subscription_id=subscription_id).first()
	if not tenant and customer_id:
		tenant = Tenant.objects.filter(asaas_customer_id=customer_id).first()

	if not tenant:
		logger.warning(
			'Webhook Asaas: tenant não encontrado para subscription=%s customer=%s',
			subscription_id, customer_id,
		)
		return JsonResponse({'ok': True, 'tenant': 'não encontrado'})

	status_anterior = tenant.status_pagamento
	tenant.status_pagamento = novo_status

	if evento == 'PAYMENT_OVERDUE':
		# Período de graça: 5 dias corridos após o vencimento da fatura.
		due_date_str = (
			payload.get('payment', {}).get('dueDate')
			or payload.get('payment', {}).get('originalDueDate')
		)
		tenant.asaas_graca_ate = None
		if due_date_str:
			due_date = parse_date(due_date_str)
			if due_date:
				tenant.asaas_graca_ate = due_date + timedelta(days=5)
			else:
				logger.warning(
					'Webhook Asaas: não foi possível parsear dueDate=%s para tenant %s',
					due_date_str, tenant.schema_name,
				)
	elif evento in ('PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED'):
		tenant.asaas_graca_ate = None

	tenant.save(update_fields=['status_pagamento', 'asaas_graca_ate', 'atualizado_em'])

	logger.info(
		'Tenant %s: status_pagamento %s → %s (evento: %s)',
		tenant.schema_name, status_anterior, novo_status, evento,
	)

	return JsonResponse({'ok': True, 'tenant': tenant.schema_name, 'status': novo_status})
