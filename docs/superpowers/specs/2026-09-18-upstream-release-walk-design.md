# Aggiornamento upstream guidato, release per release — documento di progetto

**Data:** 2026-09-18
**Stato:** progetto parziale — cinque decisioni prese con il committente, sezioni di dettaglio scritte ma **non ancora riviste**; §13 elenca ciò che resta da decidere. Aggiornato il 2026-09-18 con i dati di ampiezza reale (§3.4-3.5) e la forma di avvio interattiva (§6.2.1). **Il 2026-09-23 aggiunta la §15: mandato di costruzione della versione 1, da cui parte chi deve realizzare `/upstream-upgrade`.**
**Branch di riferimento:** `feature/oslms`
**Destinatari:** il supervisore del progetto e ogni sessione di sviluppo futura (umana o AI) che debba costruire o usare questo sistema.
**Documento collegato:** [`2026-09-18-upstream-regression-harness-design.md`](2026-09-18-upstream-regression-harness-design.md) — il sistema di verifica delle personalizzazioni, di cui questo è la naturale prosecuzione e da cui dipende.

> **Nessuna operazione è stata eseguita.** Questo documento è solo progettazione: nessun aggiornamento è stato scaricato, nessun merge tentato, nessun remote configurato. I dati del §3 provengono da interrogazioni in sola lettura dell'API pubblica di GitHub e dalla lettura del repository locale.

---

## 1. Obiettivo

Costruire uno strumento che, su richiesta e indicando una versione di arrivo, attraversi **una release upstream alla volta** a partire dalla più vecchia non ancora recepita, e per ciascuna:

1. tenti l'aggiornamento e risolva i conflitti **senza cancellare le personalizzazioni**;
2. implementi le novità dell'upstream;
3. legga le **note di release** per capire cosa viene introdotto, se una novità **sostituisce** qualcosa che il progetto già ha, o se **rende obsolete** funzionalità in uso.

Requisiti espressi dal committente:

1. L'avvio è manuale e indica la versione di arrivo: «faccio partire un agente indicando quale versione aggiornare».
2. Si procede **a step di release**, dalla più vecchia in avanti, non con un unico salto.
3. L'agente si attiva sui conflitti e decide come risolverli, con l'attenzione esplicita a non cancellare le personalizzazioni.
4. Deve leggere le note di release e ragionare su sostituzioni e deprecazioni.
5. **La precisione conta più della velocità**: è una quantità di lavoro rilevante e non tollera approssimazione.

---

## 2. Il problema, in concreto

Oggi l'aggiornamento è un'operazione manuale, non riproducibile e senza rete di sicurezza. Tre fatti rilevati sul repository il 2026-09-18.

**Manca il presupposto tecnico.** `git remote -v` mostra solo `origin` (`mrossi-os/lms`, il fork). **Non esiste un remote verso `frappe/lms`.** Il branch `develop`, che secondo la strategia di manutenzione dovrebbe essere lo specchio pulito dell'upstream, è fermo al **19 marzo 2026**, mentre l'ultimo merge upstream reale (`v2.58.0`, branch `merge/upstream-v2.58.0`) è del **2 luglio 2026**. Quel merge è quindi stato fatto agganciando l'upstream fuori dalla configurazione del repository. Oggi, dentro questo repository, **non esiste un modo riproducibile di rispondere alla domanda «cosa c'è di nuovo a monte»**.

**`git rerere` non è attivo.** È il terzo lever della strategia di manutenzione del progetto e non è mai stato abilitato (`git config rerere.enabled` non è configurato).

**Ventiquattro componenti non ricevono nulla.** In `frontend/src/overrides/` vivono 24 file `.vue` serviti dal plugin `osOverrideTheme` al posto degli originali: `CourseOverview.vue`, l'intero gruppo `DataImport` (7 file), `TextEditor` e i suoi componenti, `Combobox`, `Switch`, `Link`, `Autocomplete`, `FileUploader`, `CalendarPanel`, `ListSelectBanner` e altri. Per questi l'upstream non produce **né conflitto né aggiornamento né segnale**: se una correzione arriva a monte, semplicemente non la si riceve e nessuno lo viene a sapere.

---

## 3. Stato di fatto misurato

Dati raccolti il 2026-09-18 via `git ls-remote` e API pubblica GitHub, senza autenticazione e senza scaricare oggetti.

### 3.1 Le release da attraversare

Dall'ultimo merge (`v2.58.0`) alla più recente (`v2.63.0`) ci sono **8 release**:

| Release | Data | PR nelle note | di cui `feat` | rotture dichiarate (`!`) |
| --- | --- | ---: | ---: | ---: |
| v2.58.1 | 2026-07-07 | 7 | 0 | 0 |
| v2.59.0 | 2026-07-16 | 206 ⚠️ | 29 | 0 |
| v2.60.0 | 2026-07-24 | 6 | 1 | 0 |
| v2.60.1 | 2026-07-28 | 4 | 0 | 0 |
| v2.61.0 | 2026-07-30 | 26 | 5 | 0 |
| v2.62.0 | 2026-08-25 | 26 | 4 | 0 |
| v2.62.1 | 2026-08-28 | 4 | 0 | 0 |
| **v2.63.0** | 2026-09-10 | 12 | 4 | **3** |

