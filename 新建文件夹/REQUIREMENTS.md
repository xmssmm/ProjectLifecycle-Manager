# 企业项目过程管理与资料归档系统 — 需求规格 V2.2

| 项目 | 内容 |
| --- | --- |
| 版本 | V2.2 (基于 V2.1 + 业务决策确认) |
| 日期 | 2026-05-10 |
| 状态 | LLM Agent 可消费版 / 已 Sign-off |
| 适用范围 | 仅采购类（CG）项目 |
| 变更记录 | V2.2: 合并 OPEN_QUESTIONS 决策结果（OQ-01 ~ OQ-10），新增 PDF 预览 / 可执行文件拦截 / 转交流程 |

---

## 0. 如何阅读本文档（LLM Agent 必读）

1. **优先级关键字**：
   - `MUST` / `必须`：强约束，违反即视为缺陷
   - `MUST NOT` / `不得`：禁止行为
   - `SHOULD` / `应当`：默认行为，可在 §10 列出的开放问题中由人类调整
   - `MAY` / `可以`：可选行为
2. **ID 规则**：所有功能需求带 `FR-{模块}-{编号}`，业务规则带 `BR-{编号}`，禁止隐式引用——只引用 ID。
3. **术语锁定**：§1 术语表内的英文代码（如 `proj_leader`）是字段值的唯一形式。中文名称仅用于 UI 展示。
4. **冲突优先级**：本文档 > 设计文档 > V2.0 旧版需求。本文档已修订所有已知不一致。
5. **未明确即缺失**：如本文档未规定某行为，agent MUST 在 §10 追加开放问题，MUST NOT 自行假设。

---

## 1. 术语表

### 1.1 角色代码（5 种，闭集，不得扩展）

| 代码 | 中文名 | 定位 |
| --- | --- | --- |
| `admin` | 系统管理员 | 全局管理者；账号管理唯一入口；审核兜底 |
| `dept_manager` | 综合部负责人 | 创建主项目、审核主/子项目、查看全部项目 |
| `finance_manager` | 财务负责人 | 操作付款环节、查看全部项目 |
| `proj_leader` | 项目负责人 | 创建子项目、推进本项目环节、管理本项目任务 |
| `proj_member` | 项目参与人 | 查看参与的子项目、上传文档、完成被指派任务 |

### 1.2 主项目状态枚举（`main_project.status`）

`pending_review`（待审核）→ `reviewing`（审核中）→ `rejected`（已退回）/ `not_started`（未开始）→ `in_progress`（进行中）→ `completed`（已完成）→ `closed`（已结项）

### 1.3 子项目状态枚举（`sub_project.status`）

同主项目，并新增：`terminated`（已中止）

### 1.4 环节状态枚举（`phase.status`）

`waiting`（待开始）/ `in_progress`（进行中）/ `completed`（已完成）/ `revoked`（已撤销）

### 1.5 任务状态枚举（`task.status` / `task_executor.status`）

`not_started` / `in_progress` / `overdue` / `completed`

### 1.6 6 个采购类环节代码（`phase.phase_no`）

| no | code | 名称 | 是否依赖前序 |
| --- | --- | --- | --- |
| 1 | `initiation` | 立项 | 无（首环节） |
| 2 | `procurement` | 采购 | 依赖 1 |
| 3 | `contract` | 合同签订 | 依赖 2 |
| 4 | `acceptance` | 验收 | 依赖 3 |
| 5 | `payment` | 财务付款 | **不依赖**（详见 BR-PHASE-02） |
| 6 | `post_review` | 后评价 | **依赖 4 完成**（详见 BR-PHASE-03，修订自 V2.0） |

### 1.7 采购类型枚举（`procurement_type`）

| 代码 | 中文 | 必传材料 |
| --- | --- | --- |
| `oa_screenshot` | OA采购申请 | 流程截图 ×1 |
| `inquiry` | 询价类 | 询价报告（≥3家供应商盖章报价单） |
| `bidding` | 招标类 | 采购公告 + 采购文件 + 成交公告（3份缺一不可） |
| `single_source` | 单一来源类 | 单一来源论证报告 + 议价报告（2份缺一不可） |

> 选择规则（修订 V2.0 歧义）：环节 2 必传 = `oa_screenshot` 截图 ×1 **加上** 后三种 (`inquiry` / `bidding` / `single_source`) **三选一** 的对应材料。即"OA 截图永远要传，再额外选一种采购方式"。

---

## 2. 系统范围与边界

### 2.1 In-scope
- 主项目 + 子项目两级结构
- 6 环节固定流程（采购类）
- 项目审核、文档归档、多次付款、分步验收
- 站内通知、审计日志

