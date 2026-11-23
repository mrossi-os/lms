"""Tests for the frozen-copy base (C9) and scripts/frozen_diff.py."""

import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.customizations.checks import WARNING, check_frozen_base
from scripts.customizations.model import Site
from scripts.frozen_diff import main
from scripts.tests.test_checks import entry
from scripts.tests.test_upstream_plan import FakeUpstream


def override_entry(file, frozen_from=None, entry_id="over"):
	built = entry(entry_id, sites=[Site(file=file, anchor="x")], layer="override-file")
	return replace(built, frozen_from=frozen_from)


class CheckFrozenBaseTest(unittest.TestCase):
	def test_c9_warns_override_without_frozen_from(self):
		findings = check_frozen_base([override_entry("frontend/src/overrides/pages/Over.vue")])
		self.assertEqual([(f.check, f.severity, f.entry_id) for f in findings], [("C9", WARNING, "over")])

	def test_c9_passes_when_frozen_from_is_set(self):
		findings = check_frozen_base([override_entry("frontend/src/overrides/pages/Over.vue", "v1.0.0")])
		self.assertEqual(findings, [])

	def test_c9_ignores_entries_outside_overrides(self):
		findings = check_frozen_base([override_entry("frontend/src/pages/Over.vue")])
		self.assertEqual(findings, [])


def run(argv):
	out, err = io.StringIO(), io.StringIO()
	with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
		code = main(argv)
	return code, out.getvalue(), err.getvalue()


def write_inventory(root, sites, frozen_from=None):
	inventory = Path(root) / "docs" / "customizations"
	inventory.mkdir(parents=True, exist_ok=True)
	sites_toml = ", ".join(f'{{ file = "{f}", anchor = "x" }}' for f in sites)
	frozen = f'frozen_from = "{frozen_from}"\n' if frozen_from else ""
	(inventory / "overrides.toml").write_text(
		'[[entries]]\nid = "over"\ntitle = "t"\nlayer = "override-file"\nconfidence = "high"\n'
		f'intent = "i"\n{frozen}sites = [{sites_toml}]\n',
		encoding="utf-8",
	)


class FrozenDiffLmsTest(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.repo = FakeUpstream(self.tmp.name)
		self.repo.commit("v1", **{"frontend/src/pages/Over.vue": "original line\n"})
		self.repo.git("tag", "v1.0.0")
		self.repo.commit("v1.1", **{"frontend/src/pages/Over.vue": "changed upstream line\n"})
		self.repo.git("tag", "v1.1.0")
		self.repo.commit("ours", **{"frontend/src/overrides/pages/Over.vue": "frozen\n"})

	def test_frozen_diff_shows_upstream_change_of_original(self):
		write_inventory(self.repo.root, ["frontend/src/overrides/pages/Over.vue"], "v1.0.0")
		code, out, _ = run(["--repo-root", str(self.repo.root), "--entry", "over", "--to", "v1.1.0"])
		self.assertEqual(code, 0)
		self.assertIn("-original line", out)
		self.assertIn("+changed upstream line", out)

	def test_entry_without_frozen_from_exits_2(self):
		write_inventory(self.repo.root, ["frontend/src/overrides/pages/Over.vue"])
		code, _, err = run(["--repo-root", str(self.repo.root), "--entry", "over", "--to", "v1.1.0"])
		self.assertEqual(code, 2)
		self.assertIn("frozen_from", err)

	def test_unknown_entry_exits_2(self):
		write_inventory(self.repo.root, ["frontend/src/overrides/pages/Over.vue"], "v1.0.0")
		code, _, err = run(["--repo-root", str(self.repo.root), "--entry", "nope", "--to", "v1.1.0"])
		self.assertEqual(code, 2)
		self.assertIn("nope", err)

	def test_missing_lms_tag_exits_2(self):
		write_inventory(self.repo.root, ["frontend/src/overrides/pages/Over.vue"], "v1.0.0")
		code, _, err = run(["--repo-root", str(self.repo.root), "--entry", "over", "--to", "v9.9.9"])
		self.assertEqual(code, 2)
		self.assertIn("v9.9.9", err)


class FrozenDiffFrappeUiTest(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		root = Path(self.tmp.name)
		(root / "lms").mkdir()
		(root / "ui").mkdir()
		self.lms = FakeUpstream(root / "lms")
		self.lms.commit("init", **{"frontend/src/overrides/frappe-ui/src/components/Combobox/Combobox.vue": "x\n"})
		self.ui = FakeUpstream(root / "ui")
		path = "src/components/Combobox/Combobox.vue"
		self.ui.commit("beta.29", **{path: "old combobox\n"})
		self.ui.git("tag", "v1.0.0-beta.29")
		self.ui.commit("rc.1", **{path: "new combobox\n"})
		self.ui.git("tag", "v1.0.0-rc.1")
		write_inventory(
			self.lms.root, ["frontend/src/overrides/frappe-ui/src/components/Combobox/Combobox.vue"], "1.0.0-beta.29"
		)

	def argv(self, to, ui=None):
		return [
			"--repo-root", str(self.lms.root), "--entry", "over", "--to", to,
			"--frappe-ui-repo", str(ui or self.ui.root),
		]

	def test_diffs_component_between_frappe_ui_tags(self):
		code, out, _ = run(self.argv("1.0.0-rc.1"))
		self.assertEqual(code, 0)
		self.assertIn("-old combobox", out)
		self.assertIn("+new combobox", out)

	def test_missing_tag_prints_fetch_hint_and_exits_2(self):
		code, _, err = run(self.argv("1.0.0-rc.9"))
		self.assertEqual(code, 2)
		self.assertIn("fetch --tags", err)

	def test_uninitialized_submodule_exits_2_with_init_hint(self):
		empty = Path(self.tmp.name) / "lms" / "frappe-ui"
		empty.mkdir()
		code, _, err = run(self.argv("1.0.0-rc.1", ui=empty))
		self.assertEqual(code, 2)
		self.assertIn("git submodule update --init frappe-ui", err)


if __name__ == "__main__":
	unittest.main()
