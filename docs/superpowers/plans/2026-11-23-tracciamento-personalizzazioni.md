# Tracciamento automatico delle personalizzazioni — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ogni personalizzazione del fork è attribuita a una funzionalità del catalogo al momento del commit, la mappa delle nostre differenze dall'upstream si calcola da git, e la skill di aggiornamento confronta le novità upstream con le nostre funzionalità chiedendo sempre all'utente.

**Architecture:** si estende il pacchetto `scripts/customizations/`, oggi usato da rilevatore e piano, con quattro moduli nuovi: catalogo, accesso a git, traduzioni e attribuzione. Sopra ci sono tre comandi: `commit_guard.py` (hook `commit-msg`), `customization_map.py` (mappa) e `customization_translations.py` (generatore). Le due skill e la CI li usano. Il lavoro si chiude con la migrazione delle 374 voci in schede, fatta a lotti e approvata dall'utente.

**Tech Stack:** Python ≥ 3.11 solo libreria standard (`tomllib`, `subprocess`, `unittest`), git CLI, hook git, GitHub Actions, skill di Claude Code in Markdown.

**Spec:** `docs/superpowers/specs/2026-11-23-tracciamento-personalizzazioni-design.md`

## Global Constraints

- Python solo libreria standard, eseguibile senza bench né Docker; indentazione a **tab** come gli script esistenti.
- Commenti, identificatori e messaggi di commit in inglese; messaggi rivolti all'utente o a Claude (errori del controllo, rapporti) in italiano.
- Test in `scripts/tests/` con `unittest`; si lanciano con `python3 -m unittest discover -s scripts/tests -t .`.
- Ogni chiamata git passa da `subprocess` con lista di argomenti, mai stringhe di shell costruite (regola 7 della skill).
- Commit in Conventional Commits. I commit di strumenti e documenti **non** aggiornano l'etichetta `versionApp`: la regola del bump vale solo per il codice dell'app.
- Ambito: solo `feature/oslms` e i branch che ne derivano. `master` e `develop` sono esclusi.
- Nome della riga nei commit: `Oslms-Feature`. Deroga: `Oslms-Feature: none (<motivo>)`, non ammessa per `feat` e `fix`.
- Stati di una scheda: `active`, `retired`, `replaced-by-upstream`.
- Prima di ogni commit va chiesto l'ok all'utente (memoria `ask_before_changes_read_freely`). Durante l'esecuzione del piano l'ok dato al piano copre i commit dei task 1-9. La migrazione (task 10-12) va approvata a lotti.
- Il branch di lavoro parte da `feature/oslms`. Le modifiche non committate di `feature/live-class-draft` vanno sistemate prima (vedi Task 10).

## Review Focus

1. **Riga in un punto sbagliato del messaggio.** Una riga `Oslms-Feature:` scritta a metà del corpo, e non nel blocco finale, non conta come attribuzione, proprio come per `git interpret-trailers`. Test in Task 5.
2. **File rinominati nello stage.** Un file upstream rinominato da un nostro commit va classificato con **entrambi** i percorsi, il vecchio e il nuovo. Test in Task 5.
3. **Commit di merge del percorso con conflitti.** Se `MERGE_HEAD` punta a un tag di release upstream e `$GIT_DIR/MERGE_MSG` elenca dei conflitti, la riga è obbligatoria. Senza conflitti il merge passa. Test in Task 5.
4. **Scheda malformata nello stage.** Il controllo deve bloccare il commit con un messaggio chiaro, senza andare in crash e senza lasciar passare. Al contrario di `inventory_guard.py`, che fallisce in silenzio, qui si fallisce in modo bloccante. Test in Task 5.
5. **Commit fatto in un worktree**, dove `.git` è un file e non una cartella. La cartella git si ricava sempre con `git rev-parse --git-dir`, mai con `Path(".git")`. Test in Task 5 tramite `git worktree add` nel repository di prova.

---

### Task 1: Catalogo delle funzionalità e collegamento delle voci

