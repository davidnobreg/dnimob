# Relatório de Auditoria dos Templates — Tailwind CSS

**Projeto:** ImobCloud — SaaS de gestão imobiliária  
**Data:** 2026-06-07  
**Total de templates encontrados:** 46  
**Templates ausentes identificados:** 2  

---

## 1. Resumo Executivo

O projeto apresenta **dois grupos claramente distintos** de templates:

- **Módulos de domínio** (imóveis, inquilinos, contratos, financeiro): majoritariamente em Tailwind CSS moderno, responsivos, com Alpine.js correto.
- **Módulo de tenants/configuração** (cadastro, config, usuários, superadmin): totalmente em classes CSS proprietárias sem nenhuma classe Tailwind. Dependem de folha de estilo customizada não localizada no projeto — o que sugere que ou esta CSS está embutida em `<style>` em outro arquivo, ou esses templates estão sem estilo funcional.

O **sidebar principal** (`components/sidebar.html`) é o problema mais crítico: é incluído em todas as páginas autenticadas e não usa Tailwind.

---

## 2. Templates Encontrados

| # | Template | Módulo |
|---|---|---|
| 1 | `base.html` | Base |
| 2 | `base_public.html` | Base |
| 3 | `components/messages.html` | Componentes |
| 4 | `components/sidebar.html` | Componentes |
| 5 | `core/login.html` | Core |
| 6 | `core/dashboard.html` | Core |
| 7 | `imoveis/lista.html` | Imóveis |
| 8 | `imoveis/form.html` | Imóveis |
| 9 | `imoveis/detalhe.html` | Imóveis |
| 10 | `imoveis/index.html` | Imóveis |
| 11 | `imoveis/confirmar_exclusao.html` | Imóveis |
| 12 | `inquilinos/lista.html` | Inquilinos |
| 13 | `inquilinos/form.html` | Inquilinos |
| 14 | `inquilinos/detalhe.html` | Inquilinos |
| 15 | `inquilinos/index.html` | Inquilinos |
| 16 | `inquilinos/confirmar_exclusao.html` | Inquilinos |
| 17 | `contratos/lista.html` | Contratos |
| 18 | `contratos/form.html` | Contratos |
| 19 | `contratos/detalhe.html` | Contratos |
| 20 | `contratos/index.html` | Contratos |
| 21 | `contratos/confirmar_encerramento.html` | Contratos |
| 22 | `contratos/parcela_pagamento.html` | Contratos |
| 23 | `contratos/pdf/recibo.html` | Contratos PDF |
| 24 | `contratos/pdf/contrato.html` | Contratos PDF |
| 25 | `financeiro/dashboard.html` | Financeiro |
| 26 | `financeiro/lancamentos.html` | Financeiro |
| 27 | `financeiro/inadimplencia.html` | Financeiro |
| 28 | `financeiro/lancamento_form.html` | Financeiro |
| 29 | `financeiro/lancamento_confirmar_exclusao.html` | Financeiro |
| 30 | `financeiro/index.html` | Financeiro |
| 31 | `relatorios/index.html` | Relatórios |
| 32 | `whatsapp/index.html` | WhatsApp |
| 33 | `sicredi/index.html` | Sicredi |
| 34 | `sicredi/parcela_acoes_patch.html` | Sicredi |
| 35 | `tenants/landing.html` | Tenants |
| 36 | `tenants/cadastro.html` | Tenants |
| 37 | `tenants/cadastro_sucesso.html` | Tenants |
| 38 | `tenants/acesso_bloqueado.html` | Tenants |
| 39 | `tenants/config_conta.html` | Tenants |
| 40 | `tenants/config_sicredi.html` | Tenants |
| 41 | `tenants/config_whatsapp.html` | Tenants |
| 42 | `tenants/config_templates_whatsapp.html` | Tenants |
| 43 | `tenants/config_template_editar.html` | Tenants |
| 44 | `tenants/usuarios_lista.html` | Tenants |
| 45 | `tenants/usuario_convidar.html` | Tenants |
| 46 | `tenants/superadmin/dashboard.html` | Superadmin |

