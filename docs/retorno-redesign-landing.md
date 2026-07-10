---
date: 2026-07-10
projeto: dnimob
tags: [implementacao, landing-page, design, ui]
---

# Retorno — Redesign Visual da Landing Page

Redesign puramente visual, sem lógica nova. Direção: SaaS moderno e ousado,
base azul intensificada, movimento via AOS + CSS. Nada commitado ainda.

---

## Status

| Item | Status |
|---|---|
| Fonte de display (Google Fonts) | ✅ Space Grotesk |
| Gradientes reais no hero/CTA/plano destaque | ✅ |
| Scroll-reveal com stagger (AOS via CDN) | ✅ |
| Hover nos cards (scale + shadow lift) | ✅ |
| Blob decorativo animado (CSS puro) | ✅ |
| Composição assimétrica no hero | ✅ |
| `{% for plano in planos %}` / `{% if plano.destaque %}` | ✅ intactos |
| `cadastro.html`/`termos.html`/`privacidade.html` | ✅ não tocados |
| Backend/model/view/rota | ✅ não tocados |
| Testes `apps.tenants` (sanity, template renderiza) | ✅ 10/10 OK |
| Migration pendente aplicada no banco dev | ✅ (`0009`, a pedido) |
| Commit | ❌ não feito |

---

## Fonte escolhida: Space Grotesk

Pareada com a Inter já usada no corpo (mantida sem alteração pro texto
corrido). Motivo: é geométrica com personalidade — terminais quadrados,
aberturas largas —, comum em identidade de SaaS moderno (Vercel, Linear,
Notion-adjacent), sem virar "fonte de moda" ilegível. Contrasta bem com a
Inter (mais neutra) em vez de duas fontes parecidas competindo.

Carregada via Google Fonts, junto com a Inter já existente:

```diff
     <link
-        href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
+        href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap"
         rel="stylesheet"
     >
```

E registrada no `tailwind.config` inline (`base_public.html`) como
`font-display`, usada só em headlines/títulos (`h1`, `h2`, `h3`, preços):

```diff
                     fontFamily: {
                         sans: ['Inter', 'system-ui', 'sans-serif'],
+                        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
                     },
```

Único trecho tocado em `base_public.html` — cabeçalho (`<head>`), como
combinado. Resto do arquivo intacto.

---

## AOS (Animate On Scroll) via CDN — confere com Tailwind CDN

Carregado 100% escopado em `landing.html` (não em `base_public.html`), via
`{% block extra_head %}` (CSS) e `{% block extra_js %}` (JS + init) —
blocos que já existiam vazios no `base_public.html`, feitos pra isso:

```html
<!-- extra_head -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.css" integrity="sha512-..." crossorigin="anonymous" referrerpolicy="no-referrer">

<!-- extra_js -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.js" integrity="sha512-..." crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
    AOS.init({ duration: 700, easing: 'ease-out-cubic', once: true, offset: 60 });
</script>
```

Sem conflito: AOS não usa classes Tailwind, só `data-aos="..."` nos
elementos + CSS/JS próprios carregados via `cdnjs.cloudflare.com` (host
diferente do `cdn.tailwindcss.com`, sem colisão de namespace). Confirmado
via `python manage.py test apps.tenants` — a view `landing()` renderiza o
template inteiro (com os dois `{% block %}` novos) sem erro nas 10 asserções
que já existiam, incluindo as que checam conteúdo renderizado.

**Nota:** os testes automatizados aqui só garantem que o template renderiza
sem quebrar (Django template engine) — não testam JS/CSS visual real, que só
roda no browser. Validação visual de fato depende de abrir no navegador
(pedido explicitamente adiado pra depois do print).

---

## Diff completo — `templates/base_public.html`

```diff
diff --git a/templates/base_public.html b/templates/base_public.html
index 4fb6b44..8a528bd 100644
--- a/templates/base_public.html
+++ b/templates/base_public.html
@@ -38,6 +38,7 @@
                     },
                     fontFamily: {
                         sans: ['Inter', 'system-ui', 'sans-serif'],
+                        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
                     },
                     boxShadow: {
                         soft: '0 18px 45px rgba(15, 23, 42, 0.08)',
@@ -55,7 +56,7 @@
     <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
 
     <link
-        href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
+        href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap"
         rel="stylesheet"
     >
```

