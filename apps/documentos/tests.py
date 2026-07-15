"""
apps/documentos/tests.py
Testes minimos dos models de documentos (models basicos: str, unicidade, FK)
e do backend da Fatia 2 (services de renderizacao/PDF e views AJAX).
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from apps.contratos.models import Contrato
from apps.imoveis.models import Imovel
from apps.inquilinos.models import Inquilino

from .models import ContratoDocumentoGerado, ModeloDocumento, VariavelDocumento
from .services import (
    construir_contexto,
    criar_documentos_padrao,
    renderizar_modelo,
    salvar_documento_gerado,
)


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


class RenderizacaoModeloTests(TenantTestCase):

    def setUp(self):
        self.imovel = Imovel.objects.create(
            codigo='IM-0001', tipo='apartamento', cep='60000000',
            logradouro='Rua Teste', numero='100', bairro='Centro',
            cidade='Fortaleza', estado='CE',
            proprietario_nome='Maria Souza', proprietario_cpf_cnpj='11122233344',
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

    def test_construir_contexto_retorna_chaves_esperadas(self):
        contexto = construir_contexto(self.contrato)

        self.assertEqual(contexto['inquilino']['nome'], 'Rodrigo Oliveira')
        self.assertEqual(contexto['imovel']['proprietario_nome'], 'Maria Souza')
        self.assertEqual(contexto['contrato']['numero'], 'CT-0001')
        self.assertIn('data_atual', contexto['data'])

    def test_renderizar_modelo_substitui_variavel(self):
        html = renderizar_modelo('<p>{{ inquilino.nome }}</p>', self.contrato)

        self.assertEqual(html, '<p>Rodrigo Oliveira</p>')

    def test_renderizar_modelo_bloqueia_tag_de_logica(self):
        with self.assertRaises(ValueError):
            renderizar_modelo('{% if 1 %}x{% endif %}', self.contrato)


class ViewsDocumentosTests(TenantTestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')

        self.modelo = ModeloDocumento.objects.create(
            titulo='Modelo Teste', tipo='contrato', conteudo_html='<p>{{ contrato.numero }}</p>',
        )

    def test_lista_modelos_retorna_200(self):
        resp = self.client.get(reverse('documentos:lista_modelos'), HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 200)

    def test_salvar_modelo_retorna_ok_true(self):
        resp = self.client.post(
            reverse('documentos:salvar_modelo', args=[self.modelo.pk]),
            data=json.dumps({'conteudo_html': '<p>Novo conteúdo</p>'}),
            content_type='application/json',
            HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'ok': True})
        self.modelo.refresh_from_db()
        self.assertEqual(self.modelo.conteudo_html, '<p>Novo conteúdo</p>')

    def test_editor_modelo_retorna_200_com_contexto_esperado(self):
        resp = self.client.get(
            reverse('documentos:editor_modelo', args=[self.modelo.pk]), HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['modelo'], self.modelo)
        self.assertIn('variaveis', resp.context)
        conteudo_decodificado = json.loads(resp.context['conteudo_html_json'])
        self.assertEqual(conteudo_decodificado, self.modelo.conteudo_html)

    def test_criar_modelo_cria_e_redireciona_pro_editor(self):
        resp = self.client.post(
            reverse('documentos:criar_modelo'),
            data={'titulo': 'Recibo Padrão', 'tipo': 'recibo'},
            HTTP_HOST=self.domain.domain,
        )

        novo = ModeloDocumento.objects.get(titulo='Recibo Padrão')
        self.assertEqual(novo.tipo, 'recibo')
        self.assertRedirects(
            resp, reverse('documentos:editor_modelo', args=[novo.pk]),
            fetch_redirect_response=False,
        )


class GerarDocumentoDownloadTests(TenantTestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='senha123')
        self.client.login(username='tester', password='senha123')

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

    def test_gerar_documento_retorna_pdf(self):
        resp = self.client.post(
            reverse('documentos:gerar_documento'),
            data=json.dumps({'modelo_id': str(self.modelo.pk), 'contrato_id': self.contrato.pk}),
            content_type='application/json',
            HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(ContratoDocumentoGerado.objects.filter(contrato=self.contrato).exists())

    def test_download_documento_retorna_200_com_pdf(self):
        documento = salvar_documento_gerado(self.contrato, self.modelo, self.user)

        resp = self.client.get(
            reverse('documentos:download_documento', args=[documento.pk]), HTTP_HOST=self.domain.domain,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')


class CriarDocumentosPadraoTests(TenantTestCase):

    def test_criar_documentos_padrao_idempotente(self):
        criar_documentos_padrao()
        count1 = VariavelDocumento.objects.count()
        criar_documentos_padrao()
        count2 = VariavelDocumento.objects.count()

        self.assertEqual(count1, count2)

    def test_criar_documentos_padrao_cria_modelos(self):
        criar_documentos_padrao()

        self.assertEqual(ModeloDocumento.objects.filter(padrao=True).count(), 3)
