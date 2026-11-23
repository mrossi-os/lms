"""The computed customization map: every difference from upstream, by feature.

For a ref (default HEAD) and its upstream base (the last release tag merged
into it), each upstream file that differs from the base is split into diff
hunks and every hunk is attributed to one or more features of the catalogue,
in the order of design §5.5:

1. the `Oslms-Feature` trailers of the commits that wrote its added lines
   (`git blame`, merge commits included), or, for a hunk that only removes
   upstream lines, of our commit that removed them (`git log -S`);
2. the inventory entries whose anchor the hunk contains or touches;
3. the cards whose `areas` cover the file;
4. the legacy map (`legacy-attribution.toml`), file → features;
5. otherwise the hunk is unattributed: the number to bring to zero.

Read-only: nothing here writes to the repository.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from scripts.customizations.features import Feature, load_features
from scripts.customizations.gitbase import Git, find_base
from scripts.customizations.model import Entry, InventoryError, load_inventory
from scripts.customizations.paths import FEATURES_DIR, INVENTORY_DIR, LEGACY_FILE, is_exempt_path
from scripts.customizations.trailers import NONE_VALUE, parse_trailers
from scripts.upstream_plan import is_customization_candidate

SOURCES = ("trailer", "anchor", "area", "legacy")
UNATTRIBUTED = "unattributed"

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
BLAME_HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")


@dataclass
class Hunk:
	"""One `git diff -U0` block of a file, between the base and the ref."""

	file: str
	base_start: int
	base_len: int
	head_start: int
	head_len: int
	added: list[str] = field(default_factory=list)
	removed: list[str] = field(default_factory=list)


def _new_hunk(path: str, header: re.Match) -> Hunk:
	base_start, base_len, head_start, head_len = header.groups()
	return Hunk(
		file=path,
		base_start=int(base_start),
		base_len=1 if base_len is None else int(base_len),
		head_start=int(head_start),
		head_len=1 if head_len is None else int(head_len),
	)


def diff_hunks(git: Git, base: str, ref: str, paths: list[str]) -> list[Hunk]:
	"""The `git diff -U0` hunks of `paths` between `base` and `ref`.

	A binary file that differs yields one whole-file hunk with no lines, so it
	is still attributed (by area or legacy map) instead of vanishing.
	"""
	if not paths:
		return []
	output = git.run(
		"-c", "core.quotePath=false", "diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff",
		base, ref, "--", *paths,
	)
	hunks: list[Hunk] = []
	old_path = new_path = ""
	current: Hunk | None = None
	for line in output.split("\n"):
		if line.startswith("diff --git "):
			current = None
			old_path = new_path = ""
		elif current is None and line.startswith("--- "):
			# git appends a tab to names containing spaces, for patch(1)
			old_path = line[6:].removesuffix("\t") if line.startswith("--- a/") else ""
		elif current is None and line.startswith("+++ "):
			new_path = line[6:].removesuffix("\t") if line.startswith("+++ b/") else ""
		elif current is None and line.startswith("Binary files "):
			hunks.append(Hunk(file=new_path or old_path or _binary_path(line), base_start=0, base_len=0, head_start=0, head_len=0))
		elif header := HUNK_HEADER.match(line):
			current = _new_hunk(new_path or old_path, header)
			hunks.append(current)
		elif current is not None and line.startswith("+"):
			current.added.append(line[1:])
		elif current is not None and line.startswith("-"):
			current.removed.append(line[1:])
	return hunks


def _binary_path(line: str) -> str:
	# "Binary files a/x and b/x differ" (no ---/+++ header precedes it)
	match = re.match(r"^Binary files (?:a/(.*?)|/dev/null) and (?:b/(.*?)|/dev/null) differ$", line)
	return (match.group(2) or match.group(1)) if match else ""


def load_legacy(path: Path) -> dict[str, list[str]]:
	"""The legacy map, file path → feature ids; an absent file is an empty map."""
	try:
		text = Path(path).read_text(encoding="utf-8")
	except FileNotFoundError:
		return {}
	try:
		raw = tomllib.loads(text)
	except tomllib.TOMLDecodeError as exc:
		raise InventoryError(f"{Path(path).name}: TOML non valido ({exc})") from exc
	legacy: dict[str, list[str]] = {}
	for item in raw.get("files", []):
		if not item.get("path") or not item.get("features"):
			raise InventoryError(f"{Path(path).name}: ogni [[files]] vuole 'path' e 'features'")
		legacy.setdefault(item["path"], []).extend(item["features"])
	return legacy


class History:
	"""Per-run caches of what git says about the ref, so each file is blamed once."""

	def __init__(self, git: Git, base: str, ref: str, release_tags: list[str]):
		self.git = git
		self.base = base
		self.ref = ref
		self.release_tags = release_tags
		self._blame: dict[str, dict[int, str]] = {}
		self._trailers: dict[str, list[str]] = {}
		self._removers: dict[tuple[str, str], str | None] = {}
		self._contents: dict[str, str] = {}

	def prepare_blame(self, path: str, hunks: list[Hunk]) -> None:
		"""Blame every added range of `path` in one call (line number → commit)."""
		ranges = [arg for h in hunks if h.head_len > 0 for arg in ("-L", f"{h.head_start},+{h.head_len}")]
		lines: dict[int, str] = {}
		if ranges:
			output = self.git.run("blame", "--porcelain", *ranges, f"{self.base}..{self.ref}", "--", path)
			for line in output.split("\n"):
				match = BLAME_HEADER.match(line)
				if match:
					lines[int(match.group(2))] = match.group(1)
		self._blame[path] = lines

	def commits_of_added(self, hunk: Hunk) -> list[str]:
		if hunk.file not in self._blame:
			self.prepare_blame(hunk.file, [hunk])
		blamed = self._blame[hunk.file]
		commits = {blamed[n] for n in range(hunk.head_start, hunk.head_start + hunk.head_len) if n in blamed}
		return sorted(commits)

	def remover_of(self, hunk: Hunk) -> str | None:
		"""Our commit that removed the hunk's first non-blank line, if any."""
		text = next((line for line in hunk.removed if line.strip()), None)
		if text is None:
			return None
		key = (hunk.file, text)
		if key not in self._removers:
			found = self.git.lines(
				"log", "--format=%H", f"-S{text}", f"{self.base}..{self.ref}",
				"--not", *self.release_tags, "--", hunk.file,
			)
			self._removers[key] = found[0] if found else None
		return self._removers[key]

	def trailers(self, commit: str) -> list[str]:
		"""Feature ids named by the commit's `Oslms-Feature` lines; `none (...)` is no feature."""
		if commit not in self._trailers:
			message = self.git.run("log", "-1", "--format=%B", commit)
			self._trailers[commit] = [v for v in parse_trailers(message) if not NONE_VALUE.match(v)]
		return self._trailers[commit]

	def content(self, path: str) -> str:
		if path not in self._contents:
			self._contents[path] = self.git.show(self.ref, path) or ""
		return self._contents[path]


