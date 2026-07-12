"""
apps/billing/tests.py
Testes do AsaasClient — billing interno (DN Software cobra a imobiliária).

Nenhuma chamada real à API Asaas: requests.Session.post é sempre mockado
(não há API key/conta ainda). Mesmo padrão de apps/sicredi/tests.py.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from .client import AsaasAPIError, AsaasAuthError, AsaasClient


def _resp(status_code, json_data=None, text=''):
	"""Cria uma resposta fake de requests.Response."""
	resp = MagicMock()
	resp.status_code = status_code
	resp.text = text or str(json_data or '')
	resp.json.return_value = json_data if json_data is not None else {}
	return resp


@override_settings(ASAAS_API_URL='https://api-sandbox.asaas.com/v3', ASAAS_API_KEY='chave-teste-sandbox')
class AsaasClientTests(TestCase):

	def setUp(self):
		self.client_asaas = AsaasClient()

	@patch('requests.Session.post')
	def test_headers_montados_com_access_token_e_user_agent(self, mock_post):
		mock_post.return_value = _resp(200, {'id': 'cus_123'})

		self.client_asaas.criar_customer('Imobiliária Teste', '12345678000190')

		headers = mock_post.call_args.kwargs['headers']
		self.assertEqual(headers['access_token'], 'chave-teste-sandbox')
		self.assertEqual(headers['Content-Type'], 'application/json')
		self.assertIn('User-Agent', headers)

	@patch('requests.Session.post')
	def test_criar_customer_monta_payload_correto(self, mock_post):
		mock_post.return_value = _resp(200, {'id': 'cus_123'})

		self.client_asaas.criar_customer(
			'Imobiliária Teste', '12.345.678/0001-90',
			email='contato@imob.com', external_reference=42,
		)

		url = mock_post.call_args.args[0]
		payload = mock_post.call_args.kwargs['json']
		self.assertTrue(url.endswith('/customers'))
		self.assertEqual(payload['name'], 'Imobiliária Teste')
		self.assertEqual(payload['cpfCnpj'], '12345678000190')
		self.assertEqual(payload['email'], 'contato@imob.com')
		self.assertEqual(payload['externalReference'], '42')

	@patch('requests.Session.post')
	def test_criar_customer_retorna_resposta_parseada(self, mock_post):
		mock_post.return_value = _resp(200, {'id': 'cus_000005219613'})

		resultado = self.client_asaas.criar_customer('Imobiliária Teste', '12345678000190')

		self.assertEqual(resultado['id'], 'cus_000005219613')

	@patch('requests.Session.post')
	def test_criar_subscription_monta_payload_correto(self, mock_post):
		mock_post.return_value = _resp(200, {'id': 'sub_abc'})

		self.client_asaas.criar_subscription(
			'cus_123', 197, date(2026, 8, 10), descricao='Plano Profissional',
		)

		url = mock_post.call_args.args[0]
		payload = mock_post.call_args.kwargs['json']
		self.assertTrue(url.endswith('/subscriptions'))
		self.assertEqual(payload['customer'], 'cus_123')
		self.assertEqual(payload['billingType'], 'BOLETO')
		self.assertEqual(payload['nextDueDate'], '2026-08-10')
		self.assertEqual(payload['value'], 197.0)
		self.assertEqual(payload['cycle'], 'MONTHLY')
		self.assertEqual(payload['description'], 'Plano Profissional')

	@patch('requests.Session.post')
	def test_criar_subscription_retorna_resposta_parseada(self, mock_post):
		mock_post.return_value = _resp(200, {'id': 'sub_VXJBYgP2u0eO'})

		resultado = self.client_asaas.criar_subscription('cus_123', 97, date(2026, 8, 10))

		self.assertEqual(resultado['id'], 'sub_VXJBYgP2u0eO')

	@patch('requests.Session.post')
	def test_erro_400_vira_asaas_api_error_com_mensagem(self, mock_post):
		mock_post.return_value = _resp(400, {
			'errors': [{'code': 'invalid_cpfCnpj', 'description': 'O CPF/CNPJ informado é inválido.'}],
		})

		with self.assertRaises(AsaasAPIError) as ctx:
			self.client_asaas.criar_customer('Imobiliária Teste', '000')

		self.assertIn('CPF/CNPJ informado é inválido', str(ctx.exception))

	@patch('requests.Session.post')
	def test_erro_401_vira_asaas_auth_error(self, mock_post):
		mock_post.return_value = _resp(401, {
			'errors': [{'code': 'invalid_access_token', 'description': 'Chave de API inválida.'}],
		})

		with self.assertRaises(AsaasAuthError):
			self.client_asaas.criar_customer('Imobiliária Teste', '12345678000190')

	@patch('requests.Session.post')
	def test_falha_de_conexao_vira_asaas_api_error(self, mock_post):
		import requests
		mock_post.side_effect = requests.ConnectionError('timeout')

		with self.assertRaises(AsaasAPIError):
			self.client_asaas.criar_customer('Imobiliária Teste', '12345678000190')
