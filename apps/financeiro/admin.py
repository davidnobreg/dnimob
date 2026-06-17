from django.contrib import admin
from .models import Lancamento


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display  = ['data', 'tipo', 'categoria', 'descricao', 'valor', 'status']
    list_filter   = ['tipo', 'categoria', 'status']
    search_fields = ['descricao', 'contrato__numero']
    ordering      = ['-data']
    date_hierarchy = 'data'
