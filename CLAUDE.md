# CLAUDE.md — DNImob

Guia para o Claude Code trabalhar neste repositório.

---

## Projeto

**DNImob** — SaaS multi-tenant para gestão imobiliária.
Imobiliárias (tenants) compartilham uma instância Django com dados isolados por schema PostgreSQL.

**Stack:**
- Backend: Django 5.0.14 + django-tenants 3.6.1
- Banco: PostgreSQL 16 (externo, `172.16.51.3`)
- Frontend: Tailwind CSS 3 (CDN) + Alpine.js
- Filas: Celery + Redis + django-celery-beat
- PDF: xhtml2pdf (WeasyPrint incompatível no Windows)
- WhatsApp: Evolution API v2.3.7 (self-hosted)
- Boletos: Sicredi API (OAuth2 + webhook HMAC)
- Excel: openpyxl

---

## Comandos

```bash
# Desenvolvimento
python manage.py runserver --settings=config.settings.dev
python manage.py migrate_schemas --settings=config.settings.dev
python manage.py tenant_command shell --schema=imob_alpha

# Celery
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Migrations (sempre assim — nunca migrate comum)
python manage.py makemigrations <app>
python manage.py migrate_schemas
```

**Settings:**
- Dev: `config.settings.dev` — DEBUG=True, email no console, debug toolbar
- Prod: `config.settings.prod` — gunicorn, Sentry, SMTP real

---

## Multi-Tenancy

- Schema `public` → landing page, cadastro, superadmin (`config.urls_public`)
- Schema `imob_*` → sistema da imobiliária (`config.urls_tenant`)
- Tenant de desenvolvimento: `imob_alpha` (`localhost:8000`)
- Landing page: `127.0.0.1:8000`

**SHARED_APPS:** `django_tenants`, `tenants`, `core` + Django built-ins
**TENANT_APPS:** `imoveis`, `inquilinos`, `contratos`, `financeiro`, `sicredi`, `whatsapp`, `relatorios`

---

## Apps e Responsabilidades

| App | Responsabilidade |
|---|---|
| `tenants` | Onboarding, superadmin, configurações, planos, WhatsApp config, Sicredi config |
| `core` | `Usuario` (AbstractUser + perfil + telefone + foto), context processors |
| `imoveis` | CRUD imóveis + fotos. Excluir = inativo (nunca deletar) |
| `inquilinos` | CRUD inquilinos PF/PJ. Excluir = inativo. Reativação por CPF/CNPJ |
| `contratos` | Contratos + `Parcela` (gerar_parcelas), encerramento, rescisão, PDF |
| `financeiro` | `Lancamento` (receita/despesa), fluxo de caixa, inadimplência |
| `sicredi` | `Boleto` 1-to-1 com Parcela, OAuth2, webhook |
| `whatsapp` | `LogMensagem`, envio Evolution API, Celery Beat agendado |
| `relatorios` | Só agregação — sem models próprios |

---

## Modelos Críticos

```
Imovel ──► Contrato ──► Parcela ──► Boleto (sicredi, opcional)
Inquilino ──┘                   └──► Lancamento (signal ao pagar)
TemplateWhatsApp (13 eventos) → LogMensagem
InstanciaWhatsApp (por tenant) → Evolution API
```

**Campos importantes — não errar:**

`Lancamento`:
- `tipo`: `'receita'` | `'despesa'`
- `status`: `'realizado'` | `'previsto'` | `'cancelado'`
- `data`: DateField (não `data_vencimento`)

`Parcela`:
- `status`: `'pendente'` | `'pago'` | `'atrasado'` | `'cancelado'`
- `valor_total` é `@property` — não existe no banco, não usar em `Sum()`

`Imovel`:
- `status`: `'disponivel'` | `'alugado'` | `'vendido'` | `'manutencao'` | `'inativo'`
- Código gerado automaticamente (`IM-0001`) se não informado

`Inquilino`:
- `status`: `'ativo'` | `'inativo'` | `'inadimplente'`
- CPF e CNPJ validados com dígitos verificadores

