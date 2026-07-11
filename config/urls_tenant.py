# config/urls_tenant.py
# Rotas usadas dentro de cada tenant/subdomínio

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.tenants import views as tv

urlpatterns = [
    # Autenticação
    path('admin/', admin.site.urls),  # ← ADICIONAR
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='core/login.html'),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(next_page='login'),
        name='logout',
    ),

    # Home / Dashboard do tenant
    # path('', tv.dashboard, name='home'),
    path('', tv.dashboard, name='dashboard'),

    path('imoveis/', include('apps.imoveis.urls')),
    path('inquilinos/', include('apps.inquilinos.urls')),
    path('contratos/', include('apps.contratos.urls')),
    path('financeiro/', include('apps.financeiro.urls')),
    path('relatorios/', include('apps.relatorios.urls')),
    path('sicredi/', include('apps.sicredi.urls')),
    path('whatsapp/', include('apps.whatsapp.urls')),

    # Configurações da conta
    path('configuracoes/conta/', tv.config_conta, name='config_conta'),

    # Configurações Sicredi
    path('configuracoes/sicredi/', tv.config_sicredi, name='config_sicredi'),
    path('configuracoes/sicredi/testar/', tv.testar_sicredi, name='testar_sicredi'),
    path(
        'configuracoes/sicredi/webhook-secret/regenerar/',
        tv.regenerar_webhook_secret_sicredi,
        name='regenerar_webhook_secret_sicredi',
    ),

    # Configurações WhatsApp
    path('configuracoes/whatsapp/', tv.config_whatsapp, name='config_whatsapp'),
    path('configuracoes/whatsapp/qrcode/', tv.whatsapp_qrcode, name='whatsapp_qrcode'),
    path('configuracoes/whatsapp/status/', tv.whatsapp_status, name='whatsapp_status'),
    path('configuracoes/whatsapp/templates/', tv.whatsapp_templates, name='whatsapp_templates'),
    path(
        'configuracoes/whatsapp/templates/<int:template_id>/editar/',
        tv.whatsapp_template_editar,
        name='whatsapp_template_editar',
    ),

    # Usuários
    path('configuracoes/usuarios/', tv.usuarios_lista, name='usuarios_lista'),
    path('configuracoes/usuarios/convidar/', tv.usuario_convidar, name='usuario_convidar'),
    path('configuracoes/usuarios/<int:usuario_id>/editar/', tv.usuario_editar, name='usuario_editar'),
    path('configuracoes/usuarios/<int:usuario_id>/desativar/', tv.usuario_desativar, name='usuario_desativar'),

    # Redefinição de senha
    path('senha/redefinir/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset.html',
             email_template_name='registration/password_reset_email.txt',
         ),
         name='password_reset'),

    path('senha/redefinir/enviado/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),

    path('senha/redefinir/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
         ),
         name='password_reset_confirm'),

    path('senha/redefinir/concluido/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),

]

# Debug Toolbar somente em desenvolvimento
if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
