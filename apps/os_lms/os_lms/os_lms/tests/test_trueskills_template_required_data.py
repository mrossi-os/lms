"""TrueSkill templates that ask for data the platform never sends (requiredData).

The emission sends no requiredData, so TrueSkill refuses such a template with
required_data_missing (collaudo v2.65 on elite, 2026-10-13: template 10 "Certificato 1").
The course save refuses the template, and the learner's "Get certificate" says why
without creating a certificate that could only fail.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.trueskills import api
from os_lms.os_lms.trueskills.client import TrueSkillsError
from os_lms.os_lms.trueskills.service import TrueSkillsService

WITH_DATA = {
	"name": "Certificato 1",
	"data": {"requiredData": [{"code": "p1", "label": "Performance 1"}, {"code": "p2", "label": "Performance 2"}]},
}
WITHOUT_DATA = {"name": "Certificato corso", "data": {"requiredData": []}}


def template(payload=None, error=None):
	return patch.object(
		TrueSkillsService, "get_template", return_value=payload, side_effect=error
	)


class FakeCourse(frappe._dict):
	def is_new(self):
		return False

	def has_value_changed(self, field):
		return field in self.get("changed", ())


class TestTemplateRequiredData(UnitTestCase):
	def test_lists_the_labels_the_template_asks_for(self):
		with template(WITH_DATA):
			self.assertEqual(
				api.template_required_data(10), ("Certificato 1", ["Performance 1", "Performance 2"])
			)

	def test_a_template_without_required_data_has_none(self):
		with template(WITHOUT_DATA):
			self.assertEqual(api.template_required_data(11)[1], [])

	def test_an_unreachable_service_blocks_nothing(self):
		with template(error=TrueSkillsError("down")):
			self.assertEqual(api.template_required_data(10), ("", []))

	def test_no_template_reads_nothing(self):
		with template(WITH_DATA) as get_template:
			self.assertEqual(api.template_required_data(None), ("", []))
		get_template.assert_not_called()


class TestCourseSaveRefusesTheTemplate(UnitTestCase):
	def _validate(self, payload, **course):
		doc = FakeCourse(trueskills_certificate_enabled=1, trueskills_template_id="10", **course)
		with template(payload):
			api.validate_course_template(doc)

	def test_choosing_a_template_with_required_data_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._validate(WITH_DATA, changed=("trueskills_template_id",))

	def test_a_template_without_required_data_saves(self):
		self._validate(WITHOUT_DATA, changed=("trueskills_template_id",))

	def test_an_unchanged_template_is_not_rechecked(self):
		with template(WITH_DATA) as get_template:
			api.validate_course_template(
				FakeCourse(trueskills_certificate_enabled=1, trueskills_template_id="10")
			)
		get_template.assert_not_called()

	def test_a_course_without_trueskill_is_left_alone(self):
		with template(WITH_DATA) as get_template:
			api.validate_course_template(
				FakeCourse(trueskills_certificate_enabled=0, trueskills_template_id="10", changed=("trueskills_template_id",))
			)
		get_template.assert_not_called()


class TestLearnerIsToldBeforeAnyCertificate(UnitTestCase):
	def _get(self, payload):
		flags = frappe._dict(trueskills_certificate_enabled=1, trueskills_template_id="10")
		with (
			template(payload),
			patch.object(api.frappe.db, "get_value", return_value=flags),
			patch("lms.lms.doctype.lms_certificate.lms_certificate.is_certified", return_value=None),
			patch.object(api, "_ensure_trueskill_certificate", return_value="CERT-1") as ensure,
			patch.object(TrueSkillsService, "is_ready", return_value=False),
		):
			return api.get_course_certificate("any-course"), ensure

	def test_a_template_with_required_data_creates_no_certificate(self):
		result, ensure = self._get(WITH_DATA)
		ensure.assert_not_called()
		self.assertEqual(result["error"], "template_requires_data")
		self.assertEqual(result["state"], "unavailable")

	def test_a_supported_template_goes_on_as_before(self):
		result, ensure = self._get(WITHOUT_DATA)
		ensure.assert_called_once()
		self.assertEqual(result["lms_certificate"], "CERT-1")
