# 开发计划 V2.0（全功能版，对齐需求 V2.2）

| 项目 | 内容 |
| --- | --- |
| 版本 | V2.0（全功能版） |
| 日期 | 2026-05-10 |
| 配套需求 | REQUIREMENTS.md V2.2（已 Sign-off） |
| 适用 | LLM Agent 自主执行 / 人机协作 |
| 与 V1.1 区别 | V1.1 偏 MVP 颗粒；V2.0 显式拆分前后端、补全跨切关注点、覆盖 V2.2 全部 FR / BR / NFR；任务数 40 → 95 |

---

## 0. 如何使用本计划（LLM Agent 必读）

1. **任务 ID 规则**：`T-1-{module}-{seq}`（例 `T-1-AUTH-BE-02`）。BE = 后端，FE = 前端，未标记 = 全栈或基础设施。
2. **依赖规则**：`depends_on` 列出的任务 MUST 全部完成才能开始。
3. **DoD 严格执行**：每个任务的 DoD 全部满足才算完成。
4. **本计划已对齐 REQUIREMENTS V2.2 全部 FR/BR/NFR**，agent 不应自创需求；遇到未覆盖的边界 case，按 `AGENT_KICKOFF_PROMPT.md §D` 流程提问。
5. **代码规范**遵循 §3 工程规范，不得引入计划外的库。
6. **测试是 DoD 一部分**，不是可选项。覆盖率门槛见 §8。

---

## 1. 技术栈（已锁定，不得替换）

### 1.1 后端

| 用途 | 选型 | 版本 |
| --- | --- | --- |
| Web 框架 | FastAPI | ≥0.110 |
| ORM | SQLAlchemy | 2.0+（强制 typed style） |
| Schema 验证 | Pydantic | v2 |
| 数据库迁移 | Alembic | 最新稳定 |
| 认证 | python-jose + passlib[bcrypt] | — |
| 异步任务 | Celery | ≥5.3 |
| HTTP server | uvicorn (dev) / gunicorn + uvicorn workers (prod) | — |
| 测试 | pytest + pytest-asyncio + factory-boy + httpx + testcontainers | — |
| 代码风格 | ruff + mypy strict | — |
| 数据库 | PostgreSQL | 16 |
| 缓存/队列 | Redis | 7 |
| PDF/文件处理 | pypdf, python-magic, openpyxl（仅报表用，本期可不引入） | — |
| 日志 | structlog | — |
| 监控 | prometheus-client | — |

### 1.2 前端

| 用途 | 选型 | 版本 |
| --- | --- | --- |
| 框架 | Vue | 3.4+ |
| 构建 | Vite | 5+ |
| 语言 | TypeScript | 5+, strict |
| UI 库 | Element Plus | 最新稳定 |
| 状态 | Pinia | — |
| HTTP | Axios | — |
| 路由 | Vue Router | 4+ |
| PDF 预览 | pdfjs-dist | 4+ |
| 测试 | Vitest + Vue Test Utils | — |
| 代码风格 | eslint + prettier + stylelint | — |

### 1.3 基础设施

| 用途 | 选型 |
| --- | --- |
| 容器 | Docker + docker-compose（dev/test）/ k8s（prod 可选） |
| 反向代理 | Nginx |
| 文件存储 | 本地（dev）/ S3 兼容 OSS（prod） |
| 监控 | Prometheus + Grafana |
| 日志 | structlog → JSON 输出，stdout 收集 |

---

## 2. 项目结构（必须遵循）

```
project-mgmt/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── departments.py
│   │   │   ├── system.py             # health-warnings, version
│   │   │   ├── main_projects.py
│   │   │   ├── sub_projects.py
│   │   │   ├── phases.py
│   │   │   ├── acceptance_steps.py
│   │   │   ├── payments.py
│   │   │   ├── tasks.py
│   │   │   ├── documents.py
│   │   │   ├── notifications.py
│   │   │   ├── revoke_requests.py
│   │   │   └── audit_logs.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── db.py
│   │   │   ├── deps.py
│   │   │   ├── exceptions.py
│   │   │   ├── permissions.py
│   │   │   ├── middleware.py        # request_id, audit context
│   │   │   ├── pagination.py
│   │   │   └── responses.py         # 统一响应封装
│   │   ├── models/                  # SQLAlchemy ORM, 按业务实体分文件
│   │   ├── schemas/                 # Pydantic 请求/响应
│   │   ├── services/                # 业务逻辑层
│   │   ├── tasks/                   # Celery jobs
│   │   │   ├── celery_app.py
│   │   │   ├── reminder_jobs.py
│   │   │   ├── overdue_jobs.py
│   │   │   └── cleanup_jobs.py
│   │   ├── storage/
│   │   │   ├── base.py              # StorageBackend 接口
│   │   │   ├── local.py
│   │   │   └── s3.py                # 占位实现（生产）
│   │   ├── validators/              # 文件校验等独立工具
│   │   │   └── file_validator.py    # MIME + magic + 黑名单 + zip 内扫描
│   │   ├── seeds/                   # 初始化数据
│   │   │   ├── default_admin.py
│   │   │   ├── default_departments.py
│   │   │   └── phase_doc_templates.py
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── factories/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                     # Axios 模块（按资源拆分）
│   │   │   ├── client.ts            # Axios 实例 + 拦截器
│   │   │   ├── auth.ts
│   │   │   ├── users.ts
│   │   │   ├── ...
│   │   ├── components/              # 通用组件
│   │   │   ├── layout/              # AppLayout, Sidebar, Header
│   │   │   ├── common/              # 表格、搜索栏、分页、状态标签
│   │   │   ├── document/            # 文档上传、版本表、PDF 预览
│   │   │   └── permission/          # <PermissionGate> 权限控制组件
│   │   ├── views/                   # 页面（按模块）
│   │   │   ├── auth/
│   │   │   ├── admin/               # 用户、部门、审计、健康告警
│   │   │   ├── main-project/
│   │   │   ├── sub-project/
│   │   │   ├── task/
│   │   │   ├── payment/
│   │   │   ├── notification/
│   │   │   └── handover/
│   │   ├── stores/                  # Pinia: useAuthStore, usePermissionStore, ...
│   │   ├── router/
│   │   │   ├── index.ts
│   │   │   └── guards.ts            # 登录态 + 权限守卫
│   │   ├── types/                   # 与后端 schema 对齐的 TS 类型
│   │   ├── composables/             # useFetch, useTable, usePermission
│   │   ├── locale/                  # 中文文案（i18n 接入留口子）
│   │   └── utils/
│   ├── tests/
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── nginx/
│   └── nginx.conf
├── docs/
│   ├── REQUIREMENTS.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── AGENT_KICKOFF_PROMPT.md
│   ├── ROADMAP.md
│   └── api/
└── README.md
```

**架构纪律**：
- API 层只做参数验证、调用 service、序列化响应
- 业务规则只在 service 层
- ORM model 不暴露给 API（永远经过 Pydantic schema）
- 跨多表事务必须在 service 层用显式 `db.begin()` 包裹
- 前端 view 层不直接 import API 模块；用 Pinia store 或 composable 包装

---

## 3. 工程规范（强约束）

### 3.1 Python
- MUST 全量类型注解；mypy strict 通过
- MUST 用 `async def` for I/O 路径
- MUST NOT 用 `from xxx import *`
- MUST 用 SQLAlchemy 2.0 typed style：`Mapped[str]`, `mapped_column(...)`
- 业务异常 MUST 抛 `core/exceptions.py` 中定义的类，由全局 handler 转换响应
- 日志 MUST 用 structlog，自动包含 `request_id`, `user_id`, `action`

### 3.2 TypeScript
- MUST `tsconfig.strict = true`
- MUST 与后端 Pydantic schema 对齐的 TS 类型，放在 `types/` 下
- MUST NOT 在组件内直接 `axios.get(...)`，统一走 `api/` 模块
- MUST 用 Pinia 管理跨页面状态

### 3.3 命名
- 表名：snake_case 复数（`main_projects`）
- DB 字段：snake_case
- API 路径：kebab-case 复数（`/main-projects`）
- Pydantic schema：`{Entity}Create` / `{Entity}Update` / `{Entity}Out`
- Service 方法：`{verb}_{noun}`，事务方法在 docstring 中显式标注
- 前端组件：PascalCase（`MainProjectList.vue`）
- 前端 composable：camelCase 以 `use` 开头（`useMainProjects`）

### 3.4 数据库
- 主键 MUST 用 UUID v4（`uuid_generate_v4()`）
- 时间戳 MUST 用 `TIMESTAMPTZ`，存 UTC，前端转时区
- 金额 MUST 用 `DECIMAL(15, 2)`，禁用 float
- 软删除字段统一为 `is_deleted: bool` + `deleted_at: timestamptz | None`
- 所有表 MUST 有 `created_at`, `updated_at`，`updated_at` 用 trigger 维护
- 外键 MUST 显式指定 `ondelete` 策略（默认 `RESTRICT`，仅审计/历史关联用 `SET NULL`）

