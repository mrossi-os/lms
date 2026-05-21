# Integrazione TrueSkill — Guida

> Estensione di Frappe LMS che emette automaticamente un **Openbadge W3C** verificabile sulla piattaforma esterna [TrueSkill](https://trueskill.com) ogni volta che a un utente viene rilasciato un certificato di corso.

Audience: questa guida assume **zero conoscenza pregressa** del progetto. Spiega cosa fa l'integrazione, come si attiva, come monitorarla e dove guardare quando qualcosa va storto.

---

## 1. Cos'è e a cosa serve

### TrueSkill in 3 righe

TrueSkill è una piattaforma SaaS che emette **certificati digitali**: dato un template (es. "Corso Cybersecurity Base") e i dati di un utente, restituisce un **Openbadge** verificabile (file PNG + JSON-LD firmato secondo lo standard W3C Verifiable Credentials).

### Cosa fa questa integrazione

Quando in LMS viene creato un record `LMS Certificate` per uno studente che ha completato un corso configurato per TrueSkill, il sistema:

1. Apre un job in background.
2. Verifica che lo studente abbia un **codice fiscale** valorizzato.
3. Chiama `POST /issue` sull'API TrueSkill con `(templateId, fiscalId, email, nome)`.
4. Memorizza l'esito in una nuova doctype `TrueSkills Issue Log` (audit + reconciliation).
5. Espone allo studente nella sua pagina profilo due bottoni: **Scarica Openbadge** (PNG) e **JSON-LD**.

Tutto questo è **invisibile per lo studente** finché il badge non è pronto: non appare nulla di nuovo nelle UI di emissione, l'unico effetto è il footer aggiuntivo sulla card del certificato quando il badge è stato effettivamente emesso.

---

## 2. Quadro d'insieme

```
┌───────────────────────┐
│  Studente completa    │
│  il corso             │
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│  LMS Certificate      │
│  creato (Frappe)      │
└──────────┬────────────┘
           │  hook after_insert
           ▼
┌────────────────────────────────────┐
│  enqueue_issue()                   │
│  - controlla flag corso            │
│  - controlla template_id           │
│  - controlla che il client TS sia  │
│    configurato                     │
└──────────┬─────────────────────────┘
           │  frappe.enqueue (worker async)
           ▼
┌────────────────────────────────────┐
│  issue_certificate()               │
│  1. legge User.codice_fiscale      │
│  2. crea Issue Log = "pending"     │
│  3. POST /issue → TrueSkill API    │
│  4. aggiorna Issue Log a           │
│     "issued" / "failed" /          │
│     "needs_retry"                  │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Hourly: reconcile_pending()       │
│  recupera certificati che il       │
│  server ha emesso ma noi non       │
│  abbiamo registrato (timeout)      │
└────────────────────────────────────┘
```

---

## 3. Punti di vista — chi vede cosa

### Studente
- Pagina **My Profile → Certificates** (`/user/<username>/certificates`)
- Per ogni certificato di corso vede la card classica (PDF locale).
- **Nuovo:** se il certificato è stato emesso anche su TrueSkill, sotto la card compare un footer con due pulsanti:
  - **Download Openbadge** → scarica il file PNG con metadati incorporati.
  - **JSON-LD** → scarica il certificato W3C Verifiable Credentials (file `.jsonld`).

### Admin / Moderator / Course Creator
- Nelle impostazioni LMS (`LMS Settings`) trova **3 nuovi campi**: attivazione API, chiave, endpoint.
- Su **`LMS Course` → Settings** trova un toggle "Abilita Openbadge" + select del template TrueSkill.
- Può creare/sfogliare i template TrueSkill dal modale "Manage Templates" all'interno della form corso.
- Sulla form `LMS Certificate` del desk vede un pulsante **TrueSkills Issue Log** che apre l'elenco filtrato sul certificato.
- Sulla nuova doctype `TrueSkills Issue Log` può vedere lo stato di tutte le emissioni e, per quelle in `failed`/`needs_retry`, premere **Retry emission**.

### Sistema (automatismi)
- Hook `after_insert` su `LMS Certificate` → enqueue.
- Job background → emette su TrueSkill.
- Scheduler hourly → reconcilia gli stati `pending`/`needs_retry`.

---

## 4. Configurazione necessaria

Prima che l'integrazione possa fare qualcosa di utile, va configurata in 3 punti.

### 4.1 — `LMS Settings` (singleton Frappe)

| Campo | Tipo | Significato |
|---|---|---|
| `trueskills_api_enabled` | Checkbox | Master switch. Se off, **niente** viene emesso. |
| `trueskills_api_key` | Password | Chiave `ts_<opaque>` fornita da TrueSkill. Identifica anche l'organizzazione. |
| `trueskills_api_endpoint` | Data | **Solo host** (es. `https://api.trueskill.com`). Il client appende automaticamente `/api/v1/service/certificates`. |

### 4.2 — `User.codice_fiscale`

Custom field già esistente (16 caratteri, unique). Senza di questo, l'emissione **non parte** e viene creato un Issue Log `failed` con messaggio `missing_fiscal_id`.

### 4.3 — `LMS Course` (per ogni corso che deve emettere Openbadge)

| Campo | Tipo | Significato |
|---|---|---|
| `trueskills_certificate_enabled` | Checkbox | Attiva l'emissione TrueSkill per questo corso. |
| `trueskills_template_id` | Data | ID numerico del template TrueSkill (scelto da una select). |

---

## 5. La doctype `TrueSkills Issue Log`

È il **registro di ogni tentativo di emissione**. Ogni riga rappresenta UN tentativo. Un certificato può avere più righe (es. fallimento + retry manuale).

### Campi

| Campo | Tipo | Cosa contiene |
|---|---|---|
| `name` | autoname | `TSL-YYYY-#####` |
| `lms_certificate` | Link | Il certificato locale a cui si riferisce |
| `state` | Select | `pending`, `issued`, `failed`, `needs_retry` |
| `requested_at` | Datetime | Quando è partita la richiesta |
| `issued_at` | Datetime | Quando TrueSkill ha confermato l'emissione |
| `template_id` | Int | Snapshot del template usato |
| `recipient_email` | Data | Snapshot dell'email destinatario |
| `recipient_name` | Data | Snapshot del nome destinatario |
| `trueskill_id` | Int | ID numerico restituito da TrueSkill (per `/detail`, `/download`) |
| `trueskill_uid` | Data | UUID per la verifica pubblica (`/verify`) |
| `attempts` | Int | Numero del tentativo (1 = primo, +1 per ogni retry) |
| `error_message` | Small Text | Codice di errore stabile da TrueSkill (es. `template_not_enabled`) |

### Stati e transizioni

| Stato | Significato | Prossimo step |
|---|---|---|
| `pending` | Richiesta inviata, attesa risposta | Diventa `issued` o `needs_retry` |
| `issued` | TrueSkill ha confermato l'emissione | Terminale |
| `failed` | Errore 4xx (es. CF mancante, template disabilitato) | Operatore deve correggere e premere "Retry" |
| `needs_retry` | Errore 5xx o timeout | Scheduler tenta di reconciliare; operatore può forzare il retry |

> **Importante:** `POST /issue` non è idempotente. Un retry automatico potrebbe creare **duplicati** sul server. Per questo retry e reconciliation sono separati: lo scheduler **non emette mai**, controlla solo se TrueSkill ha già il certificato.

---

## 6. Flusso di emissione passo per passo

### 6.1 Happy path

1. Studente completa il corso → `LMS Certificate` creato.
2. Hook `after_insert` → `enqueue_issue(doc)`:
   - Se il corso non ha `trueskills_certificate_enabled` → **STOP**, silenzio.
   - Se manca `trueskills_template_id` → log warning, **STOP**.
   - Se `LMS Settings.trueskills_api_enabled = false` o mancano API key/endpoint → **STOP**.
   - Altrimenti `frappe.enqueue` con `enqueue_after_commit=True` (parte solo dopo che il certificato è stato veramente salvato) → la creazione del certificato **ritorna immediatamente**.
3. Worker prende il job → `issue_certificate(lms_certificate)`:
   - Recupera `User.codice_fiscale`, `email`, `full_name`.
   - Se manca uno dei tre → log `failed`, no retry.
   - Crea log `pending` + **commit DB** (importante: prima della chiamata HTTP).
   - `POST /issue` con `(templateId, fiscalId, email, name)`.
   - Successo (200) → log diventa `issued`, popola `trueskill_id`, `trueskill_uid`, `issued_at`.
4. Lo studente, ricaricando la pagina certificati, vede i due nuovi bottoni.

### 6.2 Errori comuni

| Cosa va storto | Stato finale | Messaggio | Azione operatore |
|---|---|---|---|
| Studente senza codice fiscale | `failed` | `missing_fiscal_id` | Aggiungere CF a User → Retry |
| Template disabilitato su TrueSkill | `failed` | `template_not_enabled` | Abilitare nel pannello TrueSkill → Retry |
| Template inesistente (rinominato/eliminato) | `failed` | `template_not_found` | Aggiornare `trueskills_template_id` del corso → Retry |
| Server TrueSkill 5xx | `needs_retry` | descrizione errore | Aspettare reconciliation, oppure Retry manuale |
| Timeout di rete | `needs_retry` | `TrueSkills request failed: ...` | Aspettare reconciliation |
| API key invalida | `failed` | `401` | Aggiornare la chiave in `LMS Settings` → Retry |

---

## 7. Reconciliation (hourly)

Funzione: `os_lms.os_lms.trueskills.scheduler.reconcile_pending`

### Quando entra in gioco

Quando il worker chiama `POST /issue` e riceve un timeout, è possibile che TrueSkill abbia **comunque emesso** il certificato — semplicemente la risposta è andata persa. Senza reconciliation, lo studente non vedrebbe mai il suo Openbadge anche se TrueSkill ce l'ha. Lo scheduler hourly:

1. Cerca Issue Log in `pending` o `needs_retry` con `requested_at > 5 min fa`.
2. Chiama `GET /list` su TrueSkill (max 100 emissioni più recenti).
3. Per ogni log non chiuso, prova a fare match con:
   - **Stesso nome template** (cache lookup via `get_template`).
   - **`createdAt` entro [requested_at - 5 min, requested_at + 30 min]**.
4. Se trova **esattamente un candidato** → marca `issued` con i dati reali.
5. Se ne trova **più di uno** → lascia il log invariato, scrive warning nei log Frappe (review umana).
6. Se non ne trova → resta `needs_retry`.

### Retry manuale dal desk

Dalla doctype `TrueSkills Issue Log`, quando lo stato è `failed` o `needs_retry`, compare un pulsante **Retry emission**.

- Crea un **nuovo** Issue Log (il vecchio non viene mai modificato → audit preservato).
- Rifiutato se esiste già un log `issued` per lo stesso certificato (protezione duplicati).
- Il nuovo log eredita `attempts = max precedente + 1`.

---

## 8. Sicurezza

### 8.1 Cosa è protetto

| Dato | Dove vive | Protezione |
|---|---|---|
| `X-Api-Key` (chiave TrueSkill) | `LMS Settings.trueskills_api_key` | Campo password Frappe (encrypted); scrubbing nei log |
| `codice_fiscale` | `User.codice_fiscale` | Solo in memoria durante `POST /issue`. **Mai persistito** sull'Issue Log. **Mai loggato** (scrubber regex sul logger) |
| `fiscalIdHash` (hash CF da TrueSkill) | Risposte `/list`, `/detail` | Mai loggato per intero |
| Body di `/issue` | Solo in flight | Mai loggato |

### 8.2 Lo scrubber

Modulo: [safelog.py](os_lms/os_lms/trueskills/safelog.py)

Tutti i log del modulo TrueSkill passano per il logger `trueskills`, su cui è installato un filtro che maschera:
- **Codice fiscale italiano** (pattern strict `LLLLLL NN L NN L NNN L`) → `[REDACTED-FISCAL-ID]`
- **Chiavi API** (pattern `ts_<opaque>`) → `ts_[REDACTED]`

I tracebacks scritti via `frappe.log_error` sono passati attraverso `scrub()` esplicitamente prima della scrittura.

### 8.3 Chi può fare cosa

| Operazione | Permessi |
|---|---|
| Test connessione, gestione template (read/create), get_status | `System Manager`, `Moderator`, `Course Creator` |
| Lettura/scrittura `TrueSkills Issue Log` | `System Manager`, `Moderator`, `Course Creator` |
| Retry emission | `System Manager`, `Moderator`, `Course Creator` |
| Verifica certificato (`/verify`) | Admin (richiede comunque API key TrueSkill della stessa org) |
| Download Openbadge (PNG / JSON-LD) | **Proprietario del certificato (`LMS Certificate.member`)** oppure admin |

---

## 9. File toccati / creati

### File **nuovi**

| Path | Cosa fa |
|---|---|
| [`os_lms/os_lms/trueskills/safelog.py`](os_lms/os_lms/trueskills/safelog.py) | Logger con scrubbing PII (CF + API key) |
| [`os_lms/os_lms/trueskills/emission.py`](os_lms/os_lms/trueskills/emission.py) | Hook `enqueue_issue` + worker `issue_certificate` |
| [`os_lms/os_lms/trueskills/scheduler.py`](os_lms/os_lms/trueskills/scheduler.py) | Job hourly `reconcile_pending` |
| [`os_lms/os_lms/doctype/trueskills_issue_log/`](os_lms/os_lms/doctype/trueskills_issue_log/) | Nuova doctype + JS desk (pulsante Retry) |
| [`os_lms/public/js/lms_certificate.js`](os_lms/public/js/lms_certificate.js) | Pulsante "TrueSkills Issue Log" su desk `LMS Certificate` |
| [`TRUESKILLS.md`](TRUESKILLS.md) | Questo documento |

### File **modificati**

| Path | Modifica |
|---|---|
| [`os_lms/os_lms/trueskills/client.py`](os_lms/os_lms/trueskills/client.py) | Refactor completo: header `X-Api-Key`, base path automatico, gerarchia errori (`Client/Server/Network`), retry esponenziale su GET e `/verify`, metodo `download` binario, `health()` |
| [`os_lms/os_lms/trueskills/service.py`](os_lms/os_lms/trueskills/service.py) | Aggiunti `health`, `get_template` (con cache), `list_issued`, `get_issued`, `verify`, `download`, `issue_certificate` |
| [`os_lms/os_lms/trueskills/api.py`](os_lms/os_lms/trueskills/api.py) | Nuovi endpoint whitelisted: `health`, `get_template`, `list_issued`, `get_issued`, `verify`, `download`, `retry_emission`, `get_issue_status`. Permission gating per `download` ridotto al proprietario |
| [`os_lms/hooks.py`](os_lms/hooks.py) | `doc_events["LMS Certificate"].after_insert`, `scheduler_events.hourly`, `doctype_js` per LMS Certificate |
| [`frontend/src/pages/ProfileCertificates.vue`](../../frontend/src/pages/ProfileCertificates.vue) | Bottoni download Openbadge + JSON-LD nella card certificato studente |

---

## 10. API endpoints (whitelisted)

Tutti sotto `os_lms.os_lms.trueskills.api`.

| Metodo Python | HTTP path Frappe | Permessi | Cosa fa |
|---|---|---|---|
| `get_status()` | `.../get_status` | Admin | Stato configurazione (enabled, has_api_key, ready) |
| `health()` | `.../health` | Admin | Smoke test → `{status, organizationId}` |
| `test_connection()` | `.../test_connection` | Admin | Wrapper di `health` per il pulsante in settings |
| `list_templates()` | `.../list_templates` | Admin | Lista template TrueSkill |
| `get_template(template_id)` | `.../get_template` | Admin | Singolo template (con cache) |
| `create_template(payload)` | `.../create_template` | Admin | Crea un nuovo template |
| `list_issued()` | `.../list_issued` | Admin | 100 certificati emessi più recenti |
| `get_issued(certificate_id)` | `.../get_issued` | Admin | Dettagli singolo certificato emesso |
| `verify(uid, fiscal_id?)` | `.../verify` | Admin | Verifica via UUID, controlla `valid` |
| `download(certificate_id, file_format)` | `.../download` | **Proprietario o Admin** | PNG (`image`) o JSON-LD (`jsonp`) |
| `retry_emission(issue_log)` | `.../retry_emission` | Admin | Crea nuovo Issue Log per ritentare |
| `get_issue_status(lms_certificates)` | `.../get_issue_status` | User stesso o Admin | Stato badge per N certificati (per il frontend studente) |

---

## 11. Limitazioni note

1. **Solo Openbadge.** Il tipo `Certificate` (PDF/HTML attestation) di TrueSkill non è implementato in Fase 1. Tutte le UI assumono Openbadge.
2. **Solo certificati di corso.** I certificati di **batch** (`LMS Certificate.batch_name` senza `course`) non emettono su TrueSkill. Estensione semplice se serve.
3. **Reconciliation imperfetta.** Il match TrueSkill ↔ Issue Log usa `(nome template, finestra temporale)` perché `/list` non restituisce email. Se due studenti completano lo stesso corso nella stessa finestra di 30 minuti e entrambi vanno in `needs_retry`, la reconciliation li lascia "ambigui" → operatore deve risolvere a mano.
4. **`POST /issue` e `POST /templates` non sono idempotenti.** L'integrazione non li ritenta mai automaticamente.
5. **Nessuna gestione `certificateValues` né `subjectData`.** `issue_certificate` invia solo i campi base. Se il template TrueSkill ha attributi obbligatori o evidenze, vanno aggiunti.
6. **Filtro 16-char generico non implementato per il CF.** Lo scrubber matcha solo CF italiani con struttura strict (LLLLLL NN L NN L NNN L). CF stranieri / partita IVA non vengono mascherati.

---

## 12. Setup e attivazione

Dopo il primo deploy (o `git pull`):

```bash
# Sul container frappe (docker compose exec frappe bash):
bench --site lms.localhost migrate          # registra TrueSkills Issue Log + custom fields
bench --site lms.localhost build --app os_lms  # bundle del JS desk
bench --site lms.localhost clear-cache
bench restart                                # ricarica scheduler hourly + worker
```

Sul frontend Vue (dev o build di produzione):

```bash
cd frontend
yarn install      # se non l'hai già fatto
yarn build        # produzione → lms/public/frontend/
# oppure
yarn dev          # dev con HMR
```

Poi via UI:

1. **`LMS Settings`** → compilare i 3 campi TrueSkill, premere "Test connection".
2. **`LMS Course`** (per ogni corso che deve emettere): toggle "Abilita Openbadge" + scegliere un template (o crearne uno nuovo dal modale).
3. **Test:** rilasciare manualmente un `LMS Certificate` a uno studente con `codice_fiscale` valorizzato. Controllare la doctype `TrueSkills Issue Log` dopo qualche secondo.

---

## 13. Troubleshooting

### "Test connection" restituisce errore

| Risposta | Causa probabile | Fix |
|---|---|---|
| `401` | API key sbagliata o revocata | Rigenerare la chiave nella dashboard TrueSkill |
| `TrueSkills request failed: ...` (timeout, DNS) | Endpoint sbagliato | Verificare che sia **solo l'host** (es. `https://api.trueskill.com`, **senza** path) |
| `404` su `/health` | Endpoint in settings include già il path | Rimuovere `/api/v1/service/certificates` dal valore in `LMS Settings.trueskills_api_endpoint` |

### Lo studente ha completato il corso ma non vedo nessun Issue Log

Controlla nell'ordine:

1. **Corso configurato?** Apri `LMS Course` → `trueskills_certificate_enabled = ✓` e `trueskills_template_id` valorizzato.
2. **Integrazione attiva?** `LMS Settings.trueskills_api_enabled = ✓` e tutti i campi compilati.
3. **Worker attivo?** `bench worker --queue long` deve essere in esecuzione. Controlla `bench logs`.
4. **Log Frappe**: `tail -f sites/lms.localhost/logs/scheduler.log` e cerca righe con `trueskills`.

### Issue Log in `failed` con `error_message=missing_fiscal_id`

Lo studente non ha il **Codice Fiscale** valorizzato. Vai su `User → <utente>` desk e compila `codice_fiscale`, poi premi **Retry emission** dall'Issue Log.

### Issue Log resta `needs_retry` per ore

1. Verifica che lo scheduler giri: `bench scheduler status`.
2. Forza una reconciliation manuale dalla bench console:
   ```python
   from os_lms.os_lms.trueskills.scheduler import reconcile_pending
   reconcile_pending()
   ```
3. Se ancora `needs_retry` dopo la reconciliation, vuol dire che TrueSkill non ha mai ricevuto la richiesta. Premi **Retry emission**.

### Lo studente non vede i bottoni "Download Openbadge"

1. C'è un Issue Log in stato `issued` per quel certificato? Se no, l'emissione non è ancora andata a buon fine.
2. Hai fatto `yarn build` dopo le modifiche? Il frontend Vue è cachato.
3. Hard refresh del browser (Cmd-Shift-R).

### Il download del badge ritorna "Not permitted"

Lo studente sta provando a scaricare un certificato che **non è suo**, oppure non c'è un Issue Log `issued` corrispondente al `trueskill_id` passato. Solo il proprietario (`LMS Certificate.member`) o un admin possono scaricare.

---

## 14. Glossario rapido

| Termine | Significato |
|---|---|
| **LMS Certificate** | Doctype Frappe LMS: certificato locale rilasciato dopo il completamento di un corso |
| **TrueSkills Issue Log** | Doctype custom: tracciamento di ogni tentativo di emissione verso TrueSkill |
| **Openbadge** | Standard W3C / IMS Global per badge digitali verificabili (PNG con metadati + JSON-LD) |
| **W3C VC** | Verifiable Credentials: il JSON-LD è cryptograficamente verificabile senza chiamare TrueSkill |
| **template** (TrueSkill) | Definizione di un certificato/badge sulla piattaforma TrueSkill (nome, criteri, immagine) |
| **fiscalId** | Codice fiscale dello studente; TrueSkill lo hasha lato server, mai memorizzato in chiaro |
| **uid** (TrueSkill) | UUID pubblico del certificato emesso, usato per la verifica di terzi |
| **id** (TrueSkill) | PK numerico interno usato per `/detail` e `/download` |
| **reconcile** | Lo scheduler hourly che recupera certificati che TrueSkill ha emesso ma noi non sappiamo |
| **PII** | Personally Identifiable Information; nel nostro contesto è soprattutto il codice fiscale |

---

## 15. Per approfondire

- **Brief API ufficiale TrueSkill:** riferimento autoritativo per endpoint, schemi e codici errore (vedi memoria del progetto: `trueskill_api_integration_brief.md`).
- **Decisioni di progetto:** scelte specifiche fatte durante l'implementazione (`trueskills_integration_decisions.md` nella memoria).
- **Codice sorgente:** tutto sotto [`apps/os_lms/os_lms/os_lms/trueskills/`](os_lms/os_lms/trueskills/).
