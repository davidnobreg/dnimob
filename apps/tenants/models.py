from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.utils import timezone
import uuid


class Plano(models.Model):
    BASICO = 'basico'
    PROFISSIONAL = 'profissional'
    ENTERPRISE = 'enterprise'

    PLANO_CHOICES = [
        (BASICO, 'Básico'),
        (PROFISSIONAL, 'Profissional'),
        (ENTERPRISE, 'Enterprise'),
    ]

    nome = models.CharField(max_length=50, choices=PLANO_CHOICES, unique=True)
    limite_imoveis = models.IntegerField(null=True, blank=True, help_text='None = ilimitado')
    limite_contratos = models.IntegerField(null=True, blank=True)
    limite_usuarios = models.IntegerField(null=True, blank=True)
    tem_whatsapp = models.BooleanField(default=False)
    preco_mensal = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'

    def __str__(self):
        return self.get_nome_display()


class Tenant(TenantMixin):
    """Representa uma imobiliária (tenant)."""

    # Dados da imobiliária
    nome = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18, blank=True)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    endereco = models.TextField(blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=9, blank=True)

    # Personalização visual
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    cor_primaria = models.CharField(max_length=7, default='#1a56db', help_text='Hex color')
    cor_secundaria = models.CharField(max_length=7, default='#1e429f')
    cor_acento = models.CharField(max_length=7, default='#3f83f8')

    # Plano e status
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, null=True)
    ativo = models.BooleanField(default=True)
    trial = models.BooleanField(default=True)
    trial_expira = models.DateField(null=True, blank=True)
    assinatura_expira = models.DateField(null=True, blank=True)

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    PROVISIONAMENTO_CHOICES = [
        ('pendente',      'Pendente'),
        ('provisionando', 'Provisionando'),
        ('pronto',        'Pronto'),
        ('erro',          'Erro'),
    ]
    provisionamento_status = models.CharField(
        max_length=20,
        choices=PROVISIONAMENTO_CHOICES,
        default='pendente',
    )

    auto_create_schema = True

    class Meta:
        verbose_name = 'Imobiliária'
        verbose_name_plural = 'Imobiliárias'

    def __str__(self):
        return self.nome

    @property
    def status_assinatura(self):
        hoje = timezone.now().date()
        if self.trial and self.trial_expira:
            if self.trial_expira >= hoje:
                return 'trial'
            return 'trial_expirado'
        if self.assinatura_expira and self.assinatura_expira < hoje:
            return 'expirado'
        return 'ativo'

    @property
    def acesso_permitido(self):
        return self.ativo and self.status_assinatura in ('trial', 'ativo')

    def tem_whatsapp(self):
        return self.plano and self.plano.tem_whatsapp

    def limite_imoveis(self):
        return self.plano.limite_imoveis if self.plano else 0

    def limite_usuarios(self):
        return self.plano.limite_usuarios if self.plano else 1


class Domain(DomainMixin):
    pass


