"""Security updates of the frontend dependencies must survive upstream merges.

Commit 29b287f31 (OWASP A03, 2026-10-27) raised these packages past published
advisories. An upstream release that touches frontend/package.json conflicts on
those lines, and taking the upstream side there brings the vulnerable versions
back without any other local check noticing: the Dependency Scan only runs on
GitHub. The floors are checked on what yarn actually resolves (yarn.lock), so a
range that still allows an old copy fails as well.

Raise a floor when a newer security update lands; never lower one to make this
pass (see the upstream-upgrade skill, rule 2).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCKFILE = REPO_ROOT / "frontend" / "yarn.lock"

FLOORS = {
	"dompurify": "3.4.17",
	"markdown-it": "14.3.3",
	"socket.io-client": "4.8.4",
	"vue": "3.5.44",
	"vite": "5.4.21",
	"postcss": "8.5.30",
	"prosemirror-model": "1.25.12",
	"prosemirror-view": "1.42.6",
	"prosemirror-transform": "1.12.2",
	"@tiptap/core": "3.32.0",
	"@tiptap/pm": "3.32.0",
	"@tiptap/vue-3": "3.32.0",
	"vitest": "4.1.12",
}


def parse_version(text):
	return tuple(int(part) for part in re.findall(r"\d+", text.split("-")[0])[:3])


def resolved_versions(lockfile_text, package):
	"""Every version of `package` a yarn v1 lockfile resolves, one per entry."""
	versions = []
	matching = False
	for line in lockfile_text.splitlines():
		if line and not line.startswith((" ", "#")):
			specs = [spec.strip().strip('"') for spec in line.rstrip(":").split(",")]
			matching = any(spec.rsplit("@", 1)[0] == package for spec in specs if "@" in spec[1:])
		elif matching and line.startswith("  version "):
			versions.append(line.split('"')[1])
			matching = False
	return versions


class TestResolvedVersions(unittest.TestCase):
	def test_reads_every_copy_and_keeps_scoped_names_apart(self):
		lockfile = (
			'"@tiptap/core@^3.32.0":\n  version "3.32.0"\n\n'
			'vite@5.4.21:\n  version "5.4.21"\n\n'
			'"vite@^8.0.0", vite@~8.3.0:\n  version "8.3.4"\n\n'
			'vite-plugin-pwa@^1.0.0:\n  version "1.0.3"\n'
		)
		self.assertEqual(resolved_versions(lockfile, "vite"), ["5.4.21", "8.3.4"])
		self.assertEqual(resolved_versions(lockfile, "@tiptap/core"), ["3.32.0"])
		self.assertEqual(resolved_versions(lockfile, "core"), [])


class TestDependencyFloors(unittest.TestCase):
	def test_no_resolved_copy_is_below_its_security_floor(self):
		lockfile = LOCKFILE.read_text()
		for package, floor in FLOORS.items():
			with self.subTest(package=package):
				versions = resolved_versions(lockfile, package)
				self.assertTrue(versions, f"{package} is no longer in frontend/yarn.lock")
				below = [v for v in versions if parse_version(v) < parse_version(floor)]
				self.assertEqual(below, [], f"{package} resolves below {floor}")


if __name__ == "__main__":
	unittest.main()
