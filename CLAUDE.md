# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Frappe Learning (LMS) — an open-source Learning Management System built on the **Frappe Framework** (Python backend) with a **Vue 3** frontend. It manages courses, batches, quizzes, assignments, certifications, and live classes.

## Development Environment (Docker)

```bash
cd docker
cp .env.example .env        # set MYSQL_PASSWORD, ADMIN_START_PASSWORD, optionally OPENAI_API_KEY
docker compose up -d
# Site: http://lms.localhost:8000/lms  (Administrator / <ADMIN_START_PASSWORD>)
```

Environment variables: see `docker/README.md`.

### Container lifecycle

`docker/init.sh` runs on every container start and always ends with `bench migrate` then `bench start`. The workspace (`/workspace`) is a bind mount of the repo root — code changes on the host are immediately visible inside the container.

## Build & Dev Commands

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

### Commit Messages

Conventional Commits enforced by commitlint (`commitlint.config.js`, checked in CI).

## Architecture

API methods use `@frappe.whitelist()` decorator. The app requires `require_type_annotated_api_methods = True` (see hooks.py).

### Custom Extension: `apps/os_lms`

A local extension app at `apps/os_lms/`. Source code is at `apps/os_lms/os_lms/os_lms/` (note the nested structure); see `apps/os_lms/CLAUDE.md`.

## Code Style

- All code comments must be written in English
- Variable names, function names, and identifiers in English
- Commit messages in English