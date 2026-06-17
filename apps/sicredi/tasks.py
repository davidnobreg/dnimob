"""
apps/sicredi/tasks.py
Tasks Celery da integração Sicredi. Fila: financeiro (ver CELERY_TASK_ROUTES).

Usa TenantTask como base: o 1º argumento é sempre o schema_name e a task
executa dentro do schema_context correspondente.
"""
import logging

from celery import shared_task

from config.celery import TenantTask
from .client import SicrediAuthError, SicrediError
from .service import gerar_boleto_parcela

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
