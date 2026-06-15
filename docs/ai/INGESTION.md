# Lesson Ingestion (RAG pipeline)

L'ingestion trasforma il contenuto di una `Course Lesson` (EditorJS + transcripts di video/file) in chunk vettoriali memorizzati in Redis, pronti per la retrieval del tutor AI.

Sorgente: `apps/os_lms/os_lms/os_lms/ai/ingestion/` + le astrazioni in `ai/utils/rag/` e `ai/utils/oslms_settings.py`.

## Architettura a livelli

```
                          ┌──────────────────────────────┐
  Whitelisted API ───────►│  IngestionService            │
  (api.py)                │  (ingestion/service.py)      │
                          │                              │
                          │  - ingest_lesson(lesson)     │
                          │  - reindex_lesson_content()  │
                          │  - add_lesson_to_ingest_     │
                          │    queue(lesson)             │
                          │  - search_chunks_by_course() │
                          │  - search_chunks_by_lessons()│
                          └──────────┬───────────────────┘
                                     │ owns
                                     ▼
                          ┌──────────────────────────────┐
                          │  RagDB facade                │
                          │  (utils/rag_db.py)           │
                          │                              │
                          │  - ingest_data(...)          │
                          │  - search(...)               │
                          │  - _chunk_text(...)          │
                          └─┬──────────────┬─────────────┘
                            │              │
                  ┌─────────▼───┐    ┌─────▼────────────┐
                  │ TextEmbedder│    │ RagStorage (ABC) │
                  │   (ABC)     │    │                  │
                  │             │    │  - save          │
                  │  - set_     │    │  - search        │
                  │    settings │    │  - delete_by_    │
                  │  - embed_   │    │    lesson        │
                  │    text     │    └────────┬─────────┘
                  └──────┬──────┘             │
                         │                    │
                  ┌──────▼──────────┐  ┌──────▼──────────┐
                  │ OpenAIApiEmbedder│ │ RedisRagStorage │
                  │ (utils/rag/)     │ │ (utils/rag/)    │
                  └──────────────────┘ └─────────────────┘
```

Convenzioni:
- **Service Pattern** (vedi `apps/os_lms/CLAUDE.md`): `IngestionService` espone le operazioni di alto livello con lazy properties per le dipendenze pesanti (`settings`, `rag_db`, `logger`).
- **Composition + DI**: `RagDB` riceve `OsLmsSettings` via costruttore. `OpenAIApiEmbedder` riceve i settings via `set_settings`. `RedisRagStorage` legge `frappe.conf.redis_vector_store` autonomamente.
- **ABC al confine**: `TextEmbedder` e `RagStorage` sono ABC pure, così un embedder alternativo (es. locale, Anthropic) o uno storage diverso (es. pgvector) può essere iniettato senza toccare `RagDB`.

## Pipeline di ingestion (write path)

`IngestionService.ingest_lesson(lesson)` esegue, in `service.py:76-108`:

1. **Gate**: throw se `LMSA Settings.enabled = False`.
2. **Idempotenza**: se `lesson.index_status == "processing"` esce subito (un altro worker sta già lavorando sulla stessa lezione).
3. **Stato**: setta `lesson.index_status = "processing"`, save + commit immediato.
4. **Parsing**: `LessonContentParser(lesson).extract_text()` estrae plain text dai blocchi EditorJS della lezione (vedi sezione successiva).
5. **Throw** se il testo è vuoto.
6. **Delega a RagDB**: `self.rag_db.ingest_data(lesson.course, lesson.name, text)`.
7. **Stato finale**: `index_status = "indexed"` + `indexed_at = now_datetime()` su successo, `"failed"` su eccezione (e re-raise). Il `save + commit` finale è in `finally` — lo stato persiste sempre.

