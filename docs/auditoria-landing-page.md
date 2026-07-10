---
date: 2026-07-10
projeto: dnimob
tags: [auditoria, landing-page, lgpd, termos]
---

# Auditoria — Landing Page Pública (DN Imob)

Inventário do estado atual, sem alterações. Só leitura.

---

## 1. Estrutura de arquivos

Landing não tem app próprio (`apps/landing/` não existe). É servida pelo app `tenants` (schema `public`).

```
config/urls_public.py          → rotas públicas (landing, cadastro, login, superadmin)
apps/tenants/
├── views.py                   → landing(), cadastro_imobiliaria(), etc.
├── forms.py                   → CadastroImobiliariaForm (campo aceite_termos)
├── models.py                  → Plano, Tenant, Domain, ConfigSicredi, InstanciaWhatsApp, TemplateWhatsApp
└── services.py                → criar_tenant()

templates/
├── base_public.html           → base das páginas públicas
└── tenants/
    ├── landing.html           → home pública (hero, recursos, planos, CTA)
    ├── cadastro.html          → form de cadastro (com checkbox aceite_termos)
    ├── aguardando.html        → tela de espera do provisionamento
    ├── cadastro_sucesso.html
    └── login_public.html
```

Não existe `termos.html`, `privacidade.html` ou qualquer template de conteúdo jurídico no projeto inteiro (busca por `termo|privacidade|LGPD|CRECI|encarregado|DPO` retornou só código, nenhum documento).

---

## 2. Planos e preços — resposta direta

**Os dois convivem, e não se falam: existe model dinâmico (`Plano`) no banco, mas o template da landing ignora ele e usa preços hardcoded.**

### Model existe e está em uso — mas não na landing

`apps/tenants/models.py:12`
```python
class Plano(models.Model):
    BASICO = 'basico'
    PROFISSIONAL = 'profissional'
    ENTERPRISE = 'enterprise'

    PLANO_CHOICES = [
        (BASICO, 'Básico'),
        (PROFISSIONAL, 'Profissional'),
        (ENTERPRISE, 'Enterprise'),
    ]

    nome = models.CharField(max_length=50, choices=PLANO_CHOICES, unique=True)
    limite_imoveis = models.IntegerField(null=True, blank=True)
    limite_contratos = models.IntegerField(null=True, blank=True)
    limite_usuarios = models.IntegerField(null=True, blank=True)
    tem_whatsapp = models.BooleanField(default=False)
    tem_sicredi = models.BooleanField(default=False)
    preco_mensal = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)
```

Registrado no admin (`apps/tenants/admin.py:14`, `PlanoAdmin`) — **já dá pra cadastrar/editar planos hoje, não seria novo**.

Usado de verdade em 4 lugares:
- `forms.py:62` e `:169` — `CadastroImobiliariaForm` e `SuperAdminCriarTenantForm` usam `Plano.objects.filter(ativo=True)` como queryset do campo de escolha de plano no cadastro real.
- `views.py:149` — painel superadmin (`superadmin_tenant_detalhe`) lista planos pra trocar o plano de um tenant.
- **`views.py:57`** — a própria `landing()`:
  ```python
  def landing(request):
      """Página pública de captação."""
      from .models import Plano
      planos = Plano.objects.filter(ativo=True).order_by('preco_mensal')
      return render(request, 'tenants/landing.html', {'planos': planos})
  ```

### Template ignora o contexto — 100% hardcoded

`templates/tenants/landing.html:182-268` (seção `id="planos"`) nunca referencia `{{ planos }}` — três `<div>` fixos, valores escritos direto no HTML:

```html
<!-- Básico -->
<h3>Básico</h3>
<p>R$ 0<span>/mês</span></p>

<!-- Profissional -->
<h3>Profissional</h3>
<p>R$ 99<span>/mês</span></p>

<!-- Empresarial -->
<h3>Empresarial</h3>
<p>Sob consulta</p>
```

**Nota:** os valores hardcoded (R$0 / R$99 / sob consulta) **não batem** com os valores citados no pedido de auditoria (R$97 / R$197 / R$397) — nem entre si, nem com o que quer que esteja hoje cadastrado em `Plano.objects` no banco (não consultei o banco, só o código — os preços reais cadastrados podem ser outros ainda).

**Resumo:** infraestrutura pra planos dinâmicos já existe e já é usada no fluxo de cadastro real — só a landing pública não foi conectada a ela. Isso é código morto de contexto (a queryset `planos` é montada e passada pra template mas nunca usada) + inconsistência de preço (hardcoded desalinhado do que está cadastrado).

---

## 3. Termos de Uso

**Não existe.** Nenhum arquivo/template de Termos de Uso no projeto.

