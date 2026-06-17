"""
Utilitário de restore para validar backups S3.

Modos:
  --list                       Lista backups disponíveis no S3
  --verify --file=KEY          Valida integridade do arquivo (pg_restore --list)
  --restore --file=KEY         Restaura em banco de destino (requer --db)
  --db=NOME                    Banco destino para restore (criado se não existir)

Exemplos:
  python manage.py restore_backup --list
  python manage.py restore_backup --verify --file=backups/2026/06/backup_20260617_020000_daily.dump
  python manage.py restore_backup --restore --file=backups/2026/06/backup_20260617_020000_daily.dump --db=imobiliaria_restore_test
"""
import os
import subprocess
import tempfile

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _bucket_e_prefixo():
    bucket = getattr(settings, 'AWS_BACKUP_BUCKET', None) \
             or getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    prefix = getattr(settings, 'BACKUP_PREFIX', 'backups').rstrip('/')
    return bucket, prefix


def _env_pg():
    db = settings.DATABASES['default']
    env = os.environ.copy()
    env['PGPASSWORD'] = db.get('PASSWORD', '')
    return db, env


class Command(BaseCommand):
    help = 'Lista, valida ou restaura backups do S3.'

    def add_arguments(self, parser):
        parser.add_argument('--list',    action='store_true', help='Lista backups no S3')
        parser.add_argument('--verify',  action='store_true', help='Valida integridade do dump')
        parser.add_argument('--restore', action='store_true', help='Restaura dump em banco de destino')
        parser.add_argument('--file',    type=str, help='S3 key do arquivo de backup')
        parser.add_argument('--db',      type=str, help='Banco destino para restore')
        parser.add_argument('--latest',  action='store_true', help='Usa o backup daily mais recente')

    def handle(self, *args, **options):
        bucket, prefix = _bucket_e_prefixo()
        if not bucket:
            raise CommandError('AWS_BACKUP_BUCKET ou AWS_STORAGE_BUCKET_NAME não configurado.')

        s3 = boto3.client('s3')

        if options['list']:
            self._listar(s3, bucket, prefix)
            return

        s3_key = options.get('file')
        if options['latest']:
            s3_key = self._ultimo_backup(s3, bucket, prefix, 'daily')
            self.stdout.write(f'Backup mais recente: {s3_key}')

        if not s3_key:
            raise CommandError('Informe --file=KEY ou --latest.')

        if options['verify']:
            self._verificar(s3, bucket, s3_key)
        elif options['restore']:
            if not options.get('db'):
                raise CommandError('--restore requer --db=NOME_DO_BANCO_DESTINO.')
            self._restaurar(s3, bucket, s3_key, options['db'])
        else:
            raise CommandError('Informe --list, --verify ou --restore.')

    def _listar(self, s3, bucket, prefix):
        paginator = s3.get_paginator('list_objects_v2')
        arquivos = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.dump'):
                    arquivos.append((obj['LastModified'], obj['Key'], obj['Size']))

        if not arquivos:
            self.stdout.write('Nenhum backup encontrado.')
            return

        arquivos.sort(reverse=True)
        self.stdout.write(f'\n{"Data/Hora (UTC)":<26} {"Tipo":<8} {"Tamanho":>10}   Arquivo')
        self.stdout.write('-' * 90)
        for ts, key, size in arquivos:
            tipo = 'weekly' if '_weekly' in key else 'daily'
            mb = size / 1024 / 1024
            self.stdout.write(f'{str(ts)[:19]:<26} {tipo:<8} {mb:>9.1f}M   {key}')

    def _ultimo_backup(self, s3, bucket, prefix, tipo):
        paginator = s3.get_paginator('list_objects_v2')
        arquivos = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith(f'_{tipo}.dump'):
                    arquivos.append((obj['LastModified'], obj['Key']))
        if not arquivos:
            raise CommandError(f'Nenhum backup {tipo} encontrado no S3.')
        arquivos.sort(reverse=True)
        return arquivos[0][1]

    def _baixar_para_temp(self, s3, bucket, s3_key):
        """Faz download do S3 para arquivo temporário e retorna o path."""
        self.stdout.write(f'Baixando s3://{bucket}/{s3_key} ...')
        tmp = tempfile.NamedTemporaryFile(suffix='.dump', delete=False)
        s3.download_fileobj(bucket, s3_key, tmp)
        tmp.flush()
        tmp.close()
        self.stdout.write(self.style.SUCCESS(f'Download concluído: {tmp.name}'))
        return tmp.name

    def _verificar(self, s3, bucket, s3_key):
        """Valida integridade do arquivo via pg_restore --list."""
        tmp_path = self._baixar_para_temp(s3, bucket, s3_key)
        try:
            result = subprocess.run(
                ['pg_restore', '--list', tmp_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.stderr.write(self.style.ERROR(f'Arquivo inválido:\n{result.stderr}'))
                return

            linhas = [l for l in result.stdout.splitlines() if not l.startswith(';')]
            self.stdout.write(self.style.SUCCESS(
                f'Arquivo válido. {len(linhas)} objetos no dump.'
            ))
            # Mostra amostra dos schemas encontrados
            schemas = {l.split()[3] for l in result.stdout.splitlines()
                       if 'SCHEMA' in l and not l.startswith(';')}
            if schemas:
                self.stdout.write(f'Schemas detectados: {", ".join(sorted(schemas))}')
        finally:
            os.unlink(tmp_path)

    def _restaurar(self, s3, bucket, s3_key, db_destino):
        """Restaura dump em banco de destino. O banco deve existir e estar vazio."""
        db, env = _env_pg()

        self.stdout.write(
            self.style.WARNING(
                f'\nATENÇÃO: isso vai restaurar em "{db_destino}" em {db["HOST"]}.\n'
                'O banco deve existir. Dados existentes SERÃO SOBRESCRITOS.\n'
                'Ctrl+C para cancelar. Enter para continuar...'
            )
        )
        input()

        tmp_path = self._baixar_para_temp(s3, bucket, s3_key)
        try:
            self.stdout.write('Restaurando...')
            result = subprocess.run(
                [
                    'pg_restore',
                    '-h', db['HOST'],
                    '-p', str(db.get('PORT', 5432)),
                    '-U', db['USER'],
                    '-d', db_destino,
                    '--no-owner',
                    '--no-privileges',
                    '--verbose',
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                env=env,
            )

            if result.returncode not in (0, 1):
                raise CommandError(f'pg_restore falhou (código {result.returncode}):\n{result.stderr[-2000:]}')

            self.stdout.write(self.style.SUCCESS(f'Restore concluído em "{db_destino}".'))
            if result.stderr:
                self.stdout.write(f'Avisos:\n{result.stderr[-500:]}')
        finally:
            os.unlink(tmp_path)
