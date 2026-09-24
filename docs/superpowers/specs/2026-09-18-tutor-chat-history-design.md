# Storico delle chat del Tutor AI — specifica di progetto

**Data:** 18 settembre 2026 · **Branch:** `feature/oslms` · **Stato:** design approvato, implementazione non iniziata
**Documento precedente:** [docs/ai/STORICO-CHAT-FATTIBILITA.md](../../ai/STORICO-CHAT-FATTIBILITA.md) (analisi di fattibilità, opzioni A/B/C)

---

## 1. Obiettivo

Rendere permanenti e consultabili le conversazioni fra studente e tutor AI, organizzate
per corso secondo il modello "progetti" di NotebookLM: il corso è il progetto, dentro ci
sono tutte e sole le conversazioni del tutor relative a quel corso.

Oggi la conversazione vive solo nella memoria del browser
([stores/aiChat.js](../../../frontend/src/stores/aiChat.js)) e si perde a ogni
ricaricamento della pagina. Gli scambi sono già scritti a database su `LMSA Query Log`
come audit, ma senza raggruppamento in conversazioni e senza alcun accesso per lo
studente.

Perimetro approvato: **opzione B** del documento di fattibilità, con la lettura del
Gestore nella **Forma 1** (stessa pagina del progetto, con selettore studente).

## 2. Decisioni prese

Decise dal committente il 18/09/2026, in risposta alle domande del documento di fattibilità.

| # | Decisione | Conseguenza tecnica |
| --- | --- | --- |
| D1 | **Visibilità: solo lo studente proprietario e il ruolo `Gestore`.** Esclusi Moderator, Course Creator, Docente, Valutatore | Il gate non può poggiare sui ruoli usati dalle simulazioni: i Gestori possiedono anche Moderator, quindi l'ordine dei controlli è load-bearing (§6) |
| D2 | **Nessuna cancellazione da parte dello studente, solo archiviazione** | Campo `archived`, nessuna logica di soft-delete, nessun conflitto con l'audit |
| D3 | **Conservazione illimitata** | Nessun parametro di retention, nessuna attività pianificata di pulizia |
| D4 | **Nessun recupero dello storico esistente** | Deciso dopo misurazione sui dati reali (§3): i log esistenti sono interamente di account interni |
| D5 | **Il Gestore non ha accesso al Desk di Frappe** | La lettura per il Gestore deve vivere nella SPA: due dei tre Gestori sono `Website User` e non possono entrare in `/app` |
| D6 | **Forma 1** per la lettura del Gestore: stessa pagina del progetto, con selettore studente | Un solo componente, una sola rotta, un solo endpoint con parametro `member` |

## 3. Dati misurati in produzione (18/09/2026, sola lettura)

```
LMSA Query Log   100 righe · 9 utenti · 11 corsi · 15/04/2026 → 14/09/2026
Esito            85 Answered · 15 Failed          (tasso di errore 15%)
Dimensioni       domanda 31 car. · risposta 591 car. · contesto 6.266 car. (max 17.048)
Piattaforma      113 iscrizioni · 20 studenti · 18 corsi (4 pubblicati)
Utenze           7 System User · 53 Website User
Gestori          3, di cui 1 solo System User
```

Tutti e nove gli utenti che hanno usato il tutor sono **account interni** (`Administrator`,
`*@overside.it`, varianti `+docente` / `+gestore` / `+studente`, due Gmail di prova).
Nessuno studente reale ha mai posto una domanda. Da qui D4.

Tre numeri che vincolano il design:

- **15% di risposte fallite** → il turno fallito è uno stato da rappresentare, non un caso
  limite da ignorare: diventerà visibile allo studente in modo permanente.
- **6,3 KB di contesto medio per riga** → il campo `context` di `LMSA Query Log` non va mai
  letto per costruire la vista dell'archivio.
- **1 Gestore su 3 è System User** → D5.

## 4. Fuori perimetro

Esplicitamente non inclusi in questo intervento:

