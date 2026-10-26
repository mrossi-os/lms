"""Regression tests for the OWASP Top 10 fixes of 2026-10 (ESG point 4).

One class per finding of docs/security/owasp-top10-2026-10-23.md, named after
its id. They patch Frappe's lookups instead of writing records, so nothing is
left in the database.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

STUDENT = "owasp-test-student@example.com"


def _session(user):
	return patch.dict(frappe.session, {"user": user})


def _roles(*roles):
	return patch.object(frappe, "get_roles", return_value=list(roles))


class FakeRequest:
	"""Just enough of a werkzeug request for code that reads frappe.request."""

	def __init__(self, query_string="", method="GET", form=None, data=b"", path="/api/method/x"):
		self.query_string = query_string.encode()
		self.method = method
		self.form = form or {}
		self.data = data
		self.full_path = f"{path}?{query_string}"


class with_request:
	def __init__(self, request=None):
		self.request = request or FakeRequest()

	def __enter__(self):
		self.previous = getattr(frappe.local, "request", None)
		frappe.local.request = self.request
		return self.request

	def __exit__(self, *exc):
		if self.previous is None:
			del frappe.local.request
		else:
			frappe.local.request = self.previous


class TestC1AnnouncementTemplateInjection(UnitTestCase):
	def test_only_the_known_placeholders_are_filled(self):
		from os_lms.os_lms.api import fill_announcement_placeholders

		values = {"message": "Ciao {{ message }}", "announcement_url": "U", "subject": "S", "frappe.utils.get_url()": "H"}
		text = "{{ frappe.db.sql('select 1') }} {{message}} {{ announcement_url }} {{ frappe.utils.get_url() }} {% if 1 %}"
		self.assertEqual(
			fill_announcement_placeholders(text, values),
			"{{ frappe.db.sql('select 1') }} Ciao {{ message }} U H {% if 1 %}",
		)

	def _send(self, recipients, content):
		from os_lms.os_lms import api

		with (
			_session("owasp-docente@example.com"),
			_roles("Docente"),
			patch("lms.lms.permissions.can_author_batch", return_value=True),
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe, "get_all", return_value=[STUDENT]),
			patch.object(frappe.db, "get_value", return_value="owasp-docente@example.com"),
			patch.object(frappe.utils, "get_fullname", return_value="Docente"),
			patch("frappe.core.doctype.communication.email.make") as make,
			patch.object(frappe, "sendmail") as sendmail,
			patch("frappe.desk.doctype.notification_log.notification_log.make_notification_logs"),
		):
			api.send_batch_announcement(
				batch="B", recipients=recipients, subject="{{ subject }}", content=content, message="M", send_email=1
			)
		return make, sendmail

	def test_the_content_is_never_evaluated(self):
		with patch("frappe.render_template") as render:
			make, sendmail = self._send([STUDENT], "{{ frappe.get_all('User') }} {{ message }}")
		render.assert_not_called()
		self.assertEqual(make.call_args.kwargs["content"], "{{ frappe.get_all('User') }} M")
		self.assertEqual(sendmail.call_args.kwargs["message"], "{{ frappe.get_all('User') }} M")

	def test_recipients_outside_the_batch_are_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self._send([STUDENT, "attacker@external.example"], "x")


class TestH1QueryLogPermissions(UnitTestCase):
	def test_students_hold_no_permission_on_the_tutor_log(self):
		roles = {perm.role for perm in frappe.get_meta("LMSA Query Log").permissions}
		self.assertNotIn("LMS Student", roles)


class TestH2CustomRoleAssignment(UnitTestCase):
	def _can(self, user, roles, role):
		from os_lms.os_lms.override_api import assert_can_assign_role

		with _session(user), _roles(*roles):
			try:
				assert_can_assign_role(role)
				return True
			except frappe.PermissionError:
				return False

	def test_only_the_administrator_assigns_gestore(self):
		self.assertTrue(self._can("Administrator", ["System Manager"], "Gestore"))
		self.assertFalse(self._can("g@example.com", ["Gestore", "Moderator"], "Gestore"))
		self.assertFalse(self._can("sm@example.com", ["System Manager"], "Gestore"))
		self.assertFalse(self._can("m@example.com", ["Moderator"], "Gestore"))

	def test_a_gestore_assigns_docente_and_valutatore_a_moderator_does_not(self):
		for role in ("Docente", "Valutatore"):
			self.assertTrue(self._can("g@example.com", ["Gestore", "Moderator"], role))
			self.assertFalse(self._can("m@example.com", ["Moderator"], role))

	def test_a_moderator_cannot_make_himself_gestore(self):
		from os_lms.os_lms import override_api

		with _session("m@example.com"), _roles("Moderator"), patch.object(frappe, "new_doc") as new_doc:
			with self.assertRaises(frappe.PermissionError):
				override_api.save_role("m@example.com", "Gestore", 1)
		new_doc.assert_not_called()

	def test_a_moderator_can_still_add_a_plain_member(self):
		from os_lms.os_lms import override_api

		user = SimpleNamespace(name="new@example.com", full_name="N", user_image=None)
		with (
			_session("m@example.com"),
			_roles("Moderator"),
			patch.object(frappe, "only_for"),
			patch.object(frappe, "get_doc", return_value=MagicMock(insert=MagicMock(return_value=user))),
			patch.object(override_api, "save_role") as save_role,
		):
			override_api.create_member("new@example.com", ["LMS Student"])
		granted = {call.args[1] for call in save_role.call_args_list}
		self.assertNotIn("Gestore", granted)
		self.assertIn("LMS Student", granted)


class TestH3TrueSkillsEndpoint(UnitTestCase):
	def _validate(self, url, addresses=("65.21.255.30",)):
		from os_lms.os_lms.trueskills import settings

		infos = [(None, None, None, None, (a, 443)) for a in addresses]
		with patch.dict(frappe.conf, {"developer_mode": 0}), patch("socket.getaddrinfo", return_value=infos):
			settings.validate_endpoint(url)

	def test_a_public_https_endpoint_is_accepted(self):
		self._validate("https://trueskills.example.com/api/v1/service/certificates")

	def test_ssrf_shapes_are_refused(self):
		for url, addresses in (
			("http://trueskills.example.com", ("65.21.255.30",)),
			("https://10.0.0.5:9200/_cat/indices#", ("10.0.0.5",)),
			("https://trueskills.example.com/x#", ("65.21.255.30",)),
			("https://trueskills.example.com/?a=1", ("65.21.255.30",)),
			("https://user:pw@trueskills.example.com", ("65.21.255.30",)),
			("https://internal.example.com", ("192.168.1.10",)),
			("https://metadata.example.com", ("169.254.169.254",)),
			("https://localhost", ("127.0.0.1",)),
		):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				self._validate(url, addresses)

	def _save(self, user, roles, old, new):
		from os_lms.os_lms.trueskills import settings

		before = frappe._dict(trueskills_api_endpoint=old)
		doc = frappe._dict(trueskills_api_endpoint=new, get_doc_before_save=lambda: before)
		with _session(user), _roles(*roles), patch.object(settings, "validate_endpoint") as validate:
			settings.validate_lms_settings(doc)
		return validate

	def test_a_moderator_cannot_repoint_the_connection(self):
		with self.assertRaises(frappe.PermissionError):
			self._save("m@example.com", ["Moderator"], "https://a.example.com", "https://b.example.com")

	def test_a_gestore_can_and_the_new_endpoint_is_validated(self):
		validate = self._save("g@example.com", ["Gestore"], "https://a.example.com", "https://b.example.com")
		validate.assert_called_once_with("https://b.example.com")

	def test_other_settings_saves_are_untouched(self):
		validate = self._save("m@example.com", ["Moderator"], "https://a.example.com", "https://a.example.com")
		validate.assert_not_called()

	def test_a_non_json_body_is_never_returned(self):
		from os_lms.os_lms.trueskills.client import TrueSkillsClient, TrueSkillsError

		response = MagicMock(content=b"<html>internal</html>", status_code=200)
		response.json.side_effect = ValueError
		with self.assertRaises(TrueSkillsError) as raised:
			TrueSkillsClient._json_or_empty(response)
		self.assertNotIn("internal", str(raised.exception))

	def test_health_returns_only_its_documented_fields(self):
		from os_lms.os_lms.trueskills.api import _health_fields

		self.assertEqual(
			_health_fields({"status": "ok", "organizationId": 7, "_cat": "indices"}),
			{"status": "ok", "organizationId": 7},
		)


class TestM1TrueSkillsAdminGate(UnitTestCase):
	def test_moderator_and_course_creator_are_not_integration_admins(self):
		from os_lms.os_lms.trueskills import api

		for roles in (["Moderator"], ["Course Creator"], ["Docente", "Course Creator"]):
			with self.subTest(roles=roles), _session("x@example.com"), _roles(*roles):
				self.assertFalse(api._is_admin())
				with self.assertRaises(frappe.PermissionError):
					api.get_issued(1)
		with _session("g@example.com"), _roles("Gestore"):
			self.assertTrue(api._is_admin())

	def test_course_authors_keep_the_template_picker(self):
		from os_lms.os_lms.trueskills import api

		with _session("cc@example.com"), _roles("Course Creator"):
			api._require_template_author()
		with _session("s@example.com"), _roles("LMS Student"):
			with self.assertRaises(frappe.PermissionError):
				api._require_template_author()

	def test_the_certificate_image_needs_the_course(self):
		from os_lms.os_lms.trueskills import api

		with _session("cc@example.com"), _roles("Course Creator"):
			with patch("lms.lms.utils.can_modify_course", return_value=False):
				with self.assertRaises(frappe.PermissionError):
					api.render_certificate_image("someone-elses-course")


class TestLessonAccessGuards(UnitTestCase):
	"""M-2 / M-3: the shared lesson and course checks."""

	def _assert(self, lesson_course="C", can_access=True, locked=(), course=None):
		from os_lms.os_lms.access_guards import assert_lesson_readable

		with (
			patch.object(frappe.db, "get_value", return_value=lesson_course),
			patch("lms.lms.permissions.can_access_lesson", return_value=can_access),
			patch("lms.lms.permissions.get_lesson_gate", return_value=(set(locked), None)),
		):
			return assert_lesson_readable("L", course)

	def test_a_readable_unlocked_lesson_passes(self):
		self.assertEqual(self._assert(), "C")

	def test_refusals(self):
		with self.assertRaises(frappe.PermissionError):
			self._assert(can_access=False)
		with self.assertRaises(frappe.PermissionError):
			self._assert(locked=["L"])
		with self.assertRaises(frappe.DoesNotExistError):
			self._assert(course="another-course")

	def test_a_course_needs_more_than_being_published(self):
		from os_lms.os_lms.access_guards import assert_course_readable

		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch("lms.lms.utils.can_modify_course", return_value=False),
			patch("lms.lms.utils.is_course_valutatore", return_value=False),
			patch("lms.lms.utils.get_membership", return_value=None),
		):
			with self.assertRaises(frappe.PermissionError):
				assert_course_readable("C")

	def test_per_user_rate_limit(self):
		from os_lms.os_lms.access_guards import check_user_rate_limit

		action = f"owasp-test-{frappe.generate_hash(length=8)}"
		try:
			with with_request(), _session(STUDENT):
				check_user_rate_limit(action, limit=2, seconds=60)
				check_user_rate_limit(action, limit=2, seconds=60)
				with self.assertRaises(frappe.RateLimitExceededError):
					check_user_rate_limit(action, limit=2, seconds=60)
		finally:
			frappe.cache.delete(frappe.cache.make_key(f"os_lms:rl:{action}:{STUDENT}"))


class TestM2LessonAudioStream(UnitTestCase):
	def test_the_stream_is_gated_on_the_lesson(self):
		from os_lms.os_lms import api

		with (
			patch(
				"os_lms.os_lms.access_guards.assert_lesson_readable", side_effect=frappe.PermissionError
			),
			patch.object(frappe, "get_single") as get_single,
		):
			with self.assertRaises(frappe.PermissionError):
				api.get_lesson_audio_stream("L")
		get_single.assert_not_called()


class TestM3Tutor(UnitTestCase):
	def test_no_llm_call_without_access(self):
		from os_lms.os_lms.ai.tutor import api

		with (
			patch.object(api, "assert_course_readable", side_effect=frappe.PermissionError),
			patch.object(api, "TutorAi") as tutor,
		):
			with self.assertRaises(frappe.PermissionError):
				api.ask("C", "", "domanda")
		tutor.assert_not_called()

	def test_a_lesson_is_checked_against_its_course(self):
		from os_lms.os_lms.ai.tutor import api

		with (
			patch.object(api, "assert_lesson_readable") as lesson_check,
			patch.object(api, "TutorAi") as tutor,
		):
			tutor.return_value.ask.return_value = "ok"
			api.ask("C", "L", "domanda")
		lesson_check.assert_called_once_with("L", "C")

	def test_the_client_history_is_bounded(self):
		from os_lms.os_lms.ai.tutor import api

		history = [{"from": "user", "message": "x" * 10_000}] * 50 + ["junk"]
		cleaned = api._clean_history(history)
		self.assertEqual(len(cleaned), api.MAX_HISTORY_TURNS)
		self.assertTrue(all(len(turn["message"]) == api.MAX_HISTORY_TURN_CHARS for turn in cleaned))


class TestM4SimulationSessionPermissions(UnitTestCase):
	def test_students_cannot_write_sessions_through_rest(self):
		perms = [p for p in frappe.get_meta("LMSA Simulation Session").permissions if p.role == "LMS Student"]
		self.assertTrue(perms and perms[0].read)
		self.assertFalse(any(p.write or p.create or p.submit for p in perms))


class TestM5VoiceTurnsAndDebrief(UnitTestCase):
	def test_turns_only_for_an_active_voice_session(self):
		from os_lms.os_lms.ai.simulations.orchestrator import SessionOrchestrator

		orchestrator = SessionOrchestrator()
		for modality, status in (("chat", "In Progress"), ("voice", "Ready")):
			session = frappe._dict(modality=modality, status=status)
			with (
				self.subTest(modality=modality, status=status),
				patch.object(frappe, "get_doc", return_value=session),
				patch.object(orchestrator, "_enforce_max_duration"),
				patch.object(orchestrator, "_persist_turn") as persist,
			):
				with self.assertRaises(frappe.ValidationError):
					orchestrator.persist_voice_turn(session_id="S", role="assistant", text="ottimo lavoro")
				persist.assert_not_called()

	def _generate(self, status="Completed", existing=None, staff=False):
		from os_lms.os_lms.ai.simulations import api

		session = frappe._dict(name="S", student=STUDENT, status=status, course="C")
		with (
			_session(STUDENT),
			patch.object(api, "load_session", return_value=session),
			patch.object(api, "has_moderator_role", return_value=False),
			patch.object(api, "_is_course_instructor", return_value=staff),
			patch.object(frappe.db, "get_value", return_value=existing),
			patch.object(api, "_run_generate_debrief", return_value="D") as run,
			patch.object(frappe, "get_doc"),
			patch.object(api, "_serialize_debrief", return_value={}),
		):
			api.generate_debrief("S")
		return run

	def test_a_student_cannot_redraw_the_grade(self):
		with self.assertRaises(frappe.ValidationError):
			self._generate(existing="Ready")
		with self.assertRaises(frappe.ValidationError):
			self._generate(status="In Progress")

	def test_first_or_failed_debrief_and_instructor_regeneration(self):
		self._generate(existing=None).assert_called_once()
		self._generate(existing="Failed").assert_called_once()
		self._generate(existing="Ready", staff=True).assert_called_once()


	def test_asking_whether_a_student_is_an_instructor_leaves_no_message(self):
		# frappe.throw queues its message even when the caller catches it: the
		# student saw "You are not an instructor of this course" on their debrief.
		from os_lms.os_lms.ai.simulations import api

		before = list(frappe.local.message_log)
		with (
			patch.object(api, "has_moderator_role", return_value=False),
			patch.object(api, "has_course_instructor_role", return_value=False),
		):
			self.assertFalse(api._is_course_instructor("C"))
		self.assertEqual(frappe.local.message_log, before)


class TestM7SpeechLimits(UnitTestCase):
	def test_text_to_speech_is_bounded(self):
		from os_lms.os_lms.ai.audio import api

		with (
			patch.object(api, "load_settings", return_value=SimpleNamespace(tts_enabled=True, tts_voice="")),
			patch.object(api, "resolve_audio_provider") as provider,
		):
			with self.assertRaises(frappe.ValidationError):
				api.synthesize("x" * (api.MAX_SYNTHESIZE_CHARS + 1))
		provider.assert_not_called()


class TestM8PostOnly(UnitTestCase):
	ENDPOINTS = (
		"os_lms.os_lms.api.send_batch_announcement",
		"os_lms.os_lms.api.reset_course_progress",
		"os_lms.os_lms.api.delete_live_class",
		"os_lms.os_lms.api.update_live_class",
		"os_lms.os_lms.api.start_live_class",
		"os_lms.os_lms.api.set_lesson_as_current",
		"os_lms.os_lms.api.register_push_token",
		"os_lms.os_lms.override_api.save_role",
		"os_lms.os_lms.override_api.create_member",
		"os_lms.os_lms.ai.tutor.api.ask",
		"os_lms.os_lms.ai.audio.api.synthesize",
		"os_lms.os_lms.ai.simulations.api.send_message",
		"os_lms.os_lms.ai.simulations.api.generate_debrief",
		"os_lms.os_lms.ai.realtime.api.persist_transcript_turn",
		"os_lms.os_lms.trueskills.api.retry_emission",
	)

	def test_data_changing_endpoints_refuse_get(self):
		for path in self.ENDPOINTS:
			with self.subTest(endpoint=path):
				fn = frappe.get_attr(path)
				self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[fn], ["POST"])


class TestM9ApiKeysEncrypted(UnitTestCase):
	def test_the_keys_are_password_fields(self):
		meta = frappe.get_meta("LMSA Settings")
		for fieldname in ("openai_key", "vimeo_api_key"):
			self.assertEqual(meta.get_field(fieldname).fieldtype, "Password")

	def test_a_key_not_yet_migrated_still_works(self):
		from os_lms.os_lms.ai.utils import api_keys

		with (
			patch.object(frappe.db, "get_single_value", return_value="sk-legacy"),
			patch.object(api_keys, "get_decrypted_password", return_value=None),
		):
			self.assertEqual(api_keys.get_api_key("openai_key"), "sk-legacy")
		with (
			patch.object(frappe.db, "get_single_value", return_value="*****"),
			patch.object(api_keys, "get_decrypted_password", return_value=None),
		):
			self.assertEqual(api_keys.get_api_key("openai_key"), "")

	def test_the_history_is_scrubbed(self):
		from os_lms.os_lms.ai.utils import api_keys

		row = frappe._dict(
			name="V",
			data=frappe.as_json({"changed": [["openai_key", "sk-old", "sk-new"], ["top_k", 4, 6]]}),
		)
		with (
			patch.object(frappe, "get_all", return_value=[row]),
			patch.object(frappe.db, "set_value") as set_value,
		):
			self.assertEqual(api_keys._scrub_version_history(), 1)
		data = frappe.parse_json(set_value.call_args.args[3])
		self.assertEqual(data["changed"], [["openai_key", "*****", "*****"], ["top_k", 4, 6]])


class TestM10SignedLiveClassLinks(UnitTestCase):
	DOC = frappe._dict(name="LC1", date="2026-10-20", time="10:00:00", duration=60, batch_name="B", host=None)

	def _holder(self, query, now="2026-10-20 12:00:00", **request):
		from os_lms.os_lms import live_class_join

		with with_request(FakeRequest(query, **request)), patch.object(
			live_class_join, "now_datetime", return_value=frappe.utils.get_datetime(now)
		):
			return live_class_join._signed_link_holder(self.DOC)

	def test_a_link_names_its_recipient_and_expires(self):
		from os_lms.os_lms.live_class_join import signed_live_class_params

		query = signed_live_class_params(self.DOC, STUDENT)
		self.assertEqual(self._holder(query), STUDENT)
		self.assertIsNone(self._holder(query, now="2026-10-21 11:01:00"))

	def test_tampered_legacy_and_foreign_links_are_rejected(self):
		from frappe.utils.verified_command import get_signed_params

		from os_lms.os_lms.live_class_join import signed_live_class_params

		query = signed_live_class_params(self.DOC, STUDENT)
		self.assertIsNone(self._holder(query.replace("owasp-test-student", "attacker")))
		self.assertIsNone(self._holder(get_signed_params({"name": "LC1"})))
		other = frappe._dict(self.DOC, name="LC2")
		self.assertIsNone(self._holder(signed_live_class_params(other, STUDENT)))
		self.assertIsNone(self._holder(query, method="POST"))

	def test_a_guest_without_a_link_is_sent_to_log_in(self):
		from os_lms.os_lms import live_class_join

		with _session("Guest"), with_request(FakeRequest("name=LC1")):
			self.assertIsNone(live_class_join.authorize_live_class_request(self.DOC))
			self.assertEqual(frappe.local.response.get("type"), "redirect")
			self.assertTrue(frappe.local.response.get("location").startswith("/login?redirect-to="))
		frappe.local.response.pop("type", None)
		frappe.local.response.pop("location", None)

	def test_a_removed_student_loses_the_link(self):
		from os_lms.os_lms import live_class_join

		query = live_class_join.signed_live_class_params(self.DOC, STUDENT)
		with (
			_session("Guest"),
			with_request(FakeRequest(query)),
			patch.object(live_class_join, "now_datetime", return_value=frappe.utils.get_datetime("2026-10-20 10:30:00")),
			patch.object(live_class_join, "user_can_access", return_value=False),
		):
			self.assertIsNone(live_class_join.authorize_live_class_request(self.DOC))
		frappe.local.response.pop("type", None)
		frappe.local.response.pop("location", None)


class TestM11Debugpy(UnitTestCase):
	def test_no_remote_debugger_outside_developer_mode(self):
		from os_lms import debug

		fake_debugpy = MagicMock()
		with (
			patch.dict(sys.modules, {"debugpy": fake_debugpy}),
			patch.dict("os.environ", {"DEBUG_MODE": "1"}),
			patch.dict(frappe.conf, {"developer_mode": 0}),
			patch.object(debug, "_debug_initialized", False),
		):
			debug.active_debug()
		fake_debugpy.listen.assert_not_called()


# Low findings (pacchetto A, docs/security/owasp-piano-residuo-2026-10-26.md).
# L-6 (assignment submissions of a Valutatore) needs real rows and lives in
# test_valutatore_assignment_submission_scope.py.


class TestL1BatchDashboardScope(UnitTestCase):
	BATCH = "owasp-batch"

	def _gate_open(self, batch_course=True, enrolled=True):
		def exists(doctype, filters=None, *args, **kwargs):
			if doctype == "Batch Course":
				return batch_course
			if doctype == "LMS Batch Enrollment":
				return enrolled
			return None

		return (
			patch("lms.lms.permissions.can_author_batch", return_value=True),
			patch("lms.lms.utils.is_batch_valutatore", return_value=False),
			patch.object(frappe.db, "exists", side_effect=exists),
		)

	def test_stats_refuse_a_course_outside_the_batch(self):
		from os_lms.os_lms.api import get_batch_progress_stats

		author, valutatore, exists = self._gate_open(batch_course=False)
		with author, valutatore, exists, self.assertRaises(frappe.PermissionError):
			get_batch_progress_stats(self.BATCH, course="unpublished-course")

	def test_drill_down_refuses_a_course_outside_the_batch(self):
		from os_lms.os_lms.api import get_batch_student_course_progress

		author, valutatore, exists = self._gate_open(batch_course=False)
		with author, valutatore, exists, self.assertRaises(frappe.PermissionError):
			get_batch_student_course_progress(self.BATCH, "unpublished-course", STUDENT)

	def test_drill_down_refuses_a_member_outside_the_batch(self):
		from os_lms.os_lms.api import get_batch_student_course_progress

		author, valutatore, exists = self._gate_open(enrolled=False)
		with author, valutatore, exists, self.assertRaises(frappe.PermissionError):
			get_batch_student_course_progress(self.BATCH, "batch-course", "someone-else@example.com")


class TestL2AnnouncementRecipients(UnitTestCase):
	BATCH = "owasp-batch"

	def _communications(self):
		return [
			frappe._dict(subject="to a", recipients="a@x.it, c@x.it", cc=None, bcc=None, sender="s@x.it"),
			frappe._dict(subject="to ba", recipients="ba@x.it", cc=None, bcc=None, sender="s@x.it"),
			frappe._dict(subject="cc a", recipients="c@x.it", cc="A@X.it", bcc=None, sender="s@x.it"),
		]

	def _announcements(self, user, roles=(), student=True):
		from os_lms.os_lms.override_api import get_announcements

		with (
			_session(user),
			_roles(*roles),
			patch.object(frappe.db, "exists", return_value=student),
			patch.object(frappe.db, "get_value", return_value=user),
			patch.object(frappe, "get_cached_value", return_value=None),
			patch.object(frappe, "get_all", return_value=self._communications()),
			patch("lms.lms.permissions.can_author_batch", return_value=False),
			patch("lms.lms.utils.is_batch_valutatore", return_value=False),
		):
			return get_announcements(self.BATCH)["data"]

	def test_student_matches_their_own_address_exactly(self):
		subjects = [comm.subject for comm in self._announcements("a@x.it")]
		self.assertEqual(subjects, ["to a", "cc a"])

	def test_student_does_not_receive_the_classmates_addresses(self):
		for comm in self._announcements("a@x.it"):
			self.assertFalse({"recipients", "cc", "bcc"} & set(comm))

	def test_staff_keeps_the_recipients(self):
		data = self._announcements("mod@x.it", roles=("Moderator",), student=False)
		self.assertEqual(len(data), 3)
		self.assertEqual(data[0].recipients, "a@x.it, c@x.it")


class TestL3UserListForValutatore(UnitTestCase):
	def _users(self, scoped, people=()):
		from os_lms.os_lms import valutatore
		from os_lms.os_lms.override_api import get_all_users

		get_all = MagicMock(return_value=[frappe._dict(name="p@x.it", full_name="P", user_image=None)])
		with (
			patch.object(frappe, "only_for"),
			patch.object(valutatore, "_only_scoped_valutatore", return_value=scoped),
			patch.object(valutatore, "get_valutatore_batch_people", return_value=set(people)),
			patch.object(frappe, "get_all", get_all),
		):
			return get_all_users(), get_all

	def test_scoped_valutatore_gets_only_the_people_of_their_batches(self):
		_users, get_all = self._users(scoped=True, people={"p@x.it"})
		filters = get_all.call_args.args[1]
		self.assertEqual(filters["name"], ["in", ["p@x.it"]])

	def test_scoped_valutatore_without_batches_gets_nobody(self):
		users, get_all = self._users(scoped=True)
		self.assertEqual(users, {})
		get_all.assert_not_called()

	def test_broader_roles_keep_the_full_list(self):
		_users, get_all = self._users(scoped=False)
		self.assertEqual(get_all.call_args.args[1], {"enabled": 1})

	def test_batch_people_are_students_instructors_and_valutatori(self):
		from os_lms.os_lms import valutatore

		def get_all(doctype, *args, **kwargs):
			return {"Course Instructor": ["teacher@x.it"], "LMS Batch Valutatore": ["val@x.it"]}[doctype]

		with (
			patch.object(valutatore, "get_valutatore_batches", return_value=["b"]),
			patch.object(valutatore, "get_valutatore_member_emails", return_value=["student@x.it"]),
			patch.object(frappe, "get_all", side_effect=get_all),
		):
			self.assertEqual(
				valutatore.get_valutatore_batch_people("val@x.it"),
				{"student@x.it", "teacher@x.it", "val@x.it"},
			)


class TestI1I3RemovedEndpoints(UnitTestCase):
	def test_debug_import_and_guest_course_duration_are_gone(self):
		from os_lms.os_lms import api

		self.assertFalse(hasattr(api, "try_import"))
		self.assertFalse(hasattr(api, "get_course_duration"))
