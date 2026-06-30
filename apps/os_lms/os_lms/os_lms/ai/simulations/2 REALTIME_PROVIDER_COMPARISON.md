# Relazione — Scelta del provider Speech-to-Speech per le simulazioni di colloquio

> Documento di **analisi comparativa** a supporto di [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md).
> Obiettivo: scegliere il provider per una chat vocale **speech-to-speech in tempo reale**
> (tipo OpenAI Realtime / Gemini Live) per le simulazioni di colloquio.
>
> - **Data ricerca:** 2026-06-30
> - **Fonti:** esclusivamente documentazione ufficiale dei provider (vedi Appendice).
> - **Provider valutati a fondo:** OpenAI Realtime · Gemini Live · ElevenLabs Conversational AI.
> - **Stato:** raccomandazione pronta; correzioni al doc di architettura elencate in §8.

---

## 0. Sintesi e raccomandazione (TL;DR)

**Usare OpenAI Realtime con il modello `gpt-realtime-2`, trasporto WebRTC, come provider di
default — dentro l'astrazione `RealtimeProvider` già prevista in [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md).
Tenere Gemini Live dietro un flag come opzione di costo a volume. NON adottare ElevenLabs come
motore centrale della simulazione.**

Il criterio decisivo coincide con la motivazione §1 del doc di architettura: la simulazione serve
a far sì che l'AI **percepisca tono, esitazioni, ritmo e sicurezza** del candidato. Questo richiede
**speech-to-speech nativo** (un solo modello audio→audio): lo offrono OpenAI e Gemini, **non**
ElevenLabs (che è una pipeline ASR→LLM→TTS e fa vedere all'LLM solo la trascrizione, perdendo la
prosodia in ingresso). Tra i due nativi, OpenAI vince per maturità (GA), sessione da 60 minuti,
aderenza al personaggio e perché **combacia con l'architettura e il codice già presenti** (riuso di
`LMSA Simulation Turn` e della pipeline di debrief).

| | MVP | Scalabile | Da evitare come core |
|---|---|---|---|
| **Scelta** | **OpenAI Realtime** (`gpt-realtime-2`, WebRTC) | OpenAI default + **Gemini** dietro flag (costo) | **ElevenLabs** (pipeline → niente prosodia) |

---

## 1. Contesto: come funzionano oggi le simulazioni (testuali)

Il sistema attuale è **testuale, a turni, non-streaming**, ma è già **provider-agnostico** e
predisposto al voice.

| Aspetto | Stato attuale | File |
|---|---|---|
| Definizione scenario | `LMSA Simulation Scenario`: `roleplay_persona`, `situation_template`, `learning_objectives`, `seed_variations`, `evaluation_schema`, `provider_override`, **`modality: chat/voice/both`**, **`time_limit_minutes`**, **`max_turns`** | doctype `lmsa_simulation_scenario` |
| Persona → system prompt | `build_role_play_system_prompt(...)` | [prompts/role_play.py](prompts/role_play.py) |
| Loop turni | user text → injection detection → LLM (Prompt 2, temp 0.7) → persist + `publish_realtime` | [orchestrator.py](orchestrator.py) |
| Astrazione LLM | OpenAI (default `gpt-4.1`), Gemini, Anthropic, DeepSeek, Mock | `ai/utils/llm/` |
| Transcript | `LMSA Simulation Turn` (`turn_index`, `role`, `text_content`, provider/model, `latency_ms`, token) | doctype `lmsa_simulation_turn` |
| Valutazione finale | job background → Prompt 3 con JSON Schema → `LMSA Simulation Debrief` (score, criteri, strengths/improvements, RAG) | [tasks.py](tasks.py) |
| Chiave API | `LMSA Settings` (campi cifrati per provider) | doctype `lmsa_settings` |

**Nota chiave:** `time_limit_minutes` e `max_turns` esistono ma **non sono ancora applicati**;
non c'è alcuna logica di chiusura automatica. Questo va progettato per il voice (§ durata/chiusura).

---

## 2. Tabella comparativa sintetica

