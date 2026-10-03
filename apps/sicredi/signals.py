"""
apps/sicredi/signals.py
Dispara geração automática de boleto quando uma Parcela é criada,
somente se houver ConfigSicredi ativa para o tenant.
"""
import logging

import sentry_sdk
from django.db import connection
from django.db.models.signals import post_save

logger = logging.getLogger('apps.sicredi')


def _on_parcela_created(sender, instance, created, **kwargs):
	if not created:
		return

	from apps.tenants.models import ConfigSicredi

	schema = connection.schema_name
	if not ConfigSicredi.objects.filter(schema_name=schema, ativo=True).exists():
		return

	from apps.sicredi.tasks import gerar_boleto_parcela_task
	try:
		gerar_boleto_parcela_task.apply_async(
			args=[schema, instance.pk],
			countdown=10,  # aguarda commit da parcela/contrato
		)
		logger.info('Sicredi: boleto agendado para parcela %s (schema=%s)', instance.pk, schema)
	except Exception as exc:
		logger.exception('Falha ao agendar gerar_boleto_parcela_task para parcela %s (schema=%s)', instance.pk, schema)
		sentry_sdk.capture_exception(exc)


def connect_signals():
	"""Chamado no AppConfig.ready()."""
	from apps.contratos.models import Parcela
	post_save.connect(
		_on_parcela_created, sender=Parcela, weak=False,
		dispatch_uid='sicredi_parcela_boleto',
	)
