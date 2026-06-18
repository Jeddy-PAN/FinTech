# FinTech Platform

这是阶段 8 的综合设计实验。目标不是重写前面所有实验，而是把已有模块串成一个最小的端到端 FinTech 学习平台，观察开户、支付、风控、入账、审计和调查如何协同。

## 设计目标

- 复用现有实验中的领域能力，而不是重新造轮子。
- 让一条最小业务链路跑通：`customer onboarding -> KYC/AML decision -> payment order -> risk decision -> ledger posting -> audit trail`.
- 把前面分散的模块放进同一个 orchestration 视角里，理解一致性边界和数据流。
- 保持教学属性，不伪装成真实生产系统。

## 最小场景

一个客户完成开户后发起支付：

1. 客户通过 KYC/AML 筛查，得到可解释决策。
2. 客户创建 payment order。
3. 风控引擎评估该订单，输出 `approved`、`review` 或 `blocked`。
4. 如果通过，账本写入分录并更新余额。
5. 全部关键动作生成 audit event。
6. 如果后续出现可疑访问或合规问题，可以导出报表并进入 investigation case。

这个场景的重点不是交易量，而是把“业务动作、状态变化、账务记录、审计追踪”串起来。

## 复用模块

```text
labs/ledger-basics/
labs/payment-orders/
labs/risk-rule-engine/
labs/kyc-aml-onboarding/
labs/compliance-audit/
```

各模块在综合平台中的角色：

| 模块 | 作用 |
| --- | --- |
| `ledger-basics` | 负责双分录入账和余额变化 |
| `payment-orders` | 负责订单状态机、退款和支付生命周期 |
| `risk-rule-engine` | 负责交易决策、人工复核和规则命中 |
| `kyc-aml-onboarding` | 负责客户准入和名单筛查 |
| `compliance-audit` | 负责统一审计视图、访问审计、留存、异常检测和调查工单 |

## 综合平台的职责

综合平台先只做 orchestration：

- 调用开户模块获得客户通过结果。
- 调用支付订单模块创建和推进订单状态。
- 调用风控模块决定支付是否可继续。
- 调用账本模块完成最终记账。
- 调用合规审计模块记录和查询审计事件。

它不直接替代底层模块，只负责把动作串联起来。

当前已实现最小 orchestration 入口：

```text
fintech_platform.py
```

核心对象：

```text
FinTechPlatform
PlatformPaymentRequest
PlatformPaymentResult
PlatformPaymentStatus
```

`FinTechPlatform.process_payment()` 会按顺序执行：

```text
KYC/AML decision
-> payment_order.created
-> risk_decision.saved
-> payment_order.succeeded / payment_order.failed / review_case.created
-> ledger_transaction.posted
-> customer audit timeline
```

如果 KYC/AML 决策不是 `approved`，平台不会创建 payment order。如果风控决策是 `blocked`，payment order 会标记为 `failed`，不会入账。如果风控决策是 `review`，payment order 保持 `pending`，并创建 risk review case。

当前还支持 risk review 后续处理：

```text
risk_review_required
-> review_case.approved / review_case.rejected
-> payment_order.succeeded / payment_order.failed
-> ledger_transaction.posted
```

如果人工复核通过，平台会把 review case 标记为 `approved`，支付订单推进为 `succeeded`，并写入账本分录。如果人工复核拒绝，平台会把 review case 标记为 `rejected`，支付订单推进为 `failed`，不会写入账本。两条路径都会追加 customer audit timeline。

当前还支持综合报表导出：

```text
platform_report_export.py
platform_payment_result.csv
platform_audit_timeline.csv
platform_report.html
```

`platform_payment_result.csv` 记录平台状态、KYC 决策、支付订单状态、风控结果、账本交易和审计事件数量。`platform_audit_timeline.csv` 记录客户维度的端到端审计时间线。HTML 报告用于人工复核，并会转义页面字段。

当前还支持 SQLite 持久化：

```text
sqlite_platform_store.py
platform_runs
platform_run_audit_events
```

`SQLitePlatformStore.save_result()` 会保存一次 platform run 的结果快照和对应 customer audit timeline。它支持按 `run_id` 取回 snapshot，列出所有 runs，并按平台状态或客户 ID 查询。

当前还支持持久化后的历史运行报表：

```text
platform_history_report_export.py
platform_run_history.csv
platform_run_audit_events.csv
platform_run_history.html
```

`platform_run_history.csv` 记录多次 platform run 的状态、客户、订单、风控、账本和审计事件数量。`platform_run_audit_events.csv` 记录每次 run 对应的 audit events。HTML 报告用于人工复核历史运行，并会转义页面字段。

当前还支持教学版一致性检查：

```text
platform_consistency_report.py
platform_consistency_findings.csv
platform_consistency_report.html
```

一致性检查会读取已持久化的 `PlatformRunSnapshot`，检查 platform status、payment order status、ledger transaction id 和 audit events 是否互相吻合。例如 `completed` 必须有 `payment_order.succeeded` 和 `ledger_transaction.posted`；`risk_review_rejected` 必须有 `review_case.rejected` 和 `payment_order.failed`，且不能有 ledger posting。这个检查不等于生产级对账，只用于学习状态、账本和 audit trail 之间的关系。

当前还支持平台报表访问控制和访问审计：

```text
platform_report_access.py
export_platform_report_with_access
export_platform_history_report_with_access
export_platform_consistency_report_with_access
```

这层包装复用合规审计实验里的 `AuditUser`、`export_audit_report` 权限、`AuditAccessRecorder` 和 `AuditExportApproval`。`audit_manager` 可以导出平台报表；缺少权限的用户会被拒绝并记录 `audit_access.denied`；高敏感导出可以要求另一名 manager 审批，并记录 `audit_export_approval.granted`。demo 会把访问审计事件写入 `SQLiteAccessAuditStore`，用于观察“谁导出了平台报表”。

当前还支持平台报表访问异常检测：

```text
platform_access_anomaly_report.py
platform_access_anomaly_findings.csv
platform_access_anomaly_report.html
```

它复用合规审计实验里的 `detect_access_anomalies()` 和 `AccessAnomalyFinding`，但只分析 `target` 以 `fintech_platform_` 开头的平台报表访问事件。demo 会构造样例的非授权导出尝试和重复拒绝访问，生成 `unauthorized_export_attempt` 与 `repeated_denied_access` finding，并导出平台专用 CSV/HTML 报告。

当前还支持平台访问异常调查工单：

```text
platform_investigation_cases.py
platform_access_investigation_cases.csv
platform_access_investigation_report.html
```

