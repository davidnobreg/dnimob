"""
apps/financeiro/tests.py

Regressão do bug de duplicidade/spam do Celery Beat: havia dois agendamentos
concorrentes (apps.whatsapp.tasks + apps.financeiro.tasks) cobrindo o mesmo
envio de WhatsApp de cobrança. Removido o de apps.whatsapp.tasks; estes testes
cobrem o que ficou em apps.financeiro.tasks:
  - _cobrar_inadimplentes só dispara nos dias exatos (3/7/15), não todo dia.
  - _avisar_vencimento_hoje usa o template certo (vence_hoje), não o de D-1.
  - nenhuma das três reenviam pra mesma parcela no mesmo dia (_ja_enviou_hoje).
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django_tenants.test.cases import TenantTestCase

from apps.contratos.models import Contrato, Parcela
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino
from apps.tenants.models import InstanciaWhatsApp
from apps.tenants.services import _criar_templates_padrao


class FinanceiroWhatsappTestCase(TenantTestCase):

    def setUp(self):
        _criar_templates_padrao()
        InstanciaWhatsApp.objects.create(
            nome_instancia='teste', evolution_url='http://evolution.local',
            token_api='token-teste', status='conectado',
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
            data_inicio=date.today(), data_fim=date(2030, 1, 1),
            valor_aluguel=Decimal('1500.00'),
        )


class CobrarInadimplentesTests(FinanceiroWhatsappTestCase):

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_so_dispara_nos_dias_exatos_3_7_15(self, mock_enviar):
        from apps.financeiro.tasks import _cobrar_inadimplentes

        hoje = date.today()
        # 5 dias de atraso: não é 3, 7 nem 15 — não deve gerar envio.
        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=hoje - timedelta(days=5),
            valor=Decimal('1500.00'), status='atrasado',
        )
        # 7 dias de atraso: deve gerar envio.
        Parcela.objects.create(
            contrato=self.contrato, numero=2,
            data_vencimento=hoje - timedelta(days=7),
            valor=Decimal('1500.00'), status='atrasado',
        )

        _cobrar_inadimplentes()

        self.assertEqual(mock_enviar.call_count, 1)

    @patch('apps.whatsapp.services.EvolutionAPIClient.enviar_texto', return_value={})
    def test_nao_reenvia_no_mesmo_dia(self, mock_enviar_texto):
        from apps.financeiro.tasks import _cobrar_inadimplentes

        hoje = date.today()
        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=hoje - timedelta(days=3),
            valor=Decimal('1500.00'), status='atrasado',
        )

        _cobrar_inadimplentes()
        _cobrar_inadimplentes()

        self.assertEqual(mock_enviar_texto.call_count, 1)


class AvisarVencimentoTests(FinanceiroWhatsappTestCase):

    @patch('apps.whatsapp.services.enviar_mensagem', return_value=True)
    def test_vencimento_hoje_usa_template_vence_hoje(self, mock_enviar):
        from apps.financeiro.tasks import _avisar_vencimento_hoje

        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date.today(),
            valor=Decimal('1500.00'), status='pendente',
        )

        _avisar_vencimento_hoje()

        self.assertEqual(mock_enviar.call_count, 1)
        texto = mock_enviar.call_args.kwargs['mensagem']
        self.assertIn('hoje', texto.lower())

    @patch('apps.whatsapp.services.EvolutionAPIClient.enviar_texto', return_value={})
    def test_vencimento_amanha_nao_reenvia_no_mesmo_dia(self, mock_enviar_texto):
        from apps.financeiro.tasks import _avisar_vencimento_amanha

        Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date.today() + timedelta(days=1),
            valor=Decimal('1500.00'), status='pendente',
        )

        _avisar_vencimento_amanha()
        _avisar_vencimento_amanha()

        self.assertEqual(mock_enviar_texto.call_count, 1)