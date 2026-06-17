"""
apps/sicredi/client.py
Cliente HTTP da API de Cobrança Sicredi v3.9.1 (OAuth2 password flow + Boletos).

Doc: API Cobrança Sicredi v3.9.1
  Sandbox:  https://api-parceiro.sicredi.com.br/sb/...
  Produção: https://api-parceiro.sicredi.com.br/...

Auth: grant_type=password no primeiro login, refresh_token quando o
access_token expira. Tokens ficam em cache (Redis) por schema de tenant.
"""
import logging
from datetime import datetime, timedelta

import requests
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

logger = logging.getLogger('apps.sicredi')

HOST = 'https://api-parceiro.sicredi.com.br'

# Margem de segurança (s) pra renovar o token antes de expirar de fato
MARGEM_EXPIRACAO = 15


# ── Exceções ──────────────────────────────────────────────────────────────────

class SicrediError(Exception):
	"""Base de todos os erros da integração Sicredi."""


class SicrediAuthError(SicrediError):
	"""Falha de autenticação (credenciais inválidas, token, etc.)."""


class SicrediAPIError(SicrediError):
	"""Falha em chamada de negócio da API (cadastro/baixa de boleto)."""


# ── Mensagens amigáveis de baixa (erros 422 documentados) ─────────────────────

ERROS_BAIXA = {
	'aguardando confirmação': 'Boleto ainda aguardando confirmação no Sicredi — não pode ser baixado agora.',
	'rejeitado':              'Boleto rejeitado pelo Sicredi — não pode ser baixado.',
	'já baixado':             'Boleto já estava baixado no Sicredi.',
	'ja baixado':             'Boleto já estava baixado no Sicredi.',
	'já liquidado':           'Boleto já foi liquidado (pago) — não pode ser baixado.',
	'ja liquidado':           'Boleto já foi liquidado (pago) — não pode ser baixado.',
	'negativação':            'Boleto em fluxo de negativação/protesto — não pode ser baixado.',
	'protesto':               'Boleto em fluxo de negativação/protesto — não pode ser baixado.',
}


