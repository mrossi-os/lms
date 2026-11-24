#!/usr/bin/env python3
"""Show every difference from upstream, grouped by the feature it serves.

For a ref (default HEAD) and the last upstream release merged into it, each
upstream file that differs is split into hunks and each hunk is attributed to
features of the catalogue (design §5.5). Hunks nobody claims are listed: that
is the number to bring to zero before an upstream upgrade, together with our
own files no card covers; the residue the user approved is shown apart.

Report only: exit code 0 whatever the map says; 2 when it cannot be computed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.attribution import build_map  # noqa: E402
from scripts.customizations.gitbase import PlanError  # noqa: E402
from scripts.customizations.model import InventoryError  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_LABELS = {"trailer": "riga Oslms-Feature", "anchor": "ancora", "area": "area", "legacy": "mappa storica"}


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT, help=argparse.SUPPRESS)
	parser.add_argument("--ref", default="HEAD", help="ref da mappare (default: HEAD)")
	parser.add_argument("--json", action="store_true", help="uscita JSON, per la skill")
	parser.add_argument("--feature", metavar="ID", help="mostra una sola funzionalità")
	parser.add_argument(
		"--unattributed",
		action="store_true",
		help="mostra solo i blocchi non attribuiti, i file nostri non coperti e il residuo approvato",
	)
	return parser


def _where(hunk: dict) -> str:
	start, length = hunk["head_start"], hunk["head_len"]
	if length == 0:
		return f"{hunk['file']}:{start} (solo righe rimosse)"
	if length == 1:
		return f"{hunk['file']}:{start}"
	return f"{hunk['file']}:{start}-{start + length - 1}"


def render_unattributed(data: dict) -> str:
	totals = data["totals"]
	lines = ["Non attribuiti:"]
	lines += [f"  {_where(hunk)}" for hunk in data["unattributed"]] or ["  nessuno"]
	lines.append(f"Totale non attribuiti: {totals['unattributed']}")
	lines += ["", "File nostri non coperti (nessuna scheda, mappa storica o residuo):"]
	lines += [f"  {path}" for path in data["uncovered_files"]] or ["  nessuno"]
	lines.append(f"Totale file nostri non coperti: {totals['uncovered_files']}")
	lines += ["", "Residuo approvato (ammesso, mostrato a parte):"]
	residue = [f"  {_where(hunk)} — {hunk['reason']} (ok del {hunk['approved']})" for hunk in data["residue"]]
	residue += [f"  {item['file']} — {item['reason']} (ok del {item['approved']})" for item in data["residue_files"]]
	lines += residue or ["  nessuno"]
	lines.append(f"Totale residuo approvato: blocchi {totals['residue']}, file {totals['residue_files']}")
	return "\n".join(lines)


def render_feature(feature_id: str, feature: dict) -> str:
	lines = [f"{feature_id} — {feature['title'] or '(scheda mancante)'}"]
	if feature["summary"]:
		lines.append(f"  {feature['summary']}")
	lines.append(f"  File ({len(feature['files'])}):")
	lines += [f"    {path}" for path in feature["files"]]
	lines.append(f"  Blocchi ({len(feature['hunks'])}):")
	lines += [f"    {_where(hunk)} [{SOURCE_LABELS[hunk['source']]}]" for hunk in feature["hunks"]]
	if feature["commits"]:
		lines.append(f"  Commit: {', '.join(sha[:10] for sha in feature['commits'])}")
	return "\n".join(lines)


def render_table(data: dict) -> str:
	totals = data["totals"]
	by_source = ", ".join(f"{SOURCE_LABELS[s]} {n}" for s, n in totals["by_source"].items())
	lines = [
		f"Mappa delle personalizzazioni di {data['ref']} rispetto a {data['base']}",
		f"{totals['hunks']} blocchi in {totals['files']} file upstream; attribuiti {totals['attributed']} ({by_source})",
		"",
	]
	width = max((len(fid) for fid in data["features"]), default=0)
	for feature_id, feature in data["features"].items():
		title = feature["title"] or "(scheda mancante)"
		lines.append(
			f"{feature_id.ljust(width)}  {title}  — file {len(feature['files'])}, blocchi {len(feature['hunks'])}"
		)
	if totals["unknown_features"]:
		lines += ["", "Funzionalità senza scheda: " + ", ".join(totals["unknown_features"])]
	lines += ["", render_unattributed(data)]
	return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	try:
		data = build_map(args.repo_root.resolve(), args.ref)
	except (PlanError, InventoryError) as exc:
		print(f"Mappa non calcolabile: {exc}", file=sys.stderr)
		return 2

	if args.feature:
		if args.feature not in data["features"]:
			print(f"Funzionalità sconosciuta: {args.feature}", file=sys.stderr)
			return 2
		data["features"] = {args.feature: data["features"][args.feature]}

	if args.json:
		print(json.dumps(data, ensure_ascii=False, indent=2))
	elif args.unattributed:
		print(render_unattributed(data))
	elif args.feature:
		print(render_feature(args.feature, data["features"][args.feature]))
	else:
		print(render_table(data))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
