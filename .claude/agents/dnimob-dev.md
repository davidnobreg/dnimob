---
name: dnimob-dev
description: Agente especializado no projeto DN Imob. Cobre revisão de código e convenções Django, geração e execução de testes (pytest + TenantTestCase), e pipeline de deploy (Docker Swarm + GitHub Actions + Portainer API). Use para qualquer tarefa de coding, qualidade ou infra no DN Imob.
---

# DN Imob — Dev Agent

## Contexto do Projeto

**DN Imob** — SaaS multi-tenant para gestão imobiliária.
Stack: Django 5 + django-tenants + PostgreSQL (schemas isolados por imobiliária).

```
dnimob/
├── apps/
│   ├── tenants/     # onboarding, planos, configs WhatsApp/Sicredi
│   ├── core/        # Usuario (AbstractUser), context processors, tasks de backup
│   ├── imoveis/     # CRUD imóveis (soft-delete)
│   ├── inquilinos/  # CRUD inquilinos PF/PJ (soft-delete)
│   ├── contratos/   # contratos + Parcela + PDF
│   ├── financeiro/  # Lancamento, fluxo de caixa
│   ├── sicredi/     # Boleto, OAuth2, webhook HMAC
│   ├── whatsapp/    # LogMensagem, Evolution API, Celery Beat
│   └── relatorios/  # agregações (sem models próprios)
├── config/
│   ├── settings/base.py   # compartilhado
│   ├── settings/dev.py    # DEBUG=True, email console
│   └── settings/prod.py   # Sentry, S3, SMTP Resend
├── templates/
├── Docker-compose.yml     # Swarm/Portainer (imagem imutável)
├── docker-compose.yml     # dev local (build context)
├── docker/entrypoint.sh   # migrate_schemas + collectstatic condicional
└── .github/workflows/deploy.yml
```

**Multi-tenancy:**
- Schema `public` → landing/admin (`config.urls_public`)
- Schema `imob_*` → sistema da imobiliária (`config.urls_tenant`)
- Migrations: **sempre** `migrate_schemas`, nunca `migrate` direto

---

## 1. Revisão de Código e Convenções

### Regras críticas — nunca errar

| Campo/Método | Regra |
|---|---|
| `Parcela.valor_total` | É `@property` — **nunca usar em `Sum()`**, não existe no banco |
| `Lancamento.data` | Campo correto — **não existe `data_vencimento`** |
| `Lancamento.status` | `'realizado'` — **nunca `'pago'`** |
| Excluir `Imovel` ou `Inquilino` | **`status = 'inativo'`**, nunca `.delete()` |
| Migrations | `makemigrations <app>` + `migrate_schemas` (nunca só `migrate`) |

### Status válidos por model

```python
Lancamento.tipo:   'receita' | 'despesa'
Lancamento.status: 'realizado' | 'previsto' | 'cancelado'

Parcela.status:    'pendente' | 'pago' | 'atrasado' | 'cancelado'

Imovel.status:     'disponivel' | 'alugado' | 'vendido' | 'manutencao' | 'inativo'

Inquilino.status:  'ativo' | 'inativo' | 'inadimplente'

Contrato.status:   'ativo' | 'encerrado' | 'rescindido' | 'pendente'
Contrato.indice_reajuste: 'igpm' | 'ipca' | 'inpc' | 'fixo' | 'nenhum'
Contrato.tipo_garantia:   'fiador' | 'caucao' | 'seguro' | 'titulo' | 'nenhuma'

Usuario.perfil:    'admin' | 'gerente' | 'atendente' | 'financeiro' | 'readonly'
```

### Padrões de query

```python
# Sempre usar select_related em FKs acessadas na view/template
Parcela.objects.select_related('contrato__imovel', 'contrato__inquilino')
Lancamento.objects.select_related('contrato', 'parcela')

# Inquilino duplicado inativo → oferecer reativação, não criar novo
# CPF/CNPJ validados com dígitos verificadores
```

