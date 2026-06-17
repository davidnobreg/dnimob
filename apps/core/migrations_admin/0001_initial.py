from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Migration 0001 do admin sobrescrita para forçar dependência
    em core.0001_initial — garante que core_usuario existe antes.
    """

    initial = True

    dependencies = [
        # ESSENCIAL: core deve rodar antes do admin
        ('core', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action_time', models.DateTimeField(auto_now=True, verbose_name='action time')),
                ('object_id', models.TextField(null=True, blank=True, verbose_name='object id')),
                ('object_repr', models.CharField(max_length=200, verbose_name='object repr')),
                ('action_flag', models.PositiveSmallIntegerField(verbose_name='action flag')),
                ('change_message', models.TextField(blank=True, verbose_name='change message')),
                ('content_type', models.ForeignKey(
                    to='contenttypes.ContentType',
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    verbose_name='content type',
                )),
                ('user', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    verbose_name='user',
                )),
            ],
            options={
                'ordering': ['-action_time'],
                'db_table': 'django_admin_log',
                'verbose_name': 'log entry',
                'verbose_name_plural': 'log entries',
            },
        ),
    ]
