from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Imovel, FotoImovel
from .forms import ImovelForm, FotoImovelForm, FiltroImovelForm


@login_required
def imovel_lista(request):
    form_filtro = FiltroImovelForm(request.GET)
    qs = Imovel.objects.exclude(status='inativo')  # oculta inativos por padrão

    if form_filtro.is_valid():
        q          = form_filtro.cleaned_data.get('q')
        tipo       = form_filtro.cleaned_data.get('tipo')
        status     = form_filtro.cleaned_data.get('status')
        finalidade = form_filtro.cleaned_data.get('finalidade')
        cidade     = form_filtro.cleaned_data.get('cidade')

        if q:
            qs = qs.filter(
                Q(codigo__icontains=q) |
                Q(bairro__icontains=q) |
                Q(cidade__icontains=q) |
                Q(logradouro__icontains=q) |
                Q(proprietario_nome__icontains=q)
            )
        if status:
            qs = Imovel.objects.filter(status=status)  # filtro explícito mostra inativo tbm
            if q:
                qs = qs.filter(
                    Q(codigo__icontains=q) |
                    Q(bairro__icontains=q) |
                    Q(cidade__icontains=q) |
                    Q(logradouro__icontains=q) |
                    Q(proprietario_nome__icontains=q)
                )
        if tipo:
            qs = qs.filter(tipo=tipo)
        if finalidade:
            qs = qs.filter(finalidade=finalidade)
        if cidade:
            qs = qs.filter(cidade__icontains=cidade)

    paginator = Paginator(qs, 12)
    page      = paginator.get_page(request.GET.get('page'))

    totais = {
        'total':      Imovel.objects.exclude(status='inativo').count(),
        'disponivel': Imovel.objects.filter(status='disponivel').count(),
        'alugado':    Imovel.objects.filter(status='alugado').count(),
        'manutencao': Imovel.objects.filter(status='manutencao').count(),
    }

    return render(request, 'imoveis/lista.html', {
        'page_obj':    page,
        'form_filtro': form_filtro,
        'totais':      totais,
    })


@login_required
def imovel_detalhe(request, pk):
    imovel = get_object_or_404(Imovel, pk=pk)
    fotos  = imovel.fotos.all()
    return render(request, 'imoveis/detalhe.html', {
        'imovel': imovel,
        'fotos':  fotos,
    })


@login_required
def imovel_criar(request):
    if request.method == 'POST':
        form = ImovelForm(request.POST, request.FILES)
        if form.is_valid():
            imovel = form.save(commit=False)
            if not imovel.responsavel_id:
                imovel.responsavel = request.user
            imovel.save()

            fotos = request.FILES.getlist('fotos')
            for i, foto in enumerate(fotos):
                FotoImovel.objects.create(
                    imovel=imovel,
                    imagem=foto,
                    principal=(i == 0),
                    ordem=i,
                )

            messages.success(request, f'Imóvel {imovel.codigo} cadastrado com sucesso!')
            return redirect('imovel_detalhe', pk=imovel.pk)
        else:
            print('ERROS IMOVEL CRIAR:', form.errors)
    else:
        form = ImovelForm()

    return render(request, 'imoveis/form.html', {
        'form':   form,
        'titulo': 'Cadastrar Imóvel',
        'acao':   'Cadastrar',
    })


@login_required
def imovel_editar(request, pk):
    imovel = get_object_or_404(Imovel, pk=pk)

    if request.method == 'POST':
        form = ImovelForm(request.POST, request.FILES, instance=imovel)
        if form.is_valid():
            form.save()

            fotos        = request.FILES.getlist('fotos')
            ultima_ordem = imovel.fotos.count()
            for i, foto in enumerate(fotos):
                FotoImovel.objects.create(
                    imovel=imovel,
                    imagem=foto,
                    ordem=ultima_ordem + i,
                )

            messages.success(request, 'Imóvel atualizado com sucesso!')
            return redirect('imovel_detalhe', pk=imovel.pk)
        else:
            print('ERROS IMOVEL EDITAR:', form.errors)
    else:
        form = ImovelForm(instance=imovel)

    return render(request, 'imoveis/form.html', {
        'form':   form,
        'imovel': imovel,
        'titulo': f'Editar Imóvel {imovel.codigo}',
        'acao':   'Salvar alterações',
    })


@login_required
def imovel_excluir(request, pk):
    """Desativa o imóvel em vez de deletar — preserva histórico."""
    imovel = get_object_or_404(Imovel, pk=pk)

    if request.method == 'POST':
        # Bloqueia se tiver contrato ativo
        contratos_ativos = imovel.contratos.filter(status='ativo').count()
        if contratos_ativos > 0:
            messages.error(
                request,
                f'Não é possível desativar o imóvel {imovel.codigo} pois possui {contratos_ativos} contrato(s) ativo(s).'
            )
            return redirect('imovel_detalhe', pk=imovel.pk)

        imovel.status = 'inativo'
        imovel.save()
        messages.success(request, f'Imóvel {imovel.codigo} desativado com sucesso.')
        return redirect('imovel_lista')

    return render(request, 'imoveis/confirmar_exclusao.html', {'imovel': imovel})


@login_required
def imovel_inativos(request):
    qs = Imovel.objects.filter(status='inativo').order_by('codigo')

    q    = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) |
            Q(bairro__icontains=q) |
            Q(cidade__icontains=q) |
            Q(logradouro__icontains=q) |
            Q(proprietario_nome__icontains=q)
        )
    if tipo:
        qs = qs.filter(tipo=tipo)

    paginator = Paginator(qs, 20)
    page      = paginator.get_page(request.GET.get('page'))

    tipos = Imovel.objects.filter(status='inativo').values_list('tipo', flat=True).distinct()

    return render(request, 'imoveis/inativos.html', {
        'page_obj': page,
        'q':        q,
        'tipo':     tipo,
        'tipos':    tipos,
        'total':    Imovel.objects.filter(status='inativo').count(),
    })


@login_required
@require_POST
def imovel_reativar(request, pk):
    imovel = get_object_or_404(Imovel, pk=pk, status='inativo')
    imovel.status = 'disponivel'
    imovel.save()
    messages.success(request, f'Imóvel {imovel.codigo} reativado com sucesso.')
    return redirect('imovel_inativos')


@login_required
@require_POST
def foto_excluir(request, pk):
    foto      = get_object_or_404(FotoImovel, pk=pk)
    imovel_pk = foto.imovel.pk
    foto.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    messages.success(request, 'Foto removida.')
    return redirect('imovel_editar', pk=imovel_pk)


@login_required
@require_POST
def foto_principal(request, pk):
    foto = get_object_or_404(FotoImovel, pk=pk)
    FotoImovel.objects.filter(imovel=foto.imovel, principal=True).update(principal=False)
    foto.principal = True
    foto.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    messages.success(request, 'Foto principal atualizada.')
    return redirect('imovel_editar', pk=foto.imovel.pk)
