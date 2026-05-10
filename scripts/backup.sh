#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[backup] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
STORAGE_ROOT="${STORAGE_ROOT:-./storage}"
BACKUP_DB_MODE="${BACKUP_DB_MODE:-url}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
POSTGRES_USER="${POSTGRES_USER:-project_mgmt}"
POSTGRES_DB="${POSTGRES_DB:-project_mgmt}"
DATABASE_URL="${DATABASE_URL:-postgresql://project_mgmt:change-me@localhost:5432/project_mgmt}"
OSS_BUCKET="${OSS_BUCKET:-}"
OSS_PREFIX="${OSS_PREFIX:-project-management}"

backup_dir="${BACKUP_ROOT%/}/backup-${timestamp}"
mkdir -p "$backup_dir"

dump_database() {
  case "$BACKUP_DB_MODE" in
    compose)
      require_command docker
      log "dumping PostgreSQL via docker compose service postgres"
      docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
        > "$backup_dir/db.dump"
      ;;
    url)
      require_command pg_dump
      log "dumping PostgreSQL via DATABASE_URL"
      pg_dump "$DATABASE_URL" --format=custom --file "$backup_dir/db.dump"
      ;;
    skip)
      log "skipping database dump because BACKUP_DB_MODE=skip"
      printf 'database backup skipped\n' > "$backup_dir/db.dump.skip"
      ;;
    *)
      printf 'Unsupported BACKUP_DB_MODE: %s\n' "$BACKUP_DB_MODE" >&2
      exit 1
      ;;
  esac
}

archive_storage() {
  require_command tar
  mkdir -p "$STORAGE_ROOT"
  log "archiving storage directory $STORAGE_ROOT"
  tar -czf "$backup_dir/storage.tar.gz" -C "$STORAGE_ROOT" .
}

write_oss_placeholder() {
  if [ -n "$OSS_BUCKET" ]; then
    cat > "$backup_dir/oss-sync-plan.txt" <<EOF
OSS sync placeholder
bucket=$OSS_BUCKET
prefix=$OSS_PREFIX
source=$backup_dir

Configure ossutil, rclone, or cloud vendor CLI here, then sync this directory
to oss://$OSS_BUCKET/$OSS_PREFIX/.
EOF
    log "wrote OSS sync placeholder for bucket $OSS_BUCKET"
  else
    printf 'OSS_BUCKET is not set; remote sync skipped.\n' > "$backup_dir/oss-sync-plan.txt"
    log "OSS_BUCKET not set; remote sync skipped"
  fi
}

write_manifest() {
  database_artifact="db.dump"
  if [ ! -f "$backup_dir/db.dump" ]; then
    database_artifact="db.dump.skip"
  fi

  cat > "$backup_dir/manifest.json" <<EOF
{
  "created_at": "$timestamp",
  "database_artifact": "$database_artifact",
  "storage_artifact": "storage.tar.gz",
  "backup_db_mode": "$BACKUP_DB_MODE",
  "postgres_db": "$POSTGRES_DB",
  "oss_bucket": "$OSS_BUCKET",
  "oss_prefix": "$OSS_PREFIX"
}
EOF
}

dump_database
archive_storage
write_oss_placeholder
write_manifest

log "backup completed: $backup_dir"
printf '%s\n' "$backup_dir"
