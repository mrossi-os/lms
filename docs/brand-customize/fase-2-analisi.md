# Brand Customize — Fase 2: anteprima live (analisi)

Data: 2026-11-04 · Stato: **decisioni B1–B6 approvate e implementate in locale (non committate)** ·
Piano generale: [PIANO.md](PIANO.md) §4.5 · Fase precedente: [fase-1-analisi.md](fase-1-analisi.md)

Vincoli: niente commit, modifiche e test solo sul sito Docker locale.

## 1. Obiettivo

Nella pagina Desk *Brand Customize* l'utente vede un'anteprima delle pagine principali
della piattaforma, che si aggiorna mentre modifica i colori, **prima di salvare**.
Per ora le modifiche riguardano solo la modalità Esperto e i colori della login.
Base e Avanzata arrivano in Fase 3 e useranno la stessa anteprima senza modificarla.

## 2. Cosa è emerso dall'analisi

| # | Verifica | Esito |
|---|---|---|
| 1 | Si può mostrare la SPA `/lms` in un iframe dentro il Desk? | **Sì.** Stessa origine. In locale non c'è `X-Frame-Options`; staging manda `SAMEORIGIN`, che lo consente. La CSP è solo *Report-Only*: se un giorno diventa bloccante, `frame-ancestors` deve includere `'self'`. |
| 2 | La pagina `/login` si può mostrare in anteprima? | **No**, se l'utente è già loggato: Frappe lo reindirizza sempre (`lms/www/login.py`; anche `?redirect-to=login` viene trasformato in URL completo). |
| 3 | Alternativa per la login | `/update-password` risponde 200 con lo stesso aspetto e usa tutte e 6 le variabili `--login-*`. Mancano logo, titolo e pulsante "link via e-mail". |
| 4 | Come cambiare il CSS dentro l'iframe | La SPA crea `<link href=/api/method/os_lms.os_lms.branding.brand_css>` in `frontend/src/main.js`; le pagine web lo hanno in `templates/base.html`. Si disattiva quel `<link>` e si inserisce `<style id="os-brand-preview">` con il CSS non salvato. Il Desk che ospita l'anteprima non viene toccato. |
| 5 | Stesso CSS del salvataggio? | **Sì.** `_build_css(values)` accetta già un dizionario di valori (preparato in Fase 1). Anteprima e foglio salvato usano lo stesso codice: l'anteprima non può divergere da ciò che si ottiene salvando. |
| 6 | Tema e contrasto | Tema e alto contrasto stanno nel `localStorage` (chiavi `theme`, `themePreference` e quella di `oslms/utils/contrast.ts`), condiviso tra Desk e iframe perché stessa origine. Il brand vale solo per il tema chiaro senza alto contrasto. Se l'amministratore usa il tema scuro, l'iframe mostrerebbe i colori standard e l'anteprima sembrerebbe rotta. **Soluzione:** nell'iframe si impostano `data-theme="light"` e si toglie `data-contrast` direttamente sull'`<html>`, con un `MutationObserver` che li mantiene. Il `localStorage` non viene scritto, quindi le preferenze dell'utente restano intatte. |
| 7 | Effetti collaterali aprendo una lezione | **Nessuno per chi non è iscritto.** In `pages/Lesson.vue`: `markProgress` (riga ~682), `startTimer` (~1172), il tracciamento video (~1157) e gli appunti (~912) escono subito se manca `lesson.data.membership`. L'iscrizione (`enrollStudent`, ~1256) parte solo con un click, bloccato dall'anteprima. **Rischio residuo:** se l'amministratore è iscritto al corso scelto, la sola apertura avvierebbe il timer di permanenza e segnerebbe la lezione come completata. Mitigazione: l'endpoint sceglie un corso a cui l'utente corrente **non** è iscritto. |
| 8 | Link, form, pulsanti nell'iframe | Si bloccano in fase di *capture* sulla `window` dell'iframe: `click`, `auxclick`, `dblclick`, `submit`, `keydown` di Invio/Spazio, più `window.open`. Hover e scroll restano attivi, così si vedono gli stati hover. Il blocco ferma anche la navigazione del router Vue (che parte da un click). |
| 9 | Test automatici e2e | Upstream è passato da Cypress a **Playwright** (`playwright.config.ts`, cartella `e2e/`, `yarn test-local` = `playwright test --ui`). Resta un solo `cypress/e2e/simulations.cy.js`. I browser Playwright **non sono installati** su questo Mac e il setup fa login con utente e password presi da variabili d'ambiente. |
| 10 | Peso | Ogni scheda carica la SPA intera (~1–2 s la prima volta). Caricare tutte e 7 le schede insieme sarebbe lento: vedi §3.3. |