**Files:**
- Create: `scripts/customizations/features.py`
- Modify: `scripts/customizations/model.py` (campi `feature` e `frozen_from` su `Entry`)
- Modify: `scripts/customizations/checks.py` (nuovo `check_feature_links`)
- Modify: `scripts/check_customizations.py` (carica il catalogo, esegue C8)
- Create: `docs/customizations/features/README.md` (schema della scheda, copiato dal §5.2 del design)
- Test: `scripts/tests/test_features.py`, `scripts/tests/test_checks.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Feature(id: str, title: str, status: str, summary: str, why: str, behaviour: tuple[str, ...], areas: tuple[str, ...], upstream_watch: tuple[str, ...], history: tuple[dict, ...], roles: tuple[str, ...] = (), data: tuple[str, ...] = (), tests: tuple[str, ...] = (), notes: str = "", source: str = "")`
  - `FEATURE_STATUSES = frozenset({"active", "retired", "replaced-by-upstream"})`
  - `load_features(directory: Path, read: Callable[[str], str | None] | None = None) -> dict[str, Feature]`. Senza `read` legge i file `*.toml` da disco; con `read` legge i percorsi relativi alla repo tramite la funzione (serve al Task 5 per leggere lo stage). Solleva `InventoryError`.
  - `Feature.matches_path(path: str) -> bool`, con glob `fnmatch` su `areas`.
  - `Entry.feature: str | None`, `Entry.frozen_from: str | None`
  - `check_feature_links(entries: list[Entry], features: dict[str, Feature], strict: bool) -> list[Finding]`, codice `C8`: voce senza `feature` o con `feature` sconosciuta. Severità `ERROR` se `strict`, altrimenti `WARNING`.
  - `STRICT_FEATURES_FLAG = Path("docs/customizations/features/.strict")`: se il file esiste, `check_customizations.py` esegue C8 in modo `strict`. Il file lo crea il Task 12.

- [ ] **Step 1: Scrivere i test che falliscono** in `test_features.py`:
  - `test_loads_a_valid_card`: la scheda `live-class-draft-publish.toml` con tutti i campi obbligatori si carica, e `behaviour` è una tupla di stringhe.
  - `test_rejects_id_different_from_filename`: `InventoryError`, e il messaggio contiene il nome del file.
  - `test_rejects_missing_required_field`: per ciascuno di `id, title, status, summary, why, behaviour, areas, upstream_watch, history`.
  - `test_rejects_unknown_status`.
  - `test_reads_through_a_reader_function`: `read` restituisce il testo e non si tocca il disco.
  - `test_matches_path_with_globs`: `areas=("apps/os_lms/os_lms/os_lms/live_class_*.py",)` corrisponde a `.../live_class_draft.py` e non a `.../valutatore.py`.

  In `test_checks.py`:
  - `test_c8_warns_on_entry_without_feature_when_not_strict`
  - `test_c8_errors_on_unknown_feature_when_strict`
  - `test_c8_skips_accepted_drift`
- [ ] **Step 2: Eseguire i test** con `python3 -m unittest scripts.tests.test_features scripts.tests.test_checks -v`. Atteso: FAIL con `ModuleNotFoundError` / `ImportError`.
- [ ] **Step 3: Implementare** `features.py` e le modifiche a `model.py`/`checks.py`/`check_customizations.py`. La cartella delle schede è `docs/customizations/features/`, e `load_inventory` continua a leggere solo `docs/customizations/*.toml` senza ricorsione, quindi le schede non vengono scambiate per voci. Scrivere il README delle schede.
- [ ] **Step 4: Eseguire tutti i test** con `python3 -m unittest discover -s scripts/tests -t .`. Atteso: OK. Poi `python3 scripts/check_customizations.py`: atteso un avviso C8 per ogni voce attiva (348), nessun errore nuovo oltre ai 3 C1 già noti.
- [ ] **Step 5: Commit** `feat(customizations): add the feature catalogue and link entries to features`

### Task 2: Accesso a git condiviso, C5 e C6

**Files:**
- Create: `scripts/customizations/gitbase.py` (spostamento di `Git`, `PlanError`, `find_base`, `sort_release_tags`, `parse_version`, `RELEASE_TAG` da `upstream_plan.py`)
- Modify: `scripts/upstream_plan.py` (importa da `gitbase`, nessun cambio di comportamento)
- Modify: `scripts/customizations/checks.py` (C5, C6; `check_sites` legge tramite una funzione)
- Modify: `scripts/check_customizations.py` (opzioni `--base <tag>`, `--no-base`)
- Test: `scripts/tests/test_checks.py`, `scripts/tests/test_upstream_plan.py` (deve passare senza modifiche ai test)

**Interfaces:**
- Produces:
  - `gitbase.Git(repo_root: Path)` con `run`, `lines`, `show(ref, path) -> str | None` e `is_ancestor`, invariati; in più `git_dir() -> Path` (da `git rev-parse --git-dir`) e `release_tags() -> list[str]`.
  - `gitbase.find_base(git: Git, head: str) -> str`, che solleva `PlanError`.
  - `Reader = Callable[[str], str | None]`: dato un percorso relativo restituisce il testo, oppure `None` se il file non c'è.
  - `disk_reader(repo_root: Path) -> Reader`.
  - `check_sites(entries, read: Reader) -> list[Finding]`. Prima prendeva `repo_root`: aggiornare tutti i chiamanti.
  - `check_anchor_provenance(entries, read: Reader, read_base: Reader) -> list[Finding]`, codice `C5`, severità `WARNING`: l'ancora compare anche nel file della base.
  - `check_anchor_uniqueness(entries, read: Reader) -> list[Finding]`, codice `C6`, severità `ERROR`: l'ancora compare più di una volta.
  - `check_customizations.py`: se la base non è calcolabile e non c'è `--no-base`, emette un finding `C0` di livello `WARNING` ("base upstream non disponibile: C5 e C7 saltati") e prosegue.

