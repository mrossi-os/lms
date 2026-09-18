# Sistema di verifica delle personalizzazioni — Piano di implementazione, Fase 0

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire l'inventario dichiarativo delle personalizzazioni, il rilevatore di scostamento che dopo un merge dice in pochi secondi quali innesti sono stati ripuliti, e la guardia che impedisce all'inventario di invecchiare — senza scrivere alcun test applicativo.

**Architecture:** Un inventario TOML in `docs/customizations/` è la fonte di verità unica. Un pacchetto Python di sola libreria standard in `scripts/customizations/` lo carica (`model.py`), esegue quattro controlli testuali (`checks.py`) e ne rende l'esito (`report.py`); `scripts/check_customizations.py` è la riga di comando. Una skill `/upstream-check` orchestra rilevatore, diff mirato ai soli file censiti e rapporto. Tutti i percorsi sono nuovi: nessun file dell'upstream viene toccato.

**Tech Stack:** Python 3.11+ con sola libreria standard (`tomllib`, `dataclasses`, `pathlib`, `argparse`, `unittest`), TOML per l'inventario, GitHub Actions per l'esecuzione in integrazione continua.

**Spec:** [docs/superpowers/specs/2026-09-18-upstream-regression-harness-design.md](../specs/2026-09-18-upstream-regression-harness-design.md)

## Global Constraints

- **Nessuna dipendenza esterna.** Il rilevatore deve girare su un interprete nudo: solo libreria standard. È vietato introdurre `pip install`, requirements o venv. Verificato il 2026-09-18: su questa macchina PyYAML e pytest **non** sono installati, `tomllib` sì perché è nella standard library dal Python 3.11.
- **Niente Frappe.** Nessun modulo di questa fase importa `frappe` né richiede un bench o un sito: deve funzionare con Docker spento.
- **Stile Python:** ruff, `line-length = 110`, **indentazione a tabulazione**, virgolette doppie, target `py310` (il codice però gira su 3.11+ per `tomllib`).
- **Lingua:** commenti, docstring, nomi di identificatori e messaggi di commit in **inglese**; i messaggi rivolti all'utente prodotti dal rilevatore in **italiano**, come il resto degli strumenti di questo progetto.
- **Commit:** Conventional Commits (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `deprecate`, `revert`), enforced da commitlint. Ogni messaggio termina con `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- **Percorsi:** ogni file creato sta in `scripts/`, `docs/customizations/`, `.github/workflows/customizations.yml` o `.claude/skills/` — tutti percorsi che l'upstream non tocca.
- **Regola inviolabile (spec §9.4):** non si modifica mai un test per farlo passare. Davanti a un test rosso si ripara il codice, oppure ci si ferma e si chiede.
- **Comandi di riferimento**, da eseguire sempre dalla root del repository:
  - test: `python3 -m unittest discover -s scripts/tests -t . -v`
  - rilevatore: `python3 scripts/check_customizations.py`

## Stato di verifica di questo piano

Il codice contenuto in questo piano **non è ipotetico**: è stato assemblato in una
cartella temporanea ed eseguito il 2026-09-18, prima che il piano fosse consegnato.
Esiti misurati:

- `python3 -m unittest discover -s scripts/tests -t . -v` → **40 test, tutti PASS**.
- Rilevatore eseguito contro il repository reale con inventario vuoto → riporta
  **esattamente i 12 file** che portano il marcatore `OSLMS-CUSTOM`, senza falsi
  positivi dai bundle generati sotto `lms/public/frontend/`.
- Tempo di esecuzione sul repository reale: **0,48 secondi**.
- Guardia dell'hook `Stop` provata **come la eseguirà l'ambiente**, con il payload su stdin, nei quattro casi: tace quando tutto è censito; emette `{"decision": "block"}` nominando il file quando un marcatore non è censito; **non** blocca una seconda volta nella stessa sessione; blocca di nuovo in una sessione diversa.

Due difetti sono stati trovati proprio così e corretti nel piano prima della consegna:
il comando documentato `python3 scripts/check_customizations.py` falliva con
`ModuleNotFoundError` perché eseguire il file direttamente mette `scripts/` nel path
di import invece della root (risolto con il bootstrap esplicito nel Task 4, e con il
test `test_runs_as_a_standalone_script_from_any_directory` che esegue lo script da
una cartella diversa); e `unittest discover` richiede che la cartella di partenza sia
importabile, quindi servono i tre `__init__.py` del Task 1.

## Perimetro di questa fase

Questa è la **Fase 0** delle cinque previste dallo spec §11. Chiude da sola il primo dei due sintomi riportati dall'utente («il file aggiornato mi ripulisce tutto») e non scrive alcun test applicativo. Le Fasi 1-4 avranno ciascuna il proprio piano, scritto dopo che la precedente è in funzione.

## Struttura dei file

| File | Responsabilità |
| --- | --- |
| `scripts/__init__.py` | marcatore di pacchetto: `unittest discover` richiede che la cartella di partenza sia importabile (verificato) |
| `scripts/customizations/__init__.py` | marcatore di pacchetto |
| `scripts/customizations/model.py` | `Site`, `Entry`, `InventoryError`, `load_inventory` — lettura e validazione dell'inventario. Non conosce il filesystem del repository, solo l'inventario |
| `scripts/customizations/checks.py` | `Finding` e i quattro controlli C1-C4. Ogni controllo è una funzione pura che prende voci e radice del repository e restituisce una lista di findings |
| `scripts/customizations/report.py` | `render_table`, `render_json`. Solo formattazione: nessun accesso al disco |
| `scripts/check_customizations.py` | riga di comando: argomenti, orchestrazione, codice di uscita |
| `scripts/tests/__init__.py` | marcatore di pacchetto |
| `scripts/tests/test_model.py` | test del caricamento e della validazione |
| `scripts/tests/test_checks.py` | test dei quattro controlli |
| `scripts/tests/test_report.py` | test della resa e della riga di comando |
| `docs/customizations/README.md` | come si legge e si aggiorna l'inventario |
| `docs/customizations/spa-grafts.toml` | le voci ricavate dai 49 marcatori `OSLMS-CUSTOM` |
| `.github/workflows/customizations.yml` | esecuzione di test e rilevatore a ogni pull request |
| `.claude/skills/upstream-check/SKILL.md` | il rituale post-merge, versione Fase 0 |
| `scripts/inventory_guard.py` | guardia dell'hook `Stop`: impedisce di chiudere un turno che ha lasciato una personalizzazione non censita |
| `scripts/tests/test_guard.py` | test della guardia |
| `.claude/settings.json` (modifica) | registrazione dell'hook, **unita** alla configurazione esistente |

La separazione `model` / `checks` / `report` / riga di comando serve a tenere ogni file sotto le duecento righe e a rendere ogni pezzo testabile senza gli altri: `model` si testa con un inventario in una cartella temporanea, `checks` con finti file sorgente, `report` con findings costruiti a mano.

---
### Task 1: Modello dell'inventario

**Files:**
- Create: `scripts/__init__.py` (vuoto)
- Create: `scripts/customizations/__init__.py` (vuoto)
- Create: `scripts/customizations/model.py`
- Create: `scripts/tests/__init__.py` (vuoto)
- Test: `scripts/tests/test_model.py`

**Interfaces:**
- Consumes: niente (primo task)
- Produces:
  - `Site(file: str, anchor: str, symbol: str | None, marker: str | None)` — dataclass congelata
  - `Entry(id, title, layer, confidence, intent, source, sites: tuple[Site, ...], visibility: dict | None, contract: dict | None, checks: dict, status: str | None)` — dataclass congelata
  - `InventoryError(Exception)`
  - `load_inventory(directory: Path) -> list[Entry]`
  - costanti `LAYERS`, `CONFIDENCES`

- [ ] **Step 1: Write the failing test**

Crea `scripts/tests/test_model.py`:

```python
"""Tests for inventory parsing and validation."""

