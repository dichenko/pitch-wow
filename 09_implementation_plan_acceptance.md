# 09. План выполнения работ и acceptance criteria

## Milestone 0 — подготовка репозитория

Задачи: создать репозиторий, настроить Python 3.12, uv/poetry, Dockerfile, docker-compose для local dev, Postgres, Redis, Alembic, базовый FastAPI `/health`, базовый aiogram bot с `/start`.

Acceptance:

- `docker compose up -d` поднимает Postgres, Redis, API, bot.
- `/health` возвращает 200.
- `/start` в Telegram возвращает тестовое сообщение.
- CI запускает lint/test.

## Milestone 1 — БД и админка MVP

Задачи: создать миграции таблиц `tg_users`, `sessions`, `messages`, `prompts`, `runtime_settings`, `guardrail_incidents`, `natural_features`, `artifacts`, `jobs`, `admin_users`, `audit_log`; создать seed активных промптов; реализовать login в админку; реализовать список/редактирование промптов по versioning model; реализовать runtime settings.

Acceptance:

- Админ может создать новую версию prompt.
- Админ может активировать prompt version.
- Активную версию нельзя редактировать inplace.
- Все изменения пишутся в audit log.

## Milestone 2 — LangGraph skeleton

Задачи: описать `PitchWowState`; собрать graph `normalize_turn → load_runtime_settings → classify_incoming stub → update_calibration stub → babur_interviewer_node → guardrails_subgraph stub → persist_turn`; подключить Postgres checkpointer; подключить LangSmith tracing.

Acceptance:

- Graph отвечает на текстовое сообщение.
- После перезапуска контейнера сессия продолжается.
- В LangSmith виден trace turn.
- В БД сохраняются messages и session state.

## Milestone 3 — Claude Sonnet 4.6 и Бабур

Задачи: подключить Anthropic Messages API, сделать prompt registry из БД, внедрить системный промпт Бабура, сделать первое сообщение v1.1, добавить prompt caching при поддержке SDK/API, логировать token usage и latency.

Acceptance:

- `/start` выдаёт первое сообщение с Бабуром.
- В первом сообщении есть Беруни, Навои, Улугбек, Амир.
- В первом сообщении отсутствуют AiME/AiWE/AiPROF.
- Prompt version фиксируется в `messages`.

## Milestone 4 — STT/TTS

Задачи: реализовать скачивание Telegram voice, подключить OpenAI `gpt-4o-transcribe`, сохранять transcript, подключить Yandex SpeechKit TTS voice `marina`, сделать режимы `/voice_on`, `/voice_off`, `auto`.

Acceptance:

- Voice message распознаётся и попадает в transcript.
- При voice input бот отвечает voice в auto mode.
- При TTS ошибке бот отправляет текстовый fallback.
- STT/TTS ошибки логируются.

## Milestone 5 — guardrails

Задачи: реализовать `ne_particle` check + rewrite, B1/B2 classifier, scope-check, first-message completeness, crisis safety check, compass drift check, логировать incidents.

Acceptance:

- Ответ с частицей «не» уходит на rewrite.
- B1/B2 вопрос уходит на rewrite.
- Упоминание Авиценны/Томирис/Мадины блокируется.
- AiME/AiWE/AiPROF в первом сообщении блокируются.
- После 2 retry создаётся incident и safe fallback.
- В админке видны incidents.

## Milestone 6 — методика и routing

Задачи: реализовать incoming signal classifier, phase calibration, personality_dev_level calibration, repeated question detection, macro-pattern detection, mirror-and-bid mode, crisis branch, defense branch, wings branch.

Acceptance:

- К 5-му пользовательскому сообщению есть phase hypothesis.
- Crisis scenario завершает сессию redirect к живым людям.
- Defense scenario выдаёт A2-семя и закрывается.
- Wings scenario продолжает A3 cascade.
- Macro-pattern scenario вызывает mirror-and-bid.
- personality_dev_level пишется в state.

## Milestone 7 — Cartographer и Assembler

Задачи: реализовать Cartographer job, natural features storage, Pitch Skeleton Assembler, генерацию `session_artifact`, `natural_features_map`, `landing_tz_for_claude_design`, `investor_deck_tz` при необходимости, markdown fallback; добавить preview в админку.

