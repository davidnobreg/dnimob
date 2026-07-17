# config/urls_public.py
# Rotas do schema public

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.tenants import views as tv
from apps.sicredi import views as sicredi_views
from apps.billing.webhook import asaas_webhook
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', tv.landing, name='landing'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt',
        content_type='text/plain',
    ), name='robots_txt'),
    path('sitemap.xml', TemplateView.as_view(
        template_name='sitemap.xml',
        content_type='application/xml',
    ), name='sitemap_xml'),
    path('cadastro/', tv.cadastro_imobiliaria, name='cadastro_imobiliaria'),
    path('cadastro/aguardando/<str:schema>/', tv.cadastro_aguardando, name='cadastro_aguardando'),
    path('cadastro/status/<str:schema>/', tv.cadastro_status, name='cadastro_status'),
    path('cadastro/sucesso/<str:schema>/', tv.cadastro_sucesso, name='cadastro_sucesso'),
    path('login/', tv.login_acesso, name='login_publico'),
    path('termos/', tv.termos_uso, name='termos_uso'),
    path('privacidade/', tv.politica_privacidade, name='politica_privacidade'),

    # Webhook Sicredi — público, sem tenant (identifica o tenant pelo beneficiario
    # no payload; o <str:secret> autentica a chamada, já que a Sicredi não envia
    # nenhum header de autenticação nesta versão da API)
    path('sicredi/webhook/<str:secret>/', sicredi_views.webhook_sicredi, name='sicredi_webhook'),

    # Webhook Asaas — público, sem tenant (autentica pelo header
    # asaas-access-token, configurado no painel Asaas)
    path('asaas/webhook/', asaas_webhook, name='asaas_webhook'),

    path('admin-master/', tv.superadmin_dashboard, name='superadmin_dashboard'),
    path('admin-master/criar/', tv.superadmin_criar_tenant, name='superadmin_criar_tenant'),
    path('admin-master/tenant/<int:tenant_id>/', tv.superadmin_tenant_detalhe, name='superadmin_tenant_detalhe'),
    path('admin-master/tenant/<int:tenant_id>/toggle/', tv.superadmin_toggle_tenant, name='superadmin_toggle_tenant'),
    path('admin-master/tenant/<int:tenant_id>/plano/', tv.superadmin_trocar_plano, name='superadmin_trocar_plano'),
    path('admin-master/tenant/<int:tenant_id>/liberar-cobranca/', tv.superadmin_liberar_cobranca, name='superadmin_liberar_cobranca'),
    path('admin-master/tenant/<int:tenant_id>/asaas/', tv.superadmin_asaas_pagamento, name='superadmin_asaas_pagamento'),
    path('admin-master/tenant/<int:tenant_id>/asaas/cartao/', tv.superadmin_asaas_cartao, name='superadmin_asaas_cartao'),
    # dentro do urlpatterns, antes do admin-master/
    path('admin-master/login/', auth_views.LoginView.as_view(
        template_name='tenants/superadmin_login.html',
        next_page='/admin-master/',
    ), name='superadmin_login'),
]

if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
