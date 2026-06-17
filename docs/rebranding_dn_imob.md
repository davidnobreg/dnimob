# Rebranding: ImobCloud → DN Imob
**Status:** Auditoria concluída — aguardando aprovação para executar  
**Data:** 2026-06-17  
**Domínio prod decidido:** `imob.dnsoftware.com.br`

---

## Nova identidade

| Campo | Valor |
|---|---|
| Empresa | DN Software (`https://www.dnsoftware.com.br`) |
| Produto | DN Imob (`https://imob.dnsoftware.com.br`) |
| Slogan (escolher) | "Gestão inteligente de locações" / "Contratos, cobranças e aluguéis em um só lugar" / "O controle completo da sua imobiliária" |
| Rodapé | `DN Imob © {{ ano }} — Uma solução DN Software.` |

---

## Inventário de ocorrências

### Templates HTML

| Arquivo | Linha | Texto atual | Sugestão |
|---|---|---|---|
| `templates/base.html` | 10 | `{% block title %}ImobCloud{% endblock %}` | `DN Imob` |
| `templates/base.html` | 202 | `{% block mobile_title %}ImobCloud{% endblock %}` | `DN Imob` |
| `templates/base.html` | 244 | `default:"ImobCloud"` | `default:"DN Imob"` |
| `templates/base.html` | 321 | `ImobCloud &copy;` (footer) | `DN Imob &copy; {% now "Y" %} — Uma solução DN Software.` |
| `templates/base_public.html` | 8 | `<title>ImobCloud</title>` | `DN Imob` |
| `templates/base_public.html` | 14 | meta description com "ImobCloud" | atualizar com slogan escolhido |
| `templates/base_public.html` | 104 | `Imob<span>Cloud</span>` (logo navbar) | `DN<span class="text-primary-700">Imob</span>` |
| `templates/base_public.html` | 107 | tagline "Gestão imobiliária inteligente" | manter ou trocar pelo slogan escolhido |
| `templates/base_public.html` | 257 | `&copy; {% now "Y" %} ImobCloud.` (footer) | `&copy; {% now "Y" %} DN Imob — Uma solução DN Software.` |
| `templates/components/sidebar.html` | 61 | `default:"ImobCloud"` | `default:"DN Imob"` |
| `templates/tenants/acesso_bloqueado.html` | 102 | `contato@dnsoftware.com.br` | `contato@dnsoftware.com.br` (ou definir e-mail oficial) |
| `templates/tenants/aguardando.html` | 2 | `Preparando sua conta — ImobCloud` | `Preparando sua conta — DN Imob` |
| `templates/tenants/cadastro_sucesso.html` | 2 | `Conta criada — ImobCloud` | `Conta criada — DN Imob` |
| `templates/tenants/cadastro.html` | 3 | `Criar conta — ImobCloud` | `Criar conta — DN Imob` |
| `templates/tenants/cadastro.html` | 36 | "Crie sua conta no ImobCloud" | "Crie sua conta no DN Imob" |
| `templates/tenants/cadastro.html` | 142 | `.imobcloud.com.br` (sufixo subdomínio) | `.imob.dnsoftware.com.br` |
| `templates/tenants/cadastro.html` | 147 | "subdominio.imobcloud.com.br" | "subdominio.imob.dnsoftware.com.br" |
| `templates/tenants/cadastro.html` | 330 | "ImobCloud" em CTA | `DN Imob` |
| `templates/tenants/cadastro.html` | 395 | `contato@imobcloud.com.br` | `contato@dnsoftware.com.br` |
| `templates/tenants/landing.html` | 53 | "Dashboard ImobCloud" | "Dashboard DN Imob" |
| `templates/tenants/landing.html` | 279 | "teste o ImobCloud gratuitamente" | "teste o DN Imob gratuitamente" |
| `templates/tenants/login_public.html` | 3 | `Acessar sua imobiliária — ImobCloud` | `Acessar sua imobiliária — DN Imob` |
| `templates/tenants/login_public.html` | 55 | `.imobcloud.com.br` | `.imob.dnsoftware.com.br` |
| `templates/tenants/superadmin/dashboard.html` | 2 | `Superadmin — ImobCloud` | `Superadmin — DN Imob` |
| `templates/tenants/superadmin/dashboard.html` | 7 | `⚡ ImobCloud` | `⚡ DN Imob` |

