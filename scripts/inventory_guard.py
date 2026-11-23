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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import Finding, check_uncatalogued_markers  # noqa: E402
from scripts.customizations.gitbase import Git  # noqa: E402
from scripts.customizations.model import load_inventory  # noqa: E402
from scripts.customizations.paths import INVENTORY_DIR, STRICT_FEATURES_FLAG  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
SENTINEL_NAME = "oslms-inventory-guard"
HOOKS_PATH = ".githooks"


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


def hooks_path_problem(repo_root: Path) -> str | None:
	"""Return a message when the commit guard hooks are not enabled, else None.

	Only after the catalogue migration (the strict flag file exists): before
	it the guard would refuse every commit. Enabling the hooks is a
	configuration change the user approves, so the message asks Claude to
	ask, never to run the command on its own.
	"""
	if not (repo_root / STRICT_FEATURES_FLAG).is_file():
		return None
	result = subprocess.run(
		["git", "config", "--get", "core.hooksPath"],
		cwd=repo_root,
		capture_output=True,
		text=True,
		encoding="utf-8",
	)
	if result.stdout.strip() == HOOKS_PATH:
		return None
	return (
		"La guardia sui commit non è attiva in questo clone: i commit non vengono "
		"controllati. Chiedi all'utente l'ok per attivarla e, solo dopo il suo ok, esegui: "
		"git config core.hooksPath " + HOOKS_PATH + " (è una modifica alla configurazione: "
		"non farla di tua iniziativa)."
	)


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	args = parser.parse_args(argv)
	repo_root = args.repo_root.resolve()

	try:
		raw = stdin_text if stdin_text is not None else sys.stdin.read()
		session_id = json.loads(raw or "{}").get("session_id", "")

		entries = load_inventory(repo_root / INVENTORY_DIR)
		decision = build_decision(check_uncatalogued_markers(entries, repo_root))
		hooks_problem = hooks_path_problem(repo_root)
		if hooks_problem:
			if decision is None:
				decision = {"decision": "block", "reason": hooks_problem}
			else:
				decision["reason"] += " " + hooks_problem
		if decision is None:
			return 0

		git_dir = Git(repo_root).git_dir()
		if not git_dir.is_absolute():
			git_dir = repo_root / git_dir
		sentinel = git_dir / SENTINEL_NAME
		if sentinel.is_file() and sentinel.read_text(encoding="utf-8").strip() == session_id:
			return 0
		sentinel.write_text(session_id, encoding="utf-8")

		print(json.dumps(decision, ensure_ascii=False))
	except Exception:
		return 0
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
