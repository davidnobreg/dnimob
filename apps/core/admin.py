from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ['username', 'email', 'first_name', 'last_name', 'perfil', 'is_active']
    list_filter   = ['perfil', 'is_active', 'is_staff']
    fieldsets     = UserAdmin.fieldsets + (
        ('Perfil DN Imob', {'fields': ('perfil', 'telefone', 'foto')}),
    )
