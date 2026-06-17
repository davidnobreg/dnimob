from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.contrato_lista,               name='contrato_lista'),
    path('novo/',                               views.contrato_criar,               name='contrato_criar'),
    path('<int:pk>/',                           views.contrato_detalhe,             name='contrato_detalhe'),
    path('<int:pk>/editar/',                    views.contrato_editar,              name='contrato_editar'),
    path('<int:pk>/encerrar/',                  views.contrato_encerrar,            name='contrato_encerrar'),
    path('<int:pk>/pdf/',                       views.contrato_pdf,                 name='contrato_pdf'),
    path('parcela/<int:pk>/pagar/',             views.parcela_registrar_pagamento,  name='parcela_pagar'),
    path('parcela/<int:pk>/estornar/',          views.parcela_estornar,             name='parcela_estornar'),
    path('parcela/<int:pk>/recibo/',            views.recibo_pdf,                   name='parcela_recibo'),
]
