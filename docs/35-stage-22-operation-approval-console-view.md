# 阶段 22：Operation Approval Console View

最后更新：2026-06-09

阶段 22 承接阶段 21。阶段 21 已经把 failed async run retry 改成“先创建 pending operation approval，审批通过后才执行 retry”。阶段 22 的目标不是继续增加操作按钮，而是让运营人员可以在现有 `FinTech Platform Console` 里只读看到待处理 approval，并同时看到它关联的 async run 状态。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

待审批操作视图，是指把还没有被 approve / reject 的 operation approval record 放到运营控制台中，作为一个只读工作队列。

对应英文术语：

- pending operation approval
- read-only approval queue
- operational console
- async status association
- maker-checker visibility

## 为什么需要这个视图

阶段 21 后，retry 申请不会立即执行：

```text
failed async run
-> retry approval request
-> operation approval record pending
-> approve approval
-> failed -> accepted
```

如果 console 只显示 failed async run 和完整 approval records，运营人员仍然需要在两块信息之间人工拼接：哪条 approval 还在 pending、它对应哪个 async run、这个 run 当前还是不是 failed。

阶段 22 增加的 `Pending Operation Approvals` 区块用于回答这个问题：

```text
哪些 retry approval 还在等审批？
它们对应的 async run 当前是什么状态？
谁申请的，申请理由是什么？
```

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
docs/35-stage-22-operation-approval-console-view.md
```

## Console 新增内容

`FinTech Platform Console` 新增一个只读区块：

```text
Pending Operation Approvals
```

表格字段：

| 字段 | 含义 |
| --- | --- |
| `approval_id` | operation approval record 的唯一 ID |
| `operation_type` | 操作类型，例如 `retry_platform_async_run` |
| `operation_id` | 被申请操作的目标 ID；retry 场景下是 async `run_id` |
| `async_status` | 如果 `operation_id` 能匹配到 async run，则显示当前 async run status |
| `requested_by` | 申请人 |
| `request_reason` | 申请理由 |
| `requested_at` | 申请时间 |

页面 summary 也新增：

```text
Pending approvals
```

它来自 `OperationApprovalReportSummary.pending_count`，用于在页面顶部快速看到当前待审批数量。

## 实现方式

本阶段没有新增数据库表，也没有新增 HTTP endpoint。

console 渲染时已有两类数据：

```text
operation_approval_records
async_runs
```

阶段 22 只在展示层增加一个关联：

```text
async_status_by_run_id = {run.run_id: run.status for run in async_runs}
```

然后筛选：

```text
record.status == pending
```

如果 pending record 的 `operation_id` 能匹配 async run id，就显示 `async_status`；匹配不到时留空。这是只读观察关系，不改变 approval 或 async run 的状态。

## 第一版不做

- 不在 console 增加 approve / reject 按钮。
- 不在 console 增加分页、排序或高级筛选。
- 不新增单独 approval 页面。
- 不新增真实 IAM、角色权限、通知、认领、锁定、SLA 或过期策略。
- 不改变阶段 21 的 retry 执行语义。

第一版只让 pending approval 变得可见，并把它和 async run 状态放在同一行里。

## 验证记录

截至 2026-06-09，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_api_app.py: 29 passed
demo 可运行，并保持 retry approval request pending -> approved -> async accepted
labs/fintech-platform: 122 passed
labs: 367 passed
```

## 后续候选方向

阶段 22 完成后，可以选择：

1. 给 operation approval 列表增加分页和排序。
2. 增加 approval 与 async run 的只读详情视图。
3. 为 pending approval 增加过期或取消状态。
4. 在保持 maker-checker 边界的前提下，设计 console approve / reject 的表单和权限约束。
