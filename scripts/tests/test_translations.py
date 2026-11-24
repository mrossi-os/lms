"""Tests for the Italian translations record (C7)."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.customization_translations import main
from scripts.customizations.checks import ERROR
from scripts.customizations.translations import (
	check_translations,
	our_translations,
	parse_po,
	read_recorded,
	write_recorded,
)

HEADER = 'msgid ""\nmsgstr ""\n"Language: it_IT\\n"\n\n'


class ParsePoTests(unittest.TestCase):
	def test_parses_multiline_msgid_and_msgstr(self):
		po = HEADER + 'msgid ""\n"Hello "\n"world"\nmsgstr ""\n"Ciao "\n"mondo"\n'
		self.assertEqual(parse_po(po), {("", "Hello world"): "Ciao mondo"})

	def test_skips_the_header(self):
		self.assertEqual(parse_po(HEADER), {})

	def test_ignores_obsolete_entries(self):
		po = HEADER + '#~ msgid "Old"\n#~ msgstr "Vecchio"\n\nmsgid "New"\nmsgstr "Nuovo"\n'
		self.assertEqual(parse_po(po), {("", "New"): "Nuovo"})

	def test_keeps_context_in_key(self):
		po = HEADER + 'msgctxt "a"\nmsgid "X"\nmsgstr "1"\n\nmsgctxt "b"\nmsgid "X"\nmsgstr "2"\n\nmsgid "X"\nmsgstr "3"\n'
		self.assertEqual(parse_po(po), {("a", "X"): "1", ("b", "X"): "2", ("", "X"): "3"})

	def test_plural_entries_keep_the_first_form_only(self):
		po = HEADER + 'msgid "One"\nmsgid_plural "Many"\n"more"\nmsgstr[0] "Uno"\nmsgstr[1] "Molti"\n'
		self.assertEqual(parse_po(po), {("", "One"): "Uno"})

	def test_unescapes_quotes_and_newlines(self):
		po = HEADER + 'msgid "Say \\"hi\\"\\n"\nmsgstr "Di\' \\"ciao\\"\\n"\n'
		self.assertEqual(parse_po(po), {("", 'Say "hi"\n'): 'Di\' "ciao"\n'})


class OurTranslationsTests(unittest.TestCase):
	def test_our_translations_are_new_or_changed_only(self):
		base = HEADER + 'msgid "A"\nmsgstr "a"\n\nmsgid "B"\nmsgstr "b"\n\nmsgid "C"\nmsgstr ""\n'
		head = (
			HEADER
			+ 'msgid "A"\nmsgstr "a"\n\nmsgid "B"\nmsgstr "b2"\n\nmsgid "C"\nmsgstr "c"\n'
			+ 'msgid "D"\nmsgstr "d"\n\nmsgid "E"\nmsgstr ""\n'
		)
		self.assertEqual(
			our_translations(base, head),
			{("", "B"): "b2", ("", "C"): "c", ("", "D"): "d"},
		)

	def test_without_a_base_everything_non_empty_is_ours(self):
		head = HEADER + 'msgid "A"\nmsgstr "a"\n\nmsgid "B"\nmsgstr ""\n'
		self.assertEqual(our_translations(None, head), {("", "A"): "a"})


class CheckTests(unittest.TestCase):
	def test_c7_flags_missing_and_changed(self):
		recorded = {("", "A"): "a", ("", "B"): "b", ("c", "D"): "d"}
		head = HEADER + 'msgid "A"\nmsgstr "a"\n\nmsgid "B"\nmsgstr "other"\n'
		findings = check_translations(recorded, head)
		self.assertEqual({f.check for f in findings}, {"C7"})
		self.assertEqual({f.severity for f in findings}, {ERROR})
		self.assertEqual(len(findings), 2)

	def test_intact_record_gives_no_findings(self):
		head = HEADER + 'msgid "A"\nmsgstr "a"\n'
		self.assertEqual(check_translations({("", "A"): "a"}, head), [])


class RecordFileTests(unittest.TestCase):
	def test_serialisation_roundtrips_awkward_strings(self):
		pairs = {("", 'q"uote\\slash\nnl\ttab'): 'r"\\\n\t', ("ctx", "é"): "è"}
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / "t.toml"
			write_recorded(path, "v2.66.0", pairs)
			base, back = read_recorded(path)
		self.assertEqual(base, "v2.66.0")
		self.assertEqual(back, pairs)


def git(root, *args):
	subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def build_repo(tmp):
	root = Path(tmp)
	git(root, "init", "-q")
	git(root, "config", "user.email", "t@t")
	git(root, "config", "user.name", "t")
	(root / "lms/locale").mkdir(parents=True)
	(root / "docs/customizations").mkdir(parents=True)
	po = root / "lms/locale/it.po"
	po.write_text(HEADER + 'msgid "A"\nmsgstr "a"\n', encoding="utf-8")
	git(root, "add", ".")
	git(root, "commit", "-qm", "base")
	git(root, "tag", "v1.0.0")
	po.write_text(HEADER + 'msgid "A"\nmsgstr "a"\n\nmsgid "B"\nmsgstr "b"\n', encoding="utf-8")
	git(root, "commit", "-qam", "ours")
	return root


def run_main(argv):
	out, err = io.StringIO(), io.StringIO()
	with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
		code = main(argv)
	return code, out.getvalue(), err.getvalue()


class CommandTests(unittest.TestCase):
	def test_write_then_check_roundtrip(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp)
			code, _, _ = run_main(["--repo-root", str(root), "--write"])
			self.assertEqual(code, 0)
			text = (root / "docs/customizations/translations-it.toml").read_text(encoding="utf-8")
			self.assertIn('generated_from = "v1.0.0"', text)
			self.assertNotIn('msgid = "A"', text)
			code, _, _ = run_main(["--repo-root", str(root), "--check"])
			self.assertEqual(code, 0)

	def test_check_fails_when_a_translation_is_lost(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp)
			run_main(["--repo-root", str(root), "--write"])
			(root / "lms/locale/it.po").write_text(HEADER + 'msgid "A"\nmsgstr "a"\n', encoding="utf-8")
			code, out, _ = run_main(["--repo-root", str(root), "--check"])
			self.assertEqual(code, 1)
			self.assertIn("C7", out)

	def test_check_exits_two_when_record_missing(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp)
			code, _, _ = run_main(["--repo-root", str(root), "--check"])
			self.assertEqual(code, 2)

	def test_detector_runs_c7_when_the_record_exists(self):
		from scripts.check_customizations import main as detector

		with tempfile.TemporaryDirectory() as tmp:
			root = build_repo(tmp)
			run_main(["--repo-root", str(root), "--write"])
			(root / "lms/locale/it.po").write_text(HEADER, encoding="utf-8")
			out = io.StringIO()
			with contextlib.redirect_stdout(out):
				code = detector(["--repo-root", str(root), "--no-base"])
			self.assertEqual(code, 1)
			self.assertIn("C7", out.getvalue())


if __name__ == "__main__":
	unittest.main()
