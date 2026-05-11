# Phase 4 发布说明

Phase 4 目标是提升系统在数据规模、合规审计、跨时区、生产高可用和批量数据处理方面的可用性。本版本在既有 FastAPI、Vue、PostgreSQL、Redis、Celery、ClamAV、Nginx、Prometheus/Grafana 架构上新增归档、全文检索、批量导入、数据库全量导出、时区与中英文国际化、HA 配置能力和关键查询优化。

## 1. 新增能力

### 用户时区

- 用户增加 `timezone` 字段，默认 `Asia/Shanghai`。
- 后端校验 IANA timezone。
- 认证响应、用户列表、用户详情和编辑接口返回/支持时区。
- 前端按当前用户时区渲染日期时间。
- 通知摘要和任务到期扫描按用户本地 09:00 分组触发。

### 中英文国际化

- 前端集成 `vue-i18n` v11。
- 默认中文，右上角可切换 English。
- 核心导航、登录表单、通用按钮、状态标签和常见错误提示已抽离到资源文件。
- 语言选择写入 `localStorage`。

### 数据归档与恢复

- 新增 `archive_batches` 和核心 `archive_*` 表。
- 已结项且达到阈值的主项目可进入归档候选。
- admin 可查看候选、创建归档批次、查看批次详情、恢复单个主项目。
- 归档和恢复操作写入审计日志。
- 恢复前校验业务唯一键冲突，冲突返回 409。

### 文档全文检索

- 上传或新版本文档保存后，后台抽取文本并写入 `document_search_entries`。
- 使用 PostgreSQL FTS 检索文档内容和元数据。
- 新增搜索页和 `GET /api/v1/search`。
- 已隔离、已删除或未通过扫描的文档不会进入结果。

### 项目批量导入

- admin 可下载 Excel 模板。
- 导入时逐行校验，失败行不阻塞成功行。
- 返回成功数、失败数、逐行错误和导入批次号。
- 本地性能目标：1000 行不超过 60 秒。

### 数据库全量导出

- admin 可发起全库导出任务。
- 导出包包含 CSV/Excel、manifest、外键说明和审计信息。
- 大导出异步执行，提供任务状态和下载地址。
- 发起和下载均写审计日志。

### 高可用与生产拓扑

- 支持可选 `DATABASE_REPLICA_URL`，未配置时保持单库行为。
- 支持 Redis Sentinel，未启用时保持 `REDIS_URL` fallback。
- 生产 compose 支持 API/worker 多副本、健康检查和滚动发布配置。
- 新增 `docs/PRODUCTION_HA_DEPLOYMENT.md` 和本次交付的生产部署手册。

### 关键查询性能

- 为主项目、子项目、文档、任务、付款、报表任务补充关键索引。
- 新增 `backend/app/services/query_metrics.py` 作为后续环境复测工具。
- 文档记录优化前后预算和复测命令：`docs/PERFORMANCE_BASELINE.md`。

## 2. 数据库迁移

上线前必须备份数据库和 storage，再执行：

```powershell
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

本阶段新增迁移：

- `0028_add_user_timezone`
- `0029_create_archive_tables`
- `0030_create_document_search_entries`
- `0031_create_database_export_jobs`
- `0032_add_query_performance_indexes`

不要在生产环境手工修改这些表或索引。

## 3. 环境变量变化

新增或重点变量：

```env
DATABASE_REPLICA_URL=
REDIS_SENTINEL_ENABLED=false
REDIS_SENTINEL_HOSTS=
REDIS_SENTINEL_MASTER_NAME=mymaster
REDIS_SENTINEL_DB=0
REDIS_SENTINEL_PASSWORD=
BACKEND_REPLICAS=2
CELERY_WORKER_REPLICAS=2
GUNICORN_WORKERS=4
PROD_VITE_API_BASE_URL=/api/v1
```

若不配置 HA 变量，系统保持原单机 PostgreSQL/Redis 行为。

## 4. 前端依赖变化

- 新增 `vue-i18n`。
- `npm.cmd install` 会更新 `package-lock.json`。
- 前端构建仍可能提示第三方 `/* #__PURE__ */` 注释和大 chunk warning；当前验证中不影响构建产物。

## 5. 升级步骤

1. 拉取发布版本。
2. 更新 `.env`，补齐生产密码、CORS、前端 API 地址和可选 HA 变量。
3. 检查 compose：

   ```powershell
   docker compose -f docker-compose.prod.yml config
   ```

4. 备份：

   ```powershell
   $env:BACKUP_DB_MODE="compose"
   $env:COMPOSE_FILE="docker-compose.prod.yml"
   $env:POSTGRES_USER="project_mgmt"
   $env:POSTGRES_DB="project_mgmt"
   $env:STORAGE_ROOT="./storage"
   bash scripts/backup.sh
   ```

5. 执行迁移：

   ```powershell
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```

6. 构建并启动：

   ```powershell
   docker compose -f docker-compose.prod.yml up -d --build
   ```

7. 执行发布后冒烟。

## 6. 验证清单

发布后至少验证：

- 用户时区可读取和修改，页面日期按用户时区显示。
- 中文/English 切换可用，刷新后保留。
- admin 可查看归档候选、创建归档批次、查看详情、恢复主项目。
- 搜索页可检索已索引且扫描通过的文档。
- Excel 模板下载和小样本导入可用。
- 数据库导出任务可创建、完成和下载。
- `docker compose -f docker-compose.prod.yml config` 通过。
- `/health`、`/metrics` 正常。
- API、worker、beat 日志无持续错误。

## 7. 运维关注点

- 归档和恢复属于高影响操作，建议先在试用环境验证。
- 数据库全量导出包包含敏感数据，应存放在受控目录。
- 全文索引依赖 Celery worker、storage 和文档扫描状态。
- 多时区通知依赖服务器时间准确，生产应启用 NTP。
- Redis Sentinel 切换后需要验证登录、限流、OAuth state、Dashboard 和 Celery。
- PostgreSQL 副本延迟过大时，不要把强一致业务查询切到只读副本。

## 8. 已知提醒

- 当前中英文资源覆盖核心导航、登录、通用按钮、状态和错误提示；业务数据、用户自定义名称和部分页面专有文案仍可能显示中文。
- 生产 compose 的 `deploy.replicas` 在普通 Docker Compose 非 Swarm 模式下仅作为拓扑示例；如果本地 compose 不按 replicas 扩容，可通过平台编排或多服务实例实现。
- 全文检索当前使用 PostgreSQL FTS；未来数据量继续增长时，可基于 `document_search_entries` 同步到 OpenSearch。
- `celery-beat` 必须单副本运行。

## 9. 交付文档

- 生产发布与试用部署：`docs/PRODUCTION_DEPLOYMENT_MANUAL.md`
- 业务使用：`docs/USER_MANUAL.md`
- 管理员与运维：`docs/ADMIN_OPERATIONS_MANUAL.md`
- HA 专项：`docs/PRODUCTION_HA_DEPLOYMENT.md`
- 性能基线：`docs/PERFORMANCE_BASELINE.md`
- 灾备恢复：`docs/disaster-recovery.md`
- 故障排查：`docs/troubleshooting.md`