它复用合规审计实验里的 `AccessAnomalyInvestigationService` 和 `SQLiteInvestigationCaseStore`，把平台 access anomaly finding 转成 investigation case，并支持 `open -> investigating -> resolved / false_positive` 的处理闭环。demo 会创建平台调查工单，启动并关闭一个样例工单，把工单写入 SQLite，再导出平台专用 CSV/HTML 报告。工单创建、接手和关闭动作本身也会生成 `access_investigation_case.*` 审计事件。

## 建议的数据对象

```text
customer
account
payment_order
risk_decision
ledger_transaction
audit_event
investigation_case
```

这些对象不一定都要由新目录重新定义；很多时候只需要在 orchestration 层引用现有模块返回的数据结构。

## 一致性边界

这个阶段最重要的学习点之一是：哪些动作必须强一致，哪些动作可以延后。

- 开户结果和支付是否允许发起，需要明确依赖前置决策。
- 订单状态变化和账本入账之间要区分“业务状态”和“会计记录”。
- 审计事件应该尽量覆盖关键动作，但不把所有东西都写进同一个事务里。
- 报表、留存、异常检测和调查工单更像派生流程，可以放在业务主路径之外。

## 暂不实现

- 真实 API 网关。
- 真实认证、会话管理和企业 IAM。
- 真实支付通道、清算和结算。
- 真实监管规则、报送和法律留存要求。
- 真实工单系统、通知、附件、SLA 和升级路径。
- 分布式事务框架。

## 下一步实现建议

1. 已完成 `README` 级别的架构草图。
2. 已完成最小 orchestration 入口。
3. 已完成端到端 demo，把开户、支付、风控、入账和审计串起来。
4. 已完成综合报表导出。
5. 已完成 SQLite 持久化。
6. 已完成持久化后的 platform runs 历史运行报表。
7. 已完成 risk review 后续处理，支持人工通过后入账、人工拒绝后失败。
8. 已完成教学版 platform consistency report，用于检查 platform run 历史、审计事件顺序和一致性边界。
9. 已完成平台报表访问控制和访问审计，支持授权、拒绝、二人审批和 SQLite 持久化访问记录。
10. 已完成平台报表访问异常检测和报告导出。
11. 已完成平台 access anomaly finding 到 investigation case 的闭环，支持工单状态流转、SQLite 持久化、报告导出和工单动作审计。
12. 已完成阶段 8 小结和端到端验收清单。
13. 已完成阶段 9 API 服务化、API access audit、API access anomaly、API investigation case 和最小 console。
14. 已完成阶段 10 async run store、worker、FastAPI async endpoints、demo 展示和阶段总结。
15. 已完成阶段 11 运营控制台增强、failed async run retry API 和控制台 retry form。
16. 已完成阶段 12 第一版：failed async run retry 增加二人审批、职责分离和更明确的操作审计边界。
17. 已完成阶段 13 第一版：新增运行报告与对账视角，把 async run、platform result、ledger posting 和 retry access audit 汇总为离线 CSV/HTML 报告。
18. 已完成阶段 14 第一版：把 retry 审批从 access audit reason 拆成独立 operation approval record。
19. 已完成阶段 15 第一版：新增 operation approval report，把 approval records 汇总为 CSV/HTML 报表。
20. 已完成阶段 16 第一版：把 operations report 和 approval report 的核心摘要接入只读 console。
21. 已完成阶段 17 第一版：新增 ledger reconciliation report，并把 ledger reconciliation findings 接入 demo 和只读 console。
22. 已完成阶段 18 第一版：operation approval record 支持 pending / approved / rejected 状态流转，approval report 和 console summary 可统计 pending。
23. 已完成阶段 19 第一版：pending operation approval 支持 HTTP 查询和 approve/reject，并记录 API access audit。
24. 已完成阶段 20 第一版：pending operation approval 支持 HTTP 创建、查询和 approve/reject，并记录 API access audit。
25. 已完成阶段 21 第一版：failed async run retry 改成先创建 pending approval，审批通过后再执行 retry。
26. 已完成阶段 22 第一版：console 新增 pending operation approvals 只读视图，并显示关联 async run 状态。
27. 已完成阶段 23 第一版：operation approval 列表支持分页和排序，console approval 表格默认按申请时间倒序展示最新记录。
28. 已完成阶段 24 第一版：operation approval 支持只读详情页，可查看 approval、关联 async run 和 completed platform result 摘要。
29. 已完成阶段 25 第一版：operation approval 支持 cancelled / expired 生命周期状态。
30. 已完成阶段 26 第一版：console 支持 pending operation approval approve / reject 表单。
31. 已完成阶段 27 第一版：operation approval 详情页新增只读 lifecycle timeline。
32. 已完成阶段 28 第一版：async run 和 platform result 支持只读详情页，并从 console / approval detail 链接进入。
33. 已完成阶段 29 第一版：operation approval 查询返回 `total_count`、`has_next_page` 和 `next_offset`。
34. 已完成阶段 30 第一版：console 支持 pending operation approval cancel / expire 表单。
35. 已完成阶段 31 第一版：console 支持 payment / async / approval status 筛选入口。
36. 已完成阶段 32 第一版：payment run 详情页支持 ledger reconciliation context。
37. 已完成阶段 33 第一版：形成剩余章节路线图与平台差距总结，建议后续按 6 个建设章节加 1 个最终验收章节推进。
38. 已完成阶段 34 第一版：console 支持 actor 和日期范围筛选，pending approval 区块新增高影响操作风险提示，operation approval、async run 和 payment run 详情页新增返回 console 的入口。
39. 已完成阶段 35 第一版：新增教学版 `PlatformIdentityContext`、role / permission policy，并对 access audit 查询、operation approval 查询和更新路径增加权限校验与身份一致性校验。
40. 已完成阶段 36 第一版：async worker 使用 `claim_next_accepted()` 原子认领 accepted run，operation approval 终态决策使用 pending 状态条件更新，并补充重复 claim / 重复 approve-retry 冲突测试。
41. 已完成阶段 37 第一版：新增教学版 `ProviderSettlementRow` 和 settlement reconciliation report，用外部 provider settlement row 检查内部 completed run、金额、币种和孤立外部记录。
42. 已完成阶段 38 第一版：新增教学版 evidence package，把 settlement reconciliation findings、access anomaly findings、operation approval records 和 denied access events 汇总成可导出的证据包。
43. 已完成阶段 39 第一版：新增教学版 operability readiness、metrics 和 test matrix API，用于本地交付、观测和验收。
44. 已完成阶段 40 第一版：形成最终验收与学习作品集总结，明确当前能力、验收命令和仍不覆盖的生产级边界。
45. 已完成阶段 40 后的前端体验改造第一版：`FinTech Platform Console` 新增统一顶部导航、页面区块锚点和响应式工作台样式；新增 `GET /platform/manual` 用户手册页，说明平台功能、主要流程、权限边界、证据包、operability 和教学边界。
46. 已完成阶段 40 后的前端体验改造第二版：顶部导航收敛为 `Console` / `Manual` 两个主入口，左侧目录负责 Console 和 Manual 内部章节跳转；Manual 支持 `?lang=en` / `?lang=cn` 双语切换，并新增详细事件流程图，用一笔订单说明从请求进入、幂等、KYC/AML、风控、入账、retry approval、对账、证据包到 operability review 的端到端路径。
47. 已新增 Playwright 小型浏览器回归：`test_platform_ui_playwright.py` 会自动启动临时 FastAPI 服务、使用临时 SQLite 数据库，并通过本机 Edge/Chrome 验证 Console/Manual 导航、Manual CN/EN 切换，以及 failed async run 从网页提交 retry approval 并 approve 后回到 accepted 的流程。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

