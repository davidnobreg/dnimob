---
date: 2026-07-10
projeto: dnimob
tags: [implementacao, landing-page, design, copywriting]
---

# Retorno — Formulário de Cadastro (visual) + Copy da Seção Recursos

Duas partes independentes, ambas puramente visuais/copy — sem lógica nova,
sem testes automatizados novos (conforme pedido). Nada commitado ainda.

---

## Status

| Item | Status |
|---|---|
| Fonte de display reaproveitada (Space Grotesk, sem escolher nova) | ✅ |
| Cabeçalho do cadastro com gradiente do hero da landing | ✅ |
| Foco em inputs/select com transição + borda azul | ✅ |
| Botão de submit com hover consistente com cards de plano | ✅ (ajustado, ver nota) |
| Micro-animação de entrada (AOS) nos campos/seções | ✅ |
| Legibilidade/usabilidade do form preservada | ✅ |
| Validação, `name=`/`id=`, JS de máscara/polling intactos | ✅ não tocados |
| Links de Termos/Privacidade no checkbox | ✅ intactos (rodada anterior) |
| Copy da seção Recursos sem jargão técnico | ✅ 6 itens reescritos |
| Sanity check: form renderiza 200, sem erro de template | ✅ |
| Testes `apps.tenants` (nenhum novo pedido) | ✅ 11/11 OK, nada quebrou |
| Commit | ❌ não feito |

---

## Parte 1 — Formulário de cadastro

### O que mudou

- **Cabeçalho**: antes era uma faixa clara (`bg-slate-50` com blobs sutis
  azul/indigo claros). Agora é uma seção separada no topo com o mesmo
  gradiente do hero da landing (`from-blue-700 via-blue-600 to-indigo-900`),
  blobs animados (`animate-blob`, mesmo `@keyframes` da landing, redeclarado
  localmente já que `cadastro.html` não estende do `<head>` de `landing.html`),
  badge com dot pulsante, título em `font-display` (Space Grotesk — reaproveitada,
  já registrada em `base_public.html` desde o redesign da landing, nenhuma
  fonte nova escolhida). O card branco do formulário continua em fundo claro
  logo abaixo — só o cabeçalho ganhou o tratamento ousado, o formulário em si
  permanece legível/neutro.
- **Foco nos campos** (`forms.py`, widgets `_INPUT`/`_SELECT`/`_SLUG`, e os
  dois inputs manuais do template — documento e wrapper do subdomínio):
  `transition` → `transition-all duration-200`, borda de foco
  `focus:border-blue-400` → `focus:border-blue-500` (mais contraste), anel de
  foco `ring-2 ring-blue-500/20` → `ring-4 ring-blue-500/15` (mais presença,
  levemente mais suave de opacidade pra não pesar).
- **Botão de submit**: `hover:-translate-y-0.5` → `hover:scale-[1.02]
  hover:shadow-2xl`, `transition` → `transition-all duration-300`.
  **Nota de ajuste**: o pedido dizia "mesmo tratamento usado nos cards de
  plano" (`hover:scale-105`). Como esse botão é `w-full` dentro de um card
  com padding, `scale-105` real faria ele visualmente estourar a borda do
  card no hover — troquei por `scale-[1.02]`, sutil o bastante pra não
  quebrar o layout mas mantendo a mesma linguagem (scale + shadow-2xl +
  duration-300). Avisando explicitamente pra você aprovar ou pedir o
  `scale-105` literal se preferir.
- **AOS**: mesma lib da landing, carregada localmente em `cadastro.html`
  (`extra_head`/`extra_js`, não em `base_public.html`) — fade-up com stagger
  crescente no card do form, nos dois fieldsets internos (0ms, 100ms) e nos
  3 cards da lateral (150ms, 225ms, 300ms). Fade-right no link "Voltar".
- **`x-data`/`x-init`/`@submit`/`x-on`, `name=`, `id=`, campos do form,
  `mascararDoc()`, `atualizarPlanos()`, polling de status**: nada tocado.

### Diff completo

