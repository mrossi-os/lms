"""Custom configurable reminder system for LMS Live Class."""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from os_lms.os_lms.doctype.lms_live_class_reminder.lms_live_class_reminder import (
	offset_to_minutes,
)
from os_lms.os_lms.email_utils import send_templated_email
from os_lms.os_lms.live_class_ics import build_ics, get_calendar_links


def send_live_class_reminders():
	"""Iterate live classes and send reminders whose scheduled time has been reached."""
	logger = frappe.logger("os_lms_live_class_reminders", allow_site=True)
	now = now_datetime()
	today = now.date().isoformat()

	classes = frappe.get_all(
		"LMS Live Class",
		filters={"date": [">=", today]},
		fields=["name", "batch_name", "title", "date", "time"],
	)

	for live_class in classes:
		try:
			_process_class_reminders(live_class, now, logger)
		except Exception:
			logger.exception(f"Error processing reminders for {live_class.name}")


def _process_class_reminders(live_class, now: datetime, logger) -> None:
	doc = frappe.get_doc("LMS Live Class", live_class.name)
	reminders = doc.get("reminders") or []
	if not reminders:
		return

	class_dt = get_datetime(f"{doc.date} {doc.time}")
	# Don't send reminders for classes that have already started.
	if now >= class_dt:
		return

	students = frappe.get_all(
		"LMS Batch Enrollment",
		{"batch": doc.batch_name},
		["member", "member_name"],
	)
	if not students:
		return

	any_sent = False
	ics_attachment = _build_ics_attachment(doc, logger)
	cal_links = _build_calendar_links(doc, logger)
	for row in reminders:
		if row.sent_at:
			continue
		offset_minutes = offset_to_minutes(row.offset_value, row.offset_unit)
		fire_at = class_dt - timedelta(minutes=offset_minutes)
		if now < fire_at:
			continue

		for student in students:
			_send_reminder_mail(doc, student, ics_attachment, cal_links)
		row.sent_at = now
		any_sent = True
		logger.info(
			f"Sent reminder for {doc.name} (offset {row.offset_value} {row.offset_unit}) to {len(students)} students"
		)

	if any_sent:
		doc.save(ignore_permissions=True)
		frappe.db.commit()


def _build_ics_attachment(live_class, logger) -> list[dict] | None:
	try:
		ics = build_ics(live_class)
	except Exception:
		logger.exception(f"Error building ICS for {live_class.name}")
		return None
	return [{"fname": f"live-class-{live_class.name}.ics", "fcontent": ics.encode("utf-8")}]


def _build_calendar_links(live_class, logger) -> dict:
	"""Build "add to calendar" links (Google, Outlook, ICS); empty dict on failure."""
	try:
		return get_calendar_links(live_class)
	except Exception:
		logger.exception(f"Error building calendar links for {live_class.name}")
		return {}


def _send_reminder_mail(live_class, student, ics_attachment=None, cal_links=None) -> None:
	from frappe.utils import format_date

	formatted_date = format_date(live_class.date, "medium")
	subject = f"Promemoria lezione: {live_class.title} del {formatted_date}"
	header_text = f"Promemoria lezione: {live_class.title}"

	cal_links = cal_links or {}
	send_templated_email(
		template_key="live_class_reminder",
		recipients=student.member,
		subject=subject,
		args={
			"student_name": student.member_name,
			"title": live_class.title,
			"date": live_class.date,
			"time": live_class.time,
			"batch_name": live_class.batch_name,
			"live_class_name": live_class.name,
			"google_url": cal_links.get("google_url"),
			"outlook_url": cal_links.get("outlook_url"),
			"ics_url": cal_links.get("ics_url"),
		},
		header=[header_text, "orange"],
		attachments=ics_attachment,
	)


def reset_sent_at(doc, method=None):
	"""When date/time/duration changes, clear sent_at on reminders so they fire again."""
	if not doc.get("reminders"):
		return
	if not (
		doc.has_value_changed("date")
		or doc.has_value_changed("time")
		or doc.has_value_changed("duration")
	):
		return
	for row in doc.reminders:
		row.sent_at = None
