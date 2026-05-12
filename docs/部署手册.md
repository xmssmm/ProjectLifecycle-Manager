# 部署手册

本文面向实施和运维人员，说明本系统在开发、测试和生产环境中的部署步骤。系统包含 FastAPI 后端、Vue 前端、PostgreSQL、Redis、Celery worker/beat、ClamAV、Nginx、Prometheus 和 Grafana。

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

Phase 3 企业集成相关变量按需启用：

```env
# 通用 OAuth2/OIDC SSO
OAUTH_GENERIC_ENABLED=true
OAUTH_GENERIC_LABEL=企业账号
OAUTH_GENERIC_CLIENT_ID=<client-id>
OAUTH_GENERIC_CLIENT_SECRET=<client-secret>
OAUTH_GENERIC_AUTHORIZE_URL=https://idp.example.com/oauth2/authorize
OAUTH_GENERIC_TOKEN_URL=https://idp.example.com/oauth2/token
OAUTH_GENERIC_USERINFO_URL=https://idp.example.com/oauth2/userinfo
OAUTH_GENERIC_REDIRECT_URI=https://<你的域名>/login?oauth_provider=generic_oidc
OAUTH_GENERIC_BIND_REDIRECT_URI=https://<你的域名>/profile?oauth_action=bind&oauth_provider=generic_oidc
OAUTH_GENERIC_SCOPE=openid email profile

# 外部通知通道
SMTP_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM_ADDRESS=project-system@example.com
SMTP_USE_TLS=true
WEWORK_ENABLED=true
WEWORK_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<key>
WEWORK_WEBHOOK_SECRET=<optional-secret>
DINGTALK_ENABLED=true
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=<token>
DINGTALK_WEBHOOK_SECRET=<optional-secret>

# 病毒扫描
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
CLAMAV_TIMEOUT_SECONDS=10
```

在企业身份提供方中登记的回调地址必须与 `OAUTH_GENERIC_REDIRECT_URI`、`OAUTH_GENERIC_BIND_REDIRECT_URI` 完全一致。API Key 和 Webhook 不通过环境变量配置，由 admin 在系统管理页签发和维护。

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
- `clamav`
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
- 每 60 秒重试邮件、企业微信、钉钉外部通知投递。
- 每 60 秒重试业务 Webhook 投递。
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

## 6. Phase 3 企业集成部署要点

### 6.1 SSO

系统支持通用 OAuth2/OIDC provider，当前 provider 标识为 `generic_oidc`。上线前确认：

1. 企业 IdP 已登记登录回调和绑定回调地址。
2. `.env` 中 SSO 变量完整，`OAUTH_GENERIC_ENABLED=true`。
3. 访问 `GET /api/v1/oauth/providers` 能看到已启用的企业登录入口。
4. 本地账号已存在且邮箱与企业账号一致；系统不会自动创建新用户。
5. admin 可在用户管理中把账号切换为“仅 SSO”，切换前应确认用户已完成绑定。

### 6.2 邮件、企业微信、钉钉通知

外部通知通道默认关闭，启用后仍不影响站内通知落库。用户需要在个人设置中打开对应 channel；没有邮箱的用户不会收到邮件。

生产验证建议先在测试用户上完成：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 celery-beat
```

若外部通道失败，系统会记录 delivery，按 1 分钟、5 分钟重试，达到 3 次后进入 dead letter 并通知 admin。

### 6.3 ClamAV

开发和生产 compose 都包含 `clamav` 服务，后端与 worker 通过 `CLAMAV_HOST=clamav`、`CLAMAV_PORT=3310` 连接。上传文档后先进入 `pending`，异步扫描完成后变为 `clean`、`infected` 或 `failed`。

```bash
docker compose -f docker-compose.prod.yml ps clamav
docker compose -f docker-compose.prod.yml logs --tail 200 clamav
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
```

测试环境可上传 EICAR 测试文件验证隔离逻辑；生产环境不要对真实业务库做破坏性演练。`infected` 文档会被拒绝下载和预览，并通知上传人和 admin。

### 6.4 API Key 与外部只读 API

admin 在“API Key 管理”页签发凭据。新 token 只在创建后展示一次，必须立即交给对接系统保存。外部系统通过请求头调用：

```bash
curl -H "X-API-Key: <token>" https://<你的域名>/api/external/v1/projects
curl -H "X-API-Key: <token>" https://<你的域名>/api/external/v1/payments
curl -H "X-API-Key: <token>" https://<你的域名>/api/external/v1/documents
```

权限范围包括 `projects:read`、`payments:read`、`documents:read`。默认每个 API Key 每小时 1000 次，Redis key 形如 `external_api:{api_key_id}:{yyyyMMddHH}`。

### 6.5 Webhook

admin 在“Webhook 管理”页配置 URL、secret 和事件类型。当前支持：

- `project.status_changed`
- `payment.created`
- `phase.promoted`
- `revoke_request.reviewed`

系统发送 JSON body，并带 `X-Event-Id`、`X-Event-Type`、`X-Timestamp`、`X-Signature`。签名格式为 `sha256=<hex>`，签名消息为 `{timestamp}.{event_id}.{canonical_json_body}`，算法为 HMAC-SHA256。

2xx 视为成功；非 2xx、超时或网络错误会进入重试，最多 6 次投递尝试（首次 + 5 次重试），之后进入死信队列。admin 可在 Webhook 管理页查询死信并手动重放。

## 7. 备份与恢复

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

## 8. 发布验证

发布后至少完成以下冒烟测试：

1. 管理员登录并查看仪表盘。
2. 创建主项目和子项目，完成审核。
3. 上传 PDF 和 Office 文档并预览。
4. 创建任务并完成一次移动端快捷完成。
5. 创建付款记录并验证通知中心出现通知。
6. 生成一份报表并下载。
7. 打开审计日志查询页面确认关键操作已记录。
8. 使用测试账号完成 SSO 登录、绑定和解绑。
9. 打开邮件、企业微信、钉钉任一测试通道并验证失败不会影响站内通知。
10. 在测试环境上传 EICAR 文件，确认文档显示已隔离且不可下载/预览。
11. 签发 API Key，调用 `/api/external/v1/projects`，再吊销并确认请求被拒绝。
12. 配置测试 Webhook，触发付款或环节推进，确认签名、重试、死信和重放可用。
