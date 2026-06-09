# 阶段 25：Operation Approval Lifecycle

最后更新：2026-06-09

阶段 25 承接阶段 24。阶段 24 已经让运营人员能从 approval 列表点进只读详情页，看清 approval、async run 和最终 platform result 的上下文。阶段 25 补齐 approval 的基础生命周期：pending approval 不应该只能 approved 或 rejected，也需要能被撤销或失效。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

operation approval lifecycle，是指一条 operation approval record 从申请创建到最终结束的状态流转。

对应英文术语：

- operation approval lifecycle
- cancelled approval
- expired approval
- terminal approval status
- stale approval

## 为什么要补取消和过期

阶段 18 到阶段 24 已经支持：

```text
pending -> approved
pending -> rejected
```

但在真实运营流程里，pending approval 还会遇到两类常见情况：

1. 申请人发现不需要执行了，主动撤回申请。
2. 申请长时间无人处理，超过 review window 后失效。

如果系统没有 `cancelled` 和 `expired`，pending approval 会永久悬挂，报表、console 和后续 retry 执行都会变得含糊。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/platform_operation_approval_report.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/demo.py
labs/fintech-platform/test_platform_operation_approval.py
labs/fintech-platform/test_platform_operation_approval_report.py
labs/fintech-platform/test_platform_api_app.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/38-stage-25-operation-approval-lifecycle.md
```

## 新增状态

operation approval record 现在支持：

```text
pending
approved
rejected
cancelled
expired
```

其中：

- `cancelled`：申请被撤销，不再允许 approve / reject / expire。
- `expired`：申请已失效，不再允许 approve / reject / cancel。

`cancelled` 和 `expired` 都是终态，只允许从 `pending` 流转。

## 新增 store 方法

`SQLiteOperationApprovalStore` 新增：

```text
cancel_pending()
expire_pending()
```

两者都会复用现有字段：

```text
approved_by       -> 记录处理人
approval_reason   -> 记录取消或过期原因
decision_reason   -> cancelled / expired
decided_at        -> 处理时间
```

这样避免为第一版生命周期单独扩展新列，也保持现有 CSV、HTML 和详情页兼容。

## 新增 HTTP endpoints

FastAPI 新增：

```text
PATCH /platform/operation-approvals/{approval_id}/cancel
PATCH /platform/operation-approvals/{approval_id}/expire
```

请求体沿用：

```text
decided_by
decision_reason
decided_at
```

成功和失败都会写入：

```text
UPDATE_PLATFORM_OPERATION_APPROVALS
```

对应 access audit 的 reason 分别是：

```text
cancelled
expired
```

如果对 `cancelled` 或 `expired` approval 再执行 approve / reject，会返回现有 invalid transition 错误。

## Report 和 Console

`OperationApprovalReportSummary` 新增：

```text
cancelled_count
expired_count
```

`FinTech Platform Console` 的 summary 也新增：

```text
Cancelled approvals
Expired approvals
```

approval records 表格继续展示所有终态记录；pending 表格仍只展示 `pending`。

## Demo

demo 的 `Pending operation approval flow` 现在展示三种终态样例：

```text
pending -> approved
pending -> cancelled
pending -> expired
```

其中 approved 仍然保持原有 retry approval request `pending -> approved -> async accepted` 主路径；cancelled 和 expired 是独立创建的样例 approval，不会执行 retry。

## 第一版不做

- 不做自动定时过期任务。
- 不做真实 SLA、提醒、通知或升级路径。
- 不在 console 增加 approve / reject / cancel / expire 表单。
- 不新增真实 IAM、登录、session 或角色系统。
- 不把 `approved_by` 字段重命名为更通用的 `decided_by`，避免本阶段扩大 schema 变更。

## 验证记录

截至 2026-06-09，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval_report.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

结果：

```text
test_platform_operation_approval.py: 14 passed
test_platform_operation_approval_report.py: 3 passed
test_platform_api_app.py: 33 passed
demo 可运行，并展示 approved / cancelled / expired approval lifecycle
```

## 后续候选方向

阶段 25 完成后，可以选择：

1. 在保持 maker-checker 边界的前提下，设计 console approve / reject 表单。
2. 给 approval detail view 增加更明确的 lifecycle timeline。
3. 为 operation approval 查询增加总数统计或 cursor pagination。
4. 补 async run detail 和 platform result detail，让 approval detail 能继续跳转。
