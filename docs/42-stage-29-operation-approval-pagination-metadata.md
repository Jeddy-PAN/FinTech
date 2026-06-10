# 阶段 29：Operation Approval Pagination Metadata

最后更新：2026-06-10

阶段 29 承接阶段 28。阶段 28 已经补齐 async run 和 platform result 的只读详情页。阶段 29 回到 operation approval 列表查询本身：在已有 `limit` / `offset` / `sort_by` / `sort_order` 基础上，补充更明确的分页元数据，让调用方知道当前筛选条件下一共有多少条记录，以及是否还能继续取下一页。

本阶段仍然只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

pagination metadata，是指列表查询返回业务数据之外，同时返回能解释分页状态的元数据。

对应英文术语：

- pagination metadata
- total count
- returned count
- next offset
- has next page
- offset pagination

## 为什么补 pagination metadata

阶段 23 已经让 operation approval 列表支持：

```text
limit
offset
sort_by
sort_order
```

但调用方之前只能知道本次返回了几条 `returned_count`，不知道当前筛选条件下一共有多少条，也不知道是否还有下一页。

这会影响两个工程判断：

1. 前端或运营脚本是否继续请求下一页。
2. 当前页面展示的是“全部记录”还是“某个筛选条件下的一部分记录”。

因此阶段 29 增加 `total_count`、`has_next_page` 和 `next_offset`。

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
docs/42-stage-29-operation-approval-pagination-metadata.md
```

## API 变化

`GET /platform/operation-approvals` 的 `pagination` 响应现在包含：

```text
limit
offset
returned_count
total_count
has_next_page
next_offset
sort_by
sort_order
```

含义：

- `returned_count`：本次响应实际返回的记录数。
- `total_count`：在当前 `status`、`operation_type`、`operation_id` 筛选条件下的总记录数。
- `has_next_page`：是否还能继续请求下一页。
- `next_offset`：如果存在下一页，下一次请求应使用的 offset；没有下一页时为 `null`。

示例：

```json
{
  "pagination": {
    "limit": 2,
    "offset": 0,
    "returned_count": 2,
    "total_count": 3,
    "has_next_page": true,
    "next_offset": 2,
    "sort_by": "requested_at",
    "sort_order": "desc"
  }
}
```

## Store 变化

`SQLiteOperationApprovalStore` 新增：

```text
count_records(status=None, operation_type=None, operation_id=None)
```

该方法复用和 `query_records()` 相同的筛选条件，不受 `limit`、`offset` 和排序影响。

## 第一版不做

- 不改成 cursor pagination。
- 不新增数据库表。
- 不新增 console 分页控件。
- 不改变已有 `limit` / `offset` / `sort_by` / `sort_order` 语义。
- 不新增真实权限、登录、session 或角色系统。

## 验证记录

截至 2026-06-10，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

结果：

```text
test_platform_operation_approval.py + test_platform_api_app.py: 53 passed
labs/fintech-platform: 137 passed
labs: 382 passed
demo.py: 可运行
```

## 后续候选方向

阶段 29 完成后，可以选择：

1. 如果继续增强 console，再考虑 cancel / expire 表单，但要先明确权限和误操作边界。
2. 为 operations console 增加更完整的筛选入口，而不是只显示最新 5 条。
3. 给 platform result detail 增加更细的 reconciliation context，但仍保持只读。
4. 如果列表数据继续增长，再讨论 cursor pagination。
