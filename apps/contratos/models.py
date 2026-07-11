from django.db import models
from django.conf import settings
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal


class Contrato(models.Model):
    STATUS_CHOICES = [
        ('ativo',      'Ativo'),
        ('encerrado',  'Encerrado'),
        ('rescindido', 'Rescindido'),
        ('pendente',   'Pendente de Assinatura'),
    ]

    REAJUSTE_CHOICES = [
        ('igpm',  'IGP-M'),
        ('ipca',  'IPCA'),
        ('inpc',  'INPC'),
        ('fixo',  'Percentual Fixo'),
        ('nenhum','Sem Reajuste'),
    ]

    GARANTIA_CHOICES = [
        ('fiador',      'Fiador'),
        ('caucao',      'Caução (Depósito)'),
        ('seguro',      'Seguro Fiança'),
        ('titulo',      'Título de Capitalização'),
        ('nenhuma',     'Sem Garantia'),
    ]

    MESMO_MES = 'mesmo_mes'
    MES_ANTERIOR = 'mes_anterior'
    REGRA_COMPETENCIA_CHOICES = [
        (MESMO_MES,    'Mesmo mês do vencimento'),
        (MES_ANTERIOR, 'Mês anterior ao vencimento'),
    ]

    # Partes
    imovel    = models.ForeignKey('imoveis.Imovel',    on_delete=models.PROTECT, related_name='contratos', verbose_name='Imóvel')
    inquilino = models.ForeignKey('inquilinos.Inquilino', on_delete=models.PROTECT, related_name='contratos', verbose_name='Inquilino')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='contratos', verbose_name='Responsável')

    # Identificação
    numero    = models.CharField('Número do Contrato', max_length=30, unique=True)
    status    = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pendente')

    # Vigência
    data_inicio    = models.DateField('Início do Contrato')
    data_fim       = models.DateField('Fim do Contrato')
    data_assinatura = models.DateField('Data de Assinatura', null=True, blank=True)

    # Valores
    valor_aluguel  = models.DecimalField('Valor do Aluguel (R$)', max_digits=12, decimal_places=2)
    valor_condominio = models.DecimalField('Condomínio (R$)', max_digits=10, decimal_places=2, default=0)
    valor_iptu     = models.DecimalField('IPTU Mensal (R$)', max_digits=10, decimal_places=2, default=0)
    dia_vencimento = models.PositiveSmallIntegerField('Dia de Vencimento', default=10)
    regra_competencia = models.CharField('Regra de Competência', max_length=15,
                                          choices=REGRA_COMPETENCIA_CHOICES, default=MESMO_MES)

    # Reajuste
    indice_reajuste = models.CharField('Índice de Reajuste', max_length=10, choices=REAJUSTE_CHOICES, default='igpm')
    percentual_fixo = models.DecimalField('Percentual Fixo (%)', max_digits=5, decimal_places=2, default=0,
                                           help_text='Usado apenas quando índice = Percentual Fixo')
    periodicidade_reajuste = models.PositiveSmallIntegerField('Periodicidade (meses)', default=12)

    # Garantia
    tipo_garantia  = models.CharField('Tipo de Garantia', max_length=20, choices=GARANTIA_CHOICES, default='nenhuma')
    valor_caucao   = models.DecimalField('Valor Caução (R$)', max_digits=12, decimal_places=2, null=True, blank=True)

    # Multa rescisória
    multa_rescisao = models.DecimalField('Multa Rescisória (%)', max_digits=5, decimal_places=2, default=10)

    # Observações / cláusulas extras
    clausulas_adicionais = models.TextField('Cláusulas Adicionais', blank=True)
    observacoes          = models.TextField('Observações Internas', blank=True)

    # Controle
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering = ['-data_inicio']

    def __str__(self):
        return f'Contrato {self.numero} — {self.inquilino.nome}'

    @property
    def duracao_meses(self):
        delta = relativedelta(self.data_fim, self.data_inicio)
        return delta.months + delta.years * 12

    @property
    def valor_total_mensal(self):
        return self.valor_aluguel + self.valor_condominio + self.valor_iptu

    @property
    def esta_vigente(self):
        hoje = timezone.now().date()
        return self.status == 'ativo' and self.data_inicio <= hoje <= self.data_fim

    @property
    def dias_para_vencer(self):
        hoje = timezone.now().date()
        return (self.data_fim - hoje).days

    @property
    def status_badge(self):
        cores = {
            'ativo':      'green',
            'encerrado':  'gray',
            'rescindido': 'red',
            'pendente':   'yellow',
        }
        return cores.get(self.status, 'gray')

    def calcular_competencia(self, data_vencimento):
        """Retorna a competência (MM/YYYY) de uma parcela, conforme regra_competencia."""
        ref = data_vencimento
        if self.regra_competencia == self.MES_ANTERIOR:
            ref = ref - relativedelta(months=1)
        return ref.strftime('%m/%Y')

    def gerar_parcelas(self):
        """Gera os objetos Parcela para todo o período do contrato."""
        from dateutil.relativedelta import relativedelta
        parcelas = []
        data = self.data_inicio.replace(day=self.dia_vencimento)
        if data < self.data_inicio:
            data += relativedelta(months=1)
        mes = 1
        while data <= self.data_fim:
            parcelas.append(Parcela(
                contrato=self,
                numero=mes,
                data_vencimento=data,
                competencia=self.calcular_competencia(data),
                valor=self.valor_aluguel,
                valor_condominio=self.valor_condominio,
                valor_iptu=self.valor_iptu,
            ))
            data += relativedelta(months=1)
            mes += 1
        Parcela.objects.bulk_create(parcelas)
        return len(parcelas)

    def gerar_parcelas_a_partir_da_proxima(self):
        """
        Recalcula as parcelas do contrato após edição (datas, dia de vencimento
        ou valores alterados). Preserva o histórico: nunca recria o número de
        uma parcela já marcada como 'pago'.
        """
        from dateutil.relativedelta import relativedelta
        numeros_pagos = set(self.parcelas.filter(status='pago').values_list('numero', flat=True))

        parcelas = []
        data = self.data_inicio.replace(day=self.dia_vencimento)
        if data < self.data_inicio:
            data += relativedelta(months=1)
        mes = 1
        while data <= self.data_fim:
            if mes not in numeros_pagos:
                parcelas.append(Parcela(
                    contrato=self,
                    numero=mes,
                    data_vencimento=data,
                    competencia=self.calcular_competencia(data),
                    valor=self.valor_aluguel,
                    valor_condominio=self.valor_condominio,
                    valor_iptu=self.valor_iptu,
                ))
            data += relativedelta(months=1)
            mes += 1
        Parcela.objects.bulk_create(parcelas)
        return len(parcelas)


