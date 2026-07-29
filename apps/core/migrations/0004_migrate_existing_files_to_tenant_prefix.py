import os
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection, migrations
from django_tenants.utils import get_public_schema_name


def _migrate_field(Model, field_name, new_prefix):
	qs = Model.objects.exclude(**{field_name: ''}).exclude(**{field_name: None})
	for obj in qs:
		old_path = getattr(obj, field_name).name
		if not old_path or old_path.startswith('tenants/') or old_path.startswith('shared/'):
			continue
		if not default_storage.exists(old_path):
			print(f'[SKIP] {Model.__name__} pk={obj.pk}: {old_path} nao existe no storage')
			continue
		ext = os.path.splitext(old_path)[1].lower()
		new_path = f'{new_prefix}{uuid.uuid4().hex}{ext}'
		try:
			with default_storage.open(old_path, 'rb') as fh:
				content = fh.read()
			default_storage.save(new_path, ContentFile(content))
			default_storage.delete(old_path)
			Model.objects.filter(pk=obj.pk).update(**{field_name: new_path})
			print(f'[OK] {Model.__name__} pk={obj.pk}: {old_path} -> {new_path}')
		except Exception as e:
			print(f'[WARN] {Model.__name__} pk={obj.pk}: {e}')


def migrate_files(apps, schema_editor):
	schema = connection.schema_name

	if schema == get_public_schema_name():
		Tenant = apps.get_model('tenants', 'Tenant')
		for tenant in Tenant.objects.exclude(logo='').exclude(logo=None):
			old_path = tenant.logo.name
			if not old_path or old_path.startswith('tenants/'):
				continue
			if not default_storage.exists(old_path):
				print(f'[SKIP] Tenant pk={tenant.pk}: {old_path} nao existe no storage')
				continue
			ext = os.path.splitext(old_path)[1].lower()
			new_path = f'tenants/{tenant.schema_name}/logos/{uuid.uuid4().hex}{ext}'
			try:
				with default_storage.open(old_path, 'rb') as fh:
					content = fh.read()
				default_storage.save(new_path, ContentFile(content))
				default_storage.delete(old_path)
				Tenant.objects.filter(pk=tenant.pk).update(logo=new_path)
				print(f'[OK] Tenant pk={tenant.pk}: {old_path} -> {new_path}')
			except Exception as e:
				print(f'[WARN] Tenant pk={tenant.pk}: {e}')
		return

	prefix = f'tenants/{schema}'

	FotoImovel = apps.get_model('imoveis', 'FotoImovel')
	_migrate_field(FotoImovel, 'imagem', f'{prefix}/imoveis/fotos/')

	Inquilino = apps.get_model('inquilinos', 'Inquilino')
	_migrate_field(Inquilino, 'foto', f'{prefix}/inquilinos/fotos/')

	Usuario = apps.get_model('core', 'Usuario')
	_migrate_field(Usuario, 'foto', f'{prefix}/usuarios/fotos/')

	ContratoDocumentoGerado = apps.get_model('documentos', 'ContratoDocumentoGerado')
	_migrate_field(ContratoDocumentoGerado, 'arquivo_pdf', f'{prefix}/documentos/contratos/')


class Migration(migrations.Migration):

	dependencies = [
		('core', '0003_alter_usuario_foto'),
		('imoveis', '0008_alter_fotoimovel_imagem'),
		('inquilinos', '0002_alter_inquilino_foto'),
		('documentos', '0002_alter_contratodocumentogerado_arquivo_pdf'),
		('tenants', '0016_alter_tenant_logo'),
	]

	operations = [
		migrations.RunPython(migrate_files, migrations.RunPython.noop),
	]
