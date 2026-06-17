from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_configsicredi_alter_domain_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='instanciawhatsapp',
            name='evolution_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='URL base da Evolution API, ex: http://192.168.1.100:8080',
                verbose_name='URL da Evolution API',
            ),
            preserve_default=False,
        ),
    ]