Otto passi sono una quantità gestibile: l'approccio a step è praticabile. Sarebbe un'altra questione con trenta o più, il che è un argomento per aggiornare con **cadenza regolare** anziché a grandi salti (§12).

### 3.2 Le note di release mentono sull'ampiezza

Le note di `v2.59.0` citano 206 PR, ma **193 di esse hanno numero inferiore alla #2542**, già inclusa in `v2.58.1`: sono note rigenerate contro una base molto più vecchia, che descrivono mesi di lavoro già presenti nell'albero.

**Conseguenza vincolante di progetto:** l'ampiezza di una release si ricava **esclusivamente** dal diff dei commit fra due tag (`git log <tag_precedente>..<tag>`). Le note servono **solo a interpretare l'intento** dei commit che quel diff contiene. Un agente che si fidasse delle note, su `v2.59.0` si metterebbe a "importare" 193 modifiche già possedute.

### 3.3 Le rotture dichiarate colpiscono le aree più personalizzate

Il progetto upstream usa Conventional Commits, quindi le rotture sono marcate con `!` e sono **rilevabili a macchina**. In `v2.63.0` ce ne sono tre:

| Rottura | Impatto atteso su questo progetto |
| --- | --- |
| `fix(lesson)!: stop lesson content being destroyed on save` | **Alto.** L'area del contenuto lezioni porta circa 2.700 righe di personalizzazione e 52 commit: blocchi quiz, compito ed esercizio, upload con player, embed a nove servizi, strumenti inline colore e allineamento con allowlist lato server |
| `feat(quiz)!: rebuild quiz authoring around a shared question bank` | **Alto.** Riscrittura dell'authoring dei quiz; il progetto ha il blocco quiz dentro l'editor a blocchi delle lezioni |
| `feat(raven)!: sync channel membership from LMS rules` | Presumibilmente nullo: integrazione Raven non in uso |

Queste due sono esattamente il caso descritto dal committente — novità upstream che **sostituiscono** qualcosa già presente — e si trovano nell'**ultima** release del percorso, cioè quella che si incontra dopo aver già investito il lavoro sulle sette precedenti.

### 3.4 Ampiezza reale, misurata dopo il collegamento del remote (2026-09-18)

Il remote `upstream` è stato configurato e il `fetch` eseguito dal committente il 2026-09-18. Questo ha permesso di sostituire le stime basate sulle note con misure dal diff dei commit. **Il quadro cambia in tre punti.**

**Le note sbagliano in entrambe le direzioni.** Ampiezza reale totale `v2.58.0..v2.63.0`: **513 commit, 672 file, +109.960 / −35.319 righe.**

| Release | Note dicevano | Commit reali | File reali |
| --- | ---: | ---: | ---: |
| v2.58.1 | 7 PR | 23 | 19 |
| v2.59.0 | 206 PR | 91 | 195 |
| v2.60.0 | 6 PR | 15 | 47 |
| v2.60.1 | 4 PR | 9 | 6 |
| v2.61.0 | 26 PR | 96 | 269 |
| **v2.62.0** | 26 PR | **200** | **515** |
| v2.62.1 | 4 PR | 14 | 7 |
| v2.63.0 | 12 PR | 65 | 155 |

Le note **sottostimano** quasi ovunque (`v2.62.0`: 26 PR dichiarate, 200 commit reali) e **sovrastimano** su `v2.59.0`. Il vincolo di §3.2 ne esce rafforzato e generalizzato: le note non sono una misura di ampiezza in nessuna delle due direzioni.

**I file personalizzati sono quasi tutti nel percorso.** Sette degli otto file con marcatori verificati sono toccati dall'upstream in `v2.58.0..v2.63.0`: `ChapterRow.vue` da 12 commit, `CourseCardOverlay.vue`, `VideoPreview.vue`, `types/api.ts` e `BatchOverview.vue` da 4 ciascuno, `ProfileCertificates.vue` da 3, `types/lms/LMSCourse.ts` da 1. Solo `stores/mobileCta.js`, che è un file nostro, non è toccato.

**Il rischio maggiore è un bump di dipendenza, e arriva al secondo passo su otto.** Traiettoria di `frappe-ui` nel `frontend/package.json` upstream:

| Release | frappe-ui |
| --- | --- |
| v2.58.0 (dove siamo) | `^1.0.0-beta.7` |
| **v2.59.0** | **`^1.0.0-beta.24`** |
| v2.61.0 | `^1.0.0-beta.24` |
| v2.62.0 → v2.63.0 | `1.0.0-beta.29` (pin esatto) |

Due fatti dalle memorie di progetto rendono questo il rischio principale dell'intero aggiornamento:

