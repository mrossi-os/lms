#!/bin/bash
set -e

# SITE SETTINGS
bench_dir="/home/frappe/bench-data/frappe-bench"
bench_owner="frappe:frappe"
bench_cmd="cd ${bench_dir} && bench"
bench_env_file="${bench_dir}/.env"
site_name="lms.localhost"



# ==================================================================
# ===================== INIT DOCKER ENVIROMENT =====================
echo "---------------------------------------------------------------"
echo "---------------------------- START ----------------------------"

if [ ! -d "$bench_dir" ]; then
  mkdir -p $bench_dir
  echo " --- Cartella creata: $bench_dir"
else
  echo " --- Cartella già esistente: $bench_dir"
fi

chown -R "${bench_owner}" /home/frappe/bench-data


if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo " --- ADD OPENAI KEY"
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > "${bench_env_file}"
    chown "${bench_owner}" "${bench_env_file}"
fi

# ==================================================================
# ================== INSTALL FRAPPE    =============================
if [ -d "${bench_dir}/apps/frappe" ]; then
    echo " --- Bench already exists, reusing it"
else
    echo " --- Creating new Bench"

    export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"
    if ! command -v yarn >/dev/null 2>&1; then
        echo " ----- Install yarn"
        if command -v corepack >/dev/null 2>&1; then
            corepack enable
        else
            npm install -g yarn
        fi
    fi  

    if [ -d "${bench_dir}" ] && [ ! -f "${bench_dir}/Procfile" ]; then
        echo " ----- Empty bench directory detected. Cleaning up."
        rm -rf "${bench_dir}"
    fi
    su -s /bin/bash frappe -c "bench init --skip-redis-config-generation --frappe-branch version-16 ${bench_dir}"
fi

# ==================================================================
# ================== CONFIGURE FRAPPE    ===========================

echo " --- Set cointainer enviroment varible for frappe"
su -s /bin/bash frappe -c "${bench_cmd} set-mariadb-host mariadb"
su -s /bin/bash frappe -c "${bench_cmd} set-redis-cache-host redis://redis:6379"
su -s /bin/bash frappe -c "${bench_cmd} set-redis-queue-host redis://redis:6379"
su -s /bin/bash frappe -c "${bench_cmd} set-redis-socketio-host redis://redis:6379"

# Remove redis, watch from Procfile
if [ -f "${bench_dir}/Procfile" ]; then
    echo " --- Remove redis watch files"
    sed -i '/redis/d' "${bench_dir}/Procfile"
    sed -i '/watch/d' "${bench_dir}/Procfile"
fi

su -s /bin/bash frappe -c "git config --global --add safe.directory /workspace"
su -s /bin/bash frappe -c "git config --global --add safe.directory /workspace/.git"



# ==================================================================
# ================== INSTALL APPS   ================================

# Installa payments da GitHub se non presente
if [ ! -d "${bench_dir}/apps/payments" ]; then
    echo " --- Installing payments app from GitHub"
    su -s /bin/bash frappe -c "cd ${bench_dir} && bench get-app payments"
fi

# - App definition: <name app>:<workspace path definition>
APPS=(
    "lms:/workspace"
    "os_lms:/workspace/apps/os_lms"
)
echo " --- Install apps on frappe if not exist "
for app_def in "${APPS[@]}"; do
    app_name="${app_def%%:*}"
    app_path="${app_def#*:}"

    # Create symlink directly (avoids bench get-app which breaks on local paths)
    if [ ! -L "${bench_dir}/apps/${app_name}" ]; then
        echo " --- Symlinking ${app_name} -> ${app_path}"
        [ -d "${bench_dir}/apps/${app_name}" ] && rm -rf "${bench_dir}/apps/${app_name}"
        ln -s "${app_path}" "${bench_dir}/apps/${app_name}"
        chown -h frappe:frappe "${bench_dir}/apps/${app_name}"
    fi

    # Install Python package if not already installed
    if ! su -s /bin/bash frappe -c "cd ${bench_dir} && env/bin/pip show ${app_name}" >/dev/null 2>&1; then
        echo " --- pip install -e ${app_name}"
        su -s /bin/bash frappe -c "cd ${bench_dir} && env/bin/pip install -e apps/${app_name}"
    fi

    # Register app in apps.txt (required by bench install-app)
    if ! grep -qx "${app_name}" "${bench_dir}/sites/apps.txt" 2>/dev/null; then
        echo " --- Registering ${app_name} in apps.txt"
        printf '\n%s\n' "${app_name}" >> "${bench_dir}/sites/apps.txt"
    fi
done

# =========================================================================
# ================== CONFIGURE SITE CONFIG + APPS =========================
if ! su -s /bin/bash frappe -c "${bench_cmd} --site ${site_name} list-apps" >/dev/null 2>&1; then
    echo " --- Create  site ${site_name} with correct database authentication"
    su -s /bin/bash frappe -c "${bench_cmd} new-site ${site_name} \
        --force \
        --mariadb-root-password ${MYSQL_PASSWORD} \
        --admin-password admin \
        --no-mariadb-socket"
fi

echo " --- Install apps on frappe site "
for app_def in "${APPS[@]}"; do
    app_name="${app_def%%:*}"
    if ! su -s /bin/bash frappe -c "${bench_cmd} --site ${site_name} list-apps" 2>/dev/null | grep -qx "${app_name}"; then
        su -s /bin/bash frappe -c "${bench_cmd} --site ${site_name} install-app ${app_name}"
    fi
done

su -s /bin/bash frappe -c "${bench_cmd} --site ${site_name} set-config developer_mode 1"
su -s /bin/bash frappe -c "${bench_cmd} --site ${site_name} clear-cache"
su -s /bin/bash frappe -c "${bench_cmd} use ${site_name}"

# remove comment if need migrate
su -s /bin/bash frappe -c "${bench_cmd} migrate"
su -s /bin/bash frappe -c "export DEBUG_MODE=${DEBUG_MODE} && export PYTHONUNBUFFERED=1 && ${bench_cmd} start"
#tail -f /dev/null