### Templates PDF (rodapés)

| Arquivo | Linha | Texto atual | Sugestão |
|---|---|---|---|
| `templates/relatorios/pdf/inadimplencia.html` | 39 | `ImobCloud` | `DN Imob` |
| `templates/relatorios/pdf/imoveis.html` | 34 | `ImobCloud` | `DN Imob` |
| `templates/relatorios/pdf/extrato.html` | 52 | `— ImobCloud` | `— DN Imob` |
| `templates/relatorios/pdf/contratos.html` | 34 | `ImobCloud` | `DN Imob` |
| `templates/relatorios/extrato_pdf.html` | 52 | `— ImobCloud` | `— DN Imob` |

### E-mails transacionais

| Arquivo | Linha | Texto atual | Sugestão |
|---|---|---|---|
| `templates/registration/password_reset_email.txt` | 3 | "sua conta no ImobCloud" | "sua conta no DN Imob" |
| `templates/registration/password_reset_email.txt` | 14 | "Equipe ImobCloud" | "Equipe DN Imob" |

### Settings Python

| Arquivo | Linha | Texto atual | Sugestão |
|---|---|---|---|
| `config/settings/base.py` | 43 | `TENANT_BASE_DOMAIN = 'imobcloud.com.br'` | `'imob.dnsoftware.com.br'` |
| `config/settings/base.py` | 111–113 | comentários com `imobcloud.com.br` | atualizar comentários |
| `config/settings/base.py` | 257 | `DEFAULT_FROM_EMAIL = 'noreply@imobcloud.com.br'` | `'DN Imob <noreply@imob.dnsoftware.com.br>'` |
| `config/settings/base.py` | 281 | `SITE_BASE_URL = 'https://imobcloud.com.br'` | `'https://imob.dnsoftware.com.br'` |
| `config/settings/dev.py` | 107 | `'ImobCloud <noreply@imobcloud.com.br>'` | `'DN Imob <noreply@imob.dnsoftware.com.br>'` |
| `config/settings_fase2_patch.py` | 26 | `BASE_DOMAIN = 'imobcloud.com.br'` | arquivo é patch histórico — atualizar ou arquivar |

### Código Python

| Arquivo | Linha | Texto atual | Sugestão |
|---|---|---|---|
| `apps/core/admin.py` | 11 | `'Perfil ImobCloud'` | `'Perfil DN Imob'` |
| `apps/tenants/views.py` | 98 | `getattr(settings, 'IMOBCLOUD_BASE_DOMAIN', 'localhost:8000')` | unificar com `BASE_DOMAIN`; renomear setting ou manter alias |
| `apps/tenants/services.py` | 147 | `getattr(settings, 'BASE_DOMAIN', 'imobcloud.com.br')` | default → `'imob.dnsoftware.com.br'` |
| `apps/tenants/forms.py` | 51 | `help_text='Ex: alpha → alpha.imobcloud.com.br'` | `alpha.imob.dnsoftware.com.br` |
| `apps/core/management/commands/test_sentry.py` | 37, 51 | `[ImobCloud]` prefixo nos erros de teste | `[DN Imob]` |

### Variáveis de ambiente

| Arquivo | Campo | Valor atual | Sugestão |
|---|---|---|---|
| `.env` | `DEFAULT_FROM_EMAIL` | `'ImobCloud <onboarding@resend.dev>'` | `'DN Imob <noreply@imob.dnsoftware.com.br>'` |
| `.env.example` | `DEFAULT_FROM_EMAIL` | `ImobCloud <noreply@...>` | `DN Imob <noreply@imob.dnsoftware.com.br>` |
| `.env.example` | `AWS_STORAGE_BUCKET_NAME` | `imobcloud-media` | `dnimob-media` |
| `.env.example` | `AWS_BACKUP_BUCKET` | `imobcloud-backups` | `dnimob-backups` |
| `.env.example` | `BASE_DOMAIN` | `imobcloud.com.br` | `imob.dnsoftware.com.br` |
| `.env.example` | `SITE_BASE_URL` | `https://imobcloud.com.br` | `https://imob.dnsoftware.com.br` |

