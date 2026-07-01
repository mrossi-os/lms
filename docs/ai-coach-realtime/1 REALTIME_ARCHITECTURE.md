# Architettura — Simulazioni vocali in tempo reale (Realtime / Live)

> Documento di **design** (non ancora implementato). Definisce come aggiungere una
> modalità **voice-to-voice in tempo reale** alle simulazioni (es. colloquio di
> lavoro), in alternativa al chained TTS/STT a turni usato nel tutor AI.
>
> Confronto TTS/STT vs Realtime: vedi [../audio/PLAN.md](../audio/PLAN.md).
> Stato: `[ ]` da fare.

## 1. Obiettivo e perché Realtime

La modalità **chat** attuale ([orchestrator.py](orchestrator.py)) è a turni: il
candidato scrive, l'LLM risponde testo. Per un colloquio realistico serve invece
una conversazione **parlata, bidirezionale, in tempo reale**, in cui l'AI:

1. **percepisce** tono, esitazioni, ritmo e sicurezza del candidato (il chained li
   perde nello step STT→testo);
2. **recita** un personaggio con voce espressiva, pause, interruzioni (barge-in);
3. **reagisce** dinamicamente allo stato emotivo dell'interlocutore.

Questo richiede un modello **speech-to-speech** (OpenAI Realtime API o Gemini Live
API), non più STT + LLM + TTS separati.

## 2. Principio architetturale chiave

> **L'audio NON passa dal backend Frappe.** Lo stream viaggia
> **browser ↔ provider** via WebRTC (bassa latenza). Frappe resta fuori dal
> percorso audio e governa solo: autorizzazione, persona, persistenza del
> transcript e debrief.

```
                 (1) mint ephemeral token          (3) WebRTC audio stream
   Browser  ───────────────────────────►  Frappe ─────────────────────────►  Provider
 (mic/speaker) ◄──────────────────────── (no audio) ◄───────────────────────  (gpt-realtime /
      │            token + session config                  audio+events           gemini-live)
      │                                                                              
      │  (4) relay eventi transcript (whitelisted API)                              
      └──────────────────────────────────►  Frappe  ──►  LMSA Simulation Turn      
                                              │                                      
                                       (5) end → debrief job (riusa pipeline esistente)
```

Motivazione: Frappe (worker request/response) non è adatto a fare da relay audio
bidirezionale long-lived. WebRTC diretto dà latenza conversazionale; il backend
fa da **control plane**, non da **data plane**.

## 3. Cosa si riusa dall'esistente (zero riscrittura)

| Componente esistente | Riuso nella modalità voice |
|---|---|
| **LMSA Simulation Scenario** (persona, situazione, obiettivi, difficoltà, `evaluation_schema`, `provider_override`) | Identico: la persona del selezionatore nasce qui. |
| **ScenarioVariantGenerator** ([role_player.py](role_player.py)) | Identico: genera persona+situazione concrete dal seed *prima* di aprire la sessione live. |
| `build_role_play_system_prompt` ([prompts/role_play.py](prompts/role_play.py)) | Riusato come **`instructions`** della sessione Realtime (la persona diventa il system prompt del modello voce). |
| **LMSA Simulation Session / Turn** | Identici: i turni vengono persistiti dai transcript emessi dal Realtime. |
| **Debrief job** ([tasks.py](tasks.py) → [eval/judges/](eval/judges/)) | Riusato: lavora sui Turn testuali. Esteso con giudici "soft-skill" (vedi §8). |
| `chat_with_fallback` / astrazione `utils/llm` | Riusato per la **generazione variante** e il **debrief** (restano testuali). |
| `modality` su Session (oggi default `"chat"`) | Nuovo valore **`"voice"`** → discrimina il flusso. |
| `pseudonymize_session_id` | Riusato: l'id sessione inviato al provider resta pseudonimizzato. |
| `validate_quota` (hook before_insert) | Riusato: stessa quota giornaliera per le sessioni voice. |

## 4. Nuovi componenti

Si rispecchia la convenzione già adottata per `utils/llm/` e `utils/audio/`
(ABC + registry + config + `resolve_*`) — interfacce **separate**, logica d'uso
**gemella**.

