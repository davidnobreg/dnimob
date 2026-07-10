"""
apps/sicredi/tests.py
Testes da integração Sicredi — autenticação, boletos e webhook.

Nenhuma chamada real à API Sicredi: o transporte HTTP (SicrediClient.session)
é sempre mockado via unittest.mock. Tasks Celery (boleto automático,
confirmação WhatsApp) também são mockadas para não depender de broker.

Roda dentro de um schema de tenant real (TenantTestCase do django_tenants),
já que Parcela/Contrato/Inquilino/Boleto são TENANT_APPS.
"""
import hashlib
import hmac
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.db import connection
from django.test import Client, override_settings
from django_tenants.test.cases import TenantTestCase

from apps.contratos.models import Contrato, Parcela
from apps.financeiro.models import Lancamento
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino
from apps.tenants.models import ConfigSicredi

from .client import SicrediAPIError, SicrediAuthError, SicrediClient
from .models import Boleto
from . import service
from .service import WebhookAuthError


def _resp(status_code, json_data=None, text=''):
	"""Cria uma resposta fake de requests.Response."""
	resp = MagicMock()
	resp.status_code = status_code
	resp.text = text or str(json_data or '')
	resp.json.return_value = json_data if json_data is not None else {}
	return resp


TOKEN_PAYLOAD = {
	'access_token': 'token-abc',
	'refresh_token': 'refresh-abc',
	'expires_in': 300,
	'refresh_expires_in': 1800,
	'token_type': 'Bearer',
}


class SicrediTestCase(TenantTestCase):
	"""Base com fixtures comuns: imóvel, inquilino, contrato, parcela, config."""

	def setUp(self):
		cache.clear()

		# Sem broker no ambiente de teste — nunca deixar tasks reais disparar
		self._patches = [
			patch('apps.sicredi.tasks.gerar_boleto_parcela_task.apply_async'),
			patch('apps.whatsapp.tasks.task_pagamento_confirmado.apply_async'),
			patch('apps.whatsapp.tasks.task_contrato_criado.apply_async'),
		]
		for p in self._patches:
			p.start()
			self.addCleanup(p.stop)

		self.config = ConfigSicredi.objects.create(
			api_key='key-teste',
			codigo_acesso='teste123',
			codigo_beneficiario='12345',
			cooperativa='6789',
			posto='03',
			beneficiario='Imobiliaria Teste',
			ambiente='sandbox',
			schema_name=self.tenant.schema_name,
			ativo=True,
		)

		self.imovel = Imovel.objects.create(
			codigo='IM-0001', tipo='apartamento', cep='60000000',
			logradouro='Rua Teste', numero='100', bairro='Centro',
			cidade='Fortaleza', estado='CE',
		)
		self.inquilino = Inquilino.objects.create(
			tipo='pf', nome='Rodrigo Oliveira', cpf='02738306006',
			telefone='85999999999', email='pagador@email.com',
			logradouro='Rua Doutor Vargas', numero='150',
			cidade='Porto Alegre', estado='RS', cep='91250000',
		)
		self.contrato = Contrato.objects.create(
			imovel=self.imovel, inquilino=self.inquilino, numero='0001',
			data_inicio=date.today(), data_fim=date.today() + timedelta(days=365),
			valor_aluguel=Decimal('1500.00'),
		)
		self.parcela = Parcela.objects.create(
			contrato=self.contrato, numero=1,
			data_vencimento=date.today() + timedelta(days=10),
			valor=Decimal('1500.00'),
		)
		self.sicredi_client = SicrediClient(self.config, schema_name=self.tenant.schema_name)


# ── Autenticação ────────────────────────────────────────────────────────────

