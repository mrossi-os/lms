"""Endpoint tests for the simulations REST API.

These call the whitelisted Python entry points directly (the same way the
HTTP shell does) under different identities to exercise the permission gates.
"""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations import SessionOrchestrator
from os_lms.os_lms.ai.simulations.api import (
    begin_session,
    clone_session,
    end_session,
    get_session,
    list_my_sessions,
    list_scenarios,
    prepare_session,
    send_message,
    start_session,
)

from . import _fixtures as F


def _stub_generate_variant(self, scenario, seed, provider):
    return F.CANNED_VARIANT


def _make_student(email: str) -> str:
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = "Test"
    user.send_welcome_email = 0
    user.enabled = 1
    user.append("roles", {"role": "LMS Student"})
    user.insert(ignore_permissions=True)
    return user.name


def _enroll(user: str, course: str) -> str:
    name = frappe.db.get_value(
        "LMS Enrollment", {"member": user, "course": course}, "name"
    )
    if name:
        return name
    enr = frappe.new_doc("LMS Enrollment")
    enr.member = user
    enr.course = course
    enr.insert(ignore_permissions=True)
    return enr.name


class TestSimulationsAPI(UnitTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        F.cleanup_sessions_and_turns()
        F.enable_mock_provider()
        cls.schema = F.make_evaluation_schema(name="API Test Schema")
        cls.scenario = F.make_published_scenario(
            name="API Test Scenario", evaluation_schema=cls.schema.name
        )
        cls.draft_scenario = F.make_published_scenario(
            name="API Draft Scenario", evaluation_schema=cls.schema.name
        )
        # Roll it back to Draft to verify students can't see it.
        cls.draft_scenario.status = "Draft"
        cls.draft_scenario.save(ignore_permissions=True)
        frappe.db.commit()

        cls.student_email = "sim-test-student@elite.com"
        _make_student(cls.student_email)
        _enroll(cls.student_email, cls.scenario.lms_course)

    @classmethod
    def tearDownClass(cls):
        F.cleanup_sessions_and_turns()
        if frappe.db.exists("User", cls.student_email):
            for enr in frappe.get_all(
                "LMS Enrollment", filters={"member": cls.student_email}, pluck="name"
            ):
                frappe.delete_doc("LMS Enrollment", enr, force=True, ignore_permissions=True)
            frappe.delete_doc("User", cls.student_email, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"scenario_name": ["like", "API%"]},
            pluck="name",
        ):
            frappe.delete_doc("LMSA Simulation Scenario", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "LMSA Evaluation Schema", filters={"schema_name": "API Test Schema"}, pluck="name"
        ):
            frappe.delete_doc("LMSA Evaluation Schema", name, force=True, ignore_permissions=True)
        F.reset_settings()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self._patcher = patch.object(
            SessionOrchestrator, "_generate_variant", _stub_generate_variant
        )
        self._patcher.start()
        frappe.set_user(self.student_email)

    def tearDown(self):
        frappe.set_user("Administrator")
        F.cleanup_sessions_and_turns()
        self._patcher.stop()
        super().tearDown()

    # ----- list_scenarios -----

    def test_list_scenarios_returns_only_published_for_student(self):
        out = list_scenarios(course=self.scenario.lms_course)
        names = [s["name"] for s in out]
        self.assertIn(self.scenario.name, names)
        self.assertNotIn(self.draft_scenario.name, names)

    def test_list_scenarios_excludes_unenrolled_courses(self):
        # Different student, not enrolled in the course
        other = "sim-test-other@elite.com"
        _make_student(other)
        try:
            frappe.set_user(other)
            out = list_scenarios(course=self.scenario.lms_course)
            self.assertEqual(out, [])
        finally:
            frappe.set_user(self.student_email)
            frappe.delete_doc("User", other, force=True, ignore_permissions=True)

    # ----- start_session -----

    def test_start_session_returns_first_turn(self):
        result = start_session(scenario_id=self.scenario.name)
        self.assertIn("session", result)
        self.assertIn("first_turn", result)
        session = frappe.get_doc("LMSA Simulation Session", result["session"])
        self.assertEqual(session.student, self.student_email)
        self.assertEqual(session.status, "In Progress")

    def test_start_session_on_draft_scenario_denied(self):
        with self.assertRaises(frappe.PermissionError):
            start_session(scenario_id=self.draft_scenario.name)

    def test_start_session_on_unenrolled_course_denied(self):
        other = "sim-test-other2@elite.com"
        _make_student(other)
        try:
            frappe.set_user(other)
            with self.assertRaises(frappe.PermissionError):
                start_session(scenario_id=self.scenario.name)
        finally:
            frappe.set_user(self.student_email)
            frappe.delete_doc("User", other, force=True, ignore_permissions=True)

    # ----- send_message -----

    def test_send_message_returns_assistant_text(self):
        start = start_session(scenario_id=self.scenario.name)
        r = send_message(session_id=start["session"], text="Buongiorno")
        self.assertIn("assistant_turn", r)
        self.assertTrue(r["assistant_turn"]["text"])
        self.assertFalse(r["injection_attempt"])

    def test_send_message_empty_rejected(self):
        start = start_session(scenario_id=self.scenario.name)
        with self.assertRaises(frappe.exceptions.ValidationError):
            send_message(session_id=start["session"], text="   ")

    def test_send_message_other_user_denied(self):
        start = start_session(scenario_id=self.scenario.name)
        other = "sim-test-stranger@elite.com"
        _make_student(other)
        try:
            frappe.set_user(other)
            with self.assertRaises(frappe.PermissionError):
                send_message(session_id=start["session"], text="hi")
        finally:
            frappe.set_user(self.student_email)
            frappe.delete_doc("User", other, force=True, ignore_permissions=True)

    # ----- end_session + get_session -----

    def test_end_session_then_get_session_payload(self):
        start = start_session(scenario_id=self.scenario.name)
        send_message(session_id=start["session"], text="prima battuta")
        end = end_session(session_id=start["session"], reason="completed")
        self.assertEqual(end["status"], "Completed")

        payload = get_session(session_id=start["session"])
        self.assertEqual(payload["session"]["status"], "Completed")
        self.assertGreaterEqual(payload["session"]["turn_count"], 3)
        self.assertGreaterEqual(len(payload["turns"]), 3)
        roles = [t["role"] for t in payload["turns"]]
        self.assertEqual(roles[0], "assistant")  # first customer turn
        self.assertIn("user", roles)

    def test_end_session_unsupported_reason_rejected(self):
        start = start_session(scenario_id=self.scenario.name)
        with self.assertRaises(frappe.exceptions.ValidationError):
            end_session(session_id=start["session"], reason="bogus")

    # ----- prepare_session / begin_session -----

    def test_prepare_then_begin(self):
        prepared = prepare_session(scenario_id=self.scenario.name)
        self.assertIn("session_id", prepared)
        self.assertTrue(prepared["brief"])
        self.assertEqual(prepared["modality"], "chat")
        detail = get_session(session_id=prepared["session_id"])
        self.assertEqual(detail["session"]["status"], "Ready")
        self.assertEqual(len(detail["turns"]), 0)
        self.assertEqual(
            detail["session"]["student_brief"], prepared["brief"]
        )

        begun = begin_session(session_id=prepared["session_id"])
        self.assertTrue(begun["first_turn"]["text"])
        detail2 = get_session(session_id=prepared["session_id"])
        self.assertEqual(detail2["session"]["status"], "In Progress")
        self.assertEqual(len(detail2["turns"]), 1)

    def test_begin_session_is_idempotent(self):
        prepared = prepare_session(scenario_id=self.scenario.name)
        result1 = begin_session(session_id=prepared["session_id"])
        result2 = begin_session(session_id=prepared["session_id"])
        self.assertEqual(result1["first_turn"]["name"], result2["first_turn"]["name"])
        payload = get_session(session_id=prepared["session_id"])
        self.assertEqual(len(payload["turns"]), 1)
        self.assertEqual(payload["session"]["status"], "In Progress")

    # ----- list_my_sessions -----

    def test_list_my_sessions_returns_only_owner(self):
        prepared = prepare_session(scenario_id=self.scenario.name)
        rows = list_my_sessions(course=self.scenario.lms_course)
        names = [r["name"] for r in rows]
        self.assertIn(prepared["session_id"], names)
        row = next(r for r in rows if r["name"] == prepared["session_id"])
        self.assertEqual(row["scenario"], self.scenario.name)
        self.assertEqual(row["status"], "Ready")

        # Create a session owned by a different user and verify it is not visible
        # to the original student (isolation check). The session is inserted
        # directly (as Administrator) to avoid the enrollment-eligibility gate
        # on the unpublished test course.
        other = "sim-test-isolation@elite.com"
        _make_student(other)
        frappe.set_user("Administrator")
        other_session = frappe.new_doc("LMSA Simulation Session")
        other_session.student = other
        other_session.scenario = self.scenario.name
        other_session.modality = "chat"
        other_session.status = "Ready"
        other_session.insert(ignore_permissions=True)
        other_session_id = other_session.name
        frappe.set_user(self.student_email)
        try:
            rows_after = list_my_sessions(course=self.scenario.lms_course)
            names_after = [r["name"] for r in rows_after]
            self.assertNotIn(other_session_id, names_after)
        finally:
            frappe.delete_doc(
                "LMSA Simulation Session", other_session_id, force=True, ignore_permissions=True
            )
            frappe.delete_doc("User", other, force=True, ignore_permissions=True)

    # ----- clone_session -----

    def test_clone_session_endpoint(self):
        start = start_session(scenario_id=self.scenario.name)
        end_session(session_id=start["session"], reason="completed")
        clone = clone_session(session_id=start["session"])
        self.assertNotEqual(clone["session_id"], start["session"])
        self.assertTrue(clone["brief"])
        self.assertIn("modality", clone)
        detail = get_session(session_id=clone["session_id"])
        self.assertEqual(detail["session"]["status"], "Ready")
