# Phase 3 企业集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 roadmap Phase 3“企业集成”的全部功能，让系统接入企业身份、外部通知、安全扫描和外部系统数据交换。

**Architecture:** Phase 3 在现有 FastAPI/Vue/Celery 架构上增加独立集成层：SSO provider、通知 channel、ClamAV scan、external API key、webhook dispatcher。所有外部依赖都用接口隔离，并用 fake transport 在测试中验证，不要求真实第三方凭据。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、Redis、Celery、Vue 3、Pinia、Element Plus、Jinja2、ClamAV daemon、HMAC、pytest、Vitest。

---

## 1. 默认决策

详见 `docs/PHASE_3_OPEN_QUESTIONS.md`：

- SSO 先做通用 OAuth2/OIDC provider，本地和 CI 使用 fake provider。
- SSO 不自动创建用户；必须先有本地账号。
- 本地账号和 SSO 双轨共存，但 admin 可设置某用户必须 SSO。
- 开放 API 按 API Key 限流，IP 限流兜底。
- Webhook 失败重试 5 次，指数退避，最终进入死信表并通知 admin。

## 2. 任务顺序

### T-3-PLAN-01 Phase 3 计划与决策文档

**Files:**

- Create: `docs/PHASE_3_OPEN_QUESTIONS.md`
- Create: `docs/PHASE_3_PLAN.md`

**Steps:**

- [ ] 写入默认决策，覆盖 OQ-14 到 OQ-18。
- [ ] 按依赖拆分 Phase 3 任务。
- [ ] 运行 `git diff --check`。
- [ ] 提交并合并到 `develop`。

**DoD:**

- [ ] 文档可直接指导后续开发。
- [ ] 没有未决项阻塞实现。

### T-3-AUTH-01 OAuth2/OIDC 通用适配层

**Files:**

- Create: `backend/app/models/oauth.py`
- Create: `backend/alembic/versions/0020_create_oauth_bindings.py`
- Create: `backend/app/services/oauth.py`
- Create: `backend/app/schemas/oauth.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_oauth_service.py`

**Implementation:**

- 新增 `oauth_bindings` 表：`user_id`、`provider`、`external_id`、`email`、`access_token_ciphertext`、`refresh_token_ciphertext`、`expires_at`、`created_at`、`updated_at`。
- 新增 provider 配置对象：authorize URL、token URL、userinfo URL、scope、client_id、client_secret。
- `OAuthService.start_login(provider, actor=None)` 生成 authorization URL，state 存 Redis，TTL 10 分钟。
- `OAuthService.handle_callback(provider, code, state)` 校验 state，交换 token，读取 userinfo，并返回可绑定的外部身份。
- token 和 state 不写明文日志。

**Test plan:**

- [ ] state 缺失或过期时拒绝回调。
- [ ] token exchange 失败时返回业务错误。
- [ ] userinfo 缺少 external_id 时拒绝。
- [ ] 已绑定 external_id 时可解析到本地用户。

**Verification:**

- `cd backend && python -B -m pytest -q tests/unit/test_oauth_service.py --no-cov`
- `cd backend && python -B -m ruff check .`
- `cd backend && python -B -m mypy app tests`

### T-3-AUTH-02 通用 OIDC 登录与账号绑定

**Files:**

- Create: `backend/app/api/v1/oauth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/auth.py`
- Create: `frontend/src/api/oauth.ts`
- Create: `frontend/src/types/oauth.ts`
- Modify: `frontend/src/views/auth/LoginView.vue`
- Modify: `frontend/src/views/Profile.vue`
- Test: `backend/tests/unit/test_oauth_api.py`
- Test: `frontend/tests/oauth-api.test.ts`
- Test: `frontend/tests/login-sso.test.ts`
- Test: `frontend/tests/profile-sso-binding.test.ts`

**Implementation:**

