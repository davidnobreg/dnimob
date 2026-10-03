import json
import logging
from datetime import timedelta

import sentry_sdk
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db import connection, transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from apps.contratos.models import Contrato

from .forms import ModeloDocumentoUploadForm, SubstituirArquivoModeloForm
from .models import (
	ContratoDocumentoGerado,
	ModeloDocumento,
	ModeloDocumentoHistorico,
	VariavelDocumento,
)
from .services import (
	MODELOS_PADRAO_DOCX,
	RE_TAG_PROIBIDA,
	caminho_modelo_padrao_docx,
	salvar_documento_gerado,
)
from .tasks import gerar_documento_docx

logger = logging.getLogger(__name__)

TIMEOUT_GERACAO = timedelta(minutes=5)
ERRO_ENFILEIRAR = 'Serviço de geração indisponível no momento. Tente novamente em instantes.'
CONTENT_TYPE_DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def _render_lista(request, form_novo=None):
	return render(request, 'documentos/lista_modelos.html', {
		'modelos': ModeloDocumento.objects.filter(ativo=True),
		'form_novo': form_novo or ModeloDocumentoUploadForm(),
		'abrir_modal': form_novo is not None,
		'max_mb': settings.DOCUMENTO_MODELO_MAX_MB,
	})


def _avisar_desconhecidas(request, analise):
	desconhecidas = analise['desconhecidas']
	if not desconhecidas:
		return
	nomes = ', '.join(desconhecidas[:10])
	extra = f' e mais {len(desconhecidas) - 10}' if len(desconhecidas) > 10 else ''
	messages.warning(
		request,
		f'Variáveis fora do catálogo (não serão preenchidas): {nomes}{extra}.',
	)


@login_required
def lista_modelos(request):
	return _render_lista(request)


@login_required
def variaveis_documento(request):
	variaveis = VariavelDocumento.objects.filter(ativo=True).order_by('categoria', 'label')
	rotulos = dict(VariavelDocumento.CATEGORIA_CHOICES)
	grupos = {}
	for variavel in variaveis:
		grupos.setdefault(variavel.categoria, []).append(variavel)
	categorias = [
		{'chave': chave, 'rotulo': rotulos.get(chave, chave), 'variaveis': itens}
		for chave, itens in grupos.items()
	]
	exemplos = [
		{'tipo': tipo, 'titulo': dados['titulo'], 'url': reverse('documentos:download_modelo_exemplo', args=[tipo])}
		for tipo, dados in MODELOS_PADRAO_DOCX.items()
	]
	return render(request, 'documentos/variaveis.html', {'categorias': categorias, 'exemplos': exemplos})


@login_required
@require_GET
def download_modelo_exemplo(request, tipo):
	# `tipo` só vale se for chave da lista fixa; o caminho vem do pacote, nunca da URL.
	if tipo not in MODELOS_PADRAO_DOCX:
		raise Http404('Modelo de exemplo inexistente.')
	caminho = caminho_modelo_padrao_docx(tipo)
	return FileResponse(
		open(caminho, 'rb'),
		as_attachment=True,
		filename=caminho.name,
		content_type=CONTENT_TYPE_DOCX,
	)


@login_required
@require_POST
def criar_modelo(request):
	form = ModeloDocumentoUploadForm(request.POST, request.FILES)
	if not form.is_valid():
		return _render_lista(request, form_novo=form)
	modelo = form.save()
	messages.success(request, f'Modelo "{modelo.titulo}" criado.')
	_avisar_desconhecidas(request, form.analise)
	return redirect('documentos:lista_modelos')


@login_required
@require_POST
def definir_predefinido(request, pk):
	with transaction.atomic():
		modelo = get_object_or_404(ModeloDocumento.objects.select_for_update(), pk=pk)
		if not modelo.ativo or not modelo.arquivo:
			messages.error(request, 'Só modelos ativos com arquivo .docx podem ser o padrão da imobiliária.')
			return redirect('documentos:lista_modelos')
		ModeloDocumento.objects.filter(tipo=modelo.tipo, predefinido=True).exclude(pk=modelo.pk).update(predefinido=False)
		if not modelo.predefinido:
			modelo.predefinido = True
			modelo.save(update_fields=['predefinido'])
	messages.success(request, f'"{modelo.titulo}" definido como padrão para {modelo.get_tipo_display()}.')
	return redirect('documentos:lista_modelos')


@login_required
def download_modelo(request, pk):
	modelo = get_object_or_404(ModeloDocumento, pk=pk)
	if not modelo.arquivo:
		raise Http404('Modelo sem arquivo.')

	arquivo = modelo.arquivo.storage.open(modelo.arquivo.name, 'rb')
	nome = f'{slugify(modelo.titulo) or "modelo"}.docx'
	return FileResponse(
		arquivo,
		as_attachment=True,
		filename=nome,
		content_type=CONTENT_TYPE_DOCX,
	)


@login_required
@require_POST
def substituir_arquivo_modelo(request, pk):
	modelo = get_object_or_404(ModeloDocumento, pk=pk)
	nome_antigo = modelo.arquivo.name if modelo.arquivo else ''
	storage = modelo.arquivo.storage

	form = SubstituirArquivoModeloForm(request.POST, request.FILES, instance=modelo)
	if not form.is_valid():
		for erro in form.errors.get('arquivo', []):
			messages.error(request, erro)
		return redirect('documentos:lista_modelos')

	modelo = form.save()
	if nome_antigo and nome_antigo != modelo.arquivo.name:
		try:
			storage.delete(nome_antigo)
		except Exception:
			logger.warning('Falha ao remover arquivo antigo do modelo %s: %s', modelo.pk, nome_antigo, exc_info=True)
	messages.success(request, f'Arquivo do modelo "{modelo.titulo}" substituído.')
	_avisar_desconhecidas(request, form.analise)
	return redirect('documentos:lista_modelos')