### 3.5 Git
- 分支：`main`（生产）、`develop`（集成）、`feat/{task-id}-{slug}`、`fix/{task-id}-{slug}`
- Commit message 格式：`{type}(T-{task-id}): {summary}`
- PR MUST 关联任务 ID + 通过 CI（lint + test + 覆盖率）
- 严禁直接推 main / develop

---

## 4. 里程碑总览

| 里程碑 | 主题 | 主要任务范围 | 工期 |
| --- | --- | --- | --- |
| M1 | 基础设施与项目骨架 | T-1-INFRA-* | 1.5 周 |
| M2 | 认证、用户、部门、跨切设施（通知/审计基础） | T-1-AUTH-* + T-1-USER-* + T-1-DEPT-* + T-1-NOTIF-BE-01 + T-1-AUDIT-BE-01 | 2 周 |
| M3 | 项目主体 + 转交 | T-1-PROJECT-* + T-1-USER-BE-04（转交） | 2.5 周 |
| M4 | 环节、文档、任务 | T-1-PHASE-* + T-1-DOC-* + T-1-TASK-* | 3 周 |
| M5 | 付款、验收、撤销 | T-1-PAY-* + T-1-ACC-* + T-1-REVOKE-* | 2 周 |
| M6 | 通知场景接入 + 审计查询 + 定时任务 | T-1-NOTIF-03+ + T-1-AUDIT-02+ + T-1-CRON-* | 1.5 周 |
| M7 | 集成测试、性能、安全、部署 | T-1-TEST-* + T-1-DEPLOY-* | 2 周 |
| **合计** | | | **~14.5 周** |

> 与 V1.1（11.5 周）相比多出 3 周，主要来自：① 前端任务显式拆分；② 跨切关注点（中间件、健康检查、seed）显式建任务；③ 测试任务前置到各模块。

---

## 5. 任务详细分解

### M1 — 基础设施与项目骨架（1.5 周）

**T-1-INFRA-01 仓库初始化**
- Deliverable：完整目录结构（§2）+ pyproject.toml + package.json + Dockerfile + docker-compose.yml + README + .gitignore + .env.example
- depends_on：无
- DoD：
  - [ ] `docker compose up` 能启动 backend + frontend + postgres + redis 四个服务且健康检查通过
  - [ ] `pytest tests/` 跑通（即使无业务测试）
  - [ ] `npm run dev` 启动前端，根路由返回占位页
  - [ ] `.env.example` 列出所有必需环境变量（DB、Redis、JWT secret 等）
  - [ ] `README.md` 含本地启动 5 步指南

**T-1-INFRA-02 CI/CD 骨架**
- Deliverable：GitHub Actions（或等价）配置：lint、test、build、覆盖率上传
- depends_on：T-1-INFRA-01
- DoD：
  - [ ] PR 触发 backend ruff + mypy + pytest
  - [ ] PR 触发 frontend eslint + tsc + vitest
  - [ ] 覆盖率阈值：backend 70%（M7 提到 80%），frontend 50%
  - [ ] CI 失败 PR 不能合并（需 branch protection 配置说明）

**T-1-INFRA-03 数据库迁移基线**
- Deliverable：Alembic 初始化 + 一次空迁移；`uuid-ossp` 扩展启用
- depends_on：T-1-INFRA-01
- DoD：`alembic upgrade head` 在干净 DB 上成功；`alembic downgrade base` 也成功

**T-1-INFRA-BE-04 后端核心基础设施**
- Deliverable：
  - `core/config.py`（Pydantic Settings 读取 env）
  - `core/db.py`（async session + connection pool）
  - `core/exceptions.py`（业务异常基类层级 + 全局 handler）
  - `core/security.py`（JWT 工具、密码 hash、JTI 生成）
  - `core/responses.py`（统一 `{code, message, data}` 封装）
  - `core/middleware.py`（request_id 注入 + 链路日志）
  - structlog 配置（JSON 格式输出 stdout，含 request_id / user_id）
- depends_on：T-1-INFRA-01
- DoD：
  - [ ] 业务异常自动转标准响应格式
  - [ ] 所有日志含 request_id（被中间件注入）
  - [ ] 单元测试覆盖各异常类型 → HTTP 状态码映射
  - [ ] mypy strict 通过

**T-1-INFRA-BE-05 跨切中间件**
- Deliverable：
  - CORS 中间件（开发宽松，生产白名单）
  - 安全 headers（HSTS, X-Content-Type-Options, X-Frame-Options 等）
  - 限流中间件（基于 Redis，默认 100 请求/分钟/IP，可按路径覆盖）
  - 请求大小限制（默认 50MB，针对上传接口）
  - 全局 OpenAPI 定制（标题、版本、tag 顺序、安全 schema）
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] CORS 配置可通过 env 切换
  - [ ] 限流触发返回 `429 Too Many Requests`
  - [ ] OpenAPI 文档 `/docs` 可访问且分组清晰
  - [ ] `/health` 接口返回 DB + Redis 连接状态

**T-1-INFRA-BE-06 文件存储抽象层**
- Deliverable：
  - `storage/base.py`：`StorageBackend` 抽象类（save / read / delete / get_url）
  - `storage/local.py`：本地文件系统实现
  - `storage/s3.py`：S3 兼容占位实现（仅签名，主体留 TODO；不必跑通）
  - 在 `core/config.py` 中通过 `STORAGE_BACKEND=local|s3` 切换
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] Local 实现完整可用
  - [ ] 文件路径格式：`{root}/{sub_id}/{phase_id}/{uuid}.{ext}`
  - [ ] 单元测试覆盖：保存、读取、删除、路径穿越攻击防御（含 `..`）

**T-1-INFRA-FE-07 前端项目脚手架**
- Deliverable：
  - Vite + Vue 3 + TS strict 配置
  - Element Plus 全局引入 + 主题色调整
  - Pinia 初始化 + 持久化（pinia-plugin-persistedstate）
  - Vue Router 基础配置（无业务路由，仅 layout 框架）
  - Axios 实例 + 拦截器（request 加 token；response 统一处理 401 跳登录、429 提示限流、5xx 显示通用错误）
  - 全局错误处理 + Element Plus message 集成
  - eslint + prettier + stylelint 配置
- depends_on：T-1-INFRA-01
- DoD：
  - [ ] `npm run dev` 启动后看到带 layout 的占位首页
  - [ ] 所有 lint 通过
  - [ ] 类型严格模式无错误
  - [ ] Axios 拦截器单元测试

**T-1-INFRA-FE-08 通用 UI 组件库**
- Deliverable：
  - `<AppLayout>`：左侧菜单 + 顶部 header + 主内容区
  - `<DataTable>`：基于 Element Plus el-table 的封装，统一分页、排序、列配置
  - `<SearchBar>`：通用筛选条
  - `<StatusTag>`：状态标签（按状态枚举映射颜色）
  - `<PermissionGate>`：权限控制包裹组件，按当前用户角色 + 资源 ID 控制可见性
  - `<ConfirmDialog>`：二次确认弹窗（用于敏感操作）
- depends_on：T-1-INFRA-FE-07
- DoD：
  - [ ] 6 个组件全部有 Storybook 或最小 demo 页验证
  - [ ] 单元测试覆盖关键交互
  - [ ] 与 Element Plus 主题 token 对齐

**T-1-INFRA-09 Seed 数据脚本**
- Deliverable：
  - `seeds/default_admin.py`：创建默认 admin 账号（username/password 从 env 读取）
  - `seeds/default_departments.py`：创建综合部、财务部 + 业务部门示例
  - `seeds/phase_doc_templates.py`：写入 §3.2 文档模板配置
  - 统一入口：`python -m app.seeds.run --target {all|admin|deps|phases}`
- depends_on：T-1-INFRA-03 + T-1-INFRA-BE-04
- DoD：
  - [ ] 在干净 DB 上执行 seed 后，admin 可登录
  - [ ] phase_doc_templates 表有 §3.2 全部行
  - [ ] 重复执行幂等（已存在不报错）

---

### M2 — 认证、用户、部门、跨切设施（2 周）

**T-1-AUTH-BE-01 用户、部门、角色相关 ORM 模型**
- Deliverable：
  - `users` 表（含 username, password_hash, role, dept_id, status, password_changed_at, last_login_at）
  - `departments` 表
  - 关联迁移
