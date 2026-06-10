# 阶段 32：Payment Detail Reconciliation Context

最后更新：2026-06-10

阶段 32 承接阶段 31。阶段 31 给 console 增加了 payment / async / approval status 筛选入口。阶段 32 回到单条 payment run 详情页：把已有 ledger reconciliation report 的检查结果接入 `Payment Run Detail`，让运营人员在查看单个 payment run 时直接看到该 run 的账本对账上下文。

本阶段仍然只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

reconciliation context，是指围绕某一条业务记录展示的对账检查上下文。它不只是给出最终业务状态，还解释金额、账本入账、余额快照和审计事件之间是否能互相印证。

对应英文术语：

- reconciliation context
- ledger reconciliation
- payment detail view
- audit evidence

## 为什么接入详情页

阶段 17 已经新增 `platform_ledger_reconciliation_report.py`，并把 ledger reconciliation findings 接入 console 的只读区块。但 console 只能横向看多条 findings。

运营人员排查单个 payment run 时，更常见的问题是：

1. 这笔 payment order amount 是否和 ledger posted amount 一致？
2. 平台银行余额和用户钱包余额是否能被 ledger amount 解释？
3. 如果不是入账状态，是否没有残留 ledger artifacts？

阶段 32 让单条 `Payment Run Detail` 直接显示这些检查结果。

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
docs/45-stage-32-payment-detail-reconciliation-context.md
```

## 页面变化

`GET /platform/payment-runs/{run_id}/view` 新增区块：

```text
Ledger Reconciliation Context
```

该区块展示：

```text
check_id
status
severity
message
```

它复用已有：

```text
evaluate_platform_ledger_reconciliation()
```

因此详情页和离线 ledger reconciliation report 使用同一套检查语义。

## 第一版不做

- 不新增数据库表。
- 不新增新的 reconciliation 规则。
- 不查询底层 `SQLiteLedger` 分录明细。
- 不新增下载按钮或单独 reconciliation endpoint。
- 不新增真实银行流水、清算文件或外部账单对账。
- 不改变 payment run、async run 或 approval 生命周期。

## 验证记录

截至 2026-06-10，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m py_compile .\labs\fintech-platform\platform_api_app.py .\labs\fintech-platform\test_platform_api_app.py
```

结果：

```text
test_platform_api_app.py: 44 passed
labs/fintech-platform: 142 passed
labs: 387 passed
demo.py: 可运行
py_compile: 通过
```

说明：

- 普通沙箱执行时，测试无法在 `labs/fintech-platform/.test-data` 下打开 SQLite 测试数据库，报 `sqlite3.OperationalError: unable to open database file`。
- 普通沙箱执行 `demo.py` 时，写入 `labs/fintech-platform/reports` 报告文件会被拒绝；普通沙箱执行 `py_compile` 时，写入 `__pycache__` 会被拒绝。
- 使用授权的非沙箱执行后，测试、demo 和编译检查均通过。

## 后续候选方向

阶段 32 完成后，可以选择：

1. 为 operation approval console 动作增加更明确的风险提示或只读详情页返回入口。
2. 给 console 增加日期范围或 actor 筛选。
3. 如果列表数据继续增长，再讨论 cursor pagination。
4. 给 payment run detail 增加更细的 audit event payload 摘要，但仍保持只读。
