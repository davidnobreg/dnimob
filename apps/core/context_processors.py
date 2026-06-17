"""apps/core/context_processors.py"""
def tenant_context(request):
    tenant = getattr(request, 'tenant', None)
    return {
        'tenant': tenant,
        'tenant_nome': getattr(tenant, 'nome_fantasia', ''),
        'tenant_cor': getattr(tenant, 'cor_primaria', '#1e40af'),
    }