| Dimensione | **OpenAI Realtime** | **Gemini Live** | **ElevenLabs Conversational AI** |
|---|---|---|---|
| Vero S2S nativo | ✅ single-model audio→audio | ✅ native audio (A2A) | ❌ pipeline ASR→LLM→TTS |
| Il modello "sente" la prosodia del candidato | ✅ | ✅ | ❌ (l'LLM vede solo testo) |
| Modello consigliato | `gpt-realtime-2` (GA, 128k, ragionamento) | `gemini-2.5-flash-native-audio` (GA su Vertex; Preview su AI Studio) | LLM a scelta o BYO + TTS ElevenLabs |
| Trasporto browser | **WebRTC** nativo (+ WS, SIP) | **WebSocket** (no WebRTC 1ª parte; WebRTC solo via partner) | **WebRTC + WebSocket** |
| Limite sessione | **60 min** | **15 min audio + ~10 min/connessione** → serve session resumption | nessun cap nativo (DIY) |
| Passaggio contesto | `instructions` via `session.update`, **aggiornabile a caldo** | `system_instruction` nel setup, **fisso al connect** | `{{dynamic_variables}}` + `overrides` per conversazione |
| Chiusura naturale | DIY (timer + `session.update`/`response.create`) | DIY (timer + `send_client_content` + `GoAway`) | **tool "End call" autonomo** + DIY per il cap |
| Transcript | eventi input/output transcription | `input/output_audio_transcription` | **webhook post-call** (transcript + audio MP3) |
| Valutazione finale integrata | ❌ (la fai tu — già presente) | ❌ (la fai tu — già presente) | ✅ **built-in** (Success Eval + Data Collection) |
| Tool / function calling | ✅ pieno + MCP remoto | ✅ (3.1 solo sync; 2.5 sync+async) | ✅ client/server/system/MCP |
| Italiano | ✅ | ✅ `it`, 30 voci | ✅ multilingual v2.5 |
| Latenza (dato ufficiale) | floor modello ~320 ms (non SLA E2E) | "sub-second", nessun numero | nessun numero pubblicato |
| Costo audio (per 1M token) | in **$32** / out **$64** | in **$3** / out **$12** | ~**$0,10/min** + LLM a parte |
| Costo stimato / colloquio 15′ | ~$1–3 | **~$0,15–0,40** | ~$1,5–2,5 |
| Maturità | **GA** | Preview (AI Studio) / **GA su Vertex** | GA |
| Lock-in | medio-alto (schema eventi proprietario) | medio-alto (`BidiGenerateContent`, non OpenAI-compatibile) | medio (LLM sostituibile; voce+eval proprietarie, solo hosted) |

> I costi/colloquio sono stime d'ordine di grandezza calcolate dalle tariffe ufficiali al
> minuto/token, **non** quotazioni ufficiali per-sessione.

---

## 3. OpenAI Realtime — analisi dei 10 punti

1. **S2S reale:** sì, nativo — *"listen, reason, and speak in one low-latency session"*; nessun
   passaggio STT/TTS intermedio.
2. **Implementazione:** il backend conia un *ephemeral client secret* (`POST /v1/realtime/client_secrets`);
   il browser apre `RTCPeerConnection`, invia l'offer SDP a `POST /v1/realtime/calls`
   (`Content-Type: application/sdp`), scambia eventi JSON sul data channel `oai-events`. La chiave
   API reale resta sul server. **È esattamente il flusso di [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md) §6.**
3. **Protocolli:** **WebRTC** (browser/mobile, raccomandato), **WebSocket** (server-to-server), **SIP**
   (telefonia). L'Agents SDK Python è solo WebSocket server-side (niente WebRTC browser).
4. **Contesto iniziale:** campo `instructions` (la persona) + `audio.output.voice` +
   `audio.input.turn_detection` + `tools`, inviati con `session.update`. **Aggiornabile in corsa**
   (es. fasi "warm-up → tecnica → chiusura" riscrivendo le istruzioni, o `response.create` con
   `instructions` per la singola risposta). ⚠️ la **voce si blocca dopo il primo audio**.
   Voci: `alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar`.
5. **Durata/chiusura:** **cap di sessione 60 min** (da set 2025, prima 30) → i 10-15 min stanno
   larghi, **niente logica di resumption**. **Nessun timer/chiusura nativi:** timer sul server →
   a T-N invii un `session.update` con direttiva di chiusura, oppure un `response.create` con
   `instructions` per-risposta; `idle_timeout_ms` su `server_vad` per i silenzi; risposte
   *out-of-band* (`"conversation":"none"`) per controlli in background.
6. **Transcript:** output `response.output_audio_transcript.delta` / `.done`; input
   `conversation.item.input_audio_transcription.delta` / `.completed` (abilitando la trascrizione
   input con modello `gpt-4o-transcribe`/`whisper-1` e `language:"it"`). **Sono gli eventi citati
   nel doc** → mappabili 1:1 su `_persist_turn`.
7. **Tool/eventi:** function calling pieno (`session.tools` → `function_call` in `response.done` →
   `conversation.item.create`/`function_call_output` → `response.create`), **MCP server remoti**,
   input immagini.
8. **Difficoltà:** media. Repo ufficiale `openai/openai-realtime-agents` (Next.js + WebRTC)
   adattabile; guida prompting con struttura persona/fasi pronta. Per il progetto è **la più
   facile** perché combacia con codice e doc esistenti.
9. **Pro/contro colloquio:** ✅ il modello **percepisce la prosodia** (requisito §1), barge-in nativo
   (`server_vad`/`semantic_vad`, `conversation.item.truncate`), persona stabile (`gpt-realtime-2`,
   128k + ragionamento), italiano ok. ❌ costo audio alto; voce ottima ma un gradino sotto
   ElevenLabs in "iper-realismo".
10. **Lock-in:** medio-alto — schema eventi proprietario (`session.update`, `response.create`, ...).
    I *trasporti* sono standard; la grammatica eventi no. **Persona e debrief restano portabili**;
    l'orchestrazione realtime va riscritta cambiando provider.

**Modelli (stato al 2026-06):** `gpt-realtime` (GA ago 2025, 32k context) · **`gpt-realtime-2`**
(GA mag 2026, **128k context**, `reasoning.effort`, **default consigliato**) · `gpt-realtime-mini`
(economico) · `gpt-4o-realtime-preview` (superato).

**Pricing (per 1M token, `gpt-realtime-2`):** audio in **$32** / out **$64**; testo in $4 / out $24;
cached $0,40. Stima ~**$1–3** per colloquio di 15 min.

---

## 4. Gemini Live — analisi dei 10 punti

1. **S2S reale:** sì, **native audio (audio-to-audio)**. ⚠️ i nomi nel doc (`*-live`, half-cascade)
   sono **dismessi (dic 2025)**. Modelli attuali: `gemini-2.5-flash-native-audio-preview-12-2025`
   (131k in / 8k out) e `gemini-3.1-flash-live-preview`; su **Vertex** `gemini-live-2.5-flash-native-audio`
   è **GA** (dic 2025).
2. **Implementazione:** WebSocket stateful `BidiGenerateContent`; SDK `google-genai`
   (`client.aio.live.connect(model, config)`); il primo messaggio è un `BidiGenerateContentSetup`.
   Token effimeri per il client (`auth_tokens.create`): ~1 min per **aprire** la sessione,
   ~30 min per **inviare**; compatibili solo con `v1alpha`.
3. **Protocolli:** **solo WebSocket (WSS)** lato Google. **Niente WebRTC di prima parte** → per
   WebRTC servono partner (LiveKit = WebRTC, Pipecat/Daily = WS, Agora, Voximplant, Firebase AI SDK).
   *Conferma la scelta WS del doc.*
4. **Contesto:** `system_instruction` nel `setup`; voce via
   `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` (30 voci); i modelli native-audio
   **scelgono la lingua da soli** (niente `language_code` esplicito) e supportano solo modalità
   AUDIO (testo via output transcription). ⚠️ il **system prompt è fisso al connect**: la steering
   di chiusura va iniettata come *turno di contenuto* (`send_client_content`), non riscrivendo la
   persona.
5. **Durata/chiusura:** ⚠️ **il nodo critico.** Sessione audio-only **15 min** senza compressione,
   ma **una connessione cade a ~10 min** → per 10-15 min **serve obbligatoriamente**:
   - **session resumption** (`SessionResumptionConfig.handle`; il server invia `SessionResumptionUpdate`;
     token validi 2h) per sopravvivere alla caduta connessione;
   - opzionale **context window compression** (`SlidingWindow`, trigger 80%) per sessioni "illimitate".
   Il messaggio **`GoAway`** con `timeLeft` segnala la chiusura imminente. Nessuna chiusura naturale
   nativa: timer server-side + iniezione di una direttiva di wrap-up.
6. **Transcript:** `input_audio_transcription` + `output_audio_transcription` (oggetti vuoti nel
   setup); testo in `server_content.input_transcription.text` / `output_transcription.text`. PCM
   grezzo disponibile (16 kHz in / 24 kHz out). La trascrizione aggiunge costo a token-testo.
7. **Tool/eventi:** function calling (dichiarato nel setup, **gestione manuale**, `FunctionResponse`),
   Google Search grounding. **NON supportati:** code execution, URL context, Maps. `3.1` solo
   **sincrono**; `2.5` anche **async** (`NON_BLOCKING` con scheduling `INTERRUPT`/`WHEN_IDLE`/`SILENT`).
8. **Difficoltà:** **medio-alta** (resumption + token effimeri + churn da Preview). Plus interessanti:
   **affective dialog** (adatta il tono all'emozione dell'utente) e **proactive audio** — ma **solo
   su 2.5, in `v1alpha`** (superficie meno stabile, **non** su 3.1).
9. **Pro/contro colloquio:** ✅ percepisce la prosodia, **costo ~5-10× più basso**, italiano ok
   (`it`), affective dialog ottimo per un selezionatore "emotivamente reattivo", barge-in con flag
   `interrupted`. ❌ Preview instabile su AI Studio, limiti di sessione, tool calling meno solido sul
   native-audio.
10. **Lock-in:** alto sul protocollo (`BidiGenerateContent`, **non** OpenAI-compatibile; il
    compat-layer OpenAI di Google **esclude** la Live API). *Dentro* Google sei portabile
    AI Studio↔Vertex (stesso SDK), ma cambia l'auth (API key → service account) e i tuned model non
    si trasferiscono.

**Pricing (per 1M token):** native-audio 2.5 → audio in **$3** / out **$12** (testo $0,50 / $2,00);
`3.1` quota anche al minuto → audio in **$0,005/min** / out **$0,018/min**. Esiste un *free tier*
(ma i dati vengono usati per il training). Stima ~**$0,15–0,40** per colloquio di 15 min.
Concorrenza: Vertex fino a **1.000 sessioni/progetto**; su AI Studio non documentato ufficialmente.

---

## 5. ElevenLabs Conversational AI — analisi dei 10 punti

1. **S2S reale:** ❌ **no.** È una **pipeline orchestrata** (ASR + turn-taking + LLM a scelta + TTS
   ElevenLabs). Conseguenza pesante: **l'LLM vede solo il testo trascritto → non percepisce
   tono/esitazioni/ritmo del candidato.** Contraddice il requisito §1.
2. **Implementazione:** crei un "Agent" (dashboard/API/CLI) con `prompt`, `voice_id`, `first_message`,
   LLM; SDK JS/React/Python/Swift/React-Native + widget `<elevenlabs-convai>`.
3. **Protocolli:** **WebRTC + WebSocket** (parametro `connectionType`; voce default WebRTC).
4. **Contesto:** ✅ **eccellente** — **dynamic variables** `{{...}}` iniettano obiettivi/scena/ruolo/
   carattere a runtime in system prompt e first message; **overrides** sostituiscono persona/voce/LLM
   per singola conversazione (da abilitare per campo nella tab Security). Variabili `system__*`
   integrate (es. `system__call_duration_secs`).
5. **Durata/chiusura:** ✅ **tool "End call" autonomo** — il modello chiude da solo quando il compito
   è completo / per accordo reciproco (con `reason` + messaggio di commiato). È il più vicino al
   *"chiude come una persona reale"*. ❌ **nessun cap di durata nativo** (lo imponi con
   `system__call_duration_secs` + prompt + timer client).
6. **Transcript:** ✅ **webhook post-call** (`post_call_transcription`: transcript + `analysis` +
   metadata; `post_call_audio`: MP3 integrale base64); endpoint REST Get Conversation.
7. **Valutazione:** ✅✅ **il vero differenziatore** — analisi post-call LLM integrata:
   **Success Evaluation** (fino a 30 criteri custom: esito success/failure/unknown + motivazione) e
   **Data Collection** (fino a 40 campi tipizzati). Niente judge separato. C'è anche un harness
   **Agent Testing**.
8. **Tool/eventi:** client tools, server/webhook tools, system tools, **MCP** (non sotto
   Zero-Retention/HIPAA).
9. **Pro/contro colloquio:** ✅ **voce più realistica in assoluto**, valutazione e transcript "chiavi
   in mano", persona-injection runtime ottima, italiano ok (multilingual v2.5, 31 lingue +
   auto-detect). ❌ **pipeline → niente percezione prosodia**, nessun numero di latenza ufficiale,
   **solo hosted**.
