# Brand Customize — piano di miglioramento

**Branch:** da decidere (proposta: `feat/brand-customize-roles` da `feature/oslms`)
**Stato:** bozza del 2026-11-04, aggiornata lo stesso giorno con le indicazioni
dell'utente (tre modalità esclusive, anteprime live multipagina). **Da approvare.**
Nessuna riga di codice scritta.
**Stima complessiva:** 10–12 giornate, indicativa (dettaglio al §5).
**Fonti:** report del cliente `~/Downloads/report-variabili-elite/report-variabili-elite.md`
(audit del 27/10 su elite.overside.it), analisi del codice e ricerca web del
2026-11-04 (worklog, attività 17–21).

Modo di lavoro, come per l'Elite API: **all'inizio di ogni fase un breve
rapporto di analisi (`fase-N-analisi.md`) e uno STOP per l'OK**, poi il codice.

## 1. Cosa si costruisce

Si migliora il pannello **Brand Customize già presente nel Desk**. Non si
riducono le possibilità di personalizzazione: si aggiungono **tre modalità**,
dalla più semplice alla più completa, e un'**anteprima live** delle pagine
principali.

| Modalità | Per chi | Cosa si compila |
|---|---|---|
| **Base** | chi vuole solo applicare il proprio brand | 4 colori: principale, accento, sfondo, tinta dei grigi. Tutto il resto è calcolato. |
| **Avanzata** | chi vuole ritoccare parti precise | ~45 ruoli con nomi chiari per area («Testo della barra laterale», «Pulsante principale»), ognuno cambia solo la sua area. Copre **tutte le 41 variabili colore** trovate a schermo dal report (oggi il form ne copre 19 con effetto). |
| **Esperto** | chi conosce frappe-ui | **tutte le variabili** definite dai fogli di stile della piattaforma (il report ne conta 859, escluse quelle interne di Tailwind): colori, raggi, ombre, player video. Elenco con ricerca e filtri. |

**È attiva una sola modalità alla volta** (deciso il 04/11): o Base, o
Avanzata, o Esperto. I valori delle altre due restano salvati ma **non vengono
applicati**. Passando a un'altra modalità il form propone di partire dai colori
di quella precedente (§4.1). In ogni modalità un campo vuoto vale il colore
standard di frappe-ui, e il campo lo mostra.

Differenza da tenere presente: **Avanzata** controlla le **aree** (il testo
della barra laterale separato dal testo della pagina); **Esperto** controlla
**ogni variabile**, ma una variabile cambia ovunque sia usata, come oggi.

**Anteprima live** (requisito principale): schede con Home, Elenco corsi,
Pagina corso, Lezione, Dashboard classe, Statistiche, Login; le pagine si
aggiornano mentre si sceglie il colore, **prima di salvare**, in tutte e tre le
modalità.

## 2. Situazione attuale (fatti verificati)

