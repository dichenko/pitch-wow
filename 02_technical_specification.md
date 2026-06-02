# 02. Техническое задание программисту

## 1. Назначение проекта

Разработать Telegram-бота Pitch Wow, который проводит фаундера через объёмное интервью и коучинговую распаковку продукта по авторской методике. Бот должен:

- вести долгий диалог на 1–2 часа;
- строго соблюдать этапы методики;
- определять фазу пользователя: `Защита`, `Кризис`, `Крылья`;
- дополнительно определять уровень развития Личности: `личность`, `бизнес`, `синергия`;
- задавать правильные классы вопросов A1/A2/A3;
- избегать запрещённых классов B1/B2;
- корректно завершать короткие и кризисные сессии;
- собирать карту природных особенностей;
- формировать ТЗ-промпт для лендинга на `claude.ai/design`;
- optionally формировать ТЗ для investor deck;
- давать прозрачный cross-sell только в рамках v1.1 scope.

## 2. Стек

### Backend

- Python 3.12+
- aiogram 3
- FastAPI для API админки, healthchecks и internal endpoints
- LangGraph
- PostgreSQL 16+
- Redis 7+ для фоновых задач, rate-limit и временных locks
- SQLAlchemy 2 + Alembic
- Pydantic v2
- httpx
- structlog или стандартный logging с JSON formatter

### LLM / AI

- Основная LLM: Anthropic Claude Sonnet 4.6, model id: `claude-sonnet-4-6`
- STT: OpenAI `gpt-4o-transcribe`
- TTS: Yandex SpeechKit, voice `marina`
- Observability: LangSmith

### Frontend админки

Допустимые варианты:

- MVP: FastAPI + Jinja2 + HTMX + Tailwind CDN
- Production-preferred: React/Vite + FastAPI REST API

Рекомендация для скорости: FastAPI + Jinja2 + HTMX. Это уменьшит объём фронтенд-кода и ускорит запуск.

## 3. Сервисы в docker-compose

Минимальный набор:

```yaml
services:
  bot:
    build: .
    command: python -m app.bot.main
    depends_on:
      - postgres
      - redis

  api:
    build: .
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    depends_on:
      - postgres
      - redis

  worker:
    build: .
    command: python -m app.worker.main
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine

  redis:
    image: redis:7-alpine
```

Опционально:

- `caddy` — reverse proxy и TLS.
- `admin-frontend` — если React/Vite вынесен отдельно.
- `otel-collector` — если позже понадобится redaction перед LangSmith или параллельный OTEL export.

## 4. Роли компонентов

### aiogram bot

Отвечает только за Telegram:

- принимает text/voice;
- скачивает voice;
- вызывает STT;
- вызывает LangGraph engine;
- отправляет text/voice response;
- обрабатывает команды `/start`, `/reset`, `/help`, `/voice_on`, `/voice_off`;
- не содержит методическую логику.

### LangGraph engine

Отвечает за методику:

- хранит состояние интервью;
- выбирает следующий node;
- вызывает Бабура;
- запускает guardrails;
- фиксирует фазу;
- фиксирует `personality_dev_level`;
- решает, когда активировать Cartographer/Assembler;
- формирует финальный артефакт;
- возвращает готовый безопасный ответ в Telegram layer.

### PostgreSQL

Отвечает за пользователей, сессии, сообщения, checkpoints, промпты, настройки, guardrail incidents, STT/TTS логи, артефакты и админских пользователей.

### Redis / worker

Отвечает за асинхронную генерацию артефактов, retry jobs, rate limiting и locks, чтобы один Telegram user не породил два параллельных graph turn.

### Web-админка

Позволяет редактировать системный промпт Бабура, helper prompts, настройки моделей, смотреть сессии, phase/personality state, guardrail incidents, финальные артефакты, включать maintenance mode и вручную завершать/сбрасывать сессию.

## 5. Основные user flows

### 5.1. Текстовый диалог

