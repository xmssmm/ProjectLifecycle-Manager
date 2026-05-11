# Phase 5 平台化与智能化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every code task, `superpowers:systematic-debugging` for failures, and `superpowers:verification-before-completion` before claiming completion.

**Goal:** 按 `docs/ROADMAP.md` Phase 5 完成工作流自定义、自定义报表、多项目类型与跨项目分析、AI 辅助能力，让系统从单一采购项目工具演进为可配置平台。

**Architecture:** Phase 5 在现有 FastAPI + SQLAlchemy + Alembic + Celery + Redis + PostgreSQL + Vue 3 架构上增加三层平台能力：可版本化工作流模板、白名单数据集驱动的报表设计器、默认关闭且可审计的 AI provider。现有采购项目流程保持兼容，新增能力通过显式项目类型、模板版本和配置入口逐步接入。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic、PostgreSQL JSONB、Redis、Celery、Vue 3、Pinia、Element Plus、ECharts、pytest、Vitest、Docker Compose。

---

## 1. 默认决策

详见 `docs/PHASE_5_OPEN_QUESTIONS.md`：

- Phase 5 引入多项目类型与工作流模板版本，现有采购 6 环节作为内置默认模板。
- 自定义报表采用内置轻量设计器，不引入外部 BI 运行时依赖。
- AI provider 默认关闭，测试使用 fake provider，生产可配置 OpenAI-compatible 或私有化模型网关。
- AI 场景先做项目风险评分、文档类型建议和自然语言指标问答；智能催办先输出建议，不自动改发送时机。

## 2. 任务顺序

### T-5-PLAN-01 Phase 5 计划与决策文档

**Files:**

- Create: `docs/PHASE_5_OPEN_QUESTIONS.md`
- Create: `docs/PHASE_5_PLAN.md`
- Modify: `README.md`

**Steps:**

- [x] 固化 OQ-23 到 OQ-26 默认决策。
- [x] 按依赖拆分 Phase 5 任务。
- [x] 将 Phase 5 文档加入 README 文档索引。
- [x] 运行 `git diff --check`。
- [x] 提交并合并到 `develop`。

**DoD:**

- [x] 文档可直接指导后续开发。
- [x] 没有未决项阻塞实现。

### T-5-WF-01 项目类型与工作流模板数据模型

**Files:**

- Create: `backend/alembic/versions/0033_create_workflow_templates.py`
- Create: `backend/app/models/project_types.py`
- Create: `backend/app/models/workflows.py`
- Create: `backend/app/schemas/workflows.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/main_projects.py`
- Modify: `backend/app/models/sub_projects.py`
- Test: `backend/tests/unit/test_workflow_models.py`

**Implementation:**

- 新增 `project_types`，字段包含 `code`、`name`、`description`、`is_builtin`、`is_active`。
- 新增 `workflow_templates`，字段包含 `project_type_id`、`name`、`description`、`status`、`created_by_id`。
- 新增 `workflow_template_versions`，字段包含 `template_id`、`version_no`、`status`、`phase_definitions JSONB`、`published_at`。
- `phase_definitions` 使用数组保存 `key`、`name`、`order`、`required_documents`、`allow_parallel`、`entry_rules`。
- `main_projects` 增加 `project_type_id`，`sub_projects` 增加 `workflow_template_version_id`。

**Test plan:**

- [x] 内置采购项目类型 code 唯一。
- [x] 模板版本同一模板下 `version_no` 唯一。
- [x] `phase_definitions` 缺少 key、name、order 时校验失败。
- [x] 已发布版本不可被原地修改。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_workflow_models.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-5-WF-02 默认采购模板迁移与 Seed

**Files:**

- Create: `backend/app/seeds/workflow_templates.py`
- Modify: `backend/app/seeds/run.py`
- Modify: `backend/app/schemas/workflows.py`
- Create: `backend/tests/unit/test_workflow_seed.py`
- Create: `backend/tests/api/test_workflow_migration_compat.py`

**Implementation:**

- Seed 创建内置 `procurement` 项目类型。
- Seed 创建内置采购模板 `procurement-default` 和版本 `procurement-v1`。
- 将现有 6 个固定环节和必传文档要求写入 `phase_definitions`。
- 迁移时把已有主项目绑定到 `procurement`，已有子项目绑定到 `procurement-v1`。
- Seed 重复执行保持幂等，不重复创建模板版本。

**Test plan:**

