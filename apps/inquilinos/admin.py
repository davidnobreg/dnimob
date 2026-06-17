from django.contrib import admin
from .models import Inquilino


@admin.register(Inquilino)
class InquilinoAdmin(admin.ModelAdmin):
    list_display  = ['nome', 'tipo', 'status', 'telefone', 'email', 'cidade', 'criado_em']
    list_filter   = ['tipo', 'status']
    search_fields = ['nome', 'cpf', 'cnpj', 'telefone', 'email']
    ordering      = ['nome']
    fieldsets = (
        ('Identificação', {'fields': ('tipo', 'status', 'nome', 'cpf', 'rg', 'data_nascimento', 'estado_civil', 'profissao', 'renda_mensal', 'nacionalidade')}),
        ('PJ', {'fields': ('cnpj', 'razao_social', 'nome_fantasia', 'inscricao_estadual'), 'classes': ('collapse',)}),
        ('Contato', {'fields': ('telefone', 'telefone2', 'email')}),
        ('Endereço', {'fields': ('cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado')}),
        ('Fiador', {'fields': ('fiador_nome', 'fiador_cpf', 'fiador_telefone'), 'classes': ('collapse',)}),
        ('Extras', {'fields': ('foto', 'observacoes')}),
    )
