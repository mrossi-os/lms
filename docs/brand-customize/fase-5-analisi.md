# Brand Customize — Fase 5: contrasto e preset (analisi)

Data: 2026-11-09 · Stato: **approvata (G1–G5) e implementata in locale, non committata** (esito al §7) ·
Piano: [PIANO.md](PIANO.md) §4.8, §5 · Fasi precedenti: [fase-1-analisi.md](fase-1-analisi.md),
[fase-2-analisi.md](fase-2-analisi.md), [fase-3-analisi.md](fase-3-analisi.md),
[fase-4-analisi.md](fase-4-analisi.md)

Vincoli: niente commit, modifiche e test solo sul sito Docker locale.

## 1. Obiettivo

Il PIANO chiede due cose:

- **Contrasto**: il form segnala, mentre si sceglie, le coppie testo/sfondo poco leggibili e le
  riassume al salvataggio. Non blocca (D6).
- **Preset**: salvare l'insieme dei colori con un nome e riapplicarlo in seguito (D7).

**Fatto quando** (PIANO §5): un contrasto sotto AA è segnalato; un preset si salva e si riapplica.

Il controllo dei colori Base salvati oggi (worklog, Attività 6) aggiunge un terzo punto. Con uno
sfondo medio, la Base rende illeggibile il testo secondario (contrasto 1,43) e il segnaposto (1,03).
Un avviso lo segnala, ma il calcolo stesso può evitarlo (§3.3).

## 2. Cosa è emerso dall'analisi

| # | Verifica | Esito |
|---|---|---|
| 1 | Contrasto dei colori **standard** di frappe-ui (beta.29), misurato sul sito locale | **Non tutti passano AA (4,5).** Testo secondario `--ink-gray-5` su bianco **4,17**; sulla barra laterale 3,93; sulle superfici grigie 3,76. Link `--ink-blue-link` **3,37**. Segnaposto `--ink-gray-4` **2,85**. Bordi 1,30–1,69. Testo, titoli e pulsante principale invece 11–19. Un avviso «sotto 4,5» scatterebbe **anche senza brand**, su campi lasciati vuoti. |
| 2 | Dove si calcolano i colori effettivi | Sul server, in `brand_css_preview`, già chiamato a ogni modifica del form (attesa di 150 ms). Ha già i ruoli calcolati della Base (`mode_roles`) e i valori standard (`_token_stock`). Basta aggiungere il contrasto alla stessa risposta, senza una seconda chiamata. |
| 3 | Coppie da misurare | Le coppie testo/sfondo **visibili davvero**. **Pagina**: titoli, testo, testo secondario, segnaposto e link sullo sfondo della pagina e sulle card. **Barra laterale**: testo e voce attiva. **Pulsanti**: testo sul pulsante principale e sul secondario. **Campi e menu**: testo su sfondo dei campi e dei menu. **Login**: testo sullo sfondo (entrambi i capi della sfumatura) e testo dei campi. Più tre coppie «non testo» (soglia 3:1, WCAG 1.4.11): pulsante principale e anello di focus rispetto alla pagina, pulsante secondario rispetto alla pagina. Sono 22 coppie, in Base e Avanzata calcolate dai ruoli; in Esperto si leggono i token (`--ink-gray-7` su `--surface-base`, …), salvati o standard. |
| 4 | Perché la Base sbaglia con uno sfondo medio | `derive_base` prende dalla tinta solo il colore dei grigi e tiene la loro **luminosità standard**, pensata per uno sfondo bianco. Su `#4F9DD9` il testo secondario (luminosità standard 0,586) finisce vicino allo sfondo. Anche il pulsante secondario (sfondo + 12% di accento) resta quasi uguale alla pagina (1,06). |
| 5 | Preset: cosa salvare | L'**Esporta** produce già un JSON completo e versionato (modalità, tutti i campi, righe Esperto), e l'**Importa** lo riapplica con conferma e numero di valori. Un preset può essere quel JSON salvato nel sito con un nome: si riusano le stesse funzioni e la compatibilità con i file v1 viene gratis. |
| 6 | Chi usa i preset | Brand Customize è solo per System Manager; i Gestore non entrano nel Desk (memoria del progetto). Il nuovo doctype avrà gli stessi permessi. |

## 3. Proposta

### 3.1 Contrasto (server)

Nuova funzione `contrast_report(values)` in `branding.py` (o in un modulo `branding_contrast.py`):

- **Valori considerati**: per ogni coppia di §2.3 prende i colori effettivi della modalità
  attiva (campo compilato, ruolo calcolato della Base, oppure valore standard se vuoto).
- **Cosa restituisce per coppia**: nome, campi coinvolti, rapporto, soglia (4,5 testo; 3 per
  segnaposto e «non testo»), rapporto con i colori standard e livello.
