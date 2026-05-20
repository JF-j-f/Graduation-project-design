#!/usr/bin/env bash
set -euo pipefail

DATADIR="/var/lib/mysql"
SEED_DIR="/opt/musicweb/mysql-seed/mysql"
SOCKET_PATH="/tmp/musicweb-mysql-fast.sock"
PID_FILE="/tmp/musicweb-mysql-fast.pid"
SEED_ROOT_PASSWORD="${MUSICWEB_SEED_ROOT_PASSWORD:-musicweb-seed-root}"

require_value() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "${value}" ]; then
        echo "Missing required environment variable: ${name}" >&2
        exit 1
    fi
}

validate_identifier() {
    local name="$1"
    local value="$2"
    if ! printf '%s' "${value}" | grep -Eq '^[A-Za-z0-9_]+$'; then
        echo "${name} only supports letters, numbers, and underscores." >&2
        exit 1
    fi
}

escape_sql_string() {
    printf '%s' "$1" | sed "s/'/''/g"
}

wait_for_socket_mysql() {
    for _ in $(seq 1 90); do
        if mysqladmin --protocol=socket --socket="${SOCKET_PATH}" -uroot -p"${SEED_ROOT_PASSWORD}" ping --silent >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "Timed out waiting for temporary MySQL server." >&2
    return 1
}

shutdown_socket_mysql() {
    mysqladmin --protocol=socket --socket="${SOCKET_PATH}" -uroot -p"${MYSQL_ROOT_PASSWORD}" shutdown >/dev/null 2>&1 || true
}

require_value MYSQL_ROOT_PASSWORD
require_value MYSQL_DATABASE
require_value MYSQL_USER
require_value MYSQL_PASSWORD

validate_identifier MYSQL_DATABASE "${MYSQL_DATABASE}"
validate_identifier MYSQL_USER "${MYSQL_USER}"

if [ ! -d "${DATADIR}/mysql" ]; then
    echo "Initializing MusicWeb MySQL datadir from embedded seed ..."
    find "${DATADIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    cp -a "${SEED_DIR}/." "${DATADIR}/"
    rm -f "${DATADIR}/auto.cnf"
    chown -R mysql:mysql "${DATADIR}"
    touch "${DATADIR}/.musicweb_seeded"
fi

if [ ! -f "${DATADIR}/.musicweb_password_configured" ]; then
    echo "Configuring runtime MySQL passwords ..."
    chown -R mysql:mysql "${DATADIR}"
    mysqld \
        --user=mysql \
        --skip-networking \
        --socket="${SOCKET_PATH}" \
        --pid-file="${PID_FILE}" &
    mysql_pid="$!"

    trap 'kill "${mysql_pid}" >/dev/null 2>&1 || true' EXIT
    wait_for_socket_mysql

    escaped_root_password="$(escape_sql_string "${MYSQL_ROOT_PASSWORD}")"
    escaped_user_password="$(escape_sql_string "${MYSQL_PASSWORD}")"

    mysql --protocol=socket --socket="${SOCKET_PATH}" -uroot -p"${SEED_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${MYSQL_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${escaped_user_password}';
ALTER USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${escaped_user_password}';
GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
ALTER USER 'root'@'localhost' IDENTIFIED BY '${escaped_root_password}';
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${escaped_root_password}';
ALTER USER 'root'@'%' IDENTIFIED BY '${escaped_root_password}';
FLUSH PRIVILEGES;
SQL

    shutdown_socket_mysql
    wait "${mysql_pid}" || true
    trap - EXIT
    touch "${DATADIR}/.musicweb_password_configured"
fi

exec docker-entrypoint.sh "$@"
