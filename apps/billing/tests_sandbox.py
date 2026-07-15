"""
apps/billing/tests_sandbox.py
Testes de integração REAL contra o sandbox do Asaas.

NÃO rodar no CI nem em `manage.py test apps.billing` normal — Django
descobre qualquer test*.py automaticamente, e ter ASAAS_API_KEY setada no
.env (uso normal de dev) não deve ser suficiente pra disparar chamada real
sem querer. Exige opt-in explícito via variável de ambiente.

Uso: RUN_ASAAS_SANDBOX_TESTS=1 python manage.py test apps.billing.tests_sandbox --verbosity=2
"""
import os
import time
from unittest import skipUnless

from django.conf import settings
from django.test import TestCase

from .client import AsaasClient

SANDBOX_DISPONIVEL = (
	bool(getattr(settings, 'ASAAS_API_KEY', ''))
	and os.environ.get('RUN_ASAAS_SANDBOX_TESTS') == '1'
)


@skipUnless(SANDBOX_DISPONIVEL, 'ASAAS_API_KEY não configurada ou RUN_ASAAS_SANDBOX_TESTS != 1')
class AsaasSandboxTest(TestCase):

	def test_criar_customer_e_subscription_reais(self):
		client = AsaasClient()

		customer = client.criar_customer(
			'Imob Teste Sandbox',
			'24971563000121',
			email=f'sandbox_{int(time.time())}@teste.com',
			external_reference='teste-sandbox',
		)
		self.assertTrue(customer['id'].startswith('cus_'))
		print(f'Customer criado no sandbox: {customer["id"]}')

		from datetime import date, timedelta

		subscription = client.criar_subscription(
			customer['id'], 97, date.today() + timedelta(days=1), descricao='Teste sandbox DNImob',
		)
		self.assertTrue(subscription['id'].startswith('sub_'))
		print(f'Subscription criada no sandbox: {subscription["id"]}')
