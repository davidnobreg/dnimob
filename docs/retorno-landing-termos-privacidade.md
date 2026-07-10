---
date: 2026-07-10
projeto: dnimob
tags: [implementacao, landing-page, lgpd, termos, tdd]
---

# Retorno — Landing Dinâmica + Termos/Privacidade + Aceite Persistido

Implementação completa das 3 partes pedidas, via TDD (RED→GREEN em cada
parte). Nada commitado — tudo em working tree, aguardando revisão.

---

## Status

| Parte | Status |
|---|---|
| 1. Landing dinâmica (Tailwind, iterando `Plano.objects`) | ✅ feito |
| 2. Persistência do aceite (`aceite_termos_em`/`aceite_termos_ip`) | ✅ feito |
| 3. Termos de Uso + Política de Privacidade (rascunho) | ✅ feito |
| Testes `apps.tenants` | ✅ 7/7 OK |
| Commit | ❌ não feito (pendente de revisão) |

---

## Onde o Tailwind CDN carrega

Já estava em `templates/base_public.html:18` (`<script src="https://cdn.tailwindcss.com">`),
herdado por `landing.html` e `cadastro.html` via `{% extends %}`. Não precisou mover nada.

---

## Arquivos tocados

**Modificados:**
- `apps/tenants/models.py`
- `apps/tenants/services.py`
- `apps/tenants/views.py`
- `config/urls_public.py`
- `templates/tenants/cadastro.html`
- `templates/tenants/landing.html`

**Novos:**
- `apps/tenants/migrations/0008_tenant_aceite_termos_em_tenant_aceite_termos_ip.py`
- `apps/tenants/tests.py`
- `templates/tenants/termos.html`
- `templates/tenants/privacidade.html`

---

## Diff completo — arquivos modificados

