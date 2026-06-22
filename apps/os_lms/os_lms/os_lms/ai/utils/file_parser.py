# os_lms/utils/file_parser.py

import frappe

from .file_transcriber import FileTranscriber


class FrappeFileParser:
	"""Extract text content from a Frappe ``File`` doctype record.

	Mirrors :class:`LessonContentParser`: the constructor takes the
	record identifier and ``extract_text`` returns the raw text.
	"""

	def __init__(self, file_name: str):
		"""
		file_name: name of the ``File`` doctype record holding the asset.
		"""
		self.file_name = file_name
		self._file_doc = None

	# ------------------------------------------------------------------
	# Lazy load of the File doc
	# ------------------------------------------------------------------

	@property
	def file_doc(self):
		if self._file_doc is None and self.file_name:
			self._file_doc = frappe.get_doc("File", self.file_name)
		return self._file_doc

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def extract_text(self) -> str:
		"""Return the textual content of the file (PDF, DOCX, TXT, PPTX)."""
		doc = self.file_doc
		if not doc or not getattr(doc, "file_url", None):
			return ""

		file_type = self._extract_extension(getattr(doc, "file_name", "") or doc.file_url)
		if not file_type:
			return ""

		return FileTranscriber().transcribe(doc.file_url, file_type)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _extract_extension(self, value: str) -> str:
		if not value or "." not in value:
			return ""
		return value.rsplit(".", 1)[1].lower()
