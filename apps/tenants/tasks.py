import logging

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Domain
from .services import _criar_templates_padrao

logger = logging.getLogger(__name__)
Usuario = get_user_model()


@shared_task(bind=True, max_retries=3)
def provisionar_tenant(self, tenant_pk: int, dados_admin: dict):
	"""
	Cria schema PostgreSQL, roda migrate_schemas, cria admin e templates.
	Executado no Celery worker — libera o request thread do onboarding.
	ATENÇÃO: dados_admin trafega pelo Redis; garanta que Redis não seja público.
	"""
	from .models import Tenant
	from django_tenants.utils import schema_context

	tenant = Tenant.objects.get(pk=tenant_pk)
	tenant.provisionamento_status = 'provisionando'
	tenant.save(update_fields=['provisionamento_status'])

	try:
		tenant.auto_create_schema = True
		tenant.create_schema(check_if_exists=True)

		with schema_context(tenant.schema_name):
			nome = dados_admin['nome']
			admin = Usuario.objects.create_user(
				username=dados_admin['email'],
				email=dados_admin['email'],
				password=dados_admin['senha'],
				first_name=nome.split()[0],
				last_name=' '.join(nome.split()[1:]),
			)
			admin.is_staff = True
			admin.save()
			_criar_templates_padrao()

			from apps.documentos.services import criar_documentos_padrao
			criar_documentos_padrao()

		tenant.provisionamento_status = 'pronto'
		tenant.save(update_fields=['provisionamento_status'])
		logger.info('Tenant provisionado: %s (schema=%s)', tenant.nome, tenant.schema_name)

		_criar_assinatura_asaas(tenant, billing_type=dados_admin.get('billing_type', 'BOLETO'))

		_enviar_email_boas_vindas(tenant, dados_admin['email'], dados_admin['senha'])

	except Exception as exc:
		tenant.provisionamento_status = 'erro'
		tenant.save(update_fields=['provisionamento_status'])
		logger.error('Falha ao provisionar tenant %s: %s', tenant_pk, exc)
		raise self.retry(countdown=30, max_retries=3)


def _criar_assinatura_asaas(tenant, billing_type='BOLETO'):
	"""
	Cria customer + subscription no Asaas pra cobrança da mensalidade do tenant.
	Roda fora do schema_context (Tenant é modelo público — SHARED_APPS).
	NUNCA falha o provisionamento: erro aqui só é logado, e o admin corrige
	manualmente depois preenchendo asaas_customer_id/asaas_subscription_id.
	`billing_type`: 'BOLETO' | 'PIX' | 'CREDIT_CARD' — forma de pagamento
	escolhida pelo tenant no cadastro.
	"""
	from apps.billing.client import AsaasClient, AsaasError

	if not tenant.plano:
		logger.warning('Tenant %s sem plano — pulando criação de assinatura Asaas', tenant.schema_name)
		return

	try:
		client = AsaasClient()
		customer = client.criar_customer(
			tenant.nome,
			tenant.cnpj or tenant.cpf or '',
			email=tenant.email,
			external_reference=tenant.pk,
		)
		subscription = client.criar_subscription(
			customer['id'],
			tenant.plano.preco_mensal,
			timezone.localdate(),
			billing_type=billing_type,
			descricao=f'DNImob — Plano {tenant.plano.get_nome_display()}',
		)

		tenant.asaas_customer_id = customer['id']
		tenant.asaas_subscription_id = subscription['id']
		tenant.save(update_fields=['asaas_customer_id', 'asaas_subscription_id', 'atualizado_em'])

		logger.info(
			'Asaas: customer=%s subscription=%s criados para tenant %s',
			customer['id'], subscription['id'], tenant.schema_name,
		)
	except AsaasError as e:
		logger.error(
			'Erro ao criar customer/subscription Asaas para tenant %s: %s',
			tenant.schema_name, e,
		)
	except Exception:
		logger.exception('Erro inesperado ao criar assinatura Asaas para tenant %s', tenant.schema_name)


