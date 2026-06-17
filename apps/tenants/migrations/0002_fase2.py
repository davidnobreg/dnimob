"""
Migration Fase 2 — modelos adicionados/atualizados:
- Plano (atualizado com preco_mensal)
- Tenant (logo, cores, trial, assinatura_expira)
- ConfigSicredi (webhook_secret)
- InstanciaWhatsApp (nova)
- TemplateWhatsApp (nova)
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        # preco_mensal, logo, cor_primaria e cor_secundaria já vêm criados em
        # 0001_initial (Plano/Tenant) — removidos daqui pra não duplicar coluna
        # em schemas novos (0001 foi reeditado depois que 0002 já tinha sido
        # aplicado nos schemas existentes; histórico de migration não é afetado).
        migrations.AddField(
            model_name='tenant',
            name='cor_acento',
            field=models.CharField(default='#3f83f8', max_length=7),
        ),
        migrations.AddField(
            model_name='tenant',
            name='trial',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='trial_expira',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='assinatura_expira',
            field=models.DateField(blank=True, null=True),
        ),
        # Adicionar webhook_secret ao ConfigSicredi
        #migrations.AddField(
        #    model_name='configsicredi',
        #    name='webhook_secret',
        #    field=models.CharField(blank=True, max_length=100),
        #),
        # Criar InstanciaWhatsApp
        migrations.CreateModel(
            name='InstanciaWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_instancia', models.CharField(max_length=100, unique=True)),
                ('token_api', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(
                    choices=[
                        ('desconectado', 'Desconectado'),
                        ('aguardando_qr', 'Aguardando QR Code'),
                        ('conectado', 'Conectado'),
                        ('erro', 'Erro'),
                    ],
                    default='desconectado',
                    max_length=20,
                )),
                ('numero_telefone', models.CharField(blank=True, max_length=20)),
                ('qr_code', models.TextField(blank=True)),
                ('qr_expira', models.DateTimeField(blank=True, null=True)),
                ('conectado_em', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Instância WhatsApp', 'verbose_name_plural': 'Instâncias WhatsApp'},
        ),
        # Criar TemplateWhatsApp
        migrations.CreateModel(
            name='TemplateWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evento', models.CharField(
                    choices=[
                        ('boas_vindas', 'Boas-vindas ao inquilino'),
                        ('boleto_gerado', 'Boleto gerado'),
                        ('vence_amanha', 'Boleto vence amanhã (D-1)'),
                        ('vence_hoje', 'Boleto vence hoje (D+0)'),
                        ('atraso_3', 'Atraso 3 dias'),
                        ('atraso_7', 'Atraso 7 dias'),
                        ('atraso_15', 'Atraso 15 dias'),
                        ('pagamento_confirmado', 'Pagamento confirmado'),
                        ('contrato_enviado', 'Contrato enviado'),
                        ('contrato_60dias', 'Contrato vencendo em 60 dias'),
                        ('contrato_30dias', 'Contrato vencendo em 30 dias'),
                        ('distrato_enviado', 'Distrato enviado'),
                        ('recibo_pagamento', 'Recibo de pagamento'),
                    ],
                    max_length=30,
                    unique=True,
                )),
                ('ativo', models.BooleanField(default=True)),
                ('mensagem', models.TextField()),
                ('variaveis_disponiveis', models.JSONField(default=list)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Template WhatsApp', 'verbose_name_plural': 'Templates WhatsApp'},
        ),
    ]
