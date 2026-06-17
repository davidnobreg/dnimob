#!/bin/sh
set -e
cd /app

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Rodando migrations (schema public)..."
  python manage.py migrate_schemas --shared --noinput

  echo "Rodando migrations (todos os tenants)..."
  python manage.py migrate_schemas --noinput

  echo "Coletando arquivos estáticos..."
  python manage.py collectstatic --noinput
fi

exec "$@"
