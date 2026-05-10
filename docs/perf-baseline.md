# T-1-TEST-04 性能基线报告

## 目标

- 使用 Locust 进行 50 并发压测。
- 覆盖操作：登录、查项目列表、上传文档、推进环节、新增付款。
- NFR：核心业务接口 P99 <= 800ms；超过 SLA 的接口进入 fix 清单。

## 脚本

- Locust 脚本：`backend/perf/locustfile.py`
- 默认目标：`http://localhost:8000`
- 默认账号：`admin / ChangeMe123!`
- 脚本会通过 API 准备性能测试部门、用户、主项目、子项目、付款与可推进环节池。

推荐命令：

```powershell
cd C:\management\backend
python -m locust -f perf\locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 3m --csv ..\docs\perf-baseline
```

## 本轮结果

执行时间：2026-05-11 01:40 Asia/Hong_Kong

执行环境：

- 本机临时后端：`http://127.0.0.1:8010`
- 数据库/Redis：Docker Compose 开发栈中的 PostgreSQL 16 + Redis 7
- 后端限流：`RATE_LIMIT_PER_MINUTE=100000`，避免 50 并发压测被默认 100/min 限流干扰
- 并发模型：50 users，spawn rate 10/s，运行 90s
- 结果文件：`docs/perf-baseline_stats.csv`、`docs/perf-baseline_failures.csv`
- 备注：开发容器内执行 `alembic upgrade head` 时缺少 `alembic.ini/alembic`，本轮改用本机后端进程连接同一 Docker 数据库执行迁移和压测。

| 操作 | Locust name | P99 | 结论 |
| --- | --- | --- | --- |
| 登录 | `POST /auth/login` | 2400ms | 未达标 |
| 查项目列表 | `GET /main-projects` | 1900ms | 未达标 |
| 上传文档 | `POST /documents` | 2700ms | 未达标 |
| 推进环节 | `POST /phases/{id}/promote` | 1700ms | 未达标 |
| 新增付款 | `POST /sub-projects/{id}/payments` | 3400ms | 未达标 |

本轮业务请求 1681 次，失败 0 次。所有核心操作 P99 均高于 800ms，因此 T-1-TEST-04 的结论是：功能稳定性通过，性能 SLA 未通过，需进入优化队列。

## fix 清单

| 接口 | 问题 | 处理状态 |
| --- | --- | --- |
| `POST /sub-projects/{id}/payments` | P99 3400ms。付款创建串行更新子/主项目聚合金额并写凭证文档，热点明显。 | 待优化 |
| `POST /documents` | P99 2700ms。文档上传写文件、校验、版本维护、DB 提交同路；并发同 doc_type 的唯一约束竞态已修复。 | 待优化 |
| `POST /auth/login` | P99 2400ms。bcrypt 校验在 50 并发下 CPU 压力明显。 | 待优化 |
| `GET /main-projects` | P99 1900ms。列表查询需检查索引、分页、序列化与连接池等待。 | 待优化 |
| `POST /phases/{id}/promote` | P99 1700ms。推进环节包含文档完整性检查、状态变更、通知写入。 | 待优化 |
| 开发 Docker backend | 容器镜像缺少 Alembic 配置，`docker compose exec backend alembic upgrade head` 无法执行。 | 待修复 |
