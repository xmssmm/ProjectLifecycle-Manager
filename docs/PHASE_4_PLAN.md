# Phase 4 规模与合规 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every code task, `superpowers:systematic-debugging` for failures, and `superpowers:verification-before-completion` before claiming completion.

**Goal:** 按 `docs/ROADMAP.md` Phase 4 完成数据归档、多时区、高可用性能、全文检索、批量导入导出，并输出中文部署手册、使用手册和运维材料。

**Architecture:** Phase 4 继续沿用 FastAPI + SQLAlchemy + Alembic + Celery + Redis + PostgreSQL + Vue 3。归档采用同库 `archive_*` 表，全文检索采用 PostgreSQL FTS，多时区使用 IANA timezone，HA 能力以可配置部署拓扑和无状态应用为边界。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic、PostgreSQL FTS、Redis、Celery、Vue 3、Pinia、Element Plus、zoneinfo、pytest、Vitest、Docker Compose。

---

## 1. 默认决策

详见 `docs/PHASE_4_OPEN_QUESTIONS.md`：

- 已结项主项目归档阈值为 `closed_at <= now() - 2 years`。
- Phase 4 归档使用同库 `archive_*` 表，不引入独立归档库。
- 全文检索先使用 PostgreSQL FTS。
- 用户时区使用 IANA timezone 字符串，默认 `Asia/Shanghai`。
- HA 任务以应用可配置能力、生产 compose 示例和中文部署手册为主要交付。

## 2. 任务顺序

### T-4-PLAN-01 Phase 4 计划与决策文档

**Files:**

- Create: `docs/PHASE_4_OPEN_QUESTIONS.md`
- Create: `docs/PHASE_4_PLAN.md`

**Steps:**

- [x] 固化 OQ-19 到 OQ-23 默认决策。
- [x] 按依赖拆分 Phase 4 任务。
- [x] 运行 `git diff --check`。
- [x] 提交并合并到 `develop`。

**DoD:**

- [x] 文档可直接指导后续开发。
- [x] 没有未决项阻塞实现。

### T-4-I18N-01 用户时区字段与显示转换

**Files:**

- Create: `backend/alembic/versions/0028_add_user_timezone.py`
- Modify: `backend/app/models/users.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/users.py`
- Modify: `backend/app/services/users.py`
- Modify: `frontend/src/types/users.ts`
- Modify: `frontend/src/stores/useAuthStore.ts`
- Create: `frontend/src/utils/timezone.ts`
- Test: `backend/tests/unit/test_user_timezone.py`
- Test: `frontend/src/utils/timezone.test.ts`

**Implementation:**

- 给 `users` 增加 `timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai'`。
- 后端用 `zoneinfo.ZoneInfo` 校验写入值；无效值返回 422。
- 认证响应、用户列表、用户详情和用户编辑都返回/支持 `timezone`。
- 前端增加统一时间格式化工具，按当前用户 timezone 渲染 datetime。
- 保持数据库时间字段为 UTC / timezone-aware datetime。

**Test plan:**

