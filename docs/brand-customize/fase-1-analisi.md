# Fase 1 — Pulizia e form: rapporto di analisi

**Data:** 2026-11-04 · **Piano:** [PIANO.md](PIANO.md) §5, Fase 1
**Stato:** analisi fatta, **STOP: in attesa dell'OK** prima di scrivere codice.
**Regola di lavoro:** nessun commit; modifiche tenute e provate **in locale**
(Docker `dev-elite-frappe-1`, sito `lms.localhost`).

## 1. Obiettivo della fase

Rendere il form attuale corretto e comprensibile, **senza cambiare l'aspetto
della piattaforma**:

- togliere i campi senza effetto;
- dare a ogni campo un'etichetta e una descrizione vere (variabile e dove si vede);
- mostrare nel campo vuoto il valore standard;
- aggiungere il campo «Modalità attiva» (in questa fase fisso su Esperto,
  perché i campi di oggi sono variabili frappe-ui scritte direttamente);
- preparare `_build_css` per le fasi successive (valori non salvati per
  l'anteprima, modalità);
- patch che pulisce i dati.

## 2. Stato locale verificato

| Cosa | Esito |
|---|---|
| Container | `dev-elite-frappe-1` attivo da 8 ore, sito `lms.localhost`. |
| CLI `bench` | Non funziona (`ModuleNotFoundError: bench`), come già noto. Test, query e migrate si lanciano con `../env/bin/python` da `/home/frappe/bench-data/frappe-bench/sites`. |
| Valori salvati in locale | `surface_gray_10 = #292929`, 5 colori `login_*`, `theme = light`. Tutti gli altri vuoti. |
| Test attuale | `test_branding_light_only`: 4 test, **OK**. |
| Meta del doctype | Allineata al JSON (il campo `mode` non esiste ancora, come atteso). |

## 3. I campi di oggi, uno per uno

Valori standard letti dal CSS compilato della SPA
(`lms/public/frontend/assets/index-BZlkCQpS.css`).

| Campo | Variabile | Valore standard | Dove si vede davvero | Proposta |
|---|---|---|---|---|
| `theme` | — | — | nessun effetto (obsoleto) | **eliminare** |
| `company_primary` | `--color-company-primary` | non definita (trasparente) | righe di `.os-list-view` e `.os-table-view` | tenere, etichetta «Righe di tabelle ed elenchi» |
| `company_secondary` | `--color-company-secondary` | — | nessun uso nella SPA | **eliminare** |
| `app_main_color`, `app_secondary_color` | — | — | app mobile (`get_instance_info`) | tenere, sezione «App mobile» |
| `surface_base` | `--surface-base` | `oklch(1 0 0)` | sfondo principale delle pagine | descrizione corretta (oggi dice `--surface-white`) |
| `surface_sidebar` | `--surface-sidebar` | `oklch(.979 0 0)` | sfondo della barra laterale | descrizione corretta (oggi `--surface-menu-bar`) |
| `surface_elevation_1` | `--surface-elevation-1` | `oklch(1 0 0)` | card | descrizione corretta (oggi `--surface-card`) |
| `surface_elevation_2` | `--surface-elevation-2` | `oklch(1 0 0)` | finestre modali e menu a tendina | descrizione corretta (oggi `--surface-modal`) |
| `surface_elevation_3` | `--surface-elevation-3` | `oklch(1 0 0)` | voce selezionata (es. barra laterale) | descrizione corretta (oggi `--surface-selected`) |
| `surface_gray_1` | `--surface-gray-1` | `oklch(.979 0 0)` | sfondi tenui, passaggio del mouse nella barra strumenti dell'editor | descrizione |
| `surface_gray_2` | `--surface-gray-2` | `oklch(.964 0 0)` | campi di inserimento, intestazioni degli elenchi, editor, tasti `kbd`, cursore della barra di scorrimento | descrizione con l'avviso «usata in molti punti» |
| `surface_gray_3` | `--surface-gray-3` | `oklch(.946 0 0)` | passaggio del mouse, selezione nell'editor | descrizione |
| `surface_gray_10` | `--surface-gray-10` | `oklch(.205 0 0)` | pulsanti principali scuri e un riquadro della barra laterale; **il passaggio del mouse resta grigio** (`--surface-gray-9`) | descrizione corretta (oggi `--surface-gray-7`) con l'avviso |
| `ink_gray_5` | `--ink-gray-5` | `oklch(.586 0 0)` | testi secondari, contatori, segnaposto | descrizione |
| `ink_gray_6` | `--ink-gray-6` | `oklch(.439 0 0)` | testi descrittivi | descrizione |
| `ink_gray_7` | `--ink-gray-7` | `oklch(.341 0 0)` | testo del corpo **e** della barra laterale | descrizione con l'avviso |
| `ink_gray_8` | `--ink-gray-8` | `oklch(.205 0 0)` | voci della barra laterale, testi dei grafici, binario della barra di scorrimento | descrizione |
| `ink_gray_9` | `--ink-gray-9` | `oklch(.168 0 0)` | titoli, righe delle tabelle | descrizione |
| `ink_gray_10` | `--ink-gray-10` | **non esiste in frappe-ui v2** | solo l'icona del pulsante della barra strumenti dell'editor lezioni (`main.css`) | tenere, descrizione onesta |
| `ink_base` | `--ink-base` | `oklch(1 0 0)` | testo dei pulsanti pieni **e** pallini degli elenchi e testo delle card di esito | descrizione corretta (oggi `--ink-white`) con l'avviso |
| `outline_gray_1` | `--outline-gray-1` | `oklch(.946 0 0)` | bordi standard | descrizione |
| `outline_elevation_2` | `--outline-elevation-2` | `oklch(.946 0 0)` | bordi di finestre modali e menu | descrizione corretta (oggi `--outline-gray-modals`) |
| `color_sidebar_menu` | `--color-sidebar-menu` | — | nessun CSS la legge | **eliminare** |
| `color_menu_bar` | `--color-menu-bar` | — | nessun CSS la legge | **eliminare** |
| `login_*` (6) | `--login-*` | standard Frappe | pagina di login e pagine collegate | tenere, sezione «Pagina di login» |

## 4. Modifiche previste, file per file

### 4.1 `brand_customize.json`

- Eliminati `theme`, `company_secondary`, `color_sidebar_menu`, `color_menu_bar`
  e le colonne/sezioni rimaste vuote.
- Nuovo campo `mode` (Select, valori interni `Base` / `Advanced` / `Expert`,
  etichetta «Active Mode»), predefinito `Expert`, **di sola lettura in questa
  fase**, con la descrizione «Le modalità Base e Avanzata arriveranno nelle
  prossime versioni».
- Sezioni riordinate:
  1. **Modalità attiva**
  2. **Esperto — Superfici** (`surface_*`)
  3. **Esperto — Testi** (`ink_*`)
  4. **Esperto — Bordi** (`outline_*`)
  5. **Esperto — Tabelle** (`company_primary`)
  6. **Pagina di login** (`login_*`)
  7. **App mobile** (`app_*`)
- In Esperto l'**etichetta è il nome della variabile** (`--surface-base`) e la
  **descrizione dice dove si vede** (colonna «Dove si vede» del §3). Testi in
  inglese nel JSON, traduzione italiana in `apps/os_lms/os_lms/translations/it.csv`.

### 4.2 `branding.py`

- Tolte le 4 voci da `FIELD_TO_CSS_VAR`.
- `_build_css(values: dict | None = None)`: senza argomento legge il doc come
  oggi; con un dizionario usa quei valori (servirà all'anteprima). Il risultato
  per l'Esperto è **identico a oggi**.
- La modalità entra nella costruzione del CSS (`_theme_declarations(values,
  mode)`): in questa fase gestisce solo `Expert`. I colori di login e dell'app
  restano **fuori dalle modalità**: valgono sempre.
- Nuovo endpoint `get_token_defaults()` (solo System Manager): legge dal file
  `lms/www/_lms.html` il foglio di stile compilato della SPA, ne estrae i
  valori standard del tema chiaro e li restituisce, con cache. Serve ai
  placeholder ora e sarà la base dell'elenco completo della modalità Esperto
  (Fase 4), **senza plugin di build** (risolve l'alternativa lasciata aperta
  nel piano §4.6).

### 4.3 `brand_customize.js`

- Placeholder del campo vuoto = valore standard (da `get_token_defaults`).
- Import JSON: i campi eliminati finiscono già tra gli «ignorati» del messaggio
  esistente; nessuna modifica di formato in questa fase.
- Il pulsante ✕ e «Reset Colors» restano invariati.

### 4.4 Patch `os_lms.patches.v0_0_10.brand_customize_cleanup` (post_model_sync)

- Imposta `mode = Expert`.
- Cancella da `tabSingles` le righe dei 4 campi eliminati (in locale c'è solo
  `theme = light`; su Elite, dal report, nessuno dei 4 è valorizzato).
- Svuota la cache del CSS di brand.
- Idempotente: rieseguita non cambia nulla.

### 4.5 `frontend/src/styles/theme/elite/main.css`

- `.card`, `.card-success`, `.card-failure`, `.ProseMirror`,
  `.os-list-view` (angoli): `0.5rem` → `var(--radius-4)` (stesso valore, 8px).
  Nessun cambiamento visivo.

### 4.6 Test

- `test_branding_light_only`: invariati i 4 test; aggiunti «i campi eliminati
  non compaiono più nel CSS», «`_build_css` con un dizionario non legge il doc»,
  «i colori di login valgono in ogni modalità».
- Nuovo `test_brand_customize_cleanup_patch`: crea le righe dei campi
  eliminati, esegue la patch, controlla l'esito e annulla tutto con
  `frappe.db.rollback()`.
- `test_get_token_defaults`: valori estratti per almeno i 18 token del form;
  accesso negato a chi non è System Manager.

## 5. Decisioni per questa fase

| # | Domanda | Proposta |
|---|---|---|
| A1 | Il campo «Modalità attiva» si vede già in Fase 1? | Sì, ma **di sola lettura** su Esperto: le modalità Base e Avanzata non hanno ancora campi. |
| A2 | La modalità Esperto in Fase 1 usa i campi di oggi o già la tabella con tutte le variabili? | **I campi di oggi.** La tabella completa arriva in Fase 4 con una seconda patch che sposta i valori. |
| A3 | Colori di login e app mobile dipendono dalla modalità? | **No**, valgono sempre: non sono variabili della piattaforma. |
| A4 | `ink_gray_10` (variabile inesistente in frappe-ui, colora una sola icona) si elimina? | **Si tiene** con una descrizione onesta: ha un effetto, anche se minimo. |
| A5 | Nome della patch: `v0_0_10`? | Sì, segue `v0_0_9`. |

## 6. Verifiche previste

1. Test con il Python del container (`test_branding_light_only`, patch,
   `get_token_defaults`) e suite os_lms.
2. Migrate locale (`SiteMigration().run("lms.localhost")`) per applicare JSON e
   patch, poi `translate.clear_cache()` per le nuove righe di `it.csv`.
3. Desk `http://lms.localhost:8000/app/brand-customize`: sezioni, etichette e
   descrizioni italiane, placeholder, campo modalità di sola lettura.
4. SPA prima e dopo: confronto del CSS servito da `brand_css` (deve essere
   identico, a parte le 4 variabili eliminate e vuote) e controllo visivo di
   Home, sidebar e pulsanti nel Browser pane.
5. Nessun commit.

## 7. Stima

1–1,5 giornate, come da piano.
