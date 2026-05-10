# 灾备与恢复手册

## 目标

任务：T-1-DEPLOY-03 备份脚本 + DR 演练。

目标状态：完整一次备份 + 恢复演练通过，并且新人可以按本文独立执行数据库与附件存储恢复。

## RPO / RTO

- RPO：默认 24 小时，生产环境建议每天至少执行一次 `scripts/backup.sh`。
- RTO：默认 2 小时，包含拉取备份、恢复 PostgreSQL、恢复 storage、启动服务、执行健康检查。

## 备份内容

- PostgreSQL：`pg_dump --format=custom` 输出 `db.dump`。
- 附件存储：将 `STORAGE_ROOT` 打包为 `storage.tar.gz`。
- Manifest：`manifest.json` 记录备份时间、数据库模式、OSS 占位配置。
- OSS 占位：`oss-sync-plan.txt` 记录 `OSS_BUCKET` / `OSS_PREFIX`，后续可接入 ossutil、rclone 或云厂商 CLI。

## 备份命令

主机直接连接数据库：

```bash
BACKUP_ROOT=./backups \
STORAGE_ROOT=./storage \
DATABASE_URL=postgresql://project_mgmt:change-me@localhost:5432/project_mgmt \
scripts/backup.sh
```

Docker Compose 环境：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
POSTGRES_USER=project_mgmt \
POSTGRES_DB=project_mgmt \
STORAGE_ROOT=./storage \
scripts/backup.sh
```

## 恢复命令

恢复脚本内部使用 `pg_restore --clean --if-exists --no-owner` 将 `db.dump` 恢复到目标数据库。

主机直接连接数据库：

```bash
BACKUP_DIR=./backups/backup-YYYYmmddTHHMMSSZ \
STORAGE_ROOT=./storage \
DATABASE_URL=postgresql://project_mgmt:change-me@localhost:5432/project_mgmt \
scripts/restore.sh
```

Docker Compose 环境：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
BACKUP_DIR=./backups/backup-YYYYmmddTHHMMSSZ \
POSTGRES_USER=project_mgmt \
POSTGRES_DB=project_mgmt \
STORAGE_ROOT=./storage \
RESTORE_STORAGE_CLEAR=true \
scripts/restore.sh
```

## 演练步骤

1. 启动隔离的 PostgreSQL 演练环境。
2. 写入一条演练数据和一个 storage 文件。
3. 执行 `scripts/backup.sh`，确认生成 `db.dump`、`storage.tar.gz`、`manifest.json`。
4. 删除演练数据和 storage 文件。
5. 执行 `scripts/restore.sh`。
6. 查询演练数据，确认 PostgreSQL 恢复成功。
7. 检查 storage 文件，确认附件恢复成功。

## 演练记录

- 日期：2026-05-10
- 环境：Docker Compose 隔离项目 `management_drtest`
- 数据库模式：`BACKUP_DB_MODE=compose`
- 结果：完整一次备份 + 恢复演练通过
- 证据：
  - `scripts/backup.sh` 生成 `db.dump`、`storage.tar.gz`、`manifest.json`
  - `scripts/restore.sh` 恢复演练表数据
  - storage 文件恢复到目标目录

## 注意事项

- 生产环境必须将 `GRAFANA_ADMIN_PASSWORD`、数据库密码、OSS 凭据写入安全的环境变量或密钥管理系统。
- 恢复前先停写业务流量，避免恢复过程中产生新数据。
- `RESTORE_STORAGE_CLEAR=true` 会清空目标 storage 目录后再解压备份，只应在确认目标目录可覆盖时使用。
- OSS 占位需要在实际云厂商确定后替换为正式同步命令，并纳入下一次 DR 演练。
