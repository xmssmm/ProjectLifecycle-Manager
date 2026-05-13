# 项目管理系统 V2 问题真实性核验报告

**日期**：2026-05-13  
**核验对象**：

- `docs/项目管理系统V2问题汇总报告(1).md`
- `docs/step by step.txt`
- 当前代码库前端、后端、单元测试和部分 e2e 测试

---

## 1. 核验结论摘要

这次核验确认：测试报告中的问题方向整体成立，但并不是每一条都是“完全未实现”。当前系统存在明显的流程体验断点，尤其是前端仍大量要求用户输入后台 UUID；但后端已经实现了不少流程骨架，包括主项目 `spent_amount` 字段、付款金额联动、验收步骤接口、验收步骤材料关联、环节推进材料校验等。

因此后续开发不应直接按原报告逐条“从零开发”，而应按以下口径处理：

1. **确认存在，需要修复**：部门下拉、ID 展示问题、采购类型选择入口、三价强校验、附件显示标题、主项目列表字段、子项目筛选、分步验收开关等。
2. **部分存在，需要修正表述**：主项目金额、创建时间、主项目修改、环节推进按钮、分步验收材料关联等。
3. **代码已有实现，需要保留并补体验或回归测试**：付款金额联动、验收步骤创建 API、验收步骤完成前材料校验、环节推进材料校验。

---

## 2. 已运行验证

### 2.1 后端针对性测试

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `python -B -m pytest -q --no-cov tests/unit/test_payment_create.py::test_create_payment_uploads_voucher_and_updates_spent_amounts tests/unit/test_payment_create.py::test_reverse_payment_creates_reversal_and_reduces_spent_amount tests/e2e/test_business_flows.py::test_payment_reversal_flow_keeps_spent_amount_accurate` | 2 passed, 1 error | 两个付款金额联动单元测试通过；e2e 被本机 Docker/Testcontainers 管道不可用阻断，不是业务断言失败 |
| `python -B -m pytest -q --no-cov tests/unit/test_acceptance_steps.py` | 6 passed | 验收步骤服务和 API 覆盖通过 |
| `python -B -m pytest -q --no-cov tests/unit/test_phase_promote.py` | 7 passed | 环节推进、必传材料校验等测试通过 |
| `python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py tests/unit/test_main_project_review_flow.py tests/unit/test_sub_project_management.py tests/unit/test_sub_project_review_flow.py` | 32 passed | 主项目、子项目创建/审核/管理基础流程通过 |

### 2.2 环境限制

Docker/Testcontainers e2e 测试在当前机器报错：

```text
docker.errors.DockerException: Error while fetching server API version: (2, 'CreateFile', '系统找不到指定的文件。')
```

这说明本机 Docker daemon 或 Windows named pipe 不可用。该错误不能证明业务逻辑失败，只说明当前环境无法跑需要真实 PostgreSQL 容器的 e2e 测试。

---

## 3. 逐项核验矩阵

### A. 部门字段显示 UUID，而非下拉选择

**结论：确认存在。**

证据：

- 用户编辑页仍是 `部门 ID` 文本输入：`frontend/src/views/admin/UserEdit.vue`
- 主项目创建/编辑页仍是 `部门 ID` 文本输入：`frontend/src/views/main-project/MainProjectEdit.vue`
- 主项目审核页仍是 `部门 ID` 文本输入：`frontend/src/views/main-project/MainProjectReview.vue`
- 子项目创建/编辑页仍是 `主项目 ID` 和 `部门 ID` 文本输入：`frontend/src/views/sub-project/SubProjectEdit.vue`
- 部门管理列表只显示编码、名称、更新时间、操作，没有显示部门 ID：`frontend/src/views/admin/DepartmentList.vue`

修正口径：

这是一个真实的前端体验和数据展示问题。后端写接口接收 `dept_id` 是合理的，但前端必须通过部门下拉隐藏 UUID 细节。

---

### B. 主项目缺少“已用金额”字段

**结论：原表述不准确。后端字段和详情展示已存在，主项目列表展示缺失。**

证据：

- 后端模型已有 `MainProject.spent_amount`：`backend/app/models/main_projects.py`
- 后端读模型返回 `spent_amount`：`backend/app/schemas/main_projects.py`
- 主项目详情页显示 `已付款`：`frontend/src/views/main-project/MainProjectDetail.vue`
- 主项目列表列定义没有 `spent_amount`：`frontend/src/views/main-project/MainProjectList.vue`

