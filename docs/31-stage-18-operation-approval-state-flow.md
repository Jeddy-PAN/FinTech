# 阶段 18：Operation Approval State Flow

最后更新：2026-06-08

阶段 18 承接阶段 14、15 和 16。阶段 14 已经把 retry 审批拆成独立 `OperationApprovalRecord`；阶段 15 已经能导出 approval report；阶段 16 已把 approval summary 接入只读 console。当前不足是：approval record 只有 `approved` 和 `rejected` 两个终态，不能表达“已经申请，等待审批”的过程。

本阶段继续只新增一篇阶段文档，把目标、实现范围、验证记录和后续方向合并在一起。

## 中文定义

操作审批状态流转，是把一次高影响操作审批拆成“申请已创建、审批通过、审批拒绝”的状态变化过程。

对应英文术语：

- operation approval state flow
- pending approval
- approval transition
- maker-checker workflow
- approval lifecycle

## 为什么需要 pending 状态

阶段 14 的第一版 approval record 更像“审批结果记录”：

```text
retry request
-> approved / rejected record
```

真实工程里，审批通常还有一个中间状态：

```text
request approval
-> pending
-> approved / rejected
```

这个中间状态很重要，因为它能回答：

1. 哪些高影响操作已经被申请，但还没有审批。
2. 审批人是谁，是否和申请人不同。
3. 审批通过或拒绝发生在什么时候。
4. 报表和 console 能否区分 pending、approved 和 rejected。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/test_platform_operation_approval.py
labs/fintech-platform/platform_operation_approval_report.py
labs/fintech-platform/test_platform_operation_approval_report.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
labs/fintech-platform/demo.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/31-stage-18-operation-approval-state-flow.md
```

## 第一版状态

`OperationApprovalRecord.status` 现在支持：

```text
pending
approved
rejected
```

含义：

- `pending`：审批申请已经创建，但还没有最终决定。
- `approved`：审批通过。
- `rejected`：审批拒绝或 retry 审批校验失败。

pending 记录允许：

```text
approved_by = null
approval_reason = null
decided_at = null
```

终态记录仍要求：

```text
approved_by / approval_reason / decided_at
```

如果 `status=approved`，仍要求 `approved_by != requested_by`，保持 maker-checker 职责分离。

## Store 能力

`SQLiteOperationApprovalStore` 新增：

```text
approve_pending()
reject_pending()
```

它们只允许从 `pending` 流转到终态。如果记录已经是 `approved` 或 `rejected`，再次 approve / reject 会被拒绝。

store 初始化时会兼容阶段 14/15 的旧 schema：旧表中 `approved_by`、`approval_reason`、`decided_at` 曾经是 `NOT NULL`，并且 status 只允许 `approved/rejected`。阶段 18 会迁移为允许 pending 的 schema，并保留旧记录。

## Report 和 Console

`OperationApprovalReportSummary` 新增：

```text
pending_count
```

导出的 summary CSV、HTML report 和 `FinTech Platform Console` 的 `Operation Approval Summary` 都会显示这个指标。

## Demo

`demo.py` 新增一个最小样例：

```text
Pending operation approval flow
- approval_demo_pending_retry_001 status=approved requested_by=... approved_by=...
```

这个样例先保存 pending approval record，再调用 `approve_pending()` 流转为 approved，方便观察 approval lifecycle。

## 第一版不做

- 不把现有 retry API 改成异步审批后再执行。
- 不新增 pending approval HTTP endpoint。
- 不新增前端审批页面。
- 不做多级审批、撤销、过期、认领、锁定或 SLA。
- 不引入真实 IAM。
- 不修改 async run 状态机。

这个边界是有意的：阶段 18 先让 approval record 自身具备状态机能力，并让 report / console 能识别 pending；后续再决定是否把 retry API 改成“先创建 pending approval，再审批后执行 retry”。

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval_report.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_operation_approval.py: 9 passed
test_platform_operation_approval_report.py: 3 passed
test_platform_api_app.py: 24 passed
demo 可运行，并输出 Pending operation approval flow
labs/fintech-platform: 117 passed
labs: 362 passed
```

## 后续候选方向

阶段 18 完成后，可以选择：

1. 给 pending approval 增加最小 HTTP 查询和审批 endpoint。
2. 把 retry API 改成先创建 pending approval，审批通过后再执行 retry。
3. 给 console 增加只读筛选和分页。
4. 继续推进更真实的 ledger entry 持久化与查询边界。