1. **beta.24 è la versione che ha già causato un incidente in produzione** su questo progetto: la deriva del caret nel `yarn.lock` portò a beta.24 e produsse l'errore 417 su `boot_config`, assente in Frappe v16. La correzione fu il pin esatto a beta.7 su `master`; `os_lms` ha ancora il caret ([[frappeui_caret_pin_drift]]).
2. **Ventitré delle ventiquattro pagine congelate sono componenti frappe-ui dell'era beta.7.** L'override `Combobox` perde `modelValue` dai bump recenti (campi Link che appaiono vuoti pur salvando correttamente) e il fork `DataImport` richiede un ri-confronto a ogni bump.

**Questo salto non è un conflitto git:** viene fuso pulito, il rilevatore di scostamento non vede nulla, la build può passare, e le rotture si manifestano a runtime nei componenti copiati.

**Conseguenza di progetto:** il comando di pianificazione (§6.2) **deve mostrare i cambi di versione delle dipendenze** accanto a commit, file e rotture. Le note di release non li menzionano, e sono la categoria invisibile a ogni strumento del sistema.

### 3.5 Le pagine congelate si dividono in due categorie

Delle 24 in `frontend/src/overrides/`, **una sola** rispecchia un file di lms — `pages/Courses/CourseOverview.vue`, toccata da 5 commit upstream nel percorso. Le altre **23 sono componenti frappe-ui**, che le release di lms non toccano: dipendono dalla versione della libreria.

Conseguenza operativa: la Fermata 6 (§8) riguarda una sola pagina per ogni percorso di release, mentre le altre 23 vanno riconciliate **quando cambia la versione di frappe-ui**, cioè nell'attività separata di §3.4.

---

## 4. Decisioni prese

Decisioni prese dal committente il 2026-09-18. **Non vanno ribaltate senza una nuova discussione.**

| # | Decisione | Alternativa scartata e perché |
| --- | --- | --- |
| E1 | **Fermata solo quando serve.** L'agente procede da solo finché il merge è pulito, il rilevatore non segnala perdite e le note non contengono rotture o sostituzioni | Fermata a ogni release: otto interruzioni anche dove non c'è nulla da decidere. Nessuna fermata: un errore al secondo passo si propaga ai sei successivi |
| E2 | **Su una sostituzione, analisi comparativa e domanda al committente.** L'agente non decide da solo fra novità upstream e personalizzazione esistente | Preferire sempre l'upstream: fa sparire funzioni in uso senza accorgersene. Preferire sempre la propria versione: la distanza dall'upstream cresce a ogni release |
| E3 | **Verifica leggera a ogni step, completa alle fermate.** A ogni release rilevatore più build; suite completa alle fermate e a fine percorso | Completa a ogni release: bench avviato otto volte, sessione di ore. Solo alla fine: annulla il motivo per cui si procede a step, cioè sapere quale release ha rotto cosa |
| E4 | **Le 24 pagine congelate entrano nel percorso, ma solo quando l'upstream tocca l'originale.** Confronto a tre vie e proposta di riconciliazione | Attività separata: non ha scadenza naturale e tende a non essere mai svolta. Lasciarle ferme: la divergenza cresce fino a rendere la riconciliazione più costosa di una riscrittura |
| E5 | **Copione deterministico più agente ai punti di giudizio.** Il meccanico è codice, il giudizio è dell'agente | Tutto dentro la skill: ogni esecuzione leggermente diversa, passi saltabili, modello pagato per lavoro deterministico. Solo strumenti senza agente: rinuncia all'analisi di sostituzioni e deprecazioni, che è il cuore della richiesta |

### 4.1 Il ragionamento che regge E5 (da non perdere)

Nel percorso convivono due tipi di lavoro con proprietà opposte. **Meccanico e riproducibile:** scaricare l'upstream, ordinare i tag, tentare il merge, eseguire il rilevatore, scaricare e classificare le note. **Che richiede giudizio:** risolvere un conflitto sapendo cosa protegge quella riga, capire se una novità sostituisce una funzione esistente, riconciliare una pagina congelata.

Il primo tipo non deve dipendere da un modello: il giudizio non è riproducibile, e un agente che ordina otto tag può sbagliare l'ordine una volta su venti — un errore invisibile che si scopre release dopo. È la stessa divisione già adottata fra rilevatore di scostamento e test nel documento collegato.

---

## 5. Non-obiettivi

- Non si automatizza la **decisione** di aggiornare: l'avvio è manuale e indica la versione di arrivo.
- Non si decide al posto del committente fra una novità upstream e una personalizzazione esistente (E2).
- Non si valuta se un cambiamento di comportamento upstream sia **desiderabile**: è una scelta di prodotto, non una regressione da riparare.
- Non si tocca il flusso di rilascio del progetto né la sua numerazione di versione.
- Non si riscrive la storia: il percorso produce commit di merge, non un rebase dell'upstream.

---

## 6. Architettura: un motore e un pilota

### 6.1 Prerequisito, indipendente dal resto

```bash
git remote add upstream https://github.com/frappe/lms.git
git fetch upstream --tags
git config rerere.enabled true
```

Senza questo nessun passo successivo esiste. `rerere` va abilitato **prima** di iniziare il percorso e non dopo: registra le risoluzioni dei conflitti mentre si attraversano le release e le riapplica quando lo stesso conflitto si ripresenta, il che accade con frequenza sui file toccati da più release consecutive.

