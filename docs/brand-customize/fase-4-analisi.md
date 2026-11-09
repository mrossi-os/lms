# Brand Customize — Fase 4: modalità Esperto completa (analisi)

Data: 2026-11-09 · Stato: **approvata (E1–E7) e implementata in locale, non committata** (esito al §7) ·
Piano: [PIANO.md](PIANO.md) §4.6, §5 · Fasi precedenti: [fase-1-analisi.md](fase-1-analisi.md),
[fase-2-analisi.md](fase-2-analisi.md), [fase-3-analisi.md](fase-3-analisi.md)

Vincoli: niente commit, modifiche e test solo sul sito Docker locale.

## 1. Obiettivo

Oggi la modalità **Esperto** ha 19 campi fissi (i gradini storici del form: `--surface-gray-10`,
`--ink-gray-7`…). Il PIANO chiede che in Esperto si possa cambiare **ogni variabile** della
piattaforma: colori, raggi, ombre, player video. Le variabili vanno elencate in una tabella con
ricerca e filtri, e ognuna deve comparire nell'anteprima.

**Fatto quando** (PIANO §5): ogni variabile dell'elenco è modificabile e visibile nell'anteprima;
i valori non validi vengono rifiutati dal server.

## 2. Cosa è emerso dall'analisi

Misure fatte sul foglio di stile compilato della SPA (`index-BvQc2O4s.css`, frappe-ui 1.0.0-beta.29).

| # | Verifica | Esito |
|---|---|---|
| 1 | Serve il plugin di build che scrive un manifest (PIANO §4.6)? | **No.** Dalla Fase 1 il server legge già i valori standard dal CSS compilato servito alla SPA (`branding._spa_token_defaults`, in cache per nome del file, quindi si aggiorna a ogni build). Basta estenderlo: l'elenco è sempre quello della build installata, senza un file in più da tenere allineato. |
| 2 | Quante variabili ci sono? | **588** dichiarate per il tema chiaro (`:root`): 549 colori, 18 lunghezze (raggi), 21 altro (ombre `--elevation-*`, anelli di focus `--focus-*`). Più **59 variabili del player video** (`--plyr-*`) che non sono dichiarate da nessuna parte: Plyr le legge con un valore di riserva (`var(--plyr-color-main, …)`), quindi si possono impostare ma il valore standard va preso dalla riserva. Il «859» del report del cliente conta anche le copie del tema scuro e dell'alto contrasto, che il brand non tocca. |
| 3 | Hanno tutte un effetto? | **No: 185 su 588.** Le altre 403 non sono usate da nessuna regola né da nessun componente: per esempio la scala primitiva `--gray-50…950`, `--blue-500` e simili (i token semantici come `--ink-gray-7` contengono già il colore, non rimandano alle primitive) e intere famiglie di palette mai usate (`teal`, `yellow`, `purple`, tinte `alpha`). Cambiarle non produce nulla a schermo. |
| 4 | Variabili nostre | Quattro gruppi letti solo da os_lms, assenti nel CSS di frappe-ui: `--ink-gray-10`, `--color-company-primary` (righe delle tabelle), `--os-table-header-bg`, `--os-chart-1…5` (grafici, Fase 3). Vanno aggiunte a mano all'elenco. |
| 5 | Dove si salvano | Una variabile per campo non è più possibile (650 campi). Serve una tabella figlia o un campo JSON. Attenzione: l'Esporta di oggi salta i campi `Table` (`frappe.model.no_value_type` li esclude), quindi va aggiornato. |
| 6 | Sicurezza | Il **nome** della variabile finisce nel foglio di stile servito a tutti, quindi ora conta anche lui, non solo il valore. Tutti i nomi esistenti rispettano `--[a-z0-9-]+` (unica eccezione `--_list-row-pad`, interna). Il controllo dei valori di oggi (niente `;`, `{}`, `<>`, commenti, `url(`, `@import`) resta. Il limite di 100 caratteri non basta: le ombre standard arrivano a **121**. |
| 7 | Tema scuro | I colori e le ombre restano solo del tema chiaro (come oggi). I **raggi** invece in Avanzata valgono già in ogni tema (Fase 3): conviene la stessa regola in Esperto per le lunghezze. |
| 8 | Evidenziazione «dove si vede» | Oggi in Esperto è approssimata dal nome della classe (`bg-surface-gray-2`), decisione C6. Si può fare **esatta** con la tecnica della prova di isolamento della Fase 3: si dà alla variabile un colore sentinella solo nell'anteprima, si confrontano gli stili calcolati e si evidenziano gli elementi cambiati. Costa decine di millisecondi per una variabile, quindi va bene al focus su un campo. |
| 9 | Filtro «solo le variabili di questa pagina» | Provare 650 variabili una per una sarebbe troppo lento (secondi). Più rapido: scorrere le regole dei fogli di stile dell'anteprima, tenere quelle che colpiscono almeno un elemento della pagina e raccogliere le variabili che usano. È esatto per le regole CSS. Mancano solo i colori passati da JavaScript (grafici), che hanno già le loro variabili `--os-chart-*`. |
| 10 | Dati esistenti | I 19 campi Esperto attuali vanno travasati nel nuovo elenco da una patch. Su Elite è valorizzato solo `surface_gray_10` (memoria del progetto). Ricordare che il deploy dello staging marca le patch come già eseguite: l'effetto va controllato prima del collaudo. |
| 11 | Dopo un aggiornamento di frappe-ui | Una variabile salvata può sparire o cambiare nome. **Non deve bloccare il salvataggio** di tutto il form: è già successo con un campo validato aggiunto dall'upstream (memoria «validated single field backfill»). |

