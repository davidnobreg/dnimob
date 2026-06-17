from django.contrib import admin
from .models import Imovel, FotoImovel


class FotoInline(admin.TabularInline):
    model = FotoImovel
    extra = 0
    fields = ['imagem', 'legenda', 'principal', 'ordem']


@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    list_display  = ['codigo', 'tipo', 'status', 'finalidade', 'bairro', 'cidade', 'estado', 'valor_aluguel', 'criado_em']
    list_filter   = ['tipo', 'status', 'finalidade', 'estado']
    search_fields = ['codigo', 'logradouro', 'bairro', 'cidade', 'proprietario_nome']
    ordering      = ['-criado_em']
    inlines       = [FotoInline]
    actions       = ['reativar_imoveis', 'desativar_imoveis']  # ← adicionar

    fieldsets = (
        ('Identificação', {'fields': ('codigo', 'tipo', 'finalidade', 'status', 'responsavel')}),
        ('Localização', {'fields': ('cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado')}),
        ('Características', {'fields': ('area_total', 'area_construida', 'quartos', 'suites', 'banheiros', 'vagas', 'mobilia')}),
        ('Comodidades', {'fields': ('piscina', 'academia', 'churrasqueira', 'portaria', 'elevador', 'pet_friendly')}),
        ('Valores', {'fields': ('valor_aluguel', 'valor_venda', 'valor_condominio', 'valor_iptu')}),
        ('Proprietário', {'fields': ('proprietario_nome', 'proprietario_cpf_cnpj', 'proprietario_telefone', 'proprietario_email')}),
        ('Extras', {'fields': ('descricao',)}),
    )

    @admin.action(description='✅ Reativar imóveis selecionados (→ Disponível)')
    def reativar_imoveis(self, request, queryset):
        total = queryset.filter(status='inativo').update(status='disponivel')
        self.message_user(request, f'{total} imóvel(is) reativado(s) com sucesso.')

    @admin.action(description='🚫 Desativar imóveis selecionados (→ Inativo)')
    def desativar_imoveis(self, request, queryset):
        # Bloqueia os que têm contrato ativo
        bloqueados = 0
        desativados = 0
        for imovel in queryset:
            if imovel.contratos.filter(status='ativo').exists():
                bloqueados += 1
            else:
                imovel.status = 'inativo'
                imovel.save()
                desativados += 1
        msg = f'{desativados} imóvel(is) desativado(s).'
        if bloqueados:
            msg += f' {bloqueados} não desativado(s) por ter contrato ativo.'
        self.message_user(request, msg)