import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contratos.models import Contrato

from .models import (
	ContratoDocumentoGerado,
	ModeloDocumento,
	ModeloDocumentoHistorico,
	VariavelDocumento,
)
from .services import RE_TAG_PROIBIDA, salvar_documento_gerado


@login_required
def lista_modelos(request):
	modelos = ModeloDocumento.objects.filter(ativo=True)
	return render(request, 'documentos/lista_modelos.html', {'modelos': modelos})


@login_required
def editor_modelo(request, pk):
	modelo = get_object_or_404(ModeloDocumento, pk=pk)

	variaveis_por_categoria = {}
	for variavel in VariavelDocumento.objects.filter(ativo=True).order_by('categoria', 'label'):
		variaveis_por_categoria.setdefault(variavel.categoria, []).append(variavel)

	return render(request, 'documentos/editor_modelo.html', {
		'modelo': modelo,
		'variaveis_por_categoria': variaveis_por_categoria,
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
	modelo = get_object_or_404(ModeloDocumento, pk=request.POST.get('modelo_id'))
	contrato = get_object_or_404(
		Contrato.objects.select_related('imovel', 'inquilino'),
		pk=request.POST.get('contrato_id'),
	)

	documento = salvar_documento_gerado(contrato, modelo, request.user)

	return redirect('documentos:download_documento', pk=documento.pk)


@login_required
def download_documento(request, pk):
	documento = get_object_or_404(ContratoDocumentoGerado, pk=pk)

	if not documento.arquivo_pdf:
		raise Http404('Documento sem PDF gerado.')

	response = HttpResponse(documento.arquivo_pdf.read(), content_type='application/pdf')
	filename = documento.arquivo_pdf.name.rsplit('/', 1)[-1]
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


@login_required
def lista_documentos_contrato(request, contrato_pk):
	contrato = get_object_or_404(Contrato, pk=contrato_pk)
	documentos = contrato.documentos_gerados.select_related('modelo').all()

	return render(request, 'documentos/lista_documentos_contrato.html', {
		'contrato': contrato,
		'documentos': documentos,
	})
