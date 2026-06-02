# 06. PostgreSQL схема

## 1. Общие принципы

- Alembic — единственный способ изменения схемы.
- Все timestamps — `TIMESTAMPTZ`.
- Все внешние API события логируются.
- Секреты в БД не храним, только ссылки на env/secret names.
- Полный transcript хранится в `messages`, а summary — в `sessions`.

## 2. Расширения

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

Если используются embeddings для повторов:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 3. Пользователи Telegram

```sql
CREATE TABLE tg_users (
  id BIGSERIAL PRIMARY KEY,
  telegram_user_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  language_code TEXT,
  is_bot BOOLEAN DEFAULT FALSE,
  raw_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  voice_reply_mode TEXT NOT NULL DEFAULT 'auto'
    CHECK (voice_reply_mode IN ('auto', 'always', 'never')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 4. Сессии

```sql
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tg_user_id BIGINT NOT NULL REFERENCES tg_users(id),
  telegram_chat_id BIGINT NOT NULL,

  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'completed', 'terminated', 'error')),

  phase TEXT NOT NULL DEFAULT 'unknown'
    CHECK (phase IN ('unknown', 'Защита', 'Кризис', 'Крылья')),
  phase_confidence NUMERIC(3,2),
  phase_calibrated_at TIMESTAMPTZ,

  personality_dev_level TEXT
    CHECK (personality_dev_level IN ('личность', 'бизнес', 'синергия')),
  personality_confidence NUMERIC(3,2),

  current_stage TEXT NOT NULL DEFAULT 'opening',
  current_substage TEXT,

  a3_depth INT NOT NULL DEFAULT 0,
  repeated_question_count INT NOT NULL DEFAULT 0,
  macro_pattern_count INT NOT NULL DEFAULT 0,

  investor_situation TEXT NOT NULL DEFAULT 'отсутствует'
    CHECK (investor_situation IN ('реальная-в-работе', 'гипотетическая', 'отсутствует')),
  target_investor_hint TEXT
    CHECK (target_investor_hint IN ('VC', 'стратег', 'ангел', 'акселератор')),

  cross_sell_readiness TEXT NOT NULL DEFAULT 'not-ready'
    CHECK (cross_sell_readiness IN ('ready', 'conditional', 'not-ready')),
  next_node_hypothesis TEXT NOT NULL DEFAULT 'none'
    CHECK (next_node_hypothesis IN ('Беруни', 'Навои', 'Улугбек', 'none')),

  outcome TEXT
    CHECK (outcome IN ('completed', 'short-session', 'crisis-walk-away')),

  state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  summary TEXT,

  langgraph_thread_id TEXT UNIQUE,
  langsmith_thread_id TEXT,

  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  last_message_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_tg_user_id ON sessions(tg_user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_phase ON sessions(phase);
CREATE INDEX idx_sessions_last_message_at ON sessions(last_message_at);
```

## 5. Сообщения

```sql
CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'admin')),
  content TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'text'
    CHECK (source IN ('text', 'voice', 'admin', 'system')),

  telegram_message_id BIGINT,
  telegram_file_id TEXT,

  stt_provider TEXT,
  stt_model TEXT,
  stt_confidence NUMERIC(4,3),
  raw_stt_response JSONB,

  tts_provider TEXT,
  tts_voice TEXT,
  tts_audio_path TEXT,

  llm_provider TEXT,
  llm_model TEXT,
  prompt_version TEXT,
  token_input INT,
  token_output INT,
  latency_ms INT,

  langsmith_trace_id TEXT,
  langsmith_run_id TEXT,

  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_langsmith_trace_id ON messages(langsmith_trace_id);
```

## 6. Промпты

```sql
CREATE TABLE prompts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL,
  type TEXT NOT NULL
    CHECK (type IN ('system', 'classifier', 'rewriter', 'guardrail', 'artifact_generator', 'summarizer', 'tts')),
  version TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  model_override TEXT,
  temperature NUMERIC(3,2),
  max_tokens INT,
  json_schema JSONB,
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  changelog TEXT,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(key, version)
);