```
ai/utils/realtime/                     # astrazione provider realtime (NUOVO)
├── __init__.py        # resolve_realtime_provider(), build_realtime_config()
├── provider.py        # RealtimeProvider (ABC) + RealtimeSession dataclass
├── config.py          # RealtimeProviderConfig
├── registry.py        # @register_realtime, get_realtime_provider
├── errors.py          # RealtimeError, RealtimeUnsupported, RealtimeInvalidAuth, ...
└── providers/
    ├── __init__.py    # side-effect registration
    ├── openai_realtime.py   # OpenAI Realtime (WebRTC + ephemeral client secret)
    ├── gemini_live.py       # Gemini Live API (BidiGenerateContent)
    └── mock.py              # deterministico per i test

ai/realtime/                           # feature layer whitelisted (NUOVO)
├── __init__.py
└── api.py             # create_voice_session(), persist_transcript_turn(), end_voice_session()
```

Frontend (custom, niente override Vite):

```
frontend/src/oslms/
├── composables/useRealtimeSession.js   # WebRTC lifecycle, RTCPeerConnection, data channel, eventi
└── components/simulations/VoiceSession.vue  # UI live: stato connessione, livello audio, transcript live, stop
```

## 5. Astrazione provider Realtime

```python
@dataclass
class RealtimeSession:
    provider: str
    model: str
    client_secret: str        # token effimero per il browser (mai la api key)
    expires_at: int
    connect_url: str          # endpoint WebRTC/WS del provider
    extra: dict               # campi provider-specific per il client

class RealtimeProvider(ABC):
    name: str = ""

    def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
        """Conia un token effimero lato server (usa la api key dalle settings).
        Il browser si collega col token, non con la chiave."""
        raise RealtimeUnsupported(...)

    def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
        """Normalizza un evento del provider in (role, text, final) per la
        persistenza dei Turn. Filtra i delta non finali."""
        ...

    def health_check(self) -> bool: ...
```

`RealtimeSessionConfig` (costruito dal feature layer dalla persona/Scenario):
`instructions` (system prompt persona), `voice`, `input_audio_transcription`
(per ottenere il testo del parlato del candidato), `turn_detection` (server VAD /
semantic VAD), `tools` (function calling opzionale), `modalities=["audio","text"]`.

### Adapter OpenAI (`openai_realtime.py`)
- Modello: `gpt-realtime` (GA) / `gpt-4o-realtime-preview`.
- `create_session`: `POST /v1/realtime/client_secrets` con la api key → ritorna un
  **client secret effimero** (~1 min) + config sessione. Trasporto browser: **WebRTC**.
- Eventi rilevanti da persistere:
  - `conversation.item.input_audio_transcription.completed` → turno **user**.
  - `response.output_audio_transcript.done` → turno **assistant**.
- Persona = `instructions`; tono/recitazione steerabili nel prompt; voce nativa.

### Adapter Gemini (`gemini_live.py`)
- Modello: `gemini-2.5-flash-native-audio` / `*-live` (preview).
- Trasporto: **WebSocket** `BidiGenerateContent`; persona = `system_instruction`;
  `speechConfig` per la voce; transcription input/output disponibili per i Turn.
- Nota preview: API meno stabile → tenerlo dietro un flag, OpenAI come default.

## 6. Flusso end-to-end

```
start_voice_session(scenario_id)                       [whitelisted]
  ├─ gate simulations_enabled + scenario Published + quota
  ├─ ScenarioVariantGenerator.generate(seed)           # persona+situazione (LLM testuale)
  ├─ crea LMSA Simulation Session (modality="voice", generated_persona=...)
  ├─ instructions = build_role_play_system_prompt(persona, situazione, difficoltà)
  ├─ provider = resolve_realtime_provider(scenario.provider_override)
  └─ session_token = provider.create_session(cfg)      # token effimero
     return { session_id, client_secret, connect_url, voice, model }

CLIENT (useRealtimeSession.js)
  ├─ getUserMedia(mic) → RTCPeerConnection → connette al provider col client_secret
  ├─ conversazione vocale in tempo reale (barge-in, prosodia)
  └─ su ogni evento transcript finale → POST persist_transcript_turn(session_id, role, text, ts)

persist_transcript_turn(...)                           [whitelisted]
  └─ append LMSA Simulation Turn (riusa _persist_turn) + publish_realtime (UI live)

end_voice_session(session_id, reason)                  [whitelisted]
  ├─ status=completed, ended_at, submit() (immutabile)
  └─ enqueue generate_debrief  ← STESSA pipeline della chat
```

Il debrief gira **identico** sui Turn testuali; l'estensione soft-skill (§8) è additiva.

## 7. Persona, personalità e turn-taking

- **Contenuto** (cosa dice): persona dello Scenario → `instructions`.
- **Recitazione** (come lo dice): direttive di stile nel prompt
  ("tono fermo, scettico, pause strategiche") + scelta della voce.
- **Turn detection**: `server_vad` (rileva fine-frase dal silenzio) o `semantic_vad`
  → consente al modello di interrompere/essere interrotto come in un colloquio vero.