import tempfile
import unittest
from pathlib import Path

from scripts.customizations.model import InventoryError, load_inventory

VALID_ENTRY = """
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = "Visibile a Moderator e Docente, mai a Studente."

  [[entries.sites]]
  file = "frontend/src/components/CourseCardOverlay.vue"
  anchor = "Boolean(user.data?.is_docente)"
  symbol = "isAdmin"

  [entries.checks]
  unit = "frontend/src/tests/oslms/courseCardAdminGate.test.ts"
"""

FLOW_ENTRY = """
[[entries]]
id = "student-enrollment"
title = "Uno studente si iscrive a un corso"
layer = "flow"
confidence = "high"
intent = "Percorso minimo che uno studente deve poter completare."
"""


def write_inventory(directory, **files):
	"""Write each keyword argument as <name>.toml inside `directory`."""
	for name, body in files.items():
		(Path(directory) / f"{name}.toml").write_text(body, encoding="utf-8")
	return Path(directory)


class LoadInventoryTest(unittest.TestCase):
	def test_parses_a_valid_entry(self):
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, grafts=VALID_ENTRY))
		self.assertEqual(len(entries), 1)
		entry = entries[0]
		self.assertEqual(entry.id, "course-card-admin-gate")
		self.assertEqual(entry.layer, "spa-graft")
		self.assertEqual(entry.source, "grafts.toml")
		self.assertEqual(len(entry.sites), 1)
		self.assertEqual(entry.sites[0].file, "frontend/src/components/CourseCardOverlay.vue")
		self.assertEqual(entry.sites[0].anchor, "Boolean(user.data?.is_docente)")
		self.assertEqual(entry.sites[0].symbol, "isAdmin")
		self.assertIsNone(entry.sites[0].marker)
		self.assertEqual(entry.checks["unit"], "frontend/src/tests/oslms/courseCardAdminGate.test.ts")
		self.assertIsNone(entry.status)

	def test_flow_entries_may_omit_sites(self):
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, flows=FLOW_ENTRY))
		self.assertEqual(entries[0].sites, ())

	def test_non_flow_entry_without_sites_is_rejected(self):
		broken = FLOW_ENTRY.replace('layer = "flow"', 'layer = "spa-graft"')
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, flows=broken))
		self.assertIn("student-enrollment", str(caught.exception))
		self.assertIn("sites", str(caught.exception))

	def test_missing_required_field_is_rejected(self):
		broken = VALID_ENTRY.replace('title = "Menu di gestione sulla card corso"\n', "")
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("title", str(caught.exception))
		self.assertIn("grafts.toml", str(caught.exception))

	def test_unknown_layer_is_rejected(self):
		broken = VALID_ENTRY.replace('layer = "spa-graft"', 'layer = "whatever"')
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("whatever", str(caught.exception))

	def test_site_without_anchor_is_rejected(self):
		broken = VALID_ENTRY.replace('  anchor = "Boolean(user.data?.is_docente)"\n', "")
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("anchor", str(caught.exception))

	def test_duplicate_id_across_files_is_rejected(self):
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, a=VALID_ENTRY, b=VALID_ENTRY))
		self.assertIn("course-card-admin-gate", str(caught.exception))

	def test_files_without_entries_are_ignored(self):
		actors = '[actors.gestore]\nemail = "e2e-gestore@oslms.test"\nroles = ["Gestore"]\n'
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, grafts=VALID_ENTRY, actors=actors))
		self.assertEqual(len(entries), 1)

	def test_invalid_toml_names_the_file(self):
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts="[[entries]\nid = 'x'"))
		self.assertIn("grafts.toml", str(caught.exception))


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
touch scripts/__init__.py scripts/tests/__init__.py
python3 -m unittest scripts.tests.test_model -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.customizations'`.

- [ ] **Step 3: Write minimal implementation**

Crea `scripts/customizations/__init__.py` vuoto e `scripts/customizations/model.py`:

```python
"""Parse and validate the customization inventory.

The inventory is the single source of truth for every customization this fork
applies on top of upstream Frappe Learning. It is TOML rather than YAML so that
the drift detector runs on a bare interpreter: tomllib ships with the standard
library since Python 3.11, PyYAML does not ship at all.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LAYERS = frozenset({"spa-graft", "override-file", "os-lms-api", "fixture", "flow"})
CONFIDENCES = frozenset({"high", "low"})
REQUIRED_FIELDS = ("id", "title", "layer", "confidence", "intent")


class InventoryError(Exception):
	"""The inventory is malformed; no check can run until it is fixed."""


@dataclass(frozen=True)
class Site:
	"""One place in the tree where a customization physically lives."""

	file: str
	anchor: str
	symbol: str | None = None
	marker: str | None = None


@dataclass(frozen=True)
class Entry:
	"""One customization: where it lives, what it must do, how it is verified."""

	id: str
	title: str
	layer: str
	confidence: str
	intent: str
	source: str
	sites: tuple[Site, ...] = ()
	visibility: dict | None = None
	contract: dict | None = None
	checks: dict = field(default_factory=dict)
	status: str | None = None


def _build_site(raw: dict, entry_id: str, source: str) -> Site:
	for key in ("file", "anchor"):
		if not raw.get(key):
			raise InventoryError(f"{source}: entry '{entry_id}' has a site without '{key}'")
	return Site(
		file=raw["file"],
		anchor=raw["anchor"],
		symbol=raw.get("symbol"),
		marker=raw.get("marker"),
	)


def _build_entry(raw: dict, source: str) -> Entry:
	for key in REQUIRED_FIELDS:
		if not raw.get(key):
			raise InventoryError(f"{source}: an entry is missing the required field '{key}'")
	entry_id = raw["id"]
	if raw["layer"] not in LAYERS:
		raise InventoryError(f"{source}: entry '{entry_id}' has unknown layer '{raw['layer']}'")
	if raw["confidence"] not in CONFIDENCES:
		raise InventoryError(f"{source}: entry '{entry_id}' has unknown confidence '{raw['confidence']}'")
	sites = tuple(_build_site(site, entry_id, source) for site in raw.get("sites", []))
	if not sites and raw["layer"] != "flow":
		raise InventoryError(
			f"{source}: entry '{entry_id}' declares no sites; only 'flow' entries may omit them"
		)
	return Entry(
		id=entry_id,
		title=raw["title"],
		layer=raw["layer"],
		confidence=raw["confidence"],
		intent=raw["intent"].strip(),
		source=source,
		sites=sites,
		visibility=raw.get("visibility"),
		contract=raw.get("contract"),
		checks=raw.get("checks", {}),
		status=raw.get("status"),
	)


def load_inventory(directory: Path) -> list[Entry]:
	"""Read every *.toml in `directory` and return the entries they declare.

	Files without an `entries` array (actors.toml, for instance) are read and
	ignored rather than rejected: they belong to the inventory but describe
	something other than customizations.
	"""
	entries: list[Entry] = []
	seen: dict[str, str] = {}
	for path in sorted(Path(directory).glob("*.toml")):
		try:
			raw = tomllib.loads(path.read_text(encoding="utf-8"))
		except tomllib.TOMLDecodeError as exc:
			raise InventoryError(f"{path.name}: invalid TOML ({exc})") from exc
		for raw_entry in raw.get("entries", []):
			entry = _build_entry(raw_entry, path.name)
			if entry.id in seen:
				raise InventoryError(
					f"{path.name}: duplicate entry id '{entry.id}', already declared in {seen[entry.id]}"
				)
			seen[entry.id] = path.name
			entries.append(entry)
	return entries
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest scripts.tests.test_model -v
```

Expected: PASS, 9 test.

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/customizations/ scripts/tests/
git commit -m "$(cat <<'MSG'
feat(customizations): add the inventory model and its loader

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---
### Task 2: Controlli C1 e C2 — ancora persa, file sparito