### 6.2 Il motore — `scripts/upstream_walk.py`

Sola libreria standard, come il rilevatore di scostamento. Quattro comandi:

| Comando | Cosa fa |
| --- | --- |
| `plan --from <tag> --to <tag>` | Per ogni tag da attraversare: **commit e file reali dal diff**, rotture dichiarate, **cambi di versione delle dipendenze** (§3.4), voci di inventario coinvolte. **Non modifica nulla** |
| `step` | Esegue il prossimo tag: merge, rilevatore, build, analisi note, controllo pagine congelate. Si ferma alla prima condizione di stop e ne registra il motivo |
| `status` | Tag completati, tag corrente, condizione che ha fermato il percorso |
| `resume` | Riprende dopo che la fermata è stata risolta |

`plan` resta invocabile **anche a mano**, indipendentemente dal percorso: serve a guardare cosa c'è a monte per decidere *quando* aggiornare, senza alcuna intenzione di farlo subito.

### 6.2.1 Forma di avvio: un comando, due domande

Decisione presa il 2026-09-18 su richiesta del committente: i passi preliminari — fetch, pianificazione, scelta dell'ambito, creazione del branch — **non sono comandi separati da ricordare**, ma vengono eseguiti dalla skill che pone due sole domande.

```
/upstream-upgrade
```

La skill esegue in sequenza:

| | Passo | Se qualcosa non va |
| --- | --- | --- |
| 1 | **Working tree pulito?** | Si ferma ed elenca cosa c'è di non committato |
| 2 | Remote `upstream` e `rerere` presenti? | Propone i comandi mancanti |
| 3 | `git fetch upstream --tags` | — |
| 4 | Invoca `plan` e mostra la tabella | — |
| 5 | Formula una **raccomandazione motivata** su dove fermarsi, applicando le regole di §3.4 (isolare i bump di dipendenza) e §8 (isolare le rotture dichiarate) | — |

Poi pone **due domande**, con la risposta proposta fra parentesi quadre:

> **1.** Fino a quale release vuoi arrivare? *[proposta]*
> **2.** Creo il branch `merge/upstream-<versione>` partendo da `<branch corrente>`. Confermi?

**I due controlli preliminari non sono formalità.** Il primo evita che modifiche non committate finiscano mescolate al lavoro dell'upstream. Il secondo — la dichiarazione esplicita del branch di partenza dentro la domanda, invece di darlo per scontato — è quello che salva davvero: partire per distrazione da `develop` invece che dal branch di lavoro farebbe lavorare il percorso per ore su una base sbagliata, e la domanda mette la partenza davanti agli occhi nel momento in cui è ancora correggibile.

### 6.3 Lo stato vive in `.git/oslms-upstream-walk.json`

Scelta deliberata: git non traccia mai il contenuto della propria directory, quindi lo stato **non finisce in un commit, non crea conflitti e non richiede di modificare `.gitignore`** — che è un file upstream, e aggiungervi una riga sarebbe l'ennesimo innesto da censire.

Contenuto: versione di partenza, versione di arrivo, elenco dei tag completati con il loro commit di merge, tag corrente, condizione di fermata attiva con i suoi dati, percorso del rapporto in corso.

**Conseguenza pratica, che vale più della pulizia architetturale:** il percorso è **interrompibile e riprendibile**. Lo stato sta in un file, non nella memoria di una conversazione. Ci si può fermare a `v2.60.0` e tornare giorni dopo, in una sessione nuova e con un altro modello, lanciare `status` e sapere esattamente dove si era e perché. Su un percorso di otto release con fermate che richiedono giudizio umano, è la differenza fra un lavoro che si chiude e uno che si abbandona a metà.

### 6.4 Il pilota — `.claude/skills/upstream-upgrade/SKILL.md`

Contiene: cosa fare a ciascuna condizione di fermata, come consultare l'inventario per capire cosa protegge una riga in conflitto, come strutturare il rapporto, e le regole inviolabili (§10).

### 6.5 Dipendenze dagli altri sottosistemi

| Dipende da | Obbligatoria | Perché |
| --- | --- | --- |
| **Fase 0** — inventario e rilevatore | Sì | Il rilevatore è il segnale di «personalizzazione persa» a ogni step. Senza inventario l'agente non sa cosa proteggere né perché |
| **Fase 1** — test backend e Vitest | Fortemente consigliata | È ciò che rende affidabile il «procede da solo» di E1: senza test, «il merge è pulito» significa soltanto che git non ha protestato |

---

## 7. Il ciclo di una release

Per ogni tag `T` della sequenza, nell'ordine. Il primo controllo che fallisce ferma il ciclo.

