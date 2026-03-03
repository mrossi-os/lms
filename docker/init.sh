#!/bin/bash

set -e

bench_dir="/home/frappe/bench-data/frappe-bench"
bench_owner="frappe:frappe"
bench_cmd="cd ${bench_dir} && bench"
bench_env_file="${bench_dir}/.env"
site_name="lms.localhost"

chown -R "${bench_owner}" /home/frappe/bench-data

if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > "${bench_env_file}"
    chown "${bench_owner}" "${bench_env_file}"
fi

if [ -d "${bench_dir}/apps/frappe" ]; then
    echo "Bench already exists, reusing it"
else
    echo "Creating new bench..."

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

if ! command -v yarn >/dev/null 2>&1; then
    if command -v corepack >/dev/null 2>&1; then
        corepack enable
    else
        npm install -g yarn
    fi
fi

    if [ -d "${bench_dir}" ] && [ ! -f "${bench_dir}/Procfile" ]; then
        echo "Empty bench directory detected. Cleaning up."
        rm -rf "${bench_dir}"
    fi

    su - frappe -c "bench init --skip-redis-config-generation --frappe-branch version-15 ${bench_dir}"
fi

# Use containers instead of localhost
su - frappe -c "${bench_cmd} set-mariadb-host mariadb"
su - frappe -c "${bench_cmd} set-redis-cache-host redis://redis:6379"
su - frappe -c "${bench_cmd} set-redis-queue-host redis://redis:6379"
su - frappe -c "${bench_cmd} set-redis-socketio-host redis://redis:6379"

# Remove redis, watch from Procfile
if [ -f "${bench_dir}/Procfile" ]; then
    sed -i '/redis/d' "${bench_dir}/Procfile"
    sed -i '/watch/d' "${bench_dir}/Procfile"
fi

# Install lms from local workspace for development
if [ ! -d "${bench_dir}/apps/lms" ]; then
    su - frappe -c "${bench_cmd} get-app /workspace"
fi

if ! su - frappe -c "${bench_cmd} --site ${site_name} list-apps" >/dev/null 2>&1; then
    su - frappe -c "${bench_cmd} new-site ${site_name} \
        --force \
        --mariadb-root-password 123 \
        --admin-password admin \
        --no-mariadb-socket"
fi

if ! su - frappe -c "${bench_cmd} --site ${site_name} list-apps | grep -qx lms"; then
    su - frappe -c "${bench_cmd} --site ${site_name} install-app lms"
fi

su - frappe -c "${bench_cmd} --site ${site_name} set-config developer_mode 1"
su - frappe -c "${bench_cmd} --site ${site_name} clear-cache"
su - frappe -c "${bench_cmd} use ${site_name}"

su - frappe -c "${bench_cmd} start"
