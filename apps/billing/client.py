"""
apps/billing/client.py
Cliente HTTP da API Asaas — assinatura interna (DN Software cobra a
imobiliária pela mensalidade do plano). Conta única/global, schema public.

Não confundir com a futura integração Asaas por-tenant do menu Boleto
(imobiliária cobrando os próprios inquilinos) — outra conta, outra chave.

Doc: https://docs.asaas.com — auth por API key simples no header
access_token (não OAuth, não expira). Ver skill asaas-api-referencia.

Fatia 1: só os métodos de criação (customer + subscription). Sem webhook,
cancelamento ou consulta ainda.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('apps.billing')


# ── Exceções ──────────────────────────────────────────────────────────────

class AsaasError(Exception):
	"""Base de todos os erros da integração Asaas."""


class AsaasAuthError(AsaasError):
	"""Falha de autenticação (API key inválida, ambiente errado, etc.)."""


class AsaasAPIError(AsaasError):
	"""Falha em chamada de negócio da API (customer/subscription)."""


class AsaasClient:
	"""
	Cliente da conta Asaas da própria DN Software (não por tenant).
	API key e URL base vêm de settings (ASAAS_API_KEY / ASAAS_API_URL).
	"""

	def __init__(self):
		self.base_url = settings.ASAAS_API_URL.rstrip('/')
		self.api_key = settings.ASAAS_API_KEY
		self.session = requests.Session()

	# ── Autenticação ─────────────────────────────────────────────────────

	def _headers(self):
		return {
			'Content-Type': 'application/json',
			'User-Agent': 'dnimob',
			'access_token': self.api_key,
		}

	# ── Operações ────────────────────────────────────────────────────────

	def criar_customer(self, nome, cpf_cnpj, email='', external_reference=None):
		"""
		Cria um customer no Asaas para o tenant. `external_reference` deve
		ser o Tenant.id, pra linkar o customer Asaas de volta ao tenant.
		Retorna o dict da resposta (contém 'id', ex: 'cus_000005219613').
		"""
		payload = {
			'name': nome,
			'cpfCnpj': _so_digitos(cpf_cnpj),
		}
		if email:
			payload['email'] = email
		if external_reference is not None:
			payload['externalReference'] = str(external_reference)

		logger.info('Asaas criar_customer: externalReference=%s', external_reference)
		return self._post('/customers', payload, contexto='criar customer')

	def criar_subscription(self, customer_id, valor, next_due_date, billing_type='BOLETO',
	                        ciclo='MONTHLY', descricao=''):
		"""
		Cria uma assinatura (recorrência) para um customer já existente.
		`next_due_date`: date do Python (primeira cobrança).
		`billing_type`: 'BOLETO' | 'PIX' | 'CREDIT_CARD' | 'UNDEFINED'.

		IMPORTANTE (doc Asaas): a subscription é só o agendador — não
		representa pagamento confirmado. Quem paga é a cobrança (payment)
		gerada por ela, acompanhada via webhook (fatia futura).
		Retorna o dict da resposta (contém 'id', ex: 'sub_VXJBYgP2u0eO').
		"""
		payload = {
			'customer': customer_id,
			'billingType': billing_type,
			'nextDueDate': next_due_date.strftime('%Y-%m-%d'),
			'value': float(valor),
			'cycle': ciclo,
		}
		if descricao:
			payload['description'] = descricao

		logger.info('Asaas criar_subscription: customer=%s valor=%s ciclo=%s', customer_id, valor, ciclo)
		return self._post('/subscriptions', payload, contexto='criar subscription')

	def obter_subscription(self, subscription_id):
		"""Consulta os dados atuais de uma subscription (inclui billingType)."""
		return self._get(f'/subscriptions/{subscription_id}', contexto='consultar subscription')

	def atualizar_billing_type(self, subscription_id, billing_type):
		"""
		Atualiza a forma de pagamento de uma subscription existente.
		`billing_type`: 'BOLETO' | 'PIX' | 'CREDIT_CARD'.
		"""
		payload = {'billingType': billing_type}
		logger.info('Asaas atualizar_billing_type: subscription=%s billing_type=%s', subscription_id, billing_type)
		return self._patch(f'/subscriptions/{subscription_id}', payload, contexto='atualizar forma de pagamento')

	def associar_cartao_subscription(self, subscription_id, credit_card_token):
		"""
		Associa cartão tokenizado (gerado pelo Asaas.js no frontend) à
		subscription. O cartão em si nunca trafega pelo nosso servidor —
		só o token.
		"""
		payload = {'billingType': 'CREDIT_CARD', 'creditCardToken': credit_card_token}
		logger.info('Asaas associar_cartao_subscription: subscription=%s', subscription_id)
		return self._patch(f'/subscriptions/{subscription_id}', payload, contexto='associar cartão')

	# ── Transporte ───────────────────────────────────────────────────────

	def _post(self, path, payload, contexto):
		try:
			resp = self.session.post(f'{self.base_url}{path}', json=payload, headers=self._headers(), timeout=20)
		except requests.RequestException as e:
			logger.error('Asaas %s: falha de conexão: %s', contexto, e)
			raise AsaasAPIError(f'Falha de conexão com o Asaas: {e}') from e
		return self._tratar_resposta(resp, contexto)

	def _patch(self, path, payload, contexto):
		try:
			resp = self.session.patch(f'{self.base_url}{path}', json=payload, headers=self._headers(), timeout=20)
		except requests.RequestException as e:
			logger.error('Asaas %s: falha de conexão: %s', contexto, e)
			raise AsaasAPIError(f'Falha de conexão com o Asaas: {e}') from e
		return self._tratar_resposta(resp, contexto)

	def _get(self, path, contexto):
		try:
			resp = self.session.get(f'{self.base_url}{path}', headers=self._headers(), timeout=20)
		except requests.RequestException as e:
			logger.error('Asaas %s: falha de conexão: %s', contexto, e)
			raise AsaasAPIError(f'Falha de conexão com o Asaas: {e}') from e
		return self._tratar_resposta(resp, contexto)

	def _tratar_resposta(self, resp, contexto):
		if resp.status_code in (401, 403):
			msg = _extrair_erro(resp)
			logger.error('Asaas %s: erro de autenticação %s: %s', contexto, resp.status_code, resp.text[:300])
			raise AsaasAuthError(f'Falha de autenticação Asaas ao {contexto}: {msg}')

		if resp.status_code not in (200, 201):
			msg = _extrair_erro(resp)
			logger.error('Asaas %s: erro %s: %s', contexto, resp.status_code, resp.text[:300])
			raise AsaasAPIError(f'Erro ao {contexto} no Asaas: {msg}')

		return resp.json()


# ── Helpers ──────────────────────────────────────────────────────────────

def _so_digitos(valor):
	return ''.join(c for c in str(valor or '') if c.isdigit())


def _extrair_erro(resp):
	"""Extrai mensagem de erro do corpo da resposta Asaas (lista de errors)."""
	try:
		data = resp.json()
		if isinstance(data, dict):
			erros = data.get('errors')
			if isinstance(erros, list) and erros:
				item = erros[0]
				if isinstance(item, dict):
					return item.get('description') or str(item)
			return data.get('message') or data.get('code') or resp.text[:200]
		return str(data)[:200]
	except ValueError:
		return resp.text[:200]