- **I livelli**:
  - **ok**: raggiunge la soglia;
  - **come lo standard**: sotto la soglia, ma non peggiore dei colori standard (es. testo
    secondario a 4,17). Si mostra solo come nota grigia, non come avviso;
  - **basso**: sotto la soglia **e** peggiore dello standard. È l'avviso vero.
- **Chi la usa**: `brand_css_preview` la aggiunge alla risposta (`contrast`), e `validate` la usa
  per il riepilogo al salvataggio (messaggio arancione, non blocca, D6).

### 3.2 Contrasto (form)

- **Riquadro «Leggibilità»** in cima alla sezione della modalità attiva: «Tutto leggibile ✓»
  oppure l'elenco delle coppie basse. Per esempio: «Testo secondario sullo sfondo della pagina —
  1,4:1 (minimo 4,5)». Un clic su una riga mette il focus sul campo e lo evidenzia nell'anteprima,
  con l'evidenziazione delle Fasi 3–4.
- **Etichetta accanto al campo**, in Avanzata e nella sezione Login: «AA ✓» o «Contrasto basso
  (1,4:1)», accanto al campo del **testo** della coppia (o dello sfondo, se il testo è vuoto). In
  Base le coppie dipendono dai 4 colori insieme, quindi solo il riquadro. In Esperto l'etichetta
  va sulla riga della variabile del testo.
- Il riquadro si aggiorna insieme all'anteprima, con la stessa chiamata.

### 3.3 Base più robusta con sfondi medi e scuri

In `derive_base`:

- **Testo**: ogni grigio del testo parte dalla luminosità standard e, se sullo sfondo scelto
  scende sotto il contrasto che ha nello standard (titoli e testo almeno 4,5), si sposta finché
  lo raggiunge, con `ensure_contrast` già usato per il link.
- **Pulsante secondario**: se resta troppo simile alla pagina, la miscela con l'accento aumenta.

Con lo sfondo bianco o chiaro **non cambia nulla**: i grigi standard superano già le soglie che
si danno da soli. Con i colori salvati oggi testo e segnaposto tornano leggibili.

### 3.4 Preset