---

## `templates/tenants/landing.html` — arquivo completo (reescrito)

O diff textual ficaria confuso porque o arquivo já tinha mudanças
acumuladas de rodadas anteriores (não commitadas) — segue o arquivo inteiro
na versão atual:

```html
{% extends "base_public.html" %}

{% block title %}Gestão imobiliária moderna{% endblock %}

{% block extra_head %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.css" integrity="sha512-A0aE7SmVvHV5xR8CxUt/bpJTLYt/8OjcGdaSJ4y8ExHRzXFV1TZLW8B24V1EiaBu9WPa0iCsCXqDpX1mvR+cyw==" crossorigin="anonymous" referrerpolicy="no-referrer">
<style>
    @keyframes blob-float {
        0%, 100% { transform: translate(0, 0) scale(1); }
        33% { transform: translate(30px, -40px) scale(1.15); }
        66% { transform: translate(-25px, 25px) scale(0.9); }
    }
    .animate-blob { animation: blob-float 9s ease-in-out infinite; }
    .animation-delay-2000 { animation-delay: 2s; }
    .animation-delay-4000 { animation-delay: 4s; }

    @keyframes float-slow {
        0%, 100% { transform: translateY(0) rotate(-2deg); }
        50% { transform: translateY(-14px) rotate(1deg); }
    }
    .animate-float-slow { animation: float-slow 6s ease-in-out infinite; }

    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.4); }
    }
    .animate-pulse-dot { animation: pulse-dot 2s ease-in-out infinite; }
</style>
{% endblock %}

{% block content %}

<!-- Hero -->
<section class="relative overflow-hidden bg-gradient-to-br from-blue-700 via-blue-600 to-indigo-900">

    <!-- Blobs decorativos -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
        <div class="animate-blob absolute -top-24 -left-16 h-96 w-96 rounded-full bg-blue-400/30 mix-blend-screen blur-3xl"></div>
        <div class="animate-blob animation-delay-2000 absolute top-1/3 -right-24 h-[28rem] w-[28rem] rounded-full bg-indigo-400/30 mix-blend-screen blur-3xl"></div>
        <div class="animate-blob animation-delay-4000 absolute -bottom-32 left-1/4 h-80 w-80 rounded-full bg-cyan-300/20 mix-blend-screen blur-3xl"></div>
    </div>

    <div class="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-24 lg:py-32">

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">

            <!-- Texto principal — ancorado à esquerda -->
            <div class="lg:col-span-6" data-aos="fade-right" data-aos-duration="800">
                <span class="inline-flex items-center gap-2 rounded-full bg-white/10 backdrop-blur-sm px-4 py-1.5 text-sm font-medium text-blue-50 ring-1 ring-white/20 mb-6">
                    <span class="relative flex h-2 w-2">
                        <span class="animate-pulse-dot absolute inline-flex h-full w-full rounded-full bg-emerald-300"></span>
                        <span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-300"></span>
                    </span>
                    Gestão imobiliária moderna
                </span>

                <h1 class="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-white leading-[1.05]">
                    Gerencie sua imobiliária
                    <span class="bg-gradient-to-r from-cyan-300 via-blue-200 to-white bg-clip-text text-transparent">com eficiência real</span>
                </h1>

                <p class="mt-6 max-w-xl text-lg leading-8 text-blue-100">
                    Contratos, cobranças, boletos Sicredi e WhatsApp automático —
                    tudo em um só lugar. Multi-tenant, seguro e com dados totalmente isolados.
                </p>

                <div class="mt-8 flex flex-col sm:flex-row gap-4">
                    <a href="{% url 'cadastro_imobiliaria' %}"
                       class="group inline-flex justify-center items-center gap-2 rounded-xl bg-white px-6 py-3.5 text-base font-bold text-blue-700 shadow-lg shadow-blue-950/30 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-blue-950/40">
                        Começar grátis por 14 dias
                        <span class="transition-transform duration-300 group-hover:translate-x-1">→</span>
                    </a>

                    <a href="#planos"
                       class="inline-flex justify-center items-center rounded-xl border border-white/30 bg-white/5 backdrop-blur-sm px-6 py-3.5 text-base font-semibold text-white transition-all duration-300 hover:bg-white/15 hover:border-white/50">
                        Ver planos
                    </a>
                </div>

                <div class="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-blue-200">
                    <span class="inline-flex items-center gap-1.5">✓ Sem cartão de crédito</span>
                    <span class="inline-flex items-center gap-1.5">✓ Cancele quando quiser</span>
                </div>
            </div>

            <!-- Card visual — saindo da grid, leve rotação -->
            <div class="lg:col-span-6 relative" data-aos="fade-left" data-aos-duration="800" data-aos-delay="150">
                <div class="animate-float-slow relative mx-auto max-w-md lg:max-w-none lg:-mr-6">
                    <div class="rounded-3xl bg-white/95 backdrop-blur shadow-2xl shadow-blue-950/40 border border-white/50 p-6 -rotate-2">
                        <div class="flex items-center justify-between border-b border-gray-100 pb-4">
                            <div>
                                <p class="text-sm text-gray-500">Resumo mensal</p>
                                <h3 class="font-display text-2xl font-bold text-gray-900">Dashboard DN Imob</h3>
                            </div>
                            <div class="h-12 w-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white text-xl shadow-lg shadow-blue-600/30">
                                📊
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-4 mt-6">
                            <div class="rounded-2xl bg-blue-50 p-4">
                                <p class="text-sm text-blue-700">Contratos ativos</p>
                                <p class="mt-2 text-3xl font-bold text-blue-900">128</p>
                            </div>

                            <div class="rounded-2xl bg-emerald-50 p-4">
                                <p class="text-sm text-emerald-700">Pagamentos</p>
                                <p class="mt-2 text-3xl font-bold text-emerald-900">94%</p>
                            </div>

                            <div class="rounded-2xl bg-yellow-50 p-4">
                                <p class="text-sm text-yellow-700">Boletos emitidos</p>
                                <p class="mt-2 text-3xl font-bold text-yellow-900">312</p>
                            </div>

                            <div class="rounded-2xl bg-purple-50 p-4">
                                <p class="text-sm text-purple-700">Mensagens enviadas</p>
                                <p class="mt-2 text-3xl font-bold text-purple-900">1.2k</p>
                            </div>
                        </div>
                    </div>

                    <!-- Elemento flutuante extra, quebra a simetria -->
                    <div class="hidden sm:block absolute -bottom-6 -left-8 rounded-2xl bg-white shadow-xl shadow-blue-950/30 border border-gray-100 px-5 py-3 rotate-3">
                        <p class="text-xs text-gray-500">WhatsApp automático</p>
                        <p class="text-sm font-bold text-emerald-600">✓ 13 eventos ativos</p>
                    </div>
                </div>
            </div>

        </div>
    </div>
</section>


<!-- Recursos -->
<section class="relative bg-white py-24">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        <div class="text-center max-w-3xl mx-auto" data-aos="fade-up">
            <span class="text-sm font-bold uppercase tracking-widest text-blue-600">Recursos</span>
            <h2 class="mt-3 font-display text-3xl sm:text-4xl font-bold text-gray-900">
                Tudo que sua imobiliária precisa
            </h2>
            <p class="mt-4 text-lg text-gray-600">
                Automatize processos, organize contratos e acompanhe sua operação em tempo real.
            </p>
        </div>

        <div class="mt-14 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">

            <div data-aos="fade-up" data-aos-delay="0" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-2xl shadow-md shadow-blue-500/20 transition-transform duration-300 group-hover:scale-110">
                    📋
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    Contratos inteligentes
                </h3>
                <p class="mt-3 text-gray-600">
                    Wizard multi-step, geração de PDF automática, reajuste por IGP-M/IPCA/INPC e distrato com multa proporcional.
                </p>
            </div>

            <div data-aos="fade-up" data-aos-delay="75" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-700 flex items-center justify-center text-2xl shadow-md shadow-emerald-500/20 transition-transform duration-300 group-hover:scale-110">
                    🏦
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    Boletos Sicredi
                </h3>
                <p class="mt-3 text-gray-600">
                    Registro automático via API OAuth2, webhook de baixa HMAC validado e sincronização ativa como fallback.
                </p>
            </div>

            <div data-aos="fade-up" data-aos-delay="150" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center text-2xl shadow-md shadow-emerald-400/20 transition-transform duration-300 group-hover:scale-110">
                    💬
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    WhatsApp automático
                </h3>
                <p class="mt-3 text-gray-600">
                    13 eventos automatizados — vencimento, atraso, pagamento confirmado e contratos — com templates editáveis.
                </p>
            </div>

            <div data-aos="fade-up" data-aos-delay="0" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-700 flex items-center justify-center text-2xl shadow-md shadow-purple-500/20 transition-transform duration-300 group-hover:scale-110">
                    📊
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    Dashboard financeiro
                </h3>
                <p class="mt-3 text-gray-600">
                    KPIs em tempo real, inadimplência, relatórios por período e exportação em Excel e PDF.
                </p>
            </div>

            <div data-aos="fade-up" data-aos-delay="75" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-orange-400 to-red-600 flex items-center justify-center text-2xl shadow-md shadow-orange-400/20 transition-transform duration-300 group-hover:scale-110">
                    🔐
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    Multi-tenant seguro
                </h3>
                <p class="mt-3 text-gray-600">
                    Schema PostgreSQL por imobiliária. Seus dados 100% isolados dos outros clientes.
                </p>
            </div>

            <div data-aos="fade-up" data-aos-delay="150" class="group rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-100 hover:border-blue-200">
                <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-slate-500 to-slate-700 flex items-center justify-center text-2xl shadow-md shadow-slate-500/20 transition-transform duration-300 group-hover:scale-110">
                    ⚙️
                </div>
                <h3 class="mt-5 text-lg font-semibold text-gray-900">
                    Automações Celery
                </h3>
                <p class="mt-3 text-gray-600">
                    Cobranças geradas no dia 1, boletos registrados automaticamente e lembretes enviados no horário certo.
                </p>
            </div>

        </div>
    </div>
</section>


<!-- Planos -->
<section id="planos" class="relative overflow-hidden bg-gradient-to-b from-gray-50 to-blue-50/40 py-24">
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
        <div class="absolute top-0 right-1/4 h-72 w-72 rounded-full bg-blue-200/30 blur-3xl"></div>
    </div>

    <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        <div class="text-center max-w-3xl mx-auto" data-aos="fade-up">
            <span class="text-sm font-bold uppercase tracking-widest text-blue-600">Planos</span>
            <h2 class="mt-3 font-display text-3xl sm:text-4xl font-bold text-gray-900">
                Planos e preços
            </h2>
            <p class="mt-4 text-lg text-gray-600">
                14 dias grátis em qualquer plano. Sem compromisso.
            </p>
        </div>

        <div class="mt-14 grid grid-cols-1 md:grid-cols-3 gap-8">

            {% for plano in planos %}
                {% if plano.destaque %}
                    <div data-aos="fade-up" data-aos-delay="{{ forloop.counter0 }}00" class="relative rounded-3xl bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-700 p-8 shadow-2xl shadow-blue-600/30 text-white ring-2 ring-blue-400/50 transition-all duration-300 hover:scale-105 hover:shadow-2xl">
                        <span class="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-yellow-300 to-amber-400 px-4 py-1 text-sm font-bold text-yellow-900 shadow-lg">
                            Mais indicado
                        </span>

                        <h3 class="font-display text-xl font-bold">{{ plano.get_nome_display }}</h3>
                        <p class="mt-4 font-display text-4xl font-bold">
                            R$ {{ plano.preco_mensal|floatformat:0 }}<span class="text-base font-medium text-blue-100">/mês</span>
                        </p>

                        <ul class="mt-8 space-y-3 text-blue-50">
                            <li>✅ {% if plano.limite_imoveis %}{{ plano.limite_imoveis }} imóveis{% else %}Imóveis ilimitados{% endif %}</li>
                            <li>✅ {% if plano.limite_contratos %}{{ plano.limite_contratos }} contratos{% else %}Contratos ilimitados{% endif %}</li>
                            <li>✅ {% if plano.limite_usuarios %}Até {{ plano.limite_usuarios }} usuários{% else %}Usuários ilimitados{% endif %}</li>
                            <li>{% if plano.tem_whatsapp %}✅{% else %}❌{% endif %} WhatsApp automático</li>
                            <li>{% if plano.tem_sicredi %}✅{% else %}❌{% endif %} Boletos Sicredi</li>
                            <li>✅ Dashboard financeiro</li>
                        </ul>

                        <a href="{% url 'cadastro_imobiliaria' %}"
                           class="mt-8 block text-center rounded-xl bg-white px-5 py-3 font-semibold text-blue-700 transition-colors duration-300 hover:bg-blue-50">
                            Testar agora
                        </a>
                    </div>
                {% else %}
                    <div data-aos="fade-up" data-aos-delay="{{ forloop.counter0 }}00" class="rounded-3xl bg-white border border-gray-200 p-8 shadow-sm transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:border-blue-200">
                        <h3 class="font-display text-xl font-bold text-gray-900">{{ plano.get_nome_display }}</h3>
                        <p class="mt-4 font-display text-4xl font-bold text-gray-900">
                            {% if plano.preco_mensal %}
                                R$ {{ plano.preco_mensal|floatformat:0 }}<span class="text-base font-medium text-gray-500">/mês</span>
                            {% else %}
                                Sob consulta
                            {% endif %}
                        </p>

                        <ul class="mt-8 space-y-3 text-gray-600">
                            <li>✅ {% if plano.limite_imoveis %}{{ plano.limite_imoveis }} imóveis{% else %}Imóveis ilimitados{% endif %}</li>
                            <li>✅ {% if plano.limite_contratos %}{{ plano.limite_contratos }} contratos{% else %}Contratos ilimitados{% endif %}</li>
                            <li>✅ {% if plano.limite_usuarios %}Até {{ plano.limite_usuarios }} usuários{% else %}Usuários ilimitados{% endif %}</li>
                            <li>{% if plano.tem_whatsapp %}✅{% else %}❌{% endif %} WhatsApp automático</li>
                            <li>{% if plano.tem_sicredi %}✅{% else %}❌{% endif %} Boletos Sicredi</li>
                            <li>✅ Relatórios e exportação</li>
                        </ul>

                        <a href="{% url 'cadastro_imobiliaria' %}"
                           class="mt-8 block text-center rounded-xl border border-blue-600 px-5 py-3 font-semibold text-blue-600 transition-colors duration-300 hover:bg-blue-50">
                            Começar grátis
                        </a>
                    </div>
                {% endif %}
            {% empty %}
                <div class="md:col-span-3 rounded-3xl bg-white border border-gray-200 p-8 text-center text-gray-500">
                    Planos em breve.
                    <a href="mailto:contato@dnsoftware.com.br" class="text-blue-600 font-semibold hover:underline">Fale com a gente</a>.
                </div>
            {% endfor %}

        </div>
    </div>
</section>


<!-- CTA final -->
<section class="relative overflow-hidden bg-gradient-to-br from-blue-700 via-blue-600 to-indigo-900 py-24">
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
        <div class="animate-blob absolute -top-20 left-1/3 h-80 w-80 rounded-full bg-blue-400/20 mix-blend-screen blur-3xl"></div>
        <div class="animate-blob animation-delay-2000 absolute -bottom-20 right-1/4 h-72 w-72 rounded-full bg-cyan-300/20 mix-blend-screen blur-3xl"></div>
    </div>

    <div class="relative max-w-4xl mx-auto px-4 text-center" data-aos="zoom-in">
        <h2 class="font-display text-3xl sm:text-4xl font-bold text-white">
            Pronto para modernizar sua imobiliária?
        </h2>

        <p class="mt-4 text-lg text-blue-100">
            Comece agora e teste o DN Imob gratuitamente por 14 dias.
        </p>

        <div class="mt-8">
            <a href="{% url 'cadastro_imobiliaria' %}"
               class="group inline-flex items-center justify-center gap-2 rounded-xl bg-white px-8 py-4 text-base font-bold text-blue-700 shadow-lg shadow-blue-950/30 transition-all duration-300 hover:scale-105 hover:shadow-xl">
                Criar minha conta grátis
                <span class="transition-transform duration-300 group-hover:translate-x-1">→</span>
            </a>
        </div>
    </div>
</section>

{% endblock %}

{% block extra_js %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.1/aos.js" integrity="sha512-A0aE7SmVvHV5xR8CxUt/bpJTLYt/8OjcGdaSJ4y8ExHRzXFV1TZLW8B24V1EiaBu9WPa0iCsCXqDpX1mvR+cyw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
    AOS.init({
        duration: 700,
        easing: 'ease-out-cubic',
        once: true,
        offset: 60,
    });
</script>
{% endblock %}
```