def _enviar_email_boas_vindas(tenant, email_admin: str, senha: str):
	"""Envia e-mail de boas-vindas ao admin da imobiliária após provisionamento."""
	dominio = Domain.objects.filter(tenant=tenant, is_primary=True).values_list('domain', flat=True).first()
	url_acesso = f'https://{dominio}/login/' if dominio else ''
	nome_imob = tenant.nome

	assunto = f'Bem-vindo ao DNImob — {nome_imob}'

	corpo_texto = (
		f'Olá!\n\n'
		f'A conta da {nome_imob} foi criada com sucesso no DNImob.\n\n'
		f'Seus dados de acesso:\n'
		f'  Endereço: {url_acesso}\n'
		f'  E-mail:   {email_admin}\n'
		f'  Senha:    {senha}\n\n'
		f'Recomendamos alterar a senha no primeiro acesso.\n\n'
		f'Equipe DNImob'
	)

	corpo_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:40px 0">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

        <!-- Cabeçalho -->
        <tr>
          <td style="background:#1e40af;padding:32px 40px;text-align:center">
            <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700">DNImob</h1>
            <p style="margin:6px 0 0;color:#bfdbfe;font-size:14px">Sistema de Gestão Imobiliária</p>
          </td>
        </tr>

        <!-- Corpo -->
        <tr>
          <td style="padding:40px">
            <h2 style="margin:0 0 16px;color:#111827;font-size:20px">Conta criada com sucesso! 🎉</h2>
            <p style="margin:0 0 24px;color:#374151;font-size:15px;line-height:1.6">
              Olá! A conta da <strong>{nome_imob}</strong> foi configurada e está pronta para uso.
            </p>

            <!-- Box de credenciais -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:24px">
              <tr><td style="padding:24px">
                <p style="margin:0 0 12px;color:#6b7280;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em">
                  Dados de acesso
                </p>
                <table cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="color:#6b7280;font-size:14px;padding:4px 16px 4px 0;white-space:nowrap">Endereço</td>
                    <td style="font-size:14px;font-weight:600;color:#1e40af">
                      <a href="{url_acesso}" style="color:#1e40af;text-decoration:none">{url_acesso}</a>
                    </td>
                  </tr>
                  <tr>
                    <td style="color:#6b7280;font-size:14px;padding:4px 16px 4px 0;white-space:nowrap">E-mail</td>
                    <td style="font-size:14px;font-weight:600;color:#111827">{email_admin}</td>
                  </tr>
                  <tr>
                    <td style="color:#6b7280;font-size:14px;padding:4px 16px 4px 0;white-space:nowrap">Senha</td>
                    <td style="font-size:14px;font-family:monospace;background:#e5e7eb;padding:2px 8px;border-radius:4px;color:#111827">{senha}</td>
                  </tr>
                </table>
              </td></tr>
            </table>

            <!-- CTA -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px">
              <tr>
                <td style="background:#1e40af;border-radius:6px">
                  <a href="{url_acesso}"
                     style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none">
                    Acessar o sistema →
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0;color:#6b7280;font-size:13px;line-height:1.6">
              ⚠️ Por segurança, altere a senha no primeiro acesso.<br>
              Se tiver dúvidas, responda este e-mail.
            </p>
          </td>
        </tr>

        <!-- Rodapé -->
        <tr>
          <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:20px 40px;text-align:center">
            <p style="margin:0;color:#9ca3af;font-size:12px">
              DNImob · Sistema SaaS de Gestão Imobiliária<br>
              Este e-mail foi gerado automaticamente — não responda caso não reconheça.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

	remetente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@dnsoftware.com.br')

	try:
		resp = requests.post(
			'https://api.resend.com/emails',
			headers={
				'Authorization': f'Bearer {settings.RESEND_API_KEY}',
				'Content-Type': 'application/json',
			},
			json={
				'from': remetente,
				'to': [email_admin],
				'subject': assunto,
				'text': corpo_texto,
				'html': corpo_html,
			},
			timeout=15,
		)
		resp.raise_for_status()
		logger.info('E-mail de boas-vindas enviado para %s (tenant: %s)', email_admin, tenant.schema_name)
	except Exception:
		# Não derruba o provisionamento — e-mail é best-effort
		logger.exception('Falha ao enviar e-mail de boas-vindas para %s', email_admin)