### 2.2 Out-of-scope（如未来需要，须立项扩展）
- 非采购类项目
- 跨主项目的资源/预算调拨
- 财务对账、发票管理
- 工作流自定义引擎（环节硬编码 6 个）
- 移动 App 原生客户端（仅响应式 H5）

### 2.3 假设
- 本系统为 **greenfield 部署**，不涉及 V1.4 历史数据迁移（如有迁移需求，须独立立项）
- 综合部负责人 (`dept_manager`) 在生产环境 MUST ≥ 2 人（详见 BR-ROLE-01）

---

## 3. 领域模型

### 3.1 核心实体

```
User ─┬─ belongs to ─→ Department
      ├─ creates ─→ MainProject
      ├─ leads/joins ─→ SubProject (via SubProjectMember)
      └─ executes ─→ Task (via TaskExecutor)

MainProject ─1:N─→ SubProject
SubProject ─1:6─→ Phase (固定 6 个，子项目审核通过时一次性创建)
SubProject ─1:N─→ SubProjectMember
SubProject ─1:N─→ Payment
Payment ─1:N─→ PaymentVoucher
Phase(no=4) ─1:N─→ AcceptanceStep (分步验收，可选)
Phase ─1:N─→ Task
Task ─1:N─→ TaskExecutor
Phase ─1:N─→ Document
{MainProject|SubProject} ─1:N─→ ProjectReview
Phase ─1:N─→ RevokeRequest
```

### 3.2 文档模板（环节 → 必传文档类型，配置表）

| phase_no | doc_type | required | 数量约束 |
| --- | --- | --- | --- |
| 1 | `meeting_material` | true | =1 |
| 1 | `meeting_minutes` | true | =1 |
| 2 | `oa_screenshot` | true | =1 |
| 2 | `inquiry_report` | conditional | ≥1（仅 `procurement_type=inquiry`） |
| 2 | `bid_announcement` | conditional | =1（仅 `bidding`） |
| 2 | `bid_document` | conditional | =1（仅 `bidding`） |
| 2 | `bid_result` | conditional | =1（仅 `bidding`） |
| 2 | `single_source_report` | conditional | =1（仅 `single_source`） |
| 2 | `negotiation_report` | conditional | =1（仅 `single_source`） |
| 3 | `contract` | true | =1 |
| 3 | `supplementary_contract` | false | 0–1 |
| 4 | `acceptance_report` | true | ≥1（分步验收每步各 1） |
| 5 | `payment_voucher` | true | 每次付款 ≥1 |
| 6 | `post_review_report` | true | =1 |
| 6 | `economic_benefit_report` | true | =1 |

> Agent 实现提示：MUST 用单独的 `phase_doc_template` 配置表存储以上规则，**不得**把 `is_required` 写到 `documents` 行记录里（修订自 V2.0 设计文档）。

---

## 4. RBAC 权限矩阵（精确版）

| 操作代码 | admin | dept_manager | finance_manager | proj_leader | proj_member |
| --- | --- | --- | --- | --- | --- |
| `user.manage` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `system.config` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `audit_log.read` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `main_project.create` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `main_project.edit` (审核前) | ✅ | ✅(创建人) | ❌ | ❌ | ❌ |
| `main_project.review` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `main_project.close` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `sub_project.create` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `sub_project.review` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `sub_project.terminate` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `phase.promote` | ✅ | ❌ | ❌ | ✅(本项目) | ❌ |
| `acceptance_step.create` | ✅ | ❌ | ❌ | ✅(本项目) | ❌ |
| `acceptance_step.complete` | ✅ | ❌ | ❌ | ✅(本项目) | ✅(被指派) |
| `payment.create` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `payment.reverse` (红冲) | ❌ | ❌ | ✅ | ❌ | ❌ |
| `document.upload` | ✅ | ✅ | ✅ | ✅(本项目) | ✅(本项目) |
| `document.download` | ✅ | ✅ | ✅ | ✅(本项目) | ✅(本项目) |
| `task.assign` | ✅ | ❌ | ❌ | ✅(本项目) | ❌ |
| `task.complete` | ✅ | ✅(被指派) | ✅(被指派) | ✅(被指派) | ✅(被指派) |
| `revoke_request.submit` | ❌ | ❌ | ❌ | ✅(本项目) | ❌ |
| `revoke_request.review` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `project.view_all` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `project.view_own` | — | — | — | ✅ | ✅ |

**BR-ROLE-01**：生产环境 `dept_manager` 角色用户数 MUST ≥ 2，以避免主项目自审死锁（详见 BR-REVIEW-01）。系统启动时若检测到 `dept_manager` 数量 < 2 MUST 在 admin 仪表盘显示告警。

