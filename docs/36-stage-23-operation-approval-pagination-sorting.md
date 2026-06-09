# 阶段 23：Operation Approval Pagination And Sorting

最后更新：2026-06-09

阶段 23 承接阶段 22。阶段 22 已经把 pending operation approval 接入 `FinTech Platform Console` 的只读视图，但 operation approval 列表仍然只支持基础筛选，console 也固定展示最近几条记录。阶段 23 的目标是补齐只读查询的分页和排序能力，为后续更大的审批记录量打基础。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

分页和排序，是指查询列表时不一次性返回全部记录，而是按明确顺序返回其中一段。

对应英文术语：

- pagination
- sorting
- limit
- offset
- sort_by
- sort_order

## 为什么先做分页排序

operation approval record 会随 retry request、approve 和 reject 持续增长。如果列表只能返回全部记录，后续会遇到三个问题：

1. 页面和 API 响应会越来越大。
2. 运营人员很难稳定复查“最新申请”或“某一页历史记录”。
3. 后续如果增加 approve / reject 表单，缺少稳定列表顺序会增加误操作风险。

因此阶段 23 仍然不新增操作按钮，而是先把只读列表查询能力做扎实。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_operation_approval.py
labs/fintech-platform/test_platform_api_app.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/36-stage-23-operation-approval-pagination-sorting.md
```

## API 查询参数

`GET /platform/operation-approvals` 继续支持原有筛选：

```text
status
operation_type
operation_id
```

阶段 23 新增：

| 参数 | 含义 |
| --- | --- |
| `limit` | 返回数量上限，允许 1 到 100；不传时不限制 |
| `offset` | 跳过前多少条，默认 0 |
| `sort_by` | 排序字段，默认 `requested_at` |
| `sort_order` | `asc` 或 `desc`，默认 `desc` |

支持的 `sort_by` 字段：

```text
approval_id
operation_type
operation_id
requested_by
status
requested_at
decided_at
```

响应仍保留 `records` 字段，并新增 `pagination` 元数据：

```json
{
  "records": [],
  "pagination": {
    "limit": 2,
    "offset": 1,
    "returned_count": 2,
    "sort_by": "requested_at",
    "sort_order": "desc"
  }
}
```

未知排序字段或排序方向会返回错误，并写入 denied access audit。

## Console 变化

`FinTech Platform Console` 的 approval 表格继续保持只读，不新增前端筛选控件。

内部排序逻辑改成统一 helper：

```text
sort_by=requested_at
sort_order=desc
limit=5
offset=0
```

受影响区块：

```text
Pending Operation Approvals
Approval Records
```

这样 console 默认显示最新记录，同时与 API 查询的排序语义保持一致。

## 第一版不做

- 不在 console 增加分页控件。
- 不在 console 增加 approve / reject 按钮。
- 不新增单独 approval 详情页。
- 不做 cursor pagination。
- 不做全文搜索或复杂组合筛选 UI。
- 不新增真实 IAM、角色权限、通知、认领、锁定、SLA 或过期策略。

第一版只补齐列表查询的稳定顺序和分页边界。

## 验证记录

截至 2026-06-09，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

结果：

```text
test_platform_operation_approval.py + test_platform_api_app.py: 41 passed
labs/fintech-platform: 125 passed
labs: 370 passed
demo 可运行，并保持 retry approval request pending -> approved -> async accepted
```

## 后续候选方向

阶段 23 完成后，可以选择：

1. 增加 approval 与 async run 的只读详情视图。
2. 为 pending approval 增加过期或取消状态。
3. 在保持 maker-checker 边界的前提下，设计 console approve / reject 的表单和权限约束。
4. 为 operation approval 查询增加更明确的总数统计或 cursor pagination。
