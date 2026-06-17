import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .client import SicrediError
from .service import gerar_boleto_parcela, cancelar_boleto, processar_webhook, get_config_tenant

logger = logging.getLogger('apps.sicredi')


# ── Emissão / baixa manual (tela de contrato) ─────────────────────────────────

@login_required
@require_POST
def boleto_emitir(request, parcela_pk):
	from apps.contratos.models import Parcela
	parcela = get_object_or_404(Parcela, pk=parcela_pk)

	if not get_config_tenant():
		messages.error(request, 'Integração Sicredi não configurada/ativa. Acesse Configurações → Sicredi.')
		return redirect('contrato_detalhe', pk=parcela.contrato.pk)

	try:
		boleto = gerar_boleto_parcela(parcela)
		messages.success(request, f'Boleto emitido para a parcela {parcela.numero} (nosso número {boleto.nosso_numero}).')
	except SicrediError as e:
		messages.error(request, f'Erro ao emitir boleto: {e}')

	return redirect('contrato_detalhe', pk=parcela.contrato.pk)


@login_required
@require_POST
def boleto_cancelar(request, parcela_pk):
	from apps.contratos.models import Parcela
	parcela = get_object_or_404(Parcela, pk=parcela_pk)

	boleto = getattr(parcela, 'boleto', None)
	if not boleto:
		messages.error(request, 'Esta parcela não possui boleto para baixar.')
		return redirect('contrato_detalhe', pk=parcela.contrato.pk)

	try:
		ok, msg = cancelar_boleto(boleto)
		(messages.success if ok else messages.warning)(request, msg)
	except SicrediError as e:
		messages.error(request, f'Erro ao baixar boleto: {e}')

	return redirect('contrato_detalhe', pk=parcela.contrato.pk)


# ── Webhook público (chamado pelo Sicredi) ────────────────────────────────────

@csrf_exempt
def webhook_sicredi(request):
	"""
	Endpoint público de eventos do Sicredi. Roda no schema public.
	Regra do Sicredi: responder SEMPRE HTTP 200 em até 10s, mesmo em erro
	interno (apenas loga). Sem autenticação obrigatória nesta versão da API.

	A validação de assinatura (X-Signature, best-effort — ver
	service._assinatura_valida) só é aplicada se o tenant tiver preenchido
	ConfigSicredi.webhook_secret; sem isso, aceita o payload normalmente.
	"""
	if request.method != 'POST':
		return HttpResponse(status=405)

	try:
		raw_body = request.body or b'{}'
		payload = json.loads(raw_body)
		assinatura = request.headers.get('X-Signature', '')
		processar_webhook(payload, raw_body=raw_body, assinatura=assinatura)
	except json.JSONDecodeError:
		logger.warning('Webhook Sicredi: corpo não é JSON válido')
	except Exception:  # noqa: BLE001 — nunca derruba a resposta (regra Sicredi)
		logger.exception('Webhook Sicredi: erro ao processar evento')

	return HttpResponse(status=200)
