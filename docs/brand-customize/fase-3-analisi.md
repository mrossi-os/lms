# Brand Customize — Fase 3: modalità Base e Avanzata (analisi)

Data: 2026-11-04 · Stato: **approvata (C1–C7) e implementata in locale, non committata** (esito al §9) ·
Piano: [PIANO.md](PIANO.md) §4.1–4.4, §4.7 · Fasi precedenti: [fase-1-analisi.md](fase-1-analisi.md), [fase-2-analisi.md](fase-2-analisi.md)

Vincoli: niente commit, modifiche e test solo sul sito Docker locale.

## 1. Obiettivo

Si rendono utilizzabili le altre due modalità, oggi presenti nel selettore ma vuote:

- **Base**: 4 colori, tutto il resto è calcolato.
- **Avanzata**: circa 40 «ruoli» con nomi chiari per area. Ognuno cambia **solo** la sua area.

Resta valido quanto deciso: è attiva una sola modalità alla volta, e il CSS contiene solo quella
attiva. L'anteprima della Fase 2 funziona già con qualunque modalità, perché il CSS viene sempre da `_build_css`.

## 2. Cosa è emerso dall'analisi

| # | Verifica | Esito |
|---|---|---|
| 1 | Servono innesti nei file upstream (`data-os-area`, PIANO §4.2) per separare le aree? | **Quasi mai.** Le classi Tailwind dei token sono già agganci stabili, e una variabile CSS ridefinita su un elemento vale per quell'elemento e per i suoi figli. Esempi:<br>• **Pulsante principale** (frappe-ui `Button.vue:84`, `bg-surface-gray-10 hover:bg-surface-gray-9 active:bg-surface-gray-8 text-ink-base`): si ridefiniscono `--surface-gray-10/9/8` e `--ink-base` su `button.bg-surface-gray-10, a.bg-surface-gray-10`. Il riquadro della sidebar che usa la stessa classe è un `div`, quindi resta fuori.<br>• **Barra laterale**: la radice di `AppSidebar.vue` ha `bg-surface-sidebar`. Dentro si ridefiniscono testo (`--ink-gray-8`), icone (`svg`), passaggio del mouse (`--surface-gray-2`) e voce attiva (`.bg-surface-elevation-3` in `SidebarLink.vue:7`).<br>• **Finestre e menu**: `[role=dialog]`, `[role=menu]`, `[role=listbox]`.<br>• **Campi**: `input`, `textarea`, `select`. |
| 2 | Cicli tra ruoli e token (PIANO §4.1) | **Non si pongono** se il server scrive valori concreti: `.bg-surface-sidebar { --ink-gray-8: #1d3557 }` non rimanda a sé stesso. Il rischio esisteva solo con derivazioni scritte in CSS come `var()` (vedi punto 3). |
| 3 | Derivazioni (hover, pressione, testo leggibile sopra un colore) in CSS con `color-mix()` o in Python? | **In Python.** Il colore del testo sopra un pulsante richiede di calcolare il contrasto, e in CSS non c'è una funzione affidabile (`contrast-color()` non è disponibile ovunque). In Python, con la conversione sRGB ↔ OKLab (circa 50 righe, senza librerie), si ottengono valori esatti e testabili. La copia «parti dai colori della Base» diventa banale: il server restituisce i ruoli già calcolati, senza leggere `getComputedStyle` nel browser. Condizione: i campi Base e Avanzata accettano solo colori **esadecimali**, che il selettore di colore produce comunque. Esperto continua ad accettare qualsiasi valore CSS. |
| 4 | Grafici | frappe-ui disegna in **SVG** (`ECharts.vue:27`, `renderer: 'svg'`) con il tema ECharts `light`. Da lì vengono i colori fissi del report: `#37A2DA`, `#FFDB5C`, assi `#6E7079`, griglia `#ccc`. `config.colors` viene passato a ECharts (`eChartOptions.ts:32`), ma nessuna delle 5 pagine lo imposta. `ProgramProgressSummary.vue` passa già `var(--red-400)` e il colore si vede (attributo `fill` dell'SVG), quindi `var()` funziona. **Proposta:** override di `AxisChart.vue` e `DonutChart.vue` in `frontend/src/overrides/` (meccanismo `osOverrideTheme`, con alias all'originale come per `Switch`). Quando la pagina non passa colori, gli override usano `var(--os-chart-N, <colore ECharts attuale>)`. Le 5 pagine upstream non si toccano e un'istanza senza brand resta identica. Da verificare nell'implementazione: l'evidenziazione al passaggio del mouse di ECharts con colori `var()`. Se non funziona, si passano i colori già risolti e il grafico si ridisegna quando cambia il CSS. |
| 5 | Tema Elite (`frontend/src/styles/theme/elite/main.css`) | È un file **nostro** (`OSLMS-CUSTOM`). Le sue regole (intestazione liste su `--surface-gray-2`, righe su `--color-company-primary`, card su `--surface-elevation-1`) possono leggere direttamente le variabili dei ruoli, con il token attuale come fallback. |
| 6 | Tema scuro e alto contrasto | Ruoli e ridefinizioni restano sotto `:root:not([data-theme="dark"]):not([data-contrast="more"])`, lo stesso selettore di oggi. `high-contrast.css` non viene toccato. |
| 7 | Onboarding «Come hai conosciuto Frappe Learning?» (PIANO D12) | **Non è un tema di colori.** Il questionario (`pages/Forms/PersonaForm.vue`) è marketing Frappe («Already using Frappe / ERPNext», «Frappe Cloud Marketplace»), e le risposte **vengono inviate a `https://school.frappe.io/api/method/capture-persona`** (`lms/lms/api.py:2271`). Cambiare solo il nome non basta: va deciso a parte se disattivarlo. Proposta: **fuori da questa fase** (vedi C4). |
| 8 | Dati esistenti | Nessuna patch necessaria. Oggi la modalità è Esperto (Fase 1) e su Elite c'è solo `surface_gray_10`. I nuovi campi nascono vuoti. |

