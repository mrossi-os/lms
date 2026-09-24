# Tutor AI Chat History ("progetto corso") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every tutor exchange as a named conversation scoped to a course, let the learner browse and resume their own conversations from a dedicated page, and let the `Gestore` role read (never edit) any learner's conversations for that course.

**Architecture:** Two new doctypes (`LMSA Tutor Conversation` + `LMSA Tutor Message`) modelled on the existing simulation session/turn pair, written by `TutorAi` in the same `finally` block that already writes the audit log. `LMSA Query Log` stays the audit trail and is untouched except for a permission fix. Reading goes through a small `history.py` endpoint module; the learner-facing UI is one route (`/courses/:courseName/tutor`) whose component gains a student picker when the viewer is a manager.

**Tech Stack:** Frappe (Python 3.10, `frappe.tests.UnitTestCase`), Vue 3 + Pinia + frappe-ui, Vite. Dev environment is Docker (`docker/docker-compose.yml`, project `dev-elite`).

**Spec:** `docs/superpowers/specs/2026-09-18-tutor-chat-history-design.md` — read it before starting; this plan implements it section by section.

> **Status (2026-09-18): approved, NOT started.** The client asked for the plan and the
> documentation only; implementation is deferred to a later, explicit go-ahead. Do not
> begin Task 1 without one.
>
> **Agreed execution mode: subagent-driven** (`superpowers:subagent-driven-development`) —
> a fresh subagent per task with a review between tasks, plus the two checkpoints marked
> below.

## Global Constraints

- **Permission rule (spec §6, decision D1):** only the owning learner and the roles in `{"System Manager", "Gestore"}` may read a conversation. **Never grant on `Moderator` or `Course Creator`** — a `Gestore` also holds `Moderator`, so a Moderator branch would open the archive to every moderator. Managers are **read-only**.
- A `has_permission` hook that returns `None` is treated as **DENY** by current Frappe. Every allow branch must `return True` explicitly.
- Whitelisted API methods stay thin (validate → gate → delegate → plain dict) and need type-annotated params **and** return type (`require_type_annotated_api_methods = True`).
- **Indentation per file — match the file you edit:** TABS in `ai/tutor/tutor_ai.py`, `ai/tutor/api.py`, `os_lms/api.py`, and all `doctype/*/*.py`. **4 SPACES** in `hooks.py`, `override_api.py`, `setup.py`, `ai/simulations/api.py` and every `tests/*.py`. New files: `ai/tutor/history.py` uses TABS (it sits next to `api.py`).
- Comments and identifiers in English. User-facing SPA strings in Italian, wrapped in `__()`.
- **Test cleanup must never use broad filters.** Delete only the records the test created, tracked by name. A broad delete on this project has already destroyed real data on the dev site. The `Created` tracker in `tests/_fixtures.py` (Task 1) is the only sanctioned cleanup path — do not copy `simulations/tests/_fixtures.py::cleanup_sessions_and_turns`, which deletes every row.
- **Backend tests run INSIDE Docker:** `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module <MODULE>'`. The container is already running.
- **A new or changed doctype JSON needs a migrate before its tests can pass:** `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost migrate'`. Doctype meta in a running container is stale until you do this.
- **Frontend has no JS unit runner** — verify with `cd frontend && yarn build` (must exit 0), plus the manual check named in the task.
- New Italian labels go in **both** `lms/translations/it.csv` and `lms/locale/it.po`: a non-empty msgstr in the PO overrides the CSV.
- `frappe.get_all` bypasses permissions by design. Every listing endpoint here gates explicitly (owner filter + `can_view_tutor_archive()`); the doctype hooks are the second line of defence for direct REST access.
- Do **not** change `LMSA Query Log`'s fields, its writer, or the RAG retrieval. The only change to it is removing a permission block (Task 4).

---

## File Structure

**Backend — create**
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/{__init__.py,lmsa_tutor_conversation.json,lmsa_tutor_conversation.py}` — the conversation entity, its `before_insert` defaults, its title helper and its two permission hooks.
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message/{__init__.py,lmsa_tutor_message.json,lmsa_tutor_message.py}` — one turn; permission hooks delegate to the parent conversation.
- `apps/os_lms/os_lms/os_lms/ai/tutor/history.py` — read/manage endpoints for the archive (kept apart from `api.py`, which stays the chat path).
- `apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py` — fixtures + the `Created` cleanup tracker.
- `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py` — doctype defaults, title helper.
- `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_persistence.py` — turns written by `TutorAi`, history window.
- `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py` — the D1 matrix.
- `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py` — endpoints.

**Backend — modify**
- `apps/os_lms/os_lms/hooks.py` — register the four permission hooks.
- `apps/os_lms/os_lms/setup.py` — grant the `Gestore` DocPerms on the two new doctypes (runs on `after_migrate`).
- `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py` — persist turns, server-side history window, feature gate.
- `apps/os_lms/os_lms/os_lms/ai/tutor/api.py` — `conversation` parameter + ownership validation.
- `apps/os_lms/os_lms/os_lms/api.py` — `can_view_tutor_archive()`.
- `apps/os_lms/os_lms/os_lms/override_api.py` — expose `can_view_tutor_archive` and `tutor_history_enabled` to the SPA.
- `apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py` + `ai/utils/llm/__init__.py` — the `tutor_history_enabled` setting.
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json` — the setting's field.
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_query_log/lmsa_query_log.json` — remove the `LMS Student` permission block.

**Frontend — create**
- `frontend/src/oslms/pages/Courses/CourseTutorArchive.vue` — the "progetto corso" page (list + transcript + resume; student picker for managers).
- `frontend/src/oslms/components/ai/ConversationPicker.vue` — the conversation dropdown reused by the floating panel.

**Frontend — modify**
- `frontend/src/stores/aiChat.js` — conversation-aware store.
- `frontend/src/oslms/components/ai/ChatBot.vue` — send/receive `conversation`.
- `frontend/src/oslms/components/ai/AiChatButton.vue` — picker, "new", "archive", link to the page.
- `frontend/src/overrides/pages/Courses/CourseOverview.vue` — the single entry button.
- `frontend/src/router.js` — the route.
- `frontend/src/oslms/utils/settings.js` — the settings toggle.
- `lms/translations/it.csv`, `lms/locale/it.po` — labels.
- `docs/ai/TUTOR.md` — documentation.

---

# FASE 1 — Persistenza e permessi (backend)

At the end of Fase 1 nothing is visible in the SPA, but conversations are stored, the permission matrix holds, and the pre-existing `LMSA Query Log` leak is closed.

---

### Task 1: Doctype `LMSA Tutor Conversation` + test fixtures

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/__init__.py` (empty)
- Create: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/lmsa_tutor_conversation.json`
- Create: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/lmsa_tutor_conversation.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py`

**Interfaces:**
- Consumes: nothing.
- Produces: doctype `LMSA Tutor Conversation` with fields `course, member, title, started_at, last_message_at, message_count, archived, last_lesson`; `build_conversation_title(question: str) -> str`; constant `TITLE_MAX_LENGTH = 140`; fixtures `Created`, `make_user(prefix, roles=None)`, `make_course(title_prefix="Tutor Test Course")`, `make_conversation(created, course, member, title=..., archived=0)`, `add_message(created, conversation, turn_index, role, content, status="Answered")`.

- [ ] **Step 1: Write the failing test**

Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py` (4 SPACES):

```python
"""Shared fixtures for the tutor archive test suite.

Every helper records what it creates in a `Created` tracker. Cleanup deletes
only those names: a broad delete (every row of a doctype) has already wiped
real data on the dev site, so it is banned here.
"""
from __future__ import annotations

import frappe


class Created:
    """Records created by a test, deleted in reverse order on cleanup."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []

    def add(self, doctype: str, name: str) -> str:
        self.rows.append((doctype, name))
        return name

    def cleanup(self) -> None:
        for doctype, name in reversed(self.rows):
            if frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        self.rows.clear()
        frappe.db.commit()


def make_user(created: Created, prefix: str, roles: list[str] | None = None):
    """Create a test User, bypassing Frappe's per-minute creation throttle."""
    prev = frappe.flags.get("in_import")
    frappe.flags.in_import = True
    try:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": f"{prefix}-{frappe.generate_hash(length=6)}@example.com",
                "first_name": prefix.title(),
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = prev
    created.add("User", user.name)
    for role in roles or []:
        if frappe.db.exists("Role", role):
            user.add_roles(role)
    return user


def make_course(created: Created, title_prefix: str = "Tutor Test Course"):
    course = frappe.get_doc(
        {
            "doctype": "LMS Course",
            "title": f"{title_prefix} {frappe.generate_hash(length=4)}",
            "short_introduction": "Tutor archive test fixture.",
            "description": "Tutor archive test fixture course.",
        }
    ).insert(ignore_permissions=True)
    created.add("LMS Course", course.name)
    return course


def make_conversation(
    created: Created,
    course: str,
    member: str,
    title: str = "Domanda di prova",
    archived: int = 0,
):
    doc = frappe.get_doc(
        {
            "doctype": "LMSA Tutor Conversation",
            "course": course,
            "member": member,
            "title": title,
            "archived": archived,
        }
    ).insert(ignore_permissions=True)
    created.add("LMSA Tutor Conversation", doc.name)
    return doc


def add_message(
    created: Created,
    conversation: str,
    turn_index: int,
    role: str,
    content: str,
    status: str = "Answered",
):
    doc = frappe.get_doc(
        {
            "doctype": "LMSA Tutor Message",
            "conversation": conversation,
            "turn_index": turn_index,
            "role": role,
            "content": content,
            "status": status,
        }
    ).insert(ignore_permissions=True)
    created.add("LMSA Tutor Message", doc.name)
    return doc
```

Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py` (4 SPACES):

```python
"""Defaults and title generation for LMSA Tutor Conversation."""
from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.tutor.tests._fixtures import Created, make_course, make_user
from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
    TITLE_MAX_LENGTH,
    build_conversation_title,
)