**BR-ROLE-02**：`admin` 角色作为审核兜底，可代替 `dept_manager` 执行任何审核操作，但 `admin` 的审核动作 MUST 在审计日志中标记为 `admin_override=true`。

---

## 5. 功能需求

### 5.1 用户与认证

**FR-AUTH-01 登录**
- 输入：`username` + `password`
- 输出：`access_token`（30 min） + `refresh_token`（7 d，HttpOnly Cookie）
- BR-AUTH-01：连续 5 次密码错误 MUST 锁定账号 30 分钟（计数器存 Redis，TTL 30min）
- BR-AUTH-02：密码 MUST 满足：≥8 位 + 大写 + 小写 + 数字 + 特殊字符（至少各 1）
- BR-AUTH-03：密码 MUST 用 Bcrypt 存储，cost=12

**FR-AUTH-02 Token 续签**
- POST `/api/v1/auth/refresh`，凭 refresh_token 换 access_token
- BR-AUTH-04：登出 / 修改密码 / 停用账号时，对应用户的所有未过期 access_token 的 jti MUST 加入 Redis 黑名单（TTL = token 剩余有效期）

**FR-USER-01 账号管理**
- 仅 `admin` 可执行：创建、停用、重置密码
- 重置密码后系统 MUST 强制用户下次登录时修改
- BR-USER-01：停用 `proj_leader` 角色账号前，admin MUST 完成所有"in-flight"子项目的负责人转交（见 FR-USER-02），否则停用操作被拒绝

**FR-USER-02 项目负责人转交（OQ-09 决策：admin 手动）**

适用场景：原 `proj_leader` 转岗、离职、轮岗。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `sub_project_id` | uuid | ✅ | 被转交的子项目 |
| `from_user_id` | uuid | ✅ | 原负责人 |
| `to_user_id` | uuid | ✅ | 新负责人，MUST `role=proj_leader` |
| `reason` | text | ✅ | 转交原因 |
| `operator_id` | uuid | auto | admin |
| `operated_at` | timestamp | auto | — |

接口：
- `GET /api/v1/users/{id}/active-sub-projects` — 列出某用户作为 proj_leader 的"in-flight"子项目（`status ∈ {not_started, in_progress, completed}`，**不**含 closed/terminated）
- `POST /api/v1/sub-projects/{id}/handover` — 单项目转交
- `POST /api/v1/users/{id}/batch-handover` — 批量转交（payload: `[{sub_project_id, to_user_id, reason}]`）

**BR-USER-02 转交规则**（OQ-09 子问题决策）：
- ① **proj_member 关系不转交**：原负责人在其他子项目作为 `proj_member` 的关系保持不变（账号停用后这些关系自然失效）
- ② **历史负责人记录 MUST 保留**：新增 `sub_project_handovers` 表，每次转交追加一行；`sub_project.manager_id` 更新为新负责人
- ③ **closed / terminated 项目不转交**：保留原 `manager_id` 用于历史追溯，UI 显示"原负责人 [姓名]（已离岗）"
- ④ 转交完成时 MUST 通知：原负责人（如未停用）、新负责人、所有该子项目成员
- ⑤ 全程写审计日志（`action=sub_project.handover`，含 from/to/reason）

### 5.2 主项目

**FR-MAIN-01 字段定义**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_no` | string | auto | `Z-{YYYY}-{seq}`，`seq` 全局递增 4 位 |
| `name` | string | ✅ | ≤200 字符 |
| `dept_id` | uuid | ✅ | 立项部门（**发起部门**，非综合部本身） |
| `status` | enum | auto | 见 §1.2 |
| `total_budget` | decimal(15,2) | ✅ | 单位元 |
| `expected_finish_date` | date | ✅ | — |
| `spent_amount` | decimal(15,2) | auto | 见 BR-PAY-04 |
| `remark` | text | ❌ | — |
| `creator_id` | uuid | auto | — |

**FR-MAIN-02 创建审核流程**

```
[dept_manager A] 填写主项目 → submit
    └─ status: pending_review
       通知所有其他 dept_manager（不通知创建人自己）
[dept_manager B 或 admin] 进入审核 → status: reviewing
    │  审核人 MAY 直接编辑字段，所有修改 MUST 写入 project_reviews.modified_fields (JSONB)
    │
    ├─ 审核通过 → status: not_started → 通知创建人
    │           可创建子项目
    │
    └─ 审核退回 → status: rejected
                通知创建人，附 review_comment
                创建人修改后可再次 submit → status: pending_review (循环)
