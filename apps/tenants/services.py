"""
services.py — Fase 2
Lógica de negócio para criação de tenant, configuração de conta,
integração Sicredi e WhatsApp via Evolution API.
"""

import logging
import re
import secrets
import string
from datetime import date, timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django_tenants.utils import schema_context

from .models import (
    ConfigSicredi,
    Domain,
    InstanciaWhatsApp,
    Plano,
    Tenant,
    TemplateWhatsApp,
)

logger = logging.getLogger(__name__)
Usuario = get_user_model()


# ---------------------------------------------------------------------------
# Templates padrão WhatsApp
# ---------------------------------------------------------------------------

TEMPLATES_PADRAO = {
    'boas_vindas': (
        'Olá {nome_inquilino}! 👋\n\n'
        'Seja bem-vindo(a) à *{nome_imobiliaria}*.\n'
        'Seu contrato referente ao imóvel em *{endereco_imovel}* foi ativado com sucesso.\n\n'
        'Qualquer dúvida, estamos à disposição!'
    ),
    'boleto_gerado': (
        'Olá {nome_inquilino}! 🏠\n\n'
        'Seu boleto de *R$ {valor}* referente a *{mes_referencia}* foi gerado.\n'
        '📅 Vencimento: *{data_vencimento}*\n\n'
        'Código de barras:\n`{codigo_barras}`\n\n'
        'O boleto em PDF está em anexo.'
    ),
    'vence_amanha': (
        '⚠️ Olá {nome_inquilino}!\n\n'
        'Seu boleto de *R$ {valor}* vence *amanhã ({data_vencimento})*.\n\n'
        'Código de barras:\n`{codigo_barras}`\n\n'
        'Evite juros pagando em dia! 😊'
    ),
    'vence_hoje': (
        '🚨 Olá {nome_inquilino}!\n\n'
        'Seu boleto de *R$ {valor}* vence *hoje ({data_vencimento})*.\n\n'
        'Código de barras:\n`{codigo_barras}`\n\n'
        'Pague ainda hoje para evitar multa e juros!'
    ),
    'atraso_3': (
        'Olá {nome_inquilino}, tudo bem?\n\n'
        'Percebemos que seu boleto de *R$ {valor}* (vencimento {data_vencimento}) ainda não foi pago.\n'
        'Já são *3 dias* em atraso.\n\n'
        'Se já pagou, desconsidere. Qualquer dúvida, fale conosco! 🙂'
    ),
    'atraso_7': (
        '⚠️ *{nome_imobiliaria}* — Aviso de inadimplência\n\n'
        'Olá {nome_inquilino},\n'
        'Seu boleto de *R$ {valor}* encontra-se em atraso há *7 dias*.\n'
        'Valor atualizado com encargos: *R$ {valor_com_encargos}*\n\n'
        'Por favor, regularize o mais breve possível para evitar medidas contratuais.'
    ),
    'atraso_15': (
        '🔴 *Notificação formal — {nome_imobiliaria}*\n\n'
        'Sr(a). {nome_inquilino},\n\n'
        'Informamos que há uma pendência financeira em aberto há *15 dias*, '
        'referente ao imóvel {endereco_imovel}.\n'
        'Valor original: R$ {valor} | Encargos: R$ {encargos} | *Total: R$ {valor_com_encargos}*\n\n'
        'Solicitamos a regularização imediata. Em caso de não pagamento, '
        'serão adotadas as medidas previstas em contrato.'
    ),
    'pagamento_confirmado': (
        '✅ Pagamento confirmado!\n\n'
        'Olá {nome_inquilino}, recebemos seu pagamento de *R$ {valor}* referente a *{mes_referencia}*.\n\n'
        'Obrigado! O recibo está em anexo.'
    ),
    'contrato_enviado': (
        '📄 Olá {nome_inquilino}!\n\n'
        'Seu contrato de locação referente ao imóvel em *{endereco_imovel}* está pronto.\n'
        'O documento em PDF está em anexo para sua conferência.\n\n'
        'Qualquer dúvida, entre em contato conosco!'
    ),
    'contrato_60dias': (
        '📋 Olá {nome_inquilino}!\n\n'
        'Informamos que seu contrato vence em *60 dias* ({data_vencimento_contrato}).\n\n'
        'Caso tenha interesse em renovar, entre em contato para tratarmos as condições. 🏠'
    ),
    'contrato_30dias': (
        '⚠️ Olá {nome_inquilino}!\n\n'
        'Seu contrato de locação vence em *30 dias* ({data_vencimento_contrato}).\n\n'
        'Entre em contato urgente para definirmos renovação ou desocupação do imóvel.'
    ),
    'distrato_enviado': (
        '📄 Olá {nome_inquilino}!\n\n'
        'O documento de *distrato* referente ao imóvel em *{endereco_imovel}* foi gerado e está em anexo.\n\n'
        'Atenciosamente,\n*{nome_imobiliaria}*'
    ),
    'recibo_pagamento': (
        '🧾 Recibo de pagamento\n\n'
        'Olá {nome_inquilino}!\n'
        'Segue em anexo o recibo referente ao pagamento de *R$ {valor}* — *{mes_referencia}*.\n\n'
        'Guarde este documento para suas referências.'
    ),
}


