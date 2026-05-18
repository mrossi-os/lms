# Simulazioni AI — Integrazione su ELITE LMS (modulo `os_lms`)

*Adattamento operativo della specifica `PLAN.md` alla codebase esistente.*

Versione 1.0 — riferimento per l'implementazione interna nel modulo `apps/os_lms`.

> Documento di lavoro: rimanda a `PLAN.md` per la specifica funzionale e didattica completa (executive summary, prompt engineering, GDPR, roadmap). Qui si descrive **come** la feature viene calata nella struttura attuale del progetto.

---

## 1. Vincoli di progetto

La feature **non** è una nuova app Frappe (`ai_simulations`) come da specifica originale. Tutta la logica viene aggiunta a `apps/os_lms`, che già ospita:

- AI/RAG pipeline (`os_lms/os_lms/ai/`) con astrazioni `Chatbot`, `TextEmbedder`, `RagStorage` e dataclass `OsLmsSettings`.
- Service pattern consolidato (`IngestionService`) con stato persistito sul doctype e logger lazy.
- Doctype custom con prefisso `LMSA` (`LMSA Settings`, `LMSA Query Log`, `LMSA Transcript Cache`).
- Hook centralizzati in `os_lms/hooks.py` (override API, scheduler, fixtures, doc_events).
- Frontend custom in `frontend/src/oslms/` (componenti Vue, composables, integrato in `Lesson.vue`).

Implicazioni:

- I nuovi doctype usano il prefisso **`LMSA`** e vivono in `apps/os_lms/os_lms/os_lms/doctype/`.
- Endpoint REST esposti come `os_lms.os_lms.ai.simulations.api.*` (sotto-modulo del namespace AI esistente).
- Frontend in `frontend/src/oslms/components/simulations/` + nuove pagine sotto `frontend/src/pages/Simulations/`.
- Provider LLM riutilizza l'astrazione `Chatbot` esistente, estesa con interfaccia *chat-multi-turno* (oggi è single-shot Q&A).
- Configurazione provider e chiavi su `LMSA Settings` (Single) estendendo i campi attuali — niente nuovo Single doctype di settings.
- Niente nuova app Frappe; nessun cambio a `lms` upstream.

## 2. Stack mappato

| Componente specifica | Implementazione effettiva |
| --- | --- |
| App Frappe custom "ai_simulations" | Sotto-modulo `os_lms/os_lms/ai/simulations/` nel modulo `os_lms` |
| LLM testuale multi-provider | Layer `LLMProvider` provider-agnostico (vedi §3.3) con adapter OpenAI/Gemini/DeepSeek/Anthropic intercambiabili a runtime |
| STT (fase 2) | Adapter `os_lms/os_lms/ai/utils/stt/` (Whisper API in MVP) |
| TTS (fase 2) | Adapter `os_lms/os_lms/ai/utils/tts/` (OpenAI TTS in MVP) |
| Realtime voce (fase 3) | Eventualmente OpenAI Realtime API via WebSocket Frappe |
| Job asincroni | Frappe Background Jobs (RQ) — pattern già usato in `IngestionService` |
| Storage media | Frappe File (private) per gli audio; opzione S3 in fase 2 |
| Cache/Redis | Riuso connessione Redis di Frappe (NON Redis vector store, che resta per RAG) |
| Frontend | Vue 3 + frappe-ui in `frontend/src/oslms/` |
| Streaming | `frappe.realtime` (Socket.IO) — già operativo |

## 3. Architettura nel modulo `os_lms`

### 3.1 Struttura directory aggiunta

```
apps/os_lms/os_lms/
├── hooks.py                                       # +scheduler_events, +doc_events, +override
├── fixtures/
│   └── custom_field.json                          # +campi su Course Lesson (collegamento scenari)
└── os_lms/
    ├── ai/
    │   ├── simulations/                           # NUOVO sotto-modulo
    │   │   ├── __init__.py
    │   │   ├── api.py                             # endpoint REST whitelisted
    │   │   ├── orchestrator.py                    # SessionOrchestrator (ciclo di vita)
    │   │   ├── scenario_generator.py              # Prompt 1
    │   │   ├── role_play.py                       # Prompt 2 (system prompt + filtri)
    │   │   ├── debrief.py                         # Prompt 3 + parsing JSON
    │   │   ├── tasks.py                           # RQ job: generate_debrief
    │   │   ├── prompt_defense.py                  # filtri anti-injection post-generazione
    │   │   └── retention.py                       # purge audio scaduti (cron)
    │   └── utils/
    │       ├── llm/
    │       │   ├── chatbot.py                     # esistente, retro-compat (RAG tutor)
    │       │   ├── gpt_chatbot.py                 # esistente, adattato sopra LLMProvider
    │       │   ├── provider.py                    # NUOVO — LLMProvider ABC + ChatMessage/ChatResponse dataclass
    │       │   ├── registry.py                    # NUOVO — registry + factory get_provider(name)
    │       │   ├── config.py                      # NUOVO — ProviderConfig (model, base_url, api_key, extra_headers)
    │       │   ├── errors.py                      # NUOVO — eccezioni normalizzate (RateLimit, InvalidAuth, ContextWindow, …)
    │       │   └── providers/                     # NUOVO — adapter per servizio (intercambiabili a runtime)
    │       │       ├── __init__.py
    │       │       ├── openai_provider.py         # OpenAI API
    │       │       ├── gemini_provider.py         # Google Generative AI
    │       │       ├── deepseek_provider.py       # DeepSeek (OpenAI-compatible)
    │       │       ├── anthropic_provider.py      # Claude (opzionale, abilitabile da Settings)
    │       │       └── openai_compatible.py       # base class riusabile per qualunque endpoint OpenAI-compat (Ollama, LM Studio, vLLM, Together, Groq, …)
    │       ├── stt/                               # NUOVO (fase 2) — provider-agnostic
    │       │   ├── provider.py                    # STTProvider ABC + TranscriptionResult/Segment dataclass
    │       │   ├── registry.py                    # registry + factory get_stt_provider(config)
    │       │   ├── config.py                      # STTProviderConfig
    │       │   ├── errors.py                      # STTRateLimit, STTInvalidAudio, STTUnsupportedLanguage, …
    │       │   └── providers/
    │       │       ├── __init__.py
    │       │       ├── openai_whisper.py          # OpenAI Whisper API
    │       │       ├── deepgram_provider.py       # Deepgram Nova-3
    │       │       ├── google_stt.py              # Google Speech-to-Text v2
    │       │       ├── azure_stt.py               # Azure AI Speech (opzionale)
    │       │       ├── elevenlabs_stt.py          # ElevenLabs Scribe (opzionale)
    │       │       └── mock_stt.py                # test deterministico
    │       └── tts/                               # NUOVO (fase 2) — provider-agnostic
    │           ├── provider.py                    # TTSProvider ABC + AudioStream/SynthesisResult dataclass
    │           ├── registry.py
    │           ├── config.py                      # TTSProviderConfig (voice_id, format, sample_rate)
    │           ├── errors.py
    │           └── providers/
    │               ├── __init__.py
    │               ├── openai_tts.py              # OpenAI TTS-1 / gpt-4o-mini-tts
    │               ├── elevenlabs_tts.py          # ElevenLabs (qualità premium)
    │               ├── google_tts.py              # Google Cloud TTS
    │               ├── deepgram_tts.py            # Deepgram Aura
    │               ├── azure_tts.py               # Azure AI Speech (opzionale)
    │               └── mock_tts.py                # test deterministico
    └── doctype/
        ├── lmsa_simulation_scenario/              # NUOVO
        ├── lmsa_simulation_seed_variation/        # child di Scenario
        ├── lmsa_simulation_learning_objective/    # child di Scenario
        ├── lmsa_evaluation_rubric/                # NUOVO
        ├── lmsa_rubric_criterion/                 # child di Rubric
        ├── lmsa_simulation_session/               # NUOVO (submittable)
        ├── lmsa_simulation_turn/                  # NUOVO (document, non child)
        ├── lmsa_simulation_debrief/               # NUOVO
        ├── lmsa_criterion_score/                  # child di Debrief
        ├── lmsa_debrief_strength/                 # child di Debrief
        ├── lmsa_debrief_improvement/              # child di Debrief
        ├── lmsa_debrief_recommendation/           # child di Debrief
        └── lmsa_recording_consent_log/            # NUOVO (append-only)
```

Frontend:

```
frontend/src/
├── oslms/
│   ├── components/
│   │   └── simulations/
│   │       ├── SimulationLauncher.vue             # modale dalla lezione
│   │       ├── ChatSession.vue                    # UI chat live
│   │       ├── VoiceSession.vue                   # UI voce (fase 2)
│   │       ├── ConsentModal.vue                   # consenso audio
│   │       ├── DebriefView.vue                    # report finale
│   │       ├── ScenarioEditor.vue                 # editor docente
│   │       ├── RubricEditor.vue                   # editor rubrica drag&drop
│   │       └── InstructorDashboard.vue            # report e drill-down
│   ├── composables/
│   │   ├── useSimulationSession.js                # state machine + WebSocket
│   │   └── useSimulationDebrief.js                # polling/realtime debrief_ready
│   └── utils/
│       └── simulationRouter.js                    # registrazione rotte custom
└── pages/Simulations/
    ├── SimulationPlay.vue                         # /simulations/:session_id
    ├── SimulationDebrief.vue                      # /simulations/:session_id/debrief
    └── InstructorReports.vue                      # /simulations/admin/reports
```

### 3.2 Componenti principali