1. Пользователь пишет `/start`.
2. Бот создаёт новую сессию.
3. LangGraph генерирует первое сообщение Бабура с cross-sell-прозрачностью v1.1.
4. Пользователь отвечает.
5. Graph обновляет state.
6. Бабур ведёт калибровку.
7. После 3–5 сообщений фиксируется фазовая гипотеза.
8. Graph ведёт пользователя по одной из веток.

### 5.2. Голосовой диалог

1. Пользователь отправляет voice message.
2. aiogram скачивает файл.
3. `STTService` отправляет файл в OpenAI `gpt-4o-transcribe`.
4. Transcript сохраняется в `messages`.
5. Graph обрабатывает transcript как обычный user input.
6. Если `voice_reply_mode = auto` и вход был голосом, ответ дополнительно синтезируется через Yandex TTS `marina`.
7. Бот отправляет voice + краткий text fallback.

### 5.3. Короткая сессия «Защита»

1. Graph фиксирует повторяющиеся вопросы, уход в обобщения или спор с вопросом.
2. После второго семантического повтора выставляется `phase = Защита`.
3. Бабур мягко закрывает сессию.
4. Обязательно выдаётся A2-семя.
5. Cartographer создаёт короткий эскиз наблюдений.
6. Сессия получает `outcome = short-session`.

### 5.4. Кризис

1. Graph фиксирует кризисные маркеры.
2. `phase = Кризис`.
3. Бабур признаёт тяжесть состояния.
4. Бабур не проводит коучинг и не делает психологическую работу.
5. Бабур направляет к живым людям.
6. Сессия получает `outcome = crisis-walk-away`.

### 5.5. Полная сессия «Крылья»

1. Graph фиксирует признаки готовности.
2. Бабур ведёт A3-каскады, A1 при метриках, A2 на завершении.
3. Cartographer фоном собирает природные особенности.
4. Assembler формирует landing TZ.
5. Если есть реальная investor situation — формирует investor deck TZ.
6. Сессия получает `outcome = completed`.
7. При `cross_sell_readiness = ready` Бабур знакомит с одним следующим узлом: Беруни, Навои или Улугбек.

## 6. Команды Telegram

- `/start` — начать или продолжить сессию.
- `/reset` — сбросить текущую сессию после подтверждения.
- `/help` — короткая справка.
- `/voice_on` — отвечать голосом, когда возможно.
- `/voice_off` — отвечать только текстом.
- `/status` — показать текущий этап кратко, без внутренней диагностики.

## 7. Нефункциональные требования

### Надёжность

- Один входящий Telegram update должен обрабатываться ровно один раз.
- Для каждого `telegram_user_id` нужен distributed lock на время обработки turn.
- При падении LLM/STT/TTS пользователь получает честный fallback.
- Состояние не теряется после перезапуска контейнеров.

### Безопасность

- Секреты не хранятся в репозитории.
- Все токены в исходном документе считать скомпрометированными.
- Админка закрыта авторизацией.
- Логи не должны содержать полные API keys.
- В LangSmith не отправлять лишние персональные данные без необходимости.

### Качество диалога

- Один вопрос за раз.
- Короткие реплики.
- Бот не спорит с фаундером.
- Бот предлагает гипотезу и принимает поправку.
- Бот не нарушает scope персон.
- Бот не задаёт B1/B2 вопросы.
- Бот избегает частицы «не» в речи к фаундеру.

## 8. Definition of Done

Проект считается готовым к MVP-запуску, если:

- локальный запуск проходит командой `docker compose up -d`;
- миграции применяются автоматически или одной командой;
- Telegram bot отвечает текстом;
- voice input transcribes через `gpt-4o-transcribe`;
- voice output synthesizes через Yandex `marina`;
- LangGraph checkpoint восстанавливает сессию;
- админка редактирует активные промпты;
- prompt hot-reload работает для новых turn;
- guardrails логируют нарушения;
- LangSmith показывает trace turn;
- GitHub Actions деплоит на VPS;
- regression test `Iv-distillation` проходит;
- нет hardcoded secrets.