- Citazioni cliccabili alle lezioni di origine e pannello "fonti del corso" (opzione C).
- Ricerca testuale dentro lo storico, conversazioni preferite, esportazione in PDF.
- Pagina di archivio globale trasversale ai corsi (`/tutor-archive`, Forma 2): resta
  aggiungibile in seguito riusando gli stessi endpoint e lo stesso componente.
- Unificazione con le sessioni di simulazione e le sessioni vocali dentro la stessa pagina.
- Statistiche d'uso del tutor (quante domande per corso, temi ricorrenti).
- Recupero dei log storici (D4).

## 5. Modello dati

Due doctype nuovi nel modulo `OS LMS`. **`LMSA Query Log` resta invariato nel ruolo di
audit** (unica modifica: i permessi, §6.3).

### 5.1 `LMSA Tutor Conversation`

`autoname: format:TCV-{#####}` · `sort_field: last_message_at` · `sort_order: DESC` · `track_changes: 1`

| Campo | Tipo | Obbl. | Note |
| --- | --- | --- | --- |
| `course` | Link `LMS Course` | sì | il "progetto". `search_index: 1` |
| `member` | Link `User` | sì | valorizzato in `before_insert` da `frappe.session.user`. `search_index: 1` |
| `title` | Data (140) | no | generato dalla prima domanda (§7.4), rinominabile dallo studente |
| `started_at` | Datetime | no | valorizzato in `before_insert` |
| `last_message_at` | Datetime | no | aggiornato a ogni turno; è il campo di ordinamento |
| `message_count` | Int | no | contatore denormalizzato: evita un `COUNT` per riga di elenco |
| `archived` | Check | no | default 0. Unica forma di rimozione concessa allo studente (D2) |
| `last_lesson` | Link `Course Lesson` | no | lezione da cui è arrivata l'ultima domanda; serve all'etichetta di contesto |

Controller: `before_insert` valorizza `member` e `started_at` sul modello di
[lmsa_simulation_session.py](../../../apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.py).

### 5.2 `LMSA Tutor Message`

`autoname: format:TMS-{######}` · `sort_field: turn_index` · `sort_order: ASC` · `track_changes: 0`

| Campo | Tipo | Obbl. | Note |
| --- | --- | --- | --- |
| `conversation` | Link `LMSA Tutor Conversation` | sì | `search_index: 1` |
| `turn_index` | Int | sì | ordinamento esplicito, mai per data di creazione |
| `role` | Select `user` / `assistant` | sì | |
| `content` | Long Text | no | vuoto ammesso solo con `status = Failed` |
| `lesson` | Link `Course Lesson` | no | contesto della singola domanda |
| `status` | Select `Answered` / `Failed` | no | default `Answered`. Necessario: 15% dei turni fallisce |
| `model_used` | Data | no | audit leggero, come nei turni di simulazione |
| `provider_used` | Data | no | |
| `query_log` | Link `LMSA Query Log` | no | ponte verso l'audit completo, per il supporto |

Messaggio separato e non tabella figlia: mantiene la possibilità di interrogare i messaggi
trasversalmente (ricerca, statistiche) senza caricare l'intera conversazione, coerente con
`LMSA Simulation Turn`.

### 5.3 Alternativa scartata

Estendere `LMSA Query Log` con `conversation` + `turn_index` invece di creare i due
doctype costerebbe **12-16 ore in meno**. Scartata perché: una riga di log accoppia
domanda e risposta, quindi i 15% di turni falliti diventerebbero bolle vuote da filtrare a
ogni lettura; il campo `context` da 6,3 KB verrebbe trascinato in ogni query non
esplicitamente proiettata; e i permessi del log dovrebbero cambiare per servire la policy
dell'archivio, cambiando **anche** chi vede l'audit. Resta una variante praticabile se il
preventivo diventa il vincolo dominante.

## 6. Permessi

### 6.1 Regola

```
ROLES_WITH_FULL_ACCESS = {"System Manager", "Gestore"}   # Moderator escluso di proposito (D1)
```

