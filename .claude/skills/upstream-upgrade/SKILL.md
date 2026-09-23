---
name: upstream-upgrade
description: Usare per aggiornare il fork a una release più recente di frappe/lms. Mostra le release upstream disponibili, fa scegliere fin dove arrivare e da quale branch partire, crea il branch dedicato e attraversa le release una alla volta senza perdere personalizzazioni, fermandosi a chiedere a ogni dubbio. Riprende un percorso interrotto.
---

# upstream-upgrade — aggiornamento upstream guidato, release per release

Porta il branch di lavoro da una release di `frappe/lms` a una più recente, **una release alla volta**, dalla più vecchia in avanti, senza conflitti irrisolti e senza perdere personalizzazioni.

- Progetto e motivazioni: `docs/superpowers/specs/2026-09-18-upstream-release-walk-design.md` (§15 è il mandato di questa versione).
- Fonte di verità delle personalizzazioni: `docs/customizations/*.toml` (schema in `docs/customizations/README.md`).
- Guida per il committente: `docs/Procedura-Aggiornamento-Upstream.md`.

## Regole

1. **Nel dubbio, chiedi.** Se non è chiaro cosa protegge una riga, se due versioni sono entrambe plausibili, se una modifica upstream potrebbe essere voluta: fermati, spiega la situazione in linguaggio semplice, presenta le opzioni con una raccomandazione motivata e decidi con il committente (`AskUserQuestion`). **Indovinare è l'errore più costoso di questo processo**: un conflitto risolto male viene registrato da `rerere` e riapplicato alle release successive.
2. **Non modificare mai un test per farlo passare.** Davanti a un test rosso: ripara il codice, oppure fermati e chiedi. Un test è un output, non un input.
3. **Non cancellare voci di inventario.** Se una regola non vale più, `status = "accepted-drift"` con data e motivo nell'`intent`, **dopo** l'ok del committente.
4. **Non proseguire oltre una fermata non risolta.** Lo stato registra la fermata attiva proprio per renderla impossibile da saltare.
5. **Non pubblicare nulla** (`git push`, PR) e **non unire nel branch di partenza** senza l'ok esplicito del committente. Si lavora solo con commit locali sul branch dedicato.
6. **Le note di release non misurano niente.** L'ampiezza viene solo dal diff fra tag (`scripts/upstream_plan.py`); le note, e i messaggi dei commit, servono solo a capire l'intento.
7. **Niente stringhe di shell costruite attorno ai tag.** In zsh `$t:path` è un modificatore e le variabili non si spezzano in parole: passa i tag letterali, uno per argomento, o usa Python con `subprocess`.
8. Registra l'attività in `docs/WORKLOG.md` secondo le convenzioni del file (il worklog non si committa).

## Stato del percorso

Vive in `$(git rev-parse --git-dir)/oslms-upstream-walk.json`: fuori dall'albero, mai committato, sopravvive alla conversazione. Scrivilo **dopo ogni evento** (branch creato, fermata aperta o chiusa, decisione presa, release completata), non solo a fine release.

```json
{
  "version": 1,
  "start_branch": "feature/oslms",
  "start_commit": "<sha del branch di partenza alla creazione>",
  "branch": "merge/upstream-v2.58.1",
  "base": "v2.58.0",
  "target": "v2.58.1",
  "started_at": "2026-09-23T10:00:00",
  "report": "docs/upstream-checks/2026-09-23-percorso-v2.58.0-v2.58.1.md",
  "detector_baseline": [{"id": "…", "check": "C1", "file": "…"}],
  "completed": [
    {"tag": "v2.58.1", "merge_commit": "<sha>", "fix_commits": ["<sha>"], "completed_at": "…"}
  ],
  "current": "v2.59.0",
  "stop": {"code": "F4", "tag": "v2.59.0", "summary": "…", "opened_at": "…"},
  "decisions": [
    {"tag": "v2.59.0", "stop": "F6", "question": "…", "answer": "…", "date": "…"}
  ]
}
```

`stop` è `null` quando nessuna fermata è aperta; `current` è `null` fra una release e l'altra.

---

## Passo 0 — Controlli

Esegui ed esamina:

```bash
git branch --show-current
git status --porcelain
git remote get-url upstream
git config rerere.enabled
test -f "$(git rev-parse --git-dir)/oslms-upstream-walk.json" && cat "$(git rev-parse --git-dir)/oslms-upstream-walk.json"
```