10. **Lock-in:** medio. LLM sostituibile/BYO (OpenAI-compatibile) → riduce il lock-in sul ragionamento,
    ma **voce + orchestrazione + valutazione sono proprietarie**; nessun on-prem.

**Pricing:** ~**$0,10/min** (poi $0,08/min, burst $0,16/min); **LLM e telefonia fatturati a parte**.
Piani con minuti/concorrenza inclusi (Free 15 min/4 concurrent … Business 12.375 min/40).

---

## 6. Perché ho escluso Azure / Nova Sonic / Deepgram

- **Azure AI Voice Live** — *incapsula* `gpt-realtime` aggiungendo VAD semantico ottimo, 600+ voci,
  it-IT, enterprise (WebSocket + WebRTC; SDK Python/.NET GA, JS/Java preview). Ma **niente
  valutazione né cap di durata integrati** e useresti comunque il motore OpenAI con un lock-in Azure
  in più. **Runner-up enterprise** se in futuro servono compliance/SLA Microsoft.
- **Amazon Nova Sonic** — vero S2S nativo unificato, italiano ok, ma **lo stream si tronca a 8 minuti**
  → per 10-15 min servono reconnection/chaining (peggio di Gemini); niente BYO-LLM; valutazione DIY.
  (Nova 2 Sonic GA dic 2025.)
