"""Security alerts (OWASP A09): thresholds, recipients and the refusals past the limit.

Threshold and recipient tests patch Frappe's lookups. The Redis counters and the
aggregated access log rows are real: cleanup deletes them by this module's
TEST-NET IPs (RFC 5737, never a real client) and the alert cooldown keys by name.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import security_alerts as alerts

TEST_IPS = ["198.51.100.41", "198.51.100.42"]
COOLDOWN_KEYS = ["security_alert:sent:failed_logins", "security_alert:sent:refused_keys"]


def _cleanup():
	frappe.db.rollback()
	log = frappe.qb.DocType("Elite API Access Log")
	frappe.db.delete(log, filters=log.ip_address.isin(TEST_IPS))
	frappe.db.commit()
	for ip in TEST_IPS:
		frappe.cache.delete(alerts._suppressed_counter_key(ip))
		frappe.cache.srem(alerts.SUPPRESSED_IPS_SET, ip)
	for key in COOLDOWN_KEYS:
		frappe.cache.delete_value(key)


class TestSecurityAlerts(UnitTestCase):
	def setUp(self):
		_cleanup()

	def tearDown(self):
		_cleanup()

	# -- failed logins -------------------------------------------------------

	def _check_logins(self, total, top=None):
		with (
			patch.object(frappe.db, "count", return_value=total),
			patch.object(alerts, "_top", return_value=top or [("<b>x</b>", total)]),
			patch.object(alerts, "alert_recipients", return_value=["admin@x.it", "gestore@x.it"]),
			patch.object(frappe, "sendmail") as sendmail,
		):
			sent = alerts.check_failed_logins()
		return sent, sendmail

	def test_failed_logins_below_the_threshold_send_nothing(self):
		sent, sendmail = self._check_logins(alerts.FAILED_LOGIN_LIMIT - 1)
		self.assertFalse(sent)
		sendmail.assert_not_called()

	def test_failed_logins_at_the_threshold_email_the_recipients_once_an_hour(self):
		sent, sendmail = self._check_logins(alerts.FAILED_LOGIN_LIMIT)
		self.assertTrue(sent)
		kwargs = sendmail.call_args.kwargs
		self.assertEqual(kwargs["recipients"], ["admin@x.it", "gestore@x.it"])
		self.assertIn(str(alerts.FAILED_LOGIN_LIMIT), kwargs["subject"])
		# Usernames come from the attacker and are escaped in the email.
		self.assertNotIn("<b>x</b>", kwargs["message"])

		sent_again, sendmail_again = self._check_logins(alerts.FAILED_LOGIN_LIMIT + 5)
		self.assertFalse(sent_again)
		sendmail_again.assert_not_called()

	def test_grouped_counts_run_on_the_real_activity_log(self):
		rows = alerts._top("Activity Log", "ip_address", {"operation": "Login", "user": "nobody@198.51.100.41"})
		self.assertEqual(rows, [])

	# -- Elite API -----------------------------------------------------------

	def test_refused_keys_count_the_attempts_past_the_limit(self):
		rows = [
			frappe._dict(ip_address=TEST_IPS[0], method="v1.ping", request_params=None),
			frappe._dict(
				ip_address=TEST_IPS[0],
				method=alerts.SUPPRESSED_METHOD,
				request_params=json.dumps({"suppressed_attempts": alerts.REFUSED_KEY_LIMIT}),
			),
		]
		with (
			patch.object(frappe, "get_all", return_value=rows),
			patch.object(alerts, "alert_recipients", return_value=["admin@x.it"]),
			patch.object(frappe, "sendmail") as sendmail,
		):
			self.assertTrue(alerts.check_refused_keys())
		self.assertIn(str(alerts.REFUSED_KEY_LIMIT + 1), sendmail.call_args.kwargs["subject"])

	def test_refusals_past_the_limit_become_one_log_row_per_ip(self):
		for _ in range(3):
			alerts.count_suppressed_attempt(TEST_IPS[1])

		alerts.flush_suppressed_attempts()

		rows = frappe.get_all(
			"Elite API Access Log",
			filters={"ip_address": TEST_IPS[1]},
			fields=["method", "status_code", "request_params"],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].method, alerts.SUPPRESSED_METHOD)
		self.assertEqual(rows[0].status_code, 429)
		self.assertEqual(json.loads(rows[0].request_params), {"suppressed_attempts": 3})
		# The counter is consumed: a second run writes nothing more.
		alerts.flush_suppressed_attempts()
		self.assertEqual(frappe.db.count("Elite API Access Log", {"ip_address": TEST_IPS[1]}), 1)

	# -- recipients ----------------------------------------------------------

	def test_recipients_are_the_administrator_and_the_enabled_gestori(self):
		def get_all(doctype, filters=None, pluck=None, **kwargs):
			if doctype == "Has Role":
				return ["Administrator", "g1@x.it", "g2@x.it"]
			self.assertEqual(filters["name"], ["in", ["g1@x.it", "g2@x.it"]])
			self.assertEqual(filters["enabled"], 1)
			return ["g1@x.it", None]

		with (
			patch.object(frappe, "get_all", side_effect=get_all),
			patch.object(frappe.db, "get_value", return_value="admin@x.it"),
		):
			self.assertEqual(alerts.alert_recipients(), ["admin@x.it", "g1@x.it"])

	def test_no_recipient_logs_an_error_instead_of_sending(self):
		with (
			patch.object(alerts, "alert_recipients", return_value=[]),
			patch.object(frappe, "sendmail") as sendmail,
			patch.object(frappe, "log_error") as log_error,
		):
			self.assertFalse(alerts._send_alert("failed_logins", "s", "m"))
		sendmail.assert_not_called()
		log_error.assert_called_once()
