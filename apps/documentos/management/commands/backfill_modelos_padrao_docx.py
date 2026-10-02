"""
Adiciona os 3 modelos padrão .docx aos tenants existentes.
Só ADICIONA: nunca altera, substitui ou apaga modelos existentes.
Idempotente: rodar de novo não duplica.

Uso:
	python manage.py backfill_modelos_padrao_docx --schema imob_alpha --dry-run
	python manage.py backfill_modelos_padrao_docx --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context

from apps.documentos.services import criar_modelos_padrao_docx, criar_variaveis_padrao
from apps.tenants.models import Tenant


class Command(BaseCommand):
	help = 'Adiciona os modelos padrão .docx aos tenants existentes (idempotente, não altera modelos existentes).'

	def add_arguments(self, parser):
		parser.add_argument('--schema', help='Processa apenas este schema.')
		parser.add_argument('--all', action='store_true', help='Processa todos os tenants (exceto o público).')
		parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria criado, sem gravar.')

	def handle(self, *args, **options):
		schema = options['schema']
		if bool(schema) == bool(options['all']):
			raise CommandError('Informe --schema <nome> ou --all (um dos dois).')

		tenants = Tenant.objects.exclude(schema_name=get_public_schema_name()).order_by('schema_name')
		if schema:
			tenants = tenants.filter(schema_name=schema)
			if not tenants.exists():
				raise CommandError(f'Tenant "{schema}" não encontrado.')

		dry_run = options['dry_run']
		if dry_run:
			self.stdout.write('DRY-RUN: nada será gravado.')

		total_criados = total_existentes = total_variaveis = total_predefinidos = erros = 0
		for tenant in tenants:
			try:
				with schema_context(tenant.schema_name), transaction.atomic():
					variaveis = criar_variaveis_padrao(dry_run=dry_run)
					resultado = criar_modelos_padrao_docx(dry_run=dry_run)
			except Exception as exc:
				erros += 1
				self.stderr.write(self.style.ERROR(f'[{tenant.schema_name}] ERRO: {exc}'))
				continue

			criados, existentes = len(resultado['criados']), len(resultado['existentes'])
			total_criados += criados
			total_existentes += existentes
			total_variaveis += variaveis
			predefinidos = len(resultado['predefinidos'])
			total_predefinidos += predefinidos
			self.stdout.write(
				f'[{tenant.schema_name}] criados={criados} já existentes={existentes} variáveis novas={variaveis} erros=0 '
				f'predefinidos={predefinidos}'
			)

		self.stdout.write(
			f'Resumo: criados={total_criados} já existentes={total_existentes} variáveis novas={total_variaveis} erros={erros} '
			f'predefinidos={total_predefinidos}'
		)
		if erros:
			raise CommandError(f'{erros} tenant(s) com erro.')
