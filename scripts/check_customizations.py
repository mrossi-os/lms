#!/usr/bin/env python3
"""Check the repository against the customization inventory.

Runs the textual drift checks and reports what no longer matches what the
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
	WARNING,
	Finding,
	check_anchor_provenance,
	check_anchor_uniqueness,
	check_feature_links,
	check_frozen_base,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
	disk_reader,
)
from scripts.customizations.gitbase import Git, PlanError, find_base  # noqa: E402
from scripts.customizations.features import load_features  # noqa: E402
from scripts.customizations.model import InventoryError, load_inventory  # noqa: E402
from scripts.customizations.paths import INVENTORY_DIR, STRICT_FEATURES_FLAG  # noqa: E402
from scripts.customizations.report import render_json, render_table  # noqa: E402
from scripts.customizations.translations import (  # noqa: E402
	PO_PATH,
	TRANSLATIONS_FILE,
	check_translations,
	read_recorded,
)

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = Path(INVENTORY_DIR)


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
	parser.add_argument(
		"--base",
		default=None,
		help="upstream release tag to compare against (default: the last one merged into HEAD)",
	)
	parser.add_argument(
		"--no-base",
		action="store_true",
		help="skip the checks that need the upstream base (C5), without warning",
	)
	return parser


def resolve_base(repo_root: Path, requested: str | None) -> tuple[Git, str]:
	"""The git handle and the base tag, or PlanError when either is unavailable."""
	git = Git(repo_root)
	git.git_dir()
	if requested:
		git.run("rev-parse", "--verify", f"{requested}^{{commit}}")
		return git, requested
	return git, find_base(git, "HEAD")


def translation_findings(repo_root: Path, read) -> list[Finding]:
	"""C7, when the recorded translations exist. It needs no base: it compares the record with it.po."""
	record = repo_root / TRANSLATIONS_FILE
	if not record.is_file():
		return []
	head_po = read(PO_PATH)
	try:
		_, recorded = read_recorded(record)
	except (OSError, ValueError) as exc:
		return [Finding("translations", "C7", ERROR, f"registro traduzioni non valido: {exc}", file=TRANSLATIONS_FILE)]
	if head_po is None:
		return [Finding("translations", "C7", ERROR, f"{PO_PATH} non trovato", file=PO_PATH)]
	return check_translations(recorded, head_po)


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	inventory_dir = args.inventory or (repo_root / DEFAULT_INVENTORY)

	try:
		entries = load_inventory(inventory_dir)
		features = load_features(inventory_dir / "features")
	except InventoryError as exc:
		print(f"Inventario non valido: {exc}", file=sys.stderr)
		return 2

	if args.list_files:
		for path in sorted({site.file for entry in entries for site in entry.sites}):
			print(path)
		return 0

	read = disk_reader(repo_root)
	base_findings: list[Finding] = []
	if not args.no_base:
		try:
			git, base = resolve_base(repo_root, args.base)
		except PlanError:
			base_findings.append(
				Finding("-", "C0", WARNING, "base upstream non disponibile: C5 saltato")
			)
		else:
			base_findings += check_anchor_provenance(entries, read, lambda path: git.show(base, path))

	findings = (
		check_sites(entries, read)
		+ check_anchor_uniqueness(entries, read)
		+ base_findings
		+ check_uncatalogued_markers(entries, repo_root)
		+ check_test_paths(entries, repo_root)
		+ check_frozen_base(entries)
		+ check_feature_links(entries, features, strict=(repo_root / STRICT_FEATURES_FLAG).is_file())
	)

	findings += translation_findings(repo_root, read)

	if args.json:
		print(render_json(findings, len(entries), datetime.now().isoformat(timespec="seconds")))
	else:
		print(render_table(findings, len(entries)))

	return 1 if any(f.severity == ERROR for f in findings) else 0


if __name__ == "__main__":
	raise SystemExit(main())
