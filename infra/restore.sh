#!/bin/sh
# Restore from backup:  ./restore.sh /var/backups/yolchi/db-YYYYMMDD-HHMM.dump [/var/backups/yolchi/files-YYYYMMDD-HHMM.tgz]
# WARNING: replaces the current database contents.
set -eu
cd "$(dirname "$0")"
set -a; . ./.env; set +a
DUMP=$1
FILES=${2:-}

docker compose stop app
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$DUMP"
if [ -n "$FILES" ]; then
  docker compose run --rm --no-deps -T --entrypoint "" app sh -c "rm -rf /srv/backend/data/files/* && tar xzf - -C /srv/backend/data" < "$FILES"
fi
docker compose start app
echo "restore finished"