Sono i due controlli che rispondono alla domanda «l'upstream mi ha ripulito il file?». C2 ha precedenza su C1: se il file non esiste più, cercarvi l'ancora non ha senso e produrrebbe due segnalazioni per un fatto solo.

**Files:**
- Create: `scripts/customizations/checks.py`
- Test: `scripts/tests/test_checks.py`

**Interfaces:**
- Consumes: `Entry`, `Site` da `scripts.customizations.model`
- Produces:
  - `Finding(entry_id: str, check: str, severity: str, message: str, file: str | None, anchor: str | None)` — dataclass congelata
  - costanti `ERROR = "error"`, `WARNING = "warning"`
  - `check_sites(entries: list[Entry], repo_root: Path) -> list[Finding]`

- [ ] **Step 1: Write the failing test**

Crea `scripts/tests/test_checks.py`:

```python
"""Tests for the four drift checks."""

import tempfile
import unittest
from pathlib import Path

from scripts.customizations.checks import ERROR, check_sites
from scripts.customizations.model import Entry, Site


def entry(entry_id="gate", sites=(), status=None, checks=None, layer="spa-graft"):
	"""Build an Entry directly, bypassing the TOML layer."""
	return Entry(
		id=entry_id,
		title="t",
		layer=layer,
		confidence="high",
		intent="i",
		source="test.toml",
		sites=tuple(sites),
		checks=checks or {},
		status=status,
	)


def fake_repo(directory, **files):
	"""Create files under `directory`; keys are slash-separated relative paths."""
	for relative, body in files.items():
		path = Path(directory) / relative
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(body, encoding="utf-8")
	return Path(directory)


class CheckSitesTest(unittest.TestCase):
	def test_reports_nothing_when_the_anchor_is_present(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/Card.vue": "const isAdmin = is_docente || false\n"})
			findings = check_sites([entry(sites=[site])], root)
		self.assertEqual(findings, [])

	def test_reports_c1_when_the_anchor_is_gone(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/Card.vue": "const isAdmin = is_moderator\n"})
			findings = check_sites([entry(sites=[site])], root)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C1")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertEqual(findings[0].entry_id, "gate")
		self.assertEqual(findings[0].file, "src/Card.vue")
		self.assertEqual(findings[0].anchor, "is_docente")

	def test_reports_only_c2_when_the_file_is_gone(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site])], Path(tmp))
		self.assertEqual([f.check for f in findings], ["C2"])

	def test_skips_entries_marked_accepted_drift(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site], status="accepted-drift")], Path(tmp))
		self.assertEqual(findings, [])

	def test_checks_every_site_of_an_entry(self):
		sites = [Site(file="src/A.vue", anchor="x"), Site(file="src/B.vue", anchor="y")]
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/A.vue": "x", "src/B.vue": "nothing"})
			findings = check_sites([entry(sites=sites)], root)
		self.assertEqual([f.file for f in findings], ["src/B.vue"])


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest scripts.tests.test_checks -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.customizations.checks'`.

- [ ] **Step 3: Write minimal implementation**

Crea `scripts/customizations/checks.py`:

```python
"""The drift checks.

Each check is a pure function taking the inventory entries plus the repository
root and returning findings. Nothing here executes application code: the whole
point of the detector is that it answers in seconds with Docker switched off.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.customizations.model import Entry

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
	"""One thing that no longer matches what the inventory declares."""

	entry_id: str
	check: str
	severity: str
	message: str
	file: str | None = None
	anchor: str | None = None


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8", errors="replace")


def check_sites(entries: list[Entry], repo_root: Path) -> list[Finding]:
	"""C1: every anchor still occurs in its file. C2: every file still exists.

	C2 short-circuits C1: a missing file is one fact, not two.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		for site in entry.sites:
			path = Path(repo_root) / site.file
			if not path.is_file():
				findings.append(
					Finding(entry.id, "C2", ERROR, "file non trovato", site.file, site.anchor)
				)
				continue
			if site.anchor not in _read(path):
				findings.append(
					Finding(entry.id, "C1", ERROR, "ancora non trovata nel file", site.file, site.anchor)
				)
	return findings
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest scripts.tests.test_checks -v
```

Expected: PASS, 5 test.

- [ ] **Step 5: Commit**

```bash
git add scripts/customizations/checks.py scripts/tests/test_checks.py
git commit -m "$(cat <<'MSG'
feat(customizations): detect lost anchors and vanished files

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Controlli C3 e C4 — marcatori non censiti, voci senza test

C3 è il controllo **inverso**, ed è quello che impedisce all'inventario di invecchiare: segnala i file che portano il marcatore `OSLMS-CUSTOM` ma che nessuna voce menziona. C4 è un avviso, non un errore: in Fase 0 nessuna voce ha test collegati e la CI non deve essere rossa per questo.

**Files:**
- Modify: `scripts/customizations/checks.py` (aggiunta in coda)
- Modify: `scripts/tests/test_checks.py` (aggiunta in coda)

**Interfaces:**
- Consumes: `Finding`, `ERROR`, `WARNING` dal Task 2
- Produces:
  - `check_uncatalogued_markers(entries: list[Entry], repo_root: Path) -> list[Finding]`
  - `check_test_paths(entries: list[Entry], repo_root: Path) -> list[Finding]`
  - costanti `MARKER`, `SCAN_ROOTS`, `SCAN_SUFFIXES`, `EXCLUDED_PARTS`

- [ ] **Step 1: Write the failing test**

Aggiungi in coda a `scripts/tests/test_checks.py`, **prima** del blocco `if __name__`:

```python
class CheckUncataloguedMarkersTest(unittest.TestCase):
	def test_reports_a_marked_file_that_no_entry_mentions(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/Loose.vue": "// OSLMS-CUSTOM: nostro\n"})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C3")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertEqual(findings[0].file, "frontend/src/Loose.vue")

	def test_stays_silent_when_the_file_is_catalogued(self):
		site = Site(file="frontend/src/Loose.vue", anchor="OSLMS-CUSTOM")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/Loose.vue": "// OSLMS-CUSTOM: nostro\n"})
			findings = check_uncatalogued_markers([entry(sites=[site])], root)
		self.assertEqual(findings, [])

	def test_ignores_generated_bundles(self):
		marked = "// OSLMS-CUSTOM\n"
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"lms/public/frontend/assets/index-abc.js": marked})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(findings, [])

	def test_ignores_unwatched_suffixes(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/notes.md": "OSLMS-CUSTOM\n"})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(findings, [])


class CheckTestPathsTest(unittest.TestCase):
	def test_warns_when_an_entry_has_no_test_at_all(self):
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_test_paths([entry()], Path(tmp))
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C4")
		self.assertEqual(findings[0].severity, WARNING)

	def test_warns_when_a_declared_test_file_is_missing(self):
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_test_paths([entry(checks={"unit": "t/missing.test.ts"})], Path(tmp))
		self.assertEqual(len(findings), 1)
		self.assertIn("unit", findings[0].message)
		self.assertEqual(findings[0].file, "t/missing.test.ts")

	def test_stays_silent_when_the_declared_test_exists(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"t/present.test.ts": "it('x', () => {})\n"})
			findings = check_test_paths([entry(checks={"unit": "t/present.test.ts"})], root)
		self.assertEqual(findings, [])
