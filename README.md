# 企业项目过程管理与资料归档系统

这是采购类项目过程管理与资料归档系统的全功能开发仓库。当前 `develop` 已完成 MVP（Phase 1）到 Phase 5“平台化与智能化”功能，覆盖项目流程、资料归档、任务协作、付款、撤销、审计、报表、仪表盘、移动端适配、Office 预览、通知增强、企业集成、归档恢复、全文检索、批量导入导出、多时区、国际化、生产高可用部署、工作流模板、自定义报表、多项目类型、跨项目分析和可审计 AI 辅助能力。

## 本地启动 5 步指南

1. 复制环境变量模板：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 安装后端依赖：

   ```powershell
   cd backend
   python -m pip install -e .[dev]
   ```

3. 安装前端依赖：

   ```powershell
   cd ..\frontend
   npm.cmd install
   ```

4. 启动本地服务：

   ```powershell
   cd ..
   docker compose up --build
   ```

5. 打开应用：

   - 前端：http://localhost:5173
   - 后端健康检查：http://localhost:8000/health
   - OpenAPI 文档：http://localhost:8000/docs

## 常用开发命令

后端：

```powershell
cd backend
python -m pytest tests/
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm.cmd run dev
npm.cmd run test:unit
npm.cmd run typecheck
```

## 文档

- 部署手册：`docs/deployment-manual.md`
- 生产发布与试用部署：`docs/PRODUCTION_DEPLOYMENT_MANUAL.md`
- 使用手册：`docs/user-manual.md`
- 用户使用手册：`docs/USER_MANUAL.md`
- 管理员与运维手册：`docs/ADMIN_OPERATIONS_MANUAL.md`
- Phase 4 发布说明：`docs/PHASE_4_RELEASE_NOTES.md`
- Phase 5 发布说明：`docs/PHASE_5_RELEASE_NOTES.md`
- Phase 5 实施计划：`docs/PHASE_5_PLAN.md`
- Phase 5 默认决策：`docs/PHASE_5_OPEN_QUESTIONS.md`
- Phase 2 发布说明：`docs/RELEASE_NOTES_PHASE_2.md`
- Phase 3 实施计划：`docs/PHASE_3_PLAN.md`
- Phase 3 默认决策：`docs/PHASE_3_OPEN_QUESTIONS.md`
- Office 在线预览部署与使用：`docs/office-preview.md`
- 日常运维：`docs/operations.md`
- 上线检查清单：`docs/release-checklist.md`
- 故障排查：`docs/troubleshooting.md`

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、Pydantic v2、Alembic、Celery、Redis、PostgreSQL 16
- 前端：Vue 3、Vite、TypeScript、Element Plus、Pinia、Axios、Vue Router
- 基础设施：Docker Compose、Nginx、Redis 7、PostgreSQL 16

## 当前状态

Phase 5 功能已合并到 `develop`，可按 `docs/PRODUCTION_DEPLOYMENT_MANUAL.md` 进行生产环境试用部署。AI provider 默认关闭，建议先完成基础流程、报表、模板、审计和权限验收，再按需启用受控 AI 网关。
