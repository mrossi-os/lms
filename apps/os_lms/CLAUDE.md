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
    │   │   ├── lmsa_settings/              # AI config (embedding model, chunk size, top_k)
    │   │   ├── lmsa_material/              # Tracks ingested lessons (status, hash, chunk count)
    │   │   ├── lmsa_chunk/                 # Individual text chunks with embeddings
    │   │   ├── lmsa_query_log/             # User questions and AI responses (audit trail)
    │   │   ├── lmsa_transcript_cache/      # Cached YouTube video transcripts
    │   │   └── lms_course_learning_item/   # Child table for course feature sections
    │   │
    │   ├── ai/                             # AI assistant module
    │   │   ├── api.py                      # Whitelisted endpoints (start ingestion, get status)
    │   │   ├── ingestion.py                # Legacy RAG pipeline (chunking, embedding, vector ops)
    │   │   ├── scheduler.py                # Daily sync_stale_materials job
    │   │   │
    │   │   └── utils/                      # AI utilities
    │   │       ├── rag_db.py               # RagDB facade (settings, embedder, storage)
    │   │       ├── lesson_parser.py        # EditorJS block parser (paragraphs, headers, lists, embeds)
    │   │       ├── video_transcriber.py    # YouTube transcript extraction with caching
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
| **LMSA Settings**          | Single      | AI config: model, chunk size/overlap, top_k       |
| **LMSA Material**          | Document    | Tracks ingested lessons (status, hash)            |
| **LMSA Chunk**             | Document    | Text chunks with embedding blobs                  |
| **LMSA Query Log**         | Document    | Audit trail for student AI questions              |
| **LMSA Transcript Cache**  | Document    | Cached YouTube transcripts                        |
| **LMS Course Learning Item** | Child Table | Feature sections for course pages               |

## AI / RAG Pipeline

### Data Flow

```
Course Lesson (EditorJS JSON)
  → LessonContentParser (parse blocks, extract YouTube transcripts)
  → chunk_text() (split into overlapping chunks)
  → OpenAIApiEmbedder (text-embedding-3-small, batched at 200K tokens)
  → RedisRagStorage (redisvl SearchIndex, HNSW, cosine similarity)
```

### Key Classes

- **`RagDB`** (`ai/utils/rag_db.py`) — Facade that wires settings, embedder, and storage together
- **`OpenAIApiEmbedder`** (`ai/utils/rag/openai_api_embedder.py`) — Calls OpenAI embeddings API with automatic batching
- **`RedisRagStorage`** (`ai/utils/rag/redis_rag_storage.py`) — Stores/queries vectors in RediSearch via redisvl
- **`LessonContentParser`** (`ai/utils/lesson_parser.py`) — Parses EditorJS blocks into plain text
- **`VideoTranscriber`** (`ai/utils/video_transcriber.py`) — Extracts YouTube captions with DB caching

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
