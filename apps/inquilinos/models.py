from django.db import models


class Inquilino(models.Model):
    TIPO_CHOICES = [
        ('pf', 'Pessoa Física'),
        ('pj', 'Pessoa Jurídica'),
    ]

    ESTADO_CIVIL_CHOICES = [
        ('solteiro',    'Solteiro(a)'),
        ('casado',      'Casado(a)'),
        ('divorciado',  'Divorciado(a)'),
        ('viuvo',       'Viúvo(a)'),
        ('uniao',       'União Estável'),
    ]

    STATUS_CHOICES = [
        ('ativo',       'Ativo'),
        ('inativo',     'Inativo'),
        ('inadimplente','Inadimplente'),
    ]

    # Tipo e identificação
    tipo          = models.CharField('Tipo', max_length=2, choices=TIPO_CHOICES, default='pf')
    status        = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='ativo')

    # Pessoa Física
    nome          = models.CharField('Nome Completo / Razão Social', max_length=200)
    cpf           = models.CharField('CPF', max_length=14, blank=True)
    rg            = models.CharField('RG', max_length=20, blank=True)
    data_nascimento = models.DateField('Data de Nascimento', null=True, blank=True)
    estado_civil  = models.CharField('Estado Civil', max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True)
    profissao     = models.CharField('Profissão', max_length=100, blank=True)
    renda_mensal  = models.DecimalField('Renda Mensal (R$)', max_digits=12, decimal_places=2, null=True, blank=True)
    nacionalidade = models.CharField('Nacionalidade', max_length=50, default='Brasileira', blank=True)

    # Pessoa Jurídica
    cnpj          = models.CharField('CNPJ', max_length=18, blank=True)
    razao_social  = models.CharField('Razão Social', max_length=200, blank=True)
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True)
    inscricao_estadual = models.CharField('Inscrição Estadual', max_length=30, blank=True)

    # Contato
    email         = models.EmailField('E-mail', blank=True)
    telefone      = models.CharField('Telefone / WhatsApp', max_length=20)
    telefone2     = models.CharField('Telefone 2', max_length=20, blank=True)

    # Endereço
    cep           = models.CharField('CEP', max_length=9, blank=True)
    logradouro    = models.CharField('Logradouro', max_length=200, blank=True)
    numero        = models.CharField('Número', max_length=10, blank=True)
    complemento   = models.CharField('Complemento', max_length=100, blank=True)
    bairro        = models.CharField('Bairro', max_length=100, blank=True)
    cidade        = models.CharField('Cidade', max_length=100, blank=True)
    estado        = models.CharField('Estado', max_length=2, blank=True)

    # Fiador / Garantia
    fiador_nome   = models.CharField('Nome do Fiador', max_length=200, blank=True)
    fiador_cpf    = models.CharField('CPF do Fiador', max_length=14, blank=True)
    fiador_telefone = models.CharField('Telefone do Fiador', max_length=20, blank=True)

    # Observações
    observacoes   = models.TextField('Observações', blank=True)
    foto          = models.ImageField('Foto', upload_to='inquilinos/fotos/', null=True, blank=True)

    # Controle
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Inquilino'
        verbose_name_plural = 'Inquilinos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def documento_principal(self):
        return self.cpf if self.tipo == 'pf' else self.cnpj

    @property
    def status_badge(self):
        cores = {
            'ativo':        'green',
            'inativo':      'gray',
            'inadimplente': 'red',
        }
        return cores.get(self.status, 'gray')