| Attore | Elenco | Documento |
| --- | --- | --- |
| `Administrator` | tutto | tutto |
| `System Manager`, `Gestore` | tutto | **sola lettura** (`read`, `report`, `print`, `export`, `email`, `share`) |
| Proprietario (studente) | `member = <utente>` | lettura e scrittura sulle proprie |
| Chiunque altro (Moderator, Course Creator, Docente, Valutatore, Guest) | `1=0` | `False` |

**L'ordine dei controlli è load-bearing.** Un Gestore possiede anche Moderator: il ramo
`Gestore` deve precedere qualunque ramo di esclusione, e non deve esistere alcun ramo
`Moderator` o `Course Creator` (a differenza di
`lmsa_simulation_session.get_permission_query_conditions`, che ne ha uno per gli
istruttori del corso). Il caso "Moderator puro riceve diniego" è coperto da test (§10).

### 6.2 Implementazione

- `LMSA Tutor Conversation`: `get_permission_query_conditions(user)` e
  `has_permission(doc, ptype, user)`, registrate in
  [hooks.py](../../../apps/os_lms/os_lms/hooks.py) accanto a quelle delle simulazioni.
- `LMSA Tutor Message`: entrambe **delegano al padre** con la stessa sottoquery già usata
  da `lmsa_simulation_turn` (`conversation IN (SELECT name FROM ... WHERE <cond padre>)`).
- Ogni ramo consentito restituisce `True` **esplicito**: in Frappe un `has_permission` che
  restituisce `None` vale diniego.
- Le stringhe di filtro usano `frappe.db.escape(value, percent=False)`, che già applica le
  virgolette.

### 6.3 Correzione necessaria su `LMSA Query Log`

`LMSA Query Log` concede oggi `read` e `create` al ruolo `LMS Student` senza `if_owner` e
senza `permission_query_conditions` registrata: **qualunque studente può leggere via API
REST le domande e le risposte di tutti gli altri**. È una condizione preesistente, ma
contraddice frontalmente D1 e renderebbe aggirabile l'archivio appena costruito.

Correzione: **rimuovere il blocco di permessi `LMS Student`** dal JSON del doctype. Il
permesso è inutile perché `TutorAi._log_query` scrive con `ignore_permissions=True`.
Verificare con un test che la scrittura continui a funzionare per un utente senza alcun
permesso sul doctype.

## 7. Backend

### 7.1 Posizione del codice

```
apps/os_lms/os_lms/os_lms/ai/tutor/
├── api.py          # endpoint esistenti: ask, ask_audio (modificati)
├── history.py      # NUOVO: endpoint dell'archivio
├── tutor_ai.py     # modificato: persistenza dei turni
└── tests/
    ├── test_api.py         # esistente
    ├── test_history.py     # NUOVO: endpoint ed elenco
    └── test_permissions.py # NUOVO: matrice dei permessi
```

### 7.2 Persistenza dei turni

`TutorAi.__init__` accetta `conversation: str | None`. In `ask`:

1. Se `conversation` è assente, crearla (titolo da §7.4, `course`, `member`, `last_lesson`).
2. Scrivere il messaggio `user` con `turn_index` progressivo.
3. Dopo la risposta, scrivere il messaggio `assistant` con `status` coerente con l'esito
   (`Answered` / `Failed`), `model_used`, `provider_used` e il collegamento al record di
   `LMSA Query Log` appena creato.
4. Aggiornare `message_count` e `last_message_at`.

La scrittura avviene nello stesso punto dove oggi vive `_log_query`, cioè nel blocco
`finally`: **anche un turno fallito viene archiviato**, coerentemente con l'audit. La
scrittura dell'archivio, a differenza dell'audit, **non** è best-effort silenziosa: se
fallisce, l'errore viene registrato ma la risposta all'utente passa comunque.

Poiché `ask_audio` chiama lo stesso metodo attraverso `run_audio_turn`, il percorso audio
è coperto senza modifiche aggiuntive.

