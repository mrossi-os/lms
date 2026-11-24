---
name: upstream-upgrade
description: Usare per aggiornare il fork a una release più recente di frappe/lms. Mostra le release upstream disponibili, fa scegliere fin dove arrivare e da quale branch partire, crea il branch dedicato e attraversa le release una alla volta senza perdere personalizzazioni, fermandosi a chiedere a ogni dubbio. Riprende un percorso interrotto.
---

# upstream-upgrade — aggiornamento upstream guidato, release per release

Porta il branch di lavoro da una release di `frappe/lms` a una più recente, **una release alla volta**, dalla più vecchia in avanti, senza conflitti irrisolti e senza perdere personalizzazioni.

- Progetto e motivazioni: `docs/superpowers/specs/2026-09-18-upstream-release-walk-design.md` (§15 è il mandato di questa versione).
- Fonte di verità delle personalizzazioni: `docs/customizations/*.toml` (schema in `docs/customizations/README.md`).
- Catalogo delle funzionalità: una scheda per funzionalità in `docs/customizations/features/<id>.toml` (schema in `docs/customizations/features/README.md`). Le voci di inventario puntano alla scheda con `feature = "<id>"`; la scheda dice cosa fa la funzionalità (`behaviour`), dove vive (`areas`) e cosa cercare nelle release (`upstream_watch`). Progetto: `docs/superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md`.
- Guida per il committente: `docs/Procedura-Aggiornamento-Upstream.md`.

## Regole

1. **Nel dubbio, chiedi.** Se non è chiaro cosa protegge una riga, se due versioni sono entrambe plausibili, se una modifica upstream potrebbe essere voluta: fermati, spiega la situazione in linguaggio semplice, presenta le opzioni con una raccomandazione motivata e decidi con il committente (`AskUserQuestion`). **Indovinare è l'errore più costoso di questo processo**: un conflitto risolto male viene registrato da `rerere` e riapplicato alle release successive.
2. **Non modificare mai un test per farlo passare.** Davanti a un test rosso: ripara il codice, oppure fermati e chiedi. Un test è un output, non un input.
3. **Non cancellare voci di inventario né schede del catalogo.** Se una regola non vale più, `status = "accepted-drift"` con data e motivo nell'`intent`, **dopo** l'ok del committente. Una scheda che non vale più non si cancella: passa a `status = "retired"` (rimossa da noi) o `status = "replaced-by-upstream"` (sostituita da una release upstream), con una riga in `history` che dice data, release e decisione, sempre **dopo** l'ok del committente.
4. **Non proseguire oltre una fermata non risolta.** Lo stato registra la fermata attiva proprio per renderla impossibile da saltare.
5. **Non pubblicare nulla** (`git push`, PR) e **non unire nel branch di partenza** senza l'ok esplicito del committente. Si lavora solo con commit locali sul branch dedicato; fanno eccezione le correzioni che chiudono F9 e F0, che si committano sul branch di partenza prima di creare il branch dedicato, ciascuna dopo l'ok del committente.
6. **Le note di release non misurano niente.** L'ampiezza viene solo dal diff fra tag (`scripts/upstream_plan.py`); le note, e i messaggi dei commit, servono solo a capire l'intento.
7. **Niente stringhe di shell costruite attorno ai tag.** In zsh `$t:path` è un modificatore e le variabili non si spezzano in parole: passa i tag letterali, uno per argomento, o usa Python con `subprocess`.
8. Registra l'attività in `docs/WORKLOG.md` secondo le convenzioni del file (il worklog non si committa).
9. **Le correzioni di conformità non si perdono e non si indeboliscono.** Vale per le correzioni di sicurezza OWASP e per i requisiti ESG (sezione sotto). Nel dubbio fra la versione upstream e la nostra, tieni la nostra e chiedi.
10. **La skill raccomanda, il committente decide.** Non adotta mai una novità upstream al posto di una nostra funzionalità, e non scarta mai una nostra funzionalità, di sua iniziativa: lo fa solo dopo la risposta del committente a F5.
11. **Ogni commit passa il controllo al commit.** I commit che toccano file upstream o codice nostro portano la riga `Oslms-Feature: <id>` nell'ultimo paragrafo, sopra `Co-Authored-By:` (regole in `CLAUDE.md`, sezione «Customization tracking»). Mai `--no-verify`: se il controllo rifiuta, correggi messaggio o scheda come dice.

## Conformità (OWASP ed ESG)

Le correzioni del piano di sicurezza (`docs/security/owasp-piano-residuo-2026-10-26.md`) e i requisiti ESG stanno in tre posti, ciascuno con la sua rete. I requisiti ESG sono:
- tema chiaro e scuro;
- alto contrasto;
- cancellazione del proprio account;
- punto 5, equità e supervisione umana del Coach AI (piano `docs/ai-simulator/PIANO-esito-e-punteggio-coach.md`, governance in `docs/ai-governance/`): nome dello studente nascosto al Coach, punteggio indicativo calcolato dai criteri, esito deciso da una persona, versione del docente, permessi per Gestore, Docente e Valutatore, avvisi, prompt aggiornati al migrate.

I posti e le loro reti:

| Dove | Cosa le protegge |
| --- | --- |
| `apps/os_lms/`, cioè la maggior parte: override delle API upstream, hook `has_permission` e `permission_query_conditions`, `doc_events` | Il merge non tocca os_lms. `test_override_signatures` segnala un'API upstream rinominata o con parametri nuovi; le suite qui sotto al Passo 7; **F8** per le API nuove che potrebbero aggirarle |
| File upstream (`lms/`, `frontend/`) | Voci di inventario con ancora: rilevatore C1/C2 |
| Dipendenze del frontend | `scripts/tests/test_dependency_floors.py`: versioni minime risolte in `frontend/yarn.lock` (voce `security-dependency-floors`) |

Suite di conformità:
- **backend** (in `apps/os_lms/os_lms/os_lms/tests/`): `test_owasp_2026_10`, `test_owasp_package_d`, `test_owasp_package_e`, `test_csp_report`, `test_security_alerts`, `test_account_deletion`, `test_discussion_reply_count`, `test_valutatore_assignment_submission_scope`, `test_role_gates_v2_64`, `test_role_gates_v2_65`, `test_owasp_discussion_submit`, `test_owasp_graded_submission`, `test_owasp_simulation_limits`, `test_owasp_lesson_completion`, `test_override_signatures`;
- **backend del punto 5 ESG**: tutti i moduli di `apps/os_lms/os_lms/os_lms/ai/simulations/tests/` (tra cui `test_access`, `test_instructor_api`, `test_debrief_prompts`, `test_debrief_job`, `test_notifications`, `test_prompt_sync`) e di `apps/os_lms/os_lms/os_lms/ai/bias/tests/`. Non chiamano l'AI: i fornitori sono finti nei test. Un test rosso in `test_debrief_prompts` o `test_debrief_job` può voler dire che il Coach rivede il nome dello studente: è una regressione di equità, non un dettaglio;
- **frontend** (in `frontend/src/tests/`): `inertPasteHtml`, `themeBootstrap`, `highContrast`, `accountDeletion`, `lessonLocking`;
- **script**: `test_dependency_floors`.

Quando una correzione di conformità nuova viene committata, aggiungi qui la sua suite.

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

`stop` è `null` quando nessuna fermata è aperta; `current` è `null` fra una release e l'altra. Le fermate **F9** e **F0** cadono prima della creazione del branch, quando il file di stato non esiste ancora: si chiudono nella conversazione e non si va oltre finché non sono chiuse.

---

## Passo 0 — Controlli

Esegui ed esamina:

```bash
git branch --show-current
git status --porcelain
git remote get-url upstream
git config rerere.enabled
git config core.hooksPath
test -f "$(git rev-parse --git-dir)/oslms-upstream-walk.json" && cat "$(git rev-parse --git-dir)/oslms-upstream-walk.json"
```

- **File di stato presente** → vai a «Ripresa di un percorso» in fondo, prima di tutto il resto.
- **Modifiche in sospeso:** sono tollerati `docs/WORKLOG.md` modificato e i file non tracciati (`??`). Qualunque altra riga blocca: elencala e chiedi al committente se committarla o metterla da parte. Non fare `stash` di tua iniziativa.
- **Merge o rebase in corso** (`git status` lo dice) → fermati e chiedi.
- **Remote `upstream` assente** → proponi `git remote add upstream https://github.com/frappe/lms.git` e chiedi.
- **`rerere` non attivo** → proponi `git config rerere.enabled true` e chiedi. Mai `rerere.autoUpdate`.
- **Controllo al commit non attivo** (`core.hooksPath` diverso da `.githooks`) → proponi `git config core.hooksPath .githooks` e chiedi: senza, i commit del percorso non vengono verificati.

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

## Passo 2b — Mappa delle personalizzazioni

```bash
python3 scripts/customization_map.py          # tabella leggibile
python3 scripts/customization_map.py --json   # per leggere i dati
```

La mappa confronta `HEAD` con l'ultima release upstream fusa (la stessa base del piano) e attribuisce ogni blocco di differenza a una funzionalità del catalogo: prima dalle righe `Oslms-Feature` dei commit che lo hanno introdotto, poi dalle ancore delle voci, dalle `areas` delle schede e da `docs/customizations/legacy-attribution.toml`. Il JSON ha `base`, `ref`, `features` (per id: `title`, `summary`, `files`, `hunks`, `commits`), `unattributed` (per blocco: `file`, `head_start`, `head_len`), `uncovered_files` (file nostri che nessuna scheda, voce `[[files]]` o residuo copre), `residue` e `residue_files` (il residuo approvato, con `reason` e `approved`) e `totals`. Se la partenza scelta al Passo 4 non è il branch corrente, rilancia con `--ref <partenza>`.

Presentala al committente **per funzionalità**, come tabella compatta: titolo, sintesi in una riga, quanti file upstream tocca, quali release in arrivo toccano quei file o i suoi `upstream_watch`. Per l'incrocio, per ogni release del piano (`previous` → `tag`): `git diff --name-only <previous> <tag>` contro i `files` della funzionalità, e i messaggi `git log --format=%B <previous>..<tag>` cercati senza distinguere maiuscole per ogni indizio di `upstream_watch` della scheda (`docs/customizations/features/<id>.toml`). Tag letterali, uno per argomento (regola 7). Sotto la tabella, in prosa breve: quali funzionalità sono più esposte e su quali F5 tornerà release per release. Non incollare le liste di blocchi: offri di mostrarle.