## 3. Modalità Base

Quattro campi colore (solo hex):

| Campo | Obbligatorio | Cosa guida |
|---|---|---|
| Colore principale | sì, per attivare la Base | pulsante principale con passaggio del mouse e pressione; testo del pulsante (bianco o nero, il più leggibile); voce attiva della barra laterale (sfondo al 12% del colore, testo scurito); link; anello di focus; serie 1 dei grafici |
| Colore di accento | no (vuoto = calcolato dal principale ruotando la tinta) | serie 2 dei grafici, link al passaggio del mouse, pulsante secondario |
| Sfondo | no (vuoto = bianco standard) | sfondo pagina, card, finestre; barra laterale leggermente più scura dello sfondo |
| Tinta dei grigi | no (vuoto = grigi neutri) | grigi di superfici, bordi e testi con la tinta scelta, a bassa saturazione (stessa luminosità della scala frappe-ui, cambia solo la tinta) |

- Le serie 3–5 dei grafici sono calcolate ruotando la tinta del principale in OKLCH.
- **Successo, errore e avviso restano standard**: un verde «successo» non deve diventare del colore del brand.
- Sotto i campi, il form mostra una striscia con i colori principali calcolati.

## 4. Modalità Avanzata: ruoli proposti

Ogni ruolo è un campo colore hex. Vuoto = standard. Le tonalità secondarie (hover, pressione,
sfondo e bordo degli stati) vuote vengono calcolate dal ruolo principale della stessa voce.

**Meccanismo**: **globale** = il token frappe-ui viene ridefinito ovunque, perché ha un solo
significato. **Area** = viene ridefinito solo dentro l'aggancio indicato.