#### 3.2.1 `SessionOrchestrator` (`ai/simulations/orchestrator.py`)

Service class che segue il **Service Pattern** già consolidato in `IngestionService`:

- `_settings`, `_logger`, `_chatbot` come attributi `Type | None = None` con `@property` lazy.
- `settings` legge `LMSA Settings` e costruisce `OsLmsSettings` esteso (vedi §4.0).
- `start_session(scenario_id, modality, seed=None) -> LMSA Simulation Session`: genera variante (Prompt 1), persiste session + primo turno cliente, ritorna.
- `send_message(session_id, user_text) -> LMSA Simulation Turn`: append turno user, chiama LLM con cronologia, persiste turno assistant, emette eventi `frappe.realtime` per streaming.
- `end_session(session_id, reason)`: imposta `status = "completed" | "abandoned"`, lancia job RQ (`os_lms.os_lms.ai.simulations.tasks.generate_debrief`).
- Errori: try/except/finally con `status = "error"` + log; persistenza nel `finally` come fa `IngestionService`.

#### 3.2.2 Layer LLM provider-agnostico

Requisito esplicito: **non legarsi a un singolo fornitore**. Tutto il codice di business (orchestrator, debrief, role-play, futuro chat tutor) interagisce con un'unica astrazione `LLMProvider`; l'adapter specifico (OpenAI, Gemini, DeepSeek, Anthropic, OpenAI-compat self-hosted) è iniettato da una factory che legge la configurazione runtime. Cambiare provider → cambia un campo in `LMSA Settings`, nessun deploy.

Dettagli completi in §3.3. Riepilogo qui:

- **Interfaccia unica** `LLMProvider.chat(messages, *, system, temperature, max_tokens, stream, response_format) → ChatResponse`.
- **Tipi normalizzati** (`ChatMessage`, `ChatResponse`, `ChatChunk`, `Usage`) — i call site non vedono mai payload provider-specifici.
- **Selezione dinamica** via `registry.get_provider(name, config)`. Il nome arriva da `LMSA Settings.simulation_provider` o dal `provider_override` dello scenario.
- **Retro-compatibilità**: l'attuale `Chatbot` ABC (`ask(question, contexts)`) viene reimplementato sopra `LLMProvider` (un solo turno), così il chat tutor RAG continua a funzionare senza modifiche ai chiamanti.
- **Streaming** uniforme: `provider.chat(..., stream=True)` ritorna un `Iterator[ChatChunk]`; esposto in UI **solo via WebSocket** (`simulation:turn_chunk`), HTTP REST resta sincrono.
- **Errori normalizzati**: ogni adapter cattura le eccezioni native (es. `openai.RateLimitError`, `google.api_core.exceptions.ResourceExhausted`, `anthropic.APIStatusError`) e rilancia `LLMRateLimit`, `LLMInvalidAuth`, `LLMContextWindow`, `LLMServerError`, `LLMTimeout` definite in `errors.py`.
- **Fallback chain**: se la chiamata fallisce con `LLMRateLimit` / `LLMServerError` e `simulation_provider == "auto"`, l'orchestrator prova il provider successivo in `simulation_provider_fallback_order` (campo Long Text in Settings, CSV).
- **Structured output**: la `chat(..., response_format=...)` accetta uno schema astratto (`JsonSchema(schema=..., name=...)`); ogni adapter lo traduce nel meccanismo nativo (OpenAI `response_format`/JSON Schema, Gemini `response_schema`, Anthropic tool-use forzato, fallback "JSON via prompt + validazione pydantic" per provider senza supporto nativo). Usato dal debrief.

#### 3.2.3 `ScenarioGenerator`, `RolePlayPrompt`, `DebriefEngine`

Tre piccoli moduli con responsabilità singola, ognuno espone `build_prompt(...)` + `parse_output(...)`. I template di prompt vivono come **stringhe versionate dentro il codice** (`PROMPT_VERSION = "rp.v1"`, `"debrief.v1"`, `"gen.v1"`), salvate sul turno/debrief come `prompt_version` per audit e A/B. Nessun nuovo doctype "AI Prompt Template" — semplice e tracciabile via git.

#### 3.2.4 Voice Pipeline (fase 2)

Stessa filosofia del layer LLM: **due astrazioni provider-agnostiche** (`STTProvider`, `TTSProvider`) consumate dall'orchestrator, con adapter intercambiabili a runtime. Dettagli completi in §3.4 e §3.5.

Pipeline end-to-end:

```
[Browser MediaRecorder]
  ── chunk audio (Opus/WebM ~500ms) ─→
[POST /send_audio]
  → STTProvider.transcribe(audio_chunk) → text + confidence + segments
  → orchestrator.send_message(text)     → LLM (layer §3.3) → reply_text
  → TTSProvider.synthesize(reply_text)  → audio stream (MP3/Opus)
[WebSocket simulation:audio_chunk]
  ── stream base64 chunk ──→ [Browser AudioContext]
```

Punti chiave implementativi:

- **VAD (Voice Activity Detection) lato client**: rileva la fine dell'utterance e chiude la registrazione. In MVP fase 2 si usa `@ricky0123/vad-web` (libreria browser, no server load) o push-to-talk come fallback semplice.
- **Chunking server-side**: il chunk audio completo (utterance) viene passato a `STTProvider.transcribe`; non si fa streaming STT in fase 2 (latenza accettabile <2s con Whisper, <1s con Deepgram Nova). Lo **streaming STT** vero (parziali in tempo reale) arriva in fase 3.
- **Streaming TTS**: tutti i provider TTS moderni espongono streaming (chunk audio mentre la sintesi avanza). L'adapter ritorna un iterator; l'orchestrator inoltra ogni chunk via `simulation:audio_chunk` per ridurre il time-to-first-audio.
- **File audio persistenti** in Frappe File (`is_private=1`, attached_to_doctype="LMSA Simulation Turn"). Solo se `consent_recording=1`. Cancellazione via cron `os_lms.os_lms.ai.simulations.retention.purge_expired_audio` (rispetta `audio_retention_until`).
- **Audio user vs audio assistant**: entrambi salvati su `LMSA Simulation Turn.audio_file`, distinti dal `role`. L'audio assistant viene salvato dopo la sintesi completa (concatenazione dei chunk stream).

#### 3.2.5 Debrief Engine

