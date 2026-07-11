"""
apps/contratos/services.py
Logica de negocio de Contrato/Parcela compartilhada entre apps -- hoje so o
estorno de pagamento, usado tanto pelo botao manual (views.parcela_estornar)
quanto pelo webhook Sicredi (apps.sicredi.service._registrar_estorno).
"""
import logging

logger = logging.getLogger('apps.contratos')


def estornar_parcela(parcela, motivo=''):
    """
    Reverte o pagamento de uma parcela: zera status/data de pagamento da
    parcela, reverte o boleto (se houver) e cancela o Lancamento de receita
    gerado. Ponto unico de estorno -- evita deixar o Lancamento orfao (com
    status='realizado') quando o estorno acontece fora do webhook Sicredi.
    """
    from apps.financeiro.models import Lancamento

    boleto = getattr(parcela, 'boleto', None)
    if boleto is not None:
        boleto.status = 'emitido'
        boleto.valor_pago = None
        boleto.pago_em = None
        boleto.save(update_fields=['status', 'valor_pago', 'pago_em', 'atualizado_em'])

    parcela.status = 'pendente'
    parcela.data_pagamento = None
    parcela.save(update_fields=['status', 'data_pagamento'])

    Lancamento.objects.filter(parcela=parcela, tipo='receita').update(status='cancelado')

    logger.info('Estorno aplicado na parcela %s%s', parcela.pk, f' ({motivo})' if motivo else '')
