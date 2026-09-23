"""Render the detector outcome, for a human and for an agent."""

from __future__ import annotations

import json

from scripts.customizations.checks import ERROR, Finding


def render_json(findings: list[Finding], entries_total: int, generated_at: str) -> str:
	"""Serialise the run, which is what the /upstream-check skill consumes."""
	payload = {
		"generated_at": generated_at,
		"entries_total": entries_total,
		"findings": [
			{
				"id": finding.entry_id,
				"check": finding.check,
				"severity": finding.severity,
				"message": finding.message,
				"file": finding.file,
				"anchor": finding.anchor,
			}
			for finding in findings
		],
	}
	return json.dumps(payload, indent=2, ensure_ascii=False)


def _block(title: str, findings: list[Finding]) -> list[str]:
	lines = [f"  {title} ({len(findings)})"]
	for finding in findings:
		lines.append(f"  {finding.check}  {finding.entry_id:<32} {finding.message}")
		if finding.file:
			lines.append(f"        {finding.file}")
		if finding.anchor:
			lines.append(f"        ancora: {finding.anchor}")
	lines.append("")
	return lines


def render_table(findings: list[Finding], entries_total: int) -> str:
	"""Render the outcome as a terminal report."""
	errors = [f for f in findings if f.severity == ERROR]
	warnings = [f for f in findings if f.severity != ERROR]
	lines = [f"Inventario: {entries_total} voci", ""]
	if errors:
		lines += _block("ERRORI", errors)
	if warnings:
		lines += _block("AVVISI", warnings)
	lines.append(f"Esito: {len(errors)} errori, {len(warnings)} avvisi")
	return "\n".join(lines)