- **File di stato presente** → vai a «Ripresa di un percorso» in fondo, prima di tutto il resto.
- **Modifiche in sospeso:** sono tollerati `docs/WORKLOG.md` modificato e i file non tracciati (`??`). Qualunque altra riga blocca: elencala e chiedi al committente se committarla o metterla da parte. Non fare `stash` di tua iniziativa.
- **Merge o rebase in corso** (`git status` lo dice) → fermati e chiedi.
- **Remote `upstream` assente** → proponi `git remote add upstream https://github.com/frappe/lms.git` e chiedi.
- **`rerere` non attivo** → proponi `git config rerere.enabled true` e chiedi. Mai `rerere.autoUpdate`.

## Passo 1 — Fetch

```bash
git fetch upstream --tags
```

## Passo 2 — Piano

```bash
python3 scripts/upstream_plan.py
python3 scripts/upstream_plan.py --json   # per leggere i dati
```

Il piano parte dall'ultima release upstream già fusa in `HEAD` e, per ogni release successiva, riporta: commit e file **reali**, versione di `frappe-ui` (con il salto rispetto alla precedente), rotture dichiarate, voci di inventario toccate, pagine congelate il cui originale è toccato, **file con modifiche nostre non censite** toccati. Chiude con una raccomandazione su dove fermarsi.

Presentalo al committente come tabella compatta (release, data, commit, file, frappe-ui, rotture, voci, non censiti, congelate) e aggiungi sotto, in prosa breve: cosa rende rischiose le release segnalate, quanti file non censiti ci sono in totale, e la raccomandazione con il suo motivo. Non incollare le liste lunghe: offri di mostrarle.

## Passo 3 — Domanda 1: fino a quale release?

