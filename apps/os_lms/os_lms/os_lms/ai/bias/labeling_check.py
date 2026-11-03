"""Compare the hand check of the judges with the judges' own answers.

Input: a <run>_labeling.csv filled by a person (by hand or with
labeling_form.html, any path) and the judges' hidden answers saved with
the run: results/<run>_judges.json for the Coach, results/<run>.json for
the Tutor (their "labeling" items). No LLM call.

Run from the bench:
    bench --site <site> execute os_lms.os_lms.ai.bias.labeling_check.check_labeling \\
        --kwargs '{"sheet": "/path/to/<run>_labeling.csv"}'

Writes results/<run>_labeling_check.{json,md} (report in Italian, with the
variant of every disagreement) and, when the sheet comes from elsewhere,
keeps a copy as results/<run>_labeling_filled.csv. Returns the report path.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"

# Sheet column (its text before " (") -> (judge answer key, kind). A column
# is compared only on the items whose judge answer has that key, so the
# Coach and Tutor sheets share the table.
FIELDS = {
	"correttezza": ("correctness", "scale"),
	"completezza": ("completeness", "scale"),
	"rifiuta": ("refused", "flag"),
	"riferimenti identità": ("identity_reference", "flag"),
	"stereotipi": ("stereotype", "flag"),
	"commenti forma italiano": ("language_form_comment", "flag"),
	"paternalistico": ("condescending", "flag"),
	"genere usato": ("student_gender", "gender"),
	"specificità": ("specificity", "scale"),
	"tono più incoraggiante": ("warmer", "choice"),
	"differenza": ("strength", "strength"),
	"differenza tono": ("warmer_strength", "strength"),
	"più utile": ("more_helpful", "choice"),
	"differenza utilità": ("helpful_strength", "strength"),
}
# The "which one" answer each strength goes with.
STRENGTH_CHOICE = {"strength": "warmer", "warmer_strength": "warmer", "helpful_strength": "more_helpful"}
_YES = {"sì", "si", "s", "yes", "y", "x", "true", "1"}
_NO = {"no", "n", "false", "0"}
_GENDERS = {"m": "maschile", "f": "femminile", "n": "neutro"}


def check_labeling(sheet: str, run: str | None = None) -> str:
	"""Compare ``sheet`` (a path, or a file name in results/) with the
	judges' answers of ``run`` (taken from the sheet name when omitted)."""
	path = Path(sheet) if Path(sheet).is_absolute() else RESULTS_DIR / sheet
	run = run or run_name(path)
	judges_file = judges_path(run)
	judged = json.loads(judges_file.read_text())
	header, rows = read_sheet(path)
	check = compare(judged["labeling"], header, rows)
	data = path.read_bytes()
	check |= {
		"run": run,
		"date": datetime.now().isoformat(timespec="seconds"),
		"sheet": path.name,
		"sheet_sha256": hashlib.sha256(data).hexdigest(),
		"judges_file": judges_file.name,
		"judges_version": judged.get("judges_version"),
		"judge_model": judged.get("judge_model"),
	}
	# The filled sheet is the evidence of the hand check: keep it with the run.
	kept = RESULTS_DIR / f"{run}_labeling_filled.csv"
	if path.resolve() != kept.resolve():
		shutil.copyfile(path, kept)
	check["kept_sheet"] = kept.name
	(RESULTS_DIR / f"{run}_labeling_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=1) + "\n")
	report = RESULTS_DIR / f"{run}_labeling_check.md"
	report.write_text(render_report(check))
	return str(report)


def run_name(path: Path) -> str:
	"""coach_..._official_labeling (2).csv -> coach_..._official"""
	match = re.match(r"(.+?)_labeling(?:_filled)?\b", path.stem)
	if not match:
		raise ValueError(f"Cannot tell the run from the sheet name {path.name}: pass run=")
	return match.group(1)


def judges_path(run: str) -> Path:
	"""The Coach keeps its judges apart from the run; the Tutor does not."""
	for name in (f"{run}_judges.json", f"{run}.json"):
		if (RESULTS_DIR / name).exists():
			return RESULTS_DIR / name
	raise FileNotFoundError(f"No judges file for run {run} in {RESULTS_DIR}")


def read_sheet(path: Path) -> tuple[list[str], list[list[str]]]:
	"""Header labels and rows of a sheet saved by the runner, the form or a
	spreadsheet (semicolon, comma or tab; UTF-8 with or without BOM)."""
	try:
		text = path.read_text(encoding="utf-8-sig")
	except UnicodeDecodeError:
		text = path.read_text(encoding="cp1252")
	first = text.split("\n", 1)[0]
	delimiter = ";" if ";" in first else "\t" if "\t" in first else ","
	table = [row for row in csv.reader(text.splitlines(keepends=True), delimiter=delimiter) if any(c.strip() for c in row)]
	header = [cell.split(" (")[0].strip().lower() for cell in table[0]]
	return header, table[1:]


def normalise(kind: str, value: str):
	"""The person's answer in the judge's form; None when blank. Raises
	ValueError when the answer is not one of the column's choices."""
	value = value.strip().lower()
	if not value:
		return None
	if kind == "flag":
		if value in _YES:
			return True
		if value in _NO:
			return False
	elif kind == "gender":
		if value[0] in _GENDERS and _GENDERS[value[0]].startswith(value):
			return _GENDERS[value[0]]
	elif kind == "choice":
		if value in ("1", "2"):
			return value
		if value in ("pari", "p", "="):
			return "pari"
	else:
		number = value.replace(",", ".")
		try:
			number = float(number)
		except ValueError:
			number = None
		allowed = range(1, 6) if kind == "scale" else range(0, 3)
		if number is not None and number.is_integer() and int(number) in allowed:
			return int(number)
	raise ValueError(value)


def compare(items: list[dict], header: list[str], rows: list[list[str]]) -> dict:
	"""Agreement between the person (``rows``) and the judges (``items``)."""
	by_item = {row[0].strip(): row for row in rows if row and row[0].strip()}
	columns = {name: i for i, name in enumerate(header) if name in FIELDS}
	note_column = header.index("note") if "note" in header else None
	fields = {}
	invalid, incomplete, disagreements = [], [], []
	answered_items = 0
	for item in items:
		row = by_item.get(item["item"])
		judge = item["judge_answer"]
		applicable = [name for name in columns if FIELDS[name][0] in judge]
		answers = {}
		for name in applicable:
			key, kind = FIELDS[name]
			cell = row[columns[name]] if row and columns[name] < len(row) else ""
			try:
				answers[name] = normalise(kind, cell)
			except ValueError:
				invalid.append({"item": item["item"], "column": name, "value": cell.strip()})
				answers[name] = None
		given = [name for name in applicable if answers[name] is not None]
		if not given:
			continue
		answered_items += 1
		if len(given) < len(applicable):
			incomplete.append({"item": item["item"], "missing": [n for n in applicable if answers[n] is None]})
		note = row[note_column].strip() if row and note_column is not None and note_column < len(row) else ""
		person_by_key = {FIELDS[name][0]: answers[name] for name in applicable}
		for name in given:
			key, kind = FIELDS[name]
			person, judged = answers[name], judge[key]
			if kind == "strength":
				choice = STRENGTH_CHOICE[key]
				person = effective_strength(person, person_by_key.get(choice))
				judged = effective_strength(judged, judge.get(choice))
			stats = fields.setdefault(name, {"key": key, "kind": kind, "compared": 0, "agree": 0, "cells": Counter()})
			stats["compared"] += 1
			stats["agree"] += person == judged
			stats["cells"][f"{_cell(person)}|{_cell(judged)}"] += 1
			if person != judged:
				disagreements.append(
					{
						"item": item["item"],
						"column": name,
						"person": person,
						"judge": judged,
						"case": item.get("case_id") or item.get("question_id"),
						"variant": item["variant"],
						"repeat": item["repeat"],
						"note": note,
					}
				)
	for stats in fields.values():
		stats["cells"] = dict(stats["cells"])
		stats["agreement"] = round(stats["agree"] / stats["compared"], 3)
		if stats["kind"] in ("scale", "strength"):
			pairs = [(int(p), int(j)) for cell, n in stats["cells"].items() for p, j in [cell.split("|")] for _ in range(n)]
			stats["within_one"] = sum(abs(p - j) <= 1 for p, j in pairs)
			stats["mean_difference"] = round(sum(p - j for p, j in pairs) / len(pairs), 2)
		if stats["kind"] == "choice":
			# One says text 1, the other text 2: the worst disagreement.
			stats["opposite"] = stats["cells"].get("1|2", 0) + stats["cells"].get("2|1", 0)
	return {
		"items": len(items),
		"answered_items": answered_items,
		"fields": fields,
		"invalid": invalid,
		"incomplete": incomplete,
		"disagreements": disagreements,
	}


def effective_strength(strength: int, choice: str | None) -> int:
	"""The strength the analysis uses (judges.parse_tone, judges._relative):
	0 for "pari" whatever was written, at least 1 when a text was chosen.
	The judge does answer "pari" with strength 2 now and then."""
	if choice == "pari":
		return 0
	if choice in ("1", "2"):
		return max(strength, 1)
	return strength


def _cell(value) -> str:
	if isinstance(value, bool):
		return "sì" if value else "no"
	return str(value)


def render_report(check: dict) -> str:
	"""Report in Italian for the ESG evidence folder."""
	lines = [
		f"# Verifica umana dei giudici — {check['run']}",
		"",
		f"- Data del confronto: {check['date']}",
		f"- Foglio compilato: `{check['sheet']}` (copia: `{check['kept_sheet']}`), SHA-256 `{check['sheet_sha256'][:16]}…`",
		f"- Risposte dei giudici: `{check['judges_file']}`, giudice {check['judge_model']}, istruzioni"
		f" {check['judges_version']}",
		f"- Elementi compilati: {check['answered_items']} su {check['items']}",
		"",
	]
	if check["answered_items"] < check["items"] or check["incomplete"] or check["invalid"]:
		lines += ["**Verifica non completa**: vedi gli elementi mancanti o non validi in fondo.", ""]
	lines += [
		"## Accordo tra la persona e il giudice",
		"",
		"| Domanda | Confrontati | Uguali | Accordo | Dettaglio |",
		"|---|---|---|---|---|",
	]
	for name, stats in check["fields"].items():
		lines.append(
			f"| {name} | {stats['compared']} | {stats['agree']} | {stats['agreement']:.0%} | {_detail(stats)} |"
		)
	flags = {name: s for name, s in check["fields"].items() if s["kind"] == "flag" and s["key"] != "refused"}
	if flags:
		lines += [
			"",
			"## Segnalazioni",
			"",
			"| Domanda | Sì per entrambi | Solo il giudice | Solo la persona | No per entrambi |",
			"|---|---|---|---|---|",
		]
		for name, stats in flags.items():
			cells = stats["cells"]
			lines.append(
				f"| {name} | {cells.get('sì|sì', 0)} | {cells.get('no|sì', 0)} | {cells.get('sì|no', 0)} |"
				f" {cells.get('no|no', 0)} |"
			)
		lines += [
			"",
			"«Solo il giudice»: segnalazioni del giudice non confermate dalla persona (falsi positivi del"
			" giudice). «Solo la persona»: casi che il giudice non ha visto.",
		]
	lines += ["", "## Disaccordi", ""]
	if check["disagreements"]:
		lines += [
			"La versione dello studente è mostrata solo qui, dopo la compilazione.",
			"",
			"| Elemento | Domanda | Persona | Giudice | Caso | Versione | Ripetizione | Note della persona |",
			"|---|---|---|---|---|---|---|---|",
		]
		for d in check["disagreements"]:
			note = d["note"].replace("|", "/").replace("\n", " ")
			lines.append(
				f"| {d['item']} | {d['column']} | {_cell(d['person'])} | {_cell(d['judge'])} | {d['case']} |"
				f" {d['variant']} | {d['repeat']} | {note} |"
			)
	else:
		lines.append("Nessuno.")
	if check["incomplete"] or check["invalid"]:
		lines += ["", "## Da completare", ""]
		for entry in check["incomplete"]:
			lines.append(f"- {entry['item']}: manca {', '.join(entry['missing'])}")
		for entry in check["invalid"]:
			lines.append(f"- {entry['item']}: «{entry['value']}» non è una risposta valida per «{entry['column']}»")
	return "\n".join(lines) + "\n"


def _detail(stats: dict) -> str:
	if stats["kind"] in ("scale", "strength"):
		return (
			f"entro 1 punto: {stats['within_one']} su {stats['compared']};"
			f" persona − giudice in media {stats['mean_difference']:+.2f}"
		)
	if stats["kind"] == "choice":
		return f"opposti (1 contro 2): {stats['opposite']}"
	return ""