class AutenticacaoTests(SicrediTestCase):

	@patch('requests.Session.post')
	def test_login_sucesso_guarda_token_em_cache(self, mock_post):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)

		token = self.sicredi_client.autenticar()

		self.assertEqual(token, 'token-abc')
		dados_cache = cache.get(self.sicredi_client._cache_key)
		self.assertEqual(dados_cache['access_token'], 'token-abc')

	@patch('requests.Session.post')
	def test_reusa_token_em_cache_sem_nova_chamada(self, mock_post):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)

		self.sicredi_client.autenticar()
		self.sicredi_client._access_token()

		self.assertEqual(mock_post.call_count, 1)

	@patch('requests.Session.post')
	def test_login_401_levanta_sicredi_auth_error(self, mock_post):
		mock_post.return_value = _resp(401, {}, text='invalid_grant')

		with self.assertRaises(SicrediAuthError):
			self.sicredi_client.autenticar()

	@patch('requests.Session.post')
	def test_testar_credenciais_sicredi_sucesso(self, mock_post):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)

		ok, msg = service.testar_credenciais_sicredi(self.config)

		self.assertTrue(ok)
		self.assertIn('estabelecida', msg.lower())

	@patch('requests.Session.post')
	def test_testar_credenciais_sicredi_falha(self, mock_post):
		mock_post.return_value = _resp(401, {}, text='invalid_grant')

		ok, msg = service.testar_credenciais_sicredi(self.config)

		self.assertFalse(ok)


# ── Cadastro de boleto ───────────────────────────────────────────────────────

class CriarBoletoTests(SicrediTestCase):

	@patch('requests.Session.post')
	def test_criar_boleto_monta_payload_correto_e_salva(self, mock_post):
		boleto_resp_data = {
			'linhaDigitavel': '74891125110061420512803153351030188640000009990',
			'codigoBarras': '74891886400000099901125100614205120315335103',
			'nossoNumero': '251006142',
		}
		mock_post.side_effect = [_resp(200, TOKEN_PAYLOAD), _resp(201, boleto_resp_data)]

		boleto = self.sicredi_client.criar_boleto(self.parcela)

		self.assertEqual(boleto.nosso_numero, '251006142')
		self.assertEqual(boleto.status, 'emitido')
		self.assertTrue(Boleto.objects.filter(parcela=self.parcela).exists())

		payload_enviado = mock_post.call_args_list[1].kwargs['json']
		self.assertEqual(payload_enviado['codigoBeneficiario'], '12345')
		self.assertEqual(payload_enviado['valor'], 1500.0)
		self.assertEqual(payload_enviado['pagador']['documento'], '02738306006')
		self.assertEqual(payload_enviado['seuNumero'], 'CT0001-P1')

	@patch('requests.Session.post')
	def test_criar_boleto_erro_generico_levanta_api_error(self, mock_post):
		mock_post.side_effect = [_resp(200, TOKEN_PAYLOAD), _resp(400, {'message': 'dados inválidos'})]

		with self.assertRaises(SicrediAPIError):
			self.sicredi_client.criar_boleto(self.parcela)

	@patch('requests.Session.post')
	def test_criar_boleto_429_mensagem_limite(self, mock_post):
		mock_post.side_effect = [_resp(200, TOKEN_PAYLOAD), _resp(429, {}, text='rate limit')]

		with self.assertRaises(SicrediAPIError) as ctx:
			self.sicredi_client.criar_boleto(self.parcela)
		self.assertIn('Limite', str(ctx.exception))

	@patch('requests.Session.post')
	def test_criar_boleto_401_levanta_auth_error(self, mock_post):
		mock_post.side_effect = [_resp(200, TOKEN_PAYLOAD), _resp(401, {}, text='unauthorized')]

		with self.assertRaises(SicrediAuthError):
			self.sicredi_client.criar_boleto(self.parcela)

	@patch('requests.Session.post')
	def test_gerar_boleto_parcela_sem_config_ativa_levanta_erro(self, mock_post):
		self.config.ativo = False
		self.config.save()

		with self.assertRaises(SicrediAPIError):
			service.gerar_boleto_parcela(self.parcela)
		mock_post.assert_not_called()


# ── Baixa de boleto ──────────────────────────────────────────────────────────