| # | Passo | Se fallisce |
| --- | --- | --- |
| 1 | `git merge <T>` sul branch di lavoro | **Fermata 1** — conflitto git |
| 2 | `python3 scripts/check_customizations.py` | **Fermata 2** — personalizzazione persa (nuovi C1/C2 rispetto allo step precedente) |
| 3 | Build del frontend | **Fermata 3** — build rotta |
| 4 | Analisi note: rotture dichiarate (`!`) fra `T_prec..T` | **Fermata 4** — rottura dichiarata |
| 5 | Analisi note: incrocio `feat` con l'inventario | **Fermata 5** — sostituzione sospetta |
| 6 | Pagine congelate toccate dall'upstream in `T_prec..T` | **Fermata 6** — riconciliazione dovuta |
| 7 | Nessuna fermata: commit del merge, avanza a `T+1` | — |

Il confronto del passo 2 è **differenziale**: conta solo ciò che questa release ha rotto, non ciò che era già rotto prima. Una personalizzazione già persa allo step precedente non deve fermare tutti gli otto passi.

La suite completa di test (E3) non gira ai passi 1-7: gira **quando il percorso si ferma** e **alla fine del percorso**. La build al passo 3 è il compromesso: costa poco e cattura la classe di rotture più grossolana.

---

## 8. Le sei condizioni di fermata

Per ciascuna: come si rileva, cosa fa l'agente, cosa produce.

### Fermata 1 — Conflitto git

**Rilevata da:** exit code di `git merge`.
**L'agente:** per ogni file in conflitto, cerca nell'inventario le voci che lo citano e legge il loro `intent`. Risolve **preservando l'intento**, non la riga: se l'upstream ha riscritto la funzione attorno, la regola va riespressa nel codice nuovo. Se nessuna voce copre quel file, il conflitto è fra codice upstream e codice upstream e si risolve con i criteri normali.
**Produce:** la risoluzione nel working tree e, nel rapporto, una riga per file con la voce di inventario applicata.

### Fermata 2 — Personalizzazione persa

**Rilevata da:** nuovi findings C1 o C2 del rilevatore rispetto allo step precedente.
**L'agente:** legge il diff della release ristretto a quel file, capisce **come** l'ancora è sparita — riscrittura, rinomina, rimozione — e riapplica la regola secondo l'`intent`. Se il file non esiste più (C2), stabilisce dove la regola deve vivere ora.
**Produce:** un commit separato `fix(oslms): restore <inventory-id> after <tag>`.

### Fermata 3 — Build rotta

**Rilevata da:** exit code della build frontend.
**L'agente:** diagnostica. Se la causa è una risoluzione di conflitto precedente, la corregge. Se è un cambiamento upstream che richiede adeguamento (una prop rinominata, un import spostato), adegua il codice nostro.
**Produce:** la correzione e la riga di rapporto.

### Fermata 4 — Rottura dichiarata (`!`)

**Rilevata da:** espressione regolare sui messaggi dei commit fra i due tag, formato Conventional Commits con `!` prima dei due punti.
**L'agente:** per ogni rottura, incrocia l'area toccata con l'inventario e con la mappa delle personalizzazioni, e produce una valutazione d'impatto: cosa cambia a monte, quali voci di inventario insistono su quell'area, cosa si rompe se non si fa nulla.
**Produce:** una sezione del rapporto **e una domanda al committente**. Non procede da solo.

### Fermata 5 — Sostituzione o deprecazione sospetta (E2)

**Rilevata da:** un commit `feat` che tocca file citati dall'inventario, o la cui area coincide con una personalizzazione censita.
**L'agente:** produce l'**analisi comparativa** — cosa fa la novità upstream, cosa fa la personalizzazione esistente, dove si sovrappongono, cosa si perde adottando l'una o l'altra, quanto costa ciascuna strada — e una raccomandazione motivata.
**Produce:** l'analisi e **una domanda al committente**. La scelta fra adottare l'upstream, mantenere la propria versione o tenere entrambe è una decisione di prodotto e non spetta all'agente.

### Fermata 6 — Pagina congelata toccata (E4)

**Rilevata da:** commit della release che modificano uno dei 24 file originali corrispondenti agli override.
**L'agente:** confronto **a tre vie** — versione upstream al momento del congelamento, versione upstream nuova, copia nostra — e propone come portare la modifica upstream dentro la copia senza perdere le personalizzazioni.
**Produce:** la proposta nel rapporto. Vedi §9 per il dato che oggi manca.

---

## 9. Le pagine congelate: il dato che oggi non esiste

Il confronto a tre vie della Fermata 6 richiede di sapere **da quale commit upstream ogni override è stato copiato**. Questo dato oggi **non esiste da nessuna parte**: gli override sono stati creati copiando il file originale in un momento non registrato.

Soluzione proposta, in due tempi:

1. **Da ora in avanti:** l'inventario porta per ogni override un campo `frozen_from` con lo SHA upstream di provenienza, obbligatorio alla creazione di un nuovo override.
2. **Per i 24 esistenti:** ricostruzione approssimata — si prende la data di creazione del file di override dalla storia git e si individua il commit upstream del file originale immediatamente precedente. **È una stima**, e va marcata come tale nell'inventario (`frozen_from_estimated = true`), perché un confronto a tre vie partito da una base sbagliata produce un diff plausibile e scorretto, che è peggio di nessun diff.

