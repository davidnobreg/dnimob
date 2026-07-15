import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class ModeloDocumento(models.Model):
    TIPO_CHOICES = [
        ('contrato', 'Contrato de Locação'),
        ('distrato', 'Distrato'),
        ('recibo', 'Recibo de Pagamento'),
        ('outro', 'Outro'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField('Título', max_length=200)
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default='outro')
    conteudo_html = models.TextField('Conteúdo', blank=True, default='')
    ativo = models.BooleanField('Ativo', default=True)
    padrao = models.BooleanField(
        'Padrão do sistema', default=False,
        help_text='Modelos padrão não podem ser excluídos, apenas editados.'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modelo de Documento'
        verbose_name_plural = 'Modelos de Documento'
        ordering = ['tipo', 'titulo']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.titulo}'


class ModeloDocumentoHistorico(models.Model):
    modelo = models.ForeignKey(ModeloDocumento, on_delete=models.CASCADE, related_name='historico')
    conteudo_html = models.TextField()
    salvo_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Histórico de Modelo'
        verbose_name_plural = 'Histórico de Modelos'
        ordering = ['-salvo_em']

    def __str__(self):
        return f'Histórico {self.modelo_id} — {self.salvo_em:%d/%m/%Y %H:%M}'


class VariavelDocumento(models.Model):
    CATEGORIA_CHOICES = [
        ('inquilino', 'Inquilino'),
        ('imovel', 'Imóvel'),
        ('contrato', 'Contrato'),
        ('proprietario', 'Proprietário'),
        ('fiador', 'Fiador'),
        ('data', 'Data'),
    ]

    slug = models.CharField('Slug', max_length=100, unique=True)
    label = models.CharField('Nome amigável', max_length=200)
    categoria = models.CharField('Categoria', max_length=20, choices=CATEGORIA_CHOICES)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Variável de Documento'
        verbose_name_plural = 'Variáveis de Documento'
        ordering = ['categoria', 'label']

    def __str__(self):
        return f'{{{{ {self.slug} }}}} — {self.label}'


class ContratoDocumentoGerado(models.Model):
    STATUS_CHOICES = [
        ('gerado', 'Gerado'),
        ('erro', 'Erro na geração'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contrato = models.ForeignKey(
        'contratos.Contrato', on_delete=models.CASCADE, related_name='documentos_gerados'
    )
    modelo = models.ForeignKey(
        ModeloDocumento, on_delete=models.SET_NULL, null=True, related_name='documentos_gerados'
    )
    titulo = models.CharField('Título', max_length=200)
    conteudo_final_html = models.TextField('Conteúdo renderizado')
    arquivo_pdf = models.FileField(
        'PDF', upload_to='documentos/contratos/%Y/%m/', null=True, blank=True
    )
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='gerado')
    gerado_em = models.DateTimeField(auto_now_add=True)
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = 'Documento Gerado'
        verbose_name_plural = 'Documentos Gerados'
        ordering = ['-gerado_em']

    def __str__(self):
        return f'{self.titulo} — Contrato {self.contrato_id}'