class BaixarBoletoTests(SicrediTestCase):

	def _boleto(self, status='emitido'):
		return Boleto.objects.create(
			parcela=self.parcela, nosso_numero='251006142', status=status,
		)

	@patch('requests.Session.patch')
	@patch('requests.Session.post')
	def test_baixa_sucesso(self, mock_post, mock_patch):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)
		mock_patch.return_value = _resp(202, {'statusComando': 'MOVIMENTO_ENVIADO'})
		boleto = self._boleto()

		ok, msg = self.sicredi_client.baixar_boleto(boleto)

		self.assertTrue(ok)
		boleto.refresh_from_db()
		self.assertEqual(boleto.status, 'cancelado')

	@patch('requests.Session.patch')
	@patch('requests.Session.post')
	def test_baixa_422_titulo_ja_liquidado_levanta_erro_amigavel(self, mock_post, mock_patch):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)
		mock_patch.return_value = _resp(422, {}, text='Título já liquidado')
		boleto = self._boleto()

		with self.assertRaises(SicrediAPIError) as ctx:
			self.sicredi_client.baixar_boleto(boleto)
		self.assertIn('liquidado', str(ctx.exception).lower())

	@patch('requests.Session.patch')
	@patch('requests.Session.post')
	def test_baixa_422_ja_baixado_e_idempotente(self, mock_post, mock_patch):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)
		mock_patch.return_value = _resp(422, {}, text='Título já baixado')
		boleto = self._boleto()

		ok, msg = self.sicredi_client.baixar_boleto(boleto)

		self.assertTrue(ok)
		boleto.refresh_from_db()
		self.assertEqual(boleto.status, 'cancelado')

	@patch('requests.Session.patch')
	@patch('requests.Session.post')
	def test_baixa_422_negativacao_levanta_erro(self, mock_post, mock_patch):
		mock_post.return_value = _resp(200, TOKEN_PAYLOAD)
		mock_patch.return_value = _resp(422, {}, text='Título em fluxo de negativação ou protesto')
		boleto = self._boleto()

		with self.assertRaises(SicrediAPIError):
			self.sicredi_client.baixar_boleto(boleto)


# ── Webhook ───────────────────────────────────────────────────────────────────

