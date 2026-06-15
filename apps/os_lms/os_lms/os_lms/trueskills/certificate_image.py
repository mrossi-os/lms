"""Render the course completion certificate (Print Format) to a PNG.

The completion certificate is a Jinja Print Format rendered to PDF by
wkhtmltopdf (per-learner, on demand). To reuse that design as the Openbadge
image, this module renders a *sample* certificate for a given course and
rasterizes the first PDF page to PNG via PyMuPDF (already a project dependency).

The sample ``LMS Certificate`` is never persisted, so no ``after_insert``
emission hook fires.
"""

import base64

import frappe
from frappe.utils import nowdate

from lms.lms.doctype.lms_certificate.lms_certificate import (
	get_default_certificate_template,
)

from .client import TrueSkillsError


def build_certificate_png_data_uri(course: str, dpi: int = 150) -> str:
	"""Return a ``data:image/png;base64,...`` of the course completion certificate.

	A sample (unsaved) ``LMS Certificate`` is rendered through the certificate
	Print Format with the session user as a placeholder holder. Raises
	``TrueSkillsError`` with a stable message on any failure.
	"""
	from frappe.utils.pdf import get_pdf
	from frappe.www.printview import get_html_and_style

	print_format = get_default_certificate_template()
	if not print_format:
		raise TrueSkillsError("No certificate Print Format is configured.")

	# Render an in-memory (unsaved) certificate via the JSON-doc path. Passing a
	# Document object to frappe.get_print does not survive the printview round
	# trip (it falls back to get_doc by name=None), and inserting a real doc
	# would run validation (course enrollment) and fire after_insert (which
	# sends a certification email). get_html_and_style rebuilds the doc from a
	# dict — nothing is persisted, no hook fires.
	doc_json = frappe.as_json(
		{
			"doctype": "LMS Certificate",
			"member": frappe.session.user,
			"course": course,
			"issue_date": nowdate(),
			"template": print_format,
		}
	)

	try:
		rendered = get_html_and_style(
			doc=doc_json, print_format=print_format, no_letterhead=1
		)
		html = (rendered or {}).get("html") or ""
		style = (rendered or {}).get("style") or ""
		if not html.strip():
			raise TrueSkillsError("Certificate render produced empty HTML.")
		# The certificate Print Format is landscape; force it so the design is
		# not squeezed onto a portrait page (which crops the right edge and
		# leaves the lower half blank).
		full_html = (
			"<!DOCTYPE html><html><head><meta charset='utf-8'>"
			"<meta name='pdfkit-orientation' content='Landscape'>"
			f"<style>{style}</style></head><body>{html}</body></html>"
		)
		pdf_bytes = get_pdf(full_html, options={"orientation": "Landscape"})
	except TrueSkillsError:
		raise
	except Exception as exc:
		raise TrueSkillsError(f"Could not render the certificate PDF: {exc}") from exc

	png_bytes = _pdf_first_page_to_png(pdf_bytes, dpi=dpi)
	encoded = base64.b64encode(png_bytes).decode("ascii")
	return f"data:image/png;base64,{encoded}"


def _pdf_first_page_to_png(pdf_bytes: bytes, dpi: int = 150) -> bytes:
	"""Rasterize the first PDF page to PNG bytes via PyMuPDF."""
	try:
		import fitz  # PyMuPDF
	except ImportError as exc:  # pragma: no cover - declared in pyproject
		raise TrueSkillsError(
			"PyMuPDF (fitz) is required to convert the certificate PDF to PNG."
		) from exc

	pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
	try:
		if pdf.page_count == 0:
			raise TrueSkillsError("Rendered certificate PDF has no pages.")
		page = pdf.load_page(0)
		zoom = dpi / 72.0
		pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
		return pix.tobytes("png")
	finally:
		pdf.close()
