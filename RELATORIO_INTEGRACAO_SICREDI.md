# Relatório — Integração Sicredi (Boletos)

Data: 2026-06-16
Projeto: ImobCloud

---

## 1. Resumo executivo

Implementada a integração com a API de Cobrança Sicredi v3.9.1 (sandbox/produção) para emissão e baixa de boletos vinculados às parcelas de contrato, incluindo:

- Cliente HTTP com autenticação OAuth2 (`grant_type=password` + `refresh_token`), token cacheado por tenant.
- Geração e cancelamento ("baixa") de boletos, com tratamento dos erros 422 documentados pela Sicredi.
- Webhook público que recebe eventos de liquidação/estorno, identifica o tenant pelo `codigo_beneficiario` e atualiza Parcela/Boleto **sem duplicar** a lógica já existente de `financeiro` (Lancamento) e `whatsapp` (confirmação) — ambas continuam disparando via os signals já existentes em `Parcela.save()`.
- Geração assíncrona de boleto via Celery quando uma Parcela é criada (somente se houver `ConfigSicredi` ativa para o tenant), com retry/backoff exponencial.
- UI na tela de contrato (status do boleto por parcela + botões "Gerar boleto" / "Baixar").
- Validação **opcional** de assinatura HMAC-SHA256 no webhook (best-effort, ver seção 6 — a Sicredi não documenta oficialmente esse mecanismo nesta versão da API; só roda se o tenant preencher `ConfigSicredi.webhook_secret`).
- 22 testes automatizados (pytest-style via `unittest`/`TenantTestCase`), todos mockados — nenhuma chamada real à API.

Durante a implementação dos testes, dois **bugs pré-existentes** (não relacionados ao Sicredi) foram encontrados e corrigidos porque bloqueavam qualquer criação de Parcela/schema novo no sistema — detalhes na seção 6.

---

## 2. Arquivos alterados

### Novos
| Arquivo | Conteúdo |
|---|---|
| `apps/sicredi/client.py` | Cliente HTTP Sicredi (auth, criar boleto, baixar boleto) |
| `apps/sicredi/tasks.py` | Task Celery `gerar_boleto_parcela_task` (retry 3x, backoff 60/120/240s) |
| `apps/sicredi/signals.py` | Dispara geração automática de boleto ao criar Parcela |
| `apps/sicredi/tests.py` | 22 testes (auth, criação/baixa de boleto, webhook, assinatura HMAC) |
| `apps/sicredi/migrations/0002_boleto_erro_mensagem_boleto_pago_em_boleto_qr_code_and_more.py` | Migration do `Boleto` estendido |
| `apps/tenants/migrations/0005_configsicredi_api_key_configsicredi_codigo_acesso_and_more.py` | Migration do `ConfigSicredi` estendido |

### Reescritos
| Arquivo | Motivo |
|---|---|
| `apps/sicredi/service.py` | Camada de negócio: testar credenciais, gerar/cancelar boleto, processar webhook |
| `apps/sicredi/views.py` | `boleto_emitir`, `boleto_cancelar` (manuais) + `webhook_sicredi` (público) |
| `apps/tenants/models.py` | `ConfigSicredi` com campos da API v3.9.1 (`api_key`, `codigo_acesso`, `codigo_beneficiario`, `schema_name`) |

### Modificados
| Arquivo | Mudança |
|---|---|
| `apps/sicredi/models.py` | `Boleto`: + `seu_numero`, `txid`, `qr_code`, `valor_pago`, `pago_em`, `erro_mensagem`, status `'erro'` |
| `apps/sicredi/apps.py` | `ready()` conecta os signals |
| `apps/tenants/services.py` | `testar_credenciais_sicredi` delega para `apps.sicredi.service` (evita duplicar lógica) |
| `apps/tenants/views.py` | `config_sicredi`/`testar_sicredi` passam a filtrar `ConfigSicredi` pelo `schema_name` do tenant atual (antes usava `.first()`, que pegava a config de **qualquer** tenant) |
| `apps/contratos/views.py` | `contrato_detalhe`: `select_related('boleto')` na query de parcelas |
| `templates/contratos/detalhe.html` | Coluna "Boleto" com status + botões de ação |
| `config/urls_public.py` | Rota do webhook (`/sicredi/webhook/`) |
| `config/settings/base.py` | `CELERY_TASK_ROUTES` (fila `financeiro`) + `CACHES` (Redis, token Sicredi) |
| `config/settings/dev.py` | `CACHES` com `LocMemCache` (dev não depende de Redis) |

### Bugfixes pré-existentes (não relacionados ao Sicredi, ver seção 6)
| Arquivo | Bug |
|---|---|
| `apps/tenants/migrations/0002_fase2.py` | `AddField` duplicado de colunas já criadas em `0001_initial` — quebrava criação de schema novo |
| `apps/whatsapp/signals.py` | `Parcela.Status.PAGO` não existe — quebrava `post_save` de **toda** Parcela |

---

## 3. Endpoints

