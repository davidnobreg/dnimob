"""apps/core/storage.py"""
import os
import uuid

from django.db import connection
from django.utils import timezone
from django_tenants.utils import get_public_schema_name


def _tenant_prefix():
	"""Retorna o prefixo do tenant atual. Fallback para 'shared' no schema public."""
	schema = connection.schema_name
	if not schema or schema == get_public_schema_name():
		return 'shared'
	return f'tenants/{schema}'


def upload_to_imoveis_fotos(instance, filename):
	ext = os.path.splitext(filename)[1].lower()
	return f'{_tenant_prefix()}/imoveis/fotos/{uuid.uuid4().hex}{ext}'


def upload_to_inquilinos_fotos(instance, filename):
	ext = os.path.splitext(filename)[1].lower()
	return f'{_tenant_prefix()}/inquilinos/fotos/{uuid.uuid4().hex}{ext}'


def upload_to_usuarios_fotos(instance, filename):
	ext = os.path.splitext(filename)[1].lower()
	return f'{_tenant_prefix()}/usuarios/fotos/{uuid.uuid4().hex}{ext}'


def upload_to_documentos_contratos(instance, filename):
	ext = os.path.splitext(filename)[1].lower()
	now = timezone.now()
	return f'{_tenant_prefix()}/documentos/contratos/{now.year}/{now.month:02d}/{uuid.uuid4().hex}{ext}'


def upload_to_tenant_logos(instance, filename):
	ext = os.path.splitext(filename)[1].lower()
	schema = getattr(instance, 'schema_name', None) or 'shared'
	return f'tenants/{schema}/logos/{uuid.uuid4().hex}{ext}'