demo 会生成：

```text
labs/fintech-platform/reports/platform_payment_result.csv
labs/fintech-platform/reports/platform_audit_timeline.csv
labs/fintech-platform/reports/platform_report.html
labs/fintech-platform/reports/platform_run_history.csv
labs/fintech-platform/reports/platform_run_audit_events.csv
labs/fintech-platform/reports/platform_run_history.html
labs/fintech-platform/reports/platform_consistency_findings.csv
labs/fintech-platform/reports/platform_consistency_report.html
labs/fintech-platform/reports/platform_access_anomaly_findings.csv
labs/fintech-platform/reports/platform_access_anomaly_report.html
labs/fintech-platform/reports/platform_api_access_anomaly_findings.csv
labs/fintech-platform/reports/platform_api_access_anomaly_report.html
labs/fintech-platform/reports/platform_access_investigation_cases.csv
labs/fintech-platform/reports/platform_access_investigation_report.html
labs/fintech-platform/reports/platform_api_access_investigation_cases.csv
labs/fintech-platform/reports/platform_api_access_investigation_report.html
labs/fintech-platform/reports/platform_operations_run_report.csv
labs/fintech-platform/reports/platform_operations_reconciliation_findings.csv
labs/fintech-platform/reports/platform_operations_report.html
labs/fintech-platform/reports/platform_operation_approval_records.csv
labs/fintech-platform/reports/platform_operation_approval_summary.csv
labs/fintech-platform/reports/platform_operation_approval_report.html
labs/fintech-platform/reports/platform_ledger_reconciliation_findings.csv
labs/fintech-platform/reports/platform_ledger_reconciliation_report.html
labs/fintech-platform/reports/platform_settlement_reconciliation_findings.csv
labs/fintech-platform/reports/platform_settlement_reconciliation_report.html
labs/fintech-platform/reports/platform_evidence_package_items.csv
labs/fintech-platform/reports/platform_evidence_package_summary.csv
labs/fintech-platform/reports/platform_evidence_package_report.html
```

demo 还会输出 `Risk review completion`，用于观察 `risk_review_required -> completed` 的人工复核通过闭环。它也会输出 `Async payment run via FastAPI`，用 in-process FastAPI client 展示创建 async run、触发教学版 worker、查询最终 platform result 和 API access audit。随后 demo 会输出 `Failed async run sample for console`，通过真实 API 流程构造一个 request fingerprint 冲突导致的 failed async run，用来观察 console 里的 failed async run、attempt count 和 last error。

demo 现在也会输出 `Exported platform operations reports`，用于观察 `PlatformAsyncRun`、`PlatformRunSnapshot`、`ledger_transaction.posted` audit event 和 `retry_platform_async_run` access audit 如何组成一份运营对账报告。

demo 现在也会输出 `Exported operation approval reports`，用于观察 `OperationApprovalRecord` 如何汇总为 approval records CSV、approval summary CSV 和 HTML 报告。运行 API 服务后，`FinTech Platform Console` 也会显示 `Operations Report Summary`、`Operation Approval Summary`、`Operations Run Rows`、`Pending Operation Approvals` 和 `Approval Records` 区块；approval 表格默认按 `requested_at desc` 展示最新记录，`approval_id` 会链接到只读详情页，pending approval 行支持 approve / reject / cancel / expire 表单。console 还支持按 payment status、async status、approval status、actor 和日期范围缩小展示范围，并在高影响 approval 操作区域显示风险提示。

demo 现在也会输出 `Pending operation approval flow`，用于观察 retry approval request 如何先创建 `pending` approval，再通过 approve endpoint 流转为 `approved`，并在审批通过后把 failed async run 放回 `accepted`；同时展示独立样例 approval 如何流转为 `cancelled` 和 `expired`。

demo 现在也会输出 `Exported platform ledger reconciliation reports`，用于观察 completed run 的 payment order amount、ledger amount、platform bank balance 和 user wallet balance 是否一致。运行 API 服务后，`FinTech Platform Console` 也会显示 `Ledger Reconciliation Findings` 只读区块；单个 payment run 详情页也会显示该 run 的 ledger reconciliation context。

demo 现在也会先生成 `reports/provider_settlement_sample.csv`，再解析成教学版外部 provider settlement row，并输出 `Exported platform settlement reconciliation reports`。这个流程用于观察内部 completed platform run 和外部 settlement file 是否能对上；该报告会检查外部 settled row 是否存在、金额和币种是否匹配、非 completed 内部 run 是否错误出现在外部 settlement file 中，以及外部 row 是否能映射回内部 run。

demo 现在也会输出 `Exported platform evidence package`，用于观察 settlement reconciliation、access anomaly、operation approval、provider webhook event 和 denied access event 如何被组织成同一个教学版 evidence package。这个包会导出 evidence items、summary 和 HTML 报告，但不代表真实法律保全、真实监管证据清单或真实留存期限。

demo 现在也会输出 `Platform operability snapshot`，用于观察本地 readiness、关键 metrics 和测试矩阵行数。readiness 会检查各个 SQLite store 是否可打开；metrics 会汇总 payment runs、async runs、operation approvals 和 denied access 等教学版计数。

运行 API 服务后，`GET /platform/view` 是运营控制台入口，`GET /platform/manual` 是面向使用者的手册页。顶部导航只负责在 `Console` 和 `Manual` 两个主入口之间切换；左侧目录负责页面内部章节跳转。Manual 支持 `GET /platform/manual?lang=en` 和 `GET /platform/manual?lang=cn`，并在 `#flow-diagram` 提供详细事件流程图。手册页只解释本教学平台的功能和流程，不代表生产级支付、清结算、监管合规、法律留存或企业 IAM。