---

## Assets visuais — Inventário

**Nenhum arquivo de imagem/ícone encontrado no repositório.** O logo atual é puramente textual (HTML + Tailwind em `base_public.html:104`):

```html
Imob<span class="text-primary-700">Cloud</span>
```

Favicon: **não configurado** (`<link rel="icon">` ausente nos templates base).

### Checklist de assets a criar para DN Imob

- [ ] Logo SVG (variantes: completa, símbolo, horizontal, negativa)
- [ ] Favicon `.ico` / `.png` 32×32, 64×64, 192×192, 512×512
- [ ] `apple-touch-icon.png` 180×180
- [ ] `og:image` para compartilhamento social (1200×630)
- [ ] Logo para rodapé de e-mail
- [ ] Logo para PDFs (rodapé de relatórios e contratos)

---

## Banco de dados — Análise

### WhatsApp Templates (`TemplateWhatsApp`)

Os 13 templates padrão definidos em `apps/tenants/services.py:TEMPLATES_PADRAO` **não contêm "ImobCloud"** — usam variáveis dinâmicas como `{nome_imobiliaria}`. Tenants já provisionados com os defaults estão limpos.

**Risco:** templates editados manualmente pelo admin da imobiliária podem ter texto customizado com "ImobCloud". Não é possível verificar sem acesso direto ao banco.

### Outros campos potenciais no banco

| Modelo | Campo | Risco | Ação sugerida |
|---|---|---|---|
| `Tenant` | `nome` | Baixo — nome da imobiliária, não da plataforma | Não alterar |
| `TemplateWhatsApp` | `texto` | Médio — se editado manualmente | Script de UPDATE com LIKE '%ImobCloud%' |
| `Configuracao` / `ConfiguracaoSistema` (se existir) | qualquer campo `nome_sistema` | Verificar se modelo existe | — |
| Emails enviados históricos | — | Imutável — não tratar | — |

### Plano de migração de dados (não executar agora)

```sql
-- Inspecionar templates com "ImobCloud" hardcoded (rodar por schema de tenant)
SELECT id, evento, texto FROM whatsapp_templatewhatsapp WHERE texto ILIKE '%ImobCloud%';

-- Se encontrar: substituir (aprovação manual antes)
UPDATE whatsapp_templatewhatsapp
SET texto = REPLACE(texto, 'ImobCloud', 'DN Imob')
WHERE texto ILIKE '%ImobCloud%';
```

---

## Riscos identificados

| # | Risco | Severidade | Mitigação |
|---|---|---|---|
| R1 | Domínio `imob.dnsoftware.com.br` ainda não apontado para o servidor | Alta | Configurar DNS antes de alterar `BASE_DOMAIN` em prod |
| R2 | Tenants existentes têm domain `*.imobcloud.com.br` salvo no banco (`Domain` model) | Alta | **Não alterar schemas** (já excluído do escopo). Domains precisam de migração de dados cuidadosa — executar separadamente com janela de manutenção |
| R3 | `IMOBCLOUD_BASE_DOMAIN` em `views.py:98` é um setting diferente de `BASE_DOMAIN` — inconsistência já presente | Médio | Unificar para `BASE_DOMAIN` nos dois pontos |
| R4 | S3 buckets com nome `imobcloud-*` já podem ter objetos em prod | Médio | Criar novos buckets `dnimob-*`, copiar objetos, atualizar env var, testar antes de remover antigos |
| R5 | `config/settings_fase2_patch.py` com `BASE_DOMAIN` hardcoded pode ser importado acidentalmente | Baixo | Arquivar ou marcar como obsoleto |
| R6 | Resend sender domain verificado é `resend.dev` (temporário) — precisa verificar `imob.dnsoftware.com.br` no Resend | Alto (e-mail) | Verificar domínio no painel Resend antes de alterar `DEFAULT_FROM_EMAIL` |

---

## Restrição crítica (reforço)

