from django.db import models
from django.conf import settings
from django.utils import timezone


class Lancamento(models.Model):
    """
    Lançamento financeiro manual ou gerado automaticamente por pagamento de parcela.
    Permite controle de caixa além dos contratos (ex: despesas da imobiliária).
    """
    TIPO_CHOICES = [
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
    ]

    CATEGORIA_CHOICES = [
        # Receitas
        ('aluguel',       'Aluguel'),
        ('condominio',    'Condomínio'),
        ('iptu',          'IPTU'),
        ('multa',         'Multa'),
        ('taxa_admin',    'Taxa de Administração'),
        ('outros_rec',    'Outras Receitas'),
        # Despesas
        ('manutencao',    'Manutenção'),
        ('comissao',      'Comissão'),
        ('despesa_adm',   'Despesa Administrativa'),
        ('imposto',       'Imposto'),
        ('outros_desp',   'Outras Despesas'),
    ]

    STATUS_CHOICES = [
        ('previsto',  'Previsto'),
        ('realizado', 'Realizado'),
        ('cancelado', 'Cancelado'),
    ]

    tipo        = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES)
    categoria   = models.CharField('Categoria', max_length=20, choices=CATEGORIA_CHOICES)
    status      = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='realizado')
    descricao   = models.CharField('Descrição', max_length=300)
    valor       = models.DecimalField('Valor (R$)', max_digits=12, decimal_places=2)
    data        = models.DateField('Data')
    data_prevista = models.DateField('Data Prevista', null=True, blank=True)

    # Vínculos opcionais
    contrato    = models.ForeignKey('contratos.Contrato', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='lancamentos',
                                    verbose_name='Contrato')
    parcela     = models.ForeignKey('contratos.Parcela', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='lancamentos',
                                    verbose_name='Parcela')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name='Responsável')

    observacao  = models.TextField('Observação', blank=True)
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento'
        verbose_name_plural = 'Lançamentos'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.descricao} — R$ {self.valor}'

    @property
    def is_receita(self):
        return self.tipo == 'receita'
