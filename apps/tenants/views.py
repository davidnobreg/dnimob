"""
views.py — Fase 2
Views do app tenants: cadastro público, painel de configurações,
Sicredi, WhatsApp e gerenciamento de usuários.
"""

import json
import logging
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django_tenants.utils import get_public_schema_name, schema_context

from .forms import (
    CadastroImobiliariaForm,
    ConfigContaForm,
    ConfigSicrediForm,
    ConfigWhatsAppForm,
    ConvidarUsuarioForm,
    EditarPermissoesForm,
    SuperAdminCriarTenantForm,
    TemplateWhatsAppForm,
)
from .models import ConfigSicredi, InstanciaWhatsApp, Plano, TemplateWhatsApp, Tenant
from .services import (
    EvolutionAPIError,
    criar_instancia_whatsapp,
    criar_tenant,
    gerar_senha_temporaria,
    obter_qrcode_instancia,
    testar_credenciais_sicredi,
    verificar_status_whatsapp,
)

logger = logging.getLogger(__name__)
Usuario = get_user_model()


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def obter_ip_cliente(request):
    """IP real do cliente — atrás de proxy (Cloudflare/NPM), usa o primeiro da X-Forwarded-For."""
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Landing page — cadastro de nova imobiliária
# ---------------------------------------------------------------------------

def landing(request):
    """Página pública de captação."""
    from .models import Plano
    planos = Plano.objects.filter(ativo=True).order_by('preco_mensal')
    return render(request, 'tenants/landing.html', {'planos': planos})


def cadastro_imobiliaria(request):
    """Formulário de cadastro público."""
    if request.method == 'POST':
        form = CadastroImobiliariaForm(request.POST)
        if form.is_valid():
            try:
                tenant = criar_tenant(
                    form.cleaned_data,
                    aceite_termos_em=timezone.now(),
                    aceite_termos_ip=obter_ip_cliente(request),
                    aceite_termos_user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
                from .tasks import provisionar_tenant
                provisionar_tenant.delay(
                    tenant.pk,
                    {
                        'nome':  form.cleaned_data['nome_admin'],
                        'email': form.cleaned_data['email_admin'],
                        'senha': form.cleaned_data['senha'],
                    },
                )
                return redirect('cadastro_aguardando', schema=tenant.schema_name)
            except ValidationError as e:
                messages.error(request, e.message)
            except Exception as e:
                logger.exception('Erro ao criar tenant')
                messages.error(request, f'Erro ao criar a conta: {e}')
    else:
        form = CadastroImobiliariaForm()

    planos_sicredi_ids = list(
        Plano.objects.filter(tem_sicredi=True, ativo=True).values_list('id', flat=True)
    )
    return render(request, 'tenants/cadastro.html', {
        'form': form,
        'planos_sicredi_ids': planos_sicredi_ids,
    })


def cadastro_aguardando(request, schema):
    """Tela intermediária enquanto o Celery provisiona o tenant."""
    tenant = get_object_or_404(Tenant, schema_name=schema)
    return render(request, 'tenants/aguardando.html', {'tenant': tenant})


def cadastro_status(request, schema):
    """AJAX — retorna status do provisionamento para polling do JS."""
    tenant = get_object_or_404(Tenant, schema_name=schema)
    return JsonResponse({'status': tenant.provisionamento_status})


def termos_uso(request):
    """Termos de Uso — página pública estática."""
    return render(request, 'tenants/termos.html')


def politica_privacidade(request):
    """Política de Privacidade — página pública estática."""
    return render(request, 'tenants/privacidade.html')


def login_acesso(request):
    """Tela pública: informa o subdomínio e redireciona para o login do tenant."""
    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'dnsoftware.com.br')
    dev_login_url = f'http://alpha.{base_domain}/login/' if settings.DEBUG else None
    return render(request, 'tenants/login_public.html', {
        'base_domain': base_domain,
        'dev_login_url': dev_login_url,
    })


