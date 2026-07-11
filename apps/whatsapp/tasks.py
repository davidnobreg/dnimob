"""
Tasks Celery para envios WhatsApp agendados.

Celery Beat executa `verificar_lembretes` e `verificar_vencidas`
diariamente (configure em CELERY_BEAT_SCHEDULE no settings).

Tasks assíncronas (`task_contrato_criado`, `task_pagamento_confirmado`)
são disparadas por signals.
"""
import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)


# ─── Agendadas via Celery Beat ────────────────────────────────────────────────

@shared_task(name='whatsapp.verificar_lembretes')
def verificar_lembretes():
    """
    Roda diariamente.
    Envia lembrete para parcelas que vencem em DIAS_ANTECEDENCIA dias.
    """
    DIAS_ANTECEDENCIA = 3
    data_alvo = date.today() + timedelta(days=DIAS_ANTECEDENCIA)

    TenantModel = get_tenant_model()
    tenants = TenantModel.objects.exclude(schema_name='public')

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            _enviar_lembretes_tenant(data_alvo)


def _enviar_lembretes_tenant(data_alvo: date):
    from apps.contratos.models import Parcela
    from apps.whatsapp.models import LogMensagem
    from apps.whatsapp.services import notificar_lembrete_vencimento

    parcelas = Parcela.objects.filter(
        data_vencimento=data_alvo,
        status='pendente',
    ).select_related('contrato__inquilino', 'contrato__imovel')

    for parcela in parcelas:
        # Evita reenvio se já enviou lembrete para esta parcela hoje
        ja_enviou = LogMensagem.objects.filter(
            evento=LogMensagem.Evento.PARCELA_LEMBRETE,
            parcela_id=parcela.pk,
            enviado_em__date=date.today(),
            status=LogMensagem.Status.ENVIADO,
        ).exists()

        if not ja_enviou:
            notificar_lembrete_vencimento(parcela)


@shared_task(name='whatsapp.verificar_vencidas')
def verificar_vencidas():
    """
    Roda diariamente.
    Envia cobrança para parcelas vencidas há 3, 7 e 15 dias.
    """
    DIAS_PARA_COBRAR = [3, 7, 15]
    hoje = date.today()

    TenantModel = get_tenant_model()
    tenants = TenantModel.objects.exclude(schema_name='public')

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            for dias in DIAS_PARA_COBRAR:
                data_alvo = hoje - timedelta(days=dias)
                _enviar_cobrancas_tenant(data_alvo)


def _enviar_cobrancas_tenant(data_venc: date):
    from apps.contratos.models import Parcela
    from apps.whatsapp.models import LogMensagem
    from apps.whatsapp.services import notificar_parcela_vencida

    parcelas = Parcela.objects.filter(
        data_vencimento=data_venc,
        status='atrasado',
    ).select_related('contrato__inquilino', 'contrato__imovel')

    for parcela in parcelas:
        ja_enviou_hoje = LogMensagem.objects.filter(
            evento=LogMensagem.Evento.PARCELA_VENCIDA,
            parcela_id=parcela.pk,
            enviado_em__date=date.today(),
            status=LogMensagem.Status.ENVIADO,
        ).exists()

        if not ja_enviou_hoje:
            notificar_parcela_vencida(parcela)


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
