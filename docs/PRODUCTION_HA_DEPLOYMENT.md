# 生产高可用部署手册

本文面向生产试用环境，说明 PostgreSQL 主从、Redis Sentinel、应用水平扩展、滚动发布和回滚步骤。默认 `docker-compose.prod.yml` 仍可单机运行；只有配置对应环境变量时才启用 HA 能力。

## 1. 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 主库写连接 | `postgres` 服务 |
| `DATABASE_REPLICA_URL` | PostgreSQL 只读副本连接；为空时读写都走主库 | 空 |
| `REDIS_URL` | 单机 Redis fallback | `redis://redis:6379/0` |
| `REDIS_SENTINEL_ENABLED` | 是否启用 Redis Sentinel | `false` |
| `REDIS_SENTINEL_HOSTS` | Sentinel 地址，格式：`host1:26379,host2:26379` | 空 |
| `REDIS_SENTINEL_MASTER_NAME` | Sentinel 监控的 master 名称 | `mymaster` |
| `REDIS_SENTINEL_DB` | Redis DB 编号 | `0` |
| `REDIS_SENTINEL_PASSWORD` | Redis/Sentinel 密码 | 空 |
| `BACKEND_REPLICAS` | API 副本数 | `2` |
| `CELERY_WORKER_REPLICAS` | Celery worker 副本数 | `2` |

## 2. PostgreSQL 主从

生产推荐由云数据库或运维平台提供 PostgreSQL 主从复制。应用侧只需要：

1. 将 `DATABASE_URL` 指向主库，用于写入、迁移、后台任务写操作。
2. 将 `DATABASE_REPLICA_URL` 指向只读副本，用于后续读密集服务注入只读 session。
3. 发布前确认副本延迟在业务可接受范围内，建议小于 5 秒。
4. 主库故障时，先由数据库平台完成副本提升，再把 `DATABASE_URL` 指向新主库。

当前代码保留单机 fallback：不配置 `DATABASE_REPLICA_URL` 时，`ReadOnlyAsyncSessionLocal` 与主库 session 使用同一连接池。

## 3. Redis Sentinel

启用 Sentinel 时配置：

```env
REDIS_SENTINEL_ENABLED=true
REDIS_SENTINEL_HOSTS=redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379
REDIS_SENTINEL_MASTER_NAME=management-master
REDIS_SENTINEL_DB=0
REDIS_SENTINEL_PASSWORD=<password>
```

API 限流、登录失败计数、Token 黑名单、OAuth state、Dashboard cache、健康检查和 Celery broker/result backend 都会通过 Sentinel 解析 master。若 `REDIS_SENTINEL_ENABLED=false`，系统继续使用 `REDIS_URL` 单机 Redis。

故障切换验证：

1. 停止当前 Redis master。
2. 观察 Sentinel 将 replica 提升为新 master。
3. 调用 `/health`，确认 `redis=ok`。
4. 登录、刷新 token、Dashboard 读取和 Celery smoke task 均应恢复。

## 4. 水平扩展

`docker-compose.prod.yml` 已为 API 和 Celery worker 提供副本参数：

```powershell
$env:BACKEND_REPLICAS="2"
$env:CELERY_WORKER_REPLICAS="2"
docker compose -f docker-compose.prod.yml up -d --build
```

注意事项：

- API 服务必须保持无状态，文件统一写入共享 `storage` 或对象存储。
- `celery-beat` 只能保留 1 个副本，避免重复触发定时任务。
- Nginx 继续通过服务名 `backend:8000` 代理 API。
- 后台 worker 可水平扩展，任务幂等性由各业务服务和唯一约束保护。

## 5. 滚动发布

推荐流程：

1. 拉取新版本代码，先运行 `docker compose -f docker-compose.prod.yml config`。
2. 备份数据库，并确认对象存储/本地 `storage` 有快照。
3. 执行数据库迁移。
4. 执行 `docker compose -f docker-compose.prod.yml up -d --build backend celery-worker frontend nginx`。
5. 观察 `/health`、`/metrics`、Celery worker 日志和 Nginx 访问日志。
6. 执行业务冒烟：登录、项目列表、文档上传、搜索、导入、导出、归档恢复。

## 6. 回滚

回滚前先判断是否包含不可逆数据库迁移：

1. 如果只有应用代码问题，切回上一版本镜像或上一提交，再执行 `docker compose -f docker-compose.prod.yml up -d --build`。
2. 如果包含数据库迁移，先评估 Alembic downgrade 是否安全；涉及数据变更时优先恢复备份到新实例验证。
3. Redis Sentinel 故障时，可临时设置 `REDIS_SENTINEL_ENABLED=false` 并指向单机 `REDIS_URL`，恢复后再切回 Sentinel。
4. PostgreSQL 主库提升失败时，停止写入口，恢复最近备份或由 DBA 重新指定 `DATABASE_URL`。

## 7. 验证命令

```powershell
cd C:\management
docker compose -f docker-compose.prod.yml config

cd C:\management\backend
python -B -m pytest -q tests/unit/test_ha_config.py --no-cov
python -B -m ruff check .
python -B -m mypy app tests
```
