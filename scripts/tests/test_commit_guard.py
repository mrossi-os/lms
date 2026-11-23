"""Tests for the commit-msg guard.

Every test builds a throwaway fork (upstream tag v1.0.0, our branch on top),
stages a change and runs the guard the way the hook does: on a message file,
with the working directory inside the repository.
"""

import contextlib
import io
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from scripts.commit_guard import classify, is_version_bump_only, main, parse_trailers
from scripts.tests.gitrepo import GIT_TEST_CONFIG, chdir, run_git, write_files

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDEBAR = "frontend/src/components/Sidebar/AppSidebar.vue"
UP = "frontend/src/pages/Up.vue"
OURS = "apps/os_lms/os_lms/os_lms/gate.py"
ANCHOR = "const isDocente = true"

UPSTREAM_UP = "".join(f"<!-- upstream line {n} -->\n" for n in range(1, 21))
OUR_UP = UPSTREAM_UP.replace(
	"<!-- upstream line 10 -->\n",
	f"<!-- upstream line 10 -->\n// OSLMS-CUSTOM: Docente gate\n{ANCHOR}\n",
)
SIDEBAR_BODY = '<div>\n\t<span id="versionApp" class="text-xs"> 1.0.0 </span>\n</div>\n'

CARD = """\
id = "{id}"
title = "Gate del Docente"
status = "active"
summary = "Il Docente vede la pagina come un amministratore."
why = "Il Docente è un istruttore globale."
behaviour = ["il Docente vede i controlli di gestione"]
areas = [{areas}]
upstream_watch = ["isAdmin"]
history = [{{ date = "2026-11-23", ref = "-", summary = "creazione" }}]
"""

INVENTORY = f"""\
[[entries]]
id = "up-docente-gate"
title = "Gate del Docente nella pagina Up"
layer = "spa-graft"
confidence = "high"
intent = "Il Docente è trattato da amministratore."
feature = "docente-gate"

  [[entries.sites]]
  file = "{UP}"
  anchor = "{ANCHOR}"
"""

TRAILERS = "Version: 1.0.1\nOslms-Feature: {feature}\nCo-Authored-By: Claude <noreply@anthropic.com>\n"


def card(feature_id, areas):
	return CARD.format(id=feature_id, areas=", ".join(f'"{a}"' for a in areas))


def message(subject, feature=None, body="Spiegazione del perché.\n"):
	text = f"{subject}\n\n{body}"
	if feature is not None:
		text += "\n" + TRAILERS.format(feature=feature)
	return text


class Fork:
	"""A fork shaped like ours: upstream release v1.0.0, then our customizations."""

	def __init__(self, root, tag=True):
		self.root = Path(root)
		self.root.mkdir(parents=True)
		run_git(self.root, "init", "-q", "-b", "main")
		self.commit(
			"chore(release): v1.0.0",
			**{UP: UPSTREAM_UP, SIDEBAR: SIDEBAR_BODY, "frontend/src/pages/Other.vue": "other\n", "docs/README.md": "doc\n"},
		)
		if tag:
			self.git("tag", "v1.0.0")
		self.git("checkout", "-q", "-b", "ours")
		self.commit(
			"feat: our customizations",
			**{
				UP: OUR_UP,
				OURS: "GATE = True\n",
				"docs/customizations/spa-grafts.toml": INVENTORY,
				"docs/customizations/features/docente-gate.toml": card("docente-gate", [UP]),
				"docs/customizations/features/ours-gate.toml": card("ours-gate", ["apps/os_lms/*"]),
			},
		)

	def git(self, *args, check=True):
		return run_git(self.root, *args, check=check)

	def commit(self, subject, **files):
		write_files(self.root, **files)
		self.git("add", "-A")
		self.git("commit", "-q", "-m", subject)

	def stage(self, **files):
		write_files(self.root, **files)
		self.git("add", "-A")

	def guard(self, text, cwd=None):
		"""Run the guard on `text` as the hook would; return (exit code, stderr)."""
		msgfile = self.root.parent / f"{self.root.name}-COMMIT_EDITMSG"
		msgfile.write_text(text, encoding="utf-8")
		stderr = io.StringIO()
		with chdir(cwd or self.root), contextlib.redirect_stderr(stderr):
			code = main([str(msgfile)])
		return code, stderr.getvalue()


