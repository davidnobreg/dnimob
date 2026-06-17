from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contratos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lancamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('receita','Receita'),('despesa','Despesa')], max_length=10, verbose_name='Tipo')),
                ('categoria', models.CharField(choices=[('aluguel','Aluguel'),('condominio','Condomínio'),('iptu','IPTU'),('multa','Multa'),('taxa_admin','Taxa de Administração'),('outros_rec','Outras Receitas'),('manutencao','Manutenção'),('comissao','Comissão'),('despesa_adm','Despesa Administrativa'),('imposto','Imposto'),('outros_desp','Outras Despesas')], max_length=20, verbose_name='Categoria')),
                ('status', models.CharField(choices=[('previsto','Previsto'),('realizado','Realizado'),('cancelado','Cancelado')], default='realizado', max_length=20, verbose_name='Status')),
                ('descricao', models.CharField(max_length=300, verbose_name='Descrição')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Valor (R$)')),
                ('data', models.DateField(verbose_name='Data')),
                ('data_prevista', models.DateField(blank=True, null=True, verbose_name='Data Prevista')),
                ('observacao', models.TextField(blank=True, verbose_name='Observação')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('contrato', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lancamentos', to='contratos.contrato', verbose_name='Contrato')),
                ('parcela', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lancamentos', to='contratos.parcela', verbose_name='Parcela')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Responsável')),
            ],
            options={'verbose_name': 'Lançamento', 'verbose_name_plural': 'Lançamentos', 'ordering': ['-data', '-criado_em']},
        ),
    ]
