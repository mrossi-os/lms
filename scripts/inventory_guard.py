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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import Finding, check_uncatalogued_markers  # noqa: E402
from scripts.customizations.model import load_inventory  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
SENTINEL = Path(".git") / "oslms-inventory-guard"


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


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	args = parser.parse_args(argv)
	repo_root = args.repo_root.resolve()

	try:
		raw = stdin_text if stdin_text is not None else sys.stdin.read()
		session_id = json.loads(raw or "{}").get("session_id", "")

		entries = load_inventory(repo_root / "docs" / "customizations")
		decision = build_decision(check_uncatalogued_markers(entries, repo_root))
		if decision is None:
			return 0

		sentinel = repo_root / SENTINEL
		if sentinel.is_file() and sentinel.read_text(encoding="utf-8").strip() == session_id:
			return 0
		sentinel.write_text(session_id, encoding="utf-8")

		print(json.dumps(decision, ensure_ascii=False))
	except Exception:
		return 0
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