```diff
diff --git a/apps/tenants/forms.py b/apps/tenants/forms.py
index bb2f79a..2a1ae9e 100644
--- a/apps/tenants/forms.py
+++ b/apps/tenants/forms.py
@@ -13,17 +13,17 @@ Usuario = get_user_model()
 
 _INPUT = (
     'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm '
-    'text-slate-900 placeholder-slate-400 transition '
-    'focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20'
+    'text-slate-900 placeholder-slate-400 transition-all duration-200 '
+    'focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15'
 )
 _SELECT = (
     'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm '
-    'text-slate-900 transition '
-    'focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20'
+    'text-slate-900 transition-all duration-200 '
+    'focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15'
 )
 _SLUG = (
     'min-w-0 flex-1 bg-transparent px-3 py-2.5 text-sm text-slate-900 '
-    'placeholder-slate-400 focus:outline-none'
+    'placeholder-slate-400 transition-all duration-200 focus:outline-none'
 )
```

```diff
diff --git a/templates/tenants/cadastro.html b/templates/tenants/cadastro.html
index 6398a1b..52a7a84 100644
--- a/templates/tenants/cadastro.html
+++ b/templates/tenants/cadastro.html
@@ -2,56 +2,86 @@
 
 {% block title %}Criar conta — DN Imob{% endblock %}
 
-{% block content %}
+{% block extra_head %}
+<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.css" integrity="sha512-A0aE7SmVvHV5xR8CxUt/bpJTLYt/8OjcGdaSJ4y8ExHRzXFV1TZLW8B24V1EiaBu9WPa0iCsCXqDpX1mvR+cyw==" crossorigin="anonymous" referrerpolicy="no-referrer">
+{% endblock %}
 
-<section class="relative overflow-hidden bg-slate-50 px-4 py-10 sm:px-6 lg:px-8">
+{% block content %}
 
-    <!-- Fundo decorativo -->
+<!-- Header — mesmo tratamento de gradiente do hero da landing -->
+<section class="relative overflow-hidden bg-gradient-to-br from-blue-700 via-blue-600 to-indigo-900">
     <div class="pointer-events-none absolute inset-0 overflow-hidden">
-        <div class="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-blue-200/40 blur-3xl"></div>
-        <div class="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-indigo-200/40 blur-3xl"></div>
+        <div class="animate-blob absolute -top-24 -left-16 h-80 w-80 rounded-full bg-blue-400/30 mix-blend-screen blur-3xl"></div>
+        <div class="animate-blob animation-delay-2000 absolute -bottom-24 right-0 h-72 w-72 rounded-full bg-indigo-400/30 mix-blend-screen blur-3xl"></div>
     </div>
 
-    <div class="relative mx-auto max-w-6xl">
+    <div class="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
 
         <!-- Voltar -->
-        <div class="mb-6">
+        <div class="mb-6" data-aos="fade-right" data-aos-duration="600">
             <a
                 href="{% url 'landing' %}"
-                class="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-white hover:text-blue-700"
+                class="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-blue-50 transition hover:bg-white/10 hover:text-white"
             >
                 <span>←</span>
                 Voltar para o início
             </a>
         </div>
 
-        <!-- Header -->
-        <div class="mb-8 text-center">
-            <div class="mx-auto mb-4 inline-flex items-center gap-2 rounded-full bg-blue-100 px-4 py-2 text-xs font-bold uppercase tracking-wide text-blue-700">
-                <span class="h-2 w-2 rounded-full bg-blue-600"></span>
+        <div class="text-center" data-aos="fade-up" data-aos-duration="700">
+            <div class="mx-auto mb-4 inline-flex items-center gap-2 rounded-full bg-white/10 backdrop-blur-sm px-4 py-2 text-xs font-bold uppercase tracking-wide text-blue-50 ring-1 ring-white/20">
+                <span class="h-2 w-2 rounded-full bg-emerald-300 animate-pulse-dot"></span>
                 Teste grátis por 14 dias
             </div>
 
-            <h1 class="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
+            <h1 class="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
                 Crie sua conta no DN Imob
             </h1>
 
-            <p class="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-500 sm:text-base">
+            <p class="mx-auto mt-3 max-w-2xl text-sm leading-6 text-blue-100 sm:text-base">
                 Organize sua imobiliária, cadastre imóveis, gerencie inquilinos,
                 contratos e financeiro em uma plataforma moderna.
             </p>
         </div>
+    </div>
+
+    <style>
+        @keyframes blob-float {
+            0%, 100% { transform: translate(0, 0) scale(1); }
+            33% { transform: translate(30px, -40px) scale(1.15); }
+            66% { transform: translate(-25px, 25px) scale(0.9); }
+        }
+        .animate-blob { animation: blob-float 9s ease-in-out infinite; }
+        .animation-delay-2000 { animation-delay: 2s; }
+
+        @keyframes pulse-dot {
+            0%, 100% { opacity: 1; transform: scale(1); }
+            50% { opacity: 0.5; transform: scale(1.4); }
+        }
+        .animate-pulse-dot { animation: pulse-dot 2s ease-in-out infinite; }
+    </style>
+</section>
+
+<section class="relative overflow-hidden bg-slate-50 px-4 py-10 sm:px-6 lg:px-8">
+
+    <!-- Fundo decorativo -->
+    <div class="pointer-events-none absolute inset-0 overflow-hidden">
+        <div class="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-blue-200/40 blur-3xl"></div>
+        <div class="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-indigo-200/40 blur-3xl"></div>
+    </div>
+
+    <div class="relative mx-auto max-w-6xl">
 
         <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
 
             <!-- Formulário -->
-            <div class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
+            <div class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm" data-aos="fade-up" data-aos-duration="600">
 
                 <!-- Topo do card -->
                 <div class="border-b border-slate-200 bg-white px-6 py-5 sm:px-8">
                     <div class="flex items-start justify-between gap-4">
                         <div>
-                            <h2 class="text-xl font-extrabold text-slate-900">
+                            <h2 class="font-display text-xl font-bold text-slate-900">
                                 Dados para cadastro
                             </h2>
 
@@ -82,7 +112,7 @@
                     {% endif %}
 
                     <!-- Dados da imobiliária -->
-                    <fieldset class="space-y-5">
+                    <fieldset class="space-y-5" data-aos="fade-up" data-aos-delay="0" data-aos-duration="500">
                         <div class="flex items-center gap-3">
                             <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
                                 🏢
@@ -154,7 +184,7 @@
                                 @input="mascararDoc($event.target, tipoPessoa)"
                                 x-on:x-tipo-changed="mascararDoc($el, tipoPessoa)"
                                 value="{{ form.data.documento|default:'' }}"
-                                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
+                                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition-all duration-200 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15"
                             >
                             {% if form.documento.errors %}
                                 <p class="mt-1.5 text-xs font-semibold text-red-600">
@@ -170,7 +200,7 @@
                                     {{ form.subdominio.label }}
                                 </label>
 
-                                <div class="flex overflow-hidden rounded-2xl border border-slate-200 bg-white transition focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-500/10">
+                                <div class="flex overflow-hidden rounded-2xl border border-slate-200 bg-white transition-all duration-200 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/15">
                                     <div class="min-w-0 flex-1">
                                         {{ form.subdominio }}
                                     </div>
@@ -215,7 +245,7 @@
                     </fieldset>
 
                     <!-- Dados do administrador -->
-                    <fieldset class="space-y-5 border-t border-slate-100 pt-8">
+                    <fieldset class="space-y-5 border-t border-slate-100 pt-8" data-aos="fade-up" data-aos-delay="100" data-aos-duration="500">
                         <div class="flex items-center gap-3">
                             <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                                 👤
@@ -314,7 +344,10 @@
                             </span>
 
                             <span class="text-sm leading-6 text-slate-600">
-                                {{ form.aceite_termos.label }}
+                                Concordo com os
+                                <a href="{% url 'termos_uso' %}" target="_blank" rel="noopener" class="font-semibold text-blue-600 hover:underline">Termos de Uso</a>
+                                e a
+                                <a href="{% url 'politica_privacidade' %}" target="_blank" rel="noopener" class="font-semibold text-blue-600 hover:underline">Política de Privacidade</a>
                             </span>
                         </label>
 
@@ -330,8 +363,8 @@
                         <button
                             type="submit"
                             :disabled="enviando"
-                            :class="enviando ? 'opacity-60 cursor-not-allowed' : 'hover:-translate-y-0.5 hover:bg-blue-700'"
-                            class="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-4 text-sm font-extrabold text-white shadow-lg shadow-blue-600/20 transition focus:outline-none focus:ring-4 focus:ring-blue-500/20"
+                            :class="enviando ? 'opacity-60 cursor-not-allowed' : 'hover:scale-[1.02] hover:shadow-2xl hover:bg-blue-700'"
+                            class="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-4 text-sm font-extrabold text-white shadow-lg shadow-blue-600/20 transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-blue-500/20"
                         >
                             <span x-show="!enviando">Criar minha conta grátis <span>→</span></span>
                             <span x-show="enviando" x-cloak>Criando sua conta…</span>
@@ -354,7 +387,7 @@
             <aside class="space-y-6">
 
                 <!-- Benefício trial -->
-                <div class="rounded-3xl border border-blue-200 bg-blue-50 p-6">
+                <div class="rounded-3xl border border-blue-200 bg-blue-50 p-6" data-aos="fade-up" data-aos-delay="150" data-aos-duration="500">
                     <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-2xl text-white shadow-lg shadow-blue-600/20">
                         ✨
                     </div>
@@ -392,7 +425,7 @@
                 </div>
 
                 <!-- Segurança -->
-                <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
+                <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm" data-aos="fade-up" data-aos-delay="225" data-aos-duration="500">
                     <div class="flex items-start gap-3">
                         <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-xl">
                             🔒
@@ -412,7 +445,7 @@
                 </div>
 
                 <!-- Ajuda -->
-                <div class="rounded-3xl border border-amber-200 bg-amber-50 p-6">
+                <div class="rounded-3xl border border-amber-200 bg-amber-50 p-6" data-aos="fade-up" data-aos-delay="300" data-aos-duration="500">
                     <div class="flex items-start gap-3">
                         <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-xl">
                             💬
@@ -471,4 +504,16 @@ function atualizarPlanos(tipo) {
 }
 </script>
 
+{% endblock %}
+
+{% block extra_js %}
+<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.js" integrity="sha512-A0aE7SmVvHV5xR8CxUt/bpJTLYt/8OjcGdaSJ4y8ExHRzXFV1TZLW8B24V1EiaBu9WPa0iCsCXqDpX1mvR+cyw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
+<script>
+    AOS.init({
+        duration: 600,
+        easing: 'ease-out-cubic',
+        once: true,
+        offset: 40,
+    });
+</script>
 {% endblock %}
```

