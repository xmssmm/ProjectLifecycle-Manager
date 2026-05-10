# 监控接入说明

## 组件

- FastAPI：暴露 `/metrics`，采集请求耗时、QPS、状态码错误率、进行中请求数。
- Prometheus：读取 `monitoring/prometheus/prometheus.yml`，抓取 backend、Celery exporter、PostgreSQL exporter、node exporter。
- Grafana：自动加载 Prometheus datasource 和 4 个仪表盘：API 性能、Celery 队列、DB 连接池、磁盘。
- 告警规则：`monitoring/prometheus/alerts.yml` 提供 P99 > 1.5s、错误率 > 1%、队列堆积 > 100 的示例规则。

## 启动

```powershell
docker compose -f docker-compose.prod.yml up -d prometheus grafana celery-exporter postgres-exporter node-exporter
```

默认访问地址：

- Prometheus：`http://localhost:9090`
- Grafana：`http://localhost:3000`

Grafana 默认账号来自环境变量 `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`，未配置时为 `admin` / `change-me`。生产环境必须在 `.env` 中覆盖默认密码。

## 验证

```powershell
Invoke-WebRequest http://localhost:8000/metrics
Invoke-WebRequest http://localhost:9090/-/ready
Invoke-WebRequest http://localhost:3000/api/health
```

进入 Grafana 后应能看到 `Project Management` 文件夹下的 4 个仪表盘。
