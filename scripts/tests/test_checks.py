"""Tests for the four drift checks."""

import tempfile
import unittest
from pathlib import Path

from scripts.customizations.checks import (
	ERROR,
	WARNING,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
)
from scripts.customizations.model import Entry, Site


def entry(entry_id="gate", sites=(), status=None, checks=None, layer="spa-graft"):
	"""Build an Entry directly, bypassing the TOML layer."""
	return Entry(
		id=entry_id,
		title="t",
		layer=layer,
		confidence="high",
		intent="i",
		source="test.toml",
		sites=tuple(sites),
		checks=checks or {},
		status=status,
	)


def fake_repo(directory, **files):
	"""Create files under `directory`; keys are slash-separated relative paths."""
	for relative, body in files.items():
		path = Path(directory) / relative
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(body, encoding="utf-8")
	return Path(directory)


class CheckSitesTest(unittest.TestCase):
	def test_reports_nothing_when_the_anchor_is_present(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/Card.vue": "const isAdmin = is_docente || false\n"})
			findings = check_sites([entry(sites=[site])], root)
		self.assertEqual(findings, [])

	def test_reports_c1_when_the_anchor_is_gone(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/Card.vue": "const isAdmin = is_moderator\n"})
			findings = check_sites([entry(sites=[site])], root)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C1")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertEqual(findings[0].entry_id, "gate")
		self.assertEqual(findings[0].file, "src/Card.vue")
		self.assertEqual(findings[0].anchor, "is_docente")

	def test_reports_only_c2_when_the_file_is_gone(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site])], Path(tmp))
		self.assertEqual([f.check for f in findings], ["C2"])

	def test_skips_entries_marked_accepted_drift(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site], status="accepted-drift")], Path(tmp))
		self.assertEqual(findings, [])

	def test_checks_every_site_of_an_entry(self):
		sites = [Site(file="src/A.vue", anchor="x"), Site(file="src/B.vue", anchor="y")]
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/A.vue": "x", "src/B.vue": "nothing"})
			findings = check_sites([entry(sites=sites)], root)
		self.assertEqual([f.file for f in findings], ["src/B.vue"])


class CheckUncataloguedMarkersTest(unittest.TestCase):
	def test_reports_a_marked_file_that_no_entry_mentions(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/Loose.vue": "// OSLMS-CUSTOM: nostro\n"})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C3")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertEqual(findings[0].file, "frontend/src/Loose.vue")

	def test_stays_silent_when_the_file_is_catalogued(self):
		site = Site(file="frontend/src/Loose.vue", anchor="OSLMS-CUSTOM")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/Loose.vue": "// OSLMS-CUSTOM: nostro\n"})
			findings = check_uncatalogued_markers([entry(sites=[site])], root)
		self.assertEqual(findings, [])

	def test_ignores_generated_bundles(self):
		marked = "// OSLMS-CUSTOM\n"
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"lms/public/frontend/assets/index-abc.js": marked})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(findings, [])

	def test_ignores_unwatched_suffixes(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"frontend/src/notes.md": "OSLMS-CUSTOM\n"})
			findings = check_uncatalogued_markers([], root)
		self.assertEqual(findings, [])


class CheckTestPathsTest(unittest.TestCase):
	def test_warns_when_an_entry_has_no_test_at_all(self):
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_test_paths([entry()], Path(tmp))
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C4")
		self.assertEqual(findings[0].severity, WARNING)

	def test_warns_when_a_declared_test_file_is_missing(self):
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_test_paths([entry(checks={"unit": "t/missing.test.ts"})], Path(tmp))
		self.assertEqual(len(findings), 1)
		self.assertIn("unit", findings[0].message)
		self.assertEqual(findings[0].file, "t/missing.test.ts")

	def test_stays_silent_when_the_declared_test_exists(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"t/present.test.ts": "it('x', () => {})\n"})
			findings = check_test_paths([entry(checks={"unit": "t/present.test.ts"})], root)
		self.assertEqual(findings, [])


if __name__ == "__main__":
	unittest.main()