@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=False)
class WebhookTests(SicrediTestCase):
	"""
	SICREDI_WEBHOOK_SECRET_REQUIRED=False força explicitamente o comportamento
	de dev (webhook_secret opcional). Não dá pra usar override_settings(DEBUG=
	True) pra isso: o test runner do Django força DEBUG=False em TODOS os
	testes por padrão, e sobrescrever DEBUG mid-test reativa o
	django-debug-toolbar, que crasha ao lidar com a troca de schema do
	webhook (TypeError em SQLPanel). Sem esse override, estes testes cairiam
	na regra de produção (secret obrigatório, ver service.py).
	"""

	def _boleto(self, status='emitido'):
		return Boleto.objects.create(
			parcela=self.parcela, nosso_numero='221000144', status=status,
		)

	def test_webhook_liquidacao_marca_parcela_paga_e_cria_lancamento(self):
		self._boleto()
		payload = {
			'beneficiario': '12345',
			'nossoNumero': '221000144',
			'movimento': 'LIQUIDACAO_PIX',
			'valorLiquidacao': '1500.00',
			'dataPrevisaoPagamento': [2026, 6, 16],
		}

		service.processar_webhook(payload)

		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')
		self.assertEqual(self.parcela.data_pagamento, date(2026, 6, 16))

		boleto = Boleto.objects.get(parcela=self.parcela)
		self.assertEqual(boleto.status, 'pago')
		self.assertEqual(boleto.valor_pago, Decimal('1500.00'))

		# Signal de financeiro deve ter criado o Lancamento (sem duplicar lógica)
		self.assertTrue(Lancamento.objects.filter(parcela=self.parcela, tipo='receita').exists())

	def test_webhook_estorno_mesmo_dia_reverte_pagamento(self):
		boleto = self._boleto()
		hoje = date.today()
		boleto.status = 'pago'
		boleto.pago_em = hoje
		boleto.valor_pago = Decimal('1500.00')
		boleto.save()

		self.parcela.status = 'pago'
		self.parcela.data_pagamento = hoje
		self.parcela.save()
		Lancamento.objects.get_or_create(
			parcela=self.parcela,
			defaults={'tipo': 'receita', 'categoria': 'aluguel', 'status': 'realizado',
			          'descricao': 'teste', 'valor': Decimal('1500.00'), 'data': hoje,
			          'contrato': self.contrato},
		)

		payload = {
			'beneficiario': '12345',
			'nossoNumero': '221000144',
			'movimento': 'ESTORNO_LIQUIDACAO_REDE',
		}
		service.processar_webhook(payload)

		self.parcela.refresh_from_db()
		boleto.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pendente')
		self.assertIsNone(self.parcela.data_pagamento)
		self.assertEqual(boleto.status, 'emitido')
		self.assertEqual(
			Lancamento.objects.get(parcela=self.parcela).status, 'cancelado',
		)

	def test_webhook_estorno_fora_do_dia_e_ignorado(self):
		boleto = self._boleto()
		boleto.status = 'pago'
		boleto.pago_em = date.today() - timedelta(days=2)
		boleto.save()
		self.parcela.status = 'pago'
		self.parcela.data_pagamento = boleto.pago_em
		self.parcela.save()

		payload = {'beneficiario': '12345', 'nossoNumero': '221000144', 'movimento': 'ESTORNO_LIQUIDACAO_REDE'}
		service.processar_webhook(payload)

		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')  # não revertido

	def test_webhook_beneficiario_desconhecido_nao_quebra(self):
		service.processar_webhook({
			'beneficiario': '99999', 'nossoNumero': 'X', 'movimento': 'LIQUIDACAO_PIX',
		})  # não deve levantar exceção

	def test_webhook_boleto_inexistente_nao_quebra(self):
		service.processar_webhook({
			'beneficiario': '12345', 'nossoNumero': 'NAO-EXISTE', 'movimento': 'LIQUIDACAO_PIX',
		})  # não deve levantar exceção


# ── Assinatura do webhook (HMAC best-effort) ──────────────────────────────────

@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=False)
class WebhookAssinaturaTests(SicrediTestCase):
	"""
	Validação best-effort: só roda quando ConfigSicredi.webhook_secret está
	preenchido. Sicredi não documenta oficialmente esse mecanismo nesta
	versão da API — ver _assinatura_valida em service.py.

	SICREDI_WEBHOOK_SECRET_REQUIRED=False força o comportamento de dev
	(secret opcional) — ver nota em WebhookTests sobre por que não usamos
	override_settings(DEBUG=True) aqui.
	"""

	def _payload_liquidacao(self):
		return {
			'beneficiario': '12345',
			'nossoNumero': '221000144',
			'movimento': 'LIQUIDACAO_PIX',
			'valorLiquidacao': '1500.00',
			'dataPrevisaoPagamento': [2026, 6, 16],
		}

	def test_assinatura_valida_processa_payload(self):
		self.config.webhook_secret = 'segredo-teste'
		self.config.save()
		Boleto.objects.create(parcela=self.parcela, nosso_numero='221000144', status='emitido')

		payload = self._payload_liquidacao()
		corpo = json.dumps(payload).encode()
		assinatura = hmac.new(b'segredo-teste', corpo, hashlib.sha256).hexdigest()

		service.processar_webhook(payload, raw_body=corpo, assinatura=assinatura)

		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')

	def test_assinatura_invalida_descarta_payload(self):
		self.config.webhook_secret = 'segredo-teste'
		self.config.save()
		Boleto.objects.create(parcela=self.parcela, nosso_numero='221000144', status='emitido')

		payload = self._payload_liquidacao()
		corpo = json.dumps(payload).encode()

		service.processar_webhook(payload, raw_body=corpo, assinatura='assinatura-forjada')

		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pendente')  # payload descartado, nada mudou

	def test_sem_secret_configurado_aceita_payload_normalmente(self):
		# webhook_secret vazio (default) — comportamento atual, sem validação
		Boleto.objects.create(parcela=self.parcela, nosso_numero='221000144', status='emitido')

		service.processar_webhook(self._payload_liquidacao())  # sem raw_body/assinatura

		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')


