# Phase 3 发布说明

Phase 3 目标是接入企业 IT 生态，补齐身份、外部通知、安全扫描和系统集成能力。本版本在原有 FastAPI、Vue、PostgreSQL、Redis、Celery 架构上新增 SSO、外部通知通道、ClamAV 扫描、API Key、只读开放 API 和业务 Webhook。

## 新增能力

### 企业 SSO

- 支持通用 OAuth2/OIDC provider，当前 provider 标识为 `generic_oidc`。
- 登录页可展示企业账号入口。
- 用户可在个人页绑定或解绑企业账号。
- admin 可在用户管理中设置“本地+SSO”或“仅 SSO”。
- 系统不自动创建用户，SSO 登录依赖已存在本地账号或已存在绑定。

### 外部通知通道

- 通知 channel 扩展为站内、邮件、企业微信、钉钉。
- 邮件使用 SMTP 和 Jinja2 模板。
- 企业微信和钉钉使用机器人 Webhook。
- 用户可在个人设置中选择通知范围、实时/摘要模式和 channel 开关。
- 外部通道失败不会影响站内通知，失败投递会记录 delivery 并自动重试。

### 通知失败重试与死信

- 外部通知 delivery 默认最多 3 次尝试。
- 重试间隔为 1 分钟、5 分钟。
- 达到上限后进入 dead letter，并给 admin 生成站内告警。

### ClamAV 文档安全扫描

- compose 新增 `clamav` 服务。
- 文档上传后异步扫描，状态为 `pending`、`clean`、`infected`、`failed`。
- `infected` 文档禁止下载和预览，并通知上传人和 admin。
- 前端文档列表显示扫描中、已通过、已隔离、扫描失败状态。

### proj_leader 自助转交

- proj_leader 可提交自己负责项目的转交申请。
- 管理端支持审核转交申请和查看转交历史。
- 转交流程写审计日志并发送通知。

### API Key 与开放只读 API

- admin 可签发、查看和吊销 API Key。
- token 只在创建后展示一次，系统只保存哈希和前缀。
- 权限范围包括 `projects:read`、`payments:read`、`documents:read`。
- 新增 `/api/external/v1/projects`、`/api/external/v1/payments`、`/api/external/v1/documents`。
- 每个 API Key 默认每小时 1000 次限流，Redis key 使用 `external_api:{api_key_id}:{hour}`。

### Webhook 推送

- admin 可配置 Webhook URL、secret、事件类型和启停状态。
- 当前支持项目状态变更、付款发生、环节推进、撤销审核完成。
- 推送带 `X-Event-Id`、`X-Event-Type`、`X-Timestamp`、`X-Signature`。
- 2xx 视为成功；非 2xx、超时或网络错误会重试。
- 最多 6 次投递尝试，失败后进入 dead letter，admin 可手动重放。

## 数据库迁移

本阶段包含以下迁移：

- `0020_create_oauth_bindings`
- `0021_add_user_sso_policy`
- `0022_add_notification_channels`
- `0023_create_notification_deliveries`
- `0024_add_document_scan_status`
- `0025_create_handover_requests`
- `0026_create_api_keys`
- `0027_create_webhooks`

上线前必须先备份，再执行：

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

## 环境与服务变化

- `.env` 新增 SSO、SMTP、企业微信、钉钉、ClamAV 配置项。
- `docker-compose.yml` 和 `docker-compose.prod.yml` 包含 `clamav` 服务。
- `celery-worker` 需要能访问 PostgreSQL、Redis、storage 和 `clamav:3310`。
- `celery-beat` 新增外部通知重试和 Webhook 重试周期任务。

## 升级步骤

1. 拉取最新 `develop` 或发布分支。
2. 按 `docs/deployment-manual.md` 更新 `.env`，尤其是 SSO、通知和 ClamAV 配置。
3. 执行 `docker compose -f docker-compose.prod.yml config --quiet`。
4. 构建镜像：`docker compose -f docker-compose.prod.yml build`。
5. 备份数据库和 `storage/`。
6. 执行 `alembic upgrade head`。
7. 执行 seed：`docker compose -f docker-compose.prod.yml run --rm backend python -m app.seeds.run`。
8. 启动服务并检查 `postgres`、`redis`、`clamav`、`backend`、`frontend`、`nginx`、`celery-worker`、`celery-beat`。
9. 按 `docs/release-checklist.md` 和本文件的验证清单完成冒烟测试。

## 验证清单

- SSO 登录、绑定、解绑、强制 SSO 策略可运行。
- 邮件、企业微信、钉钉三个外部通知通道可配置并可测试。
- 通知失败重试和 dead letter 告警可验证。
- ClamAV 可识别 EICAR 测试文件，并阻止 `infected` 文档下载/预览。
- proj_leader 自助转交流程完整跑通。
- API Key 可签发、吊销、限流，外部只读 API 可消费。
- Webhook 可配置、签名、重试、死信和重放。
- 后端 `ruff`、`mypy`、`pytest` 通过。
- 前端 `npm run lint`、`npm run typecheck`、`npm run test:unit`、`npm run build` 通过。

## 已知提醒

- 前端生产构建仍可能提示第三方包 pure comment 和大 chunk 警告；当前不影响运行。
- ClamAV 首次启动会拉取或加载病毒库，测试时需等待服务 ready。
- 外部通知和 Webhook 接收方必须自行保证幂等，避免重试导致重复处理。
- SSO 不自动创建账号；上线前应先完成用户邮箱治理。
