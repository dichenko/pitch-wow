# Pitch Wow → LangGraph: пакет документов для разработки

**Дата подготовки:** 2026-06-01  
**Целевой стек:** aiogram 3 + LangGraph + PostgreSQL + Docker + GitHub Actions CI/CD + Web-админка + OpenAI STT + Yandex SpeechKit TTS + LangSmith.  
**Основная LLM:** Claude Sonnet 4.6 (`claude-sonnet-4-6`).

## Состав архива

1. `01_interpretation_n8n_to_langgraph.md` — как исходный n8n-промпт интерпретирован в LangGraph.
2. `02_technical_specification.md` — основное ТЗ программисту.
3. `03_langgraph_architecture.md` — граф, состояния, узлы, переходы, runtime-контракты.
4. `04_system_prompt_babur.md` — системный промпт Бабура v0.1 для MVP.
5. `05_helper_prompts_and_guardrails.md` — вспомогательные промпты классификаторов, валидаторов и сборщиков артефактов.
6. `06_database_schema.md` — схема PostgreSQL, индексы, миграции, сущности админки.
7. `07_admin_panel_spec.md` — ТЗ на web-админку для промптов, настроек, сессий, логов и артефактов.
8. `08_devops_docker_github_actions.md` — Docker, env, CI/CD, деплой на VPS.
9. `09_implementation_plan_acceptance.md` — план работ, milestones, тесты, acceptance criteria.

## Ключевые решения

- **LangGraph является ядром методики.** aiogram только принимает/отправляет Telegram-сообщения.
- **Один видимый агент:** Бабур. Cartographer и Pitch Skeleton Assembler — фоновые функции/подграфы, а не отдельные собеседники.
- **Cross-sell Navigator как отдельный агент удалён.** Cross-sell — capability Бабура в финале сессии при явном или достаточном сигнале готовности.
- **Output v1.1:** карта природных особенностей + ТЗ-промпт для лендинга на `claude.ai/design`; investor deck — только если есть реальная инвесторская ситуация.
- **Состояние хранится в PostgreSQL и LangGraph checkpoints.** Таблицы доменной модели нужны для админки, аналитики и восстановления.
- **Guardrails перед отправкой в Telegram обязательны.** Проверяются запрет частицы «не» в речи к фаундеру, B1/B2-вопросы, scope по персонам, первое сообщение, кризисный redirect, drift от компаса.

## Важное замечание по безопасности

В исходном n8n-документе встречался Telegram bot token. В этих документах токен намеренно не воспроизводится. Перед запуском требуется выпустить новый токен через BotFather, старый считать скомпрометированным.

## Источники для разработчика

- Исходный файл пользователя: `n8n-migration-tz-v1.1.md`.
- LangGraph persistence/checkpoints: https://docs.langchain.com/oss/python/langgraph/persistence
- LangSmith observability: https://docs.langchain.com/langsmith/observability
- aiogram FSM: https://docs.aiogram.dev/en/v3.28.1/dispatcher/finite_state_machine/
- OpenAI STT: https://developers.openai.com/api/docs/guides/speech-to-text
- Anthropic Claude models: https://docs.anthropic.com/en/docs/about-claude/models
- Yandex SpeechKit TTS: https://aistudio.yandex.ru/docs/en/speechkit/tts/