# ── Endpoint HTTP real ─────────────────────────────────────────────────────────

class WebhookHTTPTestCase(SicrediTestCase):
	"""
	Base pros testes que batem no endpoint HTTP real via self.client (não
	service.processar_webhook() direto).

	O client de teste usa host 'testserver', que não é domínio de nenhum
	tenant cadastrado — cai no fallback SHOW_PUBLIC_IF_NO_TENANT_FOUND e é
	roteado pro urls_public.py, exatamente onde webhook_sicredi vive.

	IMPORTANTE: o middleware do django-tenants troca a conexão pro schema
	public antes de rotear a request. processar_webhook volta pro schema do
	tenant via schema_context() só durante o processamento; ao fim da
	request a conexão fica em 'public' de novo. tearDown restaura a conexão
	pro tenant de teste, senão o setUp() do próximo teste (que cria
	Imovel/Inquilino/Contrato/Parcela) quebra.
	"""
	url = '/sicredi/webhook/'

	def tearDown(self):
		connection.set_tenant(self.tenant)


class WebhookViewHTTPTests(WebhookHTTPTestCase):

	def _boleto(self, status='emitido'):
		return Boleto.objects.create(
			parcela=self.parcela, nosso_numero='331000155', status=status,
		)

	def test_metodo_errado_get_retorna_405(self):
		resp = self.client.get(self.url)
		self.assertEqual(resp.status_code, 405)

	def test_json_invalido_nao_derruba_resposta(self):
		resp = self.client.post(self.url, data=b'{isso nao e json', content_type='application/json')
		# regra Sicredi: nunca 500, sempre 200 mesmo em erro interno de parsing
		self.assertEqual(resp.status_code, 200)

	def test_post_sem_csrf_token_nao_e_bloqueado(self):
		# csrf_exempt: client com enforce_csrf_checks=True não deve levar 403
		client = Client(enforce_csrf_checks=True)
		payload = {'beneficiario': '99999', 'nossoNumero': 'X', 'movimento': 'LIQUIDACAO_PIX'}
		resp = client.post(self.url, data=json.dumps(payload), content_type='application/json')
		self.assertNotEqual(resp.status_code, 403)
		self.assertEqual(resp.status_code, 200)

	def test_header_x_signature_e_lido_e_validado(self):
		self._boleto()
		self.config.webhook_secret = 'segredo-http'
		self.config.save()

		payload = {
			'beneficiario': '12345', 'nossoNumero': '331000155',
			'movimento': 'LIQUIDACAO_PIX', 'valorLiquidacao': '1500.00',
			'dataPrevisaoPagamento': [2026, 6, 16],
		}
		corpo = json.dumps(payload).encode()
		assinatura = hmac.new(b'segredo-http', corpo, hashlib.sha256).hexdigest()

		resp = self.client.post(self.url, data=corpo, content_type='application/json',
		                         HTTP_X_SIGNATURE=assinatura)
		self.assertEqual(resp.status_code, 200)

		connection.set_tenant(self.tenant)
		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')  # header lido e assinatura validada certo


# ── webhook_secret obrigatório em produção ──────────────────────────────────────

