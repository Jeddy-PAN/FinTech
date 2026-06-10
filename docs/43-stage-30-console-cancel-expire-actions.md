# 阶段 30：Console Cancel / Expire Approval Actions

最后更新：2026-06-10

阶段 30 承接阶段 29。阶段 29 已经让 operation approval 列表查询返回更明确的 pagination metadata。阶段 30 回到运营控制台，把阶段 25 已有的 `cancelled` / `expired` 生命周期动作接入 `Pending Operation Approvals` 表格，让运营人员可以在 console 中把 pending approval 取消或标记过期。

本阶段仍然只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起，避免继续拆出细碎文档。

## 中文定义

approval cancellation，是指在审批仍处于 pending 时，由操作人主动撤销这条审批申请。

approval expiration，是指在审批仍处于 pending 时，由系统或运营人员把这条审批标记为已过期。

对应英文术语：

- approval cancellation
- approval expiration
- terminal state
- operation approval lifecycle
- console action

## 为什么需要 cancel / expire 表单

阶段 25 已经在 store 和 JSON API 中支持：

```text
pending -> cancelled
pending -> expired
```

但阶段 26 的 console 只提供 approve / reject 表单。这样运营人员可以在页面上通过或拒绝审批，却不能从同一页面处理“申请人撤回”或“审批窗口过期”。

阶段 30 补齐这个缺口：

1. `cancel` 用于表达审批申请不再需要继续处理。
2. `expire` 用于表达审批申请超过处理窗口或由系统流程终止。
3. 两者都是终态，流转后不能再 approve / reject，也不会执行 retry。

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
docs/43-stage-30-console-cancel-expire-actions.md
```

## Console 变化

`FinTech Platform Console` 的 `Pending Operation Approvals` 表格现在显示四类表单：

```text
Approve
Reject
Cancel
Expire
```

新增表单 endpoint：

```text
POST /platform/operation-approvals/{approval_id}/cancel-form
POST /platform/operation-approvals/{approval_id}/expire-form
```

两个表单都要求：

```text
decided_by
decision_reason
decided_at
confirmation
```

确认文本分别是：

```text
cancel_operation_approval
expire_operation_approval
```

提交成功后回到 console：

```text
/platform/view?approval_status=cancelled
/platform/view?approval_status=expired
```

页面会显示：

```text
Operation approval cancelled.
Operation approval expired.
```

提交失败时仍回到：

```text
/platform/view?approval_error=...
```

并显示 `Approval update failed: ...`。

## 代码边界

阶段 30 把 cancel / expire 的 JSON API 与 form endpoint 统一到内部 helper：

```text
_cancel_operation_approval(...)
_expire_operation_approval(...)
```

这样 JSON endpoint 和 console form endpoint 复用同一套：

- pending 状态校验。
- store lifecycle transition。
- granted / denied access audit。
- HTTP 错误映射。

## 审计行为

成功 cancel / expire 会写入：

```text
permission = update_platform_operation_approvals
outcome = granted
reason = cancelled / expired
```

失败时会写入：

```text
permission = update_platform_operation_approvals
outcome = denied
reason = <status> OperationApprovalError: <message>
```

这和 approve / reject 的操作审计边界保持一致。

## 第一版不做

- 不新增真实 IAM、登录、session 或 CSRF。
- 不新增数据库表。
- 不新增批量 cancel / expire。
- 不新增定时自动过期任务。
- 不新增通知、SLA、认领或锁定。
- 不改变 operation approval 的业务生命周期状态。

## 验证记录

截至 2026-06-10，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

结果：

```text
test_platform_api_app.py: 42 passed
labs/fintech-platform: 140 passed
labs: 385 passed
demo.py: 可运行
```

说明：

- 普通沙箱执行时，测试无法在 `labs/fintech-platform/.test-data` 下打开 SQLite 测试数据库，报 `sqlite3.OperationalError: unable to open database file`。
- 使用授权的非沙箱测试执行后，API app 测试通过。

## 后续候选方向

阶段 30 完成后，可以选择：

1. 为 operations console 增加更完整的筛选入口，而不是只显示最新 5 条。
2. 给 platform result detail 增加更细的 reconciliation context，但仍保持只读。
3. 为 operation approval console 动作增加更明确的风险提示或只读详情页返回入口。
4. 如果列表数据继续增长，再讨论 cursor pagination。
