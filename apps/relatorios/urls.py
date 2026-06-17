from django.urls import path
from . import views

urlpatterns = [
    path('',                  views.relatorios_index,  name='relatorios_index'),
    path('dashboard/',        views.dashboard,          name='relatorios_dashboard'),
    path('extrato/',          views.extrato,            name='relatorio_extrato'),
    path('inadimplencia/',    views.inadimplencia,      name='relatorio_inadimplencia'),
    path('imoveis/',          views.imoveis,            name='relatorio_imoveis'),
    path('contratos-ativos/', views.contratos_ativos,   name='relatorio_contratos'),
]
