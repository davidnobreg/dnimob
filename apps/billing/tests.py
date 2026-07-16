"""
apps/billing/tests.py
Testes do AsaasClient — billing interno (DN Software cobra a imobiliária).

Nenhuma chamada real à API Asaas: requests.Session.post é sempre mockado
(não há API key/conta ainda). Mesmo padrão de apps/sicredi/tests.py.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings
from django_tenants.test.cases import TenantTestCase

from apps.tenants.models import Plano, Tenant
from apps.tenants.tasks import _criar_assinatura_asaas

from .client import AsaasAPIError, AsaasAuthError, AsaasClient
from .webhook import asaas_webhook


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


class WebhookAsaasTest(TenantTestCase):
	"""
	Testes do webhook Asaas — Tenant vive no schema public, sem chamada real.

	override_settings vai por método (não por classe): TenantTestCase.setUpClass
	não chama super().setUpClass(), que é onde o Django habilitaria
	_overridden_settings no nível de classe.
	"""

	def _post_webhook(self, payload, token='token-secreto-teste'):
		factory = RequestFactory()
		req = factory.post(
			'/asaas/webhook/',
			data=json.dumps(payload),
			content_type='application/json',
			HTTP_ASAAS_ACCESS_TOKEN=token,
		)
		return asaas_webhook(req)

	@override_settings(ASAAS_WEBHOOK_TOKEN='token-secreto-teste')
	def test_evento_payment_confirmed_ativa_tenant(self):
		self.tenant.asaas_subscription_id = 'sub_123'
		self.tenant.status_pagamento = Tenant.StatusPagamento.INADIMPLENTE
		self.tenant.save()

		resp = self._post_webhook({
			'event': 'PAYMENT_CONFIRMED',
			'payment': {'subscription': 'sub_123', 'customer': 'cus_123'},
		})

		self.assertEqual(resp.status_code, 200)
		self.tenant.refresh_from_db()
		self.assertEqual(self.tenant.status_pagamento, 'ativo')

	@override_settings(ASAAS_WEBHOOK_TOKEN='token-secreto-teste')
	def test_evento_payment_overdue_marca_inadimplente(self):
		self.tenant.asaas_subscription_id = 'sub_123'
		self.tenant.status_pagamento = Tenant.StatusPagamento.ATIVO
		self.tenant.save()

		resp = self._post_webhook({
			'event': 'PAYMENT_OVERDUE',
			'payment': {'subscription': 'sub_123', 'customer': 'cus_123'},
		})

		self.assertEqual(resp.status_code, 200)
		self.tenant.refresh_from_db()
		self.assertEqual(self.tenant.status_pagamento, 'inadimplente')

	@override_settings(ASAAS_WEBHOOK_TOKEN='token-secreto-teste')
	def test_evento_subscription_deleted_cancela(self):
		self.tenant.asaas_subscription_id = 'sub_123'
		self.tenant.status_pagamento = Tenant.StatusPagamento.ATIVO
		self.tenant.save()

		resp = self._post_webhook({
			'event': 'SUBSCRIPTION_DELETED',
			'subscription': {'id': 'sub_123', 'customer': 'cus_123'},
		})

		self.assertEqual(resp.status_code, 200)
		self.tenant.refresh_from_db()
		self.assertEqual(self.tenant.status_pagamento, 'cancelado')

	@override_settings(ASAAS_WEBHOOK_TOKEN='token-secreto-teste')
	def test_evento_desconhecido_ignorado(self):
		self.tenant.asaas_subscription_id = 'sub_123'
		self.tenant.status_pagamento = Tenant.StatusPagamento.ATIVO
		self.tenant.save()

		resp = self._post_webhook({
			'event': 'PAYMENT_CREATED',
			'payment': {'subscription': 'sub_123'},
		})

		self.assertEqual(resp.status_code, 200)
		self.assertEqual(json.loads(resp.content), {'ok': True, 'ignorado': True})
		self.tenant.refresh_from_db()
		self.assertEqual(self.tenant.status_pagamento, 'ativo')

	@override_settings(ASAAS_WEBHOOK_TOKEN='token-secreto-teste')
	def test_token_invalido_retorna_401(self):
		resp = self._post_webhook({'event': 'PAYMENT_CONFIRMED'}, token='token-errado')

		self.assertEqual(resp.status_code, 401)

	def test_tenant_nao_encontrado_retorna_200(self):
		resp = self._post_webhook({
			'event': 'PAYMENT_CONFIRMED',
			'payment': {'subscription': 'sub_inexistente', 'customer': 'cus_inexistente'},
		})

		self.assertEqual(resp.status_code, 200)
		self.assertEqual(json.loads(resp.content)['tenant'], 'não encontrado')


class AcessoPermitidoTest(TenantTestCase):
	"""
	Testes da property acesso_permitido com status_pagamento.

	self.tenant é o mesmo objeto Python reaproveitado por todos os métodos
	da classe (só o schema é recriado por classe, não por teste) — o setUp
	reseta os campos relevantes pra cada teste não herdar estado deixado
	por outro (ex.: ativo=False vazando pros testes seguintes).
	"""

	def setUp(self):
		self.tenant.ativo = True
		self.tenant.trial = True
		self.tenant.trial_expira = None
		self.tenant.asaas_graca_ate = None
		self.tenant.status_pagamento = Tenant.StatusPagamento.TRIAL

	def test_status_ativo_permite_acesso(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.ATIVO
		self.tenant.save()

		self.assertTrue(self.tenant.acesso_permitido)

	def test_status_suspenso_bloqueia(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.SUSPENSO
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)

	def test_status_cancelado_bloqueia(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.CANCELADO
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)

	def test_status_inadimplente_sem_graca_bloqueia(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.INADIMPLENTE
		self.tenant.asaas_graca_ate = None
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)

	def test_status_inadimplente_dentro_graca_permite(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.INADIMPLENTE
		self.tenant.asaas_graca_ate = date.today() + timedelta(days=3)
		self.tenant.save()

		self.assertTrue(self.tenant.acesso_permitido)

	def test_status_inadimplente_graca_vencida_bloqueia(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.INADIMPLENTE
		self.tenant.asaas_graca_ate = date.today() - timedelta(days=1)
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)

	def test_status_trial_valido_permite(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.TRIAL
		self.tenant.trial = True
		self.tenant.trial_expira = date.today() + timedelta(days=5)
		self.tenant.save()

		self.assertTrue(self.tenant.acesso_permitido)

	def test_status_trial_vencido_bloqueia(self):
		self.tenant.status_pagamento = Tenant.StatusPagamento.TRIAL
		self.tenant.trial = True
		self.tenant.trial_expira = date.today() - timedelta(days=1)
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)

	def test_ativo_false_sempre_bloqueia(self):
		self.tenant.ativo = False
		self.tenant.status_pagamento = Tenant.StatusPagamento.ATIVO
		self.tenant.save()

		self.assertFalse(self.tenant.acesso_permitido)


@override_settings(ASAAS_API_URL='https://api-sandbox.asaas.com/v3', ASAAS_API_KEY='chave-teste-sandbox')
class CriarAssinaturaAsaasTest(TestCase):
	"""
	Testes de _criar_assinatura_asaas (integração do provisionamento com o
	Asaas). Tenant vive no schema public — criado direto via ORM, com
	auto_create_schema=False (mesmo padrão de criar_tenant em services.py),
	sem precisar criar o schema real pra esses testes.
	"""

	def setUp(self):
		# 0010_fixar_planos já semeia os planos padrão — não recriar, só ajustar.
		self.plano, _ = Plano.objects.update_or_create(
			nome=Plano.BASICO, defaults={'preco_mensal': Decimal('97.00')},
		)

	def _criar_tenant(self, schema_name):
		tenant = Tenant(
			schema_name=schema_name, nome='Imob Teste', cnpj='12345678000190',
			email='contato@imob.com', plano=self.plano,
		)
		tenant.auto_create_schema = False
		tenant.save()
		return tenant

	@patch('requests.Session.post')
	def test_criar_assinatura_asaas_salva_ids_no_tenant(self, mock_post):
		mock_post.side_effect = [_resp(200, {'id': 'cus_123'}), _resp(200, {'id': 'sub_456'})]
		tenant = self._criar_tenant('imob_teste_asaas1')

		_criar_assinatura_asaas(tenant)

		tenant.refresh_from_db()
		self.assertEqual(tenant.asaas_customer_id, 'cus_123')
		self.assertEqual(tenant.asaas_subscription_id, 'sub_456')

	@patch('requests.Session.post')
	def test_erro_asaas_nao_propaga_nem_falha_provisionamento(self, mock_post):
		import requests
		mock_post.side_effect = requests.ConnectionError('timeout')
		tenant = self._criar_tenant('imob_teste_asaas2')

		_criar_assinatura_asaas(tenant)  # não deve lançar

		tenant.refresh_from_db()
		self.assertEqual(tenant.asaas_customer_id, '')
		self.assertEqual(tenant.asaas_subscription_id, '')

	def test_tenant_sem_plano_nao_chama_asaas(self):
		tenant = self._criar_tenant('imob_teste_asaas3')
		tenant.plano = None
		tenant.save()

		_criar_assinatura_asaas(tenant)  # não deve lançar nem exigir mock

