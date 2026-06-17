"""
Cliente para a Evolution API (self-hosted).
Usa InstanciaWhatsApp do tenant para obter credenciais.
"""
import logging
import requests
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
    texto = (
        f'Olá, {contrato.inquilino.nome}! 👋\n\n'
        f'Seu contrato de locação do imóvel *{contrato.imovel}* foi criado com sucesso.\n'
        f'📅 Vigência: {contrato.data_inicio.strftime("%d/%m/%Y")} a {contrato.data_fim.strftime("%d/%m/%Y")}\n'
        f'💰 Aluguel: R$ {contrato.valor_aluguel:,.2f}\n\n'
        f'Qualquer dúvida, entre em contato conosco. 🏠'
    )
    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='contrato_criado',
        nome_contato=contrato.inquilino.nome, contrato_id=contrato.pk,
    )


def notificar_lembrete_vencimento(parcela) -> bool:
    numero = _formatar_numero(parcela.contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False
    texto = (
        f'Olá, {parcela.contrato.inquilino.nome}! 😊\n\n'
        f'Lembrete: o boleto referente ao mês *{parcela.competencia}* '
        f'vence em *{parcela.data_vencimento.strftime("%d/%m/%Y")}*.\n'
        f'💰 Valor: R$ {parcela.valor_total:,.2f}\n\n'
        f'Pague em dia e evite multas! 🙏'
    )
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
    texto = (
        f'Olá, {parcela.contrato.inquilino.nome}.\n\n'
        f'⚠️ Seu boleto referente ao mês *{parcela.competencia}* '
        f'está vencido há *{dias} dia(s)*.\n'
        f'💰 Valor atualizado: R$ {parcela.valor_total:,.2f}\n\n'
        f'Regularize o quanto antes para evitar maiores encargos.'
    )
    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='parcela_vencida',
        nome_contato=parcela.contrato.inquilino.nome,
        contrato_id=parcela.contrato_id, parcela_id=parcela.pk,
    )


def notificar_pagamento_confirmado(parcela) -> bool:
    numero = _formatar_numero(parcela.contrato.inquilino.telefone or '')
    if not numero or len(numero) < 12:
        return False
    texto = (
        f'✅ Pagamento confirmado!\n\n'
        f'Olá, {parcela.contrato.inquilino.nome}!\n'
        f'Recebemos o pagamento referente ao mês *{parcela.competencia}*.\n'
        f'💰 Valor: R$ {parcela.valor_pago:,.2f}\n'
        f'📅 Data: {parcela.data_pagamento.strftime("%d/%m/%Y")}\n\n'
        f'Obrigado! 🏠'
    )
    return enviar_mensagem(
        numero=numero, mensagem=texto, evento='pagamento_confirmado',
        nome_contato=parcela.contrato.inquilino.nome,
        contrato_id=parcela.contrato_id, parcela_id=parcela.pk,
    )
