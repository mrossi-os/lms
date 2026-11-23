"""Tests for the four drift checks."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.customizations.checks import (
	ERROR,
	WARNING,
	check_anchor_provenance,
	check_anchor_uniqueness,
	check_feature_links,
	check_sites,
	check_test_paths,
	check_uncatalogued_markers,
	check_uncatalogued_markers_in,
	disk_reader,
)
from scripts.customizations.features import Feature
from scripts.customizations.model import Entry, Site
from scripts.check_customizations import main


def entry(entry_id="gate", sites=(), status=None, checks=None, layer="spa-graft", feature=None):
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
		feature=feature,
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
			findings = check_sites([entry(sites=[site])], disk_reader(root))
		self.assertEqual(findings, [])

	def test_reports_c1_when_the_anchor_is_gone(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/Card.vue": "const isAdmin = is_moderator\n"})
			findings = check_sites([entry(sites=[site])], disk_reader(root))
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C1")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertEqual(findings[0].entry_id, "gate")
		self.assertEqual(findings[0].file, "src/Card.vue")
		self.assertEqual(findings[0].anchor, "is_docente")

	def test_reports_only_c2_when_the_file_is_gone(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site])], disk_reader(Path(tmp)))
		self.assertEqual([f.check for f in findings], ["C2"])

	def test_skips_entries_marked_accepted_drift(self):
		site = Site(file="src/Gone.vue", anchor="is_docente")
		with tempfile.TemporaryDirectory() as tmp:
			findings = check_sites([entry(sites=[site], status="accepted-drift")], disk_reader(Path(tmp)))
		self.assertEqual(findings, [])

	def test_checks_every_site_of_an_entry(self):
		sites = [Site(file="src/A.vue", anchor="x"), Site(file="src/B.vue", anchor="y")]
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"src/A.vue": "x", "src/B.vue": "nothing"})
			findings = check_sites([entry(sites=sites)], disk_reader(root))
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


	def test_staged_variant_checks_only_the_given_paths(self):
		files = {
			"frontend/src/Loose.vue": "// OSLMS-CUSTOM: nostro\n",
			"frontend/src/Other.vue": "// OSLMS-CUSTOM: altro\n",
			"frontend/src/notes.md": "OSLMS-CUSTOM\n",
			"lms/public/frontend/assets/index.js": "OSLMS-CUSTOM\n",
		}
		paths = {"frontend/src/Loose.vue", "frontend/src/notes.md", "lms/public/frontend/assets/index.js", "gone.vue"}
		findings = check_uncatalogued_markers_in([], paths, files.get)
		self.assertEqual([(f.check, f.file) for f in findings], [("C3", "frontend/src/Loose.vue")])


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


def feature_card(feature_id="live-class"):
	return Feature(
		id=feature_id,
		title="t",
		status="active",
		summary="s",
		why="w",
		behaviour=("b",),
		areas=("a",),
		upstream_watch=("u",),
		history=({"date": "2026-11-01"},),
	)


class CheckFeatureLinksTest(unittest.TestCase):
	def test_c8_warns_on_entry_without_feature_when_not_strict(self):
		findings = check_feature_links([entry()], {"live-class": feature_card()}, strict=False)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C8")
		self.assertEqual(findings[0].severity, WARNING)
		self.assertEqual(findings[0].entry_id, "gate")

	def test_c8_errors_on_unknown_feature_when_strict(self):
		findings = check_feature_links([entry(feature="ghost")], {"live-class": feature_card()}, strict=True)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].check, "C8")
		self.assertEqual(findings[0].severity, ERROR)
		self.assertIn("ghost", findings[0].message)

	def test_c8_skips_accepted_drift(self):
		findings = check_feature_links([entry(status="accepted-drift")], {}, strict=True)
		self.assertEqual(findings, [])

	def test_c8_accepts_a_known_feature(self):
		findings = check_feature_links([entry(feature="live-class")], {"live-class": feature_card()}, strict=True)
		self.assertEqual(findings, [])


class CheckAnchorProvenanceTest(unittest.TestCase):
	def test_c5_flags_anchor_also_in_base(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		read = {"src/Card.vue": "a is_docente b"}.get
		read_base = {"src/Card.vue": "upstream is_docente"}.get
		findings = check_anchor_provenance([entry(sites=[site])], read, read_base)
		self.assertEqual([f.check for f in findings], ["C5"])
		self.assertEqual(findings[0].severity, WARNING)
		self.assertEqual(findings[0].file, "src/Card.vue")
		self.assertEqual(findings[0].anchor, "is_docente")

	def test_c5_ignores_anchor_only_ours(self):
		site = Site(file="src/Card.vue", anchor="is_docente")
		read = {"src/Card.vue": "a is_docente b"}.get
		read_base = {"src/Card.vue": "upstream code"}.get
		self.assertEqual(check_anchor_provenance([entry(sites=[site])], read, read_base), [])

	def test_c5_skips_file_absent_in_base(self):
		site = Site(file="src/New.vue", anchor="is_docente")
		read = {"src/New.vue": "is_docente"}.get
		self.assertEqual(check_anchor_provenance([entry(sites=[site])], read, {}.get), [])


class CheckAnchorUniquenessTest(unittest.TestCase):
	def test_c6_flags_anchor_found_twice(self):
		site = Site(file="src/Card.vue", anchor="wrap")
		read = {"src/Card.vue": "wrap one\nwrap two"}.get
		findings = check_anchor_uniqueness([entry(sites=[site])], read)
		self.assertEqual([f.check for f in findings], ["C6"])
		self.assertEqual(findings[0].severity, ERROR)

	def test_c6_accepts_unique_anchor(self):
		site = Site(file="src/Card.vue", anchor="wrap")
		read = {"src/Card.vue": "wrap once"}.get
		self.assertEqual(check_anchor_uniqueness([entry(sites=[site])], read), [])


class ReaderTest(unittest.TestCase):
	def test_check_sites_reads_through_reader(self):
		site = Site(file="virtual/File.vue", anchor="marker")
		self.assertEqual(check_sites([entry(sites=[site])], {"virtual/File.vue": "has marker"}.get), [])
		findings = check_sites([entry(sites=[site])], {}.get)
		self.assertEqual([f.check for f in findings], ["C2"])

	def test_disk_reader_returns_none_for_a_missing_file(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = fake_repo(tmp, **{"a/b.txt": "hello"})
			read = disk_reader(root)
			self.assertEqual(read("a/b.txt"), "hello")
			self.assertIsNone(read("a/missing.txt"))


class CliBaseTest(unittest.TestCase):
	def test_cli_reports_c0_when_base_missing(self):
		with tempfile.TemporaryDirectory() as tmp:
			out = io.StringIO()
			with contextlib.redirect_stdout(out):
				main(["--repo-root", tmp, "--inventory", tmp, "--json"])
		findings = json.loads(out.getvalue())["findings"]
		c0 = [f for f in findings if f["check"] == "C0"]
		self.assertEqual(len(c0), 1)
		self.assertEqual(c0[0]["severity"], "warning")

	def test_cli_no_base_skips_c0(self):
		with tempfile.TemporaryDirectory() as tmp:
			out = io.StringIO()
			with contextlib.redirect_stdout(out):
				main(["--repo-root", tmp, "--inventory", tmp, "--no-base", "--json"])
		self.assertEqual([f for f in json.loads(out.getvalue())["findings"] if f["check"] == "C0"], [])


if __name__ == "__main__":
	unittest.main()
