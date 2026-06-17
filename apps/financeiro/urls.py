# apps/financeiro/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('',                      views.financeiro_dashboard, name='financeiro_dashboard'),
    path('lancamentos/',          views.lancamento_lista,     name='lancamento_lista'),
    path('lancamentos/novo/',     views.lancamento_criar,     name='lancamento_criar'),
    path('lancamentos/<int:pk>/editar/',  views.lancamento_editar,   name='lancamento_editar'),
    path('lancamentos/<int:pk>/excluir/', views.lancamento_excluir,  name='lancamento_excluir'),
    path('inadimplencia/',        views.inadimplencia,        name='inadimplencia'),
]
