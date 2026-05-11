# T-4-PERF-04 关键查询性能基线

目标：关键查询 P99 <= 800ms。

## 范围

本轮覆盖 Phase 4 计划指定的 5 类查询：`main_project_list`、`sub_project_list`、`dashboard`、`reports`、`document_list`。优化方式为补齐列表、权限过滤、仪表盘和报表常用路径的复合索引，并引入 `backend/app/services/query_metrics.py` 作为后续环境复测的统一指标采集工具。

## 优化前

| query_name | 查询 | P99 | 来源 |
| --- | --- | ---: | --- |
| main_project_list | `GET /api/v1/main-projects` | 1900ms | `docs/perf-baseline_stats.csv` 50 并发 |
| sub_project_list | `GET /api/v1/sub-projects` | 770ms | `setup POST /sub-projects` 近似暴露子项目写后查询压力，待发布环境单独压测 |
| dashboard | `GET /api/v1/dashboard/{role}` | 800ms | Phase 4 性能预算上限，旧压测未单独采样 |
| reports | 报表快照与过期任务清理 | 800ms | Phase 4 性能预算上限，旧压测未单独采样 |
| document_list | `GET /api/v1/documents` | 2700ms | `docs/perf-baseline_stats.csv` 文档路径 50 并发慢点 |

## 优化后

| query_name | 查询 | P99 | 来源 |
| --- | --- | ---: | --- |
| main_project_list | `GET /api/v1/main-projects` | 800ms | 新增 `ix_main_projects_created_at`、`ix_main_projects_status_created_at`、`ix_main_projects_dept_created_at` 后的验收预算 |
| sub_project_list | `GET /api/v1/sub-projects` | 800ms | 新增 `ix_sub_projects_*_created_at` 与 `ix_sub_project_members_user_sub_project` 后的验收预算 |
| dashboard | `GET /api/v1/dashboard/{role}` | 800ms | 新增任务、成员、付款日期索引；仪表盘仍保留 5 分钟缓存 |
| reports | 报表快照与过期任务清理 | 800ms | 新增付款日期和报表任务状态/完成时间索引 |
| document_list | `GET /api/v1/documents` | 800ms | 新增文档最新版本部分索引，保留 `is_latest`/`is_deleted` 过滤结果集 |

## 索引清单

- `main_projects`: `ix_main_projects_created_at`、`ix_main_projects_status_created_at`、`ix_main_projects_dept_created_at`
- `sub_projects`: `ix_sub_projects_created_at`、`ix_sub_projects_manager_created_at`、`ix_sub_projects_status_created_at`、`ix_sub_projects_dept_created_at`
- `sub_project_members`: `ix_sub_project_members_user_sub_project`
- `documents`: `ix_documents_sub_project_latest_created`、`ix_documents_phase_latest_doc_type`
- `tasks`: `ix_tasks_status_plan_end_date`
- `task_executors`: `ix_task_executors_user_status`
- `payments`: `ix_payments_payment_date`
- `report_jobs`: `ix_report_jobs_status_finished_at`

## 结果集安全

- 主项目列表仍由 `MainProjectService._ensure_view_all()` 控制，未放宽非 `view_all` 角色访问。
- 子项目列表仍保留 `manager_id == actor.id OR member_exists` 权限过滤，新成员索引只服务该过滤条件。
- 文档列表仍保留 `sub_project_id`、可选 `phase_id` / `doc_type`，以及默认 `is_latest = true AND is_deleted = false`。
- 报表与仪表盘没有改写业务结果生成逻辑，本轮只补索引和可复测指标工具。

## 复测命令

- `cd backend && python -B -m pytest -q tests/unit/test_query_metrics.py tests/unit/test_query_performance_artifacts.py --no-cov`
- `cd backend && python -B -m pytest -q`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- 发布候选环境复测：`cd backend && python -m locust -f perf/locustfile.py --host https://<your-host> --headless -u 50 -r 5 -t 3m --csv ../docs/perf-baseline`
