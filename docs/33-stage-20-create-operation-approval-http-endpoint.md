# 阶段 20：Create Operation Approval HTTP Endpoint

最后更新：2026-06-08

阶段 20 承接阶段 19。阶段 19 已经提供 operation approval 的 HTTP 查询和 approve/reject 流转，但 pending approval 仍主要由本地代码或 demo 直接写入 store。阶段 20 的目标是补上最小创建入口：通过 HTTP 创建一条 pending operation approval record，但不立即执行 retry。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

创建操作审批 HTTP endpoint，是把“申请一个待审批操作”的动作暴露为 API 边界。

对应英文术语：

- create operation approval endpoint
- pending operation approval
- approval request
- maker-checker workflow
- approval access audit

## 为什么需要创建 endpoint

阶段 18 和阶段 19 已经有了审批记录和状态流转：

```text
pending -> approved
pending -> rejected
```

但如果 pending approval 只能由 Python 代码直接写入，外部系统或未来 console 就不能通过统一 API 发起审批申请。创建 endpoint 的价值是把“申请审批”和“审批决策”分开：

```text
POST create pending approval
-> GET query pending approval
-> PATCH approve / reject
-> access audit granted / denied
```

这一步很关键，因为高影响操作不应该在点击 retry 时直接执行。更稳妥的方向是先形成一条待审批记录，审批通过后再由后续流程决定是否执行 retry。

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
docs/33-stage-20-create-operation-approval-http-endpoint.md
```

## 新增 API

第一版新增：

```text
POST /platform/operation-approvals
```

请求体：

```json
{
  "approval_id": "approval_pending_retry_001",
  "operation_type": "retry_failed_async_run",
  "operation_id": "async_run_001",
  "target": "fintech_platform_async_run:async_run_001",
  "requested_by": "ops_user_001",
  "request_reason": "Retry after transient processing failure",
  "requested_at": "2026-06-08T09:30:00Z"
}
```

创建后的记录会保存为：

```text
status=pending
approved_by=None
approval_reason=None
decision_reason=pending approval
decided_at=None
```

如果 `approval_id` 已存在，接口返回 `409 Conflict`，不会覆盖原记录。

## 访问审计

新增教学版权限：

```text
create_platform_operation_approvals
```

创建成功写入 granted access audit。重复 `approval_id` 或其他创建失败会写入 denied access audit。

阶段 19 已有权限继续保留：

```text
view_platform_operation_approvals
update_platform_operation_approvals
```

因此阶段 20 后，operation approval 的最小 HTTP 生命周期已经变成：

```text
POST create pending approval
GET query approval
PATCH approve / reject approval
```

## Demo

`demo.py` 的 `Pending operation approval flow` 现在通过 HTTP 演示完整的创建、查询和 approve：

```text
POST  /platform/operation-approvals
GET   /platform/operation-approvals/{approval_id}
PATCH /platform/operation-approvals/{approval_id}/approve
```

输出示例：

```text
Pending operation approval flow
- before=pending after=approved requested_by=... approved_by=...
```

## 第一版不做

- 不修改 failed async run retry API 的执行语义。
- 不让 approve endpoint 自动执行 retry。
- 不新增前端审批页面。
- 不做真实 IAM、角色授权、分页、排序或 SLA。
- 不做多级审批、撤销、过期、认领或锁定。
- 不把 pending approval 和 async worker 绑定成生产级工作流。

第一版只补上“创建 pending approval”的 HTTP 边界，继续保持审批记录和 retry 执行动作分离。

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
test_platform_api_app.py: 29 passed
demo 可运行，并通过 HTTP 创建、查询和 approve pending approval
labs/fintech-platform: 122 passed
labs: 367 passed
```

完整 `labs` 测试需要写入各实验目录的 `.test-data` SQLite/CSV 文件；本机在沙箱内写入这些目录会被拒绝，因此完整测试使用了提升权限运行。

## 后续候选方向

阶段 20 完成后，可以选择：

1. 把 retry API 改成先创建 pending approval，审批通过后再执行 retry。
2. 把 operation approval HTTP endpoint 接入 console 的只读筛选。
3. 给 operation approval 列表增加分页和排序。
4. 增加 approval 与 async run 的只读关联视图。