```

- **BR-REVIEW-01**：审核人 MUST NOT 是创建人本人。如全系统只有 1 个 `dept_manager`，UI MUST 阻止其创建主项目并提示"需 admin 角色协助审核"。
- **BR-REVIEW-02**：状态 `pending_review` / `reviewing` 期间，原创建人 MUST NOT 编辑（只能撤回 → 退回 `rejected` 或删除草稿）。
- **BR-REVIEW-03**：仅当 `status ∈ {pending_review, rejected}` 时可重新提交。

**FR-MAIN-03 主项目结项**
- 触发条件：所有子项目 `status ∈ {closed, terminated}` 时 `dept_manager` 可手动结项
- 结项后 MUST NOT 再创建子项目；MUST NOT 修改任何字段

### 5.3 子项目

**FR-SUB-01 字段定义**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_no` | string | auto | `{main_project_no}-ZX-{seq}`，`seq` 主项目内递增 |
| `name` | string | ✅ | ≤200 |
| `main_project_id` | uuid | ✅ | 关联主项目，MUST status=`in_progress` 或 `not_started` |
| `dept_id` | uuid | ✅ | 立项部门（创建子项目的部门） |
| `budget` | decimal(15,2) | ✅ | — |
| `manager_id` | uuid | ✅ | `proj_leader` 角色 |
| `status` | enum | auto | 见 §1.3 |
| `plan_end_date` | date | ❌ | — |
| `actual_end_date` | date | auto | 进入 `completed` 时由系统自动写入（修订：保留此字段，自动维护） |
| `spent_amount` | decimal(15,2) | auto | 见 BR-PAY-04 |

**FR-SUB-02 创建审核流程**
与 FR-MAIN-02 相同模式，审核人为 `dept_manager`（含 `admin` 兜底）。
- BR-SUB-01：审核通过时 MUST 在同一事务内：① 写 sub_project → ② 创建 6 条 phase 记录（phase 1 状态 `in_progress`，其余 `waiting`）→ ③ 通知 `proj_leader`
- BR-SUB-02：子项目预算 MAY 超过主项目剩余预算（`total_budget - sum(child.budget)`），但 MUST 在 UI 显示警告并要求二次确认；审计日志 MUST 记录 `over_budget_warning=true`

### 5.4 环节流转

**FR-PHASE-01 推进规则**

```python
def promote_phase(phase_id, user):
    p = get_phase(phase_id)
    
    # 1. 权限
    assert user.role == 'admin' or (
        user.role == 'proj_leader' and is_project_leader(user, p.sub_project_id)
    )
    
    # 2. 不可推进的状态
    assert p.status == 'in_progress'
    
    # 3. 必传文档校验
    required_docs = get_required_doc_types(p.phase_no, p.procurement_type)
    for doc_type, qty_rule in required_docs:
        actual = count_latest_documents(p.id, doc_type)
        assert qty_rule.matches(actual), f"缺少 {doc_type}：需 {qty_rule}，实有 {actual}"
    
    # 4. 分步验收：所有 step 必须 completed
    if p.phase_no == 4:
        steps = get_acceptance_steps(p.id)
        if steps:  # 启用了分步验收
            assert all(s.status == 'completed' for s in steps)
    
    # 5. 状态更新（事务）
    with db.transaction():
        p.status = 'completed'
        p.finish_at = now()
        write_phase_history(p, from='in_progress', to='completed', by=user)
        
        # 自动激活下一环节
        next_phase = get_next_dependent_phase(p)  # 见 BR-PHASE-02
        if next_phase and next_phase.status == 'waiting':
            next_phase.status = 'in_progress'
            next_phase.enter_at = now()
            notify_project_members(p.sub_project_id, 'phase_promoted', next_phase)
```

**BR-PHASE-01**：环节 1→2→3→4 严格顺序，前序未 `completed` 则后续保持 `waiting`。

**BR-PHASE-02**（修订自 V2.0）：
- 环节 5 (`payment`)：`status` 跟随子项目，子项目审核通过即 `in_progress`，可随时新增付款记录。当子项目所有其他环节 `completed` 且付款累计 ≥ 1 笔时，可由 `proj_leader` 手动标记为 `completed`。
- 环节 6 (`post_review`)：MUST 在环节 4 (`acceptance`) `completed` 后才进入 `in_progress`（避免逻辑漏洞：项目还没验收就写后评价）。

**BR-PHASE-03**：子项目 `completed` 条件 = 6 个环节全部 `completed`。`closed`（结项）由 `dept_manager` 手动触发。

### 5.5 分步验收

**FR-ACC-01 启用与字段**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `phase_id` | uuid | ✅ | 必为 phase_no=4 的环节 |
| `step_no` | int | ✅ | 同 phase 内递增，`UNIQUE(phase_id, step_no)` |
| `step_name` | string | ✅ | — |
| `responsible_id` | uuid | ✅ | 步骤负责人，MUST 是该子项目成员 |
| `plan_date` | date | ❌ | — |
| `description` | text | ❌ | — |
| `status` | enum | auto | `not_started` / `in_progress` / `completed` |
| `completed_at` | timestamp | auto | — |

