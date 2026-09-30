"""Tests for the v0_0_9 patch giving description images a public copy.

The regression: images in program/course descriptions were uploaded as private
Files attached to nothing, so only their uploader could load them.
"""

from __future__ import annotations

import base64

import frappe

from lms.lms.test_helpers import BaseTestUtils
from os_lms.patches.v0_0_9 import publish_description_images as patch

# 1x1 transparent PNG
PNG = base64.b64decode(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class TestPublishDescriptionImagesMarkup(BaseTestUtils):
	def test_finds_only_private_img_sources(self):
		text = (
			'<p><img src="/private/files/a.png" width="10"></p>'
			"<p><img src='/files/b.png'><a href=\"/private/files/c.pdf\">c</a></p>"
			'<img data-align="center" src="/private/files/a.png">'
		)
		self.assertEqual(patch.private_image_urls(text), ["/private/files/a.png"])
		self.assertEqual(patch.private_image_urls(None), [])

	def test_rewrites_mapped_sources_only(self):
		text = '<img src="/private/files/a b.png" width="10"><img src="/private/files/x.png">'
		out = patch.replace_image_urls(text, {"/private/files/a b.png": "/files/a b.png"})
		self.assertEqual(out, '<img src="/files/a b.png" width="10"><img src="/private/files/x.png">')


class TestPublishDescriptionImages(BaseTestUtils):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		private_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"desc-img-{frappe.generate_hash(length=8)}.png",
				"is_private": 1,
				# Unique bytes: Frappe reuses an existing file with the same content hash.
				"content": PNG + frappe.generate_hash().encode(),
			}
		).insert(ignore_permissions=True)
		self.private_file = private_file

		self.description = (
			f'<p>Intro</p><p><img src="{private_file.file_url}" width="1" data-align="center"></p>'
			'<p><img src="https://example.com/external.png"></p>'
		)
		program = frappe.get_doc(
			{
				"doctype": "LMS Program",
				"title": f"Description Image Program {frappe.generate_hash(length=8)}",
				"description": self.description,
			}
		).insert(ignore_permissions=True)
		self.program = program.name

	def _public_copies(self):
		return frappe.get_all(
			"File",
			filters={"attached_to_doctype": "LMS Program", "attached_to_name": self.program},
			fields=["name", "file_url", "is_private"],
		)

	def test_private_image_gets_a_public_copy(self):
		patch.publish_document_images("LMS Program", self.program, "description")
		copies = self._public_copies()

		self.assertEqual(len(copies), 1)
		self.assertEqual(copies[0].is_private, 0)
		self.assertTrue(copies[0].file_url.startswith("/files/"))

		text = frappe.db.get_value("LMS Program", self.program, "description")
		self.assertIn(f'src="{copies[0].file_url}"', text)
		self.assertNotIn("/private/files/", text)
		self.assertIn('src="https://example.com/external.png"', text)
		self.assertIn('data-align="center"', text)

		# The private original is left in place for anything else pointing at it.
		original = frappe.get_doc("File", self.private_file.name)
		self.assertEqual(original.is_private, 1)
		self.assertTrue(original.exists_on_disk())

	def test_second_run_changes_nothing(self):
		patch.publish_document_images("LMS Program", self.program, "description")
		first = frappe.db.get_value("LMS Program", self.program, "description")
		patch.publish_document_images("LMS Program", self.program, "description")
		copies = self._public_copies()

		self.assertEqual(frappe.db.get_value("LMS Program", self.program, "description"), first)
		self.assertEqual(len(copies), 1)

	def test_missing_file_is_left_alone(self):
		text = '<p><img src="/private/files/does-not-exist-anywhere.png"></p>'
		frappe.db.set_value("LMS Program", self.program, "description", text)
		patch.publish_document_images("LMS Program", self.program, "description")

		self.assertEqual(frappe.db.get_value("LMS Program", self.program, "description"), text)
		self.assertEqual(self._public_copies(), [])
