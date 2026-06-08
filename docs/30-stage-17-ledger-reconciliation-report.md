# 阶段 17：Ledger Reconciliation Report

最后更新：2026-06-08

阶段 17 承接阶段 13 的 operations report 和阶段 16 的 console report views。阶段 13 已经能检查 async run、platform result、ledger transaction id 和 `ledger_transaction.posted` audit event 是否互相解释得通；阶段 17 往账本方向再走一步，检查完成支付的金额、账本入账金额和平台快照余额是否一致。

本阶段继续只新增一篇阶段文档，把目标、实现范围、验证记录和后续方向放在一起，避免继续拆出细碎文档。

## 中文定义

Ledger reconciliation，是用可复核的数据来源检查账本记录、业务订单和余额快照是否一致。

对应英文术语：

- ledger reconciliation
- ledger posting
- payment amount reconciliation
- balance reconciliation
- reconciliation finding

## 为什么需要 ledger reconciliation

金融系统里，支付成功、账本入账和余额展示是三个不同层面的事实：

```text
payment order succeeded
-> ledger transaction posted
-> platform / wallet balance changed
```

如果三者不一致，常见风险包括：

1. 业务状态显示成功，但没有真实入账。
2. 入账金额和支付订单金额不一致。
3. 余额快照无法由账本入账金额解释。
4. 被拒绝、blocked 或 review rejected 的非入账流程残留了 ledger posting。

阶段 17 的目标是让这些问题先变成结构化 finding，而不是只靠人工读日志。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_ledger_reconciliation_report.py
labs/fintech-platform/test_platform_ledger_reconciliation_report.py
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
docs/30-stage-17-ledger-reconciliation-report.md
```

## 当前数据边界

当前综合平台持久化的是 `PlatformRunSnapshot`：

```text
platform run record
customer audit timeline
ledger_transaction.posted audit event payload
```

它还没有把底层 `SQLiteLedger` 的分录明细作为平台级查询对象保存下来。因此阶段 17 第一版不是生产级总账数据库对账，也不是银行流水对账，而是基于平台快照和审计事件 payload 的教学版 ledger reconciliation。

这个边界很重要：本阶段检查的是“平台保存下来的业务快照和审计证据是否自洽”，不是检查真实银行账户、清算文件或不可篡改总账。

## 第一版检查规则

`evaluate_platform_ledger_reconciliation()` 会读取一组 `PlatformRunSnapshot`，为每个 run 生成 finding。

completed run 需要通过两类检查：

```text
completed_ledger_amount_matches_payment_order
completed_balances_match_ledger_amount
```

含义是：

1. `payment_order.succeeded` audit payload 里的 amount 必须等于 `ledger_transaction.posted` audit payload 里的 amount。
2. `platform_bank_balance` 和 `user_wallet_balance` 必须等于 ledger amount。

非入账 run 需要通过：

```text
non_posting_run_has_no_ledger_artifacts
```

含义是：非 completed 状态不应有 ledger event、`ledger_transaction_id` 或非零余额。

## 报表输出

`export_platform_ledger_reconciliation_report()` 会导出：

```text
platform_ledger_reconciliation_findings.csv
platform_ledger_reconciliation_report.html
```

CSV 便于后续用脚本或表格工具分析；HTML 便于人工查看。HTML 会转义 finding 中的页面字段，避免把用户可控内容直接作为 HTML 渲染。

## Console 接入

`FinTech Platform Console` 新增只读区块：

```text
Ledger Reconciliation Findings
```

summary metrics 新增：

```text
Ledger reconciliation findings
Ledger reconciliation failed
```

这让运营人员可以在同一个页面里同时看到：

1. async run 和 platform run 状态。
2. operations report summary。
3. operation approval summary。
4. ledger reconciliation finding。

## Demo 接入

`demo.py` 现在会输出：

```text
Exported platform ledger reconciliation reports
```

并在 `labs/fintech-platform/reports/` 下生成：

```text
platform_ledger_reconciliation_findings.csv
platform_ledger_reconciliation_report.html
```

## 第一版不做

- 不新增数据库表。
- 不查询底层 `SQLiteLedger` 分录明细。
- 不引入真实银行 statement、清算文件或外部账单。
- 不新增 HTTP report endpoint。
- 不新增下载按钮。
- 不改变 payment run、async run 或 retry 审批流程。
- 不把 console 改成完整前端项目。

## 工程结论

阶段 17 把“完成支付是否真的按相同金额入账”从人工读 audit timeline，推进到结构化 finding。

程序员视角要注意两个边界：

1. reconciliation 的可信度取决于数据来源。当前只读取平台快照和 audit payload，所以只能证明这些快照之间自洽。
2. 真正生产系统通常还要对接总账分录、资金账户、支付通道回执、银行流水、清算文件和异常处理队列，本仓库目前还没有进入这些范围。

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_ledger_reconciliation_report.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_ledger_reconciliation_report.py: 5 passed
test_platform_api_app.py: 24 passed
demo 可运行并输出 Exported platform ledger reconciliation reports
labs/fintech-platform: 112 passed
labs: 357 passed
```

## 后续候选方向

阶段 17 完成后，可以选择：

1. 为 operation approval record 增加 pending / approved / rejected 状态流转。
2. 给 console 增加只读筛选和分页。
3. 继续推进更真实的 ledger entry 持久化与查询边界。
4. 继续整理历史阶段文档，减少阅读噪音。
