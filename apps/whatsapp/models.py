from django.db import models
from django.utils import timezone


class LogMensagem(models.Model):
    """Registra cada mensagem WhatsApp enviada pelo sistema."""

    class Evento(models.TextChoices):
        CONTRATO_CRIADO     = 'contrato_criado',     'Contrato criado'
        PARCELA_LEMBRETE    = 'parcela_lembrete',    'Lembrete de vencimento'
        PARCELA_VENCIDA     = 'parcela_vencida',     'Cobrança de parcela vencida'
        PAGAMENTO_CONFIRMADO = 'pagamento_confirmado', 'Pagamento confirmado'

    class Status(models.TextChoices):
        ENVIADO  = 'enviado',  'Enviado'
        ERRO     = 'erro',     'Erro'
        PENDENTE = 'pendente', 'Pendente'

    evento        = models.CharField(max_length=30, choices=Evento.choices)
    destinatario  = models.CharField(max_length=20, help_text='Número no formato 5511999999999')
    nome_contato  = models.CharField(max_length=120, blank=True)
    mensagem      = models.TextField()
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    erro_detalhe  = models.TextField(blank=True)
    enviado_em    = models.DateTimeField(default=timezone.now)

    # Vínculos opcionais para rastreabilidade
    contrato_id   = models.IntegerField(null=True, blank=True)
    parcela_id    = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-enviado_em']
        verbose_name = 'Log de Mensagem'
        verbose_name_plural = 'Logs de Mensagens'

    def __str__(self):
        return f'{self.get_evento_display()} → {self.destinatario} [{self.status}]'
