# config/urls_public.py
# Rotas do schema public

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from apps.tenants import views as tv
from apps.sicredi import views as sicredi_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', tv.landing, name='landing'),
    path('cadastro/', tv.cadastro_imobiliaria, name='cadastro_imobiliaria'),
    path('cadastro/aguardando/<str:schema>/', tv.cadastro_aguardando, name='cadastro_aguardando'),
    path('cadastro/status/<str:schema>/', tv.cadastro_status, name='cadastro_status'),
    path('cadastro/sucesso/<str:schema>/', tv.cadastro_sucesso, name='cadastro_sucesso'),
    path('login/', tv.login_acesso, name='login_publico'),

    # Webhook Sicredi — público, sem tenant (identifica o tenant pelo beneficiario)
    path('sicredi/webhook/', sicredi_views.webhook_sicredi, name='sicredi_webhook'),

    path('admin-master/', tv.superadmin_dashboard, name='superadmin_dashboard'),
    path('admin-master/tenant/<int:tenant_id>/', tv.superadmin_tenant_detalhe, name='superadmin_tenant_detalhe'),
    path('admin-master/tenant/<int:tenant_id>/toggle/', tv.superadmin_toggle_tenant, name='superadmin_toggle_tenant'),
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
