from django.urls import path

from . import views

app_name = 'documentos'

urlpatterns = [
	path('', views.lista_modelos, name='lista_modelos'),
	path('novo/', views.criar_modelo, name='criar_modelo'),
	path('<uuid:pk>/editar/', views.editor_modelo, name='editor_modelo'),
	path('<uuid:pk>/salvar/', views.salvar_modelo, name='salvar_modelo'),
	path('gerar/', views.gerar_documento, name='gerar_documento'),
	path('gerado/<uuid:pk>/download/', views.download_documento, name='download_documento'),
	path('contrato/<int:contrato_pk>/', views.lista_documentos_contrato, name='lista_documentos_contrato'),
]
