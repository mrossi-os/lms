#!/usr/bin/env python3
"""Plan an upstream upgrade: what each pending frappe/lms release really brings.

For every release after the last one already merged into HEAD, report the real
size (from the commit diff between consecutive tags, never from the release
notes, which over- and under-state it), the declared breaking changes, the
frappe-ui version, the inventory entries and frozen pages it touches, and the
files we modified without cataloguing them. Ends with a recommendation on where
to stop. Read only: it never fetches, merges or writes anything.

Standard library only, like the drift detector. Every git call goes through
subprocess with an argument list: in zsh `$t:path` is a history modifier, so
shell strings built around tag names silently break.

Exit codes: 0 plan produced, 2 cannot plan (no base tag, bad tag, git failure,
inventory malformed).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import MARKER  # noqa: E402
from scripts.customizations.model import InventoryError, load_inventory  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = Path("docs/customizations")
PACKAGE_JSON = "frontend/package.json"
WATCHED_DEPENDENCY = "frappe-ui"
OVERRIDES_DIR = "frontend/src/overrides/"
OVERRIDDEN_ROOT = "frontend/src/"

# Upstream release tags only: our own tags (ve1.0.1, vi1.0.7) and the
# assets-* tags never match.
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Conventional Commits breaking marker. frappe/lms merges pull requests with
# merge commits whose subject is "Merge pull request #N" and whose body carries
# the PR title, so every line of the message is scanned, not just the subject.
BREAKING_LINE = re.compile(r"^[a-z]+(\([^)]*\))?!: .+|^BREAKING[ -]CHANGE: .+")

# Files we touch that are not customizations to catalogue: translations and
# tests by design, lock and generated files because they are regenerated, never
# hand-merged.
NOT_CUSTOMIZATION = (
	re.compile(r"(^|/)locale/|(^|/)translations/|\.pot?$|\.mo$"),
	re.compile(r"(^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$|\.(test|spec)\.[jt]s$|^cypress/"),
	re.compile(r"(^|/)yarn\.lock$|(^|/)package-lock\.json$|^frontend/components\.d\.ts$"),
)


class PlanError(Exception):
	"""The plan cannot be computed; the message says why, for a human."""


# ── Pure logic ────────────────────────────────────────────────────────────────


def parse_version(tag: str) -> tuple[int, int, int] | None:
	"""Return the numeric version of an upstream release tag, or None."""
	match = RELEASE_TAG.match(tag)
	return tuple(int(part) for part in match.groups()) if match else None


def sort_release_tags(tags: list[str]) -> list[str]:
	"""Keep upstream release tags only, in version order (like `sort -V`)."""
	return sorted((t for t in tags if parse_version(t)), key=parse_version)


def breaking_changes(messages: list[str]) -> list[str]:
	"""Declared breaking changes in the given commit messages, deduplicated.

	The same PR title can appear both in the merge commit body and as a squashed
	commit subject: it is one breaking change, not two.
	"""
	found: list[str] = []
	for message in messages:
		for line in message.splitlines():
			line = line.strip()
			if BREAKING_LINE.match(line) and line not in found:
				found.append(line)
	return found


def dependency_version(package_json: str | None, name: str = WATCHED_DEPENDENCY) -> str | None:
	"""The version spec of `name` in a package.json text, or None if absent."""
	if not package_json:
		return None
	try:
		data = json.loads(package_json)
	except json.JSONDecodeError:
		return None
	for section in ("dependencies", "devDependencies", "peerDependencies"):
		version = data.get(section, {}).get(name)
		if version:
			return version
	return None


def parse_name_status(raw: str) -> tuple[int, set[str]]:
	"""Parse `git diff --name-status -z`: (files changed, every path involved).

	A rename counts as one changed file but contributes both paths: a file we
	customized that upstream renames away must still be matched by its old name.
	"""
	fields = [f for f in raw.split("\0") if f]
	count = 0
	paths: set[str] = set()
	index = 0
	while index < len(fields):
		status = fields[index]
		width = 2 if status[:1] in ("R", "C") else 1
		paths.update(fields[index + 1 : index + 1 + width])
		count += 1
		index += 1 + width
	return count, paths


def is_customization_candidate(path: str) -> bool:
	"""False for translations, tests and generated files."""
	return not any(pattern.search(path) for pattern in NOT_CUSTOMIZATION)


def frozen_originals(override_paths: list[str]) -> dict[str, str]:
	"""Map each lms file shadowed by an override to its override path.

	An override at frontend/src/overrides/<rel> replaces frontend/src/<rel>.
	Overrides of frappe-ui components map to paths that do not exist in lms and
	are never touched by an lms release: they follow the frappe-ui version.
	"""
	return {
		OVERRIDDEN_ROOT + path[len(OVERRIDES_DIR) :]: path
		for path in override_paths
		if path.startswith(OVERRIDES_DIR)
	}


@dataclass
class Release:
	"""One pending upstream release and what it touches."""

	tag: str
	previous: str
	date: str
	commits: int
	files: int
	frappe_ui: str | None
	frappe_ui_from: str | None = None
	breaking: list[str] = field(default_factory=list)
	inventory: list[str] = field(default_factory=list)
	frozen: list[str] = field(default_factory=list)
	uncatalogued: list[str] = field(default_factory=list)

	@property
	def dependency_bump(self) -> bool:
		return self.frappe_ui_from is not None


def recommend(releases: list[Release]) -> dict:
	"""Where to stop: just before the first dependency bump or declared break.

	If the very first pending release is itself the risky one, it is
	recommended alone, so that it is handled as a dedicated activity.
	"""
	if not releases:
		return {"tag": None, "reason": "Nessuna release da attraversare: il branch è già aggiornato."}
	for index, release in enumerate(releases):
		risks = []
		if release.dependency_bump:
			risks.append(f"il bump di {WATCHED_DEPENDENCY} {release.frappe_ui_from} → {release.frappe_ui}")
		if release.breaking:
			risks.append(f"{len(release.breaking)} rotture dichiarate")
		if not risks:
			continue
		why = " e ".join(risks)
		if index == 0:
			return {
				"tag": release.tag,
				"reason": f"{release.tag} porta {why}: va attraversata da sola, come attività dedicata.",
			}
		return {
			"tag": releases[index - 1].tag,
			"reason": f"Ultima release prima di {release.tag}, che porta {why} e va isolata.",
		}
	last = releases[-1].tag
	return {
		"tag": last,
		"reason": f"Nessun bump di {WATCHED_DEPENDENCY} né rotture dichiarate fino a {last}.",
	}


# ── Git access ────────────────────────────────────────────────────────────────


class Git:
	"""Thin read-only wrapper around the git CLI."""

	def __init__(self, repo_root: Path):
		self.repo_root = repo_root

	def run(self, *args: str, check: bool = True) -> str:
		result = subprocess.run(
			["git", *args],
			cwd=self.repo_root,
			capture_output=True,
			text=True,
			encoding="utf-8",
			errors="replace",
		)
		if check and result.returncode != 0:
			raise PlanError(f"git {' '.join(args)}: {result.stderr.strip()}")
		return result.stdout

	def is_ancestor(self, ancestor: str, descendant: str) -> bool:
		result = subprocess.run(
			["git", "merge-base", "--is-ancestor", ancestor, descendant],
			cwd=self.repo_root,
			capture_output=True,
		)
		return result.returncode == 0

	def show(self, ref: str, path: str) -> str | None:
		result = subprocess.run(
			["git", "show", f"{ref}:{path}"],
			cwd=self.repo_root,
			capture_output=True,
			text=True,
			encoding="utf-8",
			errors="replace",
		)
		return result.stdout if result.returncode == 0 else None

	def lines(self, *args: str) -> list[str]:
		return [line for line in self.run(*args).split("\0" if "-z" in args else "\n") if line]


def find_base(git: Git, head: str) -> str:
	"""The most recent upstream release tag already merged into `head`."""
	merged = sort_release_tags(git.lines("tag", "--merged", head))
	if not merged:
		raise PlanError(
			f"Nessun tag di release upstream è antenato di {head}: "
			"controlla il remote 'upstream' e lancia 'git fetch upstream --tags'."
		)
	return merged[-1]


def pending_tags(git: Git, base: str, target: str | None) -> list[str]:
	"""Release tags after `base`, up to `target`, that descend from `base`."""
	base_version = parse_version(base)
	tags = [t for t in sort_release_tags(git.lines("tag", "--list")) if parse_version(t) > base_version]
	if target is not None:
		if parse_version(target) is None or target not in tags:
			raise PlanError(f"{target} non è una release successiva a {base}.")
		tags = [t for t in tags if parse_version(t) <= parse_version(target)]
	# A hotfix line tagged on another branch is not on the path from base.
	return [t for t in tags if git.is_ancestor(base, t)]


def our_uncatalogued_files(git: Git, base: str, head: str, catalogued: set[str]) -> list[str]:
	"""Upstream files carrying our modifications that the inventory does not cover.

	Our commits are those on `head` not reachable from any upstream ref or
	upstream release tag: without the exclusion an old merge of upstream/develop
	inflates the count with upstream work. Only release tags are excluded, not
	`--tags`: the fork's own tags (ve1.0.1, vi1.0.7) sit on our branch, and
	`--not --tags` silently drops every commit of ours before them — measured on
	2026-09-23, 535 of our 741 commits. A file qualifies if it existed at `base`,
	still differs from it at `head`, carries no marker and is catalogued by no
	entry.
	"""
	release_tags = sort_release_tags(git.lines("tag", "--list"))
	ours = set(
		git.lines(
			"log",
			"--no-merges",
			"--format=",
			"--name-only",
			"-z",
			f"{base}..{head}",
			"--not",
			"--remotes=upstream",
			*release_tags,
		)
	)
	upstream_files = set(git.lines("ls-tree", "-r", "--name-only", "-z", base))
	still_different = set(git.lines("diff", "--no-renames", "--name-only", "-z", base, head))
	marked = {
		line.split(":", 1)[1]
		for line in git.run("grep", "-l", "-F", MARKER, head, check=False).splitlines()
		if ":" in line
	}
	return sorted(
		path
		for path in ours & upstream_files & still_different
		if path not in catalogued and path not in marked and is_customization_candidate(path)
	)


def build_plan(
	repo_root: Path, inventory_dir: Path, head: str, start: str | None, target: str | None
) -> dict:
	git = Git(repo_root)
	entries = load_inventory(inventory_dir)
	files_to_entries: dict[str, list[str]] = {}
	for entry in entries:
		for site in entry.sites:
			files_to_entries.setdefault(site.file, [])
			if entry.id not in files_to_entries[site.file]:
				files_to_entries[site.file].append(entry.id)

	base = start or find_base(git, head)
	if parse_version(base) is None or not git.run("tag", "--list", base).strip():
		raise PlanError(f"{base} non è un tag di release upstream.")
	tags = pending_tags(git, base, target)
	uncatalogued = our_uncatalogued_files(git, base, head, set(files_to_entries))
	originals = frozen_originals(git.lines("ls-tree", "-r", "--name-only", "-z", head, OVERRIDES_DIR))

	releases: list[Release] = []
	previous = base
	previous_ui = dependency_version(git.show(base, PACKAGE_JSON))
	for tag in tags:
		count, paths = parse_name_status(git.run("diff", "--name-status", "-z", previous, tag))
		messages = git.run("log", "--format=%B%x00", f"{previous}..{tag}").split("\0")
		frappe_ui = dependency_version(git.show(tag, PACKAGE_JSON))
		touched_entries = sorted({eid for path in paths for eid in files_to_entries.get(path, [])})
		releases.append(
			Release(
				tag=tag,
				previous=previous,
				date=git.run("log", "-1", "--format=%cs", tag).strip(),
				commits=int(git.run("rev-list", "--count", f"{previous}..{tag}").strip()),
				files=count,
				frappe_ui=frappe_ui,
				frappe_ui_from=previous_ui if frappe_ui != previous_ui else None,
				breaking=breaking_changes(messages),
				inventory=touched_entries,
				frozen=sorted(originals[path] for path in paths if path in originals),
				uncatalogued=sorted(path for path in uncatalogued if path in paths),
			)
		)
		previous, previous_ui = tag, frappe_ui

	return {
		"head": head,
		"base": base,
		"releases": releases,
		"uncatalogued_total": len(uncatalogued),
		"recommendation": recommend(releases),
	}


# ── Rendering ─────────────────────────────────────────────────────────────────


def render_json(plan: dict, generated_at: str) -> str:
	payload = {
		"generated_at": generated_at,
		**plan,
		"releases": [{**asdict(r), "dependency_bump": r.dependency_bump} for r in plan["releases"]],
	}
	return json.dumps(payload, indent=2, ensure_ascii=False)


def render_table(plan: dict) -> str:
	releases: list[Release] = plan["releases"]
	lines = [f"Base: {plan['base']} (ultima release upstream già fusa in {plan['head']})", ""]
	if not releases:
		lines.append(plan["recommendation"]["reason"])
		return "\n".join(lines)

	header = (
		"Release",
		"Data",
		"Commit",
		"File",
		WATCHED_DEPENDENCY,
		"Rotture",
		"Voci",
		"Non censiti",
		"Congelate",
	)
	rows = []
	for r in releases:
		ui = f"{r.frappe_ui_from} → {r.frappe_ui}" if r.dependency_bump else (r.frappe_ui or "-")
		rows.append(
			(
				r.tag,
				r.date,
				str(r.commits),
				str(r.files),
				ui,
				str(len(r.breaking)),
				str(len(r.inventory)),
				str(len(r.uncatalogued)),
				str(len(r.frozen)),
			)
		)
	widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
	for row in (header, *rows):
		lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
	lines.append("")

	for r in releases:
		details = []
		if r.dependency_bump:
			details.append(f"  {WATCHED_DEPENDENCY}: {r.frappe_ui_from} → {r.frappe_ui}")
		details += [f"  rottura: {line}" for line in r.breaking]
		if r.inventory:
			details.append(f"  voci di inventario: {', '.join(r.inventory)}")
		details += [f"  pagina congelata: {path}" for path in r.frozen]
		details += [f"  non censito: {path}" for path in r.uncatalogued]
		if details:
			lines += [f"{r.tag}", *details, ""]

	lines.append(f"File con modifiche nostre non censite, in totale: {plan['uncatalogued_total']}")
	lines.append("")
	rec = plan["recommendation"]
	lines.append(f"Raccomandazione: fermarsi a {rec['tag']}. {rec['reason']}")
	return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	parser.add_argument(
		"--inventory",
		type=Path,
		default=None,
		help="inventory directory (default: <repo-root>/docs/customizations)",
	)
	parser.add_argument("--head", default="HEAD", help="branch or ref to plan for (default: HEAD)")
	parser.add_argument(
		"--from",
		dest="start",
		default=None,
		help="base tag (default: the last upstream release merged into --head)",
	)
	parser.add_argument("--to", dest="target", default=None, help="last release to include (default: newest)")
	parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	inventory_dir = args.inventory or (repo_root / DEFAULT_INVENTORY)
	try:
		plan = build_plan(repo_root, inventory_dir, args.head, args.start, args.target)
	except (PlanError, InventoryError) as exc:
		print(f"Piano non calcolabile: {exc}", file=sys.stderr)
		return 2

	if args.json:
		print(render_json(plan, datetime.now().isoformat(timespec="seconds")))
	else:
		print(render_table(plan))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
