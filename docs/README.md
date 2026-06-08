# docs 文档入口

这个目录保存 FinTech 学习笔记、阶段计划和阶段总结。当前文档已经比较多，阅读时不建议从文件名 01 一路顺读到 30，而应按目标选择路径。

## 推荐阅读路径

### 路径 A：从零开始学习金融科技

适合第一次进入仓库。

1. [00-authoritative-sources.md](00-authoritative-sources.md)：先知道哪些来源更可靠。
2. [01-fintech-overview.md](01-fintech-overview.md)：建立 FinTech 全景。
3. [02-developer-to-finance.md](02-developer-to-finance.md)：理解程序员需要补哪些金融知识。
4. [03-ledger-basics.md](03-ledger-basics.md) 到 [11-outbox-publisher.md](11-outbox-publisher.md)：理解账本、支付订单、幂等、请求指纹和 outbox。
5. [12-transaction-statement-analysis.md](12-transaction-statement-analysis.md) 到 [16-compliance-audit.md](16-compliance-audit.md)：理解数据分析、投资组合、风控、KYC/AML 和合规审计。

### 路径 B：理解当前综合平台

适合想直接看工程作品的人。

1. [../labs/fintech-platform/README.md](../labs/fintech-platform/README.md)：综合平台总入口。
2. [18-stage-8-summary-and-acceptance.md](18-stage-8-summary-and-acceptance.md)：端到端 orchestration 总结。
3. [20-stage-9-summary-and-stage-10-plan.md](20-stage-9-summary-and-stage-10-plan.md)：API service 和最小 console 总结。
4. [22-stage-10-summary-and-acceptance.md](22-stage-10-summary-and-acceptance.md)：async run 和 worker 总结。
5. [23-stage-11-operations-console-plan.md](23-stage-11-operations-console-plan.md)：运营控制台、failed async run 和 retry 总结。
6. [25-stage-12-operation-approval-boundary.md](25-stage-12-operation-approval-boundary.md)：retry 二人审批边界。
7. [26-stage-13-operations-reconciliation-report.md](26-stage-13-operations-reconciliation-report.md)：运行报告与对账视角。
8. [27-stage-14-operation-approval-record.md](27-stage-14-operation-approval-record.md)：独立 operation approval record。
9. [28-stage-15-operation-approval-report.md](28-stage-15-operation-approval-report.md)：operation approval report。
10. [29-stage-16-console-report-views.md](29-stage-16-console-report-views.md)：console report views。
11. [30-stage-17-ledger-reconciliation-report.md](30-stage-17-ledger-reconciliation-report.md)：ledger reconciliation report。

### 路径 C：只看阶段计划和历史

适合回顾为什么这么实现。

| 文档 | 作用 |
| --- | --- |
| [17-stage-7-summary-and-stage-8-plan.md](17-stage-7-summary-and-stage-8-plan.md) | 从单个实验走向综合平台 |
| [18-stage-8-summary-and-acceptance.md](18-stage-8-summary-and-acceptance.md) | 阶段 8 端到端平台验收 |
| [19-stage-9-platform-api-plan.md](19-stage-9-platform-api-plan.md) | 阶段 9 API service 计划 |
| [20-stage-9-summary-and-stage-10-plan.md](20-stage-9-summary-and-stage-10-plan.md) | 阶段 9 总结和阶段 10 路线 |
| [21-stage-10-event-driven-async-plan.md](21-stage-10-event-driven-async-plan.md) | 阶段 10 async 设计 |
| [22-stage-10-summary-and-acceptance.md](22-stage-10-summary-and-acceptance.md) | 阶段 10 总结 |
| [23-stage-11-operations-console-plan.md](23-stage-11-operations-console-plan.md) | 阶段 11 设计与收尾总结 |
| [24-stage-11b-retry-failed-async-run-design.md](24-stage-11b-retry-failed-async-run-design.md) | retry API 设计记录 |
| [25-stage-12-operation-approval-boundary.md](25-stage-12-operation-approval-boundary.md) | 操作审计与审批边界 |
| [26-stage-13-operations-reconciliation-report.md](26-stage-13-operations-reconciliation-report.md) | 运行报告与对账视角 |
| [27-stage-14-operation-approval-record.md](27-stage-14-operation-approval-record.md) | 独立 operation approval record |
| [28-stage-15-operation-approval-report.md](28-stage-15-operation-approval-report.md) | operation approval report |
| [29-stage-16-console-report-views.md](29-stage-16-console-report-views.md) | console report views |
| [30-stage-17-ledger-reconciliation-report.md](30-stage-17-ledger-reconciliation-report.md) | ledger reconciliation report |