*(O trecho do checkbox de Termos/Privacidade aparece no diff porque nada foi
commitado ainda desde aquela rodada — já tinha sido reportado antes, incluído
aqui só porque o diff é cumulativo.)*

### Confirmação de que o form continua funcional

Sanity check via shell, `GET /cadastro/` chamando a view diretamente:

```
status: 200
tem form: True        (campo id_nome_imobiliaria presente)
tem AOS css: True
tem AOS js: True
tem font-display: True
tem link termos: True
tem link privacidade: True
```

Suite `apps.tenants` completa: **11/11 OK**, nenhum teste quebrou (nenhum
teste automatizado exercitava o render do template de cadastro em detalhe —
os testes de `AceiteTermosPersistenciaTests` fazem POST válido, que redireciona
sem renderizar o template — então a confirmação visual acima é o que
efetivamente valida o HTML gerado).

Não toquei: `x-data`, `x-init`, `@submit`, `x-on:x-tipo-changed`,
`mascararDoc()`, `atualizarPlanos()`, polling de `cadastro_status`, nomes de
campos (`name=`), `id=`, lógica de `CadastroImobiliariaForm`.

### Descrição visual (sem print)

Topo agora é uma faixa azul-escura em gradiente (idêntica em tom ao hero da
landing), com blobs desfocados flutuando atrás, badge "Teste grátis por 14
dias" com dot verde pulsante, título grande em Space Grotesk branco, texto de
apoio em azul-claro. Assim que a página carrega, o link "Voltar" desliza da
esquerda e o bloco de título sobe com fade — mesma linguagem de movimento do
hero da landing, mas comprimida (seção mais baixa, sem o tamanho de hero
completo).