- BR-ACC-01：仅 `proj_leader` 可创建步骤；MUST 在环节 4 `in_progress` 状态下创建
- BR-ACC-02：每步完成时 MUST 上传至少 1 份 `acceptance_report` 类型文档，`document.acceptance_step_id` 关联到该步骤
- BR-ACC-03：若未创建任何步骤，验收环节按"非分步"模式：直接上传 1 份 `acceptance_report` 即可推进

### 5.6 财务付款

**FR-PAY-01 多次付款**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `payment_no` | string | auto | `{sub_project_no}-PAY-{seq}` |
| `sub_project_id` | uuid | ✅ | — |
| `amount` | decimal(15,2) | ✅ | **可为负**（红冲场景） |
| `payment_date` | date | ✅ | — |
| `remark` | text | ❌ | — |
| `payment_type` | enum | ✅ | `normal` / `reversal`（红冲） |
| `reverses_payment_id` | uuid | conditional | `payment_type=reversal` 时必填，关联被红冲的付款 |
| `operator_id` | uuid | auto | — |

**BR-PAY-01**：付款记录 MUST NOT 物理删除，MUST NOT 修改 `amount` / `payment_date`。**修正错误的唯一方式是创建一笔 `reversal` 类型的红冲付款**。
- 红冲规则：`amount = -original.amount`；`payment_date = today`；`remark` 必填（说明红冲原因）

**BR-PAY-02（关键修订，弥补"删除超预算预警"漏洞）**：每次新增付款时：
- 计算 `new_total = sub.spent_amount + amount`
- 若 `new_total > sub.budget`：MUST 弹窗"二次确认"+ 必填 `over_budget_reason`，审计日志记录 `over_budget=true`，发送通知给该子项目所属主项目的 `dept_manager` 和 `admin`
- MUST NOT 强阻断（业务上允许超预算，但要留痕和告警）

**BR-PAY-03**：每次付款 MUST 上传 ≥1 份 `payment_voucher` 文件到 `payment_vouchers` 表，与付款记录在同一事务

**BR-PAY-04 spent_amount 聚合（事务保障）**

```python
def on_payment_inserted(payment):
    with db.transaction(isolation='SERIALIZABLE'):
        # 子项目层
        sub_total = db.query(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE sub_project_id=:id",
            id=payment.sub_project_id
        )
        sub = SubProject.get_for_update(payment.sub_project_id)  # 行级锁
        sub.spent_amount = sub_total
        
        # 主项目层
        main_total = db.query(
            "SELECT COALESCE(SUM(spent_amount), 0) FROM sub_projects WHERE main_project_id=:id",
            id=sub.main_project_id
        )
        main = MainProject.get_for_update(sub.main_project_id)
        main.spent_amount = main_total
```

- 实现选择：MUST 用应用层事务 + 行锁（不要用 DB 触发器，便于测试和回放）
- 高并发优化：MAY 使用乐观锁 + 重试，最多 3 次

### 5.7 文档管理

**FR-DOC-01 上传**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | uuid | auto | — |
| `doc_no` | string | auto | UUID |
| `sub_project_id` | uuid | ✅ | — |
| `phase_id` | uuid | ✅ | — |
| `acceptance_step_id` | uuid | ❌ | 仅验收分步时有值 |
| `doc_type` | enum | ✅ | 见 §3.2 |
| `file_name` | string | ✅ | 原始文件名 |
| `file_path` | string | ✅ | 后端不暴露给前端 |
| `file_size` | bigint | ✅ | 字节 |
| `version` | int | ✅ | 同 (sub_project, phase, doc_type) 内递增 |
| `is_latest` | bool | ✅ | 同组内仅 1 条为 true |
| `is_deleted` | bool | ✅ | 软删除标志（修订 V2.0：撤销时不重置版本，改为软删除） |
| `uploader_id` | uuid | ✅ | — |

**BR-DOC-01（修订自 V2.0 设计文档 unique_key 矛盾）**：唯一性约束改为：
```
UNIQUE(sub_project_id, phase_id, doc_type, version)
```
**不**包含 `file_name`。同类型文档新版本递增 version 即可。

**BR-DOC-02**：上传新版本时 MUST 在事务内：① 旧版本 `is_latest=false` → ② 新版本 `version = max(old.version) + 1, is_latest=true`

**BR-DOC-03**：撤销审批通过时（见 FR-REVOKE-01），MUST NOT 物理删除已上传文档，MUST NOT 重置版本号；改为：
- 该 phase 下当前所有 `is_latest=true` 的文档标记为 `is_deleted=true`
- `is_latest` 保留，便于查询历史
- 后续重新上传时 version 继续递增（即从 v3 撤销后，下次上传是 v4，不是 v1）