class GuardTestCase(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.repo = Fork(Path(self._tmp.name) / "repo")

	def assertBlocked(self, result, *fragments):
		code, stderr = result
		self.assertEqual(code, 1, stderr)
		for fragment in fragments:
			self.assertIn(fragment, stderr)

	def assertAccepted(self, result):
		code, stderr = result
		self.assertEqual(code, 0, stderr)


class AttributionTest(GuardTestCase):
	def test_blocks_upstream_change_without_trailer(self):
		self.repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
		self.assertBlocked(
			self.repo.guard(message("fix(up): tweak the page")),
			"Oslms-Feature:",
			"docente-gate",
			UP,
		)

	def test_accepts_upstream_change_with_valid_trailer(self):
		self.repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
		self.assertAccepted(self.repo.guard(message("fix(up): tweak the page", "docente-gate")))

	def test_blocks_unknown_feature_id(self):
		self.repo.stage(**{OURS: "GATE = False\n"})
		self.assertBlocked(
			self.repo.guard(message("fix(gate): flip it", "no-such-feature")),
			"no-such-feature",
			"docs/customizations/features/no-such-feature.toml",
		)

	def test_accepts_card_created_in_same_commit(self):
		self.repo.stage(
			**{
				"apps/os_lms/os_lms/os_lms/brand_new.py": "NEW = 1\n",
				"docs/customizations/features/brand-new.toml": card("brand-new", ["apps/os_lms/os_lms/os_lms/brand_new.py"]),
			}
		)
		self.assertAccepted(self.repo.guard(message("feat(brand): add brand new", "brand-new")))

	def test_docs_only_commit_needs_no_trailer(self):
		self.repo.stage(**{"docs/README.md": "doc, updated\n"})
		code, stderr = self.repo.guard(message("docs: update the readme"))
		self.assertEqual((code, stderr), (0, ""))

	def test_version_bump_alone_needs_no_trailer(self):
		self.repo.stage(**{SIDEBAR: SIDEBAR_BODY.replace("1.0.0", "1.0.1")})
		code, stderr = self.repo.guard(message("chore: bump version"))
		self.assertEqual((code, stderr), (0, ""))

	def test_trailer_in_body_middle_does_not_count(self):
		self.repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
		body = "Prima parte.\n\nOslms-Feature: docente-gate\n\nAltro testo dopo la riga.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
		self.assertBlocked(
			self.repo.guard(message("fix(up): tweak the page", body=body)),
			"Oslms-Feature:",
			"blocco finale",
		)


class CardTest(GuardTestCase):
	def test_blocks_feat_without_card_staged(self):
		self.repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
		self.assertBlocked(
			self.repo.guard(message("feat(up): new behaviour", "docente-gate")),
			"docs/customizations/features/docente-gate.toml",
		)

	def test_reminds_fix_touching_areas_without_card(self):
		self.repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
		code, stderr = self.repo.guard(message("fix(up): small fix", "docente-gate"))
		self.assertEqual(code, 0, stderr)
		self.assertIn("behaviour", stderr)
		self.assertIn("docente-gate", stderr)

	def test_malformed_staged_card_blocks_with_message(self):
		self.repo.stage(**{"docs/customizations/features/broken.toml": "id = [unterminated\n"})
		self.assertBlocked(self.repo.guard(message("docs: add a card")), "broken.toml")


class InventoryTest(GuardTestCase):
	def test_blocks_orphaned_anchor_in_stage(self):
		moved = OUR_UP.replace(f"{ANCHOR}\n", "")
		self.repo.stage(**{UP: moved, "frontend/src/pages/Moved.vue": f"// OSLMS-CUSTOM\n{ANCHOR}\n"})
		self.assertBlocked(
			self.repo.guard(message("refactor(up): move the gate", "docente-gate")),
			"C1",
			ANCHOR,
			"up-docente-gate",
		)

	def test_rename_counts_both_paths(self):
		self.repo.git("mv", UP, "frontend/src/pages/Renamed.vue")
		code, stderr = self.repo.guard(message("refactor(up): rename the page", "docente-gate"))
		# The old path only shows up in the staged diff as the source of the
		# rename: the entry still pointing at it must be caught (C2).
		self.assertBlocked((code, stderr), "C2", UP)


class WaiverTest(GuardTestCase):
	def test_none_requires_reason_and_rejects_fix(self):
		self.repo.stage(**{OURS: "GATE  = True\n"})
		self.assertBlocked(self.repo.guard(message("style(gate): spacing", "none")), "motivo")
		self.assertBlocked(self.repo.guard(message("fix(gate): spacing", "none (formattazione)")), "fix")
		self.assertAccepted(self.repo.guard(message("style(gate): spacing", "none (formattazione)")))

	def test_revert_is_exempt(self):
		self.repo.stage(**{UP: UPSTREAM_UP})
		text = 'Revert "feat: our customizations"\n\nThis reverts commit 1234567.\n'
		self.assertAccepted(self.repo.guard(text))


class MergeTest(GuardTestCase):
	def _upstream_release(self, **files):
		self.repo.git("checkout", "-q", "v1.0.0")
		self.repo.commit("chore(release): v1.1.0", **files)
		self.repo.git("tag", "v1.1.0")
		self.repo.git("checkout", "-q", "ours")

	def test_upstream_merge_with_conflicts_needs_trailer(self):
		self._upstream_release(**{UP: UPSTREAM_UP.replace("line 11 -->", "line 11, changed -->")})
		result = self.repo.git("merge", "--no-commit", "v1.1.0", check=False)
		self.assertNotEqual(result.returncode, 0, "the fixture must conflict")
		resolved = OUR_UP.replace("line 11 -->", "line 11, changed -->")
		self.repo.stage(**{UP: resolved})
		merge_message = "Merge tag 'v1.1.0' into ours\n"
		self.assertBlocked(self.repo.guard(merge_message), "Oslms-Feature:", "docente-gate")
		self.assertAccepted(self.repo.guard(merge_message + "\nOslms-Feature: docente-gate\n"))

	def test_upstream_merge_without_conflicts_passes(self):
		self._upstream_release(**{"frontend/src/pages/Other.vue": "other, changed upstream\n"})
		self.repo.git("merge", "--no-commit", "--no-ff", "v1.1.0")
		self.assertAccepted(self.repo.guard("Merge tag 'v1.1.0' into ours\n"))


class BaseTest(unittest.TestCase):
	def test_missing_base_blocks_with_fetch_hint(self):
		with tempfile.TemporaryDirectory() as tmp:
			repo = Fork(Path(tmp) / "repo", tag=False)
			repo.stage(**{UP: OUR_UP + "<!-- one more -->\n"})
			code, stderr = repo.guard(message("fix(up): tweak", "docente-gate"))
		self.assertEqual(code, 1, stderr)
		self.assertIn("git fetch upstream --tags", stderr)

	def test_missing_git_binary_blocks_instead_of_crashing(self):
		with tempfile.TemporaryDirectory() as tmp:
			repo = Fork(Path(tmp) / "repo")
			repo.stage(**{"docs/README.md": "doc, updated\n"})
			with unittest.mock.patch.dict(os.environ, {"PATH": tmp}):
				code, stderr = repo.guard(message("docs: x"))
		self.assertEqual(code, 1, stderr)
		self.assertIn("[regola 7]", stderr)
		self.assertIn("FileNotFoundError", stderr)


class WorktreeTest(GuardTestCase):
	"""The real hook, through `git commit`, from a linked worktree."""

	def _install_tooling(self):
		for relative in ("scripts/__init__.py", "scripts/commit_guard.py", "scripts/upstream_plan.py", ".githooks/commit-msg"):
			target = self.repo.root / relative
			target.parent.mkdir(parents=True, exist_ok=True)
			shutil.copyfile(REPO_ROOT / relative, target)
		shutil.copytree(
			REPO_ROOT / "scripts/customizations",
			self.repo.root / "scripts/customizations",
			ignore=shutil.ignore_patterns("__pycache__"),
		)
		hook = self.repo.root / ".githooks/commit-msg"
		hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
		self.repo.commit("chore: add tooling")

	def _commit(self, worktree, text):
		# Same neutral config as the other tests, but with the real hooks folder.
		assert GIT_TEST_CONFIG[-2:] == ("-c", "core.hooksPath=/dev/null")
		return subprocess.run(
			["git", *GIT_TEST_CONFIG[:-2], "-c", "core.hooksPath=.githooks", "commit", "-q", "-F", "-"],
			cwd=worktree,
			input=text,
			capture_output=True,
			text=True,
			env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
		)

	def test_works_inside_a_worktree(self):
		self._install_tooling()
		worktree = Path(self._tmp.name) / "wt"
		self.repo.git("worktree", "add", "-q", "-b", "wt-branch", str(worktree))
		write_files(worktree, **{UP: OUR_UP + "<!-- from the worktree -->\n"})
		run_git(worktree, "add", "-A")

		refused = self._commit(worktree, message("fix(up): from a worktree"))
		self.assertNotEqual(refused.returncode, 0, refused.stderr)
		self.assertIn("Oslms-Feature:", refused.stderr)
		self.assertIn("docente-gate", refused.stderr)

		accepted = self._commit(worktree, message("fix(up): from a worktree", "docente-gate"))
		self.assertEqual(accepted.returncode, 0, accepted.stderr)


class WrapperInterpreterTest(unittest.TestCase):
	"""The real .githooks/commit-msg fails closed, in Italian, without a usable python3."""

	def _run_wrapper(self, bin_dir, repo):
		msgfile = Path(repo) / "MSG"
		msgfile.write_text(message("docs: x"), encoding="utf-8")
		return subprocess.run(
			["/bin/sh", str(REPO_ROOT / ".githooks/commit-msg"), str(msgfile)],
			cwd=repo,
			capture_output=True,
			text=True,
			env={"PATH": str(bin_dir), "HOME": os.environ.get("HOME", "/")},
		)

	def _bin_with_git(self, tmp):
		bin_dir = Path(tmp) / "bin"
		bin_dir.mkdir()
		(bin_dir / "git").symlink_to(shutil.which("git"))
		repo = Path(tmp) / "repo"
		repo.mkdir()
		run_git(repo, "init", "-q")
		return bin_dir, repo

	def test_too_old_python_blocks_with_italian_message(self):
		with tempfile.TemporaryDirectory() as tmp:
			bin_dir, repo = self._bin_with_git(tmp)
			# Behaves like an old interpreter running the wrapper's version probe.
			stub = bin_dir / "python3"
			stub.write_text("#!/bin/sh\necho 3.9.6\nexit 1\n", encoding="utf-8")
			stub.chmod(0o755)
			result = self._run_wrapper(bin_dir, repo)
		self.assertEqual(result.returncode, 1, result.stderr)
		for fragment in ("3.9.6", "3.11", "rifiutato", "PATH"):
			self.assertIn(fragment, result.stderr)
		self.assertNotIn("Traceback", result.stderr)

	def test_missing_python_blocks_with_italian_message(self):
		with tempfile.TemporaryDirectory() as tmp:
			bin_dir, repo = self._bin_with_git(tmp)
			result = self._run_wrapper(bin_dir, repo)
		self.assertEqual(result.returncode, 1, result.stderr)
		self.assertIn("python3 non trovato", result.stderr)
		self.assertIn("3.11", result.stderr)


class HelpersTest(unittest.TestCase):
	def test_parse_trailers_reads_only_the_final_block(self):
		text = "fix: x\n\nOslms-Feature: middle\n\nbody\n\nVersion: 1\nOslms-Feature: a\noslms-feature: b\n"
		self.assertEqual(parse_trailers(text), ["a", "b"])

	def test_classify(self):
		paths = {"docs/x.md", "frontend/yarn.lock", UP, "frontend/src/New.vue", "apps/os_lms/x.py"}
		groups = classify(paths, {UP, "apps/os_lms/x.py"})
		self.assertEqual(groups["exempt"], {"docs/x.md", "frontend/yarn.lock"})
		self.assertEqual(groups["upstream"], {UP})
		self.assertEqual(groups["ours"], {"frontend/src/New.vue", "apps/os_lms/x.py"})

	def test_agent_instructions_and_tooling_files_are_exempt(self):
		exempt = {
			"CLAUDE.md",
			"apps/os_lms/CLAUDE.md",
			"frontend/src/AGENTS.md",
			"graphify-out/graph.json",
			".agents/skills/x.md",
			".vscode/settings.json",
			"osv-scanner.toml",
		}
		not_exempt = {"frontend/src/CLAUDE.md.vue", "frontend/osv-scanner.toml"}
		groups = classify(exempt | not_exempt, set())
		self.assertEqual(groups["exempt"], exempt)
		self.assertEqual(groups["ours"], not_exempt)

	def test_version_bump_detection(self):
		bump = (
			f"diff --git a/{SIDEBAR} b/{SIDEBAR}\n--- a/{SIDEBAR}\n+++ b/{SIDEBAR}\n@@ -2 +2 @@\n"
			'-\t<span id="versionApp"> 1.0.0 </span>\n+\t<span id="versionApp"> 1.0.1 </span>\n'
		)
		self.assertTrue(is_version_bump_only(bump))
		self.assertFalse(is_version_bump_only(bump + "@@ -5 +5 @@\n-a\n+b\n"))
		self.assertFalse(is_version_bump_only(""))


if __name__ == "__main__":
	unittest.main()