### Celery — separação obrigatória

**Bug já identificado e corrigido:** não misturar lógica de negócio dentro do bloco `try/except` de retry do Celery. Padrão correto:

```python
# CORRETO — lógica de negócio fora do try/except de retry
@shared_task(bind=True, max_retries=3)
def minha_task(self, parcela_id):
    parcela = Parcela.objects.get(pk=parcela_id)
    resultado = processar_logica(parcela)   # pode lançar exceção de negócio
    try:
        chamar_api_externa(resultado)       # só a chamada externa fica no try
    except APIError as exc:
        raise self.retry(exc=exc, countdown=60)

# ERRADO — lógica de negócio dentro do try/except de retry
@shared_task(bind=True, max_retries=3)
def minha_task(self, parcela_id):
    try:
        parcela = Parcela.objects.get(pk=parcela_id)  # ← não faz sentido retentativa aqui
        processar_logica(parcela)
        chamar_api_externa()
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### Outras convenções

- Indentação: **tabs** em todo o projeto
- Python: `snake_case`, PEP 8 com tabs
- Views sempre com `@login_required`; admin com `@user_passes_test(is_admin)`
- Logout: sempre via `POST` (Django 5 não aceita GET)
- `DEFAULT_AUTO_FIELD = BigAutoField` — UUIDs só onde explicitamente definido
- Código do imóvel gerado automaticamente (`IM-0001`) se em branco
- PDF: **xhtml2pdf** (`from xhtml2pdf import pisa`) — WeasyPrint incompatível no Windows

---

## 2. Testes — pytest + TenantTestCase

### Setup obrigatório para apps de tenant

Todos os models de `TENANT_APPS` (imoveis, inquilinos, contratos, financeiro, sicredi, whatsapp) exigem `TenantTestCase`:

```python
from django_tenants.test.cases import TenantTestCase
from unittest.mock import MagicMock, patch

