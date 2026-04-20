#!/bin/sh
set -e
cd /app

# Celery не гоняет миграции (схему поднимает сервис api при старте)
if [ "$1" = "celery" ]; then
  exec "$@"
fi

echo "[docker-entrypoint] Applying Alembic migrations..."
alembic upgrade head

echo "[docker-entrypoint] Demo seed (пропускает уже существующие записи)..."
python -m scripts.seed

exec "$@"
