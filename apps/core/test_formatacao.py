"""apps/core/test_formatacao.py"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.core.formatacao import formatar_valor_br


class FormatarValorBrTests(SimpleTestCase):

	def test_float_com_centavos(self):
		self.assertEqual(formatar_valor_br(1234.5), '1.234,50')

	def test_zero(self):
		self.assertEqual(formatar_valor_br(0), '0,00')

	def test_milhao(self):
		self.assertEqual(formatar_valor_br(1000000), '1.000.000,00')

	def test_arredonda_meio_centavo_para_cima(self):
		self.assertEqual(formatar_valor_br(0.005), '0,01')
		self.assertEqual(formatar_valor_br(Decimal('0.005')), '0,01')

	def test_negativo(self):
		self.assertEqual(formatar_valor_br(-1234.5), '-1.234,50')
		self.assertEqual(formatar_valor_br(Decimal('-1500')), '-1.500,00')

	def test_none_vira_zero(self):
		self.assertEqual(formatar_valor_br(None), '0,00')

	def test_decimal(self):
		self.assertEqual(formatar_valor_br(Decimal('1500.00')), '1.500,00')

	def test_negativo_que_arredonda_para_zero_nao_mostra_sinal(self):
		self.assertEqual(formatar_valor_br(Decimal('-0.001')), '0,00')
