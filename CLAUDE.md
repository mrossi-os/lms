# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Frappe Learning (LMS) — an open-source Learning Management System built on the **Frappe Framework** (Python backend) with a **Vue 3** frontend. It manages courses, batches, quizzes, assignments, certifications, and live classes. Required dependency: `frappe/payments`.

## Development Environment (Docker)

```bash
cd docker
cp .env.example .env        # set MYSQL_PASSWORD
docker compose up -d
# Site: http://lms.localhost:8000/lms  (Administrator / admin)
```

The Docker setup (`docker/docker-compose.yml`) runs MariaDB 10.8, Redis, Frappe bench, and Mailpit. Port 5678 is exposed for debugpy remote debugging.

## Build & Dev Commands

### Frontend (Vue 3 + Vite)

```bash
cd frontend
yarn install
yarn dev              # dev server with HMR, proxies to Frappe :8000
yarn build            # production build → lms/public/frontend/ + lms/www/_lms.html
```

### Backend Tests (via Frappe bench)

```bash
# All tests with coverage
bench --site <site> run-tests --app lms --coverage

# Single test module
bench --site <site> run-tests --app lms --doctest lms.lms.test_api

# Single test method
bench --site <site> run-tests --app lms --doctest lms.lms.test_api.TestLMSAPI.test_certified_participants_with_category
```

Test framework: `frappe.tests.UnitTestCase`. Test files live alongside source code (`lms/lms/test_*.py`, `lms/lms/doctype/*/test_*.py`).

### E2E Tests (Cypress)

```bash
yarn test-local                                    # interactive
bench --site <site> run-ui-tests lms --headless    # headless
```

Cypress config: `cypress.config.js`. Tests in `cypress/e2e/`.

### Linting

Pre-commit hooks handle all linting. Install and run manually:

```bash
pip install pre-commit
pre-commit run --all-files
```

**Python**: Ruff (line-length 110, tab indentation, double quotes, target py310). Config in `pyproject.toml`.
**JavaScript/Vue**: Prettier + ESLint. Config in `.eslintrc` and `.pre-commit-config.yaml`.

### Commit Messages

Conventional Commits enforced by commitlint. Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `deprecate`, `revert`.

## Architecture

### Backend (Frappe Doctypes)

The app follows Frappe's doctype pattern — each entity is a directory under `lms/lms/doctype/` containing a Python class, JSON schema, and optional test file. Key doctypes:

- **LMS Course / Course Chapter / Course Lesson** — 3-level content hierarchy
- **LMS Batch / LMS Batch Enrollment** — grouping learners with time-bound access
- **LMS Quiz / LMS Question / LMS Assignment** — assessment system
- **LMS Certificate / LMS Certificate Request / LMS Certificate Evaluation** — certification workflow with evaluator roles
- **LMS Live Class** — Zoom integration for scheduled sessions
- **LMS Payment** — Razorpay payment integration (`lms/lms/payments.py`)

**Key backend files:**
- `lms/lms/api.py` — REST API endpoints (whitelisted methods)
- `lms/lms/utils.py` — core business logic and utilities
- `lms/hooks.py` — app hooks, permissions, scheduled tasks, route rules
- `lms/install.py` — post-install setup (roles, permissions)

API methods use `@frappe.whitelist()` decorator. The app requires `require_type_annotated_api_methods = True` (see hooks.py).

### Frontend (Vue 3 SPA)

Located in `frontend/src/`. The SPA is served via Frappe's website route rules — all `/lms/*` routes map to `_lms.html`.

- **Pages** (`pages/`) — route-level components (Courses, Batches, Lesson, Profile, etc.)
- **Components** (`components/`) — reusable UI (quiz forms, assignment uploads, certificate display)
- **Stores** (`stores/`) — Pinia stores for user, session, settings, sidebar state
- **Router** (`router.js`) — Vue Router config mapping URL paths to page components
- **Socket** (`socket.js`) — Socket.IO client for real-time notifications

Built with **Frappe UI** component library and **Tailwind CSS**. Build config in `frontend/vite.config.js`.

### Custom Extension: `apps/os_lms`

A local extension app at `apps/os_lms/` with overrides. This is project-specific customization layered on top of the base LMS.

### Route Configuration

The LMS path is configurable via `site_config.lms_path` (defaults to `"lms"`). Route rules and redirects in `hooks.py` ensure old URLs (`/courses`, `/batches`) redirect to the SPA.

### Scheduled Tasks (hooks.py)

- **Hourly**: certificate evaluation scheduling, course statistics, live class attendance
- **Daily**: job opening updates, payment reminders, batch start reminders, course publish notifications

## CI Pipeline

- `ci.yml` — Python server tests (Python 3.14, MariaDB, Redis)
- `ui-tests.yml` — Cypress E2E tests (Node 24, Chrome)
- `linters.yml` — commitlint, Semgrep, pre-commit checks
- `build.yml` — Docker image builds
