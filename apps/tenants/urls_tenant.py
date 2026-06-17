from django.urls import path
from . import views_tenant

urlpatterns = [
    path('',           views_tenant.ContaView.as_view(),   name='conta'),
    path('whatsapp/',  views_tenant.WhatsAppConfigView.as_view(), name='conta_whatsapp'),
    path('sicredi/',   views_tenant.SicrediConfigView.as_view(),  name='conta_sicredi'),
]
