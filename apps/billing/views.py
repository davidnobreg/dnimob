"""
apps/billing/views.py
Tela de configuração de forma de pagamento da assinatura Asaas (DN Software
cobra a imobiliária). Segue o mesmo padrão de apps/tenants/views.py::config_sicredi.
"""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.tenants.views import is_admin

from .client import AsaasClient, AsaasError

logger = logging.getLogger('apps.billing')

BILLING_TYPES_VALIDOS = ('BOLETO', 'PIX')


@login_required
@user_passes_test(is_admin)
def config_asaas(request):
	"""
	GET: exibe forma de pagamento atual da assinatura.
	POST: atualiza para Boleto ou Pix (cartão é via associar_cartao, com token).
	"""
	tenant = request.tenant

	subscription_data = None
	billing_type_atual = 'BOLETO'

	if tenant.asaas_subscription_id:
		try:
			client = AsaasClient()
			subscription_data = client.obter_subscription(tenant.asaas_subscription_id)
			billing_type_atual = subscription_data.get('billingType', 'BOLETO')
		except AsaasError as e:
			logger.error('Erro ao consultar subscription Asaas do tenant %s: %s', tenant.schema_name, e)
			messages.warning(request, 'Não foi possível consultar os dados de pagamento no momento.')

	if request.method == 'POST':
		billing_type = request.POST.get('billing_type', '').upper()

		if billing_type not in BILLING_TYPES_VALIDOS:
			messages.error(request, 'Forma de pagamento inválida.')
			return redirect('config_asaas')

		if not tenant.asaas_subscription_id:
			messages.error(request, 'Assinatura não encontrada. Contate o suporte.')
			return redirect('config_asaas')

		try:
			client = AsaasClient()
			client.atualizar_billing_type(tenant.asaas_subscription_id, billing_type)
			messages.success(request, f'Forma de pagamento atualizada para {billing_type.title()}.')
		except AsaasError as e:
			logger.error('Erro ao atualizar billing type do tenant %s: %s', tenant.schema_name, e)
			messages.error(request, 'Erro ao atualizar forma de pagamento. Tente novamente.')

		return redirect('config_asaas')

	return render(request, 'billing/config_asaas.html', {
		'tenant': tenant,
		'subscription_data': subscription_data,
		'billing_type_atual': billing_type_atual,
		'asaas_configurado': bool(tenant.asaas_subscription_id),
		'ASAAS_PUBLIC_KEY': getattr(settings, 'ASAAS_PUBLIC_KEY', ''),
		'ASAAS_JS_URL': getattr(settings, 'ASAAS_JS_URL', ''),
	})


@login_required
@user_passes_test(is_admin)
@require_POST
def associar_cartao_asaas(request):
	"""
	Recebe o token do cartão já gerado pelo Asaas.js no frontend — o cartão
	em si nunca chega no nosso servidor.
	"""
	tenant = request.tenant
	if not tenant.asaas_subscription_id:
		return JsonResponse({'ok': False, 'erro': 'Assinatura não encontrada.'}, status=400)

	try:
		data = json.loads(request.body)
	except ValueError:
		return JsonResponse({'ok': False, 'erro': 'Corpo da requisição inválido.'}, status=400)

	credit_card_token = data.get('creditCardToken')
	if not credit_card_token:
		return JsonResponse({'ok': False, 'erro': 'Token do cartão não fornecido.'}, status=400)

	try:
		client = AsaasClient()
		client.associar_cartao_subscription(tenant.asaas_subscription_id, credit_card_token)
		return JsonResponse({'ok': True})
	except AsaasError as e:
		logger.error('Erro ao associar cartão do tenant %s: %s', tenant.schema_name, e)
		return JsonResponse({'ok': False, 'erro': 'Erro ao associar cartão. Tente novamente.'}, status=502)
