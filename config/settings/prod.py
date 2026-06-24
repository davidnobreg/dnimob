"""config/settings/prod.py"""
from .base import *  # noqa

DEBUG = False

SECURE_BROWSER_XSS_FILTER        = True
SECURE_CONTENT_TYPE_NOSNIFF      = True
SECURE_HSTS_SECONDS               = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS    = True
SECURE_HSTS_PRELOAD               = True
SECURE_SSL_REDIRECT               = False  # NPM já termina SSL
SESSION_COOKIE_SECURE             = True
CSRF_COOKIE_SECURE                = True
USE_X_FORWARDED_HOST              = True
SECURE_PROXY_SSL_HEADER           = ('HTTP_X_FORWARDED_PROTO', 'https')

# Arquivos estáticos e mídia via S3
DEFAULT_FILE_STORAGE    = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE     = 'storages.backends.s3boto3.S3StaticStorage'
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME      = env('AWS_S3_REGION_NAME', default='sa-east-1')
AWS_S3_CUSTOM_DOMAIN    = env('AWS_S3_CUSTOM_DOMAIN', default='')
AWS_S3_ENDPOINT_URL  = env('AWS_S3_ENDPOINT_URL', default='')
AWS_ACCESS_KEY_ID    = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')

# ─────────────────────────────────────────────
# SENTRY
# ─────────────────────────────────────────────
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST

# Expande o denylist padrão com campos sensíveis do domínio imobiliário
_DENYLIST = DEFAULT_DENYLIST + [
    # Documentos BR
    'cpf', 'cnpj', 'rg',
    # Auth / credenciais
    'senha', 'nova_senha', 'senha_antiga', 'senha_confirma',
    'api_key', 'token_api', 'token', 'webhook_secret',
    # Sicredi
    'codigo_acesso', 'client_secret', 'codigo_beneficiario',
    # Dados financeiros
    'codigo_barras', 'valor_caucao',
]

sentry_sdk.init(
    dsn=env('SENTRY_DSN', default=''),
    environment=env('SENTRY_ENVIRONMENT', default='production'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=env.float('SENTRY_TRACES_RATE', default=0.1),
    send_default_pii=False,
    event_scrubber=EventScrubber(denylist=_DENYLIST, recursive=True),
)

# ─────────────────────────────────────────────
# EMAIL — Resend via HTTP API (não SMTP)
# ATENÇÃO: DEFAULT_FROM_EMAIL deve usar domínio verificado no painel Resend
# ─────────────────────────────────────────────
RESEND_API_KEY = env('RESEND_API_KEY', default='')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
