"""
apps/tenants/tests.py

Testes do app tenants (schema public — SHARED_APPS, TestCase comum,
sem TenantTestCase, já que Plano/Tenant/Domain vivem no schema public).
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django_tenants.test.cases import TenantTestCase

from .forms import ConfigSicrediForm
from .models import ConfigSicredi, Plano, Tenant
from .views import config_sicredi, landing, superadmin_asaas_pagamento


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


class ConfigSicrediFormMascaramentoTests(TestCase):

    def test_api_key_usa_password_input(self):
        form = ConfigSicrediForm()
        self.assertIsInstance(form.fields['api_key'].widget, forms.PasswordInput)

    def test_codigo_acesso_continua_password_input(self):
        form = ConfigSicrediForm()
        self.assertIsInstance(form.fields['codigo_acesso'].widget, forms.PasswordInput)

    def test_password_inputs_mantem_render_value_true(self):
        form = ConfigSicrediForm()
        for nome in ('api_key', 'codigo_acesso'):
            self.assertTrue(form.fields[nome].widget.render_value)

    def test_webhook_secret_e_readonly_nao_password(self):
        form = ConfigSicrediForm()
        self.assertNotIsInstance(form.fields['webhook_secret'].widget, forms.PasswordInput)
        self.assertIn('readonly', form.fields['webhook_secret'].widget.attrs)


class AcessoBloqueadoTests(TenantTestCase):
    """
    Regressão do bug: PlanoAcessoMiddleware redirecionava para a URL name
    'acesso_bloqueado', que não existia -- NoReverseMatch (erro 500) em vez
    de mostrar uma tela de bloqueio.
    """

    def setUp(self):
        Usuario = get_user_model()
        self.user = Usuario.objects.create_user(username='user-teste', password='senha123')
        self.client.login(username='user-teste', password='senha123')

    def test_trial_expirado_redireciona_para_acesso_bloqueado(self):
        self.tenant.trial = True
        self.tenant.trial_expira = date.today() - timedelta(days=1)
        self.tenant.save()

        resp = self.client.get(reverse('dashboard'), HTTP_HOST=self.domain.domain)

        self.assertRedirects(
            resp, reverse('acesso_bloqueado'), fetch_redirect_response=False,
        )

    def test_tenant_suspenso_redireciona_para_acesso_bloqueado(self):
        self.tenant.ativo = False
        self.tenant.save()

        resp = self.client.get(reverse('dashboard'), HTTP_HOST=self.domain.domain)

        self.assertRedirects(
            resp, reverse('acesso_bloqueado'), fetch_redirect_response=False,
        )

    def test_rota_acesso_bloqueado_nao_entra_em_loop_com_tenant_bloqueado(self):
        self.tenant.trial = True
        self.tenant.trial_expira = date.today() - timedelta(days=1)
        self.tenant.save()

        resp = self.client.get(reverse('acesso_bloqueado'), HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 200)

    def test_mensagem_reflete_trial_expirado(self):
        self.tenant.trial = True
        self.tenant.trial_expira = date.today() - timedelta(days=1)
        self.tenant.save()

        resp = self.client.get(reverse('acesso_bloqueado'), HTTP_HOST=self.domain.domain)

        self.assertIn('período de teste expirou', resp.content.decode())

    def test_tenant_com_acesso_permitido_nao_e_bloqueado(self):
        self.tenant.trial = True
        self.tenant.trial_expira = date.today() + timedelta(days=5)
        self.tenant.save()

        resp = self.client.get(reverse('dashboard'), HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 200)

    def test_favicon_nao_e_redirecionado_com_tenant_bloqueado(self):
        self.tenant.trial = True
        self.tenant.trial_expira = date.today() - timedelta(days=1)
        self.tenant.save()

        resp = self.client.get('/favicon.ico', HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 404)


class ConfigSicrediWebhookSecretTests(TenantTestCase):
    """
    Regressão da troca de mecanismo de auth do webhook (HMAC/X-Signature,
    que a Sicredi nunca envia, -> secret embutido no path da URL): o secret
    passa a ser gerado automaticamente, e a URL exibida na tela precisa
    mostrar o path/host corretos.
    """

    def setUp(self):
        self.factory = RequestFactory()
        Usuario = get_user_model()
        self.user = Usuario.objects.create_user(
            username='admin-teste', password='senha123', is_staff=True,
        )

    def _request(self, method='get', data=None):
        request = getattr(self.factory, method)('/configuracoes/sicredi/', data=data or {})
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request.user = self.user
        request.tenant = self.tenant
        request._messages = FallbackStorage(request)
        return request

    def test_gera_webhook_secret_automaticamente_no_primeiro_save(self):
        request = self._request('post', {
            'api_key': 'key-teste', 'codigo_acesso': 'acesso-teste',
            'codigo_beneficiario': '12345', 'cooperativa': '1234', 'posto': '01',
            'conta': '', 'beneficiario': 'Imobiliaria Teste', 'ambiente': 'sandbox',
            'webhook_secret': '',
        })

        config_sicredi(request)

        config = ConfigSicredi.objects.get(schema_name=self.tenant.schema_name)
        self.assertTrue(config.webhook_secret)
        self.assertGreaterEqual(len(config.webhook_secret), 32)

    def test_nao_regenera_secret_se_ja_existir(self):
        ConfigSicredi.objects.create(
            schema_name=self.tenant.schema_name, cooperativa='1234', posto='01',
            beneficiario='Imobiliaria Teste', webhook_secret='secret-existente',
        )

        request = self._request('post', {
            'api_key': 'key-teste', 'codigo_acesso': 'acesso-teste',
            'codigo_beneficiario': '12345', 'cooperativa': '1234', 'posto': '01',
            'conta': '', 'beneficiario': 'Imobiliaria Teste', 'ambiente': 'sandbox',
            'webhook_secret': 'secret-existente',
        })

        config_sicredi(request)

        config = ConfigSicredi.objects.get(schema_name=self.tenant.schema_name)
        self.assertEqual(config.webhook_secret, 'secret-existente')

    def test_url_webhook_exibida_contem_secret_e_path_correto(self):
        ConfigSicredi.objects.create(
            schema_name=self.tenant.schema_name, cooperativa='1234', posto='01',
            beneficiario='Imobiliaria Teste', webhook_secret='secret-fixo-teste',
        )

        response = config_sicredi(self._request('get'))
        conteudo = response.content.decode()

        self.assertIn('/sicredi/webhook/secret-fixo-teste/', conteudo)


def _resp(status_code, json_data=None, text=''):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or str(json_data or '')
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class SuperadminAsaasPagamentoTests(TenantTestCase):
    """
    Tela de pagamento Asaas mora no admin-master (superadmin), não nas
    configurações da imobiliária — só o superuser DN Software acessa.

    Nota: override_settings aqui é aplicado por método (não na classe) porque
    TenantTestCase.setUpClass não chama super().setUpClass(), então o hook do
    Django que aplica @override_settings de classe nunca dispara.
    """

    def setUp(self):
        self.factory = RequestFactory()
        Usuario = get_user_model()
        self.superuser = Usuario.objects.create_user(
            username='super-teste', password='senha123', is_superuser=True, is_staff=True,
        )
        self.admin_tenant = Usuario.objects.create_user(
            username='admin-tenant-teste', password='senha123', is_staff=True,
        )
        self.tenant.asaas_customer_id = 'cus_123'
        self.tenant.asaas_subscription_id = 'sub_456'
        self.tenant.save()

    def _request(self, method, user, data=None):
        request = getattr(self.factory, method)(f'/admin-master/tenant/{self.tenant.pk}/asaas/', data=data or {})
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request.user = user
        request._messages = FallbackStorage(request)
        return request

    @override_settings(
        ASAAS_API_URL='https://api-sandbox.asaas.com/v3', ASAAS_API_KEY='chave-teste-sandbox',
        ROOT_URLCONF='config.urls_public',
    )
    @patch('requests.Session.get')
    def test_superadmin_asaas_pagamento_get_retorna_200(self, mock_get):
        mock_get.return_value = _resp(200, {'id': 'sub_456', 'billingType': 'BOLETO'})

        response = superadmin_asaas_pagamento(self._request('get', self.superuser), tenant_id=self.tenant.pk)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        ASAAS_API_URL='https://api-sandbox.asaas.com/v3', ASAAS_API_KEY='chave-teste-sandbox',
        ROOT_URLCONF='config.urls_public',
    )
    @patch('requests.Session.patch')
    @patch('requests.Session.get')
    def test_superadmin_asaas_pagamento_post_boleto(self, mock_get, mock_patch):
        mock_get.return_value = _resp(200, {'id': 'sub_456', 'billingType': 'PIX'})
        mock_patch.return_value = _resp(200, {'id': 'sub_456', 'billingType': 'BOLETO'})

        superadmin_asaas_pagamento(
            self._request('post', self.superuser, data={'billing_type': 'BOLETO'}), tenant_id=self.tenant.pk,
        )

        payload = mock_patch.call_args.kwargs['json']
        self.assertEqual(payload['billingType'], 'BOLETO')

    def test_superadmin_asaas_pagamento_nao_acessivel_por_tenant_admin(self):
        response = superadmin_asaas_pagamento(self._request('get', self.admin_tenant), tenant_id=self.tenant.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-master/login/', response.url)