- **Deepgram Voice Agent** — pipeline come ElevenLabs ma **solo WebSocket**, il **più economico**
  (~$0,075/min), barge-in eccellente; ma italiano sull'Agent API **non confermato ufficialmente** e
  nessuna valutazione integrata.

---

## 7. Architettura consigliata

Si conferma **integralmente** l'impianto di [REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md):

```
Browser (mic/speaker) ──WebRTC audio──► Provider S2S (OpenAI gpt-realtime-2)
       │  ▲                                   │
       │  └── token effimero ── Frappe (control plane): auth, persona, quota
       └── eventi transcript (whitelisted) ──► LMSA Simulation Turn ──► debrief job (riuso)
```

- **Frappe resta control plane** (token effimeri, persona, persistenza, debrief); l'audio non passa
  dal backend.
- **Astrazione `RealtimeProvider`** (ABC + registry, gemella di `ai/utils/llm/`) con adapter
  `openai_realtime` e `gemini_live` + `mock`: è ciò che rende sostituibile il provider nonostante il
  lock-in sul protocollo.
- **Riuso totale** di persona-generation (testuale), `LMSA Simulation Turn`, e pipeline
  `LMSA Simulation Debrief`.

### MVP vs Scalabile

- **MVP → OpenAI Realtime (`gpt-realtime-2`, WebRTC).** Percorso più rapido e a minor rischio: valida
  l'architettura senza modifiche, 60 min di sessione (zero resumption), GA, eventi transcript
  mappabili 1:1 su `_persist_turn`, riuso del debrief. Prototipo browser in **giorni**.
