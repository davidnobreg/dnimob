from django import forms
from django.contrib.auth import get_user_model
from .models import Tenant, ConfigSicredi, InstanciaWhatsApp, TemplateWhatsApp, Plano, TipoPessoa
from .validators import validar_cpf
import re

Usuario = get_user_model()


# ---------------------------------------------------------------------------
# Landing page — cadastro de nova imobiliária
# ---------------------------------------------------------------------------

_INPUT = (
    'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm '
    'text-slate-900 placeholder-slate-400 transition '
    'focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20'
)
_SELECT = (
    'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm '
    'text-slate-900 transition '
    'focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20'
)
_SLUG = (
    'min-w-0 flex-1 bg-transparent px-3 py-2.5 text-sm text-slate-900 '
    'placeholder-slate-400 focus:outline-none'
)


class CadastroImobiliariaForm(forms.Form):
    """Formulário público de cadastro (landing page)."""

    # Dados da imobiliária
    nome_imobiliaria = forms.CharField(
        max_length=200,
        label='Nome da imobiliária',
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Imobiliária Alpha', 'class': _INPUT}),
    )
    tipo_pessoa = forms.ChoiceField(
        choices=TipoPessoa.choices,
        initial=TipoPessoa.JURIDICA,
        required=True,
        widget=forms.HiddenInput(),
    )
    documento = forms.CharField(
        max_length=18,
        label='CNPJ',
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'id_documento',
            'placeholder': '00.000.000/0000-00',
            'class': _INPUT,
        }),
    )
    subdominio = forms.SlugField(
        max_length=30,
        label='Subdomínio desejado',
        help_text='Ex: alpha → alpha.dnsoftware.com.br',
        widget=forms.TextInput(attrs={'placeholder': 'minha-imobiliaria', 'class': _SLUG}),
    )
    plano = forms.ModelChoiceField(
        queryset=Plano.objects.filter(ativo=True),
        label='Plano',
        empty_label='Selecione um plano',
        widget=forms.Select(attrs={'class': _SELECT}),
    )

    # Dados do administrador
    nome_admin = forms.CharField(
        max_length=150,
        label='Seu nome completo',
        widget=forms.TextInput(attrs={'class': _INPUT}),
    )
    email_admin = forms.EmailField(
        label='E-mail do administrador',
        widget=forms.EmailInput(attrs={'class': _INPUT}),
    )
    telefone_admin = forms.CharField(
        max_length=20,
        label='Telefone / WhatsApp',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '(00) 90000-0000', 'class': _INPUT}),
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'placeholder': 'Mínimo 8 caracteres', 'class': _INPUT}),
        min_length=8,
    )
    senha_confirma = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repita a senha', 'class': _INPUT}),
    )
    aceite_termos = forms.BooleanField(
        label='Concordo com os Termos de Uso e Política de Privacidade',
        error_messages={'required': 'Você precisa aceitar os termos para continuar.'},
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 rounded border-slate-300 accent-blue-600 cursor-pointer',
        }),
    )

    def clean_subdominio(self):
        subdominio = self.cleaned_data['subdominio'].lower().strip()
        reservados = ['www', 'admin', 'api', 'mail', 'smtp', 'static', 'media', 'app']
        if subdominio in reservados:
            raise forms.ValidationError('Este subdomínio é reservado. Escolha outro.')
        from .models import Domain
        if Domain.objects.filter(domain__startswith=f'{subdominio}.').exists():
            raise forms.ValidationError('Este subdomínio já está em uso. Escolha outro.')
        return subdominio

    @staticmethod
    def _validar_cnpj(cnpj: str) -> bool:
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

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_pessoa', TipoPessoa.JURIDICA)
        doc = re.sub(r'\D', '', cleaned.get('documento', '') or '')

        if tipo == TipoPessoa.FISICA:
            if not doc:
                self.add_error('documento', 'CPF é obrigatório para Pessoa Física.')
            else:
                try:
                    validar_cpf(doc)
                except forms.ValidationError as e:
                    self.add_error('documento', e)
            cleaned['cpf'] = doc
            cleaned['cnpj'] = ''
        else:
            if doc and (len(doc) != 14 or not self._validar_cnpj(doc)):
                self.add_error('documento', 'CNPJ inválido. Verifique os dígitos e tente novamente.')
            cleaned['cnpj'] = doc
            cleaned['cpf'] = ''

        senha = cleaned.get('senha')
        senha_confirma = cleaned.get('senha_confirma')
        if senha and senha_confirma and senha != senha_confirma:
            self.add_error('senha_confirma', 'As senhas não coincidem.')
        return cleaned