| # | Fatto | Dove |
|---|---|---|
| F1 | Il form espone 22 campi del tema mappati 1:1 su token frappe-ui della scala neutra (`--surface-gray-*`, `--ink-gray-*`, `--outline-*`). | `os_lms/branding.py` `FIELD_TO_CSS_VAR` |
| F2 | I token sono condivisi da molti elementi: nel sorgente SPA `ink-gray-5` 398 usi, `ink-gray-9` 339, `ink-gray-7` 269, `surface-gray-2` 176 (input, kbd, intestazioni liste, editor, scrollbar). | `frontend/src` |
| F3 | Esempi di accoppiamento: `--ink-base` è il testo dei pulsanti pieni **e** il colore dei marcatori degli elenchi e del testo delle card di esito; `--ink-gray-7` è sia il testo della sidebar sia il testo del corpo; `--surface-gray-10` è il pulsante principale **e** un riquadro della sidebar. | `frappe-ui Button.vue:84`, `theme/elite/main.css`, `AppSidebar.vue` |
| F4 | Hover e pressione del pulsante principale usano `--surface-gray-9`/`-8`, che non sono nel form: un pulsante ricolorato torna grigio al passaggio del mouse. | `frappe-ui Button.vue:84` |
| F5 | Campi senza effetto: `color_sidebar_menu`, `color_menu_bar` (nessun CSS li legge), `company_secondary` (non usato dalla SPA), `theme` (dichiarato obsoleto). | grep su `frontend/src` e `apps/os_lms` |
| F6 | Descrizioni con nomi vecchi: «Surface Gray 10 (CTA)» → `--surface-gray-7`, «Surface Base» → `--surface-white`, «Ink Base» → `--ink-white`, ecc. | `brand_customize.json` |
| F7 | `--color-company-primary` (righe di `.os-list-view` e `.os-table-view`) esiste nella SPA solo se compilato nel form; il valore in `os_lms.css` vale solo per le pagine web/login. | `os_lms.css`, `theme/elite/main.css:45-51` |
| F8 | I grafici (`AxisChart`/`DonutChart` di frappe-ui) usano la palette di default di ECharts perché nessuna pagina passa `config.colors`; assi e legende usano già i token. | `Statistics.vue`, `CourseDashboard.vue`, `AdminBatchDashboard.vue`, `ProgramProgressSummary.vue`, `VideoStatistics.vue`; `frappe-ui eChartOptions.ts:32` |
| F9 | Il brand si applica solo al tema chiaro (`:root:not([data-theme="dark"]):not([data-contrast="more"])`); le variabili `--login-*` valgono in ogni tema. Test: `test_branding_light_only.py`. | `branding.py` |
| F10 | Il CSS di brand è servito da `branding.brand_css` (cache Redis, invalidata al salvataggio), caricato nel Desk (`app_include_css`), nelle pagine web (`templates/base.html`) e nella SPA (`main.js`, come `<link>`). | `hooks.py`, `base.html`, `main.js` |
| F11 | Sul branch attuale frappe-ui è `1.0.0-beta.29`: i token sono colori veri (oklch). Su `master` frappe-ui è 0.1.x e i token sono canali RGB grezzi (`"248 248 248"`). | `frontend/package.json`, memoria progetto |
| F12 | Esistono già: pulsante ✕ per svuotare un campo, Reset Colors, Export/Import JSON. | `brand_customize.js` |
| F13 | Il Desk non carica il CSS della SPA: l'elenco dei token frappe-ui non è disponibile nella pagina del form, va fornito a parte (§4.6). | `hooks.py` |

## 3. Decisioni

### Prese

| # | Decisione | Deciso il |
|---|---|---|
| D1 | Si migliora il **pannello Desk esistente**. | 04/11 |
| D2 | **Tre modalità**: Base, Avanzata, Esperto (tutte le variabili presenti). **Una sola attiva alla volta**: non si combinano. | 04/11 |
| D3 | **Anteprima live delle pagine principali**, funzionante in tutte le modalità: è il requisito più importante. | 04/11 |

### Da prendere (con proposta)

| # | Domanda | Proposta |
|---|---|---|
| D4 | Il brand continua a valere **solo per il tema chiaro**? | Sì (scuro e alto contrasto restano standard). Scriverlo nel pannello. |
| D5 | Cambiare modalità **cancella** i valori delle altre? E si può partire dai colori della modalità precedente? | Non si cancella nulla: i valori restano salvati ma non applicati. Al cambio, il form chiede «Vuoi partire dai colori attuali?» e copia i valori risultanti dove c'è una corrispondenza (§4.1). |
| D6 | Il contrasto insufficiente **blocca** il salvataggio? | No: avviso accanto al campo e riepilogo al salvataggio. |
| D7 | Dove vivono i **preset**? | Nuovo doctype `Brand Preset` (nome, modalità, valori JSON); Export/Import JSON restano. |
| D8 | I campi attuali a gradino e quelli senza effetto (F5)? | I gradini passano nella modalità **Esperto** (stesso token, nessun dato perso); quelli con un ruolo corrispondente vengono spostati dalla patch (es. `surface_gray_10` → «Pulsante principale», `company_primary` → «Righe tabelle»). `color_sidebar_menu`, `color_menu_bar`, `company_secondary`, `theme` eliminati. |
| D9 | Le **immagini «dove si vede»** vengono dal report? | Non servono più come immagini fisse: l'anteprima evidenzia dal vivo gli elementi del campo selezionato (§4.5). |
| D10 | Tipografia ed Editor.js/highlight.js/toast in Base e Avanzata? | Fuori da Base e Avanzata; le loro variabili, dove esistono (es. Plyr), sono comunque modificabili in **Esperto**. I colori scritti fissi nei loro CSS restano fuori ambito. |
| D11 | Su quale branch e quando su `master`? | Sviluppo su `feature/oslms` (frappe-ui v2); il porting su `master` (token RGB, F11) è un lavoro separato. |
| D12 | Onboarding «Come hai conosciuto Frappe Learning?» con logo Frappe? | Nome e logo del brand presi dalle impostazioni di branding di LMS. |

