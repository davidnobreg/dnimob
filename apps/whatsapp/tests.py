"""
apps/whatsapp/tests.py

Bug A: Parcela.Status.PENDENTE/.ATRASADO nao existem (Parcela so tem STATUS_CHOICES,
sem classe Status) -- tasks.py filtrava por esses atributos inexistentes.

Bug B: parcela.competencia nunca existiu no model -- usado direto nas mensagens
de apps/whatsapp/services.py.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django_tenants.test.cases import TenantTestCase

from apps.contratos.models import Contrato, Parcela
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino


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


# ── Bug A: filtro por status em tasks.py ────────────────────────────────────

class FiltroStatusTasksTests(WhatsappTestCase):

    @patch('apps.whatsapp.services.notificar_lembrete_vencimento')
    def test_enviar_lembretes_tenant_filtra_status_pendente_sem_erro(self, mock_notificar):
        from apps.whatsapp.tasks import _enviar_lembretes_tenant

        data_alvo = date(2026, 1, 13)
        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=data_alvo, valor=Decimal('1500.00'),
            status='pendente',
        )

        _enviar_lembretes_tenant(data_alvo)

        mock_notificar.assert_called_once()

    @patch('apps.whatsapp.services.notificar_parcela_vencida')
    def test_enviar_cobrancas_tenant_filtra_status_atrasado_sem_erro(self, mock_notificar):
        from apps.whatsapp.tasks import _enviar_cobrancas_tenant

        data_venc = date(2026, 1, 5)
        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=data_venc, valor=Decimal('1500.00'),
            status='atrasado',
        )

        _enviar_cobrancas_tenant(data_venc)

        mock_notificar.assert_called_once()


# ── Bug B: parcela.competencia nas mensagens ────────────────────────────────

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