- [ ] **Step 1: Scrivere i test che falliscono**:
  - `test_c5_flags_anchor_also_in_base`
  - `test_c5_ignores_anchor_only_ours`
  - `test_c5_skips_file_absent_in_base`
  - `test_c6_flags_anchor_found_twice`
  - `test_c6_accepts_unique_anchor`
  - `test_check_sites_reads_through_reader`
  - `test_cli_reports_c0_when_base_missing`: si lancia `main(["--repo-root", <tmp senza git>, "--json"])` e il risultato contiene `C0` con severità `warning`.
- [ ] **Step 2: Eseguire i test**. Atteso: FAIL.
- [ ] **Step 3: Implementare.** Spostare le funzioni in `gitbase.py` senza cambiarle. `check_customizations.py` costruisce `read_base` con `Git.show(base, path)`.
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK, compresi i test di `test_upstream_plan` rimasti invariati. Poi `python3 scripts/check_customizations.py`: atteso 25 avvisi C5 e 1 errore C6 (`uploader-mobile-wrap-description`), come misurato il 2026-11-23.
- [ ] **Step 5: Commit** `feat(customizations): flag anchors that also exist upstream or are not unique`

### Task 3: Traduzioni nostre (C7)

**Files:**
- Create: `scripts/customizations/translations.py`
- Create: `scripts/customization_translations.py` (comando con `--write` e `--check`)
- Modify: `scripts/check_customizations.py` (esegue C7 se il file generato esiste e la base è disponibile)
- Test: `scripts/tests/test_translations.py`

**Interfaces:**
- Produces:
  - `parse_po(text: str) -> dict[tuple[str, str], str]`, con chiave `(msgctxt or "", msgid)`. Gestisce stringhe su più righe e voci `#~` obsolete, che vanno ignorate, e salta l'intestazione con `msgid ""`.
  - `our_translations(base_po: str | None, head_po: str) -> dict[tuple[str, str], str]`: le voci di `head` assenti nella base o con `msgstr` diverso, escluse quelle con `msgstr` vuoto.
  - `TRANSLATIONS_FILE = "docs/customizations/translations-it.toml"`, con formato `generated_from = "<base tag>"` e `[[translations]] msgctxt, msgid, msgstr`.
  - `check_translations(recorded: dict, head_po: str) -> list[Finding]`, codice `C7`, severità `ERROR`, una per voce registrata che manca o ha un `msgstr` diverso.
  - `PO_PATH = "lms/locale/it.po"`

- [ ] **Step 1: Scrivere i test che falliscono**:
  - `test_parses_multiline_msgid_and_msgstr`
  - `test_ignores_obsolete_entries`
  - `test_keeps_context_in_key`
  - `test_our_translations_are_new_or_changed_only`
  - `test_c7_flags_missing_and_changed`
  - `test_write_then_check_roundtrip`: `--write` seguito da `--check` sullo stesso albero restituisce codice 0.
- [ ] **Step 2: Eseguire i test**. Atteso: FAIL.
- [ ] **Step 3: Implementare.** La serializzazione in TOML va fatta a mano, perché la libreria standard non ha un writer TOML. Ogni stringa va scritta con escape di `\`, `"` e degli a capo.
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK. Poi `python3 scripts/customization_translations.py --write` sul branch e `--check`: atteso codice 0.
- [ ] **Step 5: Commit** `feat(customizations): record our Italian translations and flag lost ones`. Includere anche il file generato.

### Task 4: Base delle copie congelate

**Files:**
- Modify: `scripts/customizations/checks.py` (aggiunge `check_frozen_base`)
- Create: `scripts/frozen_diff.py`
- Test: `scripts/tests/test_frozen.py`

**Interfaces:**
- Consumes: `Entry.frozen_from` (Task 1) e `gitbase.Git` (Task 2).
- Produces:
  - `check_frozen_base(entries) -> list[Finding]`, codice `C9`, severità `WARNING`: una voce con un sito in `frontend/src/overrides/` senza `frozen_from`.
  - `frozen_diff.py --entry <id> --to <ref>`. Per le pagine lms stampa `git diff <frozen_from>:<originale> <to>:<originale>`, dove l'originale si ricava con `upstream_plan.frozen_originals`. Per i componenti frappe-ui (`frontend/src/overrides/frappe-ui/...`) usa il sottomodulo `frappe-ui`: `git -C frappe-ui diff v<frozen_from> v<to> -- <percorso componente>`. Se il tag non esiste nel sottomodulo, stampa il comando `git -C frappe-ui fetch --tags` ed esce con codice 2. Non lancia il fetch da solo.