- **Scalabile → stessa astrazione, due provider.** Default OpenAI; **Gemini dietro flag come opzione
  di costo** (5-10× più economico) quando i volumi crescono — la complessità (resumption, WS, Preview)
  resta isolata nell'adapter. A volumi enterprise con compliance: **Azure Voice Live** come terza
  opzione.

### Facilità di implementazione (dal più facile)

1. **ElevenLabs** — MVP *ricco* più rapido (eval + voce + persona-injection pronte), **ma** fuori
   dall'architettura e perde la prosodia.
2. **OpenAI Realtime** — media in assoluto, **la più facile *per questo progetto***.
3. **Gemini Live** — la più impegnativa (resumption, token, churn Preview).

---

## 8. Correzioni da portare in REALTIME_ARCHITECTURE.md

1. **Default `gpt-realtime-2`** (non `gpt-realtime`): 128k context + ragionamento, sessione 60 min.
2. **Gemini:** aggiungere la gestione **session resumption + context compression** (obbligatoria per
   i ~10 min di connessione) e notare che il `system_instruction` è **fisso al connect** → la steering
   di chiusura passa per `send_client_content`, non per la persona.
3. **Chiusura naturale (§5 del doc):** pattern unico e portabile → *timer server-side → a T-N inietta
   direttiva di wrap-up → il modello chiude → `end_voice_session`*. OpenAI: `session.update` /
   `response.create`. Gemini: turno di contenuto + `GoAway`. ElevenLabs ha in più il tool `End call`.
4. **Costi (§11):** Gemini ~5-10× più economico sull'audio → leva di scala, non di MVP.
5. **Maturità (§11):** Gemini è **Preview su AI Studio ma GA su Vertex** (native audio) → per Gemini
   in produzione usare **Vertex** (auth service-account).

---

## 9. Raccomandazione finale (netta)