---

## 3. Status Geral dos Templates

| Status | Qtd |
|---|---|
| ✅ OK | 25 |
| 🟡 Parcial | 10 |
| 🔴 Precisa modernizar | 11 |
| ⚫ Ausente | 2 |
| **Total** | **48** |

---

## 4. Templates 100% em Tailwind

| Template | Observações |
|---|---|
| `base.html` | Layout principal sólido. CDN do Tailwind configurado. Alpine.js OK. CSS inline justificado (form-input/select sem CDN). |
| `base_public.html` | Simples e correto. |
| `components/messages.html` | Alpine.js correto, Tailwind, Tabler icons. |
| `core/dashboard.html` | Cards KPI, ações rápidas, responsivo. |
| `imoveis/lista.html` | Filtros, cards com foto, paginação. |
| `imoveis/form.html` | Formulário multi-seção, busca de CEP via ViaCEP. |
| `imoveis/detalhe.html` | Galeria, características, proprietário. |
| `imoveis/index.html` | Placeholder funcional. |
| `imoveis/confirmar_exclusao.html` | Padrão de exclusão limpo. |
| `inquilinos/confirmar_exclusao.html` | OK. |
| `inquilinos/index.html` | Placeholder funcional. |
| `contratos/confirmar_encerramento.html` | OK. |
| `contratos/parcela_pagamento.html` | Formulário de recebimento limpo. |
| `contratos/index.html` | Placeholder funcional. |
| `contratos/pdf/recibo.html` | CSS print puro — correto para PDF A5. |
| `contratos/pdf/contrato.html` | CSS print puro — correto para PDF A4. |
| `financeiro/inadimplencia.html` | Tabela responsiva, estado vazio. |
| `financeiro/lancamento_confirmar_exclusao.html` | OK. |
| `financeiro/index.html` | Placeholder funcional. |
| `relatorios/index.html` | Placeholder funcional. |
| `whatsapp/index.html` | Placeholder funcional. |
| `sicredi/index.html` | Placeholder funcional. |
| `tenants/acesso_bloqueado.html` | Tailwind, Tabler icons, correto. |
| `tenants/landing.html` | Landing page completa, seções Hero/Features/Planos/CTA. |
| `sicredi/parcela_acoes_patch.html` | Fragmento de patch, Tailwind. |

---

## 5. Templates que Precisam de Modernização

### 5a. Parcial — Tailwind com problemas menores

| Template | Problema | Ação | Prioridade |
|---|---|---|---|
| `core/login.html` | Extends `base.html` que tem `lg:pl-64` no main — layout com recuo de sidebar aparece na tela de login | Criar `base_auth.html` centrado ou ajustar condição no base | Média |
| `inquilinos/lista.html` | Usa `bg-primary` e `text-primary` sem sufixo numérico (ex: `-600`) — não é classe Tailwind nativa | Substituir por `bg-primary-600`, `text-primary-600` etc. | Baixa |
| `inquilinos/detalhe.html` | Idem `text-primary`, `bg-primary/10` | Substituir por valores Tailwind explícitos | Baixa |
| `contratos/lista.html` | Idem `bg-primary`, `text-primary` | Idem | Baixa |
| `contratos/form.html` | Alpine.js com interpolação Django em x-data: `x-data="{ indice: '{{ form.indice_reajuste.value\|default:'igpm' }}' }"` — pode quebrar se o valor contiver aspas simples | Usar `{% if %}` para setar valor, ou escapar com `\|escapejs` | Média |
| `contratos/detalhe.html` | Usa `text-primary` sem sufixo | Substituir | Baixa |
| `financeiro/dashboard.html` | Usa `bg-primary`, `text-primary` | Substituir | Baixa |
| `financeiro/lancamentos.html` | Usa `bg-primary`, `text-primary` | Substituir | Baixa |
| `financeiro/lancamento_form.html` | Usa `bg-primary` | Substituir | Baixa |
| `inquilinos/form.html` | Usa `form-input`/`form-select` (classes definidas no base.html) — dependente de CSS inline global | Aceitável enquanto mantido no `base.html`, documentar | Baixa |

