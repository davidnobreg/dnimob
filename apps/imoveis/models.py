from django.db import models
from django.conf import settings


class Imovel(models.Model):
    TIPO_CHOICES = [
        ('apartamento', 'Apartamento'),
        ('casa',        'Casa'),
        ('comercial',   'Comercial'),
        ('terreno',     'Terreno'),
        ('rural',       'Rural'),
        ('sala',        'Sala/Escritório'),
        ('galpao',      'Galpão'),
        ('outro',       'Outro'),
    ]

    STATUS_CHOICES = [
        ('disponivel',  'Disponível'),
        ('alugado',     'Alugado'),
        ('vendido',     'Vendido'),
        ('manutencao',  'Em Manutenção'),
        ('inativo',     'Inativo'),
    ]

    FINALIDADE_CHOICES = [
        ('aluguel', 'Aluguel'),
        ('venda',   'Venda'),
        ('ambos',   'Aluguel e Venda'),
    ]

    MOBILIA_CHOICES = [
        ('sem',          'Sem Mobília'),
        ('semi',         'Semi-Mobiliado'),
        ('mobiliado',    'Mobiliado'),
    ]

    # Identificação
    codigo        = models.CharField('Código', max_length=20, unique=True)
    numero        = models.CharField('Número', max_length=10)
    nome_imovel   = models.CharField('Nome do Imóvel', max_length=150, blank=True)
    tipo          = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    finalidade    = models.CharField('Finalidade', max_length=10, choices=FINALIDADE_CHOICES, default='aluguel')
    status        = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='disponivel')

    # Localização
    cep           = models.CharField('CEP', max_length=9)
    logradouro    = models.CharField('Logradouro', max_length=200)
    complemento   = models.CharField('Complemento', max_length=100, blank=True)
    bairro        = models.CharField('Bairro', max_length=100)
    cidade        = models.CharField('Cidade', max_length=100)
    estado        = models.CharField('Estado', max_length=2)

    # Características
    area_util       = models.DecimalField('Área Útil / de Piso', max_digits=10, decimal_places=2, null=True, blank=True)
    area_privativa  = models.DecimalField('Área Privativa', max_digits=10, decimal_places=2, null=True, blank=True)
    area_total      = models.DecimalField('Área Total (m²)', max_digits=10, decimal_places=2, null=True, blank=True)
    area_construida = models.DecimalField('Área Construída (m²)', max_digits=10, decimal_places=2, null=True, blank=True)
    area_comum      = models.DecimalField('Área Comum', max_digits=10, decimal_places=2, null=True, blank=True)
    quartos       = models.PositiveSmallIntegerField('Quartos', default=0)
    suites        = models.PositiveSmallIntegerField('Suítes', default=0)
    banheiros     = models.PositiveSmallIntegerField('Banheiros', default=1)
    vagas         = models.PositiveSmallIntegerField('Vagas de Garagem', default=0)
    mobilia       = models.CharField('Mobília', max_length=20, choices=MOBILIA_CHOICES, default='sem')

    # Comodidades (booleanos)
    piscina       = models.BooleanField('Piscina', default=False)
    academia      = models.BooleanField('Academia', default=False)
    churrasqueira = models.BooleanField('Churrasqueira', default=False)
    portaria      = models.BooleanField('Portaria 24h', default=False)
    elevador      = models.BooleanField('Elevador', default=False)
    pet_friendly  = models.BooleanField('Aceita Pet', default=False)

    # Valores
    valor_aluguel = models.DecimalField('Valor Aluguel (R$)', max_digits=12, decimal_places=2, null=True, blank=True)
    valor_venda   = models.DecimalField('Valor Venda (R$)', max_digits=14, decimal_places=2, null=True, blank=True)
    valor_condominio = models.DecimalField('Condomínio (R$)', max_digits=10, decimal_places=2, default=0)
    valor_iptu    = models.DecimalField('IPTU Mensal (R$)', max_digits=10, decimal_places=2, default=0)

    # Proprietário
    proprietario_nome   = models.CharField('Nome do Proprietário', max_length=200)
    proprietario_cpf_cnpj = models.CharField('CPF/CNPJ', max_length=18, blank=True)
    proprietario_telefone = models.CharField('Telefone', max_length=20, blank=True)
    proprietario_email    = models.EmailField('E-mail', blank=True)

    # Observações
    descricao     = models.TextField('Descrição/Observações', blank=True)

    # Controle
    responsavel   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Responsável',
        related_name='imoveis',
    )
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Imóvel'
        verbose_name_plural = 'Imóveis'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.codigo} — {self.logradouro}, {self.numero} ({self.cidade}/{self.estado})'

    def get_endereco_completo(self):
        partes = [self.logradouro, self.numero]
        if self.complemento:
            partes.append(self.complemento)
        partes += [self.bairro, self.cidade, self.estado]
        return ', '.join(partes)

    @property
    def status_badge(self):
        cores = {
            'disponivel': 'green',
            'alugado':    'blue',
            'vendido':    'purple',
            'manutencao': 'yellow',
            'inativo':    'gray',
        }
        return cores.get(self.status, 'gray')

    @staticmethod
    def _gerar_codigo() -> str:
        import re
        ultimo = Imovel.objects.order_by('-id').first()
        proximo = 1
        if ultimo:
            match = re.search(r'(\d+)$', ultimo.codigo)
            proximo = int(match.group(1)) + 1 if match else Imovel.objects.count() + 1
        while True:
            codigo = f'IM-{proximo:04d}'
            if not Imovel.objects.filter(codigo=codigo).exists():
                return codigo
            proximo += 1

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo()
        self.area_total = sum(
            v for v in [self.area_util, self.area_privativa, self.area_construida, self.area_comum]
            if v is not None
        ) or None
        super().save(*args, **kwargs)


class FotoImovel(models.Model):
    imovel    = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='fotos')
    imagem    = models.ImageField('Imagem', upload_to='imoveis/fotos/')
    legenda   = models.CharField('Legenda', max_length=200, blank=True)
    principal = models.BooleanField('Foto Principal', default=False)
    ordem     = models.PositiveSmallIntegerField('Ordem', default=0)

    class Meta:
        verbose_name = 'Foto do Imóvel'
        verbose_name_plural = 'Fotos do Imóvel'
        ordering = ['ordem', 'id']

    def save(self, *args, **kwargs):
        # Garante apenas uma foto principal por imóvel
        if self.principal:
            FotoImovel.objects.filter(imovel=self.imovel, principal=True).exclude(pk=self.pk).update(principal=False)
        super().save(*args, **kwargs)
