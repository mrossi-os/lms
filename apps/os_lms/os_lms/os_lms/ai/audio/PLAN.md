# Piano di sviluppo — TTS / STT nel Tutor AI

> Documento di tracciamento. Stato task: `[ ]` da fare · `[~]` in corso · `[x]` fatto.
> Ambito di **questa** iterazione: **solo Tutor AI** ([frontend/src/oslms/components/ai/ChatBot.vue](../../../../../../frontend/src/oslms/components/ai/ChatBot.vue)). Simulazioni rinviate (vedi §Fasi successive).

## Obiettivo

Permettere allo studente di:
1. **Parlare** al tutor: registra un audio nella chat → trascrizione (STT) → testo nell'input.
2. **Ascoltare** la risposta del tutor: pulsante "play" su ogni messaggio assistant → sintesi vocale (TTS).

## Decisioni di base

- **Abstraction audio separata** da quella della chat, ma **gemella** nei pattern (ABC + registry + config + `resolve_*`).
- **Solo OpenAI** ora. Gemini in seguito. DeepSeek e Anthropic **esclusi**: non offrono TTS/STT.
- **TTS** server-side OpenAI, **on-demand** (click "play"), con **cache lato client** (la cache server-side è una fase successiva).
- **STT** OpenAI (`/audio/transcriptions`); la trascrizione **riempie l'input** (l'utente rilegge e invia).
- Provider audio **indipendente** dal provider della chat, configurato in `LMSA Settings`.
- Trasporto audio via **base64 nel body** (clip brevi, nessun File su disco, privacy).

### Razionale collocazione file

Si rispecchia la convenzione già presente nel repo:
- **Astrazione provider** → `ai/utils/audio/` (specchio di `ai/utils/llm/`).
- **Endpoint whitelisted** → `ai/audio/api.py` (specchio di `ai/tutor/api.py`, `ai/ingestion/api.py`).

---

## A. Backend — astrazione `ai/utils/audio/`

Specchio di [ai/utils/llm/](../utils/llm/).

```
ai/utils/audio/
├── __init__.py        # resolve_audio_provider("stt"/"tts"), build_audio_config()
├── provider.py        # AudioProvider (ABC) + TranscriptionResult / SpeechResult
├── config.py          # AudioProviderConfig
├── registry.py        # @register_audio, get_audio_provider, list_audio_providers
├── errors.py          # AudioError, AudioUnsupported, AudioInvalidAuth, AudioRateLimit, AudioServerError, AudioTimeout, AudioInvalidInput
└── providers/
    ├── __init__.py    # side-effect: importa gli adapter (registrazione)
    ├── openai.py      # OpenAIAudioProvider (requests, SDK-free)
    └── mock.py        # MockAudioProvider (test deterministici)
```

### Contratto `provider.py`

Default = `AudioUnsupported`, così i provider non capaci ereditano senza codice.

```python
@dataclass
class TranscriptionResult:
    text: str; model: str; provider: str; raw: dict

@dataclass
class SpeechResult:
    audio: bytes; mime: str; model: str; provider: str

class AudioProvider(ABC):
    name: str = ""
    def transcribe(self, audio: bytes, *, mime: str,
                   language: str | None = None, model: str | None = None) -> TranscriptionResult:
        raise AudioUnsupported(f"{self.name} non supporta STT")
    def synthesize(self, text: str, *, voice: str,
                   model: str | None = None, fmt: str = "mp3") -> SpeechResult:
        raise AudioUnsupported(f"{self.name} non supporta TTS")
    def health_check(self) -> bool: ...
```

### `providers/openai.py`

`requests` (SDK-free, come gli adapter chat). Riusa `openai_key` + `openai_base_url` dalle settings.
- `transcribe` → `POST {base_url}/audio/transcriptions`, **multipart** (`file`, `model`, `language`), parse `{ text }`.
- `synthesize` → `POST {base_url}/audio/speech`, JSON `{ model, voice, input, response_format: "mp3" }`, ritorna `r.content`.
- `_check_status`: 401/403→`AudioInvalidAuth`, 429→`AudioRateLimit`, ≥500→`AudioServerError`, timeout→`AudioTimeout`.

