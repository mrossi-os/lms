"""Read-only access to git, shared by the drift detector and the upgrade planner.

Every git call goes through subprocess with an argument list: in zsh `$t:path`
is a history modifier, so shell strings built around tag names silently break.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Upstream release tags only: our own tags (ve1.0.1, vi1.0.7) and the
# assets-* tags never match.
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class PlanError(Exception):
	"""The plan cannot be computed; the message says why, for a human."""


def parse_version(tag: str) -> tuple[int, int, int] | None:
	"""Return the numeric version of an upstream release tag, or None."""
	match = RELEASE_TAG.match(tag)
	return tuple(int(part) for part in match.groups()) if match else None


def sort_release_tags(tags: list[str]) -> list[str]:
	"""Keep upstream release tags only, in version order (like `sort -V`)."""
	return sorted((t for t in tags if parse_version(t)), key=parse_version)


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

	def git_dir(self) -> Path:
		"""The repository's git directory (raises PlanError outside a repository)."""
		return Path(self.run("rev-parse", "--git-dir").strip())

	def release_tags(self) -> list[str]:
		"""Every upstream release tag of the repository, in version order."""
		return sort_release_tags(self.lines("tag", "--list"))

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