如果要执行小型浏览器回归，需要先安装 `pytest-playwright`。当前测试会优先使用本机 Edge/Chrome，不强制依赖 Playwright 自带 Chromium：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_ui_playwright.py -q
```

demo 还会写入并重新读取：

```text
labs/fintech-platform/.test-data/demo_platform_runs.db
labs/fintech-platform/.test-data/demo_platform_access_audit.db
labs/fintech-platform/.test-data/demo_platform_async_runs.db
labs/fintech-platform/.test-data/demo_platform_api_access_audit.db
labs/fintech-platform/.test-data/demo_platform_operation_approvals.db
labs/fintech-platform/.test-data/demo_platform_investigation_cases.db
labs/fintech-platform/.test-data/demo_platform_api_investigation_cases.db
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform
```

## 当前状态

这个目录已经包含第一版综合平台设计、最小 orchestration、demo、综合报表导出、SQLite 持久化、历史运行报表、risk review 后续处理、教学版一致性检查、平台报表访问控制与访问审计、平台访问异常检测、平台访问异常调查工单、异步任务、运营控制台、retry 审批边界、运行报告与对账视角、operation approval record、operation approval report、console report views、ledger reconciliation report、operation approval state flow、operation approval HTTP endpoints、create operation approval HTTP endpoint、retry approval before execution、operation approval console view、operation approval pagination and sorting、operation approval detail view、operation approval lifecycle、console approval actions、approval lifecycle timeline、async run detail view、platform result detail view、operation approval pagination metadata、console cancel / expire approval actions、console filter controls、payment detail reconciliation context、剩余章节路线图、console workflow controls、identity / permission / form security boundary、consistency / concurrency / recovery boundary、external settlement reconciliation、evidence package、operability readiness / metrics / test matrix、前端工作台导航、双语平台用户手册页和端到端事件流程图，以及测试。阶段 40 后已开始做小规模文件分类整理，Manual CN/EN 内容和事件流程图已从 `platform_api_app.py` 拆到 `platform_api_manual_views.py`，Console 的纯 HTML helper、筛选表单、提示和表格渲染已拆到 `platform_api_console_views.py`，payment / async / operation approval 详情页渲染已拆到 `platform_api_detail_views.py`，详情页 API 测试已从 `test_platform_api_app.py` 拆到 `test_platform_api_detail_views.py`，Console 只读渲染和筛选测试已拆到 `test_platform_api_console.py`，Console 表单动作测试已拆到 `test_platform_api_console_actions.py`，API / Console / Detail view 测试共用 helper 已抽到 `test_platform_api_helpers.py`，operation approval JSON endpoint 测试已拆到 `test_platform_api_operation_approvals.py`，async / retry JSON endpoint 测试已拆到 `test_platform_api_async_runs.py`，payment run 基础 API 测试已拆到 `test_platform_api_payment_runs.py`。阶段 8 以来的目标仍然是把已有实验组合成一个清晰的学习平台，而不是立即扩成生产级系统；后续建议保留 `test_platform_api_app.py` 作为 smoke 入口，不再继续拆得过碎。

阶段 9 已经开始在这个目录上做 API 服务化的第一步：

```text
platform_api_service.py
platform_api_app.py
platform_api_console_views.py
platform_api_detail_views.py
platform_api_manual_views.py
```

当前先实现纯 Python service 边界，支持创建 payment run、查询 payment run、按状态或客户筛选 runs，并用 `run_id` 加 request fingerprint 做教学版幂等校验。FastAPI 路由层已经接入，提供 `GET /health`、`POST /platform/payment-runs`、`GET /platform/payment-runs/{run_id}` 和带筛选参数的 `GET /platform/payment-runs`。

FastAPI 路由层现在也会记录教学版 API 访问审计：

```text
SQLiteAccessAuditStore
audit_access.granted
audit_access.denied
GET /platform/api-access-events
```

创建、查询和列出 payment runs 会记录调用者、权限、目标、结果和发生时间。查询类接口可以通过 `x-actor-id` 请求头传入 actor；如果没有传，则记录为 `anonymous_api_client`。创建 payment run 沿用请求体中的 `actor`。这只是教学版 access audit，不等于真实认证、授权或 API gateway。

API access audit 现在也能进入平台 API 访问异常检测：

```text
platform_api_access_anomaly_report.py
platform_api_access_anomaly_findings.csv
platform_api_access_anomaly_report.html
```

它只分析 `target` 以 `fintech_platform_api_` 开头的访问审计事件，并复用合规审计阶段的 access monitoring 规则。当前 demo 会构造短时间内重复查询不存在 payment run 的样例，生成 repeated denied access finding，并导出 CSV/HTML 报告。这是离线教学检测，不代表生产级实时安全告警。

API access anomaly 现在也能进入单独的调查工单闭环：

```text
platform_api_investigation_cases.py
platform_api_access_investigation_cases.csv
platform_api_access_investigation_report.html
```

这层继续复用合规审计实验里的 `AccessAnomalyInvestigationService` 和 `SQLiteInvestigationCaseStore`，但导出 API 专用的工单报告。demo 会创建一个 API access investigation case，演示 `open -> investigating -> false_positive`，写入 SQLite，并输出工单处理动作审计事件。这仍是教学版闭环，不代表真实工单系统、SLA 或自动封禁。

FastAPI 也已经暴露 API anomaly 和 API investigation case 的最小查询入口：

```text
GET  /platform/api-access-anomaly-findings
POST /platform/api-access-investigation-cases
GET  /platform/api-access-investigation-cases
GET  /platform/api-access-investigation-cases/{case_id}
PATCH /platform/api-access-investigation-cases/{case_id}/start
PATCH /platform/api-access-investigation-cases/{case_id}/resolve
PATCH /platform/api-access-investigation-cases/{case_id}/false-positive
```

这些接口用于观察“访问审计事件 -> finding -> investigation case -> 持久化查询 -> 状态流转”的链路。它们不包含真实权限、分页、锁定认领、审批或 SLA。

FastAPI 现在也提供一个最小前端查看页：

```text
GET /
GET /platform
GET /platform/view
```

页面标题是 `FinTech Platform Console`，只读展示 payment runs、async runs、failed async runs、API access anomalies、investigation cases 和 recent API access events。completed async run 会关联显示最终 platform status 和 payment order id，用来观察任务状态和业务状态的区别。它不引入单独前端项目、模板框架、登录态或真实 IAM；访问查看页本身会记录 `view_platform_console` access audit，用来观察运营查看动作也应进入审计轨迹。

运行 API 示例：

```powershell
& 'C:\App\Anaconda\python.exe' -m uvicorn platform_api_app:app --app-dir .\labs\fintech-platform --reload
```

服务启动后，可以访问 `http://127.0.0.1:8000/` 查看最小页面，或访问 `http://127.0.0.1:8000/docs` 查看 FastAPI 自动生成的接口文档。

