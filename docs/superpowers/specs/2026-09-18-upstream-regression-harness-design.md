# Sistema di verifica delle personalizzazioni contro gli aggiornamenti upstream — documento di progetto

**Data:** 2026-09-18
**Stato:** progetto approvato, da implementare
**Branch di riferimento:** `feature/oslms`
**Destinatari:** il supervisore del progetto e ogni sessione di sviluppo futura (umana o AI) che debba costruire, estendere o usare questo sistema.

---

## 1. Obiettivo

Costruire uno strumento che, dopo ogni merge dell'upstream (`frappe/lms`), risponda in modo automatico e affidabile a due domande distinte:

1. **Le mie personalizzazioni sono ancora al loro posto?** — cioè: l'aggiornamento ha ripulito righe di codice che avevo aggiunto dentro file upstream?
2. **Le mie personalizzazioni funzionano ancora come devono?** — cioè: le regole di comportamento che ho definito (tipicamente regole di visibilità per ruolo) producono ancora lo stesso risultato?

Quando la risposta è no, lo strumento deve **notificare con precisione cosa è cambiato** e **proporre il ripristino**, non limitarsi a segnalare un fallimento generico.

Requisiti espressi dal committente:

1. Non dover più ritestare l'intera piattaforma a mano dopo ogni aggiornamento upstream.
2. Rilevare quando un file aggiornato dall'upstream "ripulisce" una modifica locale.
3. Verificare che una regola di visibilità legata a un ruolo custom (esempio citato: un bottone visibile al ruolo `Gestore`) sia rimasta valida.
4. In caso di modifica: **ripristinare lo stato precedente oppure notificare** il cambiamento.
5. La stesura e l'esecuzione dei test devono essere affidate a un agente AI, non svolte a mano.

---

## 2. Il problema, in concreto

Questo repository è un fork di un upstream vivo. Le personalizzazioni vivono su tre livelli, con esposizione al conflitto molto diversa (vedi la memoria di progetto `upstream-merge-maintenance-strategy`):

| Livello | Dove | Esposizione al merge |
| --- | --- | --- |
| Backend e feature nuove | `apps/os_lms/` (app Frappe separata) | nulla per costruzione |
| Componenti `frappe-ui` e pagine SPA | `frontend/src/overrides/` via plugin `osOverrideTheme` | nulla, ma la pagina è "congelata" |
| Innesti dentro file upstream | `frontend/src/**`, `lms/**` | **alta — è qui che nasce il problema** |

Perimetro misurato il 2026-09-18:

- **49** marcatori `OSLMS-CUSTOM` in file sorgente (esclusi i bundle generati in `lms/public/frontend/`).
- **169** occorrenze di gate per ruolo (`is_moderator`, `is_docente`, `is_instructor`, `is_student`, `is_valutatore`, `can_export_stats`, `canManageOsIntegrations`) distribuite su **48** file della SPA; collassano in circa **40-50 regole distinte**, perché la stessa regola è ripetuta in più punti.
- **37** funzioni di override backend fra `override_api.py` e `override_utils.py`.

Infrastruttura di test già presente e riutilizzabile:

| Livello | Cosa esiste | Workflow CI |
| --- | --- | --- |
| Backend Python | test doctype upstream + suite `os_lms` (`ai/**/tests`) | `ci.yml` |
| Componenti Vue | 31 test Vitest in `frontend/src/tests/` | `frontend-tests.yml` |
| E2E browser | 3 spec Cypress (`course_creation`, `batch_creation`, `simulations`) | `ui-tests.yml` |

Limite dell'E2E attuale: **tutte e 3 le spec girano come `Administrator`**, che in Frappe bypassa ogni controllo di permesso. Nessuna di esse può quindi rilevare una regressione sulle regole di visibilità per ruolo.

---

## 3. Decisioni prese

Decisioni prese dal committente in sede di progettazione (2026-09-18). Ognuna esclude alternative che sono state valutate: **non vanno ribaltate senza una nuova discussione.**