CREATE UNIQUE INDEX idx_prompts_one_active_per_key
ON prompts(key)
WHERE is_active = TRUE;
```

## 7. Runtime settings

```sql
CREATE TABLE runtime_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  description TEXT,
  updated_by TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Примеры ключей: `llm.primary_model`, `llm.classifier_model`, `stt.provider`, `stt.openai_model`, `tts.provider`, `tts.yandex_voice`, `guardrails.max_retries`, `telegram.parse_mode`, `features.voice_reply_enabled`, `features.artifact_generation_enabled`, `features.maintenance_mode`.

## 8. Guardrail incidents

```sql
CREATE TABLE guardrail_incidents (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
  message_id BIGINT REFERENCES messages(id) ON DELETE SET NULL,

  reason TEXT NOT NULL,
  original_response TEXT NOT NULL,
  rewritten_response TEXT,
  retry_count INT NOT NULL DEFAULT 0,
  resolved BOOLEAN NOT NULL DEFAULT FALSE,

  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  langsmith_trace_id TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_guardrail_incidents_reason ON guardrail_incidents(reason);
CREATE INDEX idx_guardrail_incidents_session ON guardrail_incidents(session_id);
```

Причины: `ne_particle`, `dead_question_class`, `scope_violation`, `first_message_incomplete`, `crisis_safety`, `compass_drift`, `json_schema_error`, `llm_error`.

## 9. Natural features

```sql
CREATE TABLE natural_features (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  description TEXT,
  evidence_quotes JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence NUMERIC(3,2) NOT NULL,
  axis TEXT CHECK (axis IN ('личность', 'бизнес', 'синергия')),
  notes_for_assembler TEXT,

  source TEXT NOT NULL DEFAULT 'cartographer',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_natural_features_session_id ON natural_features(session_id);
```

## 10. Артефакты

```sql
CREATE TABLE artifacts (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

  artifact_type TEXT NOT NULL
    CHECK (artifact_type IN (
      'session_artifact',
      'natural_features_map',
      'landing_tz_for_claude_design',
      'investor_deck_tz',
      'markdown_fallback'
    )),

  content_md TEXT,
  content_json JSONB,
  file_path TEXT,
  public_url TEXT,

  personality_dev_level TEXT
    CHECK (personality_dev_level IN ('личность', 'бизнес', 'синергия')),
  investor_situation TEXT
    CHECK (investor_situation IN ('реальная-в-работе', 'гипотетическая', 'отсутствует')),
  cross_sell_readiness TEXT
    CHECK (cross_sell_readiness IN ('ready', 'conditional', 'not-ready')),
  next_node_hypothesis TEXT
    CHECK (next_node_hypothesis IN ('Беруни', 'Навои', 'Улугбек', 'none')),

  telegram_message_id BIGINT,
  delivered_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_artifacts_session_id ON artifacts(session_id);
CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
```

## 11. Jobs

```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled')),

  session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB,
  error TEXT,

  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_status_run_after ON jobs(status, run_after);
CREATE INDEX idx_jobs_session_id ON jobs(session_id);
```

## 12. Admin users и audit log

```sql
CREATE TABLE admin_users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT UNIQUE,
  telegram_user_id BIGINT UNIQUE,
  username TEXT,
  password_hash TEXT,
  role TEXT NOT NULL DEFAULT 'admin'
    CHECK (role IN ('owner', 'admin', 'viewer')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  admin_user_id BIGINT REFERENCES admin_users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  before JSONB,
  after JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 13. LangGraph checkpoint tables

Использовать официальный Postgres checkpointer LangGraph. Не смешивать его внутренние таблицы с доменными таблицами. Миграции checkpointer запускать отдельно в bootstrap.

Пример настройки:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
graph = builder.compile(checkpointer=checkpointer)
```

## 14. Начальные настройки

```sql
INSERT INTO runtime_settings(key, value, description) VALUES
('llm.primary_model', '"claude-sonnet-4-6"', 'Основная модель Бабура'),
('stt.openai_model', '"gpt-4o-transcribe"', 'Модель распознавания речи'),
('tts.yandex_voice', '"marina"', 'Голос Yandex SpeechKit'),
('guardrails.max_retries', '2', 'Максимум rewrite retries'),
('features.voice_reply_enabled', 'true', 'Голосовые ответы включены'),
('features.artifact_generation_enabled', 'true', 'Генерация артефактов включена');
```
