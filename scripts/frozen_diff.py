#!/usr/bin/env python3
"""Show what upstream changed in the originals that our frozen copies replaced.

A frozen copy under frontend/src/overrides/ shadows an upstream file, so a
release can change the original without any merge conflict. Given an entry
with `frozen_from`, this prints the diff of each original between that
version and `--to`. Pages of this repository are diffed in this repository;
frappe-ui components in the frappe-ui repository (`--frappe-ui-repo`).

Never fetches and never initializes a submodule: it prints the command to run.
Exit codes: 0 diff printed, 2 cannot compute it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.customizations.gitbase import Git, PlanError  # noqa: E402
from scripts.customizations.model import InventoryError, load_inventory  # noqa: E402
from scripts.customizations.paths import INVENTORY_DIR, OVERRIDES_DIR  # noqa: E402
from scripts.upstream_plan import frozen_originals  # noqa: E402

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
FRAPPE_UI_OVERRIDES = OVERRIDES_DIR + "frappe-ui/"


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--entry", required=True, help="inventory entry id")
	parser.add_argument("--to", required=True, help="target version: an lms tag, or a frappe-ui version for frappe-ui components")
	parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
	parser.add_argument("--inventory", type=Path, default=None, help="default: <repo-root>/docs/customizations")
	parser.add_argument(
		"--frappe-ui-repo", type=Path, default=None, help="frappe-ui checkout (default: <repo-root>/frappe-ui)"
	)
	return parser


def _require_tag(git: Git, tag: str, where: str, fetch_hint: str) -> None:
	try:
		git.run("rev-parse", "--verify", f"{tag}^{{commit}}")
	except PlanError:
		raise PlanError(f"Tag {tag} non trovato in {where}. Aggiornali con: {fetch_hint}")


def _frappe_ui_git(path: Path) -> Git:
	"""A Git for the frappe-ui repository, refusing an uninitialized submodule.

	An empty submodule directory silently falls through to the parent
	repository, so a plain `git -C` would diff the wrong project.
	"""
	hint = "git submodule update --init frappe-ui (oppure passa --frappe-ui-repo)"
	if not path.is_dir():
		raise PlanError(f"Repository frappe-ui non trovato in {path}. Esegui: {hint}")
	git = Git(path)
	try:
		toplevel = Path(git.run("rev-parse", "--show-toplevel").strip()).resolve()
	except PlanError:
		toplevel = None
	if toplevel != path.resolve():
		raise PlanError(f"Il sottomodulo frappe-ui non è inizializzato in {path}. Esegui: {hint}")
	return git


def diff_lms(git: Git, original: str, frozen_from: str, to: str) -> str:
	_require_tag(git, frozen_from, "questo repository", "git fetch upstream --tags")
	_require_tag(git, to, "questo repository", "git fetch upstream --tags")
	for ref in (frozen_from, to):
		if git.show(ref, original) is None:
			raise PlanError(f"{original} non esiste a {ref}")
	return git.run("diff", f"{frozen_from}:{original}", f"{to}:{original}")


def frappe_ui_tag(version: str) -> str:
	"""The frappe-ui tag of a version written with or without its leading "v"."""
	return "v" + version.removeprefix("v")


def diff_frappe_ui(git: Git, component: str, frozen_from: str, to: str) -> str:
	hint = f"git -C {git.repo_root} fetch --tags"
	old, new = frappe_ui_tag(frozen_from), frappe_ui_tag(to)
	_require_tag(git, old, "frappe-ui", hint)
	_require_tag(git, new, "frappe-ui", hint)
	if git.show(old, component) is None and git.show(new, component) is None:
		# An empty diff here would read as "nothing changed upstream".
		raise PlanError(
			f"{component} non esiste in frappe-ui né a {old} né a {new}: il percorso della copia in "
			f"{FRAPPE_UI_OVERRIDES} deve ricalcare quello del repository frappe-ui. "
			"Controlla il percorso della copia, o il nome del componente se upstream lo ha spostato."
		)
	return git.run("diff", old, new, "--", component)


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	repo_root = args.repo_root.resolve()
	try:
		entries = load_inventory(args.inventory or (repo_root / INVENTORY_DIR))
	except InventoryError as exc:
		print(f"Inventario non valido: {exc}", file=sys.stderr)
		return 2

	found = next((e for e in entries if e.id == args.entry), None)
	if found is None:
		print(f"Voce '{args.entry}' non trovata nell'inventario.", file=sys.stderr)
		return 2
	if not found.frozen_from:
		print(
			f"La voce '{args.entry}' non ha 'frozen_from': scrivi nell'inventario la versione "
			"upstream da cui è stata copiata.",
			file=sys.stderr,
		)
		return 2
	files = sorted({s.file for s in found.sites if s.file.startswith(OVERRIDES_DIR)})
	if not files:
		print(f"La voce '{args.entry}' non ha siti in {OVERRIDES_DIR}.", file=sys.stderr)
		return 2

	git = Git(repo_root)
	originals = frozen_originals(files)
	try:
		for path in files:
			if path.startswith(FRAPPE_UI_OVERRIDES):
				ui_path = args.frappe_ui_repo or (repo_root / "frappe-ui")
				ui_git = _frappe_ui_git(Path(ui_path))
				component = path[len(FRAPPE_UI_OVERRIDES) :]
				header = f"frappe-ui {component}: {frappe_ui_tag(found.frozen_from)} -> {frappe_ui_tag(args.to)}"
				diff = diff_frappe_ui(ui_git, component, found.frozen_from, args.to)
			else:
				original = next(o for o, override in originals.items() if override == path)
				header = f"{original}: {found.frozen_from} -> {args.to}"
				diff = diff_lms(git, original, found.frozen_from, args.to)
			print(f"# {header}")
			print(diff if diff else "(nessuna modifica upstream)")
	except PlanError as exc:
		print(str(exc), file=sys.stderr)
		return 2
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
