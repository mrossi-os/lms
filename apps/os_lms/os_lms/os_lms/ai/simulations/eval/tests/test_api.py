"""Integration tests for the eval API endpoints."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.simulations.eval import api


class TestEvalApi(IntegrationTestCase):
	def setUp(self):
		# Reset to Administrator so fixture inserts (Course, Schema, Scenario)
		# always pass permission checks regardless of which user the previous
		# test ended with.
		frappe.set_user("Administrator")
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_scenario_with_instructor,
		)
		self.scenario, self.instructor, self.outsider = (
			make_scenario_with_instructor()
		)

	def test_run_quick_check_creates_evaluation_and_enqueues(self):
		frappe.get_doc({
			"doctype": "LMSA Scenario Golden Run",
			"scenario": self.scenario.name,
			"name_label": "Default",
			"active": 1,
			"turns": "[]",
		}).insert(ignore_permissions=True)

		frappe.set_user(self.scenario.owner)
		with patch(
			"os_lms.os_lms.ai.simulations.eval.api.frappe.enqueue"
		) as enq:
			res = api.run_quick_check(scenario=self.scenario.name)

		self.assertIn("eval_id", res)
		evaluation = frappe.get_doc("LMSA Quality Evaluation", res["eval_id"])
		self.assertEqual(evaluation.run_mode, "quick")
		self.assertEqual(evaluation.status, "queued")
		enq.assert_called_once()
		self.assertEqual(
			enq.call_args.args[0],
			"os_lms.os_lms.ai.simulations.eval.jobs.run_authoring_evaluation",
		)
		self.assertEqual(enq.call_args.kwargs["eval_id"], res["eval_id"])

	def test_run_quick_check_rejects_without_golden(self):
		frappe.set_user(self.scenario.owner)
		with self.assertRaises(frappe.ValidationError):
			api.run_quick_check(scenario=self.scenario.name)

	def test_run_quick_check_blocks_outsider(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			api.run_quick_check(scenario=self.scenario.name)

	def test_get_evaluation_status_returns_fields(self):
		evaluation = frappe.get_doc({
			"doctype": "LMSA Quality Evaluation",
			"scenario": self.scenario.name,
			"run_mode": "quick",
			"status": "running",
			"triggered_by": self.scenario.owner,
			"triggered_at": frappe.utils.now_datetime(),
		}).insert(ignore_permissions=True)
		frappe.set_user(self.scenario.owner)
		out = api.get_evaluation_status(eval_id=evaluation.name)
		self.assertEqual(out["status"], "running")
		self.assertEqual(out["run_mode"], "quick")

	def test_save_and_list_goldens(self):
		frappe.set_user(self.scenario.owner)
		api.save_golden({
			"scenario": self.scenario.name,
			"name_label": "First",
			"active": True,
			"expected_outcomes": "Some notes",
			"turns": [
				{"role": "user", "text": "hi"},
				{"role": "assistant", "text": "hello"},
			],
		})
		rows = api.list_goldens(scenario=self.scenario.name)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["name_label"], "First")
		self.assertEqual(rows[0]["turn_count"], 2)