### 7.3 La cronologia passa lato server

Oggi il client rimanda l'intera conversazione a ogni domanda e `_build_messages` non la
tronca ([tutor_ai.py](../../../apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py)). Con le
conversazioni persistite il server la ricostruisce da sé:

- se arriva `conversation`, il server carica gli ultimi `HISTORY_WINDOW_TURNS` messaggi
  (costante di modulo, valore iniziale **12**, cioè 6 scambi) e **ignora** il parametro
  `history`;
- se `conversation` è assente, comportamento attuale invariato (compatibilità).

Chiude il rischio di costo crescente per domanda e toglie al frontend una responsabilità
che non dovrebbe avere. I messaggi con `status = Failed` sono esclusi dalla finestra.

### 7.4 Titolo automatico

Prima domanda della conversazione, normalizzata (collasso degli spazi) e troncata a 140
caratteri con ellissi. Nessuna chiamata LLM: sulla base misurata la domanda media è di 31
caratteri, quindi il titolo è quasi sempre la domanda intera. Lo studente può rinominare.

### 7.5 Endpoint

Tutti con `@frappe.whitelist()` e annotazioni di tipo (`require_type_annotated_api_methods`).

| Firma | Chi | Comportamento |
| --- | --- | --- |
| `list_conversations(course: str, member: str \| None = None, include_archived: bool = False) -> list[dict]` | studente, Gestore | Senza `member`, le proprie. Con `member`, quelle dello studente indicato: consentito solo se `can_view_tutor_archive()`, altrimenti `frappe.throw(PermissionError)` |
| `get_conversation(name: str) -> dict` | studente, Gestore | Intestazione + messaggi ordinati per `turn_index`. Permessi applicati dal doctype |
| `rename_conversation(name: str, title: str) -> dict` | solo proprietario | Titolo troncato a 140 caratteri |
| `archive_conversation(name: str, archived: bool = True) -> dict` | solo proprietario | D2 |
| `list_course_students(course: str) -> list[dict]` | solo Gestore | Alimenta il selettore studente. Gated da `can_view_tutor_archive()` |

`ask` e `ask_audio` guadagnano il parametro `conversation: str | None = None` e
restituiscono `conversation` nel payload, così il client conosce l'identificativo dopo il
primo messaggio.

### 7.6 Gate del Gestore

Helper unico in [api.py](../../../apps/os_lms/os_lms/os_lms/api.py), sul modello letterale
di `can_export_student_stats()`:

```python
TUTOR_ARCHIVE_ROLES = ("System Manager", "Gestore")

def can_view_tutor_archive() -> bool:
    roles = frappe.get_roles()
    return any(role in roles for role in TUTOR_ARCHIVE_ROLES)
```

Esposto alla SPA da `override_api.get_user_info` come `can_view_tutor_archive`, accanto a
`can_export_stats`. **Unica fonte di verità**: gli endpoint e l'interfaccia leggono lo
stesso helper, quindi non possono divergere.

## 8. Frontend

### 8.1 Store

`stores/aiChat.js` diventa consapevole della conversazione: `conversationId`, caricamento
di una conversazione esistente, creazione implicita al primo invio, cambio conversazione.
Il `watch` attuale che azzera i messaggi al cambio corso resta, ma azzera anche
`conversationId`. Non invia più `history` quando `conversationId` è valorizzato (§7.3).

### 8.2 Pannello flottante

[AiChatButton.vue](../../../frontend/src/oslms/components/ai/AiChatButton.vue):

- selettore delle conversazioni del corso corrente (le ultime N, per `last_message_at`);
- pulsante "Nuova conversazione";
- il cestino attuale passa da "svuota la memoria" ad **archivia**, con conferma (D2);
- collegamento "Vedi tutte le conversazioni" → pagina del progetto.

### 8.3 Pagina del progetto corso

Nuova rotta `/courses/:courseName/tutor`, componente
`frontend/src/oslms/pages/Courses/CourseTutorArchive.vue`.

