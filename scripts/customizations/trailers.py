"""The `Oslms-Feature` trailer of commit messages, read with git's own rules."""

from __future__ import annotations

import re
import subprocess

TRAILER = "Oslms-Feature"
TRAILER_KEY = TRAILER.lower()
NONE_VALUE = re.compile(r"^none(?:\s*\((.*)\))?\s*$", re.IGNORECASE)


def parse_trailers(message: str) -> list[str]:
	"""The `Oslms-Feature` values of the final trailer block, with git's own rules."""
	result = subprocess.run(
		["git", "interpret-trailers", "--parse", "--no-divider"],
		input=message,
		capture_output=True,
		text=True,
		encoding="utf-8",
		check=True,
	)
	values = []
	for line in result.stdout.splitlines():
		key, _, value = line.partition(":")
		if key.strip().lower() == TRAILER_KEY and value.strip():
			values.append(value.strip())
	return values
