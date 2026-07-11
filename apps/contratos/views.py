from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import Contrato, Parcela
from .forms import ContratoForm, FiltroContratoForm, ParcelaPagamentoForm


@login_required
def contrato_lista(request):
    form_filtro = FiltroContratoForm(request.GET)
    qs = Contrato.objects.select_related('imovel', 'inquilino').all()

    if form_filtro.is_valid():
        q        = form_filtro.cleaned_data.get('q')
        status   = form_filtro.cleaned_data.get('status')
        vencendo = form_filtro.cleaned_data.get('vencendo')

        if q:
            qs = qs.filter(
                Q(numero__icontains=q) |
                Q(inquilino__nome__icontains=q) |
                Q(imovel__codigo__icontains=q) |
                Q(imovel__bairro__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if vencendo:
            limite = timezone.now().date() + timedelta(days=30)
            qs = qs.filter(status='ativo', data_fim__lte=limite)

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))

    hoje = timezone.now().date()
    totais = {
        'total':     Contrato.objects.count(),
        'ativo':     Contrato.objects.filter(status='ativo').count(),
        'pendente':  Contrato.objects.filter(status='pendente').count(),
        'vencendo':  Contrato.objects.filter(
                         status='ativo',
                         data_fim__lte=hoje + timedelta(days=30)
                     ).count(),
    }

    return render(request, 'contratos/lista.html', {
        'page_obj':    page,
        'form_filtro': form_filtro,
        'totais':      totais,
    })


@login_required
def contrato_detalhe(request, pk):
    contrato = get_object_or_404(
        Contrato.objects.select_related('imovel', 'inquilino', 'responsavel'),
        pk=pk
    )
    parcelas = contrato.parcelas.select_related('boleto').all()

    # Atualizar status de parcelas atrasadas
    hoje = timezone.now().date()
    parcelas.filter(status='pendente', data_vencimento__lt=hoje).update(status='atrasado')

    resumo = {
        'total_pago':    parcelas.filter(status='pago').aggregate(s=Sum('valor'))['s'] or 0,
        'total_pendente': parcelas.filter(status__in=['pendente','atrasado']).aggregate(s=Sum('valor'))['s'] or 0,
        'pagas':   parcelas.filter(status='pago').count(),
        'atrasadas': parcelas.filter(status='atrasado').count(),
    }

    return render(request, 'contratos/detalhe.html', {
        'contrato': contrato,
        'parcelas': parcelas,
        'resumo':   resumo,
    })


@login_required
def contrato_criar(request):
    if request.method == 'POST':
        form = ContratoForm(request.POST)
        if form.is_valid():
            contrato = form.save(commit=False)
            if not contrato.responsavel_id:
                contrato.responsavel = request.user
            contrato.save()

            # Marcar imóvel como alugado
            imovel = contrato.imovel
            imovel.status = 'alugado'
            imovel.save(update_fields=['status'])

            # Gerar parcelas automaticamente
            n = contrato.gerar_parcelas()
            if n == 0:
                messages.warning(request, f'Contrato {contrato.numero} criado, mas nenhuma parcela foi gerada — verifique as datas e o dia de vencimento.')
            else:
                messages.success(request, f'Contrato {contrato.numero} criado com {n} parcelas.')
            return redirect('contrato_detalhe', pk=contrato.pk)
    else:
        form = ContratoForm()
        # Pré-preencher número sequencial
        ultimo = Contrato.objects.order_by('-id').first()
        if ultimo:
            try:
                prox = int(ultimo.numero.split('-')[-1]) + 1
                form.initial['numero'] = f'CT-{prox:04d}'
            except (ValueError, IndexError):
                form.initial['numero'] = 'CT-0001'
        else:
            form.initial['numero'] = 'CT-0001'

    return render(request, 'contratos/form.html', {
        'form':   form,
        'titulo': 'Novo Contrato',
        'acao':   'Criar Contrato',
    })


