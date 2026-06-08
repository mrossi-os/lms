# AI Tutor

Il modulo `tutor` espone un assistente conversazionale che risponde alle domande dello studente su un corso (e opzionalmente su una lezione specifica) usando il contenuto già indicizzato dalla pipeline di ingestion come contesto.

Sorgente: `apps/os_lms/os_lms/os_lms/ai/tutor/`.

```
apps/os_lms/os_lms/os_lms/ai/tutor/
├── __init__.py
├── api.py        # endpoint whitelisted `ask`
└── tutor_ai.py   # classe TutorAi
```

## Architettura

```
            ┌─────────────────────────────────────────────┐
   POST ───►│ tutor.api.ask(course, lesson, question,     │
   /api     │              history)                       │
            └────────────────────┬────────────────────────┘
                                 │
                                 ▼
            ┌─────────────────────────────────────────────┐
            │ TutorAi(course, lesson, user)               │
            │ (tutor_ai.py)                               │
            │                                             │
            │  - ask(question, history) -> str            │
            │      ├─ _build_messages(history + question) │
            │      ├─ _system_prompt(question)            │
            │      │     ├─ permission gate               │
            │      │     ├─ IngestionService.search_*     │
            │      │     ├─ _label_chunks                 │
            │      │     └─ template replace su           │
            │      │       LMSA Settings.system_prompt    │
            │      ├─ resolve_provider("chat").chat(...)  │
            │      └─ _log_query → LMSA Query Log         │
            └─────────┬──────────────────────┬────────────┘
                      │                      │
                      ▼                      ▼
            ┌──────────────────┐   ┌──────────────────────┐
            │ IngestionService │   │ LLMProvider          │
            │ (RAG retrieval)  │   │ (resolve_provider)   │
            └──────────────────┘   └──────────────────────┘
```

**Pattern**: stateless per request — `TutorAi` viene istanziato dall'endpoint, costruisce contesto + prompt, fa una sola call LLM, restituisce il testo. Niente sessione persistita lato server: la cronologia è interamente owned dal client e rinviata ad ogni domanda.

## Flusso `TutorAi.ask`

1. Validazione: `question` non vuota (`frappe.throw` altrimenti), trim.
2. `_build_messages(question, history)` → costruisce la lista di `ChatMessage` con i turni precedenti più la nuova domanda.
3. Dentro un `try` (in modo che il logging in `finally` vada sempre a buon fine):
   - `system_prompt, context = self._system_prompt(question)` → costruisce il prompt e ritorna anche il blob di contesto (chunks etichettati joinati) usato per l'audit.
   - `resolve_provider("chat")` → factory provider-agnostica che legge `LMSA Settings.simulation_chat_provider` (con fallback default) e restituisce un `LLMProvider`. Stesso meccanismo usato dal SessionOrchestrator delle simulations.
   - `provider.chat(messages=..., system=system_prompt)` → singola call LLM. Il system prompt viene ricalcolato per ogni richiesta perché il RAG retrieval dipende dalla `question`.
   - `answer = response.text`, `status = "Answered"`.
