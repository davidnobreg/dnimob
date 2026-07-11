# Plano — Reconciliação de boletos liquidados (Consulta Sicredi)

Segue TDD (teste falho → mínimo código → refactor). Nenhum código escrito ainda — isto é o plano pra revisão antes de codar.

## Escopo

Endpoint confirmado:
- **GET** `https://api-parceiro.sicredi.com.br/cobranca/boleto/v1/boletos/liquidados/dia` (produção)
- **GET** `https://api-parceiro.sicredi.com.br/sb/cobranca/boleto/v1/boletos/liquidados/dia` (sandbox)
- Resposta: `{"items": [...], "hasNext": bool}` — chave da lista confirmada como `items`.

## 1. `client.py` — `SicrediClient.consultar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None)`

- Reusa `_headers_api()` já existente (Authorization Bearer + x-api-key + cooperativa + posto).
- `dia`: `date` do Python, formatado `DD/MM/YYYY` no param. Aceita qualquer data retroativa (não só hoje).
- Params: `codigoBeneficiario`, `dia`, `pagina` (sempre), `cpfCnpjBeneficiarioFinal` (só se informado).
- Paginação **interna**: loop segue `hasNext` até `False`, acumula `items` de cada página, retorna lista única já completa.
- Erros: 401/403 → `SicrediAuthError`; 429 → `SicrediAPIError` ("Limite de requisições..."); outros != 200 → `SicrediAPIError` com `_extrair_erro(resp)` (mesmo padrão de `criar_boleto`).
- Comentário no código documentando o caso de PIX fim de semana (só aparece no dia útil seguinte) — não resolve automaticamente, só avisa quem for rodar manualmente pra trás.

## 2. `service.py` — `reconciliar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None)`

- Pega `ConfigSicredi` do tenant atual (`get_config_tenant()`), instancia `SicrediClient`, chama `consultar_liquidados_dia`.
- Pra cada item retornado, busca `Boleto` local por `nossoNumero`:
  - **Não encontrado** → conta em `nao_encontrados`, loga warning, segue (não quebra o lote).
  - **Já `status='pago'`** → no-op, idempotente (webhook já processou certo).
  - **`status` diferente de `pago`** (emitido/erro/etc.) → chama a função existente `_registrar_liquidacao(nosso_numero, payload)` (a mesma que o webhook usa), montando `payload` compatível a partir dos campos da consulta (`valorLiquidado` → `valorLiquidacao`, `dataPagamento` → `dataPrevisaoPagamento`). **Não duplica regra de negócio** — reaproveita 100% a lógica que já marca boleto+parcela como pago e deixa os signals (financeiro/whatsapp) dispararem normalmente.
  - Conta em `recuperados`, loga como discrepância recuperada (métrica de quão frequente o webhook falha).
- Retorna `{'total': N, 'recuperados': N, 'nao_encontrados': N}`.

## 3. `tasks.py` — task Celery manual (sem beat)

- `reconciliar_liquidados_dia_task(self, dia_str, cpf_cnpj_beneficiario_final=None)`, base `TenantTask` (schema como 1º arg, igual `gerar_boleto_parcela_task`).
- Retry (2x) em `SicrediError` genérico; **não** em erro de auth (credencial não se corrige sozinha — mesmo padrão da task existente).
- **Não entra no `CELERY_BEAT_SCHEDULE`.** Chamada manual: `reconciliar_liquidados_dia_task.apply_async(args=[schema, '2026-07-10'])`.

## 4. Testes (`tests.py`)

**Client:**
- Paginação: página 1 `hasNext=True` + página 2 `hasNext=False` → junta os itens das duas, 2 chamadas GET.
- Erro 400 → `SicrediAPIError`.
- Erro 429 → `SicrediAPIError` com "Limite" na mensagem.

**Service (reconciliação):**
- Boleto `emitido` local + item retornado como liquidado → vira `pago`, parcela `pago`, `Lancamento` criado (via signal existente).
- Boleto já `pago` local + item liquidado → nada muda, sem `Lancamento` duplicado (idempotência).
- Item com `nossoNumero` sem `Boleto` correspondente → não quebra, conta em `nao_encontrados`.

Roda só o módulo: `pytest apps/sicredi/ -v` (ou equivalente `manage.py test` do projeto).

## Fora de escopo (confirmado, não fazer)

- `webhook_secret`/autenticação do webhook — intocado.
- Outros 10 comandos de instrução, outras consultas — fora.
- Adicionar ao Celery beat — fica pra decisão de infra futura.
- Remover/alterar `url_boleto` — Parte 1 já trouxe evidência (campo morto + patch de template órfão, nunca aplicado em `detalhe.html`), mas decisão de remover fica com você.

---
**Próximo passo:** com esse plano aprovado, começo o ciclo TDD (teste RED → GREEN) pro método do client primeiro.
