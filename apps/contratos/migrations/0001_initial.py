from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('imoveis', '0001_initial'),
        ('inquilinos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Contrato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=30, unique=True, verbose_name='Número do Contrato')),
                ('status', models.CharField(choices=[('ativo','Ativo'),('encerrado','Encerrado'),('rescindido','Rescindido'),('pendente','Pendente de Assinatura')], default='pendente', max_length=20, verbose_name='Status')),
                ('data_inicio', models.DateField(verbose_name='Início do Contrato')),
                ('data_fim', models.DateField(verbose_name='Fim do Contrato')),
                ('data_assinatura', models.DateField(blank=True, null=True, verbose_name='Data de Assinatura')),
                ('valor_aluguel', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Valor do Aluguel (R$)')),
                ('valor_condominio', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Condomínio (R$)')),
                ('valor_iptu', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='IPTU Mensal (R$)')),
                ('dia_vencimento', models.PositiveSmallIntegerField(default=10, verbose_name='Dia de Vencimento')),
                ('indice_reajuste', models.CharField(choices=[('igpm','IGP-M'),('ipca','IPCA'),('inpc','INPC'),('fixo','Percentual Fixo'),('nenhum','Sem Reajuste')], default='igpm', max_length=10, verbose_name='Índice de Reajuste')),
                ('percentual_fixo', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Percentual Fixo (%)')),
                ('periodicidade_reajuste', models.PositiveSmallIntegerField(default=12, verbose_name='Periodicidade (meses)')),
                ('tipo_garantia', models.CharField(choices=[('fiador','Fiador'),('caucao','Caução (Depósito)'),('seguro','Seguro Fiança'),('titulo','Título de Capitalização'),('nenhuma','Sem Garantia')], default='nenhuma', max_length=20, verbose_name='Tipo de Garantia')),
                ('valor_caucao', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor Caução (R$)')),
                ('multa_rescisao', models.DecimalField(decimal_places=2, default=10, max_digits=5, verbose_name='Multa Rescisória (%)')),
                ('clausulas_adicionais', models.TextField(blank=True, verbose_name='Cláusulas Adicionais')),
                ('observacoes', models.TextField(blank=True, verbose_name='Observações Internas')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('imovel', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contratos', to='imoveis.imovel', verbose_name='Imóvel')),
                ('inquilino', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contratos', to='inquilinos.inquilino', verbose_name='Inquilino')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contratos', to=settings.AUTH_USER_MODEL, verbose_name='Responsável')),
            ],
            options={'verbose_name': 'Contrato', 'verbose_name_plural': 'Contratos', 'ordering': ['-data_inicio']},
        ),
        migrations.CreateModel(
            name='Parcela',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveSmallIntegerField(verbose_name='Nº Parcela')),
                ('data_vencimento', models.DateField(verbose_name='Vencimento')),
                ('data_pagamento', models.DateField(blank=True, null=True, verbose_name='Data de Pagamento')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Aluguel (R$)')),
                ('valor_condominio', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Condomínio (R$)')),
                ('valor_iptu', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='IPTU (R$)')),
                ('valor_multa', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Multa (R$)')),
                ('valor_desconto', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Desconto (R$)')),
                ('status', models.CharField(choices=[('pendente','Pendente'),('pago','Pago'),('atrasado','Atrasado'),('cancelado','Cancelado')], default='pendente', max_length=20, verbose_name='Status')),
                ('observacao', models.CharField(blank=True, max_length=200, verbose_name='Observação')),
                ('contrato', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parcelas', to='contratos.contrato')),
            ],
            options={'verbose_name': 'Parcela', 'verbose_name_plural': 'Parcelas', 'ordering': ['data_vencimento'], 'unique_together': {('contrato', 'numero')}},
        ),
    ]
