# Resultado — Reconciliação de boletos liquidados (Sicredi)

Implementação concluída via TDD. Referência: plano em `reconciliacao-boletos-sicredi.md`.

## Passo 0 — Checagem de `dataPrevisaoPagamento`

**Resultado: só campo de data, sem lógica condicional.**

`_registrar_liquidacao` (em `service.py`) faz:
```python
data_pgto = _parse_data(payload.get('dataPrevisaoPagamento') or payload.get('dataEvento')) or timezone.now().date()
```
Valor vai direto pra `boleto.pago_em` e `parcela.data_pagamento` — sem comparação, sem flag "ainda não confirmado", sem branch condicional. Nome do campo é resquício do payload do webhook (mal nomeado pra esse uso novo), mas o comportamento é puramente "data do pagamento". Mapeamento `dataPagamento` (consulta) → `dataPrevisaoPagamento` (payload interno) segue sem risco, como estava no plano original.

## Implementação

### `client.py` — `SicrediClient.consultar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None)`
- GET `{HOST}{/sb}/cobranca/boleto/v1/boletos/liquidados/dia`
- Reusa `_headers_api()` existente
- `dia` formatado `DD/MM/YYYY`; aceita qualquer data retroativa
- Paginação interna: segue `hasNext` até `False`, acumula `items` de todas as páginas
- Erros: 401/403 → `SicrediAuthError`; 429 → `SicrediAPIError` ("Limite de requisições..."); outros → `SicrediAPIError` via `_extrair_erro`
- Comentário no código documentando o caso de PIX fim de semana (só aparece na consulta do dia útil seguinte)

### `service.py` — `reconciliar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None)`
- Consulta a Sicredi via client, cruza cada item com `Boleto` local por `nossoNumero`
- Não encontrado → conta em `nao_encontrados`, loga warning, segue o lote
- Já `pago` → no-op (idempotente)
- Diferente de `pago` → chama `_registrar_liquidacao` (mesma função do webhook, sem duplicar regra), conta em `recuperados`, loga como discrepância recuperada
- Retorna `{'total': N, 'recuperados': N, 'nao_encontrados': N}`

### `tasks.py` — `reconciliar_liquidados_dia_task(self, dia_str, cpf_cnpj_beneficiario_final=None)`
- Base `TenantTask`, retry 2x em erro genérico, sem retry em erro de autenticação
- **Não entrou no `CELERY_BEAT_SCHEDULE`** — chamada manual: `reconciliar_liquidados_dia_task.apply_async(args=[schema, 'YYYY-MM-DD'])`

### Testes — 9 novos, todos verdes

**Client (`ConsultarLiquidadosDiaTests`):**
- Paginação junta itens de 2 páginas até `hasNext=False`
- Erro 400 → `SicrediAPIError`
- Erro 429 → `SicrediAPIError` com "Limite" na mensagem

**Service (`ReconciliarLiquidadosDiaTests`):**
- Boleto `emitido` + item liquidado → vira `pago`, parcela `pago`, `Lancamento` criado
- Boleto já `pago` + item liquidado → nada muda, sem `Lancamento` duplicado
- Item sem `Boleto` local correspondente → não quebra, conta em `nao_encontrados`

**Resultado da suíte completa:**
```
python manage.py test apps.sicredi --settings=config.settings.dev
Ran 39 tests in 39.154s
OK
```
(39 = 30 testes já existentes + 9 novos, todos passando)

## Fora de escopo — respeitado

- `webhook_secret`/autenticação do webhook: intocado
- Outros 10 comandos de instrução, outras consultas: não implementados
- `CELERY_BEAT_SCHEDULE`: não alterado — reconciliação continua 100% manual
- `Boleto.url_boleto`: intocado (achado da Parte 1 registrado em `docs/modelos/sicred.md` — campo morto + patch de template órfão nunca aplicado; decisão de remover fica em aberto)
