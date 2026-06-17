from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class ContaView(LoginRequiredMixin, TemplateView):
    template_name = 'tenants/conta.html'

class WhatsAppConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'tenants/config_whatsapp.html'

class SicrediConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'tenants/config_sicredi.html'
