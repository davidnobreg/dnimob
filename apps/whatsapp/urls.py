from django.urls import path
from . import views

urlpatterns = [
    path('historico/',       views.historico,      name='whatsapp_historico'),
    path('status-conexao/',  views.status_conexao, name='whatsapp_status_conexao'),
]
