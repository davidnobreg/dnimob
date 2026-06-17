# ImobCloud — Sistema de Gestão Imobiliária Multi-Tenant

Stack: Django 5 · django-tenants · PostgreSQL 16 · Tailwind CSS · Alpine.js · Celery · Redis · Evolution API · Sicredi

---

## Arquitetura de serviços

Este projeto contém apenas **4 serviços** no seu próprio `docker-compose.yml`:

| Serviço | O que é |
|---|---|
| `web` | Django + Gunicorn |
| `celery` | Celery Worker (4 concorrentes) |
| `celery-beat` | Agendador de tasks |
| `flower` | Monitor de tasks (Celery) |

Os serviços abaixo estão em **stacks externas separadas** e se comunicam via rede Docker `imob_network`:

| Serviço | Stack externa |
|---|---|
| PostgreSQL 16 | stack do banco |
| Redis 7 | stack do redis |
| Evolution API | stack do evolution |
| Nginx | stack do nginx |

---

## Pré-requisitos

- Docker + Docker Compose
- Stacks externas (db, redis, evolution, nginx) já rodando
- Rede Docker `imob_network` criada e compartilhada entre todas as stacks

---

## Configuração da rede Docker

Todas as stacks precisam usar a mesma rede externa.

```bash
# 1. Criar a rede (uma vez por servidor)
make network
# ou:
docker network create imob_network

# 2. Cada stack externa deve declarar a rede assim:
# (no docker-compose.yml de cada stack externa)
networks:
  imob_network:
    external: true
```

---

## Início rápido

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env:
#   DB_HOST      = nome do container PostgreSQL na rede imob_network
#   REDIS_URL    = redis://nome-do-container-redis:6379/0
#   EVOLUTION_API_URL = http://nome-do-container-evolution:8080

# 2. Build e subir
make build
make up

# 3. Migrations do schema public (primeira vez)
make migrate-shared

# 4. Criar primeira imobiliária de teste
make create-tenant

# 5. Verificar se todos os containers estão visíveis na rede
make check-network
```

---

## Configuração do Nginx externo

O Nginx da sua stack deve fazer proxy para o container `web` via rede `imob_network`.
Exemplo de bloco no Nginx externo:

```nginx
server {
    listen 443 ssl http2;
    server_name ~^(?<tenant>.+)\.dnsoftware\.com\.br$ dnsoftware.com.br;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass         http://web:8000;   # ← container web via rede Docker
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }
}
```

> **Atenção:** O volume de `/app/staticfiles` e `/app/media` do container `web`
> precisam ser acessíveis pelo Nginx. Use um volume nomeado compartilhado ou
> monte o mesmo diretório do host nas duas stacks.

---

## Variáveis de ambiente importantes

| Variável | Descrição | Exemplo |
|---|---|---|
| `SECRET_KEY` | Chave secreta Django | string longa aleatória |
| `DB_HOST` | Nome do container PostgreSQL na rede | `postgres` |
| `DB_NAME/USER/PASSWORD` | Credenciais do banco | — |
| `REDIS_URL` | URL Redis na rede Docker | `redis://redis:6379/0` |
| `EVOLUTION_API_URL` | URL Evolution na rede Docker | `http://evolution:8080` |
| `EVOLUTION_API_KEY` | Chave da Evolution API | — |
| `TENANT_BASE_DOMAIN` | Domínio base dos subdomínios | `dnsoftware.com.br` |
| `FLOWER_USER/PASSWORD` | Acesso ao painel Flower | — |
| `SICREDI_WEBHOOK_SECRET` | Secret HMAC do webhook Sicredi | — |

---

## Estrutura do projeto

```
imobiliaria/
├── config/
│   ├── settings/base.py     # configurações multi-tenant
│   ├── settings/dev.py
│   ├── settings/prod.py
│   ├── celery.py            # TenantTask
│   ├── urls_public.py       # landing page
│   └── urls_tenant.py       # sistema por imobiliária
├── apps/
│   ├── tenants/             # Tenant, Domain, Plano
│   ├── core/                # Usuario, dashboard
│   ├── imoveis/             # (Fase 3)
│   ├── inquilinos/          # (Fase 3)
│   ├── contratos/           # (Fase 4)
│   ├── financeiro/          # (Fase 5)
│   ├── sicredi/             # (Fase 5)
│   ├── whatsapp/            # (Fase 6)
│   └── relatorios/          # (Fase 7)
├── templates/
├── static/
├── requirements/
├── docker-compose.yml       # web, celery, celery-beat, flower
├── Dockerfile
├── Makefile
└── .env.example
```

---

## Comandos úteis

```bash
make network                         # cria rede Docker externa (1x)
make build && make up                # build e subir
make logs                            # ver logs
make migrate-shared                  # migrations iniciais
make migrate                         # migrations em todos os tenants
make create-tenant                   # criar imobiliária de teste
make check-network                   # verificar containers na rede
make tenant-shell schema=imob_alpha  # shell dentro de um tenant
```

---

## Fases de implementação

| Fase | Status | Descrição |
|---|---|---|
| 1 | ✅ Concluída | Setup, Docker, Django, Tailwind, multi-tenant base |
| 2 | 🔜 Próxima | App tenants: onboarding, painel superadmin, configurações |
| 3 | ⏳ | Imóveis e inquilinos — CRUD completo |
| 4 | ⏳ | Contratos e geração de PDF |
| 5 | ⏳ | Financeiro e integração Sicredi |
| 6 | ⏳ | WhatsApp via Evolution API |
| 7 | ⏳ | Relatórios e dashboard |
| 8 | ⏳ | Produção: SSL, monitoramento, backup |
