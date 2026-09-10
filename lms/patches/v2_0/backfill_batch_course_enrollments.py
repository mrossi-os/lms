import frappe

from lms.lms.utils import enroll_batch_students_in_courses


def execute():
	"""Enroll batch students in the batch courses they were never enrolled in.

	Course enrollments used to be created only when a student joined a batch, so
	every course added to a batch afterwards stayed out of the course list of the
	students already enrolled. LMSBatch.on_update now enrolls them as soon as a
	course is added; this backfills the batches that predate it.
	"""
	batches = frappe.get_all("LMS Batch", pluck="name")

	for batch in batches:
		courses = frappe.get_all("Batch Course", {"parent": batch}, pluck="course")

		# One unexpected batch must not abort the whole migration: log it, move on,
		# and let the lazy enrollment in get_batch_courses cover that batch instead.
		try:
			enroll_batch_students_in_courses(batch, courses)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title="Backfill of batch course enrollments failed",
				message=f"Batch: {batch}\n\n{frappe.get_traceback()}",
			)
		else:
			frappe.db.commit()