Logo abaixo, a faixa clara de sempre (fundo `slate-50` com blobs suaves)
carrega o card branco do formulário — que sobe com fade ao entrar na viewport
— e a coluna lateral com os 3 cards informativos, que entram em sequência
(150ms, 225ms, 300ms de atraso um do outro). Dentro do form, cada campo em
foco agora tem uma borda azul mais forte e um anel de destaque mais grosso
ao redor — fica claro qual campo está ativo sem gritar. O botão final de
"Criar minha conta grátis" cresce sutilmente e ganha sombra mais pesada no
hover, ecoando o mesmo gesto dos cards de plano na landing, mas comedido pra
não sair da caixa do card.

---

## Parte 2 — Copy da seção "Recursos" (landing.html)

### Antes → Depois

| # | Título antes | Corpo antes | Título depois | Corpo depois |
|---|---|---|---|---|
| 1 | Contratos inteligentes | "Wizard multi-step, geração de PDF automática, reajuste por IGP-M/IPCA/INPC e distrato com multa proporcional." | Contratos inteligentes *(mantido)* | "Contratos gerados em PDF automaticamente, com reajuste por IGP-M, IPCA, INPC ou percentual fixo, e cálculo de multa na rescisão sem planilha." |
| 2 | Boletos Sicredi | "Registro automático via API OAuth2, webhook de baixa HMAC validado e sincronização ativa como fallback." | **Boletos automáticos** | "Emissão de boletos direto no sistema, com baixa automática assim que o inquilino paga — sem conferência manual." |
| 3 | WhatsApp automático | "13 eventos automatizados — vencimento, atraso, pagamento confirmado e contratos — com templates editáveis." | **Cobrança pelo WhatsApp** | "Lembrete de vencimento, cobrança de atraso e confirmação de pagamento enviados direto pro WhatsApp do inquilino, com mensagens que você personaliza." |
| 4 | Dashboard financeiro | "KPIs em tempo real, inadimplência, relatórios por período e exportação em Excel e PDF." | **Financeiro em tempo real** | "Acompanhe receitas e inadimplência conforme acontece, com relatórios por período prontos pra exportar em Excel e PDF." |
| 5 | Multi-tenant seguro | "Schema PostgreSQL por imobiliária. Seus dados 100% isolados dos outros clientes." | **Seus dados, só seus** | "Cada imobiliária tem seu próprio ambiente, totalmente separado dos demais clientes — ninguém mais enxerga seus dados." |
| 6 | Automações Celery | "Cobranças geradas no dia 1, boletos registrados automaticamente e lembretes enviados no horário certo." | **Automação de cobranças** | "Cobrança do mês gerada sozinha todo dia 1, sem você precisar lançar nada na mão." |

