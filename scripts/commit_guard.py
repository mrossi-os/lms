#!/usr/bin/env python3
"""commit-msg guard: no customization lands without saying which feature it serves.

Run by `.githooks/commit-msg` with the path of the message file. A commit that
touches upstream files or our own app code must carry, in the final trailer
block, an `Oslms-Feature: <id>` line naming a feature card that exists in the
staged tree. The inventory is also re-checked on the staged tree, limited to
what the commit touches.

Almost every commit is made by Claude Code, so each refusal says the file, the
rule and the exact text to add. The guard never fails silently: an internal
error is itself a blocking problem (design §5.4).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MIN_PYTHON = (3, 11)  # tomllib
if sys.version_info < MIN_PYTHON:  # the imports below would die with a raw traceback
	found = ".".join(str(part) for part in sys.version_info[:3])
	print(
		f"commit_guard: Python {found} ({sys.executable}) è troppo vecchio: serve Python 3.11 o più recente. "
		"Il commit è rifiutato. Installa Python 3.11 o più recente e mettilo prima nel PATH di git, "
		"poi ripeti il commit.",
		file=sys.stderr,
	)
	sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import (  # noqa: E402
	ERROR,
	Finding,
	Reader,
	check_anchor_provenance,
	check_anchor_uniqueness,
	check_sites,
	check_uncatalogued_markers_in,
)
from scripts.customizations.features import Feature, load_features  # noqa: E402
from scripts.customizations.gitbase import Git, PlanError, find_base  # noqa: E402
from scripts.customizations.model import Entry, load_inventory  # noqa: E402
from scripts.customizations.paths import (  # noqa: E402,F401
	EXEMPT_BASENAMES,
	EXEMPT_FILES,
	EXEMPT_PREFIXES,
	FEATURES_DIR,
	INVENTORY_DIR,
	OUR_PREFIXES,
	is_exempt_path,
	is_our_path,
)
from scripts.customizations.stage import (  # noqa: E402
	MergeInfo,
	cached_reader,
	changed_entry_ids,
	read_merge_info,
	staged_paths,
)
from scripts.customizations.trailers import NONE_VALUE, TRAILER_KEY, parse_trailers  # noqa: E402,F401
from scripts.customizations.translations import PO_PATH, TRANSLATIONS_FILE  # noqa: E402

SIDEBAR = "frontend/src/components/Sidebar/AppSidebar.vue"
SCISSORS = "# ------------------------ >8 ------------------------"
COMMIT_TYPE = re.compile(r"^(\w+)(\(.+\))?!?:")

WHERE_TO_WRITE = (
	"Scrivi la riga nell'ultimo paragrafo del messaggio, quello delle righe finali: "
	"subito prima di 'Co-Authored-By:' (e dopo 'Version:' se sta in quel paragrafo). "
	"Più funzionalità: una riga per ciascuna."
)


@dataclass(frozen=True)
class Problem:
	"""One reason to refuse the commit (blocking) or to remind something (not blocking)."""

	rule: str
	message: str
	blocking: bool


def clean_message(text: str) -> str:
	"""Drop what git strips before storing the message: comments and the verbose diff."""
	kept = []
	for line in text.splitlines():
		if line == SCISSORS:
			break
		if not line.startswith("#"):
			kept.append(line)
	return "\n".join(kept).strip("\n") + "\n"


def commit_type(message: str) -> str:
	"""The Conventional Commits type of the subject line, or "" when there is none."""
	for line in message.splitlines():
		if line.strip():
			match = COMMIT_TYPE.match(line)
			return match.group(1) if match else ""
	return ""


def classify(paths: set[str], base_files: set[str]) -> dict[str, set[str]]:
	"""Split staged paths into upstream-owned, ours and exempt (docs, tooling, generated)."""
	groups: dict[str, set[str]] = {"upstream": set(), "ours": set(), "exempt": set()}
	for path in paths:
		if is_exempt_path(path):
			groups["exempt"].add(path)
		elif is_our_path(path, base_files):
			groups["ours"].add(path)
		else:
			groups["upstream"].add(path)
	return groups


def is_version_bump_only(diff_text: str) -> bool:
	"""True when every changed line of the diff is the `versionApp` label."""
	changed = [
		line
		for line in diff_text.splitlines()
		if line[:1] in "+-" and not line.startswith(("+++", "---"))
	]
	return bool(changed) and all('id="versionApp"' in line for line in changed)


def suggest_features(paths: set[str], features: dict[str, Feature], entries: list[Entry]) -> list[str]:
	"""Candidate feature ids: cards whose `areas` match, then features of touched entries."""
	found = [fid for fid in sorted(features) if any(features[fid].matches_path(p) for p in paths)]
	for entry in entries:
		if entry.feature and entry.feature not in found and any(s.file in paths for s in entry.sites):
			found.append(entry.feature)
	return found


def card_path(feature_id: str) -> str:
	return f"{FEATURES_DIR}/{feature_id}.toml"


def is_exempt_commit(message: str, merge: MergeInfo | None) -> bool:
	"""Reverts, merges of our own branches and clean upstream merges need nothing."""
	if message.startswith('Revert "'):
		return True
	return merge is not None and (not merge.is_upstream_release or not merge.had_conflicts)


def translation_reminder(staged: set[str]) -> list[Problem]:
	"""Not blocking: it.po changed but the registry of our translations was not regenerated."""
	if PO_PATH not in staged or TRANSLATIONS_FILE in staged:
		return []
	return [Problem("traduzioni", (
		f"Il commit cambia {PO_PATH} ma non {TRANSLATIONS_FILE}: se hai aggiunto o cambiato "
		"traduzioni nostre, esegui 'python3 scripts/customization_translations.py --write' "
		f"e aggiungi allo stage {TRANSLATIONS_FILE}, così restano registrate."
	), False)]


def _finding_problem(finding: Finding, entries_by_id: dict[str, Entry], base: str | None) -> Problem:
	entry = entries_by_id.get(finding.entry_id)
	where = f"{INVENTORY_DIR}/{entry.source}" if entry else INVENTORY_DIR
	anchor = f"'{finding.anchor}'"
	texts = {
		"C1": (
			f"{finding.file}: l'ancora {anchor} della voce '{finding.entry_id}' non è più nel file in stage. "
			f"Se hai spostato il codice, aggiorna 'file'/'anchor' della voce in {where}; "
			"se l'hai tolto per errore, rimettilo."
		),
		"C2": (
			f"{finding.file}: il file della voce '{finding.entry_id}' non esiste più nello stage "
			f"(cancellato o rinominato). Aggiorna 'file' della voce in {where}, "
			"o togli la voce se la personalizzazione non c'è più."
		),
		"C6": (
			f"{finding.file}: l'ancora {anchor} della voce '{finding.entry_id}' compare più di una volta. "
			f"Scegli in {where} un'ancora più lunga, presente una volta sola."
		),
		"C3": (
			f"{finding.file}: contiene il marcatore OSLMS-CUSTOM ma nessuna voce dell'inventario cita il file. "
			f"Aggiungi una voce in {INVENTORY_DIR}/spa-grafts.toml (file, anchor, feature)."
		),
		"C5": (
			f"{finding.file}: l'ancora {anchor} della voce '{finding.entry_id}' esiste anche nel file "
			f"upstream della base {base}, quindi non distingue il nostro codice. "
			f"Scegli in {where} un'ancora presente solo nel nostro codice."
		),
	}
	return Problem(f"3/{finding.check}", texts.get(finding.check, finding.message), True)


def _inventory_problems(
	staged: set[str],
	read_staged: Reader,
	read_base: Reader,
	base: str | None,
	entries: list[Entry],
	changed_entries: frozenset[str],
) -> list[Problem]:
	"""Rule 3: C1/C2/C6 and C3 on what the commit touches, C5 on added or changed entries."""
	touched = [e for e in entries if e.id in changed_entries or any(s.file in staged for s in e.sites)]
	findings = check_sites(touched, read_staged) + check_anchor_uniqueness(touched, read_staged)
	findings += check_uncatalogued_markers_in(entries, staged, read_staged)
	changed = [e for e in entries if e.id in changed_entries]
	findings += check_anchor_provenance(changed, read_staged, read_base)
	entries_by_id = {e.id: e for e in entries}
	return [_finding_problem(f, entries_by_id, base) for f in findings if f.check == "C5" or f.severity == ERROR]


def _attribution_problems(
	message: str,
	ctype: str,
	values: list[str],
	groups: dict[str, set[str]],
	staged: set[str],
	features: dict[str, Feature],
	entries: list[Entry],
	merge: MergeInfo | None,
) -> list[Problem]:
	"""Rules 1, 2 and 4."""
	problems: list[Problem] = []
	attributed = groups["upstream"] | groups["ours"]
	waivers = [v for v in values if NONE_VALUE.match(v)]
	ids = [v for v in values if not NONE_VALUE.match(v)]
	candidates = suggest_features(attributed or staged, features, entries)
	hint = (
		f"Funzionalità candidate in base ai file toccati: {', '.join(candidates)}."
		if candidates
		else f"Nessuna scheda copre questi file: creane una in {FEATURES_DIR}/<id>.toml e aggiungila allo stage."
	)

	for value in waivers:
		reason = NONE_VALUE.match(value).group(1)
		if not reason or not reason.strip():
			problems.append(Problem("4", (
				f"'Oslms-Feature: {value}' senza motivo. Scrivi 'Oslms-Feature: none (<motivo>)', "
				"per esempio 'Oslms-Feature: none (solo formattazione)'."
			), True))
		if ctype in ("feat", "fix"):
			problems.append(Problem("4", (
				f"'Oslms-Feature: none' non è ammessa per un commit '{ctype}': un {ctype} cambia il "
				f"comportamento di una funzionalità. Sostituiscila con 'Oslms-Feature: <id>'. {hint}"
			), True))

	for value in ids:
		if value not in features:
			problems.append(Problem("1", (
				f"'Oslms-Feature: {value}' non corrisponde a nessuna scheda nello stage "
				f"({card_path(value)} non esiste). Correggi l'id oppure crea la scheda e fai 'git add'. {hint}"
			), True))

	if attributed and not values:
		listing = "".join(
			f"\n  - {label}: {', '.join(sorted(groups[key]))}"
			for key, label in (("upstream", "file upstream"), ("ours", "codice nostro"))
			if groups[key]
		)
		misplaced = any(line.lower().startswith(f"{TRAILER_KEY}:") for line in message.splitlines())
		problems.append(Problem("1", (
			"Il commit tocca file che vanno attribuiti a una funzionalità ma manca la riga "
			f"'Oslms-Feature: <id>' nel blocco finale del messaggio.{listing}\n"
			f"{WHERE_TO_WRITE}\n{hint}\n"
			+ ("Una riga 'Oslms-Feature:' c'è ma non è nel blocco finale, quindi git non la legge come riga finale.\n" if misplaced else "")
			+ "Per modifiche senza effetto sul comportamento (non feat/fix): 'Oslms-Feature: none (<motivo>)'."
		), True))

	known = [fid for fid in ids if fid in features]
	if not attributed or merge is not None:
		return problems
	if ctype == "feat":
		if known and not any(card_path(fid) in staged for fid in known):
			cards = ", ".join(card_path(fid) for fid in known)
			problems.append(Problem("2", (
				"Commit 'feat': almeno una scheda citata deve essere nello stage, creata o aggiornata "
				f"in 'behaviour' e 'history'. Aggiorna e fai 'git add' di: {cards}."
			), True))
	else:
		for fid in known:
			if card_path(fid) not in staged and any(features[fid].matches_path(p) for p in attributed):
				problems.append(Problem("2", (
					f"Il commit tocca le aree di '{fid}' ma non la sua scheda: se il comportamento è "
					f"cambiato, aggiorna 'behaviour' (e 'history') in {card_path(fid)}."
				), False))
	return problems


def evaluate(
	message: str,
	commit_type: str,
	staged: set[str],
	read_staged: Reader,
	read_base: Reader,
	base_files: set[str] | None,
	features: dict[str, Feature],
	entries: list[Entry],
	merge: MergeInfo | None,
	*,
	base: str | None = None,
	sidebar_diff: str = "",
	changed_entries: frozenset[str] = frozenset(),
) -> list[Problem]:
	"""Every problem of the staged commit. `base_files` None means no computable base."""
	if is_exempt_commit(message, merge):
		return []
	exempt = {p for p in staged if is_exempt_path(p)}
	reminders = translation_reminder(staged)
	if base_files is None:
		if staged - exempt or changed_entries:
			return [Problem("6", (
				"Non trovo la base upstream: nessun tag di release (vX.Y.Z) è antenato di HEAD, quindi "
				"non so quali file sono upstream. Esegui 'git fetch upstream --tags' e ripeti il commit."
			), True)] + reminders
		base_files = set()
	groups = classify(staged, base_files)
	if SIDEBAR in groups["upstream"] and is_version_bump_only(sidebar_diff):
		groups["upstream"].discard(SIDEBAR)
		groups["exempt"].add(SIDEBAR)
	values = parse_trailers(message)
	problems = _attribution_problems(message, commit_type, values, groups, staged, features, entries, merge)
	problems += _inventory_problems(staged, read_staged, read_base, base, entries, changed_entries)
	return problems + reminders


def check_commit(message: str) -> list[Problem]:
	"""Gather the staged state from git and evaluate it."""
	root = Path(Git(Path.cwd()).run("rev-parse", "--show-toplevel").strip())
	# Card and inventory listing run `git ls-files` in the working directory.
	os.chdir(root)
	git = Git(root)
	merge = read_merge_info(git)
	if is_exempt_commit(message, merge):
		return []
	staged = staged_paths(git)
	try:
		base = merge.release if merge and merge.release else find_base(git, "HEAD")
	except PlanError:
		base = None
	base_files = set(git.lines("ls-tree", "-r", "--name-only", "-z", base)) if base else None
	read_staged = cached_reader(git, "")
	read_base = cached_reader(git, base) if base else (lambda relative: None)
	features = load_features(Path(FEATURES_DIR), read=read_staged)
	entries = load_inventory(Path(INVENTORY_DIR), read=read_staged)
	return evaluate(
		message,
		commit_type(message),
		staged,
		read_staged,
		read_base,
		base_files,
		features,
		entries,
		merge,
		base=base,
		sidebar_diff=git.run("diff", "--cached", "-U0", "--", SIDEBAR) if SIDEBAR in staged else "",
		changed_entries=changed_entry_ids(git, entries),
	)


def report(problems: list[Problem]) -> None:
	blocking = [p for p in problems if p.blocking]
	reminders = [p for p in problems if not p.blocking]
	if blocking:
		count = "1 problema bloccante" if len(blocking) == 1 else f"{len(blocking)} problemi bloccanti"
		print(f"commit_guard: commit rifiutato ({count}).", file=sys.stderr)
		for problem in blocking:
			print(f"\n[regola {problem.rule}] {problem.message}", file=sys.stderr)
	if reminders:
		print(("\n" if blocking else "") + "commit_guard: promemoria (non bloccanti):", file=sys.stderr)
		for problem in reminders:
			print(f"- {problem.message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
	args = sys.argv[1:] if argv is None else argv
	try:
		if len(args) != 1:
			raise ValueError("uso: commit_guard.py <file del messaggio di commit>")
		message = clean_message(Path(args[0]).read_text(encoding="utf-8", errors="replace"))
		problems = check_commit(message)
	except Exception as exc:  # rule 7: never a silent crash, never a silent pass
		problems = [Problem("7", (
			f"errore interno del controllo: {type(exc).__name__}: {exc}. "
			"Correggi la causa (per esempio una scheda o un inventario malformato nello stage) e ripeti il commit."
		), True)]
	report(problems)
	return 1 if any(p.blocking for p in problems) else 0


if __name__ == "__main__":
	sys.exit(main())