| Sezione | Ruolo | Token | Meccanismo e aggancio |
|---|---|---|---|
| Struttura | Sfondo pagina | `--surface-base` | globale (campi e pulsanti con contorno hanno il proprio ruolo, che ha la precedenza) |
| | Barra laterale — sfondo | `--surface-sidebar` | globale (usato solo dalla sidebar) |
| | Barra laterale — testo | `--ink-gray-8`, `--ink-gray-7`, `--ink-gray-5` | area `.bg-surface-sidebar` |
| | Barra laterale — icone | `--ink-gray-8` | area `.bg-surface-sidebar svg` |
| | Barra laterale — voce attiva, sfondo | `--surface-elevation-3` | area `.bg-surface-sidebar .bg-surface-elevation-3` |
| | Barra laterale — voce attiva, testo | `--ink-gray-8` | stessa area |
| | Barra laterale — passaggio del mouse | `--surface-gray-2` | area `.bg-surface-sidebar` |
| Testi | Titoli | `--ink-gray-9` | globale |
| | Testo | `--ink-gray-8`, `--ink-gray-7` | globale (la sidebar ha il suo ruolo) |
| | Testo secondario | `--ink-gray-6`, `--ink-gray-5` | globale |
| | Segnaposto e disabilitato | `--ink-gray-4` | globale |
| | Link | `--ink-blue-link` | globale (da misurare: alcuni link usano altri token) |
| Pulsanti | Principale — sfondo | `--surface-gray-10` | area `button.bg-surface-gray-10, a.bg-surface-gray-10` |
| | Principale — testo | `--ink-base` | stessa area (si separa dai marcatori degli elenchi, F3) |
| | Principale — passaggio del mouse | `--surface-gray-9` | stessa area |
| | Principale — pressione | `--surface-gray-8` | stessa area |
| | Secondario — sfondo | `--surface-gray-2/3/4` | area `button.bg-surface-gray-2` |
| | Secondario — testo | `--ink-gray-8` | stessa area |
| | Con contorno — bordo | `--outline-gray-2/3` | area `button.border-outline-gray-2` |
| Superfici | Card | `--surface-elevation-1` | globale |
| | Finestre e menu | `--surface-elevation-1/2` | area `[role=dialog], [role=menu], [role=listbox]` |
| | Campi di inserimento | `--surface-gray-2`, `--surface-base` | area `input, textarea, select` (esclusi checkbox e radio) |
| | Intestazione tabelle | variabile di ruolo letta da `main.css` | nostro CSS |
| | Righe tabelle | `--color-company-primary` | nostro CSS (ex «Righe tabelle» di Esperto) |
| Bordi | Leggero | `--outline-gray-1` | globale |
| | Standard | `--outline-gray-2` | globale |
| | Marcato | `--outline-gray-3`, `--outline-gray-4` | globale |
| | Focus | anello `--outline-gray-3` | area `:focus-visible` |
| Stati | Successo · Errore · Avviso · Informazione | scala `--ink/surface/outline-green/red/amber/blue-*` | globale: **un colore per stato**, da cui si calcolano testo, sfondo e bordo (decisione C2) |
| Grafici | Serie 1–5 | `--os-chart-1…5` | override grafici (§2 punto 4) |
| Forma | Arrotondamento angoli | scala `--radius-*` | Selezione Piccolo / Standard / Grande, che moltiplica la scala |
| Login, App mobile | invariati | `--login-*`, `app_*` | fuori dalle modalità, come oggi |

In tutto sono **circa 40 campi**. Due ruoli del PIANO (**barra superiore** e **riga selezionata**)
non hanno trovato un aggancio stabile: li aggiungo solo se l'implementazione lo trova, altrimenti
li segnalo.

## 5. Proposta tecnica

### 5.1 Server — `apps/os_lms/os_lms/os_lms/`

- **`branding_color.py` (nuovo).**
  - Lettura e scrittura hex.
  - Conversione sRGB ↔ OKLab/OKLCH.
  - Schiarire e scurire in OKLCH; ruotare la tinta.
  - Contrasto WCAG; scelta del testo leggibile (bianco o nero).
- **`branding_roles.py` (nuovo).** Un solo elenco dei ruoli, usato da CSS, anteprima e test:
  - nome del campo;
  - token;
  - selettore dell'area (o «globale»);
  - derivazioni.
- **`branding_roles.py`, funzioni:**
  - `derive_base(values) -> dict[role, hex]` (Base → valori dei ruoli);
  - `derive_advanced(values)`, che completa le tonalità secondarie vuote.
