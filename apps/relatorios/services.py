"""
services.py — Fase 7 (corrigido para os models reais do projeto)

Correções aplicadas:
  - Lancamento: data_vencimento → data | RECEITA/DESPESA/PAGO → strings literais | status 'realizado'
  - Parcela: Status.ATRASADO → 'atrasado' | Status.CANCELADO → 'cancelado'
  - valor_total é @property — usa ExpressionWrapper para Sum no banco
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mes_range(hoje: date, meses_atras: int):
    """Retorna (primeiro_dia, ultimo_dia) do mês `meses_atras` atrás."""
    primeiro = (hoje.replace(day=1) - timedelta(days=meses_atras * 28)).replace(day=1)
    if primeiro.month == 12:
        ultimo = primeiro.replace(year=primeiro.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo = primeiro.replace(month=primeiro.month + 1, day=1) - timedelta(days=1)
    return primeiro, ultimo


_EXPR_VALOR_TOTAL = ExpressionWrapper(
    F('valor') + F('valor_condominio') + F('valor_iptu') + F('valor_multa') - F('valor_desconto'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


# ─── Dashboard ────────────────────────────────────────────────────────────────

def get_dados_dashboard() -> dict:
    return {
        'receitas_despesas':  _receitas_despesas_12meses(),
        'inadimplencia':      _dados_inadimplencia(),
        'imoveis_ocupacao':   _imoveis_ocupacao(),
        'contratos_vencendo': _contratos_vencendo(),
        'cards':              _cards_resumo(),
    }


def _receitas_despesas_12meses() -> dict:
    from apps.financeiro.models import Lancamento

    hoje = date.today()
    meses, receitas, despesas = [], [], []

    for i in range(11, -1, -1):
        primeiro, ultimo = _mes_range(hoje, i)
        meses.append(primeiro.strftime('%b/%y'))

        rec = Lancamento.objects.filter(
            tipo='receita',
            status='realizado',
            data__gte=primeiro,
            data__lte=ultimo,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        desp = Lancamento.objects.filter(
            tipo='despesa',
            status='realizado',
            data__gte=primeiro,
            data__lte=ultimo,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        receitas.append(float(rec))
        despesas.append(float(desp))

    return {'labels': meses, 'receitas': receitas, 'despesas': despesas}


def _dados_inadimplencia() -> dict:
    from apps.contratos.models import Parcela

    hoje = date.today()
    meses, taxas = [], []

    for i in range(5, -1, -1):
        primeiro, ultimo = _mes_range(hoje, i)

        total = Parcela.objects.filter(
            data_vencimento__gte=primeiro,
            data_vencimento__lte=ultimo,
        ).exclude(status='cancelado').count()

        atrasadas = Parcela.objects.filter(
            data_vencimento__gte=primeiro,
            data_vencimento__lte=ultimo,
            status='atrasado',
        ).count()

        meses.append(primeiro.strftime('%b/%y'))
        taxas.append(round(atrasadas / total * 100, 1) if total > 0 else 0)

    qs_atrasadas = Parcela.objects.filter(status='atrasado')
    valor_inadimplente = qs_atrasadas.aggregate(
        t=Sum(_EXPR_VALOR_TOTAL)
    )['t'] or Decimal('0')

    return {
        'labels':             meses,
        'taxas':              taxas,
        'total_atrasadas':    qs_atrasadas.count(),
        'valor_inadimplente': float(valor_inadimplente),
    }


def _imoveis_ocupacao() -> dict:
    from apps.imoveis.models import Imovel

    qs    = Imovel.objects.values('status').annotate(total=Count('id'))
    dados = {item['status']: item['total'] for item in qs}

    ocupados   = dados.get('alugado', 0)
    vagos      = dados.get('disponivel', 0)
    manutencao = dados.get('manutencao', 0)
    total      = sum(dados.values()) or 1

    return {
        'labels':    ['Alugados', 'Disponíveis', 'Manutenção'],
        'valores':   [ocupados, vagos, manutencao],
        'total':     total,
        'ocupados':  ocupados,
        'vagos':     vagos,
        'taxa_ocup': round(ocupados / total * 100, 1),
    }


def _contratos_vencendo() -> dict:
    from apps.contratos.models import Contrato

    hoje = date.today()
    em30 = hoje + timedelta(days=30)
    em60 = hoje + timedelta(days=60)

    v30 = Contrato.objects.filter(
        status='ativo', data_fim__gte=hoje, data_fim__lte=em30,
    ).select_related('inquilino', 'imovel').order_by('data_fim')

    v60 = Contrato.objects.filter(
        status='ativo', data_fim__gt=em30, data_fim__lte=em60,
    ).select_related('inquilino', 'imovel').order_by('data_fim')

    return {
        'em_30_dias': v30, 'em_60_dias': v60,
        'count_30': v30.count(), 'count_60': v60.count(),
    }


def _cards_resumo() -> dict:
    from apps.imoveis.models import Imovel
    from apps.contratos.models import Contrato, Parcela
    from apps.financeiro.models import Lancamento

    hoje         = date.today()
    primeiro_mes = hoje.replace(day=1)

    receita_mes = Lancamento.objects.filter(
        tipo='receita', status='realizado',
        data__gte=primeiro_mes, data__lte=hoje,
    ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

    despesa_mes = Lancamento.objects.filter(
        tipo='despesa', status='realizado',
        data__gte=primeiro_mes, data__lte=hoje,
    ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

    return {
        'total_imoveis':      Imovel.objects.count(),
        'contratos_ativos':   Contrato.objects.filter(status='ativo').count(),
        'receita_mes':        float(receita_mes),
        'despesa_mes':        float(despesa_mes),
        'saldo_mes':          float(receita_mes - despesa_mes),
        'parcelas_atrasadas': Parcela.objects.filter(status='atrasado').count(),
    }


# ─── Relatórios ───────────────────────────────────────────────────────────────

def get_dados_extrato(data_inicio: date, data_fim: date) -> dict:
    from apps.financeiro.models import Lancamento

    lancamentos = Lancamento.objects.filter(
        data__gte=data_inicio,
        data__lte=data_fim,
    ).select_related('contrato').order_by('data')

    total_receitas = lancamentos.filter(tipo='receita').aggregate(
        t=Sum('valor'))['t'] or Decimal('0')
    total_despesas = lancamentos.filter(tipo='despesa').aggregate(
        t=Sum('valor'))['t'] or Decimal('0')

    return {
        'lancamentos':    lancamentos,
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'saldo':          total_receitas - total_despesas,
        'data_inicio':    data_inicio,
        'data_fim':       data_fim,
        'gerado_em':      timezone.now(),
    }


def get_dados_inadimplencia() -> dict:
    from apps.contratos.models import Parcela

    # Carrega como lista pois valor_total é @property (não campo de banco)
    parcelas = list(
        Parcela.objects.filter(status='atrasado')
        .select_related('contrato__inquilino', 'contrato__imovel')
        .order_by('data_vencimento')
    )

    total_valor = sum(p.valor_total for p in parcelas) or Decimal('0')

    return {
        'parcelas':    parcelas,
        'total_valor': total_valor,
        'count':       len(parcelas),
        'gerado_em':   timezone.now(),
    }


def get_dados_imoveis() -> dict:
    from apps.imoveis.models import Imovel

    imoveis = Imovel.objects.select_related('responsavel').order_by('codigo')
    return {'imoveis': imoveis, 'total': imoveis.count(), 'gerado_em': timezone.now()}


def get_dados_contratos_ativos() -> dict:
    from apps.contratos.models import Contrato

    contratos = Contrato.objects.filter(
        status='ativo'
    ).select_related('inquilino', 'imovel').order_by('data_fim')

    return {'contratos': contratos, 'total': contratos.count(), 'gerado_em': timezone.now()}
