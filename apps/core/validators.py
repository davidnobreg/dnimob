"""apps/core/validators.py"""
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible


@deconstructible
class validate_file_size:
	"""Validator que rejeita arquivos acima de max_mb MB.
	Classe (não closure) para poder ser serializado em migrations."""

	def __init__(self, max_mb):
		self.max_mb = max_mb

	def __call__(self, value):
		limit = self.max_mb * 1024 * 1024
		if hasattr(value, 'size') and value.size > limit:
			raise ValidationError(
				f'Arquivo muito grande. Tamanho máximo permitido: '
				f'{filesizeformat(limit)}. '
				f'Seu arquivo tem {filesizeformat(value.size)}.'
			)

	def __eq__(self, other):
		return isinstance(other, validate_file_size) and self.max_mb == other.max_mb