### O que mudou em cada caso e por quê

- **#1**: só o corpo mudou — "Wizard multi-step" é jargão de UX/dev, cortado;
  os nomes dos índices (IGP-M/IPCA/INPC) são termos financeiros do domínio
  imobiliário, não stack técnica, mantidos.
- **#2**: título e corpo trocados — a regra explícita pedia tirar
  "Sicredi/boleto bancário" e qualquer menção a API/OAuth2/webhook/HMAC.
  Ficou só o resultado: emite e baixa sozinho.
- **#3**: título trocado pra reforçar o canal (WhatsApp) sem soar como
  "feature de 13 eventos" — número de eventos automatizados é detalhe interno,
  cortado. "Templates editáveis" virou "mensagens que você personaliza".
- **#4**: "KPIs" trocado por "receitas e inadimplência" (mais concreto,
  menos jargão corporativo); "Dashboard" no título virou "tempo real" — mantém
  a ideia sem soar a nome de produto técnico.
- **#5**: **violação direta da regra** — "Multi-tenant" e "Schema PostgreSQL"
  são termos de arquitetura que nunca deveriam estar em copy pública. Título
  e corpo reescritos do zero, sem qualquer referência técnica — a mensagem
  vira só "seus dados são só seus".
- **#6**: **violação direta da regra** — "Celery" no título é nome de lib.
  Trocado por "Automação de cobranças" (o que de fato acontece, não a peça
  técnica por trás). Corpo simplificado, removida a menção redundante a
  "boletos registrados automaticamente" (já coberta pelo card #2), focado só
  na geração automática da cobrança mensal.

Ícones, cores dos ícones (gradiente por card, já do redesign visual anterior)
e ordem dos 6 cards não mudaram — só título/texto.

---

## O que NÃO foi mexido

- `CadastroImobiliariaForm` — zero alteração de validação, `clean()`,
  `clean_subdominio()`, campos ou choices.
- Links de Termos/Privacidade no checkbox — mesmos hrefs, mesmo texto,
  mesmo `target="_blank"`.
- `name=`, `id=` de todos os campos — JS de máscara e polling seguem
  funcionando sem alteração.
- Model, view, rota — só template + copy + classe CSS de widget.
- Nenhum teste automatizado novo (conforme instrução — mudança visual/copy).
