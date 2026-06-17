"""apps/core/models.py"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuário do sistema. Vive no schema do tenant."""

    PERFIL_CHOICES = [
        ('admin',      'Administrador'),
        ('gerente',    'Gerente'),
        ('atendente',  'Atendente'),
        ('financeiro', 'Financeiro'),
        ('readonly',   'Somente leitura'),
    ]

    perfil    = models.CharField(max_length=20, choices=PERFIL_CHOICES, default='atendente')
    telefone  = models.CharField(max_length=20, blank=True)
    foto      = models.ImageField(upload_to='usuarios/fotos/', blank=True, null=True)

    class Meta:
        verbose_name        = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.perfil})'

    @property
    def nome_display(self):
        return self.get_full_name() or self.username

    @property
    def is_admin_imob(self):
        return self.perfil == 'admin'