## 4. Progetto tecnico

### 4.1 Le tre modalità e le variabili

Tutte e tre le modalità finiscono sulle **stesse variabili esistenti di
frappe-ui**; cambia solo da dove arriva il colore. Il server genera il CSS
**solo per la modalità attiva** (campo `mode` del doctype); i campi delle altre
modalità vengono ignorati.

```
BASE       4 colori ─► ruoli calcolati ─► variabili frappe-ui (globali o nell'area)
AVANZATA             ruoli compilati  ─► variabili frappe-ui (globali o nell'area)
ESPERTO                                   variabili frappe-ui scritte direttamente
```

- **Base.** Salva 4 variabili proprie (`--os-brand-*`) che da sole non colorano
  nulla. Da queste il CSS calcola i ruoli (`--os-button-primary-bg`, hover,
  voce attiva, grafici…), e i ruoli vengono assegnati alle variabili frappe-ui:
  **ovunque** quando la variabile ha un solo significato (es. `--surface-base`
  per lo sfondo pagina), **solo dentro l'area** quando è condivisa (es.
  `--surface-gray-10` solo nei pulsanti principali, §4.2).
- **Avanzata.** Stesso meccanismo, ma ogni ruolo lo compila la persona. Un ruolo
  vuoto vale il colore standard; le tonalità secondarie (hover, pressione) se
  vuote si calcolano dal ruolo principale della stessa voce.
- **Esperto.** Nessuna variabile nuova e nessuna area: il server scrive
  direttamente le variabili frappe-ui compilate (`--ink-gray-7: #3A3A3A;`), che
  cambiano ovunque siano usate. È il comportamento di oggi, esteso a tutte le
  variabili.