| # | Decisione | Alternativa scartata e perché |
| --- | --- | --- |
| D1 | **Perimetro:** personalizzazioni + percorsi funzionali critici | Solo personalizzazioni (più economico, ma non dice se la piattaforma funziona); copertura totale (settimane di lavoro, suite ingestibile contro un upstream vivo) |
| D2 | **Le regole di visibilità si testano in due metà separate:** backend `ruolo → flag`, Vitest `flag → DOM` | Tutto end-to-end: massima fedeltà ma lento, fragile, e un fallimento non indica quale metà si è rotta |
| D3 | **Baseline = inventario dichiarativo**, compilato dall'agente, revisionato a campione sulle voci a bassa confidenza | Snapshot automatico dal codice: congela anche i bug presenti e non permette il ripristino, perché non conserva l'intenzione |
| D4 | **Riparazione assistita in branch:** l'agente riapplica in commit separati, il committente revisiona il diff | Ripristino automatico e silenzioso: quando l'upstream riscrive un componente il ripristino è semanticamente sbagliato e non ci si accorge |
| D5 | **E2E = smoke di visibilità per ruolo + flussi funzionali critici** | Solo flussi funzionali: la giuntura `ruolo → flag` non verrebbe mai verificata davvero end-to-end |
| D6 | Si aggiungono attributi `data-test` sugli elementi censiti nell'inventario | Selezione per testo: fragile in un'app tradotta, una modifica di traduzione produce un falso allarme |

### 3.1 Il ragionamento che regge D3 (da non perdere)

Un test è un predicato booleano: passa o fallisce. **Un test non sa ripristinare nulla.** Il requisito 4 del committente ("rimettere com'era prima") richiede per forza un artefatto che conservi **l'intenzione** oltre all'esito. Per questo l'inventario non è documentazione accessoria: è il componente che rende possibile la metà "ripara" del sistema. La sola metà "notifica" sarebbe ottenibile anche con i soli test.

### 3.2 Il ragionamento che regge D2 (da non perdere)

La SPA di LMS **non controlla i permessi Frappe**: controlla dei flag booleani calcolati da `override_api.get_user_info` (vedi memoria `docente-global-instructor-role`). La catena reale è:

```
ruolo "Gestore"  →  [backend]  →  flag can_export_stats = true  →  [SPA]  →  bottone visibile
```

C'è una giuntura netta a metà. Testare le due metà separatamente, ognuna con lo strumento veloce adatto, dà la stessa copertura dell'E2E su questa catena, in secondi anziché minuti, e un fallimento indica subito il lato rotto. L'E2E resta per verificare che la giuntura stessa regga (D5).

---

## 4. Non-obiettivi

