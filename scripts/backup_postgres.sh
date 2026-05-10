#!/usr/bin/env bash
#
# Storymaster Postgres backup.
#
# Replaces the SQLite file-copy `BackupManager` flow for the web deploy.
# Reads the database URL from STORYMASTER_DB_URL (same env the app uses);
# emits a timestamped `pg_dump` custom-format archive into BACKUP_DIR;
# prunes archives older than RETENTION_DAYS.
#
# Usage:
#   STORYMASTER_DB_URL=postgresql+psycopg://user:pass@host/db \
#   BACKUP_DIR=/var/backups/storymaster \
#   RETENTION_DAYS=14 \
#       scripts/backup_postgres.sh
#
# Restore (one-shot):
#   pg_restore --clean --if-exists --no-owner -d "$DB_URL" /path/to/backup.dump
#
# Schedule via systemd timer or cron. Output is suitable for log-aggregation
# (single line per run, exit code reflects pg_dump's).

set -euo pipefail

: "${STORYMASTER_DB_URL:?STORYMASTER_DB_URL is required}"
: "${BACKUP_DIR:=/var/backups/storymaster}"
: "${RETENTION_DAYS:=14}"

# pg_dump speaks postgresql:// directly but not the SQLAlchemy +psycopg
# variant. Strip the driver suffix.
DB_URL_FOR_PGDUMP="${STORYMASTER_DB_URL/postgresql+psycopg:/postgresql:}"
DB_URL_FOR_PGDUMP="${DB_URL_FOR_PGDUMP/postgresql+psycopg2:/postgresql:}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/storymaster-$stamp.dump"

# `--format=custom` produces a single-file archive that pg_restore handles
# best (parallel restore, selective table restore). `--no-owner` lets the
# archive restore into a database with a different role name (useful for
# disaster-recovery into a fresh role).
pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    --file="$out" \
    "$DB_URL_FOR_PGDUMP"

# Tighten the dump file: contains password hashes and session tokens.
chmod 600 "$out"

echo "wrote $out ($(stat -c%s "$out") bytes)"

# Prune older archives. We use mtime so a recent restore-test that touches
# old files doesn't accidentally re-collect them.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'storymaster-*.dump' \
    -mtime +"$RETENTION_DAYS" -print -delete \
    | sed 's/^/pruned /'
