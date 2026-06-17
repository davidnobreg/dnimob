from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import date
from decimal import Decimal

from .models import Lancamento
from .forms import LancamentoForm, FiltroLancamentoForm


def _resumo_mes(ano, mes):
    qs = Lancamento.objects.filter(data__year=ano, data__month=mes, status='realizado')
    receitas = qs.filter(tipo='receita').aggregate(s=Sum('valor'))['s'] or Decimal('0')
    despesas = qs.filter(tipo='despesa').aggregate(s=Sum('valor'))['s'] or Decimal('0')
    return receitas, despesas, receitas - despesas


@login_required
def financeiro_dashboard(request):
    hoje = timezone.now().date()
    ano  = int(request.GET.get('ano',  hoje.year))
    mes  = int(request.GET.get('mes',  hoje.month))

    receitas, despesas, saldo = _resumo_mes(ano, mes)

    # Últimos 6 meses para o gráfico
    grafico = []
    for i in range(5, -1, -1):
        m = mes - i
        a = ano
        while m <= 0:
            m += 12
            a -= 1
        r, d, _ = _resumo_mes(a, m)
        grafico.append({
            'label': f'{m:02d}/{a}',
            'receitas': float(r),
            'despesas': float(d),
        })

    # Inadimplência
    from apps.contratos.models import Parcela
    atrasadas = Parcela.objects.filter(status='atrasado').select_related('contrato__inquilino')
    total_inadimplente = atrasadas.aggregate(s=Sum('valor'))['s'] or Decimal('0')

    # Próximos vencimentos (7 dias)
    limite = hoje + timezone.timedelta(days=7)
    proximos = Parcela.objects.filter(
        status='pendente',
        data_vencimento__range=[hoje, limite]
    ).select_related('contrato__inquilino', 'contrato__imovel').order_by('data_vencimento')

    # Lançamentos recentes
    lancamentos_recentes = Lancamento.objects.filter(status='realizado')[:10]

    meses_nomes = ['', 'Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

    return render(request, 'financeiro/dashboard.html', {
        'receitas':           receitas,
        'despesas':           despesas,
        'saldo':              saldo,
        'grafico':            grafico,
        'atrasadas':          atrasadas,
        'total_inadimplente': total_inadimplente,
        'proximos':           proximos,
        'lancamentos_recentes': lancamentos_recentes,
        'ano':   ano,
        'mes':   mes,
        'mes_nome': meses_nomes[mes],
        'meses_nomes': meses_nomes,
    })


@login_required
def lancamento_lista(request):
    form_filtro = FiltroLancamentoForm(request.GET)
    qs = Lancamento.objects.select_related('contrato', 'responsavel').all()

    if form_filtro.is_valid():
        q         = form_filtro.cleaned_data.get('q')
        tipo      = form_filtro.cleaned_data.get('tipo')
        categoria = form_filtro.cleaned_data.get('categoria')
        status    = form_filtro.cleaned_data.get('status')
        data_ini  = form_filtro.cleaned_data.get('data_ini')
        data_fim  = form_filtro.cleaned_data.get('data_fim')

        if q:
            qs = qs.filter(descricao__icontains=q)
        if tipo:
            qs = qs.filter(tipo=tipo)
        if categoria:
            qs = qs.filter(categoria=categoria)
        if status:
            qs = qs.filter(status=status)
        if data_ini:
            qs = qs.filter(data__gte=data_ini)
        if data_fim:
            qs = qs.filter(data__lte=data_fim)

    from django.core.paginator import Paginator
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    totais = {
        'receitas': qs.filter(tipo='receita', status='realizado').aggregate(s=Sum('valor'))['s'] or 0,
        'despesas': qs.filter(tipo='despesa', status='realizado').aggregate(s=Sum('valor'))['s'] or 0,
    }

    return render(request, 'financeiro/lancamentos.html', {
        'page_obj':    page,
        'form_filtro': form_filtro,
        'totais':      totais,
    })


@login_required
def lancamento_criar(request):
    if request.method == 'POST':
        form = LancamentoForm(request.POST)
        if form.is_valid():
            l = form.save(commit=False)
            l.responsavel = request.user
            l.save()
            messages.success(request, 'Lançamento registrado.')
            return redirect('lancamento_lista')
    else:
        form = LancamentoForm()
    return render(request, 'financeiro/lancamento_form.html', {
        'form': form, 'titulo': 'Novo Lançamento', 'acao': 'Salvar',
    })


@login_required
def lancamento_editar(request, pk):
    lancamento = get_object_or_404(Lancamento, pk=pk)
    if request.method == 'POST':
        form = LancamentoForm(request.POST, instance=lancamento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lançamento atualizado.')
            return redirect('lancamento_lista')
    else:
        form = LancamentoForm(instance=lancamento)
    return render(request, 'financeiro/lancamento_form.html', {
        'form': form, 'lancamento': lancamento,
        'titulo': 'Editar Lançamento', 'acao': 'Salvar',
    })


@login_required
def lancamento_excluir(request, pk):
    lancamento = get_object_or_404(Lancamento, pk=pk)
    if request.method == 'POST':
        lancamento.delete()
        messages.success(request, 'Lançamento excluído.')
        return redirect('lancamento_lista')
    return render(request, 'financeiro/lancamento_confirmar_exclusao.html', {'lancamento': lancamento})


@login_required
def inadimplencia(request):
    from apps.contratos.models import Parcela
    from django.db.models import Count
    atrasadas = (
        Parcela.objects
        .filter(status='atrasado')
        .select_related('contrato__inquilino', 'contrato__imovel')
        .order_by('contrato__inquilino__nome', 'data_vencimento')
    )
    total = atrasadas.aggregate(s=Sum('valor'))['s'] or Decimal('0')
    return render(request, 'financeiro/inadimplencia.html', {
        'atrasadas': atrasadas,
        'total':     total,
    })


# ── Signal para criar lançamento automaticamente ao pagar parcela ────────────
# Registrado em apps/financeiro/apps.py → ready()
def registrar_lancamento_parcela(parcela):
    """Cria lançamento de receita quando uma parcela é marcada como paga."""
    Lancamento.objects.get_or_create(
        parcela=parcela,
        defaults={
            'tipo':      'receita',
            'categoria': 'aluguel',
            'status':    'realizado',
            'descricao': f'Aluguel — {parcela.contrato.numero} — Parcela {parcela.numero}',
            'valor':     parcela.valor_total,
            'data':      parcela.data_pagamento or timezone.now().date(),
            'contrato':  parcela.contrato,
        }
    )