```diff
diff --git a/apps/tenants/models.py b/apps/tenants/models.py
index 27f2da1..b9a66bd 100644
--- a/apps/tenants/models.py
+++ b/apps/tenants/models.py
@@ -70,6 +70,10 @@ class Tenant(TenantMixin):
     trial_expira = models.DateField(null=True, blank=True)
     assinatura_expira = models.DateField(null=True, blank=True)
 
+    # Aceite de Termos de Uso e Política de Privacidade
+    aceite_termos_em = models.DateTimeField('Aceite dos termos em', null=True, blank=True)
+    aceite_termos_ip = models.GenericIPAddressField('IP do aceite', null=True, blank=True)
+
     # Metadados
     criado_em = models.DateTimeField(auto_now_add=True)
     atualizado_em = models.DateTimeField(auto_now=True)
diff --git a/apps/tenants/services.py b/apps/tenants/services.py
index 8b60942..3c866ff 100644
--- a/apps/tenants/services.py
+++ b/apps/tenants/services.py
@@ -145,7 +145,7 @@ def _sanitizar_subdominio(valor: str) -> str:
 
 
 @transaction.atomic
-def criar_tenant(dados_form: dict) -> Tenant:
+def criar_tenant(dados_form: dict, aceite_termos_em=None, aceite_termos_ip=None) -> Tenant:
     """
     Cria registro do tenant + domain SEM criar schema/migrations.
     O provisionamento real (migrate_schemas + admin + templates) fica para a
@@ -172,6 +172,8 @@ def criar_tenant(dados_form: dict) -> Tenant:
         trial=True,
         trial_expira=date.today() + timedelta(days=14),
         provisionamento_status='pendente',
+        aceite_termos_em=aceite_termos_em,
+        aceite_termos_ip=aceite_termos_ip,
     )
     # auto_create_schema=False no nível de instância — pula o migrate_schemas
     tenant.auto_create_schema = False
diff --git a/apps/tenants/views.py b/apps/tenants/views.py
index 7bcb20e..2817315 100644
--- a/apps/tenants/views.py
+++ b/apps/tenants/views.py
@@ -13,6 +13,7 @@ from django.contrib.auth import get_user_model, login
 from django.contrib.auth.decorators import login_required, user_passes_test
 from django.http import JsonResponse
 from django.shortcuts import get_object_or_404, redirect, render
+from django.utils import timezone
 from django.utils.decorators import method_decorator
 from django.views import View
 from django.views.decorators.http import require_POST
@@ -47,6 +48,14 @@ def is_admin(user):
     return user.is_authenticated and (user.is_staff or user.is_superuser)
 
 
+def obter_ip_cliente(request):
+    """IP real do cliente — atrás de proxy (Cloudflare/NPM), usa o primeiro da X-Forwarded-For."""
+    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
+    if forwarded_for:
+        return forwarded_for.split(',')[0].strip()
+    return request.META.get('REMOTE_ADDR')
+
+
 # ---------------------------------------------------------------------------
 # Landing page — cadastro de nova imobiliária
 # ---------------------------------------------------------------------------
@@ -64,7 +73,11 @@ def cadastro_imobiliaria(request):
         form = CadastroImobiliariaForm(request.POST)
         if form.is_valid():
             try:
-                tenant = criar_tenant(form.cleaned_data)
+                tenant = criar_tenant(
+                    form.cleaned_data,
+                    aceite_termos_em=timezone.now(),
+                    aceite_termos_ip=obter_ip_cliente(request),
+                )
                 from .tasks import provisionar_tenant
                 provisionar_tenant.delay(
                     tenant.pk,
@@ -104,6 +117,16 @@ def cadastro_status(request, schema):
     return JsonResponse({'status': tenant.provisionamento_status})
 
 
+def termos_uso(request):
+    """Termos de Uso — página pública estática."""
+    return render(request, 'tenants/termos.html')
+
+
+def politica_privacidade(request):
+    """Política de Privacidade — página pública estática."""
+    return render(request, 'tenants/privacidade.html')
+
+
 def login_acesso(request):
     """Tela pública: informa o subdomínio e redireciona para o login do tenant."""
     base_domain = getattr(settings, 'BASE_DOMAIN', 'dnsoftware.com.br')
diff --git a/config/urls_public.py b/config/urls_public.py
index 0e240b1..96ef3de 100644
--- a/config/urls_public.py
+++ b/config/urls_public.py
@@ -18,6 +18,8 @@ urlpatterns = [
     path('cadastro/status/<str:schema>/', tv.cadastro_status, name='cadastro_status'),
     path('cadastro/sucesso/<str:schema>/', tv.cadastro_sucesso, name='cadastro_sucesso'),
     path('login/', tv.login_acesso, name='login_publico'),
+    path('termos/', tv.termos_uso, name='termos_uso'),
+    path('privacidade/', tv.politica_privacidade, name='politica_privacidade'),
 
     # Webhook Sicredi — público, sem tenant (identifica o tenant pelo beneficiario)
     path('sicredi/webhook/', sicredi_views.webhook_sicredi, name='sicredi_webhook'),
diff --git a/templates/tenants/cadastro.html b/templates/tenants/cadastro.html
index 6398a1b..f6b5fa2 100644
--- a/templates/tenants/cadastro.html
+++ b/templates/tenants/cadastro.html
@@ -314,7 +314,10 @@
                             </span>
 
                             <span class="text-sm leading-6 text-slate-600">
-                                {{ form.aceite_termos.label }}
+                                Concordo com os
+                                <a href="{% url 'termos_uso' %}" target="_blank" rel="noopener" class="font-semibold text-blue-600 hover:underline">Termos de Uso</a>
+                                e a
+                                <a href="{% url 'politica_privacidade' %}" target="_blank" rel="noopener" class="font-semibold text-blue-600 hover:underline">Política de Privacidade</a>
                             </span>
                         </label>
 
diff --git a/templates/tenants/landing.html b/templates/tenants/landing.html
index ffd61c0..e55559c 100644
--- a/templates/tenants/landing.html
+++ b/templates/tenants/landing.html
@@ -193,75 +193,64 @@
 
         <div class="mt-14 grid grid-cols-1 md:grid-cols-3 gap-8">
 
-            <!-- Básico -->
-            <div class="rounded-3xl bg-white border border-gray-200 p-8 shadow-sm">
-                <h3 class="text-xl font-bold text-gray-900">Básico</h3>
-                <p class="mt-4 text-4xl font-bold text-gray-900">
-                    R$ 0<span class="text-base font-medium text-gray-500">/mês</span>
-                </p>
-
-                <ul class="mt-8 space-y-3 text-gray-600">
-                    <li>✅ 10 imóveis</li>
-                    <li>✅ 10 contratos</li>
-                    <li>✅ Até 2 usuários</li>
-                    <li>❌ WhatsApp automático</li>
-                    <li>✅ Boletos Sicredi</li>
-                    <li>✅ Relatórios e exportação</li>
-                </ul>
-
-                <a href="{% url 'cadastro_imobiliaria' %}"
-                   class="mt-8 block text-center rounded-xl border border-blue-600 px-5 py-3 font-semibold text-blue-600 hover:bg-blue-50">
-                    Começar grátis
-                </a>
-            </div>
-
-            <!-- Profissional -->
-            <div class="rounded-3xl bg-blue-600 p-8 shadow-xl text-white relative">
-                <span class="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-yellow-300 px-4 py-1 text-sm font-semibold text-yellow-900">
-                    Mais indicado
-                </span>
-
-                <h3 class="text-xl font-bold">Profissional</h3>
-                <p class="mt-4 text-4xl font-bold">
-                    R$ 99<span class="text-base font-medium text-blue-100">/mês</span>
-                </p>
-
-                <ul class="mt-8 space-y-3 text-blue-50">
-                    <li>✅ 100 imóveis</li>
-                    <li>✅ Contratos ilimitados</li>
-                    <li>✅ Até 10 usuários</li>
-                    <li>✅ WhatsApp automático</li>
-                    <li>✅ Boletos Sicredi</li>
-                    <li>✅ Dashboard financeiro</li>
-                </ul>
-
-                <a href="{% url 'cadastro_imobiliaria' %}"
-                   class="mt-8 block text-center rounded-xl bg-white px-5 py-3 font-semibold text-blue-700 hover:bg-blue-50">
-                    Testar agora
-                </a>
-            </div>
-
-            <!-- Empresarial -->
-            <div class="rounded-3xl bg-white border border-gray-200 p-8 shadow-sm">
-                <h3 class="text-xl font-bold text-gray-900">Empresarial</h3>
-                <p class="mt-4 text-4xl font-bold text-gray-900">
-                    Sob consulta
-                </p>
-
-                <ul class="mt-8 space-y-3 text-gray-600">
-                    <li>✅ Imóveis ilimitados</li>
-                    <li>✅ Usuários ilimitados</li>
-                    <li>✅ Integrações personalizadas</li>
-                    <li>✅ Suporte prioritário</li>
-                    <li>✅ Ambiente dedicado</li>
-                    <li>✅ Consultoria de implantação</li>
-                </ul>
-
-                <a href="{% url 'cadastro_imobiliaria' %}"
-                   class="mt-8 block text-center rounded-xl border border-gray-300 px-5 py-3 font-semibold text-gray-700 hover:bg-gray-50">
-                    Falar com consultor
-                </a>
-            </div>
+            {% for plano in planos %}
+                {% if plano.nome == 'profissional' %}
+                    <div class="rounded-3xl bg-blue-600 p-8 shadow-xl text-white relative">
+                        <span class="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-yellow-300 px-4 py-1 text-sm font-semibold text-yellow-900">
+                            Mais indicado
+                        </span>
+
+                        <h3 class="text-xl font-bold">{{ plano.get_nome_display }}</h3>
+                        <p class="mt-4 text-4xl font-bold">
+                            R$ {{ plano.preco_mensal|floatformat:0 }}<span class="text-base font-medium text-blue-100">/mês</span>
+                        </p>
+
+                        <ul class="mt-8 space-y-3 text-blue-50">
+                            <li>✅ {% if plano.limite_imoveis %}{{ plano.limite_imoveis }} imóveis{% else %}Imóveis ilimitados{% endif %}</li>
+                            <li>✅ {% if plano.limite_contratos %}{{ plano.limite_contratos }} contratos{% else %}Contratos ilimitados{% endif %}</li>
+                            <li>✅ {% if plano.limite_usuarios %}Até {{ plano.limite_usuarios }} usuários{% else %}Usuários ilimitados{% endif %}</li>
+                            <li>{% if plano.tem_whatsapp %}✅{% else %}❌{% endif %} WhatsApp automático</li>
+                            <li>{% if plano.tem_sicredi %}✅{% else %}❌{% endif %} Boletos Sicredi</li>
+                            <li>✅ Dashboard financeiro</li>
+                        </ul>
+
+                        <a href="{% url 'cadastro_imobiliaria' %}"
+                           class="mt-8 block text-center rounded-xl bg-white px-5 py-3 font-semibold text-blue-700 hover:bg-blue-50">
+                            Testar agora
+                        </a>
+                    </div>
+                {% else %}
+                    <div class="rounded-3xl bg-white border border-gray-200 p-8 shadow-sm">
+                        <h3 class="text-xl font-bold text-gray-900">{{ plano.get_nome_display }}</h3>
+                        <p class="mt-4 text-4xl font-bold text-gray-900">
+                            {% if plano.preco_mensal %}
+                                R$ {{ plano.preco_mensal|floatformat:0 }}<span class="text-base font-medium text-gray-500">/mês</span>
+                            {% else %}
+                                Sob consulta
+                            {% endif %}
+                        </p>
+
+                        <ul class="mt-8 space-y-3 text-gray-600">
+                            <li>✅ {% if plano.limite_imoveis %}{{ plano.limite_imoveis }} imóveis{% else %}Imóveis ilimitados{% endif %}</li>
+                            <li>✅ {% if plano.limite_contratos %}{{ plano.limite_contratos }} contratos{% else %}Contratos ilimitados{% endif %}</li>
+                            <li>✅ {% if plano.limite_usuarios %}Até {{ plano.limite_usuarios }} usuários{% else %}Usuários ilimitados{% endif %}</li>
+                            <li>{% if plano.tem_whatsapp %}✅{% else %}❌{% endif %} WhatsApp automático</li>
+                            <li>{% if plano.tem_sicredi %}✅{% else %}❌{% endif %} Boletos Sicredi</li>
+                            <li>✅ Relatórios e exportação</li>
+                        </ul>
+
+                        <a href="{% url 'cadastro_imobiliaria' %}"
+                           class="mt-8 block text-center rounded-xl border border-blue-600 px-5 py-3 font-semibold text-blue-600 hover:bg-blue-50">
+                            Começar grátis
+                        </a>
+                    </div>
+                {% endif %}
+            {% empty %}
+                <div class="md:col-span-3 rounded-3xl bg-white border border-gray-200 p-8 text-center text-gray-500">
+                    Planos em breve.
+                    <a href="mailto:contato@dnsoftware.com.br" class="text-blue-600 font-semibold hover:underline">Fale com a gente</a>.
+                </div>
+            {% endfor %}
 
         </div>
     </div>
```

