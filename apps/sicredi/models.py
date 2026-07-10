from django.db import models


class Boleto(models.Model):
    STATUS_CHOICES = [
        ('emitido',   'Emitido'),
        ('pago',      'Pago'),
        ('vencido',   'Vencido'),
        ('cancelado', 'Cancelado'),
        ('erro',      'Erro'),
    ]

    parcela        = models.OneToOneField('contratos.Parcela', on_delete=models.CASCADE,
                                          related_name='boleto', verbose_name='Parcela')
    seu_numero     = models.CharField('Seu Número', max_length=30, blank=True,
                                      help_text='Controle interno (ex: CT0001-P03)')
    nosso_numero   = models.CharField('Nosso Número', max_length=20, unique=True)
    linha_digitavel = models.CharField('Linha Digitável', max_length=60, blank=True)
    codigo_barras  = models.CharField('Código de Barras', max_length=50, blank=True)
    txid           = models.CharField('TXID (PIX)', max_length=50, blank=True)
    qr_code        = models.TextField('QR Code (PIX)', blank=True)
    status         = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='emitido')
    valor_pago     = models.DecimalField('Valor Pago', max_digits=12, decimal_places=2, null=True, blank=True)
    pago_em        = models.DateField('Pago em', null=True, blank=True)
    erro_mensagem  = models.TextField('Mensagem de erro', blank=True)
    emitido_em     = models.DateTimeField('Emitido em', null=True, blank=True)
    atualizado_em  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Boleto'
        verbose_name_plural = 'Boletos'

    def __str__(self):
        return f'Boleto {self.nosso_numero} — {self.parcela}'
