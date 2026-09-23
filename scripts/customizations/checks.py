"""The drift checks.

Each check is a pure function taking the inventory entries plus the repository
root and returning findings. Nothing here executes application code: the whole
point of the detector is that it answers in seconds with Docker switched off.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.customizations.model import Entry

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
	"""One thing that no longer matches what the inventory declares."""

	entry_id: str
	check: str
	severity: str
	message: str
	file: str | None = None
	anchor: str | None = None


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8", errors="replace")


def check_sites(entries: list[Entry], repo_root: Path) -> list[Finding]:
	"""C1: every anchor still occurs in its file. C2: every file still exists.

	C2 short-circuits C1: a missing file is one fact, not two.
	"""
	findings: list[Finding] = []
	for entry in entries:
		if entry.status == "accepted-drift":
			continue
		for site in entry.sites:
			path = Path(repo_root) / site.file
			if not path.is_file():
				findings.append(
					Finding(entry.id, "C2", ERROR, "file non trovato", site.file, site.anchor)
				)
				continue
			if site.anchor not in _read(path):
				findings.append(
					Finding(entry.id, "C1", ERROR, "ancora non trovata nel file", site.file, site.anchor)
				)
	return findings
