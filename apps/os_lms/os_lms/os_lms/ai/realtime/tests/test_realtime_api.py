"""Endpoint tests for the realtime (voice) feature layer.

Call the whitelisted Python entry points directly under the student identity,
mirroring simulations/tests/test_api.py. realtime_provider="mock" so no
network is involved; _generate_variant is stubbed to a canned persona.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.realtime import api as rt_api
from os_lms.os_lms.ai.simulations.api import prepare_session
from os_lms.os_lms.ai.simulations.orchestrator import SessionOrchestrator
from os_lms.os_lms.ai.simulations.tests import _fixtures as F


def _stub_generate_variant(self, scenario, seed, provider):
	return F.CANNED_VARIANT


def _make_student(email: str) -> str:
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = "Voice"
	user.send_welcome_email = 0
	user.enabled = 1
	user.append("roles", {"role": "LMS Student"})
	user.insert(ignore_permissions=True)
	return user.name


def _enroll(user: str, course: str) -> None:
	if not frappe.db.get_value("LMS Enrollment", {"member": user, "course": course}):
		enr = frappe.new_doc("LMS Enrollment")
		enr.member = user
		enr.course = course
		enr.insert(ignore_permissions=True)


class TestRealtimeApi(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		F.cleanup_sessions_and_turns()
		F.enable_mock_provider()  # sets simulations_enabled + chat/debrief = mock
		s = frappe.get_single("LMSA Settings")
		s.realtime_enabled = 1
		s.realtime_provider = "mock"
		s.realtime_max_session_seconds = 300
		s.save(ignore_permissions=True)
		cls.scenario = F.make_published_scenario(name="Voice Test Scenario")
		cls.scenario.modality = "voice"
		cls.scenario.save(ignore_permissions=True)
		cls.student = _make_student("voice-student@example.com")
		_enroll(cls.student, cls.scenario.lms_course)
		frappe.db.commit()

	def setUp(self):
		frappe.set_user(self.student)

	def tearDown(self):
		frappe.set_user("Administrator")

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_create_voice_session_from_prepared(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		res = rt_api.create_voice_session(session_id=prepared["session_id"])
		self.assertEqual(res["session_id"], prepared["session_id"])
		self.assertTrue(res["transport"])

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_create_persist_end_roundtrip(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		out = rt_api.create_voice_session(session_id=prepared["session_id"])
		self.assertEqual(out["transport"], "mock")
		self.assertTrue(out["client_secret"].startswith("mock-secret-"))
		self.assertEqual(out["max_seconds"], 300)

		sid = out["session_id"]
		# Audit fields recorded.
		self.assertEqual(
			frappe.db.get_value("LMSA Simulation Session", sid, "realtime_provider_used"), "mock"
		)

		rt_api.persist_transcript_turn(session_id=sid, role="user", text="Salve")
		rt_api.persist_transcript_turn(session_id=sid, role="assistant", text="Benvenuto")

		ended = rt_api.end_voice_session(session_id=sid, reason="completed", seconds=42)
		self.assertEqual(ended["status"], "Completed")
		self.assertEqual(frappe.db.get_value("LMSA Simulation Session", sid, "session_seconds"), 42)
		turns = frappe.get_all(
			"LMSA Simulation Turn", filters={"session": sid}, fields=["role", "text_content"]
		)
		self.assertEqual({t["role"] for t in turns}, {"user", "assistant"})

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_duration_exceeded_terminates_session(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		out = rt_api.create_voice_session(session_id=prepared["session_id"])
		sid = out["session_id"]
		# Backdate started_at well past the 300-second limit.
		frappe.db.set_value(
			"LMSA Simulation Session",
			sid,
			"started_at",
			frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=-(300 + 60)),
		)
		frappe.db.commit()
		with self.assertRaises(frappe.ValidationError):
			rt_api.persist_transcript_turn(session_id=sid, role="user", text="late")
		status = frappe.db.get_value("LMSA Simulation Session", sid, "status")
		from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import TERMINAL_STATUSES

		self.assertIn(status, TERMINAL_STATUSES)

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_non_owner_cannot_persist_turn(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		out = rt_api.create_voice_session(session_id=prepared["session_id"])
		sid = out["session_id"]
		# A second student (not enrolled, not moderator) must not relay turns.
		second_student = _make_student("voice-student-2@example.com")
		frappe.db.commit()
		frappe.set_user(second_student)
		try:
			with self.assertRaises(frappe.PermissionError):
				rt_api.persist_transcript_turn(session_id=sid, role="user", text="intruder")
		finally:
			frappe.set_user(self.student)

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_non_owner_cannot_end_session(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		out = rt_api.create_voice_session(session_id=prepared["session_id"])
		sid = out["session_id"]
		# A second student (not enrolled, not moderator) must not end the session.
		second_student = _make_student("voice-student-3@example.com")
		frappe.db.commit()
		frappe.set_user(second_student)
		try:
			with self.assertRaises(frappe.PermissionError):
				rt_api.end_voice_session(session_id=sid, reason="completed")
		finally:
			frappe.set_user(self.student)

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_non_owner_cannot_create_voice_session(self):
		prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
		# A second student (not enrolled, not moderator) must not activate the session.
		second_student = _make_student("voice-student-4@example.com")
		frappe.db.commit()
		frappe.set_user(second_student)
		try:
			with self.assertRaises(frappe.PermissionError):
				rt_api.create_voice_session(session_id=prepared["session_id"])
		finally:
			frappe.set_user(self.student)

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_non_realtime_provider_override_falls_back(self):
		"""Fix 1: a scenario with provider_override='anthropic' (non-realtime) must NOT
		raise a ValueError / 500 — it falls back to the realtime settings default (mock)."""
		original_override = self.scenario.provider_override
		self.scenario.provider_override = "anthropic"
		self.scenario.save(ignore_permissions=True)
		frappe.db.commit()
		try:
			prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
			out = rt_api.create_voice_session(session_id=prepared["session_id"])
			self.assertEqual(out["transport"], "mock")
		finally:
			self.scenario.provider_override = original_override
			self.scenario.save(ignore_permissions=True)
			frappe.db.commit()