In assenza di una base attendibile, la Fermata 6 deve degradare onestamente: segnalare che l'upstream ha toccato l'originale, mostrare il diff upstream **puro** (senza tentare la fusione) e lasciare la riconciliazione al giudizio umano.

---

## 10. Regole inviolabili

Ereditate dal documento collegato e estese a questo percorso.

1. **Non si modifica mai un test per farlo passare.** Davanti a un test rosso: riparare il codice, oppure fermarsi e chiedere. Un test è un output, non un input.
2. **Non si cancella una voce di inventario per far tornare verde il rilevatore.** Se una regola non vale più, si marca `accepted-drift` con data e motivo.
3. **Non si decide una sostituzione al posto del committente** (E2).
4. **Non si procede oltre una fermata non risolta.** Lo stato registra la fermata attiva proprio per rendere impossibile saltarla.
5. **Non si spinge nulla su un remote.** Il percorso produce commit locali su un branch dedicato; pubblicare è una decisione del committente.

---

## 11. Branch, commit e rapporti

**Un solo branch** per l'intero percorso: `merge/upstream-<versione-arrivo>`, con un commit di merge per release in sequenza e, fra l'uno e l'altro, i commit di riparazione prodotti dalle fermate. La storia resta leggibile e consente di tornare indietro a una release specifica senza districare branch intrecciati.

**Un rapporto per release** in `docs/upstream-checks/AAAA-MM-GG-<tag>.md`, con: ampiezza reale della release (dal diff dei commit, non dalle note), fermate incontrate e come sono state risolte, voci di inventario toccate, decisioni chieste al committente con la risposta ricevuta, esito delle verifiche.

**Un rapporto finale** di percorso che aggrega gli otto e dichiara: cosa è stato adottato, cosa è stato rifiutato consapevolmente e perché, quali personalizzazioni sono state riespresse, cosa resta aperto.

---

## 12. Rischi e mitigazioni

| Rischio | Mitigazione |
| --- | --- |
| L'ampiezza viene ricavata dalle note e non dal diff | Vincolo esplicito di §3.2: le note servono solo all'intento. Il motore calcola l'ampiezza da `git log <tag_prec>..<tag>` e ignora le PR non presenti in quel diff |
| `rerere` riapplica una risoluzione sbagliata | Le risoluzioni riapplicate sono comunque soggette al rilevatore e alla build dello step; il rapporto dichiara quali risoluzioni sono state riapplicate automaticamente |
| Il confronto a tre vie parte da una base sbagliata | §9: `frozen_from` obbligatorio per i nuovi, stima marcata per i 24 esistenti, degrado onesto quando la base non è attendibile |
| «Build verde» scambiata per «funziona» | E3: la suite completa gira alle fermate e a fine percorso; la build è solo il filtro grossolano dello step |
| Le rotture più pesanti sono nell'ultima release | `plan` le mostra **prima di partire**: si sa fin dall'inizio che `v2.63.0` contiene tre rotture, due su aree molto personalizzate, e si può decidere di fermare il percorso a `v2.62.1` |
| Il percorso viene abbandonato a metà | Stato persistente in `.git/` (§6.3): riprendibile a distanza di giorni da una sessione nuova |
| Accumulo: otto release oggi, trenta domani | Il percorso è tanto più economico quanto più è frequente. Cadenza consigliata: attraversare le release nuove con regolarità, non a grandi salti |

---

## 13. Cosa resta da decidere

Le sezioni 7-12 sono state scritte ma **non sottoposte all'approvazione sezione per sezione** prevista dalla procedura di progettazione: il committente ha chiesto di produrre direttamente la documentazione. Restano quindi aperti:

1. **La sequenza esatta dei controlli del ciclo (§7)** e in particolare se la build debba stare a ogni step o solo alle fermate.
2. **Il formato del rapporto per release (§11)** e se serva davvero uno per release oltre a quello finale.
3. **La ricostruzione di `frozen_from` per i 24 override (§9)**: se valga la pena della stima approssimata o se convenga registrarlo solo da qui in avanti, accettando che le 24 pagine esistenti restino riconciliabili solo a mano.
4. **La versione di arrivo del primo percorso reale.** Alla luce di §3.4 la raccomandazione è cambiata: non `v2.62.1` ma **`v2.58.1`**, perché è l'ultima release prima del salto `frappe-ui` di `v2.59.0`. La suddivisione proposta è in quattro attività: `v2.58.1` (percorso breve di prova), `v2.59.0` (il salto frappe-ui, attività dedicata), `v2.60.0`→`v2.62.1` (percorso guidato), `v2.63.0` (le tre rotture).

**Punti chiusi dopo la stesura iniziale:**

- ~~Se il prerequisito di §6.1 vada eseguito subito~~ → **eseguito dal committente il 2026-09-18**: remote `upstream` configurato, `rerere.enabled=true`, `fetch` completato (94 riferimenti, 95 tag). I dati di §3.4 derivano da lì.
- ~~La sequenza esatta dei passi preliminari~~ → **chiusa**: collassano tutti nella skill (§6.2.1), che pone due domande.