```

E aggiorna la riga di import in testa al file:

```python
from scripts.customizations.checks import (
	ERROR,
	WARNING,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest scripts.tests.test_checks -v
```

Expected: FAIL con `ImportError: cannot import name 'check_uncatalogued_markers'`.

- [ ] **Step 3: Write minimal implementation**

Aggiungi in coda a `scripts/customizations/checks.py`:

```python
MARKER = "OSLMS-CUSTOM"
SCAN_ROOTS = ("frontend/src", "lms", "apps/os_lms", "cypress")
SCAN_SUFFIXES = (".vue", ".ts", ".js", ".py")
EXCLUDED_PARTS = ("node_modules", "__pycache__", "lms/public/frontend", "/.git/")


def _iter_source_files(repo_root: Path):
	"""Yield (relative path, absolute path) for every watched source file."""
	root = Path(repo_root)
	for scan_root in SCAN_ROOTS:
		base = root / scan_root
		if not base.is_dir():
			continue
		for path in sorted(base.rglob("*")):
			if path.suffix not in SCAN_SUFFIXES or not path.is_file():
				continue
			relative = path.relative_to(root).as_posix()
			if any(part in relative for part in EXCLUDED_PARTS):
				continue
			yield relative, path


def check_uncatalogued_markers(entries: list[Entry], repo_root: Path) -> list[Finding]:
	"""C3: every file carrying the marker is referenced by some inventory entry.

	This is the inverse check, and the only one that can notice a customization
	nobody wrote down. Without it the inventory silently drifts out of date and
	the whole suite reports green over half the real surface.
	"""
	catalogued = {site.file for entry in entries for site in entry.sites}
	findings: list[Finding] = []
	for relative, path in _iter_source_files(repo_root):
		if relative in catalogued:
			continue
		if MARKER in _read(path):
			findings.append(
				Finding("-", "C3", ERROR, f"file con marcatore {MARKER} non censito", relative, None)
			)
	return findings


def check_test_paths(entries: list[Entry], repo_root: Path) -> list[Finding]:
	"""C4: every declared test path exists, and every entry declares one.

	Warning rather than error on purpose: in phase 0 the inventory exists and
	no test has been written yet, and a red pipeline nobody can fix teaches
	people to ignore the pipeline.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		if not entry.checks:
			findings.append(Finding(entry.id, "C4", WARNING, "nessun test collegato", None, None))
			continue
		for kind, relative in sorted(entry.checks.items()):
			if not (Path(repo_root) / relative).is_file():
				findings.append(
					Finding(entry.id, "C4", WARNING, f"test '{kind}' non trovato", relative, None)
				)
	return findings
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest scripts.tests.test_checks -v
```

Expected: PASS, 12 test.

- [ ] **Step 5: Commit**

```bash
git add scripts/customizations/checks.py scripts/tests/test_checks.py
git commit -m "$(cat <<'MSG'
feat(customizations): flag uncatalogued markers and entries without tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---
### Task 4: Resa dell'esito e riga di comando

**Files:**
- Create: `scripts/customizations/report.py`
- Create: `scripts/check_customizations.py`
- Test: `scripts/tests/test_report.py`

**Interfaces:**
- Consumes: `Finding`, `ERROR`, `WARNING`, i tre controlli, `load_inventory`, `InventoryError`
- Produces:
  - `render_table(findings: list[Finding], entries_total: int) -> str`
  - `render_json(findings: list[Finding], entries_total: int, generated_at: str) -> str`
  - `main(argv: list[str] | None = None) -> int` in `scripts/check_customizations.py`

`generated_at` è un parametro e non una chiamata interna a `datetime.now()`: è l'unico modo per avere un test deterministico sull'uscita JSON.

- [ ] **Step 1: Write the failing test**

Crea `scripts/tests/test_report.py`:

```python
"""Tests for report rendering and for the command line entry point."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DETECTOR = REPO_ROOT / "scripts" / "check_customizations.py"

from scripts.check_customizations import main
from scripts.customizations.checks import ERROR, WARNING, Finding
from scripts.customizations.report import render_json, render_table

INVENTORY = """
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = "Visibile a Moderator e Docente."

  [[entries.sites]]
  file = "frontend/src/Card.vue"
  anchor = "is_docente"
"""


def build_repo(tmp, card_body):
	"""Lay out a miniature repository: inventory plus one watched source file."""
	root = Path(tmp)
	(root / "docs" / "customizations").mkdir(parents=True)
	(root / "docs" / "customizations" / "grafts.toml").write_text(INVENTORY, encoding="utf-8")
	(root / "frontend" / "src").mkdir(parents=True)
	(root / "frontend" / "src" / "Card.vue").write_text(card_body, encoding="utf-8")
	return root


def run_main(argv):
	"""Run the command line, swallowing its output, and return (exit code, output)."""
	buffer = io.StringIO()
	with contextlib.redirect_stdout(buffer):
		code = main(argv)
	return code, buffer.getvalue()


class RenderJsonTest(unittest.TestCase):
	def test_serialises_findings_with_the_documented_shape(self):
		findings = [Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x")]
		payload = json.loads(render_json(findings, entries_total=7, generated_at="2026-09-18T10:00:00"))
		self.assertEqual(payload["generated_at"], "2026-09-18T10:00:00")
		self.assertEqual(payload["entries_total"], 7)
		self.assertEqual(payload["findings"][0]["id"], "gate")
		self.assertEqual(payload["findings"][0]["check"], "C1")
		self.assertEqual(payload["findings"][0]["severity"], "error")
		self.assertEqual(payload["findings"][0]["file"], "a.vue")
		self.assertEqual(payload["findings"][0]["anchor"], "x")

	def test_serialises_an_empty_run(self):
		payload = json.loads(render_json([], entries_total=0, generated_at="2026-09-18T10:00:00"))
		self.assertEqual(payload["findings"], [])


class RenderTableTest(unittest.TestCase):
	def test_separates_errors_from_warnings(self):
		findings = [
			Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x"),
			Finding("gate", "C4", WARNING, "nessun test collegato", None, None),
		]
		text = render_table(findings, entries_total=1)
		self.assertIn("ERRORI (1)", text)
		self.assertIn("AVVISI (1)", text)
		self.assertIn("a.vue", text)
		self.assertIn("1 errori, 1 avvisi", text)

	def test_says_so_when_everything_is_intact(self):
		text = render_table([], entries_total=31)
		self.assertIn("31", text)
		self.assertIn("0 errori, 0 avvisi", text)


class MainTest(unittest.TestCase):
	def test_exits_zero_when_the_anchor_is_intact(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 0)
		self.assertIn("0 errori", output)

	def test_exits_one_when_the_anchor_is_gone(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_moderator\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 1)
		self.assertIn("C1", output)

	def test_warnings_alone_do_not_fail_the_run(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 0)
		self.assertIn("C4", output)

	def test_runs_as_a_standalone_script_from_any_directory(self):
		"""The documented command is `python3 scripts/check_customizations.py`.

		Running the file directly puts scripts/ on sys.path instead of the
		repository root, so without the bootstrap in the script this fails with
		ModuleNotFoundError. cwd is deliberately somewhere else.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			result = subprocess.run(
				[sys.executable, str(DETECTOR), "--repo-root", str(root)],
				capture_output=True,
				text=True,
				cwd=tmp,
			)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("Esito:", result.stdout)

	def test_exits_two_when_the_inventory_itself_is_broken(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			(root / "docs" / "customizations" / "grafts.toml").write_text("[[entries]\n", encoding="utf-8")
			code, _ = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 2)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest scripts.tests.test_report -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.check_customizations'`.

- [ ] **Step 3: Write minimal implementation**

Crea `scripts/customizations/report.py`:

```python
"""Render the detector outcome, for a human and for an agent."""

from __future__ import annotations

import json

from scripts.customizations.checks import ERROR, Finding


def render_json(findings: list[Finding], entries_total: int, generated_at: str) -> str:
	"""Serialise the run, which is what the /upstream-check skill consumes."""
	payload = {
		"generated_at": generated_at,
		"entries_total": entries_total,
		"findings": [
			{
				"id": finding.entry_id,
				"check": finding.check,
				"severity": finding.severity,
				"message": finding.message,
				"file": finding.file,
				"anchor": finding.anchor,
			}
			for finding in findings
		],
	}
	return json.dumps(payload, indent=2, ensure_ascii=False)


def _block(title: str, findings: list[Finding]) -> list[str]:
	lines = [f"  {title} ({len(findings)})"]
	for finding in findings:
		lines.append(f"  {finding.check}  {finding.entry_id:<32} {finding.message}")
		if finding.file:
			lines.append(f"        {finding.file}")
		if finding.anchor:
			lines.append(f"        ancora: {finding.anchor}")
	lines.append("")
	return lines


def render_table(findings: list[Finding], entries_total: int) -> str:
	"""Render the outcome as a terminal report."""
	errors = [f for f in findings if f.severity == ERROR]
	warnings = [f for f in findings if f.severity != ERROR]
	lines = [f"Inventario: {entries_total} voci", ""]
	if errors:
		lines += _block("ERRORI", errors)
	if warnings:
		lines += _block("AVVISI", warnings)
	lines.append(f"Esito: {len(errors)} errori, {len(warnings)} avvisi")
	return "\n".join(lines)
```

Crea `scripts/check_customizations.py`:

```python
#!/usr/bin/env python3
"""Check the repository against the customization inventory.

Runs the four textual drift checks and reports what no longer matches what the
inventory declares. Standard library only, no Frappe, no bench, no site: this
is meant to answer in seconds right after an upstream merge.

Exit codes: 0 intact (warnings allowed), 1 drift found, 2 inventory malformed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the repository root,
# so the absolute imports below would not resolve. Prepend the root ourselves and
# the script works from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import (  # noqa: E402
	ERROR,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
)
from scripts.customizations.model import InventoryError, load_inventory  # noqa: E402
from scripts.customizations.report import render_json, render_table  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = Path("docs/customizations")


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--repo-root",
		type=Path,
		default=DEFAULT_REPO_ROOT,
		help="repository root to check (default: the repository this script lives in)",
	)
	parser.add_argument(
		"--inventory",
		type=Path,
		default=None,
		help="inventory directory (default: <repo-root>/docs/customizations)",
	)
	parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	inventory_dir = args.inventory or (repo_root / DEFAULT_INVENTORY)

	try:
		entries = load_inventory(inventory_dir)
	except InventoryError as exc:
		print(f"Inventario non valido: {exc}", file=sys.stderr)
		return 2

	findings = (
		check_sites(entries, repo_root)
		+ check_uncatalogued_markers(entries, repo_root)
		+ check_test_paths(entries, repo_root)
	)

	if args.json:
		print(render_json(findings, len(entries), datetime.now().isoformat(timespec="seconds")))
	else:
		print(render_table(findings, len(entries)))

	return 1 if any(f.severity == ERROR for f in findings) else 0