---

## Migration nova (arquivo completo)

`apps/tenants/migrations/0008_tenant_aceite_termos_em_tenant_aceite_termos_ip.py`

```python
# Generated by Django 5.0.14 on 2026-07-10 21:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0007_plano_tem_sicredi_tenant_cpf_tenant_tipo_pessoa"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="aceite_termos_em",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Aceite dos termos em"
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="aceite_termos_ip",
            field=models.GenericIPAddressField(
                blank=True, null=True, verbose_name="IP do aceite"
            ),
        ),
    ]
```

**Ainda não aplicada em nenhum banco real** (`migrate_schemas` não foi rodado) —
só validada indiretamente pelos testes (test DB aplica todas as migrations do
zero; se essa desse erro, os testes teriam falhado).

---

## Testes escritos (`apps/tenants/tests.py`, arquivo novo)

TDD em cada parte — RED confirmado (motivo certo de falha) antes de cada GREEN.

- `LandingPlanosDinamicosTests` (3 testes)
  - renderiza planos vindos do banco (nome, preço, "ilimitado")
  - queryset vazia não quebra a página (fallback visual)
  - plano inativo não aparece
- `AceiteTermosPersistenciaTests` (2 testes)
  - `aceite_termos_em`/`aceite_termos_ip` persistidos a partir do `REMOTE_ADDR`
  - fallback correto pro primeiro IP de `X-Forwarded-For` (atrás de proxy)