---

## 6. Templates com Bootstrap ou Classes Antigas

Nenhum template do módulo de domínio usa Bootstrap. Os templates do módulo `tenants/` e `components/sidebar.html` usam exclusivamente **classes CSS proprietárias** (ex: `card`, `btn-primary`, `form-group`, `badge-green`, `nav-link`) que **não são Bootstrap** e **não são Tailwind** — são um sistema CSS customizado não localizado em nenhum arquivo lido.

Nota: `tenants/superadmin/dashboard.html` contém `d-block` (linha 65), que é uma classe Bootstrap — mistura de sistemas.

| Template | Classes problemáticas encontradas |
|---|---|
| `components/sidebar.html` | `sidebar`, `sidebar-header`, `sidebar-brand`, `sidebar-nav`, `nav-link`, `nav-group`, `nav-submenu`, `nav-sublink`, `nav-arrow`, `sidebar-footer`, `plano-status`, `trial-badge`, `expired-badge`, `logout-link` |
| `tenants/cadastro.html` | `container-sm`, `cadastro-page`, `cadastro-card`, `form-group`, `form-row`, `btn-primary`, `btn-full`, `btn-lg`, `field-error`, `back-link`, `alert`, `alert-error`, `login-link` |
| `tenants/cadastro_sucesso.html` | `sucesso-page`, `container-sm`, `sucesso-icon`, `sucesso-sub`, `sucesso-info`, `sucesso-steps`, `tenant-link`, `btn-primary`, `btn-lg` |
| `tenants/config_conta.html` | `page-header`, `config-sections`, `card`, `card-header`, `card-body`, `form-row`, `form-group`, `logo-preview`, `color-input-group`, `color-preview`, `form-actions-sticky`, `btn-primary` |
| `tenants/config_sicredi.html` | `page-header`, `config-grid-single`, `card`, `card-header`, `badge`, `form-section`, `btn-primary`, `btn-outline`, `card-info`, `info-list`, `test-result`, `hidden` |
| `tenants/config_whatsapp.html` | `page-header`, `config-grid`, `card`, `status-badge`, `btn-primary`, `btn-danger`, `qr-section`, `qr-wrapper`, `spinner`, `qr-steps`, `whatsapp-conectado`, `templates-cta` |
| `tenants/config_templates_whatsapp.html` | `page-header`, `templates-grid`, `template-card`, `template-inativo`, `badge`, `badge-green`, `badge-gray`, `var-pill`, `btn-sm`, `btn-outline` |
| `tenants/config_template_editar.html` | `page-header`, `back-link`, `template-editor-grid`, `card`, `form-actions`, `btn-primary`, `btn-ghost`, `text-muted`, `var-list`, `var-btn`, `whatsapp-preview`, `wpp-bubble` |
| `tenants/usuarios_lista.html` | `page-header`, `card`, `table-responsive`, `data-table`, `user-cell`, `user-avatar`, `badge`, `row-actions`, `btn-sm`, `btn-outline`, `btn-danger`, `btn-success`, `alert` |
| `tenants/usuario_convidar.html` | `page-header`, `back-link`, `card`, `card-form`, `form-row`, `form-group`, `form-check`, `modulos-grid`, `modulo-check`, `btn-primary`, `btn-ghost` |
| `tenants/superadmin/dashboard.html` | `superadmin-layout`, `superadmin-sidebar`, `sa-logo`, `sa-nav-link`, `sa-kpi-grid`, `sa-kpi`, `kpi-num`, `sa-card`, `sa-search`, `sa-table`, `badge`, `d-block` (Bootstrap) |

---

## 7. Templates com CSS Inline Excessivo

| Template | Situação | Ação |
|---|---|---|
| `base.html` | CSS inline para `.form-input`, `.form-select`, `.form-checkbox` — justificado pois Tailwind CDN não entrega classes de formulário | Manter. Documentar que é intencional. |
| `contratos/pdf/recibo.html` | CSS print completo inline — correto para template de impressão | OK — não alterar |
| `contratos/pdf/contrato.html` | CSS print completo inline — correto para template de impressão | OK — não alterar |
| `tenants/config_conta.html` | Script JS de preview de cores embutido | Mover para `{% block extra_js %}` |

