# Piano di sviluppo — Pagina "Esportazione statistiche"

Piano operativo passo per passo per sviluppare la nuova pagina. Prosa in italiano, identificatori/percorsi in inglese.

## Riepilogo tecnico

- **Backend**: 3 metodi whitelisted in `apps/os_lms/os_lms/os_lms/api.py` (schema, export, helper permessi).
- **Ruolo/visibilità**: nuovo flag `can_export_stats` in `get_user_info` (per ora = `is_system_manager`).
- **Frontend**: nuova pagina SPA `frontend/src/oslms/pages/StudentStatsExport.vue` + rotta in `router.js` + voce sidebar gated in `utils/index.js`.
- **Memoria colonne**: `useLocalStorage` (per browser), una selezione per tipo di report.
- **Riuso**: la meccanica CSV/XLSX esiste già in `export_batch_progress` (`api.py`, ~righe 633-821) — la generalizziamo.

Ordine consigliato: **backend prima** (schema → export), poi **frontend**. Così si può testare l'export via URL prima di avere la UI.

---

## Step 0 — Branch e preparazione

- [ ] Creare un branch di feature dedicato (es. `feature/stats-export`).
- [ ] Rileggere `export_batch_progress` in `apps/os_lms/os_lms/os_lms/api.py` come template della meccanica di download.
- **Fatto quando**: branch pronto e template compreso.

---

## Step 1 — Helper permessi (backend)

- [ ] In `apps/os_lms/os_lms/os_lms/api.py` aggiungere un helper unico:
  ```python
  def can_export_student_stats() -> bool:
      # Unico punto di verità: per ora solo System Manager (Administrator).
      # In futuro aggiungere qui altri ruoli.
      return "System Manager" in frappe.get_roles()
  ```
- [ ] Prevedere `frappe.throw(_("Not permitted"), frappe.PermissionError)` quando è `False`, da usare in cima ai due endpoint.
- **Fatto quando**: helper richiamabile; un utente non-admin riceve `PermissionError`.

---

## Step 2 — Flag di ruolo per la SPA (backend)

