"""Lesson progress guard in front of lms course_lesson.save_progress.

Upstream takes `scorm_details` from the browser and, when present, marks the
lesson "Complete" without checking quizzes and assignments. It never checks that
the lesson is a SCORM one, so any enrolled student could complete every lesson
of a course, and get its certificate (and TrueSkills badge), by posting
scorm_details={"is_complete": 1}. Here SCORM details count only on a lesson of a
SCORM chapter; anywhere else the call takes the normal path, with its checks.

Upstream also completes a lesson nobody opened: the dwell time and the video
rules live only in the page (OWASP audit 2026-10-29, H-1). Here a lesson is
completed only after the server handed it out to the same user (get_lesson or
the SCORM player), and, when enforce_video_completion is on, only once the page
recorded a watch time for it. Both are reported by the browser, so this stops a
script calling the completion API alone, not a student skipping the video.
"""

import frappe
from frappe import _
from frappe.utils import cint
from lms.lms.doctype.course_chapter.course_chapter import get_scorm_playback as lms_get_scorm_playback
from lms.lms.doctype.course_lesson.course_lesson import get_lesson_course
from lms.lms.doctype.course_lesson.course_lesson import save_progress as lms_save_progress
from lms.lms.md import find_macros
from lms.lms.utils import get_editorjs_blocks

# Long enough for a lesson left open for days; a reload records it again.
LESSON_OPEN_TTL = 7 * 24 * 3600

# The videos Lesson.vue reports a watch time for: a <video> with a src (EditorJS
# upload block) or a Plyr `.video-player` (YouTube/Vimeo embeds, the youtube field,
# the YouTubeVideo macro). Cloudflare/Bunny iframes and the legacy {{ Video }}
# macro (<source> child, empty video.src) are never reported, so they don't count.
VIDEO_UPLOAD_TYPES = {"mp4", "webm", "ogg", "mov"}
VIDEO_EMBED_SERVICES = {"youtube", "vimeo"}


@frappe.whitelist()
def save_progress(lesson: str, course: str | None = None, scorm_details: dict = None):
	if scorm_details and not is_scorm_lesson(lesson):
		scorm_details = None
	if isinstance(lesson, str):
		assert_can_complete(lesson, scorm_details)
	return lms_save_progress(lesson, course, scorm_details)


@frappe.whitelist()
def mark_lesson_progress(course: str, chapter_number: int, lesson_number: int):
	# Upstream's api.mark_lesson_progress (quiz and assignment pages) imports the
	# original save_progress, so it would skip every check above.
	chapter_name = frappe.get_value("Chapter Reference", {"parent": course, "idx": chapter_number}, "chapter")
	lesson_name = frappe.get_value(
		"Lesson Reference", {"parent": chapter_name, "idx": lesson_number}, "lesson"
	)
	save_progress(lesson_name, course)


@frappe.whitelist()
def get_scorm_playback(chapter: str) -> dict:
	# The SCORM player never calls get_lesson: its lesson is opened here.
	playback = lms_get_scorm_playback(chapter)
	record_lesson_open(playback.get("lesson"))
	return playback


def assert_can_complete(lesson: str, scorm_details: dict | None = None) -> None:
	# Without an enrollment upstream records nothing and answers 0: leave it that
	# way for staff previewing a lesson.
	course = get_lesson_course(lesson)
	if not course or not frappe.db.exists("LMS Enrollment", {"course": course, "member": frappe.session.user}):
		return
	if not was_lesson_opened(lesson):
		frappe.throw(_("Open the lesson before marking it as done."), frappe.PermissionError)
	if not scorm_details and is_video_watch_missing(lesson):
		frappe.throw(_("Watch the lesson video before marking it as done."), frappe.ValidationError)


def record_lesson_open(lesson) -> None:
	if isinstance(lesson, str) and lesson and frappe.session.user != "Guest":
		frappe.cache.set_value(_lesson_open_key(lesson), 1, expires_in_sec=LESSON_OPEN_TTL)


def was_lesson_opened(lesson: str) -> bool:
	return bool(frappe.cache.get_value(_lesson_open_key(lesson)))


def _lesson_open_key(lesson: str) -> str:
	return f"os_lms:lesson_open:{frappe.session.user}:{lesson}"


def is_video_watch_missing(lesson: str) -> bool:
	if not cint(frappe.get_cached_value("LMS Settings", None, "enforce_video_completion")):
		return False
	member = frappe.session.user
	if frappe.db.exists("LMS Course Progress", {"lesson": lesson, "member": member, "status": "Complete"}):
		return False
	if not has_tracked_video(lesson):
		return False
	# Any watch time, 0 included: a video that fails to load is still reported (at 0)
	# before the page falls back to its dwell timer.
	return not frappe.db.exists("LMS Video Watch Duration", {"lesson": lesson, "member": member})


def has_tracked_video(lesson: str) -> bool:
	row = frappe.db.get_value("Course Lesson", lesson, ["content", "body", "youtube"], as_dict=True)
	if not row:
		return False
	# Same precedence as Lesson.vue: EditorJS content, when present, replaces the body.
	if row.content:
		for block in get_editorjs_blocks(row.content):
			data = block.get("data") or {}
			if block.get("type") == "upload" and (data.get("file_type") or "").lower() in VIDEO_UPLOAD_TYPES:
				return True
			if block.get("type") == "embed" and data.get("service") in VIDEO_EMBED_SERVICES:
				return True
		return False
	if not row.body:
		return False
	if row.youtube:
		return True
	return any(name == "YouTubeVideo" and arg for name, arg in find_macros(row.body))


def is_scorm_lesson(lesson) -> bool:
	if not isinstance(lesson, str):
		return False
	chapter = frappe.db.get_value("Course Lesson", lesson, "chapter")
	return bool(chapter and frappe.db.get_value("Course Chapter", chapter, "is_scorm_package"))
