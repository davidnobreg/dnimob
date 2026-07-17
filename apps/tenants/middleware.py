"""
middleware.py — Fase 2
Middlewares para controle de acesso por plano e verificação de limites.
"""

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django_tenants.utils import get_public_schema_name


class PlanoAcessoMiddleware:
    """
    Bloqueia acesso ao tenant se o plano estiver expirado ou inativo.
    Redireciona para a tela de acesso bloqueado.

    Exceção: tenant em modo read-only (trial vencido sem pagamento —
    Tenant.acesso_readonly) nunca é bloqueado por completo. GET passa
    normalmente; métodos de escrita levam 403 com tela de aviso.
    """

    URLS_LIBERADAS = [
        '/acesso-bloqueado/',
        '/logout/',
        '/login/',
        '/senha/redefinir/',
        '/static/',
        '/media/',
        '/favicon.ico',
    ]

    METODOS_SEGUROS = ('GET', 'HEAD', 'OPTIONS')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Só aplica em schemas de tenant (não no public)
        schema = getattr(request, 'tenant', None)
        if schema and schema.schema_name != get_public_schema_name():
            # Verifica se a URL está liberada
            path = request.path_info
            liberada = any(path.startswith(url) for url in self.URLS_LIBERADAS)

            if not liberada:
                if schema.acesso_readonly:
                    if request.method not in self.METODOS_SEGUROS:
                        return render(request, 'tenants/acesso_somente_leitura.html', status=403)
                elif not schema.acesso_permitido:
                    return redirect('acesso_bloqueado')

        return self.get_response(request)


class LimitePlanoMiddleware:
    """
    Injeta no request os limites do plano atual para uso nas views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, 'tenant', None)
        if tenant and tenant.schema_name != get_public_schema_name() and tenant.plano:
            request.plano_limites = {
                'imoveis': tenant.plano.limite_imoveis,
                'contratos': tenant.plano.limite_contratos,
                'usuarios': tenant.plano.limite_usuarios,
                'whatsapp': tenant.plano.tem_whatsapp,
            }
        else:
            request.plano_limites = {}

        return self.get_response(request)


class TenantBrandingMiddleware:
    """
    Injeta cores e logo do tenant no contexto (via request) para uso nos templates.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, 'tenant', None)
        if tenant and tenant.schema_name != get_public_schema_name():
            request.branding = {
                'cor_primaria': tenant.cor_primaria,
                'cor_secundaria': tenant.cor_secundaria,
                'cor_acento': tenant.cor_acento,
                'logo_url': tenant.logo.url if tenant.logo else None,
                'nome': tenant.nome,
            }
        else:
            request.branding = {}

        return self.get_response(request)