**BR-DOC-04 可执行文件拦截（OQ-06 决策）**：上传 MUST 同时通过白名单和黑名单检查：
- 白名单（仅允许）：`.pdf .doc .docx .xls .xlsx .ppt .pptx .jpg .jpeg .png .zip`
- 黑名单（显式拒绝，作为 defense-in-depth）：`.exe .bat .cmd .com .scr .pif .ps1 .psm1 .vbs .vbe .js .jse .wsf .wsh .msi .msp .dll .sh .bash .zsh .jar .app`
- 校验顺序：① 扩展名白名单 → ② 扩展名黑名单 → ③ MIME type 白名单 → ④ 文件头（magic number）匹配 → ⑤ zip 内文件名递归扫描黑名单
- 任一不通过 MUST 拒绝上传并写审计日志（`action=upload_rejected`，含 `rejection_reason`）

**BR-DOC-05 PDF 在线预览（OQ-05 决策）**：
- 仅 `doc_type=pdf` 的文档支持在线预览
- 后端提供 `GET /api/v1/documents/{id}/preview` 端点，权限同 download
- 响应 header：`Content-Type: application/pdf`、`Content-Disposition: inline`
- 前端用 pdf.js 渲染（CDN 或本地集成皆可）
- 预览端点 MUST 写审计日志（`action=document.preview`），便于追溯敏感文档查看记录

### 5.8 任务管理

**FR-TASK-01 字段**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `task_no` | string | auto | `{sub_project_no}-T-{seq}` |
| `sub_project_id` | uuid | ✅ | — |
| `phase_id` | uuid | ✅ | — |
| `name` | string | ✅ | — |
| `plan_end_date` | date | ✅ | — |
| `status` | enum | auto | 见 §1.5，由 task_executor 状态聚合 |
| `created_at` | timestamp | auto | — |

**FR-TASK-02 执行人**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `task_id` | uuid | ✅ | — |
| `user_id` | uuid | ✅ | MUST 是子项目成员 |
| `plan_end_date` | date | ✅ | 个人计划日期 |
| `actual_end_date` | date | auto | 完成时写入 |
| `status` | enum | auto | 见 §1.5 |
| `UNIQUE(task_id, user_id)` | | | |

**BR-TASK-01 状态聚合**：`task.status` MUST 由应用层服务方法聚合，不用 DB 触发器：
```python
def aggregate_task_status(task):
    statuses = [te.status for te in task.executors]
    if all(s == 'completed' for s in statuses):
        return 'completed'
    if any(s == 'overdue' for s in statuses):
        return 'overdue'
    if any(s == 'in_progress' for s in statuses):
        return 'in_progress'
    return 'not_started'
```
任何 `task_executor.status` 变更后 MUST 立即调用此函数更新 `task.status`，同事务。

**BR-TASK-02 逾期判定**：每日 09:00 定时任务扫描所有 `task_executor` where `plan_end_date < today` AND `status ∈ {not_started, in_progress}`，更新为 `overdue`。

### 5.9 撤销审批

**FR-REVOKE-01 流程**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `phase_id` | uuid | ✅ | 申请撤销的环节 |
| `applicant_id` | uuid | ✅ | `proj_leader` |
| `reason` | text | ✅ | — |
| `status` | enum | auto | `pending` / `approved` / `rejected` |
| `reviewer_id` | uuid | auto | `dept_manager` 或 `admin` |
| `review_comment` | text | ❌ | — |
| `reviewed_at` | timestamp | auto | — |

**BR-REVOKE-01**：仅可撤销 `status=completed` 的环节。撤销审核通过后：
- `phase.status = in_progress`
- `phase.finish_at = NULL`
- 该环节下所有 `is_latest=true` 文档 → `is_deleted=true`（按 BR-DOC-03）
- 该环节下所有 `task.status = completed` 的任务 → 保持 completed（不回滚任务），但记录审计日志说明背景
- 后续环节如果已经 `in_progress`，MUST 同步回滚为 `waiting`，并删除其下未上传的文档
- **通知规则**（OQ-08 决策）：MUST 通知该环节所有 `is_latest=true` 文档的 uploader，加上该子项目的 `proj_leader`。MUST NOT 通知其他子项目成员（避免噪声）。通知内容 MUST 包含：被撤销环节、被影响的文档清单、撤销原因。

### 5.10 站内通知

**FR-NOTIF-01 通知场景**

