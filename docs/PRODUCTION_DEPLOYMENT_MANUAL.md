# 生产发布与试用部署手册

本文面向准备把系统发布到生产试用环境的实施和运维人员。目标是按当前 `develop` 版本完成一次可回滚、可验证、可交付业务试用的部署。

## 1. 部署目标

本系统由以下组件组成：

- FastAPI 后端：业务 API、健康检查、指标、OpenAPI。
- Vue 3 前端：项目、任务、文档、报表、归档、搜索、后台管理和中英文切换。
- PostgreSQL 16：主业务库、审计、归档表、全文检索索引。
- Redis 7：登录态辅助、限流、OAuth state、Celery broker/result backend、Dashboard 缓存。
- Celery worker/beat：通知、文档扫描、全文索引、报表、导入导出、归档辅助任务。
- ClamAV：文档病毒扫描。
- Nginx：生产入口、前端静态文件、API 反向代理、TLS 终止。
- Prometheus/Grafana：生产观测。

生产试用可以先使用 `docker-compose.prod.yml` 单机部署；当数据库和 Redis 改为企业托管或 HA 拓扑时，通过环境变量切换，不需要改代码。

## 2. 发布前检查

在仓库根目录执行：

```powershell
git status --short --branch
docker compose -f docker-compose.yml config
docker compose -f docker-compose.prod.yml config
```

发布前必须确认：

- 代码来自已验证的发布分支或 `develop` 指定提交。
- `management.rar`、本地备份、日志、临时导出包等未被误提交。
- PostgreSQL、Redis、ClamAV、storage 所在磁盘已纳入备份。
- 生产 `.env` 不使用示例密码。
- 业务方已确认本次试用域名、管理员账号、初始用户清单和回滚窗口。

## 3. 服务器要求

最低试用环境：

- 4 vCPU、8 GB 内存、100 GB 可用磁盘。
- Windows Server + Docker Desktop、Linux + Docker Engine，或等价容器平台。
- 对外开放 80/443；Grafana/Prometheus 仅建议内网开放。
- 生产 storage 建议挂载独立数据盘，避免随代码目录清理。

推荐生产环境：

- PostgreSQL 使用云数据库或独立主从。
- Redis 使用 Sentinel/托管 Redis。
- API 和 worker 多副本。
- storage 使用共享盘或对象存储；当前代码默认本地 `./storage`，对象存储配置入口已保留。

## 4. 生产环境变量

从模板复制：

```powershell
Copy-Item .env.example .env
```

必须修改：

```env
APP_ENV=production
APP_DEBUG=false
POSTGRES_PASSWORD=<强密码>
DATABASE_URL=postgresql+asyncpg://project_mgmt:<强密码>@postgres:5432/project_mgmt
JWT_SECRET_KEY=<强随机密钥>
DEFAULT_ADMIN_PASSWORD=<临时强密码>
GRAFANA_ADMIN_PASSWORD=<强密码>
PROD_CORS_ALLOW_ORIGINS=https://app.example.com
PROD_VITE_API_BASE_URL=/api/v1
```

Phase 4 新增或重点变量：

```env
# PostgreSQL 读副本，留空时读写都走 DATABASE_URL
DATABASE_REPLICA_URL=

# Redis Sentinel，未启用时继续使用 REDIS_URL
REDIS_SENTINEL_ENABLED=false
REDIS_SENTINEL_HOSTS=
REDIS_SENTINEL_MASTER_NAME=mymaster
REDIS_SENTINEL_DB=0
REDIS_SENTINEL_PASSWORD=

# 应用水平扩展参数
BACKEND_REPLICAS=2
CELERY_WORKER_REPLICAS=2
GUNICORN_WORKERS=4
```

企业集成按需配置：

```env
OAUTH_GENERIC_ENABLED=false
SMTP_ENABLED=false
WEWORK_ENABLED=false
DINGTALK_ENABLED=false
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
CLAMAV_TIMEOUT_SECONDS=10
```

Phase 5 AI provider 变量默认保持关闭：

```env
AI_ENABLED=false
AI_PROVIDER=disabled
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=
AI_API_KEY=
AI_TIMEOUT_SECONDS=30
```

启用 AI 时，`AI_PROVIDER` 可设为 `openai` 或企业内部 OpenAI-compatible 网关标识；后端只调用 `/chat/completions` 并要求 JSON object 响应。风险评分、文档类型建议和指标问答均有规则降级路径，生产试用建议先保持关闭，完成权限和审计验收后再逐步启用。

## 5. 首次部署步骤

1. 拉取代码并确认提交：

   ```powershell
   git fetch --all
   git checkout develop
   git pull
   git log --oneline -5
   ```

2. 检查生产 compose：

   ```powershell
   docker compose -f docker-compose.prod.yml config
   docker compose -f docker-compose.prod.yml build
   ```

3. 启动基础依赖：

   ```powershell
   docker compose -f docker-compose.prod.yml up -d postgres redis clamav
   docker compose -f docker-compose.prod.yml ps
   ```

4. 执行数据库迁移：

   ```powershell
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```

5. 初始化系统数据：

   ```powershell
   docker compose -f docker-compose.prod.yml run --rm backend python -m app.seeds.run
   ```

6. 启动应用：

   ```powershell
   docker compose -f docker-compose.prod.yml up -d
   docker compose -f docker-compose.prod.yml ps
   ```

7. 健康检查：

   ```powershell
   Invoke-WebRequest https://localhost/health
   Invoke-WebRequest http://localhost:8000/health
   Invoke-WebRequest http://localhost:8000/metrics
   ```

## 6. 从旧版本升级

升级前：

