"""
Desativa (ativo=False, sem apagar) os modelos legados em HTML que já têm o equivalente "(DOCX)".

Legado = ModeloDocumento ativo, sem arquivo .docx.
- padrao=True com equivalente DOCX ativo no mesmo tenant: desativado.
- padrao=True sem equivalente: ignorado e reportado.
- padrao=False (conteúdo do cliente): só listado. `--incluir-personalizados` os desativa,
  e só vale junto com `--schema` (nunca com `--all`).
Nunca apaga. Idempotente: legado já inativo não é mais legado.

Uso:
	python manage.py arquivar_modelos_legados --schema imob_alpha --dry-run
	python manage.py arquivar_modelos_legados --all
	python manage.py arquivar_modelos_legados --schema imob_alpha --incluir-personalizados
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django_tenants.utils import get_public_schema_name, schema_context

from apps.documentos.models import ModeloDocumento
from apps.documentos.services import MODELOS_PADRAO_DOCX, SUFIXO_MODELO_DOCX
from apps.tenants.models import Tenant


def _legados():
	return ModeloDocumento.objects.filter(Q(arquivo__isnull=True) | Q(arquivo=''), ativo=True)


def _tem_equivalente_docx(modelo):
	dados = MODELOS_PADRAO_DOCX.get(modelo.tipo)
	titulo_docx = f'{modelo.titulo}{SUFIXO_MODELO_DOCX}'
	if not dados or dados['titulo'] != titulo_docx:
		return False
	return (
		ModeloDocumento.objects.filter(tipo=modelo.tipo, titulo=titulo_docx, ativo=True)
		.exclude(arquivo='').exclude(arquivo__isnull=True).exists()
	)


class Command(BaseCommand):
	help = 'Desativa modelos legados em HTML que já têm equivalente .docx (não apaga nada).'

	def add_arguments(self, parser):
		parser.add_argument('--schema', help='Processa apenas este schema.')
		parser.add_argument('--all', action='store_true', help='Processa todos os tenants (exceto o público).')
		parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria feito, sem gravar.')
		parser.add_argument(
			'--incluir-personalizados', action='store_true',
			help='Também desativa os legados não padrão. Exige --schema; não vale com --all.',
		)

	def handle(self, *args, **options):
		schema = options['schema']
		if bool(schema) == bool(options['all']):
			raise CommandError('Informe --schema <nome> ou --all (um dos dois).')
		if options['incluir_personalizados'] and not schema:
			raise CommandError('--incluir-personalizados só pode ser usado com --schema, nunca com --all.')

		tenants = Tenant.objects.exclude(schema_name=get_public_schema_name()).order_by('schema_name')
		if schema:
			tenants = tenants.filter(schema_name=schema)
			if not tenants.exists():
				raise CommandError(f'Tenant "{schema}" não encontrado.')

		dry_run = options['dry_run']
		incluir = options['incluir_personalizados']
		if dry_run:
			self.stdout.write('DRY-RUN: nada será gravado.')

		totais = {'desativados': 0, 'ignorados': 0, 'personalizados': 0}
		erros = 0
		for tenant in tenants:
			try:
				with schema_context(tenant.schema_name), transaction.atomic():
					resultado = self._processar(dry_run, incluir)
			except Exception as exc:
				erros += 1
				self.stderr.write(self.style.ERROR(f'[{tenant.schema_name}] ERRO: {exc}'))
				continue

			self._relatar(tenant.schema_name, resultado, incluir)
			for chave in totais:
				totais[chave] += len(resultado[chave])

		self.stdout.write(
			f'Resumo: desativados={totais["desativados"]} ignorados={totais["ignorados"]} '
			f'personalizados={totais["personalizados"]} erros={erros}'
		)
		if erros:
			raise CommandError(f'{erros} tenant(s) com erro.')

	def _processar(self, dry_run, incluir):
		resultado = {'desativados': [], 'ignorados': [], 'personalizados': []}
		for modelo in _legados().order_by('tipo', 'titulo'):
			if modelo.padrao:
				destino = 'desativados' if _tem_equivalente_docx(modelo) else 'ignorados'
			else:
				destino = 'desativados' if incluir else 'personalizados'
			resultado[destino].append(modelo)
			if destino == 'desativados' and not dry_run:
				modelo.ativo = False
				modelo.save(update_fields=['ativo', 'atualizado_em'])
		return resultado

	def _relatar(self, schema, resultado, incluir):
		self.stdout.write(
			f'[{schema}] desativados={len(resultado["desativados"])} '
			f'ignorados (sem equivalente DOCX)={len(resultado["ignorados"])} '
			f'personalizados listados={len(resultado["personalizados"])} erros=0'
		)
		for modelo in resultado['desativados']:
			rotulo = 'personalizado' if not modelo.padrao and incluir else 'padrão'
			self.stdout.write(f'  desativado ({rotulo}): {modelo.pk} "{modelo.titulo}"')
		for modelo in resultado['ignorados']:
			self.stdout.write(f'  ignorado (sem equivalente DOCX): {modelo.pk} "{modelo.titulo}"')
		for modelo in resultado['personalizados']:
			self.stdout.write(
				f'  personalizado: id={modelo.pk} "{modelo.titulo}" '
				f'atualizado_em={modelo.atualizado_em:%Y-%m-%d %H:%M} conteudo_html={len(modelo.conteudo_html)} chars'
			)
