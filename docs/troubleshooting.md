# 故障排查手册

## 常见问题总览

先执行基础状态检查：

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 100 backend
curl -fsS http://localhost:8000/health
```

确认问题范围后再处理，避免同时改多个变量。

## 登录失败

现象：

- 用户密码正确但无法登录。
- 多次失败后账号被锁定。

排查：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 backend
docker compose -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'auth:*'
```

处理：

- 确认用户状态不是 disabled。
- 确认系统时间正确，JWT 过期依赖服务器时间。
- 如是失败次数锁定，按审计流程重置失败计数或等待锁定窗口结束。

## SSO 回调失败

现象：

- 点击企业账号后回到登录页但没有完成登录。
- 页面提示 state 无效、provider 未启用或账号未绑定。

排查：

```bash
curl -fsS http://localhost:8000/api/v1/oauth/providers
docker compose -f docker-compose.prod.yml logs --tail 200 backend
docker compose -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'oauth:state:*'
```

处理：

- 确认 `OAUTH_GENERIC_ENABLED=true` 且 OAuth URL、client id、client secret、scope 均已配置。
- 确认 IdP 后台登记的回调地址与 `OAUTH_GENERIC_REDIRECT_URI` 完全一致。
- 确认用户本地账号已存在，且邮箱已验证或用户已在个人页绑定。
- 如果是 state 过期，让用户重新发起登录，不要复用旧回调链接。

## 数据库连接失败

现象：

- `/health` 中 database 非 ok。
- 后端日志出现 asyncpg 或 SQLAlchemy 连接错误。

排查：

```bash
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml logs --tail 200 postgres
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U project_mgmt -d project_mgmt
```

处理：

- 检查 `DATABASE_URL`、`POSTGRES_USER`、`POSTGRES_DB`、密码。
- 检查磁盘是否满。
- 如迁移失败，参考“迁移失败”章节。

## Redis 连接失败

现象：

- `/health` 中 redis 非 ok。
- 登录、限流、token 黑名单异常。

排查：

```bash
docker compose -f docker-compose.prod.yml ps redis
docker compose -f docker-compose.prod.yml logs --tail 200 redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

处理：

- 确认 `REDIS_URL` 指向 `redis://redis:6379/0`。
- 重启 Redis 前先确认是否会影响登录态和限流数据。

## 文件上传失败

现象：

- 上传接口返回 413、400 或 500。
- storage 中没有新文件。

排查：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 backend
docker compose -f docker-compose.prod.yml exec backend python -c "from app.core.config import get_settings; print(get_settings().storage_root)"
```

处理：

- 413：文件超过 `MAX_UPLOAD_SIZE_MB`。
- 400：文件类型或业务规则不满足。
- 500：检查 `STORAGE_ROOT` 权限和磁盘空间。

## Celery 任务不执行

现象：

- 到期任务未提醒。
- 文件清理或审计分区维护未执行。
- 外部通知或 Webhook 重试不推进。
- Grafana 中 Celery 队列持续增长。

排查：

```bash
docker compose -f docker-compose.prod.yml ps celery-worker celery-beat redis
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 celery-beat
```

处理：

```bash
docker compose -f docker-compose.prod.yml restart celery-worker
docker compose -f docker-compose.prod.yml restart celery-beat
```

如果队列堆积超过 100，先暂停非关键写入，确认 worker 消费能力和 Redis 状态。

## 邮件发送失败

现象：

- 用户打开了邮件通知但收不到邮件。
- `notification_deliveries` 中 email delivery 进入 `retry_scheduled` 或 `dead_letter`。

排查：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select channel, status, attempt_count, last_error from notification_deliveries where channel='email' order by updated_at desc limit 20;"
```

处理：

- 确认 `SMTP_ENABLED=true`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_FROM_ADDRESS`、账号密码和 TLS 设置正确。
- 确认用户邮箱不为空，且个人设置中开启了 email channel。
- 如果 SMTP 服务限流或拒信，先修复邮件服务端策略，再等待 Celery 自动重试。

## 企业微信或钉钉发送失败

现象：

- 群机器人没有收到通知。
- delivery 的 `last_error` 包含 webhook returned、request timed out 或 channel disabled。

排查：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select channel, status, attempt_count, last_error from notification_deliveries where channel in ('wework','dingtalk') order by updated_at desc limit 20;"
```

