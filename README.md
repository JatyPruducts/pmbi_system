# PMBI — предиктивная HR-аналитика

## Стек

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), Motor (MongoDB), Redis, Celery, scikit-learn  
- **Frontend:** Vue 3, Vite, Pinia, Apache ECharts  
- **Infra:** Docker Compose, Nginx  

---

## Инструкция по запуску

### Что понадобится

| Компонент | Вариант с Docker | Вариант без Docker |
|-----------|-------------------|-------------------|
| PostgreSQL, MongoDB, Redis, RabbitMQ | Через `docker compose` | Установлены локально и доступны по URL из переменных окружения |
| Python | 3.11+ | 3.11+ |
| Node.js | Для сборки фронта | 18+ (для `npm run dev` / `build`) |
| Docker | Docker Desktop или Engine + Compose v2 | Не обязателен |

Backend **не читает** файл `.env`: переменные задаются либо в **окружении ОС** (локальный запуск), либо через **`infra/.env`** при работе **Docker Compose** (Compose подставляет их в контейнеры).

---

### Вариант 1. Разработка: БД в Docker, API и фронт на машине

Удобно для отладки: базы изолированы, код backend/frontend запускается локально с hot-reload.

1. **Создайте `infra/.env`** (можно скопировать шаблон):

   ```bash
   copy infra\.env.example infra\.env
   ```

   Убедитесь, что в `infra/.env` для доступа **с хоста** к сервисам в Docker указаны URL с `localhost` и проброшенными портами (как в примере ниже для локального API).

2. **Поднимите только инфраструктуру** (из корня репозитория):

   ```bash
   cd infra
   docker compose up -d postgres mongo redis rabbitmq
   ```

3. **Переменные для локального backend** (Windows PowerShell, при значениях по умолчанию из `.env.example`):

   ```powershell
   $env:DATABASE_URL="postgresql+asyncpg://pmbi:pmbi@127.0.0.1:5432/pmbi"
   $env:SYNC_DATABASE_URL="postgresql://pmbi:pmbi@127.0.0.1:5432/pmbi"
   $env:MONGODB_URL="mongodb://127.0.0.1:27017"
   $env:MONGODB_DB="pmbi"
   $env:REDIS_URL="redis://127.0.0.1:6379/0"
   $env:CELERY_BROKER_URL="amqp://guest:guest@127.0.0.1:5672//"
   $env:JWT_SECRET="dev-secret-change-in-production-min-32-chars!!"
   ```

   На Linux/macOS используйте `export VAR=value`.

4. **Backend:**

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   python -m scripts.seed
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Frontend** (новый терминал):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Откройте в браузере:** фронт обычно на `http://localhost:5173`, API и Swagger — `http://localhost:8000` и `http://localhost:8000/docs`.

**Фоновые задачи (Celery):** для очередей аналитики/ML поднимите воркер отдельно (с теми же переменными окружения):

```bash
cd backend
.venv\Scripts\activate
celery -A app.tasks.celery_app worker -l info
```

---

### Вариант 2. Всё в Docker (API + Nginx + воркер)

Подходит для демо или прода: один compose поднимает сервисы и собранный фронт за Nginx.

1. Соберите фронт:

   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. Настройте **`infra/.env`** (скопируйте из `infra/.env.example`, задайте как минимум `JWT_SECRET`).

3. Запустите профиль `full` из каталога `infra`:

   ```bash
   cd infra
   docker compose --profile full up -d --build
   ```

4. **Доступ:**

   - Сайт и API через шлюз: `http://localhost` (Nginx проксирует `/api/` на backend; см. `infra/nginx/default.conf`).  
   - Прямой API (если проброшен порт): `http://localhost:8000`.  
   - RabbitMQ Management: `http://localhost:15672` (логин/пароль из `RABBITMQ_DEFAULT_*` в `.env`).

5. **Первичные данные:** при старте контейнера `api` автоматически выполняются миграции и **демо-seed** (пользователи `admin@pmbi.local` и др., если их ещё нет) — см. [`backend/docker-entrypoint.sh`](backend/docker-entrypoint.sh) и [`backend/scripts/seed.py`](backend/scripts/seed.py). Повторный seed безопасен: существующие email не дублируются.

---

### Вариант 3. Только API в Docker, фронт локально

1. `cd infra` → `docker compose --profile api up -d --build` (поднимет `api` и зависимости: postgres, mongo, redis, rabbitmq).

2. Миграции и демо-seed поднимаются вместе с `api` автоматически (см. вариант 2, шаг 5).

3. Локально: `cd frontend && npm run dev` — Vite проксирует запросы с префиксом `/api` на backend (по умолчанию `http://127.0.0.1:8000`). Если API в Docker на другом порту, задайте `VITE_API_BASE` при сборке/запуске или поправьте `frontend/vite.config.ts`.

---

### Тестовые учётные записи (после `scripts.seed`)

| Email | Пароль | Роль |
|--------|--------|------|
| admin@pmbi.local | admin123 | ADMIN |
| hr@pmbi.local | hr123 | HR |
| lead@pmbi.local | lead123 | TEAMLEAD |
| emp@pmbi.local | emp123 | EMPLOYEE |

Подробности и дополнительные сценарии — в [`backend/scripts/seed.py`](backend/scripts/seed.py).

---

### Частые проблемы

- **Порт 80 занят** — в `infra/.env` задайте, например, `NGINX_HTTP_PORT=8080`.  
- **Backend не видит БД** — проверьте, что `DATABASE_URL` указывает на `127.0.0.1` при локальном API и на `postgres` при запуске API **внутри** Docker.  
- **Celery не обрабатывает задачи** — должен быть доступен RabbitMQ (`CELERY_BROKER_URL`) и запущен процесс `celery worker`.  
- **Ошибка миграций** — сначала должен быть запущен PostgreSQL, затем `alembic upgrade head`.

---

## Краткая справка по URL

| Режим | Фронт | API / OpenAPI |
|--------|--------|----------------|
| Локальная разработка | `http://localhost:5173` | `http://localhost:8000`, `/docs` |
| Docker + Nginx | `http://localhost` (или порт из `NGINX_HTTP_PORT`) | через `/api/` или порт `API_PORT` |