- [ ] **Step 1: Scrivere i test che falliscono**:
  - `test_c9_warns_override_without_frozen_from`
  - `test_c9_ignores_entries_outside_overrides`
  - `test_frozen_diff_shows_upstream_change_of_original`: repository di prova con `FakeUpstream`, pagina copiata al tag `v1.0.0` e originale modificato in `v1.1.0`; il diff contiene la riga cambiata.
- [ ] **Step 2: Eseguire i test**. Atteso: FAIL.
- [ ] **Step 3: Implementare.**
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK, con avvisi C9 sulle 13 voci `override-file` di `overrides/`.
- [ ] **Step 5: Commit** `feat(customizations): record where frozen copies were taken from`

### Task 5: Controllo al commit

**Files:**
- Create: `scripts/commit_guard.py`
- Create: `.githooks/commit-msg` (shell, eseguibile: `exec python3 "$(git rev-parse --show-toplevel)/scripts/commit_guard.py" "$1"`)
- Test: `scripts/tests/test_commit_guard.py`

**Interfaces:**
- Consumes: `load_features(..., read=)` (Task 1), `gitbase` (Task 2), `check_sites`/`check_anchor_uniqueness`/`check_anchor_provenance`/`check_uncatalogued_markers` con `Reader` (Task 2), `load_inventory`.
- Produces:
  - `parse_trailers(message: str) -> list[str]`: valori di `Oslms-Feature` presi solo dal blocco finale. Si ottiene con `git interpret-trailers --parse`, in modo da avere la stessa semantica di git.
  - `@dataclass Problem(rule: str, message: str, blocking: bool)`
  - `OUR_PREFIXES = ("apps/os_lms/", "frontend/src/oslms/", "frontend/src/overrides/", "frontend/oslms-vite/")`
  - `EXEMPT_PREFIXES = ("docs/", "reports/", "scripts/", ".claude/", ".githooks/", ".github/", "lms/locale/", "lms/translations/")`
  - `EXEMPT_FILES = ("frontend/yarn.lock", "yarn.lock", "frontend/components.d.ts", "frontend/src/utils/frappe-ui-colors.json")`
  - `classify(paths: set[str], base_files: set[str]) -> dict[str, set[str]]` con le chiavi `"upstream"`, `"ours"` ed `"exempt"`. Un file assente dalla base e fuori da `EXEMPT_*` è classificato `"ours"`.
  - `is_version_bump_only(diff_text: str) -> bool`: vero se l'unica riga cambiata in `AppSidebar.vue` è quella con `id="versionApp"`.
  - `suggest_features(paths: set[str], features: dict, entries: list) -> list[str]`: prima le schede con `areas` corrispondenti, poi le `feature` delle voci che hanno siti nei file toccati.
  - `evaluate(message: str, commit_type: str, staged: set[str], read_staged: Reader, read_base: Reader, base_files: set[str], features: dict, entries: list, merge: MergeInfo | None) -> list[Problem]`
  - `@dataclass MergeInfo(is_upstream_release: bool, had_conflicts: bool)`, ricavata da `MERGE_HEAD`, dai tag di release che puntano a quel commit e dalle righe sotto `# Conflicts:` di `$GIT_DIR/MERGE_MSG`.
  - `main(argv) -> int`. Restituisce 1 se esiste un `Problem` bloccante, e stampa i problemi su stderr in italiano. I promemoria non bloccanti vengono stampati ma restituisce 0.

Regole di `evaluate`, dal §5.4 del design:
1. Se `classify` trova file `upstream` (escluso il solo bump di versione) o file `ours`, serve almeno una riga valida. Ogni id deve esistere nel catalogo **in stage**. Altrimenti il problema è bloccante, e il messaggio dice dove scrivere la riga (dopo `Version:`, prima di `Co-Authored-By:`) e quali funzionalità sono candidate.
2. Con `commit_type == "feat"`, almeno una scheda citata deve essere fra i file in stage; altrimenti il problema è bloccante. Per gli altri tipi, se una scheda citata non è in stage e il commit tocca le sue `areas`, si dà un promemoria non bloccante.
3. Si eseguono C1, C2, C3 e C6 sullo stage, limitati alle voci con siti nei file in stage e ai file in stage per C3. Ogni errore è bloccante. C5 si controlla solo sulle voci **aggiunte o modificate** in questo commit, ed è bloccante.
4. Con `none (<motivo>)`: il motivo dev'essere presente e il tipo non dev'essere `feat`/`fix`; altrimenti il problema è bloccante. Se `none` è l'unica riga, la regola 1 è soddisfatta.
5. Esenti: messaggio che inizia con `Revert "`; merge con `MergeInfo.is_upstream_release == False`; merge upstream senza conflitti. Un merge upstream con conflitti applica le regole 1 e 3.
6. Se la base non è calcolabile, il problema è bloccante e il messaggio indica `git fetch upstream --tags`.
7. Qualsiasi eccezione interna (per esempio una scheda malformata) diventa un problema bloccante con il messaggio dell'eccezione, mai un crash muto.