| 场景代码 | 触发 | 接收人 |
| --- | --- | --- |
| `project_pending_review` | 主/子项目提交 | 所有 `dept_manager`（除创建人） |
| `project_review_result` | 审核完成 | 创建人 |
| `task_assigned` | 任务指派 | 执行人 |
| `task_due_today` | 计划日期当天 09:00 | 执行人 + proj_leader |
| `task_overdue` | 逾期后每日 09:00 | 执行人 + proj_leader |
| `task_overdue_escalation` | 逾期 ≥ 7 天 | 上述 + admin |
| `phase_promoted` | 推进环节 | 子项目所有成员 |
| `payment_created` | 每次付款 | 子项目 proj_leader |
| `over_budget_warning` | 触发 BR-PAY-02 | 主项目 dept_manager + admin |
| `revoke_request_pending` | 撤销申请提交 | 所有 dept_manager |
| `revoke_result` | 撤销审核完成 | 申请人 + 该环节文档 uploader + 子项目 proj_leader（**不**通知其他成员，OQ-08）|

**BR-NOTIF-01 去重键（修订 V2.0 漏洞）**：
```
dedup_key = {scenario_code}:{receiver_id}:{source_id}:{date_yyyymmdd}
```
MUST 包含 `source_id`，否则同日多任务到期会被错误去重为 1 条。

### 5.11 审计日志

**FR-AUDIT-01**：所有 write 操作 MUST 记录：
- `actor_id`（NULL 表示系统）
- `action`（如 `main_project.create`, `payment.reverse`）
- `target_type` + `target_id`
- `before_state` (JSONB)
- `after_state` (JSONB)
- `ip_address`, `user_agent`
- `extra` (JSONB) — 用于 `admin_override`、`over_budget` 等业务标记

**BR-AUDIT-01**：审计日志 MUST 仅追加，按月分区（`PARTITION BY RANGE (created_at)`），保留 ≥ 2 年。

---

## 6. 非功能性需求

| 类别 | 要求 |
| --- | --- |
| 接口响应 | P99 ≤ 800ms（目标），告警阈值 1.5s（修订 V2.0 阈值过严） |
| 页面加载 | 首屏 ≤ 2s（包含登录态校验） |
| 并发 | 同时在线 ≥ 50 人 |
| 可用性 | 工作时间 99.5%（非工作时间允许维护） |
| 数据安全 | Bcrypt 12 轮；JWT RS256；敏感操作审计；TLS 1.2+ |
| 文件存储 | 单文件 ≤ 50MB；MIME 白名单 + 文件头校验 + 可执行文件黑名单（见 BR-DOC-04）|
| 文件类型 | pdf, doc, docx, xls, xlsx, ppt, pptx, jpg, png, zip |
| 文件预览 | PDF 文件 MUST 支持浏览器内预览（pdf.js 前端实现，OQ-05）；其他类型仅下载 |
| 浏览器 | Chrome / Edge / Firefox 最新 2 个主版本 |
| 移动端 | 响应式 H5，支持查看 + 任务完成 + 文档下载（不支持审核 / 付款 / 推进） |

---

## 7. 系统架构（强约束）

| 层 | 技术 | 备注 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Axios | TypeScript |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 | Python 3.11+ |
| DB | PostgreSQL 16 | 直接生产 PG，跳过 SQLite |
| 缓存 | Redis 7 | 用于 session 计数器 + JWT 黑名单 + Celery broker |
| 异步任务 | Celery + Redis | （修订 V2.0：既然已有 Redis，不再用 APScheduler） |
| 文件存储 | 本地（dev）/ S3 兼容 OSS（prod） | 抽象 `StorageBackend` 接口 |
| 认证 | JWT RS256，Access 30min + Refresh 7d | （修订 V2.0：access 从 2h 缩到 30min） |
| 数据权限 | **应用层 service 过滤**，**不用** PostgreSQL RLS | （修订 V2.0：RLS + dept_id 无法表达项目成员关系） |
| 接口风格 | RESTful，前缀 `/api/v1/`，响应 `{code, message, data}` | — |

---

## 8. 接口路径约定

完整接口列表见开发计划 §6。命名规则：
- 资源用复数：`/main-projects`, `/sub-projects`
- 状态变更用动词子路径：`POST /main-projects/{id}/submit`, `/review`, `/close`
- 嵌套资源最多 2 级：`/sub-projects/{id}/payments`，再深用顶级 + 过滤参数

---

## 9. 已修订的歧义清单（V2.0 → V2.1 变更追踪）