- [x] 干净库执行 seed 后存在采购项目类型和默认采购流程版本。
- [x] 重复 seed 不重复写入项目类型、模板和版本。
- [x] 旧主项目和旧子项目缺少平台化字段时由 seed 回填到默认采购类型与模板版本。
- [x] 默认采购模板仍返回原有 6 环节顺序。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_workflow_seed.py tests/api/test_workflow_migration_compat.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-5-WF-03 工作流模板管理 API 与前端

**Files:**

- Create: `backend/app/api/v1/workflows.py`
- Create: `backend/app/services/workflows.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/workflows.ts`
- Create: `frontend/src/stores/useWorkflowStore.ts`
- Create: `frontend/src/types/workflows.ts`
- Create: `frontend/src/views/admin/WorkflowTemplateManagement.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Test: `backend/tests/api/test_workflows_api.py`
- Test: `frontend/tests/workflows-api.test.ts`
- Test: `frontend/tests/workflow-template-page.test.ts`

**Implementation:**

- admin 可创建项目类型、创建模板草稿、编辑草稿环节、发布模板版本、停用项目类型。
- 发布时校验环节 key 唯一、order 连续、必传文档类型合法。
- 已发布版本只读，编辑已发布模板会创建新的草稿版本。
- 前端提供项目类型列表、模板版本列表、环节编辑表格和发布确认。
- 所有写操作接入审计日志。

**Test plan:**

- [x] 非 admin 访问模板管理接口返回 403。
- [x] 无效环节定义发布失败并返回字段级错误。
- [x] 已发布版本不可直接修改。
- [x] 前端可完成项目类型创建、草稿环节编辑入口、发布和查看版本历史。

**Verification:**

- `cd backend && python -B -m pytest -q tests/api/test_workflows_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- workflows-api workflow-template-page`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-WF-04 动态环节生成与推进规则

**Files:**

- Modify: `backend/app/services/sub_projects.py`
- Modify: `backend/app/services/phases.py`
- Modify: `backend/app/schemas/sub_projects.py`
- Modify: `frontend/src/types/projects.ts`
- Test: `backend/tests/unit/test_sub_project_management.py`
- Test: `backend/tests/unit/test_sub_project_review_flow.py`
- Test: `backend/tests/unit/test_phase_promote.py`

**Implementation:**

- 新建子项目时显式记录所选模板版本；未显式选择且主项目已有项目类型时，自动绑定该项目类型最新已发布模板版本。
- 子项目审核通过后根据 `phase_definitions` 动态生成环节，不再只依赖硬编码 6 环节。
- 必传文档校验读取模板版本快照，支持不同项目类型不同文档要求。
- 环节推进仍保持现有状态机和审计日志，新增模板版本上下文。
- 采购项目不显式选择项目类型时继续走默认采购模板。

**Test plan:**

- [x] 采购子项目仍生成 6 个默认环节。
- [x] 自定义 3 环节模板生成 3 个环节且顺序正确。
- [x] 自定义必传文档缺失时推进被拒。
- [x] 模板发布新版本后，旧子项目推进仍使用旧版本规则。
- [x] 主项目绑定项目类型时，新建子项目自动选择该类型最新已发布模板版本。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_sub_project_management.py tests/unit/test_sub_project_review_flow.py tests/unit/test_phase_promote.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd backend && python -B -m compileall -q app tests alembic`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-REPORT-01 自定义报表数据集注册表与安全查询编译器

**Files:**

- Create: `backend/app/models/custom_reports.py`
- Create: `backend/app/schemas/custom_reports.py`
- Create: `backend/app/services/report_datasets.py`
- Create: `backend/app/services/report_query_compiler.py`
- Create: `backend/alembic/versions/0034_create_custom_reports.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_report_datasets.py`
- Test: `backend/tests/unit/test_report_query_compiler.py`

**Implementation:**

- 注册项目概览、任务逾期、付款执行、文档上传和风险评分 5 个白名单数据集。
- 每个 dataset 定义字段、字段类型、可筛选操作、可聚合指标和默认 RBAC 范围。
- 查询配置 JSON 包含 `dataset`、`dimensions`、`metrics`、`filters`、`sort`、`limit`。
- 编译器只接受注册字段，不接受 SQL 字符串。
- 编译结果强制注入当前用户权限范围，admin 可全局，其他角色按已有权限规则过滤。

**Test plan:**