处理：

- 确认 `WEWORK_ENABLED` / `DINGTALK_ENABLED` 已开启。
- 确认 webhook URL 和 secret 来自对应机器人后台，未复制多余空格。
- 钉钉签名依赖 timestamp + secret；企业微信如配置 secret 会追加签名参数。
- 下游恢复后等待自动重试；进入 dead letter 的通知需要按运维流程评估是否补发。

## 病毒扫描失败或文档被隔离

现象：

- 文档长时间停留在“扫描中”。
- 文档显示“已隔离”，下载和预览被拒绝。
- `scan_status=failed`。

排查：

```bash
docker compose -f docker-compose.prod.yml ps clamav celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 clamav
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select doc_no, file_name, scan_status, scan_result, scanned_at from documents order by updated_at desc limit 20;"
```

处理：

- `pending` 长时间不变：检查 `celery-worker` 是否正常，以及 worker 是否能访问 `clamav:3310`。
- `failed`：查看 `scan_result` 和 ClamAV 日志，必要时重启 `clamav` 和 `celery-worker`。
- `infected`：不要手工改库放行，要求用户重新上传确认安全的文件版本。
- 病毒库更新异常时，先恢复 ClamAV 服务并确认日志中不再出现更新错误。

## API Key 调用失败

现象：

- 外部 API 返回 401、403 或 429。
- 对接方只能调用部分接口。

排查：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select name, key_prefix, permissions, expires_at, revoked_at, last_used_at from api_keys order by updated_at desc limit 20;"
docker compose -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'external_api:*'
```

处理：

- 401：确认请求头是 `X-API-Key`，且使用完整 token，不是 key 前缀。
- 403：确认权限包含目标接口需要的 `projects:read`、`payments:read` 或 `documents:read`。
- 429：默认每小时 1000 次；先确认对接方是否循环请求或缺少缓存。
- key 过期或吊销后不会恢复，需新建 key。

## Webhook 重试堆积

现象：

- Webhook 管理页死信数量增加。
- `webhook_deliveries` 中大量 `retry_scheduled` 或 `dead_letter`。

排查：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select event_type, status, attempt_count, response_status, last_error, next_retry_at from webhook_deliveries order by updated_at desc limit 30;"
```

处理：

- 确认接收方 URL 可访问，且 2xx 才表示成功。
- 确认接收方按文档验证 `X-Signature`，签名消息为 `{timestamp}.{event_id}.{canonical_json_body}`。
- 如果下游故障导致大量堆积，先停用对应 endpoint，恢复后再手动重放 dead letter。
- 接收方必须按 `X-Event-Id` 做幂等，避免重试造成重复入账或重复推进。

## 迁移失败

现象：

- `alembic upgrade head` 失败。
- 后端启动后模型字段或表不存在。

排查：

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic current
docker compose -f docker-compose.prod.yml run --rm backend alembic history
docker compose -f docker-compose.prod.yml logs --tail 200 backend
```

处理：

- 不要手工改生产表结构。
- 保留迁移错误日志。
- 如果发布已经影响业务，执行回滚，并按 `docs/disaster-recovery.md` 从上线前备份恢复。

## Grafana 无数据

现象：

- Grafana 仪表盘为空。
- Prometheus target down。

排查：

```bash
curl -fsS http://localhost:8000/metrics
curl -fsS http://localhost:9090/targets
docker compose -f docker-compose.prod.yml logs --tail 200 prometheus
docker compose -f docker-compose.prod.yml logs --tail 200 grafana
```

处理：

- 确认 backend `/metrics` 可访问。
- 确认 `monitoring/prometheus/prometheus.yml` target 使用 Compose 服务名。
- 确认 Grafana datasource 指向 `http://prometheus:9090`。

## 回滚

触发条件：

- 核心链路登录、项目创建、阶段推进、文件上传任一阻断。
- 数据库迁移造成不可接受的数据或结构问题。
- 错误率持续超过告警阈值且短时间无法修复。

步骤：

```bash
docker compose -f docker-compose.prod.yml logs --since 30m > rollback-evidence.log
git checkout <previous-release-tag>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

如需恢复数据，使用上线前备份：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
BACKUP_DIR=./backups/backup-YYYYmmddTHHMMSSZ \
RESTORE_STORAGE_CLEAR=true \
scripts/restore.sh
```
