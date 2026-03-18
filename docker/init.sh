#!/bin/bash
set -e

# SITE SETTINGS
bench_dir="/home/frappe/bench-data/frappe-bench"
bench_owner="frappe:frappe"
bench_cmd="cd ${bench_dir} && bench"
bench_env_file="${bench_dir}/.env"
site_name="lms.localhost"


echo "======================================================================"  
echo "============================== START ================================="

if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo " --- ADD OPENAI KEY"
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > "${bench_env_file}"
    chown "${bench_owner}" "${bench_env_file}"
fi

# ==================================================================
# ================== INSTALL FRAPPE    =============================
if [ -d "${bench_dir}/apps/frappe" ]; then
    echo " --- Frappe enviroment is installed"
else
    echo " --- Install frappe and required apps"

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
    bench init --skip-redis-config-generation --frappe-branch version-16 "${bench_dir}"
fi



cd "${bench_dir}"

# ================== CONFIGURE FRAPPE    ===========================
echo " --- Set cointainer enviroment varible for frappe"
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
if [ -f "${bench_dir}/Procfile" ]; then
    echo " --- Remove redis watch files"
    sed -i '/redis/d' "${bench_dir}/Procfile"
    sed -i '/watch/d' "${bench_dir}/Procfile"
fi

git config --global --add safe.directory /workspace
git config --global --add safe.directory /workspace/.git


# Ensure setuptools < 82 in bench virtualenv
if ! "${bench_dir}/env/bin/python3" -c "import setuptools" 2>/dev/null; then
    echo " --- Installing setuptools <82 in bench env"
    "${bench_dir}/env/bin/pip" install "setuptools<82"
fi


if [ ! -d "${bench_dir}/apps/payments" ]; then
    echo " --- Installing payments app from GitHub"
    bench get-app payments --branch=version-15
fi



# - App definition: <name app>:<workspace path definition>
APPS=(
    "lms:/workspace"
    "os_lms:/workspace/apps/os_lms"
)

for app_def in "${APPS[@]}"; do
    app_name="${app_def%%:*}"
    app_path="${app_def#*:}"

    # Create symlink directly (avoids bench get-app which breaks on local paths)
    if [ ! -L "${bench_dir}/apps/${app_name}" ]; then
        echo " --- Symlinking ${app_name} -> ${app_path}"
        [ -d "${bench_dir}/apps/${app_name}" ] && rm -rf "${bench_dir}/apps/${app_name}"
        ln -s "${app_path}" "${bench_dir}/apps/${app_name}"
    fi

    # Install Python package if not already installed
    if ! "${bench_dir}/env/bin/pip" show "${app_name}" >/dev/null 2>&1; then
        echo " --- pip install -e ${app_name}"
        "${bench_dir}/env/bin/pip" install -e "apps/${app_name}"
    fi

    # Register app in apps.txt (required by bench install-app)
    if ! grep -qx "${app_name}" "${bench_dir}/sites/apps.txt" 2>/dev/null; then
        echo " --- Registering ${app_name} in apps.txt"
        printf '\n%s\n' "${app_name}" >> "${bench_dir}/sites/apps.txt"
    fi
done


# ================== CONFIGURE SITE CONFIG + APPS =========================
if ! bench --site ${site_name} list-apps >/dev/null 2>&1; then
    echo " --- Create site ${site_name} with correct database authentication"
    bench new-site ${site_name} \
        --force \
        --mariadb-user-host-login-scope '%' \
        --mariadb-root-password ${MYSQL_PASSWORD} \
        --admin-password ${ADMIN_START_PASSWORD}
fi

for app_def in "${APPS[@]}"; do
    app_name="${app_def%%:*}"
    if ! bench --site ${site_name} list-apps 2>/dev/null | grep -q "${app_name}"; then
        echo "--- Install ${app_name} on ${site_name}"
        bench --site ${site_name} install-app ${app_name}
    fi
done

cd "$bench_dir"
bench --site "${site_name}" set-config developer_mode 1
bench --site "${site_name}" clear-cache
bench use "${site_name}"

bench migrate

export PYTHONUNBUFFERED=1
export DEBUG_MODE=${DEBUG_MODE}
bench start