`RagDB.ingest_data(course, lesson, text)` (`utils/rag_db.py:32-44`):
1. **Wipe**: `RedisRagStorage.delete_by_lesson(course, lesson)` — query RediSearch per chunk con quei tag e li cancella in blocco. Garantisce che una rispondi su contenuto modificato non lasci residui obsoleti.
2. **Chunking**: `_chunk_text(text)` — split a caratteri con `chunk_size` e `chunk_overlap` da settings (default 1000/200). Sliding window con `start = end - chunk_overlap`. Skip dei chunk solo-whitespace.
3. **Throw** se la lista chunk è vuota.
4. **Embedding**: `OpenAIApiEmbedder.embed_text(chunks)` — batched HTTP calls a `https://api.openai.com/v1/embeddings`. I batch sono creati con un budget approssimativo di 200 000 token (assunzione 4 char/token), così richieste molto lunghe vengono spezzate automaticamente.
5. **Storage**: `RedisRagStorage.save(course, lesson, embeddings)` — un singolo `SearchIndex.load(...)` di tutti i chunk con i metadati.

## Estrazione del testo (`LessonContentParser`)

`utils/lesson_parser.py` parsa il contenuto EditorJS di una `Course Lesson`:

- Legge `lesson.content` + `lesson.instructor_content` (concatenati). Entrambi sono JSON con campo `blocks`.
- Aggiunge `lesson.body` (markdown) come prima parte.
- Per ogni blocco invoca l'handler corrispondente al `type`:

| Block type | Handler | Output |
|---|---|---|
| `paragraph` | `_parse_paragraph` | `data.text` |
| `header` | `_parse_header` | `[H{level}] {text}` |
| `list` | `_parse_list` | `- item` (uno per riga) |
| `quote` | `_parse_quote` | `"text" — caption` |
| `code` | `_parse_code` | `data.code` |
| `image` | `_parse_image` | `data.caption` (solo caption) |
| `embed` | `_parse_embed` | `caption + " " + VideoTranscriber.transcribe(provider, source)` |
| `upload` | `_parse_upload` | `FileTranscriber.transcribe(file_url, file_type)` |
| altro | `_parse_unknown` | `data.text` (fallback) |

Embed e upload chiamano i transcriber esterni (YouTube/Vimeo per i video, generico per i file uploadati). Le caption sono incluse anche se il transcript fallisce.

Output finale: stringa unica con i pezzi separati da `\n\n` (di default).

## Pipeline di retrieval (read path)

`IngestionService` espone due metodi di ricerca; il chaining con un chatbot/tutor avviene fuori dal service:

- `search_chunks_by_course(course, question)` → cerca su tutte le lezioni del corso (`utils/rag_db.py:46-48` con `lessons=[]`).
- `search_chunks_by_lessons(course, lessons, question)` → cerca solo nelle lezioni passate. Il chiamante decide il set `lessons` (tipicamente `allowed = completed_lessons ∪ {current_lesson}` per non rivelare contenuto di lezioni che lo studente non ha ancora completato).

Il vector search interno (`RedisRagStorage.search` in `redis_rag_storage.py:85-109`):
- Costruisce un filtro `Tag("course") == course`.
- Se `lessons` è non-vuoto, lo AND-a con un OR di `Tag("lesson") == lesson_i`.
- Esegue `VectorQuery` con `vector_field_name="embedding"`, distanza COSINE, top_k da `OsLmsSettings.top_k` (default 6).
- Ritorna `[{"content": ..., "lesson": ...}, ...]`.

## Vector index Redis

Configurato in `RedisRagStorage._redisIndex` (lazy):

- **Engine**: `redisvl` (`SearchIndex` con schema dichiarativo).
- **URL**: da `frappe.conf.redis_vector_store` (throw a init se mancante).
- **DB**: 0 (RediSearch lo richiede — vedi nota in `apps/os_lms/CLAUDE.md`).
- **Storage type**: `hash`.
- **Index name**: `lmsa:{site}:chunks`. Prefix: `lmsa:{site}`.
- **Fields**:
  - `embedding` — vector, 1536 dims (matching `text-embedding-3-small`), HNSW, COSINE, float32.
  - `chunk_id` — tag, sortable.
  - `chunk_index` — numeric.
  - `content` — text.
  - `course` — tag.
  - `lesson` — tag.
