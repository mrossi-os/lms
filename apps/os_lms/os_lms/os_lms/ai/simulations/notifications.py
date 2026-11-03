"""Notifications of the teacher review.

docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 8, decided by the
user on 2026-11-03:

- A session of a simulation with an outcome whose debrief is ready tells its
  reviewers (access.reviewers_of: the course's instructors and the valutatori
  of the student's batches, not the Gestori) in the bell.
- Every REMINDER_DAYS days until the teacher version is published, the
  reviewers get a reminder in the bell and by email: one per reviewer, listing
  all their sessions due. There is no deadline: reminders never close anything.
- The first time a teacher publishes their version, the student hears about
  it in the bell and by email.

The bell is a Notification Log of type Alert, which Frappe never emails and
os_lms push notifications fan out to phones. A notification that fails never
blocks the debrief or the teacher's save.
"""
from __future__ import annotations

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.translate import get_user_lang
from frappe.utils import add_days, escape_html, get_url, now_datetime

from lms.lms.utils import get_lms_route

from os_lms.os_lms.email_utils import as_email_text, send_templated_email

from . import access, teacher_review

REMINDER_DAYS = 7
SESSION_DOCTYPE = "LMSA Simulation Session"
SCORED_STATUSES = ("Ready", "Needs Review")


def _logger():
	return frappe.logger("os_lms_simulation_notifications", allow_site=True)


def notify_outcome_requested(debrief) -> None:
	"""Tell the reviewers that `debrief`'s session waits for its outcome. Once
	per session: a regenerated debrief does not notify again."""
	try:
		if (
			debrief.outcome_requested_at
			or debrief.status not in SCORED_STATUSES
			or debrief.review_status == teacher_review.REVIEW_PUBLISHED
			or not teacher_review.scenario_has_outcome(debrief)
		):
			return
		debrief.db_set("outcome_requested_at", now_datetime(), update_modified=False)
		student = _full_name(debrief.student)
		scenario = _scenario_name(debrief.scenario)
		for user in access.reviewers_of(debrief.course, debrief.student):
			_bell(
				user,
				_(
					"{0} completed the simulation {1}: it waits for your outcome",
					lang=get_user_lang(user),
				).format(_bold(student), _bold(scenario)),
				link=_review_link(debrief.course, debrief.session),
				session=debrief.session,
			)
	except Exception:
		_logger().exception(f"Outcome request notification failed for {debrief.name}")


def notify_review_published(debrief) -> None:
	"""Tell the student that a teacher published the evaluation of their
	session, with the outcome when the simulation has one."""
	try:
		user = debrief.student
		lang = get_user_lang(user)
		scenario = _scenario_name(debrief.scenario)
		teacher = _full_name(debrief.review_published_by)
		outcome = _outcome_label(debrief.outcome, lang)
		if outcome:
			subject = _("Your simulation {0} has been evaluated: {1}", lang=lang).format(
				_bold(scenario), outcome
			)
		else:
			subject = _("{0} published the evaluation of your simulation {1}", lang=lang).format(
				_bold(teacher), _bold(scenario)
			)
		link = get_lms_route(f"simulations/{debrief.session}/debrief")
		_bell(user, subject, link=link, session=debrief.session, from_user=debrief.review_published_by)
		send_templated_email(
			template_key="simulation_review_published",
			recipients=_email(user),
			subject=_("Evaluation of your simulation: {0}", lang=lang).format(scenario),
			args={
				"student_name": as_email_text(_full_name(user)),
				"scenario_name": as_email_text(scenario),
				"teacher_name": as_email_text(teacher),
				"outcome": debrief.outcome or "",
				"outcome_reason": as_email_text(debrief.outcome_reason or ""),
				"report_url": get_url(link),
			},
		)
	except Exception:
		_logger().exception(f"Review published notification failed for {debrief.name}")


