"""Tests for the shared path classification and trailer parsing."""

import subprocess
import sys
import unittest
from pathlib import Path

from scripts.customizations.paths import is_exempt_path, is_our_path
from scripts.customizations.trailers import NONE_VALUE, parse_trailers

REPO_ROOT = Path(__file__).resolve().parents[2]


class PathsTest(unittest.TestCase):
	def test_our_path_is_under_our_prefixes_or_absent_from_base(self):
		base = {"frontend/src/pages/Up.vue", "apps/os_lms/x.py"}
		self.assertTrue(is_our_path("apps/os_lms/x.py", base))
		self.assertTrue(is_our_path("frontend/src/stores/new.js", base))
		self.assertFalse(is_our_path("frontend/src/pages/Up.vue", base))
		self.assertFalse(is_our_path("docs/notes.md", set()))

	def test_exempt_paths(self):
		self.assertTrue(is_exempt_path("scripts/x.py"))
		self.assertTrue(is_exempt_path("apps/os_lms/CLAUDE.md"))
		self.assertFalse(is_exempt_path("frontend/src/pages/Up.vue"))


class TrailersTest(unittest.TestCase):
	def test_parse_trailers_and_none_value(self):
		text = "fix: x\n\nbody\n\nOslms-Feature: a\nOslms-Feature: none (formattazione)\n"
		self.assertEqual(parse_trailers(text), ["a", "none (formattazione)"])
		self.assertEqual(NONE_VALUE.match("none (formattazione)").group(1), "formattazione")


class ImportTest(unittest.TestCase):
	def test_map_does_not_import_the_commit_guard_cli(self):
		probe = "import sys, scripts.customizations.attribution; print('scripts.commit_guard' in sys.modules)"
		result = subprocess.run(
			[sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, check=True
		)
		self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
	unittest.main()