### Recebidos (Sicredi → ImobCloud)
| Método | URL | Schema | Auth | Observação |
|---|---|---|---|---|
| `POST` | `/sicredi/webhook/` | `public` | nenhuma (API não exige nesta versão) | `csrf_exempt`, sempre responde `200` em até 10s, mesmo com erro interno (logado) |

### Chamados (ImobCloud → Sicredi, via `SicrediClient`)
| Método | URL | Função |
|---|---|---|
| `POST` | `https://api-parceiro.sicredi.com.br[/sb]/auth/openapi/token` | Login (`grant_type=password`) / Refresh (`grant_type=refresh_token`) |
| `POST` | `.../cobranca/boleto/v1/boletos` | Criar boleto |
| `PATCH` | `.../cobranca/boleto/v1/boletos/{nossoNumero}/baixa` | Baixar (cancelar) boleto |

`/sb` é usado quando `ConfigSicredi.ambiente == 'sandbox'`; vazio em produção.

### Internos (UI, dentro do tenant)
| Método | URL | View |
|---|---|---|
| `POST` | `/boleto/<parcela_pk>/emitir/` | `boleto_emitir` |
| `POST` | `/boleto/<parcela_pk>/cancelar/` | `boleto_cancelar` |
| `GET/POST` | `/configuracoes/sicredi/` | `config_sicredi` |
| `POST` | `/configuracoes/sicredi/testar/` | `testar_sicredi` |

---

## 4. Fluxo completo

```
┌─ Criação de Parcela (gerar_parcelas / pagamento manual) ──────────────┐
│  post_save(Parcela, created=True)                                    │
│   └─ apps/sicredi/signals.py: se ConfigSicredi ativa no tenant        │
│       └─ gerar_boleto_parcela_task.apply_async(countdown=10s)         │
│           └─ SicrediClient.criar_boleto() → Boleto(status='emitido')  │
│               (falha → retry 60/120/240s; erro de auth → sem retry,   │
│                Boleto fica status='erro' com erro_mensagem)           │
└─────────────────────────────────────────────────────────────────────┘

┌─ Ação manual na tela do contrato ──────────────────────────────────────┐
│  "Gerar boleto"  → POST boleto_emitir  → gerar_boleto_parcela()        │
│  "Baixar"        → POST boleto_cancelar → cancelar_boleto()            │
└──────────────────────────────────────────────────────────────────────┘

┌─ Webhook (pagamento/estorno) ──────────────────────────────────────────┐
│  Sicredi → POST /sicredi/webhook/ (schema public)                      │
│   └─ processar_webhook(payload)                                        │
│       ├─ lookup ConfigSicredi por codigo_beneficiario → schema_name    │
│       ├─ schema_context(schema_name)                                   │
│       ├─ movimento em LIQUIDACAO_* → _registrar_liquidacao             │
│       │    ├─ Boleto: status='pago', valor_pago, pago_em               │
│       │    └─ Parcela.save(status='pago', data_pagamento=...)          │
│       │         ├─ signal financeiro → cria Lancamento (receita)       │
│       │         └─ signal whatsapp   → task_pagamento_confirmado       │
│       └─ movimento == ESTORNO_LIQUIDACAO_REDE (só mesmo dia)           │
│            └─ _registrar_estorno                                       │
│                 ├─ Boleto: volta para 'emitido'                        │
│                 ├─ Parcela: volta para 'pendente'                      │
│                 └─ Lancamento da parcela → status='cancelado'          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Checklist para produção

- [ ] Rodar migrations: `python manage.py migrate_schemas --settings=config.settings.prod`
- [ ] Cadastrar `ConfigSicredi` de cada tenant em **Configurações → Sicredi**: `api_key` (x-api-key do Portal do Desenvolvedor), `codigo_acesso`, `codigo_beneficiario`, `cooperativa`, `posto`, `beneficiario`, `ambiente='producao'`
- [ ] Clicar em "Testar conexão" (`testar_sicredi`) — só ativa (`ativo=True`) se a autenticação funcionar
- [ ] Confirmar `CACHE_URL` apontando pro Redis real em produção (token fica em cache por tenant — sem Redis funcionando, todo login Sicredi vira uma chamada nova)
- [ ] Configurar no Portal do Desenvolvedor Sicredi a URL pública do webhook: `https://<dominio-publico>/sicredi/webhook/`
- [ ] Confirmar que o worker Celery está consumindo a fila `financeiro` (`CELERY_TASK_ROUTES`)
- [ ] Cadastrar `cnpj`, `endereco`, `cidade`, `estado`, `cep` do `Tenant` (usados no `beneficiarioFinal` do payload) — ver limitação do `numeroEndereco` abaixo
- [ ] Validar em sandbox antes de trocar `ambiente` para `producao`
- [ ] (Opcional) Remover `SICREDI_API_URL` e `SICREDI_TOKEN_URL` de `config/settings/base.py` — código morto confirmado: `SicrediClient` hardcoda `HOST = 'https://api-parceiro.sicredi.com.br'` e monta as URLs a partir disso, nunca lê essas settings

---

