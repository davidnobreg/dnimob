import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import _criar_templates_padrao

logger = logging.getLogger(__name__)
Usuario = get_user_model()


@shared_task(bind=True, max_retries=3)
def provisionar_tenant(self, tenant_pk: int, dados_admin: dict):
    """
    Cria schema PostgreSQL, roda migrate_schemas, cria admin e templates.
    Executado no Celery worker — libera o request thread do onboarding.
    ATENÇÃO: dados_admin trafega pelo Redis; garanta que Redis não seja público.
    """
    from .models import Tenant
    from django_tenants.utils import schema_context

    tenant = Tenant.objects.get(pk=tenant_pk)
    tenant.provisionamento_status = 'provisionando'
    tenant.save(update_fields=['provisionamento_status'])

    try:
        tenant.auto_create_schema = True
        tenant.create_schema(check_if_exists=True)

        with schema_context(tenant.schema_name):
            nome = dados_admin['nome']
            admin = Usuario.objects.create_user(
                username=dados_admin['email'],
                email=dados_admin['email'],
                password=dados_admin['senha'],
                first_name=nome.split()[0],
                last_name=' '.join(nome.split()[1:]),
            )
            admin.is_staff = True
            admin.save()
            _criar_templates_padrao()

        tenant.provisionamento_status = 'pronto'
        tenant.save(update_fields=['provisionamento_status'])
        logger.info('Tenant provisionado: %s (schema=%s)', tenant.nome, tenant.schema_name)

    except Exception as exc:
        tenant.provisionamento_status = 'erro'
        tenant.save(update_fields=['provisionamento_status'])
        logger.error('Falha ao provisionar tenant %s: %s', tenant_pk, exc)
        raise self.retry(exc=exc, countdown=30)