## 3. Proposta

### 3.1 Elenco delle variabili (server)

Nuovo modulo `apps/os_lms/os_lms/os_lms/branding_tokens.py`, che costruisce l'elenco a partire dal CSS compilato:

- nome, valore standard, **tipo** (colore, lunghezza, ombra, altro) e **famiglia** (`ink`,
  `surface`, `outline`, palette, primitive, `radius`, `elevation`, `focus`, `plyr`, os_lms);
- **effetto**: sì se qualche regola CSS o qualche componente la usa (le 185, più Plyr e le nostre);
- Plyr: nomi e valori standard presi dalle riserve `var(--plyr-x, …)`;
- in cache come oggi, con il nome del file CSS nella chiave.

Endpoint `get_expert_tokens()` (System Manager) che restituisce l'elenco al form.

### 3.2 Dove si salvano i valori

Nuova tabella figlia **`Brand Customize Token`** (`token`, `value`), con le sole variabili
compilate. La griglia standard resta nascosta: la compila l'editor del form.

### 3.3 CSS

- Colori e ombre: nel blocco del tema chiaro, come oggi.
- Lunghezze (raggi): in `:root`, quindi in ogni tema, come il raggio dell'Avanzata.
- Le variabili Plyr si scrivono su `:root`. Plyr le legge da lì, perché non le ridefinisce sul player.

### 3.4 Controlli al salvataggio (e nell'anteprima)

- Nome: deve rispettare `^--[a-z0-9][a-z0-9-]*$` e non essere ripetuto.
- Nome sconosciuto all'elenco della build installata:
  - una **riga nuova** viene rifiutata;
  - una **riga già salvata** (variabile sparita dopo un aggiornamento) resta: avviso arancione al salvataggio e si continua a scriverla, tanto non fa danni.
- Valore: stesso controllo di oggi, limite portato a 300 caratteri.
- Senza build della SPA (per esempio nei test): si controlla solo il formato del nome.

### 3.5 Form del Desk

Nella sezione Esperto, al posto dei 19 campi, un editor in un campo HTML:

- ricerca per nome;
- filtro per famiglia;
- «solo compilate»;
- «solo in questa pagina dell'anteprima» (§2 punto 9);
- «mostra anche le variabili senza effetto», spento di default;
- una riga per variabile:
  - nome;
  - campione del valore standard;
  - campo di testo con il valore standard come segnaposto;
  - selettore di colore per i colori;
  - ✕ per svuotare;
