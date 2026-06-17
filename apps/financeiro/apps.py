# apps/financeiro/apps.py
from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.financeiro'
    verbose_name = 'Financeiro'

    def ready(self):
        import apps.financeiro.signals  # noqa


# ─────────────────────────────────────────────
# apps/financeiro/signals.py
# ─────────────────────────────────────────────
# Salve este conteúdo em apps/financeiro/signals.py:
#
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from apps.contratos.models import Parcela
# from .views import registrar_lancamento_parcela
#
# @receiver(post_save, sender=Parcela)
# def parcela_paga_signal(sender, instance, **kwargs):
#     if instance.status == 'pago' and instance.data_pagamento:
#         registrar_lancamento_parcela(instance)
