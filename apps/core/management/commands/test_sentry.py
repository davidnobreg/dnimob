"""
Comando de diagnóstico: dispara erros de teste para confirmar captura no Sentry.
Uso (APENAS em produção ou com DSN configurado):

    python manage.py test_sentry --settings=config.settings.prod
    python manage.py test_sentry --celery --settings=config.settings.prod

Remover ou restringir a admins antes de expor em produção pública.
"""
import sentry_sdk
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Dispara erros de teste para validar captura no Sentry (Django + Celery).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--celery',
            action='store_true',
            help='Também dispara erro via task Celery',
        )

    def handle(self, *args, **options):
        dsn = sentry_sdk.get_client().dsn
        if not dsn:
            self.stderr.write(self.style.ERROR(
                'SENTRY_DSN não configurado. Preencha no .env e rode com --settings=config.settings.prod'
            ))
            return

        self.stdout.write(f'DSN ativo: {dsn[:40]}...')

        # ── Erro Django (síncrono) ──────────────────────────────────────────
        self.stdout.write('Capturando erro de teste (Django)...')
        try:
            raise ValueError('[DN Imob] Erro de teste Sentry — Django OK')
        except ValueError:
            event_id = sentry_sdk.capture_exception()
            sentry_sdk.flush(timeout=5)
            self.stdout.write(self.style.SUCCESS(f'Django: event_id={event_id}'))

        # ── Erro Celery (assíncrono) ────────────────────────────────────────
        if options['celery']:
            self.stdout.write('Disparando task de teste para Celery...')
            try:
                from celery import shared_task

                @shared_task
                def _tarefa_sentry_teste():
                    raise RuntimeError('[DN Imob] Erro de teste Sentry — Celery OK')

                _tarefa_sentry_teste.delay()
                self.stdout.write(self.style.SUCCESS(
                    'Task Celery enfileirada. Verifique o worker e o painel Sentry em ~10s.'
                ))
            except Exception as e:
                self.stderr.write(f'Erro ao enfileirar task: {e}')

        self.stdout.write(self.style.SUCCESS(
            'Verifique o painel em: https://sentry.io → Issues'
        ))