- 字段对照 REQUIREMENTS §1.1, §5.1
- depends_on：T-1-INFRA-09
- DoD：
  - [ ] 模型 + Pydantic schema + Alembic 迁移
  - [ ] mypy + 单元测试通过
  - [ ] 角色用 PostgreSQL ENUM，支持的值锁定为 §1.1 的 5 个

**T-1-AUTH-BE-02 登录接口（FR-AUTH-01）**
- Deliverable：`POST /api/v1/auth/login`
- 实现 BR-AUTH-01（5 次失败锁定）、BR-AUTH-02（密码强度）、BR-AUTH-03（Bcrypt cost=12）
- depends_on：T-1-AUTH-BE-01
- DoD：
  - [ ] 单元测试覆盖：成功、密码错、锁定、解锁、密码强度校验
  - [ ] Redis 计数器 key：`auth:fail:{user_id}`，TTL 30min
  - [ ] 返回 access + refresh token

**T-1-AUTH-BE-03 Token 续签 + 登出（FR-AUTH-02 + BR-AUTH-04）**
- Deliverable：`POST /auth/refresh`、`POST /auth/logout`、`GET /auth/me`
- depends_on：T-1-AUTH-BE-02
- DoD：
  - [ ] refresh 验证通过返回新 access
  - [ ] logout 把 access jti 加入 Redis 黑名单（TTL = 剩余有效期）
  - [ ] 黑名单中的 token 调用任何 API 返回 401
  - [ ] 修改密码 / 停用账号触发该用户所有未过期 token 加黑名单
  - [ ] `/auth/me` 返回当前用户基础信息（id, username, role, dept_id）

**T-1-AUTH-BE-04 当前用户依赖 + RBAC 装饰器**
- Deliverable：
  - `core/deps.py::get_current_user` (FastAPI Depends)
  - `core/permissions.py::require_role(*roles)`
  - `core/permissions.py::require_permission(perm: str, resource_id_param: str | None)`
  - 内置权限矩阵：从 REQUIREMENTS §4 配置化为常量
- depends_on：T-1-AUTH-BE-03
- DoD：
  - [ ] `Depends(require_role('admin'))` 一行即用
  - [ ] `require_permission('project.view_own', resource_id_param='id')` 自动校验所有权
  - [ ] 单元测试覆盖：5 角色 × 关键权限矩阵的拒绝路径

**T-1-AUTH-FE-05 前端登录 / 登出 / 鉴权流**
- Deliverable：
  - `views/auth/Login.vue`：登录页（用户名/密码 + 记住我）
  - `stores/useAuthStore.ts`：登录、登出、token 刷新、当前用户管理
  - Axios 拦截器：401 自动 refresh，refresh 失败跳登录
  - 路由守卫：未登录跳登录，已登录自动跳首页
  - 顶部 header：显示当前用户 + 登出按钮
- depends_on：T-1-INFRA-FE-08 + T-1-AUTH-BE-03
- DoD：
  - [ ] 完整登录登出流程跑通
  - [ ] token 过期自动续签
  - [ ] 锁定账号显示明确错误
  - [ ] 单元 + 集成测试

**T-1-AUTH-FE-06 权限控制组件 + 路由权限元数据**
- Deliverable：
  - `composables/usePermission.ts`：当前用户对某权限的判定
  - `<PermissionGate permission="..." resource-id="...">` 组件
  - 路由 meta 字段：`{ requireRole: ['admin'] | ['dept_manager', 'admin'] }`
  - Sidebar 自动隐藏无权访问的菜单项
- depends_on：T-1-AUTH-FE-05
- DoD：
  - [ ] 不同角色登录看到的菜单不同
  - [ ] PermissionGate 单元测试覆盖

**T-1-USER-BE-01 用户管理接口**
- Deliverable：
  - `GET /api/v1/users`（admin only，支持分页 + 角色筛选）
  - `POST /api/v1/users`（admin only，创建用户）
  - `GET /api/v1/users/{id}`（admin 或自己）
  - `PUT /api/v1/users/{id}`（admin 或自己改基础信息；admin 改角色）
  - `DELETE /api/v1/users/{id}` 软停用（admin only，含 BR-USER-01 in-flight 检查）
  - `POST /api/v1/users/{id}/reset-password`（admin only，强制下次登录改密）
  - `POST /api/v1/users/me/change-password`（自己改密码）
- depends_on：T-1-AUTH-BE-04
- DoD：
  - [ ] 单元 + 集成测试覆盖权限拒绝路径
  - [ ] 停用 proj_leader 时若有 in-flight 子项目则拒绝（错误码 3010，提示先转交）
  - [ ] 改密码 / 停用立即触发 token 黑名单
  - [ ] 创建用户时密码强度校验（BR-AUTH-02）

**T-1-DEPT-BE-01 部门管理接口**
- Deliverable：
  - `GET /api/v1/departments`（已登录可查）
  - `POST /api/v1/departments`（admin only）
  - `PUT /api/v1/departments/{id}`（admin only）
  - `DELETE /api/v1/departments/{id}`（admin only，仅当无活跃用户时允许）
- depends_on：T-1-AUTH-BE-04
- DoD：单元 + 集成测试通过

**T-1-USER-BE-03 系统健康警告（BR-ROLE-01）**
- Deliverable：
  - `GET /api/v1/system/health-warnings`（admin only）
  - 启动时检查 dept_manager 数量 < 2 时记入 warning 列表
  - 留口子未来扩展（如磁盘 80%、Celery 队列堆积等）
- depends_on：T-1-USER-BE-01
- DoD：
  - [ ] dept_manager < 2 时返回告警
  - [ ] 修复（增加 dept_manager）后告警消失
  - [ ] 启动时往日志输出一次健康检查结果

**T-1-USER-FE-01 用户管理页**
- Deliverable：
  - `views/admin/UserList.vue`：用户列表 + 搜索 + 创建按钮 + 行操作
  - `views/admin/UserEdit.vue`：编辑/创建对话框
  - 接入 BR-USER-01 拒绝场景：停用按钮 hover 时显示是否有 in-flight 项目
- depends_on：T-1-AUTH-FE-06 + T-1-USER-BE-01
- DoD：admin 角色完整交互测试通过

**T-1-DEPT-FE-01 部门管理页**
- Deliverable：`views/admin/DepartmentList.vue` + 编辑对话框
- depends_on：T-1-AUTH-FE-06 + T-1-DEPT-BE-01
- DoD：交互测试通过

**T-1-USER-FE-04 个人信息 + 修改密码**
- Deliverable：
  - `views/Profile.vue`：查看 + 修改自己的基础信息
  - `views/ChangePassword.vue`：旧密码验证 + 新密码强度校验
  - 重置密码后强制改密的引导页
- depends_on：T-1-AUTH-FE-05
- DoD：交互测试通过

**T-1-NOTIF-BE-01 通知模型 + send service（基础设施先行）**
- Deliverable：
  - `notifications` 表（含 BR-NOTIF-01 dedup_key 含 source_id）
  - `notification_service.send(scenario, receivers, source_id, payload)`
  - 暂不接入业务场景（M6 时再批量接入）
- 说明：此任务前移到 M2，因为后续业务模块都需要调用通知 service。本期只实现基础发送 + dedup，业务场景接入留到 M6。
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] 单元测试覆盖：发送、去重、批量发送
  - [ ] dedup_key 格式正确 = `{scenario}:{receiver_id}:{source_id}:{date}`

**T-1-AUDIT-BE-01 审计日志中间件 + 装饰器（基础设施先行）**
- Deliverable：
  - `audit_logs` 表（按月分区）
  - `@audited('action_code')` 装饰器，自动 diff before/after 并写入
  - 异步写入（FastAPI BackgroundTasks 或 Celery，不阻塞主事务）
  - 配套 `core/middleware.py` 注入审计上下文（actor_id, ip, user_agent）
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] 装饰器单元测试覆盖
  - [ ] 性能测试：装饰器开销 ≤50ms（审计写入不阻塞主响应）
  - [ ] 月分区脚本（创建未来 12 个月分区）写入 alembic 或定时任务

---

### M3 — 项目主体 + 转交（2.5 周）

**T-1-PROJECT-BE-01 主项目模型 + 基础 CRUD**
- Deliverable：
  - `main_projects` 表（FR-MAIN-01 字段）
  - `GET /api/v1/main-projects`（按角色过滤可见范围）
  - `POST /api/v1/main-projects`（dept_manager only）
  - `GET /api/v1/main-projects/{id}`
  - `PUT /api/v1/main-projects/{id}`（仅创建人，仅 status ∈ {pending_review, rejected}）
- 实现 BR-REVIEW-02（审核期间不可改）
- depends_on：T-1-DEPT-BE-01
- DoD：
  - [ ] project_no 自动生成 `Z-{YYYY}-{seq}`，事务安全的序列
  - [ ] 状态机正确（不可强改 status）
  - [ ] 单元 + 集成测试

