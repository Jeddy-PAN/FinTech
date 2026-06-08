# 阶段 14：独立 Operation Approval Record

最后更新：2026-06-08

阶段 14 承接阶段 12 和阶段 13。阶段 12 已经给 failed async run retry 加上 maker-checker、二人审批和职责分离；阶段 13 已经能从 access audit 里统计 retry granted / denied 次数。

当前不足是：审批信息仍然主要塞在 access audit 的 `reason` 字段里。这样可以教学演示，但工程边界不够清晰。阶段 14 的目标是把高影响操作审批拆成独立 `operation approval record`，让 access audit 和 approval record 各自表达不同事实。

本阶段只新增一篇文档，合并设计、计划、实现进度和验证记录，避免继续拆分细碎文档。

## 中文定义

操作审批记录，是对高影响操作审批过程的结构化记录。

对应英文术语：

- operation approval record
- maker-checker
- four-eyes principle
- approval workflow
- separation of duties

在本仓库里，阶段 14 只服务一个操作：

```text
retry failed async payment run
```

## 为什么需要独立 approval record

access audit 记录的是：

```text
谁尝试访问或执行什么动作，结果是 granted 还是 denied。
```

operation approval record 记录的是：

```text
谁申请高影响操作，谁审批，审批理由是什么，审批结论是什么，审批发生在什么时候。
```

这两个事实相关，但不是同一个对象。把它们拆开后，后续才能更清楚地回答：

1. 某次 retry 是谁申请的。
2. 谁批准了这次 retry。
3. 审批人是否不同于申请人。
4. 审批通过后是否真的执行了 retry。
5. 被拒绝的 retry 是输入错误、审批错误，还是状态不允许。

## 第一版范围

新增代码：

```text
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/test_platform_operation_approval.py
```

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
docs/27-stage-14-operation-approval-record.md
```

## 数据模型

第一版使用 SQLite 持久化，不引入复杂审批流。

建议对象：

```text
OperationApprovalRecord
SQLiteOperationApprovalStore
OperationApprovalError
```

字段：

```text
approval_id
operation_type
operation_id
target
requested_by
request_reason
approved_by
approval_reason
status
decision_reason
requested_at
decided_at
```

第一版状态：

```text
approved
rejected
```

说明：

- `operation_type` 第一版固定为 `retry_platform_async_run`。
- `operation_id` 第一版使用 async `run_id`。
- `target` 使用现有 API target，例如 `fintech_platform_api_async_payment_runs/run_retry_http`。
- `status=approved` 表示审批输入通过，并且 retry 操作成功执行。
- `status=rejected` 表示审批或 retry 操作失败，例如 self-approval、confirmation 错误或 async run 状态不允许 retry。

## 与 access audit 的边界

retry API 仍然继续写 access audit：

```text
audit_access.granted / audit_access.denied
permission=retry_platform_async_run
```

新增 approval record 用来保存结构化审批事实：

```text
operation_type=retry_platform_async_run
requested_by=ops_user_001
approved_by=ops_manager_001
status=approved / rejected
decision_reason=...
```

两者不互相替代：

1. access audit 用于访问审计、异常检测和阶段 13 operations report。
2. approval record 用于审批复核、职责分离和后续 operation approval report。

## 第一版不做

- 不做 pending approval。
- 不做多级审批。
- 不做审批撤销。
- 不做真实 IAM。
- 不做新的前端页面。
- 不修改 existing access audit schema。
- 不修改 async run schema。
- 不把 approval 接入通用工作流引擎。

## 实现计划

### 任务 1：operation approval store

新增测试：

```text
labs/fintech-platform/test_platform_operation_approval.py
```

测试目标：

1. 能保存并读取 `approved` approval record。
2. 能保存并查询 `rejected` approval record。
3. 拒绝 self-approval。
4. 拒绝 unknown status。

新增实现：

```text
labs/fintech-platform/platform_operation_approval.py
```

### 任务 2：retry API 接入 approval record

更新：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
```

测试目标：

1. JSON retry 成功时写入 `approved` approval record。
2. JSON retry self-approval 失败时写入 `rejected` approval record。
3. console retry form 成功时也写入 `approved` approval record。

### 任务 3：demo 接入

更新：

```text
labs/fintech-platform/demo.py
```

demo 需要展示：

```text
Operation approval records
- retry_platform_async_run run_id=... status=approved/rejected requested_by=... approved_by=...
```

### 任务 4：文档和入口更新

更新：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/27-stage-14-operation-approval-record.md
```

### 任务 5：验证

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

## 实现进度

第一版已完成。

新增代码：

```text
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/test_platform_operation_approval.py
```

已接入：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
labs/fintech-platform/demo.py
```

当前行为：

1. JSON retry API 成功时写入 `status=approved` operation approval record。
2. JSON retry API self-approval 失败时写入 `status=rejected` operation approval record。
3. console retry form 成功时写入 `status=approved` operation approval record。
4. retry access audit 仍然保留 granted / denied 访问审计事件。

demo 会写入并读取：

```text
labs/fintech-platform/.test-data/demo_platform_operation_approvals.db
```

并输出：

```text
Operation approval records
- retry_platform_async_run run_id=... status=approved requested_by=... approved_by=...
```

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_operation_approval.py: 4 passed
test_platform_api_app.py: 23 passed
demo 可运行，并输出 Operation approval records
labs/fintech-platform: 103 passed
labs: 348 passed
```

## 后续候选方向

阶段 14 完成后，可以选择：

1. 做 operation approval report。
2. 把 operations report 接入只读 console。
3. 让 approval record 支持 pending / approved / rejected 状态流转。
4. 引入更深入的 ledger reconciliation。