- Non si testa il funzionamento base dell'upstream non personalizzato: lo copre la CI di `frappe/lms`.
- Non si sostituiscono i 31 test Vitest esistenti né le suite backend: il nuovo sistema si affianca.
- Non si costruisce un generatore di test a template (vedi §7.4: i test li scrive l'agente).
- Non si automatizza il merge upstream in sé, né la risoluzione dei conflitti git.
- Non si tocca `frontend/src/overrides/`: le pagine lì dentro sono congelate per scelta, e la loro riconciliazione con l'upstream resta un'attività manuale pianificata a parte.

---

## 5. Architettura d'insieme

```
        docs/customizations/*.toml          ← INVENTARIO (fonte di verità unica)
                    │                          una voce per personalizzazione
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌──────────┐
   │ DRIFT   │ │  TEST   │ │ RAPPORTO │
   │DETECTOR │ │ 3 suite │ │ + REPAIR │
   └─────────┘ └─────────┘ └──────────┘
    ~2 sec      backend/     agente AI:
   controllo    vitest/      legge intent,
   testuale     cypress      riapplica in
                             commit separati
```

**Principio strutturale: l'inventario è l'unica fonte di verità, tutto il resto ne discende.**

Motivazione: la modalità di fallimento tipica di queste suite è che si scrivono una volta, poi si aggiunge una personalizzazione senza aggiungere il test, e dopo mesi la suite passa verde su un perimetro che copre metà del reale. Con l'inventario al centro, il detector può fare anche il **controllo inverso** — segnalare marcatori `OSLMS-CUSTOM` presenti nel codice ma assenti dall'inventario — che è l'unico modo per accorgersi di ciò che non è stato censito.

**Collocazione dei file (scelta deliberata).** Tutti i file del sistema stanno o dentro `apps/os_lms/` (app separata, zero conflitti per costruzione) o in **sottocartelle nuove** che l'upstream non tocca: `frontend/src/tests/oslms/`, `cypress/e2e/oslms/`, `docs/customizations/`, `scripts/`. *Il sistema che sorveglia i merge non deve poter essere danneggiato da un merge.*

---

## 6. Componente 1 — L'inventario

### 6.1 File

```
docs/customizations/
├── README.md            # come si legge e si aggiorna l'inventario
├── actors.toml          # gli attori (utenti per ruolo) usati da test e seeding
├── spa-grafts.toml      # innesti marcati OSLMS-CUSTOM (i 49 censiti in Fase 0)
├── roles.toml           # regole di visibilità che NON stanno in file upstream
├── api-overrides.toml   # contratti delle 37 funzioni di override backend
└── flows.toml           # percorsi funzionali critici (E2E)
```

**Formato: TOML, non YAML.** Verificato il 2026-09-18: sul `python3` di sistema della macchina di sviluppo **PyYAML non è installato**, mentre `tomllib` è nella libreria standard dal Python 3.11 (macchina: 3.13.2; CI: 3.14). Il valore del rilevatore di scostamento è girare in due secondi senza installare né avviare nulla: una dipendenza esterna, con la gestione di venv che comporta, ne annullerebbe il senso. TOML offre commenti e stringhe multi-riga (necessarie per `intent`), quindi non si perde nulla rispetto a YAML.

**Confine fra `spa-grafts.toml` e `roles.toml`** — una regola di visibilità può stare in entrambi i file, e il criterio è **dove vive il codice**, non cosa fa la regola:

- se la regola è innestata in un **file upstream** (quindi esposta al merge) → `layer = "spa-graft"`;
- se vive in codice interamente nostro (`frontend/src/oslms/`, `frontend/src/overrides/`, `apps/os_lms/`) → `layer = "override-file"`.

In Fase 0 tutte le voci ricavate dai marcatori `OSLMS-CUSTOM` stanno in `spa-grafts.toml` a prescindere dal proprietario del file ospite: è il campo `layer` a portare la distinzione, e il rapporto post-merge dà priorità alle voci `spa-graft`, che sono le uniche realmente esposte. `roles.toml` nasce in Fase 1 per le regole di visibilità che nessun marcatore copre.

Le voci hanno lo stesso schema; cambia solo il rischio che corrono, e quindi l'attenzione che il rapporto post-merge dedica loro.

### 6.2 Schema di una voce

Campi comuni a tutte le voci:

| Campo | Obbligatorio | Scopo |
| --- | --- | --- |
| `id` | sì | identificatore kebab-case, usato nei commit, nei test e nel rapporto |
| `title` | sì | descrizione breve leggibile |
| `layer` | sì | `spa-graft` \| `override-file` \| `os-lms-api` \| `fixture` \| `flow` |
| `confidence` | sì | `high` \| `low` — `low` segnala al committente che la voce va rivista |
| `sites[]` | sì (tranne `flow`) | `{file, anchor, symbol?, marker?}` — dove vive la personalizzazione |
| `intent` | sì | **la regola in linguaggio naturale**: è ciò che permette all'agente di riapplicarla in un file riscritto |
| `visibility` | se pertinente | `{subject, selector, allow[], deny[]}` — genera i test |
| `contract` | se `os-lms-api` | `{method, must_return_keys[]}` |
| `checks` | sì, può essere vuoto | `{backend?, unit?, e2e?}` — percorsi dei file di test collegati. Vuoto è legittimo in Fase 0, dove l'inventario esiste ma i test non sono ancora scritti: il controllo C4 segnala le voci scoperte come `warning`, non come `error` |
| `status` | no | assente = attiva; `accepted-drift` = regola superata, con `since` e `reason` |

In `visibility.allow` / `visibility.deny` compaiono nomi di ruolo Frappe (`Moderator`, `Docente`, `Gestore`, `LMS Student`) e **pseudo-attori** che descrivono una relazione, non un ruolo: `course-instructor` (istruttore di quel corso), `batch-valutatore` (valutatore di quella classe), `Guest` (non autenticato). Gli pseudo-attori vanno dichiarati in `actors.toml` con il `scoped` che li definisce.

`anchor` è una stringa che deve comparire testualmente nel file. Va scelta il più **distintiva** possibile: l'attributo `data-test` è l'ancora ideale (vedi §6.4).

### 6.3 Esempi (uno per tipologia)

**A — innesto dentro un file upstream** (`spa-grafts.toml`):

```toml
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = """
Il menu di gestione del corso è visibile a Moderator, Docente e all'istruttore del
corso. Mai a Studente né a Valutatore: il Valutatore accede in sola lettura e
un'azione di gestione lo porterebbe a creare un'iscrizione reale per errore."""

  [[entries.sites]]
  file = "frontend/src/components/CourseCardOverlay.vue"
  anchor = "Boolean(user.data?.is_docente)"
  symbol = "isAdmin"

  [entries.visibility]
  subject = "menu di gestione del corso"
  selector = '[data-test="course-admin-menu"]'
  allow = ["Moderator", "Docente", "course-instructor"]
  deny = ["Student", "Valutatore", "Guest"]

  [entries.checks]
  unit = "frontend/src/tests/oslms/courseCardAdminGate.test.ts"
  e2e = "cypress/e2e/oslms/visibility/course-card.cy.js"
```

**B — override API backend** (`api-overrides.toml`):

```toml
[[entries]]
id = "user-info-export-flag"
title = "get_user_info espone can_export_stats"
layer = "os-lms-api"
confidence = "high"
intent = """
L'override di lms.lms.api.get_user_info aggiunge can_export_stats al payload,
calcolato da os_lms.os_lms.api.can_export_student_stats (vero per Gestore). Se
l'upstream cambia firma o payload di get_user_info, il flag deve continuare ad
arrivare: è il gate della pagina di export statistiche studenti."""

  [[entries.sites]]
  file = "apps/os_lms/os_lms/os_lms/override_api.py"
  anchor = 'result["can_export_stats"] = can_export_student_stats()'

  [entries.contract]
  method = "lms.lms.api.get_user_info"
  must_return_keys = ["can_export_stats", "is_docente", "welcome_video_seen"]

  [entries.visibility]
  subject = "pagina export statistiche studenti"
  allow = ["Gestore"]
  deny = ["Student", "Docente", "Valutatore"]

  [entries.checks]
  backend = "apps/os_lms/os_lms/os_lms/tests/test_role_flags.py"
  e2e = "cypress/e2e/oslms/visibility/student-stats-export.cy.js"
```

**C — flusso funzionale critico** (`flows.toml`), forma diversa, passi in linguaggio naturale:

```toml
[[entries]]
id = "student-enrollment-and-first-lesson"
title = "Uno studente si iscrive a un corso e completa la prima lezione"
layer = "flow"
confidence = "high"
actor = "studente"
steps = [
  "apre un corso pubblicato dalla lista corsi",
  "clicca l'iscrizione e viene portato alla prima lezione",
  "segna la lezione come completata",
  "il progresso del corso risulta aggiornato al ritorno sulla pagina corso",
]
intent = """
Percorso minimo che uno studente deve poter completare. Si rompe se cambiano il
contratto di LMS Enrollment, il calcolo del progresso, o l'ordinamento forzato
delle lezioni (enforce_lesson_order, personalizzazione os_lms)."""

  [entries.checks]
  e2e = "cypress/e2e/oslms/flows/enrollment.cy.js"
```

**D — gli attori** (`actors.toml`), letti sia dai test backend sia dal seeding E2E:

```toml
[actors.gestore]
email = "e2e-gestore@oslms.test"
roles = ["Gestore", "Moderator", "Docente", "Course Creator", "Batch Evaluator"]
note = """
Gestore non viene MAI assegnato da solo: è sempre il bundle completo (memoria di
progetto gestore-role-bundle). Un utente con solo Gestore non esiste in produzione;
testarlo darebbe falsi allarmi su gate che in realtà passano per Moderator."""

[actors.valutatore]
email = "e2e-valutatore@oslms.test"
roles = ["LMS Student"]
scoped = { batch = "E2E-batch-01" }   # ruolo per-batch, via campo valutatori su LMS Batch
```

### 6.4 Il doppio uso di `data-test`

Nella SPA esiste oggi **un solo** attributo `data-test`, e Cypress seleziona per testo (`button:contains("...")`). Si introducono attributi `data-test` **solo sugli elementi censiti** (stima: 30-40).

L'attributo fa **doppio servizio**, ed è la ragione per cui conviene più di quanto sembri:

1. è il **selettore** per Vitest e Cypress, stabile rispetto alle traduzioni;
2. è l'**ancora** per il drift detector — una stringa unica che nessun refactoring dell'upstream produrrebbe spontaneamente.

Conseguenza: se un merge riscrive il componente, l'attributo sparisce e il detector lo segnala in due secondi, **anche se la regola di visibilità fosse per caso sopravvissuta**. Diventa un sensore di "questo file è stato riscritto sotto i miei piedi", che è esattamente l'evento oggi scopribile solo ritestando a mano.

---

## 7. Componente 2 — Drift detector

**File:** `scripts/check_customizations.py`. Non esegue codice applicativo: è grep strutturato sull'inventario.

### 7.1 Controlli

| # | Controllo | Cosa intercetta |
| --- | --- | --- |
| C1 | ogni `anchor` esiste ancora nel suo `file` | la riga ripulita dall'upstream |
| C2 | ogni `file` citato esiste ancora | componente rinominato o spostato |
| C3 | ogni marcatore `OSLMS-CUSTOM` nel codice ha una voce in inventario | personalizzazioni non censite |
| C4 | ogni percorso in `checks:` punta a un file esistente | voci censite che nessuno verifica |

### 7.2 Output

Doppio: tabella leggibile a terminale, e JSON su `--json` per il consumo da parte dell'agente.

```json
{
  "generated_at": "2026-09-18T10:00:00",
  "entries_total": 92,
  "findings": [
    {"id": "course-card-admin-gate", "check": "C1", "severity": "error",
     "file": "frontend/src/components/CourseCardOverlay.vue",
     "anchor": "Boolean(user.data?.is_docente)",
     "message": "anchor non trovata nel file"}
  ]
}
```

Exit code `0` se nessun finding di severità `error`, `1` altrimenti: è usabile direttamente come step di CI. Tempo di esecuzione: secondi, senza Docker e senza sito Frappe.

---

## 8. Componente 3 — Le tre suite di test

### 8.1 Backend Frappe — "ruolo → flag/permesso"

**Dove:** `apps/os_lms/os_lms/os_lms/tests/`. Framework `frappe.tests.UnitTestCase`, già in uso nel progetto.

Un fixture crea un utente per ciascun attore di `actors.toml`; ogni test fa `frappe.set_user(...)` e verifica il payload.

```python
def test_gestore_receives_export_flag(self):
    frappe.set_user(self.actors["gestore"])
    info = get_user_info()
    self.assertTrue(info["can_export_stats"])
    self.assertTrue(info["is_docente"])

def test_student_never_receives_export_flag(self):
    frappe.set_user(self.actors["studente"])
    self.assertFalse(get_user_info()["can_export_stats"])
```

Copertura attesa: per ognuna delle 37 funzioni di override, le chiavi che devono essere presenti nel payload (`contract.must_return_keys`) più le regole di gating dichiarate. Sono i test che rilevano un aggiornamento upstream che riscrive la funzione originale facendo perdere l'aggancio dell'override.

### 8.2 Vitest — "flag → DOM"

**Dove:** `frontend/src/tests/oslms/`. Stessa forma dei 31 test esistenti in `frontend/src/tests/`.

```ts
const mountFor = (flags) => mount(CourseCardOverlay, {
    global: { provide: { $user: { data: flags } }, mocks: { __: (s) => s } },
})

it.each(['is_moderator', 'is_docente'])('mostra il menu admin con %s', (flag) => {
    expect(mountFor({ [flag]: true }).find('[data-test="course-admin-menu"]').exists()).toBe(true)
})

it('nasconde il menu admin allo studente e al valutatore', () => {
    expect(mountFor({ is_student: true }).find('[data-test="course-admin-menu"]').exists()).toBe(false)
    expect(mountFor({ is_valutatore: true }).find('[data-test="course-admin-menu"]').exists()).toBe(false)
})
```

Girano nella CI già configurata (`frontend-tests.yml`), in secondi, senza sito.

### 8.3 Cypress — seeding, smoke per ruolo, flussi

**Dove:**
- `cypress/e2e/oslms/visibility/` — una spec per pagina; cicla sugli attori e verifica presenza/assenza dei selettori censiti in `visibility`.
- `cypress/e2e/oslms/flows/` — i percorsi funzionali critici di `flows.toml`.

**Il pezzo nuovo è il seeding.** Un metodo whitelisted in `os_lms`:

```
os_lms.os_lms.testing.seed.seed_e2e()      # crea, idempotente, e restituisce i name creati
os_lms.os_lms.testing.seed.teardown_e2e()  # cancella SOLO i name registrati
```

Legge `actors.toml`, crea utenti, corsi, lezioni e batch necessari, e restituisce l'elenco dei `name` creati. Cypress lo invoca una volta nel `before()`. Il comando `cy.login()` esiste già in `cypress/support/commands.js:31` e va esteso per accettare un nome di attore.

**Le tre protezioni, non negoziabili:**

1. **Guardia sul sito.** Il metodo solleva eccezione se `frappe.conf.developer_mode` non è attivo, oppure se il nome del sito non è in una allowlist esplicita di siti di test. Su produzione non è invocabile.
2. **Namespace fisso.** Tutto ciò che il seed crea ha prefisso `E2E-` ed email nel dominio `@oslms.test`. Nessuna entità di test può collidere con dati reali.
3. **Cleanup solo per nome esplicito.** Il seed registra i `name` creati; la pulizia cancella **solo quelli**, uno per uno. **Mai un filtro `LIKE`, mai una condizione per campo.**

> **Perché la protezione 3 è scritta in questi termini.** Nella storia di questo progetto uno script di pulizia con filtro `LIKE "Corso %"` ha cancellato **11 corsi reali** sul sito di sviluppo, recuperati poi dal Deleted Document (memoria `test-cleanup-must-not-use-broad-filters`). Uno strumento nato per proteggere dai danni non deve poter causare il danno peggiore già subito. Lavorando su una lista di `name` prodotta dal seed, se la lista si perde il cleanup non cancella nulla invece di cancellare troppo: **fallisce in sicurezza**.

### 8.4 Chi scrive i test: l'agente li scrive, non li genera da template

I 31 test Vitest esistenti mostrano perché un generatore a template fallirebbe: ognuno ha uno stubbing su misura (`SettingsLayout.test.ts` stubba `Button`, altri inlinano `frappe-ui`, altri mockano il resource cache). Un template produrrebbe test che non montano.

L'agente legge la voce di inventario, legge il componente, e scrive il test come lo scriverebbe uno sviluppatore, con in testa un commento che tiene il legame con la voce:

```ts
// inventory: course-card-admin-gate
```

Il commento è ciò che permette al rapporto di mappare un test rosso sulla voce corrispondente.

---

## 9. Componente 4 — Il workflow agentico

### 9.1 Il guadagno principale: il diff mirato

Oggi dopo un merge occorre ritestare tutta la piattaforma perché non si sa dove guardare: la superficie da controllare è l'intero prodotto. Con l'inventario la superficie diventa **l'elenco dei file censiti**:

```bash
git diff <prima-del-merge>..HEAD -- $(elenco dei file dall'inventario)
```

Un diff su circa 50 file, non su migliaia. L'agente lo legge per intero, voce per voce, e produce un verdetto del tipo: *"la voce `course-card-admin-gate` sta in un file che l'upstream ha riscritto in 4 punti; ecco i 4 punti, ecco cosa è successo alla regola"*.

**È il passaggio da "ritestare a tappeto" a "leggere un diff mirato", ed è il valore che l'inventario produce indipendentemente dai test.**

### 9.2 `/upstream-check` — il rituale post-merge

Skill di progetto in `.claude/skills/upstream-check/` (cartella già presente, vuota).

| # | Passo | Output |
| --- | --- | --- |
| 0 | Verifica di essere su un branch di merge, mai su `develop`/`master` | rifiuta di procedere altrimenti |
| 1 | Drift detector | JSON dei findings |
| 2 | Diff mirato sui soli file censiti | voci a rischio con il diff che le riguarda |
| 3 | Suite veloci: Vitest + backend | test falliti, mappati sulle voci via commento `inventory:` |
| 4 | Suite E2E (opzionale, su richiesta esplicita) | smoke per ruolo + flussi |
| 5 | Rapporto in `docs/upstream-checks/AAAA-MM-GG-<versione>.md` | una riga per voce: intatta / persa / cambiata / test rosso |
| 6 | Riparazione assistita | un commit per voce ripristinata, sul branch, **non pushato** |
| 7 | Voce nel worklog di progetto | come da istruzioni globali del committente |

Al passo 6 le riparazioni sono indipendenti tra loro: si eseguono con **subagent in parallelo**, un agente per voce. Formato del commit:

```
fix(oslms): restore <inventory-id> after upstream merge
```

### 9.3 `/custom-add` — manutenzione corrente

Da usare quando si **scrive** una personalizzazione nuova, nella stessa sessione in cui la si scrive: aggiunge la voce all'inventario, inserisce il `data-test` se serve, e scrive il test collegato. È il meccanismo che impedisce all'inventario di invecchiare.

### 9.4 La regola che tiene in piedi il sistema

> **L'agente non può mai modificare un test per farlo passare.**

Motivazione, da non perdere: se si chiede a un agente AI di "far passare i test", l'agente **indebolisce il test** — allarga un assert, commenta un caso, aggiunge uno `.skip`. Il risultato è verde e vuoto, e ci si fida di una rete bucata. È il modo classico in cui una suite affidata a un'AI muore.

Davanti a un test rosso l'agente ha esattamente **due mosse consentite**:

- **(a)** riparare il **codice**, perché la regola dichiarata in inventario è ancora valida;
- **(b)** **fermarsi e chiedere al committente** se la regola è cambiata.

Se la regola è cambiata si aggiorna **prima l'inventario** e **poi** il test viene riscritto a partire da lì. Un test non si tocca mai direttamente: è un output, non un input.

### 9.5 Falsi positivi e fiducia nella suite

Quando l'upstream cambia legittimamente un comportamento, la voce riceve:

```toml
status = "accepted-drift"
status_since = "2026-10-05"
status_reason = "Upstream ha unificato il menu card in CourseCardMenu.vue; la regola ora vive lì."
```

Il rapporto successivo non la ripropone come errore, ma resta scritto **perché** quella regola non vale più. Una suite di cui non ci si fida viene ignorata: la gestione esplicita del drift accettato è ciò che impedisce l'accumulo di rosso cronico.

### 9.6 Dove gira cosa

| | CI (automatico) | Locale (con il committente) |
| --- | --- | --- |
| Drift detector | sì, ogni PR — è istantaneo | sì |
| Vitest | sì, già configurato | sì |
| Backend Frappe | sì, già configurato | sì |
| E2E Cypress | solo su PR di merge upstream (lento) | su richiesta |
| Diff mirato, rapporto, riparazione | no | **solo qui** |

La CI dà l'allarme, l'agente locale fa la diagnosi e la riparazione. La riparazione non ha senso su un runner: richiede il giudizio del committente.

---

## 10. Struttura dei file da creare

```
docs/customizations/          # inventario TOML (nuovo)
docs/upstream-checks/         # rapporti post-merge (nuovo)
scripts/check_customizations.py
apps/os_lms/os_lms/os_lms/testing/seed.py
apps/os_lms/os_lms/os_lms/tests/test_role_flags.py
apps/os_lms/os_lms/os_lms/tests/test_api_contracts.py
frontend/src/tests/oslms/*.test.ts
cypress/e2e/oslms/visibility/*.cy.js
cypress/e2e/oslms/flows/*.cy.js
.claude/skills/upstream-check/SKILL.md
.claude/skills/custom-add/SKILL.md
```

Nessuno di questi percorsi è toccato dall'upstream.

---

## 11. Piano di adozione in fasi

Ogni fase è utile da sola e il lavoro può fermarsi lì.

| Fase | Contenuto | Stima |
| --- | --- | --- |
| **0** | Inventario dei 49 innesti `OSLMS-CUSTOM` + drift detector + `/upstream-check` ridotto (drift, diff mirato, rapporto). **Nessun test scritto.** | 1 sessione |
| **1** | Inventario dei gate per ruolo + test backend e Vitest scritti dall'agente + riparazione assistita | 2-3 sessioni |
| **2** | Attributi `data-test` + seeding + smoke E2E di visibilità per ruolo | 2 sessioni |
| **3** | Flussi funzionali E2E (iscrizione, lezione, quiz, certificato) | 2-3 sessioni |
| **4** | Wiring CI completo + affinamento della skill sui primi merge reali | 1 sessione |

Le stime sono indicative e da verificare sulla Fase 0.

**La Fase 0 risolve metà del problema senza scrivere un test.** Il requisito 2 del committente ("se in un file faccio delle modifiche mie poi il file aggiornato mi ripulisce tutto") è un problema di rilevamento testuale: inventario più detector lo chiudono in una sessione. I test servono per il requisito 3 ("il bottone ha mantenuto le regole di visibilità"), che è più lento da costruire. A parità di tempo disponibile, la Fase 0 ha il rapporto valore/costo più alto.

---

## 12. Rischi e mitigazioni

| Rischio | Mitigazione |
| --- | --- |
| L'inventario invecchia e copre un perimetro parziale | Controllo C3 del detector (marcatori non censiti) + skill `/custom-add` da usare in fase di scrittura |
| L'agente indebolisce i test per farli passare | Regola §9.4 scritta nella skill: due sole mosse consentite, mai toccare un test |
| Falsi positivi che erodono la fiducia | `data-test` al posto dei selettori testuali (D6) + `status: accepted-drift` documentato |
| Il seeding danneggia dati reali | Le tre protezioni di §8.3, con cleanup per nome esplicito |
| E2E instabile e lento in CI | E2E fuori dalla CI ordinaria: solo su PR di merge upstream e su richiesta locale |
| Le voci a bassa confidenza restano non riviste | Il rapporto elenca in testa le voci `confidence: low` ancora non confermate |

---

## 13. Riferimenti

**Memorie di progetto rilevanti** (`~/.claude/projects/-Users-riccardo-Documents-Progetti-os-lms/memory/`):

- `upstream-merge-maintenance-strategy` — i tre livelli e dove va ogni tipo di personalizzazione
- `gestore-role-bundle` — Gestore non è mai assegnato da solo
- `docente-global-instructor-role` — la SPA gatea sui flag, non sui permessi doctype
- `valutatore-role-scoped-per-batch` — ruolo per-batch, modello a veto
- `test-cleanup-must-not-use-broad-filters` — l'incidente che motiva §8.3
- `courseform-sectioned-custom-grafts`, `upstream-merge-v2-58-0-2026-07` — casi reali di innesti da riapplicare dopo un merge

**File chiave del repository:**

- `docs/OS_LMS_OVERRIDES.md` — mappa completa di cosa `os_lms` fa a `lms`; è la base di partenza per compilare `api-overrides.toml`
- `frontend/vite.config.js` — plugin `osOverrideTheme`
- `apps/os_lms/os_lms/os_lms/override_api.py`, `override_utils.py` — le 37 funzioni di override
- `cypress/support/commands.js` — `cy.login` da estendere
- `.github/workflows/ci.yml`, `frontend-tests.yml`, `ui-tests.yml` — CI esistente
