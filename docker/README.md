# Docker Development Environment

## Quick Start

```bash
cd docker
cp .env.example .env        # set MYSQL_PASSWORD, ADMIN_START_PASSWORD, optionally OPENAI_API_KEY
docker compose up -d
# Site: http://lms.localhost:8000/lms  (Administrator / <ADMIN_START_PASSWORD>)
```

## Directory Structure

```
docker/
├── docker-compose.yml   # compose stack definition (project name: dev-elite)
├── Dockerfile           # extends frappe/bench:latest, pins setuptools<82
├── init.sh              # entrypoint: installs Frappe, apps, creates site, runs bench start
└── README.md
```

## Services (`docker-compose.yml`)

| Service    | Image                              | Ports                                            | Notes                                                    |
|------------|------------------------------------|--------------------------------------------------|----------------------------------------------------------|
| **frappe** | `elite-frappe-dev` (built locally) | `8000` (Frappe), `9000` (API), `5678` (debugpy)  | Mounts repo as `/workspace`, bench data in named volume  |
| **mariadb**| `mariadb:10.8`                     | `3306`                                           | UTF-8 mb4, data persisted in `dev-elite-db-data` volume  |
| **redis**  | `redis/redis-stack-server:latest`  | —                                                | Used for cache, queue, and socket.io                     |
| **mailer** | `axllent/mailpit:latest`           | `1025` (SMTP), `8025` (Web UI)                   | Auth: `user:password`, max message 10 MB                 |
| **phoenix**| `arizephoenix/phoenix:version-20.21.4` | `127.0.0.1:6006` (Web UI + OTLP `/v1/traces`) | Opt-in (`ai-eval` profile), see [Phoenix](#phoenix-ai-bias-tests) |

## Environment Variables (`.env`)

| Variable               | Required | Description                                      |
|------------------------|----------|--------------------------------------------------|
| `MYSQL_PASSWORD`       | yes      | MariaDB root password                            |
| `ADMIN_START_PASSWORD` | yes      | Frappe site admin password                       |
| `OPENAI_API_KEY`       | no       | Written to bench `.env` for AI features (os_lms) |
| `DEBUG_MODE`           | no       | `1` to enable debug mode (default `0`)           |
| `BUILD_FRONTEND`       | no       | `1` to build frontend on start (default `1`)     |
| `FRAPPE_PORT`          | no       | Host port for Frappe (default `8000`)            |
| `API_API_PORT`         | no       | Host port for API (default `9000`)               |
| `DOCKER_PLATFORM`      | no       | Container platform (default `linux/amd64`)       |
| `PHOENIX_SECRET`       | phoenix  | Signs Phoenix sessions (32+ chars, letters and digits) |
| `PHOENIX_ADMIN_SECRET` | phoenix  | Bearer token for scripts (32+ chars, different from `PHOENIX_SECRET`) |
| `PHOENIX_ADMIN_PASSWORD` | phoenix | Initial password of `admin@localhost` in the Phoenix UI |

## Init Script (`init.sh`)

The entrypoint script runs on every container start and handles:

1. **First run**: initializes Frappe bench (`bench init`, version-16 branch), installs yarn/corepack
2. **Redis/MariaDB config**: points bench at the `mariadb` and `redis` service hostnames
3. **App installation**: symlinks `lms` (from `/workspace`) and `os_lms` (from `/workspace/apps/os_lms`) into the bench, pip-installs them, registers in `apps.txt`
4. **Site setup**: creates site `lms.localhost` if it doesn't exist, installs apps, enables `developer_mode`
5. **Every start**: runs `bench migrate` then `bench start`

The workspace (`/workspace`) is a bind mount of the repo root — code changes on the host are immediately visible inside the container.

## Phoenix (AI bias tests)

[Arize Phoenix](https://arize.com/docs/phoenix) stores the LLM calls made by the AI bias tests (ESG point 5). It is not part of the default stack:

```bash
# generate the three PHOENIX_* values in .env first, e.g. with: openssl rand -hex 32
docker compose --profile ai-eval up -d phoenix
# UI: http://localhost:6006  (admin@localhost / <PHOENIX_ADMIN_PASSWORD>)
```

- Reachable only from this machine (`127.0.0.1`); the `frappe` container sends traces to `http://phoenix:6006/v1/traces`.
- Authentication is on and anonymous telemetry is off; traces older than 90 days are deleted.
- Use synthetic test data only: no real students' conversations.
- To let the test runners write there (`ai/utils/llm/tracing.py`), inside the `frappe` container:
  `env/bin/pip install -e "apps/os_lms[tracing]"`, then
  `bench --site lms.localhost set-config phoenix_collector_endpoint http://phoenix:6006/v1/traces`
  and `bench --site lms.localhost set-config phoenix_api_key <system API key from Phoenix Settings>`.
  Without these, tracing stays off and nothing changes.
- Server license is Elastic License 2.0: internal use only, never give clients access to the UI.

## Volumes

- `dev-elite-db-data` — MariaDB data (persistent across restarts)
- `dev-elite-site-data` — Frappe bench directory (`/home/frappe/bench-data`), contains site files, node modules, Python venv
- `dev-elite-phoenix-data` — Phoenix SQLite database (only with the `ai-eval` profile)

## Useful Commands

```bash
# View logs
docker compose logs -f frappe

# Enter the Frappe container
docker compose exec frappe bash

# Run bench commands inside the container
docker compose exec -u frappe frappe bash -c "cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost console"

# Rebuild the image after Dockerfile changes
docker compose build frappe

# Reset everything (destroys data)
docker compose down -v
```



## TADUZIONI 
comandi utili
```bash
# converte traduzioni da csv a .po
bench migrate-csv-to-po --app lms 
#ricompila tutti i po in mo
bench compile-po-to-mo  
# cancessla cache
bench clear-cache && bench restart
```