- **Bootstrap**: `RedisRagStorage.create_index()` ricrea l'indice se `frappe.conf.regenerate_rag_index == "1"`, altrimenti lo crea solo se non esiste (controllato via `info()` + try/except).

## API HTTP

Endpoint whitelisted in `ingestion/api.py`:

### `start_lesson_ingestion(lesson_id)` — POST

- Auth: teacher-only via `_load_lesson` (verifica moderator role, course instructor su quel corso, o LMS Enrollment dello studente).
- Costruisce un `IngestionService()` e chiama `ingest_lesson(lesson)`.
- Ritorna `{"success": True}`. Errori risalgono come eccezioni Frappe.

### `get_lesson_ingestion_status(lesson_id)` — GET

- Esistenza check su `Course Lesson`; carica il doc.
- Ritorna direttamente lo stato dai custom field della lezione:

```python
{
    "status": lesson.index_status or "not_ingested",
    "last_ingested_on": lesson.indexed_at,
}
```

- Stati possibili per `status`: `"processing"`, `"pending"`, `"indexed"`, `"failed"`, `"not_ingested"` (quando `index_status` è null/empty). Sono gli stessi valori che `IngestionService.ingest_lesson` scrive sulla lezione lungo il ciclo di vita.
- Niente lookup su `LMSA Material` e niente hash compare: il client può decidere autonomamente se ri-triggerare l'ingestion in base allo `status` e all'eventuale staleness percepita di `last_ingested_on`.

## Scheduler

`hooks.py:156-159`:

```python
scheduler_events = {
    "daily": [
        "os_lms.os_lms.ai.ingestion.scheduler.reindex_lesson_content",
    ],
}
```

`ingestion/scheduler.py:reindex_lesson_content` chiama `IngestionService().reindex_lesson_content()` che (`service.py:55-74`) seleziona tutte le `Course Lesson` con `index_status in ("pending", None, "")` e ri-esegue `ingest_lesson` su ognuna. Logga gli errori per lezione senza interrompere il batch.

Un instructor può quindi marcare una lezione `index_status = "pending"` (es. via `add_lesson_to_ingest_queue` in `service.py:47-53`) e affidare la re-indicizzazione al run notturno, oppure forzarla dall'endpoint `start_lesson_ingestion`.

## Configurazione

Da `LMSA Settings` (single doctype, letta via `load_settings()` in `ai/utils/llm/__init__.py:139-188`):

| Campo | Default | Uso |
|---|---|---|
| `enabled` | `False` | Gate globale: tutti gli entry-point throw se disabilitato |
| `embedding_model` | `text-embedding-3-small` | Modello OpenAI per `/v1/embeddings` |
| `chunk_size` | `1000` | Caratteri per chunk |
| `chunk_overlap` | `200` | Caratteri di overlap fra chunk consecutivi |
| `top_k` | `6` | Numero di chunk ritornati dal vector search |
| `openai_key` | (vuoto) | API key OpenAI per embeddings — letta come Data field |

Da `site_config.json`:

| Chiave | Required | Note |
|---|---|---|
| `redis_vector_store` | sì | URL Redis per il vector store (es. `redis://redis:6379`) |
| `regenerate_rag_index` | no | Settare a `"1"` per forzare il rebuild dell'indice al prossimo `RedisRagStorage.create_index()` (chiamato in `after_migrate`) |

## Doctype coinvolti

