"""Custom configurable reminder system for LMS Live Class."""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from os_lms.os_lms.doctype.lms_live_class_reminder.lms_live_class_reminder import (
	offset_to_minutes,
)


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
	for row in reminders:
		if row.sent_at:
			continue
		offset_minutes = offset_to_minutes(row.offset_value, row.offset_unit)
		fire_at = class_dt - timedelta(minutes=offset_minutes)
		if now < fire_at:
			continue

		for student in students:
			_send_reminder_mail(doc, student)
		row.sent_at = now
		any_sent = True
		logger.info(
			f"Sent reminder for {doc.name} (offset {row.offset_value} {row.offset_unit}) to {len(students)} students"
		)

	if any_sent:
		doc.save(ignore_permissions=True)
		frappe.db.commit()


def _send_reminder_mail(live_class, student) -> None:
	subject = _("Reminder: {0} on {1}").format(live_class.title, live_class.date)
	frappe.sendmail(
		recipients=student.member,
		subject=subject,
		template="live_class_reminder",
		args={
			"student_name": student.member_name,
			"title": live_class.title,
			"date": live_class.date,
			"time": live_class.time,
			"batch_name": live_class.batch_name,
		},
		header=[_("Class Reminder: {0}").format(live_class.title), "orange"],
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
