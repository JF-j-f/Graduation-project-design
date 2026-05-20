#!/usr/bin/env bash
set -euo pipefail

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-3306}"
export DB_NAME="${DB_NAME:-musicweb}"
export DB_USER="${DB_USER:-musicweb}"
export REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export MUSIC_API_URL="${MUSIC_API_URL:-http://127.0.0.1:3000}"
export QQ_API_URL="${QQ_API_URL:-http://127.0.0.1:8000}"
export UNBLOCK_API_URL="${UNBLOCK_API_URL:-http://127.0.0.1:8081}"
export CONFIG_OUTPUT_DIR="${CONFIG_OUTPUT_DIR:-/opt/musicweb/runtime-config}"

python3 /opt/musicweb/runtime/validate_and_generate_config.py
mkdir -p /opt/musicweb/runtime-config/qq_credentials

mkdir -p /run/mysqld
chown -R mysql:mysql /run/mysqld /var/lib/mysql

service mariadb start

for _ in $(seq 1 60); do
    if mysqladmin ping -h 127.0.0.1 --silent; then
        break
    fi
    sleep 1
done

mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'%';
FLUSH PRIVILEGES;
SQL

if [ ! -f /var/lib/mysql/.musicweb_imported ]; then
    echo "Importing embedded musicweb.sql into ${DB_NAME} ..."
    mysql -uroot "${DB_NAME}" < /opt/musicweb/data/musicweb.sql
    touch /var/lib/mysql/.musicweb_imported
fi

exec supervisord -c /etc/supervisor/conf.d/musicweb.conf
