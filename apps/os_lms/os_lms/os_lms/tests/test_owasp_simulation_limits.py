"""OWASP audit 2026-10-29: limits on AI simulation spend.

H-3 chat messages without rate, length or turn caps; H-4 realtime voice tokens
minted without limit; L-18 clone_session skipping the scenario gates; L-63 the
daily quota counted without a lock. Limits live in LMSA Simulation Limits.

Every record is created here and deleted by exact name: the shared simulation
fixtures wipe every session of the site and must not be used.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.realtime import api as rt_api
from os_lms.os_lms.ai.simulations import api as sim_api
from os_lms.os_lms.ai.simulations.limits import (
	CHAT_MESSAGE_ACTION,
	LIMIT_DEFAULTS,
	LIMITS_DOCTYPE,
	SimulationLimits,
	VOICE_TOKEN_ACTION,
	check_message_length,
	ensure_simulation_limits,
	load_limits,
)
from os_lms.os_lms.ai.simulations.orchestrator import (
	QuotaExceededError,
	SessionOrchestrator,
	SessionTerminatedError,
	VoiceTokenLimitError,
	closing_input_locked,
	validate_quota,
)
from os_lms.os_lms.ai.simulations.tests import _fixtures as F
from os_lms.os_lms.ai.utils.realtime import RealtimeSessionConfig
from os_lms.os_lms.ai.utils.realtime.providers.gemini_live import _token_request
from os_lms.os_lms.ai.utils.realtime.providers.openai_realtime import _session_body
from os_lms.os_lms.tests.test_owasp_2026_10 import with_request

SCENARIO_NAME = "OWASP Limits Scenario"
SCHEMA_NAME = "OWASP Limits Schema"
STUDENT = "owasp-limits-student@example.com"
SETTINGS_FIELDS = (
	"simulations_enabled",
	"simulation_chat_provider",
	"simulation_debrief_provider",
	"realtime_enabled",
	"realtime_provider",
)


def _stub_generate_variant(self, scenario, seed, provider):
	return F.CANNED_VARIANT


def _limits(**overrides) -> SimulationLimits:
	return replace(SimulationLimits(**LIMIT_DEFAULTS), **overrides)


def patched_limits(**overrides) -> ExitStack:
	"""Patch load_limits in every module that imported it."""
	value = _limits(**overrides)
	stack = ExitStack()
	for target in (
		"os_lms.os_lms.ai.simulations.limits.load_limits",
		"os_lms.os_lms.ai.simulations.api.load_limits",
		"os_lms.os_lms.ai.simulations.orchestrator.load_limits",
		"os_lms.os_lms.ai.realtime.api.load_limits",
	):
		stack.enter_context(patch(target, return_value=value))
	return stack


def _clear_rate_limit(action: str, user: str) -> None:
	# Raw delete: check_user_rate_limit writes the already-prefixed key with the
	# raw redis commands, and delete_value() would prefix it a second time.
	frappe.cache.delete(frappe.cache.make_key(f"os_lms:rl:{action}:{user}"))


class SimulationLimitsCase(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.saved_settings = {
			f: frappe.db.get_single_value("LMSA Settings", f) for f in SETTINGS_FIELDS
		}
		for field, value in (
			("simulations_enabled", 1),
			("simulation_chat_provider", "mock"),
			("simulation_debrief_provider", "mock"),
			("realtime_enabled", 1),
			("realtime_provider", "mock"),
		):
			frappe.db.set_single_value("LMSA Settings", field, value)
		cls.schema = F.make_evaluation_schema(name=SCHEMA_NAME)
		cls.scenario = F.make_published_scenario(name=SCENARIO_NAME, evaluation_schema=cls.schema.name)
		cls.scenario.modality = "both"
		cls.scenario.save(ignore_permissions=True)
		if not frappe.db.exists("User", STUDENT):
			user = frappe.new_doc("User")
			user.email = STUDENT
			user.first_name = "Limits"
			user.send_welcome_email = 0
			user.append("roles", {"role": "LMS Student"})
			user.insert(ignore_permissions=True)
		frappe.db.commit()
		cls.sessions: list[str] = []

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for session in cls.sessions:
			for turn in frappe.get_all("LMSA Simulation Turn", {"session": session}, pluck="name"):
				frappe.delete_doc("LMSA Simulation Turn", turn, force=True, ignore_permissions=True)
			for debrief in frappe.get_all("LMSA Simulation Debrief", {"session": session}, pluck="name"):
				frappe.delete_doc("LMSA Simulation Debrief", debrief, force=True, ignore_permissions=True)
			if frappe.db.exists("LMSA Simulation Session", session):
				frappe.db.delete("LMSA Simulation Session", {"name": session})
		frappe.delete_doc("LMSA Simulation Scenario", cls.scenario.name, force=True, ignore_permissions=True)
		frappe.delete_doc("LMSA Evaluation Schema", cls.schema.name, force=True, ignore_permissions=True)
		for enrollment in frappe.get_all("LMS Enrollment", {"member": STUDENT}, pluck="name"):
			frappe.delete_doc("LMS Enrollment", enrollment, force=True, ignore_permissions=True)
		frappe.delete_doc("User", STUDENT, force=True, ignore_permissions=True)
		for field, value in cls.saved_settings.items():
			frappe.db.set_single_value("LMSA Settings", field, value)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		self._variant = patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
		self._variant.start()

	def tearDown(self):
		self._variant.stop()
		frappe.set_user("Administrator")

	def start_chat(self) -> str:
		result = SessionOrchestrator().start_session(scenario_id=self.scenario.name)
		self.sessions.append(result.session)
		return result.session

	def prepare_voice(self) -> str:
		result = SessionOrchestrator().prepare_session(scenario_id=self.scenario.name, modality="voice")
		self.sessions.append(result.session)
		return result.session


class TestLimitsSettings(SimulationLimitsCase):
	def test_values_below_one_are_refused(self):
		doc = frappe.get_single(LIMITS_DOCTYPE)
		doc.chat_messages_per_minute = 0
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_values_sent_as_strings_by_the_spa_are_checked(self):
		# The settings form posts numbers as strings through frappe.client.set_value.
		doc = frappe.get_single(LIMITS_DOCTYPE)
		doc.chat_messages_per_minute = "2"
		doc.validate()
		doc.chat_messages_per_minute = "0"
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_missing_values_fall_back_to_the_defaults(self):
		with patch.object(frappe.db, "get_single_value", return_value=None):
			self.assertEqual(load_limits(), _limits())

	def test_first_migrate_carries_over_the_old_voice_duration(self):
		saved = {f: frappe.db.get_single_value(LIMITS_DOCTYPE, f) for f in LIMIT_DEFAULTS}
		legacy = frappe.db.get_single_value("LMSA Settings", "realtime_max_session_seconds")
		try:
			frappe.db.delete("Singles", {"doctype": LIMITS_DOCTYPE})
			frappe.db.set_single_value("LMSA Settings", "realtime_max_session_seconds", 420)
			frappe.clear_cache(doctype=LIMITS_DOCTYPE)
			ensure_simulation_limits()
			self.assertEqual(frappe.db.get_single_value(LIMITS_DOCTYPE, "voice_max_session_seconds"), 420)
			self.assertEqual(frappe.db.get_single_value(LIMITS_DOCTYPE, "chat_messages_per_minute"), 20)
			# A later migrate keeps what someone saved.
			frappe.db.set_single_value(LIMITS_DOCTYPE, "chat_messages_per_minute", 7)
			ensure_simulation_limits()
			self.assertEqual(frappe.db.get_single_value(LIMITS_DOCTYPE, "chat_messages_per_minute"), 7)
		finally:
			frappe.db.set_single_value("LMSA Settings", "realtime_max_session_seconds", legacy)
			for field, value in saved.items():
				if value is not None:
					frappe.db.set_single_value(LIMITS_DOCTYPE, field, value)
			frappe.db.commit()

	def test_gestore_may_edit_the_limits(self):
		from os_lms.setup import GESTORE_DOCPERMS

		self.assertEqual(GESTORE_DOCPERMS[LIMITS_DOCTYPE], {"read": 1, "write": 1})


class TestChatLimits(SimulationLimitsCase):
	def test_message_longer_than_the_limit_is_refused(self):
		check_message_length("x" * 10, _limits(max_message_chars=10))
		with self.assertRaises(frappe.ValidationError):
			check_message_length("x" * 11, _limits(max_message_chars=10))

	def test_send_message_endpoint_checks_the_length(self):
		session = self.start_chat()
		with patched_limits(max_message_chars=5):
			with self.assertRaises(frappe.ValidationError):
				sim_api.send_message(session_id=session, text="troppo lungo")

	def test_messages_per_minute_are_capped_per_user(self):
		session = self.start_chat()
		_clear_rate_limit(CHAT_MESSAGE_ACTION, frappe.session.user)
		try:
			with patched_limits(chat_messages_per_minute=1), with_request():
				sim_api.send_message(session_id=session, text="Buongiorno")
				with self.assertRaises(frappe.RateLimitExceededError):
					sim_api.send_message(session_id=session, text="Ancora")
		finally:
			_clear_rate_limit(CHAT_MESSAGE_ACTION, frappe.session.user)

	def test_turn_cap_closes_then_locks_the_chat(self):
		session = self.start_chat()
		with patched_limits(max_messages_per_session=2):
			with patch("os_lms.os_lms.ai.simulations.orchestrator._closing_directive_text", return_value=""):
				orchestrator = SessionOrchestrator()
				with patch.object(orchestrator, "_ask_role_player", wraps=orchestrator._ask_role_player) as ask:
					orchestrator.send_message(session_id=session, user_text="Primo messaggio")
					self.assertEqual(ask.call_args.kwargs.get("closing_directive"), "")
					orchestrator.send_message(session_id=session, user_text="Secondo messaggio")
					self.assertTrue(ask.call_args.kwargs.get("closing_directive"))
			doc = frappe.get_doc("LMSA Simulation Session", session)
			self.assertTrue(closing_input_locked(doc, 0))
			with self.assertRaises(SessionTerminatedError):
				SessionOrchestrator().send_message(session_id=session, user_text="Terzo messaggio")

	def test_switching_simulations_off_stops_open_sessions(self):
		session = self.start_chat()
		frappe.db.set_single_value("LMSA Settings", "simulations_enabled", 0)
		try:
			with self.assertRaises(frappe.ValidationError):
				SessionOrchestrator().send_message(session_id=session, user_text="Ci sei?")
		finally:
			frappe.db.set_single_value("LMSA Settings", "simulations_enabled", 1)


class TestSessionGates(SimulationLimitsCase):
	def test_clone_session_needs_the_enrollment_again(self):
		frappe.set_user(STUDENT)
		session = self.start_chat()
		with self.assertRaises(frappe.PermissionError):
			sim_api.clone_session(session_id=session)

	def test_daily_quota_comes_from_the_limits_and_locks_the_student(self):
		doc = frappe._dict(student=STUDENT)
		with patched_limits(daily_sessions_per_user=1):
			with patch.object(frappe.db, "get_value", wraps=frappe.db.get_value) as get_value:
				with patch.object(frappe.db, "count", return_value=0):
					validate_quota(doc)
				with patch.object(frappe.db, "count", return_value=1):
					with self.assertRaises(QuotaExceededError):
						validate_quota(doc)
			get_value.assert_any_call("User", STUDENT, "name", for_update=True)


class TestVoiceTokens(SimulationLimitsCase):
	def test_tokens_per_session_are_capped(self):
		session = self.prepare_voice()
		with patched_limits(voice_tokens_per_session=2):
			SessionOrchestrator().start_voice_session(session_id=session)
			SessionOrchestrator().start_voice_session(session_id=session)
			with self.assertRaises(VoiceTokenLimitError):
				SessionOrchestrator().start_voice_session(session_id=session)
		self.assertEqual(frappe.db.get_value("LMSA Simulation Session", session, "realtime_tokens_issued"), 2)

	def test_endpoint_refuses_a_session_out_of_tokens(self):
		session = self.prepare_voice()
		with patched_limits(voice_tokens_per_session=1):
			rt_api.create_voice_session(session_id=session)
			with self.assertRaises(frappe.ValidationError):
				rt_api.create_voice_session(session_id=session)

	def test_tokens_per_hour_are_capped_per_user(self):
		first, second = self.prepare_voice(), self.prepare_voice()
		_clear_rate_limit(VOICE_TOKEN_ACTION, frappe.session.user)
		try:
			with patched_limits(voice_tokens_per_hour=1), with_request():
				rt_api.create_voice_session(session_id=first)
				with self.assertRaises(frappe.RateLimitExceededError):
					rt_api.create_voice_session(session_id=second)
		finally:
			_clear_rate_limit(VOICE_TOKEN_ACTION, frappe.session.user)

	def test_openai_secret_expires_soon(self):
		cfg = RealtimeSessionConfig(instructions="x", voice="", model="", start_window_seconds=60)
		config = frappe._dict(default_model="", voice="")
		self.assertEqual(_session_body(cfg, config)["expires_after"], {"anchor": "created_at", "seconds": 60})

	def test_gemini_token_ends_with_the_session(self):
		from datetime import datetime

		cfg = RealtimeSessionConfig(
			instructions="x", voice="", model="", max_session_seconds=300, start_window_seconds=60
		)
		config = frappe._dict(default_model="", voice="")
		body = _token_request(cfg, config)
		start = datetime.strptime(body["newSessionExpireTime"], "%Y-%m-%dT%H:%M:%SZ")
		end = datetime.strptime(body["expireTime"], "%Y-%m-%dT%H:%M:%SZ")
		self.assertEqual(body["uses"], 1)
		self.assertEqual((end - start).total_seconds(), 300)
