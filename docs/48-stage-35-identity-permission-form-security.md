# 阶段 35：Identity, Permission and Form Security Boundary

最后更新：2026-06-12

阶段 35 承接阶段 34。阶段 34 已把运营 Console 的检索和返回路径补齐；阶段 35 开始给已有 API 和表单动作补一层教学版身份与权限边界，重点是让 `actor` 不再只是一个散落在请求体、header 或表单里的字符串，而是能进入一个统一的 identity context，再由 permission policy 判断是否允许执行敏感动作。

本阶段仍保持小范围实现：不新增数据库表，不做真实登录、session、token、密码、企业 IAM 或 CSRF token；只在现有 FastAPI app 内增加教学版身份上下文、角色到权限映射和高风险路径的权限校验。

## 中文定义

身份上下文，是系统在处理一次请求时识别出的“谁在操作”和“他拥有哪些角色”的最小上下文。

对应英文术语：

- identity context
- actor
- role
- permission
- route-level permission
- form security boundary
- CSRF

## 为什么金融系统需要它

金融系统里，很多动作不只是“能不能调用接口”，还要回答：

1. 谁发起了这个动作？
2. 这个人是否有权限做这个动作？
3. 请求里声明的操作人和系统识别出的操作人是否一致？
4. 如果被拒绝，拒绝事实是否也进入 access audit？

阶段 35 的目标不是做生产级认证，而是把这些问题落到可运行的代码边界上。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/48-stage-35-identity-permission-form-security.md
```

## 第一版实现

新增教学版身份对象：

```text
PlatformIdentityContext
```

字段：

```text
actor
roles
source
```

身份来源：

- `x-actor-id`：教学版 actor。
- `x-actor-role`：可选角色头，允许显式传入一个或多个角色。
- 如果没有 `x-actor-role`，系统会根据样例 actor 前缀推断角色，例如 `ops_manager_*`、`ops_user_*`、`audit_reader_*`、`api_compliance_lead_*`。

新增教学版角色和权限映射：

```text
PERMISSIONS_BY_ROLE
```

示例角色：

- `api_client`
- `api_viewer`
- `ops_user`
- `ops_manager`
- `approval_viewer`
- `audit_reader`
- `compliance_lead`
- `investigator`
- `system_scheduler`
- `async_worker`

新增权限校验 helper：

```text
_require_permission()
_require_identity_actor_matches()
```

`_require_permission()` 会在权限不足时返回 `403 PermissionDenied`，并写入 denied access audit。

`_require_identity_actor_matches()` 用于 JSON 审批更新接口，检查 `x-actor-id` 和请求体里的 `decided_by` 是否一致；不一致时返回 `403 IdentityMismatch`，并写入 denied access audit。

## 当前受保护路径

阶段 35 第一版优先保护敏感查询和审批更新路径：

```text
GET  /platform/api-access-events
GET  /platform/api-access-anomaly-findings
POST /platform/api-access-investigation-cases

POST /platform/operation-approvals
GET  /platform/operation-approvals
GET  /platform/operation-approvals/{approval_id}
GET  /platform/operation-approvals/{approval_id}/view
PATCH /platform/operation-approvals/{approval_id}/approve
PATCH /platform/operation-approvals/{approval_id}/reject
PATCH /platform/operation-approvals/{approval_id}/cancel
PATCH /platform/operation-approvals/{approval_id}/expire

POST /platform/operation-approvals/{approval_id}/approve-form
POST /platform/operation-approvals/{approval_id}/reject-form
POST /platform/operation-approvals/{approval_id}/cancel-form
POST /platform/operation-approvals/{approval_id}/expire-form
```

表单路径没有真实 session，因此暂时仍从表单里的 `decided_by` 构造教学版 identity context，再执行 permission policy。这个设计只用于学习“表单动作也要进入同一套权限边界”，不代表生产级浏览器安全。

## 当前仍不做

- 不做真实 login / logout。
- 不做 session、JWT、OAuth、OIDC 或企业 IAM。
- 不新增 user / role 数据库表。
- 不做密码、MFA、设备绑定或密钥管理。
- 不做真实 CSRF token。
- 不做真实敏感字段按角色脱敏。
- 不改变 payment run、async run、approval record 的业务状态机。
- 不声称满足任何真实金融机构、监管或审计要求。

## 程序员实现注意点

阶段 35 有三个值得记住的工程点。

第一，`actor` 和 `role` 要分开。`actor` 说明是谁，`role` 说明这个人以什么职责行动。早期系统经常把两者混在一个字符串里，后续会很难维护。

第二，拒绝也要审计。权限不足、身份不一致、状态流转失败都应该进入 access audit。否则安全事件只存在于 HTTP 响应里，事后无法复盘。

第三，表单安全不是只有 confirmation。阶段 26 到阶段 34 已经有 confirmation 字段，但 confirmation 只能降低误操作，不能替代身份认证、权限校验或 CSRF 防护。阶段 35 只补了 permission policy；CSRF 仍是后续真实 Web 安全边界。

## 验证记录

截至 2026-06-12，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m py_compile .\labs\fintech-platform\platform_api_app.py .\labs\fintech-platform\test_platform_api_app.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
py_compile: 通过
test_platform_api_app.py: 50 passed
labs/fintech-platform: 148 passed
demo.py: 可运行
labs: 393 passed
```

说明：

- 普通沙箱执行测试时，无法在 `labs/fintech-platform/.test-data` 下打开 SQLite 测试数据库，报 `sqlite3.OperationalError: unable to open database file`。
- 普通沙箱执行 `py_compile` 时，写入 `__pycache__` 会被拒绝。
- 普通沙箱执行 `demo.py` 时，写入 `labs/fintech-platform/reports` 报告文件也需要授权。
- 使用授权的非沙箱执行后，编译检查、定向测试、fintech-platform 测试、demo 和全量 labs 测试均通过。

## 后续候选方向

阶段 35 完成后，建议进入阶段 36：一致性、并发和恢复。

阶段 36 可以优先处理：

1. async worker claim / lease / timeout 的教学实现或设计。
2. 并发 approve / retry 的冲突测试。
3. platform store、async run store、approval store 的事务边界说明。
4. schema migration、backup / restore 和失败恢复演练的最小文档或代码样例。
