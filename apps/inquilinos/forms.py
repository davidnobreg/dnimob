from django import forms
from .models import Inquilino


ESTADOS_BR = [
    ('', 'Selecione...'),
    ('AC','AC'),('AL','AL'),('AP','AP'),('AM','AM'),('BA','BA'),
    ('CE','CE'),('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),
    ('MT','MT'),('MS','MS'),('MG','MG'),('PA','PA'),('PB','PB'),
    ('PR','PR'),('PE','PE'),('PI','PI'),('RJ','RJ'),('RN','RN'),
    ('RS','RS'),('RO','RO'),('RR','RR'),('SC','SC'),('SP','SP'),
    ('SE','SE'),('TO','TO'),
]


class InquilinoForm(forms.ModelForm):
    class Meta:
        model = Inquilino
        exclude = ['criado_em', 'atualizado_em']
        widgets = {
            'tipo':         forms.Select(attrs={'class': 'form-select'}),
            'status':       forms.Select(attrs={'class': 'form-select'}),
            'estado_civil': forms.Select(attrs={'class': 'form-select'}),
            'data_nascimento': forms.DateInput(
                attrs={'class': 'form-input', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'observacoes':  forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'foto':         forms.FileInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_nascimento'].input_formats = ['%Y-%m-%d']
        if self.instance.pk and self.instance.data_nascimento:
            self.initial['data_nascimento'] = self.instance.data_nascimento.strftime('%Y-%m-%d')
        text_fields = [
            'nome','cpf','rg','profissao','nacionalidade',
            'cnpj','razao_social','nome_fantasia','inscricao_estadual',
            'email','telefone','telefone2',
            'cep','logradouro','numero','complemento','bairro','cidade',
            'fiador_nome','fiador_cpf','fiador_telefone',
        ]
        for field in text_fields:
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('class', 'form-input')

        self.fields['cpf'].widget.attrs['data-mascara'] = 'cpf'
        self.fields['cnpj'].widget.attrs['data-mascara'] = 'cnpj'
        self.fields['fiador_cpf'].widget.attrs['data-mascara'] = 'cpf'

        self.fields['renda_mensal'].widget.attrs['class'] = 'form-input'

        self.fields['estado'].widget = forms.Select(
            choices=ESTADOS_BR,
            attrs={'class': 'form-select'},
        )

    @staticmethod
    def _validar_cpf(cpf: str) -> bool:
        cpf = ''.join(c for c in cpf if c.isdigit())
        if len(cpf) != 11 or len(set(cpf)) == 1:
            return False
        for i in range(2):
            soma = sum(int(cpf[j]) * (10 + i - j) for j in range(9 + i))
            digito = (soma * 10 % 11) % 10
            if digito != int(cpf[9 + i]):
                return False
        return True

    @staticmethod
    def _validar_cnpj(cnpj: str) -> bool:
        cnpj = ''.join(c for c in cnpj if c.isdigit())
        if len(cnpj) != 14 or len(set(cnpj)) == 1:
            return False
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for pesos, pos in [(pesos1, 12), (pesos2, 13)]:
            soma = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
            resto = soma % 11
            digito = 0 if resto < 2 else 11 - resto
            if digito != int(cnpj[pos]):
                return False
        return True

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf', '').strip()
        if not cpf:
            return cpf
        if not self._validar_cpf(cpf):
            raise forms.ValidationError('CPF inválido.')
        return cpf

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj', '').strip()
        if not cnpj:
            return cnpj
        if not self._validar_cnpj(cnpj):
            raise forms.ValidationError('CNPJ inválido.')
        return cnpj

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        cpf = cleaned.get('cpf', '').strip()
        cnpj = cleaned.get('cnpj', '').strip()

        if tipo == 'pf' and not cpf:
            self.add_error('cpf', 'CPF é obrigatório para Pessoa Física.')
        if tipo == 'pj' and not cnpj:
            self.add_error('cnpj', 'CNPJ é obrigatório para Pessoa Jurídica.')

        # Valida CPF duplicado (exclui o próprio registro na edição)
        if cpf:
            qs = Inquilino.objects.filter(cpf=cpf).exclude(status='inativo')
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('cpf', 'Já existe um inquilino ativo com este CPF.')

        # Valida CNPJ duplicado
        if cnpj:
            qs = Inquilino.objects.filter(cnpj=cnpj).exclude(status='inativo')
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('cnpj', 'Já existe um inquilino ativo com este CNPJ.')

        return cleaned


class FiltroInquilinoForm(forms.Form):
    q      = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Nome, CPF/CNPJ, telefone...',
        'class': 'form-input',
    }))
    status = forms.ChoiceField(required=False,
                               choices=[('', 'Todos')] + Inquilino.STATUS_CHOICES,
                               widget=forms.Select(attrs={'class': 'form-select'}))
    tipo   = forms.ChoiceField(required=False,
                               choices=[('', 'PF e PJ')] + Inquilino.TIPO_CHOICES,
                               widget=forms.Select(attrs={'class': 'form-select'}))