class SicrediClient:
	"""
	Cliente por tenant. Recebe a ConfigSicredi e o schema_name corrente.
	Gerencia o ciclo de vida do token e expõe as operações de boleto.
	"""

	def __init__(self, config, schema_name=None):
		self.config = config
		self.schema_name = schema_name or connection.schema_name
		self.session = requests.Session()

	# ── URLs por ambiente ────────────────────────────────────────────────

	@property
	def _prefixo(self):
		return '/sb' if self.config.ambiente == 'sandbox' else ''

	@property
	def _url_token(self):
		return f'{HOST}{self._prefixo}/auth/openapi/token'

	@property
	def _url_boletos(self):
		return f'{HOST}{self._prefixo}/cobranca/boleto/v1/boletos'

	def _url_baixa(self, nosso_numero):
		return f'{self._url_boletos}/{nosso_numero}/baixa'

	@property
	def _cache_key(self):
		return f'sicredi_token_{self.schema_name}'

	# ── Autenticação ─────────────────────────────────────────────────────

	def _headers_auth(self):
		return {
			'x-api-key': self.config.api_key,
			'context': 'COBRANCA',
			'Content-Type': 'application/x-www-form-urlencoded',
		}

	def _login(self):
		"""Login completo (grant_type=password)."""
		username = f'{self.config.codigo_beneficiario}{self.config.cooperativa}'
		data = {
			'grant_type': 'password',
			'username': username,
			'password': self.config.codigo_acesso,
			'scope': 'cobranca',
		}
		# DEBUG TEMPORÁRIO — remover após confirmar credenciais
		logger.debug(
			'[DEBUG SICREDI LOGIN] url=%s | x-api-key=%s... | username=%s | grant_type=%s',
			self._url_token,
			(self.config.api_key or '')[:8],
			username,
			data['grant_type'],
		)
		return self._post_token(data)

	def _refresh(self, refresh_token):
		"""Renova usando refresh_token (sem reenviar usuário/senha)."""
		data = {
			'grant_type': 'refresh_token',
			'refresh_token': refresh_token,
		}
		return self._post_token(data)

	def _post_token(self, data):
		logger.info('Sicredi auth: grant_type=%s schema=%s', data.get('grant_type'), self.schema_name)
		try:
			resp = self.session.post(self._url_token, data=data, headers=self._headers_auth(), timeout=15)
		except requests.RequestException as e:
			logger.error('Sicredi auth falha de conexão: %s', e)
			raise SicrediAuthError(f'Falha de conexão com o Sicredi: {e}') from e

		if resp.status_code != 200:
			# DEBUG TEMPORÁRIO — corpo completo da resposta de erro
			logger.debug('[DEBUG SICREDI AUTH ERRO] status=%s corpo_completo=%s', resp.status_code, resp.text)
			logger.error('Sicredi auth erro %s: %s', resp.status_code, resp.text[:300])
			if resp.status_code in (400, 401):
				raise SicrediAuthError('Credenciais Sicredi inválidas (x-api-key, beneficiário, cooperativa ou código de acesso).')
			raise SicrediAuthError(f'Erro de autenticação Sicredi ({resp.status_code}).')

		payload = resp.json()
		agora = timezone.now()
		dados = {
			'access_token': payload['access_token'],
			'refresh_token': payload.get('refresh_token', ''),
			'expira_em': (agora + timedelta(seconds=int(payload.get('expires_in', 300)))).isoformat(),
			'refresh_expira_em': (agora + timedelta(seconds=int(payload.get('refresh_expires_in', 1800)))).isoformat(),
		}
		# Guarda em cache pelo tempo de vida do refresh_token
		cache.set(self._cache_key, dados, timeout=int(payload.get('refresh_expires_in', 1800)))
		logger.info('Sicredi auth OK schema=%s expires_in=%s', self.schema_name, payload.get('expires_in'))
		return dados['access_token']

	def _access_token(self):
		"""
		Retorna um access_token válido, reaproveitando o cache.
		Renova via refresh_token quando o access expira; faz login completo
		quando o refresh também expira.
		"""
		agora = timezone.now()
		dados = cache.get(self._cache_key)

		if dados:
			expira_em = datetime.fromisoformat(dados['expira_em'])
			if expira_em - timedelta(seconds=MARGEM_EXPIRACAO) > agora:
				return dados['access_token']

			# access expirou — tenta refresh se ainda válido
			refresh_expira = datetime.fromisoformat(dados['refresh_expira_em'])
			if dados.get('refresh_token') and refresh_expira > agora:
				try:
					return self._refresh(dados['refresh_token'])
				except SicrediAuthError:
					logger.warning('Sicredi refresh falhou, refazendo login completo (schema=%s)', self.schema_name)

		return self._login()

	def autenticar(self):
		"""Força obtenção de token (usado no teste de credenciais)."""
		return self._access_token()

	def _headers_api(self):
		return {
			'x-api-key': self.config.api_key,
			'Authorization': f'Bearer {self._access_token()}',
			'cooperativa': str(self.config.cooperativa),
			'posto': str(self.config.posto),
			'Content-Type': 'application/json',
		}

	# ── Montagem de payload ──────────────────────────────────────────────

	def _pagador(self, inquilino):
		if inquilino.tipo == 'pj':
			tipo_pessoa = 'PESSOA_JURIDICA'
			documento = _so_digitos(inquilino.cnpj)
		else:
			tipo_pessoa = 'PESSOA_FISICA'
			documento = _so_digitos(inquilino.cpf)

		pagador = {
			'tipoPessoa': tipo_pessoa,
			'documento': documento,
			'nome': inquilino.nome,
			'endereco': f'{inquilino.logradouro} {inquilino.numero}'.strip(),
			'cidade': inquilino.cidade,
			'uf': inquilino.estado,
			'cep': _so_digitos(inquilino.cep),
		}
		if inquilino.telefone:
			pagador['telefone'] = _so_digitos(inquilino.telefone)
		if inquilino.email:
			pagador['email'] = inquilino.email
		return pagador

	def _beneficiario_final(self):
		"""Dados da imobiliária (tenant atual) — obrigatório no payload."""
		tenant = connection.tenant
		return {
			'tipoPessoa': 'PESSOA_JURIDICA',
			'documento': _so_digitos(getattr(tenant, 'cnpj', '')),
			'nome': self.config.beneficiario or getattr(tenant, 'nome', ''),
			'logradouro': getattr(tenant, 'endereco', '') or 'NAO INFORMADO',
			'numeroEndereco': 'S/N',
			'cidade': getattr(tenant, 'cidade', ''),
			'uf': getattr(tenant, 'estado', ''),
			'cep': _so_digitos(getattr(tenant, 'cep', '')),
		}

	def _montar_payload(self, parcela):
		contrato = parcela.contrato
		inquilino = contrato.inquilino
		seu_numero = f'CT{contrato.numero}-P{parcela.numero}'[:30]
		return seu_numero, {
			'tipoCobranca': 'NORMAL',
			'codigoBeneficiario': str(self.config.codigo_beneficiario),
			'pagador': self._pagador(inquilino),
			'beneficiarioFinal': self._beneficiario_final(),
			'especieDocumento': 'DUPLICATA_MERCANTIL_INDICACAO',
			'seuNumero': seu_numero,
			'dataVencimento': parcela.data_vencimento.strftime('%Y-%m-%d'),
			'valor': float(parcela.valor_total),
		}

	# ── Operações ────────────────────────────────────────────────────────

	def criar_boleto(self, parcela):
		"""
		Cadastra o boleto da parcela no Sicredi e grava/atualiza o model Boleto.
		Retorna a instância de Boleto. Lança SicrediAPIError em falha.
		"""
		from apps.sicredi.models import Boleto

		seu_numero, payload = self._montar_payload(parcela)
		logger.info('Sicredi criar_boleto schema=%s seuNumero=%s valor=%s',
		            self.schema_name, seu_numero, payload['valor'])

		try:
			resp = self.session.post(self._url_boletos, json=payload, headers=self._headers_api(), timeout=30)
		except requests.RequestException as e:
			logger.error('Sicredi criar_boleto conexão: %s', e)
			raise SicrediAPIError(f'Falha de conexão com o Sicredi: {e}') from e

		if resp.status_code != 201:
			msg = _extrair_erro(resp)
			logger.error('Sicredi criar_boleto erro %s: %s', resp.status_code, resp.text[:300])
			if resp.status_code in (401, 403):
				raise SicrediAuthError('Token Sicredi inválido ou sem permissão para cadastrar boleto.')
			if resp.status_code == 429:
				raise SicrediAPIError('Limite de requisições do Sicredi atingido. Tente novamente em instantes.')
			raise SicrediAPIError(f'Erro ao cadastrar boleto no Sicredi: {msg}')

		data = resp.json()
		boleto, _ = Boleto.objects.update_or_create(
			parcela=parcela,
			defaults={
				'seu_numero': seu_numero,
				'nosso_numero': data.get('nossoNumero', '') or '',
				'linha_digitavel': data.get('linhaDigitavel', '') or '',
				'codigo_barras': data.get('codigoBarras', '') or '',
				'txid': data.get('txid', '') or '',
				'qr_code': data.get('qrCode', '') or '',
				'status': 'emitido',
				'erro_mensagem': '',
				'emitido_em': timezone.now(),
			},
		)
		logger.info('Sicredi boleto criado schema=%s nossoNumero=%s', self.schema_name, boleto.nosso_numero)
		return boleto

	def baixar_boleto(self, boleto):
		"""
		Solicita a baixa (cancelamento) do boleto no Sicredi.
		Retorna (sucesso: bool, mensagem: str). Trata os erros 422 documentados.
		"""
		logger.info('Sicredi baixar_boleto schema=%s nossoNumero=%s', self.schema_name, boleto.nosso_numero)
		try:
			resp = self.session.patch(self._url_baixa(boleto.nosso_numero), headers=self._headers_api(), timeout=20)
		except requests.RequestException as e:
			logger.error('Sicredi baixar_boleto conexão: %s', e)
			raise SicrediAPIError(f'Falha de conexão com o Sicredi: {e}') from e

		if resp.status_code == 202:
			boleto.status = 'cancelado'
			boleto.save(update_fields=['status', 'atualizado_em'])
			logger.info('Sicredi baixa enviada schema=%s nossoNumero=%s', self.schema_name, boleto.nosso_numero)
			return True, 'Pedido de baixa enviado ao Sicredi.'

		texto = resp.text.lower()
		if resp.status_code == 422:
			for chave, amigavel in ERROS_BAIXA.items():
				if chave in texto:
					# "já baixado" é idempotente: tratamos como sucesso
					if 'baixado' in chave:
						boleto.status = 'cancelado'
						boleto.save(update_fields=['status', 'atualizado_em'])
						return True, amigavel
					logger.warning('Sicredi baixa rejeitada (%s): %s', boleto.nosso_numero, amigavel)
					raise SicrediAPIError(amigavel)
			raise SicrediAPIError(f'Não foi possível baixar o boleto: {_extrair_erro(resp)}')

		if resp.status_code in (401, 403):
			raise SicrediAuthError('Token Sicredi inválido ou sem permissão para baixar boleto.')

		logger.error('Sicredi baixar_boleto erro %s: %s', resp.status_code, resp.text[:300])
		raise SicrediAPIError(f'Erro ao baixar boleto no Sicredi ({resp.status_code}).')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _so_digitos(valor):
	return ''.join(c for c in str(valor or '') if c.isdigit())


def _extrair_erro(resp):
	"""Extrai mensagem de erro do corpo da resposta (JSON ou texto)."""
	try:
		data = resp.json()
		if isinstance(data, dict):
			return data.get('message') or data.get('mensagem') or data.get('error') or resp.text[:200]
		if isinstance(data, list) and data:
			item = data[0]
			if isinstance(item, dict):
				return item.get('message') or item.get('mensagem') or str(item)
		return str(data)[:200]
	except ValueError:
		return resp.text[:200]