- anteprima live ed evidenziazione esatta al focus (§2 punto 8).

Etichette e filtri in italiano. I nomi delle variabili restano in chiaro, come oggi.

### 3.6 Copia «parti dai colori attuali» verso Esperto

Passando da Base o Avanzata a Esperto, il form chiede se partire dai colori attuali:

- Si copiano le variabili che la modalità precedente scrive **ovunque**.
- Quelle scritte solo dentro un'area (pulsanti, barra laterale, campi…) non hanno un equivalente in Esperto. La finestra dice quante sono prima di copiare.
- Il raggio dell'Avanzata diventa i `--radius-*` corrispondenti.

Nuovo endpoint `to_expert(values)`, che riusa `branding_roles.blocks`.

Da Esperto verso Base o Avanzata non si copia nulla, come previsto dal PIANO.

### 3.7 Dati esistenti, Esporta e Importa

- Patch `os_lms.patches.v0_0_11.brand_customize_expert_tokens`:
  - copia i 19 campi in righe della tabella;
  - è idempotente;
  - lascia i valori in `tabSingles` finché i campi non vengono tolti dal doctype.
- Esporta, versione 2: include la modalità e le righe Esperto.
- Importa: accetta ancora la versione 1, convertendo i vecchi nomi di campo nelle variabili.
- **Reset Colors** svuota anche le righe Esperto.

## 4. File toccati (previsti)

| File | Modifica |
|---|---|
| `apps/os_lms/os_lms/os_lms/branding_tokens.py` | nuovo: elenco, tipi, famiglie, effetto, validazione dei nomi |
| `apps/os_lms/os_lms/os_lms/branding.py` | CSS da righe Esperto, controlli, anteprima, `get_expert_tokens`, `to_expert`, valori standard per l'editor |
| `apps/os_lms/os_lms/os_lms/doctype/brand_customize_token/` | nuova tabella figlia |
| `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.{json,py,js}` | sezione Esperto nuova, controlli al salvataggio, editor, copia, Esporta/Importa, Reset |
| `apps/os_lms/os_lms/patches/v0_0_11/` + `patches.txt` | travaso dei 19 campi |
| `apps/os_lms/os_lms/os_lms/tests/test_branding_tokens.py`, test della patch, test esistenti | aggiornati |
| `apps/os_lms/os_lms/translations/it.csv` | nuove stringhe |

Nessun file upstream e nessun file della SPA: la Fase 4 vive nel Desk e in os_lms.

## 5. Verifiche previste

- Test Python:
  - elenco: dichiarate, Plyr da riserva, nostre, effetto sì/no;
  - nomi pericolosi rifiutati (`--x;}body{`, `--a b`, `--x:`);
  - valori pericolosi e troppo lunghi rifiutati;
  - colori solo nel tema chiaro e raggi in ogni tema;
  - riga sconosciuta già salvata accettata con avviso, nuova rifiutata;
  - copia verso Esperto: solo le variabili globali, conteggio di quelle d'area;
  - patch idempotente, che conserva i valori;
  - modalità separate: in Base o Avanzata le righe Esperto non compaiono nel CSS.
- Suite os_lms completa (esclusa la parte AI).
- Browser, sul sito locale:
  - ricerca e filtri dell'editor;
  - una variabile per famiglia cambiata e vista nell'anteprima: colore, raggio, ombra, Plyr nella lezione, grafico;
  - evidenziazione esatta;
  - filtro «in questa pagina»;
  - copia da Avanzata;
  - Esporta e reimporta (anche un file della versione 1);
  - dopo le prove, nessun valore salvato cambiato.
- CSS servito identico a prima dopo la patch (oggi: `--surface-gray-10` e le variabili del login).

## 6. Decisioni da prendere