---

## 8. Templates com Problemas de Responsividade

| Template | Problema | Prioridade |
|---|---|---|
| `components/sidebar.html` | Sem classes responsivas (totalmente em CSS próprio) | Alta |
| `tenants/cadastro.html` | Sem classes responsivas (CSS próprio) | Alta |
| `tenants/cadastro_sucesso.html` | Sem classes responsivas (CSS próprio) | Alta |
| `tenants/config_conta.html` | Sem classes responsivas (CSS próprio) | Alta |
| `tenants/config_sicredi.html` | Sem classes responsivas (CSS próprio) | Média |
| `tenants/config_whatsapp.html` | Sem classes responsivas (CSS próprio) | Média |
| `tenants/config_templates_whatsapp.html` | `templates-grid` sem responsividade definida | Média |
| `tenants/superadmin/dashboard.html` | `sa-kpi-grid` sem responsividade definida | Média |

---

## 9. Templates com Possíveis Erros de Django Template

| Template | Problema | Linha | Severidade |
|---|---|---|---|
| `components/sidebar.html` | Link de Contratos com `href=""` — URL vazia, inacessível | 28 | Alta |
| `tenants/usuarios_lista.html` | Referência a `{% url 'usuario_editar' %}` — template de destino ausente | 61 | Alta |
| `tenants/superadmin/dashboard.html` | Referência a `{% url 'superadmin_tenant_detalhe' %}` — template de destino ausente | 88 | Alta |
| `core/login.html` | Extends `base.html` — layout inclui `lg:pl-64` mesmo sem sidebar visível | — | Média |
| `financeiro/lancamentos.html` | Saldo calculado como `totais.receitas\|add:totais.despesas` — `add` soma, não subtrai; despesas negativas precisariam estar negativas no contexto | 33 | Média |

---

## 10. Templates com Alpine.js para Revisar

| Template | Padrão | Risco | Ação |
|---|---|---|---|
| `components/sidebar.html` | `x-data="{ openConfig: false }"` com `x-collapse` | `x-collapse` requer plugin Alpine.js Collapse não carregado no base.html | Adicionar plugin ou usar `x-show` simples |
| `components/sidebar.html` | `open: {% if request.resolver_match.url_name in 'config_conta,...' %}true{% else %}false{% endif %}` | Padrão correto — usa `{% if %}` para bool | OK |
| `inquilinos/form.html` | `x-data="{ tipo: '{{ form.tipo.value\|default:'pf' }}' }"` | String simples, sem risco de injection, valor controlado | OK |
| `contratos/form.html` | `x-data="{ indice: '{{ form.indice_reajuste.value\|default:'igpm' }}' }"` | Baixo risco (valor vem de choices fechadas), mas pode quebrar com aspas simples em valor inesperado | Usar `{% if %}` para maior segurança |
| `contratos/form.html` | `x-data="{ garantia: '{{ form.tipo_garantia.value\|default:'nenhuma' }}' }"` | Idem | Idem |

---

## 11. Templates Ausentes

| Template | Referenciado em | Status | Prioridade |
|---|---|---|---|
| `templates/tenants/usuario_editar.html` | `tenants/usuarios_lista.html:61` → `{% url 'usuario_editar' usuario.pk %}` | Ausente | **Alta** |
| `templates/tenants/superadmin/tenant_detalhe.html` | `tenants/superadmin/dashboard.html:88` → `{% url 'superadmin_tenant_detalhe' tenant.pk %}` | Ausente | **Alta** |

---

## 12. Componentes Recomendados