| ID | V2.0 问题 | V2.1 修订 |
| --- | --- | --- |
| FIX-01 | 状态枚举缺 `已退回` 但流程提到 | 枚举补齐 `rejected` |
| FIX-02 | 主项目可能自审死锁 | 新增 BR-ROLE-01 + BR-ROLE-02（admin 兜底） |
| FIX-03 | 删除超预算预警有资金风险 | 新增 BR-PAY-02 软阻断 + 二次确认 + 审计 |
| FIX-04 | 后评价可在立项前完成 | BR-PHASE-02 后评价依赖验收完成 |
| FIX-05 | 三选一 / 四选一冲突 | §1.7 明确 OA 必传 + 后三选一 |
| FIX-06 | unique_key 自相矛盾 + 撤销重置版本号会冲突 | BR-DOC-01 改用 `(sub_project, phase, doc_type, version)`；BR-DOC-03 改软删除 |
| FIX-07 | 角色命名 `project_manager` vs `proj_leader` | 全文锁定 `proj_leader` |
| FIX-08 | 通知 dedup_key 漏 source_id | BR-NOTIF-01 修复 |
| FIX-09 | 任务双 status 同步规则缺失 | BR-TASK-01 明确应用层聚合 |
| FIX-10 | 财务付款无修改机制 | BR-PAY-01 红冲机制 |
| FIX-11 | JWT access 2h 太长 | §7 改为 30min |
| FIX-12 | RLS 无法表达项目成员关系 | §7 改为应用层过滤 |
| FIX-13 | APScheduler 与 Redis 重复 | §7 统一用 Celery |
| FIX-14 | `is_required` 不该在 documents 表 | §3.2 + FR-DOC-01 移到 phase_doc_template |
| FIX-15 | 撤销后状态恢复细节缺失 | BR-REVOKE-01 完整规则 |
| FIX-16 | 监控阈值 = SLA 阈值会误报 | §6 SLA 800ms / 告警 1.5s |
| FIX-17 | 后评价环节顺序漏洞 | BR-PHASE-02 |
| FIX-18 | 子项目缺 `actual_end_date` 无法统计工期 | FR-SUB-01 保留并自动维护 |
| FIX-19 (V2.2) | OQ-05 决策：新增 PDF 在线预览 | BR-DOC-05 + 新接口 `/documents/{id}/preview` |
| FIX-20 (V2.2) | OQ-06 决策：显式拦截可执行文件 | BR-DOC-04 双重校验（白名单 + 黑名单 + zip 内扫描） |
| FIX-21 (V2.2) | OQ-08 决策：撤销通知改为务实版（uploader + proj_leader） | BR-REVOKE-01 + FR-NOTIF-01 |
| FIX-22 (V2.2) | OQ-09 决策：项目负责人转交流程 | 新增 FR-USER-02 + BR-USER-01/02 + `sub_project_handovers` 表 |

---

## 10. 已确认决策记录（V2.2 Sign-off）

以下决策已经业务方确认，agent MUST 直接遵循实现，不得再询问。

| OQ-ID | 决策 | 实现要点 | 影响章节 |
| --- | --- | --- | --- |
| OQ-01 | A：立项部门可以等于综合部 | `dept_id` 无额外校验 | FR-MAIN-01 |
| OQ-02 | A：子项目超预算仅警告 + 审计 | 维持 BR-PAY-02 / BR-SUB-02 | FR-SUB-02 |
| OQ-03 | A：数据永久保留 | 不设归档脚本；监控数据库容量 | T-1-DEPLOY-* |
| OQ-04 | A：移动端不支持 SSO | 仅用户名密码 | FR-AUTH-* |
| OQ-05 | **B**：PDF 在线预览（pdf.js） | 见 BR-DOC-05 + 新任务 T-1-DOC-03 | FR-DOC-01 |
| OQ-06 | **A + 拦截可执行文件** | 见 BR-DOC-04 黑名单 | FR-DOC-01 |
| OQ-07 | A：仅站内通知 | 不集成企业微信/钉钉/邮件 | FR-NOTIF-* |
| OQ-08 | **C**（务实版）：仅通知 uploader + proj_leader | 见 BR-REVOKE-01 + FR-NOTIF-01 | FR-REVOKE-01 |
| OQ-09 | A：admin 手动转交 | 见 FR-USER-02 + BR-USER-01/02 + 新任务 T-1-USER-04 | FR-USER-* |
| OQ-10 | A：单时区 Asia/Shanghai | Celery beat 固定时区 | T-1-CRON-02 |

**OQ-09 子问题确认**：
- ✅ proj_member 不转交（原 member 关系保留，账号停用后失效）
- ✅ 保留历史负责人记录（`sub_project_handovers` 表）
- ✅ closed/terminated 项目不转交（UI 标"已离岗"）

**OQ-08 选 C 的解读**（务实版，业务方确认）：
通知范围 = 文档 uploader + 子项目 proj_leader。原选项字面意思仅 uploader，但 proj_leader 需要重新组织环节，必须知情；其他 proj_member 不通知，避免噪声。

---

*— 需求规格 V2.1 完 —*
