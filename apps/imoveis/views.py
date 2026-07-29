import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

from .models import Imovel, FotoImovel, Proprietario, Edificio, IMOVEL_TIPO_CHOICES, IMOVEL_FINALIDADE_CHOICES
from .forms import ImovelForm, FotoImovelForm, FiltroImovelForm, ProprietarioForm
from apps.core.validators import validate_file_size

Usuario = get_user_model()

FOTO_IMOVEL_EXT_VALIDATOR = FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])
FOTO_IMOVEL_SIZE_VALIDATOR = validate_file_size(5)


def _validar_fotos_imovel(request, fotos):
    """Valida extensão e tamanho de cada foto, descartando as inválidas.
    Retorna a lista de arquivos válidos."""
    validas = []
    for foto in fotos:
        try:
            FOTO_IMOVEL_EXT_VALIDATOR(foto)
            FOTO_IMOVEL_SIZE_VALIDATOR(foto)
            validas.append(foto)
        except ValidationError as e:
            messages.error(request, f'{foto.name}: {e.message}')
    return validas


@login_required
def imovel_lista(request):
    form_filtro = FiltroImovelForm(request.GET)
    qs = Imovel.objects.exclude(status='inativo')  # oculta inativos por padrão

    if form_filtro.is_valid():
        q            = form_filtro.cleaned_data.get('q')
        tipo         = form_filtro.cleaned_data.get('tipo')
        status       = form_filtro.cleaned_data.get('status')
        finalidade   = form_filtro.cleaned_data.get('finalidade')
        edificio     = form_filtro.cleaned_data.get('edificio')
        proprietario = form_filtro.cleaned_data.get('proprietario')

        if q:
            qs = qs.filter(
                Q(codigo__icontains=q) |
                Q(bairro__icontains=q) |
                Q(cidade__icontains=q) |
                Q(logradouro__icontains=q) |
                Q(proprietario__nome__icontains=q)
            )
        if status:
            qs = Imovel.objects.filter(status=status)  # filtro explícito mostra inativo tbm
            if q:
                qs = qs.filter(
                    Q(codigo__icontains=q) |
                    Q(bairro__icontains=q) |
                    Q(cidade__icontains=q) |
                    Q(logradouro__icontains=q) |
                    Q(proprietario__nome__icontains=q)
                )
        if tipo:
            qs = qs.filter(tipo=tipo)
        if finalidade:
            qs = qs.filter(finalidade=finalidade)
        if edificio:
            qs = qs.filter(edificio=edificio)
        if proprietario:
            qs = qs.filter(proprietario=proprietario)

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


def _herdar_endereco_edificio(imovel):
    """Se um edifício foi selecionado e o endereço não foi preenchido, herda do edifício."""
    if not imovel.edificio_id:
        return
    edificio = imovel.edificio
    if not imovel.cep:
        imovel.cep = edificio.cep
    if not imovel.logradouro:
        imovel.logradouro = edificio.logradouro
    if not imovel.bairro:
        imovel.bairro = edificio.bairro
    if not imovel.cidade:
        imovel.cidade = edificio.cidade
    if not imovel.estado:
        imovel.estado = edificio.estado


@login_required
def imovel_criar(request):
    if request.method == 'POST':
        form = ImovelForm(request.POST, request.FILES)
        if form.is_valid():
            imovel = form.save(commit=False)
            if not imovel.responsavel_id:
                imovel.responsavel = request.user
            _herdar_endereco_edificio(imovel)
            imovel.save()

            fotos = _validar_fotos_imovel(request, request.FILES.getlist('fotos'))
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
        'form':          form,
        'titulo':        'Cadastrar Imóvel',
        'acao':          'Cadastrar',
        'proprietarios': Proprietario.objects.all().order_by('nome'),
        'edificios':     Edificio.objects.all().order_by('nome'),
    })


@login_required
def edificio_criar(request):
    if request.method == 'POST':
        return _edificio_criar_post(request)

    proprietarios = Proprietario.objects.all().order_by('nome')
    responsaveis  = Usuario.objects.filter(is_active=True).order_by('first_name', 'username')
    context = {
        'proprietarios':       proprietarios,
        'responsaveis':        responsaveis,
        'tipo_choices':        Edificio.TIPO_CHOICES,
        'tipo_imovel_choices': IMOVEL_TIPO_CHOICES,
        'finalidade_choices':  IMOVEL_FINALIDADE_CHOICES,
    }
    return render(request, 'imoveis/edificio_criar.html', context)