**F9 — blocchi non attribuiti o file nostri non coperti** (`unattributed` o `uncovered_files` non vuoti). **Decide il committente.** Un blocco che nessuna funzionalità rivendica è una nostra modifica a un file upstream di cui non si sa lo scopo: il merge potrebbe ripulirla senza che nessuno se ne accorga, e F5 non avrebbe niente con cui confrontarla. Un file nostro che nessuna scheda copre è una funzionalità che F5 non confronterà mai con le novità upstream. Si chiude **prima di partire**:
- elenca blocchi e file con `python3 scripts/customization_map.py --unattributed`; per ogni blocco mostra il diff `git diff <base> HEAD -- <file>` attorno a `head_start`, e per blocchi e file i nostri commit sul file (`git log --no-merges --format='%h %an %cs %s' <base>..HEAD -- <file>`);
- proponi a quale funzionalità appartiene, raggruppando i blocchi dello stesso scopo, e come attribuirlo:
  - una voce `[[files]]` con `path` e `features` in `docs/customizations/legacy-attribution.toml`, per i file modificati da commit anteriori alla regola `Oslms-Feature`;
  - oppure una scheda: il file nelle `areas` di una scheda esistente, se le appartiene per intero; una scheda nuova in `docs/customizations/features/<id>.toml` se la funzionalità non è nel catalogo (titolo e confini li approva il committente). Per i file nostri non coperti è la strada normale;