def renderizar_template(evento: str, contexto: dict) -> str | None:
    """
    Busca o template ativo do evento no tenant atual e substitui as variáveis.
    Retorna None se não houver template para o evento ou se estiver desativado.
    """
    try:
        template = TemplateWhatsApp.objects.get(evento=evento, ativo=True)
    except TemplateWhatsApp.DoesNotExist:
        return None
    try:
        return template.mensagem.format(**contexto)
    except (KeyError, IndexError):
        logger.warning('Variável ausente ao renderizar template "%s"; enviando sem substituição.', evento)
        return template.mensagem

VARIAVEIS_POR_EVENTO = {
    'boas_vindas':           ['nome_inquilino', 'nome_imobiliaria', 'endereco_imovel'],
    'boleto_gerado':         ['nome_inquilino', 'valor', 'mes_referencia', 'data_vencimento', 'codigo_barras'],
    'vence_amanha':          ['nome_inquilino', 'valor', 'data_vencimento', 'codigo_barras'],
    'vence_hoje':            ['nome_inquilino', 'valor', 'data_vencimento', 'codigo_barras'],
    'atraso_3':              ['nome_inquilino', 'valor', 'data_vencimento'],
    'atraso_7':              ['nome_inquilino', 'valor', 'data_vencimento', 'valor_com_encargos'],
    'atraso_15':             ['nome_inquilino', 'valor', 'encargos', 'valor_com_encargos', 'endereco_imovel'],
    'pagamento_confirmado':  ['nome_inquilino', 'valor', 'mes_referencia'],
    'contrato_enviado':      ['nome_inquilino', 'endereco_imovel'],
    'contrato_60dias':       ['nome_inquilino', 'data_vencimento_contrato'],
    'contrato_30dias':       ['nome_inquilino', 'data_vencimento_contrato'],
    'distrato_enviado':      ['nome_inquilino', 'endereco_imovel', 'nome_imobiliaria'],
    'recibo_pagamento':      ['nome_inquilino', 'valor', 'mes_referencia'],
}


# ---------------------------------------------------------------------------
# Criação de novo tenant (onboarding)
# ---------------------------------------------------------------------------

def _sanitizar_subdominio(valor: str) -> str:
    valor = valor.strip().lower()
    valor = re.sub(r'[\s_]+', '-', valor)
    valor = re.sub(r'[^a-z0-9-]', '', valor)
    valor = re.sub(r'-+', '-', valor)
    return valor.strip('-')