@login_required
def contrato_editar(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    campos_criticos = ['data_inicio', 'data_fim', 'dia_vencimento',
                       'valor_aluguel', 'valor_condominio', 'valor_iptu']

    if request.method == 'POST':
        antes = {campo: getattr(contrato, campo) for campo in campos_criticos}
        form = ContratoForm(request.POST, instance=contrato)
        if form.is_valid():
            form.save()

            mudou_critico = any(getattr(contrato, campo) != antes[campo] for campo in campos_criticos)

            if mudou_critico:
                contrato.parcelas.exclude(status='pago').delete()
                criadas = contrato.gerar_parcelas_a_partir_da_proxima()
                messages.success(
                    request,
                    f'Contrato atualizado. {criadas} parcela(s) recalculada(s) — parcelas pagas foram preservadas.'
                )
            else:
                messages.success(request, 'Contrato atualizado.')

            return redirect('contrato_detalhe', pk=contrato.pk)
        else:
            print('ERROS CONTRATO EDITAR:', form.errors)
    else:
        form = ContratoForm(instance=contrato)

    return render(request, 'contratos/form.html', {
        'form':     form,
        'contrato': contrato,
        'titulo':   f'Editar Contrato {contrato.numero}',
        'acao':     'Salvar',
    })


@login_required
def contrato_encerrar(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'encerrado')
        contrato.status = motivo  # 'encerrado' ou 'rescindido'
        contrato.save(update_fields=['status'])

        # Liberar imóvel
        contrato.imovel.status = 'disponivel'
        contrato.imovel.save(update_fields=['status'])

        # Cancelar parcelas pendentes
        contrato.parcelas.filter(status__in=['pendente', 'atrasado']).update(status='cancelado')

        messages.success(request, f'Contrato {contrato.numero} encerrado.')
        return redirect('contrato_lista')

    return render(request, 'contratos/confirmar_encerramento.html', {'contrato': contrato})


# ── Parcelas ────────────────────────────────────────────

@login_required
def parcela_registrar_pagamento(request, pk):
    parcela = get_object_or_404(Parcela, pk=pk)

    if request.method == 'POST':
        form = ParcelaPagamentoForm(request.POST, instance=parcela)
        if form.is_valid():
            p = form.save(commit=False)
            p.status = 'pago'
            p.save()
            messages.success(request, f'Parcela {parcela.numero} registrada como paga.')
            return redirect('contrato_detalhe', pk=parcela.contrato.pk)
    else:
        form = ParcelaPagamentoForm(instance=parcela, initial={
            'data_pagamento': timezone.now().date(),
            'valor': parcela.valor,
        })

    return render(request, 'contratos/parcela_pagamento.html', {
        'form':    form,
        'parcela': parcela,
    })


@login_required
def parcela_estornar(request, pk):
    parcela = get_object_or_404(Parcela, pk=pk)
    if request.method == 'POST':
        from .services import estornar_parcela
        estornar_parcela(parcela, motivo='manual')
        messages.warning(request, f'Pagamento da parcela {parcela.numero} estornado.')
    return redirect('contrato_detalhe', pk=parcela.contrato.pk)


# ── PDF ─────────────────────────────────────────────────

@login_required
def contrato_pdf(request, pk):
    contrato = get_object_or_404(
        Contrato.objects.select_related('imovel', 'inquilino', 'responsavel'),
        pk=pk
    )
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    html_string = render_to_string('contratos/pdf/contrato.html', {
        'contrato': contrato,
        'tenant':   request.tenant,
    }, request=request)

    buffer = io.BytesIO()
    pisa.CreatePDF(html_string, dest=buffer)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="contrato-{contrato.numero}.pdf"'
    return response


@login_required
def recibo_pdf(request, pk):
    parcela = get_object_or_404(
        Parcela.objects.select_related('contrato__imovel', 'contrato__inquilino'),
        pk=pk, status='pago'
    )
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    html_string = render_to_string('contratos/pdf/recibo.html', {
        'parcela': parcela,
        'tenant':  request.tenant,
    }, request=request)

    buffer = io.BytesIO()
    pisa.CreatePDF(html_string, dest=buffer)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="recibo-{parcela.contrato.numero}-{parcela.numero:02d}.pdf"'
    return response