def _anchor_lines(content: str, anchor: str) -> list[tuple[int, int]]:
	"""1-based (first, last) line spans of every occurrence of `anchor` in `content`."""
	spans = []
	start = content.find(anchor)
	while start != -1:
		first = content.count("\n", 0, start) + 1
		spans.append((first, first + anchor.count("\n")))
		start = content.find(anchor, start + 1)
	return spans


def _touches(hunk: Hunk, span: tuple[int, int]) -> bool:
	# A removal-only hunk sits between head_start and head_start + 1.
	low = hunk.head_start
	high = hunk.head_start + max(hunk.head_len, 1) - (1 if hunk.head_len else 0)
	return span[0] <= high and span[1] >= low


def _by_trailer(hunk: Hunk, history: History) -> tuple[list[str], list[str]]:
	"""Feature ids and the commits that named them, from blame or from the remover."""
	if hunk.head_len > 0:
		commits = history.commits_of_added(hunk)
	else:
		remover = history.remover_of(hunk)
		commits = [remover] if remover else []
	ids: set[str] = set()
	naming: list[str] = []
	for commit in commits:
		found = history.trailers(commit)
		if found:
			ids.update(found)
			naming.append(commit)
	return sorted(ids), naming


def _by_anchor(hunk: Hunk, entries: list[Entry], history: History) -> list[str]:
	added = "\n".join(hunk.added)
	ids = set()
	for entry in entries:
		if not entry.feature:
			continue
		for site in entry.sites:
			if site.file != hunk.file:
				continue
			if (added and site.anchor in added) or any(
				_touches(hunk, span) for span in _anchor_lines(history.content(hunk.file), site.anchor)
			):
				ids.add(entry.feature)
	return sorted(ids)


