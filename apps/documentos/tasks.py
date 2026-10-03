"""
apps/documentos/tasks.py
Geração de PDF a partir de modelos .docx (docxtpl + LibreOffice) na fila `docx`.
Usa TenantTask como base: o 1º argumento é sempre o schema_name e a task roda
dentro do schema_context correspondente.
"""
import logging

import sentry_sdk
from celery import shared_task
from django.core.files.base import ContentFile

from config.celery import TenantTask

from .models import ContratoDocumentoGerado
from .services import (
	ConversaoDocxErro,
	ModeloDocxInvalido,
	construir_contexto,
	converter_docx_para_pdf,
	renderizar_docx,
)

logger = logging.getLogger(__name__)

# soffice tem timeout próprio (DOCUMENTO_SOFFICE_TIMEOUT=60); os limites da task
# cobrem render + storage + conversão.
SOFT_TIME_LIMIT = 90
TIME_LIMIT = 100

ERRO_GENERICO = 'Falha ao gerar o documento. Tente novamente ou contate o suporte.'


# typing=False: o schema_name é consumido por TenantTask.__call__ e não consta na
# assinatura; sem isso o check_arguments do .delay() rejeita a chamada.
@shared_task(
	base=TenantTask, bind=True, max_retries=0, typing=False,
	soft_time_limit=SOFT_TIME_LIMIT, time_limit=TIME_LIMIT,
)
def gerar_documento_docx(self, documento_id):
	try:
		documento = ContratoDocumentoGerado.objects.select_related(
			'modelo', 'contrato__imovel__proprietario', 'contrato__inquilino',
		).get(pk=documento_id)
	except ContratoDocumentoGerado.DoesNotExist:
		logger.error('Documento %s não existe — geração abortada', documento_id)
		return

	documento.status = 'processando'
	documento.erro_msg = ''
	documento.save(update_fields=['status', 'erro_msg'])

	try:
		contexto = construir_contexto(documento.contrato)
		docx_bytes = renderizar_docx(documento.modelo, contexto)
		pdf_bytes = converter_docx_para_pdf(docx_bytes)

		documento.arquivo_pdf.save('documento.pdf', ContentFile(pdf_bytes), save=False)
		documento.status = 'gerado'
		documento.save()
	except Exception as exc:
		if isinstance(exc, (ConversaoDocxErro, ModeloDocxInvalido)):
			msg = str(exc)
		else:
			msg = ERRO_GENERICO
		logger.exception('Falha ao gerar documento %s', documento_id)
		sentry_sdk.capture_exception(exc)
		documento.status = 'erro'
		documento.erro_msg = msg
		documento.save(update_fields=['status', 'erro_msg'])
