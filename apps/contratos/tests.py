"""
apps/contratos/tests.py
Testes de geracao de parcelas -- calculo de competencia conforme regra_competencia.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from apps.documentos.models import ModeloDocumento
from apps.financeiro.models import Lancamento
from apps.financeiro.views import _resumo_mes
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino

from .forms import ContratoForm
from .models import Contrato, Parcela
from .services import estornar_parcela


class GerarParcelasCompetenciaTests(TenantTestCase):

    def setUp(self):
        self._patches = [
            patch('apps.whatsapp.tasks.task_contrato_criado.apply_async'),
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

    def _criar_contrato(self, regra_competencia):
        return Contrato.objects.create(
            imovel=self.imovel, inquilino=self.inquilino, numero='0001',
            data_inicio=date(2026, 1, 10), data_fim=date(2026, 1, 10),
            dia_vencimento=10, valor_aluguel=Decimal('1500.00'),
            regra_competencia=regra_competencia,
        )

    def test_gerar_parcelas_mesmo_mes_competencia_igual_mes_vencimento(self):
        contrato = self._criar_contrato(Contrato.MESMO_MES)

        contrato.gerar_parcelas()

        parcela = contrato.parcelas.get()
        self.assertEqual(parcela.data_vencimento, date(2026, 1, 10))
        self.assertEqual(parcela.competencia, '01/2026')

    def test_gerar_parcelas_mes_anterior_competencia_um_mes_antes(self):
        contrato = self._criar_contrato(Contrato.MES_ANTERIOR)

        contrato.gerar_parcelas()

        parcela = contrato.parcelas.get()
        self.assertEqual(parcela.data_vencimento, date(2026, 1, 10))
        self.assertEqual(parcela.competencia, '12/2025')


class ContratoFormRegraCompetenciaTests(TenantTestCase):
    """
    Regressão do bug: regra_competencia é campo obrigatório no model (sem
    blank=True) mas não aparecia no template contratos/form.html, travando
    todo cadastro de contrato novo.
    """

    def setUp(self):
        self._patches = [
            patch('apps.whatsapp.tasks.task_contrato_criado.apply_async'),
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
        self.form_data = {
            'imovel': self.imovel.pk,
            'inquilino': self.inquilino.pk,
            'numero': 'CT-0001',
            'status': 'pendente',
            'data_inicio': '2026-01-10',
            'data_fim': '2026-12-10',
            'dia_vencimento': '10',
            'valor_aluguel': '1500.00',
            'valor_condominio': '0',
            'valor_iptu': '0',
            'indice_reajuste': 'igpm',
            'percentual_fixo': '0',
            'periodicidade_reajuste': '12',
            'tipo_garantia': 'nenhuma',
            'multa_rescisao': '10',
            'clausulas_adicionais': '',
            'observacoes': '',
        }

    def test_form_sem_regra_competencia_falha_validacao(self):
        form = ContratoForm(data=self.form_data)

        self.assertFalse(form.is_valid())
        self.assertIn('regra_competencia', form.errors)

    def test_form_com_regra_competencia_explicita_salva(self):
        data = {**self.form_data, 'regra_competencia': Contrato.MES_ANTERIOR}
        form = ContratoForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        contrato = form.save()
        self.assertEqual(contrato.regra_competencia, Contrato.MES_ANTERIOR)

    def test_tela_contrato_novo_exibe_campo_regra_competencia(self):
        User = get_user_model()
        User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')

        resp = self.client.get(reverse('contrato_criar'), HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="regra_competencia"', resp.content)


class EstornarParcelaTests(TenantTestCase):
    """
    Regressão do bug: estorno manual (tela de contrato) não cancelava o
    Lancamento, deixando receita "fantasma" no financeiro. Os dois
    caminhos (webhook Sicredi e botão manual) agora passam por
    `contratos.services.estornar_parcela`.
    """

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
            imovel=self.imovel, inquilino=self.inquilino, numero='CT-0001',
            data_inicio=date(2026, 1, 10), data_fim=date(2026, 12, 10),
            dia_vencimento=10, valor_aluguel=Decimal('1500.00'),
        )
        self.parcela = Parcela.objects.create(
            contrato=self.contrato, numero=1,
            data_vencimento=date(2026, 1, 10), valor=Decimal('1500.00'),
        )

    def _marcar_paga(self, hoje):
        self.parcela.status = 'pago'
        self.parcela.data_pagamento = hoje
        self.parcela.save()
        # Signal financeiro.parcela_paga_signal cria o Lancamento automaticamente

    def test_estornar_parcela_service_cancela_lancamento(self):
        hoje = date(2026, 1, 10)
        self._marcar_paga(hoje)
        self.assertEqual(Lancamento.objects.get(parcela=self.parcela).status, 'realizado')

        estornar_parcela(self.parcela, motivo='teste')

        self.parcela.refresh_from_db()
        self.assertEqual(self.parcela.status, 'pendente')
        self.assertIsNone(self.parcela.data_pagamento)
        self.assertEqual(Lancamento.objects.get(parcela=self.parcela).status, 'cancelado')

    def test_parcela_estornar_view_manual_cancela_lancamento(self):
        hoje = date(2026, 1, 10)
        self._marcar_paga(hoje)

        User = get_user_model()
        User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')

        resp = self.client.post(
            reverse('parcela_estornar', args=[self.parcela.pk]),
            HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 302)
        self.parcela.refresh_from_db()
        self.assertEqual(self.parcela.status, 'pendente')
        self.assertIsNone(self.parcela.data_pagamento)
        self.assertEqual(Lancamento.objects.get(parcela=self.parcela).status, 'cancelado')

    def test_parcela_estornar_view_manual_nao_conta_mais_no_resumo_financeiro(self):
        hoje = date(2026, 1, 10)
        self._marcar_paga(hoje)

        receitas_antes, _, _ = _resumo_mes(2026, 1)
        self.assertEqual(receitas_antes, Decimal('1500.00'))

        User = get_user_model()
        User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')
        self.client.post(
            reverse('parcela_estornar', args=[self.parcela.pk]),
            HTTP_HOST=self.domain.domain,
        )

        receitas_depois, _, _ = _resumo_mes(2026, 1)
        self.assertEqual(receitas_depois, Decimal('0'))


class ContratoDetalheModelosDocumentoTests(TenantTestCase):

    def setUp(self):
        self._patches = [
            patch('apps.whatsapp.tasks.task_contrato_criado.apply_async'),
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
            imovel=self.imovel, inquilino=self.inquilino, numero='CT-0001',
            data_inicio=date(2026, 1, 10), data_fim=date(2026, 12, 10),
            dia_vencimento=10, valor_aluguel=Decimal('1500.00'),
        )
        self.modelo = ModeloDocumento.objects.create(
            titulo='Modelo Teste', tipo='contrato', conteudo_html='<p>{{ contrato.numero }}</p>',
        )

        User = get_user_model()
        User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')

    def test_contrato_detalhe_inclui_modelos_documento_no_contexto(self):
        resp = self.client.get(
            reverse('contrato_detalhe', args=[self.contrato.pk]), HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('modelos_documento', resp.context)
        self.assertIn(self.modelo, list(resp.context['modelos_documento']))
