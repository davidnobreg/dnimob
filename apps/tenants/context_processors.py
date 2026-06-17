"""
context_processors.py — Fase 2
Injeta dados do tenant (branding, plano, limites) em todos os templates.
"""

from django_tenants.utils import get_public_schema_name


def tenant_context(request):
    """Disponibiliza tenant, branding e plano em todos os templates."""
    tenant = getattr(request, 'tenant', None)
    if not tenant or tenant.schema_name == get_public_schema_name():
        return {}

    return {
        'tenant': tenant,
        'branding': getattr(request, 'branding', {}),
        'plano_limites': getattr(request, 'plano_limites', {}),
        'status_assinatura': tenant.status_assinatura,
        'acesso_whatsapp': tenant.plano.tem_whatsapp if tenant.plano else False,
    }