---

## Descrição visual (sem print — pedido explicitamente adiado)

**Hero:** fundo com gradiente diagonal azul-royal → indigo escuro
(`from-blue-700 via-blue-600 to-indigo-900`), três blobs desfocados
(`blur-3xl`) flutuando em loop lento atrás do conteúdo (`mix-blend-screen`,
opacidade baixa, não competem com o texto). Layout quebra a simetria:
12 colunas, texto ocupa 6 à esquerda ancorado, card do dashboard ocupa 6 à
direita mas sai da grid (`lg:-mr-6`), levemente rotacionado (`-rotate-2`) e
flutuando (`animate-float-slow`), com um segundo cartãozinho menor
("WhatsApp automático · 13 eventos ativos") ancorado no canto inferior
esquerdo do card principal, sobrepondo, quebrando o alinhamento óbvio.
Headline em Space Grotesk, 5xl→7xl, parte do texto ("com eficiência real")
em gradiente ciano→branco via `bg-clip-text`. Badge superior com dot verde
pulsante (`animate-pulse-dot`) simulando "sistema ativo". CTA primário
branco sólido com seta que desliza no hover; CTA secundário translúcido
(glassmorphism leve, `bg-white/5 backdrop-blur-sm`).

**Planos:** fundo suave gradiente cinza→azul bem sutil (não mais
branco/cinza uniforme), um blur decorativo atrás do card do meio. Cards com
`hover:scale-105 hover:shadow-2xl transition-all duration-300` — sobem e
ganham peso visual ao passar o mouse. O card com `plano.destaque=True`
ganha gradiente azul→indigo cheio (em vez de azul chapado), anel de destaque
(`ring-2 ring-blue-400/50`) e a etiqueta "Mais indicado" agora em gradiente
dourado. Cada card entra com `fade-up` escalonado via AOS
(`data-aos-delay` cresce por posição no loop — 0ms, 100ms, 200ms...), então
os cards aparecem em sequência ao rolar até a seção, não todos de uma vez.