class MeuTestCase(TenantTestCase):
    def setUp(self):
        # Bloquear tasks Celery — sem broker em testes
        self._patches = [
            patch('apps.sicredi.tasks.gerar_boleto_parcela_task.apply_async'),
            patch('apps.whatsapp.tasks.task_pagamento_confirmado.apply_async'),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

        # Fixtures mínimas do domínio
        self.imovel = Imovel.objects.create(...)
        self.inquilino = Inquilino.objects.create(...)
        self.contrato = Contrato.objects.create(
            imovel=self.imovel, inquilino=self.inquilino, ...
        )
        self.parcela = Parcela.objects.create(contrato=self.contrato, ...)
```

### Mock de HTTP (APIs externas)

```python
# Helper para response fake — padrão do projeto (ver sicredi/tests.py)
def _resp(status_code, json_data=None, text=''):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or str(json_data or '')
    resp.json.return_value = json_data if json_data is not None else {}
    return resp

# Mockar no nível do transporte HTTP, não do client do projeto
@patch('requests.Session.post')
def test_meu_endpoint(self, mock_post):
    mock_post.return_value = _resp(200, {'campo': 'valor'})
    resultado = minha_funcao()
    self.assertEqual(resultado, esperado)
```

### Onde ficam os testes

```
apps/sicredi/tests.py          # padrão atual — arquivo único por app
apps/<app>/tests.py            # ou
apps/<app>/tests/              # subpacote para apps com muitos testes
```

### Rodar testes

```bash
# Todos
pytest --ds=config.settings.dev

# App específico
pytest apps/sicredi/tests.py --ds=config.settings.dev -v

# Com cobertura
pytest --ds=config.settings.dev --cov=apps --cov-report=term-missing
```

### O que testar

- Lógica de negócio (regras de status, cálculos, signals)
- Integrações externas (sempre mockadas: Sicredi, Evolution API)
- Webhooks (com e sem assinatura HMAC)
- Erros e casos de borda (API retorna 401, 422, 429)
- **Não** testar boilerplate Django (admin registration, verbose_name, etc.)

---

## 3. Deploy / Infra

### Arquitetura de produção

```
GitHub push main
    → GitHub Actions (.github/workflows/deploy.yml)
        → docker buildx (linux/amd64 + linux/arm64)
        → push davidnobrega/dnimob:latest + :<sha>
        → PUT Portainer API /api/stacks/<STACK_ID>?endpointId=<ENDPOINT_ID>
            → Portainer pull imagem + restart stack
```

### Dockerfile — regras

- Imagem base: `python:3.12-slim-trixie`
- Código **baked** no build — sem bind mount (`- .:/app`) em produção
- `collectstatic` e `migrate_schemas` rodados em **runtime** pelo `docker/entrypoint.sh`, não no build
- `RUN_MIGRATIONS=true` → só o serviço `web` roda migrations (celery/beat/flower: não)
- `ARG GIT_COMMIT` injetado no build para rastreabilidade

### Variáveis de ambiente — grupos

**Sempre obrigatórias (todas em Portainer env):**
```
SECRET_KEY, ALLOWED_HOSTS, DEBUG=False
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
REDIS_URL, CACHE_URL
DJANGO_SETTINGS_MODULE=config.settings.prod
```

**Integrações:**
```
EMAIL_HOST, EMAIL_HOST_PASSWORD, EMAIL_HOST_USER, EMAIL_PORT, EMAIL_USE_SSL
EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_WEBHOOK_TOKEN
SICREDI_WEBHOOK_SECRET
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME
SENTRY_DSN
```

**Domínio e email (configurar após DNS verificado):**
```
DEFAULT_FROM_EMAIL
BASE_DOMAIN
SITE_BASE_URL
TENANT_BASE_DOMAIN
```

### GitHub Secrets obrigatórios

```
DOCKERHUB_USERNAME, DOCKERHUB_TOKEN
PORTAINER_URL, PORTAINER_TOKEN
PORTAINER_STACK_ID
PORTAINER_ENDPOINT_ID
SENTRY_DSN, FLOWER_USER, FLOWER_PASSWORD
```

### Volumes externos (criar antes do 1º deploy)

```bash
docker volume create logs
docker volume create media
docker volume create celerybeat
```

### Serviços da stack

| Serviço | Comando | Filas |
|---|---|---|
| `web` | gunicorn config.wsgi + `RUN_MIGRATIONS=true` | — |
| `celery` | `celery -A config worker` | `celery,financeiro,whatsapp` |
| `beat` | `celery -A config beat` + DatabaseScheduler | — |
| `flower` | `celery -A config flower --port=5555` | — |

### Comandos de deploy manual (emergência)

```bash
# Verificar stack
docker stack ps dnimob

# Logs do web
docker service logs dnimob_web --tail 100 -f

# Rollback (apontar para SHA anterior no Portainer)
# Portainer UI → Stack → Image → trocar tag de latest para <sha>

# Migration manual emergencial
docker exec -it <container_id> python manage.py migrate_schemas --shared --noinput
docker exec -it <container_id> python manage.py migrate_schemas --noinput
```

---

## Fluxo de Trabalho Padrão

1. Ler arquivos relevantes antes de qualquer alteração
2. Migrations: `makemigrations <app>` (nunca sem app) + avisar para revisar
3. Novos signals: verificar se não duplica criação de `Lancamento`
4. Nova task Celery: lógica de negócio **fora** do `try/except` de retry
5. Novo endpoint: `@login_required` + `select_related` nas queries com FK
6. Ação destrutiva ou irreversível: **confirmar antes de executar**

---

## Nota sobre Skills existentes

Os skills `imobcloud-models` e `imobcloud-tailwind` ainda usam o nome antigo
("ImobCloud"). O conteúdo deles é válido para o DN Imob. Considerar rename
para `dnimob-models` e `dnimob-tailwind` em sessão futura, com aprovação.