| Componente | Arquivo sugerido | Justificativa |
|---|---|---|
| Topbar | `components/topbar.html` | Topbar está inline no `base.html` — extração facilita manutenção |
| Card genérico | `components/card.html` | Padrão `bg-white rounded-xl border p-6 shadow-sm` repetido em ~30 templates |
| Cabeçalho de página | `components/page_header.html` | Padrão `título + subtítulo + botão de ação` repetido em todos os módulos |
| Campo de formulário | `components/form_field.html` | `label + input + error` repetido em todos os forms |
| Badge de status | `components/badge.html` | Badges condicionais por status repetidas em imóveis, inquilinos, contratos, financeiro |
| Tabela padrão | `components/table.html` | Estrutura de tabela com `thead bg-gray-50` repetida em 6+ templates |
| Estado vazio | `components/empty_state.html` | Padrão `icon + texto + link de criação` repetido em inquilinos, contratos, imóveis, financeiro |
| Botões padrão | `components/button.html` | Padrões de botão primário, outline, danger e ghost |
| Paginação | `components/pagination.html` | Paginação idêntica em inquilinos, contratos, imóveis, financeiro |
| Confirmar exclusão | `components/confirm_delete.html` | Padrão de confirmação idêntico em imoveis, inquilinos, financeiro |

---

## 13. Padronização Visual Recomendada

### Classe base para templates modernizados

Usar como referência os templates **já OK** do projeto:

```html
<!-- Card padrão -->
<div class="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">

<!-- Page header -->
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="text-2xl font-bold text-gray-900">Título</h1>
    <p class="text-sm text-gray-500 mt-0.5">Subtítulo</p>
  </div>
  <a href="..." class="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition">
    + Ação
  </a>
</div>

<!-- Badge de status (padrão a seguir) -->
<span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700">Ativo</span>

<!-- Botão primário -->
<button class="px-4 py-2 text-sm font-semibold rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition">

<!-- Botão outline -->
<button class="px-4 py-2 text-sm font-medium rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition">

<!-- Botão danger -->
<button class="px-4 py-2 text-sm font-semibold rounded-lg bg-red-600 text-white hover:bg-red-700 transition">
```

### Substituição de classes proprietárias

| Classe atual | Equivalente Tailwind |
|---|---|
| `btn-primary` | `inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition` |
| `btn-outline` | `rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition` |
| `btn-danger` / `btn-sm` | `px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-700 transition` |
| `card` + `card-body` | `bg-white rounded-xl border border-gray-200 p-6 shadow-sm` |
| `card-header` | `flex items-center justify-between border-b pb-4 mb-4` |
| `form-group` | `<div>` com `<label class="block text-sm font-medium text-gray-700 mb-1">` |
| `form-row` | `grid grid-cols-1 md:grid-cols-2 gap-4` |
| `page-header` | `flex items-center justify-between mb-6` |
| `badge badge-green` | `text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700` |
| `badge badge-red` | `text-xs font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-700` |
| `field-error` | `text-xs text-red-500 mt-1` |
| `help-text` | `text-xs text-gray-400 mt-1` |
| `back-link` | `inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600` |
| `table-responsive` | `overflow-x-auto` |
| `data-table` | `w-full text-sm` |
| `text-muted` | `text-gray-400` |
| `d-block` (Bootstrap) | `block` |

### Sidebar — reescrita necessária

O sidebar atual usa classes CSS próprias sem folha de estilos Tailwind. O padrão já existe em `base.html` com `bg-primary-800` — o sidebar deve usar:

```html
<!-- Nav link sidebar (padrão a seguir) -->
<a href="..." class="flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg text-primary-100 hover:bg-primary-700 transition
  {% if ativo %}bg-primary-700 text-white{% endif %}">
  <i class="ti ti-home text-base"></i>
  Imóveis
</a>
```

---

## 14. Lista de Tarefas por Prioridade

### Alta — impede uso ou quebra funcionalidade

- [ ] **Criar** `templates/tenants/usuario_editar.html` (template ausente, link quebrado em usuários_lista)
- [ ] **Criar** `templates/tenants/superadmin/tenant_detalhe.html` (template ausente, link quebrado no superadmin)
- [ ] **Reescrever** `components/sidebar.html` em Tailwind (incluído em todas as páginas autenticadas)
- [ ] **Corrigir** link de Contratos sem href em `components/sidebar.html:28`
- [ ] **Reescrever** `tenants/cadastro.html` em Tailwind (página pública de onboarding)
- [ ] **Reescrever** `tenants/usuarios_lista.html` em Tailwind (gestão de acesso ao sistema)
- [ ] **Reescrever** `tenants/superadmin/dashboard.html` em Tailwind (remover `d-block` Bootstrap)
- [ ] **Adicionar plugin** Alpine.js Collapse em `base.html` ou refatorar `x-collapse` do sidebar para `x-show`

