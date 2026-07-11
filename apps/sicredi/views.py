import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .client import SicrediError
from .service import (
	gerar_boleto_parcela, gerar_boletos_lote, cancelar_boleto, imprimir_boleto,
	imprimir_carne_contrato, processar_webhook, get_config_tenant, WebhookAuthError,
)

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


@login_required
def boleto_pdf(request, parcela_pk):
	from apps.contratos.models import Parcela
	parcela = get_object_or_404(Parcela, pk=parcela_pk)

	boleto = getattr(parcela, 'boleto', None)
	if not boleto:
		messages.error(request, 'Esta parcela não possui boleto emitido.')
		return redirect('contrato_detalhe', pk=parcela.contrato.pk)

	try:
		pdf_bytes = imprimir_boleto(boleto)
	except SicrediError as e:
		messages.error(request, f'Erro ao imprimir boleto: {e}')
		return redirect('contrato_detalhe', pk=parcela.contrato.pk)

	response = HttpResponse(pdf_bytes, content_type='application/pdf')
	response['Content-Disposition'] = f'inline; filename="boleto-{boleto.nosso_numero}.pdf"'
	return response


@login_required
def boletos_carne(request, contrato_pk):
	from apps.contratos.models import Contrato
	contrato = get_object_or_404(Contrato, pk=contrato_pk)

	try:
		pdf_bytes = imprimir_carne_contrato(contrato)
	except SicrediError as e:
		messages.error(request, f'Erro ao gerar carnê: {e}')
		return redirect('contrato_detalhe', pk=contrato.pk)

	response = HttpResponse(pdf_bytes, content_type='application/pdf')
	response['Content-Disposition'] = f'inline; filename="carne-contrato-{contrato.pk}.pdf"'
	return response


@login_required
@require_POST
def boletos_gerar_lote(request, contrato_pk):
	from apps.contratos.models import Contrato
	contrato = get_object_or_404(Contrato, pk=contrato_pk)

	if not get_config_tenant():
		messages.error(request, 'Integração Sicredi não configurada/ativa. Acesse Configurações → Sicredi.')
		return redirect('contrato_detalhe', pk=contrato.pk)

	resultado = gerar_boletos_lote(contrato)
	gerados, falhas = resultado['gerados'], resultado['falhas']

	if gerados:
		messages.success(request, f'{gerados} boleto(s) gerado(s) com sucesso.')
	if falhas:
		detalhe = '; '.join(f'parcela {p.numero}: {msg}' for p, msg in falhas)
		messages.error(request, f'{len(falhas)} parcela(s) falharam: {detalhe}')
	if not gerados and not falhas:
		messages.warning(request, 'Nenhuma parcela pendente sem boleto encontrada.')

	return redirect('contrato_detalhe', pk=contrato.pk)


# ── Webhook público (chamado pelo Sicredi) ────────────────────────────────────

@csrf_exempt
def webhook_sicredi(request, secret):
	"""
	Endpoint público de eventos do Sicredi. Roda no schema public.
	Regra do Sicredi: responder SEMPRE HTTP 200 em até 10s, mesmo em erro
	interno (apenas loga). A Sicredi não envia nenhum header de autenticação
	nesta versão da API — por isso o secret vai embutido no path da própria
	URL cadastrada no portal deles (ver `config_sicredi` pra URL exibida).

	A validação do `secret` é aplicada conforme o ambiente:
	- Produção (DEBUG=False): ConfigSicredi.webhook_secret é OBRIGATÓRIO;
	  sem ele, ou com secret da URL não batendo, a requisição é rejeitada
	  com 401 (WebhookAuthError) — foge da regra de sempre-200, pois é
	  rejeição de autenticação, não falha de processamento do evento.
	- Dev/teste (DEBUG=True): secret opcional, comportamento antigo mantido.
	"""
	if request.method != 'POST':
		return HttpResponse(status=405)

	try:
		payload = json.loads(request.body or b'{}')
		processar_webhook(payload, secret=secret)
	except json.JSONDecodeError:
		logger.warning('Webhook Sicredi: corpo não é JSON válido')
	except WebhookAuthError:
		logger.warning('Webhook Sicredi: requisição rejeitada (autenticação)')
		return HttpResponse(status=401)
	except Exception:  # noqa: BLE001 — nunca derruba a resposta (regra Sicredi)
		logger.exception('Webhook Sicredi: erro ao processar evento')

	return HttpResponse(status=200)