**T-1-PROJECT-BE-02 主项目审核流程（FR-MAIN-02）**
- Deliverable：
  - `POST /main-projects/{id}/submit`
  - `POST /main-projects/{id}/review`（带 action: approve/reject + comment）
  - `project_reviews` 表（含 modified_fields JSONB）
  - 审核人编辑字段时记录到 modified_fields
  - 触发通知：提交后通知所有其他 dept_manager；审核完通知创建人
- 实现 BR-REVIEW-01（审核人非创建人；admin 兜底，标记 admin_override）、BR-REVIEW-03
- depends_on：T-1-PROJECT-BE-01 + T-1-NOTIF-BE-01 + T-1-AUDIT-BE-01
- DoD：
  - [ ] 审核通过/退回路径全覆盖
  - [ ] 自审被拒绝（403 + 错误码 1010）
  - [ ] admin 兜底审核成功 + audit_log 记录 `admin_override=true`
  - [ ] modified_fields 正确记录

**T-1-PROJECT-BE-03 主项目结项（FR-MAIN-03）**
- Deliverable：`POST /main-projects/{id}/close`
- 触发条件：所有子项目 status ∈ {closed, terminated}
- 实现：结项后所有字段不可改、不可创建子项目
- depends_on：T-1-PROJECT-BE-02 + T-1-PROJECT-BE-05
- DoD：单元 + 集成测试覆盖

**T-1-PROJECT-BE-04 子项目模型 + 基础 CRUD**
- Deliverable：同 T-1-PROJECT-BE-01 模式
- 字段对照 FR-SUB-01（含 actual_end_date 自动维护）
- depends_on：T-1-PROJECT-BE-01
- DoD：测试覆盖

**T-1-PROJECT-BE-05 子项目审核流程（FR-SUB-02）**
- Deliverable：
  - `POST /sub-projects/{id}/submit`
  - `POST /sub-projects/{id}/review`
  - 审核通过同事务创建 6 条 phase 记录（phase 1 = in_progress，其余 waiting）
  - 实现 BR-SUB-02 超预算警告：返回 `code=3001` + `over_budget_amount`，前端二次确认后再提交（带 confirm 参数）
- depends_on：T-1-PROJECT-BE-04 + T-1-PHASE-BE-01
- DoD：
  - [ ] 审核通过后 phase 表正确生成
  - [ ] 超预算返回 3001 → 前端确认后写审计日志 over_budget=true + 通知

**T-1-PROJECT-BE-06 子项目状态变更（结项 / 中止）**
- Deliverable：
  - `POST /sub-projects/{id}/close`（条件：6 个环节全 completed；触发 actual_end_date 写入）
  - `POST /sub-projects/{id}/terminate`（dept_manager 或 admin，附 reason）
- depends_on：T-1-PROJECT-BE-05
- DoD：状态机校验 + 测试

**T-1-PROJECT-BE-07 子项目成员管理**
- Deliverable：
  - `sub_project_members` 表（user_id + sub_project_id + role_in_project + joined_at + UNIQUE）
  - `GET /sub-projects/{id}/members`
  - `POST /sub-projects/{id}/members`（proj_leader of this project，加成员）
  - `DELETE /sub-projects/{id}/members/{user_id}`（同上；不能移除 proj_leader 自己）
- depends_on：T-1-PROJECT-BE-04
- DoD：
  - [ ] 防重 unique 约束生效
  - [ ] 不能移除子项目负责人
  - [ ] 单元 + 集成测试

**T-1-USER-BE-04 项目负责人转交（FR-USER-02）**
- Deliverable：
  - `sub_project_handovers` 表（FR-USER-02 字段）
  - `GET /api/v1/users/{id}/active-sub-projects`（admin only，列 in-flight 子项目）
  - `POST /api/v1/sub-projects/{id}/handover`（admin only，单项目转交）
  - `POST /api/v1/users/{id}/batch-handover`（admin only，批量转交）
- 实现 BR-USER-02 全部子规则（member 不转交、保留历史、closed 不转交、通知 from/to/成员、审计）
- depends_on：T-1-USER-BE-01 + T-1-PROJECT-BE-07
- DoD：
  - [ ] 单 + 批量转交全部测试通过
  - [ ] BR-USER-02 子规则 ① ② ③ ④ ⑤ 全覆盖
  - [ ] 集成测试：停用未转交的 proj_leader 被拒（关联 BR-USER-01）

**T-1-PROJECT-FE-01 主项目列表 + 详情**
- Deliverable：
  - `views/main-project/MainProjectList.vue`：列表 + 状态筛选 + 部门筛选
  - `views/main-project/MainProjectDetail.vue`：详情页 + 状态时间线 + 子项目列表
- depends_on：T-1-INFRA-FE-08 + T-1-PROJECT-BE-03
- DoD：列表交互、状态显示、跳转都正确

**T-1-PROJECT-FE-02 主项目创建 + 编辑 + 提交审核**
- Deliverable：
  - `views/main-project/MainProjectEdit.vue`：表单（含校验）
  - 提交审核确认弹窗
  - 已退回项目的修改 + 重新提交流程
- depends_on：T-1-PROJECT-FE-01
- DoD：表单校验 + 提交流程测试通过

**T-1-PROJECT-FE-03 主项目审核界面**
- Deliverable：
  - `views/main-project/MainProjectReview.vue`：审核人查看 + 编辑 + 通过/退回
  - 修改字段会自动 diff 显示
- depends_on：T-1-PROJECT-FE-02
- DoD：
  - [ ] 审核人非创建人的检查正确
  - [ ] modified_fields 正确显示
  - [ ] admin 兜底审核流程顺畅

**T-1-PROJECT-FE-04 子项目相关页面**
- Deliverable：
  - `views/sub-project/SubProjectList.vue` + `SubProjectDetail.vue` + `SubProjectEdit.vue` + `SubProjectReview.vue`
  - 超预算二次确认弹窗（基于 BR-SUB-02 返回的 3001）
- depends_on：T-1-PROJECT-FE-01 + T-1-PROJECT-BE-06
- DoD：与主项目同等覆盖

**T-1-PROJECT-FE-05 子项目成员管理界面**
- Deliverable：成员列表 + 添加 / 移除（含权限控制）
- depends_on：T-1-PROJECT-FE-04 + T-1-PROJECT-BE-07
- DoD：交互测试通过

**T-1-PROJECT-FE-06 转交管理界面（admin only）**
- Deliverable：
  - `views/admin/UserHandover.vue`：选择用户 → 看 in-flight 项目 → 批量选择新负责人 → 提交
  - `views/admin/HandoverHistory.vue`：转交历史查询
- depends_on：T-1-PROJECT-FE-05 + T-1-USER-BE-04
- DoD：批量转交流程顺畅，确认弹窗清晰

---

### M4 — 环节、文档、任务（3 周）

**T-1-PHASE-BE-01 Phase 模型 + phase_doc_templates 表**
- Deliverable：
  - `phases` 表（含 phase_no, status, enter_at, finish_at, procurement_type 等）
  - `phase_doc_templates` 表（§3.2 配置）
  - `phase_history` 表（状态变更历史）
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] 模型 + 迁移
  - [ ] phase_doc_templates 由 T-1-INFRA-09 seed 写入

**T-1-PHASE-BE-02 环节查询接口**
- Deliverable：
  - `GET /api/v1/phases?sub_project_id=...`
  - `GET /api/v1/phases/{id}`（含必传文档清单 + 已上传文档清单 + 完成度）
- depends_on：T-1-PHASE-BE-01
- DoD：返回的"必传文档清单"按 procurement_type 动态计算

**T-1-PHASE-BE-03 环节推进接口（FR-PHASE-01）**
- Deliverable：
  - `POST /phases/{id}/promote`
  - 完整实现 FR-PHASE-01 伪代码逻辑
- 实现 BR-PHASE-01（前序依赖）、BR-PHASE-02（环节 5 / 6 特殊规则，**含后评价依赖验收完成**）、BR-PHASE-03（子项目 completed 条件）
- depends_on：T-1-PHASE-BE-02 + T-1-DOC-BE-01（文档已上传校验依赖）
- DoD：
  - [ ] 缺文档被拒（含 inquiry/bidding/single_source 的条件文档）
  - [ ] 后评价在验收前推进被拒
  - [ ] 推进后自动激活下一环节
  - [ ] 通知子项目所有成员
  - [ ] 写 phase_history

**T-1-DOC-BE-01 文档模型 + 上传接口（FR-DOC-01）**
- Deliverable：
  - `documents` 表（BR-DOC-01 唯一约束）
  - `POST /documents`（multipart 上传）
  - `GET /documents?sub_project_id=&phase_id=&doc_type=&include_history=`