### Média — funcional mas inconsistente visualmente

- [ ] **Reescrever** `tenants/config_conta.html` em Tailwind
- [ ] **Reescrever** `tenants/config_sicredi.html` em Tailwind
- [ ] **Reescrever** `tenants/config_whatsapp.html` em Tailwind
- [ ] **Reescrever** `tenants/config_templates_whatsapp.html` em Tailwind
- [ ] **Reescrever** `tenants/config_template_editar.html` em Tailwind
- [ ] **Reescrever** `tenants/usuario_convidar.html` em Tailwind
- [ ] **Reescrever** `tenants/cadastro_sucesso.html` em Tailwind
- [ ] **Corrigir** Alpine.js em `contratos/form.html` — usar `{% if %}` em vez de interpolação direta em `x-data`
- [ ] **Corrigir** `core/login.html` — ajustar layout base para não incluir padding de sidebar na tela de login
- [ ] **Verificar** cálculo de saldo em `financeiro/lancamentos.html:33` — `add` soma, não subtrai

### Baixa — polimento e padronização

- [ ] **Substituir** `bg-primary` / `text-primary` sem sufixo por `bg-primary-600` / `text-primary-600` em: inquilinos/lista.html, inquilinos/detalhe.html, contratos/lista.html, contratos/detalhe.html, financeiro/dashboard.html, financeiro/lancamentos.html, financeiro/lancamento_form.html, contratos/form.html
- [ ] **Criar** componente `components/pagination.html` (paginação repetida em 5 templates)
- [ ] **Criar** componente `components/empty_state.html` (estado vazio repetido em 5 templates)
- [ ] **Criar** componente `components/confirm_delete.html` (padrão repetido em 3 templates)
- [ ] **Criar** componente `components/page_header.html`
- [ ] **Mover** script de preview de cores de `config_conta.html` para `{% block extra_js %}`

---

## 15. Checklist Final para Execução

### Fase 1 — Bloqueadores (Alta prioridade)

- [ ] Criar `templates/tenants/usuario_editar.html`
- [ ] Criar `templates/tenants/superadmin/tenant_detalhe.html`
- [ ] Reescrever `components/sidebar.html` em Tailwind
- [ ] Corrigir href vazio no link de Contratos do sidebar

### Fase 2 — Módulo Tenants (Alta/Média)

- [ ] Reescrever `tenants/cadastro.html`
- [ ] Reescrever `tenants/cadastro_sucesso.html`
- [ ] Reescrever `tenants/config_conta.html`
- [ ] Reescrever `tenants/config_sicredi.html`
- [ ] Reescrever `tenants/config_whatsapp.html`
- [ ] Reescrever `tenants/config_templates_whatsapp.html`
- [ ] Reescrever `tenants/config_template_editar.html`
- [ ] Reescrever `tenants/usuarios_lista.html`
- [ ] Reescrever `tenants/usuario_convidar.html`
- [ ] Reescrever `tenants/superadmin/dashboard.html`

### Fase 3 — Correções menores (Baixa)

- [ ] Corrigir Alpine.js em `contratos/form.html`
- [ ] Corrigir layout de login
- [ ] Substituir `bg-primary` / `text-primary` sem sufixo nos módulos de domínio
- [ ] Verificar cálculo de saldo em `financeiro/lancamentos.html`

### Fase 4 — Componentização (Baixa)

- [ ] Criar `components/pagination.html`
- [ ] Criar `components/empty_state.html`
- [ ] Criar `components/confirm_delete.html`
- [ ] Criar `components/page_header.html`
- [ ] Refatorar templates para usar os novos componentes

---

*Relatório gerado por auditoria manual de todos os 46 templates HTML do projeto ImobCloud.*