- Background job `generate_debrief(session_id)` registrato in `hooks.py` (NON come scheduler event — viene `enqueue`d dall'orchestrator).
- Usa il provider/modello indicato in `LMSA Settings.simulation_debrief_provider` + `simulation_debrief_model` con `temperature=0.2` e `response_format=JsonSchema(DebriefSchema)`.
- Parsing con `pydantic` (`DebriefSchema`). Su parse error: retry una volta con prompt correttivo a `temperature=0`; al secondo fallimento → `status="Needs Review"` e log nel `LMSA Query Log` (riusato come canale audit).
- Emette `frappe.realtime` evento `simulation:debrief_ready` al canale utente.

### 3.3 Layer LLM provider-agnostico — dettaglio

Tutto il codice business consuma **una sola interfaccia** (`LLMProvider`). I provider concreti vivono in `os_lms/os_lms/ai/utils/llm/providers/` e si registrano via decorator nel `registry`. La scelta è puramente runtime: lo stesso processo può servire studenti diversi con provider diversi.

#### 3.3.1 Strategia di implementazione degli adapter

Ogni adapter è libero di scegliere lo strumento più adatto **al suo interno**: SDK ufficiale del provider oppure HTTP diretto con `httpx`. La regola architetturale è una sola:

> **L'SDK ufficiale di un provider è ammesso esclusivamente dentro l'adapter di quel provider.** Nessun import dell'SDK è permesso fuori dal file dell'adapter (né dall'orchestrator, né dal codice business, né da altri adapter). L'interfaccia esposta resta `LLMProvider` con i suoi tipi normalizzati.

Conseguenze pratiche:

1. **SDK ufficiali consentiti** (in modo opzionale e localizzato):
   - `OpenAIProvider` può usare `openai` SDK se semplifica streaming/tool-use.
   - `AnthropicProvider` può usare `anthropic` SDK.
   - `GeminiProvider` può usare `google-genai` SDK.
   - `DeepgramSTT`/`DeepgramAura` può usare `deepgram-sdk`.
   - `ElevenLabsTTS`/`ElevenLabsSTT` può usare `elevenlabs` SDK.
   - `GoogleSTT`/`GoogleTTS` può usare `google-cloud-speech` / `google-cloud-texttospeech`.
   - `AzureSTT`/`AzureTTS` può usare `azure-cognitiveservices-speech`.
2. **Le dipendenze degli SDK sono opzionali** nel `pyproject.toml` di `os_lms` (extras per-provider):
   ```toml
   [project.optional-dependencies]
   provider-openai = ["openai>=1.50"]
   provider-anthropic = ["anthropic>=0.40"]
   provider-gemini = ["google-genai>=0.3"]
   provider-deepgram = ["deepgram-sdk>=3.0"]
   provider-elevenlabs = ["elevenlabs>=1.0"]
   provider-google-cloud = ["google-cloud-speech>=2.0", "google-cloud-texttospeech>=2.0"]
   provider-azure = ["azure-cognitiveservices-speech>=1.40"]
   all-providers = [...]  # tutto in una install
   ```
   L'adapter fa **import lazy** dentro `__init__` o al primo uso e solleva un errore chiaro (`ProviderSdkNotInstalled`) con il comando `pip install` necessario, così chi non vuole un provider non paga l'install.
3. **Fallback `httpx` per provider senza SDK valido** o quando l'SDK non aggiunge valore (DeepSeek è 100% OpenAI-compatible: nessun bisogno di SDK dedicato).
4. **Base class `OpenAICompatibleProvider`** (`providers/openai_compatible.py`) — implementa l'intero protocollo OpenAI Chat Completions in `httpx` (streaming SSE, tool use, JSON Schema). Da essa derivano provider senza dipendenze extra:
   - `DeepSeekProvider` → `base_url="https://api.deepseek.com/v1"`.
   - `GroqProvider`, `TogetherProvider`, `OllamaProvider`, `vLLMProvider` → solo override di `base_url` + header auth. **Zero codice e zero SDK.**
   - Anche `OpenAIProvider` può derivare da qui se si decide di non aggiungere l'SDK ufficiale (la versione SDK e quella HTTP convivono come due implementazioni alternative scelte via Settings se serve A/B).
5. **Nessuna libreria abstractor di terze parti** (LiteLLM, LangChain) — duplicano il lavoro degli SDK aggiungendo un layer in più che il progetto non controlla; per la stessa ragione vanno escluse.

Verifica architetturale (semplice grep o test `pytest`): nessun file fuori da `os_lms/os_lms/ai/utils/{llm,stt,tts}/providers/` può contenere `import openai`, `import anthropic`, `import google.genai`, `import deepgram`, `import elevenlabs`, `import azure.cognitiveservices`. Un test di linting custom in `tests/test_provider_encapsulation.py` lo verifica in CI.

#### 3.3.2 Interfaccia `LLMProvider`

```python
# os_lms/os_lms/ai/utils/llm/provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Literal

Role = Literal["system", "user", "assistant", "tool"]

@dataclass
class ChatMessage:
    role: Role
    content: str
    name: str | None = None

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int

@dataclass
class ChatResponse:
    text: str
    finish_reason: str           # "stop" | "length" | "content_filter" | "tool_calls"
    usage: Usage
    model: str
    provider: str
    raw: dict                    # payload originale per audit/debug, non per business logic

@dataclass
class ChatChunk:
    delta: str
    finish_reason: str | None
    usage: Usage | None          # popolato solo nel chunk finale

@dataclass
class JsonSchema:
    name: str
    schema: dict                 # JSON Schema draft 2020-12
    strict: bool = True

class LLMProvider(ABC):
    name: str                    # "openai" | "gemini" | "deepseek" | "anthropic" | ...

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,                 # default da config
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
        response_format: JsonSchema | None = None,
        stream: bool = False,
        timeout: float = 60.0,
    ) -> ChatResponse | Iterator[ChatChunk]: ...

    @abstractmethod
    def health_check(self) -> bool: ...          # ping leggero per validazione configurazione
```

L'interfaccia è **piccola di proposito**: copre l'80% dei casi d'uso del progetto (role-play, debrief, tutor RAG). Funzioni avanzate provider-specifiche (es. cache Anthropic, file Gemini) non sono in interfaccia — vivono come metodi di estensione opzionali documentati per-provider e non possono essere richieste dal codice business (che parla solo all'ABC).

#### 3.3.3 Configurazione e factory

```python
# os_lms/os_lms/ai/utils/llm/config.py
@dataclass
class ProviderConfig:
    name: str                    # chiave registry
    api_key: str
    default_model: str
    base_url: str | None = None  # solo per OpenAI-compat self-hosted
    extra_headers: dict[str, str] | None = None
    organization: str | None = None
    timeout: float = 60.0
```

```python
# os_lms/os_lms/ai/utils/llm/registry.py
_PROVIDERS: dict[str, type[LLMProvider]] = {}

def register(name: str):
    def deco(cls):
        _PROVIDERS[name] = cls
        return cls
    return deco

def get_provider(config: ProviderConfig) -> LLMProvider:
    if config.name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {config.name}. Available: {list(_PROVIDERS)}")
    return _PROVIDERS[config.name](config)

def list_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())
```

Ogni adapter:

```python
@register("deepseek")
class DeepSeekProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
```

#### 3.3.4 Risoluzione provider a runtime

La factory che parla con l'orchestrator centralizza la logica di selezione e legge **sempre** da `LMSA Settings`:

```python
# os_lms/os_lms/ai/utils/llm/__init__.py
def resolve_provider(*, purpose: Literal["chat", "debrief"], override: str | None = None) -> LLMProvider:
    settings = load_oslms_settings()
    name = (
        override
        or (settings.simulation_chat_provider if purpose == "chat" else settings.simulation_debrief_provider)
    )
    if name == "auto":
        name = settings.simulation_provider_default       # es. "openai"
    config = build_provider_config(name, settings)        # legge api_key giusta, base_url, ecc.
    return get_provider(config)
```

L'orchestrator riceve il provider tramite questa funzione; non sa né deve sapere quale sia. Il `provider_override` dello scenario (campo opzionale) viene passato come `override`.

#### 3.3.5 Fallback chain

In `LMSA Settings.simulation_provider_fallback_order` (Long Text, CSV: `"openai,gemini,deepseek"`) si definisce l'ordine di failover. Solo quando `simulation_chat_provider == "auto"`, in caso di `LLMRateLimit` o `LLMServerError`, l'orchestrator tenta i successivi. Ogni tentativo logga `model_used` + `provider_used` sul turno per audit.

#### 3.3.6 Test e benchmarking

Un piccolo provider `MockProvider` (in `providers/mock.py`) restituisce risposte deterministiche dato un fingerprint dei messaggi. Usato per:

- Tutti gli unit test backend (zero costo, zero rete).
- Cypress E2E (override `simulation_chat_provider = "mock"` su sito test).
- Benchmarking didattico: lo stesso scenario può essere rigiocato deterministicamente per validare modifiche all'orchestrator.

Aggiunto inoltre un `RecordingProvider` (wrapper) che salva richiesta+risposta su `LMSA Query Log` con tag `kind="provider_io"` — utile per replay/debug.

### 3.4 Layer STT provider-agnostico — dettaglio

Stessa architettura del layer LLM: tutto il codice business consuma `STTProvider`; gli adapter (OpenAI Whisper, Deepgram, Google STT, Azure, ElevenLabs Scribe) vivono in `os_lms/os_lms/ai/utils/stt/providers/` e si registrano via decorator. Cambiare provider STT → cambia un campo in `LMSA Settings`.

#### 3.4.1 Interfaccia `STTProvider`

```python
# os_lms/os_lms/ai/utils/stt/provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Literal, BinaryIO

@dataclass
class TranscriptionSegment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None

@dataclass
class TranscriptionResult:
    text: str                                # trascrizione completa
    language: str | None                     # ISO 639-1 rilevato o forzato
    confidence: float | None                 # confidence media 0-1 (None se non disponibile)
    segments: list[TranscriptionSegment]     # timestamp-level, vuoto se provider non supporta
    duration_ms: int
    provider: str
    model: str
    raw: dict                                # payload originale, audit

@dataclass
class TranscriptionPartial:
    text: str                                # delta o trascrizione cumulativa
    is_final: bool
    confidence: float | None

class STTProvider(ABC):
    name: str

    @abstractmethod
    def transcribe(
        self,
        audio: bytes | BinaryIO,
        *,
        mime_type: str,                      # "audio/webm;codecs=opus", "audio/wav", "audio/mp3"
        language: str | None = None,         # "it", "en", ... None = autodetect
        prompt: str | None = None,           # bias contestuale (terminologia, nomi)
        diarization: bool = False,           # speaker separation (se supportato)
        timeout: float = 30.0,
    ) -> TranscriptionResult: ...

    @abstractmethod
    def transcribe_stream(
        self,
        audio_iter: Iterator[bytes],         # chunk PCM/Opus dal client
        *,
        mime_type: str,
        language: str | None = None,
    ) -> Iterator[TranscriptionPartial]: ...

    @abstractmethod
    def supported_languages(self) -> list[str]: ...

    @abstractmethod
    def supported_mime_types(self) -> list[str]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

Note di design:

- **`transcribe` non-streaming è obbligatorio** in MVP fase 2 (sufficiente per il flow utterance-per-utterance).
- **`transcribe_stream` opzionale** in MVP fase 2: provider che non lo supportano (es. Whisper file API) sollevano `STTStreamingNotSupported`. Verrà sfruttato in fase 3 per latenza sub-secondo.
- **`prompt`** è un canale tipico (Whisper, Deepgram) per dare contesto terminologico — l'orchestrator può passare la persona/scenario per migliorare il riconoscimento di nomi di prodotti/clienti.

#### 3.4.2 Adapter previsti (MVP fase 2)

| Provider | Endpoint | Streaming | Diarization | Lingue | Note |
| --- | --- | --- | --- | --- | --- |
| **OpenAI Whisper** | `POST /v1/audio/transcriptions` | ❌ (file API) | ❌ | 99+ | Default low-cost; riusa `openai_key`. Modello `whisper-1` o `gpt-4o-transcribe` |
| **Deepgram** | `POST /v1/listen` + WS streaming | ✅ | ✅ | 36 | Modello Nova-3; <1s latency; ottimo per realtime |
| **Google Speech-to-Text** | REST v2 + streaming | ✅ | ✅ | 125+ | Buono per UE region; richiede service account JSON |
| **Azure AI Speech** | REST + WS | ✅ | ✅ | 100+ | Solo se cliente già su Azure |
| **ElevenLabs Scribe** | `POST /v1/speech-to-text` | ❌ | ✅ | 99 | Alta qualità ma costoso; opzionale |

#### 3.4.3 Selezione runtime

```python
# os_lms/os_lms/ai/utils/stt/__init__.py
def resolve_stt_provider(*, override: str | None = None) -> STTProvider:
    settings = load_oslms_settings()
    name = override or settings.stt_provider
    if name == "auto":
        name = settings.stt_provider_default
    config = build_stt_config(name, settings)
    return get_stt_provider(config)
```

Configurazione in `LMSA Settings` (vedi §4.0): `stt_provider`, `stt_provider_default`, `stt_model`, `stt_language` (default `auto`), chiavi `deepgram_key`, `google_stt_credentials_json` (Long Text), `azure_speech_key` + `azure_speech_region`.

#### 3.4.4 Errori normalizzati

`STTRateLimit`, `STTInvalidAudio`, `STTUnsupportedLanguage`, `STTUnsupportedMimeType`, `STTAudioTooLong`, `STTServerError`, `STTTimeout`, `STTStreamingNotSupported`. Mappati dagli errori nativi in ogni adapter.

#### 3.4.5 Fallback chain

Stesso pattern del layer LLM: `LMSA Settings.stt_provider_fallback_order` CSV. Su `STTRateLimit`/`STTServerError` con `stt_provider == "auto"`, l'orchestrator prova i successivi e logga il fallback su `LMSA Simulation Turn.provider_used` (lo stesso campo è riusato per LLM/STT/TTS distinguendoli per kind).

### 3.5 Layer TTS provider-agnostico — dettaglio

Analogo a STT. Astrazione `TTSProvider`; adapter intercambiabili (OpenAI TTS, ElevenLabs, Google TTS, Deepgram Aura, Azure).

#### 3.5.1 Interfaccia `TTSProvider`

```python
# os_lms/os_lms/ai/utils/tts/provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Literal

AudioFormat = Literal["mp3", "opus", "ogg_opus", "wav", "pcm16"]

@dataclass
class SynthesisRequest:
    text: str
    voice_id: str                            # opaque provider-side ("alloy" OpenAI, "21m00..." 11Labs, …)
    language: str | None = None
    speaking_rate: float = 1.0               # 0.5-2.0
    pitch: float = 0.0                       # semitoni
    style: str | None = None                 # emozione (provider che lo supportano)

@dataclass
class SynthesisResult:
    audio: bytes
    format: AudioFormat
    sample_rate: int
    duration_ms: int
    provider: str
    voice_id: str
    model: str
    raw: dict

@dataclass
class AudioChunk:
    data: bytes
    is_final: bool

@dataclass
class Voice:
    id: str
    name: str
    language: str
    gender: str | None
    description: str | None
    preview_url: str | None

class TTSProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(
        self,
        request: SynthesisRequest,
        *,
        format: AudioFormat = "mp3",
        timeout: float = 30.0,
    ) -> SynthesisResult: ...

    @abstractmethod
    def synthesize_stream(
        self,
        request: SynthesisRequest,
        *,
        format: AudioFormat = "mp3",
    ) -> Iterator[AudioChunk]: ...

    @abstractmethod
    def list_voices(self, language: str | None = None) -> list[Voice]: ...

    @abstractmethod
    def supported_formats(self) -> list[AudioFormat]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

Note di design:

- `synthesize_stream` è **obbligatorio** in MVP fase 2 (per ridurre time-to-first-audio). Provider senza streaming sintetizzano l'intero blob poi emettono un solo chunk con `is_final=True` (degrado controllato).
- `list_voices` permette di popolare un dropdown nel `ScenarioEditor` con le voci disponibili dal provider corrente.
- Il `voice_id` è **opaco** ed è salvato sullo Scenario (campo `customer_voice_id` aggiunto a `LMSA Simulation Scenario`). Se si cambia provider, il `voice_id` perde validità — l'editor lo segnala e propone re-mapping.

#### 3.5.2 Adapter previsti (MVP fase 2)

| Provider | Endpoint | Streaming | Voci | Stile/emozioni | Note |
| --- | --- | --- | --- | --- | --- |
| **OpenAI TTS** | `POST /v1/audio/speech` | ✅ (response stream) | 6 voci (alloy, echo, …) | Limitato (con `gpt-4o-mini-tts` arrivano istruzioni di stile) | Default low-cost; riusa `openai_key` |
| **ElevenLabs** | `POST /v1/text-to-speech/{voice}/stream` | ✅ (chunked SSE) | 1000+ + voice cloning | ✅ (multi-emozione) | Qualità premium per role-play realistico |
| **Google Cloud TTS** | `POST /v1/text:synthesize` + streaming | ✅ | 380+ Neural2/Studio | Limitato | UE region disponibile |
| **Deepgram Aura** | `POST /v1/speak` | ✅ | 12 voci | Limitato | Latenza minore (<200ms TTFB) |
| **Azure AI Speech** | REST + WS | ✅ | 400+ Neural | ✅ (SSML) | Solo se cliente già su Azure |

#### 3.5.3 Selezione runtime e per-scenario

```python
def resolve_tts_provider(*, override: str | None = None) -> TTSProvider:
    settings = load_oslms_settings()
    name = override or settings.tts_provider
    if name == "auto":
        name = settings.tts_provider_default
    config = build_tts_config(name, settings)
    return get_tts_provider(config)
```

Lo Scenario può **forzare un provider TTS e una voce** (`tts_provider_override`, `customer_voice_id`) per coerenza didattica (es. una persona "cliente B2B 50enne maschio" deve avere sempre la stessa voce).

#### 3.5.4 Errori normalizzati

`TTSRateLimit`, `TTSInvalidVoice`, `TTSUnsupportedLanguage`, `TTSUnsupportedFormat`, `TTSTextTooLong`, `TTSServerError`, `TTSTimeout`. Mappati dagli errori nativi.

#### 3.5.5 Caching del primo turno

Il primo turno del cliente è generato in `start_session` ed è identico per stesso `(scenario, seed)`. La sua sintesi audio viene cachata in Frappe Cache (Redis db dedicato) con TTL 7gg, key `tts:{provider}:{voice}:{hash(text)}`. Riduce sia latenza percepita sia costo per ripetizioni dello stesso scenario.

### 3.6 Flusso voce end-to-end

Tutti i tre layer (LLM, STT, TTS) sono provider-agnostici e selezionati indipendentemente. L'orchestrator coordina:

```python
# os_lms/os_lms/ai/simulations/voice_orchestrator.py
def handle_audio_turn(session, audio_bytes: bytes, mime_type: str):
    stt = resolve_stt_provider(override=session.scenario_stt_override)
    llm = resolve_provider(purpose="chat", override=session.scenario_provider_override)
    tts = resolve_tts_provider(override=session.scenario_tts_override)

    # 1. STT
    transcription = stt.transcribe(
        audio_bytes,
        mime_type=mime_type,
        language=session.language or "it",
        prompt=build_stt_context_prompt(session),
    )
    persist_user_turn(session, transcription, audio_bytes if session.consent_recording else None)

    # 2. LLM (stesso path della chat testuale)
    reply_text = reply_as_customer(session, transcription.text, provider=llm)

    # 3. TTS streaming
    audio_chunks = []
    for chunk in tts.synthesize_stream(
        SynthesisRequest(
            text=reply_text,
            voice_id=session.customer_voice_id,
            language=session.language or "it",
        ),
        format="mp3",
    ):
        frappe.publish_realtime(
            "simulation:audio_chunk",
            {"session": session.name, "chunk_b64": base64(chunk.data), "is_final": chunk.is_final},
            user=session.student,
        )
        audio_chunks.append(chunk.data)

    if session.consent_recording:
        attach_audio(session, role="assistant", audio=b"".join(audio_chunks), format="mp3")
```

## 4. Modello dati — DocType

### 4.0 Estensione `LMSA Settings`

Single doctype esistente. Aggiungere i campi (via JSON del doctype, non Custom Field):

| Campo | Tipo | Default | Note |
| --- | --- | --- | --- |
| `simulations_enabled` | Check | 0 | Master switch feature simulazioni |
| `simulation_chat_provider` | Select (`auto│openai│gemini│deepseek│anthropic│mock`) | `auto` | Provider per role-play |
| `simulation_debrief_provider` | Select (idem) | `auto` | Provider per debrief (può differire da chat) |
| `simulation_provider_default` | Select (idem, escluso `auto│mock`) | `openai` | Provider effettivo quando uno dei due è `auto` |
| `simulation_provider_fallback_order` | Long Text (CSV) | `openai,gemini,deepseek` | Sequenza failover su rate-limit/5xx (vedi §3.3.5) |
| `simulation_chat_model` | Data | `gpt-4o-mini` | Override modello role-play (vuoto → default del provider) |
| `simulation_debrief_model` | Data | `gpt-4.1` | Override modello debrief |
| `openai_key` | Password | — | **già esistente**, riusato |
| `gemini_key` | Password | — | NUOVO |
| `deepseek_key` | Password | — | NUOVO |
| `anthropic_key` | Password | — | NUOVO, opzionale |
| `openai_base_url` | Data | — | NUOVO, override per OpenAI-compat self-hosted (Ollama, vLLM, …) |
| `simulation_max_turns_default` | Int | 20 | |
| `simulation_time_limit_default` | Int | 15 | minuti |
| `simulation_voice_enabled` | Check | 0 | Fase 2 |
| `simulation_audio_retention_days` | Int | 30 | |
| `simulation_daily_quota_per_user` | Int | 10 | 0 = illimitato |
| **— STT (fase 2)** | | | |
| `stt_provider` | Select (`auto│openai_whisper│deepgram│google_stt│azure_stt│elevenlabs_stt│mock`) | `auto` | NUOVO |
| `stt_provider_default` | Select (escluso `auto│mock`) | `openai_whisper` | NUOVO, fallback effettivo |
| `stt_provider_fallback_order` | Long Text (CSV) | `openai_whisper,deepgram` | NUOVO |
| `stt_model` | Data | `whisper-1` | NUOVO, override modello |
| `stt_language` | Data | `auto` | ISO 639-1 o `auto` |
| `stt_diarization` | Check | 0 | abilita speaker separation |
| `deepgram_key` | Password | — | NUOVO |
| `google_stt_credentials_json` | Long Text | — | NUOVO, service account JSON |
| `azure_speech_key` | Password | — | NUOVO (condivisa STT+TTS Azure) |
| `azure_speech_region` | Data | — | NUOVO (es. `westeurope`) |
| `elevenlabs_key` | Password | — | NUOVO (condivisa TTS+STT) |
| **— TTS (fase 2)** | | | |
| `tts_provider` | Select (`auto│openai│elevenlabs│google_tts│deepgram_aura│azure_tts│mock`) | `auto` | NUOVO |
| `tts_provider_default` | Select (escluso `auto│mock`) | `openai` | NUOVO |
| `tts_provider_fallback_order` | Long Text (CSV) | `openai,elevenlabs` | NUOVO |
| `tts_model` | Data | `gpt-4o-mini-tts` | NUOVO, override modello |
| `tts_default_voice_id` | Data | `alloy` | NUOVO, fallback se Scenario non specifica |
| `tts_default_format` | Select (`mp3│opus│wav│pcm16`) | `mp3` | NUOVO |
| `tts_speaking_rate` | Float | `1.0` | NUOVO, 0.5-2.0 |
| `tts_streaming_enabled` | Check | 1 | NUOVO, disattivabile per debug |
| `tts_cache_enabled` | Check | 1 | NUOVO, cache primo turno (vedi §3.5.5) |
| `tts_cache_ttl_days` | Int | 7 | NUOVO |

`OsLmsSettings` dataclass va estesa con gli stessi campi (defaulted). Le chiavi API sono `Password` field e vengono lette via `frappe.utils.password.get_decrypted_password`. La build di `ProviderConfig` accade in `build_provider_config(name, settings)` (vedi §3.3.4): mappa `name → (api_key, base_url, default_model)` in una sola funzione, così l'aggiunta di un nuovo provider è un singolo punto di modifica + nuovo adapter + nuovo Select option.

Inoltre, sul doctype `LMSA Simulation Scenario` il campo `provider_override` ha lo **stesso set di opzioni** del Select Settings: permette al docente di forzare un provider/modello per uno scenario specifico (es. scenario complesso → forza `anthropic` + `claude-opus`). Analoghi override esistono per STT/TTS e per la voce — vedi §4.1.

### 4.1 `LMSA Simulation Scenario`

| Campo | Tipo | Note |
| --- | --- | --- |
| `scenario_name` | Data | required, unique per course |
| `lms_course` | Link → LMS Course | required, indexed |
| `course_lesson` | Link → Course Lesson | opzionale: uno scenario può essere legato al massimo a una singola lezione, altrimenti vive a livello corso |
| `difficulty` | Select (`easy│medium│hard`) | default `medium` |
| `modality` | Select (`chat│voice│both`) | default `chat` |
| `customer_persona` | Long Text | base persona (markdown ammesso) |
| `situation_template` | Long Text | template scena |
| `evaluation_rubric` | Link → LMSA Evaluation Rubric | required |
| `learning_objectives` | Table → LMSA Simulation Learning Objective | |
| `seed_variations` | Table → LMSA Simulation Seed Variation | |
| `max_turns` | Int | override settings |
| `time_limit_minutes` | Int | override settings |
| `provider_override` | Select (`auto│openai│gemini│deepseek│anthropic│mock`) | default `auto` (LLM) |
| `model_override` | Data | override modello LLM (vuoto = default provider) |
| `stt_provider_override` | Select (`auto│openai_whisper│deepgram│google_stt│azure_stt│elevenlabs_stt│mock`) | default `auto` |
| `tts_provider_override` | Select (`auto│openai│elevenlabs│google_tts│deepgram_aura│azure_tts│mock`) | default `auto` |
| `customer_voice_id` | Data | voice_id opaco del provider TTS (validato dall'editor con `list_voices`) |
| `customer_voice_language` | Data | ISO 639-1; default eredita dal corso |
| `customer_voice_speaking_rate` | Float | default 1.0 |
| `status` | Select (`Draft│Published│Archived`) | default `Draft` |
| `created_by_instructor` | Link → User | auto via `before_insert` |

Permessi: `LMS Instructor` può creare/modificare scenari dei propri corsi (vincolo applicato in `permission_query_conditions` riusando `has_course_instructor_role` + `is_instructor` di `lms.lms.utils`); `LMS Manager` full; `LMS Student` read solo `Published` filtrato per enrollment.

Child tables:

- **`LMSA Simulation Learning Objective`**: `objective_text` (Data), `weight` (Float, 0-1).
- **`LMSA Simulation Seed Variation`**: `variable_name` (Data), `possible_values` (Long Text, una per riga).

### 4.2 `LMSA Evaluation Rubric`

| Campo | Tipo | Note |
| --- | --- | --- |
| `rubric_name` | Data | required |
| `description` | Small Text | |
| `scoring_scale` | Select (`0-3│0-5│0-10`) | default `0-10` |
| `passing_threshold` | Percent | default 70 |
| `criteria` | Table → LMSA Rubric Criterion | required, almeno 1 |
| `is_shared` | Check | rubriche riutilizzabili tra corsi |

Child `LMSA Rubric Criterion`: `criterion_name`, `description`, `weight` (Float, validazione applicativa che la somma = 1.0 in `validate()` del parent), `observable_behaviors`.

### 4.3 `LMSA Simulation Session`

Documento submittable per immutabilità post-completion.

| Campo | Tipo | Note |
| --- | --- | --- |
| `student` | Link → User | required, indexed |
| `scenario` | Link → LMSA Simulation Scenario | required, indexed |
| `generated_situation` | Long Text | output Prompt 1 |
| `generated_persona` | JSON | persona concreta (name, role, company, mood, hidden_motivation, key_objection) |
| `seed` | Data | fingerprint generazione |
| `modality` | Select (`chat│voice`) | required |
| `status` | Select (`In Progress│Completed│Abandoned│Error│Needs Review`) | default `In Progress` |
| `started_at` / `ended_at` | Datetime | |
| `turn_count` | Int | mantenuto da orchestrator |
| `consent_recording` | Check | solo voice |
| `audio_retention_until` | Date | |
| `chat_model_used` | Data | audit |
| `debrief_model_used` | Data | audit |
| `stt_provider_used` | Data | audit voce |
| `tts_provider_used` | Data | audit voce |
| `customer_voice_id_used` | Data | audit voce (la voce effettiva può cambiare se fallback) |
| `prompt_version` | Data | audit (`rp.v1`) |
| `debrief` | Link → LMSA Simulation Debrief | popolato a fine job |
| `course` | Link → LMS Course | fetch_from `scenario.lms_course` (per query veloci) |

Permessi: studente vede le proprie; instructor del corso vede tutte le sessioni del corso; manager full.

### 4.4 `LMSA Simulation Turn`

Documento separato (non child) per:

- Append efficiente turno-per-turno senza riscrivere il parent.
- Query per analytics (latenza media, distribuzione lunghezza).

| Campo | Tipo | Note |
| --- | --- | --- |
| `session` | Link → LMSA Simulation Session | required, indexed |
| `turn_index` | Int | required, unique per session |
| `role` | Select (`user│assistant│system`) | required |
| `text_content` | Long Text | required |
| `audio_file` | Attach | Frappe File privato (voice) |
| `audio_format` | Data | `mp3│opus│wav│pcm16` (voice) |
| `audio_duration_ms` | Int | (voice) |
| `audio_transcript_confidence` | Float | STT confidence (user turn) |
| `stt_segments` | Long Text | JSON dei segments con timestamp (audit voice) |
| `latency_ms` | Int | latenza LLM |
| `stt_latency_ms` | Int | latenza STT (voice) |
| `tts_latency_ms` | Int | time-to-first-audio TTS (voice) |
| `tts_voice_id` | Data | voice_id effettivamente usato |
| `tokens_input` / `tokens_output` | Int | cost tracking LLM |
| `model_used` | Data | per-turn LLM (es. fallback) |
| `provider_used` | Data | provider LLM (`openai│gemini│deepseek│anthropic│...`) |
| `stt_provider_used` | Data | provider STT |
| `tts_provider_used` | Data | provider TTS |
| `injection_attempt_detected` | Check | flag dal filtro `prompt_defense` |

Permessi: solo via `LMSA Simulation Session` parent (no UI standalone in Desk per studenti). Implementato con `has_permission` hook che delega al parent.

### 4.5 `LMSA Simulation Debrief`

| Campo | Tipo | Note |
| --- | --- | --- |
| `session` | Link → LMSA Simulation Session | required, unique |
| `overall_score` | Float | 0-100 |
| `passed` | Check | calcolato da `overall_score` vs rubric.passing_threshold |
| `criterion_scores` | Table → LMSA Criterion Score | |
| `strengths` | Table → LMSA Debrief Strength | |
| `improvements` | Table → LMSA Debrief Improvement | |
| `behavioral_analysis` | Long Text | markdown |
| `recommended_content` | Table → LMSA Debrief Recommendation | link a Course Lesson |
| `instructor_review` | Long Text | opzionale |
| `instructor_reviewed_by` | Link → User | |
| `instructor_reviewed_at` | Datetime | |
| `raw_llm_response` | Long Text | audit (JSON crudo prima del parsing) |

Child tables minimali con i campi descritti in `PLAN.md §5.4`.

### 4.6 `LMSA Recording Consent Log`

Identico alla spec originale. Append-only via `if_owner=0`, `only_select=1` su `User`. Inserisce automaticamente IP e UA via `frappe.local.request`.

## 5. API e flussi

### 5.1 Endpoint REST (whitelist)

Tutti in `os_lms/os_lms/ai/simulations/api.py`, esposti come `os_lms.os_lms.ai.simulations.api.<method>`. Convenzione: `@frappe.whitelist()` + type-annotated (richiesto dal progetto). Permessi controllati riusando i pattern di `os_lms/os_lms/ai/api.py` (`load_lesson` → `load_session` analogo).

| Metodo | Endpoint | Auth | Descrizione |
| --- | --- | --- | --- |
| POST | `start_session` | enrollment | crea Session + primo turno cliente |
| POST | `send_message` | session owner | append turno user; ritorna turno assistant (sincrono) |
| POST | `send_audio` | session owner + consent | upload utterance audio (fase 2): trigger STT → LLM → TTS (streaming via WS) |
| POST | `end_session` | session owner | termina + enqueue debrief job |
| GET | `get_session` | session owner / instructor | stato + cronologia |
| GET | `get_debrief` | session owner / instructor | debrief (polling fallback) |
| POST | `grant_recording_consent` | self | (fase 2) registra consenso |
| POST | `revoke_recording_consent` | self | (fase 2) revoca + purge audio attuale |
| GET | `list_tts_voices` | instructor / manager | (fase 2) elenco voci dal `tts_provider` corrente, per `ScenarioEditor` |
| POST | `preview_tts_voice` | instructor / manager | (fase 2) sintetizza testo di esempio per anteprima nel `ScenarioEditor` |
| POST | `test_stt_audio` | instructor / manager | (fase 2) carica audio di test → ritorna trascrizione + latenza (debug Settings) |
| POST | `instructor_review_debrief` | instructor del corso | salva note docente |
| GET | `list_scenarios` | enrollment | scenari pubblicati per corso/lezione |
| GET | `instructor_report` | instructor / manager | aggregati per corso/studente/periodo |

### 5.2 Eventi `frappe.realtime`

Canale per-utente (`frappe.publish_realtime(event, message, user=session.student)`). Eventi:

- `simulation:turn_start` — `{session, turn_index}`
- `simulation:turn_chunk` — `{session, turn_index, delta}` (streaming token LLM)
- `simulation:turn_complete` — `{session, turn_index, metadata}`
- `simulation:stt_partial` — `{session, turn_index, text, is_final}` (fase 3, streaming STT)
- `simulation:stt_complete` — `{session, turn_index, text, confidence, latency_ms}` (fase 2)
- `simulation:audio_chunk` — `{session, turn_index, chunk_b64, is_final}` (fase 2, streaming TTS)
- `simulation:debrief_ready` — `{session, debrief}`
- `simulation:error` — `{session, code, message, layer: "llm│stt│tts"}`

### 5.3 Override / hook in `os_lms/hooks.py`

```python
# scheduler_events
"daily": [
    "os_lms.os_lms.ai.scheduler.reindex_lesson_content",
    "os_lms.os_lms.ai.simulations.retention.purge_expired_audio",
    "os_lms.os_lms.ai.simulations.retention.purge_orphan_sessions",  # abandoned > 24h
],

# doc_events
"LMSA Simulation Session": {
    "before_insert": "os_lms.os_lms.ai.simulations.orchestrator.validate_quota",
    "on_trash": "os_lms.os_lms.ai.simulations.retention.cascade_delete_turns_and_audio",
},

# fixtures (in custom_field.json):
# - "LMS Course": campo `simulations_enabled` (Check) per attivare per-corso
# - "Course Lesson": campo `default_simulation_scenario` (Link → LMSA Simulation Scenario)
```

### 5.4 Override API LMS

L'attuale `os_lms.os_lms.override_utils.get_course_details` viene esteso per restituire l'elenco scenari pubblicati associati al corso (per il pulsante "Avvia simulazione" sulla pagina corso). Analogamente `get_lesson` aggiunge `default_simulation_scenario` risolto.

## 6. Frontend

### 6.1 Integrazione in `Lesson.vue`

Pattern analogo all'attuale `ChatBot.vue` (vedi `frontend/src/pages/Lesson.vue:402` per riferimento di mount). Il bottone "Avvia simulazione" appare se:

- `settingsStore.settings.data.simulations_enabled === 1` (esposto via `get_lms_settings` override esistente).
- La lezione ha `default_simulation_scenario` valorizzato OPPURE il corso ha almeno uno scenario `Published`.

### 6.2 Routing

Le pagine di gioco/debrief vivono fuori dalla lezione (immersione full-screen). Tre nuove rotte in `frontend/src/router.js`:

- `/simulations/:session_id` → `SimulationPlay.vue` (chat o voice in base a `modality`).
- `/simulations/:session_id/debrief` → `SimulationDebrief.vue`.
- `/simulations/admin` → `InstructorReports.vue` (guard per ruolo).

`Lesson.vue` apre il launcher in modale; al click "Avvia" → POST `start_session` → redirect SPA.

### 6.3 Composables

- `useSimulationSession(sessionId)`: connessione `socket.io`, buffer streaming, send/end con ottimismo. Riusa il `socket` client già configurato in `frontend/src/socket.js`.
- `useSimulationDebrief(sessionId)`: sottoscrizione a `simulation:debrief_ready` + fallback polling ogni 5s con cap a 60s (timeout → errore).

### 6.4 Pannello docente

Vue component-only (no nuova Desk page) per coerenza con la dashboard studenti. Filtri server-side via endpoint `instructor_report`. Drill-down → modale con `ChatSession.vue` in modalità **read-only** (riusa lo stesso componente passando `readOnly=true`).

## 7. Riuso vs nuovo codice

### 7.1 Cosa si **riusa** tale quale

- Pattern `OsLmsSettings` dataclass e `_load_settings` (`os_lms/os_lms/ai/utils/oslms_settings.py`).
- `RagDB` per il **debrief recommendation step**: il debrief usa `rag_db.search(query=behavior_gap, top_k=N)` per trovare lezioni rilevanti da consigliare. Niente nuovo storage vettoriale.
- `frappe.logger("os_lmsa", allow_site=True)` come logger condiviso.
- `LMSA Query Log` come fallback audit per output LLM non parsabili (campo `extra_data` JSON con `kind=debrief_parse_failure`).
- Frappe File API per audio (no S3 in MVP).
- Pattern fixtures `custom_field.json` per campi su `LMS Course` e `Course Lesson`.

### 7.2 Cosa va **modificato in retro-compatibilità**

- `Chatbot` ABC (legacy, tutor RAG): reimplementato come thin wrapper sopra `LLMProvider` (un solo turno, niente streaming). Nessun call site cambia.
- `GptChatbot`: deprecato a favore di `OpenAIProvider` via wrapper di compat. Il vecchio `chatbot.ask(question, contexts)` resta funzionante.
- `LMSA Settings`: nuovi campi (additive, non rimuove esistenti). Migrazione: il `openai_key` esistente viene riutilizzato dal nuovo `OpenAIProvider`.
- `OsLmsSettings` dataclass: nuovi field con default → non rompe i consumer attuali.
- `get_course_details` / `get_lesson` override: aggiunta payload, non rimozione campi.

### 7.3 Cosa è **nuovo**

- **Layer LLM provider-agnostico** in `os_lms/os_lms/ai/utils/llm/`: `LLMProvider` ABC, registry, `ProviderConfig`, errori normalizzati, `MockProvider`, `RecordingProvider`. Vedi §3.3.
- **Adapter LLM** (`providers/`): `OpenAICompatibleProvider` (base in `httpx`), `OpenAIProvider`, `GeminiProvider`, `DeepSeekProvider`, `AnthropicProvider`. Ogni adapter sceglie internamente fra SDK ufficiale (solo dentro il file dell'adapter, mai esposto) e `httpx`. Vedi §3.3.1.
- **Layer STT provider-agnostico** (`ai/utils/stt/`) — fase 2: `STTProvider` ABC + adapter `OpenAIWhisper`, `Deepgram`, `GoogleSTT`, `AzureSTT`, `ElevenLabsSTT`, `MockSTT`. Vedi §3.4.
- **Layer TTS provider-agnostico** (`ai/utils/tts/`) — fase 2: `TTSProvider` ABC + adapter `OpenAITTS`, `ElevenLabsTTS`, `GoogleTTS`, `DeepgramAura`, `AzureTTS`, `MockTTS`. Vedi §3.5.
- **Voice orchestrator** (`ai/simulations/voice_orchestrator.py`) — coordina STT→LLM→TTS con audit dei provider per turno.
- Sotto-modulo `os_lms/os_lms/ai/simulations/` (orchestrator, generator, role_play, debrief, tasks, retention, prompt_defense, api).
- 10+ nuovi doctype (vedi §4).
- Frontend in `frontend/src/oslms/components/simulations/` + 3 pagine. Per la fase 2: `VoiceSession.vue`, `ConsentModal.vue`, integrazione VAD client-side (`@ricky0123/vad-web`).

## 8. GDPR e sicurezza nel contesto attuale

Le mitigazioni del `PLAN.md §8` si applicano integralmente. Nota implementativa:

- API key dei provider stoccate in **`LMSA Settings`** con fieldtype `Password` (già pattern in essere per `openai_key`), letti via `get_decrypted_password`. Niente Site Config.
- Per **Anthropic ZDR / endpoint EU**: header `anthropic-version` e `anthropic-beta` configurabili da `LMSA Settings` (campo `anthropic_extra_headers` JSON).
- **Pseudonimizzazione user_id**: hash SHA-256 del `frappe.session.user` come parte del payload inviato al provider (l'orchestrator NON deve mai mandare email reali nel prompt). Implementato in `orchestrator._pseudonymize_session_id`.
- **Rate limiting** per studente: `validate_quota` su `before_insert` di Session conta sessioni `started_at >= today()` per `student` e blocca se eccede `simulation_daily_quota_per_user`.
- **Sanitizzazione output cliente**: tutto il testo che torna in UI viene renderizzato come Markdown via `dompurify` (già usato in `ChatBot.vue` con `renderMarkdown`).
- **Filtro anti-injection** (`prompt_defense.py`): regex su pattern noti (`ignore previous`, `sei un AI`, system role hijacking) + fallback risposta in-character standard. Log evento in `LMSA Query Log`.
- **Audio in transito** (fase 2): chunk audio inviati al provider STT solo via HTTPS; preferire endpoint UE quando disponibili (Deepgram EU, Google `europe-west*`, Azure `westeurope`). Stessa cosa per TTS.
- **Retention audio**: tutti gli audio (user e assistant) hanno `audio_retention_until = today() + simulation_audio_retention_days`. Job giornaliero `purge_expired_audio` cancella i file e rimuove l'attach. Le **trascrizioni testuali restano** (servono al debrief e progress tracking) — vedi tabella retention `PLAN.md §8.3`.
- **Cache TTS**: la chiave usa l'hash SHA-256 del testo. Il blob audio è in Frappe Cache (Redis db dedicato, NON il vector store). Cancellabile via tasto "Svuota cache TTS" nel Settings doctype (action JS).
- **Diritto alla portabilità**: l'export `/export_my_data` include gli audio dell'utente (solo i propri turni `role=user`); gli audio assistant sono **derivati** del modello e non vengono esportati come dati personali.
- **Trascrizioni e prompt STT**: il `prompt` di bias contestuale inviato a STT non deve contenere PII; l'orchestrator passa solo persona fittizia + termini tecnici dello scenario.

## 9. Roadmap concreta

### Sprint 1 — LLM layer + foundation (settimane 1-2)

- **Layer LLM provider-agnostico** (`ai/utils/llm/`): ABC `LLMProvider`, dataclass tipi, registry, `errors.py`, `MockProvider`.
- `OpenAICompatibleProvider` (base) + adapter concreti: `OpenAIProvider`, `DeepSeekProvider`, `GeminiProvider`, `AnthropicProvider`.
- Estensione `LMSA Settings` (provider + chiavi + fallback order) + `OsLmsSettings` dataclass.
- Migrazione `GptChatbot` come wrapper sopra `OpenAIProvider` (retro-compat tutor RAG).
- Doctype: `LMSA Simulation Scenario` + child, `LMSA Evaluation Rubric` + child.
- Permessi base + Desk forms funzionanti.
- Test backend con `MockProvider` (`apps/os_lms/os_lms/test_*.py`, `frappe.tests.UnitTestCase`): un test per adapter usando `httpx.MockTransport` per evitare chiamate reali in CI.
- Pagina di **health-check** in Desk (action su `LMSA Settings`: "Test connessione") che invoca `provider.health_check()` per ogni provider configurato.

### Sprint 2 — Sessioni testuali end-to-end (settimane 3-4)

- `SessionOrchestrator` + `ScenarioGenerator` + `RolePlayPrompt`.
- Doctype `LMSA Simulation Session`, `LMSA Simulation Turn`.
- Endpoint `start_session`, `send_message`, `end_session`, `get_session`.
- Eventi `frappe.realtime` (streaming).
- Filtro `prompt_defense`.

### Sprint 3 — Debrief + UI studente (settimane 5-6)

- `DebriefEngine` + job RQ + parsing/retry.
- Doctype `LMSA Simulation Debrief` + child tables.
- Componenti Vue: `SimulationLauncher`, `ChatSession`, `DebriefView` + rotte.
- Integrazione in `Lesson.vue`.
- E2E Cypress test del flow happy path.

### Sprint 4 — Pannello docente + analytics (settimane 7-8)

- `ScenarioEditor`, `RubricEditor` (drag&drop con somma pesi forzata 1.0).
- `InstructorDashboard` + endpoint `instructor_report`.
- Drill-down trascrizione in read-only.
- Pilot con 1 corso reale.

### Fase 2 — Voce (6-8 settimane post-MVP)

**Sprint 5 — STT layer (settimane 1-2)**

- Layer `STTProvider` (`ai/utils/stt/`): ABC, registry, errori, `MockSTT`.
- Adapter: `OpenAIWhisper`, `Deepgram`, `GoogleSTT`. (Azure/ElevenLabs opzionali, sprint successivo se richiesti.)
- Estensione `LMSA Settings` (campi STT + chiavi `deepgram_key`, `google_stt_credentials_json`, `azure_speech_*`).
- Health-check action in Desk + endpoint `test_stt_audio` per debug.
- Unit test con `httpx.MockTransport` (zero rete in CI).

**Sprint 6 — TTS layer (settimane 3-4)**

- Layer `TTSProvider` (`ai/utils/tts/`): ABC, registry, errori, `MockTTS`.
- Adapter: `OpenAITTS`, `ElevenLabsTTS`, `GoogleTTS`, `DeepgramAura`.
- Cache TTS primo turno (Frappe Cache key `tts:{provider}:{voice}:{hash}`).
- Estensione `LMSA Settings` (campi TTS + `elevenlabs_key` condivisa).
- Endpoint `list_tts_voices` + `preview_tts_voice` per `ScenarioEditor`.
- Unit test con `httpx.MockTransport`.

**Sprint 7 — Voice orchestrator + consent (settimane 5-6)**

- `voice_orchestrator.handle_audio_turn` (STT → LLM → TTS streaming).
- Endpoint `send_audio`, `grant_recording_consent`, `revoke_recording_consent`.
- Doctype `LMSA Recording Consent Log` attivato.
- Cron `purge_expired_audio` + `cascade_delete_turns_and_audio`.
- Audit fields su `LMSA Simulation Turn` (stt/tts provider, latenze, voice_id, segments).
- Eventi WS `simulation:stt_complete`, `simulation:audio_chunk`.

**Sprint 8 — Frontend voce (settimane 7-8)**

- `VoiceSession.vue` con `MediaRecorder` + VAD client-side (`@ricky0123/vad-web`) + push-to-talk fallback.
- `ConsentModal.vue` granulare (3 toggle: registrazione / analytics anonime / ascolto docente).
- Estensione `ScenarioEditor` con dropdown voci (popolato da `list_tts_voices`) e preview audio.
- Cypress E2E con `MockSTT`/`MockTTS` (deterministico).
- Pilot voce con 5-10 studenti su un singolo scenario.

### Fase 3 — Avanzato

- **Streaming STT vero** (`STTProvider.transcribe_stream` su Deepgram/Google): trascrizione live mentre l'utente parla → evento `simulation:stt_partial`.
- **OpenAI Realtime API** come provider unificato voce→voce (bypass STT+TTS): nuovo adapter `OpenAIRealtimeProvider` che soddisfa **entrambe** le interfacce `STTProvider`+`TTSProvider`+`LLMProvider` (caso speciale, vedi nota in §3.6) per latenza sub-secondo.
- **Coach AI on-demand** durante simulazione (penalità score).
- **Adaptive difficulty**: lo scenario si adatta in tempo reale alle performance.
- Voice cloning ElevenLabs per persone ricorrenti (con consenso esplicito istituzionale).

## 10. Test plan

- **Unit (Python)**: parser output debrief, pesi rubrica, validate_quota, prompt_defense (corpus di tentativi noti).
- **Unit (orchestrator)**: `MockProvider`/`MockSTT`/`MockTTS`, verifica state machine `In Progress → Completed → Debrief`.
- **Unit (provider adapter)**: ogni adapter ha test con `httpx.MockTransport` (per adapter HTTP) o con `monkeypatch` dell'SDK ufficiale (per adapter SDK-based) che valida richiesta inviata + parsing risposta (fixtures JSON nel test). Test eseguibili **senza rete**, **senza chiavi API**, in CI standard.
- **Architectural test (`test_provider_encapsulation.py`)**: scansiona ricorsivamente `os_lms/` e fallisce se trova `import openai`, `import anthropic`, `import google.genai`, `import deepgram`, `import elevenlabs`, `import azure.cognitiveservices` (e simili) **fuori da** `os_lms/os_lms/ai/utils/{llm,stt,tts}/providers/`. Garantisce che la regola di encapsulation SDK non venga violata silenziosamente in futuro.
- **Integration**: Frappe test client su endpoint REST; verifica permessi student vs instructor vs manager.
- **Voice integration test (fase 2)**: un test end-to-end con `MockSTT`+`MockProvider`+`MockTTS` che simula `send_audio` → verifica generazione turno completo, persistenza audio, eventi WS emessi.
- **E2E (Cypress)**: in `cypress/e2e/simulations.cy.js` — happy path chat, abbandono, retry scenario, debrief visualizzato. Per voce (`simulations_voice.cy.js`): upload audio fixture, verifica trascrizione+sintesi end-to-end con provider mock.
- **Smoke real-provider** (manuale, una volta per release): playbook di test su provider reali con scenario "golden" — verifica funzionamento contrattuale (modelli aggiornati, chiavi valide, voci esistenti).
- **Manuale**: ogni release usa un test set di 5-10 scenari "golden" con valutazione umana settimanale (vedi `PLAN.md §10.4`).

## 11. Decisioni aperte da confermare

1. **SDK ufficiali per gli adapter**: regola architetturale fissata (§3.3.1) — **SDK ufficiale consentito ma solo dentro l'adapter del provider corrispondente**; mai usato dal codice business o da altri moduli. Dipendenze SDK come `[project.optional-dependencies]` extras per-provider in `pyproject.toml`, import lazy con `ProviderSdkNotInstalled` se mancanti. Test CI (`test_provider_encapsulation.py`) verifica con grep che nessun file fuori da `providers/` importi un SDK provider-specifico. **OK come regola? Lista extras definitiva da decidere quando si scrive ogni adapter.**
2. **Gemini via OpenAI-compat o REST nativo?** Google espone un endpoint OpenAI-compatible (`https://generativelanguage.googleapis.com/v1beta/openai/`) che permetterebbe a `GeminiProvider` di derivare da `OpenAICompatibleProvider` con zero codice extra, al costo di rinunciare a feature non standard (file API, grounding). **Proposta: usare endpoint OpenAI-compat per il role-play, REST nativo solo se in futuro servono feature avanzate.** OK?
3. **Provider STT default fase 2**: proposto `OpenAIWhisper` (riusa `openai_key`, single billing, qualità buona). Alternativa: `Deepgram Nova-3` se serve latenza <1s in pilot. OK Whisper come default, Deepgram come fallback?
4. **Provider TTS default fase 2**: proposto `OpenAITTS` con modello `gpt-4o-mini-tts` (low cost, voci sufficienti per pilot). Alternativa premium: `ElevenLabs` se la qualità voce è critica per il role-play. OK OpenAI come default?
5. **Formato audio in uscita**: proposto `mp3` (compatibile ovunque, bitrate basso). Alternative: `opus` (qualità migliore a parità di bitrate, supportato da browser moderni) o `pcm16` per minore latenza. **MP3 OK come default?**
6. **VAD client-side**: proposta `@ricky0123/vad-web` (Silero VAD via ONNX, ~2MB). Alternativa: solo push-to-talk in MVP, VAD in fase 3. Decisione richiesta perché impatta UX percepita.
7. **Frappe File vs S3 per audio**: MVP solo Frappe File privato (più semplice, sufficiente per pilot). Migrazione a S3 in fase 2 se >100 sessioni voce/giorno.
8. **Modello debrief default**: proposto `gpt-4.1` (single-billing OpenAI). Alternative configurabili in qualunque momento via Settings (no deploy). OK come default?
9. **Streaming**: in MVP solo WebSocket per chat testuale; HTTP `send_message` sincrono. In fase 2 anche TTS in streaming via WS. OK?
10. **Pannello docente**: full SPA Vue (proposto) o anche Desk views auto-generate da Frappe? Proposta: Vue per coerenza UX studente, Desk forms restano per CRUD scenario/rubric.

---

## Appendice A — Esempio uso `LLMProvider`

Lo stesso codice business funziona con qualunque provider configurato. Il call site non importa mai una classe provider-specifica.

```python
# os_lms/os_lms/ai/simulations/role_play.py
from os_lms.os_lms.ai.utils.llm import resolve_provider, ChatMessage
from os_lms.os_lms.ai.utils.llm.errors import LLMRateLimit, LLMServerError

def reply_as_customer(session, user_text: str) -> str:
    provider = resolve_provider(
        purpose="chat",
        override=session.scenario_provider_override,   # opzionale
    )
    history = [
        ChatMessage(role=t.role, content=t.text_content)
        for t in load_turns(session)
    ]
    history.append(ChatMessage(role="user", content=user_text))

    try:
        response = provider.chat(
            messages=history,
            system=build_role_play_system_prompt(session),
            model=session.scenario_model_override or None,
            temperature=0.75,
            max_tokens=400,
        )
    except (LLMRateLimit, LLMServerError):
        provider = next_fallback_provider("chat", failed=provider.name)
        response = provider.chat(messages=history, system=..., max_tokens=400)

    persist_turn(
        session,
        text=response.text,
        provider_used=response.provider,
        model_used=response.model,
        tokens_input=response.usage.prompt_tokens,
        tokens_output=response.usage.completion_tokens,
    )
    return response.text
```

Esempio di **structured output** per il debrief, indipendente dal provider:

```python
from os_lms.os_lms.ai.utils.llm import resolve_provider, ChatMessage, JsonSchema
from os_lms.os_lms.ai.simulations.debrief import DebriefSchema  # pydantic

provider = resolve_provider(purpose="debrief")
response = provider.chat(
    messages=[ChatMessage(role="user", content=build_debrief_user_prompt(session))],
    system=DEBRIEF_SYSTEM_PROMPT,
    temperature=0.2,
    max_tokens=2000,
    response_format=JsonSchema(name="debrief", schema=DebriefSchema.model_json_schema()),
)
debrief = DebriefSchema.model_validate_json(response.text)
```

Cambiare provider per uno scenario: l'admin imposta `provider_override = "gemini"` sullo Scenario, niente codice cambia.

### Esempio uso `STTProvider` e `TTSProvider`

```python
# os_lms/os_lms/ai/simulations/voice_orchestrator.py
from os_lms.os_lms.ai.utils.stt import resolve_stt_provider
from os_lms.os_lms.ai.utils.tts import resolve_tts_provider, SynthesisRequest
from os_lms.os_lms.ai.utils.stt.errors import STTRateLimit, STTServerError
from os_lms.os_lms.ai.utils.tts.errors import TTSRateLimit, TTSServerError

# STT: provider trasparente al caller
stt = resolve_stt_provider(override=session.stt_provider_override)
try:
    result = stt.transcribe(
        audio_bytes,
        mime_type="audio/webm;codecs=opus",
        language=session.language or "it",
        prompt=f"Cliente {session.generated_persona['role']} di {session.generated_persona['company']}",
    )
except (STTRateLimit, STTServerError):
    stt = next_fallback_stt(failed=stt.name)
    result = stt.transcribe(audio_bytes, mime_type="audio/webm;codecs=opus")

# TTS streaming: stesso pattern
tts = resolve_tts_provider(override=session.tts_provider_override)
request = SynthesisRequest(
    text=reply_text,
    voice_id=session.customer_voice_id,
    language=session.language or "it",
    speaking_rate=session.customer_voice_speaking_rate or 1.0,
)
try:
    for chunk in tts.synthesize_stream(request, format="mp3"):
        publish_audio_chunk(session, chunk)
except (TTSRateLimit, TTSServerError):
    tts = next_fallback_tts(failed=tts.name)
    result = tts.synthesize(request, format="mp3")
    publish_audio_chunk(session, AudioChunk(data=result.audio, is_final=True))
```

Cambiare provider TTS per coerenza voce di uno scenario: l'admin imposta `tts_provider_override = "elevenlabs"` e seleziona la `customer_voice_id` dal dropdown popolato da `list_tts_voices`; nessun cambio codice.

## Appendice B — Estratto schema JSON debrief (riepilogo)

Identico a `PLAN.md §5.4`. Lo schema viene validato server-side con `pydantic.BaseModel` (`DebriefSchema`) in `debrief.py`. In caso di `ValidationError`: retry una volta con prompt correttivo, poi `status="Needs Review"` su Session.

## Appendice C — Mapping naming convention

| Spec originale | Implementazione `os_lms` |
| --- | --- |
| `Simulation Scenario` | `LMSA Simulation Scenario` |
| `Evaluation Rubric` | `LMSA Evaluation Rubric` |
| `Simulation Session` | `LMSA Simulation Session` |
| `Simulation Turn` | `LMSA Simulation Turn` |
| `Simulation Debrief` | `LMSA Simulation Debrief` |
| `Recording Consent Log` | `LMSA Recording Consent Log` |
| `Rubric Criterion` | `LMSA Rubric Criterion` |
| App `ai_simulations` | Modulo `os_lms.os_lms.ai.simulations` |
| Endpoint `/api/method/ai_simulations.api.*` | `/api/method/os_lms.os_lms.ai.simulations.api.*` |
| `AIProvider` ABC (PLAN.md §3.3.2) | `LLMProvider` ABC (`os_lms.os_lms.ai.utils.llm.provider`) |
| `AnthropicProvider`, `OpenAIProvider` | adapter in `os_lms.os_lms.ai.utils.llm.providers.*` (estensibili: Gemini, DeepSeek, OpenAI-compat self-hosted) |
| Whisper (STT) — singolo provider | `STTProvider` ABC + adapter `OpenAIWhisper`, `Deepgram`, `GoogleSTT`, `AzureSTT`, `ElevenLabsSTT`, `MockSTT` (`os_lms.os_lms.ai.utils.stt.providers.*`) |
| OpenAI TTS / ElevenLabs (singoli) | `TTSProvider` ABC + adapter `OpenAITTS`, `ElevenLabsTTS`, `GoogleTTS`, `DeepgramAura`, `AzureTTS`, `MockTTS` (`os_lms.os_lms.ai.utils.tts.providers.*`) |