- [x] 用户默认时区为 `Asia/Shanghai`。
- [x] 有效 IANA timezone 可写入。
- [x] 无效 timezone 被拒绝。
- [x] 前端同一 UTC 时间在不同时区显示不同本地时间。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_user_timezone.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run test:unit -- timezone`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-4-I18N-02 Celery beat 多时区调度

**Files:**

- Modify: `backend/app/services/task_deadlines.py`
- Modify: `backend/app/services/notifications.py`
- Modify: `backend/app/tasks/celery_app.py`
- Modify: `backend/app/tasks/notifications.py`
- Modify: `backend/app/tasks/task_deadlines.py`
- Test: `backend/tests/unit/test_notification_service.py`
- Test: `backend/tests/unit/test_task_deadline_cron.py`
- Test: `backend/tests/unit/test_celery_app.py`

**Implementation:**

- 计算每个用户当前本地时间，筛选本地 09:00 触发摘要。
- 摘要任务按用户时区分组，避免对每个用户创建独立 beat entry。
- 记录摘要发送窗口，避免 worker 重试导致同一天重复发送。
- 截止日期扫描任务按执行人时区分组，避免固定业务时区 09:00 漏发或早发。

**Test plan:**

- [x] `Asia/Shanghai` 用户在 UTC 01:00 命中本地 09:00。
- [x] `America/New_York` 用户在对应 UTC 时间命中。
- [x] 同一用户同一自然日不会重复发送摘要。
- [x] 截止日期扫描只处理当前本地 09:00 的执行人。
- [x] 摘要与截止日期扫描的 Celery beat 均改为每小时触发，由服务层按用户时区筛选。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_notification_service.py tests/unit/test_task_deadline_cron.py tests/unit/test_celery_app.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-4-DATA-01 归档策略与 archive 表

**Files:**

- Create: `backend/alembic/versions/0029_create_archive_tables.py`
- Create: `backend/app/models/archives.py`
- Create: `backend/app/schemas/archives.py`
- Create: `backend/app/services/archives.py`
- Modify: `backend/app/models/main_projects.py`
- Modify: `backend/app/models/sub_projects.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_archive_service.py`

**Implementation:**

- 新增 `main_projects.closed_at`、`sub_projects.closed_at` 并在结项/关闭时写入。
- 新增 `archive_batches` 和核心 `archive_*` 表，保存关键列与 `snapshot JSONB`。
- 归档候选规则：主项目 `closed`、`closed_at <= now - 2 years`、所有子项目均 `closed` 或 `terminated`。
- 归档事务先写 archive 表，再删除主表对应数据；失败时整体回滚。
- 归档服务返回归档前后主表行数、耗时、批次号，支撑性能量化。

**Test plan:**

- [x] 未关闭、关闭未满 2 年、有活跃子项目的主项目不会进入候选。
- [x] 合格主项目及其子数据写入 archive 表。
- [x] 归档事务失败时主表和 archive 表都不产生半成品。
- [x] 归档结果包含主表行数变化和批次号。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_archive_service.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-4-DATA-02 归档 / 恢复后台操作面板

**Files:**

- Create: `backend/app/api/v1/archives.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `frontend/src/api/archives.ts`
- Create: `frontend/src/stores/useArchiveStore.ts`
- Create: `frontend/src/types/archives.ts`
- Create: `frontend/src/views/admin/ArchiveManagement.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `backend/tests/api/test_archives_api.py`
- Test: `frontend/src/views/admin/ArchiveManagement.test.ts`

**Implementation:**

- admin 可查看归档候选、创建归档批次、查看批次详情、恢复单个主项目。
- 恢复时校验业务唯一键冲突并写入审计日志。
- 前端提供归档候选表、批次历史、恢复确认对话框。
- 归档和恢复操作必须展示影响范围。

**Test plan:**

- [ ] 非 admin 不能归档或恢复。
- [ ] admin 归档成功后写审计日志。
- [ ] 恢复冲突返回 409 和冲突字段。
- [ ] 前端能完成候选查询、归档、恢复主流程。

**Verification:**

- `cd backend && python -B -m pytest -q tests/api/test_archives_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- ArchiveManagement`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-4-SEARCH-01 文档全文索引与搜索接口

**Files:**

- Create: `backend/alembic/versions/0030_create_document_search_entries.py`
- Create: `backend/app/models/search.py`
- Create: `backend/app/schemas/search.py`
- Create: `backend/app/services/document_text_extraction.py`
- Create: `backend/app/services/search.py`
- Create: `backend/app/api/v1/search.py`
- Modify: `backend/app/tasks.py`
- Modify: `backend/app/services/documents.py`
- Create: `frontend/src/api/search.ts`
- Create: `frontend/src/stores/useSearchStore.ts`
- Create: `frontend/src/views/SearchView.vue`
- Test: `backend/tests/unit/test_document_search_service.py`
- Test: `backend/tests/api/test_search_api.py`

**Implementation:**

- 上传或新版本文档保存后排队抽取文本。
- 抽取成功后写入 `document_search_entries` 和 PostgreSQL FTS vector。
- `GET /api/v1/search?q=...&scope=documents` 返回文档、项目、环节、命中摘要。
- 前端新增搜索页，并从导航进入。

**Test plan:**

- [ ] 空查询被拒绝。
- [ ] clean 文档索引后可检索。
- [ ] infected / deleted 文档不进入结果。
- [ ] 抽取失败保留失败状态，不阻塞文档主流程。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_document_search_service.py tests/api/test_search_api.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`
- `cd frontend && npm.cmd run test:unit`

### T-4-DATA-03 项目批量导入

**Files:**

- Create: `backend/app/schemas/imports.py`
- Create: `backend/app/services/project_imports.py`
- Create: `backend/app/api/v1/imports.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `frontend/src/api/imports.ts`
- Create: `frontend/src/views/admin/ProjectImport.vue`
- Test: `backend/tests/unit/test_project_imports.py`
- Test: `backend/tests/api/test_project_imports_api.py`

**Implementation:**

- 提供 Excel 模板下载。
- 导入时逐行校验，失败行不阻塞成功行。
- 返回成功数、失败数、逐行错误、导入批次号。
- 1000 行导入目标时间不超过 60 秒。

**Test plan:**

- [ ] 模板字段完整。
- [ ] 部分失败时成功行落库、失败行返回错误。
- [ ] 重复项目编号被拒绝。
- [ ] 1000 行本地性能基准可记录。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_project_imports.py tests/api/test_project_imports_api.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-4-DATA-04 数据库全量导出

**Files:**

- Create: `backend/app/schemas/exports.py`
- Create: `backend/app/services/database_exports.py`
- Create: `backend/app/api/v1/exports.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `frontend/src/api/exports.ts`
- Create: `frontend/src/views/admin/DatabaseExport.vue`
- Test: `backend/tests/unit/test_database_exports.py`
- Test: `backend/tests/api/test_database_exports_api.py`

