"""Tests for the computed customization map."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.customization_map import main
from scripts.customizations.attribution import attribute, build_map, diff_hunks, load_legacy
from scripts.customizations.gitbase import Git
from scripts.tests.gitrepo import run_git, write_files

UPSTREAM_A = "".join(f"a line {n}\n" for n in range(1, 11))
UPSTREAM_B = "keep one\nremove_me_line\nkeep two\n"


def card(feature_id, areas=()):
	"""A minimal valid feature card."""
	area_list = ", ".join(f'"{area}"' for area in areas) or '"nowhere/**"'
	return (
		f'id = "{feature_id}"\n'
		f'title = "Titolo {feature_id}"\n'
		'status = "active"\n'
		f'summary = "Sintesi {feature_id}"\n'
		'why = "perché"\n'
		'behaviour = ["fa qualcosa"]\n'
		f"areas = [{area_list}]\n"
		'upstream_watch = ["niente"]\n'
		'history = [{ date = "2026-11-23", note = "creata" }]\n'
	)


INVENTORY = """
[[entries]]
id = "live-anchor"
title = "anchor"
layer = "spa-graft"
confidence = "high"
intent = "x"
feature = "live-class"
sites = [{ file = "src/c.vue", anchor = "OSLMS live join" }]
"""

LEGACY = """
schema_version = 1

[[files]]
path = "src/e.vue"
features = ["legacy-feature"]