- 实现 BR-DOC-01（unique 约束）、BR-DOC-02（版本递增 + is_latest 翻转）
- depends_on：T-1-PHASE-BE-01 + T-1-INFRA-BE-06
- DoD：
  - [ ] 版本递增 + is_latest 翻转事务保障
  - [ ] 文件存储路径正确
  - [ ] 上传响应返回 doc_id + version
  - [ ] 50MB 限制（nginx + FastAPI 双层）
  - [ ] 文件名过滤 `..`

**T-1-DOC-BE-02 文件校验器（BR-DOC-04）**
- Deliverable：
  - `validators/file_validator.py`
  - 实现五重校验链：扩展名白名单 → 扩展名黑名单 → MIME 白名单 → 文件头 magic number → zip 内文件名递归扫描
  - 黑名单清单按 BR-DOC-04 列出
  - 校验失败抛业务异常 + 写审计日志（action=upload_rejected）
- depends_on：T-1-INFRA-BE-04
- DoD：
  - [ ] 测试用例：合法文件通过、扩展名错误被拒、MIME 不匹配被拒、伪装 PDF 的 EXE 被拒、含 .exe 的 zip 被拒
  - [ ] 黑名单覆盖 BR-DOC-04 全部扩展
  - [ ] 审计日志含 rejection_reason

**T-1-DOC-BE-03 文档下载 + 软删除 service（BR-DOC-03）**
- Deliverable：
  - `GET /documents/{id}/download`（流式响应，权限校验）
  - 内部 service：`soft_delete_phase_documents(phase_id)`（撤销审批用）
- depends_on：T-1-DOC-BE-01
- DoD：
  - [ ] 权限校验：仅项目成员可下载
  - [ ] 物理路径不暴露
  - [ ] 软删除后文档列表不再显示（除非 include_history=true）

**T-1-DOC-BE-04 PDF 在线预览（BR-DOC-05，OQ-05）**
- Deliverable：
  - `GET /documents/{id}/preview`
  - 仅 doc_type=pdf 接受；其他返回 400 + 错误码 3020
  - 权限同 download
  - 响应 header：`Content-Type: application/pdf` + `Content-Disposition: inline`
  - 写审计日志（action=document.preview）
- depends_on：T-1-DOC-BE-03
- DoD：
  - [ ] 大 PDF（50MB）流式响应不卡
  - [ ] 非 PDF 拒绝
  - [ ] 审计日志记录正确

**T-1-TASK-BE-01 任务模型**
- Deliverable：
  - `tasks` 表 + `task_executors` 表
  - 字段对照 FR-TASK-01 / 02
- depends_on：T-1-PHASE-BE-01
- DoD：模型 + 迁移 + 单测

**T-1-TASK-BE-02 任务 CRUD + 指派 + 完成**
- Deliverable：
  - `GET /api/v1/tasks?sub_project_id=&assignee=me&status=`
  - `POST /api/v1/tasks`（proj_leader）
  - `GET /api/v1/tasks/{id}`
  - `PUT /api/v1/tasks/{id}`（proj_leader 改基础信息 + 调整指派人）
  - `POST /api/v1/tasks/{id}/complete`（被指派人，标记自己完成）
- 实现 BR-TASK-01（应用层状态聚合）
- depends_on：T-1-TASK-BE-01 + T-1-PROJECT-BE-07
- DoD：
  - [ ] 多人指派各自独立 status
  - [ ] 任意 executor 完成触发同事务的 task.status 聚合
  - [ ] 指派后通知 executor

**T-1-DOC-FE-01 文档上传组件 + 列表 + 版本表**
- Deliverable：
  - `<DocumentUploader>`：拖拽上传 + 进度 + 失败重试 + 校验失败明确提示
  - `<DocumentList>`：按 doc_type 分组，显示最新版 + 历史版折叠
  - `<DocumentVersionDiff>`：版本元信息对比
- depends_on：T-1-INFRA-FE-08 + T-1-DOC-BE-02
- DoD：
  - [ ] 拒绝上传时显示具体原因（黑名单/类型不符）
  - [ ] 版本切换正确
  - [ ] 50MB 上限前端预校验

**T-1-DOC-FE-02 PDF 预览组件**
- Deliverable：
  - `<PdfPreview>`：基于 pdfjs-dist 的弹窗式预览
  - 集成到 `<DocumentList>`：PDF 文档显示"预览"按钮
- depends_on：T-1-DOC-FE-01 + T-1-DOC-BE-04
- DoD：
  - [ ] PDF 翻页、缩放、下载（在预览面板内）
  - [ ] 非 PDF 不显示预览按钮

**T-1-TASK-FE-01 任务列表 + 详情 + 指派**
- Deliverable：
  - `views/task/TaskList.vue`：任务列表（按子项目、按状态、按 assignee=me）
  - `views/task/TaskDetail.vue`：任务详情 + 完成按钮（仅本人可见）
  - 任务创建/指派对话框
- depends_on：T-1-INFRA-FE-08 + T-1-TASK-BE-02
- DoD：交互测试通过

**T-1-TASK-FE-02 "我的任务"工作台**
- Deliverable：登录后默认页（如有未完成任务），显示按 due 日期排序的待办
- depends_on：T-1-TASK-FE-01
- DoD：逾期任务高亮；当日到期标黄

**T-1-PHASE-FE-01 环节进度面板 + 推进按钮**
- Deliverable：
  - `<PhaseProgress>`：6 环节进度可视化（已完成/进行中/待开始/已撤销）
  - 当前进行中环节显示推进按钮（含必传文档校验提示）
- depends_on：T-1-PHASE-BE-03 + T-1-DOC-FE-01
- DoD：
  - [ ] 推进失败的错误信息明确（缺哪个文档）
  - [ ] 推进成功有 toast 提示

**T-1-PHASE-FE-02 环节文档管理面板**
- Deliverable：环节详情页，含必传文档清单 + 已上传文档（带版本）+ 上传入口
- depends_on：T-1-PHASE-FE-01 + T-1-DOC-FE-01
- DoD：必传 vs 选传清晰区分

---

### M5 — 付款、验收、撤销（2 周）

**T-1-PAY-BE-01 付款模型**
- Deliverable：
  - `payments` 表（含 payment_type, reverses_payment_id 自引用 FK）
  - `payment_vouchers` 表
- depends_on：T-1-PROJECT-BE-04
- DoD：模型 + 迁移

**T-1-PAY-BE-02 新增付款（BR-PAY-02 + 03 + 04）**
- Deliverable：
  - `POST /api/v1/sub-projects/{id}/payments`（multipart：金额 + 凭证）
  - 实现 BR-PAY-02 超预算二次确认（无 confirm 参数返回 3001 + 待确认信息；带 confirm 直接写）
  - 实现 BR-PAY-03 凭证必传
  - 实现 BR-PAY-04 spent_amount 聚合（行锁 + 重试）
- depends_on：T-1-PAY-BE-01 + T-1-DOC-BE-02 + T-1-NOTIF-BE-01
- DoD：
  - [ ] 单次付款 + 凭证同事务
  - [ ] **并发测试**：10 并发付款不出现 spent_amount 漂移
  - [ ] 超预算确认流程通过
  - [ ] 超预算时通知 dept_manager + admin + 审计 over_budget=true

**T-1-PAY-BE-03 红冲付款（BR-PAY-01）**
- Deliverable：`POST /api/v1/sub-projects/{id}/payments` 中 payment_type=reversal 的分支
- 校验：reverses_payment_id 必填且必须存在；amount 自动取 -original.amount；remark 必填
- depends_on：T-1-PAY-BE-02
- DoD：
  - [ ] reversal 引用不存在付款被拒
  - [ ] 红冲后 spent_amount 准确减少
  - [ ] 红冲不可被红冲（reversal 类型不能再次 reverse）

**T-1-PAY-BE-04 付款查询接口**
- Deliverable：
  - `GET /api/v1/sub-projects/{id}/payments`（分页 + 类型筛选）
  - `GET /api/v1/sub-projects/{id}/payments/{pid}`
- depends_on：T-1-PAY-BE-02
- DoD：测试通过

**T-1-PAY-FE-01 付款记录列表 + 创建**
- Deliverable：
  - `views/payment/PaymentList.vue`：列表 + 红冲标识
  - 新增付款对话框：金额、日期、凭证上传
- depends_on：T-1-INFRA-FE-08 + T-1-PAY-BE-04
- DoD：交互测试通过

**T-1-PAY-FE-02 超预算二次确认 + 红冲 UI**
- Deliverable：
  - 超预算时弹出二次确认弹窗，必填超预算原因
  - 付款行的红冲操作入口（finance_manager only）
- depends_on：T-1-PAY-FE-01
- DoD：流程顺畅、不可误操作