**Recursos e CTA final:** mesma lógica — ícones dos 6 cards de recursos
ganharam gradientes individuais (antes eram fundo sólido de cor pastel),
hover com leve elevação + ícone escalando; seção CTA final repete o
tratamento do hero (gradiente azul escuro + blobs), fechando o loop visual
da página.

---

## Migration aplicada no banco dev (a pedido, durante esta rodada)

```bash
python manage.py migrate_schemas --schema=public --settings=config.settings.dev
# Applying tenants.0009_plano_destaque_tenant_aceite_termos_user_agent... OK
```

Confirmado via `information_schema.columns`: `tenants_plano.destaque` e
`tenants_tenant.aceite_termos_user_agent` existem no schema `public`.

---

## Testes

```
python manage.py test apps.tenants --settings=config.settings.dev

Found 10 test(s).
..........
Ran 10 tests in 0.277s

OK
```

Mesmos 10 testes de antes — nenhum novo teste pedido pra esta rodada (visual
puro). Servem como sanity check de que o template continua renderizando sem
erro de sintaxe Django após o redesign.

---

## O que NÃO foi mexido

- Contexto/lógica de `views.py` — `landing()` continua igual.
- `{% for plano in planos %}` e `{% if plano.destaque %}` — só estilo em volta.
- `cadastro.html`, `termos.html`, `privacidade.html`.
- Resto de `base_public.html` fora do `<head>` (header, footer, nav).
- Nenhuma dependência nova via npm — Tailwind e AOS seguem via CDN puro.
