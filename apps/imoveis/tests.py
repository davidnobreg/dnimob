"""
apps/imoveis/tests.py
Testes do campo opcional nome_imovel -- model, form e listagem.
"""
from django import forms as django_forms
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from .forms import ImovelForm
from .models import Imovel


class NomeImovelTests(TenantTestCase):

    def _dados_imovel(self, **overrides):
        dados = dict(
            tipo='apartamento', finalidade='aluguel', status='disponivel',
            cep='60000000', logradouro='Rua Teste', numero='100', bairro='Centro',
            cidade='Fortaleza', estado='CE', proprietario_nome='João Silva',
            quartos=0, suites=0, banheiros=1, vagas=0, mobilia='sem',
            valor_aluguel='1500.00', valor_condominio='0', valor_iptu='0',
        )
        dados.update(overrides)
        return dados

    def test_criar_imovel_sem_nome_imovel(self):
        imovel = Imovel.objects.create(**self._dados_imovel())
        self.assertEqual(imovel.nome_imovel, '')

    def test_criar_imovel_com_nome_imovel(self):
        imovel = Imovel.objects.create(**self._dados_imovel(nome_imovel='Casa da Praia'))
        self.assertEqual(imovel.nome_imovel, 'Casa da Praia')

    def test_form_valido_sem_nome_imovel(self):
        form = ImovelForm(data=self._dados_imovel())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['nome_imovel'], '')

    def test_form_widget_nome_imovel_e_texto_livre(self):
        form = ImovelForm()
        self.assertIsInstance(form.fields['nome_imovel'].widget, django_forms.TextInput)

    def test_listagem_exibe_nome_imovel_quando_preenchido(self):
        Usuario = get_user_model()
        Usuario.objects.create_user(username='teste', password='senha123')
        Imovel.objects.create(**self._dados_imovel(nome_imovel='Casa da Praia'))

        self.client.login(username='teste', password='senha123')
        resp = self.client.get(reverse('imovel_lista'), HTTP_HOST=self.domain.domain)

        self.assertContains(resp, 'Casa da Praia')

    def test_listagem_nao_quebra_sem_nome_imovel(self):
        Usuario = get_user_model()
        Usuario.objects.create_user(username='teste2', password='senha123')
        Imovel.objects.create(**self._dados_imovel())

        self.client.login(username='teste2', password='senha123')
        resp = self.client.get(reverse('imovel_lista'), HTTP_HOST=self.domain.domain)

        self.assertEqual(resp.status_code, 200)
