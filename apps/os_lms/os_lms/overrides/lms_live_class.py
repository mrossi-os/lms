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
		_lc_log(f"[create_calendar_event] {self.name} provider={self.conferencing_provider} meet_account={self.google_meet_account} zoom_account={self.zoom_account}")

		if self.conferencing_provider == "Google Meet":
			calendar = frappe.db.get_value(
				"LMS Google Meet Settings", self.google_meet_account, "google_calendar"
			)
		else:
			calendar = frappe.db.get_value(
				"Google Calendar", {"user": frappe.session.user, "enable": 1}, "name"
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
			"add_video_conferencing": 1 if self.conferencing_provider == "Google Meet" else 0,
		}
		event.update(event_data)
		_lc_log(f"[create_calendar_event] {self.name} saving Event with sync=1 add_vc={event_data['add_video_conferencing']}")

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

		if self.conferencing_provider == "Google Meet":
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

		try:
			self.send_invitation_email()
			_lc_log(f"[create_calendar_event] {self.name} invitation emails sent")
		except Exception:
			_lc_log(f"[create_calendar_event] {self.name} send_invitation_email RAISED (continuing)")
			frappe.log_error(title="LMS Live Class send_invitation_email failed")

		try:
			self.send_notification()
			_lc_log(f"[create_calendar_event] {self.name} notifications sent")
		except Exception:
			_lc_log(f"[create_calendar_event] {self.name} send_notification RAISED (continuing)")
			frappe.log_error(title="LMS Live Class send_notification failed")

	def send_invitation_email(self):
		participants = self.get_participants()
		for participant in participants:
			member_name = frappe.db.get_value("User", participant, "first_name") or participant
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

	def send_notification(self):
		students = frappe.get_all(
			"LMS Batch Enrollment", {"batch": self.batch_name}, pluck="member"
		)
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
