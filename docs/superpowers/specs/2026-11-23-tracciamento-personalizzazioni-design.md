# Tracciamento automatico delle personalizzazioni e confronto con l'upstream — design

Data: 2026-11-23 · Stato: bozza da approvare · Autore: Claude Code (Opus 5.5) con Riccardo Liciotti

## 1. Intento

Il fork `os_lms` porta sopra `frappe/lms` centinaia di modifiche: innesti in file upstream,
funzionalità intere nell'app `apps/os_lms`, componenti frappe-ui copiati, traduzioni. Il
99% di queste modifiche è scritto da Claude Code.

Due esigenze del committente:

1. **Tracciare tutto, sempre, da solo.** Ogni modifica, personalizzazione o funzionalità
   nuova deve lasciare traccia di *cosa* è stato fatto e *perché*, senza doverlo ricordare.
   All'aggiornamento upstream deve essere possibile vedere l'elenco completo delle proprie
   personalizzazioni, raggruppate per funzionalità.
2. **Preferenza per l'upstream, ma sempre su decisione umana.** Se una release upstream
   porta una funzionalità che può soppiantare una nostra, la skill di aggiornamento deve
   **sempre fermarsi e chiedere**, presentando un confronto fra le due. Decide chi usa la
   skill; la skill raccomanda, non sceglie.

### Perché l'impianto attuale non basta

L'inventario `docs/customizations/spa-grafts.toml` (374 voci, revisione del 2026-11-23,
worklog Attività 6) registra **dove** è stato toccato il codice upstream con ancore
testuali. Limiti verificati:

- descrive righe, non funzionalità: non serve a confrontare una novità upstream con una
  nostra funzionalità;
- le funzionalità che vivono solo in `apps/os_lms` (TrueSkill, OS Audit, Coach AI, API
  Elite, ruoli Gestore/Docente/Valutatore, classi live in bozza…) quasi non compaiono, ma
  sono proprio quelle che l'upstream può sostituire;
- il tracciamento dipende dal marcatore `OSLMS-CUSTOM` e dall'hook Stop, che controlla solo
  `C3`: uno spostamento di codice (refactor `206d5cd89`, `Settings.vue`) ha lasciato 3 `C1`
  senza che nessuno se ne accorgesse;
- 25 ancore esistono anche nel file upstream puro e non possono mai segnalare una perdita;
  1 ancora non è unica;
- `it.po` non ha protezione; la base delle pagine congelate non è registrata;
- molta conoscenza "da riapplicare dopo i merge" vive solo nella memoria personale di
  Claude su questo Mac (`~/.claude/projects/.../memory/`, 13 file), non nella repo.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**

- O1. Nessuna modifica a codice upstream o a codice nostro entra in un commit senza essere
  attribuita a una funzionalità del catalogo.
- O2. All'aggiornamento, una **mappa calcolata** da git elenca *tutte* le nostre differenze
  rispetto all'ultima release upstream fusa, raggruppate per funzionalità; nulla resta
  fuori, anche senza marcatore o dopo uno spostamento.
- O3. Un **catalogo delle funzionalità** in repo descrive per ciascuna cosa fa, per chi,
  con quali regole osservabili, e cosa cercare nelle release upstream.
- O4. A ogni release attraversata, la skill individua le novità upstream che potrebbero
  soppiantare una nostra funzionalità, produce un confronto e **chiede sempre**.
- O5. Le lacune di protezione emerse nella revisione (C1/C2 non controllati in corso
  d'opera, ancore deboli, `it.po`, base delle pagine congelate, `upstream-check` ferma alla
  Fase 0) sono chiuse.

**Non obiettivi**

- Correggere il calcolo del percorso fra le linee `v15`/`v16` in `upstream_plan.py`
  (criticità 1 della revisione): è un difetto del piano, non del tracciamento. **Va fatto
  prima del prossimo aggiornamento**, come attività separata.
- Scrivere test applicativi per le 295 voci senza test, o spostare le suite al ciclo per
  release (criticità 4 e 5): attività separate.
- Controllare in CI la riga `Oslms-Feature` dei commit: per il volume attuale non ripaga.
  La CI esistente (`.github/workflows/customizations.yml`) resta e viene estesa ai nuovi
  controlli dell'inventario (§5.10).
- Applicare catalogo, controllo e mappa a `master` (produzione, base `v2.58.0`, frappe-ui
  v1) o a `develop`: si lavora **solo su `feature/oslms` e sui branch che ne derivano**.
  Quando una modifica viene rifatta su `master` si conserva la riga `Oslms-Feature` nel
  commit, ma su `master` nulla viene controllato.