class Parcela(models.Model):
    STATUS_CHOICES = [
        ('pendente',  'Pendente'),
        ('pago',      'Pago'),
        ('atrasado',  'Atrasado'),
        ('cancelado', 'Cancelado'),
    ]

    contrato        = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='parcelas')
    numero          = models.PositiveSmallIntegerField('Nº Parcela')
    data_vencimento = models.DateField('Vencimento')
    competencia     = models.CharField('Competência', max_length=7, blank=True, default='')
    data_pagamento  = models.DateField('Data de Pagamento', null=True, blank=True)
    valor           = models.DecimalField('Aluguel (R$)', max_digits=12, decimal_places=2)
    valor_condominio = models.DecimalField('Condomínio (R$)', max_digits=10, decimal_places=2, default=0)
    valor_iptu      = models.DecimalField('IPTU (R$)', max_digits=10, decimal_places=2, default=0)
    valor_multa     = models.DecimalField('Multa (R$)', max_digits=10, decimal_places=2, default=0)
    valor_desconto  = models.DecimalField('Desconto (R$)', max_digits=10, decimal_places=2, default=0)
    status          = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pendente')
    observacao      = models.CharField('Observação', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Parcela'
        verbose_name_plural = 'Parcelas'
        ordering = ['data_vencimento']
        unique_together = [['contrato', 'numero']]

    def __str__(self):
        return f'Parcela {self.numero} — {self.contrato.numero}'

    @property
    def valor_total(self):
        return self.valor + self.valor_condominio + self.valor_iptu + self.valor_multa - self.valor_desconto

    @property
    def esta_atrasada(self):
        return self.status == 'pendente' and self.data_vencimento < timezone.now().date()

    def atualizar_status(self):
        if self.status == 'pendente' and self.data_vencimento < timezone.now().date():
            self.status = 'atrasado'
            self.save(update_fields=['status'])
