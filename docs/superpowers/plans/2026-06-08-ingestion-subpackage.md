# Ingestion Subpackage Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all ingestion logic from `ai/api.py`, `ai/ingestion_service.py`, `ai/ingestion.py`, `ai/scheduler.py` into a new `ai/ingestion/` subpackage that mirrors the `simulations/` and `tutor/` pattern. Pure structural refactor — no behaviour change.

**Architecture:** Each AI feature becomes a self-contained subpackage with its own `api.py`, service, and scheduler. The chat helper `load_lesson` is extracted to a private sibling module (`ai/_lesson_access.py`) to avoid an upward sibling import from `ai/ingestion/api.py` back into `ai/api.py`. `ai/api.py` keeps `ask_lmsa_chat` and the OpenAPI aggregator.

**Tech Stack:** Python 3.10+, Frappe Framework, Vue 3 frontend (one URL update).

**Reference spec:** `docs/superpowers/specs/2026-06-08-ingestion-subpackage-design.md`

**Commit strategy:** The moves are tightly coupled — there is no useful intermediate state where some files are moved and others are not. The whole refactor lands in a single atomic commit at the end (Task 8). Earlier tasks make changes to the working tree but do not commit. If a task fails midway, `git restore` returns the tree to clean state.

---

## File structure after the refactor

```
apps/os_lms/os_lms/os_lms/ai/
├── __init__.py                # unchanged
├── _lesson_access.py          # NEW — load_lesson() helper
├── api.py                     # SHRUNK — only ask_lmsa_chat + get_lmsa_openapi_spec
├── ingestion/                 # NEW subpackage
│   ├── __init__.py            # re-exports IngestionService
│   ├── api.py                 # NEW — start_lesson_ingestion + get_lesson_ingestion_status
│   ├── service.py             # MOVED from ai/ingestion_service.py (renamed)
│   ├── pipeline.py            # MOVED from ai/ingestion.py (renamed)
│   └── scheduler.py           # MOVED from ai/scheduler.py
├── simulations/               # unchanged
├── tutor/                     # unchanged
└── utils/                     # unchanged

# DELETED after the moves:
#   apps/os_lms/os_lms/os_lms/ai/ingestion_service.py
#   apps/os_lms/os_lms/os_lms/ai/ingestion.py
#   apps/os_lms/os_lms/os_lms/ai/scheduler.py
```

---

### Task 1: Capture green baseline

**Files:** read-only.

- [ ] **Step 1: Confirm the working tree is clean except for the in-flight files**

Run:
```bash
git status --short
```
Expected output (one modified file from prior simulation work plus the spec, nothing else):
```
 M apps/os_lms/os_lms/os_lms/ai/simulations/eval/api.py
```
If any other files are dirty, stash them before proceeding. The refactor needs a clean slate to commit atomically.

- [ ] **Step 2: Run the existing test suite to capture the baseline**

Run:
```bash
docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms
```
Expected: all tests pass. Capture the count for the post-refactor comparison. If anything fails on baseline, **stop** — that failure is unrelated to this refactor and must be triaged separately before continuing.

- [ ] **Step 3: Record the four old paths that must disappear after the refactor**

These are the strings we will grep for at the end:
- `os_lms.os_lms.ai.ingestion_service`
- `os_lms.os_lms.ai.scheduler` (note: distinct from the new `ai.ingestion.scheduler`)
- `os_lms.os_lms.ai.api.start_lesson_ingestion`
- `os_lms.os_lms.ai.api.get_lesson_ingestion_status`

Plus the four pipeline symbols whose imports must move from `ai.ingestion` to `ai.ingestion.pipeline`: `material_hash`, `normalize_lesson_text`, `chunk_text`, `get_settings`.

---

### Task 2: Extract `load_lesson` into `_lesson_access.py`

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/_lesson_access.py`

- [ ] **Step 1: Create the new module**

Write `apps/os_lms/os_lms/os_lms/ai/_lesson_access.py` with this exact content:

```python
"""Shared permission helper for AI endpoints.

Lives at the `ai/` package level so both `ai/api.py` (chat) and
`ai/ingestion/api.py` (ingestion) can import it without creating a
sibling-up import cycle between the two endpoint modules.
"""

import frappe
from frappe import _

from lms.lms.utils import has_course_instructor_role, has_moderator_role, is_instructor