修正口径：

不应按“新增主项目 spent_amount 字段”处理。正确任务是：确认金额刷新链路、在主项目列表展示已用金额/剩余金额，并统一命名为“已用金额”或“已付款”。

---

### C. 主项目列表缺少创建人、创建时间

**结论：部分存在。创建时间后端已有，创建人名称缺失，列表 UI 未展示。**

证据：

- `MainProjectRead` 返回 `creator_id` 和 `created_at`：`backend/app/schemas/main_projects.py`
- 不返回 `creator_name`。
- 主项目列表列定义没有创建人、创建时间：`frontend/src/views/main-project/MainProjectList.vue`

修正口径：

后端无需新增 `created_at` 字段，但需要补充创建人名称或用户摘要；前端列表需要展示创建人、创建时间。

---

### D. 主项目没有修改审批功能

**结论：确认存在，但需区分“驳回后修改”和“通过后修改审批”。**

证据：

- 当前主项目更新只允许创建人在 `rejected` 状态编辑。
- 主项目审核接口允许审核人在审核时修正字段后通过。
- 没有看到“审核通过后修改申请、修改前后快照、再审批”的独立流程。

修正口径：

不是完全没有修改能力，而是缺少已审核通过项目的修改审批流程。后续应按“通过后的重大修改审批”设计，不要破坏现有驳回后编辑和审核时修正机制。

---

### E. 子项目创建流程不明确

**结论：确认存在。**

证据：

- 子项目创建页仅提示“填写子项目立项信息，提交后进入综合部审核”。
- 表单仍要求手动输入 `主项目 ID` 和 `部门 ID`。
- 没有说明“主项目必须先审核通过”“审核通过后自动生成 6 个环节”“预算会纳入主项目约束”等流程信息。

修正口径：

这是前端引导问题，同时也和主项目/部门下拉选择有关。应先把子项目创建页变成业务选择，而不是后台 ID 填写页。

---

### F. 金额联动未实现

**结论：原表述不准确。后端付款联动已有实现且单元测试通过。**

证据：

- 创建付款后会重算子项目和主项目 `spent_amount`：`backend/app/services/payments.py`
- 红冲后也会重算子项目和主项目 `spent_amount`：`backend/app/services/payments.py`
- 单元测试已通过：`test_create_payment_uploads_voucher_and_updates_spent_amounts`、`test_reverse_payment_creates_reversal_and_reduces_spent_amount`

修正口径：

不要按“从零实现付款联动”处理。应重点验证真实数据库 e2e、页面刷新、列表显示和看板口径。如果用户测试仍观察到不更新，更可能是前端刷新或测试环境数据路径问题。

---

### G. 分步验收开关缺失

**结论：确认存在。**

证据：

- `Phase` 模型和读模型没有 `is_stepped_acceptance` 字段。
- 前端验收步骤面板在第 4 环节直接显示，没有显式“启用分步验收”开关。

修正口径：

需要决定业务口径：是所有验收环节默认都允许步骤，还是必须显式启用分步验收。测试文档要求开关，因此应补开关字段和 UI。

---

### H. 分步验收步骤文档缺失

**结论：原表述不准确。后端和前端已经支持文档关联到验收步骤，但展示体验可能不足。**

证据：

- `Document` 模型已有 `acceptance_step_id` 外键。
- 文档上传 API 接收 `acceptance_step_id`。
- 前端 `DocumentUploader` 支持 `acceptanceStepId`。
- 验收步骤面板给每个步骤传入 `acceptance-step-id` 上传验收报告。
- `test_complete_acceptance_step_requires_report_document` 验证“没有步骤材料不能完成步骤”。

修正口径：

不要按“新增关联能力”处理。正确任务是：补强步骤下材料展示、中文标题/display_name、责任人名称展示和操作引导。

---

### 1. 子项目列表缺少“我的项目”筛选

**结论：确认存在，但后端已有可见性过滤基础。**

证据：

- 子项目列表前端只支持状态和主项目 ID 筛选。
- API 查询参数只有 `page`、`page_size`。
- 后端对非全局角色会自动限制为“负责人或成员可见”，但没有提供“我负责的 / 我参与的”显式筛选。

修正口径：

需要新增显式筛选能力，尤其服务于管理员、部门经理或同时负责/参与多个项目的用户。

---

### 2. 环节详情页缺少“推进环节”按钮

