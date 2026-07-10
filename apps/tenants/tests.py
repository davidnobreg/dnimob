"""
apps/tenants/tests.py

Testes do app tenants (schema public — SHARED_APPS, TestCase comum,
sem TenantTestCase, já que Plano/Tenant/Domain vivem no schema public).
"""
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve

from .models import Plano, Tenant
from .views import landing


@override_settings(ROOT_URLCONF='config.urls_public')
class LandingPlanosDinamicosTests(TestCase):

    def test_landing_renderiza_planos_vindos_do_banco(self):
        Plano.objects.update_or_create(nome=Plano.BASICO, defaults={
            'preco_mensal': 151, 'limite_imoveis': 10, 'limite_contratos': 10,
            'limite_usuarios': 2, 'tem_whatsapp': False, 'tem_sicredi': False, 'ativo': True,
        })
        Plano.objects.update_or_create(nome=Plano.PROFISSIONAL, defaults={
            'preco_mensal': 251, 'limite_imoveis': 100, 'limite_contratos': None,
            'limite_usuarios': 10, 'tem_whatsapp': True, 'tem_sicredi': True, 'ativo': True,
        })

        request = RequestFactory().get('/')
        response = landing(request)
        conteudo = response.content.decode()

        self.assertIn('151', conteudo)
        self.assertIn('251', conteudo)
        self.assertIn('Básico', conteudo)
        self.assertIn('Profissional', conteudo)
        self.assertIn('ilimitado', conteudo.lower())

    def test_landing_sem_planos_ativos_nao_quebra(self):
        Plano.objects.update(ativo=False)

        request = RequestFactory().get('/')
        response = landing(request)
        self.assertEqual(response.status_code, 200)

    def test_landing_ignora_plano_inativo(self):
        Plano.objects.update_or_create(nome=Plano.ENTERPRISE, defaults={
            'preco_mensal': 397, 'ativo': False,
        })

        request = RequestFactory().get('/')
        response = landing(request)
        conteudo = response.content.decode()

        self.assertNotIn('397', conteudo)

    def test_landing_plano_com_destaque_renderiza_como_mais_indicado(self):
        Plano.objects.update_or_create(nome=Plano.ENTERPRISE, defaults={
            'preco_mensal': 397, 'ativo': True, 'destaque': True,
        })

        request = RequestFactory().get('/')
        response = landing(request)
        conteudo = response.content.decode()

        self.assertIn('Mais indicado', conteudo)

    def test_landing_sem_plano_com_destaque_nao_quebra(self):
        Plano.objects.update(destaque=False, ativo=True)

        request = RequestFactory().get('/')
        response = landing(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Mais indicado', response.content.decode())


@override_settings(ROOT_URLCONF='config.urls_public')
class AceiteTermosPersistenciaTests(TestCase):

    def setUp(self):
        self.plano, _ = Plano.objects.update_or_create(
            nome=Plano.BASICO, defaults={'preco_mensal': 97, 'ativo': True},
        )

    def _post_cadastro(self, **meta):
        from .views import cadastro_imobiliaria
        request = RequestFactory().post('/cadastro/', {
            'nome_imobiliaria': 'Imobiliária Teste',
            'tipo_pessoa': 'PJ',
            'documento': '',
            'subdominio': 'teste-aceite',
            'plano': self.plano.pk,
            'nome_admin': 'Fulano de Tal',
            'email_admin': 'fulano@teste.com',
            'telefone_admin': '',
            'senha': 'senha1234',
            'senha_confirma': 'senha1234',
            'aceite_termos': 'on',
        }, **meta)
        return cadastro_imobiliaria(request)

    @patch('apps.tenants.tasks.provisionar_tenant.delay')
    def test_cadastro_persiste_user_agent_do_aceite(self, mock_delay):
        self._post_cadastro(
            REMOTE_ADDR='203.0.113.42',
            HTTP_USER_AGENT='Mozilla/5.0 (TesteAgent/1.0)',
        )

        tenant = Tenant.objects.get(schema_name='imob_teste_aceite')
        self.assertEqual(tenant.aceite_termos_user_agent, 'Mozilla/5.0 (TesteAgent/1.0)')

    @patch('apps.tenants.tasks.provisionar_tenant.delay')
    def test_cadastro_persiste_aceite_termos_em_e_ip(self, mock_delay):
        self._post_cadastro(REMOTE_ADDR='203.0.113.42')

        tenant = Tenant.objects.get(schema_name='imob_teste_aceite')
        self.assertIsNotNone(tenant.aceite_termos_em)
        self.assertEqual(tenant.aceite_termos_ip, '203.0.113.42')

    @patch('apps.tenants.tasks.provisionar_tenant.delay')
    def test_cadastro_usa_primeiro_ip_do_x_forwarded_for(self, mock_delay):
        self._post_cadastro(
            REMOTE_ADDR='10.0.0.1',
            HTTP_X_FORWARDED_FOR='198.51.100.7, 10.0.0.1',
        )

        tenant = Tenant.objects.get(schema_name='imob_teste_aceite')
        self.assertEqual(tenant.aceite_termos_ip, '198.51.100.7')


class PlanosFixadosMigrationTests(TestCase):

    def test_planos_pagos_existem_com_preco_e_ativo_corretos(self):
        precos_esperados = {
            Plano.BASICO: 97,
            Plano.PROFISSIONAL: 197,
            Plano.ENTERPRISE: 397,
        }
        for nome, preco in precos_esperados.items():
            plano = Plano.objects.get(nome=nome)
            self.assertEqual(plano.preco_mensal, preco)
            self.assertTrue(plano.ativo)


@override_settings(ROOT_URLCONF='config.urls_public')
class TermosPrivacidadeRotasTests(TestCase):

    def test_termos_resolve_para_view_e_retorna_200(self):
        match = resolve('/termos/')
        request = RequestFactory().get('/termos/')
        response = match.func(request)
        self.assertEqual(response.status_code, 200)

    def test_privacidade_resolve_para_view_e_retorna_200(self):
        match = resolve('/privacidade/')
        request = RequestFactory().get('/privacidade/')
        response = match.func(request)
        self.assertEqual(response.status_code, 200)