**T-1-ACC-BE-01 分步验收（FR-ACC-01）**
- Deliverable：
  - `acceptance_steps` 表
  - `GET /phases/{id}/acceptance-steps`
  - `POST /phases/{id}/acceptance-steps`
  - `PUT /phases/{id}/acceptance-steps/{sid}`（更新状态）
- 实现 BR-ACC-01 / 02 / 03（含未创建步骤的 fallback）
- depends_on：T-1-PHASE-BE-03 + T-1-DOC-BE-01
- DoD：
  - [ ] 所有 step completed 后才允许推进 phase 4
  - [ ] 每步关联至少 1 份 acceptance_report 文档
  - [ ] 未创建步骤的 phase 走原有流程

**T-1-ACC-FE-01 分步验收 UI**
- Deliverable：在环节 4 详情页内嵌入步骤管理（创建、指派、完成、关联文档）
- depends_on：T-1-PHASE-FE-02 + T-1-ACC-BE-01
- DoD：交互测试通过

**T-1-REVOKE-BE-01 撤销审批（FR-REVOKE-01）**
- Deliverable：
  - `revoke_requests` 表
  - `GET /api/v1/revoke-requests`
  - `POST /api/v1/revoke-requests`（proj_leader）
  - `POST /api/v1/revoke-requests/{id}/review`（dept_manager / admin）
- 实现 BR-REVOKE-01 完整规则：
  - phase 状态恢复 in_progress
  - 文档软删
  - 后续 in_progress 环节回滚为 waiting
  - 任务保留 completed 状态 + 审计日志说明
  - **通知范围**（OQ-08 决策）：uploader + proj_leader（不通知其他成员）
- depends_on：T-1-PHASE-BE-03 + T-1-DOC-BE-03
- DoD：
  - [ ] 撤销审核通过后状态正确恢复
  - [ ] 仅可撤销 completed 的环节
  - [ ] 通知范围正确（写测试覆盖：proj_member 不应收到通知）

**T-1-REVOKE-FE-01 撤销申请 + 审核 UI**
- Deliverable：
  - `views/revoke/RevokeApply.vue`：申请表单
  - `views/revoke/RevokeReview.vue`：审核人界面
  - 我的撤销申请列表
- depends_on：T-1-INFRA-FE-08 + T-1-REVOKE-BE-01
- DoD：交互测试通过

---

### M6 — 通知场景接入 + 审计查询 + 定时任务（1.5 周）

**T-1-NOTIF-BE-03 各业务场景接入**
- Deliverable：把 REQUIREMENTS §5.10 表中**全部**通知场景接入对应业务 service
- 列表（含已确认 OQ-08 的修订）：
  1. `project_pending_review` — 主/子项目提交后
  2. `project_review_result` — 审核完成后
  3. `task_assigned` — 任务指派后
  4. `task_due_today` / `task_overdue` / `task_overdue_escalation` — 由定时任务触发
  5. `phase_promoted` — 推进环节后
  6. `payment_created` — 每次付款
  7. `over_budget_warning` — 触发 BR-PAY-02 时
  8. `revoke_request_pending` — 撤销申请提交
  9. `revoke_result` — 仅 uploader + proj_leader（OQ-08）
  10. `handover_completed` — 转交完成（FR-USER-02）
- depends_on：所有业务模块（M2 ~ M5）+ T-1-NOTIF-BE-01
- DoD：
  - [ ] 每个场景至少 1 个集成测试触发
  - [ ] dedup_key 防重测试
  - [ ] OQ-08 通知范围测试（proj_member 不应收到撤销通知）

**T-1-NOTIF-BE-02 通知查询 + 已读接口**
- Deliverable：
  - `GET /api/v1/notifications`（分页 + 未读筛选）
  - `POST /api/v1/notifications/{id}/read`
  - `POST /api/v1/notifications/read-all`
  - `GET /api/v1/notifications/unread-count`
- depends_on：T-1-NOTIF-BE-01
- DoD：测试通过

**T-1-NOTIF-FE-01 通知中心 UI**
- Deliverable：
  - 顶部 header 红点 + 未读数（轮询 30s 或 SSE 长连接，选简单方案）
  - 通知中心面板（点击 header 红点弹出）
  - 通知详情跳转到对应业务页
  - 全部已读 / 单条已读
- depends_on：T-1-AUTH-FE-05 + T-1-NOTIF-BE-02
- DoD：交互流畅；未读数实时更新

**T-1-AUDIT-BE-02 审计日志查询接口**
- Deliverable：
  - `GET /api/v1/audit-logs`（admin only，支持按 actor / action / target_type / target_id / 时间范围筛选）
  - 分页 + 排序（按 created_at desc）
- depends_on：T-1-AUDIT-BE-01
- DoD：
  - [ ] 跨月分区查询正确
  - [ ] 大数据量分页性能 ≤ 1s

**T-1-AUDIT-FE-01 审计日志查询 UI（admin only）**
- Deliverable：`views/admin/AuditLogQuery.vue` + 详情查看（before/after diff）
- depends_on：T-1-AUTH-FE-06 + T-1-AUDIT-BE-02
- DoD：交互测试通过

**T-1-CRON-BE-01 Celery 应用搭建**
- Deliverable：
  - `tasks/celery_app.py`
  - docker-compose 加 celery worker + celery beat 服务
  - Celery 配置：result backend = Redis；task serializer = JSON；timezone = Asia/Shanghai
- depends_on：T-1-INFRA-BE-04
- DoD：worker + beat 启动成功；测试任务能被 beat 触发

**T-1-CRON-BE-02 任务到期 / 逾期定时任务（BR-TASK-02）**
- Deliverable：
  - 每日 09:00（Asia/Shanghai）执行
  - 扫描 task_executors where plan_end_date < today AND status ∈ {not_started, in_progress} → 改为 overdue
  - 触发任务聚合（BR-TASK-01）
  - 发送通知：当日到期 → task_due_today；已逾期 → task_overdue；逾期 ≥7 天 → task_overdue_escalation 给 admin
  - dedup_key 防重
- depends_on：T-1-CRON-BE-01 + T-1-TASK-BE-02 + T-1-NOTIF-BE-03
- DoD：
  - [ ] 时区固定 Asia/Shanghai
  - [ ] 7 天逾期升级 admin 测试通过
  - [ ] dedup 防同日重复（含同日多任务的覆盖测试）

**T-1-CRON-BE-03 文件清理任务**
- Deliverable：
  - 每周一 03:00 清理临时上传残留（≥7 天未关联到 document 的 storage 文件）
  - 清理软删除 ≥ 90 天的 document 物理文件（仅删除文件，DB 记录保留供审计）
- depends_on：T-1-CRON-BE-01 + T-1-INFRA-BE-06
- DoD：清理日志 + dry-run 模式

**T-1-AUDIT-BE-03 月分区自动维护**
- Deliverable：每月 1 日 00:30 创建未来 3 个月的 audit_logs 分区
- depends_on：T-1-CRON-BE-01 + T-1-AUDIT-BE-01
- DoD：分区创建幂等

---

### M7 — 集成测试、性能、安全、部署（2 周）

**T-1-TEST-01 单元测试基础设施**
- Deliverable：
  - `tests/conftest.py`：testcontainers PG + Redis + 全局 fixtures
  - `tests/factories/`：所有核心实体 factory-boy 类
  - 覆盖率配置：CI 阈值 80%（backend）、50%（frontend）
- depends_on：T-1-INFRA-02
- DoD：所有现有测试在 CI 跑通；覆盖率门槛生效

**T-1-TEST-02 端到端集成测试套件**
- Deliverable：pytest e2e suite，覆盖以下完整流程：
  1. 主项目立项 → 审核通过 → 创建子项目 → 审核通过 → 推进 6 环节 → 多次付款 → 结项
  2. 撤销流程：环节 3 完成后撤销 → 文档软删 → 通知验证
  3. 红冲流程：错误付款 → 红冲 → spent_amount 准确
  4. 转交流程：admin 批量转交 → 通知 + 审计
  5. dept_manager 死锁场景：1 个 dept_manager 创建主项目 → admin 兜底审核 → 标记 admin_override
- depends_on：所有业务模块完成
- DoD：5 个流程全跑通，每次跑都用全新 DB

