# apps/sicredi/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('boleto/<int:parcela_pk>/emitir/',   views.boleto_emitir,   name='boleto_emitir'),
    path('boleto/<int:parcela_pk>/cancelar/', views.boleto_cancelar, name='boleto_cancelar'),
]

# ── O webhook vai no urls_public.py (schema public) ──────────────────────────
# path('sicredi/webhook/', sicredi_views.webhook_sicredi, name='sicredi_webhook'),
