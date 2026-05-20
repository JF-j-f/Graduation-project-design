FROM mysql:8.4

COPY mysql /opt/musicweb/mysql-seed/mysql
COPY entrypoint.sh /usr/local/bin/musicweb-mysql-fast-entrypoint.sh

RUN chmod +x /usr/local/bin/musicweb-mysql-fast-entrypoint.sh

ENTRYPOINT ["musicweb-mysql-fast-entrypoint.sh"]
CMD ["mysqld", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci", "--default-time-zone=+08:00", "--max-allowed-packet=512M"]
