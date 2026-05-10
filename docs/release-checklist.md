# 上线 Checklist

任务：T-1-DEPLOY-04 上线 checklist + 运维文档。

本文用于生产发布前后逐项确认。每一项完成后在发布记录里写入执行人、时间、命令输出摘要。

## 1. 发布前冻结

- 确认 `develop` 或发布分支已合并完目标版本代码。
- 确认没有未提交变更：`git status --short --branch`。
- 确认 `.env` 已按生产环境填写，不提交到 Git。
- 确认 `GRAFANA_ADMIN_PASSWORD`、数据库密码、JWT 密钥、OSS 凭据不使用默认值。

## 2. 构建与基础检查

```bash
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build
```

本地质量门：

```bash
cd backend
python -B -m ruff check .
python -B -m mypy app tests
python -B -m pytest -q
```

前端：

```bash
cd frontend
npm ci
npm run build
```

## 3. 数据库迁移

上线前必须先完成数据库迁移：

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

如果迁移失败，停止上线，保留日志并进入“回滚预案”。

## 4. seed

确认默认部门、管理员、阶段模板等 seed 已执行：

```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m app.seeds.run
```

验证默认管理员可以登录，并在首次登录后修改默认密码。

## 5. 备份

上线前做一次完整备份，确认 `db.dump`、`storage.tar.gz`、`manifest.json` 均生成：

```bash
BACKUP_DB_MODE=compose \
COMPOSE_FILE=docker-compose.prod.yml \
POSTGRES_USER=project_mgmt \
POSTGRES_DB=project_mgmt \
STORAGE_ROOT=./storage \
scripts/backup.sh
```

备份路径写入发布记录。需要远端备份时配置 `OSS_BUCKET` / `OSS_PREFIX`，并按 `docs/disaster-recovery.md` 执行 OSS 占位替换。

## 6. 启动服务

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

所有核心服务必须为 healthy 或 running：`postgres`、`redis`、`backend`、`frontend`、`nginx`、`celery-worker`、`celery-beat`、`prometheus`、`grafana`。

## 7. 健康检查

```bash
curl -fsS https://localhost/health
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/metrics
```

`/health` 必须返回整体 `ok`；`/metrics` 必须包含 `http_requests_total` 和 `http_request_duration_seconds_bucket`。

## 8. 监控

- Prometheus：打开 `http://localhost:9090/targets`，确认 backend、celery、postgres、node 均为 UP。
- Grafana：打开 `http://localhost:3000`，确认 `Project Management` 文件夹下四个仪表盘存在。
- 仪表盘：API 性能、Celery 队列、DB 连接池、磁盘。

## 9. 告警

确认 `monitoring/prometheus/alerts.yml` 已被 Prometheus 加载，并包含：

- API P99 > 1.5s
- API 错误率 > 1%
- Celery 队列堆积 > 100

```bash
curl -fsS http://localhost:9090/api/v1/rules
```

## 10. 冒烟测试

- 管理员登录。
- 创建主项目、子项目。
- 上传一个小附件。
- 推进一个阶段。
- 创建一笔付款。
- 查看通知中心和审计日志。

## 11. 回滚预案

如果发布后出现阻断问题：

1. 停止写入流量或切回旧版本入口。
2. 保留日志：`docker compose -f docker-compose.prod.yml logs --since 30m > release-failure.log`。
3. 回退镜像或代码到上一版本。
4. 如数据库已发生不可逆变更，按 `docs/disaster-recovery.md` 使用上线前备份恢复。
5. 恢复后重新执行 `/health`、`/metrics`、核心业务冒烟测试。

回滚命令示例：

```bash
git checkout <previous-release-tag>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```
