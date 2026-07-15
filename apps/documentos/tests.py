"""
apps/documentos/tests.py
Testes minimos dos models de documentos (models basicos: str, unicidade, FK).
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django_tenants.test.cases import TenantTestCase

from apps.contratos.models import Contrato
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino

from .models import ContratoDocumentoGerado, ModeloDocumento, VariavelDocumento


class ModeloDocumentoTests(TenantTestCase):

    def test_str_usa_tipo_e_titulo(self):
        modelo = ModeloDocumento.objects.create(
            titulo='Contrato Residencial Padrão', tipo='contrato',
        )

        self.assertEqual(str(modelo), 'Contrato de Locação — Contrato Residencial Padrão')


class VariavelDocumentoTests(TenantTestCase):

    def test_slug_deve_ser_unico(self):
        VariavelDocumento.objects.create(
            slug='inquilino.nome', label='Nome do Inquilino', categoria='inquilino',
        )

        with self.assertRaises(IntegrityError):
            VariavelDocumento.objects.create(
                slug='inquilino.nome', label='Duplicado', categoria='inquilino',
            )


class ContratoDocumentoGeradoTests(TenantTestCase):

    def setUp(self):
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

    def test_criar_documento_gerado_vinculado_ao_contrato(self):
        documento = ContratoDocumentoGerado.objects.create(
            contrato=self.contrato, titulo='Contrato CT-0001',
            conteudo_final_html='<p>teste</p>',
        )

        self.assertEqual(documento.contrato, self.contrato)
        self.assertEqual(documento.status, 'gerado')
        self.assertEqual(str(documento), f'Contrato CT-0001 — Contrato {self.contrato.pk}')
