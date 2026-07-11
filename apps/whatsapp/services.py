"""
Cliente para a Evolution API (self-hosted).
Usa InstanciaWhatsApp do tenant para obter credenciais.
"""
import logging
import requests
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_instancia():
    """Retorna a InstanciaWhatsApp do tenant atual."""
    from apps.tenants.models import InstanciaWhatsApp
    return InstanciaWhatsApp.objects.first()


class EvolutionAPIClient:
    def __init__(self, base_url: str, api_key: str, instance: str):
        self.base_url = base_url.rstrip('/')
        self.api_key  = api_key
        self.instance = instance
        self.session  = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key,
            'Content-Type': 'application/json',
        })

    def _url(self, path: str) -> str:
        return f'{self.base_url}/{path}'

    def verificar_conexao(self) -> dict:
        resp = self.session.get(
            self._url(f'instance/connectionState/{self.instance}'),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def obter_qrcode(self) -> dict:
        resp = self.session.get(
            self._url(f'instance/connect/{self.instance}'),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def criar_instancia(self) -> dict:
        payload = {
            'instanceName': self.instance,
            'qrcode': True,
        }
        resp = self.session.post(
            self._url('instance/create'),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def enviar_texto(self, numero: str, mensagem: str) -> dict:
        payload = {
            'number': numero,
            'text': mensagem,
        }
        resp = self.session.post(
            self._url(f'message/sendText/{self.instance}'),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


def get_client_for_tenant() -> EvolutionAPIClient | None:
    """Retorna cliente configurado para o tenant atual. None se não configurado."""
    instancia = _get_instancia()
    if not instancia:
        return None
    if not all([instancia.evolution_url, instancia.token_api, instancia.nome_instancia]):
        return None
    return EvolutionAPIClient(
        base_url=instancia.evolution_url,
        api_key=instancia.token_api,
        instance=instancia.nome_instancia,
    )


def enviar_mensagem(
    numero: str,
    mensagem: str,
    evento: str,
    nome_contato: str = '',
    contrato_id: int | None = None,
    parcela_id:  int | None = None,
) -> bool:
    from .models import LogMensagem

    log = LogMensagem(
        evento=evento,
        destinatario=numero,
        nome_contato=nome_contato,
        mensagem=mensagem,
        status=LogMensagem.Status.PENDENTE,
        contrato_id=contrato_id,
        parcela_id=parcela_id,
    )

    try:
        client = get_client_for_tenant()
        if client is None:
            log.status = LogMensagem.Status.ERRO
            log.erro_detalhe = 'WhatsApp não configurado para este tenant.'
            log.save()
            return False

        client.enviar_texto(numero, mensagem)
        log.status     = LogMensagem.Status.ENVIADO
        log.enviado_em = timezone.now()
        log.save()
        return True

    except requests.HTTPError as exc:
        logger.error('Evolution API HTTP error: %s', exc)
        log.status       = LogMensagem.Status.ERRO
        log.erro_detalhe = f'HTTP {exc.response.status_code}: {exc.response.text[:500]}'
        log.save()
        return False

    except Exception as exc:
        logger.exception('Erro inesperado ao enviar WhatsApp')
        log.status       = LogMensagem.Status.ERRO
        log.erro_detalhe = str(exc)[:500]
        log.save()
        return False


# ─── Funções por evento ───────────────────────────────────────────────────────

def _formatar_numero(numero: str) -> str:
    limpo = ''.join(c for c in numero if c.isdigit())
    if not limpo.startswith('55'):
        limpo = '55' + limpo
    return limpo


def notificar_contrato_criado(contrato) -> bool:
    numero = _formatar_numero(contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False

    from apps.tenants.services import renderizar_template
    texto = renderizar_template('contrato_enviado', {
        'nome_inquilino': contrato.inquilino.nome,
        'endereco_imovel': str(contrato.imovel),
    })
    if not texto:
        return False

    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='contrato_criado',
        nome_contato=contrato.inquilino.nome, contrato_id=contrato.pk,
    )


def notificar_lembrete_vencimento(parcela) -> bool:
    numero = _formatar_numero(parcela.contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False

    try:
        codigo_barras = parcela.boleto.codigo_barras
    except ObjectDoesNotExist:
        codigo_barras = ''

    from apps.tenants.services import renderizar_template
    texto = renderizar_template('vence_amanha', {
        'nome_inquilino': parcela.contrato.inquilino.nome,
        'valor': f'{parcela.valor_total:,.2f}',
        'data_vencimento': parcela.data_vencimento.strftime('%d/%m/%Y'),
        'codigo_barras': codigo_barras,
        'mes_referencia': parcela.competencia,
    })
    if not texto:
        return False

    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='parcela_lembrete',
        nome_contato=parcela.contrato.inquilino.nome,
        contrato_id=parcela.contrato_id, parcela_id=parcela.pk,
    )


def notificar_parcela_vencida(parcela) -> bool:
    numero = _formatar_numero(parcela.contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False

    dias = (timezone.now().date() - parcela.data_vencimento).days
    evento_template = f'atraso_{dias}' if dias in (3, 7, 15) else 'atraso_3'

    from apps.tenants.services import renderizar_template
    texto = renderizar_template(evento_template, {
        'nome_inquilino': parcela.contrato.inquilino.nome,
        'valor': f'{(parcela.valor_total - parcela.valor_multa):,.2f}',
        'encargos': f'{parcela.valor_multa:,.2f}',
        'valor_com_encargos': f'{parcela.valor_total:,.2f}',
        'data_vencimento': parcela.data_vencimento.strftime('%d/%m/%Y'),
        'endereco_imovel': str(parcela.contrato.imovel),
    })
    if not texto:
        return False

    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='parcela_vencida',
        nome_contato=parcela.contrato.inquilino.nome,
        contrato_id=parcela.contrato_id, parcela_id=parcela.pk,
    )


def notificar_pagamento_confirmado(parcela) -> bool:
    numero = _formatar_numero(parcela.contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False

    from apps.tenants.services import renderizar_template
    texto = renderizar_template('pagamento_confirmado', {
        'nome_inquilino': parcela.contrato.inquilino.nome,
        'valor': f'{parcela.valor_total:,.2f}',
        'mes_referencia': parcela.competencia,
    })
    if not texto:
        return False

    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='pagamento_confirmado',
        nome_contato=parcela.contrato.inquilino.nome,
        contrato_id=parcela.contrato_id, parcela_id=parcela.pk,
    )
