from django.contrib import admin
from .models import Contrato, Parcela


class ParcelaInline(admin.TabularInline):
    model = Parcela
    extra = 0
    fields = ['numero', 'data_vencimento', 'valor', 'status', 'data_pagamento']
    readonly_fields = ['numero']


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display  = ['numero', 'inquilino', 'imovel', 'status', 'data_inicio', 'data_fim', 'valor_aluguel']
    list_filter   = ['status', 'indice_reajuste', 'tipo_garantia']
    search_fields = ['numero', 'inquilino__nome', 'imovel__codigo']
    ordering      = ['-data_inicio']
    inlines       = [ParcelaInline]


@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display  = ['contrato', 'numero', 'data_vencimento', 'valor', 'status', 'data_pagamento']
    list_filter   = ['status']
    search_fields = ['contrato__numero', 'contrato__inquilino__nome']
    ordering      = ['data_vencimento']
