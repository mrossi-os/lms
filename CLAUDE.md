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

### Container lifecycle

`docker/init.sh` runs on every container start and always ends with `bench migrate` then `bench start`. The workspace (`/workspace`) is a bind mount of the repo root — code changes on the host are immediately visible inside the container.

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

### Commit Messages

Conventional Commits enforced by commitlint. Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `deprecate`, `revert`.

## Architecture

API methods use `@frappe.whitelist()` decorator. The app requires `require_type_annotated_api_methods = True` (see hooks.py).

### Component Override System (`osOverrideTheme` Vite plugin)

The `osOverrideTheme` Vite plugin (defined in `frontend/vite.config.js`) enables overriding Vue components from `node_modules` (e.g. `frappe-ui`) without forking the package. To override a component:

1. Identify the component's path relative to `node_modules/` (e.g. `frappe-ui/src/components/Button.vue`).
2. Create a file at the same relative path under `frontend/src/overrides/` (e.g. `frontend/src/overrides/frappe-ui/src/components/Button.vue`).
3. The plugin will automatically resolve imports to the override instead of the original.

The plugin runs with `enforce: 'pre'` and only intercepts relative `.vue` imports that resolve inside `node_modules/`.

### Custom Extension: `apps/os_lms`

A local extension app at `apps/os_lms/`. Source code is at `apps/os_lms/os_lms/os_lms/` (note the nested structure); see `apps/os_lms/CLAUDE.md`.

### Route Configuration

The LMS path is configurable via `site_config.lms_path` (defaults to `"lms"`). Route rules and redirects in `hooks.py` ensure old URLs (`/courses`, `/batches`) redirect to the SPA.

## Code Style

- All code comments must be written in English
- Variable names, function names, and identifiers in English
- Commit messages in English