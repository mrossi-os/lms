"""Render the course completion certificate (Print Format) to a PNG.

The completion certificate is a Jinja Print Format whose CSS uses a portrait
page with the landscape design rotated 90° — so it must be rendered by the
Chrome PDF generator (wkhtmltopdf ignores transform:rotate). To reuse that
design as the Openbadge image, this module renders a *sample* certificate for a
given course, rasterizes the first PDF page via PyMuPDF (already a project
dependency), and rotates it back to a readable landscape orientation.

The sample ``LMS Certificate`` is never persisted, so no ``after_insert``
emission hook fires.
"""

import base64
import io

import frappe
from frappe.utils import nowdate

from lms.lms.doctype.lms_certificate.lms_certificate import (
	get_default_certificate_template,
)

from .client import TrueSkillsError

# The certificate Print Format renders as a PORTRAIT page with the landscape
# design rotated 90° (so the downloadable PDF fills a portrait sheet). For the
# openbadge we want a readable LANDSCAPE image, so we rotate the rasterized page
# back. 270 (i.e. 90° counter-clockwise) undoes the template's rotate(90deg).
# Flip to 90 if the badge ever comes out upside down.
_RASTER_ROTATION = 270


def build_certificate_png_data_uri(course: str, dpi: int = 150) -> str:
	"""Return a ``data:image/png;base64,...`` of the course completion certificate.

	A sample (unsaved) ``LMS Certificate`` is rendered through the certificate
	Print Format with the session user as a placeholder holder. Raises
	``TrueSkillsError`` with a stable message on any failure.
	"""
	from frappe.utils.pdf import get_chrome_pdf
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
		# The template controls page geometry and rotation through its own CSS
		# (@page / .print-format / transform: rotate). Render with the Chrome PDF
		# generator: wkhtmltopdf ignores transform:rotate and would output a blank
		# page. Passing the real print_format lets Chrome apply its page settings,
		# matching the downloadable certificate.
		full_html = (
			"<!DOCTYPE html><html><head><meta charset='utf-8'>"
			f"<style>{style}</style></head><body>{html}</body></html>"
		)
		pdf = get_chrome_pdf(print_format, full_html, {}, None, pdf_generator="chrome")
		if pdf is None:
			raise TrueSkillsError("Chrome PDF generator is not available.")
		# transform_pdf may return bytes, a BytesIO, or a PdfWriter.
		if isinstance(pdf, bytes | bytearray):
			pdf_bytes = bytes(pdf)
		elif hasattr(pdf, "getvalue"):
			pdf_bytes = pdf.getvalue()
		else:
			buffer = io.BytesIO()
			pdf.write(buffer)
			pdf_bytes = buffer.getvalue()
	except TrueSkillsError:
		raise
	except Exception as exc:
		raise TrueSkillsError(f"Could not render the certificate PDF: {exc}") from exc

	png_bytes = _pdf_first_page_to_png(pdf_bytes, dpi=dpi, rotation=_RASTER_ROTATION)
	encoded = base64.b64encode(png_bytes).decode("ascii")
	return f"data:image/png;base64,{encoded}"


def _pdf_first_page_to_png(pdf_bytes: bytes, dpi: int = 150, rotation: int = 0) -> bytes:
	"""Rasterize the first PDF page to PNG bytes via PyMuPDF.

	``rotation`` (a multiple of 90) rotates the rendered page clockwise, used to
	turn the portrait rotated certificate back into a readable landscape image.
	"""
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
		if rotation:
			page.set_rotation((page.rotation + rotation) % 360)
		zoom = dpi / 72.0
		pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
		return pix.tobytes("png")
	finally:
		pdf.close()
