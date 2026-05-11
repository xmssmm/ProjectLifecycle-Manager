# Phase 4 开放问题默认决策

> 本文把 `docs/ROADMAP.md` Phase 4 中的 TBD 和 OQ 固化为可执行默认值。后续若业务方有明确反馈，以新决策覆盖本文；在没有反馈前，开发不再被这些问题阻塞。

## OQ-19 归档阈值

**Decision:** 已结项主项目默认在 `closed_at <= now() - 2 years` 时进入归档候选。

**Rationale:**

- Roadmap 已给出“已结项 >= 2 年”的业务假设，先按该值执行。
- `completed` 仍可能有收尾动作；只有 `closed` 视为归档安全状态。
- 当前主项目没有独立 `closed_at` 字段，Phase 4 归档任务会补充该字段，并将历史 `closed` 数据以 `updated_at` 回填。

**Implementation notes:**

- 主项目、子项目在进入 `closed` 状态时写入 `closed_at`。
- 历史数据迁移时，对 `closed_at IS NULL AND status = 'closed'` 的记录用 `updated_at` 回填。
- 归档候选只包含主项目状态为 `closed` 且所有子项目处于 `closed` 或 `terminated` 的项目。

## OQ-20 归档存储位置

**Decision:** Phase 4 使用同库不同表的 `archive_*` 表；暂不切换独立归档库或对象存储。

**Rationale:**

- 同库归档能先完成性能隔离和恢复闭环，复杂度低于跨库事务。
- 后续迁移独立 archive DB 时，可以把 `archive_*` 表作为边界。
- 文档文件本体继续留在现有文件存储路径；归档表保存文件路径、哈希和元数据快照。

**Implementation notes:**

- 建立 `archive_batches`、`archive_main_projects`、`archive_sub_projects`、`archive_phases`、`archive_documents`、`archive_tasks`、`archive_payments`、`archive_acceptance_steps`、`archive_project_reviews`。
- 归档表保留关键筛选列，并额外保存 `snapshot JSONB`，确保可审计和可恢复。
- 用户常规列表默认只查主表；详情、搜索和报表提供 `include_archived` 或专用归档查询入口。
- 恢复操作必须写审计日志，并校验主表不存在同 `original_id` 或业务唯一键冲突。

## OQ-21 全文检索引擎

**Decision:** Phase 4 首选 PostgreSQL FTS；暂不引入 OpenSearch / Elasticsearch。

**Rationale:**

- 当前系统已依赖 PostgreSQL，PG FTS 能满足合规检索和小到中等规模文档检索。
- 避免在 Phase 4 同时引入额外搜索集群、同步链路和运维成本。
- 后续如果文档量或检索能力超过 PG FTS，可将 `document_search_entries` 作为外部搜索同步源。

**Implementation notes:**

- 新增 `document_search_entries`，包含 `document_id`、`language`、`plain_text`、`search_vector`、`indexed_at`、`extract_status`。
- PDF 使用 Python 文本提取库；Office 文档优先走可部署的转换/提取器；扫描件 OCR 作为可配置 worker 能力。
- 上传或版本更新后异步抽取，5 分钟内可检索。
- `GET /api/v1/search?q=...&scope=documents` 先实现文档范围，后续可扩展项目和任务。

## OQ-22 多时区边界

**Decision:** 用户时区保存为 IANA timezone 字符串，默认 `Asia/Shanghai`；数据库继续保存 timezone-aware UTC 时间。

**Rationale:**

- IANA 时区能正确处理夏令时。
- 前端显示按用户配置转换，避免更改已有数据库语义。
- 无效或缺失时区一律回退 `Asia/Shanghai`，并在写入时校验。

**Implementation notes:**

- `users.timezone` 默认 `Asia/Shanghai`。
- 认证响应和用户资料接口返回 `timezone`。
- 前端统一通过时间格式化工具渲染日期时间。
- 定时摘要按用户时区分组计算本地 09:00。

## OQ-23 高可用落地边界

**Decision:** Phase 4 先实现应用可配置能力和生产部署文档，再提供主从 / Sentinel / 多副本 compose 示例；本地测试不依赖真实 HA 集群。

**Rationale:**

- PostgreSQL 主从、Redis Sentinel 和应用水平扩展主要是部署拓扑，不应让单机 CI 变复杂。
- 代码层需要支持只读连接、健康检查、Redis Sentinel 配置和无状态多副本。

**Implementation notes:**

- 后端配置增加可选 `DATABASE_REPLICA_URL` 和 Redis Sentinel 配置。
- 报表、仪表盘等读密集服务可走只读 session。
- 生产部署手册包含故障切换、回滚和容量验证步骤。