阶段 9 已经形成收尾总结：

```text
docs/20-stage-9-summary-and-stage-10-plan.md
```

该文档总结 API service、幂等、访问审计、API access anomaly、investigation case 和最小 console 的工程结论，并建议阶段 10 优先进入事件驱动与异步任务主题。

阶段 10 已经形成设计和收尾总结：

```text
docs/21-stage-10-event-driven-async-plan.md
docs/22-stage-10-summary-and-acceptance.md
```

阶段 10 不另起项目，而是在当前 API service 后面增加教学版异步边界。目标是把同步的 payment run 处理拆成 `accepted -> processing -> completed / failed`，学习 async run store、worker、retry、request fingerprint 和最终 platform run 快照之间的关系。

当前已新增：

```text
platform_async_service.py
test_platform_async_service.py
```

`SQLitePlatformAsyncRunStore` 会把 `PlatformApiPaymentRequest` 保存成 `accepted` async run，写入 `platform_async_runs` 表，并用 `run_id` 加 request fingerprint 区分安全重放和参数冲突。`PlatformAsyncWorker` 会读取最早的 `accepted` run，标记为 `processing`，调用现有 `PlatformApiService` 处理 payment run，把最终结果写入 `SQLitePlatformStore`，再把 async run 标记为 `completed`。如果 worker 处理失败，会记录 `last_error` 和 `attempt_count`，未超过 `max_attempts` 时回到 `accepted` 等待重试，达到上限后标记为 `failed`。

FastAPI 现在也暴露阶段 10 的教学版 async endpoints：

```text
POST /platform/async-payment-runs
GET  /platform/async-payment-runs
GET  /platform/async-payment-runs/{run_id}
POST /platform/async-payment-runs/{run_id}/retry
POST /platform/async-worker/process-next
POST /platform/async-worker/process-pending
```

`POST /platform/async-payment-runs` 返回 `202 Accepted` 风格响应，只表示请求已被保存为 async run，不表示支付业务已经完成。worker 触发接口会推进 accepted run，并把最终业务结果写入 `SQLitePlatformStore`。查询单个 async run 时，如果最终 platform run 已存在，会返回 `platform_result`，用于观察任务状态和业务结果的区别。async 创建、查询、列表和 worker 触发都会写入教学版 API access audit。当前测试覆盖 async API 创建、查询、按状态筛选、幂等重放、fingerprint 冲突、worker 处理、空队列和批量处理。demo 现在也展示了 async HTTP 观察路径。阶段 10 总结文档已记录工程结论、验收清单、当前边界和阶段 11 候选路线。

阶段 11B 新增教学版 failed async run retry endpoint：`POST /platform/async-payment-runs/{run_id}/retry`。

该接口只允许把 `failed` async run 重新放回 `accepted` 队列，要求请求体包含 `actor`、`reason` 和 `confirmation: retry_failed_async_run`。retry 不直接执行业务处理，后续仍由 worker endpoint 推进；成功和失败都会写入 API access audit。

阶段 11C 已把 retry 接入 `FinTech Platform Console` 的 failed async runs 区域。页面表单提交到 `POST /platform/async-payment-runs/{run_id}/retry-form`，该 form endpoint 只是浏览器表单适配层，内部仍复用同一套 retry 校验和 API access audit；提交成功后回到 console，run 只进入 `accepted`，不会直接触发 worker。

阶段 11 已经完成运营控制台增强设计与收尾总结：

```text
docs/23-stage-11-operations-console-plan.md
```

阶段 11 继续增强现有 `FinTech Platform Console`，目标是在同一个页面里观察 payment runs、async runs、API access anomalies、investigation cases 和 recent API access events。当前已把 async run summary、recent async runs 和 failed async runs 接入现有 console 页面，并在 demo 中补充了 failed async run 可观察样例；阶段 11B/11C 又补充了 failed async run retry API 和控制台 retry form。

阶段 12 第一版已完成：

```text
docs/25-stage-12-operation-approval-boundary.md
```

阶段 12 已把 failed async run retry 从“单人操作 + 原因 + confirmation”升级为“操作人 + 原因 + 独立审批人 + 审批原因 + confirmation”的教学版 maker-checker 边界。JSON API 和控制台 form 都要求 `approved_by`、`approval_reason` 和 `approval_confirmation: approve_retry_failed_async_run`；`actor == approved_by` 会被拒绝并写入 denied access audit。当前仍不引入真实 IAM、审批流数据库或前端框架。

阶段 13 第一版已完成：

```text
docs/26-stage-13-operations-reconciliation-report.md
platform_operations_report.py
test_platform_operations_report.py
```

阶段 13 新增离线 operations report，不新增 HTTP endpoint 或数据库表。报告按 `run_id` 汇总 async status、platform status、payment order status、ledger transaction id、worker attempt、last error 和 retry granted/denied 次数，并生成 reconciliation finding：completed async run 缺少 platform result、failed async run 待运营复核、completed platform run 缺少 ledger transaction id、ledger transaction id 缺少 matching `ledger_transaction.posted` audit event。

阶段 14 第一版已完成：

```text
docs/27-stage-14-operation-approval-record.md
platform_operation_approval.py
test_platform_operation_approval.py
```

阶段 14 把 failed async run retry 的审批信息拆成独立 `OperationApprovalRecord`。access audit 仍然记录 retry API 的 granted/denied 访问事实；operation approval record 记录 requested_by、request_reason、approved_by、approval_reason、status 和 decision_reason 等结构化审批事实。demo 会输出 `Operation approval records`，用于观察一次 retry approval 如何独立落盘。

阶段 15 第一版已完成：

```text
docs/28-stage-15-operation-approval-report.md
platform_operation_approval_report.py
test_platform_operation_approval_report.py
```

阶段 15 新增离线 operation approval report，不新增 HTTP endpoint 或数据库表。报告从 `OperationApprovalRecord` 汇总 total records、approved、rejected、retry operation 和 self-approval rejected 数量，并导出 `platform_operation_approval_records.csv`、`platform_operation_approval_summary.csv` 和 `platform_operation_approval_report.html`。HTML 会转义 approval 明细中的用户可控字段。

阶段 16 第一版已完成：

