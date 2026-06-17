from django.urls import path
from . import views

urlpatterns = [
    path('',                  views.inquilino_lista,   name='inquilino_lista'),
    path('novo/',             views.inquilino_criar,   name='inquilino_criar'),
    path('<int:pk>/',         views.inquilino_detalhe, name='inquilino_detalhe'),
    path('<int:pk>/editar/',  views.inquilino_editar,  name='inquilino_editar'),
    path('<int:pk>/excluir/', views.inquilino_excluir, name='inquilino_excluir'),
]