- [x] 未注册 dataset 被拒。
- [x] 未注册字段、非法聚合、非法筛选操作被拒。
- [x] proj_leader 查询被自动限制到自己负责项目。
- [x] 合法配置可生成查询语句和字段元数据。
- [x] 自定义报表定义和运行记录表注册到 SQLAlchemy metadata。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_report_datasets.py tests/unit/test_report_query_compiler.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd backend && python -B -m compileall -q app tests alembic`
- `cd backend && python -B -m alembic heads`

### T-5-REPORT-02 自定义报表定义 API

**Files:**

- Create: `backend/app/api/v1/custom_reports.py`
- Create: `backend/app/services/custom_reports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_custom_reports_api.py`

**Implementation:**

- `GET /api/v1/custom-reports/datasets` 返回可用 dataset 和字段元数据。
- `POST /api/v1/custom-reports/preview` 校验配置并返回最多 100 行预览。
- admin 和 dept_manager 可保存报表定义；普通成员只能查看被分享的报表。
- 报表定义支持共享范围：private、department、global。
- 保存、更新、删除和预览均写入审计日志。

**Test plan:**

- [x] 普通成员不能创建 global 报表。
- [x] 非法配置 preview 返回 422 且不执行查询。
- [x] department 共享只对本部门可见。
- [x] 删除报表后 preview 入口不可用。

**Verification:**

- `cd backend && python -B -m pytest -q tests/api/test_custom_reports_api.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd backend && python -B -m compileall -q app tests alembic`

### T-5-REPORT-03 自定义报表设计器前端

**Files:**

- Create: `frontend/src/api/customReports.ts`
- Create: `frontend/src/stores/useCustomReportStore.ts`
- Create: `frontend/src/types/customReports.ts`
- Create: `frontend/src/views/reports/CustomReportBuilder.vue`
- Create: `frontend/src/components/reports/ReportChartPreview.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Test: `frontend/tests/custom-reports-api.test.ts`
- Test: `frontend/tests/custom-report-builder.test.ts`

**Implementation:**

- 设计器支持选择数据集、维度、指标、筛选器、图表类型和共享范围。
- 预览区显示表格或 ECharts 图表。
- 保存前进行前端字段合法性校验，后端仍作为最终校验。
- 报表列表支持打开、复制、删除和预览。
- 移动端降级为只读预览，复杂编辑显示移动端只读提示。

**Test plan:**

- [x] 选择 dataset 后加载字段元数据。
- [x] 添加非法筛选器时保存按钮禁用。
- [x] preview 成功后渲染表格和图表。
- [x] 非 owner 无法看到删除按钮。

**Verification:**

- `cd frontend && npm.cmd run test:unit -- custom-reports-api custom-report-builder`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-REPORT-04 定时报表与分享

**Files:**

- Create: `backend/app/tasks/custom_reports.py`
- Modify: `backend/app/tasks/celery_app.py`
- Modify: `backend/app/tasks/task_names.py`
- Modify: `backend/app/services/custom_reports.py`
- Modify: `backend/app/services/database_exports.py`
- Modify: `frontend/src/views/reports/CustomReportBuilder.vue`
- Test: `backend/tests/unit/test_scheduled_custom_reports.py`
- Test: `backend/tests/api/test_custom_report_exports.py`
- Test: `frontend/tests/custom-report-schedule.test.ts`

**Implementation:**

- 报表定义可配置月度、每周和每日定时生成。
- 定时任务按报表 owner 的时区计算触发窗口。
- 生成结果复用导出服务，支持 CSV 和 Excel。
- 生成成功后按共享范围通知订阅用户。
- 失败重试 3 次，最终写入失败状态和通知 owner。

**Test plan:**