def load_lesson(lesson_id):
	lesson = frappe.get_doc("Course Lesson", lesson_id)
	if not lesson:
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	if has_moderator_role():
		return lesson

	if has_course_instructor_role() and is_instructor(lesson.course):
		return lesson

	if frappe.db.exists("LMS Enrollment", {"member": frappe.session.user, "course": lesson.course}):
		return lesson

	frappe.throw(_("You don't have permission to access this lesson"), frappe.PermissionError)
```

The function body is copied verbatim from `ai/api.py:11-24`. Indentation matches the existing codebase (tabs — see `pyproject.toml` ruff config `indent-style = "tab"`).

- [ ] **Step 2: Sanity-check the file imports cleanly**

Run:
```bash
docker compose -f docker/docker-compose.yml exec frappe python -c "from os_lms.os_lms.ai._lesson_access import load_lesson; print(load_lesson)"
```
Expected: prints `<function load_lesson at 0x...>`. No `ImportError`.

---

### Task 3: Create the `ingestion/` subpackage skeleton and move three files

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/ingestion/__init__.py`
- Rename: `apps/os_lms/os_lms/os_lms/ai/ingestion_service.py` → `apps/os_lms/os_lms/os_lms/ai/ingestion/service.py`
- Rename: `apps/os_lms/os_lms/os_lms/ai/ingestion.py` → `apps/os_lms/os_lms/os_lms/ai/ingestion/pipeline.py`
- Rename: `apps/os_lms/os_lms/os_lms/ai/scheduler.py` → `apps/os_lms/os_lms/os_lms/ai/ingestion/scheduler.py`

- [ ] **Step 1: Create the package directory and `__init__.py`**

Write `apps/os_lms/os_lms/os_lms/ai/ingestion/__init__.py` with:

```python
"""Ingestion subpackage: lesson content → RAG vector store.

Re-exports the public service class so external callers can do
`from os_lms.os_lms.ai.ingestion import IngestionService` without
reaching into the internal module layout.
"""

from .service import IngestionService

__all__ = ["IngestionService"]
```

- [ ] **Step 2: Move + rename the three source files with git**

Use `git mv` so the rename is preserved in history (better diffs, blame survives):
```bash
git mv apps/os_lms/os_lms/os_lms/ai/ingestion_service.py apps/os_lms/os_lms/os_lms/ai/ingestion/service.py
git mv apps/os_lms/os_lms/os_lms/ai/ingestion.py        apps/os_lms/os_lms/os_lms/ai/ingestion/pipeline.py
git mv apps/os_lms/os_lms/os_lms/ai/scheduler.py        apps/os_lms/os_lms/os_lms/ai/ingestion/scheduler.py
```

- [ ] **Step 3: Verify the layout**

Run:
```bash
ls apps/os_lms/os_lms/os_lms/ai/ingestion/
```
Expected exactly:
```
__init__.py  pipeline.py  scheduler.py  service.py
```
And:
```bash
ls apps/os_lms/os_lms/os_lms/ai/ | grep -E '^(ingestion_service|ingestion|scheduler)\.py$' || echo "OK: old files gone"
```
Expected: `OK: old files gone`.

---

### Task 4: Fix internal imports inside `ingestion/`

