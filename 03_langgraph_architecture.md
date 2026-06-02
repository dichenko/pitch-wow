# 03. Архитектура LangGraph

## 1. Общая схема

```text
Telegram
  ↓
aiogram handlers
  ↓
InputNormalizer
  ↓
STTService, если voice
  ↓
LangGraph Coaching Engine
  ↓
Guardrails Subgraph
  ↓
TelegramResponder
  ↓
TTSService, если нужен voice response
```

Фоновые задачи:

```text
LangGraph Coaching Engine
  ├─ Cartographer Job
  ├─ Pitch Skeleton Assembler Job
  └─ Artifact Delivery Job
```

## 2. PitchWowState

```python
from typing import Literal, TypedDict, Optional, Any

Phase = Literal["unknown", "Защита", "Кризис", "Крылья"]
PersonalityLevel = Literal["личность", "бизнес", "синергия"]
Outcome = Literal["completed", "short-session", "crisis-walk-away"]

class Message(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    ts: str
    source: Literal["text", "voice", "admin", "system"]
    langsmith_run_id: Optional[str]

class PitchWowState(TypedDict, total=False):
    session_id: str
    telegram_chat_id: int
    telegram_user_id: int
    messages: list[Message]
    current_stage: str
    current_substage: Optional[str]
    phase: Phase
    phase_confidence: float
    phase_calibrated_at: Optional[str]
    personality_dev_level: Optional[PersonalityLevel]
    personality_confidence: float
    a3_depth: int
    last_question_class: Optional[Literal["A1", "A2", "A3", "B1", "B2"]]
    repeated_question_count: int
    macro_pattern_count: int
    live_observations: list[str]
    direct_quotes: list[str]
    signals_for_cartographer: list[str]
    natural_features: list[dict[str, Any]]
    investor_situation: Literal["реальная-в-работе", "гипотетическая", "отсутствует"]
    target_investor_hint: Optional[Literal["VC", "стратег", "ангел", "акселератор"]]
    cross_sell_readiness: Literal["ready", "conditional", "not-ready"]
    next_node_hypothesis: Literal["Беруни", "Навои", "Улугбек", "none"]
    pending_response: Optional[str]
    validated_response: Optional[str]
    guardrail_retries: int
    guardrail_incidents: list[dict[str, Any]]
    artifacts: dict[str, Any]
    outcome: Optional[Outcome]
```

## 3. Основной граф

```text
START
  ↓
normalize_turn
  ↓
load_runtime_settings
  ↓
classify_incoming
  ↓
update_calibration
  ↓
route_by_phase
      ├─ crisis_node
      ├─ defense_node
      └─ wings_interviewer_node
  ↓
guardrails_subgraph
  ↓
persist_turn
  ↓
schedule_background_jobs
  ↓
END
```

## 4. Узлы графа

### `normalize_turn`

Вход: текст пользователя, metadata от Telegram, признак voice/text. Выход: сообщение в `state.messages`.

Задачи: удалить технический мусор, сохранить transcript, пометить источник `voice`, нормализовать язык, поставить lock на session/user.

### `load_runtime_settings`

Загружает из БД активный системный промпт Бабура, helper prompts, модели, temperature, max tokens, guardrail settings, TTS/STT settings и feature flags.

### `classify_incoming`

LLM-классификатор или hybrid classifier определяет кризисные маркеры, повтор вопроса, макро-паттерн, наличие метрик/цифр, явный сигнал cross-sell, investor situation.

### `update_calibration`

Обновляет `phase`, `phase_confidence`, `personality_dev_level`, `personality_confidence`, `macro_pattern_count`, `repeated_question_count`.

Правила:

- к 5-му пользовательскому сообщению должна быть гипотеза по фазе;
- `Кризис` имеет приоритет над всеми остальными ветками;
- `Защита` включается при повторе, споре с вопросом, уходе в обобщения;
- `Крылья` включается при готовности видеть ошибку, деталях, сценах, спокойном признании провалов;
- `personality_dev_level` фиксируется фоном, без прямого вопроса.

### `route_by_phase`

```python
def route_by_phase(state: PitchWowState) -> str:
    if state["phase"] == "Кризис":
        return "crisis_node"
    if state["phase"] == "Защита":
        return "defense_node"
    return "wings_interviewer_node"
```

В первые 3–5 сообщений, пока `phase = unknown`, используется `wings_interviewer_node` в режиме мягкой калибровки, но с запретом углубляться в product coaching до калибровки.

### `crisis_node`

Назначение: безопасно завершить кризисную ветку. Запрещено: терапевтические интервенции, анализ чувств, поиск причин травмы, мотивационный коучинг, советы по психическому состоянию. Разрешено: признать тяжесть, остановить распаковку, направить к живым людям, сказать, что к Продукту можно вернуться позже.

### `defense_node`

Назначение: короткая сессия без продавливания. Задачи: мягко признать, что сейчас лучше сохранить рамку; дать A2-семя; сохранить уважение; создать короткий эскиз карты; завершить `outcome = short-session`.

### `wings_interviewer_node`

Основной узел Бабура. Режимы: opening, calibration, A3 cascade, A1 benchmark, A2 seed, mirror-and-bid, synthesis, artifact handoff, cross-sell capability.

### `guardrails_subgraph`

```text
guard_ne_particle
  ↓
guard_dead_questions
  ↓
guard_scope
  ↓
guard_first_message
  ↓
guard_crisis_safety
  ↓
guard_compass_drift
  ↓
pass_or_rewrite
```

После любой ошибки: если `guardrail_retries < 2`, вызвать `rewrite_node`; если retry исчерпаны, fallback + incident log.

### `persist_turn`

Пишет user message, assistant message, state snapshot, phase/personality, guardrail incidents, token usage, model, LangSmith trace URL/id.

### `schedule_background_jobs`

Создаёт jobs: Cartographer после калибровки и далее инкрементально; Assembler при достаточном материале; Artifact delivery после генерации output; Self-termination job для защиты/unknown.

## 5. Checkpointing

Использовать LangGraph checkpointer с PostgreSQL. Рекомендуемый `thread_id`:

```text
telegram:{telegram_chat_id}:session:{session_id}
```

Если пользователь делает `/reset`, создаётся новый `session_id`, значит новый thread.

## 6. Human-in-the-loop для админки

В MVP не требуется ручное вмешательство в каждый turn, но админка должна позволять поставить сессию на паузу, вручную изменить phase/personality, добавить private admin note, перегенерировать артефакт, выключить voice output, отправить service message.
