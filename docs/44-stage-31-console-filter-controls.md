# 阶段 31：Console Filter Controls

最后更新：2026-06-10

阶段 31 承接阶段 30。阶段 30 已经把 pending operation approval 的 cancel / expire 表单接入 console。阶段 31 不继续新增审批动作，而是补一个运营页面最基础的筛选入口，让 `FinTech Platform Console` 不再只能展示最新 5 条全量数据。

本阶段仍然只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

console filter controls，是指运营控制台页面上的筛选控件。它让使用者按状态缩小页面展示范围，而不是每次都看全量最新数据。

对应英文术语：

- console filter controls
- status filter
- filtered view
- operations console

## 为什么先做筛选入口

阶段 23 已经让 operation approval JSON 查询支持分页和排序，阶段 29 又补了 pagination metadata。但 console 页面仍然只是固定展示最新记录。

当 payment run、async run 和 operation approval 同时变多时，运营人员通常先问：

1. 只看某类 payment status 可以吗？
2. 只看 failed async runs 可以吗？
3. 只看 pending / approved / rejected approval records 可以吗？

阶段 31 先回答这三个问题。

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
docs/44-stage-31-console-filter-controls.md
```

## Console 变化

`GET /platform/view` 现在支持三个查询参数：

```text
payment_status
async_status
operation_approval_status
```

页面新增一个原生 HTML GET 表单：

```text
Payment status
Async status
Approval status
Apply Filters
Clear Filters
```

筛选会影响：

- `Recent Payment Runs`
- `Recent Async Runs`
- `Failed Async Runs`
- `Operations Report Summary`
- `Operations Run Rows`
- `Ledger Reconciliation Findings`
- `Operation Approval Summary`
- `Pending Operation Approvals`
- `Approval Records`

## 合法状态

`payment_status` 来自平台业务状态：

```text
completed
kyc_review_required
kyc_blocked
risk_review_required
risk_review_rejected
risk_blocked
```

`async_status` 来自 async run 状态：

```text
accepted
processing
completed
failed
```

`operation_approval_status` 来自 operation approval 状态：

```text
pending
approved
rejected
cancelled
expired
```

## 错误处理

如果传入未知筛选值，console 不返回 400，而是在页面顶部显示 filter error，并忽略无效筛选值。

这样处理的原因是：当前 console 是教学版运营页面，目标是让页面保持可观察，而不是因为一个错误 query string 阻断整个页面。

## 第一版不做

- 不新增 JSON API 参数。
- 不新增数据库表。
- 不新增 cursor pagination。
- 不新增复杂搜索、日期范围、actor 筛选或多选筛选。
- 不新增真实 IAM、登录、session 或 CSRF。
- 不引入前端框架。

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
test_platform_api_app.py: 44 passed
labs/fintech-platform: 142 passed
labs: 387 passed
demo.py: 可运行
```

说明：

- 普通沙箱执行时，测试无法在 `labs/fintech-platform/.test-data` 下打开 SQLite 测试数据库，报 `sqlite3.OperationalError: unable to open database file`。
- 使用授权的非沙箱测试执行后，API app 测试通过。

## 后续候选方向

阶段 31 完成后，可以选择：

1. 给 platform result detail 增加更细的 reconciliation context，但仍保持只读。
2. 为 operation approval console 动作增加更明确的风险提示或只读详情页返回入口。
3. 给 console 增加日期范围或 actor 筛选。
4. 如果列表数据继续增长，再讨论 cursor pagination。
