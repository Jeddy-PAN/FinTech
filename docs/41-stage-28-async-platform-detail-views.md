# 阶段 28：Async Run 与 Platform Result 只读详情页

最后更新：2026-06-10

阶段 28 承接阶段 27。阶段 27 已经在 operation approval detail view 中加入 lifecycle timeline，让一条 approval 的申请、决策和 retry execution 能按时间解释清楚。阶段 28 继续增强只读解释能力：让 approval detail 和 console 中出现的 async run、platform result 可以继续点进详情页。

本阶段仍然只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

drill-down detail view，是指从汇总页面或关联对象继续进入更细粒度详情页的只读查看能力。

对应英文术语：

- async run detail view
- platform result detail view
- drill-down navigation
- read-only operational context
- customer audit timeline

## 为什么做 detail drill-down

阶段 24 到阶段 27 已经让 operation approval detail view 能展示：

1. approval record。
2. lifecycle timeline。
3. associated async run 摘要。
4. platform result 摘要。

但这些摘要仍然不能完整回答：

1. 这个 async run 的 request payload 是什么？
2. worker 是否已处理，attempt 和 last error 如何变化？
3. 最终 platform result 的 KYC、payment、risk、ledger 字段是什么？
4. customer audit timeline 中发生了哪些业务事件？

所以阶段 28 不增加新操作，而是补两个只读详情页，并把现有页面里的 ID 链成可点击入口。

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
docs/41-stage-28-async-platform-detail-views.md
```

## 页面变化

新增 async run HTML 详情页：

```text
GET /platform/async-payment-runs/{run_id}/view
```

展示区块：

```text
Async Run
Request Payload
Platform Result Summary
```

新增 platform result HTML 详情页：

```text
GET /platform/payment-runs/{run_id}/view
```

展示区块：

```text
Platform Result
Associated Async Run
Customer Audit Timeline
```

已有页面新增链接：

- `FinTech Platform Console` 的 recent payment runs、recent async runs、failed async runs 中的 `run_id` 可点击进入详情页。
- operation approval detail view 的 `Associated Async Run` 和 `Platform Result Summary` 中的 `run_id` 可点击进入详情页。

## Access audit 边界

两个 HTML detail view 复用已有查询权限：

```text
view_platform_async_payment_run
view_platform_payment_run
```

成功查看会记录 granted access audit，并用：

```text
reason = view detail
```

查询不存在的 run 仍记录 denied access audit，并返回对应 HTTP 错误。

## 第一版不做

- 不新增数据库表。
- 不新增业务状态。
- 不新增操作按钮。
- 不新增单独前端项目或模板框架。
- 不新增真实 IAM、登录、session 或 CSRF。
- 不把详情页做成可编辑页面。
- 不展示完整底层 ledger 分录，只展示当前 platform result 和 customer audit timeline。

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
test_platform_api_app.py: 39 passed
labs/fintech-platform: 137 passed
labs: 382 passed
demo.py: 可运行
```

## 后续候选方向

阶段 28 完成后，可以选择：

1. 为 operation approval 查询增加总数统计或 cursor pagination。
2. 如果继续增强 console，再考虑 cancel / expire 表单，但要先明确权限和误操作边界。
3. 为 operations console 增加更完整的筛选入口，而不是只显示最新 5 条。
4. 给 platform result detail 增加更细的 reconciliation context，但仍保持只读。