```text
docs/29-stage-16-console-report-views.md
platform_api_app.py
test_platform_api_app.py
```

阶段 16 把 `build_platform_operations_report()` 和 `build_operation_approval_report()` 的核心输出接入现有 `FinTech Platform Console`。页面新增 `Operations Report Summary`、`Operation Approval Summary`、`Operations Run Rows` 和 `Approval Records` 只读区块，不新增下载按钮、HTTP report endpoint 或数据库表。

阶段 17 第一版已完成：

```text
docs/30-stage-17-ledger-reconciliation-report.md
platform_ledger_reconciliation_report.py
test_platform_ledger_reconciliation_report.py
```

阶段 17 新增教学版 ledger reconciliation report。它基于 `PlatformRunSnapshot` 和 audit payload 检查 completed run 的 payment order amount、ledger posted amount、platform bank balance 和 user wallet balance 是否一致，也检查非入账状态是否没有 ledger artifacts。报告导出 `platform_ledger_reconciliation_findings.csv` 和 `platform_ledger_reconciliation_report.html`，并在 `FinTech Platform Console` 中新增 `Ledger Reconciliation Findings` 只读区块。当前仍不查询底层 `SQLiteLedger` 分录明细，也不代表真实银行流水或清算文件对账。

阶段 18 第一版已完成：

```text
docs/31-stage-18-operation-approval-state-flow.md
platform_operation_approval.py
test_platform_operation_approval.py
platform_operation_approval_report.py
test_platform_operation_approval_report.py
```

阶段 18 让 `OperationApprovalRecord` 支持 `pending / approved / rejected` 状态。pending 记录允许 `approved_by`、`approval_reason` 和 `decided_at` 为空；`approve_pending()` 和 `reject_pending()` 只允许从 pending 流转到终态；旧的 approved/rejected schema 会在 store 初始化时迁移。`OperationApprovalReportSummary` 和 console 的 `Operation Approval Summary` 现在会显示 `pending_count`。当前仍不新增 HTTP approval endpoint，也不把 retry API 改成“先 pending 审批、审批通过后再执行 retry”。

阶段 19 第一版已完成：

```text
docs/32-stage-19-operation-approval-http-endpoints.md
platform_api_app.py
test_platform_api_app.py
```

阶段 19 新增 operation approval HTTP endpoints：`GET /platform/operation-approvals`、`GET /platform/operation-approvals/{approval_id}`、`PATCH /approve` 和 `PATCH /reject`。列表接口支持按 status、operation_type 和 operation_id 筛选；approve/reject 只负责把已有 pending approval 流转到终态，并写入 `view_platform_operation_approvals` 或 `update_platform_operation_approvals` 的 API access audit。阶段 19 当时还没有创建 pending approval 的 HTTP endpoint，也不让 approve endpoint 自动执行 retry。

阶段 20 第一版已完成：

```text
docs/33-stage-20-create-operation-approval-http-endpoint.md
platform_api_app.py
test_platform_api_app.py
demo.py
```

阶段 20 新增 `POST /platform/operation-approvals`，用于通过 HTTP 创建 pending operation approval。创建接口只保存审批申请，不执行 retry；`approval_id` 重复会返回 `409 Conflict`，不会覆盖原记录；成功和失败都会写入 `create_platform_operation_approvals` API access audit。demo 的 `Pending operation approval flow` 现在通过 HTTP 完成 create、query 和 approve。当前仍不修改 failed async run retry API 的执行语义，也不让 approve endpoint 自动执行 retry。

阶段 21 第一版已完成：

```text
docs/34-stage-21-retry-approval-before-execution.md
platform_api_app.py
test_platform_api_app.py
demo.py
```

阶段 21 把 failed async run retry 改成先审批后执行：`POST /platform/async-payment-runs/{run_id}/retry` 现在只校验 failed run 并创建 pending operation approval，返回 `202 Accepted` 风格响应，不直接把 run 改成 `accepted`；`PATCH /platform/operation-approvals/{approval_id}/approve` 在审批 retry approval 时才执行 `failed -> accepted`，并写入 `retry_platform_async_run` execution access audit。console retry form 现在只创建 pending approval，不直接执行 retry。

阶段 22 第一版已完成：

```text
docs/35-stage-22-operation-approval-console-view.md
platform_api_app.py
test_platform_api_app.py
```

阶段 22 在 `FinTech Platform Console` 新增 `Pending Operation Approvals` 只读区块，展示 pending approval 的 `approval_id`、`operation_type`、`operation_id`、关联 `async_status`、申请人、申请理由和申请时间。页面 summary 也新增 `Pending approvals` 计数。当前不在 console 增加 approve/reject 按钮，也不做分页、排序、IAM、通知或 SLA。

阶段 23 第一版已完成：

```text
docs/36-stage-23-operation-approval-pagination-sorting.md
platform_operation_approval.py
platform_api_app.py
test_platform_operation_approval.py
test_platform_api_app.py
```

阶段 23 让 `GET /platform/operation-approvals` 支持 `limit`、`offset`、`sort_by` 和 `sort_order`，并返回 `pagination` 元数据。支持按 `approval_id`、`operation_type`、`operation_id`、`requested_by`、`status`、`requested_at` 和 `decided_at` 排序。`FinTech Platform Console` 的 `Pending Operation Approvals` 和 `Approval Records` 继续保持只读，但内部统一按 `requested_at desc` 取最新 5 条。当前不在 console 增加分页控件或 approve/reject 按钮。

阶段 24 第一版已完成：

```text
docs/37-stage-24-operation-approval-detail-view.md
platform_api_app.py
test_platform_api_app.py
```

阶段 24 新增 `GET /platform/operation-approvals/{approval_id}/view` 只读 HTML 详情页。页面展示 approval record 全字段；如果 `operation_id` 能匹配 async run，则展示 async run 状态、attempt、last error 和时间戳；如果 async run 已 completed，则展示最终 platform result 摘要。`FinTech Platform Console` 的 `Pending Operation Approvals` 和 `Approval Records` 现在会把 `approval_id` 渲染为详情页链接。当前仍不在详情页或 console 增加 approve/reject 按钮。

阶段 25 第一版已完成：

```text
docs/38-stage-25-operation-approval-lifecycle.md
platform_operation_approval.py
platform_operation_approval_report.py
platform_api_app.py
demo.py
test_platform_operation_approval.py
test_platform_operation_approval_report.py
test_platform_api_app.py
```