**结论：部分存在。推进按钮在环节进度组件中存在，但不在材料详情面板中，且前端不按必传材料预判显示。**

证据：

- `PhaseProgress.vue` 对 `in_progress` 且有权限的环节显示“推进”按钮。
- `PhaseDocumentPanel.vue` 只展示必传材料、上传控件和验收步骤，没有推进按钮。
- 当前前端按钮显示逻辑只看状态和权限，缺失材料时依靠后端返回错误。

修正口径：

不是完全没有推进按钮。应把推进入口放到用户正在补材料的环节详情/材料面板中，并根据 `missing_doc_types` 和后端规则展示可推进或阻断原因。

---

### 3. 新增验收步骤 500 错误

**结论：当前代码和测试未复现，倾向于已修复或原测试数据触发了业务错误但被前端表现成 500。**

证据：

- 后端有验收步骤创建 API：`POST /api/v1/phases/{phase_id}/acceptance-steps`
- `test_acceptance_step_endpoints_create_list_and_complete` 覆盖 API 创建并断言 200。
- `tests/unit/test_acceptance_steps.py` 全部通过。

修正口径：

需要用真实环境再复现一次。如果仍 500，应抓具体响应和后端日志。当前静态代码和单元/API 测试不支持“接口未实现”这个结论。

---

### 4. 采购类型缺少下拉及三价强制校验

**结论：确认存在，但后端已有采购类型枚举和条件材料基础。**

证据：

- 后端 `ProcurementType` 已有 `inquiry`、`bidding`、`single_source`。
- `Phase` 已有 `procurement_type` 字段。
- 默认材料模板已有采购类型条件材料。
- 但前端没有采购类型选择入口。
- `phases` API 没有更新采购类型的接口。
- 询价类模板当前是 `inquiry_report >=1`，不是“3 家供应商报价单 >=3”。

修正口径：

不是完全没有采购类型模型，而是缺少“用户选择采购类型”的产品入口和“三家报价单”的精确材料规则。

---

### 5. 附件显示系统文件名而非中文标题

**结论：确认存在。**

证据：

- `Document` 模型没有 `display_name` 字段。
- `DocumentRead` 没有 `display_name`。
- 前端 `DocumentList` 主标题显示 `file_name`。
- 上传组件没有让用户填写文件标题。

修正口径：

这是端到端缺口：模型、上传 API、前端上传表单、列表展示都需要支持 `display_name`。

---

## 4. 修订后的优先级建议

### P0：真实阻塞用户走流程的问题

1. 部门、主项目、子项目相关 ID 输入改为业务下拉。
2. 主项目和子项目列表补关键业务字段。
3. 子项目创建页增加流程引导。
4. 环节详情材料面板增加推进入口和阻断原因。
5. 采购类型选择入口和询价类三家报价校验。
6. 附件 `display_name`。

### P1：流程治理和体验补强

1. 分步验收开关。
2. 验收步骤下材料展示和责任人名称展示。
3. 子项目“我负责 / 我参与”筛选。
4. 主项目通过后的修改审批。

### P2：回归和真实环境复现

1. 在 Docker 可用环境跑完整 e2e。
2. 用 `docs/step by step.txt` 固化端到端验收剧本。
3. 针对“付款后页面未刷新”和“验收步骤 500”补真实环境复现记录。

---

## 5. 对规格文档的影响

`docs/V2_FLOW_DRIVEN_REFACTOR_SPEC.md` 应作为流程设计初稿保留，但后续实施计划必须先吸收本报告：

1. 不再把 `spent_amount`、付款联动、验收步骤 API、验收步骤文档关联当作全新功能。
2. 把重点从“补模型”调整为“补入口、补展示、补校验精度、补端到端体验”。
3. 对仍需真实环境复现的问题，先加诊断和测试，不直接猜测修复。

---

## 6. P0 修复验证记录（2026-05-13）

本轮 P0 修复按“先确认问题、再补流程入口”的方式实施，已覆盖本报告中确认存在且会阻塞用户主流程的问题。

### 已处理的问题

1. 部门、主项目相关 ID 手输已改为业务下拉选择。
2. 主项目、子项目列表和详情已补充部门、负责人、主项目名称、余额等业务字段。
3. 子项目创建页已增加主项目选择和前置说明，减少用户直接填写数据库 ID 的概率。
4. 环节材料面板已增加当前环节推进入口和缺失材料阻断提示。
5. 采购环节已增加采购类型选择入口，询价类材料规则已调整为“三家供应商报价单”。
6. 附件已支持 `display_name`，上传时可填写中文标题，列表和预览优先显示标题。