After the moves the relative imports inside `service.py`, `pipeline.py`, and `scheduler.py` reference old siblings that no longer exist.

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/ingestion/pipeline.py` (lines 11-12)
- Modify: `apps/os_lms/os_lms/os_lms/ai/ingestion/scheduler.py` (line 3)
- Modify: `apps/os_lms/os_lms/os_lms/ai/ingestion/service.py` (imports use absolute paths already — verify only)

- [ ] **Step 1: Fix `pipeline.py` relative imports**

The file was `ai/ingestion.py` and used `from .utils.lesson_parser` / `from .utils.rag_db`. After moving to `ai/ingestion/pipeline.py`, `utils` is one directory up. Change:

```python
from .utils.lesson_parser import LessonContentParser
from .utils.rag_db import RagDB
```
to:
```python
from ..utils.lesson_parser import LessonContentParser
from ..utils.rag_db import RagDB
```

Use Edit on `apps/os_lms/os_lms/os_lms/ai/ingestion/pipeline.py`:
- `old_string`: `from .utils.lesson_parser import LessonContentParser\nfrom .utils.rag_db import RagDB`
- `new_string`: `from ..utils.lesson_parser import LessonContentParser\nfrom ..utils.rag_db import RagDB`

- [ ] **Step 2: Fix `scheduler.py` relative import**

The file was `ai/scheduler.py` with `from .ingestion_service import IngestionService`. After move, `IngestionService` lives in the same package (`ingestion/`), and the file we want is the sibling `service.py`. Edit `apps/os_lms/os_lms/os_lms/ai/ingestion/scheduler.py`:
- `old_string`: `from .ingestion_service import IngestionService`
- `new_string`: `from .service import IngestionService`

- [ ] **Step 3: Verify `service.py` needs no changes**

`service.py` was `ai/ingestion_service.py` and used **absolute** imports (`from os_lms.os_lms.ai.utils...`), so the move doesn't break those. Verify:
```bash
grep -n "^from \." apps/os_lms/os_lms/os_lms/ai/ingestion/service.py
```
Expected: no output (no relative imports to fix).

- [ ] **Step 4: Import-smoke the whole subpackage**

```bash
docker compose -f docker/docker-compose.yml exec frappe python -c "
from os_lms.os_lms.ai.ingestion import IngestionService
from os_lms.os_lms.ai.ingestion.pipeline import material_hash, normalize_lesson_text, chunk_text, get_settings
from os_lms.os_lms.ai.ingestion.scheduler import reindex_lesson_content
print('OK', IngestionService, material_hash, reindex_lesson_content)
"
```
Expected: `OK <class ...IngestionService> <function material_hash at ...> <function reindex_lesson_content at ...>`. Any `ImportError` means a relative path is still wrong — fix before moving on.

---

### Task 5: Create `ai/ingestion/api.py` with the two endpoints

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/ingestion/api.py`

This file owns `start_lesson_ingestion` and `get_lesson_ingestion_status`. Both currently live in `ai/api.py` and are moved verbatim except for their imports.

- [ ] **Step 1: Write the new endpoints module**

Write `apps/os_lms/os_lms/os_lms/ai/ingestion/api.py` with this exact content:

```python
import frappe
from frappe import _

from .._lesson_access import load_lesson
from .service import IngestionService


@frappe.whitelist()
def start_lesson_ingestion(lesson_id):
	"""
	Start ingestion for a lesson. Teacher-only endpoint.

	Args:
	        lesson_id: The Course Lesson name/ID

	Returns:
	        dict with status, message, material name and chunk_count
	"""
	lesson = load_lesson(lesson_id)
	service = IngestionService()
	service.ingest_lesson(lesson)
	return {"success": True}


@frappe.whitelist()
def get_lesson_ingestion_status(lesson_id):
	"""
	Get ingestion status for a lesson.

	Args:
	        lesson_id: The Course Lesson name/ID

	Returns:
	        dict with status, chunk_count, last_ingested_on, and needs_update flag
	"""
	if not frappe.db.exists("Course Lesson", lesson_id):
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)

	material = frappe.db.get_value(
		"LMSA Material",
		{"lesson": lesson_id},
		["name", "status", "chunk_count", "last_ingested_on", "source_hash"],
		as_dict=True,
	)

	if not material:
		return {
			"status": "not_ingested",
			"chunk_count": 0,
			"last_ingested_on": None,
			"needs_update": True,
		}

	from .pipeline import material_hash, normalize_lesson_text

	current_text = normalize_lesson_text(lesson_id)
	current_hash = material_hash(current_text) if current_text else ""
	needs_update = material.source_hash != current_hash
	if material.status and material.status.lower() == "failed":
		needs_update = True

	return {
		"status": material.status.lower(),
		"chunk_count": material.chunk_count or 0,
		"last_ingested_on": (str(material.last_ingested_on) if material.last_ingested_on else None),
		"needs_update": needs_update,
		"material": material.name,
	}
```

Notes:
- Bodies are copied byte-for-byte from `ai/api.py:27-87` (the two functions plus `load_lesson` use). The lazy `from .pipeline import …` inside `get_lesson_ingestion_status` is kept after the early-return for un-ingested lessons — same shape as the original `from .ingestion import …`, just pointed at the renamed module. Preserving the lazy form keeps the cold path (status check for a never-ingested lesson) from paying the cost of importing the heavy pipeline module.

- [ ] **Step 2: Verify the endpoints load**

```bash
docker compose -f docker/docker-compose.yml exec frappe python -c "
from os_lms.os_lms.ai.ingestion.api import start_lesson_ingestion, get_lesson_ingestion_status
print('OK', start_lesson_ingestion, get_lesson_ingestion_status)
"
```
Expected: `OK <function start_lesson_ingestion ...> <function get_lesson_ingestion_status ...>`.

---