if __name__ == "__main__":
	raise SystemExit(main())
```

- [ ] **Step 4: Run the whole suite to verify it passes**

```bash
python3 -m unittest discover -s scripts/tests -t . -v
```

Expected: PASS, 30 test (9 del Task 1, 12 dei Task 2-3, 9 di questo task).

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/check_customizations.py
git add scripts/customizations/report.py scripts/check_customizations.py scripts/tests/test_report.py
git commit -m "$(cat <<'MSG'
feat(customizations): add the drift detector command line

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---
### Task 5: Popolare l'inventario con i 49 marcatori reali

È il task che trasforma il rilevatore da programma funzionante a strumento utile. Non è codice: è lettura del repository e scrittura di voci. Va eseguito da un agente con accesso al codice, perché ogni voce richiede di capire **cosa fa** quella personalizzazione, non solo dove sta.

**Files:**
- Create: `docs/customizations/README.md`
- Create: `docs/customizations/spa-grafts.toml`

**Interfaces:**
- Consumes: lo schema definito nel Task 1 (`LAYERS`, `CONFIDENCES`, campi obbligatori) e i controlli dei Task 2-3
- Produces: l'inventario che tutte le fasi successive estendono

**Distribuzione misurata il 2026-09-18** — 49 marcatori su 12 file:

| File | Marcatori | `layer` |
| --- | ---: | --- |
| `frontend/src/overrides/pages/Courses/CourseOverview.vue` | 17 | `override-file` |
| `frontend/src/components/CourseCardOverlay.vue` | 15 | `spa-graft` |
| `frontend/src/components/ChapterRow.vue` | 5 | `spa-graft` |
| `frontend/src/types/api.ts` | 3 | `spa-graft` |
| `frontend/src/pages/Batches/BatchOverview.vue` | 2 | `spa-graft` |
| `frontend/src/types/lms/LMSCourse.ts` | 1 | `spa-graft` |
| `frontend/src/stores/mobileCta.js` | 1 | `override-file` |
| `frontend/src/pages/ProfileCertificates.vue` | 1 | `spa-graft` |
| `frontend/src/overrides/frappe-ui/src/components/TextEditor/extensions/toc-node/TocNodeView.vue` | 1 | `override-file` |
| `frontend/src/oslms/components/CourseHero.vue` | 1 | `override-file` |
| `frontend/src/oslms/components/AiFixedButtons.vue` | 1 | `override-file` |
| `frontend/src/components/VideoPreview.vue` | 1 | `spa-graft` |

Criterio per `layer`: `spa-graft` se il file ospite appartiene all'upstream (quindi esposto al merge), `override-file` se è un file nostro — tutto ciò che sta sotto `frontend/src/overrides/`, `frontend/src/oslms/`, più i file che abbiamo creato noi dentro cartelle upstream (`stores/mobileCta.js`).

- [ ] **Step 1: Elencare i marcatori con il loro contesto**

```bash
grep -rn -A 4 "OSLMS-CUSTOM" frontend/src lms apps/os_lms cypress \
  --include="*.vue" --include="*.ts" --include="*.js" --include="*.py" \
  | grep -v "public/frontend" > /tmp/markers.txt
wc -l /tmp/markers.txt
```

- [ ] **Step 2: Scrivere l'intestazione dell'inventario**

Crea `docs/customizations/spa-grafts.toml`:

```toml
# Inventario delle personalizzazioni marcate OSLMS-CUSTOM.
#
# Fonte di verità unica: da qui si genera la verifica dopo ogni merge upstream.
# Chi aggiunge una personalizzazione aggiunge anche la voce, nella stessa sessione.
# Schema e criteri: vedi README.md in questa cartella.

schema_version = 1
area = "spa-grafts"
```

- [ ] **Step 3: Scrivere una voce per ogni personalizzazione distinta**

**Una voce per personalizzazione, non per marcatore.** Più marcatori nello stesso file appartengono spesso alla stessa regola: `CourseCardOverlay.vue` ha 15 marcatori ma non 15 personalizzazioni indipendenti. Attesa realistica: 25-35 voci per 49 marcatori.

Per ogni voce:

1. **`anchor`** — scegli la stringa **più distintiva** che identifica l'innesto, non la riga del commento `OSLMS-CUSTOM` (l'upstream potrebbe conservare un commento e riscrivere il codice sotto). Preferisci l'espressione che *porta* la regola: `Boolean(user.data?.is_docente)`, `props.course.data?.is_valutatore`. Verifica che sia unica nel file con `grep -c`.
2. **`intent`** — scrivi **perché** la personalizzazione esiste, non cosa fa il codice. È il campo che permette di riapplicare la regola in un file che l'upstream ha riscritto. Il commento `OSLMS-CUSTOM` esistente è spesso già una buona base: molti spiegano la motivazione.
3. **`confidence`** — `high` solo se la motivazione è evidente dal codice o dal commento. `low` se stai deducendo: sarà una delle voci che il committente rivede.
4. **`visibility`** — compilalo solo se la personalizzazione è una regola di visibilità e i ruoli sono chiari dal codice. Lascia `selector` fuori: gli attributi `data-test` arrivano in Fase 2.
5. **`checks`** — ometti la tabella: in Fase 0 non esistono test, e C4 produrrà un avviso per ogni voce. È il comportamento atteso.

Modello di voce da copiare:

```toml
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = """
Il menu di gestione del corso è visibile a Moderator, Docente e all'istruttore del
corso. Mai a Studente né a Valutatore: il Valutatore accede in sola lettura e un
click su un'azione di gestione gli creerebbe un'iscrizione reale."""

  [[entries.sites]]
  file = "frontend/src/components/CourseCardOverlay.vue"
  anchor = "Boolean(user.data?.is_docente)"
  symbol = "isAdmin"

  [entries.visibility]
  subject = "menu di gestione del corso"
  allow = ["Moderator", "Docente", "course-instructor"]
  deny = ["Student", "Valutatore", "Guest"]