---

## 14. Riferimenti

**Documenti:**
- [`../../Procedura-Aggiornamento-Upstream.md`](../../Procedura-Aggiornamento-Upstream.md) — **la guida operativa per chi esegue l'aggiornamento**: cosa lanciare, cosa fa l'agente, cosa tocca a te e le tre attività che si chiamano tutte "testare"
- [`2026-09-18-upstream-regression-harness-design.md`](2026-09-18-upstream-regression-harness-design.md) — inventario, rilevatore, suite di test; prerequisito di questo sistema
- [`../plans/2026-09-18-upstream-regression-harness-fase-0.md`](../plans/2026-09-18-upstream-regression-harness-fase-0.md) — piano della Fase 0
- `docs/OS_LMS_OVERRIDES.md` — mappa di cosa `os_lms` fa a `lms`

**Memorie di progetto rilevanti:**
- `upstream-merge-maintenance-strategy` — i tre livelli, e `rerere` come lever mai attivato
- `upstream-merge-v2-58-0-2026-07` — pattern di risoluzione dell'ultimo merge reale
- `frappeui-1-0-beta-merge-2026-06`, `frappeui-v1-v2-branch-split`, `frappeui-caret-pin-drift` — precedenti di merge upstream con le loro trappole
- `courseform-sectioned-custom-grafts` — innesti da riapplicare a ogni merge
- `dataimport-uploadstep-fork`, `combobox-override-event-api` — override congelati che richiedono ri-confronto a ogni bump di frappe-ui
- `lesson-editorjs-custom-tags-server-strip` — l'area colpita dalla rottura `fix(lesson)!` di `v2.63.0`

**Stato del repository al 2026-09-18:** nessun remote `upstream`; `develop` fermo al 2026-03-19; ultimo merge upstream `v2.58.0` del 2026-07-02 su `merge/upstream-v2.58.0`; `rerere` non configurato; 24 override in `frontend/src/overrides/`; 49 marcatori `OSLMS-CUSTOM` su 12 file sorgente.

---

## 15. Versione 1 da costruire — decisa il 2026-09-23

> **Questa sezione è il mandato di costruzione.** Una sessione che deve realizzare `/upstream-upgrade` parte da qui; il resto del documento spiega il perché delle scelte. Dove questa sezione e le precedenti divergono, vale questa.

### 15.1 Cosa vuole il committente

Lanciare **un solo comando**, `/upstream-upgrade`, che:

1. mostra le release upstream disponibili;
2. gli fa scegliere fino a quale arrivare;
3. crea un branch dedicato, partendo da `feature/oslms` oppure chiedendogli da quale branch partire;
4. esegue tutte le operazioni necessarie per avere l'aggiornamento **senza conflitti irrisolti e senza perdere nessuna personalizzazione**;
5. **in caso di dubbio o perplessità, è incentivato a chiedere**, spiegare la situazione e decidere insieme a lui. Non deve mai indovinare.

### 15.2 Stato di partenza (verificato il 2026-09-23)

- Prerequisito git: remote `upstream` = `frappe/lms` configurato, `rerere.enabled=true`.
- Fase 0 completa: inventario `docs/customizations/spa-grafts.toml` (33 voci, 0 a bassa confidenza), rilevatore `scripts/check_customizations.py`, guardia hook `Stop` `scripts/inventory_guard.py`, workflow CI, skill `/upstream-check` (rapporto post-merge, non fa il merge).
- Tutti i file toccati da `v2.58.1` che contengono modifiche nostre sono censiti.
- **Limite noto:** circa 78 file upstream contengono modifiche nostre **senza marcatore** e non sono censiti; molti sono toccati dalle release da `v2.59.0` in poi. Vedi §15.4, fermata F7.

### 15.3 Scope della versione 1

| Da costruire | Contenuto |
| --- | --- |
| `.claude/skills/upstream-upgrade/SKILL.md` | L'intero flusso di §15.4, con le regole di §15.5 |
| `scripts/upstream_plan.py` + `scripts/tests/test_upstream_plan.py` | Il comando `plan` di §6.2: la tabella delle release. Sola libreria standard, stesso stile del rilevatore (ruff, tab, bootstrap del `sys.path`) |
| `docs/Procedura-Aggiornamento-Upstream.md` | Aggiornata: rimuovere i ⚙️ dei passi ora reali |

**Fuori scope nella v1:** i comandi `step`/`status`/`resume` del motore (§6.2) restano **dentro la skill**; lo stato del percorso lo scrive l'agente (§15.4, passo 7). Si potranno spostare in codice in una versione successiva.

`upstream_plan.py` deve produrre, per ogni release successiva all'ultima già fusa nel branch di partenza (ultimo tag upstream antenato di `HEAD`, ordinamento per versione con `sort -V` o equivalente):

