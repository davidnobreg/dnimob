"""apps/core/tests.py"""
import inspect
import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase
from django_tenants.postgresql_backend.base import FakeTenant
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from apps.core.tenancy import get_tenant_atual
from apps.tenants.models import Tenant
from config.celery import TenantTask, app as celery_app


class GetTenantAtualTests(TenantTestCase):

	def test_com_tenant_real_devolve_o_proprio_tenant(self):
		self.assertIsInstance(connection.tenant, Tenant)

		self.assertEqual(get_tenant_atual(), self.tenant)

	def test_com_fake_tenant_busca_o_tenant_real_pelo_schema(self):
		with schema_context(self.tenant.schema_name):
			self.assertIsInstance(connection.tenant, FakeTenant)

			atual = get_tenant_atual()

		self.assertIsInstance(atual, Tenant)
		self.assertEqual(atual.pk, self.tenant.pk)
		self.assertEqual(atual.nome, self.tenant.nome)

	def test_schema_inexistente_levanta_does_not_exist_com_mensagem(self):
		with schema_context('schema_que_nao_existe'):
			with self.assertRaises(Tenant.DoesNotExist) as ctx:
				get_tenant_atual()

		self.assertIn('schema_que_nao_existe', str(ctx.exception))


class SemConnectionTenantTests(SimpleTestCase):
	"""connection.tenant vira FakeTenant em tasks Celery: use apps.core.tenancy.get_tenant_atual()."""

	PADRAO = re.compile(r'connection\.tenant\b')
	EXCLUIDOS = {'tenancy.py'}

	def test_nenhum_uso_de_connection_tenant_fora_do_helper(self):
		base = Path(settings.BASE_DIR)
		achados = []
		for pasta in ('apps', 'config'):
			for arquivo in (base / pasta).rglob('*.py'):
				partes = set(arquivo.parts)
				if 'migrations' in partes or 'tests' in partes or arquivo.name in self.EXCLUIDOS:
					continue
				if arquivo.name.startswith('test'):
					continue
				for numero, linha in enumerate(arquivo.read_text(encoding='utf-8').splitlines(), 1):
					if self.PADRAO.search(linha):
						achados.append(f'{arquivo.relative_to(base)}:{numero}')

		self.assertEqual(achados, [], 'Use get_tenant_atual() em vez de connection.tenant.')


class TenantTaskDelayTests(SimpleTestCase):
	"""`.delay(schema_name, ...)` é a convenção de toda task com base=TenantTask."""

	def _tasks_tenant(self):
		celery_app.loader.import_default_modules()
		return {nome: task for nome, task in celery_app.tasks.items() if isinstance(task, TenantTask)}

	def test_todas_as_tasks_tenant_aceitam_delay_com_schema(self):
		tasks = self._tasks_tenant()
		self.assertIn('apps.documentos.tasks.gerar_documento_docx', tasks)
		self.assertIn('apps.sicredi.tasks.gerar_boleto_parcela_task', tasks)

		for nome, task in tasks.items():
			obrigatorios = [
				p for p in inspect.signature(task.run).parameters.values()
				if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
			]
			args = ('imob_teste', *range(len(obrigatorios)))
			with self.subTest(task=nome), patch('celery.app.base.Celery.send_task') as send_task:
				task.delay(*args)
				self.assertEqual(send_task.call_args.args[1], args)
