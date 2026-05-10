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