## 当前平台能力地图

当前综合平台位于 [../labs/fintech-platform/](../labs/fintech-platform/)。

### 主业务流程

```text
API request
-> PlatformApiService
-> FinTechPlatform.process_payment()
-> KYC/AML decision
-> payment order
-> risk decision
-> ledger posting
-> customer audit timeline
-> SQLitePlatformStore
```

这个流程回答：一个支付请求如何从外部请求变成业务结果、账本记录和审计轨迹。

### 异步处理流程

```text
POST /platform/async-payment-runs
-> SQLitePlatformAsyncRunStore: accepted
-> PlatformAsyncWorker: processing
-> PlatformApiService
-> SQLitePlatformStore: final platform result
-> SQLitePlatformAsyncRunStore: completed / failed
```

这个流程回答：接口返回 `202 Accepted` 后，后台任务如何独立推进，任务状态和业务状态为什么要分开。

### 失败重试和审批流程

```text
failed async run
-> retry request
-> actor + reason
-> approved_by + approval_reason
-> separation of duties check
-> operation approval record approved / rejected
-> access audit granted / denied
-> failed -> accepted
```

这个流程回答：高影响操作为什么不能只靠一个按钮，需要操作人、审批人、确认文本、结构化审批记录和访问审计。

### 访问异常和调查流程

```text
API / report access audit
-> anomaly detection
-> finding
-> investigation case
-> open / investigating / resolved / false_positive
-> case action audit events
```

这个流程回答：访问审计如何从日志变成可处理的调查工单。

### 运行报告与对账流程

```text
PlatformAsyncRun
PlatformRunSnapshot
ledger_transaction.posted audit event
retry_platform_async_run access audit
-> PlatformOperationsReport
-> CSV / HTML reports
```

这个流程回答：运营人员如何横向检查任务状态、最终业务结果、账本入账和 retry 审计是否互相解释得通。

### 操作审批报表流程

```text
OperationApprovalRecord
-> OperationApprovalReport
-> approval records CSV
-> approval summary CSV
-> approval HTML report
```

这个流程回答：运营和合规人员如何汇总查看 retry 审批记录、审批通过/拒绝分布，以及 self-approval 拒绝尝试。

### Console 报表视图

```text
PlatformOperationsReport
OperationApprovalReport
-> FinTech Platform Console
-> read-only report summaries
-> recent operations / approval rows
```

这个流程回答：运营人员如何在同一个页面里观察 async run、对账摘要、retry 审计和审批记录，而不必先下载离线报表。

### Ledger Reconciliation 流程

```text
PlatformRunSnapshot
payment_order.succeeded audit payload
ledger_transaction.posted audit payload
platform / wallet balance snapshot
-> PlatformLedgerReconciliationFinding
-> CSV / HTML report
-> FinTech Platform Console read-only findings
```

这个流程回答：完成支付的订单金额、账本入账金额和平台余额快照是否能互相解释；非入账 run 是否没有残留 ledger artifacts。

## 文档维护约定

- 新金融基础概念优先写在编号文档中，例如账本、支付、风控、KYC/AML、合规审计。
- 阶段性工程计划和总结继续放在 `17+` 的阶段文档中。
- 小阶段尽量把设计、实现进度和验证记录合并到同一篇阶段文档，避免继续拆出很多细碎文档。
- 根目录 [../README.md](../README.md) 只保留仓库入口、快速阅读路径和运行方式；详细文档导航放在本文件。

## 下一步候选方向

1. 为 operation approval record 增加 pending / approved / rejected 状态流转。
2. 给 console 增加只读筛选和分页。
3. 继续推进更真实的 ledger entry 持久化与查询边界。
4. 继续压缩阶段文档，把历史计划和最终总结的关系标得更清楚。
