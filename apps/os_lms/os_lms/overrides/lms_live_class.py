from datetime import timedelta

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint, format_date, format_time, get_datetime, now_datetime

from lms.lms.doctype.lms_live_class.lms_live_class import LMSLiveClass
from lms.lms.utils import get_lms_route

from os_lms.os_lms.email_utils import send_templated_email
from os_lms.os_lms.live_class_ics import get_calendar_links
from os_lms.os_lms.live_class_join import get_join_gate_url


def _lc_log(msg):
	frappe.logger("lms_live_class_debug", allow_site=True).info(msg)


# Changing any of these moves the class for its participants: they are the fields
# that trigger the "class updated" email and the Zoom reschedule.
NOTIFIED_FIELDS = ("title", "date", "time", "duration", "timezone")


class CustomLMSLiveClass(LMSLiveClass):
	def _is_zoom(self) -> bool:
		# `create_live_class` (Zoom flow) does not set `conferencing_provider`.
		# Treat anything that isn't Google Meet but has a zoom_account as Zoom.
		if self.conferencing_provider == "Zoom":
			return True
		if self.conferencing_provider != "Google Meet" and self.zoom_account:
			return True
		return False

	def on_update(self):
		# Keeps the linked Google Calendar event in sync (upstream behaviour).
		super().on_update()
		self._handle_class_update()

	def _update_linked_event(self):
		"""Same as upstream, but keeps the Italian subject used at creation time."""
		event = frappe.get_doc("Event", self.event)
		start = f"{self.date} {self.time}"

		event.subject = _("Lezione dal vivo: {0}").format(self.title)
		event.starts_on = start
		event.ends_on = get_datetime(start) + timedelta(minutes=cint(self.duration))
		event.description = self.build_event_description()

		event.save(ignore_permissions=True)

	def _handle_class_update(self):
		"""On a real change of the class details, reschedule Zoom and warn everyone.

		Triggered from any save path — the SPA endpoint and the desk form alike.
		`description` is not in the list: correcting the text must not email the
		whole batch. Reminders re-arm themselves through the `before_save` hook
		`os_lms.os_lms.live_class_reminders.reset_sent_at`.
		"""
		from os_lms.os_lms.api import normalize_live_class_value

		previous = self.get_doc_before_save()
		if not previous:
			# Part of the insert: the invitation email already covers this.
			return

		changed = [
			field
			for field in NOTIFIED_FIELDS
			if normalize_live_class_value(field, previous.get(field))
			!= normalize_live_class_value(field, self.get(field))
		]
		if not changed:
			return

		# A class that is already over notifies nobody: correcting the title of last
		# month's lesson must not email the whole batch, and there is nothing left
		# to reschedule on Zoom. The check runs on the NEW schedule, so postponing
		# a past class to a future slot does notify — which is the point of it.
		end = get_datetime(f"{self.date} {self.time}") + timedelta(minutes=cint(self.duration))
		if end <= now_datetime():
			_lc_log(f"[_handle_class_update] {self.name} changed={changed} but already over, skipping")
			return

		_lc_log(f"[_handle_class_update] {self.name} changed={changed}")

		# Run the side effects AFTER the transaction commits, never inside it.
		# Rescheduling on Zoom is two HTTP calls with a 10s timeout each, and the
		# emails add a write per participant: doing that here kept a write lock on
		# this row for the whole time, long enough for a second click (or the
		# reminder / attendance scheduler) to hit it and fail the save with
		# MariaDB 1020, "Record has changed since last read".
		frappe.enqueue(
			"os_lms.overrides.lms_live_class.apply_live_class_update",
			queue="short",
			enqueue_after_commit=True,
			live_class=self.name,
		)

	def apply_update_side_effects(self):
		"""Reschedule the meeting and tell the participants. Runs out of the save."""
		from os_lms.os_lms.api import update_zoom_meeting

		if self._is_zoom():
			update_zoom_meeting(self)

		self._send_update_safe()
		self._send_update_notification_safe()

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
		except Exception as exc:
			_lc_log(
				f"[create_calendar_event] {self.name} Event save RAISED "
				f"type={type(exc).__name__} msg={exc!r}"
			)
			frappe.log_error(title="LMS Live Class Event save failed")
			frappe.throw(
				_(
					"Impossibile creare l'evento sul Google Calendar \"{0}\". "
					"L'autorizzazione potrebbe essere mancante, scaduta o revocata: "
					"apri il documento Google Calendar e ricompleta il flusso OAuth, poi riprova."
				).format(calendar)
			)

		frappe.db.set_value(self.doctype, self.name, "event", event.name)

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

	def _send_update_safe(self):
		try:
			self.send_update_email()
			_lc_log(f"[_send_update_safe] {self.name} OK")
		except Exception as exc:
			_lc_log(f"[_send_update_safe] {self.name} RAISED type={type(exc).__name__} msg={exc!r}")
			frappe.log_error(title="LMS Live Class send_update_email failed")

	def _send_update_notification_safe(self):
		try:
			self.send_update_notification()
			_lc_log(f"[_send_update_notification_safe] {self.name} OK")
		except Exception as exc:
			_lc_log(
				f"[_send_update_notification_safe] {self.name} RAISED "
				f"type={type(exc).__name__} msg={exc!r}"
			)
			frappe.log_error(title="LMS Live Class send_update_notification failed")

	def _get_batch_valutatori(self) -> set[str]:
		"""Users assigned as valutatori of this class's batch. They act as hosts:
		they receive the invitation, can start the class and enter as organizer."""
		return set(
			frappe.get_all(
				"LMS Batch Valutatore",
				{"parent": self.batch_name, "parenttype": "LMS Batch"},
				pluck="valutatore",
			)
		)

	def get_participants(self):
		# Batch valutatori are hosts too, so they must receive the invitation and
		# the calendar event alongside the enrolled students and instructors.
		return list(set(super().get_participants()) | self._get_batch_valutatori())

	def send_invitation_email(self):
		self._mail_participants(
			template_key="live_class_invitation",
			subject=_("Lezione dal vivo: {0}").format(self.title),
			header=[_("Invito lezione dal vivo"), "green"],
			log_tag="send_invitation_email",
		)

	def send_update_email(self):
		"""Tell the participants the class changed, restating every current detail.

		Same shape as the invitation — the recipient gets the class as it stands
		now (title, date, time, duration, description, join link, calendar
		buttons), not a diff against the previous schedule.
		"""
		# No `header`: the template carries its own branded header, and Frappe's
		# would print the same title again as a bare line above the design.
		self._mail_participants(
			template_key="live_class_updated",
			subject=_("Lezione dal vivo aggiornata: {0}").format(self.title),
			header=None,
			log_tag="send_update_email",
		)

	def _mail_participants(self, template_key, subject, header, log_tag):
		participants = self.get_participants()
		# These emails link to the internal gated join page (join_live_class),
		# NOT the raw Zoom/Meet URL. That endpoint authenticates the recipient,
		# checks they are entitled to the class and that the join window is open,
		# then forwards them to the correct meeting URL (start_url for hosts,
		# join_url for students). A single link therefore works for every
		# recipient — the host/student decision happens server-side at click time.
		# It is also stable across a reschedule, so an invitation already sent
		# keeps working after the class is moved.
		from os_lms.os_lms.api import get_live_class_join_url

		join_url = get_live_class_join_url(self.name)
		_lc_log(
			f"[{log_tag}] {self.name} participants_count={len(participants)} "
			f"participants={participants} join_url={self.join_url} "
			f"start_url={self.start_url} internal_url={join_url} title={self.title!r}"
		)
		# "Add to calendar" deep links (Google, Outlook) plus the raw .ics download
		# (Apple/desktop clients) — one button each, so the recipient picks their own
		# calendar. No .ics *attachment*: an attached calendar file makes Gmail/Outlook
		# render their own native card that adds the event to one calendar automatically
		# without letting the user choose. Exposed in `args` so any template (file-based
		# or per-client desk Email Template) can render the buttons.
		cal_links = get_calendar_links(self)
		# Values the templates cannot compute on their own: the end of the class,
		# the host's display name and the batch title (`batch_name` is the slug).
		start_dt = get_datetime(f"{self.date} {self.time}")
		end_time = (
			format_time(start_dt + timedelta(minutes=cint(self.duration)), "HH:mm")
			if cint(self.duration)
			else None
		)
		host_name = frappe.db.get_value("User", self.host, "full_name") if self.host else None
		batch_title = (
			frappe.db.get_value("LMS Batch", self.batch_name, "title") if self.batch_name else None
		)
		sent = 0
		failed = 0
		for participant in participants:
			try:
				member_name = frappe.db.get_value("User", participant, "first_name") or participant
				_lc_log(
					f"[{log_tag}] {self.name} -> {participant} "
					f"(name={member_name}) attempting sendmail"
				)
				send_templated_email(
					template_key=template_key,
					recipients=participant,
					subject=subject,
					args={
						"student_name": member_name,
						"title": self.title,
						"date": self.date,
						"time": self.time,
						"duration": self.duration,
						"end_time": end_time,
						"host_name": host_name,
						"batch_title": batch_title,
						"join_url": join_url,
						"description": self.description,
						"batch_name": self.batch_name,
						"live_class_name": self.name,
						"google_url": cal_links["google_url"],
						"outlook_url": cal_links["outlook_url"],
						"ics_url": cal_links["ics_url"],
					},
					header=header,
				)
				sent += 1
				_lc_log(f"[{log_tag}] {self.name} -> {participant} queued OK")
			except Exception as exc:
				failed += 1
				_lc_log(
					f"[{log_tag}] {self.name} -> {participant} FAILED "
					f"type={type(exc).__name__} msg={exc!r}"
				)
				frappe.log_error(title=f"LMS Live Class {log_tag} to {participant} failed")
		_lc_log(f"[{log_tag}] {self.name} summary sent={sent} failed={failed}")

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

	def send_update_notification(self):
		"""In-app counterpart of the "class updated" email, for the students."""
		students = frappe.get_all(
			"LMS Batch Enrollment", {"batch": self.batch_name}, pluck="member"
		)
		_lc_log(f"[send_update_notification] {self.name} students_count={len(students)}")
		if not students:
			return

		notification = frappe._dict(
			{
				"subject": _("Lezione dal vivo aggiornata: {0} - {1} alle {2}").format(
					frappe.bold(self.title),
					format_date(self.date, "medium"),
					format_time(self.time, "hh:mm a"),
				),
				"email_content": _(
					"La lezione dal vivo è stata modificata: ora è in programma il {0} alle {1}."
				).format(format_date(self.date, "medium"), format_time(self.time, "hh:mm a")),
				"document_type": "LMS Live Class",
				"document_name": self.name,
				"from_user": frappe.session.user,
				"type": "Alert",
				"link": get_lms_route(f"batches/details/{self.batch_name}#classes"),
			}
		)
		make_notification_logs(notification, students)


def apply_live_class_update(live_class: str) -> None:
	"""Background entry point for the side effects of an updated live class.

	Enqueued with `enqueue_after_commit` by `_handle_class_update`, so it starts
	only once the new schedule is safely stored and no row lock is held.
	"""
	doc = frappe.get_doc("LMS Live Class", live_class)
	doc.apply_update_side_effects()
	frappe.db.commit()
