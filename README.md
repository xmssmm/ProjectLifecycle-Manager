# 企业项目过程管理与资料归档系统

这是采购类项目过程管理与资料归档系统的全功能开发仓库。当前任务为 `T-1-INFRA-01`，目标是建立可运行的后端、前端、数据库、缓存与本地开发骨架。

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

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、Pydantic v2、Alembic、Celery、Redis、PostgreSQL 16
- 前端：Vue 3、Vite、TypeScript、Element Plus、Pinia、Axios、Vue Router
- 基础设施：Docker Compose、Nginx、Redis 7、PostgreSQL 16

## 当前状态

本仓库处于 greenfield 初始化阶段。业务功能会严格按照 `docs/DEVELOPMENT_PLAN_FULL.md` 和 `docs/ROADMAP.md` 分阶段实现。
