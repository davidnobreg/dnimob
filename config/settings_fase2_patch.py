"""
config/settings/base.py — atualizado para Fase 2
Adiciona middlewares de plano, context processor de tenant e configurações Evolution API.
"""

# ── Trecho a adicionar/substituir no base.py existente ──────────────────────
# (apenas as seções que mudam na Fase 2)

# MIDDLEWARE — adicionar após TenantMainMiddleware:
MIDDLEWARE_FASE2_ADICIONAR = [
    'apps.tenants.middleware.PlanoAcessoMiddleware',
    'apps.tenants.middleware.LimitePlanoMiddleware',
    'apps.tenants.middleware.TenantBrandingMiddleware',
]

# TEMPLATES → OPTIONS → context_processors — adicionar:
CONTEXT_PROCESSORS_ADICIONAR = [
    'apps.tenants.context_processors.tenant_context',
]

# Evolution API
EVOLUTION_API_URL = 'http://evolution:8080'   # Docker Compose
EVOLUTION_API_KEY = 'sua-api-key-aqui'        # mesmo valor do docker-compose.yml

# Base domain (usado na criação de tenants)
BASE_DOMAIN = 'dnsoftware.com.br'

# TENANT_APPS — adicionar se não estiver:
TENANT_APPS_FASE2 = [
    'apps.tenants',   # já era shared; InstanciaWhatsApp e TemplateWhatsApp ficam no tenant
]

# Exemplo de MIDDLEWARE completo após Fase 2:
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Fase 2:
    'apps.tenants.middleware.PlanoAcessoMiddleware',
    'apps.tenants.middleware.LimitePlanoMiddleware',
    'apps.tenants.middleware.TenantBrandingMiddleware',
]

# LOGIN
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Media files (logos)
import os
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