`AskUserQuestion`, al massimo 4 opzioni: **la raccomandata per prima** con «(Consigliata)», poi i confini di rischio successivi (l'ultima release prima di ogni bump o rottura), poi la più recente. Nella descrizione di ogni opzione scrivi cosa comporta arrivarci (bump, rotture, file da censire). Il committente può indicare qualsiasi altra release con «Other».

## Passo 4 — Domanda 2: da dove partire e con quale nome?

`AskUserQuestion`. Proposta: partenza `feature/oslms`, nome `merge/upstream-<tag scelto>`. **Dichiara sempre il branch di partenza nel testo della domanda**: è il momento in cui ci si accorge di essere sul branch sbagliato. Se il branch corrente non è `feature/oslms`, offri entrambi e dillo esplicitamente.

- Se la partenza scelta non è il branch corrente, rilancia `python3 scripts/upstream_plan.py --head <partenza>`: la base potrebbe essere diversa. Se lo è, mostralo e riconferma la Domanda 1.
- Se il branch di destinazione esiste già (`git rev-parse --verify --quiet <nome>`), fermati e chiedi: riprenderlo, sceglierne un altro nome, o altro. Non cancellarlo mai.

## Passo 5 — Branch

```bash
git switch -c <nome> <partenza>
```

Poi:

1. `python3 scripts/check_customizations.py --json` → registra gli errori (`C1`, `C2`, `C3`) come `detector_baseline`. Se ce ne sono, **dillo**: sono scostamenti preesistenti, non causati dal percorso, e non fermeranno il ciclo; se ci sono `C3`, proponi di censirli prima di partire.
2. Crea `docs/upstream-checks/` se manca e il rapporto di percorso `AAAA-MM-GG-percorso-<base>-<target>.md` con intestazione (data, partenza e suo SHA, branch, base, arrivo, tabella del piano).
3. Scrivi il file di stato.

## Passo 6 — Il ciclo, per ogni release `T` (precedente `P`), dalla più vecchia

Imposta `current = T` nello stato. Poi:

### 6.1 Analisi prima del merge

```bash
python3 scripts/upstream_plan.py --to T --json
```

Su questo branch la base è `P`, quindi il JSON contiene solo `T`. Da qui e dai commit `P..T` si ricavano **prima di fondere** le fermate di giudizio, nell'ordine sotto. Raccogli le domande di una stessa release e ponile insieme quando sono indipendenti; registra ogni risposta in `decisions`.

**F7 — file con modifiche nostre non censite** (`uncatalogued` non vuoto). **Decide il committente.** Il merge potrebbe ripulirle senza che il rilevatore se ne accorga, perché non le conosce.
- Per ogni file mostra cosa abbiamo cambiato: i nostri commit con `git log --no-merges --format='%h %an %cs %s' P..HEAD --not --remotes=upstream <tag di release> -- <file>` (i tag di release, letterali, sono quelli elencati da `git tag -l 'v*'` che hanno forma `vX.Y.Z`; **non** usare `--tags`: esclude anche i nostri tag `ve…`/`vi…` e fa sparire i nostri commit) e il diff `git diff P HEAD -- <file>`.
- Proponi di censirli **prima** del merge, come fatto il 2026-09-23 per `v2.58.1` (commit `0c4edec85`): commento marcatore `OSLMS-CUSTOM` sulla riga che porta la regola, voce in `docs/customizations/spa-grafts.toml` con `file`, `anchor` unica (`grep -cF` = 1), `intent` che dice **perché**. Per i file senza commenti (JSON) la voce basta, senza marcatore.
- Con molti file (decine), proponi di raggrupparli per funzionalità e procedi a gruppi, un commit per gruppo: `docs(customizations): catalogue unmarked grafts touched by <T>`.
- Se l'`intent` di una modifica non è ricostruibile dal codice e dai commit, **chiedi**; se lo deduci, `confidence = "low"`.
- Chiusura: rilancia il piano (`uncatalogued` di `T` = 0) e il rilevatore (nessun `C3`).

**F6 — bump di `frappe-ui` o pagina congelata toccata.** **Decide il committente.**
- *Bump:* il salto viene fuso pulito e si rompe a runtime nei 23 componenti frappe-ui copiati in `frontend/src/overrides/frappe-ui/`. Spiegalo e ricorda i precedenti: beta.24 ha già causato in produzione l'errore 417 su `boot_config`; l'override `Combobox` perde `modelValue` ai bump (campi Link vuoti che però salvano); il fork `DataImport` va riconfrontato file per file. Opzioni: fermare il percorso a `P`; procedere e riconciliare ora gli override; procedere registrando la riconciliazione come attività aperta.
- *Pagina congelata* (`frozen` non vuoto): il file originale è stato modificato a monte, ma noi serviamo la copia in `overrides/`, quindi la modifica non arriva. La base del congelamento non è registrata da nessuna parte (§9 del progetto): **non tentare un confronto a tre vie**. Mostra il diff upstream puro `git diff P T -- <originale>`, spiega cosa porta, confrontalo a occhio con la copia e proponi cosa portare nella copia. Il committente decide.

**F4 — rotture dichiarate** (`breaking` non vuoto). **Decide il committente.** Per ogni rottura:
- trova il commit che la dichiara: `git log --format='%H %s' --grep='<testo della riga>' --fixed-strings P..T`; se è un merge di PR, i commit della PR sono `<merge>^1..<merge>^2`;
- file toccati dalla PR, incrociati con l'inventario (`grep -n '<file>' docs/customizations/*.toml`) e con i nostri file modificati;
- valutazione d'impatto: cosa cambia a monte, quali voci insistono su quell'area, cosa si rompe se non si fa nulla, costo stimato dell'adeguamento.
Scrivila nel rapporto e chiedi. Non proseguire da solo.

**F5 — novità upstream che sostituiscono o rendono obsoleta una funzione nostra.** **Decide il committente.** Candidati:
- commit `feat` (nei soggetti **e nei corpi**: frappe/lms mette il titolo della PR nel corpo del merge) i cui file toccano l'inventario o i nostri file modificati: `git log --format='%H%n%B%x00' P..T`, poi `git show --name-only <sha>`;
- voci di inventario il cui `intent` annuncia già una sovrapposizione con questa release (cerca `T` e «ATTENZIONE» negli intent delle voci toccate).
Per ciascuno: analisi comparativa — cosa fa la novità, cosa fa la nostra personalizzazione, dove si sovrappongono, cosa si perde adottando l'una o l'altra, quanto costa ciascuna strada — e una raccomandazione motivata. Opzioni tipiche: adottare l'upstream (la voce diventa `accepted-drift`, dopo l'ok), mantenere la nostra, tenerle entrambe. Se nulla si sovrappone davvero, dillo in una riga e prosegui.

