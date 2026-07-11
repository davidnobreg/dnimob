"""
Tasks Celery para envios WhatsApp.

Os agendamentos diários (lembrete de vencimento, cobrança de atraso) vivem
em apps.financeiro.tasks (disparar_todos_tenants) — não duplicar aqui.

Tasks assíncronas (`task_contrato_criado`, `task_pagamento_confirmado`)
são disparadas por signals.
"""
import logging

from celery import shared_task
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


# ─── Disparadas por signals ────────────────────────────────────────────────────

@shared_task(name='whatsapp.task_contrato_criado')
def task_contrato_criado(schema_name: str, contrato_id: int):
    """Dispara ao criar contrato (via signal)."""
    from apps.contratos.models import Contrato
    from apps.whatsapp.services import notificar_contrato_criado

    with schema_context(schema_name):
        try:
            contrato = Contrato.objects.select_related(
                'inquilino', 'imovel'
            ).get(pk=contrato_id)
            notificar_contrato_criado(contrato)
        except Contrato.DoesNotExist:
            logger.warning('Contrato %s não encontrado no schema %s', contrato_id, schema_name)


@shared_task(name='whatsapp.task_pagamento_confirmado')
def task_pagamento_confirmado(schema_name: str, parcela_id: int):
    """Dispara ao registrar pagamento de parcela (via signal)."""
    from apps.contratos.models import Parcela
    from apps.whatsapp.services import notificar_pagamento_confirmado

    with schema_context(schema_name):
        try:
            parcela = Parcela.objects.select_related(
                'contrato__inquilino', 'contrato__imovel'
            ).get(pk=parcela_id)
            notificar_pagamento_confirmado(parcela)
        except Parcela.DoesNotExist:
            logger.warning('Parcela %s não encontrada no schema %s', parcela_id, schema_name)