class WebhookProducaoSecretObrigatorioTests(WebhookHTTPTestCase):
	"""
	Regra nova: em produção (DEBUG=False), webhook_secret é obrigatório —
	sem ele, ou com assinatura ausente/inválida, a requisição é rejeitada
	(401). Em dev/teste (DEBUG=True) o comportamento antigo é mantido
	(ver WebhookAssinaturaTests) — não usa override_settings.
	"""

	def _boleto(self, status='emitido'):
		return Boleto.objects.create(
			parcela=self.parcela, nosso_numero='441000166', status=status,
		)

	def _payload(self):
		return {
			'beneficiario': '12345', 'nossoNumero': '441000166',
			'movimento': 'LIQUIDACAO_PIX', 'valorLiquidacao': '1500.00',
			'dataPrevisaoPagamento': [2026, 6, 16],
		}

	@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=True)
	def test_producao_sem_secret_e_rejeitado_com_401(self):
		self._boleto()

		resp = self.client.post(self.url, data=json.dumps(self._payload()), content_type='application/json')
		self.assertEqual(resp.status_code, 401)

		connection.set_tenant(self.tenant)
		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pendente')  # nada processado

	@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=True)
	def test_producao_com_secret_e_assinatura_valida_e_aceito(self):
		self._boleto()
		self.config.webhook_secret = 'segredo-prod'
		self.config.save()

		payload = self._payload()
		corpo = json.dumps(payload).encode()
		assinatura = hmac.new(b'segredo-prod', corpo, hashlib.sha256).hexdigest()

		resp = self.client.post(self.url, data=corpo, content_type='application/json',
		                         HTTP_X_SIGNATURE=assinatura)
		self.assertEqual(resp.status_code, 200)

		connection.set_tenant(self.tenant)
		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')

	@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=True)
	def test_producao_com_secret_e_assinatura_forjada_e_rejeitado_com_401(self):
		self._boleto()
		self.config.webhook_secret = 'segredo-prod'
		self.config.save()

		resp = self.client.post(self.url, data=json.dumps(self._payload()), content_type='application/json',
		                         HTTP_X_SIGNATURE='assinatura-forjada')
		self.assertEqual(resp.status_code, 401)

		connection.set_tenant(self.tenant)
		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pendente')

	@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=False)
	def test_dev_sem_secret_mantem_comportamento_atual_e_aceita(self):
		# override_settings explícito na setting dedicada (não em DEBUG): o
		# test runner do Django força DEBUG=False em todos os testes, e
		# sobrescrever DEBUG=True mid-test reativa o django-debug-toolbar
		# (que não convive bem com a troca de schema do webhook — crasha
		# com TypeError em SQLPanel). SICREDI_WEBHOOK_SECRET_REQUIRED simula
		# o dev local sem esse efeito colateral.
		self._boleto()

		resp = self.client.post(self.url, data=json.dumps(self._payload()), content_type='application/json')
		self.assertEqual(resp.status_code, 200)

		connection.set_tenant(self.tenant)
		self.parcela.refresh_from_db()
		self.assertEqual(self.parcela.status, 'pago')

	@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=True)
	def test_service_levanta_webhookautherror_sem_secret_em_producao(self):
		# Nível de unidade: confirma o tipo de exceção, não só o status HTTP.
		self._boleto()
		with self.assertRaises(WebhookAuthError):
			service.processar_webhook(self._payload())


# ── Movimento desconhecido / não mapeado ────────────────────────────────────────

@override_settings(SICREDI_WEBHOOK_SECRET_REQUIRED=False)
class WebhookMovimentoDesconhecidoTests(WebhookHTTPTestCase):
	"""
	Movimento fora do mapeamento conhecido (MOVIMENTOS_LIQUIDACAO / ESTORNO).
	SICREDI_WEBHOOK_SECRET_REQUIRED=False pra isolar do gate de webhook_secret
	obrigatório (fora de escopo aqui) — ConfigSicredi de teste não tem secret
	configurado.
	"""

	def _payload(self):
		return {'beneficiario': '12345', 'nossoNumero': 'X999', 'movimento': 'MOVIMENTO_INEXISTENTE_XYZ'}

	def test_movimento_desconhecido_e_ignorado_sem_excecao(self):
		try:
			service.processar_webhook(self._payload())
		except Exception as e:  # noqa: BLE001
			self.fail(f'processar_webhook não deveria levantar exceção para movimento desconhecido: {e}')

	def test_movimento_desconhecido_via_http_retorna_200(self):
		resp = self.client.post(self.url, data=json.dumps(self._payload()), content_type='application/json')
		self.assertEqual(resp.status_code, 200)
