"""apps/documentos/validators.py — validação de modelos .docx enviados pelo tenant."""
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

MB = 1024 * 1024


def validar_tamanho_modelo(value):
	"""Limite lido de settings em tempo de execução (não congela na migration)."""
	max_mb = settings.DOCUMENTO_MODELO_MAX_MB
	if hasattr(value, 'size') and value.size > max_mb * MB:
		raise ValidationError(f'Arquivo acima de {max_mb} MB.')


validar_extensao_docx = FileExtensionValidator(
	allowed_extensions=['docx'],
	message='Envie um arquivo .docx.',
)


@deconstructible
class ValidarDocx:
	"""Valida estrutura do .docx: zip íntegro, partes obrigatórias, sem macros,
	sem zip bomb e sem path traversal."""

	def __call__(self, value):
		max_bytes = settings.DOCUMENTO_MODELO_MAX_DESCOMPACTADO_MB * MB
		max_entradas = settings.DOCUMENTO_MODELO_MAX_ENTRADAS_ZIP

		posicao = value.tell() if hasattr(value, 'tell') else 0
		try:
			value.seek(0)
			if value.read(2) != b'PK':
				raise ValidationError('O arquivo não é um .docx válido.')
			value.seek(0)
			if not zipfile.is_zipfile(value):
				raise ValidationError('O arquivo não é um .docx válido.')
			value.seek(0)
			try:
				with zipfile.ZipFile(value) as zf:
					self._validar_zip(zf, max_bytes, max_entradas)
			except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
				raise ValidationError(
					'Arquivo corrompido, criptografado ou protegido por senha.'
				)
		finally:
			value.seek(posicao)

	@staticmethod
	def _validar_zip(zf, max_bytes, max_entradas):
		infos = zf.infolist()

		if len(infos) > max_entradas:
			raise ValidationError('O arquivo tem itens demais para ser um modelo válido.')

		total = 0
		nomes = set()
		for info in infos:
			nome = info.filename
			if nome.startswith(('/', '\\')) or '..' in nome.replace('\\', '/').split('/'):
				raise ValidationError('O arquivo contém caminhos inválidos.')
			if info.flag_bits & 0x1:
				raise ValidationError('Arquivo criptografado ou protegido por senha.')
			total += info.file_size
			if total > max_bytes:
				raise ValidationError(
					f'Conteúdo do arquivo grande demais após descompactar '
					f'(máximo {settings.DOCUMENTO_MODELO_MAX_DESCOMPACTADO_MB} MB).'
				)
			nomes.add(nome)

		if '[Content_Types].xml' not in nomes or 'word/document.xml' not in nomes:
			raise ValidationError('O arquivo não é um documento Word (.docx) válido.')

		if 'word/vbaProject.bin' in nomes:
			raise ValidationError('Arquivos com macros não são permitidos.')

	def __eq__(self, other):
		return isinstance(other, ValidarDocx)
