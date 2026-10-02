"""
apps/whatsapp/tests.py

Testes das funções notificar_* (apps.whatsapp.services). Os agendamentos
diários que as chamam (lembrete de vencimento, cobrança de atraso) vivem
em apps.financeiro.tasks — ver apps/financeiro/tests.py.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django_tenants.postgresql_backend.base import FakeTenant
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name, schema_context

from apps.contratos.models import Contrato, Parcela
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino
from apps.tenants.models import InstanciaWhatsApp, Plano, TemplateWhatsApp, Tenant

from .models import LogMensagem
from .services import _get_instancia, enviar_mensagem, get_client_for_tenant, notificar_parcela_vencida


class WhatsappTestCase(TenantTestCase):

    def setUp(self):
        self._patches = [
            patch('apps.whatsapp.tasks.task_contrato_criado.apply_async'),
            patch('apps.whatsapp.tasks.task_pagamento_confirmado.apply_async'),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

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
            data_inicio=date.today(), data_fim=date(2030, 1, 1),
            valor_aluguel=Decimal('1500.00'),
        )


class MensagensCompetenciaTests(WhatsappTestCase):
    """
    Mensagens agora vêm de TemplateWhatsApp (apps.tenants), não mais de
    f-string hardcoded — por isso os templates padrão precisam existir no
    schema do teste, igual acontece em produção via provisionar_tenant.
    """

    def setUp(self):
        super().setUp()
        from apps.tenants.services import _criar_templates_padrao
        _criar_templates_padrao()

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_notificar_lembrete_vencimento_monta_mensagem_sem_erro(self, mock_enviar):
        from apps.whatsapp.services import notificar_lembrete_vencimento

        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2026, 1, 20), valor=Decimal('1500.00'),
            competencia='01/2026',
        )

        resultado = notificar_lembrete_vencimento(parcela)

        self.assertTrue(resultado)
        texto = mock_enviar.call_args.kwargs['mensagem']
        self.assertIn('20/01/2026', texto)

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_notificar_vencimento_hoje_monta_mensagem_sem_erro(self, mock_enviar):
        from apps.whatsapp.services import notificar_vencimento_hoje

        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2026, 1, 20), valor=Decimal('1500.00'),
            competencia='01/2026',
        )

        resultado = notificar_vencimento_hoje(parcela)

        self.assertTrue(resultado)
        texto = mock_enviar.call_args.kwargs['mensagem']
        self.assertIn('20/01/2026', texto)

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_notificar_parcela_vencida_monta_mensagem_sem_erro(self, mock_enviar):
        from apps.whatsapp.services import notificar_parcela_vencida

        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2020, 1, 5), valor=Decimal('1500.00'),
            competencia='01/2020',
        )

        resultado = notificar_parcela_vencida(parcela)

        self.assertTrue(resultado)
        texto = mock_enviar.call_args.kwargs['mensagem']
        self.assertIn('3 dias', texto)

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_notificar_pagamento_confirmado_monta_mensagem_sem_erro(self, mock_enviar):
        from apps.whatsapp.services import notificar_pagamento_confirmado

        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2026, 1, 20), valor=Decimal('1500.00'),
            competencia='01/2026',
            data_pagamento=date(2026, 1, 18), status='pago',
        )

        resultado = notificar_pagamento_confirmado(parcela)

        self.assertTrue(resultado)
        texto = mock_enviar.call_args.kwargs['mensagem']
        self.assertIn('01/2026', texto)


class TenantEmTaskCeleryTests(WhatsappTestCase):
    """Dentro de tasks Celery o schema é ativado com schema_context e connection.tenant vira FakeTenant."""

    def _instancia(self, nome, tenant):
        return InstanciaWhatsApp.objects.create(nome_instancia=nome, tenant=tenant, status='conectado')

    def _outro_tenant(self):
        tenant = Tenant(
            schema_name='imob_outro_wpp', nome='Outra', email='o@y.com',
            plano=Plano.objects.filter(ativo=True).first(), provisionamento_status='pronto',
        )
        tenant.auto_create_schema = False
        with schema_context(get_public_schema_name()):
            tenant.save()
        return tenant

    def test_get_instancia_sob_fake_tenant_devolve_a_do_tenant(self):
        propria = self._instancia('propria', self.tenant)
        self._instancia('alheia', self._outro_tenant())
        self._instancia('orfa', None)

        with schema_context(self.tenant.schema_name):
            self.assertIsInstance(connection.tenant, FakeTenant)
            encontrada = _get_instancia()

        self.assertEqual(encontrada, propria)

    def test_get_instancia_sem_instancia_do_tenant_devolve_none(self):
        self._instancia('alheia', self._outro_tenant())
        self._instancia('orfa', None)

        with schema_context(self.tenant.schema_name):
            self.assertIsNone(_get_instancia())

    def test_get_instancia_e_deterministica_com_mais_de_uma(self):
        primeira = self._instancia('a-primeira', self.tenant)
        self._instancia('b-segunda', self.tenant)

        with schema_context(self.tenant.schema_name):
            self.assertEqual(_get_instancia(), primeira)

    def test_get_client_sem_instancia_devolve_none_e_envio_registra_nao_configurado(self):
        with schema_context(self.tenant.schema_name):
            self.assertIsNone(get_client_for_tenant())

            resultado = enviar_mensagem('5585999999999', 'oi', 'parcela_vencida')

        self.assertFalse(resultado)
        log = LogMensagem.objects.get()
        self.assertEqual(log.status, LogMensagem.Status.ERRO)
        self.assertIn('não configurado', log.erro_detalhe)

    def test_get_client_com_instancia_usa_o_nome_da_instancia_do_tenant(self):
        self._instancia('minha-instancia', self.tenant)

        with schema_context(self.tenant.schema_name):
            client = get_client_for_tenant()

        self.assertEqual(client.instance, 'minha-instancia')

    def test_notificar_parcela_vencida_sob_fake_tenant_usa_nome_da_imobiliaria(self):
        from apps.tenants.services import _criar_templates_padrao
        _criar_templates_padrao()
        TemplateWhatsApp.objects.filter(evento='atraso_3').update(mensagem='{nome_imobiliaria}|{valor}')
        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2020, 1, 5), valor=Decimal('1500.00'), competencia='01/2020',
        )

        with patch('apps.whatsapp.services.enviar_mensagem', return_value=True) as mock_enviar:
            with schema_context(self.tenant.schema_name):
                self.assertIsInstance(connection.tenant, FakeTenant)
                resultado = notificar_parcela_vencida(parcela)

        self.assertTrue(resultado)
        self.assertTrue(mock_enviar.call_args.kwargs['mensagem'].startswith(f'{self.tenant.nome}|'))

    def test_notificar_parcela_vencida_registra_log_quando_nao_acha_o_tenant(self):
        parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2020, 1, 5), valor=Decimal('1500.00'), competencia='01/2020',
        )

        with patch('apps.core.tenancy.get_tenant_atual', side_effect=Tenant.DoesNotExist('sem tenant')):
            resultado = notificar_parcela_vencida(parcela)

        self.assertFalse(resultado)
        log = LogMensagem.objects.get()
        self.assertEqual(log.status, LogMensagem.Status.ERRO)
        self.assertEqual(log.evento, LogMensagem.Evento.PARCELA_VENCIDA)
        self.assertEqual(log.parcela_id, parcela.pk)
        self.assertIn('Imobiliária não identificada', log.erro_detalhe)