- `GET /api/v1/oauth/{provider}/login` 返回授权跳转 URL。
- `GET /api/v1/oauth/{provider}/callback` 完成登录并签发系统 token。
- `POST /api/v1/oauth/{provider}/bind` 让已登录用户绑定外部身份。
- `DELETE /api/v1/oauth/{provider}/bind` 解绑。
- 登录页显示“企业账号登录”，Profile 页显示绑定状态。
- 找不到本地账号时拒绝登录，不自动创建用户。

**Test plan:**

- [ ] 已绑定用户可通过 SSO 登录。
- [ ] 未绑定但 email 匹配已有用户时可提示绑定或自动绑定已登录会话。
- [ ] 找不到用户时返回明确错误。
- [ ] 前端点击企业登录会调用 login URL 并跳转。

### T-3-AUTH-03 SSO 与本地账号共存策略

**Files:**

- Modify: `backend/app/models/users.py`
- Create: `backend/alembic/versions/0021_add_user_sso_policy.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/services/users.py`
- Modify: `backend/app/schemas/users.py`
- Modify: `frontend/src/views/admin/UserList.vue`
- Modify: `frontend/src/types/users.ts`
- Test: `backend/tests/unit/test_auth_service.py`
- Test: `backend/tests/unit/test_user_service.py`
- Test: `frontend/tests/user-management-page.test.ts`

**Implementation:**

- `users.sso_required` 默认 `false`。
- 本地密码登录时，若 `sso_required=true`，返回业务错误。
- admin 用户管理页可切换 SSO 强制策略。
- 切换策略写审计日志。

**Test plan:**

- [ ] 强制 SSO 用户不能密码登录。
- [ ] 非强制用户仍可密码登录。
- [ ] admin 可更新策略，非 admin 不可更新。

### T-3-NOTIF-01 通知通道抽象与偏好扩展

**Files:**

- Create: `backend/app/services/notification_channels.py`
- Create: `backend/alembic/versions/0022_add_notification_channels.py`
- Modify: `backend/app/models/notifications.py`
- Modify: `backend/app/services/notifications.py`
- Modify: `backend/app/schemas/notifications.py`
- Modify: `frontend/src/views/Profile.vue`
- Modify: `frontend/src/types/notifications.ts`
- Test: `backend/tests/unit/test_notification_channels.py`
- Test: `backend/tests/unit/test_notification_service.py`
- Test: `frontend/tests/profile-password-page.test.ts`

**Implementation:**

- 增加 channel 枚举：`in_app`、`email`、`wework`、`dingtalk`。
- 用户偏好支持每个场景的 channel 开关。
- 站内通知保持默认开启，兼容已有实时/摘要模式。
- `NotificationChannel` 接口包含 `send(message) -> ChannelDeliveryResult`。

**Test plan:**

- [ ] 关闭某 channel 后不触发该 channel。
- [ ] 站内通知现有逻辑不回退。
- [ ] Profile 页可保存 channel 偏好。

### T-3-NOTIF-04 SMTP 邮件通知适配

**Files:**