- **`branding.py`:**
  - `_theme_declarations` per Base e Avanzata produce i blocchi globali e quelli di area, tutti sotto il selettore del tema chiaro;
  - `_build_css` resta l'unica fonte;
  - nuovo endpoint `base_to_advanced(values)` (solo System Manager): restituisce i ruoli calcolati dalla Base, per la copia.
- **Validazione:** i campi Base e Avanzata devono essere hex; resta il controllo della Fase 2 per tutti.

### 5.2 Doctype e form

- **Doctype:**
  - `mode` diventa modificabile;
  - sezioni Base e Avanzata con `depends_on: eval:doc.mode=="…"`, così il form mostra solo la modalità attiva;
  - le sezioni Esperto ricevono lo stesso `depends_on`.
- **Cambio di modalità verso Avanzata, se la Base è compilata e l'Avanzata è vuota:**
  - il form chiede «Vuoi partire dai colori della Base?»;
  - con «Sì» compila i ruoli con `base_to_advanced`;
  - l'anteprima si aggiorna subito, perché `mode` è già tra i campi che la attivano.
- **Placeholder dei ruoli:** il valore standard del token (meccanismo della Fase 1), così un campo vuoto mostra cosa vale.
- **Evidenziazione «dove si vede»:**
  - quando un campo Base, Avanzata o Esperto riceve il focus, l'anteprima disegna un riquadro sugli elementi interessati;
  - per i ruoli usa il selettore dell'area;
  - per i campi Esperto usa le classi che contengono il nome del token, per esempio `[class*="surface-gray-2"]` (approssimato, decisione C6);
  - massimo 200 riquadri, su un livello che non riceve i click.

### 5.3 SPA

- **Override grafici:** `frontend/src/overrides/frappe-ui/src/components/Charts/AxisChart.vue` e `DonutChart.vue`, più l'alias all'originale in `vite.config.js`.
- **`main.css` Elite:** intestazione e righe delle tabelle leggono le variabili dei ruoli, con fallback ai token di oggi.
- **Nessuna modifica** a pagine o componenti upstream.

### 5.4 Traduzioni

Circa 60 stringhe nuove in `apps/os_lms/os_lms/translations/it.csv`, con contesto `Brand Customize`
dove sono generiche.

## 6. File toccati (previsti)

| File | Modifica |
|---|---|
| `apps/os_lms/os_lms/os_lms/branding_color.py` (nuovo) | matematica dei colori |
| `apps/os_lms/os_lms/os_lms/branding_roles.py` (nuovo) | elenco dei ruoli e derivazioni |
| `apps/os_lms/os_lms/os_lms/branding.py` | CSS di Base e Avanzata, `base_to_advanced` |
| `…/doctype/brand_customize/brand_customize.json` | campi Base (4) e Avanzata (circa 40), `mode` modificabile, `depends_on` |
| `…/doctype/brand_customize/brand_customize.py` | validazione hex |
| `…/doctype/brand_customize/brand_customize.js` | copia Base → Avanzata, evidenziazione, striscia dei colori Base |
| `frontend/src/overrides/frappe-ui/src/components/Charts/AxisChart.vue`, `DonutChart.vue` (nuovi) | colori dei grafici |
| `frontend/vite.config.js` | alias agli originali dei grafici |
| `frontend/src/styles/theme/elite/main.css` | tabelle sulle variabili dei ruoli |
| `apps/os_lms/os_lms/translations/it.csv` | stringhe |
| `apps/os_lms/os_lms/os_lms/tests/test_branding_color.py`, `test_branding_roles.py` (nuovi) | test |
| `frontend/src/tests/brandAnchors.test.ts` (nuovo) | controlla che gli agganci esistano ancora nei sorgenti (classi della sidebar e del pulsante) |
| `docs/upstream-checks/` (checklist) | agganci e override dei grafici da ricontrollare dopo le merge |

## 7. Verifiche previste

- **Test Python:**
  - conversioni di colore (valori di riferimento OKLab);
  - testo leggibile sopra colori chiari e scuri;
  - Base e Avanzata senza valori = CSS vuoto;
  - solo la modalità attiva nel CSS;
  - ogni ruolo emesso solo nel suo selettore;
  - nessuna ridefinizione che rimandi a sé stessa;
  - `base_to_advanced` coerente con il CSS della Base;
  - validazione hex;
  - permessi.