- **Anti-injection**: `detect_injection` oggi è testuale; in voice va applicato al
  transcript del candidato a valle, con eventuale rientro in carattere
  (`in_character_refusal`) iniettato come messaggio di sistema nella sessione live.

## 8. Debrief esteso (il vero valore aggiunto)

Poiché l'audio non è appiattito a solo testo, si possono valutare le **soft skill**
— impossibile nel chained:

- **MVP**: debrief invariato sui Turn testuali (riusa i giudici esistenti: coverage,
  persona, difficulty, debrief).
- **Estensione**: nuovo giudice `delivery` che valuta chiarezza/sicurezza/ritmo.
  Due strade per le feature di delivery:
  1. chiedere allo stesso modello Realtime una **auto-valutazione** della delivery a
     fine sessione (economico, nessuna infra extra);
  2. **catturare l'audio** del candidato (vedi §9) e analizzarlo separatamente
     (più ricco, ma con implicazioni privacy/costo).

## 9. Sicurezza, privacy, integrità

- **Token effimeri**: la api key resta sul server; il browser riceve solo un client
  secret a vita breve. Mai esporre la chiave nello SPA.
- **Pseudonimizzazione**: id sessione verso il provider via `pseudonymize_session_id`.
- **Audio retention**: di default **non** si memorizza l'audio grezzo (solo i
  transcript nei Turn). Se serve per il debrief delivery → File **privato** per
  sessione, con consenso esplicito e TTL/cancellazione.
- **Integrità del transcript (trust model)** — due opzioni:
  - **A. WebRTC diretto + relay client** (MVP consigliato): semplice, bassa latenza.
    Il client inoltra i transcript: accettabile per uno strumento di **pratica**, non
    a prova di manomissione.
    - **B. Relay server-side** (WebSocket via servizio asincrono dedicato, fuori da
    Frappe): il backend vede gli eventi in modo autoritativo. Necessario solo se la
    simulazione diventa un **esame ad alto rischio**. Più infra, più latenza.

## 10. Modifiche a doctype / settings

- **LMSA Simulation Scenario**: opzionali `voice` (override voce per-scenario) e
  `voice_instructions` (stile recitativo della persona).
- **LMSA Simulation Session**: `modality` accetta `"voice"`; campi audit
  `realtime_provider_used`, `realtime_model_used`, `voice_used`,
  `session_seconds` (per costo/quota al minuto).
- **LMSA Settings** (sezione nuova "Realtime / Voice"): `realtime_enabled`,
  `realtime_provider` (`openai`\|`gemini`), `realtime_model`, `realtime_voice`,
  `turn_detection` (`server_vad`\|`semantic_vad`), `realtime_max_session_seconds`.

## 11. Costi e limiti (decisione informata)

- **Tariffazione al minuto audio** (input+output) → introdurre `realtime_max_session_seconds`
  e riusare la quota giornaliera. Tracciare `session_seconds` per il reporting.
- **Ragionamento**: i modelli realtime sono un gradino sotto i top testuali → la
  *generazione della persona/variante* resta affidata al modello testuale (già così);
  durante la sessione live ragiona il modello voce.
- **Niente fallback in streaming**: a differenza di `chat_with_fallback`, una sessione
  live non può fare failover a metà. La scelta provider è fissata all'avvio.
- **Maturità**: OpenAI Realtime è GA; Gemini Live è preview → **OpenAI default**.

## 12. Fasi di implementazione

1. **Astrazione** `utils/realtime/` (ABC + registry + config + mock) — testabile senza rete.
2. **Adapter OpenAI** (`create_session` ephemeral + `parse_transcript_event`) + unit test con `requests` mockato.
3. **Feature layer** `ai/realtime/api.py` (`create_voice_session`, `persist_transcript_turn`, `end_voice_session`) — riusa SessionOrchestrator/`_persist_turn`.
4. **Frontend** `useRealtimeSession.js` (WebRTC) + `VoiceSession.vue` (collegato al campo `modality="voice"`).
5. **Settings + Scenario** (campi §10) + i18n.
6. **Debrief delivery** (giudice soft-skill) — estensione additiva.
7. **Adapter Gemini Live** dietro flag.

## 13. Decisioni aperte

- Trust model transcript: A (relay client) per la pratica, o subito B per esami?
- Cattura audio per il debrief delivery: sì/no? (privacy vs ricchezza valutativa)
- WebRTC (browser) confermato vs WebSocket: per il client browser WebRTC è lo standard
  consigliato; WebSocket solo per un eventuale relay server-side.
- Provider di default e modello (OpenAI `gpt-realtime`).
