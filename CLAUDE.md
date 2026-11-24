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

## Customization tracking

Every change to upstream code or to our own code is attributed to a feature card. A commit guard (`scripts/commit_guard.py`, run by `.githooks/commit-msg`) enforces it; it is enabled with `git config core.hooksPath .githooks` (a configuration change: ask the user for OK before running it, never run it on your own) and needs python3 >= 3.11 on git's PATH. The card schema is in `docs/customizations/features/README.md`.

- Put `Oslms-Feature: <id>` in the LAST paragraph of the message, directly above `Co-Authored-By:`. It counts only in the final trailer block, so `Version: X.Y.Z` stays in its own paragraph above it:

  ```
  feat(live-class): save every live class as a draft

  <body>

  Version: 1.16.80

  Oslms-Feature: live-class-draft-publish
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```

- It is required when the commit touches upstream files or our code (`apps/os_lms/`, `frontend/src/oslms/`, `frontend/src/overrides/`, `frontend/oslms-vite/`, files absent from the upstream base). It is not required for `docs/`, `reports/`, `scripts/`, `.claude/`, `.githooks/`, `.github/`, translations (`lms/locale/`, `lms/translations/`), lock or generated files, `CLAUDE.md`/`AGENTS.md`, `graphify-out/`, `.agents/`, `.vscode/`, `frontend/oslms-test/`, `osv-scanner.toml`, `skills-lock.json`, or a commit whose only upstream change is the `versionApp` line.
- A `feat` commit must stage its card `docs/customizations/features/<id>.toml`: create it, or update it.
- When the behaviour changes, update the card's `behaviour` and add an entry to `history`.
- `Oslms-Feature: none (<reason>)` is only for changes with no behavioural effect, never for `feat` or `fix`.
- Never use `--no-verify`. If the guard blocks, fix the message or the card as it says.
- Known limitation: `git commit --amend` that adds code to a `feat` commit is refused because the card is no longer in the staged diff. Restage the card file in the amend, or make a new commit.
- A Stop hook (`scripts/inventory_guard.py`) reminds you once per session to catalogue any `OSLMS-CUSTOM` marker and, once the catalogue migration is done (`docs/customizations/features/.strict` exists), that the guard is off when `core.hooksPath` is not `.githooks`: then ASK THE USER for OK before running `git config core.hooksPath .githooks`.
- When a commit stages `lms/locale/it.po` without `docs/customizations/translations-it.toml`, run `python3 scripts/customization_translations.py --write` and stage the registry (the guard reminds you, without blocking).
- `git cherry-pick --continue` after a conflict runs the guard: when porting an old commit, add the `Oslms-Feature` trailer to its message.
- GUI git clients (IDE, desktop apps) need python3 >= 3.11 first on their PATH, or their commits are refused.