- **Prova di isolamento nel browser** (il criterio «fatto quando» del PIANO), con uno script eseguito nell'anteprima:
  - per ogni ruolo si imposta un colore vistoso (`#ff00ff`);
  - si elencano gli elementi delle 7 pagine il cui colore calcolato cambia;
  - si controlla che stiano tutti dentro l'area del ruolo;
  - risultato in una tabella ruolo → elementi fuori area (atteso: zero), allegata al worklog.
- **Altri controlli:**
  - istanza senza brand identica a oggi (confronto del CSS servito);
  - tema scuro e alto contrasto invariati;
  - grafici con e senza brand;
  - suite os_lms;
  - `test_override_signatures`, perché si aggiungono override frappe-ui;
  - build della SPA (necessaria per gli override dei grafici).

## 8. Decisioni da prendere

| # | Domanda | Proposta |
|---|---|---|
| C1 | Derivazioni in Python e campi Base/Avanzata solo hex? | **Sì.** Valori esatti e testabili, testo dei pulsanti sempre leggibile, copia Base → Avanzata semplice. Esperto resta libero. |
| C2 | Stati (successo, errore, avviso, informazione): un colore per stato o tre (testo, sfondo, bordo)? | **Un colore per stato**, con sfumature calcolate. Sono 4 campi invece di 12. |
| C3 | La Base cambia anche i colori degli stati? | **No**, restano standard. |
| C4 | Onboarding Frappe | **Fuori da questa fase.** È un questionario di marketing Frappe che invia le risposte a `school.frappe.io`; propongo un'attività separata per decidere se disattivarlo. |
| C5 | Grafici | **Override di `AxisChart`/`DonutChart`**: nessuna modifica alle 5 pagine; senza brand restano i colori di oggi. |
| C6 | Evidenziazione anche per i campi Esperto, approssimata per nome di classe? | **Sì** (costa poco). Quella esatta resta in Fase 4 con il manifest dei token. |
| C7 | Elenco dei ruoli (§4) | **Approvare l'elenco**, con «barra superiore» e «riga selezionata» solo se si trova un aggancio stabile. |

Stima: **4–5 giornate**, come da PIANO. L'onboarding esce dalla fase (circa −0,25 g), gli override
dei grafici e la prova di isolamento entrano (circa +0,25 g).

## 9. Esito dell'implementazione

Implementata il 2026-11-04 sul sito Docker locale, senza commit (dettaglio: `docs/WORKLOG.md`, Attività 32).

- **Una differenza rispetto al §4.** La prova di isolamento ha mostrato che un ruolo globale entrava
  nelle aree con un ruolo proprio rimasto vuoto. Esempi: «Testo» cambiava 78 elementi della barra
  laterale e il testo dei pulsanti secondari; «Sfondi chiari» cambiava i campi. Ora ogni area
  (barra laterale, finestre e menu, campi, pulsanti, focus) **blocca i token che possiede**: finché
  il suo ruolo è vuoto riscrive il valore standard. Le aree annidate (icone e voce attiva della
  barra laterale) seguono la barra laterale. In Base la tinta dei grigi compila anche i ruoli delle
  aree (testo della barra laterale, passaggio del mouse, campi, pulsanti secondari e con contorno),
  così l'aspetto della Base non cambia. «Barra laterale — testo» copre anche `--ink-gray-9`.
- **Effetti voluti che restano.** Il bordo destro della barra laterale segue «Bordi leggeri».
  Il testo dentro i campi segue «Testo», perché il ruolo dei campi è solo lo sfondo.
- **Esito della prova di isolamento** (pagina Corsi, `#ff00ff` per ogni ruolo, solo proprietà
  visibili, colori confrontati in RGB): 0 elementi cambiati fuori dall'area per tutti i ruoli
  d'area. Per i ruoli globali, 0 elementi cambiati dentro le aree oltre ai due effetti voluti.
  Grafici: con la Base `#c2185b` la serie 1 è `#c2185b`; senza brand tornano a `#37A2DA`.
  Tabelle: intestazione e righe prendono il colore del ruolo; con il tema scuro restano standard.