- Create: `backend/app/services/email_channel.py`
- Create: `backend/app/templates/notifications/email/*.j2`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_email_channel.py`

**Implementation:**

- 支持 SMTP host、port、username、password、from address、TLS。
- Jinja2 模板渲染任务到期、项目待审核等通知。
- 邮件发送使用可替换 transport，单测用 fake transport。
- 邮件退订只影响 email channel，不影响站内通知。

**Test plan:**

- [ ] 模板变量完整渲染。
- [ ] SMTP 失败返回失败结果，不影响站内通知落库。
- [ ] 退订用户不发邮件。

### T-3-NOTIF-02 企业微信通知适配

**Files:**

- Create: `backend/app/services/wework_channel.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_wework_channel.py`

**Implementation:**

- Phase 3 采用企业微信机器人 Webhook。
- 支持签名 secret。
- 任务到期和项目待审核两个场景必须跑通。
- 单测用 fake HTTP transport 验证请求体。

**Test plan:**

- [ ] 签名参数正确。
- [ ] Markdown 消息内容包含业务链接。
- [ ] 非 2xx 响应返回失败结果。

### T-3-NOTIF-03 钉钉通知适配

**Files:**

- Create: `backend/app/services/dingtalk_channel.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_dingtalk_channel.py`

**Implementation:**

- Phase 3 采用钉钉机器人 Webhook。
- 支持 timestamp + secret 签名。
- 任务到期和项目待审核两个场景必须跑通。
- 单测用 fake HTTP transport。

**Test plan:**

- [ ] 签名算法正确。
- [ ] Markdown 消息内容包含业务链接。
- [ ] 超时或非 2xx 进入失败结果。

### T-3-NOTIF-05 通知失败重试与死信队列

**Files:**

- Create: `backend/app/models/notification_deliveries.py`
- Create: `backend/alembic/versions/0023_create_notification_deliveries.py`
- Create: `backend/app/tasks/notification_delivery.py`
- Modify: `backend/app/tasks/celery_app.py`
- Modify: `backend/app/tasks/task_names.py`
- Test: `backend/tests/unit/test_notification_delivery_retry.py`

**Implementation:**

- 每次外部 channel 发送生成 delivery 记录。
- 失败重试 3 次用于 channel 通知，webhook 另按 T-3-API-03 使用 5 次。
- 最终失败进入 `dead_letter` 状态并通知 admin 站内消息。
- delivery 记录包含 channel、scenario、receiver_id、attempt_count、last_error、next_retry_at。

**Test plan:**

- [ ] 失败后 attempt_count 增加。
- [ ] 到达上限进入 dead_letter。
- [ ] 成功后状态为 delivered。

### T-3-DOC-01 ClamAV 主动扫描

**Files:**

- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`
- Modify: `backend/app/models/documents.py`
- Create: `backend/alembic/versions/0024_add_document_scan_status.py`
- Create: `backend/app/services/virus_scan.py`
- Create: `backend/app/tasks/document_scanning.py`
- Modify: `backend/app/services/documents.py`
- Modify: `frontend/src/components/document/DocumentList.vue`
- Test: `backend/tests/unit/test_virus_scan.py`
- Test: `backend/tests/unit/test_document_service.py`
- Test: `frontend/tests/document-components.test.ts`

**Implementation:**

- Docker 添加 `clamav` 服务。
- 文档字段：`scan_status=pending|clean|infected|failed`、`scan_result`、`scanned_at`。
- 上传成功后异步扫描，不阻塞上传响应。
- infected 文件隔离，下载和预览被拒绝，并通知 uploader + admin。
- 前端显示扫描中、已通过、已隔离。

**Test plan:**

- [ ] EICAR 测试内容被识别为 infected。
- [ ] pending 文档可见但下载/预览策略按需求限制。
- [ ] infected 文档下载被拒绝。

### T-3-USER-01 proj_leader 自助转交流程

**Files:**

