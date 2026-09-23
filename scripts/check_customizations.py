#!/usr/bin/env python3
"""Check the repository against the customization inventory.

Runs the four textual drift checks and reports what no longer matches what the
inventory declares. Standard library only, no Frappe, no bench, no site: this
is meant to answer in seconds right after an upstream merge.

Exit codes: 0 intact (warnings allowed), 1 drift found, 2 inventory malformed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the repository root,
# so the absolute imports below would not resolve. Prepend the root ourselves and
# the script works from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import (  # noqa: E402
	ERROR,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
)
from scripts.customizations.model import InventoryError, load_inventory  # noqa: E402
from scripts.customizations.report import render_json, render_table  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = Path("docs/customizations")


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--repo-root",
		type=Path,
		default=DEFAULT_REPO_ROOT,
		help="repository root to check (default: the repository this script lives in)",
	)
	parser.add_argument(
		"--inventory",
		type=Path,
		default=None,
		help="inventory directory (default: <repo-root>/docs/customizations)",
	)
	parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
	parser.add_argument(
		"--list-files",
		action="store_true",
		help="print the catalogued file paths, one per line, and exit",
	)
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	inventory_dir = args.inventory or (repo_root / DEFAULT_INVENTORY)

	try:
		entries = load_inventory(inventory_dir)
	except InventoryError as exc:
		print(f"Inventario non valido: {exc}", file=sys.stderr)
		return 2

	if args.list_files:
		for path in sorted({site.file for entry in entries for site in entry.sites}):
			print(path)
		return 0

	findings = (
		check_sites(entries, repo_root)
		+ check_uncatalogued_markers(entries, repo_root)
		+ check_test_paths(entries, repo_root)
	)

	if args.json:
		print(render_json(findings, len(entries), datetime.now().isoformat(timespec="seconds")))
	else:
		print(render_table(findings, len(entries)))

	return 1 if any(f.severity == ERROR for f in findings) else 0


if __name__ == "__main__":
	raise SystemExit(main())