### Task 6: Slim down `ai/api.py`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/api.py` (full rewrite — easier than a series of edits given how much goes away)

After this task, `ai/api.py` only contains `ask_lmsa_chat` and `get_lmsa_openapi_spec`. The OpenAPI spec strings for the two ingestion endpoints are updated to the new URLs.

- [ ] **Step 1: Replace `ai/api.py` with the slim version**

Overwrite `apps/os_lms/os_lms/os_lms/ai/api.py` with this exact content:

```python
import frappe
from frappe import _

from ._lesson_access import load_lesson
from .ingestion import IngestionService


@frappe.whitelist()
def ask_lmsa_chat(lesson_id, question):
	"""
	Ask a question to the LMSA chatbot.

	Args:
	        course_id: The LMS Course name/ID
	        lesson_id: The Course Lesson name/ID
	        question: The user's question

	Returns:
	        dict with answer, sources, and status
	"""
	if not question or not question.strip():
		frappe.throw(_("Question cannot be empty"))

	lesson = load_lesson(lesson_id)
	service = IngestionService()
	result = service.ask(lesson, question)
	if not result:
		result = "I couldn't find relevant information in the lesson content to answer your question."
	return {"answer": result}


@frappe.whitelist(allow_guest=True)
def get_lmsa_openapi_spec():
	"""Return OpenAPI/Swagger spec for LMSA endpoints."""
	base_url = frappe.utils.get_url()
	return {
		"openapi": "3.0.0",
		"info": {
			"title": "LMSA API",
			"description": "API for LMS AI Assistant ingestion and chat endpoints",
			"version": "1.0.0",
		},
		"servers": [{"url": base_url}],
		"paths": {
			"/api/method/os_lms.os_lms.ai.ingestion.api.start_lesson_ingestion": {
				"post": {
					"summary": "Start lesson ingestion",
					"description": "Trigger ingestion for a specific lesson. Requires teacher permissions.",
					"requestBody": {
						"required": True,
						"content": {
							"application/x-www-form-urlencoded": {
								"schema": {
									"type": "object",
									"properties": {
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										}
									},
									"required": ["lesson_id"],
								}
							},
							"application/json": {
								"schema": {
									"type": "object",
									"properties": {
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										}
									},
									"required": ["lesson_id"],
								}
							},
						},
					},
					"responses": {
						"200": {
							"description": "Successful ingestion",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"status": {"type": "string"},
													"message": {"type": "string"},
													"material": {"type": "string"},
													"chunk_count": {"type": "integer"},
												},
											}
										},
									}
								}
							},
						},
						"403": {"description": "Permission denied"},
						"500": {"description": "Server error"},
					},
				}
			},
			"/api/method/os_lms.os_lms.ai.ingestion.api.get_lesson_ingestion_status": {
				"get": {
					"summary": "Get lesson ingestion status",
					"description": "Retrieve the current ingestion status for a lesson.",
					"parameters": [
						{
							"name": "lesson_id",
							"in": "query",
							"required": True,
							"schema": {"type": "string"},
							"description": "Course Lesson ID",
						}
					],
					"responses": {
						"200": {
							"description": "Status retrieved",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"status": {"type": "string"},
													"chunk_count": {"type": "integer"},
													"last_ingested_on": {
														"type": "string",
														"nullable": True,
													},
													"needs_update": {"type": "boolean"},
													"material": {"type": "string"},
												},
											}
										},
									}
								}
							},
						},
						"404": {"description": "Lesson not found"},
					},
				}
			},
			"/api/method/os_lms.os_lms.ai.api.ask_lmsa_chat": {
				"post": {
					"summary": "Ask LMSA chatbot",
					"description": "Ask a question about lesson content. Requires course enrollment.",
					"requestBody": {
						"required": True,
						"content": {
							"application/json": {
								"schema": {
									"type": "object",
									"properties": {
										"course_id": {
											"type": "string",
											"description": "LMS Course ID",
										},
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										},
										"question": {
											"type": "string",
											"description": "User question",
										},
									},
									"required": ["course_id", "lesson_id", "question"],
								}
							},
						},
					},
					"responses": {
						"200": {
							"description": "Chat response",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"answer": {"type": "string"},
													"sources": {
														"type": "array",
														"items": {
															"type": "object",
															"properties": {
																"lesson_id": {"type": "string"},
																"chunk_index": {"type": "integer"},
																"score": {"type": "number"},
																"excerpt": {"type": "string"},
															},
														},
													},
													"status": {
														"type": "string",
														"enum": [
															"answered",
															"not_found",
														],
													},
												},
											}
										},
									}
								}
							},
						},
						"403": {"description": "Access denied"},
						"500": {"description": "Server error"},
					},
				}
			},
		},
		"components": {
			"securitySchemes": {
				"cookieAuth": {"type": "apiKey", "in": "cookie", "name": "sid"},
				"tokenAuth": {
					"type": "apiKey",
					"in": "header",
					"name": "Authorization",
				},
			}
		},
		"security": [{"cookieAuth": []}, {"tokenAuth": []}],
	}
```

