"""Parse and validate the customization inventory.

The inventory is the single source of truth for every customization this fork
applies on top of upstream Frappe Learning. It is TOML rather than YAML so that
the drift detector runs on a bare interpreter: tomllib ships with the standard
library since Python 3.11, PyYAML does not ship at all.
"""

from __future__ import annotations

import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

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
	feature: str | None = None
	frozen_from: str | None = None


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
		feature=raw.get("feature"),
		frozen_from=raw.get("frozen_from"),
	)


def list_cached_toml(directory: Path) -> list[str]:
	"""The *.toml files directly inside `directory` in the git index, repo-relative.

	Runs `git ls-files --cached` in the current working directory, which must
	be the repository root. Subdirectories are left out on purpose, like the
	flat `*.toml` glob of disk mode: the cards under docs/customizations/features
	are not inventory files.
	"""
	parent = PurePosixPath(Path(directory).as_posix())
	try:
		result = subprocess.run(
			["git", "ls-files", "--cached", "-z", "--", parent.as_posix()],
			capture_output=True,
			text=True,
			encoding="utf-8",
			errors="replace",
		)
	except OSError as exc:
		raise InventoryError(f"impossibile eseguire git per elencare {parent}: {exc}") from exc
	if result.returncode != 0:
		raise InventoryError(f"git ls-files {parent}: {result.stderr.strip()}")
	return sorted(
		path
		for path in result.stdout.split("\0")
		if path.endswith(".toml") and PurePosixPath(path).parent == parent
	)


def load_inventory(directory: Path, read: Callable[[str], str | None] | None = None) -> list[Entry]:
	"""Read every *.toml in `directory` and return the entries they declare.

	Files without an `entries` array (actors.toml, for instance) are read and
	ignored rather than rejected: they belong to the inventory but describe
	something other than customizations.

	Without `read` the files come from disk. With `read`, `directory` is
	repo-relative, the files are listed from the git index (see
	`list_cached_toml`) and their text comes from `read`; None means absent.
	"""
	if read is None:
		sources = [(path.name, path.read_text(encoding="utf-8")) for path in sorted(Path(directory).glob("*.toml"))]
	else:
		sources = []
		for relative in list_cached_toml(directory):
			text = read(relative)
			if text is not None:
				sources.append((PurePosixPath(relative).name, text))
	entries: list[Entry] = []
	seen: dict[str, str] = {}
	for name, text in sources:
		try:
			raw = tomllib.loads(text)
		except tomllib.TOMLDecodeError as exc:
			raise InventoryError(f"{name}: invalid TOML ({exc})") from exc
		for raw_entry in raw.get("entries", []):
			entry = _build_entry(raw_entry, name)
			if entry.id in seen:
				raise InventoryError(
					f"{name}: duplicate entry id '{entry.id}', already declared in {seen[entry.id]}"
				)
			seen[entry.id] = name
			entries.append(entry)
	return entries