- `TermosPrivacidadeRotasTests` (2 testes)
  - `/termos/` resolve pra view certa e retorna 200
  - `/privacidade/` resolve pra view certa e retorna 200

**Nota técnica:** `apps.tenants` é `SHARED_APPS` (schema `public`), então os
testes usam `django.test.TestCase` comum (não `TenantTestCase`) e
`@override_settings(ROOT_URLCONF='config.urls_public')`, já que o
`ROOT_URLCONF` padrão do projeto é `config.urls_tenant`. Views de cadastro/
landing/termos são chamadas diretamente via `RequestFactory` (bypass do
`TenantMainMiddleware`, que exige um `Domain` cadastrado pro host de teste —
infra que não existe hoje pro schema `public` nos testes).

### Resultado

```
python manage.py test apps.tenants --settings=config.settings.dev

Found 7 test(s).
System check identified no issues (0 silenced).
.......
----------------------------------------------------------------------
Ran 7 tests in 0.219s

OK
```

---

## Placeholders `[PREENCHER: ...]` pra revisar

7 no total, nenhum dado inventado:

| Arquivo:linha | O que falta |
|---|---|
| `termos.html:12` | Data de publicação |
| `termos.html:20` | Razão social da DN Software |
| `termos.html:21` | CNPJ |
| `termos.html:21` | Endereço completo |
| `termos.html:95` | Comarca/foro |
| `privacidade.html:12` | Data de publicação |
| `privacidade.html:75` | E-mail do encarregado/DPO |

