"""Where things live in the repository, and which paths are customizations.

One place for the classification the commit guard and the map share: a path
is exempt (documents, tooling, generated files), ours (our own code, or a file
upstream does not have), or upstream. All paths are repo-relative POSIX strings.
"""

from __future__ import annotations

INVENTORY_DIR = "docs/customizations"
FEATURES_DIR = f"{INVENTORY_DIR}/features"
STRICT_FEATURES_FLAG = f"{FEATURES_DIR}/.strict"
LEGACY_FILE = f"{INVENTORY_DIR}/legacy-attribution.toml"
OVERRIDES_DIR = "frontend/src/overrides/"

OUR_PREFIXES = ("apps/os_lms/", "frontend/src/oslms/", "frontend/src/overrides/", "frontend/oslms-vite/")
EXEMPT_PREFIXES = (
	"docs/",
	"reports/",
	"scripts/",
	".claude/",
	".githooks/",
	".github/",
	"lms/locale/",
	"lms/translations/",
	"graphify-out/",
	".agents/",
	".vscode/",
)
EXEMPT_FILES = (
	"frontend/yarn.lock",
	"yarn.lock",
	"frontend/components.d.ts",
	"frontend/src/utils/frappe-ui-colors.json",
	"osv-scanner.toml",
)
EXEMPT_BASENAMES = ("CLAUDE.md", "AGENTS.md")  # agent instructions, at any depth


def is_exempt_path(path: str) -> bool:
	"""Documents, tooling and generated files: no feature attribution needed."""
	return (
		path.startswith(EXEMPT_PREFIXES)
		or path in EXEMPT_FILES
		or path.rsplit("/", 1)[-1] in EXEMPT_BASENAMES
	)


def is_our_path(path: str, base_files: set[str]) -> bool:
	"""A non-exempt file of ours: under our prefixes, or absent from the upstream base."""
	return not is_exempt_path(path) and (path.startswith(OUR_PREFIXES) or path not in base_files)