## 3. Proposta tecnica

### 3.1 Server — `apps/os_lms/os_lms/os_lms/branding.py`

1. **`brand_css_preview(values: str) -> str`**, whitelisted, solo POST, `frappe.only_for("System Manager")`.
   - Riceve il JSON dei valori del form non salvato.
   - Tiene solo i campi noti (`FIELD_TO_CSS_VAR` + `mode`) e li valida (punto 3).
   - Restituisce `_build_css(values)`.
   - Non usa né tocca la cache Redis del foglio salvato.
2. **`get_preview_targets() -> dict`**, solo System Manager. Restituisce gli URL delle 7 schede, con contenuto reale scelto dal server:

   | Scheda | URL | Contenuto |
   |---|---|---|
   | Home | `/lms` | — |
   | Elenco corsi | `/lms/courses` | — |
   | Pagina corso | `/lms/courses/<corso>` | primo corso pubblicato **con almeno una lezione** e **senza iscrizione** dell'utente corrente |
   | Lezione | `/lms/courses/<corso>/learn/1-1` | stesso corso |
   | Dashboard classe | `/lms/batches/<classe>` | prima classe pubblicata |
   | Statistiche | `/lms/statistics` | — |
   | Login | `/update-password` | — |

   Se manca un contenuto (nessun corso o classe), la scheda appare disattivata con il motivo,
   ad esempio "Nessun corso pubblicato con lezioni".
