from django.urls import path
from . import views

urlpatterns = [
    path('',           views.LandingView.as_view(),  name='landing'),
    path('cadastro/',  views.CadastroView.as_view(), name='tenant_cadastro'),
    path('planos/',    views.PlanosView.as_view(),   name='planos'),
]