Quando una fermata è aperta, scrivila in `stop` **prima** di porre la domanda, e azzerala solo quando la risposta è stata applicata.

### 6.2 Merge

```bash
git merge --no-ff --no-commit T
```

- **Conflitti** → **F1**, sotto.
- Git rifiuta il merge perché un file non tracciato verrebbe sovrascritto → fermati e chiedi cosa fare di quel file.
- `git rerere status` e `git rerere diff`: se `rerere` ha riapplicato risoluzioni registrate, **elencale nel rapporto** e verificane il contenuto. Ripetono fedelmente anche gli errori.

**F1 — conflitto git.** Decide l'agente, ma **se l'intent non basta a decidere, chiedi**.
Per ogni file in `git diff --name-only --diff-filter=U`:
1. cerca le voci che lo citano: `grep -n '<file>' docs/customizations/*.toml`, e leggine l'`intent` per intero;
2. guarda i due lati: `git diff P T -- <file>` (cosa ha fatto l'upstream) e `git log --no-merges P..HEAD -- <file>` (cosa abbiamo fatto noi);
3. risolvi **preservando l'intento, non la riga**: se l'upstream ha riscritto il codice attorno, riesprimi la regola nel codice nuovo e aggiorna l'`anchor` della voce se cambia; se l'upstream ora fa da sé ciò che faceva la nostra modifica, **non** scartarla da solo: è un caso F5, chiedi;
4. se nessuna voce copre il file, il conflitto è fra codice upstream e codice upstream (tipicamente residuo del vecchio merge di `upstream/develop`): di norma vince `T`, ma controlla che non sia una nostra modifica non censita — in quel caso chiedi;
5. **traduzioni** (`lms/locale/*.po`): prendi la versione upstream e riapplica le nostre voci; il `it.po` upstream ha stringhe rotte note (memoria `it-translations-workflow`);
6. `yarn.lock`: non risolverlo a mano; risolvi `package.json` e rigenera il lock con `yarn install --ignore-engines` dentro `frontend/`.

Nel rapporto: una riga per file, con la voce di inventario applicata e come.

### 6.3 Rilevatore sulla risoluzione

```bash
python3 scripts/check_customizations.py --json
```

Confronta con `detector_baseline`: contano **solo gli errori nuovi**. Un `C1`/`C2` nuovo su un file che hai risolto tu in F1 è un errore della tua risoluzione: correggilo adesso, dentro il merge.

### 6.4 Commit del merge

```bash
git commit --no-edit
```

Il messaggio predefinito (`Merge tag 'T' into <branch>`) è quello giusto: commitlint ignora i messaggi di merge. Aggiungi le righe di attribuzione previste dalle convenzioni della sessione.

### 6.5 F2 — personalizzazione persa in silenzio

Rilancia il rilevatore. Un `C1`/`C2` nuovo rispetto alla baseline su un file che git ha fuso **senza conflitto** è una perdita silenziosa. Decide l'agente:
- leggi `git diff P T -- <file>` e capisci **come** l'ancora è sparita (riscrittura, rinomina, rimozione);
- riapplica la regola secondo l'`intent`; se il file non esiste più (`C2`), stabilisci dove la regola deve vivere ora e aggiorna `file` e `anchor` della voce — **se non è evidente, chiedi**;
- un commit per voce: `fix(oslms): restore <inventory-id> after <T>`.

### 6.6 F3 — build

Se `frontend/package.json` o `frontend/yarn.lock` sono cambiati in `P..T`, prima installa: `cd frontend && yarn install --ignore-engines` (con `node_modules` stantii la build fallisce con «class does not exist»: memoria `frappeui-v1-v2-branch-split`).

```bash
cd frontend && yarn build
```

- La build rigenera `frontend/src/utils/frappe-ui-colors.json`, che è tracciato. Se risulta modificato e in `P..T` non c'è bump di `frappe-ui`, ripristinalo con `git checkout -- frontend/src/utils/frappe-ui-colors.json`. Se il bump c'è, è parte dell'adeguamento deciso in F6.
- **Build rotta** → decide l'agente: se la causa è una tua risoluzione, correggila; se è un cambiamento upstream che richiede adeguamento (prop rinominata, import spostato), adegua il nostro codice. Commit `fix(oslms): adapt <area> to <T>`. Se la correzione richiede una scelta di prodotto, chiedi.

### 6.7 Chiusura della release

1. Rilevatore: nessun errore nuovo rispetto alla baseline. La nuova baseline è l'esito attuale.
2. Aggiorna lo stato: `completed` += `{tag, merge_commit, fix_commits, completed_at}`, `current = null`, `stop = null`.
3. Aggiungi al rapporto di percorso la sezione di `T`: ampiezza reale (dal piano), fermate incontrate e come sono state risolte, risoluzioni `rerere` riapplicate, voci di inventario toccate, decisioni chieste con la risposta, esito di rilevatore e build.
4. Una riga al committente («`T` fusa: N conflitti risolti, M ripristini, build verde») e passa alla release successiva **senza chiedere**, a meno che non ci sia una fermata.

## Passo 7 — Chiusura del percorso

Dopo l'ultima release:

1. **Suite completa**, riportando l'esito reale di ciascun comando:
   - `python3 scripts/check_customizations.py`
   - `python3 -m unittest discover -s scripts/tests -t .`
   - `cd frontend && yarn test` (Vitest)
   - **test backend `os_lms`** nel container Docker. Controlla con `docker compose -f docker/docker-compose.yml ps`; se il container `frappe` non è attivo, **chiedi** se avviarlo. Il container monta il repository, quindi vede il branch di merge, ma il suo DB ha lo schema vecchio: serve un `migrate`. **Chiedi prima di lanciarlo**: aggiorna il DB di sviluppo alla nuova release e non torna indietro cambiando branch. Se il CLI `bench` è rotto nel container, usa il Python dell'ambiente (memoria `stale-doctype-meta-in-running-container`: `SiteMigration().run("lms.localhost")` e `unittest` con `frappe.init`/`frappe.connect`; bench in `/home/frappe/bench-data/frappe-bench`, sito `lms.localhost`).
   - Un test rosso: regola 2. Ripara il codice o chiedi.
2. Esegui la skill **`/upstream-check`** passando come riferimento di partenza `start_commit` (non `HEAD^1`: il percorso ha più merge).
3. Completa il rapporto di percorso: cosa è stato adottato, cosa è stato rifiutato consapevolmente e perché, quali personalizzazioni sono state riespresse, cosa resta aperto (riconciliazioni rimandate, voci `confidence = "low"` nuove).
4. **Lista puntuale di cosa provare nell'app** (`http://lms.localhost:8000/lms`), ricavata dalle voci toccate da conflitti, ripristini e adeguamenti. Per ciascuna: cosa fare, cosa deve succedere, **con quale ruolo** (da `visibility.allow`/`deny` della voce, altrimenti dall'`intent`; se il ruolo non è ricavabile dillo), e perché è in lista. Esempio:
   > Apri un quiz come **Studente**, lascia una domanda senza risposta e consegna: la consegna deve riuscire e la domanda saltata vale 0. *(Conflitto risolto su `lms/lms/doctype/lms_quiz/lms_quiz.py`, voce `quiz-submit-unanswered`.)*