- commit e file **reali** (`git log`/`git diff` fra tag consecutivi — **mai** dalle note di release, §3.2 e §3.4);
- rotture dichiarate (`!` nei soggetti dei commit, formato Conventional Commits);
- versione di `frappe-ui` in `frontend/package.json` a quel tag, segnalando il cambio rispetto alla release precedente;
- voci di inventario i cui file sono toccati dalla release;
- **file con modifiche nostre non censiti** toccati dalla release: file upstream (presenti al tag base) modificati da commit nostri, cioè `git log --no-merges <base>..HEAD --not --remotes=upstream --tags`, privi di marcatore `OSLMS-CUSTOM`, esclusi traduzioni e test;
- una raccomandazione su dove fermarsi: prima del primo bump di dipendenza importante o della prima rottura dichiarata.

Uscita a tabella e `--json`. Attenzione ai tranelli già incontrati: in zsh `$t:path` è un modificatore (usare `subprocess` con liste di argomenti, non stringhe di shell); senza `--not --remotes=upstream --tags` il conteggio dei file nostri si gonfia per un vecchio merge di `upstream/develop`.

### 15.4 Il flusso della skill

| # | Passo | Dettaglio |
| --- | --- | --- |
| 0 | Controlli | Branch corrente; modifiche in sospeso (sono **tollerati** `docs/WORKLOG.md` modificato e i file non tracciati: non bloccano il merge); remote `upstream`; `rerere`. Se manca qualcosa, propone il comando e chiede |
| 1 | Fetch | `git fetch upstream --tags` |
| 2 | Piano | `python3 scripts/upstream_plan.py` e presentazione della tabella con la raccomandazione |
| 3 | Domanda 1 | **Fino a quale release?** Opzioni = le release, la raccomandata per prima |
| 4 | Domanda 2 | **Da quale branch partire e con quale nome?** Proposta: partenza `feature/oslms` (o il branch corrente, dichiarato esplicitamente), nome `merge/upstream-<tag>` |
| 5 | Branch | Creazione del branch |
| 6 | Ciclo | Per ogni release, dalla più vecchia: merge → fermate F1-F7 → rilevatore → build frontend → commit del merge |
| 7 | Stato | Dopo ogni release scrive `.git/oslms-upstream-walk.json` (partenza, arrivo, release completate con commit, fermata attiva). All'avvio, se il file esiste, propone di riprendere |
| 8 | Chiusura | Suite completa (rilevatore, Vitest, test backend `os_lms` con Docker: se non è attivo lo chiede), skill `/upstream-check`, rapporto in `docs/upstream-checks/`, **lista puntuale di cosa provare nell'app** ricavata dalle voci toccate, con il ruolo con cui provarle |

**Fermate.** Le prime sei sono quelle di §8; F7 è nuova.

| | Condizione | Chi decide |
| --- | --- | --- |
| F1 | Conflitto git in un file censito | Agente, usando l'`intent` della voce; **se l'intent non basta a decidere, chiede** |
| F2 | Il rilevatore segnala una personalizzazione persa | Agente, riapplica secondo l'`intent` |
| F3 | Build rotta | Agente |
| F4 | Rottura dichiarata dall'upstream | **Committente**, con valutazione d'impatto |
| F5 | Novità upstream che sostituisce o rende obsoleta una funzione nostra (incluse le sovrapposizioni già annotate negli intent) | **Committente**, con analisi comparativa e raccomandazione |
| F6 | Pagina congelata in `overrides/` con originale toccato, o bump di `frappe-ui` | **Committente** |
| F7 | La release tocca file con **modifiche nostre non censite** | **Committente**: la skill propone di censirle **prima** del merge (marcatore + voce di inventario, come fatto il 2026-09-23 per i file di `v2.58.1`) e procede solo dopo |

### 15.5 Regole della skill

1. **Nel dubbio, chiedi.** Se non è chiaro cosa protegge una riga, se due versioni sono entrambe plausibili, se una modifica upstream potrebbe essere voluta: fermati, spiega la situazione in linguaggio semplice, presenta le opzioni con una raccomandazione motivata, e decidi con il committente. Indovinare è l'errore più costoso di questo processo.
2. Non modificare mai un test per farlo passare (§10).
3. Non cancellare voci di inventario; se una regola non vale più, `status = "accepted-drift"` con data e motivo, **dopo** l'ok del committente.
4. Non proseguire oltre una fermata non risolta.
5. Non pubblicare nulla e non unire nel branch di partenza senza l'ok esplicito del committente.
6. Registrare l'attività nel worklog secondo le convenzioni del progetto.

### 15.6 Criteri di completamento della v1

1. `python3 -m unittest discover -s scripts/tests -t .` verde, compresi i test di `upstream_plan.py`.
2. `python3 scripts/upstream_plan.py` sul repository reale mostra `v2.58.1` → `v2.63.0` con: il bump di `frappe-ui` in `v2.59.0` (beta.7 → beta.24) e in `v2.62.0` (→ beta.29), le 3 rotture di `v2.63.0`, **0 file non censiti** per `v2.58.1`, e la raccomandazione di fermarsi a `v2.58.1`.
3. La skill è elencata fra quelle disponibili ed esegue i passi 0-4 fino alla creazione del branch. **Il merge vero non fa parte della costruzione**: lo lancia il committente quando vuole.
