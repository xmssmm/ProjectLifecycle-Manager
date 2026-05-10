# 企业项目过程管理与资料归档系统

这是采购类项目过程管理与资料归档系统的全功能开发仓库。当前 `develop` 已完成 MVP（Phase 1）和 Phase 2“体验与可视化”功能，覆盖项目流程、资料归档、任务协作、付款、撤销、审计、报表、仪表盘、移动端适配、Office 预览和通知增强。

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
- 使用手册：`docs/user-manual.md`
- Phase 2 发布说明：`docs/RELEASE_NOTES_PHASE_2.md`
- Office 在线预览部署与使用：`docs/office-preview.md`
- 日常运维：`docs/operations.md`
- 上线检查清单：`docs/release-checklist.md`
- 故障排查：`docs/troubleshooting.md`

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、Pydantic v2、Alembic、Celery、Redis、PostgreSQL 16
- 前端：Vue 3、Vite、TypeScript、Element Plus、Pinia、Axios、Vue Router
- 基础设施：Docker Compose、Nginx、Redis 7、PostgreSQL 16

## 当前状态

Phase 2 功能已合并到 `develop`。后续演进按 `docs/ROADMAP.md` 继续推进 Phase 3 企业集成、Phase 4 规模与合规、Phase 5 平台化与智能化。