# ---------------------------------------------------------------------------
# Superadmin — criar tenant
# ---------------------------------------------------------------------------

class SuperAdminCriarTenantForm(forms.Form):
	nome = forms.CharField(
		max_length=200,
		label='Nome da imobiliária',
		widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: Imobiliária Beta'}),
	)
	subdominio = forms.SlugField(
		max_length=30,
		label='Subdomínio',
		widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'imobiliaria-beta'}),
	)
	plano = forms.ModelChoiceField(
		queryset=Plano.objects.filter(ativo=True),
		label='Plano',
		empty_label='Selecione um plano',
		widget=forms.Select(attrs={'class': _SELECT}),
	)
	email_admin = forms.EmailField(
		label='E-mail do administrador',
		widget=forms.EmailInput(attrs={'class': _INPUT, 'placeholder': 'admin@imobiliaria.com'}),
	)

	def clean_subdominio(self):
		subdominio = self.cleaned_data['subdominio'].lower().strip()
		reservados = ['www', 'admin', 'api', 'mail', 'smtp', 'static', 'media', 'app']
		if subdominio in reservados:
			raise forms.ValidationError('Subdomínio reservado. Escolha outro.')
		from .models import Domain
		if Domain.objects.filter(domain__startswith=f'{subdominio}.').exists():
			raise forms.ValidationError('Subdomínio já está em uso.')
		return subdominio


# ---------------------------------------------------------------------------
# Configuração da conta (dentro do tenant)
# ---------------------------------------------------------------------------

class ConfigContaForm(forms.ModelForm):
    """Dados gerais da imobiliária — editável pelo admin do tenant."""

    class Meta:
        model = Tenant
        fields = [
            'nome', 'cnpj', 'cpf', 'email', 'telefone',
            'endereco', 'cidade', 'estado', 'cep',
            'logo', 'cor_primaria', 'cor_secundaria', 'cor_acento',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-input'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-input'}),
            'cpf': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '000.000.000-00'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'telefone': forms.TextInput(attrs={'class': 'form-input'}),
            'endereco': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'cidade': forms.TextInput(attrs={'class': 'form-input'}),
            'cep': forms.TextInput(attrs={'class': 'form-input'}),
            'cor_primaria': forms.TextInput(attrs={'type': 'color', 'class': 'h-11 w-14 cursor-pointer rounded-lg border border-slate-200 bg-white p-1'}),
            'cor_secundaria': forms.TextInput(attrs={'type': 'color', 'class': 'h-11 w-14 cursor-pointer rounded-lg border border-slate-200 bg-white p-1'}),
            'cor_acento': forms.TextInput(attrs={'type': 'color', 'class': 'h-11 w-14 cursor-pointer rounded-lg border border-slate-200 bg-white p-1'}),
            'estado': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', '— Estado —'),
                ('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'),
                ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'),
                ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'),
                ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'),
                ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'),
                ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'),
                ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO'),
            ]),
        }


# ---------------------------------------------------------------------------
# Config Sicredi
# ---------------------------------------------------------------------------