## 6. Limitações conhecidas / bugs corrigidos

**Limitação aceita (`numeroEndereco`)**: `Tenant.endereco` é um campo de texto livre (não separado em logradouro/número). `SicrediClient._beneficiario_final()` envia `numeroEndereco='S/N'` fixo. Aceito pelo usuário durante o planejamento — se a Sicredi rejeitar endereços sem número em produção, será necessário separar o campo `Tenant.endereco` em logradouro/número.

**Validação de assinatura do webhook é best-effort (`webhook_secret`)**: a API de Cobrança Sicredi v3.9.1 não documenta oficialmente nenhum mecanismo de assinatura/HMAC para o webhook — pesquisa em documentação pública (Sicredi, integradores como IXC/Omie) não encontrou um header padronizado (ex.: `X-Signature`). Por isso a validação implementada em `apps/sicredi/service.py::_assinatura_valida` é **opcional e defensiva**:
- Se `ConfigSicredi.webhook_secret` estiver vazio (padrão), o webhook aceita o payload normalmente — comportamento idêntico ao anterior, sem quebrar quem não configurar nada.
- Se `webhook_secret` estiver preenchido, a view (`webhook_sicredi`) lê o header `X-Signature` e compara com HMAC-SHA256(secret, corpo bruto da requisição) — formato assumido por convenção (GitHub/Stripe), não confirmado pela Sicredi. Assinatura ausente ou inválida → payload é descartado (log de warning), mas a resposta HTTP continua sendo `200` (regra do Sicredi de sempre responder 200).
- Quando a Sicredi formalizar o mecanismo oficial (header/algoritmo), ajustar `_assinatura_valida` e a leitura do header em `webhook_sicredi`.

**Bugs pré-existentes corrigidos** (necessários para os testes rodarem, mas afetam o sistema independente do Sicredi):
1. `apps/tenants/migrations/0002_fase2.py` adicionava (`AddField`) `preco_mensal`, `logo`, `cor_primaria`, `cor_secundaria` que já existiam em `0001_initial.py` (CreateModel). Isso quebrava `migrate_schemas` em qualquer schema novo (banco de teste, ou um tenant novo cadastrado em produção). Os `AddField` duplicados foram removidos — não afeta tenants já migrados, pois o histórico de migrations já estava marcado como aplicado.
2. `apps/whatsapp/signals.py` usava `Parcela.Status.PAGO`, que não existe (`Parcela` não tem classe `Status`, só o campo `status`). Isso fazia **qualquer** `Parcela.save()` levantar `AttributeError` dentro do signal de confirmação de pagamento via WhatsApp — ou seja, a notificação de "pagamento confirmado" estava quebrada em produção antes desta correção. Trocado por `instance.status != 'pago'`.

---

## 7. Próximos passos sugeridos

- Job periódico (Celery Beat) pra marcar `Boleto.status='vencido'` quando `parcela.data_vencimento` passar sem pagamento (hoje só existe o status no `STATUS_CHOICES`, sem nada que o aplique).
- Reenviar boleto automaticamente quando `Boleto.status='erro'` (hoje só reemite manual pela UI).
- Validar/normalizar `Tenant.endereco` em campos estruturados para resolver a limitação do `numeroEndereco`.
- Confirmar com a Sicredi (Portal do Desenvolvedor/gerente de conta) o formato oficial de assinatura do webhook, se/quando existir, e ajustar `_assinatura_valida`/header lido em `webhook_sicredi` de acordo (ver limitação na seção 6).

---

## 8. Testes

Comando:
```bash
python manage.py test apps.sicredi --settings=config.settings.dev --noinput
```

Resultado:
```
Ran 22 tests in 18.728s
OK
```

Cobertura:
- **Autenticação** (5): login com sucesso, reaproveitamento de token em cache, falha 401, `testar_credenciais_sicredi` sucesso/falha.
- **Criação de boleto** (5): payload montado corretamente (valores, documento do pagador, `seuNumero`), erro genérico, erro 429 (limite), erro 401 (auth), erro quando não há `ConfigSicredi` ativa.
- **Baixa de boleto** (4): sucesso (202), título já liquidado (422 → erro amigável), título já baixado (422 → idempotente, trata como sucesso), negativação/protesto (422 → erro).
- **Webhook** (5): liquidação marca parcela como paga e cria `Lancamento` (via signal existente, sem duplicar lógica), estorno no mesmo dia reverte tudo e cancela o `Lancamento`, estorno fora do dia é ignorado, beneficiário desconhecido não quebra, boleto inexistente não quebra.
- **Assinatura do webhook** (3): assinatura válida processa o payload normalmente, assinatura inválida descarta o payload (parcela não muda), `webhook_secret` vazio mantém o comportamento antigo (aceita sem validar).

Todas as chamadas HTTP são mockadas (`unittest.mock`, sem pacote `responses` instalado); as tasks Celery (`gerar_boleto_parcela_task`, `task_pagamento_confirmado`, `task_contrato_criado`) são mockadas via `apply_async` para não depender de broker.