- **Cambio di modalità con «parti dai colori attuali» (D5):**
  - Base → Avanzata: ogni ruolo riceve il valore calcolato dalla Base
    (risolto nel browser dall'anteprima, con `getComputedStyle`).
  - Base o Avanzata → Esperto: ricevono un valore solo le variabili assegnate
    **ovunque**; quelle assegnate solo dentro un'area non hanno un equivalente
    in Esperto, e il form lo dice prima di copiare.
  - Esperto → Avanzata o Base: nessuna copia automatica (una variabile non
    corrisponde a un'area); si parte dai valori già salvati di quella modalità.
- **I derivati si calcolano nel CSS** (`color-mix(in oklch, …)`), non in Python:
  nel database restano solo i valori scelti dalla persona.
- **Attenzione ai cicli.** Se in uno scope si scrive
  `--surface-gray-10: var(--os-button-primary-bg)` e il ruolo ricade su
  `var(--surface-gray-10)`, la variabile si riferisce a sé stessa: il browser
  la considera non valida e il pulsante diventa trasparente. Regola:
  `branding.py` emette la ridefinizione nello scope **solo quando il ruolo ha
  un valore** (compilato o calcolato da un colore base compilato), e i valori
  standard servono come fallback tramite copie catturate su `:root`
  (`--os-default-surface-gray-10: var(--surface-gray-10)`). In Esperto il
  problema non si pone: non ci sono ridefinizioni nelle aree.
- **Una sola fonte del CSS.** La funzione che oggi costruisce il CSS
  (`_build_css`) viene generalizzata per ricevere anche valori non salvati:
  la usano sia `brand_css` (valori salvati, con cache) sia l'anteprima (§4.5).

### 4.2 Come si separano gli usi condivisi senza toccare i componenti

Le variabili CSS si ereditano: **ridefinire un token frappe-ui dentro un
contenitore cambia solo quel contenitore**.

```css
/* Only the sidebar subtree: body text elsewhere keeps --ink-gray-7. */
.bg-surface-sidebar {
	--ink-gray-7: var(--os-sidebar-ink);
}
```

- Per ogni ruolo serve un **aggancio stabile**. Dove esiste già
  (`.bg-surface-sidebar`, `.os-list-view`, `.os-table-view`, classi dei
  pulsanti frappe-ui) si usa quello; dove manca si aggiunge un attributo
  `data-os-area="…"` con un innesto minimo nel file upstream, registrato nella
  checklist degli aggiornamenti.
- **Lo stesso aggancio serve all'anteprima** per evidenziare gli elementi del
  campo selezionato: la mappa ruolo → selettore è una sola, condivisa da CSS,
  anteprima e test.
- **Pulsante principale (F3/F4):** si ridefiniscono `--surface-gray-10/9/8` e
  `--ink-base` nello scope del pulsante, così il testo del pulsante si separa
  dai marcatori degli elenchi e l'hover segue il colore scelto.
- Le regole di `theme/elite/main.css` che oggi puntano a `--surface-gray-2`
  per gli input passano a `--os-input-bg`.

### 4.3 Modalità Base

4 campi: **Colore principale**, **Colore di accento**, **Sfondo**, **Tinta dei
grigi** (opzionale, sfuma superfici e bordi verso il colore del brand). Dai 4
colori si calcolano tutti i ruoli della tabella 4.4. Il form mostra, sotto i
campi, una striscia con i colori calcolati principali.

### 4.4 Modalità Avanzata: ruoli previsti

Elenco di partenza (~45 ruoli), da confermare nell'analisi della fase con lo
script del report: ogni ruolo deve cambiare **solo** la sua area.

| Sezione | Ruoli |
|---|---|
| Struttura | sfondo pagina; barra laterale: sfondo, testo, icone, voce attiva (sfondo, testo), passaggio del mouse; barra superiore |
| Testi | titoli, testo, secondario, segnaposto, disabilitato, link, link al passaggio del mouse |
| Pulsanti | principale: sfondo, testo, passaggio del mouse, pressione; secondario: sfondo, testo, bordo |
| Superfici | card, finestre e menu, campi di inserimento, intestazione tabelle, righe tabelle (ex Company Primary), riga selezionata |
| Bordi | leggero, standard, marcato, focus |
| Stati | successo, errore, avviso, informazione: testo, sfondo, bordo |
| Grafici | serie 1–5, pallini e ciambelle delle dashboard (oggi `--red/amber/blue/green/purple-400`) |
| Forma | arrotondamento angoli (Piccolo / Medio / Grande, applicato alla scala `--radius-*`) |
| Login | invariati (`--login-*`) |
| App mobile | invariati (`app_main_color`, `app_secondary_color`) |

### 4.5 Anteprima live

È il pezzo più importante: va costruito **prima** dei ruoli, così serve anche a
verificarli.

- **Pagine vere** della piattaforma in `iframe` della stessa origine, una
  scheda per pagina: Home, Elenco corsi, Pagina corso, Lezione, Dashboard
  classe, Statistiche, Login. Copie disegnate a mano sono scartate: si
  allontanerebbero dalla piattaforma a ogni aggiornamento upstream.
- **Come si aggiorna:** a ogni modifica di un campo (con attesa di ~150 ms tra
  un tasto e l'altro) il form chiede al server il CSS costruito con i valori
  non salvati (endpoint `brand_css_preview`, stessa funzione di §4.1). Nelle
  anteprime aperte il `<link>` del brand salvato viene disattivato e sostituito
  da uno `<style>` con il CSS ricevuto. Stessa origine = accesso diretto al
  documento dell'iframe, nessun messaggio tra finestre.
- **Caricamento solo su richiesta:** una scheda carica la sua pagina quando la
  si apre e poi resta in memoria; le altre restano vuote.
- **Contenuto di esempio** scelto automaticamente (primo corso, prima lezione,
  prima classe pubblicati), con un menu per cambiarlo.
- **«Dove si vede»:** quando il cursore è su un campo, nell'anteprima si
  illuminano gli elementi che quel campo colora (stessa mappa ruolo →
  selettore di §4.2). In Esperto si illuminano gli elementi che usano quel
  token.
- **Interazioni bloccate:** clic, invio dei moduli e tasto Invio intercettati
  nell'iframe, così non si fanno azioni vere; passaggio del mouse e scorrimento
  restano attivi (servono a vedere i colori di hover).
- **Vista desktop / telefono** (larghezza 375 px) e interruttore per vedere che
  il tema scuro resta quello standard.
- **Da verificare nell'analisi:** `/login` per un utente già autenticato
  probabilmente reindirizza (serve una vista di sola visualizzazione, es. un
  parametro che la mostri comunque); intestazione `X-Frame-Options` delle
  pagine; pagine vuote su un sito senza contenuti.
- **Test automatico:** test Cypress che apre Brand Customize, cambia il colore
  principale e controlla che nell'iframe il colore calcolato del pulsante
  cambi senza salvare. Così «l'anteprima funziona» resta verificato anche dopo
  gli aggiornamenti.

### 4.6 Modalità Esperto

- **Elenco dei token:** il Desk non carica il CSS della SPA (F13), quindi
  l'elenco si genera al build da un plugin in `frontend/oslms-vite/` (come
  `translate-frappe-ui.js`) che legge il CSS compilato e scrive un manifest
  JSON con nome, valore standard e tipo (colore, lunghezza, ombra, altro).
  Alternativa più semplice da valutare nell'analisi: leggerlo a runtime dai
  fogli di stile dell'iframe di anteprima.
- **Interfaccia:** tabella con ricerca, filtri per famiglia (`ink`, `surface`,
  `outline`, palette, `radius`, `elevation`, `plyr`, …) e filtro «solo quelli
  usati nella pagina in anteprima»; selettore colore per i colori, campo di
  testo per gli altri; valore standard mostrato accanto.
- **Salvataggio:** tabella figlia `Brand Customize Token` (token, valore) con
  solo i token compilati. `branding.py` li emette nello scope del tema chiaro.
- **Validazione:** il server accetta solo nomi presenti nel manifest e valori
  senza caratteri che chiudano la regola CSS (`;`, `}`, `<`), per evitare
  iniezioni nel foglio di stile servito a tutti.
- I campi a gradino attuali (F1) confluiscono qui (D8).

### 4.7 Grafici

ECharts non legge sempre `var(--…)`. Composable `useChartColors()` in
`frontend/src/oslms/` che risolve `--os-chart-1…5` con `getComputedStyle` e li
passa come `config.colors` alle pagine di F8 (innesti di una riga nei file
upstream). Nell'anteprima i grafici si ridisegnano quando cambia il CSS.

### 4.8 Form, contrasto, preset

- **Selettore «Modalità attiva»** in cima (Base / Avanzata / Esperto): il form
  mostra solo le sezioni della modalità scelta, l'anteprima mostra subito
  quella modalità con i valori non salvati, e al salvataggio diventa la
  modalità applicata alla piattaforma. Una nota accanto al selettore ricorda
  che le altre modalità sono salvate ma non applicate.
  Etichette e descrizioni in italiano (`it.csv` + `it.po`).
- **Valore standard** mostrato nel campo vuoto (placeholder impostato da JS).
- **Contrasto WCAG** calcolato da JS per le coppie testo/sfondo principali:
  «AA ✓» o «Contrasto basso (3,1:1)» accanto al campo e riepilogo al
  salvataggio (D6).
- **Preset (D7):** «Salva come preset» / «Applica preset» con conferma e
  numero di campi sovrascritti; miniatura dei colori base nell'elenco.
- Restano ✕ per campo, Reset Colors, Export/Import (formato versione 2, che
  include modalità e token Esperto; l'import accetta ancora la versione 1).

### 4.9 Pulizia

- Patch `os_lms.patches.v0_0_x_brand_customize_modes`: sposta i valori secondo
  D8 (le Single conservano i valori in `tabSingles` anche dopo la rimozione del
  campo) e imposta la modalità in base ai valori presenti (Esperto se c'erano
  gradini compilati, altrimenti Base).
- `.card` e `.ProseMirror` nel tema: `border-radius: var(--radius-4)`.
- Onboarding (`PersonaForm.vue`): nome e logo del brand (D12).

## 5. Fasi

| Fase | Contenuto | Stima |
|---|---|---|
| 1 | **Pulizia e form**: campi senza effetto rimossi, descrizioni ed etichette italiane corrette, selettore Modalità (con la sola Esperto popolata dai campi attuali), generalizzazione di `_build_css`, patch. Nessun cambiamento visivo per gli utenti. | 1–1,5 g |
| 2 | **Anteprima live**: schede delle 7 pagine, endpoint `brand_css_preview`, aggiornamento senza salvare, blocco delle interazioni, desktop/telefono, test Cypress. Funziona subito con i campi esistenti. | 2–2,5 g |
| 3 | **Base e Avanzata**: `roles.css`, colori base, ~45 ruoli, agganci per area, pulsante con hover derivato, grafici, onboarding, evidenziazione «dove si vede», copia «parti dai colori attuali» Base → Avanzata. | 4–5 g |
| 4 | **Esperto completo**: manifest dei token, tabella con ricerca e filtri, tabella figlia, validazione, copia «parti dai colori attuali» verso Esperto. | 1,5–2 g |
| 5 | **Contrasto e preset**. | 1–1,5 g |

**Fatto quando** (per fase):

1. Il form mostra solo campi con effetto, con etichetta e descrizione corrette; la patch è idempotente; test os_lms verdi.
2. Cambiando un colore, le 7 anteprime si aggiornano in meno di un secondo senza salvare; nessun clic nell'anteprima produce azioni; il test Cypress passa.
3. Ogni ruolo cambia **solo** la sua area (script del report rilanciato sulle 29 schermate); un'istanza senza brand è identica a oggi; tema scuro e alto contrasto invariati; con una modalità attiva, i valori salvati delle altre due non compaiono nel CSS servito (test).
4. Ogni token del manifest è modificabile e visibile nell'anteprima; valori non validi rifiutati dal server.
5. Un contrasto sotto AA è segnalato; un preset si salva e si riapplica.

**Verifiche comuni:**

- Test: `test_branding_light_only` esteso (scope solo chiaro, `--login-*`
  indipendenti, campo vuoto = nessuna riga, nessun ciclo nelle ridefinizioni),
  test della patch e della validazione, suite os_lms, `test_override_signatures`
  se si toccano file upstream.
- Traduzioni: ogni stringa nuova in `__()` e in `it.csv` + `it.po`.
- Controllo manuale in locale: tema chiaro con e senza brand, scuro, alto
  contrasto; Desk, SPA, login.
- Collaudo su elite.overside.it **dopo aver verificato che la patch sia
  stata eseguita** (il deploy di staging marca le patch come già fatte).
- Ogni commit aggiorna la versione nella sidebar.

## 6. Rischi

| Rischio | Mitigazione |
|---|---|
| Aggiornamenti upstream cancellano gli innesti (`data-os-area`, `config.colors`, onboarding). | Innesti minimi, elencati in `docs/upstream-checks/` e nella skill `upstream-check`; i ruoli vivono in file nostri. |
| frappe-ui rinomina token o classi in una nuova beta. | Il manifest Esperto si rigenera al build e un test segnala token aggiunti o spariti; controllo nella checklist dei bump. |
| Cicli tra ruoli e token (§4.1) rendono trasparenti degli elementi. | Ridefinizioni emesse solo con valore; test dedicato. |
| Anteprima lenta con molte pagine della piattaforma aperte. | Caricamento su richiesta; aggiornamento con attesa tra i tasti. |
| Iniezione di CSS dai campi Esperto. | Nomi solo dal manifest, valori validati lato server. |
| Patch non eseguite su staging. | Verificare l'effetto prima del collaudo; su Elite oggi è valorizzato solo `surface_gray_10`. |
| Porting su `master` (frappe-ui 0.1.x, token RGB). | Fuori da questo piano (D11). |

## 7. Fuori ambito

Token tipografici; ricolorazione dei colori scritti fissi nei CSS di
Editor.js, highlight.js, Plyr e toast (restano modificabili solo le loro
variabili, in Esperto); brand anche per il tema scuro; schemi colore per
singola sezione (come Shopify); pannello nella SPA per i Gestore.