4. `finally`: `_log_query(question, answer, context, status)` scrive un record su `LMSA Query Log` (best-effort, vedi sotto). Se l'LLM fallisce, `answer` resta stringa vuota e `status = "Failed"` — il record viene scritto comunque.
5. Ritorna `response.text` (o propaga l'eccezione se il `try` ha sollevato).

## Costruzione del system prompt

`_system_prompt(question)` (`tutor_ai.py:74-105`) è la parte più interessante: combina il template configurato in `LMSA Settings.system_prompt` con i chunk recuperati dal RAG, e ritorna `(prompt, lessons_content)` — il secondo elemento viene riusato come `context` per l'audit log.

### 1. Permission gate sul retrieval

```python
if is_instructor(self.course) or has_moderator_role(self.user):
    chunks = service.search_chunks_by_course(self.course, question)
else:
    completed = set(
        frappe.get_all(
            "LMS Course Progress",
            filters={"course": course, "member": self.user, "status": "Complete"},
            pluck="lesson",
        )
    )
    chunks = service.search_chunks_by_lessons(self.course, list(completed), question)
```

- **Istruttori del corso + moderator**: vector search su tutte le lezioni del corso.
- **Studenti**: vector search ristretto alle lezioni con `LMS Course Progress.status == "Complete"` per quel `member`. Anti-spoiler: una lezione non ancora completata non finisce mai nel contesto del tutor.
- Caso limite: se lo studente non ha completato nessuna lezione, `search_chunks_by_lessons` riceve `lessons=[]` e ritorna `[]` (vedi `utils/rag_db.py`) → il system prompt avrà `{{LESSONS_CONTENT}}` vuoto e il tutor risponderà solo in base al template + course title/description.

### 2. Etichettatura dei chunk

`_label_chunks` (`tutor_ai.py:141-158`) prefissa ogni chunk con il titolo della lezione sorgente:

```
[Lezione: "Introduzione alle obiezioni"]
<contenuto del chunk>
```

Il titolo viene risolto da una `frappe.get_all` su `Course Lesson` (un solo query batch per tutto il corso). Senza titolo, il chunk viene incluso così com'è. Lo scopo è permettere al modello di citare e cross-referenziare tra lezioni nella risposta.

### 3. Template replace

`LMSA Settings.system_prompt` è una stringa con 4 placeholder che vengono sostituiti:

| Placeholder | Valore |
|---|---|
| `{{COURSE_TITLE}}` | `course.title` da `get_course_details(course)` |
| `{{COURSE_DESCRIPTION}}` | Output di `_course_description(course)` — `course.description` + eventuale blocco delle feature sections (vedi sotto) |
| `{{LESSONS_CONTENT}}` | Tutti i chunk recuperati (post-`_label_chunks`), joinati con `\n\n---\n\n` |
| `{{CURRENT_LESSON_CONTENT}}` | Solo i chunk con `chunk.lesson == self.lesson` (la lezione corrente), joinati. Vuoto se `lesson is None` o se nessun chunk ricade nella lezione attiva |

Una mancata sostituzione (placeholder non presente nel template) è silenziosa: il prompt risultante sarà semplicemente privo di quel blocco. Una sostituzione vuota (es. lezione corrente senza chunk) inserisce stringa vuota.

### 4. `_course_description` + feature sections

`_course_description(course)` (`tutor_ai.py:128-139`) compone la descrizione estesa del corso:

```python
def _course_description(self, course):
    description = course.get("description") or ""

    feature_sections = course.get("feature_sections") or []
    if len(feature_sections) > 0:
        description += "\n COURSE FEATURES:\n"
        for feature in feature_sections:
            title = feature.get("title", "")
            feature_description = feature.get("description", "")
            description += f"\n{title}\n{feature_description}"

    return description
```

Le feature sections vengono lette dal campo `LMS Course.feature_sections` (JSON) tramite il loader `_load_feature_sections` (`tutor_ai.py:41-46`) e attaccate alla `course_details` cached property al primo accesso (`tutor_ai.py:37`). Il formato JSON atteso è una lista di oggetti con almeno `title` e `description`. Errori di parsing → lista vuota, mai throw.

`_system_prompt` consuma la property cached (`course = self.course_details`), quindi `feature_sections` è disponibile e il blocco `COURSE FEATURES` viene effettivamente popolato quando presente.

## Audit log (`LMSA Query Log`)

Ogni `ask` produce un record di audit via `_log_query`:

| Field | Valore | Required |
|---|---|---|
| `course` | `self.course` (Link a `LMS Course`) | sì |
| `lesson` | `self.lesson or ""` (Link a `Course Lesson`, opzionale) | no |
| `member` | `self.user` (Link a `User`) | sì |
| `question` | testo trim della domanda | sì |
| `answer` | risposta dell'LLM, stringa vuota se la call è fallita | no |
| `context` | i chunk recuperati + etichettati (joinati con `\n\n---\n\n`) — stesso blob inserito nel placeholder `{{LESSONS_CONTENT}}` | no |
| `status` | `"Answered"` se la chat LLM è andata a buon fine, `"Failed"` altrimenti (default schema `"Pending"`) | no |

Convenzioni:

- **Best-effort**: la scrittura su `LMSA Query Log` è dentro un try/except e in caso di errore chiama `frappe.log_error` senza propagare. Il client riceve sempre la risposta del tutor anche se il log fallisce.
- **`finally` block**: il log viene scritto sia su success che su failure dell'LLM call. Una risposta fallita ha `answer = ""` e `status = "Failed"`. Utile per misurare il rate di failure dei provider.
- **Domande a livello corso**: `lesson` è opzionale nel doctype. Quando `self.lesson is None` la riga viene scritta comunque con `lesson = ""` — niente skip dell'audit.
- **Save con `ignore_permissions=True`**: lo studente non ha by-default `create` su `LMSA Query Log` solo quando manca un ruolo applicativo (la policy permission include `System Manager`, `LMS Student`, `Moderator`, `Course Creator` con `create`). Il flag è una safety net per future restrizioni.

## Cronologia conversazionale

`_build_messages(question, history)` (`tutor_ai.py:160-169`):

```python
messages = [
    ChatMessage(
        role="user" if turn.get("from") == "user" else "assistant",
        content=turn.get("message", ""),
    )
    for turn in history
]
messages.append(ChatMessage(role="user", content=question))
return messages
```

Convenzioni:
- Il client invia `history` come lista di `{"from": "user" | "assistant" (o altro), "message": str}`. Il check `turn.get("from") == "user"` significa che qualsiasi valore diverso da `"user"` viene mappato ad `assistant` — tolerante ma facile da confondere con sistemi che usano `"bot"`, `"ai"`, etc. Il client deve mandare `"user"` esattamente per i messaggi dell'utente.
- Niente troncamento o riassunto: tutta la `history` ricevuta finisce nel prompt. È responsabilità del client (frontend) limitarne la dimensione per evitare context overflow.
- Niente persistenza lato server: la conversazione vive solo nel client. Se la UI viene ricaricata, la cronologia è persa a meno che il client non la salvi separatamente.

## API HTTP

`tutor/api.py` espone un singolo endpoint whitelisted:

### `ask(course, lesson=None, question, history=None)` — POST

```python
@frappe.whitelist()
def ask(course, lesson, question, history=None) -> dict:
    if isinstance(history, str):
        history = json.loads(history)
    tutor = TutorAi(course=course, lesson=lesson or None, user=frappe.session.user)
    answer = tutor.ask(question, history or [])
    return {"answer": answer}
```

- `history` viene parsata da JSON se arriva come stringa (caso form-encoded di Frappe). Quando passa come array nativo è usata direttamente.
- `lesson` è opzionale: `lesson or None` normalizza la stringa vuota a `None`, così a valle `current_lesson_content` resta vuoto e l'audit log viene scritto senza lesson valorizzata.
- `user` viene letto da `frappe.session.user` — l'endpoint richiede sessione autenticata (built-in di `@frappe.whitelist()`).
- Errori (course non trovato, question vuota, LLM provider fail) risalgono come eccezioni Frappe e diventano risposte di errore al client.

## Configurazione

Da `LMSA Settings`:

| Campo | Uso |
|---|---|
| `system_prompt` | Template del system prompt con placeholder `{{COURSE_TITLE}}`, `{{COURSE_DESCRIPTION}}`, `{{LESSONS_CONTENT}}`, `{{CURRENT_LESSON_CONTENT}}` |
| `simulation_chat_provider` (e correlati) | Letti da `resolve_provider("chat")` per scegliere il provider LLM. Se `"auto"`, usa `simulation_provider_default` con fallback chain. Stessa meccanica documentata in `docs/superpowers/plans/...` per le simulations |
| `simulation_chat_model` | Modello concreto per il chat (es. `gpt-4o-mini`). Se vuoto, il provider usa il default del suo config |
| `openai_key` / `gemini_key` / `deepseek_key` / `anthropic_key` | API key per il provider selezionato |
| `enabled` | **NON gattato dal tutor**: l'endpoint risponde anche se `enabled = False`. Il gate `LMSA enabled` vive sul lato ingestion. Conseguenza: il tutor può girare con un indice vuoto e ritornare risposte basate solo sul template + course title/description |

Da `site_config.json`: ereditata l'infrastruttura provider/LLM (vedi `docs/superpowers/plans/...` per le simulations) — il tutor non legge `site_config` direttamente.

## Note operative

- **Costo per richiesta**: ogni `ask` esegue (1) un'embedding-call per la query del vector search dentro `IngestionService.search_*`, (2) la query Redis, (3) una chat-completion LLM. La parte costosa è l'LLM call; embedding e Redis sono trascurabili. Niente caching sulla domanda — domande identiche di studenti diversi rifanno tutto il flusso.
- **`course_details` è lazy + load-bearing**: la `@property` carica `get_course_details` UNA volta per richiesta e attacca `feature_sections` parsate da `LMS Course.feature_sections`. `_system_prompt` usa `self.course_details` (no doppia fetch). Throw via property se il corso non esiste o non è accessibile.
- **Audit log completo**: `ask` scrive su `LMSA Query Log` (vedi sezione dedicata sopra) per ogni richiesta, anche per le domande a livello corso senza lezione specifica.
- **History tolerant ma fragile**: la convenzione `from == "user"` significa che `"bot"`, `"assistant"`, `"ai"`, `null` finiscono tutti come ruolo `assistant`. Documentare bene il contract con il frontend per evitare confusione.
- **No tool/function calling**: il provider viene chiamato solo con `messages` e `system`. Non è previsto chain-of-thought esterno, function calls, o multi-turn reasoning lato server.
- **Schema migration richiesta**: il bump di `LMSA Query Log` (lesson resa opzionale) richiede `bench --site <site> migrate` sul deploy esistente. Senza migrate, i nuovi insert con `lesson = ""` saranno respinti dal vincolo required precedente.

## File rilevanti (cheat sheet)

| Layer | File |
|---|---|
| HTTP endpoint | `apps/os_lms/os_lms/os_lms/ai/tutor/api.py` |
| Tutor class | `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py` |
| RAG retrieval | `apps/os_lms/os_lms/os_lms/ai/ingestion/service.py` (`IngestionService.search_chunks_by_course`, `search_chunks_by_lessons`) — vedi [INGESTION.md](INGESTION.md) |
| Provider abstraction | `apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py` (`resolve_provider`, `ChatMessage`) |
| Settings dataclass | `apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py` |
| Course details | `lms.lms.utils.get_course_details` (base LMS app) |
| Permission helpers | `lms.lms.utils.is_instructor`, `has_moderator_role` |
