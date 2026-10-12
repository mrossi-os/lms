# OS LMS - CLAUDE.md

Custom extension app for the ELITE LMS platform, built on Frappe Framework. Adds AI-powered RAG (Retrieval-Augmented Generation) assistant, custom doctypes, overrides, and UI customizations.

## AI / RAG Pipeline

### Data Flow

```
Course Lesson (EditorJS JSON)
  → LessonContentParser (parse blocks, extract video transcripts via YoutubeTranscriber/VimeoTranscriber)
  → chunk_text() (split into overlapping chunks)
  → OpenAIApiEmbedder (text-embedding-3-small, batched at 200K tokens)
  → RedisRagStorage (redisvl SearchIndex, HNSW, cosine similarity)
  → Course Lesson fields updated (index_status, indexed_at)
```

### Service Pattern

Service classes (e.g. `IngestionService`) follow these conventions:

1. **Lazy properties for dependencies** — Heavy objects (`settings`, `rag_db`, `logger`) are declared as `_attribute: Type | None = None` class-level attributes and exposed via `@property` that initializes on first access and caches in the private attribute.
2. **Settings via `OsLmsSettings` dataclass** — The `settings` property reads `LMSA Settings` doctype once, builds an `OsLmsSettings` dataclass with defaults, and caches it. Dependencies that need settings (e.g. `RagDB`) receive the dataclass via constructor injection.
3. **Logger** — Initialized lazily via `frappe.logger("os_lmsa", allow_site=True)`.
4. **State management on processed documents** — Methods that process documents (e.g. `ingest_lesson`) check for an `index_status` guard (`"processing"` = skip), set it to `"processing"` before work, then update to `"indexed"` (with `indexed_at` timestamp) on success or `"failed"` on error. The final `save()` + `db.commit()` is in a `finally` block to ensure state is always persisted.
5. **Error handling** — Business logic is wrapped in `try/except/finally`. The `except` sets failure state and logs the error, then re-raises. The `finally` persists the document state.

### Redis Vector Index

- Library: `redisvl` (SearchIndex)
- Index name: `lmsa:{site}:chunks`
- Prefix: `lmsa:{site}`
- Fields: `embedding` (vector, 1536 dims, HNSW, cosine), `course` (tag), `lesson` (tag), `content` (text), `chunk_index` (numeric)
- RediSearch requires **db 0**

### Configuration

**`site_config.json`**:
- `redis_vector_store` — Redis URL for vector storage (required)
- `regenerate_rag_index` — Set to `"1"` to force index rebuild on migrate

**Environment variables**:
- `OPENAI_API_KEY` — Required for embeddings and chat
- `DEBUG_MODE` — Set to `1` to enable debugpy

## Realtime Voice (Simulations)

Provider-agnostic speech-to-speech voice modality for AI simulations. **OpenAI Realtime** is the default provider (WebRTC transport); **Gemini Live** is available via the `realtime_provider` setting (WebSocket transport). Config lives in `LMSA Settings → Realtime / Voice` (enable/disable, provider, model, voice, turn detection, max session seconds). **Audio never passes through Frappe** — Frappe is the control plane only: it mints ephemeral tokens (`ai.realtime.api.create_voice_session`), persists transcript turns relayed by the client (`persist_transcript_turn`), records session duration, and enqueues the post-session debrief. The client streams audio directly to the provider using the ephemeral token. Provider logic lives in `ai/utils/realtime/` (ABC + registry + per-provider adapters); control-plane endpoints in `ai/realtime/api.py`; frontend in `frontend/src/oslms/` (`composables/realtime/`, `composables/useRealtimeSession.js`, `components/simulations/VoiceSession.vue`).

## Elite API (`os_lms/elite_api/`)

Read-only API that external systems (first: TrueSkill) call with a key to list courses/batches and fetch their students (name, codice fiscale, email, progress). Plan, per-phase reports and decisions: `docs/elite-api/PIANO.md`; client-facing guide (Italian): `docs/elite-api/guida-integrazione.md`.

- **Keys** (`keys.py`, doctype `Elite API Key`): `elite_<prefix>_<secret>`; the doc name is the prefix, only a SHA-256 of the secret is stored. Revoked/expired keys are final.
- **Auth** (`auth.py`): `before_request` hook verifies `X-Elite-Api-Key` only on `/api/(v1/|v2/)?method/os_lms.os_lms.elite_api.vN.*`, then runs the request as the disabled technical user `elite-api@elite-api.invalid` (role `Elite API Client`, desk access but no perms — see `setup.setup_elite_api_client`). It must stay a `before_request` hook: `lms.auth.authenticate` runs earlier than any os_lms `auth_hook`. It refuses (400 `invalid_request`) keys sent with a `cmd` parameter (Frappe runs `form_dict.cmd` BEFORE routing `/api/` paths, so it would execute any whitelisted method as the client user), an `Authorization` header or a logged-in session, and refuses keys when the client user carries roles beyond its own + Frappe's automatic ones. `after_request` writes `Elite API Access Log` and commits (Frappe rolls back GETs). Endpoints use `@frappe.whitelist(methods=["GET"])` + `@elite_api_endpoint`.
- **Endpoints** (`v1.py`, `progress.py`): `ping`, `list_courses`, `list_batches`, `get_course_students`, `get_batch_students`. Progress SQL is literal (no f-strings); each list query has a COUNT twin kept aligned by `test_lists_agree_with_the_summaries`. Parameters are `str | None` parsed by `errors.parse_*` (400, not Frappe's 417).
- **Key management** (`admin.py`) for the SPA tab `frontend/src/oslms/components/eliteApi/EliteApiSettings.vue`: System Manager + Gestore only.
- **Tests**: `os_lms/tests/test_elite_api_*.py`; shared data in `tests/elite_api_fixture.py` (written with `db_insert`, deleted by exact name).
