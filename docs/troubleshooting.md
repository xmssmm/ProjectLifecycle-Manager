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