`schema_name` dos tenants usa prefixo `imob_` (ex: `imob_alpha`). Isso é identificador técnico interno — **não alterar** como parte deste rebranding. A lógica de geração do `schema_name` em `services.py` permanece intacta.

---

## Plano de rollout

### Fase A — Sem impacto em prod (fazer primeiro)
1. Aprovar slogan (escolher 1 dos 3)
2. Criar assets visuais (logo, favicon, og:image)
3. Verificar domínio `imob.dnsoftware.com.br` no Resend
4. Configurar DNS: `imob.dnsoftware.com.br` → servidor prod

### Fase B — Substituições de texto/código (zero risco de quebra)
5. Aplicar todas as substituições em **templates**, **settings**, **código Python**, **e-mails**
6. Testar: landing page, cadastro, sidebar, PDFs, e-mail de reset de senha
7. Deploy para prod com `BASE_DOMAIN` ainda apontando para o domínio antigo

### Fase C — Troca de domínio (janela de manutenção)
8. Atualizar `BASE_DOMAIN` → `imob.dnsoftware.com.br` em prod (env var no Portainer)
9. Se necessário: migrar registros `Domain` no banco para o novo domínio de tenants existentes
10. Configurar Item 4 (SSL) no NPM com `*.imob.dnsoftware.com.br`

### Fase D — Limpeza
11. Inspecionar e migrar templates WhatsApp no banco (script SQL acima)
12. Migrar S3 buckets (`imobcloud-*` → `dnimob-*`) se necessário
13. Remover aliases/referências residuais

---

## Checklist final (antes de executar cada fase)

### Fase A
- [ ] Slogan escolhido e registrado
- [ ] Assets criados (logo + favicon + og:image)
- [ ] Domínio `imob.dnsoftware.com.br` verificado no Resend
- [ ] DNS propagado (verificar com `dig imob.dnsoftware.com.br`)

### Fase B — Arquivos a alterar (43 ocorrências em 18 arquivos)
- [ ] `templates/base.html` (4 ocorrências)
- [ ] `templates/base_public.html` (4 ocorrências incluindo logo navbar)
- [ ] `templates/components/sidebar.html` (1)
- [ ] `templates/tenants/acesso_bloqueado.html` (1)
- [ ] `templates/tenants/aguardando.html` (1)
- [ ] `templates/tenants/cadastro_sucesso.html` (1)
- [ ] `templates/tenants/cadastro.html` (5)
- [ ] `templates/tenants/landing.html` (2)
- [ ] `templates/tenants/login_public.html` (2)
- [ ] `templates/tenants/superadmin/dashboard.html` (2)
- [ ] `templates/relatorios/pdf/inadimplencia.html` (1)
- [ ] `templates/relatorios/pdf/imoveis.html` (1)
- [ ] `templates/relatorios/pdf/extrato.html` (1)
- [ ] `templates/relatorios/pdf/contratos.html` (1)
- [ ] `templates/relatorios/extrato_pdf.html` (1)
- [ ] `templates/registration/password_reset_email.txt` (2)
- [ ] `config/settings/base.py` (4)
- [ ] `config/settings/dev.py` (1)
- [ ] `apps/core/admin.py` (1)
- [ ] `apps/tenants/views.py` (1)
- [ ] `apps/tenants/services.py` (1)
- [ ] `apps/tenants/forms.py` (1)
- [ ] `apps/core/management/commands/test_sentry.py` (2)
- [ ] `.env` (1)
- [ ] `.env.example` (5)

### Fase C
- [ ] `BASE_DOMAIN` atualizado em prod (Portainer env var)
- [ ] NPM Proxy Host configurado para `*.imob.dnsoftware.com.br`
- [ ] SSL wildcard ativo (Item 4)
- [ ] Testar acesso `imob.dnsoftware.com.br` (landing)
- [ ] Testar acesso `alpha.imob.dnsoftware.com.br` (tenant)

### Fase D
- [ ] Inspecionar banco: templates WhatsApp com "ImobCloud" hardcoded
- [ ] Executar UPDATE de dados (script SQL acima) após aprovação
- [ ] Buckets S3 migrados (se aplicável)
- [ ] `config/settings_fase2_patch.py` arquivado ou marcado obsoleto
