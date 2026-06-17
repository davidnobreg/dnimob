"""config/celery.py"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('imobiliaria')
app.config_from_object('django.conf:settings', namespace='CELERY')


class TenantTask(app.Task):
    """
    Task base que executa dentro do schema correto.
    Uso: @shared_task(base=TenantTask)
    O primeiro argumento deve ser sempre schema_name.
    """
    abstract = True

    def __call__(self, schema_name, *args, **kwargs):
        from django_tenants.utils import schema_context
        with schema_context(schema_name):
            return self.run(*args, **kwargs)


app.autodiscover_tasks()
