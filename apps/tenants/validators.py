from validate_docbr import CPF as CPFValidator
from django.core.exceptions import ValidationError


def validar_cpf(value):
    digits = ''.join(c for c in (value or '') if c.isdigit())
    if not CPFValidator().validate(digits):
        raise ValidationError('CPF inválido. Verifique os dígitos e tente novamente.')