阶段 25 让 operation approval record 支持 `cancelled` 和 `expired` 终态，并新增 `PATCH /platform/operation-approvals/{approval_id}/cancel` 与 `PATCH /platform/operation-approvals/{approval_id}/expire`。两种状态都只能从 `pending` 流转，流转后不能再 approve/reject，也不会执行 retry。`OperationApprovalReportSummary` 和 `FinTech Platform Console` 新增 cancelled / expired approval 计数。当前仍不做自动定时过期任务、真实 SLA、通知、IAM 或 console 操作按钮。

阶段 26 第一版已完成：

```text
docs/39-stage-26-console-approval-actions.md
platform_api_app.py
test_platform_api_app.py
```

阶段 26 在 `FinTech Platform Console` 的 `Pending Operation Approvals` 表格中新增 approve / reject 表单，并新增 `POST /platform/operation-approvals/{approval_id}/approve-form` 与 `POST /platform/operation-approvals/{approval_id}/reject-form` 作为浏览器表单适配层。表单要求 `decided_by`、`decision_reason`、`decided_at` 和 confirmation；成功或失败都会回到 console 并显示反馈。JSON API 和 form endpoint 复用同一套内部 approve/reject 逻辑，因此 approve retry approval 仍会执行 `failed -> accepted`，reject 不会执行 retry。当前仍不做 cancel / expire 表单、真实 IAM、登录、CSRF、批量审批、认领、锁定、通知或 SLA。

阶段 27 第一版已完成：

```text
docs/40-stage-27-approval-lifecycle-timeline.md
platform_api_app.py
test_platform_api_app.py
```

阶段 27 在 `GET /platform/operation-approvals/{approval_id}/view` 只读详情页新增 `Lifecycle Timeline` 区块，按时间展示 `approval_requested`、`approval_decided` 和匹配 `approval_id=...` 的 `retry_execution` access audit。该区块用于解释一条 approval 从申请、决策到 retry execution 的轨迹；当前仍不新增数据库表、单独 timeline endpoint、详情页操作按钮、真实 IAM、登录、session 或 CSRF。

阶段 28 第一版已完成：

```text
docs/41-stage-28-async-platform-detail-views.md
platform_api_app.py
test_platform_api_app.py
```

阶段 28 新增 `GET /platform/async-payment-runs/{run_id}/view` 和 `GET /platform/payment-runs/{run_id}/view` 两个只读 HTML 详情页。async run detail 展示 async run 状态、request payload 和 platform result summary；payment run detail 展示 platform result、关联 async run 和 customer audit timeline。`FinTech Platform Console` 的 recent payment runs、recent async runs、failed async runs，以及 operation approval detail view 的关联 run 字段现在都可以继续链接到对应详情页。当前仍不新增数据库表、业务状态、操作按钮、真实 IAM、登录、session 或 CSRF。

阶段 29 第一版已完成：

```text
docs/42-stage-29-operation-approval-pagination-metadata.md
platform_operation_approval.py
platform_api_app.py
test_platform_operation_approval.py
test_platform_api_app.py
```

阶段 29 让 `SQLiteOperationApprovalStore` 新增 `count_records()`，并让 `GET /platform/operation-approvals` 的 `pagination` 响应新增 `total_count`、`has_next_page` 和 `next_offset`。这些字段复用当前 `status`、`operation_type`、`operation_id` 筛选条件，用于说明当前页是否只是筛选结果的一部分。当前仍不改成 cursor pagination，不新增 console 分页控件，也不改变已有 `limit` / `offset` / `sort_by` / `sort_order` 语义。

阶段 30 第一版已完成：

```text
docs/43-stage-30-console-cancel-expire-actions.md
platform_api_app.py
test_platform_api_app.py
```

阶段 30 把阶段 25 已有的 cancel / expire 生命周期动作接入 `FinTech Platform Console` 的 `Pending Operation Approvals` 表格。FastAPI 新增 `POST /platform/operation-approvals/{approval_id}/cancel-form` 和 `/expire-form` 浏览器表单适配层，并让 JSON cancel / expire endpoint 与 form endpoint 复用 `_cancel_operation_approval()` / `_expire_operation_approval()` helper。pending approval 现在可在 console 中流转到 approved / rejected / cancelled / expired；cancel / expire 只改变 approval 终态，不执行 retry。当前仍不做真实 IAM、登录、CSRF、批量操作、自动过期任务、通知、SLA、认领或锁定。

阶段 31 第一版已完成：

```text
docs/44-stage-31-console-filter-controls.md
platform_api_app.py
test_platform_api_app.py
```

阶段 31 在 `GET /platform/view` 新增 `payment_status`、`async_status` 和 `operation_approval_status` 三个查询参数，并在页面顶部新增原生 HTML GET 筛选表单。筛选会影响 Recent Payment Runs、Recent Async Runs、Failed Async Runs、Operations Report Summary、Operations Run Rows、Ledger Reconciliation Findings、Operation Approval Summary、Pending Operation Approvals 和 Approval Records。未知筛选值会在页面顶部提示并被忽略。当前仍不做复杂搜索、日期范围、actor 筛选、多选筛选、cursor pagination、真实 IAM、登录、session 或 CSRF。

阶段 32 第一版已完成：

```text
docs/45-stage-32-payment-detail-reconciliation-context.md
platform_api_app.py
test_platform_api_app.py
```

阶段 32 在 `GET /platform/payment-runs/{run_id}/view` 新增 `Ledger Reconciliation Context` 只读区块。该区块复用 `evaluate_platform_ledger_reconciliation()`，展示当前 run 的 `check_id`、`status`、`severity` 和 `message`，让单个 payment run 详情页能直接解释 payment order amount、ledger posted amount、余额快照和 audit evidence 是否互相吻合。当前仍不新增数据库表、新 reconciliation 规则、单独 endpoint、下载按钮、底层 ledger 分录查询、真实银行流水或清算文件对账。

阶段 33 第一版已完成：

```text
docs/46-stage-33-remaining-roadmap.md
```

阶段 33 不改业务代码，重新总结当前平台能力、和更完整教学版平台的差距，以及后续剩余章节。阶段 33 当时建议从阶段 34 开始按 `6 个建设章节 + 1 个最终验收章节` 推进：运营 Console 和工作流补强、身份权限和表单安全、一致性并发和恢复、外部支付清结算和真实对账模型、合规证据和留存治理、可运行交付和观测，最后做最终验收与学习作品集总结。

阶段 34 第一版已完成：

```text
docs/47-stage-34-console-workflow-controls.md
platform_api_app.py
test_platform_api_app.py
```

阶段 34 在现有 `GET /platform/view` 上新增 `actor`、`created_from` 和 `created_to` 筛选，并让筛选影响 payment runs、async runs、operations report、ledger reconciliation、operation approval summary、pending approvals 和 approval records。pending approval 区块新增高影响操作风险提示，operation approval、async run 和 payment run 详情页新增 `Back to Console` 返回入口。当前仍不做真实 IAM、登录、session、CSRF、批量操作或复杂工单工作流；阶段 34 当时建议下一步进入阶段 35：身份、权限和表单安全边界。