[[files]]
path = "src/d.vue"
features = ["legacy-feature"]
"""


class FakeFork:
	"""Upstream v1.0.0, then our branch with four commits of our own and a conflicted merge."""

	def __init__(self, root):
		self.root = Path(root)
		self.git("init", "-q", "-b", "main")
		self.commit(
			"chore(release): v1.0.0",
			**{
				"src/a.vue": UPSTREAM_A,
				"src/b.vue": UPSTREAM_B,
				"src/c.vue": "c1\nc2\n",
				"src/d.vue": "d1\n",
				"src/e.vue": "e1\n",
				"src/f.vue": "f1\n",
				"src/g.vue": "g1\ng2\n",
				"yarn.lock": "lock1\n",
				"lms/locale/it.po": "msgid one\n",
			},
		)
		self.git("tag", "v1.0.0")
		self.commit(
			"docs: catalogue",
			**{
				"docs/customizations/features/quiz-timer.toml": card("quiz-timer"),
				"docs/customizations/features/live-class.toml": card("live-class"),
				"docs/customizations/features/gestore.toml": card("gestore", ["src/d.vue", "apps/os_lms/gestore/**"]),
				"docs/customizations/features/legacy-feature.toml": card("legacy-feature"),
				"docs/customizations/features/merge-feature.toml": card("merge-feature"),
				"docs/customizations/spa-grafts.toml": INVENTORY,
				"docs/customizations/legacy-attribution.toml": LEGACY,
			},
		)
		# 1. A commit with the trailer: adds lines to a.vue, removes a line from b.vue.
		self.commit(
			"feat(quiz): timer\n\nOslms-Feature: quiz-timer",
			**{
				"src/a.vue": UPSTREAM_A.replace("a line 5\n", "a line 5\ntimer start\ntimer stop\n"),
				"src/b.vue": "keep one\nkeep two\n",
			},
		)
		# 2. Before the rule: no trailer, but the added line carries an inventory anchor.
		self.commit("fix: live join", **{"src/c.vue": "c1\nOSLMS live join button\nc2\n"})
		# 3. Before the rule: no trailer and no anchor.
		self.commit(
			"fix: assorted",
			**{
				"src/d.vue": "d1\nd gestore\n",
				"src/e.vue": "e1\ne legacy\n",
				"src/f.vue": "f1\nf orphan\n",
				"yarn.lock": "lock2\n",
				"lms/locale/it.po": "msgid two\n",
				"apps/os_lms/gestore/api.py": "x = 1\n",
			},
		)
		# 4. A conflicted merge whose resolution writes a line nobody else wrote.
		self.git("checkout", "-q", "-b", "side")
		self.commit("fix: side", **{"src/g.vue": "g1\ng side\n"})
		self.git("checkout", "-q", "main")
		self.commit("fix: main", **{"src/g.vue": "g1\ng main\n"})
		run_git(self.root, "merge", "side", "-m", "merge", check=False)
		write_files(self.root, **{"src/g.vue": "g1\ng resolved\n"})
		self.git("add", "-A")
		self.git("commit", "-q", "-m", "Merge branch 'side'\n\nOslms-Feature: merge-feature")

	def git(self, *args):
		return run_git(self.root, *args).stdout

	def commit(self, message, **files):
		write_files(self.root, **files)
		self.git("add", "-A")
		self.git("commit", "-q", "-m", message)


def hunks_of(result, feature_id):
	return result["features"][feature_id]["hunks"]


class AttributionTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		FakeFork(cls.tmp.name)
		cls.root = Path(cls.tmp.name)
		cls.result = build_map(cls.root)

	@classmethod
	def tearDownClass(cls):
		cls.tmp.cleanup()

	def test_attributes_added_lines_by_trailer(self):
		hunks = [h for h in hunks_of(self.result, "quiz-timer") if h["file"] == "src/a.vue"]
		self.assertEqual(len(hunks), 1)
		self.assertEqual(hunks[0]["source"], "trailer")
		self.assertEqual((hunks[0]["head_start"], hunks[0]["head_len"]), (6, 2))
		self.assertEqual(len(self.result["features"]["quiz-timer"]["commits"]), 1)

	def test_attributes_removed_only_hunk_by_trailer_of_removing_commit(self):
		hunks = [h for h in hunks_of(self.result, "quiz-timer") if h["file"] == "src/b.vue"]
		self.assertEqual(len(hunks), 1)
		self.assertEqual(hunks[0]["source"], "trailer")
		self.assertEqual(hunks[0]["head_len"], 0)

	def test_falls_back_to_anchor_for_commit_without_trailer(self):
		hunks = hunks_of(self.result, "live-class")
		self.assertEqual([(h["file"], h["source"]) for h in hunks], [("src/c.vue", "anchor")])

	def test_falls_back_to_area_then_legacy(self):
		gestore = self.result["features"]["gestore"]
		self.assertEqual([(h["file"], h["source"]) for h in gestore["hunks"]], [("src/d.vue", "area")])
		# Our own files under the feature's areas are listed, though not hunk-attributed.
		self.assertIn("apps/os_lms/gestore/api.py", gestore["files"])
		legacy = hunks_of(self.result, "legacy-feature")
		self.assertEqual([(h["file"], h["source"]) for h in legacy], [("src/e.vue", "legacy")])

	def test_reports_unattributed_hunk(self):
		self.assertEqual(
			self.result["unattributed"], [{"file": "src/f.vue", "head_start": 2, "head_len": 1}]
		)
		self.assertEqual(self.result["totals"]["unattributed"], 1)
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			code = main(["--repo-root", str(self.root), "--unattributed"])
		self.assertEqual(code, 0)
		self.assertIn("src/f.vue:2", out.getvalue())
		self.assertEqual(out.getvalue().strip().splitlines()[-1], "Totale non attribuiti: 1")

	def test_reads_trailers_of_a_merge_commit_that_wrote_the_line(self):
		hunks = hunks_of(self.result, "merge-feature")
		self.assertEqual([(h["file"], h["source"]) for h in hunks], [("src/g.vue", "trailer")])

	def test_excludes_lock_and_translation_files(self):
		files = {h["file"] for feature in self.result["features"].values() for h in feature["hunks"]}
		files |= {h["file"] for h in self.result["unattributed"]}
		self.assertNotIn("yarn.lock", files)
		self.assertNotIn("lms/locale/it.po", files)
		self.assertEqual(self.result["totals"]["hunks"], 7)

	def test_feature_filter(self):
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			code = main(["--repo-root", str(self.root), "--json", "--feature", "quiz-timer"])
		self.assertEqual(code, 0)
		data = json.loads(out.getvalue())
		self.assertEqual(list(data["features"]), ["quiz-timer"])
		self.assertEqual(data["base"], "v1.0.0")


MIXED_INVENTORY = """
[[entries]]
id = "z-anchor"
title = "anchor"
layer = "spa-graft"
confidence = "high"
intent = "x"
feature = "feat-z"
sites = [{ file = "src/n.vue", anchor = "ANCHOR_Z" }]
"""


class MixedFork(FakeFork):
	"""Hunks written by commits with and without the trailer (design §5.5, per commit)."""

	def __init__(self, root):
		self.root = Path(root)
		self.git("init", "-q", "-b", "main")
		self.commit(
			"chore(release): v1.0.0",
			**{"src/m.vue": "m1\nm2\nm3\n", "src/n.vue": "n1\nn2\n", "lms/lms/test_api.py": "def test_a():\n\tpass\n"},
		)
		self.git("tag", "v1.0.0")
		self.commit(
			"docs: catalogue",
			**{
				"docs/customizations/features/feat-x.toml": card("feat-x"),
				"docs/customizations/features/feat-y.toml": card("feat-y", ["src/m.vue"]),
				"docs/customizations/features/feat-z.toml": card("feat-z"),
				"docs/customizations/spa-grafts.toml": MIXED_INVENTORY,
			},
		)
		self.commit("feat: x\n\nOslms-Feature: feat-x", **{"src/m.vue": "m1\nx line\nm2\nm3\n"})
		self.commit("fix: y", **{"src/m.vue": "m1\nx line\ny line\nm2\nm3\n"})
		self.commit("fix: x end\n\nOslms-Feature: feat-x", **{"src/m.vue": "m1\nx line\ny line\nm2\nm3\nx end\n"})
		self.commit("fix: z\n\nOslms-Feature: feat-x", **{"src/n.vue": "n1\nANCHOR_Z here\nn2\n"})
		self.commit(
			"test: ours\n\nOslms-Feature: feat-x",
			**{"lms/lms/test_api.py": "def test_a():\n\tpass\n\n\ndef test_ours():\n\tpass\n"},
		)


def features_of(result, file, head_start):
	return sorted(
		fid
		for fid, feature in result["features"].items()
		for h in feature["hunks"]
		if h["file"] == file and h["head_start"] == head_start
	)


class MixedAttributionTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		MixedFork(cls.tmp.name)
		cls.result = build_map(Path(cls.tmp.name))

	@classmethod
	def tearDownClass(cls):
		cls.tmp.cleanup()

	def test_mixed_hunk_unites_trailer_and_fallback_of_untrailered_lines(self):
		# Line 2 comes from the feat-x commit, line 3 from a commit without trailer: area feat-y.
		self.assertEqual(features_of(self.result, "src/m.vue", 2), ["feat-x", "feat-y"])
		sources = {
			fid: h["source"]
			for fid, f in self.result["features"].items()
			for h in f["hunks"]
			if h["file"] == "src/m.vue" and h["head_start"] == 2
		}
		self.assertEqual(sources, {"feat-x": "trailer", "feat-y": "area"})

	def test_fully_trailered_hunk_skips_area(self):
		self.assertEqual(features_of(self.result, "src/m.vue", 6), ["feat-x"])

	def test_anchor_is_always_added(self):
		self.assertEqual(features_of(self.result, "src/n.vue", 2), ["feat-x", "feat-z"])

	def test_includes_modified_upstream_test_files(self):
		self.assertIn("lms/lms/test_api.py", self.result["features"]["feat-x"]["files"])


class RefCatalogueTest(unittest.TestCase):
	"""With --ref, cards, inventory and legacy map are read at that ref."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.fork = MixedFork(self.tmp.name)
		self.root = Path(self.tmp.name)
		self.fork.git("tag", "snap")
		self.fork.git("rm", "-q", "docs/customizations/features/feat-y.toml")
		self.fork.commit(
			"docs: rename card",
			**{
				"docs/customizations/features/feat-w.toml": card("feat-w", ["src/m.vue"]),
				"docs/customizations/legacy-attribution.toml": '[[files]]\npath = "src/m.vue"\nfeatures = ["feat-w"]\n',
			},
		)
		# A commit on top so that "snap" and HEAD differ in history, not only in the catalogue.
		self.fork.commit("docs: note", **{"docs/note.md": "n\n"})

	def test_reads_the_catalogue_at_the_ref(self):
		result = build_map(self.root, "snap")
		self.assertIn("feat-y", result["features"])
		self.assertNotIn("feat-w", result["features"])
		self.assertEqual(features_of(result, "src/m.vue", 2), ["feat-x", "feat-y"])

	def test_head_reads_the_working_tree(self):
		write_files(self.root, **{"docs/customizations/features/feat-v.toml": card("feat-v")})
		result = build_map(self.root)
		self.assertIn("feat-w", result["features"])
		self.assertIn("feat-v", result["features"])
		self.assertNotIn("feat-y", result["features"])


class AttributeFunctionTest(unittest.TestCase):
	def test_attribute_without_shared_history(self):
		with tempfile.TemporaryDirectory() as tmp:
			FakeFork(tmp)
			git = Git(Path(tmp))
			[hunk] = diff_hunks(git, "v1.0.0", "HEAD", ["src/a.vue"])
			self.assertEqual(hunk.added, ["timer start", "timer stop"])
			result = attribute(
				hunk,
				git=git,
				base="v1.0.0",
				ref="HEAD",
				features={},
				entries=[],
				legacy={},
				release_tags=git.release_tags(),
			)
			self.assertEqual(result, (["quiz-timer"], "trailer"))


class LegacyTest(unittest.TestCase):
	def test_missing_file_is_empty(self):
		self.assertEqual(load_legacy(Path("/nonexistent/legacy.toml")), {})


if __name__ == "__main__":
	unittest.main()