`Contrato`:
- `status`: `'ativo'` | `'encerrado'` | `'rescindido'` | `'pendente'`
- `indice_reajuste`: `'igpm'` | `'ipca'` | `'inpc'` | `'fixo'` | `'nenhum'`
- `tipo_garantia`: `'fiador'` | `'caucao'` | `'seguro'` | `'titulo'` | `'nenhuma'`

`Usuario`:
- `perfil`: `'admin'` | `'gerente'` | `'atendente'` | `'financeiro'` | `'readonly'`
- `telefone`, `foto` campos extras além do AbstractUser

---

## Regras de negócio

- **Imóvel excluído** → status `inativo`, nunca `delete()`
- **Inquilino excluído** → status `inativo`, nunca `delete()`
- **CPF/CNPJ duplicado inativo** → oferecer reativação em vez de novo cadastro
- **Parcela paga** → signal cria `Lancamento` automaticamente
- **Código do imóvel** → gerado automaticamente se em branco (`IM-0001`, `IM-0002`...)
- **Logout** → sempre via `POST` (Django 5 não aceita GET)

---

## Templates e Frontend

**Padrão visual:** Tailwind CSS via CDN + Alpine.js
**Base:** `templates/base.html` (sidebar inclusa, topbar com menu do usuário)
**Sidebar:** `templates/components/sidebar.html`

**Convenções de componentes:**
```html
{# Card padrão #}
<div class="bg-white rounded-xl border border-gray-200 p-5">

{# Badge de status #}
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">

{# Botão primário #}
<button class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition-colors">

{# Tabela padrão #}
<div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
  <table class="min-w-full divide-y divide-gray-200 text-sm">
    <thead class="bg-gray-50">...
```

**Nunca usar** classes CSS customizadas (`card`, `btn-primary`, `page-header`, `badge`) — o projeto usa Tailwind puro.

---

## PDF

Usar **xhtml2pdf** (não WeasyPrint — incompatível no Windows).

```python
from xhtml2pdf import pisa
import io
from django.template.loader import render_to_string

def gerar_pdf(template, context):
    html = render_to_string(template, context)
    buffer = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buffer)
    buffer.seek(0)
    return buffer
```

Templates PDF: HTML simples com `@page { size: A4; margin: 2cm; }`, sem `@bottom-center` ou `counter()`.

---

## WhatsApp (Evolution API)

- URL e token salvos em `InstanciaWhatsApp.evolution_url` e `InstanciaWhatsApp.token_api`
- `integration`: sempre `'WHATSAPP-BAILEYS'` no payload de criação
- Instância de dev: `imob2` (conectada)
- Logs em `LogMensagem` (app `whatsapp`)
- Envio via `apps.whatsapp.services.enviar_mensagem()`

---

## Celery Beat — Agendamentos WhatsApp

```python
CELERY_BEAT_SCHEDULE = {
    'whatsapp-lembretes-diarios': {
        'task': 'whatsapp.verificar_lembretes',
        'schedule': crontab(hour=8, minute=0),  # parcelas vencendo em 3 dias
    },
    'whatsapp-vencidas-diarios': {
        'task': 'whatsapp.verificar_vencidas',
        'schedule': crontab(hour=9, minute=0),  # parcelas vencidas há 1/3/7 dias
    },
}
```

---

## Fases — Status atual

| Fase | Status | Descrição |
|---|---|---|
| 1 | ✅ | Setup, Docker, Django, Tailwind, multi-tenant |
| 2 | ✅ | Onboarding, superadmin, configurações, planos |
| 3 | ✅ | Imóveis e Inquilinos — CRUD completo |
| 4 | ✅ | Contratos, parcelas, PDF (xhtml2pdf) |
| 5 | ✅ | Financeiro + Sicredi (estrutura) |
| 6 | ✅ | WhatsApp via Evolution API + Celery Beat |
| 7 | ✅ | Dashboard analítico + 4 relatórios PDF/Excel |
| 8 | ⏳ | Produção: SSL wildcard, Sentry, backup, SMTP |
| 9 | 🔄 | Testes automatizados (pytest, ~75 testes) |

---

## Idioma e Estilo

- Todo código e comentário em **português brasileiro**
- Models: `verbose_name` sempre em PT-BR
- Mensagens de sucesso/erro via `messages.success()` / `messages.error()`
- Views sempre com `@login_required`
- Admin views com `@user_passes_test(is_admin)`
