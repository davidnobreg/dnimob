# Inventário — Integração Sicredi (`apps/sicredi/`)

Levantamento item a item do manual oficial Sicredi (Autenticação, Cobrança, Distribuição de Crédito, Webhook) comparado ao que está implementado no código hoje. Base: `apps/sicredi/client.py`, `service.py`, `views.py`, `urls.py`, `models.py`, `tasks.py`, `signals.py`, `tests.py`.

## Tabela geral

| Frente | Item | Status | Localização no código | Tem teste? | Observação |
|---|---|---|---|---|---|
| Autenticação | OAuth2 password + `x-api-key` | ✅ Implementado | `client.py:97-141` `_login/_post_token/_headers_auth` | Sim (`tests.py` `AutenticacaoTests`) | grant_type=password + scope=cobranca |
| Autenticação | Renovação via refresh_token | ✅ Implementado | `client.py:108-114,143-165` `_refresh/_access_token` | Sim (reusa token em cache) | fallback pra login completo se refresh também expirar |
| Autenticação | Cache de token (Redis) por schema | ✅ Implementado | `client.py:85-86,139` `_cache_key` | Sim | TTL = `refresh_expires_in` |
| Autenticação | Sandbox vs Produção | ✅ Implementado | `client.py:69-71` `_prefixo` (`/sb`) | Não direto (só via `config.ambiente` nos fixtures) | via `ConfigSicredi.ambiente` |
| Cobrança — Cadastro | Cadastro de Boleto | ✅ Implementado | `client.py:236-278` `criar_boleto` | Sim (4 testes) | `POST /cobranca/boleto/v1/boletos` |
| Cobrança — Cadastro | Nosso Número | ⚠️ Parcial | `client.py:267` — só **lê** `nossoNumero` da resposta | Sim (indireto) | Sem geração/reserva própria — depende 100% do retorno da Sicredi |
| Cobrança — Cadastro | Impressão de Boletos | ❌ Ausente | — | — | Model `Boleto` guarda `linha_digitavel`/`codigo_barras`/`qr_code`, mas nenhuma view/endpoint gera PDF ou imprime. Campo `url_boleto` existe no model e **nunca é preenchido** |
| Instrução | Pedido de Baixa | ✅ Implementado | `client.py:280-315` `baixar_boleto` | Sim (4 testes) | Trata 422 documentados (já baixado, liquidado, negativação) |
| Instrução | Alteração de Vencimento | ❌ Ausente | — | — | Sem uso dependente encontrado |
| Instrução | Alteração de Desconto | ❌ Ausente | — | — | — |
| Instrução | Alteração de Data de Desconto | ❌ Ausente | — | — | — |
| Instrução | Alteração de Juros | ❌ Ausente | — | — | — |
| Instrução | Alteração de Seu Número | ❌ Ausente | — | — | `seu_numero` só é setado na criação (`_montar_payload`), imutável depois |
| Instrução | Conceder Abatimento | ❌ Ausente | — | — | — |
| Instrução | Cancelar Abatimento Concedido | ❌ Ausente | — | — | — |
| Instrução | Pedido de Protesto | ❌ Ausente | — | — | `ERROS_BAIXA` só reconhece a mensagem de protesto vinda do Sicredi, não solicita |
| Instrução | Sustar Protesto e Baixar Título | ❌ Ausente | — | — | — |
| Instrução | Sustar Protesto e Manter Título | ❌ Ausente | — | — | — |
| Instrução | Incluir Negativação | ❌ Ausente | — | — | — |
| Instrução | Excluir Negativação e Baixar Título | ❌ Ausente | — | — | — |
| Instrução | Cancelar Protesto Automático | ❌ Ausente | — | — | — |
| Consultas | Boletos por Nosso Número | ❌ Ausente | — | — | Sem GET individual — status só chega via webhook, sem reconciliação ativa |
| Consultas | Boletos Liquidados por Dia | ❌ Ausente | — | — | Sem job de conciliação diária — risco se webhook falhar/perder evento |
| Consultas | Por idEmpresa/seuNumero | ❌ Ausente | — | — | — |
| Consultas | Francesinha (movimentações financeiras) | ❌ Ausente | — | — | — |
| Consultas | Boletos com Distribuição de Crédito | ❌ Ausente | — | — | — |
| Distribuição de Crédito | Cancelar Parcelas de Distribuição | ❌ Ausente | — | — | Sistema não trata distribuição de crédito em nenhum model |
| Distribuição de Crédito | Liberar Repasse | ❌ Ausente | — | — | — |
| Webhook | Recebimento de Eventos | ✅ Implementado (já auditado antes) | `views.py:60-91` `webhook_sicredi` + `service.py:112-232` | Sim (~15 testes) | Liquidação (6 movimentos) + estorno mesmo-dia; HMAC opcional/obrigatório por ambiente já coberto |
| Webhook | Cadastro de Contrato Webhook | ❌ Ausente | — | — | Endpoint público existe e funciona, mas contratação do webhook (registrar URL no Sicredi via API) é manual — ver checklist em `RELATORIO_INTEGRACAO_SICREDI.md:133` |
| Webhook | Consulta de Contratos | ❌ Ausente | — | — | — |
| Webhook | Alteração de Contrato Webhook | ❌ Ausente | — | — | — |

## Achados que merecem atenção antes de priorizar testes

1. **Nenhuma consulta ativa (reconciliação).** Sistema 100% dependente do webhook chegar. Se a Sicredi não reenviar um evento perdido, o boleto fica `emitido` pra sempre mesmo já pago. `Consulta de Boletos Liquidados por Dia` cobriria esse gap.
2. **`Boleto.url_boleto`** existe no model mas nunca é preenchido em `criar_boleto`. Ou é campo morto, ou indica feature de impressão planejada e não terminada.
3. **`ERROS_BAIXA`** reconhece textualmente "negativação"/"protesto" vindos de erro 422 da baixa, mas o sistema nunca *solicita* essas operações — só reage se já estiverem em curso.
4. Cobertura de teste é boa (~22-25 testes), mas cobre só as 4 frentes implementadas: autenticação, criar boleto, baixar boleto, webhook (liquidação/estorno).

## Escopo implementado hoje (resumo)

- Autenticação (OAuth2 password + refresh + cache)
- Cadastro de Boleto (criação)
- Pedido de Baixa
- Webhook — recebimento de eventos de liquidação/estorno

Tudo mais do manual (impressão, geração ativa de nosso número, os outros 10 comandos de instrução, todas as consultas, distribuição de crédito, contratação/gestão de webhook via API) está ausente.

---
*Fonte: inventário gerado por leitura direta do código em `apps/sicredi/`, cruzado com `RELATORIO_INTEGRACAO_SICREDI.md`.*