5. Committa i rapporti sul branch del percorso: `docs(upstream): report the walk to <target>`.
6. Chiedi al committente cosa fare del branch: unirlo nel branch di partenza, lasciarlo per revisione, pubblicarlo. **Nulla di questo senza il suo ok esplicito.**
7. Archivia lo stato: rinomina il file in `oslms-upstream-walk.<target>.done.json` (stessa cartella), così un avvio futuro non propone di riprenderlo.
8. Worklog.

## Ripresa di un percorso

Se all'avvio esiste il file di stato:

1. Mostra lo stato in chiaro: partenza, branch, arrivo, release completate con i loro commit, release corrente, fermata attiva con il suo riassunto, decisioni già prese.
2. Verifica la coerenza: il branch esiste; i `merge_commit` completati sono antenati del suo `HEAD`; se c'è un merge in corso (`git status`), è quello di `current`.
3. Chiedi: **riprendere** (default), oppure **abbandonare il percorso** (lo stato si archivia come `oslms-upstream-walk.<target>.abandoned.json`; il branch resta dov'è, non si cancella niente).
4. Riprendendo: `git switch <branch>` (se ci sono modifiche in sospeso, Passo 0), poi riparti **dalla fermata attiva**. Se era una domanda al committente, riponila con il contesto; se era un lavoro dell'agente (F1, F2, F3), riverificane lo stato reale prima di continuare, senza fidarti del riassunto.