The only differences vs. the previous `ai/api.py`:
1. `load_lesson` is now imported from `._lesson_access` instead of defined inline.
2. `IngestionService` is imported from `.ingestion`.
3. The `start_lesson_ingestion` and `get_lesson_ingestion_status` endpoint functions are removed (they now live in `ai/ingestion/api.py`).
4. Inside the OpenAPI `paths` dict, the two ingestion path keys are rewritten to `…ai.ingestion.api.start_lesson_ingestion` and `…ai.ingestion.api.get_lesson_ingestion_status`.
5. The `ask_lmsa_chat` path key is unchanged.

- [ ] **Step 2: Smoke-check that `ai/api.py` still loads and exposes the expected callables**

```bash
docker compose -f docker/docker-compose.yml exec frappe python -c "
from os_lms.os_lms.ai.api import ask_lmsa_chat, get_lmsa_openapi_spec
import inspect
assert not hasattr(__import__('os_lms.os_lms.ai.api', fromlist=['*']), 'start_lesson_ingestion'), 'start_lesson_ingestion must no longer live in ai/api.py'
assert not hasattr(__import__('os_lms.os_lms.ai.api', fromlist=['*']), 'load_lesson'), 'load_lesson must move to _lesson_access'
print('OK')
"
```
Expected: `OK`. Any assertion failure means the slim file accidentally kept something it shouldn't.

---

### Task 7: Update external callers

**Files:**
- Modify: `apps/os_lms/os_lms/hooks.py` (line 157)
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py` (line 7)
- Modify: `frontend/src/oslms/composables/useLessonIngestion.js` (line 35)

- [ ] **Step 1: Update the scheduled task path in hooks.py**

Edit `apps/os_lms/os_lms/hooks.py`:
- `old_string`: `        "os_lms.os_lms.ai.scheduler.reindex_lesson_content",`
- `new_string`: `        "os_lms.os_lms.ai.ingestion.scheduler.reindex_lesson_content",`

- [ ] **Step 2: Update the `IngestionService` import in tutor_ai.py**

Edit `apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py`:
- `old_string`: `from os_lms.os_lms.ai.ingestion_service import IngestionService`
- `new_string`: `from os_lms.os_lms.ai.ingestion import IngestionService`

(Uses the re-export form from the `ingestion/__init__.py` we wrote in Task 3 — shorter and explicitly the public path.)

- [ ] **Step 3: Update the frontend endpoint URL**

Edit `frontend/src/oslms/composables/useLessonIngestion.js`:
- `old_string`: `		url: 'os_lms.os_lms.ai.api.start_lesson_ingestion',`
- `new_string`: `		url: 'os_lms.os_lms.ai.ingestion.api.start_lesson_ingestion',`

(The composable does not currently call `get_lesson_ingestion_status` directly — that endpoint is exposed in the OpenAPI spec for external/teacher use; if you grep and find an additional caller, update that line the same way.)

- [ ] **Step 4: Sanity-check no other source files reference the old paths**

Run from the repo root:
```bash
grep -rn \
  -e "os_lms\.os_lms\.ai\.ingestion_service" \
  -e "os_lms\.os_lms\.ai\.scheduler\." \
  -e "os_lms\.os_lms\.ai\.api\.start_lesson_ingestion" \
  -e "os_lms\.os_lms\.ai\.api\.get_lesson_ingestion_status" \
  --include="*.py" --include="*.js" --include="*.vue" --include="*.json" \
  apps frontend lms 2>/dev/null