```

- [ ] **Step 4: Scrivere il README dell'inventario**

Crea `docs/customizations/README.md`, che deve contenere: a cosa serve l'inventario e perché è la fonte di verità unica; lo schema dei campi con quali sono obbligatori; il criterio per scegliere il `layer`; come si sceglie una buona `anchor`; la regola «una voce per personalizzazione, non per marcatore»; il comando del rilevatore; e la regola che chi aggiunge una personalizzazione aggiunge la voce nella stessa sessione. Rimanda allo spec per le motivazioni di progetto invece di ripeterle.

- [ ] **Step 5: Eseguire il rilevatore sul repository vero**

```bash
python3 scripts/check_customizations.py
```

Expected: `Esito: 0 errori, N avvisi`, dove tutti gli avvisi sono `C4 nessun test collegato`. **Zero errori è il criterio di completamento di questo task**: zero C1 e C2 (ogni ancora è corretta), zero C3 (nessun marcatore è rimasto fuori dall'inventario).

Se compare un C3, il file segnalato ha marcatori e nessuna voce lo menziona: aggiungi la voce. Se compare un C1, l'`anchor` che hai scritto non corrisponde al file: correggila, non correggere il codice.

- [ ] **Step 6: Verificare che il JSON sia consumabile**

```bash
python3 scripts/check_customizations.py --json | python3 -m json.tool > /dev/null && echo "JSON valido"
```

Expected: `JSON valido`.

- [ ] **Step 7: Commit**

```bash
git add docs/customizations/
git commit -m "$(cat <<'MSG'
docs(customizations): catalogue the 49 OSLMS-CUSTOM grafts

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Esecuzione in integrazione continua

Un file di workflow **nuovo**, non una modifica a quelli esistenti: `ci.yml`, `frontend-tests.yml` e `ui-tests.yml` appartengono all'upstream e modificarli creerebbe proprio il tipo di conflitto che questo sistema esiste per evitare.

**Files:**
- Create: `.github/workflows/customizations.yml`

**Interfaces:**
- Consumes: `python3 -m unittest discover -s scripts/tests -t .` e `python3 scripts/check_customizations.py` dai task precedenti
- Produces: niente che altri task consumino

- [ ] **Step 1: Write the workflow**

Crea `.github/workflows/customizations.yml`:

```yaml
name: Customizations

on:
  pull_request:
  push:
    branches: [develop, feature/oslms]

jobs:
  check:
    name: Inventory and drift
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v6
        with:
          python-version: '3.13'

      - name: Detector unit tests
        run: python3 -m unittest discover -s scripts/tests -t . -v

      - name: Customization drift
        run: python3 scripts/check_customizations.py
```

Nessuno step di installazione dipendenze: è la conferma operativa del vincolo «sola libreria standard». Se un giorno servisse un `pip install`, questo workflow è il posto dove il vincolo si romperebbe per primo, in modo visibile.

- [ ] **Step 2: Verify the commands locally, exactly as CI runs them**

```bash
python3 -m unittest discover -s scripts/tests -t . -v && python3 scripts/check_customizations.py
```

Expected: tutti i test PASS, poi `Esito: 0 errori, N avvisi`, e codice di uscita 0 (`echo $?` restituisce 0).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/customizations.yml
git commit -m "$(cat <<'MSG'
ci: run the customization drift detector on every pull request

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---
### Task 7: La skill `/upstream-check`

Il rituale post-merge, versione Fase 0: guardia sul branch, rilevatore, **diff mirato ai soli file censiti**, rapporto, voce nel worklog. La riparazione assistita arriva in Fase 1 e in questa fase la skill si ferma a proporre.

Il diff mirato ha bisogno dell'elenco dei file censiti, quindi il task comincia aggiungendo quell'opzione alla riga di comando.

**Files:**
- Modify: `scripts/check_customizations.py` (opzione `--list-files`)
- Modify: `scripts/tests/test_report.py` (aggiunta in coda)
- Create: `.claude/skills/upstream-check/SKILL.md`

**Interfaces:**
- Consumes: `main(argv)` dal Task 4, l'inventario dal Task 5
- Produces: `python3 scripts/check_customizations.py --list-files` — un percorso per riga, ordinati, senza duplicati

- [ ] **Step 1: Write the failing test**

Aggiungi in coda a `scripts/tests/test_report.py`, **prima** del blocco `if __name__`:

```python
class ListFilesTest(unittest.TestCase):
	def test_prints_one_catalogued_path_per_line(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			code, output = run_main(["--repo-root", str(root), "--list-files"])
		self.assertEqual(code, 0)
		self.assertEqual(output.split(), ["frontend/src/Card.vue"])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest scripts.tests.test_report -v
```

Expected: FAIL con `error: unrecognized arguments: --list-files` (SystemExit 2 sollevato da argparse).

- [ ] **Step 3: Write minimal implementation**

In `scripts/check_customizations.py`, aggiungi l'argomento dentro `build_parser`, subito prima della riga `return parser`:

```python
	parser.add_argument(
		"--list-files",
		action="store_true",
		help="print the catalogued file paths, one per line, and exit",
	)
```

e in `main`, subito dopo il blocco `try/except` che carica l'inventario, prima del calcolo di `findings`:

```python
	if args.list_files:
		for path in sorted({site.file for entry in entries for site in entry.sites}):
			print(path)
		return 0
```

- [ ] **Step 4: Run the whole suite to verify it passes**

```bash
python3 -m unittest discover -s scripts/tests -t . -v
```

Expected: PASS, 31 test.

- [ ] **Step 5: Write the skill**

Crea `.claude/skills/upstream-check/SKILL.md`:

````markdown
---
name: upstream-check
description: Usare dopo aver fatto il merge dell'upstream (frappe/lms) in un branch, per sapere quali personalizzazioni sono state ripulite o alterate. Produce un rapporto; non ripara.
---

# upstream-check — verifica dopo un merge upstream

Questa skill risponde a una domanda sola: **il merge che ho appena fatto ha rotto o ripulito le mie personalizzazioni?**

Fonte di verità: `docs/customizations/*.toml`. Progetto e motivazioni: `docs/superpowers/specs/2026-09-18-upstream-regression-harness-design.md`.

## Regola inviolabile

**Non modificare mai un test per farlo passare.** Davanti a un test rosso hai due mosse consentite:

- **(a)** riparare il **codice**, perché la regola dichiarata nell'inventario è ancora valida;
- **(b)** **fermarti e chiedere all'utente** se la regola è cambiata.

Se la regola è cambiata si aggiorna **prima l'inventario** e poi il test si riscrive da lì. Un test è un output, non un input. Vale anche per l'inventario: non cancellare una voce per far tornare verde il rilevatore.

## Passo 0 — Guardia sul branch

```bash
git branch --show-current
```

Se sei su `develop`, `master` o `main`, **fermati** e dillo all'utente: questa skill si usa su un branch di merge. Non proseguire.

## Passo 1 — Rilevatore di scostamento

```bash
python3 scripts/check_customizations.py --json
```

