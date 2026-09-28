"""Give images already in program and course descriptions a public copy.

The description editors uploaded images as private Files attached to nothing,
and Frappe serves such a file only to its uploader (and Administrator): every
other reader got a 403 and a broken image. The editors now upload public; this
repoints the images saved before. Each private image gets a public copy
attached to the document and the <img src> is rewritten to it. The private
original is left untouched, since other content may still point at it.
Idempotent: a rewritten description has no private image left.
"""

import html
import re
from urllib.parse import unquote

import frappe

TARGETS = (("LMS Program", "description"), ("LMS Course", "description"))
PRIVATE_IMG_SRC = re.compile(r"""(<img\b[^>]*?\bsrc\s*=\s*)(["'])(/private/files/[^"']+)\2""", re.IGNORECASE)


def private_image_urls(text: str | None) -> list[str]:
	"""The distinct private file URLs used as <img src>, in document order."""
	if not text:
		return []
	return list(dict.fromkeys(match.group(3) for match in PRIVATE_IMG_SRC.finditer(text)))


def replace_image_urls(text: str, mapping: dict[str, str]) -> str:
	"""Rewrite <img src> values found in mapping; other sources stay as they are."""

	def repoint(match: re.Match) -> str:
		new_url = mapping.get(match.group(3))
		if not new_url:
			return match.group(0)
		return f"{match.group(1)}{match.group(2)}{new_url}{match.group(2)}"

	return PRIVATE_IMG_SRC.sub(repoint, text)


def find_private_file(src: str) -> str | None:
	"""The File name behind an <img src>, which may be entity- or URL-encoded."""
	path = html.unescape(src).split("?", 1)[0]
	for url in dict.fromkeys((path, unquote(path))):
		name = frappe.db.get_value("File", {"file_url": url, "is_folder": 0}, "name")
		if name:
			return name
	return None


def make_public_copy(src: str, doctype: str, docname: str) -> str | None:
	file_name = find_private_file(src)
	if not file_name:
		return None
	private_file = frappe.get_doc("File", file_name)
	try:
		content = private_file.get_content()
	except OSError:
		return None
	public_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": private_file.file_name,
			"is_private": 0,
			"content": content,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
		}
	)
	public_file.insert(ignore_permissions=True)
	return public_file.file_url


def publish_document_images(doctype: str, docname: str, field: str) -> None:
	text = frappe.db.get_value(doctype, docname, field)
	mapping = {}
	for src in private_image_urls(text):
		try:
			public_url = make_public_copy(src, doctype, docname)
		except Exception:
			frappe.log_error(title=f"Description image not published: {doctype} {docname} {src}")
			continue
		if public_url:
			mapping[src] = public_url
	if mapping:
		frappe.db.set_value(doctype, docname, field, replace_image_urls(text, mapping), update_modified=False)


def execute():
	for doctype, field in TARGETS:
		for docname in frappe.get_all(doctype, filters={field: ["like", "%/private/files/%"]}, pluck="name"):
			publish_document_images(doctype, docname, field)