- [ ] In `apps/os_lms/os_lms/os_lms/override_api.py`, dentro `get_user_info`, aggiungere:
  ```python
  result["can_export_stats"] = "System Manager" in result.get("roles", [])
  ```
  (allineato all'helper dello Step 1 — è il flag che il frontend userà per mostrare/nascondere la pagina).
- **Fatto quando**: `get_user_info` ritorna `can_export_stats: true` per Administrator, `false` per uno studente.

---

## Step 3 — Endpoint schema (backend, fonte unica di verità)

Definisce i tipi di report e le colonne disponibili per ciascuno. Frontend e backend leggono da qui, così non divergono mai.

- [ ] Definire una struttura dati (costante nel modulo) tipo:
  ```python
  STATS_REPORTS = {
      "users":        {"label": "Utenti",         "columns": [ {"key": "...", "label": "..."}, ... ]},
      "user_courses": {"label": "Utenti × Corsi", "columns": [ ... ]},
      "quizzes":      {"label": "Quiz",           "columns": [ ... ]},
      "ai":           {"label": "Interazioni AI", "columns": [ ... ]},
  }
  ```
  Colonne per tipo (chiavi = nomi tecnici, label = testo IT):
  - **users**: `user_id, full_name, email, role, class, registered_on, status, last_login`
  - **user_courses**: `user_id, full_name, email, course_id, course_title, enrolled_on, progress, started_on, last_activity_on, completed_on`
  - **quizzes**: `user_id, full_name, course_title, quiz_id, quiz_title, attempts, first_attempt_on, last_attempt_on, last_score, best_score, max_score`
  - **ai**: `student_id, interacted_on, course, lesson, question, answer, context, server_error, cannot_answer`
- [ ] Metodo `@frappe.whitelist()` `get_student_stats_schema()`:
  - gate con `can_export_student_stats()`;
  - ritorna `STATS_REPORTS` (label + colonne) e l'elenco filtri supportati.
- **Fatto quando**: `GET /api/method/os_lms.os_lms.api.get_student_stats_schema` ritorna la struttura per un admin.

---

## Step 4 — Endpoint di export (backend, il cuore)

- [ ] Metodo `@frappe.whitelist()`:
  ```python
  def export_student_stats(report_type: str, columns: str, file_format: str = "csv", filters: str | None = None):
  ```
  - `columns` e `filters` arrivano **JSON-encoded** (query string via `window.open`) → `frappe.parse_json(...)`.
  - gate con `can_export_student_stats()`;
  - validare `report_type` contro `STATS_REPORTS` e `columns` contro le colonne ammesse (scartare chiavi non valide);
  - costruire le righe con la funzione del report (Step 4b);
  - **riusare la meccanica CSV/XLSX** di `export_batch_progress` (branch `csv.writer` + `io.StringIO`; branch `make_xlsx`; streaming via `frappe.response["filename"|"filecontent"|"type"|"content_type"]`).
- [ ] **Step 4b — un builder per tipo di report**, ognuno ritorna `(header_labels, rows)` in base alle `columns` scelte, applicando i `filters`:

  | report_type | Fonte dati | Note query |
  |---|---|---|
  | `users` | `User` | `enabled` → status; `creation` → registered_on; `last_login`/`last_active` → last_login; ruoli via `frappe.get_roles(user)`; classe via `LMS Batch Enrollment.batch` |
  | `user_courses` | `LMS Enrollment` (+ `LMS Course` per title) | `creation`→enrolled_on, `progress`; `completed_on` = `LMS Certificate.issue_date` se presente, altrimenti `max(LMS Course Progress.creation)` con `status=Complete` **e** progress=100; `started_on`=`min(...creation)`, `last_activity_on`=`max(...creation)` (approssimate) |
  | `quizzes` | `LMS Quiz Submission` | raggruppare per `(member, quiz)`: `attempts`=count, `first/last_attempt_on`=min/max `creation`, `last_score`=submission più recente, `best_score`=max `percentage`, `max_score`=`score_out_of`/`passing_percentage` |
  | `ai` | `LMSA Query Log` | mappa diretta: `member, creation, course, lesson, question, answer, context`; `server_error`/`cannot_answer` derivati da `status`/testo `answer` |

- [ ] Usare `frappe.qb` (come già in `get_batch_progress_stats`) per le query con join/aggregazioni.
- **Fatto quando**: chiamando l'URL con `report_type`, `columns`, `file_format` si scarica un file corretto per ciascuno dei 4 report.

---

## Step 5 — Filtri (backend + contratto)

Filtri supportati (combinabili; se assenti → tutti i dati): **corso**, **classe** (batch), **studenti**, **data attività** (intervallo).

- [ ] Nel builder applicare i filtri sulla fonte del report:
  - `course` → `LMS Enrollment.course` / `Quiz Submission.course` / `Query Log.course`; per `users`, restringere agli iscritti a quel corso.
  - `class` (batch) → risolvere i membri via `LMS Batch Enrollment.batch` e filtrare per `member`.
  - `students` → `member in [...]`.
  - `activity_date` (`from`/`to`) → sul timestamp rilevante del report (es. `creation` della riga; per `users` su `last_login`).
- [ ] Documentare il formato `filters` (oggetto JSON) e validarlo.
- **Fatto quando**: gli stessi 4 export rispettano i filtri passati.

---

## Step 6 — Rotta e voce sidebar (frontend)

- [ ] In `frontend/src/router.js` aggiungere la rotta (path proposto `/statistics/export`, component `@/oslms/pages/StudentStatsExport.vue`).
- [ ] In `frontend/src/utils/index.js` aggiungere la voce sidebar con gating:
  ```js
  { label: 'Esportazione statistiche', route: '/statistics/export',
    condition: () => usersStore().userResource?.data?.can_export_stats }
  ```
- **Fatto quando**: la voce compare solo per Administrator; navigando si apre la pagina (anche vuota).

---

## Step 7 — Pagina SPA (frontend, UI)

Modello: `frontend/src/pages/Statistics.vue` per layout; download come `exportProgress()` in `AdminBatchDashboard.vue`.

- [ ] All'avvio, `createResource({ url: 'os_lms.os_lms.api.get_student_stats_schema' })` per popolare tipi di report, colonne e filtri.
- [ ] UI:
  1. **Selettore tipo di report** (users / user_courses / quizzes / ai).
  2. **Lista colonne** (checkbox) del report selezionato, con "seleziona/deseleziona tutto".
  3. **Filtri**: corso (link/multiselect), classe/batch (multiselect), studenti (multiselect), intervallo date.
  4. **Bottone Esporta** con scelta formato (CSV / XLSX), come menu.
- [ ] Download: `window.open('/api/method/os_lms.os_lms.api.export_student_stats?report_type=...&columns=' + encodeURIComponent(JSON.stringify(cols)) + '&file_format=...&filters=' + encodeURIComponent(JSON.stringify(filters)))`.
- **Fatto quando**: dalla pagina si genera e scarica il file nei due formati.

---

## Step 8 — Memoria colonne (frontend)

- [ ] `useLocalStorage('lms_stats_export_columns', {})` (in `frontend/src/utils/composables.js` esiste già l'helper).
- [ ] Struttura: `{ [reportType]: [colKey, ...] }` — memorizza la selezione **per ogni tipo di report** separatamente.
- [ ] Al cambio report, ricaricare la selezione salvata (o un default sensato se assente).
- **Fatto quando**: ricaricando la pagina si ritrovano le colonne spuntate l'ultima volta, per ciascun tipo.

---

## Step 9 — Verifica

- [ ] Test manuale dei 4 report in CSV e XLSX, con e senza filtri.
- [ ] Verifica gating: uno studente **non** vede la voce e riceve `PermissionError` chiamando l'endpoint direttamente.
- [ ] Sanity su casi limite: utente senza corsi, corso senza quiz, studente senza interazioni AI, corso con lezioni aggiunte dopo il 100% (data completamento vuota).
- [ ] (Opzionale) Test backend `bench --site <site> run-tests --app os_lms` per i builder.
- **Fatto quando**: i 4 report sono corretti e il gating regge.

---

## Step 10 — Rifiniture (opzionali)

- [ ] **Log degli export** (chi/quando/cosa) per tracciabilità/privacy — valutare un doctype dedicato o `frappe.log`.
- [ ] Etichette in `__()` per la traduzione IT (coerente con il workflow traduzioni del progetto).
- [ ] Gestione volumi elevati (limiti/streaming) se i dataset diventano molto grandi.

---

## Checklist file toccati

- `apps/os_lms/os_lms/os_lms/api.py` — helper permessi + `get_student_stats_schema` + `export_student_stats` + builder.
- `apps/os_lms/os_lms/os_lms/override_api.py` — flag `can_export_stats` in `get_user_info`.
- `frontend/src/router.js` — rotta.
- `frontend/src/utils/index.js` — voce sidebar gated.
- `frontend/src/oslms/pages/StudentStatsExport.vue` — nuova pagina.
