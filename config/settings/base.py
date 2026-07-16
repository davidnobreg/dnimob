"""
config/settings/base.py
Configurações base compartilhadas entre dev e prod.
"""
from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Lê o .env na raiz do projeto
environ.Env.read_env(BASE_DIR / 'configuration/.envDnimob')

#BASE_DIR = Path(__file__).resolve().parent.parent

#ENV_PATH = BASE_DIR / 'configuration' / '.envDnimob'

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# ─────────────────────────────────────────────
# MULTI-TENANT
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME', default='imobiliaria'),
        'USER': env('DB_USER', default='imob'),
        'PASSWORD': env('DB_PASSWORD', default='senha'),
        'HOST': env('DB_HOST', default='db'),
        'PORT': env('DB_PORT', default='5432'),
        'OPTIONS': {'options': '-c search_path=public'},
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

TENANT_MODEL = 'tenants.Tenant'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

TENANT_BASE_DOMAIN = env('TENANT_BASE_DOMAIN', default='dnsoftware.com.br')

# Apps no schema PUBLIC (compartilhado entre todos os tenants)
SHARED_APPS = [
    'django_tenants',
    'apps.tenants',
    'apps.billing',

    # apps.core DEVE estar aqui porque AUTH_USER_MODEL = 'core.Usuario'
    # e o django.contrib.admin referencia o user model no schema public
    'apps.core',

    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.humanize',

    'crispy_forms',
    'crispy_tailwind',

    # Celery Beat/Results vivem no schema public (scheduler centralizado)
    'django_celery_beat',
    'django_celery_results',
]

# Apps em cada schema de TENANT (dados isolados por imobiliária)
TENANT_APPS = [
    'django.contrib.contenttypes',

    # apps.core também aqui para que cada tenant tenha seus próprios usuários
    'apps.core',
    'apps.imoveis',
    'apps.inquilinos',
    'apps.contratos',
    'apps.documentos',
    'apps.financeiro',
    'apps.sicredi',
    'apps.whatsapp',
    'apps.relatorios',

    'crispy_forms',
    'crispy_tailwind',
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',  # PRIMEIRO
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Middleware do tenant
    # 'apps.tenants.middleware.TenantAccessMiddleware',
    'apps.tenants.middleware.PlanoAcessoMiddleware',

]

# ─────────────────────────────────────────────
# URLs
# ─────────────────────────────────────────────
# URL pública: imob.dnsoftware.com.br (landing, cadastro, admin master)
PUBLIC_SCHEMA_URLCONF = 'config.urls_public'
# URL de tenant: alpha.imob.dnsoftware.com.br (sistema completo)
ROOT_URLCONF = 'config.urls_tenant'

SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

# ─────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.tenant_context',
            ],
        },
    },
]

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
AUTH_USER_MODEL = 'core.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ─────────────────────────────────────────────
# STATIC & MEDIA
# ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ─────────────────────────────────────────────
# CACHE (Redis nativo — usado pelo token Sicredi por tenant)
# ─────────────────────────────────────────────
CACHES = {
	'default': {
		'BACKEND': 'django.core.cache.backends.redis.RedisCache',
		'LOCATION': env('CACHE_URL', default='redis://redis:6379/1'),
	}
}

# ─────────────────────────────────────────────
# CELERY
# ─────────────────────────────────────────────
CELERY_BROKER_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_TIMEZONE = 'America/Fortaleza'
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True

# Tasks da integração Sicredi rodam na fila financeiro
CELERY_TASK_ROUTES = {
	'apps.sicredi.tasks.*': {'queue': 'financeiro'},
}

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ── Financeiro ──────────────────────────────────
    'gerar-cobrancas-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['gerar_cobrancas_mensais'],
        'schedule': crontab(day_of_month='1', hour='6', minute='0'),
    },
    'registrar-boletos-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['registrar_boletos_pendentes'],
        'schedule': crontab(hour='7', minute='30'),
    },
    'sincronizar-baixas-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['sincronizar_baixas_sicredi'],
        'schedule': crontab(minute='0'),
    },
    'marcar-inadimplencias-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['marcar_inadimplencias'],
        'schedule': crontab(hour='0', minute='30'),
    },
    # ── WhatsApp ─────────────────────────────────────
    'whatsapp-vence-amanha-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['task_avisar_vencimento_amanha'],
        'schedule': crontab(hour='9', minute='0'),
    },
    'whatsapp-vence-hoje-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['task_avisar_vencimento_hoje'],
        'schedule': crontab(hour='8', minute='0'),
    },
    'whatsapp-cobrar-inadimplentes-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['task_cobrar_inadimplentes'],
        'schedule': crontab(hour='10', minute='0'),
    },
    'whatsapp-contratos-vencendo-todos': {
        'task': 'apps.financeiro.tasks.disparar_todos_tenants',
        'args': ['task_avisar_contratos_vencendo'],
        'schedule': crontab(hour='9', minute='30'),
    },
}

