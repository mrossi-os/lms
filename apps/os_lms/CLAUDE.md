# OS LMS - CLAUDE.md

Custom extension app for the ELITE LMS platform, built on Frappe Framework. Adds AI-powered RAG (Retrieval-Augmented Generation) assistant, custom doctypes, overrides, and UI customizations.

## Directory Structure

```
apps/os_lms/
├── pyproject.toml                          # Dependencies & build config (flit_core)
└── os_lms/                                 # Frappe app package
    ├── __init__.py                         # Version: 0.0.1
    ├── hooks.py                            # App hooks, overrides, scheduled tasks, fixtures
    ├── setup.py                            # Post-install/migrate setup (language, custom fields, Redis index)
    ├── debug.py                            # Debug mode init (debugpy on port 5678)
    ├── badge_utils.py                      # Cache clearing on badge insert
    │
    ├── os_lms/                             # Core business logic
    │   ├── api.py                          # REST endpoints (lesson position, course duration)
    │   ├── override_api.py                 # Frappe API overrides (sidebar, lesson details, search)
    │   ├── override_utils.py               # Utility overrides (course details with feature_sections)
    │   │
    │   ├── doctype/                        # Custom Frappe doctypes
    │   │   ├── lmsa_settings/              # AI config (embedding model, chunk size, top_k, LLM model, system prompt)
    │   │   ├── lmsa_query_log/             # User questions and AI responses (audit trail)
    │   │   ├── lmsa_transcript_cache/      # Cached video transcripts (YouTube, Vimeo)
    │   │   └── lms_course_learning_item/   # Child table for course feature sections
    │   │
    │   ├── ai/                             # AI assistant module
    │   │   ├── api.py                      # Whitelisted endpoints (start ingestion, get status)
    │   │   ├── ingestion.py                # Legacy RAG pipeline (chunking, embedding, vector ops)
    │   │   ├── ingestion_service.py        # IngestionService class (main ingestion orchestrator)
    │   │   ├── scheduler.py                # Daily sync_stale_materials job
    │   │   │
    │   │   └── utils/                      # AI utilities
    │   │       ├── rag_db.py               # RagDB facade (settings, embedder, storage)
    │   │       ├── oslms_settings.py       # OsLmsSettings dataclass (AI config values)
    │   │       ├── lesson_parser.py        # EditorJS block parser (paragraphs, headers, lists, embeds)
    │   │       ├── video_transcriber.py    # YouTube transcript extraction with caching (legacy)
    │   │       ├── llm_chatbot.py          # LLMChatbot wrapper (receives OsLmsSettings)
    │   │       │
    │   │       ├── transcriber/            # Video transcription implementations
    │   │       │   ├── youtube.py          # YoutubeTranscriber (youtube_transcript_api)
    │   │       │   └── vimeo.py            # VimeoTranscriber (Vimeo API text tracks)
    │   │       │
    │   │       ├── llm/                    # LLM chatbot abstraction
    │   │       │   ├── chatbot.py          # Chatbot ABC (set_model, set_system_prompt, ask)
    │   │       │   └── gpt_chatbot.py      # GptChatbot implementation (OpenAI GPT-4o-mini)
    │   │       │
    │   │       └── rag/                    # RAG storage abstraction
    │   │           ├── embedding_item.py   # EmbeddingItem dataclass (text + vector)
    │   │           ├── text_embedder.py    # TextEmbedder ABC (set_model, embed_text)
    │   │           ├── openai_api_embedder.py  # OpenAI embeddings implementation (batched)
    │   │           ├── rag_storage.py      # RagStorage ABC (save, search, delete_by_lesson)
    │   │           └── redis_rag_storage.py    # RediSearch/redisvl implementation
    │   │
    │   └── overrides/                      # Frappe doctype overrides
    │       ├── email_account.py            # Fixes SMTP size limit (ESMTP)
    │       └── sqlite.py                   # Extends search to include Programs, Quizzes, Assignments
    │
    ├── public/                             # Static assets
    │   ├── css/os_lms.css                  # Theme variables and login styles
    │   └── js/os_lms.js                    # Custom scripts placeholder
    │
    ├── templates/
    │   └── base.html                       # Extends Frappe base, includes custom CSS
    │
    ├── fixtures/
    │   └── custom_field.json               # Custom fields (LMS Program, Settings, Course Lesson)
    │
    └── locale/                             # Translation files
```

