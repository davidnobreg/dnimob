from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import (
    ConfigSicredi,
    Domain,
    InstanciaWhatsApp,
    Plano,
    TemplateWhatsApp,
    Tenant,
)


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco_mensal', 'limite_imoveis', 'limite_usuarios', 'tem_whatsapp', 'ativo']
    list_editable = ['preco_mensal', 'ativo']


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'schema_name', 'plano', 'ativo', 'trial', 'trial_expira', 'criado_em']
    list_filter = ['ativo', 'trial', 'plano']
    search_fields = ['nome', 'email', 'schema_name']
    readonly_fields = ['schema_name', 'criado_em', 'atualizado_em', 'status_assinatura']
    inlines = [DomainInline]
    fieldsets = (
        ('Identificação', {'fields': ('schema_name', 'nome', 'cnpj', 'email', 'telefone')}),
        ('Endereço', {'fields': ('endereco', 'cidade', 'estado', 'cep')}),
        ('Plano e Status', {'fields': ('plano', 'ativo', 'trial', 'trial_expira', 'assinatura_expira', 'status_assinatura')}),
        ('Visual', {'fields': ('logo', 'cor_primaria', 'cor_secundaria', 'cor_acento'), 'classes': ('collapse',)}),
        ('Metadados', {'fields': ('criado_em', 'atualizado_em'), 'classes': ('collapse',)}),
    )


@admin.register(ConfigSicredi)
class ConfigSicrediAdmin(admin.ModelAdmin):
    list_display = ['beneficiario', 'ambiente', 'cooperativa', 'ativo']
    list_filter = ['ambiente', 'ativo']


@admin.register(InstanciaWhatsApp)
class InstanciaWhatsAppAdmin(admin.ModelAdmin):
    list_display = ['nome_instancia', 'status', 'numero_telefone', 'conectado_em']
    list_filter = ['status']
    readonly_fields = ['qr_code', 'conectado_em', 'criado_em', 'atualizado_em']


@admin.register(TemplateWhatsApp)
class TemplateWhatsAppAdmin(admin.ModelAdmin):
    list_display = ['evento', 'get_evento_display', 'ativo', 'atualizado_em']
    list_filter = ['ativo']
    list_editable = ['ativo']
    search_fields = ['evento', 'mensagem']
