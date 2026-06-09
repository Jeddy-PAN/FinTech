# 阶段 24：Operation Approval Detail View

最后更新：2026-06-09

阶段 24 承接阶段 23。阶段 23 已经让 operation approval 列表支持分页和排序，但运营人员从列表看到一条 approval 后，仍然缺少一个只读详情页来查看它和 async run、最终 platform result 之间的上下文关系。阶段 24 的目标是补齐这个只读详情视图。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

operation approval 详情视图，是指围绕一条 approval record 展示它的完整字段、关联 async run 状态，以及在 async run 完成时展示最终 platform result 摘要。

对应英文术语：

- operation approval detail view
- read-only detail page
- linked async run context
- platform result summary
- operational drill-down

## 为什么先做只读详情

阶段 22 和阶段 23 已经让 console 能看到 pending approval、列表记录、分页和排序。但审批类操作不能只依赖列表行里的几个字段。真实运营人员在做判断前通常需要先回答：

1. 这条 approval 是谁申请的，理由是什么？
2. 它对应哪个 async run？
3. async run 当前是什么状态，失败原因或处理次数是什么？
4. 如果 async run 已完成，最终业务结果是什么？

阶段 24 仍然不做 approve / reject 按钮，而是先把“看清上下文”的只读能力补齐。

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
docs/37-stage-24-operation-approval-detail-view.md
```

## 新增页面

新增只读 HTML 页面：

```text
GET /platform/operation-approvals/{approval_id}/view
```

页面包含三块：

### Approval Record

展示 approval record 全字段：

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

### Associated Async Run

如果 `operation_id` 能匹配 async run id，展示：

```text
run_id
status
attempt_count
max_attempts
last_error
created_at
updated_at
started_at
completed_at
```

如果找不到 async run，则显示空状态。

### Platform Result Summary

如果 async run 已经是 `completed`，并且能找到最终 platform result，展示：

```text
run_id
customer_id
status
payment_order_id
payment_order_status
risk_status
ledger_transaction_id
audit_event_count
created_at
```

如果 async run 还没有完成，或没有最终 platform result，则显示空状态。

## Console 链接

`FinTech Platform Console` 的两个只读区块现在会把 `approval_id` 渲染成详情页链接：

```text
Pending Operation Approvals
Approval Records
```

链接目标：

```text
/platform/operation-approvals/{approval_id}/view
```

字段值仍然会做 HTML 转义；链接只由服务端生成，不接收前端传入的 HTML。

## 访问审计

详情页沿用：

```text
VIEW_PLATFORM_OPERATION_APPROVALS
```

成功访问记录 granted access audit，reason 为：

```text
view detail
```

找不到 approval record 时记录 denied access audit，并返回现有 operation approval 错误响应。

## 第一版不做

- 不在详情页增加 approve / reject 按钮。
- 不新增单独前端项目或模板系统。
- 不做真实 IAM、角色权限、通知、认领、锁定、SLA 或过期策略。
- 不做可编辑字段。
- 不做跨数据库事务。

第一版只做只读 drill-down，让运营人员能从 approval 看到 async run 和业务结果上下文。

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
test_platform_api_app.py: 31 passed
labs/fintech-platform: 126 passed
labs: 371 passed
demo 可运行，并保持 retry approval request pending -> approved -> async accepted
```

## 后续候选方向

阶段 24 完成后，可以选择：

1. 为 pending approval 增加过期或取消状态。
2. 在保持 maker-checker 边界的前提下，设计 console approve / reject 的表单和权限约束。
3. 为 operation approval 查询增加更明确的总数统计或 cursor pagination。
4. 把 detail view 中的 async run 和 platform result 链接到更完整的只读详情页。