```
Expected: no output. (Generated Vite bundles under `lms/public/frontend/assets/*.js` are excluded — they regenerate on `yarn build`. If any of those show up in the grep, that is fine and not a blocker.)

Also check that no `from os_lms.os_lms.ai.ingestion import X` is grabbing a pipeline symbol that should now come from `.pipeline`:
```bash
grep -rn "from os_lms\.os_lms\.ai\.ingestion import" --include="*.py" apps 2>/dev/null
```
Expected: only references to `IngestionService` (which the `__init__.py` re-exports). Anything else (e.g. `chunk_text`, `material_hash`) is a bug — update the import to `…ai.ingestion.pipeline`.

---

### Task 8: Verify and commit

**Files:** none modified in this task.

- [ ] **Step 1: Re-run the test suite**

```bash
docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms
```
Expected: same number of tests pass as in Task 1, Step 2. Any new failure is a regression — diagnose and fix before committing.

- [ ] **Step 2: Re-run the import smoke covering all relocated symbols**

```bash
docker compose -f docker/docker-compose.yml exec frappe python -c "
from os_lms.os_lms.ai import api as ai_api
from os_lms.os_lms.ai._lesson_access import load_lesson
from os_lms.os_lms.ai.ingestion import IngestionService
from os_lms.os_lms.ai.ingestion.api import start_lesson_ingestion, get_lesson_ingestion_status
from os_lms.os_lms.ai.ingestion.pipeline import material_hash, normalize_lesson_text, chunk_text, get_settings
from os_lms.os_lms.ai.ingestion.scheduler import reindex_lesson_content
from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi
assert ai_api.ask_lmsa_chat and ai_api.get_lmsa_openapi_spec
spec = ai_api.get_lmsa_openapi_spec()
assert '/api/method/os_lms.os_lms.ai.ingestion.api.start_lesson_ingestion' in spec['paths']
assert '/api/method/os_lms.os_lms.ai.ingestion.api.get_lesson_ingestion_status' in spec['paths']
assert '/api/method/os_lms.os_lms.ai.api.ask_lmsa_chat' in spec['paths']
assert '/api/method/os_lms.os_lms.ai.api.start_lesson_ingestion' not in spec['paths']
print('OK — every relocated symbol imports and OpenAPI spec paths match')
"
```
Expected: `OK — every relocated symbol imports and OpenAPI spec paths match`.

- [ ] **Step 3: Inspect the staged diff**

Run:
```bash
git status --short
git diff --stat
```
Expected: deletions of three files at `ai/` level (shown by `git mv` as renames with new paths), additions of `ai/_lesson_access.py`, `ai/ingestion/__init__.py`, `ai/ingestion/api.py`, modifications to `ai/api.py`, `hooks.py`, `tutor_ai.py`, `useLessonIngestion.js`. Nothing else. `simulations/eval/api.py` should still be the only unrelated dirty file (carry-over from before the refactor).

- [ ] **Step 4: Stage and commit**

The `simulations/eval/api.py` dirty file is **not** part of this refactor — do not stage it.

```bash
git add \
  apps/os_lms/os_lms/os_lms/ai/_lesson_access.py \
  apps/os_lms/os_lms/os_lms/ai/api.py \
  apps/os_lms/os_lms/os_lms/ai/ingestion \
  apps/os_lms/os_lms/os_lms/ai/tutor/tutor_ai.py \
  apps/os_lms/os_lms/hooks.py \
  frontend/src/oslms/composables/useLessonIngestion.js
git status --short
```
Verify the staged set looks right (the renamed files appear as `R` entries), then:
```bash
git commit -m "$(cat <<'EOF'
refactor(ai): extract ingestion logic into ai/ingestion/ subpackage

Mirrors the simulations/ and tutor/ subpackage pattern. Moves
IngestionService, the RAG pipeline primitives, the daily scheduler,
and the two ingestion endpoints under ai/ingestion/. Pulls the
shared load_lesson() permission helper into ai/_lesson_access.py so
chat and ingestion endpoints share it without a sibling-up import.

Pure structural refactor — no behaviour change. Updates the OpenAPI
spec path strings, the hooks.py scheduler path, the tutor_ai.py
import, and the SPA composable's endpoint URL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Manual smoke (optional but recommended)**

If the dev stack is running:
1. Open a Course Lesson in the SPA as an instructor.
2. Click "Index for AI" / "Re-index". The Network tab should show a POST to `…ai.ingestion.api.start_lesson_ingestion` returning `{"message": {"success": true}}`.
3. Refresh; the lesson's `index_status` indicator should reach `indexed`.
4. As an enrolled student, ask a question via the chatbot. The call hits `…ai.api.ask_lmsa_chat` (unchanged URL) and returns an answer.

A failure here means an endpoint URL is wrong somewhere we missed; grep again with the patterns from Task 7, Step 4.