# ─────────────────────────────────────────────
# EMAIL — Resend HTTP API (sem SMTP, usa HTTPS 443)
# ─────────────────────────────────────────────
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='DN Imob <noreply@dnsoftware.com.br>')
EMAIL_BACKEND      = 'apps.core.email_backend.ResendEmailBackend'
RESEND_API_KEY     = env('RESEND_API_KEY', default='')

# ─────────────────────────────────────────────
# SICREDI (globais — cada tenant tem ConfigSicredi no banco)
# ─────────────────────────────────────────────
SICREDI_API_URL = env('SICREDI_API_URL', default='https://cobranca.sicredi.com.br/v1')
SICREDI_TOKEN_URL = env('SICREDI_TOKEN_URL', default='https://auth.sicredi.com.br/oauth/token')
SICREDI_WEBHOOK_SECRET = env('SICREDI_WEBHOOK_SECRET', default='')

# Exige ConfigSicredi.webhook_secret em produção (ver apps/sicredi/service.py::processar_webhook).
# Derivado de DEBUG aqui, mas como setting própria — não lemos settings.DEBUG
# direto na regra porque o test runner do Django força DEBUG=False em TODOS
# os testes (mesmo com --settings=dev), e overridar DEBUG em teste reativa o
# django-debug-toolbar (que não convive bem com a troca de schema do
# webhook). dev.py redefine isso explicitamente para False.
SICREDI_WEBHOOK_SECRET_REQUIRED = not DEBUG

# ─────────────────────────────────────────────
# EVOLUTION API (WhatsApp)
# ─────────────────────────────────────────────
EVOLUTION_API_URL = env('EVOLUTION_API_URL', default='http://evolution:8080')
EVOLUTION_API_KEY = env('EVOLUTION_API_KEY', default='')
EVOLUTION_WEBHOOK_TOKEN = env('EVOLUTION_WEBHOOK_TOKEN', default='')

SITE_BASE_URL = env('SITE_BASE_URL', default='https://dnsoftware.com.br')

# ─────────────────────────────────────────────
# ASAAS — assinatura (DN Software cobra a imobiliária). Conta única, global
# (não confundir com futura integração Asaas por-tenant do menu Boleto).
# Default aponta pro sandbox — nunca produção por engano sem API key setada.
# ─────────────────────────────────────────────
ASAAS_API_URL = env('ASAAS_API_URL', default='https://api-sandbox.asaas.com/v3')
ASAAS_API_KEY = env('ASAAS_API_KEY', default='')
ASAAS_WEBHOOK_TOKEN = env('ASAAS_WEBHOOK_TOKEN', default='')

# Chave pública (Asaas.js, tokenização de cartão no frontend) — diferente da
# API key privada. Painel Asaas → Integrações → Chaves de API.
ASAAS_PUBLIC_KEY = env('ASAAS_PUBLIC_KEY', default='')

# URL do Asaas.js derivada de ASAAS_API_URL, pra nunca dessincronizar
# ambiente da API com ambiente do script de tokenização.
ASAAS_JS_URL = (
	'https://sandbox.asaas.com/static/js/asaas.js'
	if 'sandbox' in ASAAS_API_URL
	else 'https://www.asaas.com/static/js/asaas.js'
)

# ─────────────────────────────────────────────
# MISC
# ─────────────────────────────────────────────
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# ─────────────────────────────────────────────
# FORÇAR ORDEM DE MIGRATIONS
# O admin depende de core.Usuario (AUTH_USER_MODEL)
# mas o migrate_schemas rodava admin antes de core.
# Sobrescrevemos as migrations do admin para
# adicionar dependência explícita no core.
# ─────────────────────────────────────────────
MIGRATION_MODULES = {
    'admin': 'apps.core.migrations_admin',
}
