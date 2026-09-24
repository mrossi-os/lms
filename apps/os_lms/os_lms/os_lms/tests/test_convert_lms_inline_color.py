"""Unit tests for the v0_0_7 patch turning <lms-inline-color> into a colour span."""

from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.patches.v0_0_7 import convert_lms_inline_color as patch


class TestConvertLmsInlineColor(UnitTestCase):
	def test_element_becomes_a_colour_span(self):
		out = patch.convert_markup('a <lms-inline-color style="color: red;">b</lms-inline-color> c')
		self.assertEqual(out, 'a <span class="lms-inline-color" style="color: red;">b</span> c')

	def test_bare_element_and_existing_class(self):
		self.assertEqual(
			patch.convert_markup("<lms-inline-color>x</lms-inline-color>"),
			'<span class="lms-inline-color">x</span>',
		)
		self.assertEqual(
			patch.convert_markup('<lms-inline-color class="k" style="color: red">x</lms-inline-color>'),
			'<span class="lms-inline-color k" style="color: red">x</span>',
		)

	def test_only_strings_inside_the_json_change(self):
		raw = json.dumps(
			{
				"time": 1,
				"blocks": [
					{"type": "paragraph", "data": {"text": '<lms-inline-color style="color: red">x</lms-inline-color>'}}
				],
			}
		)
		data = json.loads(patch.convert_content(raw))
		self.assertEqual(data["time"], 1)
		self.assertEqual(
			data["blocks"][0]["data"]["text"], '<span class="lms-inline-color" style="color: red">x</span>'
		)

	def test_nothing_to_do_or_unreadable_returns_none(self):
		self.assertIsNone(patch.convert_content('{"blocks": []}'))
		self.assertIsNone(patch.convert_content(None))
		self.assertIsNone(patch.convert_content('{"blocks":[{"da <lms-inline-color>'))

	def test_converted_content_is_left_alone(self):
		once = patch.convert_content(json.dumps({"t": "<lms-inline-color>x</lms-inline-color>"}))
		self.assertIsNone(patch.convert_content(once))
