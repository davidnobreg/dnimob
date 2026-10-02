"""apps/core/tenancy.py"""
from django.db import connection


def get_tenant_atual():
	"""
	Retorna o Tenant do schema ativo.

	Em tarefas Celery o schema é ativado com schema_context(), que deixa
	connection.tenant como um FakeTenant (só tem schema_name). Por isso o
	Tenant real é buscado pelo schema_name, nunca usado direto de connection.tenant.
	"""
	from apps.tenants.models import Tenant

	atual = connection.tenant
	if isinstance(atual, Tenant):
		return atual

	schema = connection.schema_name
	try:
		return Tenant.objects.get(schema_name=schema)
	except Tenant.DoesNotExist:
		raise Tenant.DoesNotExist(f'Nenhum Tenant encontrado para o schema "{schema}".') from None
