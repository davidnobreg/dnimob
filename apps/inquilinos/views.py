from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Inquilino
from .forms import InquilinoForm, FiltroInquilinoForm


@login_required
def inquilino_lista(request):
    form_filtro = FiltroInquilinoForm(request.GET)
    qs = Inquilino.objects.exclude(status='inativo')  # oculta inativos por padrão

    if form_filtro.is_valid():
        q      = form_filtro.cleaned_data.get('q')
        status = form_filtro.cleaned_data.get('status')
        tipo   = form_filtro.cleaned_data.get('tipo')

        if q:
            qs = qs.filter(
                Q(nome__icontains=q) |
                Q(cpf__icontains=q) |
                Q(cnpj__icontains=q) |
                Q(telefone__icontains=q) |
                Q(email__icontains=q)
            )
        if status:
            qs = Inquilino.objects.filter(status=status)  # se filtro explícito, mostra inativo tbm
            if q:
                qs = qs.filter(
                    Q(nome__icontains=q) |
                    Q(cpf__icontains=q) |
                    Q(cnpj__icontains=q) |
                    Q(telefone__icontains=q) |
                    Q(email__icontains=q)
                )
        if tipo:
            qs = qs.filter(tipo=tipo)

    paginator = Paginator(qs, 15)
    page      = paginator.get_page(request.GET.get('page'))

    totais = {
        'total':        Inquilino.objects.exclude(status='inativo').count(),
        'ativo':        Inquilino.objects.filter(status='ativo').count(),
        'inadimplente': Inquilino.objects.filter(status='inadimplente').count(),
        'inativo':      Inquilino.objects.filter(status='inativo').count(),
    }

    return render(request, 'inquilinos/lista.html', {
        'page_obj':    page,
        'form_filtro': form_filtro,
        'totais':      totais,
    })


@login_required
def inquilino_detalhe(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk)
    contratos = inquilino.contratos.select_related('imovel').order_by('-data_inicio')
    return render(request, 'inquilinos/detalhe.html', {
        'inquilino': inquilino,
        'contratos': contratos,
    })


@login_required
def inquilino_criar(request):
    """
    Ao criar, verifica se já existe inquilino inativo com o mesmo CPF/CNPJ.
    Se sim, oferece reativar e atualizar em vez de duplicar.
    """
    # Verifica reativação pendente (vindo da tela de confirmação)
    reativar_pk = request.POST.get('reativar_pk') or request.GET.get('reativar_pk')
    if reativar_pk:
        return _reativar_inquilino(request, reativar_pk)

    if request.method == 'POST':
        form = InquilinoForm(request.POST, request.FILES)
        if form.is_valid():
            # Verifica duplicata inativa antes de salvar
            cpf  = form.cleaned_data.get('cpf', '').replace('.', '').replace('-', '')
            cnpj = form.cleaned_data.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '')
            doc  = cpf or cnpj

            duplicado = None
            if doc:
                if cpf:
                    duplicado = Inquilino.objects.filter(
                        cpf__icontains=cpf, status='inativo'
                    ).first()
                elif cnpj:
                    duplicado = Inquilino.objects.filter(
                        cnpj__icontains=cnpj, status='inativo'
                    ).first()

            if duplicado:
                # Salva dados do form na sessão e mostra tela de confirmação
                return render(request, 'inquilinos/confirmar_reativacao.html', {
                    'duplicado':   duplicado,
                    'form':        form,
                    'reativar_pk': duplicado.pk,
                })

            inquilino = form.save()
            messages.success(request, f'Inquilino {inquilino.nome} cadastrado com sucesso!')
            return redirect('inquilino_detalhe', pk=inquilino.pk)
    else:
        form = InquilinoForm()

    return render(request, 'inquilinos/form.html', {
        'form':   form,
        'titulo': 'Cadastrar Inquilino',
        'acao':   'Cadastrar',
    })


def _reativar_inquilino(request, pk):
    """Reativa inquilino inativo e atualiza com os novos dados do form."""
    inquilino = get_object_or_404(Inquilino, pk=pk)
    if request.method == 'POST':
        form = InquilinoForm(request.POST, request.FILES, instance=inquilino)
        if form.is_valid():
            inquilino = form.save(commit=False)
            inquilino.status = 'ativo'
            inquilino.save()
            messages.success(
                request,
                f'Cadastro de {inquilino.nome} reativado e atualizado com sucesso!'
            )
            return redirect('inquilino_detalhe', pk=inquilino.pk)
    else:
        form = InquilinoForm(instance=inquilino)

    return render(request, 'inquilinos/form.html', {
        'form':      form,
        'inquilino': inquilino,
        'titulo':    f'Reativar — {inquilino.nome}',
        'acao':      'Reativar e salvar',
    })


@login_required
def inquilino_editar(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk)
    if request.method == 'POST':
        form = InquilinoForm(request.POST, request.FILES, instance=inquilino)
        if form.is_valid():
            form.save()
            messages.success(request, 'Inquilino atualizado com sucesso!')
            return redirect('inquilino_detalhe', pk=inquilino.pk)
        else:
            print('ERROS INQUILINO:', form.errors)
    else:
        form = InquilinoForm(instance=inquilino)

    return render(request, 'inquilinos/form.html', {
        'form':      form,
        'inquilino': inquilino,
        'titulo':    f'Editar — {inquilino.nome}',
        'acao':      'Salvar alterações',
    })


@login_required
def inquilino_excluir(request, pk):
    """Desativa o inquilino em vez de deletar — preserva histórico."""
    inquilino = get_object_or_404(Inquilino, pk=pk)
    if request.method == 'POST':
        # Bloqueia se tiver contrato ativo
        contratos_ativos = inquilino.contratos.filter(status='ativo').count()
        if contratos_ativos > 0:
            messages.error(
                request,
                f'Não é possível desativar {inquilino.nome} pois possui {contratos_ativos} contrato(s) ativo(s).'
            )
            return redirect('inquilino_detalhe', pk=inquilino.pk)

        inquilino.status = 'inativo'
        inquilino.save()
        messages.success(request, f'Inquilino {inquilino.nome} desativado com sucesso.')
        return redirect('inquilino_lista')

    return render(request, 'inquilinos/confirmar_exclusao.html', {'inquilino': inquilino})