- Elenco delle conversazioni a sinistra (titolo, data, numero di messaggi, etichetta della
  lezione di origine), trascrizione a destra, possibilità di riprendere la conversazione
  riusando `ChatBot.vue`.
- I messaggi con `status = Failed` sono resi come avviso ("risposta non disponibile"), mai
  come bolla vuota.
- Ogni risposta mostra la data di generazione: le risposte archiviate invecchiano se il
  corso cambia.
- Interruttore "mostra archiviate".
- Su telefono: elenco e trascrizione impilati, con ritorno all'elenco.

### 8.4 Vista del Gestore (Forma 1)

Stessa rotta, stesso componente. Se `can_view_tutor_archive` è vero, compare un selettore
**Studente** (`MultiLink` con `doctype="User"`, lo stesso controllo usato dai filtri di
[StudentStatsExport.vue](../../../frontend/src/oslms/pages/StudentStatsExport.vue)),
alimentato da `list_course_students`. Selezionando uno studente, l'elenco mostra le sue
conversazioni in **sola lettura**: niente riprendi, niente rinomina, niente archivia.

### 8.5 Punto d'ingresso

Un solo pulsante "Tutor AI" in
[CourseOverview.vue](../../../frontend/src/overrides/pages/Courses/CourseOverview.vue) —
file **già mantenuto come override**, quindi nessun innesto nuovo su codice upstream da
riapplicare dopo le fusioni.

**Gating:** il pulsante è visibile a chi è iscritto al corso oppure ha
`can_view_tutor_archive`. **Non** va gated su `isAdmin`, che nella SPA vale
`is_instructor || is_moderator || is_evaluator` e mostrerebbe l'archivio proprio ai ruoli
che D1 esclude.

### 8.6 Traduzioni

Etichette nuove in `lms/translations/it.csv` **e** in `lms/locale/it.po`: se la voce nel
PO esiste ed è non vuota, prevale sul CSV.

## 9. Configurazione

Campo `tutor_history_enabled` (Check, default 0) in `LMSA Settings`, sezione *Rag Tutor*:

- esposto alla SPA da `override_api.get_lms_settings` accanto a `ai_enabled`;
- dichiarato nel pannello impostazioni in
  [oslms/utils/settings.js](../../../frontend/src/oslms/utils/settings.js), sezione `AI`;
