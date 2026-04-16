from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, format_date, format_time, get_datetime

from lms.lms.doctype.lms_live_class.lms_live_class import LMSLiveClass


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

	def create_event(self):
		start = f"{self.date} {self.time}"

		event = frappe.new_doc("Event")
		event.update(
			{
				"doctype": "Event",
				"subject": _("Lezione dal vivo: {0}").format(self.title),
				"event_type": "Public",
				"starts_on": start,
				"ends_on": get_datetime(start) + timedelta(minutes=cint(self.duration)),
			}
		)

		event.save()
		return event

	def create_calendar_event(self):
		event = self.create_event()
		frappe.db.set_value(self.doctype, self.name, "event", event.name)

		event.reload()
		event.update({"description": self.build_event_description()})
		event.save()

		self.send_invitation_email()

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
