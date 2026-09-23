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