- Nuovo doctype **`Brand Preset`**:
  - campi: nome (titolo), modalità, colori di anteprima (4 swatch), `data` (il JSON
    dell'Esporta, versione 2);
  - permessi: solo System Manager;
  - nel Desk resta raggiungibile anche dall'elenco, per rinominare o cancellare.
- Nel menu **Azioni** del form:
  - **Salva come preset**: chiede il nome e salva i valori **attuali del form**, anche non
    salvati. Se il nome esiste, chiede se sovrascrivere;
  - **Applica preset**: elenco con nome, modalità e swatch. La scelta passa dalla stessa
    conferma dell'Importa («sovrascriverà … N valori»). Il form diventa da salvare e
    l'anteprima si aggiorna; niente è applicato alla piattaforma finché non si salva.
- **Preset già pronti**: nessuno. Per tornare allo standard c'è Reset Colors.

## 4. File toccati (previsti)

| File | Modifica |
|---|---|
| `apps/os_lms/os_lms/os_lms/branding_contrast.py` | nuovo: coppie, colori effettivi, livelli |
| `apps/os_lms/os_lms/os_lms/branding.py` | `contrast` nella risposta di `brand_css_preview` |
| `apps/os_lms/os_lms/os_lms/branding_roles.py` | `derive_base`: testo e pulsante secondario leggibili |
| `apps/os_lms/os_lms/os_lms/doctype/brand_customize/brand_customize.{py,js}` | riepilogo al salvataggio; riquadro ed etichette; Salva/Applica preset |
| `apps/os_lms/os_lms/os_lms/doctype/brand_preset/` | nuovo doctype |
| `apps/os_lms/os_lms/os_lms/tests/test_branding_contrast.py`, `test_branding_roles.py`, test del preset | nuovi e aggiornati |
| `apps/os_lms/os_lms/translations/it.csv` | nuove stringhe |

Nessun file upstream e nessun file della SPA.

## 5. Verifiche previste

- Test Python:
  - colori standard: nessun livello «basso»;
  - colori Base salvati oggi: oggi «basso» su testo secondario e segnaposto; dopo §3.3 nessun
    testo «basso»;
  - sfondo bianco: `derive_base` identico a prima (nessuna regressione della Fase 3);
  - Avanzata: un testo chiaro su sfondo chiaro è «basso» e indica il campo giusto;
  - login: entrambi i capi della sfumatura;
  - riepilogo al salvataggio non bloccante;
  - preset: salvataggio, sovrascrittura, applicazione di un JSON v1 e v2.
- Suite os_lms completa (esclusa la parte AI).
- Browser, sul sito locale:
  - riquadro e etichette che cambiano mentre si sceglie;
  - clic su una riga → focus ed evidenziazione;
  - Salva/Applica preset con l'anteprima;
  - dopo le prove, valori salvati invariati (o ripristinati a quelli dell'utente).

## 6. Decisioni da prendere

| # | Domanda | Proposta |
|---|---|---|
| G1 | Avvisare anche quando un colore è **come lo standard** ma sotto AA (es. testo secondario 4,17)? | **No, solo una nota grigia.** L'avviso arancione solo se il brand peggiora la leggibilità; altrimenti segnaleremmo sempre 3–4 problemi su un form vuoto. |
| G2 | Quali coppie? | **Le 22 del §2.3** (testo e i tre controlli «non testo»). Niente bordi: lo standard stesso è a 1,3. |
| G3 | La Base corregge da sola i grigi del testo con sfondi medi o scuri (§3.3)? | **Sì.** Con sfondi chiari non cambia nulla; con quelli medi evita testi invisibili. Il riquadro resta per i casi che il calcolo non risolve, come i pulsanti principali grigi. |
| G4 | Il preset salva i valori del form non ancora salvati? | **Sì**, come l'Esporta: si può provare un brand nell'anteprima e salvarlo come preset senza applicarlo. |
| G5 | Preset già pronti forniti da noi? | **No** per ora. Si possono aggiungere più avanti come record del doctype. |

Stima: **1,5–2 giornate**: contrasto 0,75–1, Base 0,25–0,5, preset 0,5. Il PIANO diceva 1–1,5;
in più c'è la correzione della Base (§3.3).

## 7. Esito dell'implementazione

Implementata il 2026-11-09 sul sito Docker locale, senza commit (dettaglio: `docs/WORKLOG.md`, Attività 8).

- **Differenze rispetto al §3.**
  - Le coppie sono 22, in parte diverse dal §2.3. Il segnaposto si misura dentro i campi
    (sfondo `--surface-gray-2`) e non sulla pagina; in più c'è il testo nei campi.
  - Il riepilogo al salvataggio è in `on_update` e non in `validate`: compare solo se il
    salvataggio è riuscito («Salvato. Questi colori…»).
  - Il riquadro si aggiorna anche ad anteprima chiusa, con la stessa chiamata.
  - **Corretto un difetto dell'Importa**, che i preset avrebbero reso frequente: un file che
    cambia la modalità faceva partire la domanda «vuoi partire dai colori della modalità
    precedente?», che poteva sovrascrivere i valori appena caricati. Durante l'applicazione di
    un file o di un preset la domanda è sospesa.
- **Limite della correzione della Base** (§3.3). Il ruolo «Barra laterale — testo» scrive 5 grigi
  a distanze di luminosità fisse dal più scuro. Su sfondi medi, anche col più scuro portato al
  nero, il più chiaro (testo secondario della barra laterale) arriva a circa 3:1 contro il 3,9:1
  standard. Resta segnalato nel riquadro e il clic porta allo Sfondo. Superarlo richiederebbe di
  comprimere le distanze tra i grigi, e la Base copiata nell'Avanzata non darebbe più lo
  stesso CSS.
- **Effetto sui colori Base già salvati sul sito locale** (`#4F9DD9` di sfondo):
  - prima: testo 4,0:1, testo secondario 1,4:1;
  - ora: testo e testo secondario scuri e leggibili, segnaposto invariato;
  - segnalati ancora 3 punti: testo secondario della barra laterale 3,1:1, pulsante principale
    grigio sulla pagina 1,9:1, anello di focus 1,5:1;
  - a schermo tornano leggibili le schede del corso, la briciola «Corsi», il contatore delle
    notifiche e la versione.
- **Esito delle prove nel browser** (Administrator, Brand Customize):
  - riquadro «Leggibilità» in italiano;
  - clic su una riga → focus sul campo (`base_background` in Base);
  - in Avanzata con il testo `#dddddd`: «Contrasto basso (1,4:1)» accanto al campo e 4 righe nel
    riquadro; etichette «AA ✓» o «Come lo standard» sugli altri campi;
  - «Salva come preset» salva anche i valori non salvati (G4) e avvisa;
  - «Applica preset» mostra elenco con modalità e data, poi la conferma con il numero di valori;
    il form torna in Avanzata senza la domanda sul cambio di modalità;
  - dopo le prove: modifiche scartate, preset di prova cancellato per nome, valori salvati
    invariati.
- **Non verificato nel browser**: il riepilogo al salvataggio, perché richiederebbe di salvare
  sopra i colori dell'utente. È coperto dal test `TestSaveSummary`.
