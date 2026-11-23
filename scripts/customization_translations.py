#!/usr/bin/env python3
"""Record our Italian translations (--write) or check they survived (--check).

Exit codes: 0 intact or written, 1 recorded translations lost, 2 record missing
or malformed, or the upstream base cannot be computed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.checks import disk_reader  # noqa: E402
from scripts.customizations.gitbase import Git, PlanError, find_base  # noqa: E402
from scripts.customizations.translations import (  # noqa: E402
	PO_PATH,
	TRANSLATIONS_FILE,
	check_translations,
	our_translations,
	read_recorded,
	write_recorded,
)

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	mode = parser.add_mutually_exclusive_group(required=True)
	mode.add_argument("--write", action="store_true", help="regenerate the record against the base")
	mode.add_argument("--check", action="store_true", help="report recorded translations that are lost")
	parser.add_argument("--base", default=None, help="upstream release tag (default: last one merged into HEAD)")
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	head_po = disk_reader(repo_root)(PO_PATH)
	if head_po is None:
		print(f"{PO_PATH} non trovato", file=sys.stderr)
		return 2
	target = repo_root / TRANSLATIONS_FILE

	if args.write:
		git = Git(repo_root)
		try:
			base = args.base or find_base(git, "HEAD")
		except PlanError as exc:
			print(str(exc), file=sys.stderr)
			return 2
		pairs = our_translations(git.show(base, PO_PATH), head_po)
		target.parent.mkdir(parents=True, exist_ok=True)
		write_recorded(target, base, pairs)
		print(f"{len(pairs)} traduzioni nostre registrate in {TRANSLATIONS_FILE} (base {base})")
		return 0

	try:
		_, recorded = read_recorded(target)
	except (OSError, ValueError) as exc:
		print(f"Registro delle traduzioni non valido: {exc}", file=sys.stderr)
		return 2
	findings = check_translations(recorded, head_po)
	for finding in findings:
		print(f"{finding.check} {finding.message}")
	print(f"{len(recorded)} traduzioni registrate, {len(findings)} perse")
	return 1 if findings else 0


if __name__ == "__main__":
	raise SystemExit(main())