- Create: `backend/app/models/handover_requests.py`
- Create: `backend/alembic/versions/0025_create_handover_requests.py`
- Create: `backend/app/services/handover_requests.py`
- Create: `backend/app/api/v1/handover_requests.py`
- Create: `frontend/src/views/handover/SelfServiceHandover.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `backend/tests/unit/test_handover_request_service.py`
- Test: `frontend/tests/handover-page.test.ts`

**Implementation:**

- 原 proj_leader 发起转交，候选人确认，dept_manager 审核，审核通过后生效。
- admin 兜底强制转交通道保留。
- 候选人 7 天未确认后，admin 可强制处理。
- 全流程写审计日志和通知。

**Test plan:**

- [ ] 发起人不能选择自己。
- [ ] 候选人确认前不改变项目负责人。
- [ ] dept_manager 审核通过后批量转交关联子项目。
- [ ] 超过 7 天 admin 可强制转交。

### T-3-API-01 API Key 管理

**Files:**

- Create: `backend/app/models/api_keys.py`
- Create: `backend/alembic/versions/0026_create_api_keys.py`
- Create: `backend/app/services/api_keys.py`
- Create: `backend/app/api/v1/api_keys.py`
- Create: `frontend/src/views/admin/ApiKeyManagement.vue`
- Test: `backend/tests/unit/test_api_key_service.py`
- Test: `frontend/tests/api-key-management-page.test.ts`

**Implementation:**

- admin 可签发、查看、吊销 API Key。
- 只存 key hash，不存明文。
- Key 支持 permissions、expires_at、last_used_at。
- 创建时只返回一次明文 token。

**Test plan:**

- [ ] 明文 token 只在创建响应出现。
- [ ] 过期和吊销 key 立即拒绝。
- [ ] 权限范围不足时拒绝。

### T-3-API-02 公开 Read-only API

**Files:**

- Create: `backend/app/api/external/v1/router.py`
- Create: `backend/app/api/external/v1/projects.py`
- Create: `backend/app/api/external/v1/payments.py`
- Create: `backend/app/api/external/v1/documents.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_external_api.py`

**Implementation:**

- 新增 `/api/external/v1/*`。
- 支持读取项目、付款、文档元数据。
- API Key 认证和限流。
- 返回字段不暴露内部敏感信息。

**Test plan:**

- [ ] 无 Key 拒绝。
- [ ] Key 权限不足拒绝。
- [ ] Key 有权限时只读接口返回正确数据。
- [ ] 1000 次/小时限流生效。

### T-3-API-03 Webhook 推送

**Files:**

- Create: `backend/app/models/webhooks.py`
- Create: `backend/alembic/versions/0027_create_webhooks.py`
- Create: `backend/app/services/webhooks.py`
- Create: `backend/app/tasks/webhooks.py`
- Create: `backend/app/api/v1/webhooks.py`
- Create: `frontend/src/views/admin/WebhookManagement.vue`
- Test: `backend/tests/unit/test_webhook_service.py`
- Test: `backend/tests/unit/test_webhook_task.py`
- Test: `frontend/tests/webhook-management-page.test.ts`

**Implementation:**

- admin 可配置 webhook URL、secret、事件类型。
- 支持项目状态变更、付款发生、环节推进、撤销审核完成。
- 推送带 `X-Event-Id`、`X-Signature`、`X-Timestamp`。
- 失败重试 5 次，指数退避，最终进入死信表。
- 死信可查询和手动重放。

**Test plan:**

- [ ] HMAC 签名稳定可验证。
- [ ] 2xx 视为成功。
- [ ] 非 2xx 或超时按计划重试。
- [ ] 到达上限进入 dead_letter。

### T-3-DOCS-01 Phase 3 文档与发布说明

**Files:**

- Create: `docs/RELEASE_NOTES_PHASE_3.md`
- Modify: `docs/deployment-manual.md`
- Modify: `docs/user-manual.md`
- Modify: `docs/operations.md`
- Modify: `docs/troubleshooting.md`

**Implementation:**

- 补充 SSO 配置、SMTP/企业微信/钉钉配置、ClamAV 部署、API Key 和 Webhook 运维。
- 使用手册增加企业登录、外部通知偏好、自助转交、开放 API 管理。
- 故障排查增加 SSO 回调失败、邮件发送失败、病毒库更新失败、Webhook 重试堆积。

**Verification:**

- `git diff --check`
- 抽查所有新增命令和 compose service 名称一致。

## 3. Phase 3 验收

- [ ] SSO 登录、绑定、解绑、强制 SSO 策略可运行。
- [ ] 邮件、企业微信、钉钉三个外部通知通道可配置并可测试。
- [ ] 通知失败重试和死信队列可验证。
- [ ] ClamAV 可识别 EICAR 并阻止 infected 文档下载/预览。
- [ ] proj_leader 自助转交流程完整跑通。
- [ ] API Key 可签发、吊销、限流，外部只读 API 可消费。
- [ ] Webhook 可配置、签名、重试、死信和重放。
- [ ] 后端 `ruff`、`mypy`、`pytest` 通过。
- [ ] 前端 `npm run lint`、`npm run typecheck`、`npm run test:unit`、`npm run build` 通过。
- [ ] 中文部署、使用、运维、故障排查和发布说明已更新。