### 本轮验证命令

后端：

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py tests/unit/test_sub_project_management.py tests/unit/test_document_upload.py tests/unit/test_phase_promote.py tests/unit/test_acceptance_steps.py tests/unit/test_payment_create.py tests/unit/test_seed_data.py tests/unit/test_workflow_seed.py
python -B -m ruff check .
python -B -m mypy app tests
python -B -m compileall -q app tests alembic
```

前端：

```powershell
cd C:\management\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run build
```

### 2026-05-13 最终验证结果

1. 后端目标测试：`62 passed, 1 warning`。
2. 后端 `ruff`：`All checks passed!`。
3. 后端 `mypy`：`Success: no issues found in 293 source files`。
4. 后端 `compileall`：通过，无错误输出。
5. 前端 `lint`：通过。
6. 前端 `typecheck`：通过。
7. 前端单元测试：`78 passed` test files，`154 passed` tests。
8. 前端 `build`：通过；仍有 Vite 对大 chunk 和 `@vueuse/core` 注释的构建警告，不影响本轮通过状态。

### 仍需真实环境复核

1. Docker 环境下的完整端到端剧本仍建议按 `docs/step by step.txt` 再跑一遍。
2. “付款后页面未刷新”和“验收步骤 500”在代码与单元测试层面未复现为当前缺陷，仍建议在真实部署环境保留一次操作日志和后端日志采样。
3. 本轮聚焦 P0 主流程阻塞项，P1 的分步验收治理、主项目修改审批、我的项目筛选等事项仍按后续计划推进。

---

## 7. Step-by-Step 闭环记录（2026-05-14）

针对 `docs/step by step.txt` 的完整推演，本轮补齐了昨天仍会卡住的执行点：

1. 单人部门负责人场景支持自审；如果存在其他可用部门负责人，仍保持自审拦截。
2. 项目成员可以操作自己参与子项目的环节推进和采购类型选择；服务层仍会校验其必须是该子项目成员。
3. 财务付款环节不再要求后评价先完成，支持按剧本在验收后、后评价前完成付款环节。
4. 子项目详情页增加“结项”入口，已完成子项目可由部门负责人结项。
5. 主项目详情页接入“结项”入口，所有子项目完成、结项或中止后可由部门负责人结项主项目。
6. 主项目结项后端规则允许子项目处于“已完成”状态，不再强制要求每个子项目先变为“已结项”。

本轮新增验证：

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py tests/unit/test_sub_project_management.py tests/unit/test_phase_promote.py tests/unit/test_acceptance_steps.py tests/unit/test_payment_create.py tests/unit/test_permissions.py

cd C:\management\frontend
npm.cmd run test:unit -- main-project-pages sub-project-pages phase-document-panel payment-pages permission main-projects-api sub-projects-api
```

结果：

1. 后端相关回归：`66 passed, 1 warning`。
2. 前端相关回归：`7 passed` test files，`27 passed` tests。

### 2026-05-14 最终补充验证

1. 后端单元全量：`python -B -m pytest -q --no-cov tests/unit`，结果 `406 passed, 1 warning`。
2. 后端静态与编译：`python -B -m ruff check .`、`python -B -m mypy app tests`、`python -B -m compileall -q app tests alembic` 均通过。
3. 后端全量：`python -B -m pytest -q --no-cov`，结果 `431 passed, 1 warning, 6 errors`；6 个错误全部来自 `tests/e2e/test_business_flows.py` 在启动 Testcontainers/PostgreSQL 前无法连接本机 Docker named pipe `//./pipe/docker_engine`，错误为 `(2, 'CreateFile', '系统找不到指定的文件。')`。
4. 前端全量：`npm.cmd run lint`、`npm.cmd run typecheck`、`npm.cmd run test:unit`、`npm.cmd run build` 均通过；单元测试结果为 `78 passed` test files，`157 passed` tests。构建仍有 Vite 大 chunk 与第三方 PURE 注释警告，不影响退出码。

至此，`docs/step by step.txt` 的业务剧本在代码能力层面已闭环；发布前仍建议在 Docker 或试运行环境跑一次真实浏览器端到端操作，验证账号、基础数据、文件上传和迁移后的真实数据库状态。