**T-1-TEST-03 关键规则覆盖测试**
- Deliverable：所有 BR-* 规则的失败路径测试用例清单
- 必含场景（参考 §8 必测场景）：
  1. dept_manager 自审被拒
  2. dept_manager < 2 时 health endpoint 告警
  3. 后评价在验收前推进被拒
  4. 多次付款 spent_amount 准确（含红冲）
  5. 超预算付款触发二次确认 + 通知
  6. 撤销审批通过后状态、文档软删、后续环节回滚正确
  7. 任务多人指派、个人完成、整体完成聚合
  8. 任务到期/逾期/7 天升级
  9. 通知 dedup（含同日多任务的修复验证）
  10. 文件上传：MIME / 50MB / 路径穿越拒绝
  11. 可执行文件上传被拒（.exe / .sh / 含 .exe 的 zip）
  12. PDF 在线预览（PDF 可、非 PDF 拒、审计正确）
  13. proj_leader 转交（单 / 批量 / in-flight 列表 / closed 不在列表 / 停用未转交被拒）
  14. 撤销通知范围（仅 uploader + proj_leader）
- depends_on：T-1-TEST-01
- DoD：每条规则至少 1 个失败路径测试

**T-1-TEST-04 性能基线测试**
- Deliverable：
  - locust 脚本测 50 并发，覆盖：登录、查项目列表、上传文档、推进环节、新增付款
  - 验证 P99 ≤ 800ms（NFR）
  - 报告写入 `docs/perf-baseline.md`
- depends_on：T-1-TEST-02
- DoD：报告生成；超 SLA 的接口列入 fix 清单

**T-1-TEST-05 基础安全测试**
- Deliverable：
  - 依赖漏洞扫描（pip-audit / npm audit）
  - 简单越权测试：proj_member 尝试访问其他子项目数据 → 被拒
  - 弱密码测试：BR-AUTH-02 全覆盖
  - JWT 篡改 / 过期 / 黑名单测试
  - SQL 注入测试（关键查询参数）
- depends_on：T-1-TEST-03
- DoD：报告写入 `docs/security-baseline.md`；高危漏洞修复

**T-1-DEPLOY-01 生产 docker-compose + Nginx**
- Deliverable：
  - `docker-compose.prod.yml`：含 nginx、backend (gunicorn + uvicorn workers)、frontend (静态构建产物)、postgres、redis、celery worker、celery beat
  - `nginx/nginx.conf`：HTTPS（用 letsencrypt 或自签证书占位）+ 限流 + gzip + 静态资源缓存
  - 健康检查 + 重启策略
- depends_on：T-1-TEST-02
- DoD：
  - [ ] 一条命令启动生产 stack
  - [ ] HTTPS 生效
  - [ ] 限流配置生效

**T-1-DEPLOY-02 监控接入**
- Deliverable：
  - FastAPI prometheus 中间件（请求耗时 / QPS / 错误率）
  - Celery prometheus exporter
  - PostgreSQL exporter
  - Grafana 仪表盘 JSON：API 性能、Celery 队列、DB 连接池、磁盘
- depends_on：T-1-DEPLOY-01
- DoD：
  - [ ] 4 个仪表盘可访问
  - [ ] 告警规则示例（P99 > 1.5s、错误率 > 1%、队列堆积 > 100）

**T-1-DEPLOY-03 备份脚本 + DR 演练**
- Deliverable：
  - `scripts/backup.sh`：pg_dump + storage 同步到 OSS（占位）
  - `scripts/restore.sh`：从备份恢复
  - 文档：`docs/disaster-recovery.md`
- depends_on：T-1-DEPLOY-01
- DoD：完整一次备份 + 恢复演练通过

**T-1-DEPLOY-04 上线 checklist + 运维文档**
- Deliverable：
  - `docs/release-checklist.md`：上线前必检项（迁移、seed、备份、监控、告警、回滚预案）
  - `docs/operations.md`：日常运维（添加 admin、查日志、清缓存、Celery 重启）
  - `docs/troubleshooting.md`：常见问题
- depends_on：T-1-DEPLOY-03
- DoD：文档可独立指导新人上手

---

## 6. API 接口完整清单

下表是全功能 API。Agent 实现时 MUST 完全对齐路径与方法。

| Method | Path | 任务 ID | 权限 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | T-1-AUTH-BE-02 | 公开 |
| POST | `/api/v1/auth/refresh` | T-1-AUTH-BE-03 | refresh_token |
| POST | `/api/v1/auth/logout` | T-1-AUTH-BE-03 | 已登录 |
| GET | `/api/v1/auth/me` | T-1-AUTH-BE-03 | 已登录 |
| GET | `/api/v1/users` | T-1-USER-BE-01 | admin |
| POST | `/api/v1/users` | T-1-USER-BE-01 | admin |
| GET | `/api/v1/users/{id}` | T-1-USER-BE-01 | admin / 自己 |
| PUT | `/api/v1/users/{id}` | T-1-USER-BE-01 | admin / 自己（限基础信息）|
| DELETE | `/api/v1/users/{id}` | T-1-USER-BE-01 | admin |
| POST | `/api/v1/users/{id}/reset-password` | T-1-USER-BE-01 | admin |
| POST | `/api/v1/users/me/change-password` | T-1-USER-BE-01 | 自己 |
| GET | `/api/v1/users/{id}/active-sub-projects` | T-1-USER-BE-04 | admin |
| POST | `/api/v1/users/{id}/batch-handover` | T-1-USER-BE-04 | admin |
| GET | `/api/v1/departments` | T-1-DEPT-BE-01 | 已登录 |
| POST | `/api/v1/departments` | T-1-DEPT-BE-01 | admin |
| PUT | `/api/v1/departments/{id}` | T-1-DEPT-BE-01 | admin |
| DELETE | `/api/v1/departments/{id}` | T-1-DEPT-BE-01 | admin |
| GET | `/api/v1/system/health-warnings` | T-1-USER-BE-03 | admin |
| GET | `/api/v1/system/health` | T-1-INFRA-BE-05 | 公开 |
| GET | `/api/v1/main-projects` | T-1-PROJECT-BE-01 | view_all |
| POST | `/api/v1/main-projects` | T-1-PROJECT-BE-01 | dept_manager |
| GET | `/api/v1/main-projects/{id}` | T-1-PROJECT-BE-01 | view_all |
| PUT | `/api/v1/main-projects/{id}` | T-1-PROJECT-BE-01 | 创建人 + 审核前 |
| POST | `/api/v1/main-projects/{id}/submit` | T-1-PROJECT-BE-02 | 创建人 |
| POST | `/api/v1/main-projects/{id}/review` | T-1-PROJECT-BE-02 | dept_manager 非创建人 / admin |
| POST | `/api/v1/main-projects/{id}/close` | T-1-PROJECT-BE-03 | dept_manager |
| GET | `/api/v1/sub-projects` | T-1-PROJECT-BE-04 | 按角色 |
| POST | `/api/v1/sub-projects` | T-1-PROJECT-BE-04 | proj_leader |
| GET | `/api/v1/sub-projects/{id}` | T-1-PROJECT-BE-04 | 按权限 |
| PUT | `/api/v1/sub-projects/{id}` | T-1-PROJECT-BE-04 | 创建人 + 审核前 |
| POST | `/api/v1/sub-projects/{id}/submit` | T-1-PROJECT-BE-05 | 创建人 |
| POST | `/api/v1/sub-projects/{id}/review` | T-1-PROJECT-BE-05 | dept_manager / admin |
| POST | `/api/v1/sub-projects/{id}/close` | T-1-PROJECT-BE-06 | dept_manager |
| POST | `/api/v1/sub-projects/{id}/terminate` | T-1-PROJECT-BE-06 | dept_manager / admin |
| POST | `/api/v1/sub-projects/{id}/handover` | T-1-USER-BE-04 | admin |
| GET | `/api/v1/sub-projects/{id}/members` | T-1-PROJECT-BE-07 | view_own 及以上 |
| POST | `/api/v1/sub-projects/{id}/members` | T-1-PROJECT-BE-07 | proj_leader（本项目）|
| DELETE | `/api/v1/sub-projects/{id}/members/{user_id}` | T-1-PROJECT-BE-07 | proj_leader |
| GET | `/api/v1/phases` | T-1-PHASE-BE-02 | 按权限 |
| GET | `/api/v1/phases/{id}` | T-1-PHASE-BE-02 | 按权限 |
| POST | `/api/v1/phases/{id}/promote` | T-1-PHASE-BE-03 | proj_leader / admin |
| GET | `/api/v1/phases/{id}/acceptance-steps` | T-1-ACC-BE-01 | 按权限 |
| POST | `/api/v1/phases/{id}/acceptance-steps` | T-1-ACC-BE-01 | proj_leader |
| PUT | `/api/v1/phases/{id}/acceptance-steps/{sid}` | T-1-ACC-BE-01 | step 责任人 / proj_leader |
| GET | `/api/v1/sub-projects/{id}/payments` | T-1-PAY-BE-04 | view_all / 项目成员 |
| POST | `/api/v1/sub-projects/{id}/payments` | T-1-PAY-BE-02/03 | finance_manager |
| GET | `/api/v1/sub-projects/{id}/payments/{pid}` | T-1-PAY-BE-04 | 同列表 |
| GET | `/api/v1/tasks` | T-1-TASK-BE-02 | 按权限 |
| POST | `/api/v1/tasks` | T-1-TASK-BE-02 | proj_leader |
| GET | `/api/v1/tasks/{id}` | T-1-TASK-BE-02 | 按权限 |
| PUT | `/api/v1/tasks/{id}` | T-1-TASK-BE-02 | proj_leader |
| POST | `/api/v1/tasks/{id}/complete` | T-1-TASK-BE-02 | 被指派人 |
| POST | `/api/v1/documents` | T-1-DOC-BE-01 | 项目成员 |
| GET | `/api/v1/documents` | T-1-DOC-BE-01 | 按权限 |
| GET | `/api/v1/documents/{id}/download` | T-1-DOC-BE-03 | 按权限 |
| GET | `/api/v1/documents/{id}/preview` | T-1-DOC-BE-04 | 按权限（仅 PDF） |
| GET | `/api/v1/notifications` | T-1-NOTIF-BE-02 | 已登录 |
| GET | `/api/v1/notifications/unread-count` | T-1-NOTIF-BE-02 | 已登录 |
| POST | `/api/v1/notifications/{id}/read` | T-1-NOTIF-BE-02 | 接收人 |
| POST | `/api/v1/notifications/read-all` | T-1-NOTIF-BE-02 | 已登录 |
| GET | `/api/v1/revoke-requests` | T-1-REVOKE-BE-01 | 按权限 |
| POST | `/api/v1/revoke-requests` | T-1-REVOKE-BE-01 | proj_leader |
| POST | `/api/v1/revoke-requests/{id}/review` | T-1-REVOKE-BE-01 | dept_manager / admin |
| GET | `/api/v1/audit-logs` | T-1-AUDIT-BE-02 | admin |

