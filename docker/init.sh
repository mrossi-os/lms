#!/bin/bash

bench_dir="/home/frappe/bench-data/frappe-bench"
bench_owner="frappe:frappe"
bench_cmd="cd ${bench_dir} && bench"
bench_env_file="${bench_dir}/.env"

chown -R "${bench_owner}" /home/frappe/bench-data

if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > "${bench_env_file}"
    chown "${bench_owner}" "${bench_env_file}"
fi

if [ -d "${bench_dir}/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    su - frappe -c "${bench_cmd} start"
    exit 0
fi

echo "Creating new bench..."

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

if [ -d "${bench_dir}" ] && [ ! -f "${bench_dir}/Procfile" ]; then
    echo "Empty bench directory detected. Cleaning up."
    rm -rf "${bench_dir}"
fi

su - frappe -c "bench init --skip-redis-config-generation --frappe-branch version-15 ${bench_dir}"

# Use containers instead of localhost
su - frappe -c "${bench_cmd} set-mariadb-host mariadb"
su - frappe -c "${bench_cmd} set-redis-cache-host redis://redis:6379"
su - frappe -c "${bench_cmd} set-redis-queue-host redis://redis:6379"
su - frappe -c "${bench_cmd} set-redis-socketio-host redis://redis:6379"

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

# Install lms from local workspace for development
su - frappe -c "${bench_cmd} get-app /workspace"

su - frappe -c "${bench_cmd} new-site lms.localhost \
    --force \
    --mariadb-root-password 123 \
    --admin-password admin \
    --no-mariadb-socket"

su - frappe -c "${bench_cmd} --site lms.localhost install-app lms"
su - frappe -c "${bench_cmd} --site lms.localhost set-config developer_mode 1"
su - frappe -c "${bench_cmd} --site lms.localhost clear-cache"
su - frappe -c "${bench_cmd} use lms.localhost"

su - frappe -c "${bench_cmd} start"