EXTENSOES_JS_EDITOR = [
	'documentos/js/editor/variavel-node.js',
	'documentos/js/editor/indent-attrs.js',
	'documentos/js/editor/font-attrs.js',
	'documentos/js/editor/line-height-attrs.js',
]


@login_required
def editor_modelo(request, pk):
	modelo = get_object_or_404(ModeloDocumento, pk=pk)
	variaveis = VariavelDocumento.objects.filter(ativo=True).order_by('categoria', 'label')

	extensoes_js = [caminho for caminho in EXTENSOES_JS_EDITOR if finders.find(caminho)]

	return render(request, 'documentos/editor_modelo.html', {
		'modelo': modelo,
		'variaveis': variaveis,
		'conteudo_html_json': mark_safe(json.dumps(modelo.conteudo_html)),
		'extensoes_js': extensoes_js,
	})


@login_required
@require_POST
def salvar_modelo(request, pk):
	modelo = get_object_or_404(ModeloDocumento, pk=pk)

	try:
		payload = json.loads(request.body)
	except json.JSONDecodeError:
		return JsonResponse({'ok': False, 'erro': 'JSON inválido.'}, status=400)

	conteudo_html = payload.get('conteudo_html', '')

	if RE_TAG_PROIBIDA.search(conteudo_html):
		return JsonResponse(
			{'ok': False, 'erro': 'O modelo contém tags de lógica não permitidas.'}, status=400
		)

	if conteudo_html != modelo.conteudo_html:
		ModeloDocumentoHistorico.objects.create(modelo=modelo, conteudo_html=modelo.conteudo_html)
		modelo.conteudo_html = conteudo_html
		modelo.save(update_fields=['conteudo_html', 'atualizado_em'])

	return JsonResponse({'ok': True})


@login_required
@require_POST
def gerar_documento(request):
	try:
		payload = json.loads(request.body)
	except json.JSONDecodeError:
		return JsonResponse({'erro': 'JSON inválido.'}, status=400)

	modelo = get_object_or_404(ModeloDocumento, pk=payload.get('modelo_id'), ativo=True)
	contrato = get_object_or_404(
		Contrato.objects.select_related('imovel', 'inquilino'),
		pk=payload.get('contrato_id'),
	)

	if modelo.arquivo:
		documento = ContratoDocumentoGerado.objects.create(
			contrato=contrato,
			modelo=modelo,
			titulo=f'{modelo.titulo} — Contrato {contrato.numero}',
			status='pendente',
			gerado_por=request.user,
		)
		try:
			gerar_documento_docx.delay(connection.schema_name, str(documento.pk))
		except Exception as exc:
			logger.exception('Falha ao enfileirar geração do documento %s', documento.pk)
			sentry_sdk.capture_exception(exc)
			documento.status = 'erro'
			documento.erro_msg = ERRO_ENFILEIRAR
			documento.save(update_fields=['status', 'erro_msg'])
			return JsonResponse({'erro': ERRO_ENFILEIRAR}, status=503)
		return JsonResponse(
			{'id': str(documento.pk), 'status_url': reverse('documentos:status_documento', args=[documento.pk])},
			status=202,
		)

	documento = salvar_documento_gerado(contrato, modelo, request.user)

	if not documento.arquivo_pdf:
		return JsonResponse({'erro': 'Falha ao gerar PDF.'}, status=500)

	response = HttpResponse(documento.arquivo_pdf.read(), content_type='application/pdf')
	response['Content-Disposition'] = f'attachment; filename="{documento.titulo}.pdf"'
	return response


@login_required
def download_documento(request, pk):
	documento = get_object_or_404(ContratoDocumentoGerado, pk=pk)

	if documento.status != 'gerado' or not documento.arquivo_pdf:
		raise Http404('Documento sem PDF gerado.')

	response = HttpResponse(documento.arquivo_pdf.read(), content_type='application/pdf')
	filename = documento.arquivo_pdf.name.rsplit('/', 1)[-1]
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


@login_required
@require_GET
def status_documento(request, pk):
	documento = get_object_or_404(ContratoDocumentoGerado, pk=pk)

	if documento.status in ('pendente', 'processando') and timezone.now() - documento.gerado_em > TIMEOUT_GERACAO:
		documento.status = 'erro'
		documento.erro_msg = 'Tempo esgotado na geração do documento.'
		documento.save(update_fields=['status', 'erro_msg'])

	download_url = None
	if documento.status == 'gerado' and documento.arquivo_pdf:
		download_url = reverse('documentos:download_documento', args=[documento.pk])

	return JsonResponse({'status': documento.status, 'erro': documento.erro_msg, 'download_url': download_url})


@login_required
def lista_documentos_contrato(request, contrato_pk):
	contrato = get_object_or_404(Contrato, pk=contrato_pk)
	documentos = contrato.documentos_gerados.select_related('modelo').all()

	return render(request, 'documentos/lista_documentos_contrato.html', {
		'contrato': contrato,
		'documentos': documentos,
	})
