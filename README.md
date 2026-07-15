# DN Imob — Sistema de Gestão Imobiliária Multi-Tenant

SaaS multi-tenant para imobiliárias. Cada imobiliária (tenant) tem dados
isolados por schema PostgreSQL, compartilhando uma única instância Django.

Stack: Django 5.0.14 · django-tenants 3.6.1 · PostgreSQL 16 · Tailwind CSS (CDN) · Alpine.js · Celery 5.4 + Redis · django-celery-beat · xhtml2pdf · Evolution API (WhatsApp) · Sicredi API (boletos) · openpyxl

---

## Arquitetura multi-tenant

- Schema `public` → landing page, cadastro, superadmin (`config.urls_public`)
- Schema `imob_*` → sistema da imobiliária (`config.urls_tenant`)

**SHARED_APPS:** `apps.tenants`, `apps.billing`, `apps.core` + apps built-in do Django
**TENANT_APPS:** `apps.core`, `apps.imoveis`, `apps.inquilinos`, `apps.contratos`, `apps.financeiro`, `apps.sicredi`, `apps.whatsapp`, `apps.relatorios`

| App | Responsabilidade |
|---|---|
| `tenants` | Onboarding, superadmin, configurações, planos, WhatsApp/Sicredi config |
| `billing` | Assinatura interna via Asaas (DN Software cobra a imobiliária pelo plano) |
| `core` | `Usuario` (AbstractUser + perfil), context processors, task de backup |
| `imoveis` | CRUD imóveis + fotos. Excluir = inativo (nunca deletar) |
| `inquilinos` | CRUD inquilinos PF/PJ. Excluir = inativo. Reativação por CPF/CNPJ |
| `contratos` | Contratos + parcelas, encerramento, rescisão, PDF |
| `financeiro` | Lançamentos (receita/despesa), fluxo de caixa, inadimplência |
| `sicredi` | Boletos (1-para-1 com Parcela), OAuth2, webhook |
| `whatsapp` | Log de mensagens, envio via Evolution API, Celery Beat agendado |
| `relatorios` | Só agregação — sem models próprios |

---

## Arquitetura de serviços (produção)

Stack Docker Swarm / Portainer, imagem imutável (`davidnobrega/dnimob:latest`) baked no build via GitHub Actions:

| Serviço | O que é |
|---|---|
| `web` | Django + Gunicorn |
| `celery` | Celery Worker (filas `celery`, `financeiro`, `whatsapp`) |
| `beat` | Celery Beat (agendador, `DatabaseScheduler`) |
| `flower` | Monitor de tasks Celery |
| `backup` | Serviço dedicado (`davidnobrega/dnimob-backup:latest`) — dump do PostgreSQL para Backblaze B2 |

PostgreSQL, Redis, Evolution API e proxy reverso rodam em stacks externas separadas, comunicando-se via rede Docker `app_network`.

---

## Pré-requisitos (dev local)

- Python 3.12+
- PostgreSQL 16 acessível (externo, ex: `172.16.51.3`)
- Redis (para Celery)

---

## Início rápido — desenvolvimento local

```bash
# 1. Ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements/dev.txt

# 2. Variáveis de ambiente
copy configuration\.envDnimob.example configuration\.envDnimob
# Editar configuration/.envDnimob com credenciais reais

# 3. Migrations
python manage.py migrate_schemas --settings=config.settings.dev

# 4. Rodar
python manage.py runserver --settings=config.settings.dev
```

- Landing page (schema `public`): `127.0.0.1:8000`
- Tenant de desenvolvimento (`imob_alpha`): `localhost:8000`

### Celery (dev)

```bash
celery -A config worker -l info --settings=config.settings.dev
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler --settings=config.settings.dev
```

---

## Variáveis de ambiente