Ambos os templates têm o comentário HTML `<!-- RASCUNHO — não publicar sem
revisão jurídica profissional -->` no topo do bloco de conteúdo (não visível
ao usuário final).

### Cobertura de conteúdo

**Termos de Uso** (`templates/tenants/termos.html`): identificação, objeto do
serviço, planos e cobrança (reflete a realidade atual: trial 14 dias, sem
cobrança automática), cláusula CRECI (responsabilidade regulatória é da
imobiliária cliente, não da DN Software), disclaimer de dados de terceiros
inseridos pela imobiliária, rescisão/cancelamento, foro.

**Política de Privacidade** (`templates/tenants/privacidade.html`): dados
coletados (cliente + dados de terceiros inseridos pela imobiliária), finalidade,
direitos do art. 18 LGPD (lista completa), canal de contato/DPO, retenção,
compartilhamento com terceiros — **Sicredi, Evolution API (WhatsApp), Resend,
Backblaze B2**, listados como fato (integrações reais do sistema), não invenção.

---

## O que NÃO foi mexido (fora de escopo, como pedido)

- `Plano` model — só leitura/uso, campos intactos.
- Fluxo de `provisionar_tenant` (Celery), criação de schema, migrate_schemas real.
- Queryset de plano em `CadastroImobiliariaForm` (já funcionava).
- Sem backfill nos tenants existentes — `aceite_termos_em`/`aceite_termos_ip`
  ficam `null` pra quem já se cadastrou.
- Sem commit.