@transaction.atomic
def criar_tenant(dados_form: dict, aceite_termos_em=None, aceite_termos_ip=None, aceite_termos_user_agent=None) -> Tenant:
    """
    Cria registro do tenant + domain SEM criar schema/migrations.
    O provisionamento real (migrate_schemas + admin + templates) fica para a
    task Celery `provisionar_tenant`.
    """
    subdominio  = _sanitizar_subdominio(dados_form['subdominio'])
    plano       = dados_form['plano']
    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'dnsoftware.com.br')
    schema_name = f'imob_{subdominio.replace("-", "_")}'

    if Tenant.objects.filter(schema_name=schema_name).exists():
        from django.core.exceptions import ValidationError
        raise ValidationError(f"Subdomínio '{subdominio}' já está em uso. Escolha outro nome.")

    tenant = Tenant(
        schema_name=schema_name,
        nome=dados_form['nome_imobiliaria'],
        tipo_pessoa=dados_form.get('tipo_pessoa', 'PJ'),
        cnpj=dados_form.get('cnpj', ''),
        cpf=dados_form.get('cpf', '') or '',
        email=dados_form['email_admin'],
        telefone=dados_form.get('telefone_admin', ''),
        plano=plano,
        trial=True,
        trial_expira=date.today() + timedelta(days=14),
        provisionamento_status='pendente',
        aceite_termos_em=aceite_termos_em,
        aceite_termos_ip=aceite_termos_ip,
        aceite_termos_user_agent=aceite_termos_user_agent,
    )
    # auto_create_schema=False no nível de instância — pula o migrate_schemas
    tenant.auto_create_schema = False
    tenant.save()

    Domain.objects.create(
        domain=f'{subdominio}.{base_domain}',
        tenant=tenant,
        is_primary=True,
    )

    logger.info('Tenant registrado: %s (schema=%s)', tenant.nome, tenant.schema_name)
    return tenant


def _criar_templates_padrao():
    """Cria os 13 templates WhatsApp padrão no schema atual."""
    for evento, mensagem in TEMPLATES_PADRAO.items():
        TemplateWhatsApp.objects.get_or_create(
            evento=evento,
            defaults={
                'mensagem': mensagem,
                'variaveis_disponiveis': VARIAVEIS_POR_EVENTO.get(evento, []),
                'ativo': True,
            },
        )


def gerar_senha_temporaria(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Evolution API — WhatsApp
# ---------------------------------------------------------------------------

class EvolutionAPIError(Exception):
    pass


class EvolutionAPINotFoundError(EvolutionAPIError):
    """Instância não existe no servidor Evolution API (HTTP 404)."""
    pass


class EvolutionAPIClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (
            base_url or getattr(settings, 'EVOLUTION_API_URL', 'http://evolution:8080')
        ).rstrip('/')
        self.api_key = api_key or getattr(settings, 'EVOLUTION_API_KEY', '')
        self.session = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key,
            'Content-Type': 'application/json',
        })

    def _request(self, method: str, endpoint: str, **kwargs):
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code == 404:
                # Instância não existe — warning, não error (não gera issue no Sentry)
                logger.warning('Evolution API instância não encontrada: %s', url)
                raise EvolutionAPINotFoundError(str(e)) from e
            else:
                logger.error('Evolution API HTTP error %s %s: %s', status_code, url, e)
                logger.error('Response body: %s', e.response.text if e.response is not None else 'N/A')
            raise EvolutionAPIError(str(e)) from e
        except requests.exceptions.RequestException as e:
            logger.error('Evolution API connection error: %s', e)
            raise EvolutionAPIError(f'Falha de conexão: {e}') from e

    # --- Instância ---

    def criar_instancia(self, nome: str, token: str = '') -> dict:
        return self._request('POST', '/instance/create', json={
            'instanceName': nome,
            'token': token or secrets.token_urlsafe(32),
            'qrcode': True,
            'integration': 'WHATSAPP-BAILEYS',
        })

    def obter_qrcode(self, nome: str) -> dict:
        return self._request('GET', f'/instance/connect/{nome}')

    def status_instancia(self, nome: str) -> dict:
        return self._request('GET', f'/instance/connectionState/{nome}')

    def desconectar_instancia(self, nome: str) -> dict:
        return self._request('DELETE', f'/instance/logout/{nome}')

    def deletar_instancia(self, nome: str) -> dict:
        return self._request('DELETE', f'/instance/delete/{nome}')

    def configurar_webhook(self, nome: str, webhook_url: str) -> dict:
        return self._request('POST', f'/webhook/set/{nome}', json={
            'url': webhook_url,
            'webhook_by_events': True,
            'events': [
                'MESSAGES_UPSERT',
                'QRCODE_UPDATED',
                'CONNECTION_UPDATE',
                'SEND_MESSAGE',
            ],
        })

    # --- Mensagens ---

    def enviar_texto(self, nome: str, numero: str, mensagem: str) -> dict:
        return self._request('POST', f'/message/sendText/{nome}', json={
            'number': numero,
            'options': {'delay': 1200, 'presence': 'composing'},
            'textMessage': {'text': mensagem},
        })

    def enviar_pdf(self, nome: str, numero: str, url_pdf: str, caption: str = '') -> dict:
        return self._request('POST', f'/message/sendMedia/{nome}', json={
            'number': numero,
            'options': {'delay': 1200},
            'mediaMessage': {
                'mediatype': 'document',
                'caption': caption,
                'media': url_pdf,
                'fileName': 'documento.pdf',
            },
        })


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_client_tenant(tenant_schema: str) -> EvolutionAPIClient:
    """
    Retorna um EvolutionAPIClient configurado com EVOLUTION_API_URL/EVOLUTION_API_KEY
    do settings (servidor único por instância DN Software, não por tenant).
    """
    return EvolutionAPIClient()