- a interruttore spento il tutor funziona esattamente come oggi (nessuna persistenza,
  nessun ingresso all'archivio): permette un rilascio in due tempi.

## 10. Piano di test

Suite Python in `ai/tutor/tests/`, con il provider fittizio già usato dalle simulazioni
(`enable_mock_provider`) e fixture sul modello di
[_fixtures.py](../../../apps/os_lms/os_lms/os_lms/ai/simulations/tests/_fixtures.py).

**Persistenza**
1. La prima `ask` senza `conversation` crea la conversazione e due messaggi con
   `turn_index` 0 e 1.
2. Una seconda `ask` con `conversation` accoda 2 e 3 e aggiorna `message_count` e
   `last_message_at`.
3. Una `ask` che fallisce scrive comunque il messaggio `assistant` con `status = Failed` e
   `content` vuoto.
4. `ask_audio` produce gli stessi record del percorso testuale.
5. Oltre `HISTORY_WINDOW_TURNS`, il prompt inviato al provider contiene solo gli ultimi
   N turni, esclusi i falliti.
6. Con `conversation` valorizzata, un parametro `history` inviato dal client viene ignorato.

**Permessi** (il cuore di D1)
7. Lo studente proprietario legge e modifica le proprie conversazioni.
8. Uno studente non può leggere quelle di un altro, né per elenco né per nome.
9. **Un Moderator puro riceve diniego** su elenco e documento.
10. Un Course Creator del corso riceve diniego.
11. Un Gestore legge tutto e **non** può scrivere.
12. `list_conversations(member=...)` da parte di un non-Gestore solleva `PermissionError`.
13. Dopo la rimozione dei permessi `LMS Student` su `LMSA Query Log`, la scrittura
    dell'audit continua a funzionare e uno studente non riesce più a leggerlo.

**Archiviazione e titolo**
14. `archive_conversation` nasconde la conversazione dall'elenco predefinito e la mostra
    con `include_archived=True`.
15. Il titolo è la prima domanda troncata a 140 caratteri; `rename_conversation` lo
    sostituisce e tronca a sua volta.

Collaudo manuale: percorso studente completo su telefono e desktop, percorso Gestore con
un'utenza `Website User` reale (per verificare che non serva il Desk).

## 11. Stima

Lo sviluppo è interamente a carico dell'assistente AI (Claude Code, Opus 5), sotto
supervisione del committente. La stima **operativa** è quindi in giornate di calendario e
in ore di impegno diretto del committente; la scomposizione in ore-uomo che segue resta
valida come **base per il preventivo al cliente**, non come costo di esecuzione.

### 11.1 Esecuzione (sviluppo AI + supervisione)

| Fase | Sviluppo (elapsed) | Revisione committente | Collaudo committente |
| --- | ---: | ---: | ---: |
| 1 — Dati, permessi, persistenza | 1–1,5 gg | 1,5–2 h | 0,5 h |
| 2 — Archivio e interfaccia studente | 1,5–2 gg | 3–4 h | 1,5–2 h |
| 3 — Gestore, impostazioni, documentazione | 0,5–1 gg | 1 h | 3–4 h |
| Giri di correzione dal collaudo | 0,5–1 gg | 0,5 h | 1 h |
| **Totale** | **4–5,5 giornate** | **6–7,5 h** | **6–7,5 h** |

**4–6 giornate di calendario, 12–15 ore di impegno diretto del committente.**

Base empirica: il 17/09/2026 il repository ha assorbito in una giornata 10 commit con
analisi, implementazione (512 righe su 8 file), restyle di un template email e tre giri di
correzione — circa 780 righe. Questo intervento vale 2.300–2.800 righe, con in più i
doctype nuovi da migrare nel container e una matrice di permessi da verificare a mano.

Non si comprime: il collaudo del committente, l'iterazione visiva della pagina, l'attrito
dell'ambiente Docker (`bench migrate` su doctype nuovi; la meta stale è un problema
ricorrente su questo progetto), le decisioni di prodotto che emergeranno.

### 11.2 Ore-uomo equivalenti (riferimento per l'offerta)

| Area | Voce | Ore |
| --- | --- | ---: |
| **Backend** | Doctype `LMSA Tutor Conversation` (campi, indici, controller) | 4 |
| | Doctype `LMSA Tutor Message` | 3 |
| | Hook dei permessi su entrambi + registrazione in `hooks.py` | 5 |
| | Correzione dei permessi di `LMSA Query Log` (§6.3) | 2 |
| | Persistenza dei turni in `TutorAi` + percorso audio + creazione implicita | 7 |
| | Cronologia lato server con finestra scorrevole | 4 |
| | Titolo automatico, rinomina, archiviazione | 3 |
| | Endpoint dell'archivio (`history.py`) | 5 |
| | Helper `can_view_tutor_archive` + esposizione in `get_user_info` | 2 |
| | Endpoint `list_course_students` per il selettore | 2 |
| | Test (persistenza + matrice dei permessi) | 9 |
| | *subtotale* | **46** |
| **Frontend** | Store consapevole della conversazione | 6 |
| | Pannello flottante: selettore, nuova, archivia | 8 |
| | Pagina del progetto corso | 12 |
| | Selettore studente per il Gestore + modalità sola lettura | 5 |
| | Rotta, punto d'ingresso, adattamento mobile | 5 |
| | Traduzioni IT/EN | 2 |
| | *subtotale* | **38** |
| **Consegna** | Interruttore in `LMSA Settings` + esposizione + pannello | 3 |
| | Documentazione (`docs/ai/TUTOR.md` + pagina nuova) | 3 |
| | Collaudo, UAT, giro di correzioni | 7 |
| | *subtotale* | **13** |
| | **Totale** | **97** |
| | *range realistico* | **87–105 h → 12–14 giorni** |