def _edificio_criar_post(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    edificio_data = data.get('edificio', {})
    unidades_data = data.get('unidades', [])

    if not edificio_data or not edificio_data.get('nome', '').strip() or not unidades_data:
        return JsonResponse({'erro': 'Dados incompletos'}, status=400)

    erros = []

    try:
        with transaction.atomic():
            edificio = Edificio(
                nome=edificio_data.get('nome', ''),
                tipo=edificio_data.get('tipo', 'residencial'),
                cep=edificio_data.get('cep', ''),
                logradouro=edificio_data.get('logradouro', ''),
                bairro=edificio_data.get('bairro', ''),
                cidade=edificio_data.get('cidade', ''),
                estado=edificio_data.get('estado', ''),
                tipo_imovel_padrao=edificio_data.get('tipo_imovel_padrao', 'apartamento'),
                finalidade_padrao=edificio_data.get('finalidade_padrao', 'aluguel'),
            )
            proprietario_id = edificio_data.get('proprietario_id')
            if proprietario_id:
                edificio.proprietario_id = proprietario_id
            responsavel_id = edificio_data.get('responsavel_id')
            if responsavel_id:
                edificio.responsavel_id = responsavel_id
            edificio.save()

            for i, u in enumerate(unidades_data):
                try:
                    imovel = Imovel(
                        edificio=edificio,
                        proprietario=edificio.proprietario,
                        cep=edificio.cep,
                        logradouro=edificio.logradouro,
                        bairro=edificio.bairro,
                        cidade=edificio.cidade,
                        estado=edificio.estado,
                        complemento=u.get('complemento', ''),
                        nome_imovel=u.get('nome_imovel', ''),
                        numero=u.get('numero', ''),
                        tipo=u.get('tipo', edificio.tipo_imovel_padrao),
                        finalidade=u.get('finalidade', edificio.finalidade_padrao),
                        quartos=u.get('quartos') or 0,
                        suites=u.get('suites') or 0,
                        banheiros=u.get('banheiros') or 0,
                        vagas=u.get('vagas') or 0,
                        valor_aluguel=u.get('valor_aluguel') or 0,
                        valor_venda=u.get('valor_venda') or 0,
                        responsavel=edificio.responsavel,
                        status='disponivel',
                    )
                    imovel.save()
                except Exception as e:
                    erros.append({'unidade': i + 1, 'erro': str(e)})

            if erros:
                raise Exception('Erros nas unidades')

    except Exception as e:
        return JsonResponse({'erro': str(e), 'detalhes': erros}, status=400)

    return JsonResponse({
        'sucesso':        True,
        'edificio_id':    edificio.id,
        'edificio_codigo': edificio.codigo,
        'total_unidades': len(unidades_data),
    })


@login_required
def edificio_dados_ajax(request, pk):
    edificio = get_object_or_404(Edificio, pk=pk)
    return JsonResponse({
        'cep':              edificio.cep,
        'logradouro':       edificio.logradouro,
        'bairro':           edificio.bairro,
        'cidade':           edificio.cidade,
        'estado':           edificio.estado,
        'proprietario_id':  edificio.proprietario_id,
    })


@login_required
def proprietario_lista(request):
    q = request.GET.get('q', '').strip()
    proprietarios = Proprietario.objects.all().order_by('nome')
    if q:
        proprietarios = proprietarios.filter(
            Q(nome__icontains=q) |
            Q(cpf_cnpj__icontains=q)
        )
    return render(request, 'imoveis/proprietario_lista.html', {
        'proprietarios': proprietarios,
        'q': q,
    })


@login_required
def proprietario_criar(request):
    if request.method == 'POST':
        form = ProprietarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proprietário cadastrado com sucesso.')
            return redirect('proprietario_lista')
    else:
        form = ProprietarioForm()
    return render(request, 'imoveis/proprietario_form.html', {
        'form':   form,
        'titulo': 'Novo Proprietário',
    })


@login_required
def proprietario_editar(request, pk):
    proprietario = get_object_or_404(Proprietario, pk=pk)
    if request.method == 'POST':
        form = ProprietarioForm(request.POST, instance=proprietario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proprietário atualizado com sucesso.')
            return redirect('proprietario_lista')
    else:
        form = ProprietarioForm(instance=proprietario)
    return render(request, 'imoveis/proprietario_form.html', {
        'form':          form,
        'titulo':        'Editar Proprietário',
        'proprietario':  proprietario,
    })


@login_required
def imovel_editar(request, pk):
    imovel = get_object_or_404(Imovel, pk=pk)

    if request.method == 'POST':
        form = ImovelForm(request.POST, request.FILES, instance=imovel)
        if form.is_valid():
            imovel = form.save(commit=False)
            _herdar_endereco_edificio(imovel)
            imovel.save()

            fotos        = _validar_fotos_imovel(request, request.FILES.getlist('fotos'))
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
        'form':          form,
        'imovel':        imovel,
        'titulo':        f'Editar Imóvel {imovel.codigo}',
        'acao':          'Salvar alterações',
        'proprietarios': Proprietario.objects.all().order_by('nome'),
        'edificios':     Edificio.objects.all().order_by('nome'),
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
            Q(proprietario__nome__icontains=q)
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