# ---------------------------------------------------------------------------
# Funções de negócio — WhatsApp
# ---------------------------------------------------------------------------

def criar_instancia_whatsapp(
    tenant_schema: str,
    nome_instancia: str,
) -> InstanciaWhatsApp:
    """Cria ou atualiza a instância WhatsApp na Evolution API e salva no banco."""
    with schema_context(tenant_schema):
        instancia, created = InstanciaWhatsApp.objects.get_or_create(
            nome_instancia=nome_instancia,
            defaults={'status': 'desconectado'},
        )

        client = EvolutionAPIClient()

        try:
            client.criar_instancia(nome_instancia)
            instancia.status = 'aguardando_qr'
            instancia.save()
        except EvolutionAPIError as e:
            logger.error('Erro ao criar instância %s: %s', nome_instancia, e)
            instancia.status = 'erro'
            instancia.save()
            raise

        return instancia


def obter_qrcode_instancia(tenant_schema: str, nome_instancia: str) -> dict:
    """Busca QR code atualizado da instância usando credenciais salvas no tenant."""
    client = _get_client_tenant(tenant_schema)
    try:
        data      = client.obter_qrcode(nome_instancia)
        qr_base64 = data.get('base64', '')
        if qr_base64.startswith('data:'):
            qr_base64 = qr_base64.split(',', 1)[-1]
        data['base64'] = qr_base64
        with schema_context(tenant_schema):
            InstanciaWhatsApp.objects.filter(nome_instancia=nome_instancia).update(
                qr_code=qr_base64,
                status='aguardando_qr',
            )
        return data
    except EvolutionAPIError:
        return {}


def verificar_status_whatsapp(tenant_schema: str, nome_instancia: str) -> str:
    """Consulta estado atual da conexão WhatsApp e atualiza o banco."""
    client = _get_client_tenant(tenant_schema)
    try:
        data   = client.status_instancia(nome_instancia)
        estado = data.get('instance', {}).get('state', 'desconectado')
        mapa   = {
            'open':       'conectado',
            'connecting': 'aguardando_qr',
            'close':      'desconectado',
        }
        status = mapa.get(estado, 'desconectado')
        with schema_context(tenant_schema):
            InstanciaWhatsApp.objects.filter(nome_instancia=nome_instancia).update(status=status)
        return status
    except EvolutionAPINotFoundError:
        # Instância não existe mais no servidor (reinício, limpeza, etc)
        with schema_context(tenant_schema):
            InstanciaWhatsApp.objects.filter(nome_instancia=nome_instancia).update(status='nao_encontrada')
        return 'nao_encontrada'
    except EvolutionAPIError:
        return 'erro'


# ---------------------------------------------------------------------------
# Sicredi — testar credenciais
# ---------------------------------------------------------------------------

def testar_credenciais_sicredi(config: ConfigSicredi) -> tuple[bool, str]:
    """
    Testa as credenciais Sicredi (API v3.9.1) via SicrediClient.
    Retorna (sucesso: bool, mensagem: str).
    Delega para apps.sicredi.service para não duplicar a lógica de auth.
    """
    from apps.sicredi.service import testar_credenciais_sicredi as _testar
    return _testar(config)
