# 日常运维手册

本文面向首次接手系统的运维人员，覆盖添加 admin、查日志、清缓存、Celery 重启、备份、监控巡检等日常动作。

## 环境入口

所有生产命令默认在仓库根目录执行：

```bash
docker compose -f docker-compose.prod.yml ps
```

先确认服务状态，再做变更。

## 添加 admin

推荐通过后端 seed 或管理命令创建管理员。执行前先确认 `.env` 中数据库连接正确：

```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m app.seeds.default_admin
```

创建后立即登录系统修改默认密码。如果需要临时重置密码，应在审计记录中写明原因、执行人、时间。

## 查日志

查看所有服务最近日志：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200
```

查看单个服务：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 backend
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 nginx
```

跟随日志：

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

## 清缓存

Redis 中包含限流、登录失败计数、token 黑名单等缓存。清缓存前必须确认影响范围。

进入 Redis：

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

查看 key：

```bash
redis-cli -u redis://redis:6379/0 KEYS 'rate_limit:*'
redis-cli -u redis://redis:6379/0 KEYS 'auth:*'
redis-cli -u redis://redis:6379/0 KEYS 'oauth:state:*'
redis-cli -u redis://redis:6379/0 KEYS 'external_api:*'
```

清理单类 key 示例：

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'rate_limit:*' | xargs -r docker compose -f docker-compose.prod.yml exec -T redis redis-cli DEL
```

不要在生产环境随意执行 `FLUSHALL`。

## Celery 重启

重启 worker：

```bash
docker compose -f docker-compose.prod.yml restart celery-worker
```

重启 beat：

```bash
docker compose -f docker-compose.prod.yml restart celery-beat
```

检查任务日志：

```bash
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
docker compose -f docker-compose.prod.yml logs --tail 200 celery-beat
```

当前定时任务包括：

- 每日 09:00：任务到期/逾期扫描。
- 每日 09:00：通知每日摘要生成。
- 每 60 秒：外部通知 delivery 重试。
- 每 60 秒：Webhook delivery 重试。
- 每周一 03:00：文件清理。
- 每月 1 日 00:30：审计日志分区维护。
- 每日 03:30：过期报表清理。

如果用户反馈报表长时间生成中、每日摘要未发送、任务逾期未提醒，先检查 `celery-worker` 和 `celery-beat` 日志。

## SSO 运维

确认 provider 是否对前端可见：

```bash
curl -fsS http://localhost:8000/api/v1/oauth/providers
```

常规检查点：

- `.env` 中 `OAUTH_GENERIC_ENABLED=true`，且 client、authorize、token、userinfo、redirect URI 配置完整。
- 企业 IdP 后台登记的 redirect URI 与 `.env` 完全一致。
- 用户本地账号已存在，邮箱与企业账号一致，或用户已在个人页完成绑定。
- admin 将用户设置为“仅 SSO”前，应确认用户已有可用绑定。

排查绑定数据时可在数据库中查看 `oauth_bindings`，不要手工改 token 字段：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select user_id, provider, email, created_at, updated_at from oauth_bindings order by updated_at desc limit 20;"
```

## 外部通知通道运维

邮件、企业微信、钉钉通道由 `.env` 控制，用户还需要在个人设置中打开对应 channel。外部通道失败不会阻断站内通知。

检查最近投递：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select channel, scenario, status, attempt_count, last_error, next_retry_at from notification_deliveries order by updated_at desc limit 20;"
```

进入 `dead_letter` 后系统会给 admin 生成站内告警。处理步骤：

1. 根据 `channel` 和 `last_error` 修复 SMTP、企业微信或钉钉配置。
2. 查看 `celery-worker` 日志确认通道恢复。
3. 如需重发，先通过业务补发或数据库审计流程确认影响范围；不要直接改投递状态绕过审计。

## ClamAV 运维

ClamAV 是独立 compose 服务，后端和 worker 通过 TCP 3310 访问：

```bash
docker compose -f docker-compose.prod.yml ps clamav
docker compose -f docker-compose.prod.yml logs --tail 200 clamav
docker compose -f docker-compose.prod.yml logs --tail 200 celery-worker
```

查看最近扫描结果：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select doc_no, file_name, scan_status, scan_result, scanned_at from documents order by updated_at desc limit 20;"
```

测试环境可用 EICAR 文件验证隔离；生产环境只做日志、服务状态和少量非业务样本检查。`infected` 文档不要手工改回 `clean`，应重新上传确认安全的文件版本。

## API Key 与外部只读 API 运维

API Key 由 admin 在页面签发。token 只展示一次；遗失后应吊销旧 key 并新建。外部请求使用 `X-API-Key` header，接口前缀为 `/api/external/v1`。

检查 key 和限流：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select name, key_prefix, permissions, expires_at, revoked_at, last_used_at from api_keys order by updated_at desc limit 20;"
docker compose -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'external_api:*'
```

默认限流是每个 API Key 每小时 1000 次。若外部系统被 429 限制，先确认是否为异常循环请求，再决定是否临时暂停该 key。

## Webhook 运维

Webhook 由 admin 在页面配置 URL、secret 和订阅事件。系统每次推送会生成 delivery，失败后由 Celery 每 60 秒扫描重试。

检查最近投递：

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U project_mgmt -d project_mgmt -c "select event_type, status, attempt_count, response_status, last_error, next_retry_at from webhook_deliveries order by updated_at desc limit 20;"
```

运维处理顺序：

1. 确认 endpoint 仍启用、URL 可从后端容器访问。
2. 让接收方按 `X-Event-Id` 做幂等，避免重试造成重复处理。
3. 对接方修复后，在“Webhook 管理”页重放 dead letter。
4. 如果大量堆积，先停用异常 endpoint，再恢复下游服务。

## 报表文件维护

报表文件默认保留 7 天，由 Celery 定时清理。若磁盘压力异常，先查看报表任务和 storage 占用：

```bash
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from pathlib import Path
root = Path('/app/storage')
total = sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
print(f'storage bytes={total}')
PY
```

不要直接删除数据库中仍引用的报表或文档文件；需要人工清理时先做备份。

## 备份

每日备份命令：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
POSTGRES_USER=project_mgmt \
POSTGRES_DB=project_mgmt \
STORAGE_ROOT=./storage \
scripts/backup.sh
```

恢复流程见 `docs/disaster-recovery.md`，恢复前必须停止写入流量。

## 监控巡检

- Prometheus：`http://localhost:9090/targets`
- Grafana：`http://localhost:3000`
- 后端健康：`http://localhost:8000/health`
- 后端指标：`http://localhost:8000/metrics`

Grafana 每日重点看：

- API 性能：P99 是否超过 1.5s。
- Celery 队列：是否堆积超过 100。
- DB 连接池：连接数是否接近上限。
- 磁盘：剩余空间是否低于 20%。

## 常规维护节奏

- 每日：检查 `/health`、Grafana、Celery 队列、磁盘。
- 每周：抽查备份产物并执行一次小规模恢复验证。
- 每月：检查依赖漏洞扫描报告，评估 Vite/Vitest/esbuild 等 moderate 漏洞升级。
