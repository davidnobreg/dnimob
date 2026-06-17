"""config/settings/dev.py"""

from .base import *  # noqa

# =============================================================================
# Configurações gerais de desenvolvimento
# =============================================================================

DEBUG = True

ALLOWED_HOSTS = ['*']

# =============================================================================
# Apps de desenvolvimento
# =============================================================================

DEV_APPS = [
    'debug_toolbar',
    'django_extensions',
]

for app in DEV_APPS:
    if app not in INSTALLED_APPS:
        INSTALLED_APPS.append(app)

# =============================================================================
# Middleware de desenvolvimento
# =============================================================================

DEBUG_TOOLBAR_MIDDLEWARE = 'debug_toolbar.middleware.DebugToolbarMiddleware'

if DEBUG_TOOLBAR_MIDDLEWARE not in MIDDLEWARE:
    MIDDLEWARE.insert(1, DEBUG_TOOLBAR_MIDDLEWARE)

# =============================================================================
# Django Debug Toolbar
# =============================================================================

INTERNAL_IPS = [
    'localhost',
    '127.0.0.1',

]

# =============================================================================
# E-mail em desenvolvimento
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# =============================================================================
# Cache em memória no dev (não depende de Redis pra subir o runserver)
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# =============================================================================
# Logs detalhados em desenvolvimento
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },

    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

DEFAULT_FROM_EMAIL = 'DNImob <noreply@dnsoftware.com.br>'
