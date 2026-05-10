# Phase 2 实施计划

目标：实现 roadmap Phase 2“体验与可视化”的全部功能，让用户用得舒服，让管理者看得清楚。

实施策略：按价值和依赖排序，从后端数据能力到前端体验逐步推进。每个任务单独分支、先写失败测试、实现、review、全量验证后合并。

## 默认决策

详见 `docs/PHASE_2_OPEN_QUESTIONS.md`：

- 仪表盘数据缓存 5 分钟。
- 报表导出 Phase 2 不做电子签章。
- Office 预览采用 LibreOffice 转 PDF，不先上 OnlyOffice。

## 任务顺序

1. `T-2-DASH-01` 仪表盘数据 API（按角色聚合）
   - 后端新增 dashboard router/service/schema。
   - 支持 admin、dept_manager、finance_manager、proj_leader、proj_member 5 个 scope。
   - Redis 缓存 5 分钟，cache key 包含 scope 和 actor id。
   - 权限隔离：proj_leader/proj_member 只看自己负责或参与的数据。

2. `T-2-DASH-02` 仪表盘前端页面
   - 增加 dashboard API client/store/views。
   - 使用 ECharts 呈现饼图、柱图和关键指标。
   - 角色进入首页时看到对应 dashboard。

3. `T-2-DASH-03` 项目进度漏斗
   - 后端提供主项目下子项目环节分布。
   - 前端支持点击环节钻取子项目列表。

4. `T-2-REPORT-01` 报表生成 service
   - 新增 report_jobs 表。
   - 支持 project_list、payment_journal、dept_summary、monthly_summary。
   - Excel 使用 openpyxl，PDF 使用 reportlab。
   - 大报表走 Celery，提供进度查询。

5. `T-2-REPORT-02` 报表下载与分享
   - 下载接口校验请求者权限。
   - 生成文件 7 天后由 Celery 清理。

6. `T-2-MOBILE-01` 响应式布局适配
   - 已有 MVP 页面在 375px 到 768px 宽度可读可操作。
   - 审核、付款、推进环节在移动端只读并引导到 PC。

7. `T-2-MOBILE-02` 移动端任务完成快捷操作
   - 我的任务移动端两步内完成任务。
   - 保留二次确认。

8. `T-2-DOC-04` Office 文档预览
   - LibreOffice headless 转 PDF 副本。
   - 后端提供 Office 预览接口，前端沿用 PDF 预览组件。

9. `T-2-NOTIF-04` 通知偏好设置
   - 新增 user_notification_preferences。
   - 通知发送前读取偏好，关闭后对新通知立即生效。

10. `T-2-NOTIF-05` 通知摘要
    - 支持实时通知和每日摘要。
    - 每日 9 点 Celery 汇总前一天通知。

## Phase 2 验收

- 角色仪表盘、报表导出、移动端、Office 预览、通知偏好/摘要均可运行。
- 后端 `ruff`、`mypy`、`pytest` 通过。
- 前端 `npm run lint`、`npm run typecheck`、`npm run test:unit`、`npm run build` 通过。
- 更新中文部署、使用和运维文档。
