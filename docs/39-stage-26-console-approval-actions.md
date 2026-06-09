# 阶段 26：Console Approval Actions

最后更新：2026-06-09

阶段 26 承接阶段 25。阶段 25 已经补齐 operation approval 的 `cancelled` 和 `expired` 生命周期状态。阶段 26 开始把 pending approval 的操作入口放进 `FinTech Platform Console`，但只做 approve / reject 两个动作，不做 cancel / expire 按钮，也不引入真实 IAM。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

console approval actions，是指运营人员在控制台页面上直接对 pending operation approval 执行 approve 或 reject。

对应英文术语：

- console approval actions
- approval form adapter
- maker-checker boundary
- decision confirmation
- form endpoint

## 为什么现在可以做表单

阶段 22 到阶段 24 已经让 console 能看到 pending approval，并能点进只读详情页查看上下文。阶段 25 又补齐了 cancelled / expired 终态，避免 pending approval 永久悬挂。

因此阶段 26 可以谨慎加入 approve / reject 表单。这里的重点不是“加两个按钮”，而是保持以下边界：

1. 表单只是浏览器适配层，不绕过已有 HTTP approve / reject 逻辑。
2. approve retry approval 时，仍然由现有逻辑执行 `failed -> accepted`。
3. reject approval 时，不执行 retry。
4. 成功和失败都继续写入 `UPDATE_PLATFORM_OPERATION_APPROVALS` access audit。

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
docs/39-stage-26-console-approval-actions.md
```

## 新增 form endpoints

FastAPI 新增两个浏览器表单 endpoint：

```text
POST /platform/operation-approvals/{approval_id}/approve-form
POST /platform/operation-approvals/{approval_id}/reject-form
```

表单字段：

```text
decided_by
decision_reason
decided_at
confirmation
```

confirmation 要求：

```text
approve_operation_approval
reject_operation_approval
```

表单 endpoint 成功后通过 `303 See Other` 回到 console：

```text
/platform/view?approval_status=approved
/platform/view?approval_status=rejected
```

失败时回到：

```text
/platform/view?approval_error=...
```

## Console 变化

`Pending Operation Approvals` 表格新增 `action` 列。每条 pending approval 会展示：

```text
Approve form
Reject form
```

两个表单都要求填写处理人、处理原因、处理时间和 confirmation。

页面顶部新增 approval 操作反馈：

```text
Operation approval approved.
Operation approval rejected.
Approval update failed: ...
```

## 复用既有边界

阶段 26 把 JSON PATCH endpoint 的核心逻辑抽成内部 helper：

```text
_approve_operation_approval()
_reject_operation_approval()
```

JSON API 和 HTML form 都调用这两个 helper，因此不会出现“API 有审计，表单没审计”或“API 会执行 retry，表单不执行”的分叉。

## 第一版不做

- 不在 console 增加 cancel / expire 按钮。
- 不做真实登录、session、CSRF token、IAM 或角色权限。
- 不做前端框架、模板系统或独立前端项目。
- 不做批量审批、认领、锁定、通知、SLA 或升级路径。
- 不修改 JSON approve / reject endpoint 的请求合同。

## 验证记录

截至 2026-06-09，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

结果：

```text
test_platform_api_app.py: 36 passed
labs/fintech-platform: 134 passed
labs: 379 passed
demo 可运行
```

## 后续候选方向

阶段 26 完成后，可以选择：

1. 给 approval detail view 增加 lifecycle timeline。
2. 补 async run detail 和 platform result detail，让 approval detail 能继续跳转。
3. 为 operation approval 查询增加总数统计或 cursor pagination。
4. 如果继续增强 console，再考虑 cancel / expire 表单，但要先明确权限和误操作边界。