class TestTutorConversation(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.student = make_user(self.created, "student")

    def tearDown(self):
        self.created.cleanup()

    def test_before_insert_fills_member_and_timestamps(self):
        doc = frappe.get_doc(
            {"doctype": "LMSA Tutor Conversation", "course": self.course.name, "title": "X"}
        ).insert(ignore_permissions=True)
        self.created.add("LMSA Tutor Conversation", doc.name)
        self.assertEqual(doc.member, frappe.session.user)
        self.assertIsNotNone(doc.started_at)
        self.assertEqual(doc.last_message_at, doc.started_at)

    def test_explicit_member_is_kept(self):
        doc = frappe.get_doc(
            {
                "doctype": "LMSA Tutor Conversation",
                "course": self.course.name,
                "member": self.student.name,
                "title": "X",
            }
        ).insert(ignore_permissions=True)
        self.created.add("LMSA Tutor Conversation", doc.name)
        self.assertEqual(doc.member, self.student.name)

    def test_title_collapses_whitespace(self):
        self.assertEqual(build_conversation_title("  come   si   fa? "), "come si fa?")

    def test_title_is_clipped_with_ellipsis(self):
        title = build_conversation_title("a" * 400)
        self.assertEqual(len(title), TITLE_MAX_LENGTH)
        self.assertTrue(title.endswith("…"))

    def test_empty_question_gets_a_fallback_title(self):
        self.assertTrue(build_conversation_title("   "))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_conversation'`
Expected: FAIL — `ModuleNotFoundError: os_lms.os_lms.doctype.lmsa_tutor_conversation`.

- [ ] **Step 3: Create the doctype JSON**

Create `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/__init__.py` (empty file) and `lmsa_tutor_conversation.json`:

```json
{
 "actions": [],
 "autoname": "format:TCV-{#####}",
 "creation": "2026-09-18 10:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "course",
  "member",
  "title",
  "column_break_1",
  "started_at",
  "last_message_at",
  "message_count",
  "archived",
  "last_lesson"
 ],
 "fields": [
  {
   "fieldname": "course",
   "fieldtype": "Link",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Course",
   "options": "LMS Course",
   "read_only": 1,
   "reqd": 1,
   "search_index": 1
  },
  {
   "fieldname": "member",
   "fieldtype": "Link",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Member",
   "options": "User",
   "read_only": 1,
   "reqd": 1,
   "search_index": 1
  },
  {
   "description": "First question of the conversation, clipped to 140 characters. Renamable by the learner.",
   "fieldname": "title",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Title",
   "length": 140
  },
  {
   "fieldname": "column_break_1",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "started_at",
   "fieldtype": "Datetime",
   "label": "Started At",
   "read_only": 1
  },
  {
   "description": "Sort key of the archive list.",
   "fieldname": "last_message_at",
   "fieldtype": "Datetime",
   "in_list_view": 1,
   "label": "Last Message At",
   "read_only": 1
  },
  {
   "description": "Denormalised counter: avoids a COUNT per row in the archive list.",
   "fieldname": "message_count",
   "fieldtype": "Int",
   "label": "Messages",
   "read_only": 1
  },
  {
   "default": "0",
   "description": "The learner cannot delete a conversation, only archive it.",
   "fieldname": "archived",
   "fieldtype": "Check",
   "in_standard_filter": 1,
   "label": "Archived"
  },
  {
   "description": "Lesson the last question was asked from, when any.",
   "fieldname": "last_lesson",
   "fieldtype": "Link",
   "label": "Last Lesson",
   "options": "Course Lesson",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-18 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "OS LMS",
 "name": "LMSA Tutor Conversation",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "print": 1,
   "read": 1,
   "role": "LMS Student"
  }
 ],
 "row_format": "Dynamic",
 "sort_field": "last_message_at",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

The learner gets **read only**. Renaming and archiving go through endpoints that check ownership and then write with `ignore_permissions=True`, so no write DocPerm is needed and direct REST writes stay impossible. The `Gestore` DocPerm is added in Task 3 through `setup.py`, because the role may not exist on a fresh site.

- [ ] **Step 4: Create the controller**

Create `lmsa_tutor_conversation.py` (TABS):

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Roles that may read every learner's tutor conversations (spec §6, decision D1).
# Deliberately NOT Moderator / Course Creator: a "Gestore" also holds Moderator,
# so granting on Moderator would open the archive to every moderator.
ROLES_WITH_FULL_ACCESS = {"System Manager", "Gestore"}

# Managers read the archive; they never edit a learner's conversation.
READ_PTYPES = {"read", "report", "print", "export", "email", "share"}

TITLE_MAX_LENGTH = 140


def build_conversation_title(question: str) -> str:
	"""The first question, whitespace-collapsed and clipped, is the title."""
	text = " ".join((question or "").split())
	if not text:
		return _("New conversation")
	if len(text) <= TITLE_MAX_LENGTH:
		return text
	return text[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


class LMSATutorConversation(Document):
	def before_insert(self):
		if not self.member:
			self.member = frappe.session.user
		if not self.started_at:
			self.started_at = frappe.utils.now_datetime()
		if not self.last_message_at:
			self.last_message_at = self.started_at
```

The permission hooks are added in Task 3 — this task only has to make the doctype exist.

- [ ] **Step 5: Migrate, then run the tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost migrate'`
Then: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_conversation'`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py
git commit -m "feat(tutor): add the LMSA Tutor Conversation doctype"
```

---

### Task 2: Doctype `LMSA Tutor Message`

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message/{__init__.py,lmsa_tutor_message.json,lmsa_tutor_message.py}`
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py` (extend)

**Interfaces:**
- Consumes: `LMSA Tutor Conversation` (Task 1), fixtures `Created`/`make_course`/`make_user`/`make_conversation`.
- Produces: doctype `LMSA Tutor Message` with fields `conversation, turn_index, role, content, lesson, status, model_used, provider_used, query_log`; ordered by `turn_index ASC`.

- [ ] **Step 1: Write the failing test**

Append to `test_conversation.py`, inside a new class:

```python
class TestTutorMessage(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.conversation = make_conversation(
            self.created, self.course.name, frappe.session.user
        )

    def tearDown(self):
        self.created.cleanup()

    def test_messages_come_back_in_turn_order(self):
        add_message(self.created, self.conversation.name, 1, "assistant", "seconda")
        add_message(self.created, self.conversation.name, 0, "user", "prima")
        rows = frappe.get_all(
            "LMSA Tutor Message",
            filters={"conversation": self.conversation.name},
            fields=["turn_index", "role", "content"],
            order_by="turn_index asc",
        )
        self.assertEqual([r["turn_index"] for r in rows], [0, 1])
        self.assertEqual(rows[0]["content"], "prima")

    def test_failed_message_may_have_empty_content(self):
        msg = add_message(
            self.created, self.conversation.name, 0, "assistant", "", status="Failed"
        )
        self.assertEqual(msg.status, "Failed")
        self.assertFalse(msg.content)
```

Add `make_conversation` and `add_message` to the imports at the top of the file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_conversation'`
Expected: FAIL — `DoesNotExistError: DocType LMSA Tutor Message not found`.

- [ ] **Step 3: Create the doctype**

`__init__.py` (empty) and `lmsa_tutor_message.json`:

```json
{
 "actions": [],
 "autoname": "format:TMS-{######}",
 "creation": "2026-09-18 10:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "conversation",
  "turn_index",
  "role",
  "column_break_1",
  "status",
  "lesson",
  "section_content",
  "content",
  "section_audit",
  "model_used",
  "provider_used",
  "query_log"
 ],
 "fields": [
  {
   "fieldname": "conversation",
   "fieldtype": "Link",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Conversation",
   "options": "LMSA Tutor Conversation",
   "read_only": 1,
   "reqd": 1,
   "search_index": 1
  },
  {
   "fieldname": "turn_index",
   "fieldtype": "Int",
   "in_list_view": 1,
   "label": "Turn Index",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "role",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Role",
   "options": "user\nassistant",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "column_break_1",
   "fieldtype": "Column Break"
  },
  {
   "default": "Answered",
   "description": "A failed turn is stored with empty content and rendered as a notice, never as an empty bubble.",
   "fieldname": "status",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Status",
   "options": "Answered\nFailed",
   "read_only": 1
  },
  {
   "fieldname": "lesson",
   "fieldtype": "Link",
   "label": "Lesson",
   "options": "Course Lesson",
   "read_only": 1
  },
  {
   "fieldname": "section_content",
   "fieldtype": "Section Break",
   "label": "Content"
  },
  {
   "fieldname": "content",
   "fieldtype": "Long Text",
   "label": "Content",
   "read_only": 1
  },
  {
   "collapsible": 1,
   "fieldname": "section_audit",
   "fieldtype": "Section Break",
   "label": "Audit"
  },
  {
   "fieldname": "model_used",
   "fieldtype": "Data",
   "label": "Model",
   "read_only": 1
  },
  {
   "fieldname": "provider_used",
   "fieldtype": "Data",
   "label": "Provider",
   "read_only": 1
  },
  {
   "description": "Bridge to the full audit record (prompt and retrieved context).",
   "fieldname": "query_log",
   "fieldtype": "Link",
   "label": "Query Log",
   "options": "LMSA Query Log",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-18 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "OS LMS",
 "name": "LMSA Tutor Message",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "print": 1,
   "read": 1,
   "role": "LMS Student"
  }
 ],
 "row_format": "Dynamic",
 "sort_field": "turn_index",
 "sort_order": "ASC",
 "states": [],
 "track_changes": 0
}
```

`lmsa_tutor_message.py` (TABS):

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSATutorMessage(Document):
	pass
```

- [ ] **Step 4: Migrate, then run the tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost migrate'`
Then the `test_conversation` module command from Task 1 Step 5.
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_conversation.py
git commit -m "feat(tutor): add the LMSA Tutor Message doctype"
```

---

### Task 3: Permission hooks and the Gestore DocPerms

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation/lmsa_tutor_conversation.py`
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message/lmsa_tutor_message.py`
- Modify: `apps/os_lms/os_lms/hooks.py:60-101`
- Modify: `apps/os_lms/os_lms/setup.py:143-146` (`GESTORE_DOCPERMS`)
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py`

**Interfaces:**
- Consumes: both doctypes, `ROLES_WITH_FULL_ACCESS`, `READ_PTYPES`.
- Produces: `get_permission_query_conditions(user=None) -> str` and `has_permission(doc, ptype="read", user=None) -> bool` on both doctype modules.

- [ ] **Step 1: Write the failing test**

Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py` (4 SPACES):

```python
"""The D1 permission matrix: only the owner and the Gestore bundle may read.

The interesting case is the Moderator: a Gestore also holds Moderator, so the
hooks must grant on Gestore WITHOUT granting on Moderator.
"""
from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.tutor.tests._fixtures import (
    Created,
    add_message,
    make_conversation,
    make_course,
    make_user,
)
from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
    get_permission_query_conditions,
    has_permission,
)
from os_lms.os_lms.doctype.lmsa_tutor_message import lmsa_tutor_message as msg_module


class TestTutorArchivePermissions(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.owner = make_user(self.created, "owner", ["LMS Student"])
        self.other = make_user(self.created, "other", ["LMS Student"])
        self.moderator = make_user(self.created, "mod", ["Moderator"])
        self.creator = make_user(self.created, "creator", ["Course Creator"])
        self.manager = make_user(self.created, "gestore", ["Moderator", "Gestore"])
        self.conversation = make_conversation(
            self.created, self.course.name, self.owner.name
        )
        self.message = add_message(
            self.created, self.conversation.name, 0, "user", "ciao"
        )

    def tearDown(self):
        self.created.cleanup()

    def _doc(self):
        return frappe.get_doc("LMSA Tutor Conversation", self.conversation.name)

    def test_owner_reads_own_conversation(self):
        self.assertTrue(has_permission(self._doc(), "read", self.owner.name))

    def test_other_student_is_denied(self):
        self.assertFalse(has_permission(self._doc(), "read", self.other.name))

    def test_plain_moderator_is_denied(self):
        self.assertFalse(has_permission(self._doc(), "read", self.moderator.name))

    def test_course_creator_is_denied(self):
        self.assertFalse(has_permission(self._doc(), "read", self.creator.name))

    def test_gestore_reads_but_cannot_write(self):
        self.assertTrue(has_permission(self._doc(), "read", self.manager.name))
        self.assertFalse(has_permission(self._doc(), "write", self.manager.name))
        self.assertFalse(has_permission(self._doc(), "delete", self.manager.name))

    def test_owner_query_condition_filters_by_member(self):
        cond = get_permission_query_conditions(self.owner.name)
        self.assertIn("member", cond)
        self.assertIn(self.owner.name, cond)

    def test_gestore_query_condition_is_unrestricted(self):
        self.assertEqual(get_permission_query_conditions(self.manager.name), "")

    def test_moderator_query_condition_is_restricted_to_self(self):
        cond = get_permission_query_conditions(self.moderator.name)
        self.assertIn(self.moderator.name, cond)

    def test_message_permission_follows_its_conversation(self):
        doc = frappe.get_doc("LMSA Tutor Message", self.message.name)
        self.assertTrue(msg_module.has_permission(doc, "read", self.owner.name))
        self.assertFalse(msg_module.has_permission(doc, "read", self.other.name))
        self.assertFalse(msg_module.has_permission(doc, "read", self.moderator.name))
        self.assertTrue(msg_module.has_permission(doc, "read", self.manager.name))

    def test_message_query_condition_is_a_subquery_on_the_parent(self):
        cond = msg_module.get_permission_query_conditions(self.owner.name)
        self.assertIn("tabLMSA Tutor Conversation", cond)
        self.assertIn(self.owner.name, cond)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_permissions'`
Expected: FAIL — `ImportError: cannot import name 'get_permission_query_conditions'`.

- [ ] **Step 3: Add the hooks to the conversation controller**

Append to `lmsa_tutor_conversation.py` (TABS):

```python
def get_permission_query_conditions(user: str | None = None) -> str:
	"""List filter: learners see only their own conversations; the manager
	bundle sees everything. No branch for Moderator or Course Creator — see
	ROLES_WITH_FULL_ACCESS."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	if set(frappe.get_roles(user)) & ROLES_WITH_FULL_ACCESS:
		return ""

	# frappe.db.escape() already wraps the value in quotes.
	return (
		f"`tabLMSA Tutor Conversation`.member = "
		f"{frappe.db.escape(user, percent=False)}"
	)


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Per-document gate. Always returns an explicit bool: a None return is
	treated as DENY by Frappe."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	if set(frappe.get_roles(user)) & ROLES_WITH_FULL_ACCESS:
		return ptype in READ_PTYPES

	return doc.member == user
```

- [ ] **Step 4: Add the delegating hooks to the message controller**

Replace the body of `lmsa_tutor_message.py` (TABS):

```python
# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSATutorMessage(Document):
	pass


def get_permission_query_conditions(user: str | None = None) -> str:
	"""A message is visible iff its conversation is visible to the user."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
		get_permission_query_conditions as conversation_filter,
	)

	parent_cond = conversation_filter(user)
	if parent_cond == "":
		return ""
	# The parent condition references `tabLMSA Tutor Conversation`.<col> — those
	# references stay valid inside a subquery on the same table.
	return (
		f"`tabLMSA Tutor Message`.conversation IN ("
		f"SELECT name FROM `tabLMSA Tutor Conversation` "
		f"WHERE {parent_cond})"
	)


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Defer to the parent conversation."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not doc.conversation:
		return False

	from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
		has_permission as conversation_has_permission,
	)

	try:
		parent = frappe.get_doc("LMSA Tutor Conversation", doc.conversation)
	except frappe.DoesNotExistError:
		return False
	return conversation_has_permission(parent, ptype=ptype, user=user)
```

- [ ] **Step 5: Register the hooks**

In `apps/os_lms/os_lms/hooks.py` (4 SPACES), add to the `permission_query_conditions` dict, right after the `"LMSA Simulation Debrief"` entry:

```python
    "LMSA Tutor Conversation": (
        "os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation.get_permission_query_conditions"
    ),
    "LMSA Tutor Message": (
        "os_lms.os_lms.doctype.lmsa_tutor_message.lmsa_tutor_message.get_permission_query_conditions"
    ),
```

and to the `has_permission` dict, in the same position:

```python
    "LMSA Tutor Conversation": (
        "os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation.has_permission"
    ),
    "LMSA Tutor Message": (
        "os_lms.os_lms.doctype.lmsa_tutor_message.lmsa_tutor_message.has_permission"
    ),
```

- [ ] **Step 6: Grant the Gestore DocPerms**

In `apps/os_lms/os_lms/setup.py` (4 SPACES), extend `GESTORE_DOCPERMS`:

```python
GESTORE_DOCPERMS = {
    "Student Stats Export": {"read": 1, "create": 1, "write": 1, "delete": 1},
    # Read-only access to the learner-facing tutor archive. The row-level gate
    # lives in the doctypes' has_permission / get_permission_query_conditions.
    "LMSA Tutor Conversation": {"read": 1},
    "LMSA Tutor Message": {"read": 1},
}
```

This is granted by `setup_gestore_role_permissions`, already wired to `after_migrate` in `hooks.py:39`, and it skips silently when the role does not exist.

- [ ] **Step 7: Migrate, then run the tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost migrate'`
Then the `test_permissions` module command from Step 2.
Expected: PASS, 10 tests — in particular `test_plain_moderator_is_denied`.

- [ ] **Step 8: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_conversation apps/os_lms/os_lms/os_lms/doctype/lmsa_tutor_message apps/os_lms/os_lms/hooks.py apps/os_lms/os_lms/setup.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py
git commit -m "feat(tutor): restrict the chat archive to its owner and the Gestore role"
```

---

### Task 4: Close the `LMSA Query Log` read leak

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_query_log/lmsa_query_log.json`
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: no `LMS Student` DocPerm on `LMSA Query Log`.

Context: the doctype grants `read` and `create` to `LMS Student` with no `if_owner` and no query conditions, so any learner can read every learner's questions and answers over the REST API. The audit writer uses `ignore_permissions=True`, so the block is dead weight.

- [ ] **Step 1: Write the failing test**

Append to `test_permissions.py`:

```python
class TestQueryLogIsNotReadableByLearners(UnitTestCase):
    def test_lms_student_has_no_docperm_on_the_audit_log(self):
        roles = [
            p.role
            for p in frappe.get_meta("LMSA Query Log").permissions
            if p.read
        ]
        self.assertNotIn("LMS Student", roles)

    def test_audit_write_still_works_without_any_docperm(self):
        created = Created()
        try:
            course = make_course(created)
            student = make_user(created, "audit", ["LMS Student"])
            frappe.set_user(student.name)
            log = frappe.new_doc("LMSA Query Log")
            log.course = course.name
            log.member = student.name
            log.question = "domanda"
            log.answer = "risposta"
            log.status = "Answered"
            log.save(ignore_permissions=True)
            created.add("LMSA Query Log", log.name)
            self.assertTrue(frappe.db.exists("LMSA Query Log", log.name))
        finally:
            frappe.set_user("Administrator")
            created.cleanup()
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run the `test_permissions` module command.
Expected: FAIL on `test_lms_student_has_no_docperm_on_the_audit_log` — `'LMS Student' unexpectedly found`.

- [ ] **Step 3: Remove the permission block**

In `lmsa_query_log.json`, delete the whole `LMS Student` object from the `permissions` array:

```json
  {
   "create": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "LMS Student",
   "share": 1
  },
```

Leave the `System Manager`, `Moderator` and `Course Creator` blocks untouched: the audit trail stays available to the technical and editorial roles, which is a different question from who reads the learner-facing archive.

- [ ] **Step 4: Migrate, then run the tests to verify they pass**

Run the migrate command, then the `test_permissions` module command.
Expected: PASS, 12 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_query_log/lmsa_query_log.json apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_permissions.py
git commit -m "fix(tutor): stop learners from reading each other's AI query log"
```

---

### Task 5: Persist each turn from `TutorAi`, behind a setting

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json` (add `tutor_history_enabled` to `field_order` after `enabled`, and the field object)
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py:11` (after `openai_key`)
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py:168` (in the `OsLmsSettings(...)` construction)
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py` (settings helpers)
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_persistence.py`

**Interfaces:**
- Consumes: both doctypes, `build_conversation_title`.
- Produces: `TutorAi(course, lesson, user, conversation=None)`; the instance attribute `TutorAi.conversation` holds the conversation name after `ask`; setting `OsLmsSettings.tutor_history_enabled`; fixtures `enable_tutor_history()`/`restore_settings(previous)`.

- [ ] **Step 1: Write the failing test**

Append to `_fixtures.py`:

```python
def enable_tutor_history(chat_provider: str = "mock") -> dict:
    """Turn archive persistence on and return the previous values to restore."""
    doc = frappe.get_single("LMSA Settings")
    previous = {
        "tutor_history_enabled": doc.get("tutor_history_enabled"),
        "simulation_chat_provider": doc.get("simulation_chat_provider"),
    }
    doc.tutor_history_enabled = 1
    doc.simulation_chat_provider = chat_provider
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return previous


def restore_settings(previous: dict) -> None:
    doc = frappe.get_single("LMSA Settings")
    for field, value in previous.items():
        setattr(doc, field, value)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
```

Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_persistence.py` (4 SPACES):

```python
"""TutorAi writes every exchange to the learner-facing archive."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.tutor import tutor_ai as tutor_module
from os_lms.os_lms.ai.tutor.tests._fixtures import (
    Created,
    enable_tutor_history,
    make_course,
    make_user,
    restore_settings,
)
from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.model = "fake-model"
        self.provider = "fake"


class _FakeProvider:
    last_messages: list = []

    def chat(self, messages, system):
        _FakeProvider.last_messages = list(messages)
        return _FakeResponse("risposta del tutor")


class _FailingProvider:
    def chat(self, messages, system):
        raise RuntimeError("provider down")


class TestTutorPersistence(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.previous = enable_tutor_history()
        self.course = make_course(self.created)
        self.student = make_user(self.created, "learner", ["LMS Student"])

    def tearDown(self):
        # Conversations are created by the code under test, not by a fixture,
        # so collect them by name before cleaning up — never by a broad filter.
        for name in frappe.get_all(
            "LMSA Tutor Conversation", filters={"course": self.course.name}, pluck="name"
        ):
            for msg in frappe.get_all(
                "LMSA Tutor Message", filters={"conversation": name}, pluck="name"
            ):
                self.created.add("LMSA Tutor Message", msg)
            self.created.add("LMSA Tutor Conversation", name)
        for name in frappe.get_all(
            "LMSA Query Log", filters={"course": self.course.name}, pluck="name"
        ):
            self.created.add("LMSA Query Log", name)
        self.created.cleanup()
        restore_settings(self.previous)

    def _ask(self, question: str, conversation: str | None = None, provider=None):
        tutor = TutorAi(
            course=self.course.name,
            lesson=None,
            user=self.student.name,
            conversation=conversation,
        )
        with patch.object(
            tutor_module, "resolve_provider", lambda _cap: provider or _FakeProvider()
        ), patch.object(TutorAi, "_system_prompt", lambda self, q: "SYSTEM PROMPT"):
            answer = tutor.ask(question)
        return tutor, answer

    def _messages(self, conversation: str):
        return frappe.get_all(
            "LMSA Tutor Message",
            filters={"conversation": conversation},
            fields=["turn_index", "role", "content", "status", "model_used", "query_log"],
            order_by="turn_index asc",
        )

    def test_first_ask_creates_the_conversation_and_two_messages(self):
        tutor, answer = self._ask("come si gestisce un'obiezione?")
        self.assertEqual(answer, "risposta del tutor")
        self.assertTrue(tutor.conversation)

        conversation = frappe.get_doc("LMSA Tutor Conversation", tutor.conversation)
        self.assertEqual(conversation.course, self.course.name)
        self.assertEqual(conversation.member, self.student.name)
        self.assertEqual(conversation.title, "come si gestisce un'obiezione?")
        self.assertEqual(conversation.message_count, 2)

        rows = self._messages(tutor.conversation)
        self.assertEqual([r["turn_index"] for r in rows], [0, 1])
        self.assertEqual(rows[0]["role"], "user")
        self.assertEqual(rows[1]["role"], "assistant")
        self.assertEqual(rows[1]["status"], "Answered")
        self.assertEqual(rows[1]["model_used"], "fake-model")
        self.assertTrue(rows[1]["query_log"])

    def test_second_ask_appends_to_the_same_conversation(self):
        tutor, _ = self._ask("prima domanda")
        self._ask("seconda domanda", conversation=tutor.conversation)

        rows = self._messages(tutor.conversation)
        self.assertEqual([r["turn_index"] for r in rows], [0, 1, 2, 3])
        self.assertEqual(rows[2]["content"], "seconda domanda")
        count = frappe.db.get_value(
            "LMSA Tutor Conversation", tutor.conversation, "message_count"
        )
        self.assertEqual(count, 4)

    def test_failed_turn_is_archived_with_empty_content(self):
        tutor = TutorAi(
            course=self.course.name, lesson=None, user=self.student.name, conversation=None
        )
        with patch.object(
            tutor_module, "resolve_provider", lambda _cap: _FailingProvider()
        ), patch.object(TutorAi, "_system_prompt", lambda self, q: "SYSTEM PROMPT"):
            with self.assertRaises(RuntimeError):
                tutor.ask("domanda che fallisce")

        rows = self._messages(tutor.conversation)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["status"], "Failed")
        self.assertFalse(rows[1]["content"])

    def test_nothing_is_archived_when_the_setting_is_off(self):
        restore_settings({"tutor_history_enabled": 0})
        tutor, _ = self._ask("domanda senza archivio")
        self.assertIsNone(tutor.conversation)
        self.assertEqual(
            frappe.db.count("LMSA Tutor Conversation", {"course": self.course.name}), 0
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_persistence'`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'conversation'`.

- [ ] **Step 3: Add the setting**

In `lmsa_settings.json`, add `"tutor_history_enabled"` to `field_order` right after `"enabled"`, and this field object right after the `enabled` field:

```json
  {
   "default": "0",
   "description": "Store every tutor exchange as a conversation the learner can re-read. When off, only the audit log is written and the archive stays empty.",
   "fieldname": "tutor_history_enabled",
   "fieldtype": "Check",
   "label": "Chat History"
  },
```

In `oslms_settings.py`, right after the `openai_key: str` line (it must come after the last non-defaulted field):

```python
    # Learner-facing chat archive (spec 2026-09-18). Off by default so the
    # feature can ship dark and be switched on per site.
    tutor_history_enabled: bool = False
```

In `ai/utils/llm/__init__.py`, inside the `OsLmsSettings(...)` call, right after the `openai_key=...` line:

```python
        tutor_history_enabled=bool(getattr(doc, "tutor_history_enabled", 0)),
```

- [ ] **Step 4: Persist the turns**

In `tutor_ai.py` (TABS), extend the import block:

```python
from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
	build_conversation_title,
)
```

Change `__init__` to accept the conversation:

```python
	def __init__(self, course: str, lesson: str | None, user: str, conversation: str | None = None):
		if not course:
			frappe.throw(_("Course is required"))
		self.course = course
		self.lesson = lesson
		self.user = user
		# Name of the LMSA Tutor Conversation this exchange belongs to. Set by
		# the caller to continue a stored conversation, or filled in on the
		# first archived turn.
		self.conversation = conversation
		self._course_details: dict | None = None
		self._settings: OsLmsSettings | None = None
```

Replace `ask` with:

```python
	def ask(self, question: str, history: list[dict] | None = None) -> str:
		if not question or not question.strip():
			frappe.throw(_("Question is required"))

		question = question.strip()
		messages = self._build_messages(question, history or [])

		answer = ""
		status = "Failed"
		response = None
		# Initialised before the try: if _system_prompt raises, the finally
		# block must not blow up on an unbound name and mask the real error.
		system_prompt = ""
		try:
			system_prompt = self._system_prompt(question)
			provider = resolve_provider("chat")
			response = provider.chat(messages=messages, system=system_prompt)
			answer = response.text
			status = "Answered"
			return answer
		finally:
			log_name = self._log_query(
				question=question, answer=answer, context=system_prompt, status=status
			)
			self._archive_turn(
				question=question,
				answer=answer,
				status=status,
				response=response,
				query_log=log_name,
			)
```

Make `_log_query` return the record name — change its signature line to `-> str | None`, add `return log.name` after the commit, and `return None` in the `except` branch.

Append the three new helpers:

```python
	def _archive_turn(
		self,
		*,
		question: str,
		answer: str,
		status: str,
		response=None,
		query_log: str | None = None,
	) -> None:
		"""Persist the exchange to the learner-facing archive.

		Distinct from _log_query, which is the audit trail: this is the product
		entity the learner re-reads. Never raises — the answer must reach the
		user even when the archive write fails.
		"""
		if not self.settings.tutor_history_enabled:
			return
		try:
			conversation = self._ensure_conversation(question)
			start = (
				frappe.db.get_value("LMSA Tutor Conversation", conversation, "message_count") or 0
			)
			# Both turns carry the exchange's status: a failed pair is then
			# skipped whole by _stored_history, instead of replaying a question
			# whose answer is missing and breaking the user/assistant alternation.
			self._insert_message(conversation, start, "user", question, status)
			self._insert_message(
				conversation,
				start + 1,
				"assistant",
				answer,
				status,
				model_used=getattr(response, "model", "") or "",
				provider_used=getattr(response, "provider", "") or "",
				query_log=query_log,
			)
			frappe.db.set_value(
				"LMSA Tutor Conversation",
				conversation,
				{
					"message_count": start + 2,
					"last_message_at": frappe.utils.now_datetime(),
					"last_lesson": self.lesson or None,
				},
				update_modified=False,
			)
			frappe.db.commit()
		except Exception:
			frappe.log_error(title="LMSA Tutor Conversation write failed")

	def _ensure_conversation(self, question: str) -> str:
		if self.conversation:
			return self.conversation
		doc = frappe.new_doc("LMSA Tutor Conversation")
		doc.course = self.course
		doc.member = self.user
		doc.title = build_conversation_title(question)
		doc.last_lesson = self.lesson or None
		doc.insert(ignore_permissions=True)
		self.conversation = doc.name
		return doc.name

	def _insert_message(
		self,
		conversation: str,
		turn_index: int,
		role: str,
		content: str,
		status: str,
		*,
		model_used: str = "",
		provider_used: str = "",
		query_log: str | None = None,
	) -> None:
		doc = frappe.new_doc("LMSA Tutor Message")
		doc.conversation = conversation
		doc.turn_index = turn_index
		doc.role = role
		doc.content = content or ""
		doc.status = status
		doc.lesson = self.lesson or None
		doc.model_used = model_used
		doc.provider_used = provider_used
		doc.query_log = query_log
		doc.insert(ignore_permissions=True)
```

- [ ] **Step 5: Migrate, then run the tests to verify they pass**

Run the migrate command (the settings doctype changed), then the `test_persistence` module command.
Expected: PASS, 4 tests.

- [ ] **Step 6: Run the existing tutor tests to check for regressions**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_api'`
Expected: PASS, 3 tests (the audio endpoint is unchanged).

- [ ] **Step 7: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json apps/os_lms/os_lms/os_lms/ai/tutor/tests/_fixtures.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_persistence.py
git commit -m "feat(tutor): archive every exchange as a conversation turn"
```

---

### Task 6: Server-side history window and the `conversation` parameter

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/api.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_persistence.py` (extend)

**Interfaces:**
- Consumes: Task 5's `TutorAi.conversation`.
- Produces: constant `HISTORY_WINDOW_TURNS = 12`; `ask(course, lesson, question, history=None, conversation=None) -> dict` returning `{"answer": str, "conversation": str | None}`; `ask_audio(..., conversation=None)` returning the same extra key; `_resolve_conversation(conversation, course) -> str | None` in `api.py`.

Today the client re-sends the whole conversation on every question and `_build_messages` never truncates it. With storage in place the server owns the history, so a long chat can no longer inflate every subsequent prompt.

- [ ] **Step 1: Write the failing test**

Append to `test_persistence.py`:

```python
class TestHistoryWindow(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.previous = enable_tutor_history()
        self.course = make_course(self.created)
        self.student = make_user(self.created, "window", ["LMS Student"])

    def tearDown(self):
        for name in frappe.get_all(
            "LMSA Tutor Conversation", filters={"course": self.course.name}, pluck="name"
        ):
            for msg in frappe.get_all(
                "LMSA Tutor Message", filters={"conversation": name}, pluck="name"
            ):
                self.created.add("LMSA Tutor Message", msg)
            self.created.add("LMSA Tutor Conversation", name)
        for name in frappe.get_all(
            "LMSA Query Log", filters={"course": self.course.name}, pluck="name"
        ):
            self.created.add("LMSA Query Log", name)
        self.created.cleanup()
        restore_settings(self.previous)

    def _ask(self, question, conversation=None, history=None):
        tutor = TutorAi(
            course=self.course.name,
            lesson=None,
            user=self.student.name,
            conversation=conversation,
        )
        with patch.object(
            tutor_module, "resolve_provider", lambda _cap: _FakeProvider()
        ), patch.object(TutorAi, "_system_prompt", lambda self, q: "SYSTEM PROMPT"):
            tutor.ask(question, history or [])
        return tutor

    def test_stored_history_is_capped_at_the_window(self):
        tutor = self._ask("turno 0")
        for i in range(1, 10):
            self._ask(f"turno {i}", conversation=tutor.conversation)
        # The last call replayed at most HISTORY_WINDOW_TURNS stored turns
        # plus the new question.
        self.assertLessEqual(
            len(_FakeProvider.last_messages), tutor_module.HISTORY_WINDOW_TURNS + 1
        )

    def test_client_history_is_ignored_when_a_conversation_is_given(self):
        tutor = self._ask("prima")
        self._ask(
            "seconda",
            conversation=tutor.conversation,
            history=[{"from": "user", "message": "INIETTATO"}],
        )
        replayed = [m.content for m in _FakeProvider.last_messages]
        self.assertNotIn("INIETTATO", replayed)
        self.assertIn("prima", replayed)

    def test_failed_turns_are_not_replayed(self):
        tutor = self._ask("buona")
        failing = TutorAi(
            course=self.course.name,
            lesson=None,
            user=self.student.name,
            conversation=tutor.conversation,
        )
        with patch.object(
            tutor_module, "resolve_provider", lambda _cap: _FailingProvider()
        ), patch.object(TutorAi, "_system_prompt", lambda self, q: "SYSTEM PROMPT"):
            with self.assertRaises(RuntimeError):
                failing.ask("fallita")
        self._ask("terza", conversation=tutor.conversation)
        replayed = [m.content for m in _FakeProvider.last_messages]
        self.assertNotIn("", replayed)
```

And a test for the endpoint's ownership check, in the same file:

```python
class TestAskConversationOwnership(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.owner = make_user(self.created, "owner", ["LMS Student"])
        self.intruder = make_user(self.created, "intruder", ["LMS Student"])
        self.conversation = frappe.get_doc(
            {
                "doctype": "LMSA Tutor Conversation",
                "course": self.course.name,
                "member": self.owner.name,
                "title": "privata",
            }
        ).insert(ignore_permissions=True)
        self.created.add("LMSA Tutor Conversation", self.conversation.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        self.created.cleanup()

    def test_another_learner_cannot_append_to_a_conversation(self):
        from os_lms.os_lms.ai.tutor import api as tutor_api

        frappe.set_user(self.intruder.name)
        with self.assertRaises(frappe.PermissionError):
            tutor_api.ask(
                course=self.course.name,
                lesson="",
                question="fammi vedere",
                conversation=self.conversation.name,
            )

    def test_a_conversation_from_another_course_is_rejected(self):
        from os_lms.os_lms.ai.tutor import api as tutor_api

        other_course = make_course(self.created, "Other Course")
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            tutor_api.ask(
                course=other_course.name,
                lesson="",
                question="domanda",
                conversation=self.conversation.name,
            )
```

And the audio path, which must archive exactly like the text path (spec §10, case 4).
Add these imports at the top of `test_persistence.py`:

```python
from dataclasses import dataclass

from os_lms.os_lms.ai.audio import pipeline
from os_lms.os_lms.ai.tutor import api as tutor_api
```

and this class at the end of the file:

```python
@dataclass
class _FakeAudioSettings:
    stt_enabled: bool = False
    tts_enabled: bool = False
    tts_voice: str = "alloy"


class TestAskAudioPersistence(UnitTestCase):
    """ask_audio must produce the same archive records as ask."""

    def setUp(self):
        self.created = Created()
        self.previous = enable_tutor_history()
        self.course = make_course(self.created)
        self.student = make_user(self.created, "audio", ["LMS Student"])
        self._orig_load = pipeline.load_settings
        pipeline.load_settings = lambda: _FakeAudioSettings()

    def tearDown(self):
        pipeline.load_settings = self._orig_load
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "LMSA Tutor Conversation", filters={"course": self.course.name}, pluck="name"
        ):
            for msg in frappe.get_all(
                "LMSA Tutor Message", filters={"conversation": name}, pluck="name"
            ):
                self.created.add("LMSA Tutor Message", msg)
            self.created.add("LMSA Tutor Conversation", name)
        for name in frappe.get_all(
            "LMSA Query Log", filters={"course": self.course.name}, pluck="name"
        ):
            self.created.add("LMSA Query Log", name)
        self.created.cleanup()
        restore_settings(self.previous)

    def test_audio_turn_is_archived_and_reports_the_conversation(self):
        frappe.set_user(self.student.name)
        with patch.object(
            tutor_module, "resolve_provider", lambda _cap: _FakeProvider()
        ), patch.object(TutorAi, "_system_prompt", lambda self, q: "SYSTEM PROMPT"):
            out = tutor_api.ask_audio(
                course=self.course.name,
                lesson="",
                question="domanda vocale",
                want_audio=False,
            )

        self.assertTrue(out["conversation"])
        rows = frappe.get_all(
            "LMSA Tutor Message",
            filters={"conversation": out["conversation"]},
            fields=["turn_index", "role", "content"],
            order_by="turn_index asc",
        )
        self.assertEqual([r["role"] for r in rows], ["user", "assistant"])
        self.assertEqual(rows[0]["content"], "domanda vocale")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run the `test_persistence` module command.
Expected: FAIL — `AttributeError: module ... has no attribute 'HISTORY_WINDOW_TURNS'`.

- [ ] **Step 3: Add the window to `TutorAi`**

In `tutor_ai.py` (TABS), add the constant below the imports:

```python
# Stored turns replayed to the model when the server owns the history.
# 12 turns = 6 exchanges; failed turns are skipped. Caps the per-question cost
# of a long conversation, which the client-side history never did.
HISTORY_WINDOW_TURNS = 12
```

In `ask`, replace the line that builds the messages with:

```python
		# With a stored conversation the server owns the history: whatever the
		# client sends is ignored, so a long chat cannot inflate the prompt and
		# a forged history cannot be injected.
		if self.conversation:
			history = self._stored_history()
		messages = self._build_messages(question, history or [])
```

Add the helper:

```python
	def _stored_history(self) -> list[dict]:
		"""Replay the last HISTORY_WINDOW_TURNS answered turns of the conversation."""
		rows = frappe.get_all(
			"LMSA Tutor Message",
			filters={"conversation": self.conversation, "status": "Answered"},
			fields=["role", "content"],
			order_by="turn_index desc",
			limit=HISTORY_WINDOW_TURNS,
		)
		rows.reverse()
		return [{"from": row["role"], "message": row["content"]} for row in rows]
```

- [ ] **Step 4: Add the parameter and the ownership check to the endpoints**

Replace `apps/os_lms/os_lms/os_lms/ai/tutor/api.py` (TABS) with:

```python
import json

import frappe
from frappe import _

from os_lms.os_lms.ai.audio.pipeline import run_audio_turn
from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi


def _resolve_conversation(conversation: str | None, course: str) -> str | None:
	"""Validate that the caller owns the conversation and that it belongs to
	this course. Without this check a learner could append to — and replay the
	history of — somebody else's conversation."""
	if not conversation:
		return None
	row = frappe.db.get_value(
		"LMSA Tutor Conversation", conversation, ["member", "course"], as_dict=True
	)
	if not row or row.member != frappe.session.user or row.course != course:
		frappe.throw(_("Conversation not found"), frappe.PermissionError)
	return conversation


@frappe.whitelist()
def ask(
	course: str,
	lesson: str,
	question: str,
	history: list[dict] | None = None,
	conversation: str | None = None,
) -> dict:
	"""Answer a learner's question about a course or lesson."""
	# Frappe forwards complex args as JSON strings when the client posts
	# form-encoded data; normalize before use.
	if isinstance(history, str):
		history = json.loads(history)

	tutor = TutorAi(
		course=course,
		lesson=lesson or None,
		user=frappe.session.user,
		conversation=_resolve_conversation(conversation, course),
	)
	answer = tutor.ask(question, history or [])
	return {"answer": answer, "conversation": tutor.conversation}


@frappe.whitelist()
def ask_audio(
	course: str,
	lesson: str = "",
	question: str | None = None,
	audio: str | None = None,
	mime: str = "audio/webm",
	language: str = "it",
	history: list[dict] | None = None,
	want_audio: bool = True,
	conversation: str | None = None,
) -> dict:
	"""Single-call audio (or text) tutor turn: STT? -> TutorAi.ask -> TTS?.

	Returns {question_text, answer_text, audio_base64, mime, conversation}.
	"""
	if isinstance(history, str):
		history = json.loads(history)
	user = frappe.session.user
	resolved = _resolve_conversation(conversation, course)
	# One TutorAi instance for the whole turn, so the conversation it creates
	# on the first question is the one reported back to the client.
	tutor = TutorAi(course=course, lesson=lesson or None, user=user, conversation=resolved)

	def _produce(q: str) -> str:
		return tutor.ask(q, history or [])

	result = run_audio_turn(
		audio=audio,
		text=question,
		mime=mime,
		language=language,
		produce_answer=_produce,
		want_audio=want_audio,
	)
	result["conversation"] = tutor.conversation
	return result
```

Note the change of shape in `ask_audio`: it used to build a new `TutorAi` inside `_produce`. Hoisting it out is what lets the caller learn the conversation name.

- [ ] **Step 5: Run the tests to verify they pass**

Run the `test_persistence` module command, then the `test_api` module command.
Expected: PASS — `test_persistence` 10 tests, `test_api` 3 tests. `test_api` patches `TutorAi` with a fake whose `__init__` takes `(course, lesson, user)`; if it now fails on the `conversation` kwarg, update `_FakeTutor.__init__` in `test_api.py` to `def __init__(self, course, lesson, user, conversation=None)` and give it `self.conversation = conversation`.

- [ ] **Step 6: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py apps/os_lms/os_lms/os_lms/ai/tutor/api.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/
git commit -m "feat(tutor): own the chat history server-side with a sliding window"
```

> **CHECKPOINT — end of Fase 1.** Stop here for review. Verify by hand: switch `Chat History` on in `LMSA Settings`, ask the tutor two questions from the SPA, and confirm in the Desk (`/app/lmsa-tutor-conversation`) that one conversation with four messages exists and that its title is the first question.

---

# FASE 2 — Archivio e interfaccia dello studente

---

### Task 7: The archive endpoints

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/tutor/history.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py`

**Interfaces:**
- Consumes: both doctypes, `build_conversation_title`, `TITLE_MAX_LENGTH`, `can_view_tutor_archive` (Task 8 — import it lazily inside the functions so the two tasks can land in either order).
- Produces: `list_conversations(course, member=None, include_archived=False) -> list[dict]`; `get_conversation(name) -> dict` (keys: `name, title, course, member, started_at, last_message_at, message_count, archived, can_write, messages[]`); `rename_conversation(name, title) -> dict`; `archive_conversation(name, archived=True) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py` (4 SPACES):

```python
"""Endpoints of the learner-facing tutor archive."""
from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.tutor import history
from os_lms.os_lms.ai.tutor.tests._fixtures import (
    Created,
    add_message,
    make_conversation,
    make_course,
    make_user,
)


class TestArchiveEndpoints(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.owner = make_user(self.created, "owner", ["LMS Student"])
        self.other = make_user(self.created, "other", ["LMS Student"])
        self.manager = make_user(self.created, "gestore", ["Moderator", "Gestore"])

        self.live = make_conversation(
            self.created, self.course.name, self.owner.name, title="viva"
        )
        add_message(self.created, self.live.name, 0, "user", "domanda")
        add_message(self.created, self.live.name, 1, "assistant", "risposta")
        self.archived = make_conversation(
            self.created, self.course.name, self.owner.name, title="archiviata", archived=1
        )
        self.foreign = make_conversation(
            self.created, self.course.name, self.other.name, title="altrui"
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        self.created.cleanup()

    def test_owner_lists_only_their_own_live_conversations(self):
        frappe.set_user(self.owner.name)
        rows = history.list_conversations(course=self.course.name)
        titles = [r["title"] for r in rows]
        self.assertEqual(titles, ["viva"])

    def test_include_archived_adds_the_archived_ones(self):
        frappe.set_user(self.owner.name)
        rows = history.list_conversations(course=self.course.name, include_archived=True)
        self.assertEqual(sorted(r["title"] for r in rows), ["archiviata", "viva"])

    def test_a_learner_cannot_list_another_learner(self):
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            history.list_conversations(course=self.course.name, member=self.other.name)

    def test_a_manager_can_list_another_learner(self):
        frappe.set_user(self.manager.name)
        rows = history.list_conversations(course=self.course.name, member=self.other.name)
        self.assertEqual([r["title"] for r in rows], ["altrui"])

    def test_get_conversation_returns_messages_in_order(self):
        frappe.set_user(self.owner.name)
        data = history.get_conversation(self.live.name)
        self.assertEqual(data["title"], "viva")
        self.assertTrue(data["can_write"])
        self.assertEqual([m["turn_index"] for m in data["messages"]], [0, 1])

    def test_get_conversation_is_denied_to_another_learner(self):
        frappe.set_user(self.other.name)
        with self.assertRaises(frappe.PermissionError):
            history.get_conversation(self.live.name)

    def test_manager_reads_but_cannot_write(self):
        frappe.set_user(self.manager.name)
        data = history.get_conversation(self.live.name)
        self.assertFalse(data["can_write"])
        with self.assertRaises(frappe.PermissionError):
            history.rename_conversation(self.live.name, "rinominata")

    def test_rename_clips_the_title(self):
        frappe.set_user(self.owner.name)
        history.rename_conversation(self.live.name, "x" * 400)
        title = frappe.db.get_value("LMSA Tutor Conversation", self.live.name, "title")
        self.assertEqual(len(title), 140)

    def test_archive_hides_the_conversation_from_the_default_list(self):
        frappe.set_user(self.owner.name)
        history.archive_conversation(self.live.name, archived=True)
        rows = history.list_conversations(course=self.course.name)
        self.assertEqual(rows, [])
        history.archive_conversation(self.live.name, archived=False)
        rows = history.list_conversations(course=self.course.name)
        self.assertEqual(len(rows), 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_history_api'`
Expected: FAIL — `ModuleNotFoundError: os_lms.os_lms.ai.tutor.history`.

- [ ] **Step 3: Write the endpoints**

Create `apps/os_lms/os_lms/os_lms/ai/tutor/history.py` (TABS):

```python
"""Learner-facing archive of tutor conversations.

Read and manage only: the conversations themselves are written by TutorAi
during `ask`. Kept apart from api.py so the chat path and the archive path stay
independently readable.

frappe.get_all bypasses permissions by design, so every listing here gates
explicitly on the member filter plus can_view_tutor_archive(); the doctype
hooks are the second line of defence, for direct REST access.
"""

import frappe
from frappe import _
from frappe.utils import cint

from os_lms.os_lms.doctype.lmsa_tutor_conversation.lmsa_tutor_conversation import (
	TITLE_MAX_LENGTH,
	build_conversation_title,
)

CONVERSATION_FIELDS = [
	"name",
	"title",
	"course",
	"member",
	"started_at",
	"last_message_at",
	"message_count",
	"archived",
	"last_lesson",
]


def _can_view_others() -> bool:
	# Imported lazily: os_lms.os_lms.api imports heavy report helpers.
	from os_lms.os_lms.api import can_view_tutor_archive

	return can_view_tutor_archive()


def _owned(name: str):
	"""Load a conversation the caller owns, or refuse."""
	doc = frappe.get_doc("LMSA Tutor Conversation", name)
	if doc.member != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


def _stringify_dates(row: dict) -> dict:
	for key in ("started_at", "last_message_at", "creation"):
		if row.get(key):
			row[key] = str(row[key])
	return row


@frappe.whitelist()
def list_conversations(
	course: str, member: str | None = None, include_archived: bool = False
) -> list[dict]:
	"""Conversations for `course`: the caller's, or — managers only — `member`'s."""
	target = frappe.session.user
	if member and member != frappe.session.user:
		if not _can_view_others():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		target = member

	filters: dict = {"course": course, "member": target}
	if not cint(include_archived):
		filters["archived"] = 0

	rows = frappe.get_all(
		"LMSA Tutor Conversation",
		filters=filters,
		fields=CONVERSATION_FIELDS,
		order_by="last_message_at desc",
	)
	return [_stringify_dates(row) for row in rows]


@frappe.whitelist()
def get_conversation(name: str) -> dict:
	"""Conversation header plus its messages, oldest first."""
	row = frappe.db.get_value(
		"LMSA Tutor Conversation", name, CONVERSATION_FIELDS, as_dict=True
	)
	if not row:
		frappe.throw(_("Conversation not found"))
	if row.member != frappe.session.user and not _can_view_others():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	messages = frappe.get_all(
		"LMSA Tutor Message",
		filters={"conversation": name},
		fields=["name", "turn_index", "role", "content", "status", "lesson", "creation"],
		order_by="turn_index asc",
	)
	data = _stringify_dates(dict(row))
	data["messages"] = [_stringify_dates(m) for m in messages]
	# Managers read the archive; only the owner may rename, archive or resume.
	data["can_write"] = row.member == frappe.session.user
	return data


@frappe.whitelist()
def rename_conversation(name: str, title: str) -> dict:
	"""Rename a conversation. Owner only."""
	doc = _owned(name)
	doc.title = build_conversation_title(title)[:TITLE_MAX_LENGTH]
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "title": doc.title}


@frappe.whitelist()
def archive_conversation(name: str, archived: bool = True) -> dict:
	"""Archive or restore a conversation. Owner only.

	The learner cannot delete: archiving is the only removal (decision D2).
	"""
	doc = _owned(name)
	doc.archived = 1 if cint(archived) else 0
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "archived": doc.archived}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the `test_history_api` module command.
Expected: PASS, 9 tests. They depend on `can_view_tutor_archive` from Task 8 — if that function does not exist yet, do Task 8 Step 3 first.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/tutor/history.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py
git commit -m "feat(tutor): add the chat archive endpoints"
```

---

### Task 8: The manager gate and the student picker source

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/api.py` (next to `EXPORT_STATS_ROLES`, around line 921)
- Modify: `apps/os_lms/os_lms/os_lms/override_api.py:212-214`
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/history.py` (add `list_course_students`)
- Test: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py` (extend)

**Interfaces:**
- Consumes: `LMSA Tutor Conversation`.
- Produces: `can_view_tutor_archive() -> bool`; `TUTOR_ARCHIVE_ROLES`; `list_course_students(course) -> list[dict]` with keys `member, full_name, conversations`; SPA flags `can_view_tutor_archive` and `tutor_history_enabled`.

- [ ] **Step 1: Write the failing test**

Append to `test_history_api.py`:

```python
class TestManagerGate(UnitTestCase):
    def setUp(self):
        self.created = Created()
        self.course = make_course(self.created)
        self.learner = make_user(self.created, "learner", ["LMS Student"])
        self.moderator = make_user(self.created, "mod", ["Moderator"])
        self.manager = make_user(self.created, "gestore", ["Moderator", "Gestore"])
        make_conversation(self.created, self.course.name, self.learner.name, title="una")
        make_conversation(self.created, self.course.name, self.learner.name, title="due")

    def tearDown(self):
        frappe.set_user("Administrator")
        self.created.cleanup()

    def test_moderator_is_not_a_manager(self):
        from os_lms.os_lms.api import can_view_tutor_archive

        frappe.set_user(self.moderator.name)
        self.assertFalse(can_view_tutor_archive())

    def test_gestore_is_a_manager(self):
        from os_lms.os_lms.api import can_view_tutor_archive

        frappe.set_user(self.manager.name)
        self.assertTrue(can_view_tutor_archive())

    def test_student_picker_lists_learners_with_conversations(self):
        frappe.set_user(self.manager.name)
        rows = history.list_course_students(course=self.course.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["member"], self.learner.name)
        self.assertEqual(rows[0]["conversations"], 2)
        self.assertTrue(rows[0]["full_name"])

    def test_student_picker_is_denied_to_a_learner(self):
        frappe.set_user(self.learner.name)
        with self.assertRaises(frappe.PermissionError):
            history.list_course_students(course=self.course.name)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run the `test_history_api` module command.
Expected: FAIL — `ImportError: cannot import name 'can_view_tutor_archive'`.

- [ ] **Step 3: Add the gate helper**

In `apps/os_lms/os_lms/os_lms/api.py` (TABS), right below the `EXPORT_STATS_ROLES` block:

```python
TUTOR_ARCHIVE_ROLES = ("System Manager", "Gestore")


def can_view_tutor_archive() -> bool:
	"""Single source of truth for who may read another learner's tutor chats.

	Deliberately NOT Moderator / Course Creator: the client scoped this to the
	learner plus the "Gestore" manager bundle. Since a Gestore also holds
	Moderator, granting on Moderator would widen it to every moderator.
	The SPA reads the same helper through override_api.get_user_info, so the
	link and the endpoints can never disagree.
	"""
	roles = frappe.get_roles()
	return any(role in roles for role in TUTOR_ARCHIVE_ROLES)
```

- [ ] **Step 4: Add the student picker endpoint**

Append to `history.py` (TABS):

```python
@frappe.whitelist()
def list_course_students(course: str) -> list[dict]:
	"""Learners with at least one stored conversation on `course`. Managers only.

	Deliberately not the enrolment list: the picker should only offer people
	who actually have something to read.
	"""
	if not _can_view_others():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	rows = frappe.get_all(
		"LMSA Tutor Conversation",
		filters={"course": course},
		fields=["member", "count(name) as conversations"],
		group_by="member",
		order_by="conversations desc",
	)
	if not rows:
		return []

	full_names = {
		user["name"]: user["full_name"]
		for user in frappe.get_all(
			"User",
			filters={"name": ["in", [row["member"] for row in rows]]},
			fields=["name", "full_name"],
		)
	}
	for row in rows:
		row["full_name"] = full_names.get(row["member"]) or row["member"]
	return rows
```

- [ ] **Step 5: Expose the flags to the SPA**

In `override_api.py` (4 SPACES), in `get_user_info`, replace the `can_export_student_stats` import line and its use with:

```python
        from os_lms.os_lms.api import can_export_student_stats, can_view_tutor_archive

        result["can_export_stats"] = can_export_student_stats()
        # Read-only access to other learners' tutor conversations (Gestore only).
        result["can_view_tutor_archive"] = can_view_tutor_archive()
```

In the same file, in `get_lms_settings`, after the `result["ai_enabled"]` line:

```python
         result["tutor_history_enabled"] = bool(lmsa.get("tutor_history_enabled"))
```

(Keep the file's existing 9-space indentation inside that `if` block — it is pre-existing and consistent there.)

- [ ] **Step 6: Run the tests to verify they pass**

Run the `test_history_api` module command.
Expected: PASS, 13 tests.

- [ ] **Step 7: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/api.py apps/os_lms/os_lms/os_lms/override_api.py apps/os_lms/os_lms/os_lms/ai/tutor/history.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_history_api.py
git commit -m "feat(tutor): gate the chat archive on the Gestore role"
```

---

### Task 9: Make the chat store conversation-aware

**Files:**
- Modify: `frontend/src/stores/aiChat.js` (full rewrite, 45 lines → ~85)

**Interfaces:**
- Consumes: `os_lms.os_lms.ai.tutor.history.get_conversation` (Task 7).
- Produces: store fields `conversationId`; actions `startNew()`, `loadConversation(name)`; `clear()` now also resets `conversationId`.

- [ ] **Step 1: Rewrite the store**

Replace `frontend/src/stores/aiChat.js` with:

```js
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { call } from 'frappe-ui'
import { useAiContext } from './aiContext'

export const useAiChat = defineStore('ai-chat', () => {
	const messages = ref([])
	const question = ref('')
	const isLoading = ref(false)
	const lastCourse = ref(null)
	// Name of the stored LMSA Tutor Conversation this panel is writing to.
	// Null means "a new conversation": the backend creates it on the first turn
	// and returns its name.
	const conversationId = ref(null)

	const aiContext = useAiContext()

	// Reset only when the user moves between two different non-null courses.
	// Transitions through null (navigating away then back to the same course)
	// must preserve the conversation.
	watch(
		() => aiContext.course,
		(newCourse) => {
			if (!newCourse) return
			if (lastCourse.value && lastCourse.value !== newCourse) {
				clear()
			}
			lastCourse.value = newCourse
		},
		{ immediate: true },
	)

	function addMessage(message) {
		messages.value.push(message)
	}

	function clear() {
		messages.value = []
		question.value = ''
		isLoading.value = false
		conversationId.value = null
	}

	// Start a fresh conversation. The stored ones are untouched — nothing is
	// deleted from the panel any more, only archived from the archive page.
	function startNew() {
		clear()
	}

	// Load a stored conversation so the learner can read it and keep going.
	async function loadConversation(name) {
		const data = await call(
			'os_lms.os_lms.ai.tutor.history.get_conversation',
			{ name },
		)
		conversationId.value = data.name
		messages.value = (data.messages || []).map((m) => ({
			role: m.role,
			content: m.content,
			status: m.status,
			createdAt: m.creation,
			sources: [],
		}))
		question.value = ''
		isLoading.value = false
		return data
	}

	return {
		messages,
		question,
		isLoading,
		conversationId,
		addMessage,
		clear,
		startNew,
		loadConversation,
	}
})
```

- [ ] **Step 2: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/aiChat.js
git commit -m "feat(tutor): make the chat store conversation-aware"
```

---

### Task 10: Wire the floating panel to stored conversations

**Files:**
- Create: `frontend/src/oslms/components/ai/ConversationPicker.vue`
- Modify: `frontend/src/oslms/components/ai/ChatBot.vue` (the two call sites and the assistant bubble)
- Modify: `frontend/src/oslms/components/ai/AiChatButton.vue` (header)

**Interfaces:**
- Consumes: store from Task 9; `list_conversations`, `archive_conversation` from Task 7.
- Produces: `<ConversationPicker :course :modelValue @update:modelValue @new />` exposing `reload()`.

- [ ] **Step 1: Create the picker**

Create `frontend/src/oslms/components/ai/ConversationPicker.vue`:

```vue
<template>
	<div class="flex items-center gap-1.5">
		<Select
			class="flex-1 min-w-0"
			size="sm"
			:modelValue="modelValue ?? ''"
			:options="options"
			@update:modelValue="(value) => emit('update:modelValue', value || null)"
		/>
		<Button
			variant="ghost"
			size="sm"
			:aria-label="__('New conversation')"
			@click="emit('new')"
		>
			<template #icon>
				<Plus class="size-4 stroke-1.5" />
			</template>
		</Button>
	</div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { Button, Select, createResource } from 'frappe-ui'
import { Plus } from 'lucide-vue-next'

const props = defineProps<{
	course: string
	modelValue: string | null
}>()

const emit = defineEmits<{
	(e: 'update:modelValue', value: string | null): void
	(e: 'new'): void
}>()

const conversations = createResource({
	url: 'os_lms.os_lms.ai.tutor.history.list_conversations',
	makeParams: () => ({ course: props.course }),
	auto: false,
})

watch(
	() => props.course,
	(course) => {
		if (course) conversations.fetch()
	},
	{ immediate: true },
)

const options = computed(() => [
	{ label: __('New conversation'), value: '' },
	...(conversations.data || []).map((row: any) => ({
		label: row.title || __('Untitled conversation'),
		value: row.name,
	})),
])

defineExpose({ reload: () => conversations.reload() })
</script>
```

- [ ] **Step 2: Send and receive the conversation in `ChatBot.vue`**

In `sendQuestion`, replace the history snapshot and the call with:

```ts
	// With a stored conversation the server owns the history, so don't resend it.
	const history = chat.conversationId
		? null
		: chat.messages.map((m) => ({
				from: m.role,
				message: m.content,
			}))
```

and inside the `call(...)` payload object, replace `history,` with:

```ts
				...(history ? { history } : {}),
				...(chat.conversationId ? { conversation: chat.conversationId } : {}),
```

After the answer is read from the response, before `chat.addMessage`, add:

```ts
		if (response.conversation) chat.conversationId = response.conversation
```

Apply the same three edits to `onAudioMessage` (its call uses `res`, so the last line is `if (res.conversation) chat.conversationId = res.conversation`).

- [ ] **Step 3: Render a failed turn as a notice**

In the `ChatBot.vue` template, replace the assistant branch opening tag

```html
				<div
					v-if="message.role === 'assistant'"
					class="flex items-end gap-1.5"
				>
```

with a preceding failure branch:

```html
				<div
					v-if="message.role === 'assistant' && message.status === 'Failed'"
					class="text-sm italic text-ink-gray-5"
				>
					{{ __('Answer not available: the AI service failed on this question.') }}
				</div>
				<div
					v-else-if="message.role === 'assistant'"
					class="flex items-end gap-1.5"
				>
```

and add, just before the `sources` block, the generation date for stored turns:

```html
				<div v-if="message.createdAt" class="mt-1 text-xs text-ink-gray-4">
					{{ __('Generated on') }} {{ dayjs(message.createdAt).format('DD/MM/YYYY HH:mm') }}
				</div>
```

Add `import { dayjs } from 'frappe-ui'` to the script block, and extend the `Message` interface with `status?: string` and `createdAt?: string`.

- [ ] **Step 4: Put the picker in the panel header**

In `AiChatButton.vue`, replace the header's right-hand button group so the trash becomes "archive" and a picker row is added under the title:

```html
				<div class="flex items-center gap-2">
					<button
						type="button"
						class="text-ink-gray-5 hover:text-ink-red-6 transition disabled:opacity-40 disabled:cursor-not-allowed"
						:aria-label="__('Archive conversation')"
						:disabled="!chat.conversationId"
						@click="archiveCurrent"
					>
						<Archive class="size-4 stroke-1.5" />
					</button>
					<router-link
						v-if="aiContext.course"
						class="text-ink-gray-5 hover:text-ink-gray-9 transition"
						:aria-label="__('All conversations')"
						:to="{
							name: 'CourseTutorArchive',
							params: { courseName: aiContext.course },
						}"
						@click="close"
					>
						<History class="size-4 stroke-1.5" />
					</router-link>
					<button
						type="button"
						class="text-ink-gray-5 hover:text-ink-gray-9 transition"
						:aria-label="__('Close')"
						@click="close"
					>
						<X class="size-4 stroke-1.5" />
					</button>
				</div>
```

Immediately after the header `div`, add the picker row:

```html
			<div
				v-if="historyEnabled && aiContext.course"
				class="px-4 py-2 border-b border-outline-gray-2"
			>
				<ConversationPicker
					ref="pickerRef"
					:course="aiContext.course"
					:modelValue="chat.conversationId"
					@update:modelValue="onPick"
					@new="chat.startNew()"
				/>
			</div>
```

Replace the script block's imports and body additions:

```ts
import { computed, ref } from 'vue'
import { Archive, History, Sparkles, X } from 'lucide-vue-next'
import { toast, call } from 'frappe-ui'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'
import ConversationPicker from '@/oslms/components/ai/ConversationPicker.vue'
import { useAiContext } from '@/stores/aiContext'
import { useAiChat } from '@/stores/aiChat'
import { useSettings } from '@/stores/settings'

const aiContext = useAiContext()
const chat = useAiChat()
const settings = useSettings()
const isOpen = ref<boolean>(false)
const pickerRef = ref<{ reload: () => void } | null>(null)

const historyEnabled = computed<boolean>(() =>
	Boolean(settings.settings?.data?.tutor_history_enabled),
)

async function onPick(name: string | null): Promise<void> {
	if (!name) {
		chat.startNew()
		return
	}
	try {
		await chat.loadConversation(name)
	} catch (error: any) {
		toast.error(error?.message || __('Could not load the conversation'))
	}
}

async function archiveCurrent(): Promise<void> {
	if (!chat.conversationId) return
	try {
		await call('os_lms.os_lms.ai.tutor.history.archive_conversation', {
			name: chat.conversationId,
			archived: true,
		})
		chat.startNew()
		pickerRef.value?.reload()
		toast.success(__('Conversation archived'))
	} catch (error: any) {
		toast.error(error?.message || __('Could not archive the conversation'))
	}
}
```

Delete the old `clearChat` function — nothing references it any more.

- [ ] **Step 5: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 6: Manual check**

With `Chat History` on: open the floating panel on a course, ask two questions, reload the page, reopen the panel, pick the conversation from the dropdown — the two exchanges come back. Press the archive icon: the panel empties and the conversation leaves the dropdown.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/oslms/components/ai/ConversationPicker.vue frontend/src/oslms/components/ai/ChatBot.vue frontend/src/oslms/components/ai/AiChatButton.vue
git commit -m "feat(tutor): browse and resume stored conversations from the chat panel"
```

---

### Task 11: The "progetto corso" page

**Files:**
- Create: `frontend/src/oslms/pages/Courses/CourseTutorArchive.vue`
- Modify: `frontend/src/router.js` (after the `/courses/:courseName/certification` route)
- Modify: `frontend/src/overrides/pages/Courses/CourseOverview.vue` (entry button)

**Interfaces:**
- Consumes: `list_conversations`, `get_conversation`, `rename_conversation`, `archive_conversation`; the store from Task 9; `ChatBot.vue`.
- Produces: route name `CourseTutorArchive` with param `courseName`.

- [ ] **Step 1: Create the page**

Create `frontend/src/oslms/pages/Courses/CourseTutorArchive.vue`:

```vue
<template>
	<div class="flex h-full flex-col">
		<header class="border-b border-outline-gray-2 px-5 py-4">
			<Breadcrumbs :items="breadcrumbs" />
			<h1 class="mt-2 text-xl font-semibold text-ink-gray-9">
				{{ __('AI Tutor') }}
			</h1>
			<p class="text-sm text-ink-gray-6">
				{{ __('All your conversations with the tutor for this course.') }}
			</p>
		</header>

		<div class="flex min-h-0 flex-1 flex-col md:flex-row">
			<aside
				class="overflow-y-auto border-outline-gray-2 md:w-80 md:border-e"
				:class="{ 'hidden md:block': selected }"
			>
				<div class="flex items-center justify-between px-4 py-3">
					<Button variant="subtle" size="sm" @click="startNew">
						{{ __('New conversation') }}
					</Button>
					<label class="flex items-center gap-1.5 text-xs text-ink-gray-6">
						<input type="checkbox" v-model="includeArchived" />
						{{ __('Show archived') }}
					</label>
				</div>

				<p
					v-if="conversations.data && !conversations.data.length"
					class="px-4 py-6 text-sm text-ink-gray-5"
				>
					{{ __('No conversations yet. Ask the tutor a question to start one.') }}
				</p>

				<button
					v-for="row in conversations.data || []"
					:key="row.name"
					type="button"
					class="block w-full border-b border-outline-gray-1 px-4 py-3 text-start hover:bg-surface-gray-1"
					:class="{ 'bg-surface-gray-2': row.name === selected }"
					@click="open(row.name)"
				>
					<div class="truncate text-sm font-medium text-ink-gray-8">
						{{ row.title || __('Untitled conversation') }}
					</div>
					<div class="mt-0.5 text-xs text-ink-gray-5">
						{{ dayjs(row.last_message_at).format('DD/MM/YYYY HH:mm') }} ·
						{{ row.message_count }} {{ __('messages') }}
						<span v-if="row.archived"> · {{ __('archived') }}</span>
					</div>
				</button>
			</aside>

			<section class="flex min-w-0 flex-1 flex-col">
				<div
					v-if="!selected"
					class="hidden flex-1 items-center justify-center p-6 text-sm text-ink-gray-5 md:flex"
				>
					{{ __('Pick a conversation to read it.') }}
				</div>

				<template v-else>
					<div
						class="flex items-center justify-between gap-2 border-b border-outline-gray-2 px-4 py-2"
					>
						<Button
							class="md:hidden"
							variant="ghost"
							size="sm"
							@click="selected = null"
						>
							{{ __('Back') }}
						</Button>
						<div class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-8">
							{{ current?.title }}
						</div>
						<Button
							v-if="current?.can_write && current?.name"
							variant="ghost"
							size="sm"
							@click="rename"
						>
							{{ __('Rename') }}
						</Button>
						<Button
							v-if="current?.can_write && current?.name"
							variant="ghost"
							size="sm"
							@click="toggleArchive"
						>
							{{ current?.archived ? __('Restore') : __('Archive') }}
						</Button>
					</div>

					<div class="min-h-0 flex-1 overflow-y-auto">
						<ChatBot :courseId="courseName" lessonId="" />
					</div>
				</template>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Breadcrumbs, Button, call, createResource, dayjs, toast } from 'frappe-ui'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'
import { useAiChat } from '@/stores/aiChat'
import { useAiContext } from '@/stores/aiContext'

const props = defineProps<{ courseName: string }>()

const chat = useAiChat()
const aiContext = useAiContext()
const selected = ref<string | null>(null)
const includeArchived = ref<boolean>(false)
const current = ref<any>(null)

// The panel and this page share one store, so the floating button keeps
// writing to whatever conversation is open here.
watch(
	() => props.courseName,
	(course) => {
		aiContext.setContext({ course })
		selected.value = null
		current.value = null
		chat.startNew()
	},
	{ immediate: true },
)

const conversations = createResource({
	url: 'os_lms.os_lms.ai.tutor.history.list_conversations',
	makeParams: () => ({
		course: props.courseName,
		include_archived: includeArchived.value ? 1 : 0,
	}),
	auto: true,
})

watch(includeArchived, () => conversations.reload())

const breadcrumbs = computed(() => [
	{ label: __('Courses'), route: { name: 'Courses' } },
	{
		label: props.courseName,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{ label: __('AI Tutor') },
])

async function open(name: string): Promise<void> {
	try {
		current.value = await chat.loadConversation(name)
		selected.value = name
	} catch (error: any) {
		toast.error(error?.message || __('Could not load the conversation'))
	}
}

function startNew(): void {
	chat.startNew()
	// No `name` yet: the backend creates the record on the first answered turn,
	// which is why Rename and Archive stay hidden until then.
	current.value = {
		name: null,
		title: __('New conversation'),
		can_write: true,
		archived: 0,
	}
	selected.value = 'new'
}

// The backend names a brand-new conversation on its first turn: pick that name
// up so the list refreshes and the header actions appear.
watch(
	() => chat.conversationId,
	(id) => {
		if (!id || selected.value === id) return
		selected.value = id
		if (current.value) current.value.name = id
		conversations.reload()
	},
)

async function rename(): Promise<void> {
	const title = window.prompt(__('New title'), current.value?.title || '')
	if (!title) return
	const data = await call('os_lms.os_lms.ai.tutor.history.rename_conversation', {
		name: current.value.name,
		title,
	})
	current.value.title = data.title
	conversations.reload()
}

async function toggleArchive(): Promise<void> {
	const data = await call('os_lms.os_lms.ai.tutor.history.archive_conversation', {
		name: current.value.name,
		archived: !current.value?.archived,
	})
	current.value.archived = data.archived
	conversations.reload()
	toast.success(data.archived ? __('Conversation archived') : __('Conversation restored'))
}
</script>
```

- [ ] **Step 2: Add the route**

In `frontend/src/router.js`, right after the `CourseCertification` route object:

```js
	{
		path: '/courses/:courseName/tutor',
		name: 'CourseTutorArchive',
		component: () =>
			import('@/oslms/pages/Courses/CourseTutorArchive.vue'),
		props: true,
	},
```

- [ ] **Step 3: Add the single entry point**

In `frontend/src/overrides/pages/Courses/CourseOverview.vue`, inside the first `<section class="space-y-4">`, right after the `<CourseTagBadges ... />` element:

```html
					<!-- OSLMS-CUSTOM: entry point to the per-course AI tutor archive
					("progetto corso"). Gated on membership OR the manager flag —
					never on isAdmin, which also covers instructors and moderators,
					the roles the archive policy excludes. -->
					<router-link
						v-if="showTutorArchive"
						:to="{
							name: 'CourseTutorArchive',
							params: { courseName: course.data.name },
						}"
					>
						<Button variant="subtle" size="sm">
							<template #prefix>
								<span class="lucide-sparkles size-4" />
							</template>
							{{ __('AI Tutor conversations') }}
						</Button>
					</router-link>
```

and in its `<script setup>`, after the `showMobileCta` computed:

```ts
// OSLMS-CUSTOM: the archive entry. `can_view_tutor_archive` is the Gestore-only
// flag from override_api.get_user_info — do NOT use isAdmin here.
const showTutorArchive = computed<boolean>(() => {
	if (!settings.settings?.data?.tutor_history_enabled) return false
	return (
		Boolean(props.course.data?.membership) ||
		Boolean(user?.data?.can_view_tutor_archive)
	)
})
```

Add `import { useSettings } from '@/stores/settings'` and `const settings = useSettings()` to the script block.

- [ ] **Step 4: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 5: Manual check**

As an enrolled learner with `Chat History` on: the course page shows "Conversazioni del Tutor AI"; the page lists the conversations; opening one shows the transcript; asking a new question from it appends to that conversation; "Show archived" reveals archived ones. On a phone the list and the transcript alternate with the Back button.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/oslms/pages/Courses/CourseTutorArchive.vue frontend/src/router.js frontend/src/overrides/pages/Courses/CourseOverview.vue
git commit -m "feat(tutor): add the per-course AI tutor archive page"
```

> **CHECKPOINT — end of Fase 2.** Stop for review. The learner-facing feature is complete; the manager sees nothing yet.

---

# FASE 3 — Vista del Gestore, impostazioni, documentazione

---

### Task 12: The student picker for managers

**Files:**
- Modify: `frontend/src/oslms/pages/Courses/CourseTutorArchive.vue`

**Interfaces:**
- Consumes: `list_course_students` and the `member` parameter of `list_conversations` (Task 8); the SPA flag `can_view_tutor_archive`.
- Produces: nothing downstream.

- [ ] **Step 1: Add the picker to the header**

In `CourseTutorArchive.vue`, after the `<p>` in `<header>`:

```html
			<!-- Manager-only (Gestore): read another learner's conversations.
			Read-only — the actions above the transcript stay hidden because
			get_conversation returns can_write = false. -->
			<div v-if="canViewOthers" class="mt-3 w-72">
				<Select
					:label="__('Student')"
					v-model="selectedMember"
					:options="studentOptions"
				/>
			</div>
```

- [ ] **Step 2: Add the state and the resource**

In the script block, add to the imports `Select` from `frappe-ui` and `inject` from `vue`, then:

```ts
import type { SessionUser } from '@/types/api'

const user = inject<SessionUser>('$user')

const canViewOthers = computed<boolean>(() =>
	Boolean(user?.data?.can_view_tutor_archive),
)

// Empty = the viewer's own conversations. A manager picks a learner here.
const selectedMember = ref<string>('')

const students = createResource({
	url: 'os_lms.os_lms.ai.tutor.history.list_course_students',
	makeParams: () => ({ course: props.courseName }),
	auto: false,
})

watch(
	[canViewOthers, () => props.courseName],
	([allowed, course]) => {
		if (allowed && course) students.fetch()
	},
	{ immediate: true },
)

const studentOptions = computed(() => [
	{ label: __('My conversations'), value: '' },
	...(students.data || []).map((row: any) => ({
		label: `${row.full_name} (${row.conversations})`,
		value: row.member,
	})),
])

watch(selectedMember, () => {
	selected.value = null
	current.value = null
	conversations.reload()
})
```

and extend the list resource's params:

```ts
	makeParams: () => ({
		course: props.courseName,
		include_archived: includeArchived.value ? 1 : 0,
		...(selectedMember.value ? { member: selectedMember.value } : {}),
	}),
```

- [ ] **Step 3: Hide the composer when reading someone else**

Wrap the `<ChatBot ... />` element:

```html
					<div class="min-h-0 flex-1 overflow-y-auto">
						<ChatBot
							v-if="current?.can_write"
							:courseId="courseName"
							lessonId=""
						/>
						<TranscriptReadOnly v-else :messages="current?.messages || []" />
					</div>
```

The read-only renderer is its own component, so the page keeps one responsibility. Create `frontend/src/oslms/components/ai/TranscriptReadOnly.vue`:

```vue
<template>
	<div class="space-y-4 p-4">
		<div
			v-for="message in messages"
			:key="message.name"
			:class="[
				'rounded-lg p-3',
				message.role === 'user' ? 'ms-8 bg-surface-gray-2' : 'me-8 bg-surface-blue-3',
			]"
		>
			<div class="mb-1 text-xs font-medium text-ink-gray-5">
				{{ message.role === 'user' ? __('Student') : __('AI Assistant') }}
				<span v-if="message.creation">
					· {{ dayjs(message.creation).format('DD/MM/YYYY HH:mm') }}
				</span>
			</div>
			<div
				v-if="message.status === 'Failed'"
				class="text-sm italic text-ink-gray-5"
			>
				{{ __('Answer not available: the AI service failed on this question.') }}
			</div>
			<div v-else class="whitespace-pre-wrap text-sm text-ink-gray-9">
				{{ message.content }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { dayjs } from 'frappe-ui'

defineProps<{ messages: any[] }>()
</script>
```

Import it in the page: `import TranscriptReadOnly from '@/oslms/components/ai/TranscriptReadOnly.vue'`.

- [ ] **Step 4: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 5: Manual check — this is the one that matters**

Log in as a **Website User with the Gestore role** (not a System User): the page shows the Student picker, picking a learner lists their conversations, opening one shows the transcript with **no composer and no Rename/Archive buttons**. Then log in as a **plain Moderator**: no picker, and hitting `/courses/<c>/tutor` shows only their own (empty) list.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/oslms/pages/Courses/CourseTutorArchive.vue frontend/src/oslms/components/ai/TranscriptReadOnly.vue
git commit -m "feat(tutor): let a Gestore read a learner's conversations read-only"
```

---

### Task 13: The settings toggle

**Files:**
- Modify: `frontend/src/oslms/utils/settings.js:155-170` (the `Rag Tutor` section)
- Modify: `lms/translations/it.csv` and `lms/locale/it.po`

**Interfaces:**
- Consumes: the `tutor_history_enabled` field (Task 5).
- Produces: nothing downstream.

- [ ] **Step 1: Add the field to the settings panel**

In `frontend/src/oslms/utils/settings.js`, inside the `Rag Tutor` section, after the `fields` array that holds `enabled`, add a sibling column entry:

```js
								{
									fields: [
										{
											label: __('Chat History'),
											name: 'tutor_history_enabled',
											type: 'checkbox',
											description: __(
												'Store every tutor exchange so learners can re-read and resume their conversations.',
											),
										},
									],
								},
```

- [ ] **Step 2: Add the Italian labels**

Append to `lms/translations/it.csv`:

```csv
AI Tutor,Tutor AI
AI Tutor conversations,Conversazioni del Tutor AI
All your conversations with the tutor for this course.,Tutte le tue conversazioni con il tutor per questo corso.
New conversation,Nuova conversazione
Untitled conversation,Conversazione senza titolo
Archive conversation,Archivia conversazione
All conversations,Tutte le conversazioni
Conversation archived,Conversazione archiviata
Conversation restored,Conversazione ripristinata
Could not load the conversation,Impossibile caricare la conversazione
Could not archive the conversation,Impossibile archiviare la conversazione
No conversations yet. Ask the tutor a question to start one.,Nessuna conversazione. Fai una domanda al tutor per iniziarne una.
Pick a conversation to read it.,Scegli una conversazione per leggerla.
Show archived,Mostra archiviate
messages,messaggi
archived,archiviata
Generated on,Generata il
Answer not available: the AI service failed on this question.,Risposta non disponibile: il servizio AI non ha risposto a questa domanda.
New title,Nuovo titolo
My conversations,Le mie conversazioni
Chat History,Storico delle chat
Store every tutor exchange so learners can re-read and resume their conversations.,Salva ogni scambio con il tutor così gli studenti possono rileggere e riprendere le loro conversazioni.
```

Then check `lms/locale/it.po` for each of these msgids: if one exists with a **non-empty** `msgstr`, the PO wins over the CSV — update the PO entry instead of relying on the CSV.

- [ ] **Step 3: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 4: Manual check**

Settings → AI → Rag Tutor shows the "Storico delle chat" checkbox; toggling it off makes the course-page entry button disappear and stops new conversations from being created.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/utils/settings.js lms/translations/it.csv lms/locale/it.po
git commit -m "feat(tutor): expose the chat-history switch in the AI settings"
```

---

### Task 14: Documentation

**Files:**
- Modify: `docs/ai/TUTOR.md`

**Interfaces:** none.

- [ ] **Step 1: Rewrite the persistence sections**

In `docs/ai/TUTOR.md`:

1. Replace the sentence in **Architettura** that reads *"Niente sessione persistita lato server: la cronologia è interamente owned dal client e rinviata ad ogni domanda"* with: *"La cronologia è persistita lato server in `LMSA Tutor Conversation` / `LMSA Tutor Message` quando `LMSA Settings.tutor_history_enabled` è attivo; in quel caso il client manda solo l'identificativo della conversazione e il server ricostruisce gli ultimi `HISTORY_WINDOW_TURNS` turni. A interruttore spento vale il comportamento legacy: la cronologia è owned dal client."*
2. In **Cronologia conversazionale**, replace the "Niente persistenza lato server" bullet with the window rule and the fact that a client-sent `history` is ignored when `conversation` is set.
3. Add a new section **Archivio delle conversazioni** documenting the two doctypes, the permission rule (owner + `{System Manager, Gestore}`, read-only for managers, no Moderator branch), the four endpoints of `history.py`, and the `Failed` status.
4. Fix two statements that the code no longer matches and that sit next to what you just rewrote: `_system_prompt` returns **only** the prompt (not a `(prompt, context)` pair), and the audit `context` field stores the **whole system prompt** (~6 KB on production data), not just the chunks; the method `_course_description` no longer exists — course context is built by `format_course_context`.
5. Add `history.py` and the two doctypes to the **File rilevanti** table.

- [ ] **Step 2: Commit**

```bash
git add docs/ai/TUTOR.md
git commit -m "docs(tutor): document the conversation archive"
```

---

## Collaudo finale (a carico del committente)

Run through this list on the dev site with `Chat History` on, before calling the feature done.

- [ ] **Learner, desktop.** Ask three questions on a course; reload; reopen the panel; the conversation is still there. Start a new conversation; both appear on `/courses/<c>/tutor`.
- [ ] **Learner, phone.** The same page: the list and the transcript alternate, the Back button works, the floating panel does not cover the bottom CTA.
- [ ] **Failed turn.** Temporarily clear the provider key in `LMSA Settings`, ask a question, put the key back: the archive shows the notice, not an empty bubble.
- [ ] **Isolation.** With a second learner account, confirm their archive shows only their own conversations, and that `/api/method/frappe.client.get_list?doctype=LMSA%20Tutor%20Conversation` returns only their own rows.
- [ ] **Gestore (Website User).** The Student picker appears, a learner's conversations open read-only, no composer, no Rename/Archive.
- [ ] **Plain Moderator.** No picker, no access to another learner's conversations — **verify this from the interface, not only from the test suite**.
- [ ] **Audit log.** As a learner, `/api/method/frappe.client.get_list?doctype=LMSA%20Query%20Log` returns a permission error.
- [ ] **Switch off.** With `Chat History` off, the tutor still answers, the entry button disappears, and no new conversation rows are created.

---

## Stima

Lo sviluppo è interamente a carico dell'assistente AI (Claude Code, Opus 5), sotto
supervisione del committente. La stima operativa è quindi in **giornate di calendario**
e in **ore di impegno diretto del committente**, non in ore-uomo di sviluppo.

| Fase | Task | Sviluppo (elapsed) | Revisione committente | Collaudo committente |
| --- | --- | ---: | ---: | ---: |
| 1 — Dati, permessi, persistenza | 1–6 | 1–1,5 gg | 1,5–2 h | 0,5 h |
| 2 — Archivio e interfaccia studente | 7–11 | 1,5–2 gg | 3–4 h | 1,5–2 h |
| 3 — Gestore, impostazioni, documentazione | 12–14 | 0,5–1 gg | 1 h | 3–4 h |
| Giri di correzione dal collaudo | — | 0,5–1 gg | 0,5 h | 1 h |
| **Totale** | | **4–5,5 giornate** | **6–7,5 h** | **6–7,5 h** |

**In sintesi: 4–6 giornate di calendario, con 12–15 ore di impegno diretto del
committente** (circa una giornata e mezza-due, distribuite).

*Riferimento per il preventivo al cliente:* le stesse funzioni realizzate da uno
sviluppatore umano valgono **87–105 ore → 12–14 giornate** (scomposizione per voce nella
specifica, §11). È quello il valore da usare in offerta; la tabella sopra è il costo di
esecuzione interno.

**Base empirica della stima**, non impressione: il 17 settembre 2026 questo repository ha
assorbito in una giornata 10 commit contenenti l'analisi completa della modifica di una
lezione dal vivo, la sua implementazione (512 righe su 8 file), la riscrittura di un
template email e tre giri di correzione emersi dal collaudo — circa 780 righe. Questo
piano vale all'incirca 2.300–2.800 righe fra backend, due doctype, test e frontend, con
in più due voci che quella giornata non aveva: doctype nuovi da migrare nel container e
una matrice di permessi da verificare a mano.

**Cosa non si comprime** e va messo a bilancio così com'è: il collaudo del committente
(6–7,5 h, irriducibili), l'iterazione visiva della pagina del progetto (due o tre giri
con i suoi occhi), l'attrito dell'ambiente Docker (`bench migrate` su doctype nuovi: su
questo progetto la meta stale è un problema ricorrente — mezza giornata di margine), e le
decisioni di prodotto che emergeranno strada facendo.

**Due verifiche che il committente deve fare di persona**, perché l'esito della suite di
test non basta:

1. **Il caso Moderator** (collaudo finale, punto 6). La regola D1 è controintuitiva — si
   concede a `Gestore` e si nega a `Moderator`, che i Gestori possiedono comunque — ed è
   il tipo di logica in cui un errore resta invisibile finché qualcuno non guarda.
2. **Il turno fallito.** Il 15% delle risposte in produzione fallisce: la sua resa
   nell'archivio è una scelta di design che va vista, non descritta.