### `__init__.py`

- Riusa `load_settings` di [ai/utils/llm/__init__.py](../utils/llm/__init__.py) (un solo `OsLmsSettings`).
- `build_audio_config(name, settings, *, capability)` → `AudioProviderConfig`.
- `resolve_audio_provider("stt"|"tts", override=None)` → sceglie `settings.stt_provider`/`tts_provider` (default `openai`).
- Fallback multi-provider: **rinviato** all'arrivo di Gemini (hook predisposto).

---

## B. Backend — Settings

1. **Dataclass** [ai/utils/oslms_settings.py](../utils/oslms_settings.py) — campi additivi (defaulted):
   ```python
   stt_enabled: bool = False
   stt_provider: str = "openai"
   stt_model: str = "gpt-4o-mini-transcribe"   # alt: whisper-1
   tts_enabled: bool = False
   tts_provider: str = "openai"
   tts_model: str = "gpt-4o-mini-tts"           # alt: tts-1
   tts_voice: str = "alloy"
   ```
2. **Loader** `_load_settings()` in [ai/utils/llm/__init__.py](../utils/llm/__init__.py) (~riga 163) — popola i 7 campi con `getattr`.
3. **Doctype** [doctype/lmsa_settings/lmsa_settings.json](../../doctype/lmsa_settings/lmsa_settings.json) — nuovo `section_audio` ("Audio (TTS / STT)") + campi, aggiunti anche a `field_order`. Provider = Select `openai` (Gemini dopo).

---

## C. Backend — Endpoint `ai/audio/api.py`

Annotazione di tipo obbligatoria (`require_type_annotated_api_methods`); richiedono login (no guest).

```python
@frappe.whitelist()
def transcribe(audio: str, mime: str = "audio/webm", language: str = "it") -> dict:
    # gate stt_enabled → decode base64 → guard (non vuoto, ≤ ~25MB)
    # resolve_audio_provider("stt").transcribe(bytes, mime=mime, language=language)
    return {"text": result.text}

@frappe.whitelist()
def synthesize(text: str, voice: str | None = None) -> dict:
    # gate tts_enabled → resolve_audio_provider("tts").synthesize(text, voice=...)
    return {"audio": base64(result.audio), "mime": result.mime}
```
Errori `AudioError` → `frappe.throw` con messaggio amichevole.

---

## D. Frontend — solo ChatBot

Componenti `oslms/` sono custom → editabili direttamente (niente override Vite).

| File nuovo | Ruolo |
|---|---|
| `frontend/src/oslms/utils/audioApi.js` | `transcribeAudio(blob)`, `synthesizeSpeech(text)`, `blobToBase64` |
| `frontend/src/oslms/composables/useSpeechToText.js` | `MediaRecorder` (mime dinamico Safari) → `{ isRecording, isTranscribing, toggle }` |
| `frontend/src/oslms/composables/useTextToSpeech.js` | singolo `Audio` condiviso + cache `Map` → `{ playingId, isSynthesizing, play, stop }` |
| `frontend/src/oslms/components/ai/MicButton.vue` | toggle microfono, `@transcript(text)` |
| `frontend/src/oslms/components/ai/SpeakButton.vue` | play/stop/loading per messaggio |

> ⚠️ **Non** riusare [frontend/src/components/AudioBlock.vue](../../../../../../frontend/src/components/AudioBlock.vue): usa `document.querySelector('audio')` (riga 58), prende il primo `<audio>` della pagina → si rompe con più messaggi. `useTextToSpeech` usa una singola istanza `Audio` dedicata.

### Innesti in `ChatBot.vue`

