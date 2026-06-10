# 阶段 34：Console Workflow Controls

最后更新：2026-06-10

阶段 34 承接阶段 33 的剩余路线图，先补强已有 `FinTech Platform Console` 的运营检索和工作流可用性。阶段 34 不新增数据库表，不引入前端框架，也不处理真实登录；目标是让现有 payment run、async run 和 operation approval 数据更容易被运营人员按人和时间范围定位。

本阶段继续遵守“不要拆太多细碎文档”的约定，把目标、范围、实现和验证记录合并在这一篇文档里。

## 中文定义

运营 Console 工作流控件，是指帮助运营人员在控制台中缩小数据范围、识别高影响操作风险，并在列表和详情页之间往返的最小页面能力。

对应英文术语：

- operations console
- workflow controls
- actor filter
- date range filter
- high-impact operation

## 为什么先做这个阶段

阶段 31 已经给 console 增加了 payment / async / approval status 筛选；阶段 33 总结时也明确当前平台的运营工作流仍偏轻。进入身份权限、并发恢复或外部清结算前，先把现有运营页面的基本检索和返回路径补齐，可以更清楚地看出后续哪些页面和动作需要权限保护。

本阶段回答三个实践问题：

1. 运营人员如何按 actor 查找一批相关 payment、async 和 approval 记录？
2. 运营人员如何按创建日期范围缩小最近列表、报表摘要和待审批记录？
3. 高影响审批动作和详情页跳转如何减少误操作和迷路？

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
docs/47-stage-34-console-workflow-controls.md
```

## 页面变化

`GET /platform/view` 新增三个查询参数：

```text
actor
created_from
created_to
```

console 顶部的 GET 筛选表单现在包含：

```text
Payment status
Async status
Approval status
Actor
Created from
Created to
```

筛选会影响：

- Recent Payment Runs。
- Recent Async Runs。
- Failed Async Runs。
- Operations Report Summary。
- Operations Run Rows。
- Ledger Reconciliation Findings。
- Operation Approval Summary。
- Pending Operation Approvals。
- Approval Records。

## 过滤语义

`actor` 使用大小写不敏感的包含匹配。

不同数据来源的 actor 取法不同：

- payment run：当前 response 不直接暴露 actor，因此从 `PlatformRunSnapshot.audit_events` 中匹配 audit event 的 actor。
- async run：从 `PlatformAsyncRun.request_payload["actor"]` 匹配。
- operation approval：从 `requested_by` 和 `approved_by` 匹配。

日期范围使用 ISO 日期：

```text
YYYY-MM-DD
```

日期来源：

- payment run：使用 response 中的 `created_at`。
- async run：使用 `PlatformAsyncRun.created_at`。
- operation approval：使用 `OperationApprovalRecord.requested_at`。

如果 `created_from` 或 `created_to` 格式无效，console 会显示错误提示并忽略该无效日期。若 `created_from` 晚于 `created_to`，两个日期筛选都会被忽略。

## 工作流提示和返回路径

`Pending Operation Approvals` 区块新增高影响操作提示：

```text
High-impact approval actions can change retry eligibility. Review the async status, request reason, and confirmation text before deciding.
```

以下详情页新增明确返回入口：

```text
GET /platform/operation-approvals/{approval_id}/view
GET /platform/async-payment-runs/{run_id}/view
GET /platform/payment-runs/{run_id}/view
```

页面会显示：

```text
Back to Console
```

这些变化是运营可用性补强，不代表真实 IAM、session、CSRF 或权限模型已经完成。

## 第一版不做

- 不新增数据库表。
- 不新增真实登录、session、token 或 role-based access control。
- 不新增 CSRF 防护。
- 不新增复杂前端框架、模板框架或独立前端项目。
- 不新增 cursor pagination 或批量操作。
- 不新增 operation type、severity、SLA、assignee 或 comment 工作流。
- 不把教学版 actor 字段当成可信身份来源。

## 工程结论

阶段 34 的关键点不是新增业务状态，而是把已有运营数据从“能看见”推进到“能按人和时间定位”。

对程序员来说，这里有一个重要边界：同一个 `actor` 筛选在不同表里的来源并不相同。payment run 的 actor 需要从 audit timeline 推断，async run 的 actor 来自请求 payload，approval 的 actor 来自审批记录字段。因此筛选函数不能假装所有对象有同一个字段；必须针对数据模型分别处理，并在文档里说明来源。

## 验证记录

截至 2026-06-10，已确认：

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
test_platform_api_app.py: 46 passed
labs/fintech-platform: 144 passed
demo.py: 可运行
labs: 389 passed
```

说明：

- 普通沙箱执行时，测试无法在 `labs/fintech-platform/.test-data` 下打开 SQLite 测试数据库，报 `sqlite3.OperationalError: unable to open database file`。
- 普通沙箱执行 `demo.py` 时，写入 `labs/fintech-platform/reports` 报告文件也需要授权。
- 普通沙箱执行 `py_compile` 时，写入 `__pycache__` 会被拒绝。
- 使用授权的非沙箱执行后，编译检查、定向测试、fintech-platform 测试、demo 和全量 labs 测试均通过。

## 后续候选方向

阶段 34 完成后，建议进入阶段 35：身份、权限和表单安全边界。

阶段 35 可以优先回答：

1. actor 如何从“请求自报字段”升级为教学版身份上下文？
2. 哪些 route 和 console form 需要 permission policy？
3. 当前 approve / reject / cancel / expire 表单如何解释 CSRF、self-approval 和敏感字段脱敏边界？
