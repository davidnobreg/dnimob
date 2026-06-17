from django.apps import AppConfig


class SicrediConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sicredi"

    def ready(self):
        from . import signals
        signals.connect_signals()