Leggi il JSON. Significato dei controlli:

| Controllo | Significato | Gravità |
| --- | --- | --- |
| `C1` | l'ancora non c'è più nel file: **la riga è stata ripulita dal merge** | errore |
| `C2` | il file non esiste più: l'upstream lo ha rinominato o rimosso | errore |
| `C3` | un file ha il marcatore `OSLMS-CUSTOM` ma nessuna voce lo censisce | errore |
| `C4` | una voce non ha test collegati, o il test dichiarato non esiste | avviso |

In Fase 0 gli avvisi `C4` sono attesi su tutte le voci: i test arrivano in Fase 1. Non segnalarli come problema.

## Passo 2 — Diff mirato

È il passo di maggior valore: riduce la superficie da controllare dai file del merge ai soli file censiti.

```bash
python3 scripts/check_customizations.py --list-files > /tmp/oslms-watched.txt
git diff HEAD^1..HEAD -- $(cat /tmp/oslms-watched.txt | tr '\n' ' ')
```

`HEAD^1` è il primo genitore del commit di merge, cioè lo stato del branch **prima** di ricevere l'upstream. Se il merge non è l'ultimo commit, chiedi all'utente il riferimento da cui partire e usalo al posto di `HEAD^1`.

Leggi il diff **per intero**. Per ogni voce dell'inventario il cui file compare nel diff, stabilisci quale dei tre casi si applica:

- **intatta** — il file è cambiato ma non nella parte che porta la regola;
- **a rischio** — il file è stato riscritto attorno alla regola: l'ancora c'è ancora ma il contesto è diverso, e la regola potrebbe non applicarsi più come prima;
- **persa** — l'ancora non c'è più (te lo ha già detto il Passo 1, qui capisci *come* è successo).

Un `C1` senza corrispondenza nel diff è un caso da segnalare a parte: significa che l'ancora è sparita **fuori** dal merge, quindi per mano nostra.

## Passo 3 — Rapporto

Scrivi `docs/upstream-checks/AAAA-MM-GG-<versione-upstream>.md` con:

1. **Intestazione** — data, branch, riferimenti dei due lati del merge, versione upstream.
2. **Esito in una riga** — quante voci intatte, a rischio, perse; quanti marcatori non censiti.
3. **Una sezione per ogni voce non intatta** — id, titolo, file, cosa ha fatto il merge, l'`intent` dichiarato, e la riapplicazione **proposta** (il codice, non applicato).
4. **Voci a bassa confidenza** — l'elenco delle voci `confidence = "low"` toccate dal merge, che meritano uno sguardo del committente perché la regola dichiarata potrebbe non essere quella vera.
5. **Marcatori non censiti** — i `C3`, con la voce di inventario proposta per ciascuno.

## Passo 4 — Worklog

Registra l'attività in `docs/WORKLOG.md` secondo le convenzioni del file: blocco «In sintesi» con i campi obbligatori, poi i punti 1-4 e 6. Il worklog non si committa salvo richiesta esplicita.

## Cosa questa skill NON fa (in Fase 0)

- Non applica riparazioni: le **propone** nel rapporto. La riparazione assistita in commit separati arriva in Fase 1.
- Non esegue test applicativi: non esistono ancora. Arrivano in Fase 1.
- Non tocca `frontend/src/overrides/`: quelle pagine sono congelate per scelta e si riconciliano a parte.
````

- [ ] **Step 6: Dry run sui passi eseguibili**

```bash
git branch --show-current
python3 scripts/check_customizations.py --json | head -20
python3 scripts/check_customizations.py --list-files
```

Expected: il branch corrente non è `develop`/`master`; il JSON è ben formato e contiene `entries_total` maggiore di zero; `--list-files` elenca i file censiti al Task 5, uno per riga.

- [ ] **Step 7: Commit**

```bash
git add scripts/check_customizations.py scripts/tests/test_report.py .claude/skills/upstream-check/
git commit -m "$(cat <<'MSG'
feat(customizations): add the upstream-check skill and the watched file listing

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

---

### Task 8: La guardia dell'inventario — hook `Stop`

Rende l'aggiunta all'inventario **eseguita dall'ambiente** e non affidata alla memoria del modello. A fine turno il controllo C3 gira; se trova un marcatore `OSLMS-CUSTOM` in un file che nessuna voce censisce, l'agente viene rimandato a lavorare con l'istruzione di aggiungere la voce.

Perché l'evento `Stop` e non `PostToolUse`: mentre una personalizzazione viene scritta, il marcatore esiste già e la voce ancora no, quindi un controllo dopo ogni modifica fallirebbe a metà lavoro su un problema che non è ancora tale. `Stop` scatta a turno concluso.

Perché il blocco è una volta per sessione: un hook `Stop` che blocca può entrare in ciclo se l'agente non riesce a risolvere. La guardia ricorda il `session_id` dell'ultimo blocco e non blocca due volte nella stessa sessione.

**Files:**
- Create: `scripts/inventory_guard.py`
- Test: `scripts/tests/test_guard.py`
- Modify: `.claude/settings.json` (merge, non sostituire)

**Interfaces:**
- Consumes: `load_inventory` (Task 1), `check_uncatalogued_markers` (Task 3), `Finding` (Task 2)
- Produces: `build_decision(findings: list[Finding]) -> dict | None` e `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Crea `scripts/tests/test_guard.py`:

```python
"""Tests for the Stop-hook inventory guard."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.customizations.checks import ERROR, WARNING, Finding
from scripts.inventory_guard import build_decision, main


def marker_finding(file="frontend/src/Loose.vue"):
	return Finding("-", "C3", ERROR, "file con marcatore OSLMS-CUSTOM non censito", file, None)


class BuildDecisionTest(unittest.TestCase):
	def test_returns_none_when_everything_is_catalogued(self):
		self.assertIsNone(build_decision([]))

	def test_ignores_findings_that_are_not_c3(self):
		other = Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x")
		warning = Finding("gate", "C4", WARNING, "nessun test collegato", None, None)
		self.assertIsNone(build_decision([other, warning]))

	def test_blocks_and_names_every_uncatalogued_file(self):
		decision = build_decision([marker_finding("a.vue"), marker_finding("b.vue")])
		self.assertEqual(decision["decision"], "block")
		self.assertIn("a.vue", decision["reason"])
		self.assertIn("b.vue", decision["reason"])
		self.assertIn("spa-grafts.toml", decision["reason"])

	def test_names_each_file_once(self):
		decision = build_decision([marker_finding("a.vue"), marker_finding("a.vue")])
		self.assertEqual(decision["reason"].count("a.vue"), 1)


def guard_repo(tmp, marked):
	"""A repository with an empty inventory and optionally one marked file."""
	root = Path(tmp)
	(root / "docs" / "customizations").mkdir(parents=True)
	(root / ".git").mkdir()
	(root / "frontend" / "src").mkdir(parents=True)
	body = "// OSLMS-CUSTOM: nostro\n" if marked else "const a = 1\n"
	(root / "frontend" / "src" / "Loose.vue").write_text(body, encoding="utf-8")
	return root


def run_guard(root, session_id):
	"""Run the guard the way the hook does and return its stdout."""
	import contextlib
	import io

	payload = json.dumps({"session_id": session_id})
	buffer = io.StringIO()
	with contextlib.redirect_stdout(buffer):
		code = main(["--repo-root", str(root)], stdin_text=payload)
	return code, buffer.getvalue().strip()


class MainTest(unittest.TestCase):
	def test_stays_silent_when_nothing_is_uncatalogued(self):
		with tempfile.TemporaryDirectory() as tmp:
			code, output = run_guard(guard_repo(tmp, marked=False), "s1")
		self.assertEqual(code, 0)
		self.assertEqual(output, "")

	def test_emits_a_block_decision_for_an_uncatalogued_marker(self):
		with tempfile.TemporaryDirectory() as tmp:
			code, output = run_guard(guard_repo(tmp, marked=True), "s1")
		self.assertEqual(code, 0)
		payload = json.loads(output)
		self.assertEqual(payload["decision"], "block")
		self.assertIn("Loose.vue", payload["reason"])

	def test_blocks_only_once_per_session(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			first_code, first = run_guard(root, "s1")
			second_code, second = run_guard(root, "s1")
		self.assertEqual((first_code, second_code), (0, 0))
		self.assertNotEqual(first, "")
		self.assertEqual(second, "")

	def test_blocks_again_in_a_new_session(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			run_guard(root, "s1")
			_, second = run_guard(root, "s2")
		self.assertNotEqual(second, "")

	def test_never_blocks_when_the_inventory_is_broken(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			(root / "docs" / "customizations" / "x.toml").write_text("[[entries]\n", encoding="utf-8")
			code, output = run_guard(root, "s1")
		self.assertEqual(code, 0)
		self.assertEqual(output, "")


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest scripts.tests.test_guard -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.inventory_guard'`.

