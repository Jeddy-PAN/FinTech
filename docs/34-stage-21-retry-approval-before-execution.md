# 阶段 21：Retry Approval Before Execution

最后更新：2026-06-09

阶段 21 承接阶段 20。阶段 20 已经支持通过 HTTP 创建 pending operation approval，但 failed async run retry endpoint 仍然是“提交 retry 请求后直接把 failed run 放回 accepted”。阶段 21 的目标是把 retry 执行从 retry request 中拆出来：先创建 pending approval，审批通过后才执行 `failed -> accepted`。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

先审批后执行，是指高影响操作的请求和执行必须分成两个动作。

对应英文术语：

- approval before execution
- maker-checker workflow
- retry approval request
- retry execution audit
- separation of duties

## 为什么要改 retry 边界

旧流程是：

```text
POST /platform/async-payment-runs/{run_id}/retry
-> validate actor / approver
-> failed -> accepted
-> write approved operation approval record
```

这能证明“retry 有审批信息”，但仍然把申请、审批、执行挤在一个请求里。更接近真实运营控制的流程应该是：

```text
POST retry request
-> create pending operation approval
-> PATCH approve approval
-> failed async run -> accepted
-> write retry execution access audit
```

这样 pending approval 可以被查询、拒绝、报表汇总，也能让 retry 执行和审批记录形成明确关联。

## 第一版范围

更新代码：

```text
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
docs/34-stage-21-retry-approval-before-execution.md
```

## 新流程

### 1. 请求 retry approval

```text
POST /platform/async-payment-runs/{run_id}/retry
```

请求体只需要操作申请信息：

```json
{
  "actor": "ops_user_001",
  "reason": "Retry after transient worker failure",
  "confirmation": "retry_failed_async_run"
}
```

接口只做三件事：

1. 校验 confirmation。
2. 校验 async run 存在且当前是 `failed`。
3. 创建一条 `pending` operation approval record。

响应变为 `202 Accepted` 风格：

```json
{
  "record": {
    "approval_id": "...",
    "operation_type": "retry_platform_async_run",
    "operation_id": "run_retry_http",
    "status": "pending"
  }
}
```

它不会把 async run 改成 `accepted`。

### 2. 审批通过并执行 retry

```text
PATCH /platform/operation-approvals/{approval_id}/approve
```

如果 approval record 的 `operation_type` 是 `retry_platform_async_run`，审批通过后会执行：

```text
failed async run -> accepted
```

响应会同时返回 approval record 和 async run：

```json
{
  "record": {
    "status": "approved"
  },
  "run": {
    "run_id": "run_retry_http",
    "status": "accepted"
  }
}
```

如果 async run 不存在，或者已经不是 `failed`，approve endpoint 会拒绝，不会把 approval record 改成 approved。

### 3. 拒绝 approval 不执行 retry

```text
PATCH /platform/operation-approvals/{approval_id}/reject
```

reject 只把 approval record 流转到 `rejected`，不会改变 async run 状态。

## 访问审计

阶段 21 后，审计语义更清楚：

```text
create_platform_operation_approvals
```

记录 retry approval request 是否成功创建。

```text
update_platform_operation_approvals
```

记录 approval approve/reject 是否成功。

```text
retry_platform_async_run
```

只在审批通过并真正执行 `failed -> accepted` 时记录 granted。

这避免把“申请 retry”误看成“retry 已执行”。

## Console 表单

`FinTech Platform Console` 的 failed async run 表单现在只提交：

```text
actor
reason
confirmation
```

提交成功后显示：

```text
Retry approval request created.
```

failed async run 仍保持 `failed`，直到对应 approval 被 approve。

## 第一版不做

- 不新增单独的审批页面。
- 不在 console 里直接 approve approval。
- 不做 approval 与 async run 的分页、排序或高级筛选。
- 不做真实 IAM、权限角色、通知、SLA、认领、锁定或过期。
- 不做跨 SQLite 数据库的强事务；当前仍是教学版边界。

第一版只把 retry 的申请、审批、执行三个动作拆清楚。

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
demo 可运行，并输出 retry approval request pending -> approved -> async accepted
labs/fintech-platform: 122 passed
labs: 367 passed
```

## 后续候选方向

阶段 21 完成后，可以选择：

1. 把 operation approval HTTP endpoint 接入 console 的只读筛选。
2. 给 operation approval 列表增加分页和排序。
3. 增加 approval 与 async run 的只读关联视图。
4. 为 pending approval 增加过期或取消状态。
