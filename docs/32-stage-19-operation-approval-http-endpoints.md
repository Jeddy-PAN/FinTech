# 阶段 19：Operation Approval HTTP Endpoints

最后更新：2026-06-08

阶段 19 承接阶段 18。阶段 18 已经让 `OperationApprovalRecord` 支持 `pending / approved / rejected` 状态流转，但这些能力主要停留在 store、report、console summary 和 demo 的本地调用里。阶段 19 的目标是给 pending approval 增加最小 HTTP 查询和审批入口，让审批记录可以通过 API 被查看和流转。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

操作审批 HTTP endpoint，是把 operation approval record 的查询和状态流转暴露为 API 边界。

对应英文术语：

- operation approval endpoint
- approval query API
- approve pending approval
- reject pending approval
- approval access audit

## 为什么需要 HTTP endpoint

阶段 18 已经有 store 层状态机：

```text
pending -> approved
pending -> rejected
```

但如果只能在 Python 代码里调用 `approve_pending()`，运营人员、后台服务或未来 console 都无法通过统一 API 操作审批记录。HTTP endpoint 的价值是把审批流转放到平台边界上：

```text
approval record in SQLite
-> HTTP query
-> HTTP approve / reject
-> access audit granted / denied
```

这样后续才能继续做审批列表、只读筛选、审批页面或把 retry API 改成“先 pending 审批，审批通过后再执行 retry”。

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
docs/32-stage-19-operation-approval-http-endpoints.md
```

## 新增 API

第一版新增：

```text
GET   /platform/operation-approvals
GET   /platform/operation-approvals/{approval_id}
PATCH /platform/operation-approvals/{approval_id}/approve
PATCH /platform/operation-approvals/{approval_id}/reject
```

列表接口支持筛选：

```text
status
operation_type
operation_id
```

approve / reject 请求体：

```json
{
  "decided_by": "ops_manager_001",
  "decision_reason": "Approved pending retry after review",
  "decided_at": "2026-06-08T09:30:00Z"
}
```

## 访问审计

新增教学版权限：

```text
view_platform_operation_approvals
update_platform_operation_approvals
```

查询成功写入 granted access audit。查询不存在的 approval、非法 status、重复 approve/reject 等失败会写入 denied access audit。

错误状态映射：

```text
unknown approval record -> 404
cannot approve/reject terminal record -> 409
other validation error -> 400
```

## Demo

`demo.py` 的 `Pending operation approval flow` 现在通过 HTTP 演示：

```text
GET /platform/operation-approvals/{approval_id}
PATCH /platform/operation-approvals/{approval_id}/approve
```

输出示例：

```text
Pending operation approval flow
- before=pending after=approved requested_by=... approved_by=...
```

## 第一版不做

- 不新增创建 pending approval 的 HTTP endpoint。
- 不把 retry API 改成先创建 pending approval。
- 不让 approve endpoint 自动执行 retry。
- 不新增前端审批页面。
- 不做分页、排序参数、权限角色和真实 IAM。
- 不做多级审批、撤销、过期、认领、锁定或 SLA。

第一版只把已有 approval record 的查询和终态流转放到 API 边界上。

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_api_app.py: 27 passed
demo 可运行，并通过 HTTP 输出 Pending operation approval flow
labs/fintech-platform: 120 passed
labs: 365 passed
```

## 后续候选方向

阶段 19 完成后，可以选择：

1. 新增创建 pending approval 的 HTTP endpoint。
2. 把 retry API 改成先创建 pending approval，审批通过后再执行 retry。
3. 把 operation approval HTTP endpoint 接入 console 的只读筛选。
4. 给 console 增加只读筛选和分页。
