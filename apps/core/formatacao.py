"""apps/core/formatacao.py"""
from decimal import Decimal, ROUND_HALF_UP


def formatar_valor_br(valor):
	"""
	Formata um valor no padrão brasileiro (1.234,50), sem prefixo "R$".
	Independe de locale. Aceita Decimal, int, float e None (vira 0,00).
	"""
	decimal = Decimal(str(valor if valor is not None else 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
	if decimal == 0:
		decimal = abs(decimal)
	return f'{decimal:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
