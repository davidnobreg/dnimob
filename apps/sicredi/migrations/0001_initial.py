from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contratos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Boleto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nosso_numero', models.CharField(max_length=20, unique=True, verbose_name='Nosso Número')),
                ('linha_digitavel', models.CharField(blank=True, max_length=60, verbose_name='Linha Digitável')),
                ('codigo_barras', models.CharField(blank=True, max_length=50, verbose_name='Código de Barras')),
                ('url_boleto', models.URLField(blank=True, verbose_name='URL do Boleto')),
                ('status', models.CharField(choices=[('emitido','Emitido'),('pago','Pago'),('vencido','Vencido'),('cancelado','Cancelado')], default='emitido', max_length=20, verbose_name='Status')),
                ('emitido_em', models.DateTimeField(blank=True, null=True, verbose_name='Emitido em')),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('parcela', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='boleto', to='contratos.parcela', verbose_name='Parcela')),
            ],
            options={'verbose_name': 'Boleto', 'verbose_name_plural': 'Boletos'},
        ),
    ]