- Riga input (~riga 79, prima del Send): `<MicButton v-if="sttEnabled" :disabled="chat.isLoading" @transcript="t => chat.question = t" />`.
- Risposta assistant (~righe 31–35): affianca `<SpeakButton v-if="ttsEnabled" :text="message.content" :id="index" />`.
- Flag: `sttEnabled`/`ttsEnabled` = `settingsStore.settings?.data?.stt_enabled` / `tts_enabled`.

### Esposizione flag al SPA

[os_lms/override_api.py](../../override_api.py) `get_lms_settings()` (~riga 58), accanto ad `ai_enabled`:
```python
result["stt_enabled"] = bool(lmsa.get("stt_enabled"))
result["tts_enabled"] = bool(lmsa.get("tts_enabled"))
```

---

## E. i18n & Test

- **i18n**: etichette/`aria-label` in `__()` + stringhe IT in `lms/translations/it.csv`.
- **Test backend**: `MockAudioProvider` (registrato `mock`); unit test su `OpenAIAudioProvider` (mock `requests`), `resolve_audio_provider`, e i due endpoint con gate on/off.

---

## Checklist a fasi

### Fase 1 — Settings ✅
- [x] Campi audio in `OsLmsSettings` (dataclass)
- [x] Popolamento in `_load_settings()`
- [x] `section_audio` + campi in `lmsa_settings.json` (+ `field_order`)
- [x] Flag `stt_enabled`/`tts_enabled` in `override_api.get_lms_settings()`

### Fase 2 — Core audio (`ai/utils/audio/`) ✅
- [x] `provider.py` (ABC + dataclass)
- [x] `config.py` (`AudioProviderConfig`)
- [x] `errors.py`
- [x] `registry.py`
- [x] `providers/openai.py`
- [x] `providers/mock.py`
- [x] `providers/__init__.py` (registrazione)
- [x] `__init__.py` (`resolve_audio_provider`, `build_audio_config`)

### Fase 3 — Endpoint (`ai/audio/api.py`) ✅
- [x] `transcribe()`
- [x] `synthesize()`

### Fase 4 — Frontend (Tutor) ✅
- [x] `utils/audioApi.js`
- [x] `composables/useSpeechToText.js`
- [x] `composables/useTextToSpeech.js`
- [x] `components/ai/MicButton.vue`
- [x] `components/ai/SpeakButton.vue`
- [x] Wiring in `ChatBot.vue` (mic + speak + flag)
- Build di produzione `yarn build` ok (28.7s, nessun errore)

### Fase 5 — i18n & test ✅
- [x] Etichette in `__()` + traduzioni `it.csv` (27 stringhe)
- [x] Test backend abstraction (`ai/utils/audio/tests/test_audio.py`)
- [x] Test backend endpoint (`ai/audio/tests/test_api.py`)

### Fasi successive (fuori ambito ora)
- [ ] Adapter **Gemini** (API nativa `generateContent` + fallback)
- [ ] Cache TTS **server-side** (File privato per hash)
- [ ] Estensione a **simulazioni** ([ChatSession.vue](../../../../../../frontend/src/oslms/components/simulations/ChatSession.vue) + composable)
- [x] Sezione "Audio (TTS / STT)" nel pannello SPA `Settings.vue` (tab AI → campi su `LMSA Settings`, con default come placeholder)
- [x] Opzione `tts_autoplay_on_stt`: legge la risposta ad alta voce in automatico quando la domanda è posta a voce

---

## Rischi / dettagli

- **Mime `MediaRecorder`**: webm/opus (Chrome/FF) vs mp4 (Safari) → `MediaRecorder.isTypeSupported`.
- **Limiti**: durata max ~60s lato client (limite OpenAI 25 MB/file); gate `stt_enabled`/`tts_enabled` su FE e BE.
- **Permessi microfono**: rifiuto `getUserMedia` → `toast.error`, nessun crash.
- **Migrazione**: `bench migrate` assorbe i nuovi campi del Single; nessun dato da migrare; nessuna nuova dipendenza Python (`requests` già presente).
