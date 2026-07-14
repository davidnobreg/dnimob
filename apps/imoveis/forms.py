from django import forms
from .models import Imovel, FotoImovel


ESTADOS_BR = [
    ('', 'Selecione...'),
    ('AC','AC'),('AL','AL'),('AP','AP'),('AM','AM'),('BA','BA'),
    ('CE','CE'),('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),
    ('MT','MT'),('MS','MS'),('MG','MG'),('PA','PA'),('PB','PB'),
    ('PR','PR'),('PE','PE'),('PI','PI'),('RJ','RJ'),('RN','RN'),
    ('RS','RS'),('RO','RO'),('RR','RR'),('SC','SC'),('SP','SP'),
    ('SE','SE'),('TO','TO'),
]


class ImovelForm(forms.ModelForm):
    class Meta:
        model = Imovel
        exclude = ['criado_em', 'atualizado_em']
        widgets = {
            'tipo':       forms.Select(attrs={'class': 'form-select'}),
            'finalidade': forms.Select(attrs={'class': 'form-select'}),
            'status':     forms.Select(attrs={'class': 'form-select'}),
            'mobilia':    forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'descricao':  forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica classe padrão nos inputs de texto/número
        text_fields = [
            'codigo','numero','nome_imovel','cep','logradouro','complemento','bairro',
            'cidade','area_util','area_privativa','area_total','area_construida','area_comum','quartos','suites',
            'banheiros','vagas','valor_aluguel','valor_venda',
            'valor_condominio','valor_iptu','proprietario_nome',
            'proprietario_cpf_cnpj','proprietario_telefone','proprietario_email',
        ]
        for field in text_fields:
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('class', 'form-input')

        self.fields['area_total'].widget.attrs.update({
            'readonly': True,
            'id': 'id_area_total',
            'class': 'form-input bg-gray-50 cursor-not-allowed text-gray-500',
            'tabindex': '-1',
        })
        self.fields['area_total'].required = False

        # Checkboxes (comodidades)
        checkbox_fields = [
            'piscina',
            'academia',
            'churrasqueira',
            'portaria',
            'elevador',
            'pet_friendly',
        ]
        for field in checkbox_fields:
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('class', 'form-checkbox')

        # Estado como select
        self.fields['estado'].widget = forms.Select(
            choices=ESTADOS_BR,
            attrs={'class': 'form-select'},
        )
        self.fields['codigo'].required = False
        self.fields['codigo'].widget.attrs['placeholder'] = 'Ex: IM-0001 — ou deixe em branco'

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '').upper().strip()
        if not codigo:
            return codigo
        qs = Imovel.objects.filter(codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um imóvel com este código.')
        return codigo

    def clean(self):
        cleaned = super().clean()
        finalidade = cleaned.get('finalidade')
        aluguel = cleaned.get('valor_aluguel')
        venda = cleaned.get('valor_venda')

        if finalidade in ('aluguel', 'ambos') and not aluguel:
            self.add_error('valor_aluguel', 'Informe o valor de aluguel.')
        if finalidade in ('venda', 'ambos') and not venda:
            self.add_error('valor_venda', 'Informe o valor de venda.')
        return cleaned


class FotoImovelForm(forms.ModelForm):
    class Meta:
        model = FotoImovel
        fields = ['imagem', 'legenda', 'principal', 'ordem']


class FiltroImovelForm(forms.Form):
    q          = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Código, bairro, cidade...',
        'class': 'form-input',
    }))
    tipo       = forms.ChoiceField(required=False, choices=[('', 'Todos os tipos')] + Imovel.TIPO_CHOICES,
                                   widget=forms.Select(attrs={'class': 'form-select'}))
    status     = forms.ChoiceField(required=False, choices=[('', 'Todos os status')] + Imovel.STATUS_CHOICES,
                                   widget=forms.Select(attrs={'class': 'form-select'}))
    finalidade = forms.ChoiceField(required=False, choices=[('', 'Todas as finalidades')] + Imovel.FINALIDADE_CHOICES,
                                   widget=forms.Select(attrs={'class': 'form-select'}))
    cidade     = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Cidade',
        'class': 'form-input',
    }))
