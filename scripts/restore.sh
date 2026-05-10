#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[restore] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

BACKUP_DIR="${BACKUP_DIR:-}"
STORAGE_ROOT="${STORAGE_ROOT:-./storage}"
BACKUP_DB_MODE="${BACKUP_DB_MODE:-url}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
POSTGRES_USER="${POSTGRES_USER:-project_mgmt}"
POSTGRES_DB="${POSTGRES_DB:-project_mgmt}"
DATABASE_URL="${DATABASE_URL:-postgresql://project_mgmt:change-me@localhost:5432/project_mgmt}"
RESTORE_STORAGE_CLEAR="${RESTORE_STORAGE_CLEAR:-false}"

if [ -z "$BACKUP_DIR" ]; then
  printf 'Set BACKUP_DIR to the backup directory created by scripts/backup.sh\n' >&2
  exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
  printf 'Backup directory not found: %s\n' "$BACKUP_DIR" >&2
  exit 1
fi

restore_database() {
  if [ ! -f "$BACKUP_DIR/db.dump" ]; then
    log "db.dump not found; database restore skipped"
    return
  fi

  case "$BACKUP_DB_MODE" in
    compose)
      require_command docker
      log "restoring PostgreSQL via docker compose service postgres"
      docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        < "$BACKUP_DIR/db.dump"
      ;;
    url)
      require_command pg_restore
      log "restoring PostgreSQL via DATABASE_URL"
      pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" "$BACKUP_DIR/db.dump"
      ;;
    skip)
      log "skipping database restore because BACKUP_DB_MODE=skip"
      ;;
    *)
      printf 'Unsupported BACKUP_DB_MODE: %s\n' "$BACKUP_DB_MODE" >&2
      exit 1
      ;;
  esac
}

restore_storage() {
  if [ ! -f "$BACKUP_DIR/storage.tar.gz" ]; then
    log "storage.tar.gz not found; storage restore skipped"
    return
  fi

  require_command tar
  mkdir -p "$STORAGE_ROOT"
  if [ "$RESTORE_STORAGE_CLEAR" = "true" ]; then
    log "clearing storage directory $STORAGE_ROOT before restore"
    find "$STORAGE_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  fi
  log "restoring storage archive into $STORAGE_ROOT"
  tar -xzf "$BACKUP_DIR/storage.tar.gz" -C "$STORAGE_ROOT"
}

restore_database
restore_storage

log "restore completed from: $BACKUP_DIR"