def cadastro_sucesso(request, schema):
    tenant = get_object_or_404(Tenant, schema_name=schema)
    return render(request, 'tenants/cadastro_sucesso.html', {'tenant': tenant})


# ---------------------------------------------------------------------------
# Acesso bloqueado (schema tenant) — destino do PlanoAcessoMiddleware quando
# tenant.acesso_permitido é False. Rota fica na whitelist do próprio
# middleware (URLS_LIBERADAS), então não pode entrar em loop de redirect.
# ---------------------------------------------------------------------------

def acesso_bloqueado(request):
    tenant = request.tenant
    if not tenant.ativo:
        motivo = 'suspenso'
    elif tenant.status_assinatura == 'trial_expirado':
        motivo = 'trial_expirado'
    elif tenant.status_assinatura == 'expirado':
        motivo = 'assinatura_expirada'
    else:
        motivo = 'bloqueado'
    return render(request, 'tenants/acesso_bloqueado.html', {'tenant': tenant, 'motivo': motivo})


# ---------------------------------------------------------------------------
# Painel superadmin (schema public)
# ---------------------------------------------------------------------------

@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
def superadmin_dashboard(request):
    tenants = Tenant.objects.exclude(schema_name=get_public_schema_name()).order_by('-criado_em')
    total = tenants.count()
    ativos = tenants.filter(ativo=True).count()
    context = {
        'tenants': tenants,
        'total': total,
        'ativos': ativos,
        'trial': tenants.filter(trial=True).count(),
        'inativos': total - ativos,
    }
    return render(request, 'tenants/superadmin/dashboard.html', context)


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
def superadmin_tenant_detalhe(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    with schema_context(tenant.schema_name):
        usuarios = Usuario.objects.all().order_by('email')

    billing_type_atual = None
    pagamentos = []
    if tenant.asaas_subscription_id:
        try:
            from apps.billing.client import AsaasClient, AsaasError
            client = AsaasClient()
            subscription_data = client.obter_subscription(tenant.asaas_subscription_id)
            billing_type_atual = subscription_data.get('billingType')
        except AsaasError as e:
            logger.warning('Erro ao consultar subscription Asaas do tenant %s: %s', tenant.schema_name, e)

        try:
            from apps.billing.client import AsaasClient, AsaasError
            client = AsaasClient()
            pagamentos = client.listar_pagamentos_subscription(tenant.asaas_subscription_id)
        except AsaasError as e:
            logger.warning('Erro ao listar pagamentos Asaas do tenant %s: %s', tenant.schema_name, e)

    return render(request, 'tenants/superadmin/tenant_detalhe.html', {
        'tenant': tenant,
        'usuarios': usuarios,
        'planos': Plano.objects.filter(ativo=True),
        'billing_type_atual': billing_type_atual,
        'pagamentos': pagamentos,
    })


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
@require_POST
def superadmin_toggle_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    tenant.ativo = not tenant.ativo
    tenant.save()
    status = 'ativada' if tenant.ativo else 'desativada'
    messages.success(request, f'Imobiliária {tenant.nome} {status}.')
    return redirect('superadmin_dashboard')


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
def superadmin_criar_tenant(request):
    if request.method == 'POST':
        form = SuperAdminCriarTenantForm(request.POST)
        if form.is_valid():
            dados = {
                'nome_imobiliaria': form.cleaned_data['nome'],
                'subdominio': form.cleaned_data['subdominio'],
                'plano': form.cleaned_data['plano'],
                'email_admin': form.cleaned_data['email_admin'],
            }
            senha = gerar_senha_temporaria()
            try:
                tenant = criar_tenant(dados)
                from .tasks import provisionar_tenant
                provisionar_tenant.delay(
                    tenant.pk,
                    {'nome': 'Administrador', 'email': dados['email_admin'], 'senha': senha},
                )
                messages.success(
                    request,
                    f'Imobiliária "{tenant.nome}" criada com sucesso. '
                    f'Senha do admin: {senha}',
                )
            except Exception as e:
                logger.exception('Erro ao criar tenant via superadmin')
                messages.error(request, f'Erro ao criar imobiliária: {e}')
            return redirect('superadmin_dashboard')
    else:
        form = SuperAdminCriarTenantForm()
    return render(request, 'tenants/superadmin/criar_tenant.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
def superadmin_asaas_pagamento(request, tenant_id):
    """
    Tela admin-master pra mudar a forma de pagamento da assinatura Asaas
    de um tenant. Só o superadmin DN Software acessa — a imobiliária não
    gerencia o próprio pagamento da mensalidade.
    """
    from apps.billing.client import AsaasClient, AsaasError

    tenant = get_object_or_404(Tenant, pk=tenant_id)

    if request.method == 'POST':
        billing_type = request.POST.get('billing_type', '').upper()

        if billing_type not in ('BOLETO', 'PIX'):
            messages.error(request, 'Forma de pagamento inválida.')
            return redirect('superadmin_asaas_pagamento', tenant_id=tenant_id)

        if not tenant.asaas_subscription_id:
            messages.error(request, 'Tenant sem subscription Asaas.')
            return redirect('superadmin_tenant_detalhe', tenant_id=tenant_id)

        try:
            client = AsaasClient()
            client.atualizar_billing_type(tenant.asaas_subscription_id, billing_type)
            messages.success(request, f'Forma de pagamento de {tenant.nome} atualizada para {billing_type}.')
        except AsaasError as e:
            logger.error('Erro ao atualizar billing type do tenant %s: %s', tenant.schema_name, e)
            messages.error(request, f'Erro Asaas: {e}')

        return redirect('superadmin_tenant_detalhe', tenant_id=tenant_id)

    billing_type_atual = None
    subscription_data = None
    if tenant.asaas_subscription_id:
        try:
            client = AsaasClient()
            subscription_data = client.obter_subscription(tenant.asaas_subscription_id)
            billing_type_atual = subscription_data.get('billingType')
        except AsaasError as e:
            logger.warning('Erro ao consultar subscription Asaas do tenant %s: %s', tenant.schema_name, e)
            messages.warning(request, f'Erro ao consultar Asaas: {e}')

    return render(request, 'tenants/superadmin_asaas_pagamento.html', {
        'tenant': tenant,
        'billing_type_atual': billing_type_atual,
        'subscription_data': subscription_data,
        'ASAAS_PUBLIC_KEY': settings.ASAAS_PUBLIC_KEY,
        'ASAAS_JS_URL': settings.ASAAS_JS_URL,
    })


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
@require_POST
def superadmin_asaas_cartao(request, tenant_id):
    """Recebe o token do cartão gerado pelo Asaas.js — nunca dado de cartão cru."""
    from apps.billing.client import AsaasClient, AsaasError

    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if not tenant.asaas_subscription_id:
        return JsonResponse({'ok': False, 'erro': 'Tenant sem subscription Asaas.'}, status=400)

    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'Corpo da requisição inválido.'}, status=400)

    credit_card_token = data.get('creditCardToken')
    if not credit_card_token:
        return JsonResponse({'ok': False, 'erro': 'Token do cartão não fornecido.'}, status=400)

    try:
        client = AsaasClient()
        client.associar_cartao_subscription(tenant.asaas_subscription_id, credit_card_token)
        return JsonResponse({'ok': True})
    except AsaasError as e:
        logger.error('Erro ao associar cartão do tenant %s: %s', tenant.schema_name, e)
        return JsonResponse({'ok': False, 'erro': 'Erro ao associar cartão. Tente novamente.'}, status=502)


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-master/login/')
@require_POST
def superadmin_trocar_plano(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    plano = get_object_or_404(Plano, pk=request.POST.get('plano_id'))
    tenant.plano = plano
    tenant.save()
    messages.success(request, f'Plano de {tenant.nome} alterado para {plano}.')
    return redirect('superadmin_tenant_detalhe', tenant_id=tenant.pk)


# ---------------------------------------------------------------------------
# Configurações da conta (dentro do tenant)
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def config_conta(request):
    """Dados gerais da imobiliária — editado pelo admin do tenant."""
    tenant = request.tenant
    if request.method == 'POST':
        form = ConfigContaForm(request.POST, request.FILES, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações salvas com sucesso!')
            return redirect('config_conta')
    else:
        form = ConfigContaForm(instance=tenant)
    return render(request, 'tenants/config_conta.html', {'form': form, 'tenant': tenant})


# ---------------------------------------------------------------------------
# Configuração Sicredi
# ---------------------------------------------------------------------------

def _webhook_url(request, config):
    if not config or not config.webhook_secret:
        return ''
    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'dnsoftware.com.br')
    return f'{request.scheme}://{base_domain}/sicredi/webhook/{config.webhook_secret}/'


@login_required
@user_passes_test(is_admin)
def config_sicredi(request):
    schema = request.tenant.schema_name
    config = ConfigSicredi.objects.filter(schema_name=schema).first()
    if request.method == 'POST':
        form = ConfigSicrediForm(request.POST, instance=config)
        if form.is_valid():
            config = form.save(commit=False)
            config.schema_name = schema  # vínculo do tenant (roteamento do webhook)
            config.ativo = False  # só ativa após testar
            if not config.webhook_secret:
                config.webhook_secret = secrets.token_urlsafe(32)
            config.save()
            messages.success(request, 'Configurações Sicredi salvas. Clique em "Testar conexão" para validar.')
            return redirect('config_sicredi')
    else:
        form = ConfigSicrediForm(instance=config)
    return render(request, 'tenants/config_sicredi.html', {
        'form': form, 'config': config, 'webhook_url': _webhook_url(request, config),
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def testar_sicredi(request):
    config = ConfigSicredi.objects.filter(schema_name=request.tenant.schema_name).first()
    if not config:
        return JsonResponse({'ok': False, 'msg': 'Nenhuma configuração salva.'})
    ok, msg = testar_credenciais_sicredi(config)
    if ok:
        config.ativo = True
        config.save()
    return JsonResponse({'ok': ok, 'msg': msg})


@login_required
@user_passes_test(is_admin)
@require_POST
def regenerar_webhook_secret_sicredi(request):
    config = ConfigSicredi.objects.filter(schema_name=request.tenant.schema_name).first()
    if not config:
        messages.error(request, 'Salve as configurações Sicredi antes de gerar um webhook secret.')
        return redirect('config_sicredi')

    config.webhook_secret = secrets.token_urlsafe(32)
    config.save(update_fields=['webhook_secret', 'atualizado_em'])
    messages.warning(
        request,
        'Novo webhook secret gerado. A URL antiga parou de funcionar — '
        'atualize a URL do webhook no portal do Sicredi com o novo valor abaixo.',
    )
    return redirect('config_sicredi')


# ---------------------------------------------------------------------------
# Configuração WhatsApp
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def config_whatsapp(request):
    instancia = InstanciaWhatsApp.objects.first()

    if request.method == 'POST':
        form = ConfigWhatsAppForm(request.POST, instance=instancia)

        if form.is_valid():
            dados = form.cleaned_data
            try:
                instancia = criar_instancia_whatsapp(
                    request.tenant.schema_name,
                    dados['nome_instancia'],
                )
                messages.success(request, 'Instância criada! Escaneie o QR Code abaixo.')
                return redirect('config_whatsapp')

            except Exception as e:
                messages.error(request, f'Erro na Evolution API: {e}')
        else:
            messages.error(request, 'Corrija os erros abaixo.')
    else:
        form = ConfigWhatsAppForm(instance=instancia)

    return render(request, 'tenants/config_whatsapp.html', {
        'form': form,
        'instancia': instancia,
        'evolution_api_url': settings.EVOLUTION_API_URL,
    })



@login_required
@user_passes_test(is_admin)
def whatsapp_qrcode(request):
    """AJAX — retorna QR code atualizado."""
    instancia = InstanciaWhatsApp.objects.first()
    if not instancia:
        return JsonResponse({'ok': False, 'msg': 'Nenhuma instância configurada.'})
    data = obter_qrcode_instancia(request.tenant.schema_name, instancia.nome_instancia)
    return JsonResponse({'ok': bool(data), 'qr': data.get('base64', ''), 'status': instancia.status})


@login_required
@user_passes_test(is_admin)
def whatsapp_status(request):
    """AJAX — verifica status da conexão."""
    instancia = InstanciaWhatsApp.objects.first()
    if not instancia:
        return JsonResponse({'status': 'desconectado'})
    status = verificar_status_whatsapp(request.tenant.schema_name, instancia.nome_instancia)
    return JsonResponse({'status': status, 'numero': instancia.numero_telefone})


@login_required
@user_passes_test(is_admin)
@require_POST
def recriar_instancia_whatsapp(request):
    """Recria no servidor Evolution API uma instância que sumiu de lá (status='nao_encontrada')."""
    instancia = InstanciaWhatsApp.objects.first()
    if not instancia:
        messages.error(request, 'Nenhuma instância configurada.')
        return redirect('config_whatsapp')

    try:
        criar_instancia_whatsapp(request.tenant.schema_name, instancia.nome_instancia)
        messages.success(request, 'Instância recriada! Escaneie o QR Code para conectar.')
    except EvolutionAPIError as e:
        messages.error(request, f'Erro ao recriar instância: {e}')

    return redirect('config_whatsapp')


GRUPOS_TEMPLATES_WHATSAPP = [
    ('📋 Contrato', ['boas_vindas', 'contrato_enviado', 'contrato_60dias', 'contrato_30dias', 'distrato_enviado']),
    ('💰 Cobrança', ['boleto_gerado', 'vence_amanha', 'vence_hoje']),
    ('⚠️ Atraso', ['atraso_3', 'atraso_7', 'atraso_15']),
    ('✅ Pagamento', ['pagamento_confirmado', 'recibo_pagamento']),
]

# Quando cada evento dispara de verdade no sistema. `wired=False` = evento
# ainda sem gatilho no código (template existe mas nunca é enviado).
DISPARO_POR_EVENTO = {
    'boas_vindas':          {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
    'contrato_enviado':     {'wired': True,  'descricao': 'Ao criar um novo contrato (signal → task_contrato_criado).'},
    'contrato_60dias':      {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
    'contrato_30dias':      {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
    'distrato_enviado':     {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
    'boleto_gerado':        {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
    'vence_amanha':         {'wired': True,  'descricao': 'Diariamente, para boletos que vencem no dia seguinte.'},
    'vence_hoje':           {'wired': True,  'descricao': 'Diariamente, para boletos que vencem no próprio dia.'},
    'atraso_3':             {'wired': True,  'descricao': 'Diariamente, para boletos vencidos há 3 dias.'},
    'atraso_7':             {'wired': True,  'descricao': 'Diariamente, para boletos vencidos há 7 dias.'},
    'atraso_15':            {'wired': True,  'descricao': 'Diariamente, para boletos vencidos há 15 dias.'},
    'pagamento_confirmado': {'wired': True,  'descricao': 'Ao registrar o pagamento de uma parcela (signal → task_pagamento_confirmado).'},
    'recibo_pagamento':     {'wired': False, 'descricao': 'Ainda sem gatilho automático no código.'},
}

EXEMPLOS_VARIAVEIS = {
    'nome_inquilino':           'Maria Silva',
    'endereco_imovel':          'Rua das Flores, 123 — Centro',
    'valor':                    '1.500,00',
    'mes_referencia':           '03/2026',
    'data_vencimento':          '10/03/2026',
    'data_vencimento_contrato': '15/09/2026',
    'codigo_barras':            '00190.00009 03388.020128 12345.678901 1 90910000150000',
    'encargos':                 '60,00',
    'valor_com_encargos':       '1.560,00',
}


@login_required
@user_passes_test(is_admin)
def whatsapp_templates(request):
    templates_por_evento = {t.evento: t for t in TemplateWhatsApp.objects.all().order_by('evento')}
    grupos = [
        {
            'titulo': titulo,
            'templates': [
                {
                    'template': templates_por_evento[evento],
                    'disparo': DISPARO_POR_EVENTO.get(evento, {'wired': False, 'descricao': ''}),
                }
                for evento in eventos if evento in templates_por_evento
            ],
        }
        for titulo, eventos in GRUPOS_TEMPLATES_WHATSAPP
    ]
    total = sum(len(g['templates']) for g in grupos)
    ativos = sum(1 for g in grupos for t in g['templates'] if t['template'].ativo)
    return render(request, 'tenants/config_templates_whatsapp.html', {
        'grupos': grupos,
        'total': total,
        'ativos': ativos,
    })


def _grupo_do_evento(evento):
    for titulo, eventos in GRUPOS_TEMPLATES_WHATSAPP:
        if evento in eventos:
            return titulo
    return ''


@login_required
@user_passes_test(is_admin)
def whatsapp_template_editar(request, template_id):
    template = get_object_or_404(TemplateWhatsApp, pk=template_id)
    if request.method == 'POST':
        form = TemplateWhatsAppForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f'Template "{template.get_evento_display()}" salvo.')
            return redirect('whatsapp_templates')
    else:
        form = TemplateWhatsAppForm(instance=template)
    disparo = DISPARO_POR_EVENTO.get(template.evento, {'wired': False, 'descricao': ''})
    exemplos = {**EXEMPLOS_VARIAVEIS, 'nome_imobiliaria': request.tenant.nome}
    return render(request, 'tenants/config_template_editar.html', {
        'form': form,
        'template': template,
        'grupo_titulo': _grupo_do_evento(template.evento),
        'disparo': disparo,
        'exemplos': exemplos,
    })


# ---------------------------------------------------------------------------
# Usuários e permissões
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def usuarios_lista(request):
    usuarios = Usuario.objects.all().order_by('first_name', 'email')
    return render(request, 'tenants/usuarios_lista.html', {'usuarios': usuarios})


@login_required
@user_passes_test(is_admin)
def usuario_convidar(request):
    if request.method == 'POST':
        form = ConvidarUsuarioForm(request.POST)
        if form.is_valid():
            from .services import gerar_senha_temporaria
            senha_temp = gerar_senha_temporaria()
            usuario = Usuario.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['nome'].split()[0],
                last_name=' '.join(form.cleaned_data['nome'].split()[1:]),
                password=senha_temp,
            )
            usuario.is_staff = form.cleaned_data.get('is_admin', False)
            usuario.save()
            # TODO: enviar e-mail de boas-vindas com senha temporária
            messages.success(
                request,
                f'Usuário {usuario.email} criado. Senha temporária: {senha_temp}'
            )
            return redirect('usuarios_lista')
    else:
        form = ConvidarUsuarioForm()
    return render(request, 'tenants/usuario_convidar.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def usuario_editar(request, usuario_id):
    from .forms import MODULO_CHOICES
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    # Módulos salvos no campo extra do usuário (JSON no perfil ou como atributo)
    # Usamos um campo extra no usuario ou guardamos nos groups — aqui usamos
    # um atributo simples via JSON em um campo de texto se existir, ou lista vazia
    try:
        import json
        modulos_ativos = json.loads(getattr(usuario, 'modulos_acesso', '') or '[]')
    except Exception:
        modulos_ativos = []

    if request.method == 'POST':
        # Dados pessoais
        usuario.first_name = request.POST.get('first_name', '').strip()
        usuario.last_name  = request.POST.get('last_name', '').strip()
        usuario.email      = request.POST.get('email', '').strip()
        usuario.username   = usuario.email
        usuario.telefone   = request.POST.get('telefone', '').strip()
        usuario.perfil     = request.POST.get('perfil', 'atendente')

        # Foto
        if 'foto' in request.FILES:
            usuario.foto = request.FILES['foto']

        # Permissões
        usuario.is_staff  = request.POST.get('is_staff') == 'on'
        usuario.is_active = request.POST.get('is_active') == 'on'

        # Módulos selecionados
        modulos_selecionados = request.POST.getlist('modulos')
        # Salva como atributo se o campo existir no model
        if hasattr(usuario, 'modulos_acesso'):
            import json
            usuario.modulos_acesso = json.dumps(modulos_selecionados)

        # Senha (opcional)
        nova_senha          = request.POST.get('nova_senha', '').strip()
        nova_senha_confirma = request.POST.get('nova_senha_confirma', '').strip()

        if nova_senha:
            if nova_senha != nova_senha_confirma:
                messages.error(request, 'As senhas não coincidem.')
                return render(request, 'tenants/usuario_editar.html', {
                    'usuario': usuario,
                    'modulos_choices': MODULO_CHOICES,
                    'modulos_ativos': modulos_selecionados,
                })
            usuario.set_password(nova_senha)

        usuario.save()
        messages.success(request, f'Usuário {usuario.email} atualizado com sucesso.')
        return redirect('usuarios_lista')

    return render(request, 'tenants/usuario_editar.html', {
        'usuario':         usuario,
        'modulos_choices': MODULO_CHOICES,
        'modulos_ativos':  modulos_ativos,
    })




@login_required
@user_passes_test(is_admin)
@require_POST
def usuario_desativar(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    if usuario == request.user:
        messages.error(request, 'Você não pode desativar sua própria conta.')
    else:
        usuario.is_active = not usuario.is_active
        usuario.save()
        acao = 'ativado' if usuario.is_active else 'desativado'
        messages.success(request, f'Usuário {usuario.email} {acao}.')
    return redirect('usuarios_lista')

@login_required
def dashboard(request):
    from decimal import Decimal
    from datetime import date
    from django.db.models import Sum

    hoje = date.today()
    primeiro_mes = hoje.replace(day=1)

    try:
        from apps.imoveis.models import Imovel
        from apps.contratos.models import Contrato, Parcela
        from apps.financeiro.models import Lancamento

        total_imoveis     = Imovel.objects.count()
        contratos_ativos  = Contrato.objects.filter(status='ativo').count()
        inadimplentes     = Parcela.objects.filter(status='atrasado').count()
        recebido_mes      = Lancamento.objects.filter(
            tipo='receita',
            status='realizado',
            data__gte=primeiro_mes,
            data__lte=hoje,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

    except Exception:
        total_imoveis = contratos_ativos = inadimplentes = 0
        recebido_mes = Decimal('0')

    kpi_cards = [
        {
            'icon': 'ti-home',
            'bg': 'bg-blue-50',
            'color': 'text-blue-600',
            'badge_bg': 'bg-blue-100',
            'badge_color': 'text-blue-700',
            'variacao': 'Imóveis',
            'valor': total_imoveis,
            'label': 'Imóveis cadastrados',
        },
        {
            'icon': 'ti-file-text',
            'bg': 'bg-green-50',
            'color': 'text-green-600',
            'badge_bg': 'bg-green-100',
            'badge_color': 'text-green-700',
            'variacao': 'Ativos',
            'valor': contratos_ativos,
            'label': 'Contratos ativos',
        },
        {
            'icon': 'ti-coin',
            'bg': 'bg-yellow-50',
            'color': 'text-yellow-600',
            'badge_bg': 'bg-yellow-100',
            'badge_color': 'text-yellow-700',
            'variacao': 'Este mês',
            'valor': f'R$ {recebido_mes:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
            'label': 'Recebido este mês',
        },
        {
            'icon': 'ti-alert-triangle',
            'bg': 'bg-red-50',
            'color': 'text-red-600',
            'badge_bg': 'bg-red-100',
            'badge_color': 'text-red-700',
            'variacao': 'Em atraso',
            'valor': inadimplentes,
            'label': 'Inadimplentes',
        },
    ]

    return render(request, 'core/dashboard.html', {
        'tenant': request.tenant,
        'kpi_cards': kpi_cards,
    })