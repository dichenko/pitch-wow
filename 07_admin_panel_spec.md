# 07. Web-админка

## 1. Назначение

Админка нужна, чтобы методолог и владелец продукта могли управлять ботом без деплоя: менять промпты, модели, смотреть сессии, guardrail incidents, анализировать нарушения методики, просматривать и перегенерировать артефакты, управлять фичами и maintenance mode.

## 2. Роли

- `owner`: полный доступ, управление админами, изменение всех промптов и настроек, просмотр audit log.
- `admin`: промпты, настройки, сессии, артефакты, incidents.
- `viewer`: только просмотр.

## 3. Авторизация

MVP-вариант: email + password, password hash через Argon2 или bcrypt, cookie session, CSRF protection.

Production-вариант: Telegram Login Widget или OAuth, allowlist Telegram ID, 2FA для owner.

## 4. Разделы админки

### Dashboard

Показывает active sessions, completed sessions, short-session count, crisis-walk-away count, phase distribution, personality_dev_level distribution, guardrail incidents today, STT/TTS errors, LLM cost estimate, average latency, LangSmith project link.

### Sessions

Таблица:

| Поле | Описание |
|---|---|
| User | Telegram username / id |
| Status | active/completed/terminated |
| Phase | unknown/Защита/Кризис/Крылья |
| Personality | личность/бизнес/синергия |
| Messages | число сообщений |
| Last activity | время |
| Outcome | итог |
| Next node | Беруни/Навои/Улугбек/none |

Карточка сессии: transcript, summary, state JSON, direct quotes, natural features, artifacts, guardrail incidents, LangSmith trace links, admin notes.

Действия: pause, resume, reset, force phase, force personality level, regenerate summary, regenerate artifacts, mark completed, export transcript.

### Prompts

Список промптов:

- `babur.system`
- `classifier.incoming_signals`
- `classifier.question_class`
- `rewriter.no_ne_particle`
- `guard.scope_check`
- `guard.crisis_safety`
- `guard.compass_drift`
- `cartographer.system`
- `assembler.system`
- `summarizer.session`
- `tts.voice_friendly`

Функции: create new version, diff versions, activate version, rollback, test prompt on fixture, store changelog, show last editor.

Правило: нельзя редактировать активную версию inplace. Любое изменение создаёт новую версию.

### Runtime settings

Настройки: primary LLM model, classifier model, temperature, max tokens, STT model, Yandex voice, TTS speed, voice reply mode default, guardrail max retries, Telegram parse mode, maintenance mode, artifact generation enabled, LangSmith project name.

### Guardrail incidents

Фильтры: reason, session, resolved/unresolved, date, prompt version, model.

Карточка incident: original response, rewritten response, violation reason, retry count, trace link, state fragment, кнопки `mark resolved` и `create prompt improvement note`.

### Artifacts

Список: natural features map, landing TZ, investor deck TZ, markdown fallback.

Действия: preview, copy, download `.md`, send again to user, regenerate, compare versions.

### Users

Telegram ID, username, sessions, voice mode, blocked flag, created_at, last_seen.

Действия: block/unblock user, reset voice mode, start admin note.

### Audit log

Фиксировать login, logout, prompt created, prompt activated, setting changed, session forced, artifact regenerated, user blocked.

## 5. API endpoints

```http
POST /admin/login
POST /admin/logout
GET  /admin/me

GET    /admin/prompts
GET    /admin/prompts/{key}
POST   /admin/prompts/{key}/versions
POST   /admin/prompts/{id}/activate
GET    /admin/prompts/{id}/diff/{other_id}
POST   /admin/prompts/{id}/test

GET  /admin/sessions
GET  /admin/sessions/{session_id}
POST /admin/sessions/{session_id}/pause
POST /admin/sessions/{session_id}/resume
POST /admin/sessions/{session_id}/force-phase
POST /admin/sessions/{session_id}/force-personality
POST /admin/sessions/{session_id}/regenerate-artifacts

GET  /admin/settings
PUT  /admin/settings/{key}

GET  /admin/incidents
GET  /admin/incidents/{id}
POST /admin/incidents/{id}/resolve
```

## 6. Prompt test fixtures

В админке нужен раздел тестовых fixtures:

- first_message;
- defense_short_session;
- crisis_redirect;
- wings_normal;
- macro_pattern_mirror_and_bid;
- iv_distillation_regression;
- scope_violation;
- b1_b2_rewrite;
- no_ne_particle_rewrite.

Каждый fixture содержит input messages, expected phase, expected forbidden terms absent, expected required markers, expected JSON schema.

## 7. UX требования

- Интерфейс простой, без сложного дизайна.
- Главная ценность — быстро увидеть, где бот сломал методику.
- Везде показывать prompt version и model.
- В сессии давать ссылку на LangSmith trace.
- Для длинного transcript — collapsible blocks.
- JSON state показывать красиво, с copy button.

## 8. Безопасность админки

- Все POST/PUT требуют CSRF token.
- Session cookie: HttpOnly, Secure, SameSite=Lax.
- Rate limit login.
- Password policy.
- Audit log без возможности удаления через UI.
- Роль viewer не видит raw API errors с секретами.
