from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import LogMensagem
from .services import get_client_for_tenant


@login_required
def historico(request):
    """Lista todos os logs de mensagens do tenant."""
    qs = LogMensagem.objects.all()

    # Filtros
    evento = request.GET.get('evento')
    status = request.GET.get('status')
    if evento:
        qs = qs.filter(evento=evento)
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    # Totais para os cards
    total_enviado = LogMensagem.objects.filter(status=LogMensagem.Status.ENVIADO).count()
    total_erro    = LogMensagem.objects.filter(status=LogMensagem.Status.ERRO).count()
    total_hoje    = LogMensagem.objects.filter(
        enviado_em__date=__import__('datetime').date.today()
    ).count()

    return render(request, 'whatsapp/historico.html', {
        'page_obj':      page,
        'eventos':       LogMensagem.Evento.choices,
        'statuses':      LogMensagem.Status.choices,
        'filtro_evento': evento,
        'filtro_status': status,
        'total_enviado': total_enviado,
        'total_erro':    total_erro,
        'total_hoje':    total_hoje,
    })


@login_required
def status_conexao(request):
    """Retorna JSON com status da conexão WhatsApp (chamado via AJAX)."""
    client = get_client_for_tenant()
    if client is None:
        return JsonResponse({'configurado': False, 'estado': 'não configurado'})

    try:
        data = client.verificar_conexao()
        estado = data.get('instance', {}).get('state', 'desconhecido')
        return JsonResponse({'configurado': True, 'estado': estado})
    except Exception as exc:
        return JsonResponse({'configurado': True, 'estado': 'erro', 'detalhe': str(exc)})