Arquivo: `configuration/.envDnimob` (local) — ver `configuration/.envDnimob.example` para o template completo.

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta Django |
| `DEBUG` | `True` em dev, `False` em prod |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Credenciais PostgreSQL |
| `REDIS_URL` | URL Redis para Celery |
| `EMAIL_*` | SMTP relay via Resend (prod) ou console backend (dev) |
| `EVOLUTION_API_URL` | URL base da instância Evolution API (WhatsApp) |
| `EVOLUTION_API_KEY` | Chave de autenticação da Evolution API |
| `EVOLUTION_WEBHOOK_TOKEN` | Token do webhook Evolution |
| `SICREDI_API_URL` / `SICREDI_TOKEN_URL` / `SICREDI_WEBHOOK_SECRET` | Integração de boletos Sicredi |
| `ASAAS_API_URL` / `ASAAS_API_KEY` / `ASAAS_WEBHOOK_TOKEN` | Assinatura interna (billing DN Software → imobiliária) |
| `SENTRY_DSN` / `SENTRY_ENVIRONMENT` / `SENTRY_TRACES_RATE` | Monitoramento de erros (prod) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_STORAGE_BUCKET_NAME` / `AWS_S3_REGION_NAME` / `AWS_S3_CUSTOM_DOMAIN` | Storage S3-compatível (prod) |
| `AWS_BACKUP_BUCKET` / `BACKUP_PREFIX` | Bucket e prefixo do backup PostgreSQL |
| `PG_DUMP_PATH` | Caminho do binário `pg_dump` usado pelo serviço de backup |
| `BASE_DOMAIN` | Domínio base dos subdomínios de tenant |
| `SITE_BASE_URL` | URL pública do site |

---

## Geração de PDF

Usa **xhtml2pdf** (WeasyPrint é incompatível com Windows e não é usado no projeto).

---

## Estrutura do projeto

```
dnimob/
├── config/
│   ├── settings/base.py     # configurações multi-tenant
│   ├── settings/dev.py
│   ├── settings/prod.py
│   ├── celery.py
│   ├── urls.py
│   ├── urls_public.py       # schema public — landing, cadastro, superadmin
│   └── urls_tenant.py       # schema tenant — sistema da imobiliária
├── apps/
│   ├── tenants/              # Tenant, Domain, Plano, onboarding, superadmin
│   ├── billing/               # assinatura interna (Asaas)
│   ├── core/                  # Usuario, dashboard, backup
│   ├── imoveis/                # CRUD imóveis
│   ├── inquilinos/              # CRUD inquilinos
│   ├── contratos/                # contratos, parcelas, PDF
│   ├── financeiro/                # lançamentos, fluxo de caixa
│   ├── sicredi/                    # boletos, OAuth2, webhook
│   ├── whatsapp/                    # Evolution API, LogMensagem
│   └── relatorios/                   # agregação de relatórios
├── templates/
├── static/
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── docker-compose.yml        # web, celery, beat, flower, backup
├── Dockerfile
└── manage.py
```

---

## Testes

```bash
python manage.py test apps.<app> --settings=config.settings.dev --verbosity=2
```

Suíte com pytest cobrindo lógica de negócio, APIs e regras críticas (parcelas, boletos, webhooks).

---

## Fases — status atual

| Fase | Status | Descrição |
|---|---|---|
| 1 | ✅ | Setup, Docker, Django, Tailwind, multi-tenant |
| 2 | ✅ | Onboarding, superadmin, configurações, planos |
| 3 | ✅ | Imóveis e Inquilinos — CRUD completo |
| 4 | ✅ | Contratos, parcelas, PDF (xhtml2pdf) |
| 5 | ✅ | Financeiro + Sicredi |
| 6 | ✅ | WhatsApp via Evolution API + Celery Beat |
| 7 | ✅ | Dashboard analítico + relatórios PDF/Excel |
| 8 | ⏳ | Produção: SSL wildcard, Sentry, backup, SMTP |
| 9 | 🔄 | Testes automatizados (pytest) |
