# 08. DevOps: Docker, env, GitHub Actions CI/CD

## 1. Структура репозитория

```text
pitchwow-bot/
  app/
    bot/
      main.py
      handlers.py
      telegram_responder.py
    graph/
      state.py
      builder.py
      nodes/
        normalize_turn.py
        classify_incoming.py
        update_calibration.py
        babur.py
        crisis.py
        defense.py
        guardrails.py
        persist.py
        jobs.py
      prompts/
        registry.py
    services/
      stt_openai.py
      tts_yandex.py
      anthropic_client.py
      langsmith.py
      locks.py
    api/
      main.py
      admin/
        routes.py
        templates/
    worker/
      main.py
      jobs.py
    db/
      models.py
      repositories.py
      migrations/
  tests/
    unit/
    integration/
    fixtures/
  docker/
    Caddyfile
  alembic.ini
  Dockerfile
  docker-compose.yml
  docker-compose.prod.yml
  pyproject.toml
  .env.example
  .github/
    workflows/
      ci.yml
      deploy.yml
```

## 2. .env.example

```env
APP_ENV=production
APP_BASE_URL=https://pitchwow.example.com
ADMIN_BASE_URL=https://admin.pitchwow.example.com

POSTGRES_DB=pitchwow
POSTGRES_USER=pitchwow
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+psycopg://pitchwow:change_me@postgres:5432/pitchwow

REDIS_URL=redis://redis:6379/0

TELEGRAM_BOT_TOKEN=replace_with_new_rotated_token
TELEGRAM_WEBHOOK_SECRET=replace_with_random_secret
TELEGRAM_WEBHOOK_URL=https://pitchwow.example.com/telegram/webhook

ANTHROPIC_API_KEY=replace_me
ANTHROPIC_PRIMARY_MODEL=claude-sonnet-4-6
ANTHROPIC_CLASSIFIER_MODEL=claude-haiku-4-5

OPENAI_API_KEY=replace_me
OPENAI_STT_MODEL=gpt-4o-transcribe

YANDEX_FOLDER_ID=replace_me
YANDEX_API_KEY=replace_me
YANDEX_TTS_VOICE=marina
YANDEX_TTS_ROLE=friendly
YANDEX_TTS_SPEED=1.05
YANDEX_TTS_FORMAT=oggopus

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=replace_me
LANGSMITH_PROJECT=pitchwow-prod

ADMIN_INITIAL_EMAIL=owner@example.com
ADMIN_INITIAL_PASSWORD=change_me_now

SENTRY_DSN=
LOG_LEVEL=INFO
```

## 3. Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
RUN pip install --upgrade pip && pip install uv && uv sync --frozen --no-dev

COPY app ./app
COPY alembic.ini ./alembic.ini

CMD ["python", "-m", "app.bot.main"]
```

## 4. docker-compose.prod.yml

```yaml
services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    command: python -m app.bot.main
    depends_on:
      - postgres
      - redis

  api:
    build: .
    restart: unless-stopped
    env_file: .env
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    depends_on:
      - postgres
      - redis

  worker:
    build: .
    restart: unless-stopped
    env_file: .env
    command: python -m app.worker.main
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: pitchwow
      POSTGRES_USER: pitchwow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 5. Webhook vs polling

Рекомендация для production: webhook. Причины: меньше latency, проще контролировать вход, нет риска двойного polling owner, проще логировать входящие events.

Для MVP на VPS допустим polling, если домен/TLS ещё не готов. Но в acceptance зафиксировать один режим, чтобы не было двойного владельца чата.

## 6. GitHub Actions CI

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: pitchwow_test
          POSTGRES_USER: pitchwow
          POSTGRES_PASSWORD: pitchwow
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          pip install uv
          uv sync --frozen
      - name: Lint
        run: |
          uv run ruff check app tests
          uv run mypy app
      - name: Tests
        env:
          DATABASE_URL: postgresql+psycopg://pitchwow:pitchwow@localhost:5432/pitchwow_test
          REDIS_URL: redis://localhost:6379/0
        run: uv run pytest -q
```

## 7. GitHub Actions deploy

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            set -e
            cd /opt/pitchwow-bot
            git fetch origin main
            git reset --hard origin/main
            docker compose -f docker-compose.prod.yml build
            docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f
```

## 8. Bootstrap на VPS

```bash
sudo mkdir -p /opt/pitchwow-bot
sudo chown -R deploy:deploy /opt/pitchwow-bot
cd /opt/pitchwow-bot
git clone git@github.com:ORG/REPO.git .
cp .env.example .env
nano .env
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f
```

## 9. Healthchecks

```http
GET /health
GET /health/db
GET /health/redis
GET /health/langsmith
```

Bot internal: last update processed timestamp, last successful sendMessage, webhook status, queue size.

## 10. Backups

```bash
pg_dump "$DATABASE_URL" | gzip > backups/pitchwow_$(date +%F_%H-%M).sql.gz
```

Рекомендация: ежедневный backup, хранить 14 дней, отдельно backup `.env` вне репозитория, проверять restore раз в месяц.

## 11. Логи

```json
{
  "ts": "2026-06-01T10:00:00Z",
  "level": "INFO",
  "event": "graph_turn_completed",
  "session_id": "...",
  "telegram_user_id": 123,
  "phase": "Крылья",
  "personality_dev_level": "бизнес",
  "latency_ms": 4200,
  "langsmith_trace_id": "..."
}
```

## 12. LangSmith

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=pitchwow-prod
```

Каждый turn должен передавать metadata:

```python
metadata = {
    "session_id": str(session_id),
    "telegram_user_id": telegram_user_id,
    "phase": state.get("phase"),
    "personality_dev_level": state.get("personality_dev_level"),
    "prompt_version": prompt.version,
}
```

## 13. Ротация секретов

Перед первым production-запуском: перевыпустить Telegram bot token, создать новые API keys Anthropic/OpenAI/Yandex, проверить, что `.env` отсутствует в git, проверить GitHub Actions Secrets, удалить старые ключи из провайдеров, включить audit log в админке.