- se lo scopo non è ricostruibile dal codice e dai commit, **chiedi**: il committente lo attribuisce, oppure lo approva come residuo, cioè una voce `[[residue]]` con `path`, `reason` e `approved` (la data del suo ok) in `docs/customizations/legacy-attribution.toml`. Mai un residuo senza il suo ok esplicito;
- le attribuzioni sono commit di soli documenti sul branch di partenza, dopo l'ok del committente: `docs(customizations): attribute unmapped changes before <target>`. Se la partenza non è il branch corrente, scrivile al Passo 5 dopo il `git switch <partenza>`, prima di creare il branch del percorso;
- chiusura: `python3 scripts/customization_map.py --unattributed` (con `--ref <partenza>` se serve) riporta zero blocchi non attribuiti **e** zero file nostri non coperti: nessun blocco non attribuito; il residuo approvato è ammesso e va mostrato al committente (sezione «Residuo approvato» dell'uscita) e scritto nel rapporto di percorso. Non si passa al Passo 5, punto 3, con F9 aperta.

## Passo 3 — Domanda 1: fino a quale release?

`AskUserQuestion`, al massimo 4 opzioni: **la raccomandata per prima** con «(Consigliata)», poi i confini di rischio successivi (l'ultima release prima di ogni bump o rottura), poi la più recente. Nella descrizione di ogni opzione scrivi cosa comporta arrivarci (bump, rotture, file da censire). Il committente può indicare qualsiasi altra release con «Other».

## Passo 4 — Domanda 2: da dove partire e con quale nome?

`AskUserQuestion`. Proposta: partenza `feature/oslms`, nome `merge/upstream-<tag scelto>`. **Dichiara sempre il branch di partenza nel testo della domanda**: è il momento in cui ci si accorge di essere sul branch sbagliato. Se il branch corrente non è `feature/oslms`, offri entrambi e dillo esplicitamente.

- La partenza è `feature/oslms` o un branch che ne deriva. `master` e `develop` sono fuori ambito: non hanno il catalogo delle funzionalità né il controllo al commit. Se il committente li sceglie, fermati e spiegalo.
- Se la partenza scelta non è il branch corrente, rilancia `python3 scripts/upstream_plan.py --head <partenza>` e `python3 scripts/customization_map.py --ref <partenza>`: la base potrebbe essere diversa, e la mappa pure. Se lo è, mostralo e riconferma la Domanda 1.
- Se il branch di destinazione esiste già (`git rev-parse --verify --quiet <nome>`), fermati e chiedi: riprenderlo, sceglierne un altro nome, o altro. Non cancellarlo mai.
- **Conformità sulla partenza.** `git ls-tree --name-only -r <partenza> -- apps/os_lms/os_lms/os_lms/tests/test_owasp_package_e.py frontend/src/tests/highContrast.test.ts apps/os_lms/os_lms/os_lms/ai/simulations/teacher_review.py` deve stampare tutti e tre i file. Se ne manca uno, la partenza non contiene le correzioni OWASP o ESG: fermati, spiegalo e chiedi. Non avviare un percorso che le lascerebbe fuori. Il branch che le contiene va prima unito nella partenza, oppure usato come partenza.

## Passo 5 — Fermata F0 e branch

1. Se la partenza non è il branch corrente: `git switch <partenza>`. Se F9 è ancora aperta, chiudila qui (Passo 2b).
2. Rilevatore sulla partenza:

   ```bash
   python3 scripts/check_customizations.py --json
   ```

   **F0 — errori di partenza.** **Decide il committente.** Gli errori trovati sulla partenza (`C1`, `C2`, `C3`, `C6`, `C7`, e `C8` quando esiste `docs/customizations/features/.strict`) non sono una baseline da ignorare: un'ancora già persa o non unica prima del merge non può dire se il merge ha ripulito la regola, e una traduzione già persa non verrà riapplicata in F1. Si chiudono **prima di creare il branch**:
   - per ogni errore mostra voce, file, ancora e `intent`, e proponi la correzione: riportare la regola nel codice, scegliere un'ancora nuova e unica (`grep -cF` = 1), censire il marcatore `C3` con una voce collegata a una scheda, ripristinare la traduzione dal registro `docs/customizations/translations-it.toml`, collegare la voce a una scheda esistente; oppure, se la regola non vale più, `accepted-drift` (regola 3);
   - le correzioni sono commit sul branch di partenza, dopo l'ok del committente, con la riga `Oslms-Feature` quando toccano codice (regola 11);
   - chiusura: il rilevatore non riporta errori. Non creare il branch con F0 aperta.

   Gli avvisi non fermano, ma vanno detti al committente e scritti nel rapporto: `C0` (base upstream non disponibile: mancano i tag, torna al Passo 1), `C5` (ancora presente anche nella base: non dimostra la nostra modifica, quindi il merge può ripulire la regola senza che il rilevatore se ne accorga; quelle voci si guardano a mano in F1 e F2), `C9` (copia congelata senza `frozen_from`: F6 non potrà calcolare cosa le manca), `C4` e `C8`.
3. Crea il branch:

   ```bash
   git switch -c <nome> <partenza>
   ```

4. Registra l'esito del rilevatore (dopo F0, solo avvisi) come `detector_baseline`.
5. Crea `docs/upstream-checks/` se manca e il rapporto di percorso `AAAA-MM-GG-percorso-<base>-<target>.md` con intestazione (data, partenza e suo SHA, branch, base, arrivo, tabella del piano, tabella della mappa per funzionalità, avvisi `C5` e `C9`, fermate F9 e F0 con le correzioni fatte).
6. Scrivi il file di stato.

## Passo 6 — Il ciclo, per ogni release `T` (precedente `P`), dalla più vecchia

Imposta `current = T` nello stato. Poi:

### 6.1 Analisi prima del merge

```bash
python3 scripts/upstream_plan.py --to T --json
```

Su questo branch la base è `P`, quindi il JSON contiene solo `T`. Da qui e dai commit `P..T` si ricavano **prima di fondere** le fermate di giudizio, nell'ordine sotto. Raccogli le domande di una stessa release e ponile insieme quando sono indipendenti; registra ogni risposta in `decisions`.

**F7 — file con modifiche nostre non censite** (`uncatalogued` non vuoto). **Decide il committente.** Il merge potrebbe ripulirle senza che il rilevatore se ne accorga, perché non le conosce.
- Per ogni file mostra cosa abbiamo cambiato: i nostri commit con `git log --no-merges --format='%h %an %cs %s' P..HEAD --not --remotes=upstream <tag di release> -- <file>` (i tag di release, letterali, sono quelli elencati da `git tag -l 'v*'` che hanno forma `vX.Y.Z`; **non** usare `--tags`: esclude anche i nostri tag `ve…`/`vi…` e fa sparire i nostri commit) e il diff `git diff P HEAD -- <file>`.
- Proponi di censirli **prima** del merge, come fatto il 2026-09-23 per `v2.58.1` (commit `0c4edec85`): commento marcatore `OSLMS-CUSTOM` sulla riga che porta la regola, voce in `docs/customizations/spa-grafts.toml` con `file`, `anchor` unica (`grep -cF` = 1), `intent` che dice **perché** e `feature = "<id>"` (scheda esistente, o nuova approvata dal committente). Per i file senza commenti (JSON) la voce basta, senza marcatore.
- Con molti file (decine), proponi di raggrupparli per funzionalità e procedi a gruppi, un commit per gruppo: `docs(customizations): catalogue unmarked grafts touched by <T>`.
- Se l'`intent` di una modifica non è ricostruibile dal codice e dai commit, **chiedi**; se lo deduci, `confidence = "low"`.
- Chiusura: rilancia il piano (`uncatalogued` di `T` = 0) e il rilevatore (nessun `C3`).

**F6 — bump di `frappe-ui` o pagina congelata toccata.** **Decide il committente.**
- *Bump:* il salto viene fuso pulito e si rompe a runtime nei 23 componenti frappe-ui copiati in `frontend/src/overrides/frappe-ui/`. Spiegalo e ricorda i precedenti: beta.24 ha già causato in produzione l'errore 417 su `boot_config`; l'override `Combobox` perde `modelValue` ai bump (campi Link vuoti che però salvano); il fork `DataImport` va riconfrontato file per file. Per ogni voce con siti in `frontend/src/overrides/frappe-ui/` e `frozen_from`, mostra cosa è cambiato nel componente originale fra la versione copiata e quella nuova: `python3 scripts/frozen_diff.py --entry <id> --to <nuova versione frappe-ui>` (versione senza `v`, es. `1.0.0-beta.29`). Lo script usa il sottomodulo `frappe-ui` e non lo inizializza né fa fetch da solo: se esce con codice 2 stampa il comando da eseguire (es. `git submodule update --init frappe-ui`); **chiedi prima di lanciarlo**. Opzioni: fermare il percorso a `P`; procedere e riconciliare ora gli override; procedere registrando la riconciliazione come attività aperta. Riconciliato un override, il suo `frozen_from` passa alla versione nuova.
- *Pagina congelata* (`frozen` non vuoto): il file originale è stato modificato a monte, ma noi serviamo la copia in `overrides/`, quindi la modifica non arriva. Per ogni voce coinvolta: `python3 scripts/frozen_diff.py --entry <id> --to T`. Lo script parte dal `frozen_from` della voce (la release da cui è stata fatta la copia), quindi il diff è **tutto ciò che la copia non ha ricevuto** fino a `T`, non solo quello di `P..T`: è il confronto a tre vie (originale alla copia, copia nostra, originale in `T`). Spiega cosa porta, confrontalo con la copia e proponi cosa portare nella copia. Se la voce non ha `frozen_from` (avviso `C9`), la base della copia non è nota: mostra solo `git diff P T -- <originale>`, dillo, e proponi di ricostruire `frozen_from` dalla storia git della copia. Se lo script esce con codice 2 (tag mancante), esegui il comando che stampa. Il committente decide. Se porti nella copia **tutte** le modifiche fino a `T`, aggiorna `frozen_from` a `T` nella voce; se ne porti solo una parte, lascialo com'è e scrivi nel rapporto cosa resta fuori.

**F4 — rotture dichiarate** (`breaking` non vuoto). **Decide il committente.** Per ogni rottura:
- trova il commit che la dichiara: `git log --format='%H %s' --grep='<testo della riga>' --fixed-strings P..T`; se è un merge di PR, i commit della PR sono `<merge>^1..<merge>^2`;
- file toccati dalla PR, incrociati con l'inventario (`grep -n '<file>' docs/customizations/*.toml`) e con i nostri file modificati;
- valutazione d'impatto: cosa cambia a monte, quali voci insistono su quell'area, cosa si rompe se non si fa nulla, costo stimato dell'adeguamento.
Scrivila nel rapporto e chiedi. Non proseguire da solo.

**F5 — novità upstream che potrebbero soppiantare una nostra funzionalità.** **Decide sempre il committente; la skill confronta e raccomanda, e basta** (regola 10). Per ogni release, prima del merge, in quattro tempi.

1. *Candidati.* Incrocia le novità di `P..T` con ogni scheda `status = "active"` del catalogo (`docs/customizations/features/*.toml`), **comprese le funzionalità che vivono solo in `apps/os_lms`** e che il merge non tocca: sono proprio quelle che una novità upstream può rendere inutili senza un solo conflitto.
   - Novità upstream (`P` e `T` letterali, regola 7):
     - messaggi dei commit, soggetti **e corpi** (frappe/lms mette il titolo della PR nel corpo del merge): `git log --format='%H%n%B%x00' P..T`, poi `git show --name-only <sha>` per i file di ciascuno;
     - file cambiati: `git diff --name-status P T`;
     - doctype e campi nuovi: `git diff --name-status --diff-filter=A P T -- 'lms/lms/doctype/*/*.json'` e `git diff P T -- 'lms/lms/doctype/*/*.json' | grep -nE '^\+\s*"(fieldname|label)"'`;
     - endpoint nuovi o cambiati: `git diff P T -- lms | grep -nE '^\+.*@frappe\.whitelist'` (lo stesso elenco serve a F8);
     - stringhe nuove: `git diff P T -- lms/locale/main.pot | grep -nE '^\+msgid'`.
   - Per ogni scheda, contro: gli indizi di `upstream_watch` (cercati senza distinguere maiuscole in messaggi, nomi di file, doctype, campi, endpoint e stringhe); le `areas`; i `data` (doctype, campi e impostazioni con lo stesso nome o lo stesso scopo); i siti delle voci collegate (`feature = "<id>"`) e i file upstream della funzionalità (`python3 scripts/customization_map.py --feature <id> --json`) toccati da `P..T`.
   - In più: le voci di inventario il cui `intent` annuncia già una sovrapposizione con questa release (cerca `T` e «ATTENZIONE» negli intent delle voci toccate) e le `notes` delle schede che fanno lo stesso.
   - Un riscontro di parole non basta: leggi il commit e stabilisci se la novità tocca davvero lo stesso comportamento. Se nessun candidato resta, scrivilo in una riga nel rapporto e prosegui.
2. *Confronto*, per ogni candidato, scritto nel rapporto di percorso in una sezione «F5 — `<id>` e `<novità>`»:
   - cosa fa la novità upstream, **leggendo il codice di `T`** (`git show T:<file>`), non solo i messaggi;
   - tabella delle regole `behaviour` della scheda: per ciascuna, coperta / coperta in parte / non coperta dall'upstream, con la prova (file e funzione in `T`, o perché manca);
   - ruoli: chi può fare cosa nell'una e nell'altra (`roles` della scheda contro i permessi della novità);
   - dati: cosa andrebbe migrato (i `data` della scheda, nostri custom field e doctype, contro i campi upstream);
   - livello di somiglianza in parole, **alta**, **parziale** o **bassa**, con il motivo; nessun punteggio numerico. Nel dubbio fra bassa e parziale, tratta come parziale e chiedi;
   - cosa si perde e quanto costa ciascuna strada;
   - raccomandazione motivata.
3. *Domanda, sempre.* Per **ogni** candidato con somiglianza alta o parziale, `AskUserQuestion`, **anche quando la raccomandazione è chiara**. Prima di porla scrivi la fermata in `stop`. Nel testo: la scheda (titolo e id), la novità, la somiglianza con il motivo e il rimando alla sezione del rapporto. Le opzioni sono sempre queste quattro, nessuna esclusa:
   - **Adottare l'upstream e ritirare la nostra**: la scheda passa a `replaced-by-upstream`, il nostro codice si rimuove (6.4b);
   - **Adottare l'upstream e riportare sopra solo le regole non coperte**: la scheda resta `active`, con `behaviour` ridotto alle regole riportate (6.4b);
   - **Mantenere la nostra**: nessun cambiamento alla nostra funzionalità; la novità upstream entra con il merge come qualunque altra modifica;
   - **Rimandare**: il percorso si ferma a `P`, `T` non si fonde.

   L'opzione raccomandata va per prima con «(Consigliata)» e il motivo nella descrizione; le altre restano sempre selezionabili. La raccomandazione sta solo nel testo, mai in un'azione: **la skill non adotta e non scarta mai niente da sola**, nemmeno con somiglianza alta e scelta apparentemente ovvia; senza risposta non si fonde `T`. Candidati indipendenti della stessa release si possono porre nella stessa chiamata. I candidati a somiglianza **bassa** vanno in una riga del rapporto (scheda, novità, motivo), senza domanda.
4. *Registrazione.* Ogni risposta va:
   - in `decisions` dello stato: `{"tag": "T", "stop": "F5", "question": "<id>: <novità>", "answer": "<opzione scelta>", "date": "…"}`;
   - nella `history` della scheda: `{ date = "…", ref = "T", summary = "F5: <novità>, somiglianza <livello>; decisione: <opzione scelta>" }`. Per «Mantenere» e «Rimandare» è un commit di soli documenti sul branch del percorso, `docs(customizations): record the <T> comparison for <id>`; per le adozioni entra nei commit di 6.4b.

   Azzera `stop` solo dopo aver registrato. Con «Rimandare»: non fondere `T`, aggiorna stato e rapporto e vai al Passo 7 con `P` come ultima release fusa; se `P` è la base del percorso, nessuna release è stata fusa: dillo e chiedi cosa fare del branch.

**F8 — superficie nuova da controllare per la conformità.** Una release può aggiungere un'API che fa ciò che una nostra correzione ha chiuso, per esempio un secondo modo di cancellare un utente o di leggere i certificati. Il rilevatore non la vede, perché non tocca nessuna ancora. **Decide il committente** quando raggiunge un'area protetta; altrimenti basta una riga nel rapporto.
- Funzioni pubbliche nuove o cambiate: `git diff P T -- lms | grep -nE '^\+.*@frappe\.whitelist'` (con `P` e `T` letterali), poi leggi ogni funzione in `git show T:<file>`. Guarda anche `git diff P T -- lms/hooks.py` per i permessi e `git diff --stat P T -- 'lms/lms/doctype/*/*.json'` per i doctype con permessi cambiati.
- Per ognuna stabilisci: chi può chiamarla (ruoli, `allow_guest`), cosa legge o scrive, e se raggiunge un'area già corretta. Le aree sono: certificati (E4), membri e ruoli (E10, E20), lezioni dal vivo (E6), discussioni (E12), recensioni (E11), esercizi (E9), dati degli studenti visti dal Valutatore (E8), quiz (E1), file ed export dei corsi (E3, D1), registrazione (E5), indicizzazione AI (E13).
- I nostri hook di permesso valgono solo per gli accessi con controllo: `frappe.get_doc`/`get_list` sì; `frappe.get_all`, `frappe.db.*` e `ignore_permissions=True` no. Una funzione nuova che usa i secondi su un doctype protetto è quasi sempre un aggiramento.
- Se raggiunge un'area protetta: spiega il rischio, proponi override o innesto con voce di inventario e test, e chiedi.

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
3. risolvi **preservando l'intento, non la riga**: se l'upstream ha riscritto il codice attorno, riesprimi la regola nel codice nuovo e aggiorna l'`anchor` della voce se cambia; se l'upstream ora fa da sé ciò che faceva la nostra modifica, **non** scartarla da solo: è un caso F5, chiedi. Se F5 ha già deciso di adottare l'upstream per quella funzionalità, prendi il lato upstream dove la novità sostituisce il nostro codice e lascia il resto della rimozione ai commit dedicati di 6.4b;
4. se nessuna voce copre il file, il conflitto è fra codice upstream e codice upstream (tipicamente residuo del vecchio merge di `upstream/develop`): di norma vince `T`, ma controlla che non sia una nostra modifica non censita — in quel caso chiedi;
5. **traduzioni** (`lms/locale/*.po`): prendi la versione upstream e riapplica le nostre voci. Quali sono lo dice `docs/customizations/translations-it.toml`: le coppie `msgid` → `msgstr` del nostro `it.po` che differiscono dalla base upstream, generate dallo script, mai scritte a mano. Riapplica ogni coppia il cui `msgid` esiste ancora in `T`; quelle il cui `msgid` l'upstream ha tolto non si riapplicano: elencale nel rapporto. Verifica con `python3 scripts/customization_translations.py --check`: l'unico `C7` ammesso è quello delle coppie tolte dall'upstream, che restano segnalate finché il registro non si rigenera al Passo 7; ogni altro `C7` è una traduzione nostra non riapplicata. Il `it.po` upstream ha stringhe rotte note (memoria `it-translations-workflow`);
6. `yarn.lock`: non risolverlo a mano; risolvi `package.json` e rigenera il lock con `yarn install --ignore-engines` dentro `frontend/`. In `package.json` nessuna versione scende sotto le soglie di `scripts/tests/test_dependency_floors.py`: se l'upstream ne porta una più bassa, tieni la nostra. Dopo il lock, `python3 -m unittest scripts.tests.test_dependency_floors` deve passare.

Nel rapporto: una riga per file, con la voce di inventario applicata e come.

### 6.3 Rilevatore sulla risoluzione

```bash
python3 scripts/check_customizations.py --json
```

Confronta con `detector_baseline`: contano **solo gli errori nuovi**. Un `C1`/`C2` nuovo su un file che hai risolto tu in F1 è un errore della tua risoluzione: correggilo adesso, dentro il merge. Fanno eccezione i `C7` delle coppie il cui `msgid` l'upstream ha tolto (F1, punto 5): sono attesi fino alla rigenerazione del registro al Passo 7, e vanno solo elencati nel rapporto.

### 6.4 Commit del merge

```bash
git commit --no-edit
```

Il messaggio predefinito (`Merge tag 'T' into <branch>`) è quello giusto: commitlint ignora i messaggi di merge. Aggiungi le righe di attribuzione previste dalle convenzioni della sessione.

**Righe `Oslms-Feature` nel merge.** Un merge di release upstream **senza conflitti** è esente dal controllo al commit. Un merge **con conflitti** no: le risoluzioni che riapplicano i nostri innesti nascono dentro il commit di merge, quindi il controllo lo rifiuta se non dice di quali funzionalità sono. Aggiungi una riga `Oslms-Feature: <id>` per ogni funzionalità le cui voci hai applicato in F1 (il `feature` delle voci; per i file senza voci, la funzionalità che la mappa attribuisce al file: `python3 scripts/customization_map.py --json`), nell'ultimo paragrafo insieme a `Co-Authored-By:`. `--trailer` le mette nel posto giusto:

```bash
git commit --no-edit --trailer 'Oslms-Feature: <id-1>' --trailer 'Oslms-Feature: <id-2>' --trailer 'Co-Authored-By: <modello> <noreply@anthropic.com>'
```

Se il controllo rifiuta il merge, leggi il suo messaggio (dice cosa manca) e ripeti; mai `--no-verify` (regola 11). Le funzionalità attribuite vanno anche nella sezione di `T` del rapporto.

### 6.4b Adozione dell'upstream

Solo per le funzionalità per cui il committente, **rispondendo a F5**, ha scelto di adottare l'upstream; mai per altre. Si fa dopo il commit del merge di `T`, perché la novità esiste solo da lì, e prima di F2. Per ogni funzionalità adottata, in **commit dedicati**, mai dentro il merge:

1. **Codice.** Rimuovi il nostro codice superato: moduli, endpoint e hook in `apps/os_lms`, componenti in `frontend/src/oslms/`, innesti nei file upstream, override in `frontend/src/overrides/`. Con «riportare sopra solo le regole non coperte», riesprimi quelle regole sopra il codice upstream di `T`, ciascuna con una voce di inventario (ancora unica, `intent`, `feature`) e un test.
2. **Test.** I test che verificano solo regole ritirate si tolgono nello stesso commit e si elencano nel rapporto; un test di una regola riportata resta e deve passare (regola 2). Nel dubbio su quale sia quale, chiedi.
3. **Scheda.** «Ritirare la nostra»: `status = "replaced-by-upstream"`. «Riportare le regole non coperte»: resta `active`, con `behaviour` ridotto alle regole riportate e `areas`/`data` aggiornati. In entrambi i casi una riga in `history` con data, release `T` e decisione F5 (regola 3: la scheda non si cancella).
4. **Voci di inventario** collegate alla scheda che non servono più: `status = "accepted-drift"` con data e motivo nell'`intent` (es. «2026-12-01: adottata la novità upstream di v2.67.0, decisione F5»). La risposta a F5 vale come ok della regola 3 per le voci di quella scheda; per voci di altre schede chiedi.
5. **Dati.** Se la scheda ha `data` (custom field, doctype, impostazioni) che l'upstream rappresenta con campi suoi, scrivi una patch di migrazione in `apps/os_lms` (registrata in `apps/os_lms/os_lms/patches.txt`) che porta i dati nei campi upstream. Mostrala al committente, con cosa sposta e cosa si perde, e committala **solo dopo il suo ok**. Non eseguirla mai su un DB remoto.
6. **Commit.** Ogni commit porta `Oslms-Feature: <id>` (regola 11) e la scheda in stage, per esempio `refactor(oslms): adopt upstream <novità> from <T> in place of <id>`. Aggiungi gli sha a `fix_commits` della release nello stato.
7. **Verifica.** Rilevatore senza errori nuovi (le voci `accepted-drift` non contano), e nel rapporto: cosa è stato rimosso, cosa riportato, quali dati migrati, quali test tolti. Ogni funzionalità adottata entra nella lista delle prove nell'app del Passo 7.

### 6.5 F2 — personalizzazione persa in silenzio

Rilancia il rilevatore. Un `C1`/`C2` nuovo rispetto alla baseline su un file che git ha fuso **senza conflitto** è una perdita silenziosa. Decide l'agente:
- leggi `git diff P T -- <file>` e capisci **come** l'ancora è sparita (riscrittura, rinomina, rimozione);
- riapplica la regola secondo l'`intent`; se il file non esiste più (`C2`), stabilisci dove la regola deve vivere ora e aggiorna `file` e `anchor` della voce — **se non è evidente, chiedi**;
- un commit per voce: `fix(oslms): restore <inventory-id> after <T>`, con `Oslms-Feature: <feature della voce>`;
- un `C7` nuovo è una nostra traduzione sovrascritta dal merge senza conflitto: riapplica la coppia dal registro `docs/customizations/translations-it.toml`.

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
3. Aggiungi al rapporto di percorso la sezione di `T`: ampiezza reale (dal piano), fermate incontrate e come sono state risolte, risoluzioni `rerere` riapplicate, voci di inventario toccate, funzionalità attribuite nel merge, confronti F5 con la decisione presa, adozioni eseguite, decisioni chieste con la risposta, esito di rilevatore e build.
4. Una riga al committente («`T` fusa: N conflitti risolti, M ripristini, build verde») e passa alla release successiva **senza chiedere**, a meno che non ci sia una fermata.

## Passo 7 — Chiusura del percorso

Dopo l'ultima release:

1. **Registro delle traduzioni.** Rigenera `docs/customizations/translations-it.toml` contro la nuova base: prima `python3 scripts/customization_translations.py --check` e confronta i `C7` con le coppie che in F1 risultavano tolte dall'upstream (devono essere solo quelle: un `C7` diverso è una traduzione nostra persa, da riapplicare), poi `python3 scripts/customization_translations.py --write`. Commit: `docs(customizations): record Italian translations against <target>`.
2. **Suite completa**, riportando l'esito reale di ciascun comando:
   - `python3 scripts/check_customizations.py`
   - `python3 scripts/customization_map.py --unattributed`: nessun blocco non attribuito e nessun file nostro non coperto (il residuo approvato è ammesso e va riportato); se ce ne sono, è una F9 nata durante il percorso, da chiudere sul branch del percorso prima di proseguire
   - `python3 -m unittest discover -s scripts/tests -t .`
   - `cd frontend && yarn test` (Vitest)
   - **test backend `os_lms`** nel container Docker. Controlla con `docker compose -f docker/docker-compose.yml ps`; se il container `frappe` non è attivo, **chiedi** se avviarlo. Il container monta il repository, quindi vede il branch di merge, ma il suo DB ha lo schema vecchio: serve un `migrate`. **Chiedi prima di lanciarlo**: aggiorna il DB di sviluppo alla nuova release e non torna indietro cambiando branch. Se il CLI `bench` è rotto nel container, usa il Python dell'ambiente (memoria `stale-doctype-meta-in-running-container`: `SiteMigration().run("lms.localhost")` e `unittest` con `frappe.init`/`frappe.connect`; bench in `/home/frappe/bench-data/frappe-bench`, sito `lms.localhost`).
   - **suite di conformità** (sezione «Conformità»): riporta l'esito di ciascuna per nome, anche se sono già comprese nei comandi sopra.
   - **scansione delle dipendenze**: `osv-scanner scan source -r .` se è installato. Altrimenti scrivi nel rapporto che la scansione girerà su GitHub (workflow Dependency Scan, bloccante) e va guardata prima di unire il branch.
   - Un test rosso: regola 2. Ripara il codice o chiedi.
3. Esegui la skill **`/upstream-check`** passando come riferimento di partenza `start_commit` (non `HEAD^1`: il percorso ha più merge).
4. Completa il rapporto di percorso: cosa è stato adottato, cosa è stato rifiutato consapevolmente e perché, quali personalizzazioni sono state riespresse, cosa resta aperto (riconciliazioni rimandate, voci `confidence = "low"` nuove).
5. **Lista puntuale di cosa provare nell'app** (`http://lms.localhost:8000/lms`), ricavata dalle voci toccate da conflitti, ripristini e adeguamenti, e dalle **funzionalità adottate dall'upstream** in 6.4b: per ognuna, la novità upstream che ora fa il lavoro della nostra (regole `behaviour` che la scheda aveva, provate una per una sulla versione upstream) e, se riportate, le regole rimaste nostre. Se c'è una patch di migrazione dei dati, aggiungi la prova che i dati migrati compaiono dove l'upstream li mostra. Per ciascuna: cosa fare, cosa deve succedere, **con quale ruolo** (da `visibility.allow`/`deny` della voce, altrimenti dall'`intent`; se il ruolo non è ricavabile dillo), e perché è in lista. Esempio:
   > Apri un quiz come **Studente**, lascia una domanda senza risposta e consegna: la consegna deve riuscire e la domanda saltata vale 0. *(Conflitto risolto su `lms/lms/doctype/lms_quiz/lms_quiz.py`, voce `quiz-submit-unanswered`.)*

   Per ogni voce o area di conformità toccata (conflitti, ripristini, F8), aggiungi la prova sullo staging corrispondente del piano OWASP: le tabelle «Test su staging» del documento dicono chi, quali passi e quale risultato.
6. Committa i rapporti sul branch del percorso: `docs(upstream): report the walk to <target>`.
7. Chiedi al committente cosa fare del branch: unirlo nel branch di partenza, lasciarlo per revisione, pubblicarlo. **Nulla di questo senza il suo ok esplicito.**
8. Archivia lo stato: rinomina il file in `oslms-upstream-walk.<target>.done.json` (stessa cartella), così un avvio futuro non propone di riprenderlo.
9. Worklog.

## Ripresa di un percorso

Se all'avvio esiste il file di stato:

1. Mostra lo stato in chiaro: partenza, branch, arrivo, release completate con i loro commit, release corrente, fermata attiva con il suo riassunto, decisioni già prese.
2. Verifica la coerenza: il branch esiste; i `merge_commit` completati sono antenati del suo `HEAD`; se c'è un merge in corso (`git status`), è quello di `current`.
3. Chiedi: **riprendere** (default), oppure **abbandonare il percorso** (lo stato si archivia come `oslms-upstream-walk.<target>.abandoned.json`; il branch resta dov'è, non si cancella niente).
4. Riprendendo: `git switch <branch>` (se ci sono modifiche in sospeso, Passo 0), poi riparti **dalla fermata attiva**. Se era una domanda al committente, riponila con il contesto; se era un lavoro dell'agente (F1, F2, F3), riverificane lo stato reale prima di continuare, senza fidarti del riassunto.