- [ ] 每月 1 日本地 09:00 触发 owner 报表。
- [ ] 失败重试后进入 failed 状态。
- [ ] 生成的 Excel 包含报表字段和筛选条件摘要。
- [ ] 未被分享的用户不能下载报表结果。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_scheduled_custom_reports.py tests/api/test_custom_report_exports.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- custom-report-schedule`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-PROJECT-01 项目标签、分类与模板库

**Files:**

- Create: `backend/app/models/project_taxonomy.py`
- Create: `backend/app/schemas/project_taxonomy.py`
- Create: `backend/app/services/project_templates.py`
- Create: `backend/app/api/v1/project_templates.py`
- Create: `backend/alembic/versions/0035_create_project_taxonomy.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/projectTemplates.ts`
- Create: `frontend/src/stores/useProjectTemplateStore.ts`
- Create: `frontend/src/types/projectTemplates.ts`
- Create: `frontend/src/views/admin/ProjectTemplateLibrary.vue`
- Test: `backend/tests/api/test_project_templates_api.py`
- Test: `frontend/tests/project-template-library.test.ts`

**Implementation:**

- 新增项目标签、分类和项目模板库。
- admin 可把已完成项目保存为模板，选择是否复制环节、文档要求和任务清单。
- 新建项目可基于模板预填字段和默认任务。
- 标签和分类支持跨项目筛选、报表和风险评分使用。
- 模板创建和使用写审计日志。

**Test plan:**

- [ ] 非 admin 不能创建全局模板。
- [ ] 从历史项目生成模板时不会复制敏感附件内容。
- [ ] 使用模板新建项目会预填字段但生成新的业务编号。
- [ ] 标签筛选结果受角色权限限制。

**Verification:**

- `cd backend && python -B -m pytest -q tests/api/test_project_templates_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- project-template-library`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-PROJECT-02 跨项目对标分析

**Files:**

- Create: `backend/app/services/project_benchmarks.py`
- Create: `backend/app/api/v1/project_benchmarks.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/projectBenchmarks.ts`
- Create: `frontend/src/stores/useProjectBenchmarkStore.ts`
- Create: `frontend/src/types/projectBenchmarks.ts`
- Create: `frontend/src/views/analytics/ProjectBenchmark.vue`
- Test: `backend/tests/unit/test_project_benchmarks.py`
- Test: `backend/tests/api/test_project_benchmarks_api.py`
- Test: `frontend/tests/project-benchmark-page.test.ts`

**Implementation:**

- 按项目类型、分类、标签和部门计算历史平均周期、预算偏差、环节停留时间、任务逾期率。
- API 返回当前项目与同类历史样本的 P50、P90、平均值和样本数。
- 样本数少于 5 时不展示对标结论，只展示样本不足提示。
- 前端提供对标分析页和项目详情入口。
- 权限按用户可见项目集合过滤样本。

**Test plan:**

- [ ] 样本不足时返回 `insufficient_sample`。
- [ ] admin 与普通用户看到的样本集合不同。
- [ ] 同类项目 P50/P90 计算正确。
- [ ] 前端能展示周期、预算、逾期三个分析面板。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_project_benchmarks.py tests/api/test_project_benchmarks_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- project-benchmark-page`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-AI-01 AI Provider 抽象与隐私审计

**Files:**

- Modify: `backend/app/core/config.py`
- Create: `backend/app/models/ai.py`
- Create: `backend/app/schemas/ai.py`
- Create: `backend/app/services/ai_providers.py`
- Create: `backend/app/services/ai_audit.py`
- Create: `backend/alembic/versions/0036_create_ai_audit_logs.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_ai_providers.py`
- Test: `backend/tests/unit/test_ai_audit.py`

**Implementation:**

- 新增 AI 配置项，默认关闭。
- Provider 接口支持 `complete_json(prompt, schema_name)`，fake provider 返回测试 fixture。
- OpenAI-compatible provider 只依赖可配置 base URL、model、API key 和 timeout。
- 发送前生成脱敏摘要，记录用途、操作者、provider、model、token 估算、状态和错误码。
- Provider 输出必须通过 Pydantic schema 校验。

**Test plan:**

- [ ] 默认关闭时调用返回未启用错误。
- [ ] fake provider 可返回符合 schema 的结果。
- [ ] schema 校验失败时记录失败审计。
- [ ] 审计日志不保存 API key 和完整敏感 payload。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_ai_providers.py tests/unit/test_ai_audit.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-5-AI-02 项目风险评分与 AI 解释摘要

**Files:**

- Create: `backend/app/services/project_risk.py`
- Create: `backend/app/api/v1/project_risk.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/projectRisk.ts`
- Create: `frontend/src/stores/useProjectRiskStore.ts`
- Create: `frontend/src/types/projectRisk.ts`
- Create: `frontend/src/views/analytics/ProjectRisk.vue`
- Test: `backend/tests/unit/test_project_risk.py`
- Test: `backend/tests/api/test_project_risk_api.py`
- Test: `frontend/tests/project-risk-page.test.ts`

**Implementation:**

- 规则评分使用延期天数、预算偏差、撤销次数、任务逾期、环节停留时间和样本对标偏差。
- 输出风险分 0-100、等级 low/medium/high/critical、原因列表和建议动作。
- AI 启用时只基于规则原因生成解释摘要，不直接改分。
- AI 关闭时返回规则摘要。
- 前端在仪表盘和项目详情显示风险卡片。

**Test plan:**