**Implementation:**

- admin 可发起全库导出任务。
- 导出包包含 CSV/Excel、manifest、外键说明和生成审计信息。
- 大导出异步执行，并提供任务状态和下载地址。

**Test plan:**

- [ ] 非 admin 被拒绝。
- [ ] manifest 包含表、行数、生成时间、操作者。
- [ ] 外键引用能在导出包中追踪。
- [ ] 审计日志记录导出发起和下载。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_database_exports.py tests/api/test_database_exports_api.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-4-PERF-04 关键查询性能优化

**Files:**

- Create: `backend/app/services/query_metrics.py`
- Create: `docs/PERFORMANCE_BASELINE.md`
- Modify: relevant Alembic migrations for indexes or materialized views
- Test: targeted service tests for optimized queries

**Implementation:**

- 记录主项目列表、子项目列表、仪表盘、报表、文档查询的 baseline。
- 使用索引、查询改写或物化视图优化 P99。
- 文档中记录优化前后指标和复测命令。

**Test plan:**

- [ ] 关键查询保留权限过滤。
- [ ] 新索引/视图不会改变结果集。
- [ ] baseline 与优化后指标写入文档。

**Verification:**

- `cd backend && python -B -m pytest -q`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-4-PERF-01 / 02 / 03 生产高可用部署能力

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/db/session.py`
- Modify: `backend/app/core/redis.py`
- Modify: `docker-compose.prod.yml`
- Create: `docs/PRODUCTION_HA_DEPLOYMENT.md`
- Test: `backend/tests/unit/test_ha_config.py`

**Implementation:**

- 支持可选 PostgreSQL replica URL，读密集服务可注入只读 session。
- 支持 Redis Sentinel 配置，并保留单机 Redis fallback。
- 生产 compose 示例支持 API/worker 多副本、健康检查和滚动发布说明。
- 文档覆盖 PostgreSQL 主从提升、Redis 故障切换、应用水平扩展和回滚步骤。

**Test plan:**

- [ ] 未配置 HA 时保持现有单机行为。
- [ ] 配置 replica URL 时生成只读连接。
- [ ] Redis Sentinel 配置解析正确。
- [ ] compose 配置可通过 `docker compose config`。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_ha_config.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `docker compose -f docker-compose.prod.yml config`

### T-4-I18N-03 中英文国际化

**Files:**

- Modify: `frontend/package.json`
- Create: `frontend/src/i18n/index.ts`
- Create: `frontend/src/i18n/locales/zh-CN.ts`
- Create: `frontend/src/i18n/locales/en-US.ts`
- Modify: frontend views and components with user-facing text
- Test: `frontend/src/i18n/i18n.test.ts`

**Implementation:**

- 集成 vue-i18n。
- 抽离核心导航、表单、按钮、状态、错误提示、管理页面文案。
- 用户可切换中英文，默认中文。

**Test plan:**

- [ ] 默认中文可用。
- [ ] 切换英文后核心页面显示英文文案。
- [ ] 状态枚举映射不丢失。

**Verification:**

- `cd frontend && npm.cmd run test:unit -- i18n`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`
- `cd frontend && npm.cmd run build`

### T-4-DOCS-01 中文部署、使用、运维手册

**Files:**

- Create: `docs/PRODUCTION_DEPLOYMENT_MANUAL.md`
- Create: `docs/USER_MANUAL.md`
- Create: `docs/ADMIN_OPERATIONS_MANUAL.md`
- Create: `docs/PHASE_4_RELEASE_NOTES.md`
- Modify: `docs/PHASE_4_PLAN.md`

**Implementation:**

- 部署手册覆盖生产发布、环境变量、迁移、回滚、Docker、HA、备份恢复。
- 使用手册覆盖业务角色、项目流程、文档、通知、搜索、导入导出。
- 运维手册覆盖归档、恢复、审计、全文索引、任务队列、故障排查。
- Phase 4 所有任务完成后勾选验收清单。

**Verification:**

- `git diff --check`
- `cd backend && python -B -m pytest -q`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`
- `cd frontend && npm.cmd run test:unit`
- `cd frontend && npm.cmd run build`
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.prod.yml config`

## 3. Phase 4 总体验收

- [ ] Phase 4 全部计划任务完成并合并到 `develop`。
- [ ] 后端 ruff、mypy、pytest 全量通过。
- [ ] 前端 lint、typecheck、unit test、build 全量通过。
- [ ] 生产 compose 配置通过。
- [ ] 中文部署手册、使用手册、运维手册可直接交付试用。
- [ ] 归档、恢复、全文检索、批量导入导出均有审计或操作记录。
- [ ] 发布前 review 完成，关键风险有记录。
