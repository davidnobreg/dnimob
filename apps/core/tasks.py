import logging
import os
import subprocess
from datetime import datetime, timezone

import boto3
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _s3_client():
    return boto3.client('s3')


def _bucket_e_prefixo():
    bucket = getattr(settings, 'AWS_BACKUP_BUCKET', None) \
             or getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    prefix = getattr(settings, 'BACKUP_PREFIX', 'backups').rstrip('/')
    return bucket, prefix


def _env_pg():
    """Env dict com PGPASSWORD para subprocessos pg_*."""
    db = settings.DATABASES['default']
    env = os.environ.copy()
    env['PGPASSWORD'] = db.get('PASSWORD', '')
    return db, env


@shared_task(bind=True, max_retries=2)
def executar_backup(self, tipo='daily'):
    """
    Faz pg_dump de todo o banco (todos os schemas) e envia para S3.
    tipo: 'daily' | 'weekly'
    Formato custom do PostgreSQL (já comprimido internamente).
    """
    db, env = _env_pg()
    bucket, prefix = _bucket_e_prefixo()

    if not bucket:
        raise RuntimeError('AWS_BACKUP_BUCKET ou AWS_STORAGE_BUCKET_NAME não configurado.')

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f'backup_{timestamp}_{tipo}.dump'
    year_month = datetime.now(timezone.utc).strftime('%Y/%m')
    s3_key = f'{prefix}/{year_month}/{filename}'

    cmd = [
        os.environ.get('PG_DUMP_PATH', '/usr/bin/pg_dump'),
        '-h', db['HOST'],
        '-p', str(db.get('PORT', 5432)),
        '-U', db['USER'],
        '-d', db['NAME'],
        '--format=custom',
        '--no-password',
        '--verbose',
    ]

    logger.info('Iniciando backup %s → s3://%s/%s', tipo, bucket, s3_key)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        s3 = _s3_client()
        s3.upload_fileobj(proc.stdout, bucket, s3_key)

        proc.wait()
        if proc.returncode != 0:
            erro = proc.stderr.read().decode(errors='replace')
            raise RuntimeError(f'pg_dump saiu com código {proc.returncode}: {erro[:500]}')

        logger.info('Backup concluído: s3://%s/%s', bucket, s3_key)
        _limpar_backups_antigos(s3, bucket, prefix, tipo)
        return f's3://{bucket}/{s3_key}'

    except Exception as exc:
        logger.error('Falha no backup %s: %s', tipo, exc)
        raise self.retry(exc=exc, countdown=300)


def _limpar_backups_antigos(s3, bucket, prefix, tipo):
    """Mantém apenas os N mais recentes do tipo informado."""
    retencao = {'daily': 7, 'weekly': 4}.get(tipo, 7)
    sufixo = f'_{tipo}.dump'

    paginator = s3.get_paginator('list_objects_v2')
    arquivos = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            if obj['Key'].endswith(sufixo):
                arquivos.append((obj['LastModified'], obj['Key']))

    arquivos.sort(reverse=True)
    for _, key in arquivos[retencao:]:
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info('Backup antigo removido: s3://%s/%s', bucket, key)
