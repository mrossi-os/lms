"""Teacher version of a simulation debrief.

docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 4. The AI version
(overall_score, criterion_scores, strengths, improvements, behavioral analysis,
recommended lessons) is written by the debrief job and never edited by a
person. A teacher starts their own version as a copy of it, edits it as a
draft and publishes it: students only ever see a published one, and every
later save of a published version reaches them at once.

On simulations with an outcome (`has_human_outcome` on the scenario) the
teacher also decides passed / not passed, with a reason when not passed, and
cannot publish without it. The AI never decides the outcome; `passed` is set
from the person's decision only.
"""
from __future__ import annotations

import frappe
from frappe import _

REVIEW_DRAFT = "Draft"
REVIEW_PUBLISHED = "Published"

OUTCOME_PASSED = "Passed"
OUTCOME_NOT_PASSED = "Not Passed"
OUTCOMES = (OUTCOME_PASSED, OUTCOME_NOT_PASSED)

COMMENT_MAX_LENGTH = 5000
REASON_MAX_LENGTH = 1000
TEXT_MAX_LENGTH = 2000
# Data fields hold 140 characters
TITLE_MAX_LENGTH = 140
MAX_ROWS = 20


def scenario_has_outcome(debrief) -> bool:
	return bool(
		frappe.db.get_value("LMSA Simulation Scenario", debrief.scenario, "has_human_outcome")
	)


def start_review(debrief) -> None:
	"""Create the teacher version as a draft copy of the AI version. Does
	nothing when a teacher version already exists."""
	if debrief.review_status:
		return
	debrief.review_status = REVIEW_DRAFT
	debrief.review_overall_score = debrief.overall_score
	debrief.set("review_criterion_scores", [])
	for c in debrief.criterion_scores or []:
		debrief.append(
			"review_criterion_scores",
			{
				"criterion_name": c.criterion_name,
				"score": c.score,
				"max_score": c.max_score,
				"evidence_quote": c.evidence_quote,
				"note": c.note,
			},
		)
	debrief.set("review_strengths", [])
	for s in debrief.strengths or []:
		debrief.append("review_strengths", {"title": s.title, "detail": s.detail, "quote": s.quote})
	debrief.set("review_improvements", [])
	for i in debrief.improvements or []:
		debrief.append(
			"review_improvements",
			{"title": i.title, "detail": i.detail, "quote": i.quote, "suggestion": i.suggestion},
		)


def apply_review(debrief, data: dict, *, publish: bool, has_outcome: bool) -> None:
	"""Validate the teacher's edits and write them into the teacher version.

	`data` carries overall_score, criterion_scores, strengths, improvements,
	comment, outcome and outcome_reason. Criteria are the AI's: the teacher
	changes their scores and notes, not which criteria there are."""
	if not debrief.review_status:
		frappe.throw(_("Start the teacher version first"))
	if not isinstance(data, dict):
		frappe.throw(_("The teacher version must be an object"))

	debrief.review_overall_score = _score(data.get("overall_score"))
	_set_criteria(debrief, data.get("criterion_scores"))
	_set_rows(debrief, "review_strengths", data.get("strengths"), ("detail", "quote"))
	_set_rows(debrief, "review_improvements", data.get("improvements"), ("detail", "quote", "suggestion"))
	debrief.instructor_review = _text(data.get("comment"), COMMENT_MAX_LENGTH, _("The comment"))

	outcome = (data.get("outcome") or "").strip()
	if outcome and outcome not in OUTCOMES:
		frappe.throw(_("Unknown outcome"))
	if outcome and not has_outcome:
		frappe.throw(_("This simulation has no outcome: it cannot be passed or failed"))
	reason = _text(data.get("outcome_reason"), REASON_MAX_LENGTH, _("The reason")) if outcome else ""

	published = publish or debrief.review_status == REVIEW_PUBLISHED
	if published and has_outcome and not outcome:
		frappe.throw(_("Decide whether the simulation is passed before publishing"))
	if published and outcome == OUTCOME_NOT_PASSED and not reason:
		frappe.throw(_("A reason is required when the simulation is not passed"))

	user = frappe.session.user
	now = frappe.utils.now_datetime()
	if outcome != (debrief.outcome or "") or reason != (debrief.outcome_reason or ""):
		debrief.outcome = outcome or None
		debrief.outcome_reason = reason or None
		debrief.outcome_decided_by = user if outcome else None
		debrief.outcome_decided_at = now if outcome else None

	debrief.instructor_reviewed_by = user
	debrief.instructor_reviewed_at = now
	if publish:
		debrief.review_status = REVIEW_PUBLISHED
		debrief.review_published_by = user
		debrief.review_published_at = now
	debrief.passed = int(
		debrief.review_status == REVIEW_PUBLISHED and debrief.outcome == OUTCOME_PASSED
	)