**OpenAI Realtime (`gpt-realtime-2`, WebRTC) come default, dentro l'astrazione `RealtimeProvider`;
Gemini Live dietro flag per il costo a volume; ElevenLabs non come motore centrale.**

Motivo unico e decisivo, allineato al §1 del doc di architettura: vuoi che l'AI **percepisca** tono,
esitazioni, ritmo e sicurezza del candidato → serve **speech-to-speech nativo** (OpenAI/Gemini).
ElevenLabs — pur con la voce migliore e l'unica valutazione integrata — è **cascaded**: il suo LLM
legge solo la trascrizione e **butta via la prosodia in ingresso**, cioè proprio il segnale per cui
passi al voice. Tra i nativi, OpenAI vince per maturità (GA), sessione 60 min, aderenza al
personaggio e perché **non costringe a riscrivere nulla** dell'impianto esistente.

**Dove ElevenLabs ha senso comunque:** per un *prodotto diverso* (pratica di pronuncia/delivery a
bassa posta) o come **riferimento per estendere il debrief** (i criteri Success Evaluation +
Data Collection sono un buon modello per il giudice "delivery" del §8).

---

## 10. Framework di astrazione (un solo codice per OpenAI Realtime + Gemini Live)

> Domanda ricorrente: esiste un kit/framework che implementi **sia** Gemini Live **sia** OpenAI
> Realtime con un'unica interfaccia, senza scrivere due codici? Sì — i due maturi sono **LiveKit
> Agents** e **Pipecat** (gli stessi partner che Google elenca per la Live API). Ma vanno valutati
> alla luce della scelta "audio fuori da Frappe" del §2/§7.

### 10.1 I candidati

