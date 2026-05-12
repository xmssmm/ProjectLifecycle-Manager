# Branch Protection 配置说明

本项目要求 `main` 和 `develop` 分支启用保护规则，确保 CI 失败的 PR 不能合并。

## 保护分支

- `main`
- `develop`

## 必选规则

1. 启用 `Require a pull request before merging`。
2. 启用 `Require status checks to pass before merging`。
3. 将以下 GitHub Actions job 设为 required status checks：
   - `Backend lint, typecheck, test`
   - `Frontend lint, typecheck, test`
4. 启用 `Require branches to be up to date before merging`。
5. 启用 `Do not allow bypassing the above settings`。
6. 禁止 force push。
7. 禁止删除受保护分支。

## 覆盖率门槛

- Backend：`pytest --cov` 强制不低于 70%。
- Frontend：`vitest --coverage` 强制不低于 50%。

M7 的测试基础设施任务会把 backend 覆盖率门槛提升到 80%。
