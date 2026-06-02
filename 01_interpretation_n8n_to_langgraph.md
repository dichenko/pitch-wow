# 01. Интерпретация исходного n8n-промпта в LangGraph

## 1. Что изменилось концептуально

Исходный документ был написан как ТЗ на n8n workflow: Telegram Trigger, ветка text/voice, Postgres state, LLM node, guardrails function node, retry, sendMessage, post-message branches.

В LangGraph эту схему нужно трактовать иначе:

- n8n-ноды становятся **узлами графа** или **сервисами вокруг графа**.
- `state` становится типизированным объектом `PitchWowState`.
- Postgres используется в двух слоях: LangGraph checkpointing для восстановления графа и доменные таблицы для сессий, промптов, настроек, логов, артефактов и админки.
- Guardrails становятся отдельным **подграфом валидации и переписывания**.
- Handoff-и становятся **асинхронными jobs/subgraphs**, а не отдельными n8n workflow.
- Telegram перестаёт быть «местом методики». Telegram — только транспорт.

Главный принцип реализации:

> Методика должна быть детерминированно зашита в граф, state machine, БД и guardrails. LLM получает свободу в формулировках, но не в управлении процессом.

## 2. Карта переноса n8n → LangGraph

| Исходная n8n часть | LangGraph / Python-эквивалент | Комментарий |
|---|---|---|
| Telegram Trigger | `aiogram` handler | Принимает update, определяет тип сообщения, создаёт `IncomingMessage`. |
| Branch text/voice | `InputNormalizer` service | Текст идёт сразу, voice скачивается через Telegram API. |
| Whisper ASR | `STTService` на OpenAI `gpt-4o-transcribe` | Возвращает transcript + metadata. |
| Load state by chat_id | LangGraph checkpointer + `sessions` table | `thread_id = tg_chat_id` или `session_id`. |
| Compose context | `PromptRegistry` + `StateSerializer` | Системный промпт берётся из БД, не из env. |
| Anthropic Claude node | `babur_interviewer_node` | Основной LLM-вызов Claude Sonnet 4.6. |
| Guardrails Function node | `guardrails_subgraph` | Проверки, retry, rewrite, incident log. |
| Retry up to 2 | `rewrite_node` + counter в state | После 2 неудач — safe fallback. |
| Update state | LangGraph state update + domain repositories | История и метрики пишутся после каждого turn. |
| Telegram sendMessage | `TelegramResponder` | Отправка находится вне LLM и не принимает сырые ответы без guardrails. |
| Cartographer sub-workflow | `cartographer_job` / `cartographer_subgraph` | Фоновая сборка карты природных особенностей. |
| Pitch Skeleton Assembler | `assembler_job` / `assembler_subgraph` | Генерация landing TZ и optional deck TZ. |
| Cross-sell Navigator | Удалён | По v1.1 cross-sell — mode/capability Бабура. |
| PDF rendering | Отменено как default | Default output — prompt/TZ для `claude.ai/design`; markdown fallback. |

## 3. Что из v1.1 Patch обязательно учесть

### 3.1. Персона Бабур

В Telegram виден только Бабур:

- ИИ-ассистент Pitch Wow по распаковке.
- Возраст голоса — 18 лет.
- Архетип — peer-стартапер.
- Всегда честно сообщает, что он ИИ-ассистент.
- Не притворяется живым человеком и не говорит «я тоже был фаундером».

### 3.2. 4-узловая труба

В первом сообщении и cross-sell разрешено называть только:

- Бабур — Pitch Wow / распаковка.
- Беруни — Insta-аудит SMM.
- Навои — контент-завод.
- Улугбек — аналитика + A2A.
- Амир — мудрый голос холдинга soft-retail.ai.

Запрещено называть фаундеру: Авиценна, Томирис, Мадина.

### 3.3. Вторая ось калибровки

Кроме фазы `Защита | Кризис | Крылья`, граф должен фиксировать:

- `личность`
- `бизнес`
- `синергия`

Это поле называется `personality_dev_level`. Оно не является отдельным прямым вопросом. Это фоновая гипотеза, обновляемая по речи пользователя.

### 3.4. Mirror-and-bid

Если пользователь дважды подряд отвечает макро-фактами вместо личного слоя, Бабур переключается:

1. Mirror: назвать замеченный паттерн.
2. Hypothesis: дать гипотезу природной силы.
3. Bid: попросить однословное подтверждение или поправку.

### 3.5. Новый output

Старый PDF-output отменяется как default. Новый default:

- карта природных особенностей;
- ТЗ-промпт для лендинга на `claude.ai/design`;
- optional investor deck TZ только при `investor_situation = реальная-в-работе`.

## 4. Что не переносить буквально

1. Не создавать отдельный Cross-sell Navigator.
2. Не строить output вокруг PDF как основного артефакта.
3. Не хранить системный промпт только в `.env`.
4. Не делать guardrails простыми regex-only проверками. Regex нужен, но часть проверок должна идти через LLM-классификатор.
5. Не делать всё в одном огромном prompt. Методика должна быть в коде, graph state и правилах переходов.

## 5. Ядро MVP

MVP считается годным, если:

- бот стабильно ведёт Telegram-диалог;
- voice → STT работает через `gpt-4o-transcribe`;
- при голосовом входе ответ может уходить голосом через Yandex SpeechKit `marina`;
- LangGraph сохраняет и восстанавливает состояние;
- Бабур проходит первые 3–5 минут калибровки;
- есть маршрутизация в `Защита`, `Кризис`, `Крылья`;
- guardrails блокируют основные нарушения;
- админка позволяет менять системный промпт, helper prompts и ключевые настройки без деплоя;
- LangSmith показывает trace каждого turn;
- по завершении полной сессии создаётся структурированный артефакт и landing TZ.