- [ ] **Step 1: Scrivere i test che falliscono.** Si usa un repository di prova costruito come in `test_upstream_plan.FakeUpstream`, con tag `v1.0.0`, un file upstream, un file nostro, una scheda e una voce. Ogni test prepara lo stage e chiama `main([msgfile])` con `cwd` nel repository di prova. I test:
  - `test_blocks_upstream_change_without_trailer` (il messaggio d'errore contiene `Oslms-Feature:` e il nome della funzionalità candidata)
  - `test_accepts_upstream_change_with_valid_trailer`
  - `test_blocks_unknown_feature_id`
  - `test_accepts_card_created_in_same_commit`
  - `test_blocks_feat_without_card_staged`
  - `test_reminds_fix_touching_areas_without_card` (codice di uscita 0, promemoria su stderr)
  - `test_docs_only_commit_needs_no_trailer`
  - `test_version_bump_alone_needs_no_trailer`
  - `test_trailer_in_body_middle_does_not_count` (Review Focus 1)
  - `test_rename_counts_both_paths` (Review Focus 2)
  - `test_upstream_merge_with_conflicts_needs_trailer` e `test_upstream_merge_without_conflicts_passes` (Review Focus 3)
  - `test_malformed_staged_card_blocks_with_message` (Review Focus 4)
  - `test_works_inside_a_worktree` (Review Focus 5)
  - `test_blocks_orphaned_anchor_in_stage` (il caso `Settings.vue`: si sposta il codice senza aggiornare la voce)
  - `test_none_requires_reason_and_rejects_fix`
  - `test_revert_is_exempt`
  - `test_missing_base_blocks_with_fetch_hint`
- [ ] **Step 2: Eseguire i test** con `python3 -m unittest scripts.tests.test_commit_guard -v`. Atteso: FAIL.
- [ ] **Step 3: Implementare** `commit_guard.py` e `.githooks/commit-msg` (`chmod +x`). Il tipo del commit si legge dalla prima riga con la regex `^(\w+)(\(.+\))?!?:`.
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK.
- [ ] **Step 5: Commit** `feat(customizations): block commits that leave a customization unattributed`. Il controllo non è ancora attivo su questo clone: si attiva nel Task 12.

### Task 6: Hook Stop e istruzioni a Claude

**Files:**
- Modify: `scripts/inventory_guard.py`
- Modify: `CLAUDE.md` (nuova sezione «Tracciamento delle personalizzazioni»)
- Test: `scripts/tests/test_guard.py`

**Interfaces:**
- Produces: `hooks_path_problem(repo_root: Path) -> str | None`. Restituisce un messaggio in italiano se `git config core.hooksPath` non vale `.githooks`, e `None` altrimenti. La guardia unisce questo messaggio a quello di C3 nella stessa decisione `block`, sempre una sola volta per sessione con il meccanismo della sentinella già esistente. La sentinella va spostata sotto `git rev-parse --git-dir` (Review Focus 5).

- [ ] **Step 1: Scrivere i test che falliscono**:
  - `test_blocks_once_when_hooks_path_not_set`: il messaggio contiene `git config core.hooksPath .githooks`.
  - `test_silent_when_hooks_path_set`
  - `test_sentinel_lives_in_git_dir`
- [ ] **Step 2: Eseguire i test**. Atteso: FAIL.
- [ ] **Step 3: Implementare** e scrivere la sezione di `CLAUDE.md`. Contenuto, in breve:
  - ogni commit che tocca codice upstream o nostro porta `Oslms-Feature: <id>` dopo `Version:`;
  - per `feat` si crea o aggiorna la scheda in `docs/customizations/features/`;
  - quando cambia il comportamento si aggiorna `behaviour` e si aggiunge una voce a `history`;
  - `none (<motivo>)` vale solo per modifiche senza effetto;
  - non usare mai `--no-verify`;
  - lo schema della scheda è in `docs/customizations/features/README.md`.
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK.
- [ ] **Step 5: Commit** `feat(customizations): remind to enable the commit guard and document the rule`

### Task 7: Mappa calcolata

**Files:**
- Create: `scripts/customizations/attribution.py`
- Create: `scripts/customization_map.py`
- Create: `docs/customizations/legacy-attribution.toml` (vuoto con intestazione: `schema_version = 1`)
- Test: `scripts/tests/test_attribution.py`

**Interfaces:**
- Consumes: `gitbase` (Task 2), `load_features` (Task 1), `parse_trailers` (Task 5), `NOT_CUSTOMIZATION`/`is_customization_candidate` da `upstream_plan.py`.
- Produces:
  - `@dataclass Hunk(file: str, base_start: int, base_len: int, head_start: int, head_len: int, added: list[str], removed: list[str])`
  - `diff_hunks(git: Git, base: str, ref: str, paths: list[str]) -> list[Hunk]` (`git diff -U0`)
  - `load_legacy(path: Path) -> dict[str, list[str]]`, con formato `[[files]] path = "...", features = ["..."]`.
  - `attribute(hunk: Hunk, *, git, base, ref, features, entries, legacy, release_tags) -> tuple[list[str], str]`. Restituisce gli id delle funzionalità e la fonte, cioè uno fra `"trailer"`, `"anchor"`, `"area"`, `"legacy"` e `"unattributed"`. L'ordine è quello del §5.5 del design:
    1. con `git blame --porcelain -L <head_start>,+<head_len> <ref> -- <file>` si leggono le righe aggiunte e le righe dei loro commit, merge compresi;
    2. per i blocchi di sole righe rimosse si usa `git log --format=%H -S<prima riga rimossa> <base>..<ref> --not <release tags> -- <file>`: il primo commit trovato fornisce le righe;
    3. poi le ancore delle voci contenute nel blocco;
    4. poi `areas`;
    5. poi `legacy`.
  - `build_map(repo_root, ref="HEAD") -> dict`, con chiavi `base`, `ref`, `features` (id → `{title, summary, files, hunks, commits}`), `unattributed` (lista di `{file, head_start, head_len}`) e `totals`.
  - `customization_map.py [--ref R] [--json] [--feature ID] [--unattributed]`, con codice di uscita 0. Il comando si limita a riportare.

- [ ] **Step 1: Scrivere i test che falliscono.** Si usa il repository di prova (fork da `v1.0.0` con quattro commit nostri):
  - `test_attributes_added_lines_by_trailer`
  - `test_attributes_removed_only_hunk_by_trailer_of_removing_commit`
  - `test_falls_back_to_anchor_for_commit_without_trailer`
  - `test_falls_back_to_area_then_legacy`
  - `test_reports_unattributed_hunk`
  - `test_reads_trailers_of_a_merge_commit_that_wrote_the_line`
  - `test_excludes_lock_and_translation_files`
  - `test_feature_filter`
- [ ] **Step 2: Eseguire i test**. Atteso: FAIL.
- [ ] **Step 3: Implementare.**
- [ ] **Step 4: Eseguire tutta la suite**. Atteso: OK. Poi `python3 scripts/customization_map.py --unattributed | tail -3` sul branch: stampa un totale, che prima della migrazione sarà alto. Annotare il numero nel rapporto del Task 10.
- [ ] **Step 5: Commit** `feat(customizations): compute the customization map from git history`

### Task 8: Skill `upstream-upgrade` e `upstream-check`

**Files:**
- Modify: `.claude/skills/upstream-upgrade/SKILL.md`
- Modify: `.claude/skills/upstream-check/SKILL.md`
- Modify: `docs/customizations/README.md` (sezione su catalogo, C5-C9, mappa, controllo al commit)

Contenuto, dal §5.6 e dal §5.7 del design:

- **upstream-upgrade**:
  - **Passo 2b** nuovo: `python3 scripts/customization_map.py --json`, presentazione per funzionalità e fermata **F9** sui blocchi non attribuiti, che vanno attribuiti con una voce in `legacy-attribution.toml` o con una scheda prima di partire.
  - **Passo 4**: togliere le note datate su `feature/esg` e `feature/esg-bias-tests`.
  - **Passo 5**: gli errori di partenza del rilevatore diventano fermata **F0**, da chiudere prima di creare il branch.
  - **F5** riscritta: candidati, confronto per regole di `behaviour`, domanda sempre posta per somiglianza alta o parziale, 4 opzioni e registrazione in `decisions` e nella `history` della scheda.
  - Nuova sezione «Adozione dell'upstream», con commit dedicati, cambio di stato della scheda, voci `accepted-drift` ed eventuale patch dati approvata.
  - **Passo 6.4**: righe `Oslms-Feature` nel merge se ci sono stati conflitti.
  - **F6**: usare `scripts/frozen_diff.py`.
  - **F1** traduzioni: usare `translations-it.toml` per sapere cosa riapplicare e rigenerarlo alla chiusura.
  - **Passo 7**: prove nell'app per le funzionalità adottate e rigenerazione delle traduzioni.
  - Regola 3 estesa alle schede: non si cancellano, si mettono a `retired` o `replaced-by-upstream`.
- **upstream-check**: togliere la Fase 0, usare come partenza lo `start_commit` dello stato quando esiste (altrimenti chiedere), mettere nella guardia dei branch anche `feature/oslms`, aggiungere al rapporto la sezione per funzionalità con `customization_map.py --feature`, e aggiungere C5-C9 alla tabella dei controlli.

- [ ] **Step 1: Modificare** i tre file.
- [ ] **Step 2: Verificare** con `grep -n "F9\|Passo 2b\|Oslms-Feature\|customization_map\|frozen_diff\|translations-it" .claude/skills/upstream-upgrade/SKILL.md`: atteso almeno un risultato per ciascun termine. Poi `grep -c "Fase 0" .claude/skills/upstream-check/SKILL.md`: atteso `0`.
- [ ] **Step 3: Rileggere F5** contro il §5.6 del design, punto per punto: i quattro punti e le quattro opzioni ci sono tutti, e non esiste nessun percorso in cui la skill adotta qualcosa senza domanda.
- [ ] **Step 4: Commit** `docs(upstream): compare upstream features with ours and always ask`

### Task 9: CI esistente

**Files:**
- Modify: `.github/workflows/customizations.yml`

- [ ] **Step 1: Modificare.** `actions/checkout@v4` con `fetch-depth: 0`. Uno step `git fetch --tags https://github.com/frappe/lms.git 'refs/tags/v*:refs/tags/v*'` con `continue-on-error: true`. Poi i test degli script, il rilevatore e `python3 scripts/customization_translations.py --check` (se il file generato esiste). Il rilevatore senza tag riporta C0 come avviso, come previsto dal Task 2.
- [ ] **Step 2: Verificare la sintassi** con `actionlint .github/workflows/customizations.yml` se è installato, altrimenti con una rilettura. Il controllo vero è la prima esecuzione su GitHub dopo il push, che fa l'utente: annotarlo nel worklog come verifica da fare.
- [ ] **Step 3: Commit** `ci(customizations): fetch upstream tags for the base-dependent checks`

### Task 10: Migrazione — elenco delle funzionalità (fermata per l'utente)

**Files:**
- Create: `docs/customizations/features/PROPOSTA-elenco.md` (temporaneo, rimosso nel Task 12)

- [ ] **Step 1: Mettere in ordine `feature/live-class-draft`.** Le modifiche non committate a `spa-grafts.toml` e agli altri file vanno committate su quel branch, dopo aver chiesto all'utente, oppure lasciate lì. La migrazione si fa su un branch nuovo `chore/feature-catalogue` creato da `feature/oslms` dopo che i task 1-9 vi sono stati uniti, oppure direttamente in continuazione sul branch dei task 1-9, se l'utente preferisce.
- [ ] **Step 2: Ricavare i candidati.** Raggruppare le 348 voci attive per area e regola (prefissi degli id, file, `visibility`). Aggiungere le funzionalità di `apps/os_lms` che non hanno voci, ricavandole dai moduli di `apps/os_lms/os_lms/os_lms/`, dagli spec in `docs/superpowers/specs/` e dalla memoria di progetto. Contare i file upstream che differiscono dalla base al netto delle esclusioni: è il numero di righe potenziali in `legacy-attribution.toml`.
- [ ] **Step 3: Scrivere la proposta.** Una tabella con `id`, titolo, sintesi di una riga, numero di voci, aree e moduli `os_lms`, più un elenco delle voci che non rientrano in nessuna funzionalità, con una proposta per ciascuna.
- [ ] **Step 4: FERMARSI e chiedere all'utente** l'approvazione dell'elenco: nomi, confini, unioni e divisioni. Non scrivere schede prima dell'ok. Registrare le correzioni.

### Task 11: Migrazione — schede a lotti

**Files:**
- Create: `docs/customizations/features/<id>.toml` (uno per funzionalità approvata)
- Modify: `docs/customizations/spa-grafts.toml` (campo `feature` su ogni voce del lotto)

Ripetere per ogni lotto di area, nell'ordine dell'elenco approvato:

- [ ] **Step 1: Scrivere le schede del lotto.** `behaviour` va ricavato da codice, test, commit, worklog e spec, e scritto come regole osservabili da fuori. `notes` riprende i file di memoria «da riapplicare dopo i merge» pertinenti; a ciascun file di memoria si aggiunge una riga che rimanda alla scheda. Ogni scheda ha `history` con almeno l'evento di creazione, presa dal primo commit della funzionalità.
- [ ] **Step 2: Collegare le voci** aggiungendo `feature = "<id>"`.
- [ ] **Step 3: Verificare** con `python3 scripts/check_customizations.py`: nessun errore di caricamento, e gli avvisi C8 calano esattamente del numero di voci del lotto.
- [ ] **Step 4: Mostrare il lotto all'utente** (titoli e `behaviour`) e applicare le correzioni.
- [ ] **Step 5: Commit** `docs(customizations): catalogue <area> features`

### Task 12: Migrazione — chiusura e attivazione

**Files:**
- Modify: `docs/customizations/spa-grafts.toml`, `docs/customizations/legacy-attribution.toml` (si aggiornano solo le voci, il codice dell'app non si tocca)
- Create: `docs/customizations/features/.strict`
- Delete: `docs/customizations/features/PROPOSTA-elenco.md`

- [ ] **Step 1: Correggere i 3 C1** di `settings-google-calendar-tab` e `settings-welcome-tab`. Il codice è stato spostato in `frontend/src/oslms/utils/settingsTabs.js` con il commit `206d5cd89`: aggiornare `file` e `anchor` dei siti in modo che puntino al codice nuovo e all'innesto `googleCalendarTab(`/`welcomeTab()` in `Settings.vue`, con ancore uniche.
- [ ] **Step 2: Correggere C6 e i 25 C5.** Per ognuno si sceglie un'ancora nuova presente solo nel nostro codice. Se l'upstream ha adottato la modifica, si mette `accepted-drift`, ma **prima si chiede all'utente**: è la regola 3 della skill.
- [ ] **Step 3: Impostare `frozen_from`** su tutte le voci segnalate da C9, ricavandolo dalla storia git del file copiato (versione upstream o frappe-ui al commit che ha creato la copia). Se non è ricostruibile, va chiesto all'utente.
- [ ] **Step 4: Scrivere `legacy-attribution.toml`.** Con `python3 scripts/customization_map.py --unattributed --json`, per ogni file con blocchi non attribuiti si aggiunge una voce `files` con le funzionalità che ci vivono. Ripetere finché `unattributed` è vuoto. Se restano casi in cui la funzionalità non è riconoscibile, si portano all'utente in un elenco: o li approva come residuo esplicito, o li attribuisce lui.
- [ ] **Step 5: Rigenerare** con `python3 scripts/customization_translations.py --write`.
- [ ] **Step 6: Attivare la modalità stretta.** Creare `docs/customizations/features/.strict` e lanciare `python3 scripts/check_customizations.py`: atteso codice di uscita 0, senza C8, C1, C2, C3 né C6 (C4 e C9 restano avvisi).
- [ ] **Step 7: Chiedere all'utente** l'ok per eseguire `git config core.hooksPath .githooks`, poi eseguirlo.
- [ ] **Step 8: Prova reale del controllo**, su un branch usa e getta che poi si cancella. Un commit con una modifica a `frontend/src/pages/Lesson.vue` senza riga dev'essere rifiutato, e il messaggio deve indicare le candidate. Con la riga dev'essere accettato. Spostare un'ancora senza aggiornare la voce dev'essere rifiutato. Fare `git reset --hard` del branch di prova e cancellarlo.
- [ ] **Step 9: Simulare F5** sui commit `v2.64.0..v2.65.0` con le schede migrate, seguendo a mano il procedimento della skill. Tra i candidati devono emergere almeno le funzionalità Docente e Valutatore (permessi), già note dal percorso v2.65. Annotare l'esito nel worklog.
- [ ] **Step 10: Suite completa** con `python3 -m unittest discover -s scripts/tests -t .` e `python3 scripts/check_customizations.py`. Atteso: OK e codice 0.
- [ ] **Step 11: Commit** `docs(customizations): finish the feature catalogue migration and enforce it`. Questo commit deve passare dal controllo appena attivato.

---

## Autorevisione (fatta)

- **Copertura del design.** §5.2 → Task 1, 11. §5.3/§5.4 → Task 5, 6. §5.5 → Task 7. §5.6 → Task 8. §5.7: C5/C6 → Task 2, traduzioni → Task 3, congelate → Task 4, `upstream-check` → Task 8. §5.8 → Task 10-12. §5.9 → test di ogni task più Task 12 step 8-9. §5.10 → Task 9. Hook Stop per `core.hooksPath` → Task 6.
- **Fuori piano, da fare a parte prima del prossimo aggiornamento:** la correzione di `pending_tags` per le linee v15/v16, che il design esclude.