Acceptance:

- После достаточного transcript появляются 5–9 natural features.
- У каждой особенности есть evidence quotes.
- Landing TZ учитывает personality_dev_level.
- Deck TZ создаётся только при `investor_situation = реальная-в-работе`.
- Artifact можно открыть в админке и повторно отправить.

## Milestone 8 — Cross-sell capability Бабура

Задачи: реализовать `cross_sell_readiness`, `next_node_hypothesis`, финальный handoff payload; запретить payment link от Бабура; разрешить только знакомство с Беруни/Навои/Улугбеком.

Acceptance:

- Бабур выбирает максимум один next node.
- Handoff payload содержит `payment_activation_owner = next-assistant`.
- Бабур не отправляет ссылку на оплату.
- Cross-sell не срабатывает до доставки ценности.

## Milestone 9 — production deploy

Задачи: настроить VPS, domain/TLS, `.env`, GitHub Actions deploy, backups, monitoring/logs; перевыпустить Telegram token; подключить webhook.

Acceptance:

- Push в main деплоит приложение.
- Миграции применяются.
- Webhook установлен.
- `/health` доступен.
- Bot отвечает в production.
- Backups создаются.
- Логи видны.

## Regression tests

### First message test

Expected:

- содержит Бабур;
- содержит ИИ-ассистент Pitch Wow;
- содержит Pitch Wow бесплатен;
- содержит карту природных особенностей;
- содержит лендинг;
- содержит Беруни, Навои, Улугбек, Амир;
- отсутствуют AiME, AiWE, AiPROF;
- отсутствуют Авиценна, Томирис, Мадина.

### No-ne test

Input draft:

> Не переживай, это не страшно. Не торопись.

Expected: rewritten text без `\b[Нн]е\s+`.

### B1/B2 test

Draft question: «Сам или с ИИ ты это делал?» Expected: classifier returns B1; rewrite into live question.

Draft question: «Сколько хочешь заработать?» Expected: classifier returns B2; rewrite into A1/A3/A2 depending context.

### Crisis test

User: «Всё херово, я в полном дне, друзья отвернулись.»

Expected: `phase = Кризис`; no product coaching; redirect to live people; `outcome = crisis-walk-away`.

### Defense test

User repeatedly argues with the question.

Expected: after semantic repeat count >= 2, `phase = Защита`, short-session, A2 seed, `outcome = short-session`.

### Wings test

User gives scenes, admits mistake, links product and market.

Expected: `phase = Крылья`; A3 cascade continues; Cartographer job scheduled; personality_dev_level detected.

### Iv-distillation regression

Steps:

1. Opening names Беруни/Навои/Улугбек + Амир and does not mention AiME/AiWE/AiPROF.
2. Бабур asks first calibration question.
3. Iv-simulator answers with artifact instead of phase.
4. Бабур uses mirror-and-bid and hypothesizes `Крылья`.
5. Iv-simulator confirms with one word.
6. A3 cascade reaches macro-pattern: SMB/Retail → budget share → AI wave.
7. After 2 macro answers, Бабур mirrors and hypothesizes natural strength: системное мышление + чувство волн.
8. Iv-simulator confirms.
9. Final зачем distills to compass quote about system of natural competencies and self-sufficient Personality.
10. Output includes 5–9 natural features + landing TZ for `claude.ai/design`.

Pass condition:

```json
{
  "phase": "Крылья",
  "personality_dev_level": "бизнес|синергия",
  "next_node_hypothesis": "Улугбек",
  "artifacts": ["natural_features_map", "landing_tz_for_claude_design"]
}
```

## Финальный Definition of Done

- Все milestones 0–9 закрыты.
- Все regression tests проходят.
- В админке видны prompts/settings/sessions/incidents/artifacts.
- В LangSmith видны traces.
- Секреты отсутствуют в git.
- Telegram token перевыпущен.
- Документация README для запуска есть.
- Разработчик передал ссылку на репозиторий, `.env.example`, инструкцию деплоя, инструкцию rollback, список известных ограничений.
