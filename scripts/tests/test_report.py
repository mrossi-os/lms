"""Tests for report rendering and for the command line entry point."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DETECTOR = REPO_ROOT / "scripts" / "check_customizations.py"

from scripts.check_customizations import main
from scripts.customizations.checks import ERROR, WARNING, Finding
from scripts.customizations.report import render_json, render_table

INVENTORY = """
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = "Visibile a Moderator e Docente."

  [[entries.sites]]
  file = "frontend/src/Card.vue"
  anchor = "is_docente"
"""


def build_repo(tmp, card_body):
	"""Lay out a miniature repository: inventory plus one watched source file."""
	root = Path(tmp)
	(root / "docs" / "customizations").mkdir(parents=True)
	(root / "docs" / "customizations" / "grafts.toml").write_text(INVENTORY, encoding="utf-8")
	(root / "frontend" / "src").mkdir(parents=True)
	(root / "frontend" / "src" / "Card.vue").write_text(card_body, encoding="utf-8")
	return root


def run_main(argv):
	"""Run the command line, swallowing its output, and return (exit code, output)."""
	buffer = io.StringIO()
	with contextlib.redirect_stdout(buffer):
		code = main(argv)
	return code, buffer.getvalue()


class RenderJsonTest(unittest.TestCase):
	def test_serialises_findings_with_the_documented_shape(self):
		findings = [Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x")]
		payload = json.loads(render_json(findings, entries_total=7, generated_at="2026-09-18T10:00:00"))
		self.assertEqual(payload["generated_at"], "2026-09-18T10:00:00")
		self.assertEqual(payload["entries_total"], 7)
		self.assertEqual(payload["findings"][0]["id"], "gate")
		self.assertEqual(payload["findings"][0]["check"], "C1")
		self.assertEqual(payload["findings"][0]["severity"], "error")
		self.assertEqual(payload["findings"][0]["file"], "a.vue")
		self.assertEqual(payload["findings"][0]["anchor"], "x")

	def test_serialises_an_empty_run(self):
		payload = json.loads(render_json([], entries_total=0, generated_at="2026-09-18T10:00:00"))
		self.assertEqual(payload["findings"], [])


class RenderTableTest(unittest.TestCase):
	def test_separates_errors_from_warnings(self):
		findings = [
			Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x"),
			Finding("gate", "C4", WARNING, "nessun test collegato", None, None),
		]
		text = render_table(findings, entries_total=1)
		self.assertIn("ERRORI (1)", text)
		self.assertIn("AVVISI (1)", text)
		self.assertIn("a.vue", text)
		self.assertIn("1 errori, 1 avvisi", text)

	def test_says_so_when_everything_is_intact(self):
		text = render_table([], entries_total=31)
		self.assertIn("31", text)
		self.assertIn("0 errori, 0 avvisi", text)


class MainTest(unittest.TestCase):
	def test_exits_zero_when_the_anchor_is_intact(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 0)
		self.assertIn("0 errori", output)

	def test_exits_one_when_the_anchor_is_gone(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_moderator\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 1)
		self.assertIn("C1", output)

	def test_warnings_alone_do_not_fail_the_run(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			code, output = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 0)
		self.assertIn("C4", output)

	def test_runs_as_a_standalone_script_from_any_directory(self):
		"""The documented command is `python3 scripts/check_customizations.py`.

		Running the file directly puts scripts/ on sys.path instead of the
		repository root, so without the bootstrap in the script this fails with
		ModuleNotFoundError. cwd is deliberately somewhere else.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			result = subprocess.run(
				[sys.executable, str(DETECTOR), "--repo-root", str(root)],
				capture_output=True,
				text=True,
				cwd=tmp,
			)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("Esito:", result.stdout)

	def test_exits_two_when_the_inventory_itself_is_broken(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp, "const a = is_docente\n")
			(root / "docs" / "customizations" / "grafts.toml").write_text("[[entries]\n", encoding="utf-8")
			code, _ = run_main(["--repo-root", str(root)])
		self.assertEqual(code, 2)


if __name__ == "__main__":
	unittest.main()
