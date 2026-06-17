"""
Signals da app whatsapp.
Conecta eventos de Contrato e Parcela às tasks Celery.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import connection

logger = logging.getLogger(__name__)


def _schema_name() -> str:
    return connection.schema_name


# ─── Contrato criado ──────────────────────────────────────────────────────────

def _on_contrato_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.whatsapp.tasks import task_contrato_criado
    try:
        task_contrato_criado.apply_async(
            args=[_schema_name(), instance.pk],
            countdown=5,  # aguarda 5s para garantir commit
        )
    except Exception as e:
        logger.error('Falha ao agendar task_contrato_criado para contrato %s: %s', instance.pk, e)


# ─── Pagamento confirmado ─────────────────────────────────────────────────────

def _on_parcela_post_save(sender, instance, **kwargs):
    """Dispara ao marcar parcela como paga."""
    if instance.status != 'pago':
        return

    # Verifica se acabou de ser pago (data_pagamento = hoje)
    from django.utils import timezone
    if instance.data_pagamento and instance.data_pagamento == timezone.now().date():
        from apps.whatsapp.tasks import task_pagamento_confirmado
        try:
            task_pagamento_confirmado.apply_async(
                args=[_schema_name(), instance.pk],
                countdown=3,
            )
        except Exception as e:
            logger.error('Falha ao agendar task_pagamento_confirmado para parcela %s: %s', instance.pk, e)


def connect_signals():
    """Chamado no AppConfig.ready()."""
    from apps.contratos.models import Contrato, Parcela
    post_save.connect(_on_contrato_post_save, sender=Contrato, weak=False)
    post_save.connect(_on_parcela_post_save,  sender=Parcela,  weak=False)