def discard_review(debrief) -> None:
	"""Delete a draft teacher version. A published one stays: the student has
	already seen it."""
	if debrief.review_status != REVIEW_DRAFT:
		frappe.throw(_("Only a draft teacher version can be discarded"))
	debrief.review_status = None
	debrief.review_overall_score = 0
	for field in ("review_criterion_scores", "review_strengths", "review_improvements"):
		debrief.set(field, [])
	for field in (
		"instructor_review",
		"instructor_reviewed_by",
		"instructor_reviewed_at",
		"outcome",
		"outcome_reason",
		"outcome_decided_by",
		"outcome_decided_at",
	):
		debrief.set(field, None)
	debrief.passed = 0


def serialize_review(debrief, *, include_scores: bool) -> dict | None:
	if not debrief.review_status:
		return None
	payload = {
		"status": debrief.review_status.lower(),
		"strengths": [
			{"title": s.title, "detail": s.detail, "quote": s.quote}
			for s in debrief.review_strengths or []
		],
		"improvements": [
			{"title": i.title, "detail": i.detail, "quote": i.quote, "suggestion": i.suggestion}
			for i in debrief.review_improvements or []
		],
		"comment": debrief.instructor_review or "",
		"outcome": debrief.outcome or "",
		"outcome_reason": debrief.outcome_reason or "",
		"outcome_decided_by_name": _full_name(debrief.outcome_decided_by),
		"outcome_decided_at": _when(debrief.outcome_decided_at),
		"edited_by_name": _full_name(debrief.instructor_reviewed_by),
		"edited_at": _when(debrief.instructor_reviewed_at),
		"published_by_name": _full_name(debrief.review_published_by),
		"published_at": _when(debrief.review_published_at),
	}
	if include_scores:
		payload["overall_score"] = debrief.review_overall_score
		payload["criterion_scores"] = [
			{
				"criterion_name": c.criterion_name,
				"score": c.score,
				"max_score": c.max_score,
				"evidence_quote": c.evidence_quote,
				"note": c.note,
			}
			for c in debrief.review_criterion_scores or []
		]
	return payload


def _set_criteria(debrief, rows) -> None:
	rows = _rows(rows)
	ai_rows = {c.criterion_name: c for c in debrief.criterion_scores or []}
	seen = set()
	debrief.set("review_criterion_scores", [])
	for row in rows:
		name = (row.get("criterion_name") or "").strip()
		ai_row = ai_rows.get(name)
		if ai_row is None:
			frappe.throw(_("Unknown criterion: {0}").format(name))
		if name in seen:
			frappe.throw(_("Criterion listed twice: {0}").format(name))
		seen.add(name)
		max_score = ai_row.max_score or 10
		try:
			score = float(row.get("score"))
		except (TypeError, ValueError):
			score = None
		if score is None or not 0 <= score <= max_score:
			frappe.throw(
				_("The score of {0} must be a number between 0 and {1}").format(name, max_score)
			)
		debrief.append(
			"review_criterion_scores",
			{
				"criterion_name": name,
				"score": round(score, 1),
				"max_score": max_score,
				"evidence_quote": ai_row.evidence_quote,
				"note": _text(row.get("note"), TEXT_MAX_LENGTH, _("The note")),
			},
		)


def _set_rows(debrief, field: str, rows, text_fields: tuple[str, ...]) -> None:
	debrief.set(field, [])
	for row in _rows(rows):
		title = (row.get("title") or "").strip()
		if not title:
			continue
		if len(title) > TITLE_MAX_LENGTH:
			frappe.throw(
				_("A title cannot be longer than {0} characters").format(TITLE_MAX_LENGTH)
			)
		values = {"title": title}
		for name in text_fields:
			values[name] = _text(row.get(name), TEXT_MAX_LENGTH, _("A text"))
		debrief.append(field, values)


def _rows(rows) -> list[dict]:
	if rows is None:
		return []
	if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
		frappe.throw(_("Rows must be a list of objects"))
	if len(rows) > MAX_ROWS:
		frappe.throw(_("At most {0} rows are allowed").format(MAX_ROWS))
	return rows


def _score(value) -> float:
	try:
		score = round(float(value), 1)
	except (TypeError, ValueError):
		score = None
	if score is None or not 0 <= score <= 100:
		frappe.throw(_("The score must be a number between 0 and 100"))
	return score


def _text(value, max_length: int, what: str) -> str:
	text = (value or "").strip() if isinstance(value, str) else ""
	if len(text) > max_length:
		frappe.throw(_("{0} cannot be longer than {1} characters").format(what, max_length))
	return text


def _full_name(user: str | None) -> str | None:
	if not user:
		return None
	return frappe.db.get_value("User", user, "full_name") or user


def _when(value) -> str | None:
	return str(value) if value else None