## Doctypes

| Doctype                    | Type        | Purpose                                          |
|----------------------------|-------------|--------------------------------------------------|
| **LMSA Settings**          | Single      | AI config: embedding model, chunk size/overlap, top_k, LLM model, system prompt |
| **LMSA Query Log**         | Document    | Audit trail for student AI questions              |
| **LMSA Transcript Cache**  | Document    | Cached video transcripts (YouTube, Vimeo)         |
| **LMS Course Learning Item** | Child Table | Feature sections for course pages               |

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

### Key Classes

- **`IngestionService`** (`ai/ingestion_service.py`) — Main service class for lesson ingestion (see Service Pattern below)
- **`RagDB`** (`ai/utils/rag_db.py`) — Facade that wires settings, embedder, and storage together. Receives `OsLmsSettings` via constructor
- **`OsLmsSettings`** (`ai/utils/oslms_settings.py`) — Dataclass holding AI configuration (enabled, embedding_model, chunk_size, chunk_overlap, top_k, llm_model, system_prompt)
- **`Chatbot`** (`ai/utils/llm/chatbot.py`) — ABC for LLM chatbots (set_model, set_system_prompt, ask)
- **`GptChatbot`** (`ai/utils/llm/gpt_chatbot.py`) — OpenAI GPT implementation (default: gpt-4o-mini)
- **`OpenAIApiEmbedder`** (`ai/utils/rag/openai_api_embedder.py`) — Calls OpenAI embeddings API with automatic batching
- **`RedisRagStorage`** (`ai/utils/rag/redis_rag_storage.py`) — Stores/queries vectors in RediSearch via redisvl
- **`LessonContentParser`** (`ai/utils/lesson_parser.py`) — Parses EditorJS blocks into plain text
- **`YoutubeTranscriber`** (`ai/utils/transcriber/youtube.py`) — Extracts YouTube captions via youtube_transcript_api
- **`VimeoTranscriber`** (`ai/utils/transcriber/vimeo.py`) — Extracts Vimeo text tracks via Vimeo API

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

## Frontend Components (`frontend/src/oslms/`)

Custom Vue 3 components and composables for the os_lms extension. Located in the main frontend directory (not inside `apps/os_lms`).

### Composables

- **`useLessonIngestion`** (`composables/useLessonIngestion.js`) — Shared composable for lesson AI ingestion. Provides status, icon, ingestion trigger, error handling via toast. Used by both `LessonAIStatus` and `LessonAIIngestion` components.

### AI Components (`components/ai/`)

- **`ChatBot.vue`** — AI chat interface for students
- **`Course/LessonAIStatus.vue`** — Compact icon-only ingestion status with tooltip (used in course outline)
- **`Course/LessonAIIngestion.vue`** — Full ingestion panel with status label and action button (used in lesson form)
- **`Settings/AISettings.vue`** — Admin AI settings panel

### Other Components

- **`CourseFeaturedSections.vue`** / **`FeatureSectionEditor.vue`** — Course feature sections
- **`Home/WelcomeWithOverallProgress.vue`** — Homepage welcome with progress
- **`Form/Switch.vue`** — Custom switch input
- **`IconPicker.vue`** — Icon selection component

## Hooks

- **After Migrate**: setup language, custom fields, Redis index
- **Doctype Overrides**: Email Account (SMTP fix), SQLite search (extended types)
- **API Overrides**: sidebar settings, lesson creation details, search, course details
- **Scheduled Tasks**: `sync_stale_materials` (daily) — re-indexes changed lessons

## Dependencies

- `redisvl` — Redis vector library
- `numpy >= 1.24.0`
- `redis >= 7.0.0, < 8.0.0`
- `youtube_transcript_api` — YouTube caption extraction
- `debugpy` — Remote debugging