class ConfigSicredi(models.Model):
    """
    Credenciais Sicredi (API Cobrança v3.9.1).

    Vive no schema public (app tenants é SHARED). O campo `schema_name`
    liga cada config ao tenant dono, permitindo o webhook (que não tem
    contexto de tenant) descobrir o schema pelo `codigo_beneficiario`.
    """

    # Credenciais legadas (fluxo client_credentials antigo — mantidas, sem uso novo)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=200, blank=True)

    # API v3.9.1 (OAuth2 password flow)
    api_key = models.CharField(
        'x-api-key', max_length=200, blank=True,
        help_text='client_id do Portal do Desenvolvedor Sicredi (header x-api-key)',
    )
    codigo_acesso = models.CharField(
        'Código de acesso', max_length=100, blank=True,
        help_text='Código de acesso gerado no Internet Banking (senha do token)',
    )
    codigo_beneficiario = models.CharField(
        'Código do beneficiário', max_length=20, blank=True, db_index=True,
        help_text='Código numérico do beneficiário (ex: 12345). Usado pelo webhook.',
    )

    cooperativa = models.CharField(max_length=4, help_text='Código da cooperativa (4 dígitos)')
    posto = models.CharField(max_length=2, help_text='Posto atendimento (2 dígitos)')
    conta = models.CharField(max_length=10, blank=True, help_text='Número da conta')
    beneficiario = models.CharField(max_length=200, help_text='Nome do beneficiário no boleto')
    ambiente = models.CharField(
        max_length=10,
        choices=[('sandbox', 'Sandbox'), ('producao', 'Produção')],
        default='sandbox',
    )

    # Roteamento de webhook (tenant dono desta config)
    schema_name = models.CharField(
        'Schema do tenant', max_length=63, blank=True, db_index=True,
        help_text='Schema do tenant dono desta config (preenchido ao salvar no schema do tenant)',
    )

    webhook_secret = models.CharField(max_length=100, blank=True, help_text='Secret HMAC do webhook (opcional)')
    ativo = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Config Sicredi'
        verbose_name_plural = 'Config Sicredi'
        constraints = [
            models.UniqueConstraint(
                fields=['codigo_beneficiario'],
                condition=~models.Q(codigo_beneficiario=''),
                name='unique_codigo_beneficiario_sicredi',
            ),
        ]

    def __str__(self):
        return f'Sicredi — {self.beneficiario} ({self.ambiente})'


class InstanciaWhatsApp(models.Model):
    """Instância Evolution API por tenant."""

    STATUS_CHOICES = [
        ('desconectado', 'Desconectado'),
        ('aguardando_qr', 'Aguardando QR Code'),
        ('conectado', 'Conectado'),
        ('erro', 'Erro'),
    ]

    evolution_url  = models.URLField(blank=True, default='', verbose_name='URL da Evolution API',
                                     help_text='URL base da Evolution API, ex: http://192.168.1.100:8080')
    nome_instancia = models.CharField(max_length=100, unique=True, help_text='ID único na Evolution API')
    token_api      = models.CharField(max_length=300, blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='desconectado')
    numero_telefone = models.CharField(max_length=20, blank=True, help_text='Número conectado')
    qr_code        = models.TextField(blank=True, help_text='Base64 do QR Code atual')
    qr_expira      = models.DateTimeField(null=True, blank=True)
    conectado_em   = models.DateTimeField(null=True, blank=True)
    criado_em      = models.DateTimeField(auto_now_add=True)
    atualizado_em  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Instância WhatsApp'
        verbose_name_plural = 'Instâncias WhatsApp'

    def __str__(self):
        return f'{self.nome_instancia} — {self.status}'

    @property
    def esta_conectado(self):
        return self.status == 'conectado'


class TemplateWhatsApp(models.Model):
    """Templates editáveis de mensagens WhatsApp."""

    EVENTO_CHOICES = [
        ('boas_vindas', 'Boas-vindas ao inquilino'),
        ('boleto_gerado', 'Boleto gerado'),
        ('vence_amanha', 'Boleto vence amanhã (D-1)'),
        ('vence_hoje', 'Boleto vence hoje (D+0)'),
        ('atraso_3', 'Atraso 3 dias'),
        ('atraso_7', 'Atraso 7 dias'),
        ('atraso_15', 'Atraso 15 dias'),
        ('pagamento_confirmado', 'Pagamento confirmado'),
        ('contrato_enviado', 'Contrato enviado'),
        ('contrato_60dias', 'Contrato vencendo em 60 dias'),
        ('contrato_30dias', 'Contrato vencendo em 30 dias'),
        ('distrato_enviado', 'Distrato enviado'),
        ('recibo_pagamento', 'Recibo de pagamento'),
    ]

    evento = models.CharField(max_length=30, choices=EVENTO_CHOICES, unique=True)
    ativo = models.BooleanField(default=True)
    mensagem = models.TextField(help_text='Use {variavel} para campos dinâmicos')
    variaveis_disponiveis = models.JSONField(default=list, help_text='Lista de variáveis permitidas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Template WhatsApp'
        verbose_name_plural = 'Templates WhatsApp'

    def __str__(self):
        return self.get_evento_display()
