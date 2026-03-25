# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Frappe Learning (LMS) — an open-source Learning Management System built on the **Frappe Framework** (Python backend) with a **Vue 3** frontend. It manages courses, batches, quizzes, assignments, certifications, and live classes. Required dependency: `frappe/payments`.

## Development Environment (Docker)

```bash
cd docker
cp .env.example .env        # set MYSQL_PASSWORD, ADMIN_START_PASSWORD, optionally OPENAI_API_KEY
docker compose up -d
# Site: http://lms.localhost:8000/lms  (Administrator / <ADMIN_START_PASSWORD>)
```

### Docker Directory Structure

```
docker/
├── docker-compose.yml   # compose stack definition (project name: dev-elite)
├── Dockerfile           # extends frappe/bench:latest, pins setuptools<82
└── init.sh              # entrypoint: installs Frappe, apps, creates site, runs bench start
```

### Services (`docker-compose.yml`)

| Service   | Image                              | Ports                        | Notes                                                    |
|-----------|------------------------------------|------------------------------|----------------------------------------------------------|
| **frappe** | `elite-frappe-dev` (built locally) | `8000` (Frappe), `9000` (API), `5678` (debugpy) | Mounts repo as `/workspace`, bench data in named volume |
| **mariadb** | `mariadb:10.8`                   | `3306`                       | UTF-8 mb4, data persisted in `dev-elite-db-data` volume  |
| **redis**  | `redis/redis-stack-server:latest` | —                            | Used for cache, queue, and socket.io                     |
| **mailer** | `axllent/mailpit:latest`          | `1025` (SMTP), `8025` (Web UI) | Auth: `user:password`, max message 10 MB              |

### Environment Variables (`.env`)

| Variable             | Required | Description                                      |
|----------------------|----------|--------------------------------------------------|
| `MYSQL_PASSWORD`     | yes      | MariaDB root password                            |
| `ADMIN_START_PASSWORD` | yes    | Frappe site admin password                       |
| `OPENAI_API_KEY`     | no       | Written to bench `.env` for AI features (os_lms) |
| `DEBUG_MODE`         | no       | `1` to enable debug mode (default `0`)           |
| `BUILD_FRONTEND`     | no       | `1` to build frontend on start (default `1`)     |
| `FRAPPE_PORT`        | no       | Host port for Frappe (default `8000`)            |
| `API_API_PORT`       | no       | Host port for API (default `9000`)               |
| `DOCKER_PLATFORM`    | no       | Container platform (default `linux/amd64`)       |

### Init Script (`init.sh`)

The entrypoint script runs on every container start and handles:

1. **First run**: initializes Frappe bench (`bench init`, version-16 branch), installs yarn/corepack
2. **Redis/MariaDB config**: points bench at the `mariadb` and `redis` service hostnames
3. **App installation**: symlinks `lms` (from `/workspace`) and `os_lms` (from `/workspace/apps/os_lms`) into the bench, pip-installs them, registers in `apps.txt`
4. **Site setup**: creates site `lms.localhost` if it doesn't exist, installs apps, enables `developer_mode`
5. **Every start**: runs `bench migrate` then `bench start`

The workspace (`/workspace`) is a bind mount of the repo root — code changes on the host are immediately visible inside the container.

### Volumes

- `dev-elite-db-data` — MariaDB data (persistent across restarts)
- `dev-elite-site-data` — Frappe bench directory (`/home/frappe/bench-data`), contains site files, node modules, Python venv

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

The app follows Frappe's doctype pattern — each entity is a directory containing a Python class, JSON schema, and optional test file. Doctypes are defined in two locations:
- `lms/lms/doctype/` — base LMS doctypes
- `apps/os_lms/os_lms/os_lms/doctype/` — custom/extended doctypes for this project

Key doctypes:

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

#### Component Override System (`osOverrideTheme` Vite plugin)

The `osOverrideTheme` Vite plugin (defined in `frontend/vite.config.js`) enables overriding Vue components from `node_modules` (e.g. `frappe-ui`) without forking the package. To override a component:

1. Identify the component's path relative to `node_modules/` (e.g. `frappe-ui/src/components/Button.vue`).
2. Create a file at the same relative path under `frontend/src/overrides/` (e.g. `frontend/src/overrides/frappe-ui/src/components/Button.vue`).
3. The plugin will automatically resolve imports to the override instead of the original.

The plugin runs with `enforce: 'pre'` and only intercepts relative `.vue` imports that resolve inside `node_modules/`.

### Custom Extension: `apps/os_lms`

A local extension app at `apps/os_lms/`. Source code is at `apps/os_lms/os_lms/os_lms/` (note the nested structure). Contains:
- `doctype/` — custom doctypes (e.g. `LMSA Settings` for AI config, `LMSA Material`, `LMSA Chunk`, `LMSA Query Log`)
- `ai/` — AI assistant implementation and RAG pipeline:
  - `ingestion.py` — document chunking and embedding (OpenAI embeddings)
  - `api.py` — AI assistant API endpoints
  - `scheduler.py` — scheduled AI tasks
- `overrides/` — Frappe doctype overrides

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


## Code Style

- All code comments must be written in English
- Variable names, function names, and identifiers in English
- Commit messages in English