阶段 35 第一版已完成：

```text
docs/48-stage-35-identity-permission-form-security.md
platform_api_app.py
test_platform_api_app.py
```

阶段 35 新增教学版 `PlatformIdentityContext`，支持从 `x-actor-id` 和可选 `x-actor-role` 构造身份上下文，并在未显式传 role 时按样例 actor 前缀推断角色。`PERMISSIONS_BY_ROLE` 定义了本地 role / permission policy，`_require_permission()` 会对敏感查询和 operation approval 创建、查询、更新路径做权限校验；`_require_identity_actor_matches()` 会拒绝 JSON 审批更新中 `x-actor-id` 和 `decided_by` 不一致的请求。权限拒绝和身份不一致都会写入 denied access audit。当前仍不做真实登录、session、token、企业 IAM、CSRF token 或按角色脱敏；下一步建议进入阶段 36：一致性、并发和恢复。

阶段 36 第一版已完成：

```text
docs/49-stage-36-consistency-concurrency-recovery.md
platform_async_service.py
platform_operation_approval.py
test_platform_async_service.py
test_platform_operation_approval.py
test_platform_api_app.py
```

阶段 36 补强了教学平台的一致性、并发和恢复边界：`SQLitePlatformAsyncRunStore.claim_next_accepted()` 会用状态条件把 accepted run 原子认领为 processing，`PlatformAsyncWorker.process_next()` 改为先 claim 再处理；`SQLiteOperationApprovalStore` 的 approve / reject / cancel / expire 决策改为通过 `WHERE status = 'pending'` 的条件更新消费 pending approval。测试覆盖两个连接重复 claim 同一条 async run、两个连接重复决策同一条 approval，以及 API 层重复 approve retry 只执行一次 retry execution audit。当前仍不做生产级分布式锁、lease timeout scanner、saga/workflow engine、版本化 migration 框架或自动 backup / restore；下一步建议进入阶段 37：外部支付、清结算和真实对账模型。

阶段 37 第一版已完成：

```text
docs/50-stage-37-external-settlement-reconciliation.md
platform_settlement_reconciliation_report.py
test_platform_settlement_reconciliation_report.py
demo.py
```

阶段 37 新增教学版外部 settlement reconciliation：`ProviderSettlementRow` 表示外部 provider settlement file 的一行，`evaluate_platform_settlement_reconciliation()` 会检查内部 completed run 是否有外部 settled row、外部金额和币种是否匹配内部 payment audit payload、非 completed 内部 run 是否错误出现在外部 settlement file 中，以及外部 row 是否能映射回内部 run。`export_platform_settlement_reconciliation_report()` 可导出 CSV/HTML；demo 已接入 `provider_settlement_sample.csv -> parse_provider_settlement_csv() -> Exported platform settlement reconciliation reports`。当前仍不接真实 payment provider、webhook、卡组织清算、银行流水、多币种 FX 或任何监管结论。

阶段 40 后补充了更明确的 provider boundary 教学实现：`platform_payment_provider.py` 支持教学版 provider intent link、HMAC-SHA256 webhook signature、timestamp tolerance / replay window、event_id 幂等去重、provider status 到 internal status 映射，以及 settlement CSV parser；demo 会导出 `provider_payment_intents.csv`，展示 `provider_intent_id -> internal_run_id -> payment_order_id` 的映射；`platform_api_app.py` 新增 `POST /platform/provider-webhooks`，会对 signed webhook payload 做验签、时间窗口检查、事件去重、状态映射和 access audit；`platform_evidence_package.py` 会把 provider webhook 的 granted / duplicate / denied 处理结果打包成 `provider_webhook_event` evidence item。当前这些规则是教学版协议，不代表 Stripe、PayPal、Visa、银行或清算机构的真实接口规范；如后续引用真实 provider API、签名 header、时间窗口或 settlement file 格式，必须查证官方或专业来源。

阶段 38 第一版已完成：

```text
docs/51-stage-38-evidence-retention-governance.md
platform_evidence_package.py
test_platform_evidence_package.py
demo.py
```

阶段 38 新增教学版 evidence package：`build_platform_evidence_package()` 会把 failed settlement reconciliation findings、access anomaly findings、operation approval records、provider webhook events 和 denied access events 汇总为统一 `PlatformEvidenceItem`，并用 `case_id`、`generated_by`、`legal_hold` 和 `retention_policy_id` 作为包级元数据。`export_platform_evidence_package()` 可导出 evidence items CSV、summary CSV 和 HTML；demo 已接入 `Exported platform evidence package`。当前仍不做真实法律保全、真实留存期限、WORM 存储、电子签名、附件哈希或 custody 流程；随后阶段 39 已进入可运行交付、观测和测试矩阵。

阶段 39 第一版已完成：

```text
docs/52-stage-39-operability-observability-test-matrix.md
platform_operability.py
test_platform_operability.py
platform_api_app.py
test_platform_api_app.py
demo.py
```

阶段 39 新增教学版 operability 边界：`build_platform_readiness_report()` 会检查 platform store、access audit store、async run store、investigation case store 和 operation approval store 是否可打开；`build_platform_metrics_snapshot()` 会汇总 payment runs、async runs、operation approvals、access events 和 investigation cases 的结构化计数；`build_platform_test_matrix()` 会列出本地 py_compile、平台测试、demo 和全量 labs 测试矩阵。FastAPI 已新增 `/platform/operability/readiness`、`/platform/operability/metrics` 和 `/platform/operability/test-matrix`，并写入 granted / denied access audit；demo 已接入 `Platform operability snapshot`。当前仍不做真实部署平台、生产监控、Prometheus/OpenTelemetry、SLO/SLA、告警或 secret 管理；随后阶段 40 已进入最终验收与学习作品集总结。

阶段 40 第一版已完成：

```text
docs/53-stage-40-final-acceptance-and-portfolio.md
```

阶段 40 不新增业务代码，重点把当前平台作为学习作品集做收口：总结主业务、异步任务、运营控制台、审批工作流、报表对账、证据包和 operability；列出本地验收命令；记录当前验证结果；明确仍不覆盖真实支付通道、真实监管合规、真实 IAM、真实部署、生产监控、secret 管理和法律/税务/会计/合规建议。后续如继续扩展，建议按真实外部接口模拟、生产化基础设施、身份权限、数据治理或作品集包装这些大章节推进。