**Anti-obiettivi** (sarebbe un fallimento anche se funzionasse)

- Una skill che adotta o scarta da sola una funzionalità nostra in favore dell'upstream.
- Un controllo così rumoroso che Claude impara ad aggirarlo (`Oslms-Feature: none` usato
  ovunque, schede vuote o generiche).
- Un catalogo che descrive il codice invece del comportamento: non servirebbe al confronto.
- Perdere le 374 voci attuali o il loro `intent` nella migrazione.

## 3. Vincoli

- Python solo libreria standard, come rilevatore e piano (nessun bench, nessun Docker).
- Commenti e identificatori in inglese; documenti e messaggi all'utente in italiano.
- Commit in Conventional Commits (commitlint in CI); ogni commit di codice porta già
  `Version: X.Y.Z` e `Co-Authored-By:` in fondo e aggiorna l'etichetta `versionApp` in
  `frontend/src/components/Sidebar/AppSidebar.vue` (file upstream, voce
  `sidebar-app-version-label`).
- Molti branch di funzionalità in parallelo (`feature/oslms`, `feature/os-audit`,
  `feature/esg*`, …): il formato del catalogo non deve generare conflitti a ogni merge fra
  branch.
- Su questo repo esiste `.pre-commit-config.yaml` ma `pre-commit` non è installato negli
  hook di `.git/hooks`; `core.hooksPath` non è impostato.
- Il committente vuole essere interpellato prima di ogni modifica (memoria
  `ask_before_changes_read_freely`): la migrazione propone, l'utente approva.

## 4. Approcci considerati

| | Approccio | Pro | Contro |
| --- | --- | --- | --- |
| A | Rafforzare l'hook Stop di Claude | modifica minima | copre solo le sessioni Claude; unità sbagliata (il turno, non il commit) |
| B | Hook git sul commit + CI, con riga `Oslms-Feature` | vale per tutti | il "dove" resta scritto a mano; attrito sui commit manuali |
| **C** | **Mappa del "dove" calcolata da git + catalogo delle funzionalità per il "perché", con controllo al commit** | niente può sfuggire; confronto con upstream per funzionalità | migrazione iniziale delle 374 voci |

