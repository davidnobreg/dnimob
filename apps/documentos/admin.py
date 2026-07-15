from django.contrib import admin

from .models import (
	ContratoDocumentoGerado,
	ModeloDocumento,
	ModeloDocumentoHistorico,
	VariavelDocumento,
)


@admin.register(ModeloDocumento)
class ModeloDocumentoAdmin(admin.ModelAdmin):
	list_display = ('titulo', 'tipo', 'ativo', 'padrao', 'atualizado_em')
	list_filter = ('tipo', 'ativo', 'padrao')
	search_fields = ('titulo',)


@admin.register(ModeloDocumentoHistorico)
class ModeloDocumentoHistoricoAdmin(admin.ModelAdmin):
	list_display = ('modelo', 'salvo_em')
	list_filter = ('salvo_em',)


@admin.register(VariavelDocumento)
class VariavelDocumentoAdmin(admin.ModelAdmin):
	list_display = ('slug', 'label', 'categoria', 'ativo')
	list_filter = ('categoria', 'ativo')
	search_fields = ('slug', 'label')


@admin.register(ContratoDocumentoGerado)
class ContratoDocumentoGeradoAdmin(admin.ModelAdmin):
	list_display = ('titulo', 'contrato', 'modelo', 'status', 'gerado_em')
	list_filter = ('status', 'gerado_em')
	search_fields = ('titulo',)