def send_outcome_reminders() -> None:
	"""Daily job: remind the reviewers of the sessions waiting for their
	outcome for REMINDER_DAYS days or more since the request or the last
	reminder."""
	now = now_datetime()
	cutoff = add_days(now, -REMINDER_DAYS)
	due = frappe.db.sql(
		"""
		SELECT d.name, d.session, d.course, d.student, d.scenario, d.outcome_requested_at
		FROM `tabLMSA Simulation Debrief` d
		JOIN `tabLMSA Simulation Scenario` s ON s.name = d.scenario
		WHERE d.outcome_requested_at IS NOT NULL
			AND COALESCE(d.review_status, '') != %(published)s
			AND d.status IN %(statuses)s
			AND s.has_human_outcome = 1
			AND COALESCE(d.outcome_reminded_at, d.outcome_requested_at) <= %(cutoff)s
		ORDER BY d.outcome_requested_at
		""",
		{"published": teacher_review.REVIEW_PUBLISHED, "statuses": SCORED_STATUSES, "cutoff": cutoff},
		as_dict=True,
	)
	if not due:
		return

	by_reviewer: dict[str, list[dict]] = {}
	for row in due:
		for user in access.reviewers_of(row.course, row.student):
			by_reviewer.setdefault(user, []).append(row)

	for user, rows in by_reviewer.items():
		try:
			_remind(user, rows, now)
		except Exception:
			_logger().exception(f"Outcome reminder failed for {user}")

	# Every due session counts as reminded, also those without reviewers: the
	# next look comes REMINDER_DAYS days later.
	frappe.db.set_value(
		"LMSA Simulation Debrief",
		{"name": ["in", [row.name for row in due]]},
		"outcome_reminded_at",
		now,
		update_modified=False,
	)
	frappe.db.commit()


def _remind(user: str, rows: list[dict], now) -> None:
	lang = get_user_lang(user)
	courses = {row.course for row in rows}
	link = (
		_review_link(rows[0].course, rows[0].session)
		if len(rows) == 1
		else _panel_link(courses.pop() if len(courses) == 1 else None)
	)
	_bell(
		user,
		_("{0} simulation sessions are waiting for your outcome", lang=lang).format(len(rows))
		if len(rows) > 1
		else _("A simulation session is waiting for your outcome", lang=lang),
		link=link,
		session=rows[0].session if len(rows) == 1 else None,
	)
	send_templated_email(
		template_key="simulation_outcome_reminder",
		recipients=_email(user),
		subject=_("Simulations waiting for your outcome: {0}", lang=lang).format(len(rows)),
		args={
			"reviewer_name": as_email_text(_full_name(user)),
			"sessions": [
				{
					"student_name": as_email_text(_full_name(row.student)),
					"scenario_name": as_email_text(_scenario_name(row.scenario)),
					"waiting_days": (now - row.outcome_requested_at).days,
					"url": get_url(_review_link(row.course, row.session)),
				}
				for row in rows
			],
			"panel_url": get_url(link),
		},
	)


def _bell(user: str, subject: str, *, link: str, session: str | None, from_user: str | None = None) -> None:
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	notification = frappe._dict(
		subject=subject,
		type="Alert",
		link=link,
		from_user=from_user,
	)
	if session:
		notification.update(document_type=SESSION_DOCTYPE, document_name=session)
	make_notification_logs(notification, [_email(user)])


def _review_link(course: str, session: str) -> str:
	# The panel opens the session's transcript drawer from `session`.
	return get_lms_route(f"simulations/admin?{urlencode({'course': course, 'session': session})}")


def _panel_link(course: str | None) -> str:
	query = f"?{urlencode({'course': course})}" if course else ""
	return get_lms_route(f"simulations/admin{query}")


def _outcome_label(outcome: str | None, lang: str) -> str:
	if outcome == teacher_review.OUTCOME_PASSED:
		return _("passed", lang=lang)
	if outcome == teacher_review.OUTCOME_NOT_PASSED:
		return _("not passed", lang=lang)
	return ""


def _bold(text: str) -> str:
	# Names and titles are typed by people; the bell renders the subject as HTML.
	return frappe.bold(escape_html(text or ""))


def _email(user: str) -> str:
	# Bells and emails go by address, which is not always the user name
	# (Administrator).
	return frappe.db.get_value("User", user, "email") or user


def _full_name(user: str | None) -> str:
	if not user:
		return ""
	return frappe.db.get_value("User", user, "full_name") or user


def _scenario_name(scenario: str | None) -> str:
	if not scenario:
		return ""
	return frappe.db.get_value("LMSA Simulation Scenario", scenario, "scenario_name") or scenario