| # | Domanda | Proposta |
|---|---|---|
| E1 | Elenco dal CSS compilato letto dal server, invece del plugin di build del PIANO? | **Sì.** Esiste già, si aggiorna da solo a ogni build e non aggiunge file. |
| E2 | Le 403 variabili senza effetto si mostrano? | **Nascoste di default**, con un interruttore «mostra anche le variabili senza effetto». Restano modificabili, ma non confondono chi cerca. |
| E3 | Tabella figlia o campo JSON? | **Tabella figlia**: la cronologia del documento mostra le modifiche riga per riga. |
| E4 | Raggi e altre lunghezze in Esperto valgono anche nel tema scuro? | **Sì**, come il raggio dell'Avanzata. Colori e ombre restano solo nel tema chiaro (D4). |
| E5 | Variabile salvata che sparisce con un aggiornamento di frappe-ui | **Non blocca il salvataggio**: avviso, la riga resta. Solo le righe nuove devono essere note. |
| E6 | Evidenziazione esatta in Esperto con il colore sentinella | **Sì.** Sostituisce quella approssimata della Fase 3 (C6). |
| E7 | I 19 campi Esperto attuali | **Travasati dalla patch** e tolti dal form; Importa accetta ancora i file vecchi. |

Stima: **2–2,5 giornate**. Il PIANO diceva 1,5–2; in più ci sono l'evidenziazione esatta e il filtro
«in questa pagina», mentre il plugin di build non serve più.

## 7. Esito dell'implementazione

Implementata il 2026-11-09 sul sito Docker locale, senza commit (dettaglio: `docs/WORKLOG.md`, Attività 3).

- **Differenze rispetto al §3.**
  - La patch `v0_0_11` **toglie** i vecchi valori da `tabSingles` dopo averli copiati: i 19 campi
    escono dal doctype nella stessa fase, quindi lasciarli non serviva a nulla.
  - L'elenco sulla build installata conta **653 variabili, 250 con effetto** (588 su `:root`,
    le `--plyr-*` lette con riserva, 8 variabili os_lms). Le 185 del §2 erano solo quelle di
    frappe-ui usate dal CSS: ora si contano anche i riferimenti nel JS e le variabili Plyr e os_lms.
  - Il filtro «solo nella pagina dell'anteprima» legge anche gli stili in linea (`style`,
    `fill`, `stroke`) e, se la pagina ha un grafico, aggiunge `--os-chart-*`.
- **Esito delle prove nel browser** (Administrator, pagina Brand Customize del Desk):
  - editor: «250 variabili mostrate su 653», etichette e filtri in italiano; i selettori di colore
    partono dal valore standard convertito in hex (`--surface-blue-7` → `#077ddf`);
  - anteprima live senza salvare (`--surface-base` `#fff4e6` cambia lo sfondo della pagina);
  - evidenziazione esatta in circa 26 ms: `--radius-4` trova 12 elementi (0 con il metodo per
    nome di classe), `--ink-gray-5` 6 (3 prima). Dopo la prova non resta nessuno stile temporaneo
    nella pagina e le transizioni funzionano;
  - filtro «solo nella pagina dell'anteprima»: Home 17 variabili, Lezione 51, Statistiche 21
    (con le 5 `--os-chart-*`);
  - copia dall'Avanzata: la domanda compare passando a Esperto; con «Sì» si compilano
    `--surface-base` e 13 `--radius-*` (raggio «Grande» ×1,6);
  - Importa: un file v1 (vecchi campi) diventa righe della tabella e il campo sconosciuto viene
    segnalato; un file v2 sostituisce le righe;
  - salvataggio con una variabile inesistente: rifiutato con «Queste variabili non esistono nella
    piattaforma», nessuna scrittura.
  - Dopo le prove modifiche annullate con `reload_doc`: DB invariato (Esperto,
    `--surface-gray-10 = #292929`, data di modifica del 2026-11-04) e `brand_css` identico.
- **Non verificato nel browser**:
  - la variabile Plyr: la lezione dell'anteprima (`corso-c01`, 1-1) non ha un video;
  - la riga sconosciuta già salvata: richiederebbe una scrittura nel DB. È coperta dal test
    `test_saved_variable_gone_after_an_update_does_not_block`;
  - l'Esporta: scarica un file. La costruzione dei dati è la stessa che l'Importa v2 rilegge.
