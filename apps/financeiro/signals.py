from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.contratos.models import Parcela
from .views import registrar_lancamento_parcela


@receiver(post_save, sender=Parcela)
def parcela_paga_signal(sender, instance, **kwargs):
    """Cria lançamento de receita automaticamente quando parcela é paga."""
    if instance.status == 'pago' and instance.data_pagamento:
        registrar_lancamento_parcela(instance)