- [ ] 无异常项目评分低于 30。
- [ ] 超预算且多个逾期任务项目评分高于 70。
- [ ] AI 关闭时仍返回确定性摘要。
- [ ] AI 返回无效 JSON 时降级为规则摘要并记录审计。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_project_risk.py tests/api/test_project_risk_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- project-risk-page`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-AI-03 文档类型智能建议

**Files:**

- Create: `backend/app/services/document_classification.py`
- Create: `backend/app/api/v1/document_classification.py`
- Modify: `backend/app/services/documents.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/documentClassification.ts`
- Modify: `frontend/src/components/document/DocumentUploader.vue`
- Test: `backend/tests/unit/test_document_classification.py`
- Test: `backend/tests/api/test_document_classification_api.py`
- Test: `frontend/tests/document-classification.test.ts`

**Implementation:**

- 上传前或上传后可按文件名、扩展名、环节、项目类型和短摘要生成 doc_type 建议。
- 规则分类器优先匹配模板必传文档、常见关键字和文件扩展名。
- AI 启用时基于规则候选生成排序和原因。
- 用户确认建议后才写入文档类型。
- 建议结果和用户确认动作写入审计日志。

**Test plan:**

- [ ] 文件名包含“合同”时建议合同类文档。
- [ ] 项目模板必传文档只包含一个候选时优先建议该类型。
- [ ] AI 关闭时规则建议可用。
- [ ] 用户未确认时不会修改文档记录。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_document_classification.py tests/api/test_document_classification_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- document-classification`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-AI-04 自然语言指标问答

**Files:**

- Create: `backend/app/services/analytics_qa.py`
- Create: `backend/app/api/v1/analytics_qa.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/api/analyticsQa.ts`
- Create: `frontend/src/stores/useAnalyticsQaStore.ts`
- Create: `frontend/src/views/analytics/AnalyticsQuestionAnswer.vue`
- Test: `backend/tests/unit/test_analytics_qa.py`
- Test: `backend/tests/api/test_analytics_qa_api.py`
- Test: `frontend/tests/analytics-qa-page.test.ts`

**Implementation:**

- 自然语言问题先映射到自定义报表白名单 dataset、metrics 和 filters。
- AI 启用时 provider 只返回受控查询配置，不返回 SQL。
- AI 关闭时支持内置模板问题，例如“本部门今年项目数”“平均周期多少”“逾期任务最多的项目”。
- 后端执行受控查询并返回答案、数据表和可视化建议。
- 前端提供问答页、示例问题和结果引用数据表。

**Test plan:**

- [ ] 内置模板问题在 AI 关闭时可回答。
- [ ] AI 返回未知 dataset 时拒绝执行。
- [ ] 回答结果受当前用户权限范围限制。
- [ ] 前端展示答案、表格和图表建议。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_analytics_qa.py tests/api/test_analytics_qa_api.py --no-cov`
- `cd frontend && npm.cmd run test:unit -- analytics-qa-page`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`

### T-5-DOCS-01 Phase 5 中文文档、发布说明与总体验收

**Files:**

- Create: `docs/PHASE_5_RELEASE_NOTES.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/ADMIN_OPERATIONS_MANUAL.md`
- Modify: `docs/PRODUCTION_DEPLOYMENT_MANUAL.md`
- Modify: `docs/PHASE_5_PLAN.md`
- Modify: `README.md`

**Implementation:**

- 使用手册补充项目类型、工作流模板、自定义报表、对标分析、风险评分和 AI 建议。
- 运维手册补充 AI 配置、隐私审计、报表任务、模板版本回滚和故障排查。
- 部署手册补充 AI provider 环境变量和默认关闭策略。
- 发布说明列出 Phase 5 新增能力、兼容性说明、迁移步骤和已知限制。
- 全量 review、测试和 compose 配置验证完成后勾选总体验收。

**Verification:**

- `git diff --check`
- `cd backend && python -B -m pytest -q`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`
- `cd backend && python -B -m compileall -q app tests alembic`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run typecheck`
- `cd frontend && npm.cmd run test:unit`
- `cd frontend && npm.cmd run build`
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.prod.yml config`

## 3. Phase 5 总体验收

- [ ] Phase 5 全部计划任务完成并合并到 `develop`。
- [ ] 工作流模板可支持非采购项目类型，且现有采购项目流程保持兼容。
- [ ] 自定义报表只能基于白名单数据集生成，权限隔离和审计完整。
- [ ] 项目模板、标签、分类和跨项目对标分析可用。
- [ ] AI provider 默认关闭，启用后所有调用可审计、可降级、不会绕过业务规则。
- [ ] 后端 ruff、mypy、pytest、compileall 全量通过。
- [ ] 前端 lint、typecheck、unit test、build 全量通过。
- [ ] 开发和生产 compose 配置均通过。
- [ ] 中文部署手册、使用手册、运维手册和发布说明已更新。

## 4. 发布前 review 记录

- 待 Phase 5 功能完成后记录最终 review 结论、验证结果和已知风险。
