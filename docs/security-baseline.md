# T-1-TEST-05 基础安全测试报告

## 目标

- 依赖漏洞扫描：`pip-audit` / `npm audit`
- 越权测试：`proj_member` 访问其他子项目数据必须被拒
- 弱密码测试：BR-AUTH-02 全覆盖
- JWT 篡改 / 过期 / 黑名单测试
- SQL 注入测试：关键查询参数必须参数化或按普通字符串处理
- 处理结论：高危漏洞必须修复；非高危进入跟踪清单

## 测试证据

| 类别 | 命令/测试 | 处理结论 |
| --- | --- | --- |
| pip-audit | `cd backend; python -m pip_audit . --format json --output ..\docs\security-pip-audit.json` | 已执行；未发现已知 Python 依赖漏洞 |
| npm audit | `cd frontend; npm.cmd audit --json` 输出到 `docs/security-npm-audit.json` | 已执行；5 个 moderate，0 个 high/critical |
| 越权测试 | `backend/tests/unit/test_phase_query.py::test_phase_service_lists_visible_phases_and_dynamic_required_documents` | `proj_member` outsider 被拒 |
| 弱密码测试 | `backend/tests/unit/test_auth_login.py::test_password_strength_validator_rejects_weak_passwords` | 覆盖长度、数字、大小写、特殊字符 |
| JWT 篡改 / 过期 / 黑名单 | `backend/tests/unit/test_auth_session.py::test_validate_token_claims_rejects_tampered_and_expired_tokens`；`backend/tests/unit/test_auth_session.py::test_user_wide_token_revocation_rejects_existing_access_tokens`；`backend/tests/unit/test_auth_session.py::test_refresh_me_logout_and_blacklisted_access_token_flow` | 覆盖篡改、过期、用户级吊销、logout 黑名单 |
| SQL 注入 | `backend/tests/unit/test_audit_log_query.py::test_audit_log_query_parameters_are_bound_against_sql_injection` | 查询参数不拼接 SQL 字面量 |

## 依赖扫描结果

| 工具 | 结果 | 高危漏洞 | 处理结论 |
| --- | --- | --- | --- |
| pip-audit | 0 个漏洞；原始结果见 `docs/security-pip-audit.json` | 0 | 无高危漏洞需要修复 |
| npm audit | 5 个 moderate、0 个 high、0 个 critical；原始结果见 `docs/security-npm-audit.json` | 0 | 无高危漏洞需要修复；moderate 项均来自前端开发工具链，进入后续依赖升级跟踪 |

## npm audit 跟踪清单

| 包 | 等级 | 修复建议 | 当前处理 |
| --- | --- | --- | --- |
| `@vitest/coverage-v8` | moderate | 升级到 `4.1.5`，属于 SemVer major | 记录到依赖升级清单，避免在安全基线任务中引入大版本测试栈变更 |
| `esbuild` | moderate | 通过 `vite@8.0.11` 修复，属于 SemVer major | 记录到依赖升级清单 |
| `vite` | moderate | 升级到 `8.0.11`，属于 SemVer major | 记录到依赖升级清单 |
| `vite-node` | moderate | 通过 `vitest@4.1.5` 修复，属于 SemVer major | 记录到依赖升级清单 |
| `vitest` | moderate | 升级到 `4.1.5`，属于 SemVer major | 记录到依赖升级清单 |

## 处理结论

- `pip-audit` 未发现已知漏洞。
- `npm audit` 未发现 high/critical 漏洞，满足本任务“高危漏洞修复”的 DoD。
- 前端 moderate 漏洞集中在 Vite/Vitest/esbuild 开发工具链，官方修复路径需要 SemVer major 升级；本阶段不做盲目大版本升级，后续依赖升级任务需结合前端测试与构建回归一起处理。
- 越权测试、弱密码测试、JWT 篡改 / 过期 / 黑名单测试、SQL 注入测试均纳入自动化测试证据。
