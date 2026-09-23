"""Tests for the upstream upgrade planner."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.upstream_plan import (
	Release,
	breaking_changes,
	build_plan,
	dependency_version,
	frozen_originals,
	is_customization_candidate,
	main,
	parse_name_status,
	parse_version,
	recommend,
	sort_release_tags,
)


def release(tag, frappe_ui="1.0", frappe_ui_from=None, breaking=()):
	return Release(
		tag=tag,
		previous="-",
		date="2026-01-01",
		commits=1,
		files=1,
		frappe_ui=frappe_ui,
		frappe_ui_from=frappe_ui_from,
		breaking=list(breaking),
	)


class VersionTest(unittest.TestCase):
	def test_parses_release_tags_only(self):
		self.assertEqual(parse_version("v2.58.1"), (2, 58, 1))
		self.assertIsNone(parse_version("ve1.0.1"))
		self.assertIsNone(parse_version("assets-develop"))
		self.assertIsNone(parse_version("v2.58.1-beta"))

	def test_sorts_numerically_and_drops_foreign_tags(self):
		tags = ["v2.10.0", "vi1.0.7", "v2.9.0", "v2.58.1", "assets-main", "v2.58.0"]
		self.assertEqual(sort_release_tags(tags), ["v2.9.0", "v2.10.0", "v2.58.0", "v2.58.1"])


class BreakingChangesTest(unittest.TestCase):
	def test_finds_the_marker_in_a_merge_commit_body(self):
		message = "Merge pull request #2710 from someone/branch\n\nfeat(quiz)!: rebuild quiz authoring\n"
		self.assertEqual(breaking_changes([message]), ["feat(quiz)!: rebuild quiz authoring"])

	def test_finds_the_marker_without_scope_and_the_footer(self):
		messages = ["feat!: drop the old api", "fix: x\n\nBREAKING CHANGE: the api is gone"]
		self.assertEqual(
			breaking_changes(messages),
			["feat!: drop the old api", "BREAKING CHANGE: the api is gone"],
		)

	def test_ignores_ordinary_commits_and_stray_exclamation_marks(self):
		messages = ["feat(quiz): a normal feature", "fix: handle x != y!", "Merge pull request #1\n\nfix: it"]
		self.assertEqual(breaking_changes(messages), [])

	def test_counts_the_same_title_once(self):
		title = "fix(lesson)!: stop lesson content being destroyed on save"
		self.assertEqual(breaking_changes([title, f"Merge pull request #2709\n\n{title}"]), [title])


class DependencyVersionTest(unittest.TestCase):
	def test_reads_caret_and_exact_versions(self):
		self.assertEqual(
			dependency_version('{"dependencies": {"frappe-ui": "^1.0.0-beta.7"}}'), "^1.0.0-beta.7"
		)
		self.assertEqual(
			dependency_version('{"devDependencies": {"frappe-ui": "1.0.0-beta.29"}}'), "1.0.0-beta.29"
		)

	def test_returns_none_when_absent_or_unreadable(self):
		self.assertIsNone(dependency_version('{"dependencies": {"vue": "3"}}'))
		self.assertIsNone(dependency_version("{not json"))
		self.assertIsNone(dependency_version(None))


class NameStatusTest(unittest.TestCase):
	def test_counts_a_rename_once_but_keeps_both_paths(self):
		raw = "M\0a.vue\0R087\0old.vue\0new.vue\0D\0gone.py\0"
		count, paths = parse_name_status(raw)
		self.assertEqual(count, 3)
		self.assertEqual(paths, {"a.vue", "old.vue", "new.vue", "gone.py"})

	def test_handles_an_empty_diff(self):
		self.assertEqual(parse_name_status(""), (0, set()))


class CandidateTest(unittest.TestCase):
	def test_excludes_translations_tests_and_generated_files(self):
		for path in (
			"lms/locale/it.po",
			"lms/translations/it.csv",
			"frontend/src/tests/video.test.ts",
			"lms/lms/doctype/lms_quiz/test_lms_quiz.py",
			"cypress/e2e/course.cy.js",
			"frontend/yarn.lock",
			"frontend/components.d.ts",
		):
			self.assertFalse(is_customization_candidate(path), path)

	def test_keeps_source_and_config_files(self):
		for path in ("frontend/src/pages/Lesson.vue", "lms/lms/permissions.py", "frontend/package.json"):
			self.assertTrue(is_customization_candidate(path), path)


class FrozenOriginalsTest(unittest.TestCase):
	def test_maps_an_lms_page_override_to_its_original(self):
		mapping = frozen_originals(
			[
				"frontend/src/overrides/pages/Courses/CourseOverview.vue",
				"frontend/src/overrides/frappe-ui/src/components/Switch/Switch.vue",
			]
		)
		self.assertEqual(
			mapping["frontend/src/pages/Courses/CourseOverview.vue"],
			"frontend/src/overrides/pages/Courses/CourseOverview.vue",
		)
		self.assertIn("frontend/src/frappe-ui/src/components/Switch/Switch.vue", mapping)


class RecommendTest(unittest.TestCase):
	def test_nothing_to_do(self):
		self.assertIsNone(recommend([])["tag"])

	def test_stops_just_before_the_first_dependency_bump(self):
		releases = [release("v1.0.1"), release("v1.1.0", "2.0", "1.0"), release("v1.2.0", "2.0")]
		rec = recommend(releases)
		self.assertEqual(rec["tag"], "v1.0.1")
		self.assertIn("v1.1.0", rec["reason"])

	def test_stops_just_before_the_first_declared_break(self):
		releases = [release("v1.0.1"), release("v1.0.2"), release("v1.1.0", breaking=["feat!: x"])]
		self.assertEqual(recommend(releases)["tag"], "v1.0.2")

	def test_isolates_a_risky_first_release(self):
		rec = recommend([release("v1.1.0", "2.0", "1.0"), release("v1.2.0", "2.0")])
		self.assertEqual(rec["tag"], "v1.1.0")
		self.assertIn("da sola", rec["reason"])

	def test_goes_to_the_newest_when_nothing_is_risky(self):
		self.assertEqual(recommend([release("v1.0.1"), release("v1.0.2")])["tag"], "v1.0.2")


def package_json(version):
	return json.dumps({"dependencies": {"frappe-ui": version}})


class FakeUpstream:
	"""A throwaway repository shaped like this fork: upstream tags plus our branch."""

	def __init__(self, root):
		self.root = Path(root)
		self.git("init", "-q", "-b", "main")

	def git(self, *args):
		return subprocess.run(
			[
				"git",
				"-c",
				"user.name=t",
				"-c",
				"user.email=t@t",
				"-c",
				"commit.gpgsign=false",
				"-c",
				"tag.gpgsign=false",
				"-c",
				"core.hooksPath=/dev/null",
				*args,
			],
			cwd=self.root,
			check=True,
			capture_output=True,
			text=True,
		).stdout

	def commit(self, message, **files):
		for relative, body in files.items():
			path = self.root / relative
			path.parent.mkdir(parents=True, exist_ok=True)
			path.write_text(body, encoding="utf-8")
		self.git("add", "-A")
		self.git("commit", "-q", "--allow-empty", "-m", message)


def build_fake_fork(tmp):
	"""Upstream v0.9.0 → v1.0.0 → v1.0.1 → v1.1.0; our branch forks at v1.0.0.

	Our branch customizes a.vue without a marker, b.vue with one, c.vue inside
	the inventory, adds an override of pages/Over.vue, carries our own tag and
	merges an untagged upstream/develop commit that touches d.vue.
	"""
	repo = FakeUpstream(tmp)
	repo.commit("chore: start", **{"frontend/package.json": package_json("^1.0.0-beta.7")})
	repo.git("tag", "v0.9.0")
	repo.commit(
		"chore(release): v1.0.0",
		**{
			"src/a.vue": "a\n",
			"src/b.vue": "b\n",
			"src/c.vue": "c\n",
			"src/d.vue": "d\n",
			"src/tests/a.test.js": "t\n",
			"frontend/src/pages/Over.vue": "over\n",
		},
	)
	repo.git("tag", "v1.0.0")

	repo.git("checkout", "-q", "-b", "develop")
	repo.commit("fix: upstream develop work", **{"src/d.vue": "d upstream\n"})
	repo.git("update-ref", "refs/remotes/upstream/develop", "HEAD")

	repo.git("checkout", "-q", "main")
	repo.commit(
		"fix: touch everything",
		**{
			"src/a.vue": "a2\n",
			"src/b.vue": "b2\n",
			"src/c.vue": "c2\n",
			"src/d.vue": "d2\n",
			"src/tests/a.test.js": "t2\n",
			"frontend/src/pages/Over.vue": "over2\n",
		},
	)
	repo.git("tag", "v1.0.1")
	repo.commit(
		"Merge pull request #7 from someone/quiz\n\nfeat(quiz)!: rebuild quiz authoring",
		**{"frontend/package.json": package_json("^1.0.0-beta.24")},
	)
	repo.git("tag", "v1.1.0")

	repo.git("checkout", "-q", "-b", "ours", "v1.0.0")
	repo.commit(
		"feat: our work",
		**{
			"src/a.vue": "a ours\n",
			"src/b.vue": "b ours // OSLMS-CUSTOM\n",
			"src/c.vue": "c ours\n",
			"src/tests/a.test.js": "t ours\n",
			"frontend/src/overrides/pages/Over.vue": "frozen\n",
		},
	)
	repo.git("tag", "ve1.0.1")
	repo.git("merge", "-q", "--no-ff", "-m", "Merge upstream/develop", "develop")

	inventory = repo.root / "docs" / "customizations"
	inventory.mkdir(parents=True)
	(inventory / "spa-grafts.toml").write_text(
		'[[entries]]\nid = "c-rule"\ntitle = "t"\nlayer = "spa-graft"\nconfidence = "high"\n'
		'intent = "i"\nsites = [{ file = "src/c.vue", anchor = "c ours" }]\n',
		encoding="utf-8",
	)
	return repo


class BuildPlanTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.repo = build_fake_fork(self._tmp.name)
		self.inventory = self.repo.root / "docs" / "customizations"

	def tearDown(self):
		self._tmp.cleanup()

	def plan(self, **kwargs):
		return build_plan(self.repo.root, self.inventory, kwargs.get("head", "HEAD"), None, kwargs.get("to"))

	def test_base_is_the_newest_release_merged_and_ignores_our_tags(self):
		plan = self.plan()
		self.assertEqual(plan["base"], "v1.0.0")
		self.assertEqual([r.tag for r in plan["releases"]], ["v1.0.1", "v1.1.0"])

	def test_measures_size_from_the_diff(self):
		first = self.plan()["releases"][0]
		self.assertEqual(first.commits, 1)
		self.assertEqual(first.files, 6)

	def test_reports_the_dependency_bump_and_the_break(self):
		first, second = self.plan()["releases"]
		self.assertFalse(first.dependency_bump)
		self.assertEqual((second.frappe_ui_from, second.frappe_ui), ("^1.0.0-beta.7", "^1.0.0-beta.24"))
		self.assertEqual(second.breaking, ["feat(quiz)!: rebuild quiz authoring"])

	def test_flags_only_unmarked_uncatalogued_files_of_ours(self):
		first = self.plan()["releases"][0]
		# b.vue has a marker, c.vue is catalogued, d.vue is upstream work merged
		# from develop, the test file is excluded: only a.vue is left.
		self.assertEqual(first.uncatalogued, ["src/a.vue"])
		self.assertEqual(first.inventory, ["c-rule"])

	def test_flags_the_frozen_page_whose_original_is_touched(self):
		first = self.plan()["releases"][0]
		self.assertEqual(first.frozen, ["frontend/src/overrides/pages/Over.vue"])

	def test_recommends_stopping_before_the_bump(self):
		self.assertEqual(self.plan()["recommendation"]["tag"], "v1.0.1")

	def test_to_limits_the_releases(self):
		self.assertEqual([r.tag for r in self.plan(to="v1.0.1")["releases"]], ["v1.0.1"])

	def test_json_output_and_exit_code(self):
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			code = main(["--repo-root", str(self.repo.root), "--json"])
		self.assertEqual(code, 0)
		payload = json.loads(out.getvalue())
		self.assertEqual(payload["recommendation"]["tag"], "v1.0.1")
		self.assertTrue(payload["releases"][1]["dependency_bump"])

	def test_fails_cleanly_without_a_release_tag_in_history(self):
		self.repo.git("checkout", "-q", "--orphan", "empty")
		self.repo.commit("chore: nothing")
		err = io.StringIO()
		with contextlib.redirect_stderr(err):
			code = main(["--repo-root", str(self.repo.root)])
		self.assertEqual(code, 2)
		self.assertIn("Nessun tag", err.getvalue())

	def test_rejects_a_target_that_is_not_pending(self):
		err = io.StringIO()
		with contextlib.redirect_stderr(err):
			code = main(["--repo-root", str(self.repo.root), "--to", "v0.9.0"])
		self.assertEqual(code, 2)
