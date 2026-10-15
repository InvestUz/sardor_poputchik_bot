#!/bin/sh
# Daily backup: PostgreSQL dump + uploaded files. Keep 14 days locally; copy off-site (see docs).
# cron:  15 3 * * *  /opt/yolchi/infra/backup.sh >> /var/log/yolchi-backup.log 2>&1
set -eu
cd "$(dirname "$0")"
set -a; . ./.env; set +a

TS=$(date +%Y%m%d-%H%M)
DEST=${BACKUP_DIR:-/var/backups/yolchi}
mkdir -p "$DEST"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DEST/db-$TS.dump"
docker compose exec -T app tar czf - -C /srv/backend/data files > "$DEST/files-$TS.tgz"

# sanity check: the dump must be readable
docker compose exec -T db pg_restore --list < "$DEST/db-$TS.dump" > /dev/null

find "$DEST" -type f -mtime +14 -delete
echo "$(date) backup ok: $DEST/db-$TS.dump"

# Off-site copy (fill in your storage), e.g.:
# rsync -az "$DEST/" backup-user@backup-host:/backups/yolchi/