**Scelto: C**, dal committente, il 2026-11-23. Dato che il 99% dei commit li fa Claude, il
controllo è pensato per Claude (messaggi d'errore che dicono esattamente cosa scrivere) e
l'attrito sui commit manuali non è un criterio.

## 5. Design

### 5.1 Concetti

- **File upstream**: un file presente nell'albero dell'ultima release upstream fusa in
  `HEAD` (la stessa base che calcola `find_base()` di `upstream_plan.py`).
- **Codice nostro**: `apps/os_lms/**`, `frontend/src/oslms/**`, `frontend/src/overrides/**`,
  `frontend/oslms-vite/**`, e i file creati da noi dentro cartelle upstream (non presenti
  nella base).
- **Funzionalità**: un'unità di comportamento che un utente riconosce ("classi live in
  bozza", "ruolo Valutatore per classe", "certificati TrueSkill"). Ha una **scheda** nel
  catalogo. Le voci attuali dell'inventario diventano **siti** di una funzionalità.

### 5.2 Il catalogo delle funzionalità

Una cartella `docs/customizations/features/`, **un file TOML per funzionalità**
(`<id>.toml`): file separati evitano i conflitti fra branch paralleli che un file unico
avrebbe a ogni nuova scheda.

Campi della scheda:

| Campo | Obbl. | Contenuto |
| --- | --- | --- |
| `id` | sì | kebab-case, uguale al nome del file, unico |
| `title` | sì | titolo in italiano, come lo direbbe un utente |
| `status` | sì | `active`, `retired` (rimossa da noi), `replaced-by-upstream` (sostituita, con riferimento alla release e alla decisione) |
| `summary` | sì | cosa fa, per chi, in 2-5 frasi di linguaggio non tecnico |
| `why` | sì | perché esiste: esigenza del cliente o lacuna upstream che colma |
| `roles` | no | ruoli coinvolti (`Gestore`, `Docente`, `Valutatore`, `Student`, …) |
| `behaviour` | sì | elenco di **regole osservabili**, una per riga, verificabili da fuori ("una classe live nuova nasce in bozza", "gli inviti partono solo alla pubblicazione"). È la base del confronto con l'upstream |
| `areas` | sì | percorsi o glob del codice che le appartiene per intero (moduli os_lms, componenti nostri) |
| `upstream_watch` | sì | indizi da cercare nelle release upstream: parole chiave, doctype, campi, endpoint, nomi di pagina. Es. `["live class", "LMS Live Class", "draft", "publish"]` |
| `data` | no | dati che la funzionalità possiede (custom field, doctype, impostazioni): servono a stimare la migrazione se si adotta l'upstream |
| `tests` | no | test che ne verificano il comportamento |
| `notes` | no | conoscenza operativa: insidie, cosa riverificare dopo i merge (qui confluisce quanto oggi sta nella memoria di Claude) |
| `history` | sì | eventi: creazione, cambi di comportamento rilevanti, decisioni di confronto con l'upstream (data, commit o release, sintesi) |

Le voci di `spa-grafts.toml` restano dove sono e guadagnano un campo obbligatorio
`feature = "<id>"`. Le ancore restano l'allarme veloce sulle righe critiche; il catalogo
porta il significato.

Il caricamento (`scripts/customizations/model.py`) valida: campi obbligatori, `id` = nome
file, ogni `feature` delle voci esiste, ogni scheda `active` ha almeno un sito o un'area.

### 5.3 La riga `Oslms-Feature` nei commit

Ogni commit che tocca file upstream o codice nostro porta una o più righe in fondo al
messaggio, fra le altre righe finali:

```
feat(live-class): save every live class as a draft and publish it separately

…

Version: 1.16.80
Oslms-Feature: live-class-draft-publish
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

- Più funzionalità nello stesso commit: più righe.
- Commit che toccano solo documentazione, report, worklog, script di supporto o test di
  strumenti non la richiedono.
- Unica deroga ammessa: `Oslms-Feature: none (<motivo>)` per modifiche senza effetto sul
  comportamento (formattazione, rinomina interna). Il motivo è obbligatorio e la deroga
  non è ammessa per commit `feat` o `fix`.
- Il bump di versione in `AppSidebar.vue` (sola riga `versionApp`) non conta come modifica
  a file upstream ai fini del controllo.

Questa riga è ciò che permette alla mappa (§5.5) di attribuire ogni differenza a una
funzionalità, leggendo la storia di git.

### 5.4 Il controllo al commit

Uno script `scripts/commit_guard.py`, eseguito come hook git `commit-msg` da una cartella
tracciata `.githooks/` (attivata con `git config core.hooksPath .githooks`). Il controllo
è nel commit perché è l'unità di lavoro e perché vale qualunque sia la strada con cui Claude
(o una persona) fa il commit.

Cosa verifica, sui file in stage e sul messaggio:

1. **Attribuzione**: se il commit tocca file upstream o codice nostro, c'è almeno una riga
   `Oslms-Feature` valida e ogni `id` ha una scheda (nella versione in stage).
2. **Scheda nuova o aggiornata**: per i commit `feat`, la scheda di almeno una funzionalità
   citata è nello stage (creata o aggiornata in `behaviour`/`history`). Per gli altri tipi,
   se il commit tocca un'area della funzionalità ma non la scheda, stampa un **promemoria non
   bloccante** ("se il comportamento è cambiato, aggiorna `behaviour`").
3. **Inventario integro sullo stage**: esegue `C1`, `C2`, `C3` e i nuovi `C5`/`C6` (§5.7)
   sull'albero in stage, limitati ai file del commit. Uno spostamento di codice che lascia
   un'ancora orfana blocca il commit: è il caso `Settings.vue` che oggi passa inosservato.
4. **Deroga** `none`: motivo presente, tipo di commit ammesso.

Esenti: commit di merge fra branch nostri e `git revert` (ereditano le righe del commit
annullato).

**Merge upstream del percorso**: non sono esenti. Le risoluzioni dei conflitti che
riapplicano i nostri innesti nascono dentro il commit di merge (oggi 19 file differiscono
da `v2.66.0` solo per effetto di merge), quindi la skill, al Passo 6.4, aggiunge al
messaggio predefinito una riga `Oslms-Feature` per ogni funzionalità le cui voci ha
applicato in F1. Il controllo accetta un merge upstream senza righe solo se non ci sono
stati conflitti.

**Base non calcolabile** (clone senza `git fetch upstream --tags`): il controllo blocca il
commit e dice il comando da eseguire. Dato che i commit li fa Claude, lanciare il fetch
costa poco, mentre un controllo che si spegne in silenzio non protegge nulla.

**Messaggi d'errore scritti per Claude**: dicono il file, la regola violata e il testo
esatto da aggiungere ("aggiungi `Oslms-Feature: <id>` dopo `Version:`; funzionalità
candidate in base alle aree toccate: `live-class-draft-publish`, `live-class-docente-manage`").
Lo script propone le candidate confrontando i file toccati con `areas` e siti delle schede.

**Attivazione garantita**: l'hook Stop esistente (`inventory_guard.py`) diventa anche il
controllo che `core.hooksPath` sia impostato su `.githooks`; se non lo è, lo segnala una
volta per sessione con il comando da eseguire. Non lo imposta da solo (è una modifica alla
configurazione che il committente approva).

**Istruzioni a Claude**: una sezione in `CLAUDE.md` del progetto spiega la regola (riga
`Oslms-Feature`, quando creare o aggiornare una scheda, cosa scrivere in `behaviour`), così
Claude la applica prima di arrivare al rifiuto dell'hook.

### 5.5 La mappa calcolata

Un comando `scripts/customization_map.py` (sola lettura) produce, per un ref (default
`HEAD`) rispetto alla sua base upstream:

- per ogni file upstream che differisce dalla base: i blocchi di differenza
  (`git diff <base> <ref>`), ciascuno attribuito a una o più funzionalità;
- per ogni funzionalità: i file e i blocchi che le appartengono, i commit che li hanno
  introdotti, la scheda;
- l'elenco dei **blocchi non attribuiti**, che è il numero da portare a zero.

Ordine di attribuzione di un blocco:

1. commit che lo ha introdotto (`git blame` sulle righe aggiunte; per le righe upstream
   rimosse, il commit nostro che le ha tolte) → sue righe `Oslms-Feature`;
2. se il commit è anteriore alla regola: il blocco contiene o tocca l'ancora di una voce →
   `feature` della voce;
3. il file ricade in `areas` di una scheda → quella scheda;
4. il file compare nella **mappa della storia passata** (sotto) → le funzionalità elencate
   per quel file;
5. altrimenti: **non attribuito**.

**Mappa della storia passata.** I commit anteriori alla regola non hanno la riga e le
ancore coprono solo le righe che proteggono: da soli non bastano per i file upstream che
mescolano più funzionalità. Si aggiunge un file tracciato
`docs/customizations/legacy-attribution.toml`, scritto una volta nella migrazione, che
associa **file upstream → funzionalità** (anche più d'una per file). La chiave è il
percorso del file, non lo SHA del commit, perché gli SHA non sopravvivono alle riscritture
della storia (`feature/os-audit`) né ai porting. L'attribuzione è più grossolana (a livello
di file, non di blocco), ma basta allo scopo: sapere quali funzionalità vivono in quel
file. Il file non si aggiorna più dopo la migrazione: i commit nuovi portano la riga.
Ordine di grandezza: circa 970 file differiscono da `v2.66.0`, ma tolti lock, documenti,
traduzioni e file nostri, i file upstream da associare sono molti meno. Il costruttore li
conta come primo passo della migrazione.

Uscite: tabella leggibile, `--json` per la skill, `--feature <id>` per una sola
funzionalità. Esclusi come oggi: lock file e file generati. Le traduzioni (`it.po`) sono
trattate a parte (§5.7).

### 5.6 Cambiamenti alla skill `upstream-upgrade`

**Nuovo Passo 2b — mappa delle personalizzazioni.** Dopo il piano, la skill esegue la
mappa e la mostra al committente per funzionalità: titolo, sintesi, quanti file upstream
toccati, quali release in arrivo toccano quei file o i suoi `upstream_watch`. I blocchi non
attribuiti diventano una fermata (come oggi F7): si attribuiscono prima di partire.

**F5 riscritta — novità upstream che potrebbero soppiantare una nostra funzionalità.**
Per ogni release, prima del merge:

1. *Candidati.* Incrocia i commit `P..T` (soggetti **e corpi**), i file cambiati, i doctype,
   campi, endpoint e stringhe nuove con `upstream_watch`, `areas`, `data` e siti di ogni
   scheda `active`, comprese le funzionalità che vivono solo in `apps/os_lms` e che il merge
   non tocca.
2. *Confronto*, per ogni candidato, scritto nel rapporto di percorso:
   - cosa fa la novità upstream (leggendo il codice di `T`, non solo i messaggi);
   - tabella delle regole `behaviour` della nostra scheda: per ciascuna, coperta / coperta
     in parte / non coperta dall'upstream, con la prova;
   - ruoli: chi può fare cosa nell'una e nell'altra;
   - dati: cosa andrebbe migrato (nostri custom field contro campi upstream);
   - livello di somiglianza in parole (alta / parziale / bassa) con il motivo; nessun
     punteggio numerico;
   - cosa si perde e quanto costa ciascuna strada;
   - raccomandazione motivata.
3. *Domanda, sempre.* `AskUserQuestion` per ogni candidato con somiglianza alta o parziale,
   **anche quando la raccomandazione è chiara**. Opzioni:
   - adottare l'upstream e ritirare la nostra;
   - adottare l'upstream e riportare sopra solo le regole non coperte;
   - mantenere la nostra;
   - rimandare: il percorso si ferma a `P`.
   I candidati a somiglianza bassa vanno in una riga del rapporto, senza domanda.
4. *Registrazione.* La decisione va nello stato del percorso (`decisions`) e nella
   `history` della scheda.

**Esecuzione dell'adozione** (dopo la risposta): commit dedicati; la scheda passa a
`replaced-by-upstream` (o resta `active` con `behaviour` ridotto alle regole riportate);
le voci collegate diventano `accepted-drift` con data e motivo; il codice nostro superato
si rimuove; se ci sono dati, si scrive una patch di migrazione e la si fa approvare. Ogni
commit porta `Oslms-Feature: <id>`.

**Altre modifiche alla skill**: Passo 5, gli errori trovati dal rilevatore in partenza
diventano una fermata da chiudere, non una baseline da ignorare; Passo 4, rimosse le note
datate su `feature/esg`/`feature/esg-bias-tests`; Passo 7, la lista delle prove nell'app
include le funzionalità adottate dall'upstream.

### 5.7 Lacune di protezione chiuse

- **`C5` — ancora non probatoria** (avviso, errore sulle voci nuove): l'ancora compare anche
  nel file dell'ultima release upstream fusa, quindi non distingue la nostra versione da
  quella upstream. Le 25 voci attuali si sistemano nella migrazione: ancora nuova, oppure
  `accepted-drift` se l'upstream ha adottato la modifica.
- **`C6` — ancora non unica** (errore): l'ancora compare più di una volta nel file.
- **Traduzioni.** Un file `docs/customizations/translations-it.toml` non scritto a mano ma
  generato: le coppie `msgid → msgstr` di `lms/locale/it.po` che differiscono dalla versione
  upstream della base. Il rilevatore aggiunge `C7`: una coppia registrata che non c'è più o
  è cambiata. La skill lo usa in F1 sulle traduzioni ("prendi upstream e riapplica") per
  sapere cosa riapplicare. Il file si rigenera alla chiusura di ogni percorso e quando il
  commit tocca `it.po`.
- **Pagine e componenti congelati.** Le voci `override-file` di pagine e componenti copiati
  guadagnano `frozen_from` (tag upstream o versione frappe-ui da cui è stata fatta la copia).
  Con questo la skill può fare il confronto a tre vie che oggi il §9 del progetto del
  percorso esclude. Per i componenti frappe-ui: al bump, confronto automatico fra il
  componente originale della versione `frozen_from` e quello della versione nuova.
- **`upstream-check`** allineata: via i riferimenti alla Fase 0, riferimento di partenza
  `start_commit` dello stato invece di `HEAD^1`, guardia sui branch che tiene conto di
  `feature/oslms`, sezione del rapporto per funzionalità usando la mappa.

### 5.8 Migrazione iniziale

Una tantum, fatta da Claude, approvata dal committente a lotti:

1. Proposta dell'elenco delle funzionalità: raggruppamento delle 374 voci (per ruolo,
   pagina, area) più le funzionalità di `apps/os_lms` che non hanno voci. Il committente
   approva l'elenco (nomi e confini) prima di scrivere le schede.
2. Scrittura delle schede a lotti per area, ciascuna con `behaviour` ricavato da codice,
   test, commit, worklog e documenti di design in `docs/superpowers/specs/`.
3. Trasferimento nelle `notes` delle schede della conoscenza oggi solo nella memoria di
   Claude (i file di memoria "da riapplicare dopo i merge"). Le memorie restano, con un
   rimando alla scheda.
4. Campo `feature` su tutte le voci; correzione dei 3 `C1` attuali, delle 25 `C5` e
   dell'ancora non unica.
5. Generazione di `translations-it.toml` e dei `frozen_from` (ricostruiti dalla storia git
   dei file copiati; se non ricostruibili, si dice e si chiede).
6. Mappa su `feature/oslms` con **zero blocchi non attribuiti**, oppure con un elenco
   residuo esplicito approvato dal committente.
7. Attivazione di `.githooks` e della sezione in `CLAUDE.md`.

Un commit per lotto: `docs(customizations): catalogue <area> features`.

**Ordine rispetto ai branch aperti** (decisione del committente): la migrazione si fa
subito su `feature/oslms`. Gli altri branch aperti (`feature/os-audit`, `feature/esg*`,
`feature/manager-settings`, `feature/live-class-draft`, …) si riallineano dopo, uno alla
volta, quando vengono ripresi: si risolvono i conflitti su `spa-grafts.toml` aggiungendo
`feature` alle voci nuove e si scrivono le schede che mancano. I loro commit già fatti non
si correggono: li coprono la mappa della storia passata e le ancore. Il primo branch da
riallineare è quello corrente, `feature/live-class-draft`, che ha modifiche non committate
all'inventario: vanno committate prima della migrazione o riportate subito dopo.

### 5.9 Verifiche

- Test unitari in `scripts/tests/` per: caricamento e validazione delle schede, regole del
  `commit_guard` (attribuzione, deroghe, esenzioni, bump di versione, C1-C6 sullo stage),
  attribuzione dei blocchi nella mappa (con repo git di prova creati nel test, come fa già
  `test_upstream_plan.py`), `C5`, `C6`, `C7`.
- Prova reale: un commit di prova senza riga viene rifiutato con il messaggio atteso; con
  la riga passa; uno spostamento di codice che orfana un'ancora viene bloccato.
- Mappa su `feature/oslms` e sul branch corrente: zero non attribuiti dopo la migrazione.
- Simulazione di F5 su una release già attraversata, come `v2.65.0`, con le schede
  migrate: verifica che emergano i candidati attesi (es. i controlli di permesso upstream
  sulle aree Docente/Valutatore già noti dal percorso v2.65).

### 5.10 CI esistente

`.github/workflows/customizations.yml` esegue già test degli script e rilevatore a ogni
PR e a ogni push su `develop` e `feature/oslms`, ma con un checkout superficiale e senza
tag upstream. I controlli che dipendono dalla base (`C5`, `C7`, la validazione delle aree)
ne hanno bisogno, quindi il workflow passa a `fetch-depth: 0` più il fetch dei tag da
`https://github.com/frappe/lms.git`. Se il fetch fallisce, quei controlli vengono riportati
come avvisi invece di far fallire il job. Le PR da branch anteriori alla migrazione falliranno
sul campo `feature` obbligatorio finché non vengono riallineate: è voluto.

## 6. Decisioni del committente

- Approccio C (mappa calcolata + catalogo + controllo al commit), 2026-11-23.
- Davanti a una funzionalità upstream che può soppiantare una nostra si chiede **sempre**;
  decide chi usa la skill, la skill raccomanda. 2026-11-23.
- Il controllo è pensato per Claude, che fa il 99% dei commit. 2026-11-23.
- Solo `feature/oslms` e i branch che ne derivano; `master` escluso. 2026-11-23.
- Migrazione subito su `feature/oslms`, branch aperti riallineati dopo. 2026-11-23.

## 7. Scelte lasciate al costruttore (o fatte da Claude, da rivedere)

- *Scelta di Claude:* un file TOML per scheda, per evitare conflitti fra branch.
- *Scelta di Claude:* hook `commit-msg` in `.githooks/` con `core.hooksPath`, non tramite il
  framework `pre-commit` (non installato). Il costruttore verifica che non entri in
  conflitto con un eventuale `pre-commit install` futuro.
- *Scelta di Claude:* nessun controllo della riga `Oslms-Feature` in CI; CI esistente
  estesa con storia completa e tag upstream, avvisi se il fetch fallisce.
- *Scelta di Claude:* mappa della storia passata a livello di file, con chiave il percorso.
- *Scelta di Claude:* i merge upstream del percorso portano le righe `Oslms-Feature`
  delle funzionalità riapplicate nei conflitti.
- *Scelta di Claude:* senza tag upstream il controllo al commit blocca e dice come fare il
  fetch.
- *Scelta di Claude:* livello di somiglianza qualitativo, nessun punteggio numerico.
- Al costruttore: algoritmo esatto di attribuzione delle righe rimosse, formato delle
  uscite della mappa, elenco preciso dei percorsi "codice nostro" e "esenti", soglie del
  promemoria non bloccante.
