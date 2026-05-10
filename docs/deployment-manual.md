# 部署手册

本文面向实施和运维人员，说明本系统在开发、测试和生产环境中的部署步骤。系统包含 FastAPI 后端、Vue 前端、PostgreSQL、Redis、Celery worker/beat、Nginx、Prometheus 和 Grafana。

## 1. 部署前准备

### 1.1 服务器要求

- Docker Engine 和 Docker Compose v2。
- 可用内存建议不低于 8 GB；生产环境建议单独挂载 `storage/` 和数据库卷。
- 生产环境开放 80/443，Prometheus/Grafana 端口按内网策略开放。
- 若启用 Office 预览，后端镜像已内置 LibreOffice；非 Docker 部署需自行安装 LibreOffice。

### 1.2 环境变量

先复制模板：

```bash
cp .env.example .env
```

生产环境必须修改以下值：

```env
APP_ENV=production
APP_DEBUG=false
POSTGRES_PASSWORD=<强密码>
DATABASE_URL=postgresql+asyncpg://project_mgmt:<强密码>@postgres:5432/project_mgmt
JWT_SECRET_KEY=<强随机密钥>
DEFAULT_ADMIN_PASSWORD=<临时强密码>
GRAFANA_ADMIN_PASSWORD=<强密码>
PROD_CORS_ALLOW_ORIGINS=https://<你的域名>
PROD_VITE_API_BASE_URL=/api/v1
```

如使用本地文件存储，确认宿主机 `storage/` 已纳入备份。S3/OSS 存储保留配置入口，当前生产默认仍为本地存储。

## 2. 开发环境部署

开发环境用于本机联调，服务端口直接暴露：

```bash
docker compose up --build
```

常用入口：

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/health
- OpenAPI：http://localhost:8000/docs

首次启动后执行迁移和 seed：

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.seeds.run
```

## 3. 生产环境部署

### 3.1 构建配置检查

```bash
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build
```

### 3.2 数据库迁移

上线前先做备份，再执行迁移：

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

若迁移失败，停止上线并按 `docs/disaster-recovery.md` 恢复。

### 3.3 初始化数据

```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m app.seeds.run
```

首次登录默认管理员后必须修改密码。

### 3.4 启动服务

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

核心服务应为 `running` 或 `healthy`：

- `postgres`
- `redis`
- `backend`
- `frontend`
- `nginx`
- `celery-worker`
- `celery-beat`
- `prometheus`
- `grafana`

### 3.5 健康检查

```bash
curl -fsS https://localhost/health
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/metrics
```

`/health` 必须返回整体可用；`/metrics` 必须包含 API 请求和耗时指标。

## 4. 定时任务

Celery beat 当前负责：

- 每日 09:00 扫描任务到期、逾期和 7 天逾期升级。
- 每日 09:00 生成前一天通知摘要。
- 每周一 03:00 清理临时和过期文件。
- 每月 1 日 00:30 维护审计日志分区。
- 每日 03:30 清理过期报表文件。

检查 worker/beat：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 celery-beat
```

## 5. Phase 2 功能部署要点

### 5.1 仪表盘

仪表盘接口使用 Redis 缓存 5 分钟。若看到数据短暂延迟，先确认是否仍在缓存窗口内。

### 5.2 报表导出

大报表会进入 Celery 异步队列，结果文件保留 7 天。确保 `storage/` 可写，且 Celery worker 正常运行。

### 5.3 Office 预览

Office 文档通过 LibreOffice 转 PDF。排查方式见 `docs/office-preview.md`。

### 5.4 通知摘要

用户可在个人页选择实时通知或每日摘要。每日摘要由 Celery beat 在 Asia/Shanghai 09:00 触发，合并前一天的摘要模式通知。

## 6. 备份与恢复

上线前和每日定时执行：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
POSTGRES_USER=project_mgmt \
POSTGRES_DB=project_mgmt \
STORAGE_ROOT=./storage \
scripts/backup.sh
```

恢复演练见 `docs/disaster-recovery.md`。

## 7. 发布验证

发布后至少完成以下冒烟测试：

1. 管理员登录并查看仪表盘。
2. 创建主项目和子项目，完成审核。
3. 上传 PDF 和 Office 文档并预览。
4. 创建任务并完成一次移动端快捷完成。
5. 创建付款记录并验证通知中心出现通知。
6. 生成一份报表并下载。
7. 打开审计日志查询页面确认关键操作已记录。