3. **Validazione dei valori** (`_validate_color_value`). Un valore è accettato solo se
   - non contiene `; { } < > \` né `/*`;
   - non supera i 100 caratteri.

   Restano validi `#hex`, `rgb()`, `oklch()`, `color-mix()`, `var(--x)` e i nomi dei colori.
   Oggi **nessun controllo** impedisce di salvare per esempio `red; } body {display:none`: chi ha
   accesso alla pagina potrebbe rompere tutta la piattaforma con un campo. La stessa funzione va
   usata anche in `BrandCustomize.validate()` (`brand_customize.py`, oggi vuoto), così l'errore
   compare al salvataggio, con il nome del campo. (Decisione **B4**.)

### 3.2 Desk — `brand_customize.js`

Si aggiunge al file esistente un blocco "preview", senza toccare Export/Import/Reset/✕.

- **Pannello affiancato a destra**
  - Largo circa il 45% dello schermo, fisso durante lo scroll.
  - Il form si restringe a sinistra, così campi e anteprima si vedono insieme.
  - Pulsante "Anteprima" nella barra per aprirlo e chiuderlo. La scelta resta salvata in `localStorage`, con una chiave dedicata.
  - Sotto i 1200 px di larghezza il pannello si apre a schermo intero con un pulsante "Chiudi".
- **Contenuto del pannello**
  - Schede: Home · Elenco corsi · Pagina corso · Lezione · Dashboard classe · Statistiche · Login.
  - Interruttore Desktop / Telefono (iframe largo 375 px).
  - Etichetta "Anteprima — modifiche non salvate", con un pallino quando il form è *dirty*.
- **Aggiornamento**
  - A ogni cambio di un campo colore o di `mode` parte una chiamata a `brand_css_preview`, con debounce di 150 ms.
  - Le risposte vecchie vengono scartate (conta solo l'ultima richiesta).
  - Il CSS va in tutte le schede già caricate.
  - Dopo il salvataggio l'anteprima resta com'è: coincide con il salvato.
- **Iframe**
  - Hanno `sandbox` **disattivato**: la SPA ha bisogno di script e cookie della stessa origine, e la protezione viene dal blocco delle interazioni del punto 8.

### 3.3 Prestazioni

- Si carica solo la scheda aperta (*lazy*).
- Le schede già aperte restano in memoria nascoste, così tornarci è immediato e ricevono comunque il CSS aggiornato.
- Massimo 7 iframe, tutti chiusi quando si chiude il pannello.

### 3.4 Traduzioni

Tutte le nuove stringhe vanno con `__()` in `apps/os_lms/os_lms/translations/it.csv`. Quelle
generiche ("Preview", "Desktop", "Phone", "Close"…) vanno con contesto `Brand Customize`, come
in Fase 1, per non cambiare la traduzione nel resto della piattaforma.

### 3.5 Fuori da questa fase

- L'evidenziazione "dove si vede questo colore" resta in **Fase 3**, come da PIANO.
- Nessun interruttore per il tema scuro (decisione **B6**).
- Conversione dei placeholder oklch → hex: piccola, la includo se c'è tempo, altrimenti resta per la Fase 3.

## 4. File toccati (previsti)

| File | Modifica |
|---|---|
| `apps/os_lms/os_lms/os_lms/branding.py` | `brand_css_preview`, `get_preview_targets`, `_validate_color_value` |
| `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.py` | `validate()` che usa `_validate_color_value` |
| `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.js` | pannello anteprima |
| `apps/os_lms/os_lms/translations/it.csv` | nuove stringhe |
| `apps/os_lms/os_lms/os_lms/tests/test_branding_preview.py` (nuovo) | test server |

Nessun file upstream (`lms/`, `frontend/src`) viene modificato: l'anteprima agisce dall'esterno
sull'iframe. Le prossime merge upstream non toccano questa funzione, salvo un cambio del `<link>`
in `main.js` o del redirect della login.

## 5. Verifiche previste

- **Test Python** (`test_branding_preview.py`):
  - il CSS dell'anteprima coincide con `_build_css` sugli stessi valori;
  - i campi sconosciuti vengono ignorati;
  - i valori pericolosi vengono rifiutati, sia nell'anteprima sia al salvataggio;
  - serve System Manager (per l'ospite: 403);
  - le schede senza contenuto risultano disattivate;
  - il corso scelto non è uno a cui l'utente è iscritto.
- Suite completa `os_lms/os_lms/tests`, esclusi i test AI (costo).
- **Prova manuale nel browser** (Browser pane, sito locale), su tutte e 7 le schede, in Desktop e Telefono:
  - un colore cambiato si vede in meno di mezzo secondo;
  - un click su un link non naviga;
  - nessuna chiamata `save_progress`/`insert` nel traffico di rete;
  - con il tema scuro attivo nel Desk, l'anteprima resta chiara e la preferenza non cambia.

## 6. Decisioni da prendere

| # | Domanda | Proposta |
|---|---|---|
| B1 | Anteprima login | **`/update-password`** (zero codice upstream). Alternativa: una pagina os_lms dedicata con logo e titolo veri, circa +0,5 g. |
| B2 | Dove sta l'anteprima | **Pannello affiancato a destra**, richiudibile. Alternativa: finestra a schermo intero (non si vedono i campi mentre si guarda). |
| B3 | Contenuto delle schede | **Scelto in automatico dal server** (primo corso o classe adatti). Un menu per scegliere il corso si può aggiungere dopo. |
| B4 | Validazione dei valori | **Sì, anche al salvataggio** (oggi un valore errato può rompere tutta la grafica). |
| B5 | Test e2e Playwright | **Ora no**: servono il download dei browser Playwright (~150 MB, `npx playwright install chromium`) e una password admin per il setup. Restano test Python + prova manuale nel browser. Lo spec si aggiunge quando si deciderà di far girare la suite e2e. |
| B6 | Tema scuro nell'anteprima | **No**: il brand vale solo per il tema chiaro, quindi lo scuro mostrerebbe solo i colori standard. |

Stima: **2–2,5 giornate**, come da PIANO. B1 con pagina dedicata: +0,5 g.

## 7. Esito dell'implementazione (2026-11-04)

- Implementata come proposta, con tre aggiustamenti emersi dalla prova nel browser:
  - il form del Desk restringe `.container` con `width` esplicita (Frappe la fissa al 100%) e nasconde la barra laterale del form (assegna, allegati, cronologia) mentre l'anteprima è aperta;
  - su schermi stretti il pannello copre il form ma non la barra laterale del Desk;
  - nella scheda Login il pulsante principale di `/update-password` (`.btn-update`) riceve la classe `.btn-login`, così mostra il colore «Pulsante» come su `/login`.
- **Problema separato trovato, non corretto:** sul Frappe locale la regola `.btn.btn-primary` del bundle web (specificità 0,2,0) prevale su `.btn-login` di `os_lms.css` (0,1,0). Il colore «Pulsante» della login quindi probabilmente non si applica neanche sul `/login` vero. Verificato e corretto lo stesso giorno (WORKLOG, Attività 29–30): il selettore in `os_lms.css` è ora `.btn.btn-primary.btn-login`.
