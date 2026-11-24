"""The drift checks.

Each check is a pure function taking the inventory entries plus a reader (or
the repository root) and returning findings. Nothing here executes application code: the whole
point of the detector is that it answers in seconds with Docker switched off.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from scripts.customizations.features import Feature
from scripts.customizations.model import Entry
from scripts.customizations.paths import FEATURES_DIR, OVERRIDES_DIR

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


Reader = Callable[[str], "str | None"]
"""Given a repository-relative path, return the file text, or None if absent."""


def disk_reader(repo_root: Path) -> Reader:
	"""A reader over the working tree."""
	root = Path(repo_root)

	def read(relative: str) -> str | None:
		path = root / relative
		return _read(path) if path.is_file() else None

	return read


def check_sites(entries: list[Entry], read: Reader) -> list[Finding]:
	"""C1: every anchor still occurs in its file. C2: every file still exists.

	C2 short-circuits C1: a missing file is one fact, not two.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		for site in entry.sites:
			text = read(site.file)
			if text is None:
				findings.append(
					Finding(entry.id, "C2", ERROR, "file non trovato", site.file, site.anchor)
				)
			elif site.anchor not in text:
				findings.append(
					Finding(entry.id, "C1", ERROR, "ancora non trovata nel file", site.file, site.anchor)
				)
	return findings


def check_anchor_provenance(entries: list[Entry], read: Reader, read_base: Reader) -> list[Finding]:
	"""C5: the anchor also occurs in the same file at the upstream base.

	Such an anchor cannot tell our code from upstream's, so a merge could wipe
	our change and the anchor would still match. Warning: the fix is choosing a
	better anchor, not repairing drift. A file absent in the base is ours alone.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		for site in entry.sites:
			base_text = read_base(site.file)
			if base_text is not None and site.anchor in base_text:
				findings.append(
					Finding(
						entry.id, "C5", WARNING, "ancora presente anche nel file della base upstream",
						site.file, site.anchor,
					)
				)
	return findings


def check_anchor_uniqueness(entries: list[Entry], read: Reader) -> list[Finding]:
	"""C6: the anchor occurs exactly once, so it points at one place."""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		for site in entry.sites:
			text = read(site.file)
			if text is not None and text.count(site.anchor) > 1:
				findings.append(
					Finding(
						entry.id, "C6", ERROR, "ancora presente più di una volta nel file",
						site.file, site.anchor,
					)
				)
	return findings


MARKER = "OSLMS-CUSTOM"
SCAN_ROOTS = ("frontend/src", "lms", "apps/os_lms", "cypress")
SCAN_SUFFIXES = (".vue", ".ts", ".js", ".py")
EXCLUDED_PARTS = ("node_modules", "__pycache__", "lms/public/frontend", "/.git/")


def is_watched_source(relative: str) -> bool:
	"""True for a repo-relative path the marker scan (C3) looks at."""
	return (
		relative.startswith(tuple(f"{root}/" for root in SCAN_ROOTS))
		and relative.endswith(SCAN_SUFFIXES)
		and not any(part in relative for part in EXCLUDED_PARTS)
	)


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


def _uncatalogued(entries: list[Entry], marked: list[str]) -> list[Finding]:
	catalogued = {site.file for entry in entries for site in entry.sites}
	return [
		Finding("-", "C3", ERROR, f"file con marcatore {MARKER} non censito", relative, None)
		for relative in marked
		if relative not in catalogued
	]


def check_uncatalogued_markers(entries: list[Entry], repo_root: Path) -> list[Finding]:
	"""C3: every file carrying the marker is referenced by some inventory entry.

	This is the inverse check, and the only one that can notice a customization
	nobody wrote down. Without it the inventory silently drifts out of date and
	the whole suite reports green over half the real surface.
	"""
	return _uncatalogued(
		entries, [relative for relative, path in _iter_source_files(repo_root) if MARKER in _read(path)]
	)


def check_uncatalogued_markers_in(entries: list[Entry], paths: set[str], read: Reader) -> list[Finding]:
	"""C3 limited to `paths`, read through `read` (the commit guard uses the index)."""
	marked = []
	for relative in sorted(paths):
		if not is_watched_source(relative):
			continue
		text = read(relative)
		if text is not None and MARKER in text:
			marked.append(relative)
	return _uncatalogued(entries, marked)


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


def check_feature_links(entries: list[Entry], features: dict[str, Feature], strict: bool) -> list[Finding]:
	"""C8: every entry points at a feature card that exists.

	A warning until the catalogue is migrated (the strict flag file does not
	exist yet), an error afterwards. Also, always an error: an active card with
	no `areas` and no entry linked to it, since it then points at no code at
	all (design §5.2: every active card has at least a site or an area).
	"""
	severity = ERROR if strict else WARNING
	findings: list[Finding] = []
	linked = {entry.feature for entry in entries if entry.feature}
	for feature in sorted(features.values(), key=lambda f: f.id):
		if feature.status == "active" and not feature.areas and feature.id not in linked:
			findings.append(
				Finding(
					feature.id, "C8", ERROR,
					"scheda active senza 'areas' e senza voci collegate: aggiungi le aree del suo codice "
					f"o collega una voce con feature = \"{feature.id}\"",
					f"{FEATURES_DIR}/{feature.source or feature.id + '.toml'}", None,
				)
			)
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		if not entry.feature:
			findings.append(Finding(entry.id, "C8", severity, "voce senza funzionalità collegata", None, None))
		elif entry.feature not in features:
			findings.append(
				Finding(entry.id, "C8", severity, f"funzionalità sconosciuta '{entry.feature}'", None, None)
			)
	return findings


def check_area_globs(features: dict[str, Feature], tracked: list[str]) -> list[Finding]:
	"""C10: every `areas` glob of an active card matches at least one tracked file.

	A glob that matches nothing usually has a typo, or points at code that was
	moved: the card then silently stops covering its files. Retired cards are
	skipped, their code is gone by definition. Warning: the fix is the glob.
	"""
	findings: list[Finding] = []
	for feature in sorted(features.values(), key=lambda f: f.id):
		if feature.status != "active":
			continue
		for pattern in feature.areas:
			if not any(path == pattern or fnmatch(path, pattern) for path in tracked):
				findings.append(
					Finding(
						feature.id, "C10", WARNING, "area della scheda che non corrisponde a nessun file tracciato",
						f"{FEATURES_DIR}/{feature.source or feature.id + '.toml'}", pattern,
					)
				)
	return findings


def check_frozen_base(entries: list[Entry]) -> list[Finding]:
	"""C9: an entry with a frozen copy under overrides/ records where it was copied from.

	Without `frozen_from` nobody can tell which upstream version the copy
	froze, so the upstream changes it has missed cannot be listed. Warning:
	the fix is writing the version down, not repairing drift.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift" or entry.frozen_from:
			continue
		for site in entry.sites:
			if site.file.startswith(OVERRIDES_DIR):
				findings.append(
					Finding(
						entry.id, "C9", WARNING, "copia congelata senza 'frozen_from' (versione upstream di partenza)",
						site.file, None,
					)
				)
				break
	return findings