1. 宣布维护窗口，暂停批量导入、全库导出、归档和大报表任务。
2. 备份数据库和 storage。
3. 记录当前版本：

   ```powershell
   git rev-parse HEAD
   docker compose -f docker-compose.prod.yml ps
   ```

4. 执行迁移：

   ```powershell
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```

5. 滚动发布应用：

   ```powershell
   docker compose -f docker-compose.prod.yml up -d --build backend celery-worker celery-beat frontend nginx
   ```

6. 观察 15-30 分钟 `/health`、`/metrics`、Celery 日志和 Nginx 错误日志。

## 7. Phase 4 迁移说明

本阶段涉及以下迁移：

- `0028_add_user_timezone`：用户时区字段，默认 `Asia/Shanghai`。
- `0029_create_archive_tables`：归档批次和 `archive_*` 表。
- `0030_create_document_search_entries`：文档全文检索索引表。
- `0031_create_database_export_jobs`：数据库全量导出任务表。
- `0032_add_query_performance_indexes`：关键查询索引优化。

迁移必须由后端容器执行，不要手工改生产表结构。

## 7.1 Phase 5 迁移说明

Phase 5 新增迁移覆盖项目类型/工作流模板、自定义报表、项目模板分类标签和 AI 审计日志。升级前必须备份数据库；升级后重点确认：

- `workflow_templates`、`workflow_template_versions` 可写入并发布模板。
- `custom_report_definitions`、`custom_report_runs` 可创建预览和定时任务。
- `project_templates`、`project_categories`、`project_tags` 可用于模板库。
- `ai_audit_logs` 存在，AI 关闭时不会产生外部调用。

## 8. 高可用部署

### 8.1 PostgreSQL 主从

推荐由云数据库或 DBA 平台提供主从。应用配置：

- `DATABASE_URL` 指向主库。
- `DATABASE_REPLICA_URL` 指向只读副本。
- 迁移、写入、归档、恢复、导入、导出任务仍以主库为准。

主库故障时，先完成数据库平台的副本提升，再把 `DATABASE_URL` 指向新主库。详见 `docs/PRODUCTION_HA_DEPLOYMENT.md`。

### 8.2 Redis Sentinel

启用示例：

```env
REDIS_SENTINEL_ENABLED=true
REDIS_SENTINEL_HOSTS=redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379
REDIS_SENTINEL_MASTER_NAME=management-master
REDIS_SENTINEL_DB=0
REDIS_SENTINEL_PASSWORD=<password>
```

API 限流、登录失败计数、OAuth state、Dashboard 缓存、健康检查和 Celery broker/result backend 都会通过 Sentinel 解析 master。

### 8.3 应用多副本

```powershell
$env:BACKEND_REPLICAS="2"
$env:CELERY_WORKER_REPLICAS="2"
docker compose -f docker-compose.prod.yml up -d --build
```

注意：

- `celery-beat` 只能 1 个副本。
- 多副本 API 必须共享同一个 `storage`。
- 下游 Webhook 接收方必须按 `X-Event-Id` 做幂等。

## 9. 发布后冒烟测试

至少完成：

1. admin 登录，修改默认密码。
2. 切换中文/English，确认导航和登录页可读。
3. 创建主项目、提交审核、审核通过。
4. 创建子项目、提交审核、推进一个环节。
5. 上传 PDF/Office 文档，确认扫描状态和预览。
6. 搜索已索引文档。
7. 创建任务并完成一次。
8. 登记付款，验证预算和通知。
9. 下载项目批量导入模板，试导入小样本。
10. 发起数据库导出任务并下载。
11. 创建工作流模板新版本并绑定项目类型，确认旧项目不受影响。
12. 创建自定义报表并预览，配置一次定时报表。
13. 使用模板库实例化项目。
14. 打开对标分析、风险评分、文档类型建议和指标问答，确认 AI 关闭时规则路径可用。
15. 查看归档候选，执行测试归档和恢复。
16. 创建 API Key 调用 `/api/external/v1/projects`。
17. 配置测试 Webhook，触发事件并验证签名。
18. 打开 Grafana，确认 API、Celery、数据库、磁盘仪表盘有数据。

## 10. 备份

每日备份：

```powershell
$env:BACKUP_DB_MODE="compose"
$env:COMPOSE_FILE="docker-compose.prod.yml"
$env:POSTGRES_USER="project_mgmt"
$env:POSTGRES_DB="project_mgmt"
$env:STORAGE_ROOT="./storage"
bash scripts/backup.sh
```

备份内容包括 PostgreSQL dump、storage 包和 manifest。恢复演练见 `docs/disaster-recovery.md`。

## 11. 回滚

代码回滚：

```powershell
docker compose -f docker-compose.prod.yml logs --since 30m > rollback-evidence.log
git checkout <previous-release-tag-or-commit>
docker compose -f docker-compose.prod.yml up -d --build
```

数据回滚：

```powershell
$env:BACKUP_DB_MODE="compose"
$env:COMPOSE_FILE="docker-compose.prod.yml"
$env:BACKUP_DIR="./backups/backup-YYYYmmddTHHMMSSZ"
$env:RESTORE_STORAGE_CLEAR="true"
bash scripts/restore.sh
```

如果本次发布包含数据库迁移，优先在隔离环境验证 downgrade 或备份恢复，再操作生产。

## 12. 发布验收命令

```powershell
cd C:\management\backend
python -B -m pytest -q
python -B -m ruff check .
python -B -m mypy app tests
python -B -m compileall -q app tests alembic

cd C:\management\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run build

cd C:\management
docker compose -f docker-compose.yml config
docker compose -f docker-compose.prod.yml config
git diff --check
```