| Framework | Provider S2S unificati | Swap provider | Trasporto | Modello architetturale |
|---|---|---|---|---|
| **LiveKit Agents** | OpenAI Realtime · Gemini Live · Nova Sonic · Azure Realtime · xAI/Ultravox… | **una riga** (`RealtimeModel`; l'`AgentSession` resta identica) | WebRTC (SFU LiveKit) | **worker server-side nel media path** |
| **Pipecat** (Daily) | OpenAI Realtime · Gemini Multimodal Live · (40+ servizi) | scambio del *service* nella pipeline | Daily WebRTC / WebSocket / Twilio | **bot Python nel media path** *oppure* transport client-side (browser→provider diretto) |
| Stream **Vision Agents** | Gemini Live · OpenAI Realtime · Nova Sonic | sì | WebRTC | più recente |

### 10.2 Il trade-off rispetto a questa architettura

Questi framework risolvono il "due codici diversi" **inserendo un servizio dedicato dentro il
percorso audio**: `browser → WebRTC LiveKit/Daily → worker del framework → provider` (chiave lato
server). È esattamente la **"Opzione B — relay server-side"** prevista in
[REALTIME_ARCHITECTURE.md](REALTIME_ARCHITECTURE.md) §9/§13 *come scenario per esami ad alto rischio*,
**non** il modello MVP scelto (browser↔provider diretto, Frappe solo control-plane). Adottarli
significa quindi:

- aggiungere un **servizio di media stateful** accanto a Frappe;
- scambiare il **lock-in sul provider** con un **lock-in sul framework** — l'astrazione non è uno
  standard neutro (gli schemi-eventi restano proprietari, vedi §3-§4).

**Dov'è davvero il "doppio codice"?** Non nel backend: il `RealtimeProvider` ABC del §7 è minuscolo
(conia il token effimero + normalizza l'evento transcript). È nel **client browser**: OpenAI = WebRTC
+ data channel `oai-events`; Gemini = WebSocket + `BidiGenerateContent`. Nessun SDK browser parla
nativamente entrambi.

### 10.3 Tre strade (in ordine di aderenza al design attuale)

1. **`RealtimeProvider` ABC + Pipecat *client-side transports*** — *sembrava la via di mezzo ideale
   (un solo frontend, browser→provider diretto, Frappe control-plane), ma in produzione **non
   regge**.* I transport `OpenAIRealTimeWebRTCTransport` e `GeminiLiveWebSocketTransport`
   **non implementano il processo di token effimero**: richiedono la **chiave API lato client** e la
   doc Pipecat li dichiara "per dev/testing, insicuri in produzione", rimandando a un componente
   server (`DailyTransport`). Con i token effimeri obbligatori (§9 del doc di architettura) questa
   strada serve **solo per prototipi**, non per la produzione.
2. **Nessun framework** — *la scelta consigliata (vedi §10.5).* Backend: `RealtimeProvider` ABC con
   adapter per-provider (conia token effimero + normalizza transcript). Frontend: un
   `useRealtimeSession.js` con i transport browser, adattati dai reference ufficiali OpenAI/Google
   (entrambi con token effimeri). Zero servizi nuovi, zero lock-in aggiuntivo.
3. **Framework completo (LiveKit Agents)** — quando servono "batterie incluse" (turn-taking,
   interruzione, trascrizione, registrazione, function-calling, telefonia), swap a una riga **e** va
   bene un media server dedicato. È il più solido in produzione e regala anche Nova Sonic e Azure;
   è anche l'evoluzione naturale verso la "Opzione B" (transcript autoritativi server-side per esami).

### 10.4 Sintesi

- **Sì**, un unico strumento per OpenAI Realtime + Gemini Live esiste: **LiveKit Agents** o **Pipecat**.
- L'unica versione adottabile in **produzione** è **server-side** (media server) → fuori dal modello
  "audio fuori da Frappe" e con lock-in di framework.
- I **client-side transport di Pipecat** **non** implementano i token effimeri (solo dev/test) → non
  sono una via di produzione che preservi l'architettura.
- Per restare nell'architettura attuale, il `RealtimeProvider` ABC è già "l'unico strumento", ed è di
  proprietà. Per lo scenario **due provider** vedi §10.5.

### 10.5 Raccomandazione con DUE provider obbligatori (OpenAI + Gemini)

Con entrambi i provider come requisito fisso, il punto debole del "nessuno strumento" — mantenere
*due* client browser, di cui Gemini WebSocket contro un'API **Preview** che cambia spesso — diventa un
costo **certo**, e questo sposterebbe peso verso un framework. Ma due fatti chiudono la questione:

1. **La via di mezzo "Pipecat client-side" è esclusa in produzione** (§10.3.1): i suoi transport non
   implementano i token effimeri. L'unica opzione "framework" praticabile resta quindi quella
   **server-side** (LiveKit / Pipecat-server) — cioè un **media server** che **frammenta la logica di
   simulazione** (priorità #1) tra Frappe e il worker, e aggiunge un servizio da operare.
2. **Il costo del no-framework è già dimezzato da reference ufficiali con token effimeri:**
   - OpenAI → `openai/openai-realtime-agents` (WebRTC + ephemeral key);
   - Gemini → `google-gemini/gemini-live-api-examples/gemini-live-ephemeral-tokens-websocket`
     (WebSocket + token effimero — esattamente il pezzo che Pipecat-client *non* fa).
   - Backend: `ai/utils/llm/` ha **già** adapter OpenAI + Gemini + Anthropic → stesso pattern.

**Decisione: nessuno strumento, anche con due provider.** Il framework comprerebbe un beneficio
*secondario* (manutenzione del layer transport) al prezzo di un danno *primario* (customizzazione di
dominio + architettura + un servizio in più da gestire). Cattivo scambio per questo progetto.

| | **Nessuno strumento** | **LiveKit / Pipecat-server** |
|---|---|---|
| Token effimeri (prod) | ✅ coniati in Frappe | ✅ server-side nel worker |
| Swap / gestione 2 provider | 2 transport browser (da reference ufficiali) | una riga (`RealtimeModel`) |
| Churn Gemini (Preview) | lo assorbi tu (frontend isolato) | lo assorbe il framework |
| Personalizz. simulazioni (logica in Frappe) | ★★★★★ unificata | ★★★ frammentata |
| Infra da operare | **nessuna** | media server + bridge |
| Lock-in aggiunto | nessuno | framework (+ Cloud) |

**Piano:**
- Backend: `RealtimeProvider` ABC + adapter `openai_realtime` / `gemini_live` (specchio di `utils/llm/`).
- Frontend: un solo `useRealtimeSession.js` con due transport interni (OpenAI WebRTC / Gemini
  WebSocket), adattati dai due reference ufficiali sopra. UI e logica di sessione condivise; cambia
  solo il transport.
- Isolare il churn: default OpenAI (GA, 60 min); Gemini dietro flag puntando al **native-audio su
  Vertex (GA)**, non alla superficie Preview di AI Studio.

**Quando passare a LiveKit:** se la voce diventa un prodotto a sé (telefonia, registrazione audio,
multi-agente, esami ad alto rischio con transcript autoritativi server-side) **oppure** se la
manutenzione dei due transport si rivela troppo onerosa. Grazie all'astrazione `RealtimeProvider` +
dominio in Frappe, la migrazione resta **contenuta** (sostituisci il layer transport, tieni doctype e
debrief).

---

## Appendice — Fonti ufficiali

**OpenAI Realtime**
- Guida Realtime · Conversations/eventi: https://developers.openai.com/api/docs/guides/realtime · .../guides/realtime-conversations
- WebRTC · WebSocket · SIP · VAD: .../guides/realtime-webrtc · .../realtime-websocket · .../realtime-sip · .../realtime-vad
- Transcription · Costi · Prompting: .../guides/realtime-transcription · .../realtime-costs · .../realtime-models-prompting
- Modelli · Changelog · Pricing: .../models/gpt-realtime · .../gpt-realtime-2 · .../changelog · .../pricing
- Blog: GA https://openai.com/index/introducing-gpt-realtime/ · limite 60 min https://developers.openai.com/blog/realtime-api · latenza GPT-4o https://openai.com/index/hello-gpt-4o/
- Esempi: https://github.com/openai/openai-realtime-agents · https://github.com/openai/openai-agents-python

**Gemini Live**
- Overview · Capabilities · Session management: https://ai.google.dev/gemini-api/docs/live-api · .../live-api/capabilities · .../live-api/session-management
- Tools · Ephemeral tokens · WebSockets ref: .../live-api/tools · .../live-api/ephemeral-tokens · https://ai.google.dev/api/live
- Get started (SDK/WS) · Modelli · Deprecations · Pricing · Voci: .../live-api/get-started-sdk · .../models · .../deprecations · .../pricing · .../speech-generation
- Vertex AI Live API · quote: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api · .../docs/quotas
- Partner/WebRTC: https://ai.google.dev/gemini-api/docs/partner-integration

**ElevenLabs Conversational AI (ElevenAgents)**
- Overview · Quickstart · LLM/Custom LLM: https://elevenlabs.io/docs/eleven-agents/overview · .../quickstart · .../customization/llm · .../customization/llm/custom-llm
- WebRTC · WebSocket: https://elevenlabs.io/blog/conversational-ai-webrtc · https://elevenlabs.io/docs/agents-platform/api-reference/agents-platform/websocket
- Dynamic variables · Overrides · End-call: .../personalization/dynamic-variables · .../personalization/overrides · .../tools/system-tools/end-call
- Post-call webhooks · Success Evaluation · Data Collection: .../workflows/post-call-webhooks · .../agent-analysis/success-evaluation · .../agent-analysis/data-collection
- Pricing: https://elevenlabs.io/pricing/agents

**Altri (scansione)**
- Azure AI Voice Live: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live
- Amazon Nova Sonic: https://docs.aws.amazon.com/nova/latest/userguide/speech-bidirection.html
- Deepgram Voice Agent: https://developers.deepgram.com/docs/voice-agent

**Framework di astrazione (single-codebase multi-provider) — §10**
- LiveKit Agents — Realtime models: https://docs.livekit.io/agents/models/realtime/ · Gemini plugin: https://docs.livekit.io/agents/models/realtime/plugins/gemini/ · repo: https://github.com/livekit/agents
- Pipecat: https://github.com/pipecat-ai/pipecat · Building with Gemini Live: https://docs.pipecat.ai/guides/features/gemini-multimodal-live · client web transports: https://github.com/pipecat-ai/pipecat-client-web-transports
- Pipecat client transports — limite token effimeri (dev/test): https://docs.pipecat.ai/api-reference/client/js/transports/openai-webrtc · https://github.com/pipecat-ai/pipecat-client-web-transports/blob/main/transports/gemini-live-websocket-transport/README.md
- Reference client ufficiali con token effimeri: https://github.com/openai/openai-realtime-agents · https://github.com/google-gemini/gemini-live-api-examples/tree/main/gemini-live-ephemeral-tokens-websocket
- Stream Vision Agents (S2S: Gemini Live · OpenAI Realtime · Nova Sonic): https://getstream.io/blog/voice-agents-mcp-platforms/

> **Note di verificabilità:** OpenAI non pubblica una latenza end-to-end ufficiale (solo il floor del
> modello GPT-4o ~232/320 ms) né un timer/registrazione nativi. Gemini Live è Preview su AI Studio
> (GA su Vertex); il limite "audio-only 15 min / connessione ~10 min" impone session resumption; il
> numero di voci/lingue varia tra pagine ufficiali (70 vs 97). ElevenLabs non pubblica numeri di
> latenza né un cap di durata nativo. I costi per-sessione sono stime d'ordine di grandezza.
