# apps/imoveis/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.imovel_lista,      name='imovel_lista'),
    path('novo/',                               views.imovel_criar,      name='imovel_criar'),
    path('<int:pk>/',                           views.imovel_detalhe,    name='imovel_detalhe'),
    path('<int:pk>/editar/',                    views.imovel_editar,     name='imovel_editar'),
    path('<int:pk>/excluir/',                   views.imovel_excluir,    name='imovel_excluir'),
    path('inativos/',                             views.imovel_inativos,   name='imovel_inativos'),
    path('<int:pk>/reativar/',                    views.imovel_reativar,   name='imovel_reativar'),
    path('foto/<int:pk>/excluir/',              views.foto_excluir,      name='imovel_foto_excluir'),
    path('foto/<int:pk>/principal/',            views.foto_principal,    name='imovel_foto_principal'),
]


# ──────────────────────────────────────────────────────────
# apps/inquilinos/urls.py
# ──────────────────────────────────────────────────────────
# from django.urls import path
# from . import views
#
# urlpatterns = [
#     path('',              views.inquilino_lista,   name='inquilino_lista'),
#     path('novo/',         views.inquilino_criar,   name='inquilino_criar'),
#     path('<int:pk>/',     views.inquilino_detalhe, name='inquilino_detalhe'),
#     path('<int:pk>/editar/',  views.inquilino_editar,  name='inquilino_editar'),
#     path('<int:pk>/excluir/', views.inquilino_excluir, name='inquilino_excluir'),
# ]
