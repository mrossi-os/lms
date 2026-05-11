from datetime import timedelta

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint, format_date, format_time, get_datetime

from lms.lms.doctype.lms_live_class.lms_live_class import LMSLiveClass
from lms.lms.utils import get_lms_route


def _lc_log(msg):
	frappe.logger("lms_live_class_debug", allow_site=True).info(msg)


class CustomLMSLiveClass(LMSLiveClass):
	def _is_zoom(self) -> bool:
		# `create_live_class` (Zoom flow) does not set `conferencing_provider`.
		# Treat anything that isn't Google Meet but has a zoom_account as Zoom.
		if self.conferencing_provider == "Zoom":
			return True
		if self.conferencing_provider != "Google Meet" and self.zoom_account:
			return True
		return False

	def build_event_description(self):
		description = _("È stata programmata una lezione dal vivo il {0} alle {1}.").format(
			format_date(self.date, "medium"), format_time(self.time, "hh:mm a")
		)
		if self.join_url:
			description += " " + _("Clicca su questo link per partecipare: {0}").format(self.join_url) + "\n\n"
		if self.description:
			description += self.description
		return description

	def create_calendar_event(self):
		is_zoom = self._is_zoom()
		is_meet = self.conferencing_provider == "Google Meet"
		_lc_log(
			f"[create_calendar_event] START name={self.name} provider={self.conferencing_provider!r} "
			f"is_zoom={is_zoom} is_meet={is_meet} meet_account={self.google_meet_account} "
			f"zoom_account={self.zoom_account} join_url={self.join_url} session_user={frappe.session.user}"
		)

		if not is_zoom and not is_meet:
			_lc_log(f"[create_calendar_event] {self.name} unknown provider, aborting")
			frappe.throw(_("Provider di conferenza non riconosciuto."))

		if is_meet:
			calendar = frappe.db.get_value(
				"LMS Google Meet Settings", self.google_meet_account, "google_calendar"
			)
		else:
			calendar = frappe.db.get_value(
				"LMS Zoom Settings", self.zoom_account, "google_calendar"
			)
		_lc_log(f"[create_calendar_event] {self.name} resolved calendar={calendar}")

		if not calendar:
			frappe.throw(
				_(
					"Nessun calendario è configurato per il provider di conferenza. Configura un calendario per creare gli eventi."
				)
			)

		start = f"{self.date} {self.time}"
		event = frappe.new_doc("Event")
		event_data = {
			"subject": _("Lezione dal vivo: {0}").format(self.title),
			"event_type": "Public",
			"starts_on": start,
			"ends_on": get_datetime(start) + timedelta(minutes=cint(self.duration)),
			"sync_with_google_calendar": 1,
			"google_calendar": calendar,
			"description": self.build_event_description(),
			"send_reminder": 0,
		}
		if is_meet:
			event_data["add_video_conferencing"] = 1
		event.update(event_data)
		_lc_log(
			f"[create_calendar_event] {self.name} saving Event sync=1 "
			f"add_vc={event_data.get('add_video_conferencing', 0)} send_reminder=0"
		)

		try:
			event.save()
			_lc_log(
				f"[create_calendar_event] {self.name} Event saved name={event.name} "
				f"event_id={event.google_calendar_event_id} meet={event.google_meet_link}"
			)
		except Exception:
			_lc_log(f"[create_calendar_event] {self.name} Event save RAISED")
			frappe.log_error(title="LMS Live Class Event save failed")
			raise

		frappe.db.set_value(self.doctype, self.name, "event", event.name)

		try:
			self.add_event_participants(event, calendar)
			_lc_log(f"[create_calendar_event] {self.name} participants added")
		except Exception:
			_lc_log(f"[create_calendar_event] {self.name} add_event_participants RAISED")
			frappe.log_error(title="LMS Live Class add_event_participants failed")
			raise

		if is_meet:
			event.reload()
			meet_link = event.google_meet_link
			_lc_log(f"[create_calendar_event] {self.name} after reload meet={meet_link}")
			if meet_link:
				frappe.db.set_value(
					self.doctype,
					self.name,
					{"start_url": meet_link, "join_url": meet_link},
				)
				self.start_url = meet_link
				self.join_url = meet_link
				_lc_log(f"[create_calendar_event] {self.name} start_url/join_url persisted")
			else:
				_lc_log(f"[create_calendar_event] {self.name} NO meet link returned by Google")

		self._send_invitation_safe()
		self._send_notification_safe()
		_lc_log(f"[create_calendar_event] END name={self.name} ({'Meet' if is_meet else 'Zoom'})")

	def _send_invitation_safe(self):
		try:
			self.send_invitation_email()
			_lc_log(f"[_send_invitation_safe] {self.name} OK")
		except Exception as exc:
			_lc_log(f"[_send_invitation_safe] {self.name} RAISED type={type(exc).__name__} msg={exc!r}")
			frappe.log_error(title="LMS Live Class send_invitation_email failed")

	def _send_notification_safe(self):
		try:
			self.send_notification()
			_lc_log(f"[_send_notification_safe] {self.name} OK")
		except Exception as exc:
			_lc_log(f"[_send_notification_safe] {self.name} RAISED type={type(exc).__name__} msg={exc!r}")
			frappe.log_error(title="LMS Live Class send_notification failed")

	def send_invitation_email(self):
		participants = self.get_participants()
		_lc_log(
			f"[send_invitation_email] {self.name} participants_count={len(participants)} "
			f"participants={participants} join_url={self.join_url} title={self.title!r}"
		)
		sent = 0
		failed = 0
		for participant in participants:
			try:
				member_name = frappe.db.get_value("User", participant, "first_name") or participant
				_lc_log(f"[send_invitation_email] {self.name} -> {participant} (name={member_name}) attempting sendmail")
				frappe.sendmail(
					recipients=participant,
					subject=_("Lezione dal vivo: {0}").format(self.title),
					template="live_class_invitation",
					args={
						"student_name": member_name,
						"title": self.title,
						"date": self.date,
						"time": self.time,
						"join_url": self.join_url,
						"description": self.description,
						"batch_name": self.batch_name,
					},
					header=[_("Invito lezione dal vivo"), "green"],
				)
				sent += 1
				_lc_log(f"[send_invitation_email] {self.name} -> {participant} queued OK")
			except Exception as exc:
				failed += 1
				_lc_log(
					f"[send_invitation_email] {self.name} -> {participant} FAILED "
					f"type={type(exc).__name__} msg={exc!r}"
				)
				frappe.log_error(title=f"LMS Live Class invitation to {participant} failed")
		_lc_log(f"[send_invitation_email] {self.name} summary sent={sent} failed={failed}")

	def send_notification(self):
		students = frappe.get_all(
			"LMS Batch Enrollment", {"batch": self.batch_name}, pluck="member"
		)
		_lc_log(f"[send_notification] {self.name} students_count={len(students)}")
		if not students:
			return

		notification = frappe._dict(
			{
				"subject": _("Nuova lezione dal vivo: {0} - {1} alle {2}").format(
					frappe.bold(self.title),
					format_date(self.date, "medium"),
					format_time(self.time, "hh:mm a"),
				),
				"email_content": _("È stata programmata una lezione dal vivo il {0} alle {1}.").format(
					format_date(self.date, "medium"), format_time(self.time, "hh:mm a")
				),
				"document_type": "LMS Live Class",
				"document_name": self.name,
				"from_user": frappe.session.user,
				"type": "Alert",
				"link": get_lms_route(f"batches/details/{self.batch_name}#classes"),
			}
		)
		make_notification_logs(notification, students)