Giornate uomo di sviluppo effettivo (7,5 h), al netto di attese per decisioni, revisioni
grafiche e finestre di rilascio. Valore da usare in offerta; il costo di esecuzione reale
è quello di §11.1.

### 11.3 Sequenza di consegna

| Fase | Contenuto | Ore | Risultato |
| --- | --- | ---: | --- |
| 1 | Dati, permessi (incluso §6.3), persistenza, cronologia lato server, test | 46 | La chat non si perde più; nessuno legge quello che non deve |
| 2 | Store, pannello flottante, pagina del progetto, ingresso | 33 | Lo studente sfoglia e riprende le proprie conversazioni |
| 3 | Vista Gestore, interruttore, documentazione, collaudo | 18 | Funzione completa e rilasciabile |

## 12. Rischi e mitigazioni

| Rischio | Mitigazione |
| --- | --- |
| Il Gestore possiede anche Moderator: un ordine sbagliato nel gate apre a tutti i moderatori | Test 9 e 10, obbligatori prima del rilascio |
| Il 15% di risposte fallite diventa visibile e permanente | `status = Failed` reso come avviso esplicito (§8.3) |
| Le risposte archiviate invecchiano quando il corso cambia | Data di generazione mostrata accanto a ogni risposta |
| Conservazione illimitata (D3) a fronte di crescita della piattaforma | Alle dimensioni attuali è irrilevante; il modello non preclude l'aggiunta di una politica di conservazione |
| Il pulsante d'ingresso vive in un file adiacente all'upstream | È in un override già nostro; nessun innesto nuovo |
| `LMSA Query Log` continua a crescere di 6,3 KB per scambio | Fuori perimetro, segnalato: da valutare quando i numeri cresceranno |

## 13. Domande residue

Nessuna bloccante. Una da girare al committente perché cambia la promessa, non il design:
se al Gestore serve **sorvegliare l'uso** del tutor più che leggere le singole chat,
l'archivio non è lo strumento adatto e servirebbe invece un contatore d'uso per corso.
L'archivio risponde bene a "cosa ha risposto il tutor a questo studente", che è una
domanda da contestazione o da verifica puntuale.

## 14. Piano di implementazione

Il piano task-by-task, con codice e test per ogni passo, è in
[docs/superpowers/plans/2026-09-18-tutor-chat-history.md](../plans/2026-09-18-tutor-chat-history.md).

## 15. File toccati (previsione)

**Nuovi**
```
apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/
apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message/
apps/os_lms/os_lms/os_lms/ai/tutor/history.py
apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history.py
apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py
frontend/src/oslms/pages/Courses/CourseTutorArchive.vue
```

**Modificati**
```
apps/os_lms/os_lms/hooks.py                                  (hook permessi)
apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py               (persistenza, finestra)
apps/os_lms/os_lms/os_lms/ai/tutor/api.py                    (parametro conversation)
apps/os_lms/os_lms/os_lms/api.py                             (can_view_tutor_archive)
apps/os_lms/os_lms/os_lms/override_api.py                    (get_user_info, get_lms_settings)
apps/os_lms/os_lms/os_lms/doctype/lmsa_query_log/*.json      (rimozione perm LMS Student)
apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/*.json       (tutor_history_enabled)
frontend/src/stores/aiChat.js                                (conversazione)
frontend/src/oslms/components/ai/AiChatButton.vue            (selettore, archivia)
frontend/src/oslms/components/ai/ChatBot.vue                 (conversationId, turni falliti)
frontend/src/overrides/pages/Courses/CourseOverview.vue      (pulsante d'ingresso)
frontend/src/oslms/utils/settings.js                         (interruttore)
frontend/src/router.js                                       (rotta)
lms/translations/it.csv · lms/locale/it.po                   (etichette)
docs/ai/TUTOR.md                                             (aggiornamento)
```