| Doctype | Ruolo | Stato |
|---|---|---|
| `LMSA Settings` (Single) | Configurazione AI/RAG | Implementato |
| `Course Lesson` | Sorgente del contenuto; track `index_status`, `indexed_at` via custom field — è la single source of truth per lo stato di indicizzazione | Implementato (custom_field.json) |
| `LMSA Query Log` | Audit delle domande studente al tutor | Implementato |
| `LMSA Transcript Cache` | Cache dei transcript video (YouTube/Vimeo) | Implementato |
| `LMSA Material` / `LMSA Chunk` | Persistenza in MariaDB dei material/chunk (citati nella roadmap originale in `CLAUDE.md`) | Non implementati — la persistenza avviene solo in Redis e lo stato sta sui custom field di `Course Lesson` |

> **Nota**: la prima versione dell'ingestion (legacy `pipeline.py`, ora rimosso) prevedeva una persistenza dual MariaDB + Redis con `rehydrate_vectors()` per ricostruire l'indice e un doctype dedicato `LMSA Material` per il tracking. L'architettura attuale tiene i vettori in Redis e lo stato sui custom field di `Course Lesson`. Una perdita del vector store costringe a re-indicizzare via `reindex_lesson_content` (che richiede `Course Lesson.index_status` impostato a `pending` per le lezioni da rifare).

## Note operative

- **Costo embedding**: ogni `ingest_lesson` cancella e ri-crea tutti i chunk della lezione → ri-embeddare l'intero testo. Non c'è caching per chunk già visti né content-hash dedup (l'endpoint di status non confronta più un hash del contenuto: si limita a riflettere `lesson.index_status`).
- **Idempotenza parziale**: il guard `index_status == "processing"` impedisce esecuzioni concorrenti sulla stessa lezione, ma non protegge fra worker su nodi diversi senza un lock distribuito.
- **Embedding model lock-in**: l'indice Redis è creato con `dims: 1536` hardcoded per `text-embedding-3-small`. Cambiare embedding model richiede `regenerate_rag_index=1` E re-indicizzare tutte le lezioni.
- **Rate limit OpenAI**: nessun retry/backoff a livello applicativo — un 429 fa fallire l'ingestion (`OpenAIApiEmbedder._embed_batch` throw direttamente). Per ora il volume di lezioni rende non urgente, ma è un punto di fragilità.
- **Transcriber esterni**: errori in `VideoTranscriber`/`FileTranscriber` non fanno fallire l'ingestion — il parser ritorna la caption sola. Questo significa che un video con transcript fallito viene indicizzato con poco testo: la query semantica perderà richiamo su quella lezione senza segnale visibile.

## File rilevanti (cheat sheet)

| Layer | File |
|---|---|
| HTTP endpoints | `apps/os_lms/os_lms/os_lms/ai/ingestion/api.py` |
| Service / orchestration | `apps/os_lms/os_lms/os_lms/ai/ingestion/service.py` |
| Scheduler | `apps/os_lms/os_lms/os_lms/ai/ingestion/scheduler.py` |
| RAG facade | `apps/os_lms/os_lms/os_lms/ai/utils/rag_db.py` |
| Settings dataclass | `apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py` |
| Settings loader | `apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py` (`_load_settings` / `load_settings`) |
| Embedder ABC | `apps/os_lms/os_lms/os_lms/ai/utils/rag/text_embedder.py` |
| OpenAI embedder | `apps/os_lms/os_lms/os_lms/ai/utils/rag/openai_api_embedder.py` |
| Storage ABC | `apps/os_lms/os_lms/os_lms/ai/utils/rag/rag_storage.py` |
| Redis storage | `apps/os_lms/os_lms/os_lms/ai/utils/rag/redis_rag_storage.py` |
| Lesson parser | `apps/os_lms/os_lms/os_lms/ai/utils/lesson_parser.py` |
| Video transcriber | `apps/os_lms/os_lms/os_lms/ai/utils/transcriber/` (youtube.py, vimeo.py) |
| Hook scheduler | `apps/os_lms/os_lms/hooks.py:156-159` |
