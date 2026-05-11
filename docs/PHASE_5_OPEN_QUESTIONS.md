# Phase 5 开放问题默认决策

> 本文把 `docs/ROADMAP.md` Phase 5 中的 OQ 固化为可执行默认值。用户已授权后续由 Agent 自行确认并继续推进，因此在没有新的业务反馈前，本文件作为 Phase 5 实施依据。

## OQ-23 是否突破单项目类型

**Decision:** Phase 5 突破单一采购项目模型，但采用兼容迁移：先引入 `project_types`、`workflow_templates`、`workflow_template_versions` 和动态环节定义，现有采购项目自动绑定内置“采购项目”类型与默认 6 环节模板。

**Rationale:**

- Roadmap 的平台化目标要求支持科研、合规、人力等非采购项目；继续在代码里硬编码 6 环节会阻塞后续演进。
- 直接重写现有项目、环节、文档体系风险太高，必须用兼容层逐步抽象。
- 已上线数据不能被模板变更影响，因此流程必须按版本固定到项目实例。

**Implementation notes:**

- 新增项目类型和流程模板模型，不删除现有 `phases`、`phase_doc_templates` 语义。
- 现有采购 6 环节作为系统内置模板版本 `procurement-v1`。
- 新建子项目时写入 `workflow_template_version_id`，后续模板修改不影响该子项目已生成环节。
- 模板版本发布后不可变；编辑草稿必须生成新版本。
- 前端先提供 admin 模板管理，普通用户仍通过现有项目创建流程进入默认采购模板。

## OQ-24 BI 工具自研 vs 集成开源

**Decision:** Phase 5 先实现内置轻量自定义报表设计器，不引入 Metabase 或 Superset 作为运行时依赖。

**Rationale:**

- 当前系统已有报表、权限、审计、导出和通知基础；轻量报表可以复用这些能力。
- 外部 BI 工具需要额外身份集成、权限同步、部署和审计边界，生产试用阶段成本偏高。
- 内置设计器先限制在白名单数据集与字段，能避免任意 SQL 带来的数据越权风险。

**Implementation notes:**

- 后端提供 `report_datasets` 注册表，字段、筛选器、聚合和维度均由代码或迁移白名单定义。
- 自定义报表定义保存为 JSON 配置，不保存用户自定义 SQL。
- 查询编译器只生成受控 SQLAlchemy 查询，并强制注入 RBAC 范围。
- 图表类型先支持表格、柱状图、折线图、饼图和指标卡。
- 定时报表复用 Celery、通知通道和数据库导出能力。

## OQ-25 AI 模型选型

**Decision:** Phase 5 建立 AI provider 抽象，默认关闭外部调用；本地开发和测试使用 fake provider，生产可通过环境变量启用 OpenAI-compatible HTTP provider 或私有化模型网关。

**Rationale:**

- AI 能力需要隐私、成本和可解释性控制，不应成为系统启动依赖。
- 使用 provider 抽象能兼容外部 API 与私有化部署，也能让 CI 不依赖真实凭据。
- 先做可审计、可关闭、可降级的辅助能力，避免把核心流程绑定到模型输出。

**Implementation notes:**

- 配置项包含 `AI_ENABLED`、`AI_PROVIDER`、`AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`、`AI_TIMEOUT_SECONDS`。
- 默认 `AI_ENABLED=false`，所有 AI 接口返回明确的未启用状态。
- 所有发给模型的 payload 必须写入脱敏摘要、操作者、用途、token 估算和响应状态审计。
- Provider 输出必须经过 Pydantic schema 校验；校验失败时降级为规则结果或空建议。
- 不把文件原文默认发送给外部模型；文档分类先只发送文件名、扩展名、业务上下文和可配置短摘要。

## OQ-26 哪些 AI 场景值得做

**Decision:** Phase 5 先实现三个低风险闭环：项目风险评分、文档类型建议和自然语言指标问答；智能催办只做规则化建议，不自动改变发送时间。

**Rationale:**

- 项目风险评分可以先用确定性规则落地，再由 AI 生成解释摘要，业务价值清晰且可验证。
- 文档类型建议发生在上传前后，用户可确认或忽略，不会自动改变审批结果。
- 指标问答限定在白名单数据集，能复用自定义报表层并控制数据范围。
- 智能催办涉及行为画像和通知时机优化，先输出建议，避免误发通知。

**Implementation notes:**

- 风险评分使用延期、超预算、撤销次数、任务逾期、环节停留时间等信号，输出 0-100 分和原因列表。
- AI narrative 仅用于解释已计算出的规则信号，不允许模型直接修改评分。
- 文档分类建议返回候选 `doc_type`、置信度和原因；用户确认后才写入文档记录。
- 指标问答将自然语言映射到已注册 dataset、filters、metrics，不执行任意 SQL。
- 所有 AI 建议都保留“由系统生成，需人工确认”的审计状态。
