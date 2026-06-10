# docs 文档入口

这个目录保存 FinTech 学习笔记、阶段计划和阶段总结。当前文档已经比较多，阅读时不建议从文件名 01 一路顺读到 46，而应按目标选择路径。

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
12. [31-stage-18-operation-approval-state-flow.md](31-stage-18-operation-approval-state-flow.md)：operation approval state flow。
13. [32-stage-19-operation-approval-http-endpoints.md](32-stage-19-operation-approval-http-endpoints.md)：operation approval HTTP 查询和 approve/reject endpoints。
14. [33-stage-20-create-operation-approval-http-endpoint.md](33-stage-20-create-operation-approval-http-endpoint.md)：创建 pending operation approval 的 HTTP endpoint。
15. [34-stage-21-retry-approval-before-execution.md](34-stage-21-retry-approval-before-execution.md)：retry 先审批后执行。
16. [35-stage-22-operation-approval-console-view.md](35-stage-22-operation-approval-console-view.md)：pending operation approval console 只读视图。
17. [36-stage-23-operation-approval-pagination-sorting.md](36-stage-23-operation-approval-pagination-sorting.md)：operation approval 列表分页和排序。
18. [37-stage-24-operation-approval-detail-view.md](37-stage-24-operation-approval-detail-view.md)：operation approval 只读详情视图。
19. [38-stage-25-operation-approval-lifecycle.md](38-stage-25-operation-approval-lifecycle.md)：operation approval 取消和过期生命周期。
20. [39-stage-26-console-approval-actions.md](39-stage-26-console-approval-actions.md)：console approve / reject approval 表单。
21. [40-stage-27-approval-lifecycle-timeline.md](40-stage-27-approval-lifecycle-timeline.md)：approval detail lifecycle timeline。
22. [41-stage-28-async-platform-detail-views.md](41-stage-28-async-platform-detail-views.md)：async run 与 platform result 只读详情页。
23. [42-stage-29-operation-approval-pagination-metadata.md](42-stage-29-operation-approval-pagination-metadata.md)：operation approval pagination metadata。
24. [43-stage-30-console-cancel-expire-actions.md](43-stage-30-console-cancel-expire-actions.md)：console cancel / expire approval 表单。
25. [44-stage-31-console-filter-controls.md](44-stage-31-console-filter-controls.md)：console payment / async / approval status 筛选入口。
26. [45-stage-32-payment-detail-reconciliation-context.md](45-stage-32-payment-detail-reconciliation-context.md)：payment run detail reconciliation context。
27. [46-stage-33-remaining-roadmap.md](46-stage-33-remaining-roadmap.md)：剩余章节路线图与平台差距总结。

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
| [31-stage-18-operation-approval-state-flow.md](31-stage-18-operation-approval-state-flow.md) | operation approval state flow |
| [32-stage-19-operation-approval-http-endpoints.md](32-stage-19-operation-approval-http-endpoints.md) | operation approval HTTP endpoints |
| [33-stage-20-create-operation-approval-http-endpoint.md](33-stage-20-create-operation-approval-http-endpoint.md) | create operation approval HTTP endpoint |
| [34-stage-21-retry-approval-before-execution.md](34-stage-21-retry-approval-before-execution.md) | retry approval before execution |
| [35-stage-22-operation-approval-console-view.md](35-stage-22-operation-approval-console-view.md) | operation approval console view |
| [36-stage-23-operation-approval-pagination-sorting.md](36-stage-23-operation-approval-pagination-sorting.md) | operation approval pagination and sorting |
| [37-stage-24-operation-approval-detail-view.md](37-stage-24-operation-approval-detail-view.md) | operation approval detail view |
| [38-stage-25-operation-approval-lifecycle.md](38-stage-25-operation-approval-lifecycle.md) | operation approval lifecycle |
| [39-stage-26-console-approval-actions.md](39-stage-26-console-approval-actions.md) | console approval actions |
| [40-stage-27-approval-lifecycle-timeline.md](40-stage-27-approval-lifecycle-timeline.md) | approval lifecycle timeline |
| [41-stage-28-async-platform-detail-views.md](41-stage-28-async-platform-detail-views.md) | async run and platform result detail views |
| [42-stage-29-operation-approval-pagination-metadata.md](42-stage-29-operation-approval-pagination-metadata.md) | operation approval pagination metadata |
| [43-stage-30-console-cancel-expire-actions.md](43-stage-30-console-cancel-expire-actions.md) | console cancel / expire approval actions |
| [44-stage-31-console-filter-controls.md](44-stage-31-console-filter-controls.md) | console filter controls |
| [45-stage-32-payment-detail-reconciliation-context.md](45-stage-32-payment-detail-reconciliation-context.md) | payment detail reconciliation context |
| [46-stage-33-remaining-roadmap.md](46-stage-33-remaining-roadmap.md) | remaining roadmap and platform gap summary |

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
-> GET /platform/async-payment-runs/{run_id}/view
-> GET /platform/payment-runs/{run_id}/view
-> Payment Run Detail: ledger reconciliation context
```

这个流程回答：接口返回 `202 Accepted` 后，后台任务如何独立推进，任务状态和业务状态为什么要分开，以及运营人员如何继续点进 async run 和最终 platform result 详情页查看业务、审计和账本对账上下文。

### 失败重试和审批流程

```text
failed async run
-> retry approval request
-> operation approval record pending
-> approve / reject approval
-> approval access audit granted / denied
-> retry execution access audit
-> failed -> accepted
```

这个流程回答：高影响操作为什么不能只靠一个按钮，需要把申请、审批和执行拆开，并留下结构化审批记录与访问审计。

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

### 操作审批 HTTP 流程

```text
OperationApprovalRecord
-> POST /platform/operation-approvals
-> GET /platform/operation-approvals
-> limit / offset / sort_by / sort_order
-> pagination metadata: total_count / has_next_page / next_offset
-> GET /platform/operation-approvals/{approval_id}
-> GET /platform/operation-approvals/{approval_id}/view
-> Lifecycle Timeline: approval_requested / approval_decided / retry_execution
-> linked async run detail / platform result detail
-> PATCH approve / reject / cancel / expire
-> POST approve-form / reject-form / cancel-form / expire-form
-> access audit granted / denied
```

这个流程回答：pending approval 如何通过 API 被创建、分页查看、排序查看，并通过 `total_count`、`has_next_page` 和 `next_offset` 判断是否还需要继续翻页；之后可进入详情查看、在详情页按时间解释申请、决策和 retry execution，并继续跳转到关联 async run 和 platform result 详情页；再通过 JSON 或 console form 流转到 approved / rejected / cancelled / expired，并留下访问审计。

### Console 报表视图

```text
PlatformOperationsReport
OperationApprovalReport
-> FinTech Platform Console
-> read-only report summaries
-> status filter controls: payment / async / approval
-> recent operations / approval rows
-> pending approval rows with async status
-> approval detail links
-> lifecycle timeline in approval detail view
-> async run detail links
-> platform result detail links
-> cancelled / expired approval counts
-> approve / reject / cancel / expire forms for pending approvals
```

这个流程回答：运营人员如何在同一个页面里观察 async run、对账摘要、retry 审计、审批记录和待审批 approval，能按 payment / async / approval status 缩小展示范围，能点进只读详情页查看 approval lifecycle timeline、async run request payload、platform result 和 customer audit timeline，并能对 pending approval 执行 approve / reject / cancel / expire。

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

阶段 33 估算从当前教学版平台到更完整平台还剩约 `6 个建设章节 + 1 个最终验收章节`。

建议下一步进入阶段 34：运营 Console 和工作流补强。

1. 给 console 增加 `actor` 和日期范围筛选。
2. 给 pending approval 操作区域增加更明确的风险提示。
3. 给 detail views 增加返回 console 的链接。
4. 暂不新增数据库表，不引入前端框架，不处理真实登录。
