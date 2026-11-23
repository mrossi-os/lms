"""The feature catalogue: one TOML card per functionality.

A card carries the meaning (what the feature does, why it exists, which rules
are observable from outside); inventory entries carry the anchors that raise
the quick alarm. Entries point at a card through their `feature` field.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable

from scripts.customizations.model import InventoryError, list_cached_toml

FEATURE_STATUSES = frozenset({"active", "retired", "replaced-by-upstream"})
STRICT_FEATURES_FLAG = Path("docs/customizations/features/.strict")
REQUIRED_FIELDS = (
	"id",
	"title",
	"status",
	"summary",
	"why",
	"behaviour",
	"areas",
	"upstream_watch",
	"history",
)


@dataclass(frozen=True)
class Feature:
	"""One functionality of the fork, as described by its card."""

	id: str
	title: str
	status: str
	summary: str
	why: str
	behaviour: tuple[str, ...]
	areas: tuple[str, ...]
	upstream_watch: tuple[str, ...]
	history: tuple[dict, ...]
	roles: tuple[str, ...] = ()
	data: tuple[str, ...] = ()
	tests: tuple[str, ...] = ()
	notes: str = ""
	source: str = ""

	def matches_path(self, path: str) -> bool:
		"""True when `path` falls under one of the card's `areas` globs."""
		return any(fnmatch(path, pattern) for pattern in self.areas)


def _build_feature(raw: dict, filename: str) -> Feature:
	for key in REQUIRED_FIELDS:
		if not raw.get(key):
			raise InventoryError(f"{filename}: la scheda non ha il campo obbligatorio '{key}'")
	expected = filename.removesuffix(".toml")
	if raw["id"] != expected:
		raise InventoryError(f"{filename}: l'id '{raw['id']}' non coincide con il nome del file")
	if raw["status"] not in FEATURE_STATUSES:
		raise InventoryError(f"{filename}: stato sconosciuto '{raw['status']}'")
	return Feature(
		id=raw["id"],
		title=raw["title"],
		status=raw["status"],
		summary=raw["summary"].strip(),
		why=raw["why"].strip(),
		behaviour=tuple(raw["behaviour"]),
		areas=tuple(raw["areas"]),
		upstream_watch=tuple(raw["upstream_watch"]),
		history=tuple(raw["history"]),
		roles=tuple(raw.get("roles", ())),
		data=tuple(raw.get("data", ())),
		tests=tuple(raw.get("tests", ())),
		notes=raw.get("notes", "").strip(),
		source=filename,
	)


def load_features(
	directory: Path, read: Callable[[str], str | None] | None = None
) -> dict[str, Feature]:
	"""Load every card and return them keyed by id.

	Without `read`, the `*.toml` files in `directory` are read from disk. With
	`read`, `directory` is the repo-relative path (for instance
	Path("docs/customizations/features")): cards are enumerated with
	`list_cached_toml` (git index, current working directory) and their contents
	come from `read(relative_path)`, which reads the git index; the disk is not
	touched. `read` returning None means the file is absent and it is skipped.
	"""
	if read is None:
		sources = [(path.name, path.read_text(encoding="utf-8")) for path in sorted(Path(directory).glob("*.toml"))]
	else:
		sources = []
		for relative in list_cached_toml(Path(directory)):
			text = read(relative)
			if text is not None:
				sources.append((relative.rsplit("/", 1)[-1], text))
	features: dict[str, Feature] = {}
	for filename, text in sources:
		try:
			raw = tomllib.loads(text)
		except tomllib.TOMLDecodeError as exc:
			raise InventoryError(f"{filename}: TOML non valido ({exc})") from exc
		feature = _build_feature(raw, filename)
		features[feature.id] = feature
	return features