class ConfigSicrediForm(forms.ModelForm):
    codigo_acesso = forms.CharField(
        label='Código de acesso',
        widget=forms.PasswordInput(render_value=True, attrs={'class': 'form-input'}),
        help_text='Código de acesso gerado no Internet Banking (senha do token). Mantido em sigilo.',
        required=False,
    )

    class Meta:
        model = ConfigSicredi
        fields = [
            'api_key', 'codigo_acesso', 'codigo_beneficiario',
            'cooperativa', 'posto', 'conta',
            'beneficiario', 'ambiente', 'webhook_secret',
        ]
        widgets = {
            'api_key':              forms.TextInput(attrs={'class': 'form-input'}),
            'codigo_beneficiario':  forms.TextInput(attrs={'class': 'form-input'}),
            'cooperativa':          forms.TextInput(attrs={'class': 'form-input'}),
            'posto':                forms.TextInput(attrs={'class': 'form-input'}),
            'conta':                forms.TextInput(attrs={'class': 'form-input'}),
            'beneficiario':         forms.TextInput(attrs={'class': 'form-input'}),
            'ambiente':             forms.Select(attrs={'class': 'form-select'}),
            'webhook_secret':       forms.TextInput(attrs={'class': 'form-input'}),
        }
        help_texts = {
            'cooperativa': 'Código de 4 dígitos fornecido pelo Sicredi',
            'posto': 'Código de 2 dígitos do posto de atendimento',
            'conta': 'Número da conta sem dígito verificador',
            'webhook_secret': 'Secret compartilhado com o Sicredi para validar webhooks HMAC',
        }


# ---------------------------------------------------------------------------
# WhatsApp — criar/configurar instância
# ---------------------------------------------------------------------------

class ConfigWhatsAppForm(forms.ModelForm):
    class Meta:
        model = InstanciaWhatsApp
        fields = ['nome_instancia', 'token_api']
        help_texts = {
            'nome_instancia': 'Identificador único desta instância na Evolution API (sem espaços)',
            'token_api': 'Token de autenticação da sua Evolution API',
        }
        widgets = {
            'token_api': forms.PasswordInput(render_value=True),
        }

    def clean_nome_instancia(self):
        nome = self.cleaned_data['nome_instancia'].strip().replace(' ', '-')
        return nome


class TemplateWhatsAppForm(forms.ModelForm):
    class Meta:
        model = TemplateWhatsApp
        fields = ['ativo', 'mensagem']
        widgets = {
            'mensagem': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Olá {nome_inquilino}, seu boleto referente ao imóvel {endereco_imovel} vence em {data_vencimento}...',
            }),
        }


# ---------------------------------------------------------------------------
# Usuários e permissões
# ---------------------------------------------------------------------------

MODULO_CHOICES = [
    ('imoveis', 'Imóveis'),
    ('inquilinos', 'Inquilinos'),
    ('contratos', 'Contratos'),
    ('financeiro', 'Financeiro'),
    ('relatorios', 'Relatórios'),
    ('configuracoes', 'Configurações'),
]

PERMISSAO_CHOICES = [
    ('visualizar', 'Visualizar'),
    ('editar', 'Editar'),
    ('excluir', 'Excluir'),
]


class ConvidarUsuarioForm(forms.Form):
    email = forms.EmailField(label='E-mail do usuário')
    nome = forms.CharField(max_length=150, label='Nome completo')
    cargo = forms.CharField(max_length=100, label='Cargo / função', required=False)
    is_admin = forms.BooleanField(label='Administrador (acesso total)', required=False)
    modulos = forms.MultipleChoiceField(
        choices=MODULO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Módulos com acesso',
        required=False,
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Já existe um usuário cadastrado com este e-mail.')
        return email


class EditarPermissoesForm(forms.Form):
    is_admin = forms.BooleanField(label='Administrador', required=False)
    modulos = forms.MultipleChoiceField(
        choices=MODULO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    ativo = forms.BooleanField(label='Acesso ativo', required=False)
