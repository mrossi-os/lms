"""Tests for the Stop-hook inventory guard."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.customizations.checks import ERROR, WARNING, Finding
from scripts.inventory_guard import build_decision, main


def marker_finding(file="frontend/src/Loose.vue"):
	return Finding("-", "C3", ERROR, "file con marcatore OSLMS-CUSTOM non censito", file, None)


class BuildDecisionTest(unittest.TestCase):
	def test_returns_none_when_everything_is_catalogued(self):
		self.assertIsNone(build_decision([]))

	def test_ignores_findings_that_are_not_c3(self):
		other = Finding("gate", "C1", ERROR, "ancora non trovata nel file", "a.vue", "x")
		warning = Finding("gate", "C4", WARNING, "nessun test collegato", None, None)
		self.assertIsNone(build_decision([other, warning]))

	def test_blocks_and_names_every_uncatalogued_file(self):
		decision = build_decision([marker_finding("a.vue"), marker_finding("b.vue")])
		self.assertEqual(decision["decision"], "block")
		self.assertIn("a.vue", decision["reason"])
		self.assertIn("b.vue", decision["reason"])
		self.assertIn("spa-grafts.toml", decision["reason"])

	def test_names_each_file_once(self):
		decision = build_decision([marker_finding("a.vue"), marker_finding("a.vue")])
		self.assertEqual(decision["reason"].count("a.vue"), 1)


def guard_repo(tmp, marked):
	"""A repository with an empty inventory and optionally one marked file."""
	root = Path(tmp)
	(root / "docs" / "customizations").mkdir(parents=True)
	(root / ".git").mkdir()
	(root / "frontend" / "src").mkdir(parents=True)
	body = "// OSLMS-CUSTOM: nostro\n" if marked else "const a = 1\n"
	(root / "frontend" / "src" / "Loose.vue").write_text(body, encoding="utf-8")
	return root


def run_guard(root, session_id):
	"""Run the guard the way the hook does and return its stdout."""
	import contextlib
	import io

	payload = json.dumps({"session_id": session_id})
	buffer = io.StringIO()
	with contextlib.redirect_stdout(buffer):
		code = main(["--repo-root", str(root)], stdin_text=payload)
	return code, buffer.getvalue().strip()


class MainTest(unittest.TestCase):
	def test_stays_silent_when_nothing_is_uncatalogued(self):
		with tempfile.TemporaryDirectory() as tmp:
			code, output = run_guard(guard_repo(tmp, marked=False), "s1")
		self.assertEqual(code, 0)
		self.assertEqual(output, "")

	def test_emits_a_block_decision_for_an_uncatalogued_marker(self):
		with tempfile.TemporaryDirectory() as tmp:
			code, output = run_guard(guard_repo(tmp, marked=True), "s1")
		self.assertEqual(code, 0)
		payload = json.loads(output)
		self.assertEqual(payload["decision"], "block")
		self.assertIn("Loose.vue", payload["reason"])

	def test_blocks_only_once_per_session(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			first_code, first = run_guard(root, "s1")
			second_code, second = run_guard(root, "s1")
		self.assertEqual((first_code, second_code), (0, 0))
		self.assertNotEqual(first, "")
		self.assertEqual(second, "")

	def test_blocks_again_in_a_new_session(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			run_guard(root, "s1")
			_, second = run_guard(root, "s2")
		self.assertNotEqual(second, "")

	def test_never_blocks_when_the_inventory_is_broken(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = guard_repo(tmp, marked=True)
			(root / "docs" / "customizations" / "x.toml").write_text("[[entries]\n", encoding="utf-8")
			code, output = run_guard(root, "s1")
		self.assertEqual(code, 0)
		self.assertEqual(output, "")


if __name__ == "__main__":
	unittest.main()