> 完整请求/响应 schema MUST 在 OpenAPI 文档体现（FastAPI 自动 + 手工补 description / example）。

---

## 7. 错误码规范

| 范围 | 用途 | 关键示例 |
| --- | --- | --- |
| 0 | 成功 | `{code: 0, message: "success"}` |
| 1xxx | 认证错误 | 1001 token 失效；1002 账号锁定；1003 权限不足；1010 自审被拒 |
| 2xxx | 参数错误 | 2001 字段缺失；2002 类型错误；2003 取值非法；2004 密码强度不足 |
| 3xxx | 业务逻辑错误 | 3001 超预算需确认；3002 必传文档缺失；3003 状态不允许；3010 in-flight 项目阻断停用；3020 非 PDF 不可预览；3030 撤销环节非 completed |
| 4xxx | 资源错误 | 4001 不存在；4002 已存在；4003 唯一约束冲突 |
| 5xxx | 服务器错误 | 5001 DB 错误；5002 文件存储错误；5003 第三方依赖不可用 |

**3xxx 错误响应 MUST 含足够的 `data` 字段供前端处理**：
- 3001：`data: {budget, current_spent, this_amount, over_amount}`
- 3010：`data: {in_flight_count, sample_projects: [...]}`

---

## 8. 测试策略

### 8.1 测试金字塔

| 层 | 工具 | 目标覆盖率 |
| --- | --- | --- |
| 单元测试（service / utility / validator） | pytest + factory-boy | 80% |
| 集成测试（API + DB） | pytest + httpx + testcontainers | 关键路径 100% |
| E2E 测试 | pytest + 完整环境 | 5 个核心流程（T-1-TEST-02） |
| 前端单元 | Vitest | 50% |
| 前端 E2E | Playwright（可选 Phase 2） | — |
| 性能测试 | locust | NFR 验证 |
| 安全测试 | pip-audit + 手工脚本 | 零高危 |

### 8.2 必测场景（不通过即不准上线）

参见 T-1-TEST-03 列出的 14 项必测场景。

### 8.3 测试数据策略

- 每个测试用 fresh DB（testcontainers 启动新容器或事务回滚）
- factory-boy 生成数据，不写硬编码 SQL
- 共用 fixture：`admin_user`, `dept_manager_user`, `proj_leader_user`, `proj_member_user`, `finance_user`, `sample_main_project`, `sample_sub_project_with_phases`

---

## 9. Definition of Done（任务级通用 DoD）

每个 §5 任务的 DoD 之外，全部任务 MUST 满足：

- [ ] 代码合并到 develop 分支，通过 CI（lint + mypy + test + 覆盖率）
- [ ] 涉及 API 的任务，OpenAPI 文档已更新（含 description + example）
- [ ] 涉及 DB 的任务，Alembic 迁移已生成且 `upgrade head` + `downgrade -1` 都通过
- [ ] 涉及业务规则的任务，对应的 BR-* / FR-* 在 PR 描述中列出，并有测试用例引用
- [ ] 至少 1 个集成测试覆盖 happy path
- [ ] 至少 1 个测试覆盖最关键的 failure path（权限拒绝 / 状态不允许 等）
- [ ] structlog 关键操作日志已加（user_id, action, target_id）
- [ ] 涉及敏感操作（写、删、状态变更），audit_log 已接入（@audited 装饰）
- [ ] 前端任务额外要求：组件单元测试（covering 核心交互） + 错误状态有 UI 反馈
- [ ] 性能合理：列表接口默认带分页；查询带索引；N+1 已用 `selectinload` / `joinedload` 优化

---

## 10. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 主项目 spent_amount 写热点 | 行锁 + 重试；如压力高，改为异步聚合（outbox 模式） |
| dept_manager 数量不足导致系统不可用 | BR-ROLE-01 启动检查 + UI 告警 + admin 兜底 |
| 文件存储 disk full | 监控磁盘 80% 告警；prod 强制用 OSS |
| Celery worker 失败任务丢失 | 启用 result backend + 失败重试 3 次 + 死信队列告警 |
| LLM agent 误解需求 | §0 强约束阅读规则；遇到歧义按 AGENT_KICKOFF_PROMPT.md §D 提问 |
| 测试覆盖率刷数 | code review 重点检查 assertion 是否对核心规则 |
| 并发付款金额漂移 | T-1-PAY-BE-02 必须 10 并发测试 |
| audit_log 表膨胀 | 月分区 + 老分区归档脚本（Phase 4） |
| 前端打包后路由刷新 404 | nginx 配置 history 模式 fallback；T-1-DEPLOY-01 必含 |
| Celery beat 多实例重复触发 | 仅启动 1 个 beat 实例；用 `redbeat` 分布式锁（如要多实例） |

---

## 11. 启动顺序与并行建议

### 11.1 关键路径

```
M1 INFRA → M2 AUTH/USER → M3 PROJECT → M4 PHASE/DOC/TASK → M5 PAY/ACC/REVOKE → M6 NOTIF场景/CRON → M7 TEST/DEPLOY
```

### 11.2 可并行的工作

**M1 内部**：
- T-1-INFRA-BE-04 / 05 / 06 / 09 与 T-1-INFRA-FE-07 / 08 可并行（FE 不依赖 BE 业务）

**M2 内部**：
- BE 模块（AUTH-01~04 + USER + DEPT + NOTIF-01 + AUDIT-01）按依赖串行
- FE 模块（AUTH-FE-05/06 + USER-FE + DEPT-FE）可与对应 BE 完成后立刻启动

**M3 内部**：
- PROJECT-BE-01 → 02 → 03 串行
- 与之并行：PROJECT-BE-04 → 05 → 06 → 07
- USER-BE-04 依赖 PROJECT-BE-07，紧随其后
- FE 任务等对应 BE 完成

**M4 内部**：
- PHASE / DOC / TASK 三条线一定程度可并行（DOC 依赖 PHASE 表存在，TASK 依赖 PHASE 表存在）
- FE 任务等对应 BE

**M5 内部**：
- PAY / ACC / REVOKE 三条线可并行

**M6**：
- NOTIF-03 依赖所有业务模块 → 必须等 M5 全部完成
- AUDIT-02/03、CRON-01/02/03 可并行

**单 LLM agent 全栈执行**：按 §11.1 关键路径，14.5 周。
**多 agent 并行（前后端各 1）**：可压缩到 ~10 周，但跨 agent 的接口契约需要严格对齐，建议每个 BE 任务完成后立即出 Pydantic schema 给 FE。

---

## 12. 后续阶段

Phase 2 ~ Phase 5 见 `docs/ROADMAP.md`。本计划仅覆盖 MVP（Phase 1）全功能范围。

每个 Phase 启动时按本计划相同模板展开（同样的 ID 规则、同样的 DoD 严格度、同样的 OPEN_QUESTIONS 流程）。

---

*— 开发计划 V2.0（全功能版）完 —*
