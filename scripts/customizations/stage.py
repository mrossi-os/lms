"""The commit being prepared, as git sees it: staged paths, staged and base text, merge state.

Everything here reads the index (`git show :<path>`, `git diff --cached`) or
$GIT_DIR, never the working tree: the commit-msg hook must judge what will be
committed, not what happens to be on disk.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from scripts.customizations.checks import Reader
from scripts.customizations.gitbase import Git, sort_release_tags
from scripts.customizations.model import Entry, list_cached_toml
from scripts.upstream_plan import parse_name_status

INVENTORY_DIR = "docs/customizations"


@dataclass(frozen=True)
class MergeInfo:
	"""The merge being concluded, if any. `release` is the upstream tag merged."""

	is_upstream_release: bool
	had_conflicts: bool
	release: str | None = None


def staged_paths(git: Git) -> set[str]:
	"""Every path the staged commit touches; a rename contributes both paths."""
	return parse_name_status(git.run("diff", "--cached", "--name-status", "-z", "-M"))[1]


def read_merge_info(git: Git) -> MergeInfo | None:
	"""Describe the merge in progress from MERGE_HEAD and MERGE_MSG, or None."""
	git_dir = git.repo_root / git.git_dir()
	merge_head = git_dir / "MERGE_HEAD"
	if not merge_head.is_file():
		return None
	tags = []
	for sha in merge_head.read_text(encoding="utf-8").split():
		tags += git.lines("tag", "--points-at", sha)
	releases = sort_release_tags(tags)
	merge_msg = git_dir / "MERGE_MSG"
	text = merge_msg.read_text(encoding="utf-8", errors="replace") if merge_msg.is_file() else ""
	conflicts = any(line.startswith(("# Conflicts:", "Conflicts:")) for line in text.splitlines())
	return MergeInfo(bool(releases), conflicts, releases[-1] if releases else None)


def _sites_by_entry(text: str | None) -> dict[str, tuple]:
	"""Raw `id -> sites` of one inventory file, tolerant: the old version may be anything."""
	if text is None:
		return {}
	try:
		raw = tomllib.loads(text)
	except tomllib.TOMLDecodeError:
		return {}
	result = {}
	for entry in raw.get("entries", []):
		if isinstance(entry, dict) and "id" in entry:
			sites = entry.get("sites", [])
			result[entry["id"]] = tuple((s.get("file"), s.get("anchor")) for s in sites if isinstance(s, dict))
	return result


def changed_entry_ids(git: Git, entries: list[Entry]) -> frozenset[str]:
	"""Entries this commit adds, or whose sites it changes, compared with HEAD."""
	before: dict[str, tuple] = {}
	for relative in list_cached_toml(Path(INVENTORY_DIR)):
		before.update(_sites_by_entry(git.show("HEAD", relative)))
	return frozenset(
		e.id for e in entries if before.get(e.id) != tuple((s.file, s.anchor) for s in e.sites)
	)


def cached_reader(git: Git, ref: str) -> Reader:
	"""A reader over `ref` ("" = the index), memoised: the checks read the same files repeatedly."""
	cache: dict[str, str | None] = {}

	def read(relative: str) -> str | None:
		if relative not in cache:
			cache[relative] = git.show(ref, relative)
		return cache[relative]

	return read