O que existe é só um checkbox de aceite no formulário de cadastro, sem link pra nenhum documento:

`apps/tenants/forms.py:93`
```python
aceite_termos = forms.BooleanField(
    label='Concordo com os Termos de Uso e Política de Privacidade',
    error_messages={'required': 'Você precisa aceitar os termos para continuar.'},
    widget=forms.CheckboxInput(attrs={
        'class': 'h-4 w-4 rounded border-slate-300 accent-blue-600 cursor-pointer',
    }),
)
```

`templates/tenants/cadastro.html:309-325` renderiza o label do checkbox (`{{ form.aceite_termos.label }}`) mas **não há `<a href>` nenhum apontando pra um documento de Termos ou Política de Privacidade** — busquei todos os `href=` do template, só existem 3: link pra landing, link pro login público e um `mailto:contato@dnsoftware.com.br`.

- Sem menção a CRECI em lugar nenhum do código (templates ou views).
- Sem disclaimer de onboarding além do checkbox genérico "Concordo com os Termos de Uso e Política de Privacidade" — texto que descreve documentos que não existem.
- O aceite (`aceite_termos`) é só validado no form — **não é persistido em lugar nenhum** (não existe campo correspondente em `Tenant` no `models.py`, nem log de aceite com timestamp/IP).
- `git log` do arquivo mais próximo (`cadastro.html`): última modificação **2026-06-18**. `landing.html`: **2026-06-17**.

---

## 4. LGPD

**Nada encontrado.** Busca por `LGPD`, `titular`, `encarregado`, `DPO` no projeto inteiro: zero resultado fora deste relatório.

- Não existe Política de Privacidade (nem separada, nem embutida nos "Termos" — porque nenhum dos dois existe como documento).
- Nenhuma menção a direitos do titular (art. 18: acesso, correção, eliminação, portabilidade).
- Nenhum canal de contato de encarregado/DPO — o único contato público é `contato@dnsoftware.com.br` (genérico, achado em `cadastro.html:432`, não é rotulado como canal de privacidade).
- Nenhum formulário ou fluxo (nem manual/e-mail documentado) de solicitação de dados.

---

## 5. Fluxo de onboarding atual

1. Usuário acessa `/` (`landing()`, `views.py:54`) → vê hero + recursos + planos (hardcoded) + CTA.
2. Clica em "Começar grátis" → `/cadastro/` (`cadastro_imobiliaria()`, `views.py:61`).
3. Preenche `CadastroImobiliariaForm` — inclui escolha real de `Plano` (dropdown vindo do banco, diferente da landing) e checkbox `aceite_termos`.
4. Submit válido → `criar_tenant()` (`services.py:148`):
   - Cria `Tenant` com `trial=True`, `trial_expira = hoje + 14 dias`, `provisionamento_status='pendente'`.
   - **Sem cobrança nenhuma neste ponto** — nenhum campo de cartão/pagamento no form, nenhuma chamada a gateway.
   - Cria `Domain` (subdomínio).
   - `tenant.auto_create_schema = False` — schema real não é criado aqui.
5. Dispara task Celery `provisionar_tenant.delay(...)` (assíncrona) → redireciona pra `/cadastro/aguardando/<schema>/`.
6. `cadastro_aguardando()` renderiza tela de espera; JS faz polling em `/cadastro/status/<schema>/` (`cadastro_status()`, retorna JSON com `provisionamento_status`).
7. Quando pronto → `/cadastro/sucesso/<schema>/` (`cadastro_sucesso()`).

**Asaas:** busca por `asaas` no projeto inteiro (código-fonte) → **zero resultados**. Confirmado — nenhuma integração de cobrança de assinatura existe ainda, nem estrutura preparada pra ela. Fluxo é 100% trial manual, sem qualquer coleta de pagamento no cadastro.

---

## 6. Código morto / inconsistências notadas de passagem

- **`landing()` passa `planos` pro contexto e o template nunca usa** (item 2) — trabalho de query jogado fora a cada request na home pública.
- **Preços da landing hardcoded não batem com nenhuma outra fonte** conhecida (nem com os valores citados na tarefa, nem entre os 3 planos exibidos vs. os 3 `PLANO_CHOICES` do model — mapeiam por posição/nome, mas o valor em R$ é digitado à mão em HTML, dessincronizável a qualquer edição no admin).
- **Checkbox de aceite de termos referencia documentos inexistentes** e não persiste o aceite — risco caso vire exigência de auditoria/compliance depois.
- `ConfigSicredi.client_id`/`client_secret` comentados como "credenciais legadas ... mantidas, sem uso novo" (`models.py:141`) — não investigado a fundo, só notado de passagem, fora do escopo desta auditoria.
