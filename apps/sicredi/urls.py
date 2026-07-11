# apps/sicredi/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('boleto/<int:parcela_pk>/emitir/',   views.boleto_emitir,   name='boleto_emitir'),
    path('boleto/<int:parcela_pk>/cancelar/', views.boleto_cancelar, name='boleto_cancelar'),
    path('boleto/<int:parcela_pk>/pdf/',      views.boleto_pdf,      name='boleto_pdf'),
    path('contrato/<int:contrato_pk>/boletos/gerar-lote/', views.boletos_gerar_lote, name='boletos_gerar_lote'),
    path('contrato/<int:contrato_pk>/boletos/carne/', views.boletos_carne, name='boletos_carne'),
]

# ── O webhook vai no urls_public.py (schema public) ──────────────────────────
# path('sicredi/webhook/<str:secret>/', sicredi_views.webhook_sicredi, name='sicredi_webhook'),