- [ ] **Step 3: Write minimal implementation**

Crea `scripts/inventory_guard.py`:

```python
#!/usr/bin/env python3
"""Stop-hook guard: refuse to end a turn that left a customization uncatalogued.

Runs check C3 only. An uncatalogued marker means someone wrote a customization
and did not write it down, which is how an inventory silently stops covering
what it claims to cover.

The guard blocks at most once per session: a Stop hook that keeps blocking can
loop when the agent cannot resolve what it is asked to resolve. It also stays
silent on any internal error — a guard that breaks the workflow because it
itself is broken is worse than no guard.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import Finding, check_uncatalogued_markers  # noqa: E402
from scripts.customizations.model import load_inventory  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
SENTINEL = Path(".git") / "oslms-inventory-guard"


def build_decision(findings: list[Finding]) -> dict | None:
	"""Return the Stop-hook payload when uncatalogued markers exist, else None."""
	files = sorted({f.file for f in findings if f.check == "C3" and f.file})
	if not files:
		return None
	return {
		"decision": "block",
		"reason": (
			"Marcatori OSLMS-CUSTOM non censiti in: "
			+ ", ".join(files)
			+ ". Aggiungi una voce a docs/customizations/spa-grafts.toml con file, "
			"anchor e intent prima di chiudere il turno. Se la personalizzazione non "
			"va censita, togli il marcatore."
		),
	}


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	args = parser.parse_args(argv)
	repo_root = args.repo_root.resolve()

	try:
		raw = stdin_text if stdin_text is not None else sys.stdin.read()
		session_id = json.loads(raw or "{}").get("session_id", "")

		entries = load_inventory(repo_root / "docs" / "customizations")
		decision = build_decision(check_uncatalogued_markers(entries, repo_root))
		if decision is None:
			return 0

		sentinel = repo_root / SENTINEL
		if sentinel.is_file() and sentinel.read_text(encoding="utf-8").strip() == session_id:
			return 0
		sentinel.write_text(session_id, encoding="utf-8")

		print(json.dumps(decision, ensure_ascii=False))
	except Exception:
		return 0
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
```

- [ ] **Step 4: Run the whole suite to verify it passes**

```bash
python3 -m unittest discover -s scripts/tests -t . -v
```

Expected: PASS, 40 test (31 dei task precedenti, 9 di questo).

- [ ] **Step 5: Pipe-test the hook command exactly as the hook will run it**

```bash
echo '{"session_id":"probe"}' | python3 scripts/inventory_guard.py
echo "exit: $?"
```

Expected: nessuna uscita e `exit: 0`, perché dopo il Task 5 l'inventario copre tutti i marcatori. Per provare il percorso di blocco, introduci temporaneamente un marcatore non censito e ripeti:

```bash
echo '// OSLMS-CUSTOM: prova' > frontend/src/GuardProbe.vue
echo '{"session_id":"probe"}' | python3 scripts/inventory_guard.py
rm frontend/src/GuardProbe.vue .git/oslms-inventory-guard
```

Expected: un JSON con `"decision": "block"` che nomina `frontend/src/GuardProbe.vue`. **Ricorda la pulizia**: il file di prova e il sentinella vanno rimossi.

- [ ] **Step 6: Merge the hook into the project settings**

`.claude/settings.json` **esiste già** e contiene `enabledPlugins`. Va **unito**, non sostituito. Risultato atteso:

```json
{
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "code-review@claude-plugins-official": true
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/inventory_guard.py",
            "timeout": 15,
            "statusMessage": "Controllo inventario personalizzazioni"
          }
        ]
      }
    ]
  }
}
```

Va in `.claude/settings.json` (progetto, committato) e non in `settings.local.json`, perché è una convenzione del progetto che deve valere per chiunque ci lavori, non una preferenza personale.

- [ ] **Step 7: Validate the settings syntax and schema**

```bash
jq -e '.hooks.Stop[] | .hooks[] | select(.type == "command") | .command' .claude/settings.json
jq -e '.enabledPlugins' .claude/settings.json
```

Expected: il primo stampa `"python3 scripts/inventory_guard.py"`, il secondo stampa l'oggetto dei plugin — cioè l'unione è avvenuta e non ha cancellato la configurazione esistente. Un `settings.json` malformato disattiva **silenziosamente tutte** le impostazioni di quel file, quindi questo controllo non è facoltativo.

- [ ] **Step 8: Commit**

```bash
git add scripts/inventory_guard.py scripts/tests/test_guard.py .claude/settings.json
git commit -m "$(cat <<'MSG'
feat(customizations): guard turn end against uncatalogued markers

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

**Nota per chi esegue:** l'hook entra in vigore quando Claude Code ricarica la configurazione. Se dopo il commit non scatta, l'utente deve aprire `/hooks` una volta o riavviare la sessione — non è una cosa che l'agente possa fare da solo.

## Criterio di completamento della Fase 0

La fase è finita quando tutte e tre queste condizioni valgono insieme:

1. `python3 -m unittest discover -s scripts/tests -t . -v` → 40 test, tutti PASS.
2. `python3 scripts/check_customizations.py` → `0 errori`, e gli unici avvisi sono `C4 nessun test collegato`.
3. La skill `/upstream-check` esegue i passi 0-2 sul branch corrente e produce un diff mirato non vuoto quando il branch contiene un merge.
4. `jq -e '.hooks.Stop[] | .hooks[] | .command' .claude/settings.json` stampa il comando della guardia, e `jq -e '.enabledPlugins' .claude/settings.json` continua a stampare i plugin — l'hook è registrato e l'unione non ha cancellato nulla.

## Cosa resta fuori, e dove va

| Elemento | Fase | Perché non ora |
| --- | --- | --- |
| Test backend `ruolo → flag` | 1 | Richiede un bench e utenti seedati; la Fase 0 deve restare eseguibile a Docker spento |
| Test Vitest `flag → DOM` | 1 | Serve prima l'inventario delle regole di visibilità, che i marcatori non coprono |
| Riparazione assistita in commit separati | 1 | Ha senso solo quando esiste un test che conferma che la riparazione ha funzionato |
| Attributi `data-test` | 2 | Sono selettori per i test E2E, che non esistono ancora |
| Seeding degli attori e smoke E2E | 2 | Il pezzo infrastrutturale più grosso, con le tre protezioni dello spec §8.3 |
| Flussi funzionali E2E | 3 | Dipendono dal seeding |
| `roles.toml`, `api-overrides.toml`, `flows.toml` | 1-3 | Ogni file nasce con la fase che lo usa |

Ogni fase successiva avrà il proprio piano, scritto quando la precedente è in funzione: il piano della Fase 1 deve poter tenere conto di cosa la Fase 0 ha effettivamente prodotto, in particolare di quante voci sono risultate a bassa confidenza.
