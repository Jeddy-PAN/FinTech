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
12. 下一步可以做阶段 8 小结和端到端验收清单，确认这个学习作品覆盖了哪些金融系统工程能力，以及后续是否进入 API 服务化或前端化。

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
```

demo 还会输出 `Risk review completion`，用于观察 `risk_review_required -> completed` 的人工复核通过闭环。

demo 还会写入并重新读取：

```text
labs/fintech-platform/.test-data/demo_platform_runs.db
labs/fintech-platform/.test-data/demo_platform_access_audit.db
labs/fintech-platform/.test-data/demo_platform_investigation_cases.db
labs/fintech-platform/.test-data/demo_platform_api_investigation_cases.db
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform
```

## 当前状态

这个目录已经包含第一版综合平台设计、最小 orchestration、demo、综合报表导出、SQLite 持久化、历史运行报表、risk review 后续处理、教学版一致性检查、平台报表访问控制与访问审计、平台访问异常检测、平台访问异常调查工单，以及测试。阶段 8 的目标仍然是把已有实验组合成一个清晰的学习平台，而不是立即扩成生产级系统。

阶段 9 已经开始在这个目录上做 API 服务化的第一步：

```text
platform_api_service.py
platform_api_app.py
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

页面标题是 `FinTech Platform Console`，只读展示 payment runs、API access anomalies、investigation cases 和 recent API access events。它不引入单独前端项目、模板框架、登录态或真实 IAM；访问查看页本身会记录 `view_platform_console` access audit，用来观察运营查看动作也应进入审计轨迹。

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