def attribute(
	hunk: Hunk,
	*,
	git: Git,
	base: str,
	ref: str,
	features: dict[str, Feature],
	entries: list[Entry],
	legacy: dict[str, list[str]],
	release_tags: list[str],
	history: History | None = None,
) -> tuple[list[str], str]:
	"""The feature ids of `hunk` and the source that gave them (design §5.5 order).

	`history` shares the blame and trailer caches across the hunks of a run;
	without it every call starts from scratch.
	"""
	attribution, _ = attribute_with_commits(
		hunk,
		history=history or History(git, base, ref, release_tags),
		features=features,
		entries=entries,
		legacy=legacy,
	)
	return attribution


def attribute_with_commits(
	hunk: Hunk,
	*,
	history: History,
	features: dict[str, Feature],
	entries: list[Entry],
	legacy: dict[str, list[str]],
) -> tuple[tuple[list[str], str], list[str]]:
	"""Like `attribute`, plus the commits whose trailers gave the attribution."""
	ids, commits = _by_trailer(hunk, history)
	if ids:
		return (ids, "trailer"), commits
	ids = _by_anchor(hunk, entries, history)
	if ids:
		return (ids, "anchor"), []
	ids = sorted(f.id for f in features.values() if f.matches_path(hunk.file))
	if ids:
		return (ids, "area"), []
	ids = sorted(set(legacy.get(hunk.file, [])))
	if ids:
		return (ids, "legacy"), []
	return ([], UNATTRIBUTED), []


def map_paths(git: Git, base: str, ref: str) -> tuple[list[str], list[str]]:
	"""Upstream files that differ from the base, and our own files, both filtered."""
	base_files = set(git.lines("ls-tree", "-r", "--name-only", "-z", base))
	changed = git.lines("diff", "--no-renames", "--name-only", "-z", base, ref)
	ref_files = git.lines("ls-tree", "-r", "--name-only", "-z", ref)

	def kept(path: str) -> bool:
		return is_customization_candidate(path) and not is_exempt_path(path)

	upstream = sorted(p for p in changed if p in base_files and kept(p))
	ours = sorted(p for p in ref_files if p not in base_files and kept(p))
	return upstream, ours


def build_map(repo_root: Path, ref: str = "HEAD") -> dict:
	"""The customization map of `ref` against its upstream base.

	Cards, inventory and legacy map are read from the working tree of
	`repo_root`: they describe what we know today, whatever ref is mapped.
	"""
	repo_root = Path(repo_root)
	git = Git(repo_root)
	base = find_base(git, ref)
	features = load_features(repo_root / FEATURES_DIR)
	entries = load_inventory(repo_root / INVENTORY_DIR)
	legacy = load_legacy(repo_root / LEGACY_FILE)
	history = History(git, base, ref, git.release_tags())

	upstream_paths, our_paths = map_paths(git, base, ref)
	hunks = diff_hunks(git, base, ref, upstream_paths)
	by_file: dict[str, list[Hunk]] = {}
	for hunk in hunks:
		by_file.setdefault(hunk.file, []).append(hunk)
	for path, file_hunks in by_file.items():
		history.prepare_blame(path, file_hunks)

	result_features: dict[str, dict] = {
		f.id: {"title": f.title, "summary": f.summary, "files": set(), "hunks": [], "commits": set()}
		for f in features.values()
	}
	unattributed: list[dict] = []
	by_source = {source: 0 for source in SOURCES}
	unknown: set[str] = set()

	for hunk in hunks:
		(ids, source), commits = attribute_with_commits(
			hunk, history=history, features=features, entries=entries, legacy=legacy
		)
		where = {"file": hunk.file, "head_start": hunk.head_start, "head_len": hunk.head_len}
		if source == UNATTRIBUTED:
			unattributed.append(where)
			continue
		by_source[source] += 1
		for feature_id in ids:
			if feature_id not in features:
				unknown.add(feature_id)
			slot = result_features.setdefault(
				feature_id, {"title": "", "summary": "", "files": set(), "hunks": [], "commits": set()}
			)
			slot["files"].add(hunk.file)
			slot["hunks"].append({**where, "source": source})
			slot["commits"].update(c for c in commits if feature_id in history.trailers(c))

	for feature in features.values():
		result_features[feature.id]["files"].update(p for p in our_paths if feature.matches_path(p))

	for slot in result_features.values():
		slot["files"] = sorted(slot["files"])
		slot["commits"] = sorted(slot["commits"])

	return {
		"base": base,
		"ref": ref,
		"features": dict(sorted(result_features.items())),
		"unattributed": unattributed,
		"totals": {
			"files": len(by_file),
			"hunks": len(hunks),
			"attributed": len(hunks) - len(unattributed),
			"unattributed": len(unattributed),
			"by_source": by_source,
			"unknown_features": sorted(unknown),
		},
	}
