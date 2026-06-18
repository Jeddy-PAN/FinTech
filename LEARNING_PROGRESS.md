# Learning Progress

最后更新：2026-06-18

## 当前状态

- 学习者背景：程序员，金融和 FinTech 目前按零基础处理。
- 当前阶段：阶段 40 后已完成前端 Console / Manual 体验改造、Playwright 小型浏览器回归、结构命名复盘、FinTech 知识地图复盘、本地验证脚本整理和 Mermaid 图集初版，当前进入后续大章节选择。
- 当前主线：把账本、支付订单、风控规则引擎、KYC/AML 开户筛查和合规审计串成一个最小端到端学习项目，并把这条链路放到 API service 和异步 worker 边界后面，理解外部请求、幂等、状态查询、后台处理、retry、audit trail、报表和调查工单如何协同。
- 当前仓库状态：已完成账本基础实验、支付订单实验、交易流水分析实验、投资组合分析实验、风控规则引擎实验、KYC/AML 开户筛查实验、合规审计实验、阶段 7 到阶段 40 的综合平台建设与最终验收；阶段 40 后已完成前端体验改造，顶部导航收敛为 `Console` / `Manual` 两个主入口，Manual 支持 CN/EN 切换并提供详细事件流程图；已新增 Playwright 小型浏览器回归，覆盖 Console/Manual 导航、Manual CN/EN 切换和网页端 retry approval -> approve 流程。当前复盘结论：仓库结构总体稳定，后续避免新增细碎阶段文档，优先维护根 `README.md`、`docs/README.md`、`labs/fintech-platform/README.md` 和本进度文件；代码整理优先对 `labs/fintech-platform` 做低风险拆分，Manual view 已拆到 `platform_api_manual_views.py`，Console 纯 view helper 已拆到 `platform_api_console_views.py`，详情页渲染已拆到 `platform_api_detail_views.py`，详情页测试已拆到 `test_platform_api_detail_views.py`，Console 只读渲染和筛选测试已拆到 `test_platform_api_console.py`，Console 表单动作测试已拆到 `test_platform_api_console_actions.py`，API / Console / Detail view 测试共用 helper 已抽到 `test_platform_api_helpers.py`，operation approval JSON endpoint 测试已拆到 `test_platform_api_operation_approvals.py`，async / retry JSON endpoint 测试已拆到 `test_platform_api_async_runs.py`，payment run 基础 API 测试已拆到 `test_platform_api_payment_runs.py`。后续结构整理基本进入收尾：建议保留 `test_platform_api_app.py` 作为 health / access audit / manual / operability smoke 入口，不再继续拆得过碎。知识覆盖复盘已新增 `docs/54-fintech-knowledge-map-and-gap-analysis.md`：当前理论主线适合作为工程学习作品集，但还不是完整金融理论教材；已新增 `scripts/verify_labs.ps1` 标准化本地验证入口；已新增 `docs/diagrams/` Mermaid 图集初版，帮助从系统结构、外部 provider 边界、payment run 生命周期和对账证据链理解平台；后续优先考虑外部 payment provider / webhook / settlement parser、核心银行账户和信贷生命周期等大章节。

## 学习原则

1. 先掌握一个金融概念，再写一个最小代码实验。
2. 每个概念尽量回答三个问题：它是什么、金融系统为什么需要它、程序员实现时要注意什么。
3. 遇到监管、市场数据、API、产品规则、认证考试等时效性内容，必须使用官方或专业来源查证。
4. 不做投资建议；本仓库仅用于学习金融科技和软件工程实践。
5. 文档类学习资料使用中文和 UTF-8；脚本、命令行输出、测试样例中的用户可见文本、未来前端 UI 文案使用英文。
6. Python 环境优先使用 Anaconda / conda 管理。

## 已完成

- 建立仓库入口：`README.md`
- 建立后续 AI 协作规则：`AGENTS.md`
- 建立学习进度文件：`LEARNING_PROGRESS.md`
- 建立权威资料索引：`docs/00-authoritative-sources.md`
- 建立 FinTech 基础概览：`docs/01-fintech-overview.md`
- 建立程序员转金融领域技能图谱：`docs/02-developer-to-finance.md`
- 建立账本基础笔记：`docs/03-ledger-basics.md`
- 实现第一个内存版双分录账本：`labs/ledger-basics/`
- 添加账本测试：`labs/ledger-basics/test_ledger.py`
- 新增 conda 环境配置：`environment.yml`
- 建立账本持久化笔记：`docs/04-ledger-persistence.md`
- 实现 SQLite 持久化账本：`labs/ledger-basics/sqlite_ledger.py`
- 添加 SQLite 账本测试：`labs/ledger-basics/test_sqlite_ledger.py`
- 建立幂等性笔记：`docs/05-idempotency.md`
- 内存版和 SQLite 版账本均支持 `idempotency_key`
- 建立请求指纹笔记：`docs/06-request-fingerprint.md`
- 内存版和 SQLite 版账本均支持 `request_fingerprint`
- 建立支付订单系统笔记：`docs/07-payment-order-system.md`
- 实现最小支付订单系统：`labs/payment-orders/`
- 添加支付订单测试：`labs/payment-orders/test_payment_orders.py`
- 建立退款和冲正笔记：`docs/08-refunds-and-reversals.md`
- 支付订单系统支持 `refunded` 状态和退款反向账本分录
- 建立支付订单持久化笔记：`docs/09-payment-order-persistence.md`
- 实现 SQLite 持久化支付订单系统：`labs/payment-orders/sqlite_payment_orders.py`
- 添加 SQLite 支付订单测试：`labs/payment-orders/test_sqlite_payment_orders.py`
- 建立 transactional outbox 笔记：`docs/10-transactional-outbox.md`
- SQLite 支付订单系统支持 `payment_outbox` 表和 pending/published 状态
- 建立 outbox publisher 笔记：`docs/11-outbox-publisher.md`
- SQLite 支付订单系统支持 `publish_pending_outbox_messages()`
- 建立交易流水分析笔记：`docs/12-transaction-statement-analysis.md`
- 实现交易流水 CSV 导入、SQLite 存储、分类和月度现金流分析：`labs/transaction-analysis/`
- 添加交易流水分析测试：`labs/transaction-analysis/test_transaction_analysis.py`
- 交易流水分析支持按类别的月度支出矩阵和预算对比
- 交易流水分析支持 HTML 报告和 CSV 导出：`labs/transaction-analysis/reporting.py`
- 交易流水分析支持从 `category_rules.csv` 读取可配置分类规则
- 建立投资组合分析笔记：`docs/13-portfolio-analysis.md`
- 实现投资组合收益率、年化波动率和最大回撤实验：`labs/portfolio-analysis/`
- 添加投资组合分析测试：`labs/portfolio-analysis/test_portfolio_analysis.py`
- 投资组合分析支持相关性矩阵、协方差矩阵和基于协方差的组合波动率
- 投资组合分析支持基于当前持仓、最新价格和目标权重计算再平衡交易
- 投资组合分析支持 HTML 报告和 CSV 导出：`labs/portfolio-analysis/portfolio_reporting.py`
- 建立风控规则引擎笔记：`docs/14-risk-rule-engine.md`
- 实现最小风控规则引擎：`labs/risk-rule-engine/`
- 添加风控规则引擎测试：`labs/risk-rule-engine/test_risk_rule_engine.py`
- 风控规则引擎支持从 `risk_rules.json` 读取阈值和允许币种配置
- 风控规则引擎支持为 `review` 决策创建人工复核案例，并流转 `pending_review -> approved / rejected`
- 风控规则引擎支持使用 SQLite 保存风控决策、规则命中和人工审核案例：`labs/risk-rule-engine/sqlite_risk_store.py`
- 风控规则引擎支持追加式审计事件：`risk_decision.saved`、`review_case.created`、`review_case.approved/rejected`
- 风控规则引擎支持保存规则版本，并让风控决策关联 `rule_version_id`
- 风控规则引擎支持非金额风险信号：`device_id`、`ip_country`、`beneficiary_id`
- 风控规则引擎支持规则分值和总风险分数 `risk_score`
- 风控规则引擎支持纯评分策略：`unusual_hour` 和 `round_amount` 作为弱风险信号，多个弱信号累计达到阈值后进入 `review`
- 风控规则引擎支持规则命中统计报表：决策状态、规则命中次数、风险分数和审核状态，并可按规则版本和决策时间窗口筛选
- 风控规则引擎支持规则版本对比报表：比较两个规则版本的决策状态、规则命中、风险分数和审核状态差异
- 风控规则引擎支持导出 CSV 和 HTML 报表：`labs/risk-rule-engine/risk_report_export.py`
- 建立 KYC/AML 开户筛查笔记：`docs/15-kyc-aml-onboarding.md`
- 实现最小 KYC/AML 开户筛查实验：`labs/kyc-aml-onboarding/`
- 添加 KYC/AML 开户筛查测试：`labs/kyc-aml-onboarding/test_kyc_aml.py`
- KYC/AML 开户筛查支持个人和法人客户资料检查、beneficial owner 检查、教学版 watchlist screening、模糊匹配、风险评分和可解释决策
- KYC/AML 开户筛查支持为 `review` 决策创建人工复核案例，并流转 `pending_review -> approved / rejected / request_more_info`
- KYC/AML 开户筛查支持使用 SQLite 保存客户申请、beneficial owner、KYC/AML 决策、检查结果和审核案例：`labs/kyc-aml-onboarding/sqlite_kyc_store.py`
- KYC/AML 开户筛查支持追加式审计事件：`kyc_application.saved`、`kyc_decision.saved`、`kyc_review_case.created`、`kyc_review_case.approved/rejected/request_more_info`
- KYC/AML 开户筛查支持汇总报表：客户类型、决策状态、检查命中次数、风险分数和审核状态，并可按客户类型、决策状态、提交时间窗口和决策时间窗口筛选：`labs/kyc-aml-onboarding/kyc_reporting.py`
- KYC/AML 开户筛查支持导出 CSV 和 HTML 报表：`labs/kyc-aml-onboarding/kyc_report_export.py`
- KYC/AML 开户筛查支持保存 watchlist 数据版本，并让 KYC/AML 决策关联 `watchlist_version_id`
- KYC/AML 开户筛查支持保存策略版本，并让 KYC/AML 决策关联 `policy_version_id`
- KYC/AML 开户筛查支持 watchlist/policy 版本对比报表，比较已保存版本下的决策状态、检查命中、风险分数和审核状态差异
- KYC/AML 开户筛查支持 replay 报表，用新的样例 watchlist 或 policy 重新评估已保存申请，并逐客户比较原决策和重放决策
- KYC/AML 开户筛查支持保存 replay run、逐客户 replay 明细和 `pending_review -> approved / rejected` 审批结论，并记录 replay run 审计事件
- 建立合规与审计笔记：`docs/16-compliance-audit.md`
- 实现最小合规审计时间线实验：`labs/compliance-audit/`
- 合规审计实验支持合并风控和 KYC/AML 审计事件、按字段筛选、构造主体时间线、汇总事件数量、教学版 payload 脱敏、CSV/HTML 报表导出、角色权限控制、访问审计记录、访问审计 SQLite 持久化、审计报告导出审批、审计留存策略报告、访问异常检测、异常访问报告导出、留存报告导出、访问异常调查工单状态、工单 SQLite 持久化、调查工单报告导出和工单处理动作审计
- 建立阶段 7 总结与阶段 8 规划文档：`docs/17-stage-7-summary-and-stage-8-plan.md`
- 建立阶段 8 总结与验收清单：`docs/18-stage-8-summary-and-acceptance.md`
- 建立端到端 FinTech 工程作品设计：`labs/fintech-platform/README.md`
- 实现端到端 FinTech 最小 orchestration：`labs/fintech-platform/fintech_platform.py`
- 新增端到端 FinTech demo 和测试：`labs/fintech-platform/demo.py`、`labs/fintech-platform/test_fintech_platform.py`
- 新增端到端 FinTech 综合报表导出：`labs/fintech-platform/platform_report_export.py`
- 新增端到端 FinTech SQLite 持久化：`labs/fintech-platform/sqlite_platform_store.py`
- 新增端到端 FinTech 历史运行报表：`labs/fintech-platform/platform_history_report_export.py`
- 端到端 FinTech 综合平台支持 risk review 后续处理：人工通过后支付成功并入账，人工拒绝后支付失败且不入账
- 新增端到端 FinTech 一致性检查报表：`labs/fintech-platform/platform_consistency_report.py`
- 新增端到端 FinTech 平台报表访问控制和访问审计：`labs/fintech-platform/platform_report_access.py`
- 新增端到端 FinTech 平台访问异常检测和报告导出：`labs/fintech-platform/platform_access_anomaly_report.py`
- 新增端到端 FinTech 平台访问异常调查工单：`labs/fintech-platform/platform_investigation_cases.py`
- 建立阶段 9 平台 API 服务化计划：`docs/19-stage-9-platform-api-plan.md`
- 新增端到端 FinTech 平台 API service 边界：`labs/fintech-platform/platform_api_service.py`
- 新增端到端 FinTech 平台 FastAPI 路由层：`labs/fintech-platform/platform_api_app.py`
- 新增端到端 FinTech 平台 API 访问审计：FastAPI 路由会把 health、创建 payment run、查询 payment run、列出 runs 和查询 API access events 写入 `SQLiteAccessAuditStore`
- 新增端到端 FinTech 平台 API 访问异常检测：`labs/fintech-platform/platform_api_access_anomaly_report.py` 只分析 `fintech_platform_api_` 目标，并导出 API access anomaly CSV/HTML 报告
- 新增端到端 FinTech 平台 API 访问异常调查工单：`labs/fintech-platform/platform_api_investigation_cases.py` 把 API access anomaly finding 转成 investigation case，并导出 API 专用工单 CSV/HTML 报告
- 新增端到端 FinTech 平台 API 工单 HTTP 查询接口：`platform_api_app.py` 支持列出 API access anomaly findings、从 findings 开工单、按状态/actor/assignee 查询 API investigation cases 和查询单个 case
- 新增端到端 FinTech 平台 API 工单状态流转 HTTP 接口：`platform_api_app.py` 支持 start、resolve 和 false-positive，并继续记录接口访问审计
- 新增阶段 9 最小前端查看页：`platform_api_app.py` 支持 `GET /`、`GET /platform` 和 `GET /platform/view`，渲染 `FinTech Platform Console`，只读展示 payment runs、API access anomalies、investigation cases 和 recent API access events，并记录 `view_platform_console` 访问审计
- 建立阶段 9 总结与阶段 10 路线：`docs/20-stage-9-summary-and-stage-10-plan.md`
- 建立阶段 10 事件驱动与异步任务设计：`docs/21-stage-10-event-driven-async-plan.md`
- 新增阶段 10 最小 async run store：`labs/fintech-platform/platform_async_service.py`
- 新增阶段 10 最小 async worker：`PlatformAsyncWorker`
- 新增阶段 10 FastAPI async endpoints：创建 async run、查询 async run、按状态列表和教学版 worker 触发
- 新增阶段 10 demo 展示：通过 FastAPI 创建 async run、触发 worker、查询最终 platform result 和 API access audit
- 建立阶段 10 总结与验收清单：`docs/22-stage-10-summary-and-acceptance.md`
- 建立阶段 11 运营控制台增强设计：`docs/23-stage-11-operations-console-plan.md`
- 新增阶段 11 最小运营控制台 async run 展示：`platform_api_app.py` 的 `FinTech Platform Console` 会展示 async run summary、recent async runs、failed async runs，并把 completed async run 关联到最终 platform result
- 新增阶段 11 failed async run demo 样例：`demo.py` 通过真实 API 流程构造 request fingerprint 冲突导致的 failed async run，并确认 console 可展示 failed run、attempt count 和 last error
- 新增阶段 11B failed async run retry 设计：`docs/24-stage-11b-retry-failed-async-run-design.md`
- 新增阶段 11B failed async run retry API：`POST /platform/async-payment-runs/{run_id}/retry` 支持把 `failed` async run 重新放回 `accepted`，要求 actor、reason 和 confirmation，并记录成功/失败 API access audit
- 新增阶段 11C 控制台 failed async run retry form：Failed Async Runs 区域可提交 actor、reason 和 confirmation，成功/失败复用 retry API access audit，成功后 run 回到 `accepted` 且不直接触发 worker
- 完成阶段 11 收尾总结：`docs/23-stage-11-operations-console-plan.md` 已合并运营控制台实现进度、验收清单、工程结论、文档整理约定和阶段 12 候选方向
- 新增阶段 12 操作审计与审批边界计划：`docs/25-stage-12-operation-approval-boundary.md`
- 新增阶段 12 failed async run retry 二人审批：JSON API 和控制台 form 要求 `approved_by`、`approval_reason` 和 `approval_confirmation`，并拒绝 self-approval
- 新增阶段 13 运行报告与对账视角：`docs/26-stage-13-operations-reconciliation-report.md`
- 新增阶段 13 operations report：`labs/fintech-platform/platform_operations_report.py`
- 新增阶段 13 operations report 测试：`labs/fintech-platform/test_platform_operations_report.py`
- 新增 docs 入口和平台能力地图：`docs/README.md`
- 压缩根 README 的超长学习顺序，改为快速阅读路径并链接到 `docs/README.md`
- 新增阶段 14 独立 operation approval record 文档：`docs/27-stage-14-operation-approval-record.md`
- 新增 operation approval store：`labs/fintech-platform/platform_operation_approval.py`
- 新增 operation approval store 测试：`labs/fintech-platform/test_platform_operation_approval.py`
- 权威资料索引新增 FinCEN 和 OFAC：`docs/00-authoritative-sources.md`
- 新增阶段 15 operation approval report 文档：`docs/28-stage-15-operation-approval-report.md`
- 新增 operation approval report：`labs/fintech-platform/platform_operation_approval_report.py`
- 新增 operation approval report 测试：`labs/fintech-platform/test_platform_operation_approval_report.py`
- 新增阶段 16 console report views 文档：`docs/29-stage-16-console-report-views.md`
- `FinTech Platform Console` 新增 operations report summary、operation approval summary、operations run rows 和 approval records 只读区块
- 新增阶段 17 ledger reconciliation report 文档：`docs/30-stage-17-ledger-reconciliation-report.md`
- 新增端到端 FinTech 平台 ledger reconciliation report：`labs/fintech-platform/platform_ledger_reconciliation_report.py`
- `FinTech Platform Console` 新增 ledger reconciliation findings 只读区块
- 新增阶段 18 operation approval state flow 文档：`docs/31-stage-18-operation-approval-state-flow.md`
- operation approval record 支持 pending / approved / rejected 状态流转
- operation approval report 和 console summary 新增 `pending_count`
- 新增阶段 19 operation approval HTTP endpoints 文档：`docs/32-stage-19-operation-approval-http-endpoints.md`
- FastAPI 支持查询 operation approvals、查询单条 approval、approve pending 和 reject pending
- operation approval HTTP endpoint 会写入 granted / denied API access audit
- 新增阶段 20 create operation approval HTTP endpoint 文档：`docs/33-stage-20-create-operation-approval-http-endpoint.md`
- FastAPI 支持通过 `POST /platform/operation-approvals` 创建 pending operation approval
- create operation approval endpoint 会对重复 `approval_id` 返回 409，并写入 granted / denied API access audit
- 新增阶段 21 retry approval before execution 文档：`docs/34-stage-21-retry-approval-before-execution.md`
- failed async run retry endpoint 现在只创建 pending approval，approve approval 后才执行 `failed -> accepted`
- console retry form 现在只创建 pending approval，不直接执行 retry
- 新增阶段 22 operation approval console view 文档：`docs/35-stage-22-operation-approval-console-view.md`
- `FinTech Platform Console` 新增 `Pending Operation Approvals` 只读区块，展示 pending approval 及其关联 async status
- 新增阶段 23 operation approval pagination and sorting 文档：`docs/36-stage-23-operation-approval-pagination-sorting.md`
- operation approval 查询支持 `limit`、`offset`、`sort_by` 和 `sort_order`，console approval 表格统一按 `requested_at desc` 取最新记录
- 新增阶段 24 operation approval detail view 文档：`docs/37-stage-24-operation-approval-detail-view.md`
- operation approval 支持只读 HTML 详情页，展示 approval record、关联 async run 和 completed platform result 摘要
- 新增阶段 25 operation approval lifecycle 文档：`docs/38-stage-25-operation-approval-lifecycle.md`
- operation approval record 支持 cancelled / expired 终态，并通过 HTTP endpoint、report、console summary 和 demo 展示
- 新增阶段 26 console approval actions 文档：`docs/39-stage-26-console-approval-actions.md`
- `FinTech Platform Console` 的 pending approval 行支持 approve / reject 表单，并复用 JSON API 的审批与 retry execution 边界
- 新增阶段 27 approval lifecycle timeline 文档：`docs/40-stage-27-approval-lifecycle-timeline.md`
- operation approval 只读详情页新增 `Lifecycle Timeline`，按时间展示 approval request、decision 和 retry execution audit
- 新增阶段 28 async run / platform result detail views 文档：`docs/41-stage-28-async-platform-detail-views.md`
- FastAPI 新增 async run 和 platform result 只读 HTML 详情页，并从 console / approval detail 链接进入
- 新增阶段 29 operation approval pagination metadata 文档：`docs/42-stage-29-operation-approval-pagination-metadata.md`
- operation approval 查询 pagination 响应新增 `total_count`、`has_next_page` 和 `next_offset`
- 新增阶段 30 console cancel / expire approval actions 文档：`docs/43-stage-30-console-cancel-expire-actions.md`
- `FinTech Platform Console` 的 pending approval 行支持 cancel / expire 表单，并复用 JSON API 的 lifecycle transition 与 access audit 边界
- 新增阶段 31 console filter controls 文档：`docs/44-stage-31-console-filter-controls.md`
- `FinTech Platform Console` 支持按 payment status、async status 和 approval status 筛选页面展示
- 新增阶段 32 payment detail reconciliation context 文档：`docs/45-stage-32-payment-detail-reconciliation-context.md`
- payment run 详情页新增 `Ledger Reconciliation Context`，复用 ledger reconciliation report 检查语义
- 新增阶段 33 remaining roadmap 文档：`docs/46-stage-33-remaining-roadmap.md`
- 阶段 33 当时建议从阶段 34 开始按 `6 个建设章节 + 1 个最终验收章节` 推进：运营 Console 和工作流补强、身份权限和表单安全、一致性并发和恢复、外部支付清结算和真实对账模型、合规证据和留存治理、可运行交付和观测，最后做最终验收与学习作品集总结
- 新增阶段 34 console workflow controls 文档：`docs/47-stage-34-console-workflow-controls.md`
- `FinTech Platform Console` 支持按 actor 和日期范围筛选 payment / async / approval 相关展示，pending approval 区块新增高影响操作风险提示，operation approval / async run / payment run 详情页新增返回 console 的入口
- 新增阶段 35 identity / permission / form security 文档：`docs/48-stage-35-identity-permission-form-security.md`
- FastAPI app 新增教学版 `PlatformIdentityContext`、`PERMISSIONS_BY_ROLE`、`_require_permission()` 和 `_require_identity_actor_matches()`；access audit 查询和 operation approval 创建、查询、更新路径会执行权限校验，权限拒绝和身份不一致会写入 denied access audit
- 新增阶段 36 consistency / concurrency / recovery 文档：`docs/49-stage-36-consistency-concurrency-recovery.md`
- async worker 新增 `claim_next_accepted()` 认领边界，operation approval 终态决策使用 pending 状态条件更新，并补充重复 claim / 重复 retry approve 冲突测试
- 新增阶段 37 external settlement reconciliation 文档：`docs/50-stage-37-external-settlement-reconciliation.md`
- 新增 `platform_settlement_reconciliation_report.py`，用教学版 `ProviderSettlementRow` 检查内部 completed run 与外部 provider settlement row 是否一致
- 新增阶段 38 evidence / retention governance 文档：`docs/51-stage-38-evidence-retention-governance.md`
- 新增 `platform_evidence_package.py`，把 settlement reconciliation、access anomaly、operation approval 和 denied access events 组织成教学版 evidence package
- 新增阶段 39 operability / observability / test matrix 文档：`docs/52-stage-39-operability-observability-test-matrix.md`
- 新增 `platform_operability.py`，提供 readiness、metrics 和本地 test matrix；FastAPI 新增 `/platform/operability/readiness`、`/platform/operability/metrics` 和 `/platform/operability/test-matrix`
- 新增阶段 40 final acceptance and portfolio 文档：`docs/53-stage-40-final-acceptance-and-portfolio.md`
- 阶段 40 总结当前平台可演示流程、本地验收命令、作品集能力和仍不覆盖的生产级边界；本阶段不新增业务代码

## 当前待学

### 主题 1：FinTech 全景

- FinTech 的主要方向：支付、银行、信贷、财富管理、资本市场、保险、数字资产、RegTech。
- 金融系统里的基础对象：账户、交易、余额、订单、资产、风险、审计。
- 程序员切入点：后端系统、数据分析、风控模型、支付流程、合规自动化。

### 主题 2：账本和交易

- 账户 account
- 交易 transaction
- 分录 entry
- 借方 debit 和贷方 credit
- 余额 balance
- 审计日志 audit log
- 幂等 idempotency

当前已完成第一版学习材料和代码实验。

### 主题 3：账本持久化

- SQLite 基础表结构
- 数据库事务 database transaction
- 原子写入 atomic write
- 外键 foreign key
- 金额持久化方式
- 交易失败时不能留下部分写入

当前已完成第一版学习材料和代码实验。

### 主题 4：幂等性

- 幂等 idempotency
- 幂等键 idempotency key
- 重复请求 retry
- 支付回调重复到达
- 服务端防重复入账
- 数据库唯一约束兜底

当前已完成第一版学习材料和代码实验；后续可加入请求指纹 request fingerprint，检测同一个 key 下参数是否一致。

### 主题 5：请求指纹

- 请求指纹 request fingerprint
- 同一个幂等键下的参数一致性检查
- 相同请求返回已有交易
- 不同请求拒绝复用同一个 key
- 分录顺序规范化

当前已完成第一版学习材料和代码实验。

### 主题 6：支付订单系统

- 支付订单 payment order
- 订单状态机 state machine
- pending / succeeded / failed / refunded
- 创建订单不立即入账
- 支付成功后调用账本入账
- webhook event id 防重复处理
- 账本 idempotency key 作为第二道防线

当前已完成 `pending`、`succeeded`、`failed` 的第一版学习材料和代码实验；`refunded` 留到下一轮。

### 主题 7：退款和冲正

- 退款 refund
- 反向分录 reversal
- 成功订单才能退款
- 退款后状态变为 refunded
- 重复退款事件不重复出账
- 退款后余额可以被分录解释，而不是删除历史交易

当前已完成全额退款的第一版学习材料和代码实验；部分退款留到后续。

### 主题 8：支付订单持久化

- payment_orders 表
- processed_payment_events 表
- 订单状态持久化
- webhook event 防重持久化
- 与 SQLiteLedger 共用数据库文件
- 当前一致性边界：订单状态更新和账本入账还不是统一事务

当前已完成第一版学习材料和代码实验；下一步学习事务一致性和 outbox pattern。

### 主题 9：Transactional Outbox

- transactional outbox pattern
- payment_outbox 表
- pending / published message 状态
- 订单状态变化和 outbox message 同事务保存
- pending message 可重试发布
- 当前边界：账本写入仍由独立 SQLiteLedger 连接完成

当前已完成 outbox 记录和发布标记的第一版学习材料和代码实验；下一步可实现 outbox publisher。

### 主题 10：Outbox Publisher

- OutboxPublisher 协议
- OutboxPublishResult
- pending message 批量发布
- 发布成功后标记 published
- 发布失败后保留 pending
- limit 分批处理
- 消费方仍需幂等

当前已完成第一版学习材料和代码实验。

### 主题 11：交易流水分析

- 交易流水 transaction statement
- CSV 导入
- SQLite `bank_transactions` 表
- 金额用整数分 `amount_cents` 持久化
- 简单关键词分类 categorization
- SQL 月度收入、支出、净现金流聚合
- Pandas `groupby` 月度现金流汇总
- 重复导入时用 `transaction_id` 防止重复计入
- 按类别的月度支出矩阵 pivot table
- 预算 budget 与实际支出 actual 对比
- HTML 报告和 CSV 导出
- 可配置分类规则 `category_rules.csv`

当前已完成第一版学习材料和代码实验，并新增了按类别的月度支出矩阵、预算对比、HTML 报告、CSV 导出和可配置分类规则；下一步建议进入投资组合实验。

### 主题 12：投资组合分析

- 投资组合 portfolio
- 价格历史 price history
- 单资产收益率 asset return
- 组合收益率 portfolio return
- 固定权重 fixed weights
- 累计收益率 cumulative return
- 年化波动率 annualized volatility
- 最大回撤 maximum drawdown
- 相关性矩阵 correlation matrix
- 协方差矩阵 covariance matrix
- 组合风险公式 `sqrt(w^T * Sigma * w)`
- 组合再平衡 rebalancing
- 当前权重 current weight
- 目标权重 target weight
- 交易金额 trade value
- 交易份额 trade quantity
- HTML 报告和 CSV 导出

当前已完成第一版学习材料和代码实验，并加入资产相关性、协方差矩阵、基于协方差的组合波动率、组合再平衡、HTML 报告和 CSV 导出；下一步建议进入风控规则引擎。

### 主题 13：风控规则引擎

- 风险 risk
- 风控规则 risk rule
- 决策 decision
- 规则命中 rule hit
- 人工审核 manual review
- 审核案例 review case
- 审核状态 review status
- 审核人 reviewer
- 审核理由 review reason
- 风控持久化 risk persistence
- 审计追踪 audit trail
- 审计事件 audit event
- 追加式日志 append-only log
- 规则版本 rule version
- 生效时间 effective at
- 风险信号 risk signal
- 风险评分 risk score
- 纯评分策略 score-only strategy
- 弱风险信号 weak risk signal
- 规则分值 rule score
- 设备标识 device id
- IP 国家/地区 IP country
- 收款方 beneficiary
- 决策表 risk decisions table
- 规则命中明细表 rule hits table
- 审计事件表 audit events table
- 规则命中统计报表 rule hit reporting
- 风控汇总报表 risk summary report
- 规则版本对比报表 rule version comparison report
- 报表导出 report export
- CSV 报表 CSV report
- HTML 报表 HTML report
- 报表筛选 report filter
- 决策时间窗口 decision time window
- 阻断 blocked
- 限额 limit
- 速度规则 velocity rule
- 币种限制 currency control
- 规则配置 rule configuration

当前已完成第一版学习材料和代码实验，支持从 JSON 配置读取规则参数，已加入最小人工复核状态机、SQLite 持久化、追加式风控审计事件、规则版本记录、第一组非金额风险信号、教学版风险评分、纯评分策略、可筛选规则命中统计报表、规则版本对比报表和风控报表导出；后续可以和 KYC/AML 决策、审核案例和审计日志继续衔接。

### 主题 14：KYC/AML 开户筛查

- KYC / Know Your Customer
- AML / Anti-Money Laundering
- CDD / Customer Due Diligence
- EDD / Enhanced Due Diligence
- CIP / Customer Identification Program
- beneficial owner
- sanctions screening
- watchlist matching
- fuzzy matching
- false positive
- risk-based approach
- customer application
- customer type
- individual
- legal entity
- expected activity
- risk score
- check result
- manual review
- review case
- review status
- request more info
- reviewer
- review reason
- KYC persistence
- audit event
- append-only log
- kyc applications table
- kyc decisions table
- kyc check results table
- kyc review cases table
- KYC summary report
- report filter
- submitted time window
- decided time window
- check hit count
- customer type count
- report export
- CSV report
- HTML report
- watchlist version
- watchlist version id
- policy version
- policy version id
- KYC version comparison report
- KYC replay report
- KYC replay run
- replay run approval
- content hash
- effective at
- approved / review / blocked

当前已完成第一版学习材料和代码实验，支持个人和法人客户开户申请检查、beneficial owner 信息检查、样例名单筛查、模糊匹配、样例高风险国家/地区、较高预期月交易量、风险评分和可解释决策；已加入最小人工复核状态机、SQLite 持久化、追加式审计事件、可筛选 KYC/AML 汇总报表、报表导出、watchlist 数据版本记录、KYC/AML 策略版本记录、版本对比报表、replay 重放分析、replay run 运行记录和审批结论。所有名单、国家/地区和阈值均为教学数据，不代表真实合规规则；下一步可进入合规与审计主题，继续理解权限、留痕、数据保护和记录保留。

### 主题 15：合规与审计

- audit log
- audit event
- audit trail
- subject timeline
- actor
- aggregate
- payload
- PII
- redaction / masking
- record retention
- access anomaly detection
- access control
- least privilege
- segregation of duties
- source system
- event type filter
- time window filter
- compliance audit summary
- compliance audit report export
- audit events CSV
- audit timeline CSV
- audit summary CSV
- RBAC
- role
- permission
- audit_viewer
- audit_analyst
- audit_manager
- view_audit_events
- view_audit_payload
- export_audit_report
- approve_audit_export
- access audit
- download audit
- maker/checker
- archive
- legal hold
- AuditAccessEvent
- AuditAccessRecorder
- AuditExportApproval
- AuditRetentionPolicy
- AuditRetentionDecision
- AuditRetentionReport
- AuditRetentionExportPaths
- AccessMonitoringRule
- AccessAnomalyFinding
- AccessAnomalyExportPaths
- AccessAnomalyInvestigationCase
- AccessAnomalyInvestigationService
- InvestigationCaseExportPaths
- SQLiteAccessAuditStore
- SQLiteInvestigationCaseStore
- audit_access.granted
- audit_access.denied
- audit_payload.viewed
- audit_payload.hidden
- audit_export_approval.granted
- audit_export_approval.denied
- audit_access_events
- query_access_events
- active
- archive_due
- delete_due
- held
- repeated_denied_access
- unauthorized_export_attempt
- repeated_payload_view
- access_anomaly_findings.csv
- access_anomaly_report.html
- audit_retention_decisions.csv
- audit_retention_report.html
- investigation case
- open
- investigating
- resolved
- false_positive
- access_investigation_cases
- access_investigation_case_events
- save_case
- get_case
- open_cases
- access_investigation_cases.csv
- access_investigation_report.html
- access_investigation_case.created
- access_investigation_case.started
- access_investigation_case.resolved
- access_investigation_case.false_positive

当前已完成第一版学习材料和代码实验，支持把风控和 KYC/AML 的审计事件统一成 `ComplianceAuditEvent`，按来源系统、事件类型、事件前缀、主体、操作人和时间窗口筛选，构造跨系统主体时间线，汇总来源系统、事件类型和操作人数量，对 JSON payload 中常见 PII 字段做教学版脱敏，导出审计事件 CSV、主体时间线 CSV、审计汇总 CSV 和 HTML 报告，用 `audit_viewer`、`audit_analyst`、`audit_manager` 三个教学版角色控制查看事件、查看 payload、导出报表和审批导出，并记录查看事件、查看或隐藏 payload、导出报表、审批导出的访问审计事件。访问审计事件现在可以写入 SQLite 的 `audit_access_events` 表，并按操作人、权限、结果和时间窗口查询。导出函数可以要求 `AuditExportApproval`，并校验申请人与审批人不能是同一个用户。留存策略可以按事件类型前缀生成 `active`、`archive_due`、`delete_due` 和 `held` 状态报告，并导出 `audit_retention_decisions.csv` 与 `audit_retention_report.html`。访问异常检测可以基于 `AuditAccessEvent` 生成 repeated denied、unauthorized export attempt 和 repeated payload view finding，并导出 `access_anomaly_findings.csv` 与 `access_anomaly_report.html`。访问异常发现项现在可以转成 `AccessAnomalyInvestigationCase`，流转 `open -> investigating -> resolved / false_positive`，通过 `SQLiteInvestigationCaseStore` 写入 `access_investigation_cases` 和 `access_investigation_case_events` 表，导出 `access_investigation_cases.csv` 与 `access_investigation_report.html`，并生成 `access_investigation_case.created/started/resolved/false_positive` 工单处理动作审计事件。当前实验不实现真实身份认证、企业 IAM、不可篡改日志、WORM 存储、真实记录留存期限、真实安全监控、真实工单系统或监管报送；阶段 7 已总结，下一步进入端到端 FinTech 工程作品规划。

### 主题 16：端到端 FinTech 工程作品

- customer onboarding
- KYC/AML decision
- payment order
- risk decision
- ledger posting
- audit trail
- orchestration
- consistency boundary
- module boundary
- `labs/fintech-platform/`
- FinTechPlatform
- PlatformPaymentRequest
- PlatformPaymentResult
- PlatformPaymentStatus
- kyc_decision.saved
- payment_order.created
- risk_decision.saved
- payment_order.succeeded
- payment_order.failed
- review_case.created
- review_case.approved
- review_case.rejected
- ledger_transaction.posted
- risk_review_rejected
- PlatformReportExportPaths
- export_platform_report
- platform_payment_result.csv
- platform_audit_timeline.csv
- platform_report.html
- SQLitePlatformStore
- PlatformRunRecord
- PlatformRunSnapshot
- platform_runs
- platform_run_audit_events
- PlatformHistoryReportExportPaths
- export_platform_history_report
- platform_run_history.csv
- platform_run_audit_events.csv
- platform_run_history.html
- PlatformConsistencyFinding
- evaluate_platform_run_consistency
- export_platform_consistency_report
- platform_consistency_findings.csv
- platform_consistency_report.html
- export_platform_report_with_access
- export_platform_history_report_with_access
- export_platform_consistency_report_with_access
- detect_platform_report_access_anomalies
- export_platform_access_anomaly_report
- platform_access_anomaly_findings.csv
- platform_access_anomaly_report.html
- open_platform_access_investigation_cases
- export_platform_access_investigation_report
- platform_access_investigation_cases.csv
- platform_access_investigation_report.html

当前已完成阶段 7 总结与阶段 8 规划文档，新增 `labs/fintech-platform/README.md` 作为阶段 8 综合平台设计，并实现 `FinTechPlatform.process_payment()` 最小 orchestration。它可以串起 KYC/AML、payment order、risk decision、ledger posting 和 audit trail，并覆盖 KYC blocked、risk blocked、risk review 和 approved posting 场景。综合平台现在还能导出 `platform_payment_result.csv`、`platform_audit_timeline.csv` 和 `platform_report.html`，通过 `SQLitePlatformStore` 保存 platform run 快照和对应 customer audit timeline，并导出 `platform_run_history.csv`、`platform_run_audit_events.csv` 和 `platform_run_history.html` 历史运行报表。risk review 后续处理也已完成：人工通过会追加 `review_case.approved`、推进订单成功并写入账本；人工拒绝会追加 `review_case.rejected`、推进订单失败且不入账。教学版一致性检查也已完成，可以导出 `platform_consistency_findings.csv` 和 `platform_consistency_report.html`，用于观察 platform status、payment order status、ledger transaction 和 audit events 是否互相吻合。平台报表访问控制和访问审计也已完成，可以授权、拒绝、二人审批并将访问记录写入 SQLite。平台访问异常检测也已完成，可以把非授权导出尝试和重复拒绝访问转成 finding，并导出 `platform_access_anomaly_findings.csv` 和 `platform_access_anomaly_report.html`。平台访问异常调查工单也已完成，可以把平台 finding 转成 investigation case，流转 `open -> investigating -> resolved / false_positive`，写入 SQLite，导出 `platform_access_investigation_cases.csv` 与 `platform_access_investigation_report.html`，并生成工单动作审计事件。阶段 9 已完成 API service、API access audit、API access anomaly、API investigation case 和最小 console；阶段 10 已完成 async run store、最小 worker、FastAPI async endpoints、demo 展示和阶段总结，下一步进入阶段 11 运营控制台增强设计。

### 主题 17：事件驱动与异步任务

- event-driven architecture
- async run
- worker
- accepted / processing / completed / failed
- retry
- attempt_count
- last_error
- request_fingerprint
- outbox
- at-least-once delivery
- idempotent consumer
- `docs/21-stage-10-event-driven-async-plan.md`
- `docs/22-stage-10-summary-and-acceptance.md`

当前已完成阶段 10 设计文档、SQLite async run store、最小 `PlatformAsyncWorker`、FastAPI async endpoints、demo 展示和阶段 10 总结与验收清单，覆盖创建任务、查询任务、按状态筛选、幂等重放、request fingerprint 冲突、重开数据库读取、request payload 重建、worker 成功处理、失败重试、达到上限后失败、批量处理、HTTP `202 Accepted` 响应、教学版 worker 触发、最终 platform result 查询和 API access audit。下一步进入阶段 11 运营控制台增强设计，把 payment runs、async runs、API access events 和 investigation cases 放到更完整的只读运营视图里。

### 主题 18：运营控制台增强

- operations console
- read-only console
- operational summary
- async run monitoring
- failed async runs
- API access events
- API access anomalies
- investigation cases
- platform observability
- empty state
- HTML escaping
- `docs/23-stage-11-operations-console-plan.md`

当前已完成阶段 11 设计与收尾总结，明确不另起前端项目，而是在现有 FastAPI `FinTech Platform Console` 上增强运营视图。当前 console 已能同时展示 payment runs、async runs、failed async runs、API access anomalies、investigation cases 和 recent API access events；completed async run 会关联显示最终 platform status 和 payment order id；demo 也已补充 failed async run 可观察样例，用于观察 `attempt_count` 和 `last_error`。阶段 11B 已新增 failed async run retry API，要求 actor、reason 和 `retry_failed_async_run` confirmation，且成功和失败都会写入 API access audit。阶段 11C 已把 retry 接入 Failed Async Runs 区域的原生 HTML form；form endpoint 只作为浏览器表单适配层。阶段 12 已完成 failed async run retry 二人审批第一版。阶段 13 已完成运行报告与对账视角第一版。文档入口已整理：`docs/README.md` 现在提供阅读路径、阶段文档索引和当前平台能力地图。阶段 14 已完成独立 operation approval record。阶段 15 已完成 operation approval report。阶段 16 已把 operations report 和 approval report 的核心摘要接入 `FinTech Platform Console`。阶段 17 已新增 ledger reconciliation report。阶段 18 已让 operation approval record 支持 pending / approved / rejected 状态流转。阶段 19 已新增 operation approval HTTP endpoints，支持通过 HTTP 查询 pending approval 并流转到 approved/rejected。阶段 20 已新增 `POST /platform/operation-approvals`，支持通过 HTTP 创建 pending approval。阶段 21 已把 failed async run retry 改成先审批后执行：retry request 只创建 pending approval，approval approve 后才把 failed async run 放回 accepted，并写入 retry execution access audit。阶段 22 已在 `FinTech Platform Console` 新增 `Pending Operation Approvals` 只读区块，展示 pending approval 及其关联 async status。阶段 23 已让 operation approval 列表支持 `limit`、`offset`、`sort_by` 和 `sort_order`，console approval 表格统一按 `requested_at desc` 取最新记录。阶段 24 已新增 operation approval 只读详情页，展示 approval record、关联 async run 和 completed platform result 摘要。阶段 25 已让 operation approval 支持 cancelled / expired 生命周期状态。阶段 26 已把 pending approval approve / reject 表单接入 console，并复用现有审批和 retry execution 边界。阶段 27 已在 operation approval 详情页新增 `Lifecycle Timeline`，展示 `approval_requested`、`approval_decided` 和匹配 `approval_id=...` 的 `retry_execution`。阶段 28 已新增 async run 和 platform result 只读详情页，并从 console 与 operation approval detail view 链接进入。阶段 29 已让 operation approval 查询在 `pagination` 中返回 `total_count`、`has_next_page` 和 `next_offset`。阶段 30 已把 pending approval cancel / expire 表单接入 console，并复用 JSON API 的 lifecycle transition 与 access audit。阶段 31 已给 console 增加 payment / async / approval status 筛选入口。阶段 32 已给 payment run 详情页增加 ledger reconciliation context。阶段 33 到阶段 39 已继续补齐剩余路线图、console 工作流控制、identity / permission、并发恢复、外部 settlement reconciliation、evidence package 和 operability；阶段 40 已完成最终验收与学习作品集总结。

## 近期计划

### 第 1 周

- 阅读 `docs/01-fintech-overview.md`
- 阅读 `docs/02-developer-to-finance.md`
- 阅读 `docs/03-ledger-basics.md`
- 运行 `labs/ledger-basics/demo.py`
- 理解 demo 中两笔交易：用户充值、平台收取手续费
- 在测试里观察“不平衡交易会被拒绝”

### 第 2 周

- 阅读 `docs/04-ledger-persistence.md`
- 阅读 `docs/05-idempotency.md`
- 运行 `labs/ledger-basics/demo_sqlite.py`
- 对比 `Ledger` 和 `SQLiteLedger` 的实现差异
- 学习数据库事务和金融交易的区别
- 理解幂等键如何防止重复请求重复入账
- 阅读 `docs/06-request-fingerprint.md`
- 理解请求指纹如何拒绝同一个 key 下参数不一致的请求
- 阅读 `docs/07-payment-order-system.md`
- 阅读 `docs/08-refunds-and-reversals.md`
- 阅读 `docs/09-payment-order-persistence.md`
- 阅读 `docs/10-transactional-outbox.md`
- 阅读 `docs/11-outbox-publisher.md`
- 运行 `labs/payment-orders/demo.py`
- 运行 `labs/payment-orders/demo_sqlite.py`
- 理解创建订单不入账、成功回调才入账
- 理解退款不删除原交易，而是写入反向分录
- 理解订单、事件、账本数据在 SQLite 中如何恢复
- 理解 outbox message 如何作为可靠待发布事件
- 理解 outbox publisher 如何发布、标记成功和保留失败消息
- 下一步进入交易流水分析：CSV 导入、SQLite 查询、Pandas 月度现金流

### 第 3-4 周

- 阅读 `docs/12-transaction-statement-analysis.md`
- 运行 `labs/transaction-analysis/demo.py`
- 理解 CSV 字段如何映射为 SQLite 表
- 理解为什么金额用整数分保存，而不是浮点数
- 理解月度现金流里的收入、支出和净现金流
- 对比 SQL 汇总和 Pandas 汇总的结果
- 理解按类别的月度支出矩阵
- 理解预算和实际支出的差异计算
- 理解 HTML 报告和 CSV 导出如何让分析结果可阅读、可复核
- 理解 `category_rules.csv` 如何把业务规则从代码里分离出来
- 下一步进入投资组合实验：收益率、波动率、最大回撤

### 第 5 周

- 阅读 `docs/13-portfolio-analysis.md`
- 运行 `labs/portfolio-analysis/demo.py`
- 理解价格如何转换成收益率
- 理解组合收益率为什么是资产收益率的加权和
- 理解年化波动率的 `sqrt(252)` 简化假设
- 理解最大回撤如何从净值曲线计算
- 理解资产相关性和协方差如何影响组合风险
- 理解 `sqrt(w^T * Sigma * w)` 如何从协方差矩阵计算组合波动率
- 理解组合再平衡如何从当前持仓和目标权重计算买卖金额
- 理解投资组合报告如何导出收益、风险和再平衡结果
- 下一步进入风控规则引擎：限额、异常检测、规则命中和审核

### 第 6 周

- 阅读 `docs/14-risk-rule-engine.md`
- 运行 `labs/risk-rule-engine/demo.py`
- 理解 `approved`、`review`、`blocked` 的区别
- 理解单笔金额限额和日累计金额限额
- 理解为什么规则命中必须保存原因
- 理解当前实验和真实风控系统的差距
- 理解 `risk_rules.json` 如何把规则参数从代码里分离出来
- 理解 `review` 决策如何创建人工复核案例
- 理解 `pending_review -> approved / rejected` 的状态流转
- 运行 `labs/risk-rule-engine/demo_sqlite.py`
- 理解风控决策、规则命中和审核案例为什么要分表保存
- 理解待审核案例如何从 SQLite 中恢复
- 理解 `risk_audit_events` 如何记录关键动作历史
- 理解状态表和追加式审计日志的区别
- 理解 `risk_rule_versions` 如何保存当时使用的阈值、允许币种和生效时间
- 理解风控决策为什么要关联 `rule_version_id`
- 理解设备、IP 国家/地区和收款方为什么也是风险信号
- 理解新设备、高风险国家/地区、受阻收款方三类规则的简化边界
- 理解每条规则的 `score` 如何汇总为 `risk_score`
- 理解当前评分和真实机器学习模型评分的区别
- 理解 `unusual_hour` 和 `round_amount` 如何作为弱风险信号只贡献分数
- 理解多个弱风险信号如何通过总分阈值触发 `review`
- 理解规则命中统计报表如何汇总决策状态、规则命中次数、风险分数和审核状态
- 理解规则命中统计报表为什么需要按规则版本和决策时间窗口筛选
- 理解规则版本对比报表如何比较两个版本的决策状态、规则命中和风险分数差异
- 理解风控报表导出如何把统计结果写成 CSV 和 HTML 文件
- 下一步可进入 KYC/AML/合规基础

### 第 7 周

- 阅读 `docs/15-kyc-aml-onboarding.md`
- 运行 `labs/kyc-aml-onboarding/demo.py`
- 理解 KYC、AML、CDD、beneficial owner 和 sanctions screening 的区别
- 理解为什么名单筛查需要模糊匹配和人工复核，而不是简单字符串相等
- 理解当前实验为什么只使用教学版名单和样例国家/地区
- 理解开户筛查决策为什么要保存每条检查的原因和分值
- 运行 `labs/kyc-aml-onboarding/demo_sqlite.py`
- 理解客户申请、beneficial owner、KYC/AML 决策和检查结果为什么要分表保存
- 理解 `pending_review -> approved / rejected / request_more_info` 的状态流转
- 理解 `kyc_audit_events` 如何记录关键动作历史
- 理解状态表和追加式审计日志的区别
- 理解 KYC/AML 汇总报表如何聚合客户类型、决策状态、检查命中、风险分数和审核状态
- 理解报表为什么需要按客户类型、决策状态、提交时间窗口和决策时间窗口筛选
- 理解 KYC/AML 报表导出如何把统计结果写成 CSV 和 HTML 文件
- 理解 watchlist 数据版本为什么需要保存 `version_id`、`source`、`entry_count`、`content_hash` 和 `effective_at`
- 理解 KYC/AML 决策为什么要关联当时使用的 `watchlist_version_id`
- 理解 KYC/AML 策略版本为什么需要保存阈值、样例高风险国家/地区、匹配分数门槛和 `effective_at`
- 理解 KYC/AML 决策为什么要关联当时使用的 `policy_version_id`
- 理解 watchlist/policy 版本对比报表如何比较已保存决策的决策状态、检查命中、风险分数和审核状态差异
- 理解 KYC/AML replay 如何用新名单或新策略重新评估已保存申请，并逐客户比较原决策和重放决策
- 理解 replay run 如何保存评估结果、逐客户变化和 `pending_review -> approved / rejected` 审批结论
- 理解 replay run 审批为什么不会自动改写原始 KYC/AML 决策
- 下一步可进入合规与审计主题，继续理解权限、留痕、数据保护和记录保留

### 第 8 周

- 阅读 `docs/16-compliance-audit.md`
- 运行 `labs/compliance-audit/demo.py`
- 理解 audit event 和普通 debug log 的区别
- 理解状态表和 audit trail 为什么不能互相替代
- 理解 `source_system`、`aggregate_type`、`aggregate_id`、`actor` 和 `occurred_at` 的作用
- 理解如何把 KYC/AML 和风控事件合并成一个客户时间线
- 理解为什么 payload 需要克制、脱敏和访问控制
- 理解当前教学版脱敏和真实 PII 数据保护的差距
- 理解审计事件、主体时间线和汇总结果如何导出为 CSV 和 HTML 报告
- 理解 `audit_viewer`、`audit_analyst` 和 `audit_manager` 的权限差异
- 理解为什么查看事件、查看 payload 和导出报表应当分开授权
- 理解为什么查看审计日志和导出审计报表本身也需要被记录
- 理解访问审计事件为什么需要从内存 recorder 写入 SQLite 后再查询和复核
- 理解为什么敏感导出可以要求申请人与审批人分离
- 理解教学版留存策略如何把事件分成 active、archive_due、delete_due 和 held
- 理解访问审计数据如何进一步生成可疑访问模式线索
- 理解异常访问发现项如何导出为 CSV 和 HTML 报告
- 理解留存决策如何导出为 CSV 和 HTML 报告，但不真的删除或归档任何记录
- 理解访问异常 finding 为什么需要进入 investigation case 处理闭环
- 理解 open、investigating、resolved 和 false_positive 的状态流转
- 理解 investigation case 为什么需要写入 SQLite 后再查询未关闭工单
- 理解 investigation case 如何导出为 CSV 和 HTML 报告
- 理解 investigation case 创建、接手和关闭动作为什么也要生成审计事件
- 阅读 `docs/17-stage-7-summary-and-stage-8-plan.md`
- 总结阶段 7 的关键工程结论：状态表和 audit trail 的区别、payload 克制、报表导出权限、finding 到 investigation case 的闭环
- 确认阶段 8 主线：customer onboarding -> KYC/AML decision -> payment order -> risk decision -> ledger posting -> audit trail -> reports / investigation
- 已完成 `labs/fintech-platform/README.md` 的最小业务流程、模块边界和数据流设计

### 第 9 周

- 新建 `labs/fintech-platform/README.md`
- 设计端到端场景：已通过 KYC 的客户发起支付，风控审核通过后入账，并生成审计时间线
- 画清楚模块依赖：KYC/AML、payment-orders、risk-rule-engine、ledger-basics、compliance-audit
- 定义最小数据流：customer、account、payment_order、risk_decision、ledger_transaction、audit_event
- 明确暂不实现范围：真实 API、真实身份认证、生产级一致性、真实监管规则和投资建议
- 已实现最小 orchestration 代码，优先复用现有实验模块
- 运行 `labs/fintech-platform/demo.py`，观察一条 approved 链路如何生成 payment order、risk decision、ledger transaction 和 customer audit timeline
- 查看 `labs/fintech-platform/reports/platform_payment_result.csv`、`platform_audit_timeline.csv` 和 `platform_report.html`
- 理解端到端平台状态、KYC/Risk/Payment/Ledger 结果和 customer audit timeline 如何导出为可复核报告
- 理解 `SQLitePlatformStore` 如何把 platform run 结果和 customer audit timeline 写入 `platform_runs` 与 `platform_run_audit_events`
- 观察 demo 输出的 `Persisted platform run`
- 查看 `labs/fintech-platform/reports/platform_run_history.csv`、`platform_run_audit_events.csv` 和 `platform_run_history.html`
- 理解多次 platform run 如何从 SQLite 快照导出为历史运行报表
- 观察 demo 输出的 `Risk review completion`
- 理解 `risk_review_required -> completed` 如何经过人工通过、支付成功和账本入账形成闭环
- 查看 `labs/fintech-platform/reports/platform_consistency_findings.csv` 和 `platform_consistency_report.html`
- 理解 platform status、payment order status、ledger transaction 和 audit events 为什么需要互相吻合
- 观察 demo 输出的 `Platform report access audit events`
- 理解谁导出了平台报表、导出目标是什么、访问记录如何落到 SQLite
- 观察 demo 输出的 `Platform access anomaly findings`
- 查看 `labs/fintech-platform/reports/platform_access_anomaly_findings.csv` 和 `platform_access_anomaly_report.html`
- 理解非授权导出尝试和重复拒绝访问如何变成 finding
- 观察 demo 输出的 `Platform access investigation cases`
- 观察 demo 输出的 `Persisted open platform investigation cases`
- 查看 `labs/fintech-platform/reports/platform_access_investigation_cases.csv` 和 `platform_access_investigation_report.html`
- 理解平台 access anomaly finding 如何进入 investigation case，以及工单动作为什么也要进入 audit trail
- 读 `docs/18-stage-8-summary-and-acceptance.md`
- 理解阶段 8 的端到端链路、验收清单和后续路线
- 读 `docs/19-stage-9-platform-api-plan.md`
- 理解为什么阶段 9 先做纯 Python API service 边界，再考虑 FastAPI 路由层
- 查看 `labs/fintech-platform/platform_api_service.py`
- 理解 `run_id` 和 request fingerprint 如何一起支持教学版幂等
- 查看 `labs/fintech-platform/platform_api_app.py`
- 理解 FastAPI 路由层如何调用 `PlatformApiService`，并把业务错误映射成 HTTP 状态码
- 理解 API 调用本身也需要 access audit：成功调用记录 `audit_access.granted`，业务错误或缺失资源记录 `audit_access.denied`
- 调用 `GET /platform/api-access-events`，按 actor、permission 或 outcome 查询 API 访问审计事件
- 查看 `labs/fintech-platform/platform_api_access_anomaly_report.py`
- 理解 API 访问审计如何被筛选为 `fintech_platform_api_` 事件，并复用 access monitoring 规则生成 repeated denied access finding
- 查看 `labs/fintech-platform/reports/platform_api_access_anomaly_findings.csv` 和 `platform_api_access_anomaly_report.html`
- 查看 `labs/fintech-platform/platform_api_investigation_cases.py`
- 理解 API access anomaly finding 如何进入 `open -> investigating -> resolved / false_positive` 工单闭环
- 查看 `labs/fintech-platform/reports/platform_api_access_investigation_cases.csv` 和 `platform_api_access_investigation_report.html`
- 调用 `GET /platform/api-access-anomaly-findings`，观察 API access audit 如何通过 HTTP 形成 finding 视图
- 调用 `POST /platform/api-access-investigation-cases`，观察 API finding 如何通过 HTTP 开成 investigation case 并落盘
- 调用 `GET /platform/api-access-investigation-cases` 和 `GET /platform/api-access-investigation-cases/{case_id}`，观察工单持久化查询
- 调用 `PATCH /platform/api-access-investigation-cases/{case_id}/start`
- 调用 `PATCH /platform/api-access-investigation-cases/{case_id}/resolve` 或 `/false-positive`，观察 API 工单状态流转和访问审计记录
- 运行 `python -m uvicorn platform_api_app:app --app-dir .\labs\fintech-platform --reload`
- 读 `docs/20-stage-9-summary-and-stage-10-plan.md`
- 理解阶段 9 的 API service、幂等、访问审计、API access anomaly、investigation case 和最小 console 的工程结论
- 读 `docs/21-stage-10-event-driven-async-plan.md`
- 读 `docs/22-stage-10-summary-and-acceptance.md`
- 读 `docs/23-stage-11-operations-console-plan.md`
- 读 `docs/25-stage-12-operation-approval-boundary.md`
- 读 `docs/26-stage-13-operations-reconciliation-report.md`
- 读 `docs/README.md`，按文档入口选择学习路径，并用“当前平台能力地图”回顾主业务、async、retry approval、investigation case 和 operations report 流程
- 读 `docs/27-stage-14-operation-approval-record.md`，理解 access audit 和 operation approval record 的边界
- 读 `docs/28-stage-15-operation-approval-report.md`，理解 approval report 如何汇总 retry 审批记录
- 读 `docs/29-stage-16-console-report-views.md`，理解 console 如何只读展示 operations report 和 approval report 摘要
- 读 `docs/30-stage-17-ledger-reconciliation-report.md`，理解 ledger reconciliation report 如何检查 payment amount、ledger amount 和余额快照的一致性
- 读 `docs/31-stage-18-operation-approval-state-flow.md`，理解 operation approval record 如何支持 pending / approved / rejected 状态流转
- 读 `docs/32-stage-19-operation-approval-http-endpoints.md`，理解 pending approval 如何通过 HTTP 查询并流转到 approved / rejected
- 读 `docs/33-stage-20-create-operation-approval-http-endpoint.md`，理解 pending approval 如何通过 HTTP 创建、查询并流转到 approved / rejected
- 读 `docs/34-stage-21-retry-approval-before-execution.md`，理解 retry request 如何先创建 pending approval，审批通过后才执行 `failed -> accepted`
- 读 `docs/35-stage-22-operation-approval-console-view.md`，理解 console 如何只读展示 pending approval 及其关联 async status
- 读 `docs/36-stage-23-operation-approval-pagination-sorting.md`，理解 operation approval 列表如何通过 `limit`、`offset`、`sort_by` 和 `sort_order` 做稳定查询
- 读 `docs/42-stage-29-operation-approval-pagination-metadata.md`，理解 operation approval 查询如何返回 `total_count`、`has_next_page` 和 `next_offset`
- 读 `docs/43-stage-30-console-cancel-expire-actions.md`，理解 console 如何复用 JSON API 的 cancel / expire lifecycle transition 与 access audit
- 读 `docs/44-stage-31-console-filter-controls.md`，理解 console 如何按 payment / async / approval status 缩小展示范围
- 读 `docs/45-stage-32-payment-detail-reconciliation-context.md`，理解 payment run 详情页如何展示 ledger reconciliation context
- 阶段 40 第一版已完成；当前主线可作为可运行 FinTech 工程学习作品集收口

## 本机环境记录

- 用户偏好使用 Anaconda / conda 管理 Python 环境。
- 默认 `python` 命令当前指向不可用的 Windows Store alias。
- 已验证可用 Python：`C:\App\Anaconda\python.exe`
- 2026-05-05：Anaconda PowerShell 启动时报 `UnicodeEncodeError: cp1252`。原因是 conda 激活脚本输出中包含中文路径，但 Anaconda Python stdout 默认编码为 `cp1252`。
- 已设置用户环境变量 `PYTHONIOENCODING=utf-8`。需要重新打开 Anaconda PowerShell 才会在新窗口生效。
- 建议后续可使用 `environment.yml` 创建独立学习环境：

```powershell
conda env create -f environment.yml
conda activate fintech-lab
```

- 运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo.py
```

- 运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\ledger-basics
```

- 运行 SQLite demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo_sqlite.py
```

- 运行支付订单 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo.py
```

- 运行 SQLite 支付订单 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo_sqlite.py
```

- 运行交易流水分析 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\transaction-analysis\demo.py
```

- 运行全量测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs
```

- 运行投资组合分析 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\portfolio-analysis\demo.py
```

- 运行风控规则引擎 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo.py
```

- 运行风控规则引擎 SQLite demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo_sqlite.py
```

- 运行 KYC/AML 开户筛查 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo.py
```

- 运行 KYC/AML SQLite demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo_sqlite.py
```

- 运行合规审计 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\compliance-audit\demo.py
```

- pytest 曾生成 `pytest-cache-files-*` 临时目录且当前无法删除，已通过 `.ignore` 和 `.gitignore` 忽略，避免影响 `rg --files`。
- pytest 的默认用户临时目录曾出现访问权限问题；测试数据优先写入仓库内各实验的 `.test-data/`，并已忽略该目录。

## 中期路线

1. 双分录账本：理解金融系统底层记账。
2. 支付订单系统：理解订单状态、退款、回调、幂等。
3. 交易流水分析：理解个人金融数据和报表。
4. 投资组合实验：理解收益率、波动率、最大回撤。
5. 风控规则引擎：理解异常检测、额度、评分和审核。
6. KYC/AML 开户筛查：理解身份识别、CDD、beneficial owner、名单筛查和可解释决策。
7. 合规与审计：理解日志、权限、数据保护、记录留存和复核流程。
8. 端到端 FinTech 工程作品：串联开户、支付、风控、账本和审计，理解跨模块流程和一致性边界。

## 交接给后续 AI 终端

新的 AI 终端开始工作前，应先读取：

1. `AGENTS.md`
2. `LEARNING_PROGRESS.md`
3. `README.md`

后续 AI 终端应继续使用中文协作，并在完成学习内容、代码实验或计划调整后更新本文件。

## 学习日志

| 日期 | 内容 | 结果 |
| --- | --- | --- |
| 2026-04-30 | 初始化学习仓库结构、进度文件和 AI 协作规则 | 完成阶段 0 的基础骨架 |
| 2026-04-30 | 新增账本基础文档和内存版双分录账本实验 | demo 可运行；pytest 4 个测试通过 |
| 2026-04-30 | 记录 Anaconda 偏好和中英文使用边界 | 新增 `environment.yml`；脚本用户可见文本改为英文 |
| 2026-05-05 | 修复 Anaconda PowerShell 激活时的 cp1252 编码错误 | 持久化 `PYTHONIOENCODING=utf-8`；重新打开终端后生效 |
| 2026-05-05 | 新增 SQLite 持久化账本和持久化学习文档 | demo 可运行；pytest 8 个测试通过 |
| 2026-05-05 | 新增幂等性学习文档并实现 `idempotency_key` | 内存版和 SQLite 版 demo 可运行；pytest 13 个测试通过 |
| 2026-05-05 | 新增请求指纹学习文档并实现参数一致性检查 | 内存版和 SQLite 版 demo 可运行；pytest 18 个测试通过 |
| 2026-05-05 | 新增支付订单系统第一版 | payment-orders demo 可运行；全量 pytest 26 个测试通过 |
| 2026-05-05 | 新增退款和反向分录 | payment-orders demo 可运行；全量 pytest 33 个测试通过 |
| 2026-05-05 | 新增 SQLite 持久化支付订单系统 | demo_sqlite 可运行；全量 pytest 40 个测试通过 |
| 2026-05-05 | 新增 transactional outbox 第一版 | demo_sqlite 可显示 pending outbox；全量 pytest 45 个测试通过 |
| 2026-05-05 | 新增 outbox publisher 第一版 | demo_sqlite 可发布 outbox；全量 pytest 50 个测试通过 |
| 2026-05-05 | 新增交易流水分析第一版 | transaction-analysis demo 可运行；全量 pytest 58 个测试通过 |
| 2026-05-05 | 扩展交易流水分析 | 支持按类别的月度支出矩阵和预算对比；全量 pytest 61 个测试通过 |
| 2026-05-05 | 新增交易流水报告导出 | 生成 HTML 报告和 CSV 导出；全量 pytest 62 个测试通过 |
| 2026-05-05 | 新增可配置分类规则 | 从 `category_rules.csv` 读取关键词规则；全量 pytest 64 个测试通过 |
| 2026-05-05 | 新增投资组合分析第一版 | portfolio-analysis demo 可运行；全量 pytest 72 个测试通过 |
| 2026-05-05 | 扩展投资组合风险指标 | 支持相关性矩阵、协方差矩阵和协方差组合波动率；全量 pytest 75 个测试通过 |
| 2026-05-05 | 新增组合再平衡计算 | 根据当前持仓、最新价格和目标权重计算买卖金额；全量 pytest 77 个测试通过 |
| 2026-05-05 | 新增投资组合报告导出 | 生成 HTML 报告和收益/风险/再平衡 CSV；全量 pytest 78 个测试通过 |
| 2026-05-05 | 补强交易流水和投资组合学习文档 | 增加核心概念定义、真实金融使用场景和实现注意点 |
| 2026-05-05 | 新增风控规则引擎第一版 | 支持单笔限额、日累计限额、币种限制和可解释规则命中；全量 pytest 88 个测试通过 |
| 2026-05-05 | 新增风控规则配置文件 | 从 `risk_rules.json` 读取阈值和允许币种；全量 pytest 91 个测试通过 |
| 2026-05-06 | 新增风控人工复核状态机 | `review` 决策可创建审核案例并流转 `pending_review -> approved / rejected`；全量 pytest 99 个测试通过 |
| 2026-05-06 | 新增风控 SQLite 持久化 | 保存风控决策、规则命中和审核案例；SQLite demo 可运行；全量 pytest 109 个测试通过 |
| 2026-05-06 | 新增风控审计事件日志 | 追加记录风控决策保存、审核案例创建和审核完成事件；SQLite demo 可显示事件序列；全量 pytest 111 个测试通过 |
| 2026-05-06 | 新增风控规则版本记录 | 保存规则配置版本并让风控决策关联 `rule_version_id`；SQLite demo 可显示规则版本；全量 pytest 118 个测试通过 |
| 2026-05-06 | 新增非金额风险信号 | 支持新设备审核、高风险 IP 国家/地区阻断、受阻收款方阻断；demo 可显示新规则命中；全量 pytest 124 个测试通过 |
| 2026-05-06 | 新增教学版风险评分 | 规则命中带 `score`，风控决策汇总 `risk_score`，SQLite 持久化评分；全量 pytest 126 个测试通过 |
| 2026-05-06 | 新增规则命中统计报表 | 汇总决策状态、规则命中次数、平均/最高风险分数和审核状态；风控实验 pytest 50 个测试通过；全量 pytest 128 个测试通过 |
| 2026-05-06 | 扩展规则命中统计报表筛选 | 支持按 `rule_version_id` 和决策时间窗口筛选报表；SQLite demo 可显示筛选报表；风控实验 pytest 53 个测试通过 |
| 2026-05-07 | 新增规则版本对比报表 | 比较两个规则版本的决策状态、规则命中、风险分数和审核状态差异；SQLite demo 可显示版本对比；风控实验 pytest 55 个测试通过；全量 pytest 133 个测试通过 |
| 2026-05-07 | 新增风控报表导出 | 导出风险汇总 CSV、规则版本对比 CSV 和 HTML 报告；SQLite demo 可生成 `reports/` 文件；风控实验 pytest 57 个测试通过；全量 pytest 135 个测试通过 |
| 2026-05-07 | 新增纯评分策略 | `unusual_hour` 和 `round_amount` 作为弱信号只贡献分数，累计达到阈值后触发审核；全量 pytest 138 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 开户筛查第一版 | 支持个人/法人客户资料检查、beneficial owner 检查、教学版名单筛查、模糊匹配和风险评分；KYC/AML 实验 pytest 10 个测试通过；全量 pytest 148 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 人工复核和 SQLite 持久化 | 保存客户申请、beneficial owner、决策、检查结果、审核案例和审计事件；KYC/AML 实验 pytest 21 个测试通过；全量 pytest 159 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 汇总报表 | 汇总客户类型、决策状态、检查命中、风险分数和审核状态，并支持客户类型、决策状态和时间窗口筛选；KYC/AML 实验 pytest 28 个测试通过；全量 pytest 166 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 报表导出 | 导出 KYC 汇总 CSV 和 HTML 报告；KYC/AML 实验 pytest 31 个测试通过；全量 pytest 169 个测试通过 |
| 2026-05-07 | 新增 watchlist 数据版本记录 | 保存样例名单版本、来源、条目数、内容哈希和生效时间，并让 KYC/AML 决策关联 `watchlist_version_id`；KYC/AML 实验 pytest 36 个测试通过；全量 pytest 174 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 策略版本记录 | 保存样例策略阈值、高风险国家/地区、匹配分数门槛和生效时间，并让 KYC/AML 决策关联 `policy_version_id`；KYC/AML 实验 pytest 41 个测试通过 |
| 2026-05-07 | 新增 KYC/AML 版本对比报表 | 比较两个 watchlist/policy 版本下已保存决策的决策状态、检查命中、风险分数和审核状态差异，并导出 `kyc_version_comparison_report.csv`；KYC/AML 实验 pytest 45 个测试通过 |
| 2026-05-07 | 新增 KYC/AML replay 重放分析 | 用新的样例 watchlist 或 policy 重新评估已保存申请，逐客户比较原决策和重放决策，并导出 `kyc_replay_report.csv`；KYC/AML 实验 pytest 49 个测试通过 |
| 2026-05-07 | 新增 KYC/AML replay 运行记录和审批 | 保存 replay run、逐客户变化、审批结论和审计事件；KYC/AML 实验 pytest 51 个测试通过；全量 pytest 189 个测试通过 |
| 2026-05-08 | 新增合规审计时间线第一版 | 合并风控和 KYC/AML 审计事件，支持筛选、主体时间线、汇总和教学版 payload 脱敏；compliance-audit 实验 pytest 5 个测试通过；全量 pytest 194 个测试通过 |
| 2026-05-08 | 新增合规审计报表导出 | 导出审计事件 CSV、主体时间线 CSV、审计汇总 CSV 和 HTML 报告；compliance-audit 实验 pytest 8 个测试通过；全量 pytest 197 个测试通过 |
| 2026-05-08 | 新增合规审计教学版权限模型 | 使用 `audit_viewer`、`audit_analyst`、`audit_manager` 控制查看事件、查看 payload 和导出报表；compliance-audit 实验 pytest 12 个测试通过；全量 pytest 201 个测试通过 |
| 2026-05-08 | 新增合规审计访问审计记录 | 记录查看事件、查看或隐藏 payload、导出报表的访问审计事件；compliance-audit 实验 pytest 15 个测试通过；全量 pytest 204 个测试通过 |
| 2026-05-08 | 新增访问审计 SQLite 持久化 | `SQLiteAccessAuditStore` 保存 `AuditAccessEvent`，支持按操作人、权限、结果和时间窗口查询；demo 可显示持久化后的 denied payload 访问记录；compliance-audit 实验 pytest 20 个测试通过；全量 pytest 209 个测试通过 |
| 2026-05-08 | 新增审计报告导出审批 | `AuditExportApproval` 支持二人审批，导出函数可要求申请人与审批人分离，并记录 `approve_audit_export` 和审批审计事件；compliance-audit 实验 pytest 24 个测试通过；全量 pytest 213 个测试通过 |
| 2026-05-08 | 新增审计留存策略报告 | `AuditRetentionPolicy` 按事件类型前缀生成 active、archive_due、delete_due 和 held 留存状态；demo 可显示 `Audit retention summary`；compliance-audit 实验 pytest 29 个测试通过；全量 pytest 218 个测试通过 |
| 2026-05-08 | 新增访问异常检测 | `AccessMonitoringRule` 和 `AccessAnomalyFinding` 基于访问审计事件识别 repeated denied、非 manager 导出尝试和重复 payload 查看；demo 可显示 `Access anomaly findings`；compliance-audit 实验 pytest 35 个测试通过；全量 pytest 224 个测试通过 |
| 2026-05-11 | 新增访问异常报告导出 | `export_access_anomaly_report` 导出 `access_anomaly_findings.csv` 和 `access_anomaly_report.html`，HTML 会转义用户可控字段；compliance-audit 实验 pytest 38 个测试通过；全量 pytest 227 个测试通过 |
| 2026-05-11 | 新增审计留存报告导出 | `export_audit_retention_report` 导出 `audit_retention_decisions.csv` 和 `audit_retention_report.html`，HTML 会转义事件和策略字段；compliance-audit 实验 pytest 41 个测试通过；全量 pytest 230 个测试通过 |
| 2026-05-11 | 新增访问异常调查工单状态 | `AccessAnomalyInvestigationService` 把 access anomaly finding 转成 investigation case，并支持 `open -> investigating -> resolved / false_positive`；compliance-audit 实验 pytest 48 个测试通过；全量 pytest 237 个测试通过 |
| 2026-05-11 | 新增访问异常调查工单 SQLite 持久化 | `SQLiteInvestigationCaseStore` 保存 investigation case 和关联 access events，支持按状态、分派人和 finding actor 查询；compliance-audit 实验 pytest 53 个测试通过；全量 pytest 242 个测试通过 |
| 2026-05-11 | 新增访问异常调查工单报告导出 | `export_investigation_case_report` 导出 `access_investigation_cases.csv` 和 `access_investigation_report.html`，HTML 会转义工单和 finding 字段；compliance-audit 实验 pytest 56 个测试通过；全量 pytest 245 个测试通过 |
| 2026-05-11 | 新增访问异常调查工单处理动作审计 | `AccessAnomalyInvestigationService` 为 investigation case 创建、开始调查、关闭为 resolved/false_positive 生成 `access_investigation_case.*` 审计事件；compliance-audit 实验 pytest 56 个测试通过；全量 pytest 245 个测试通过 |
| 2026-05-11 | 新增阶段 7 总结与阶段 8 规划 | `docs/17-stage-7-summary-and-stage-8-plan.md` 总结合规审计阶段的工程结论，并把下一阶段定位为端到端 FinTech 工程作品规划；下一步设计 `labs/fintech-platform/` |
| 2026-05-18 | 新增阶段 8 综合平台设计 | `labs/fintech-platform/README.md` 定义端到端场景、复用模块、综合平台职责、数据对象、一致性边界和暂不实现范围；下一步实现最小 orchestration 入口 |
| 2026-05-18 | 新增阶段 8 最小 orchestration | `FinTechPlatform.process_payment()` 串起 KYC/AML、payment order、risk decision、ledger posting 和 customer audit timeline；覆盖 approved、KYC blocked、risk blocked、risk review 场景；fintech-platform 实验 pytest 4 个测试通过；全量 pytest 249 个测试通过 |
| 2026-05-18 | 新增阶段 8 综合报表导出 | `export_platform_report` 导出 `platform_payment_result.csv`、`platform_audit_timeline.csv` 和 `platform_report.html`，HTML 会转义页面字段；fintech-platform 实验 pytest 7 个测试通过；全量 pytest 252 个测试通过 |
| 2026-05-18 | 新增阶段 8 SQLite 持久化 | `SQLitePlatformStore` 保存 platform run 快照和 customer audit timeline，支持按 `run_id` 取回、列出 runs、按状态或客户查询；fintech-platform 实验 pytest 11 个测试通过；全量 pytest 256 个测试通过 |
| 2026-05-18 | 新增阶段 8 历史运行报表 | `export_platform_history_report` 从 `PlatformRunSnapshot` 导出 `platform_run_history.csv`、`platform_run_audit_events.csv` 和 `platform_run_history.html`，HTML 会转义页面字段；fintech-platform 实验 pytest 13 个测试通过；全量 pytest 258 个测试通过 |
| 2026-05-18 | 新增阶段 8 risk review 后续处理 | `FinTechPlatform.approve_risk_review()` 支持人工通过后支付成功并入账，`reject_risk_review()` 支持人工拒绝后支付失败且不入账；demo 可显示 `Risk review completion`；fintech-platform 实验 pytest 17 个测试通过；全量 pytest 262 个测试通过 |
| 2026-05-18 | 新增阶段 8 一致性检查报表 | `evaluate_platform_run_consistency()` 检查 platform status、payment order status、ledger transaction 和 audit events 是否吻合，`export_platform_consistency_report()` 导出 CSV/HTML；demo 可生成 `platform_consistency_findings.csv` 和 `platform_consistency_report.html`；fintech-platform 实验 pytest 21 个测试通过；全量 pytest 266 个测试通过 |
| 2026-05-18 | 新增阶段 8 平台报表访问控制和访问审计 | `platform_report_access.py` 复用 `AuditUser`、`export_audit_report` 权限、`AuditAccessRecorder` 和 `AuditExportApproval`，为平台 payment/history/consistency 报表提供授权、拒绝、二人审批和 SQLite 访问审计持久化；demo 可显示 `Platform report access audit events`；fintech-platform 实验 pytest 27 个测试通过；全量 pytest 272 个测试通过 |
| 2026-05-18 | 新增阶段 8 平台访问异常检测 | `detect_platform_report_access_anomalies()` 只分析平台报表访问事件，并复用 `detect_access_anomalies()` 生成 `unauthorized_export_attempt` 和 `repeated_denied_access` finding；`export_platform_access_anomaly_report()` 导出 CSV/HTML；demo 可显示 `Platform access anomaly findings`；fintech-platform 实验 pytest 31 个测试通过；全量 pytest 276 个测试通过 |
| 2026-05-18 | 新增阶段 8 平台访问异常调查工单 | `open_platform_access_investigation_cases()` 把平台 access anomaly finding 转成 investigation case，复用 `AccessAnomalyInvestigationService`、`SQLiteInvestigationCaseStore` 和工单动作审计事件，并导出 `platform_access_investigation_cases.csv` 与 `platform_access_investigation_report.html`；demo 可显示 `Platform access investigation cases`；fintech-platform 实验 pytest 36 个测试通过 |
| 2026-05-18 | 新增阶段 8 总结与验收清单 | `docs/18-stage-8-summary-and-acceptance.md` 总结端到端链路、已完成资产、工程结论、验收清单、当前边界和后续 API 服务化或前端查看页路线；fintech-platform 实验 pytest 36 个测试通过 |
| 2026-05-19 | 新增阶段 9 平台 API 服务化计划 | `docs/19-stage-9-platform-api-plan.md` 说明阶段 9 继续基于综合平台构建 API service，不另起小项目；当前环境尚未安装 FastAPI/uvicorn，因此先做纯 Python service 边界 |
| 2026-05-19 | 新增平台 API service 第一版 | `PlatformApiService` 支持创建 payment run、查询单个 run、按状态或客户筛选 runs，用 `run_id` 和 request fingerprint 做教学版幂等校验，并把结果保存到 `SQLitePlatformStore`；fintech-platform API service pytest 7 个测试通过 |
| 2026-05-19 | 新增平台 FastAPI 路由层第一版 | `platform_api_app.py` 提供 `GET /health`、`POST /platform/payment-runs`、`GET /platform/payment-runs/{run_id}` 和 `GET /platform/payment-runs`，路由层只负责请求/响应和 HTTP 状态码映射；FastAPI 路由 pytest 5 个测试通过 |
| 2026-05-19 | 新增平台 API 访问审计 | `platform_api_app.py` 复用 `AuditAccessEvent` 和 `SQLiteAccessAuditStore`，记录 API 调用的 granted/denied access audit，并新增 `GET /platform/api-access-events` 查询接口；FastAPI 路由 pytest 6 个测试通过 |
| 2026-05-19 | 新增平台 API 访问异常检测 | `platform_api_access_anomaly_report.py` 筛选 `fintech_platform_api_` 访问事件，复用 access monitoring 规则识别 repeated denied access，并导出 `platform_api_access_anomaly_findings.csv` 与 HTML 报告；fintech-platform API anomaly pytest 4 个测试通过 |
| 2026-05-19 | 新增平台 API 访问异常调查工单 | `platform_api_investigation_cases.py` 把 API access anomaly finding 转成 investigation case，支持状态流转、SQLite 持久化、工单动作审计和 API 专用 CSV/HTML 报告；fintech-platform API investigation pytest 5 个测试通过 |
| 2026-05-19 | 新增平台 API 工单 HTTP 查询接口 | `platform_api_app.py` 新增 API anomaly findings 查询、API investigation case 创建、列表筛选和单个 case 查询接口，继续记录接口访问审计；fintech-platform API investigation endpoint pytest 3 个测试通过 |
| 2026-05-19 | 新增平台 API 工单状态流转 HTTP 接口 | `platform_api_app.py` 新增 start、resolve 和 false-positive PATCH 接口，状态流转结果写回 SQLite，并记录 granted/denied API access audit；fintech-platform API investigation endpoint pytest 6 个测试通过；全量 pytest 309 个测试通过 |
| 2026-05-19 | 新增阶段 9 最小前端查看页 | `platform_api_app.py` 新增 `GET /`、`GET /platform` 和 `GET /platform/view`，渲染 `FinTech Platform Console`，只读展示 payment runs、API access anomalies、investigation cases 和 recent API access events，并记录 `view_platform_console` 访问审计；fintech-platform pytest 66 个测试通过；全量 pytest 311 个测试通过 |
| 2026-05-19 | 新增阶段 9 总结与阶段 10 路线 | `docs/20-stage-9-summary-and-stage-10-plan.md` 总结 API service、幂等、HTTP 状态、访问审计、API access anomaly、investigation case 和最小 console 的工程结论，并建议阶段 10 优先进入事件驱动与异步任务；全量 pytest 311 个测试通过 |
| 2026-05-20 | 新增阶段 10 事件驱动与异步任务设计 | `docs/21-stage-10-event-driven-async-plan.md` 明确阶段 10 不另起项目，而是在现有 API service 后增加 async run store、worker、retry 和状态查询边界；下一步实现 `platform_async_service.py` |
| 2026-06-02 | 新增阶段 10 最小 async run store | `platform_async_service.py` 新增 `PlatformAsyncRun`、`SQLitePlatformAsyncRunStore` 和 `platform_async_runs` 表，支持创建 accepted run、查询、按状态筛选、`run_id` + request fingerprint 幂等重放和冲突检测；`test_platform_async_service.py` 6 个测试通过；fintech-platform pytest 72 个测试通过 |
| 2026-06-03 | 新增阶段 10 最小 async worker | `PlatformAsyncWorker` 支持读取 accepted async run、推进 `processing -> completed`、调用现有 `PlatformApiService` 写入最终 `SQLitePlatformStore`，并支持失败重试、达到 `max_attempts` 后标记 failed、批量处理 pending runs；`test_platform_async_service.py` 11 个测试通过；fintech-platform pytest 77 个测试通过 |
| 2026-06-03 | 新增阶段 10 FastAPI async endpoints | `platform_api_app.py` 新增 `POST /platform/async-payment-runs`、async run 查询/列表、`POST /platform/async-worker/process-next` 和 `process-pending`，支持 `202 Accepted`、幂等重放、fingerprint 冲突、worker 触发、最终 platform result 查询和 API access audit；fintech-platform pytest 82 个测试通过 |
| 2026-06-03 | 更新阶段 10 demo 展示 async HTTP 路径 | `demo.py` 通过 in-process FastAPI client 展示 async run 创建、状态查询、worker 处理、最终 platform result、幂等重放和 async API access audit；demo 可运行 |
| 2026-06-03 | 新增阶段 10 总结与验收清单 | `docs/22-stage-10-summary-and-acceptance.md` 总结 async run、worker、HTTP `202`、retry、idempotency、任务状态与业务状态分离、audit trail、验收清单和当前边界；下一步建议阶段 11 进入运营控制台增强 |
| 2026-06-03 | 新增阶段 11 运营控制台增强设计 | `docs/23-stage-11-operations-console-plan.md` 规划只读 console 如何展示 payment runs、async runs、API access anomalies、investigation cases 和 recent API access events；下一步接入 async run summary 与 failed async runs |
| 2026-06-03 | 新增阶段 11 最小运营控制台 async run 展示 | `platform_api_app.py` 的 `FinTech Platform Console` 已接入 `SQLitePlatformAsyncRunStore`，summary 展示 async runs、accepted async runs 和 failed async runs，页面展示 recent async runs 与 failed async runs 空状态，completed async run 可显示最终 platform status 和 payment order id；下一步可补充失败 async run demo 样例或设计操作型控制台动作 |
| 2026-06-03 | 新增阶段 11 failed async run demo 样例 | `demo.py` 新增 `create_failed_async_run_sample()`，通过真实 API 流程构造 request fingerprint 冲突导致的 failed async run，并确认 console 可展示 failed run、attempt count 和 last error；`test_platform_api_app.py` 新增对应覆盖；下一步设计操作型控制台动作边界 |
| 2026-06-04 | 新增阶段 11B failed async run retry 设计 | `docs/24-stage-11b-retry-failed-async-run-design.md` 明确只做 `failed -> accepted` 的人工 retry 边界，要求 actor、reason、confirmation，成功和失败都写入 API access audit；下一步写实现计划并进入 TDD 实现 |
| 2026-06-04 | 新增阶段 11B failed async run retry API | `SQLitePlatformAsyncRunStore.retry_failed()` 支持 `failed -> accepted` 状态转换；FastAPI 新增 `POST /platform/async-payment-runs/{run_id}/retry`，要求 actor、reason 和 `retry_failed_async_run` confirmation，成功和失败都写入 API access audit；retry 后现有 worker 可继续处理该 run；fintech-platform pytest 通过 |
| 2026-06-04 | 新增阶段 11C 控制台 failed async run retry form | `FinTech Platform Console` 的 Failed Async Runs 区域新增原生 HTML retry form；`POST /platform/async-payment-runs/{run_id}/retry-form` 作为浏览器表单适配层复用同一套 retry 校验和 API access audit；成功后 run 回到 `accepted`，不直接触发 worker；fintech-platform API app pytest 通过 |
| 2026-06-04 | 完成阶段 11 运营控制台增强收尾总结 | `docs/23-stage-11-operations-console-plan.md` 已从设计文档更新为设计与收尾总结，合并 async run 观察、failed sample、retry API、retry form、验收清单、工程结论、文档整理约定和阶段 12 候选方向；全量 `labs` pytest 336 个测试通过 |
| 2026-06-04 | 新增阶段 12 操作审计与审批边界计划 | `docs/25-stage-12-operation-approval-boundary.md` 明确阶段 12 先围绕 failed async run retry 增加 maker-checker、二人审批、职责分离、审批原因和 access audit 边界；本次仅更新计划与入口文档，尚未改代码 |
| 2026-06-04 | 新增阶段 12 failed async run retry 二人审批 | `platform_api_app.py` 的 JSON retry API 和 console retry form 已要求 `approved_by`、`approval_reason` 和 `approval_confirmation: approve_retry_failed_async_run`；`actor == approved_by`、错误审批确认和错误 retry confirmation 都会被拒绝并写入 denied access audit；`test_platform_api_app.py` 23 个测试通过，`labs/fintech-platform` 94 个测试通过，全量 `labs` 339 个测试通过 |
| 2026-06-08 | 新增阶段 13 运行报告与对账视角 | `platform_operations_report.py` 汇总 async run、platform result、ledger posting 和 retry access audit，导出 `platform_operations_run_report.csv`、`platform_operations_reconciliation_findings.csv` 和 `platform_operations_report.html`；demo 已接入；`test_platform_operations_report.py` 5 个测试通过，`labs/fintech-platform` 99 个测试通过，全量 `labs` 344 个测试通过 |
| 2026-06-08 | 整理 docs 入口和平台能力地图 | 新增 `docs/README.md`，把阅读路径、阶段文档索引和当前平台能力地图集中到 docs 入口；根 `README.md` 的超长学习顺序已压缩为快速阅读路径；本次未改业务代码 |
| 2026-06-08 | 新增阶段 14 operation approval record | `platform_operation_approval.py` 新增 `OperationApprovalRecord` 和 `SQLiteOperationApprovalStore`，retry API 和 console retry form 会写入结构化 approval record；demo 可输出 `Operation approval records`；`test_platform_operation_approval.py` 4 个测试通过，`test_platform_api_app.py` 23 个测试通过，`labs/fintech-platform` 103 个测试通过，全量 `labs` 348 个测试通过 |
| 2026-06-08 | 新增阶段 15 operation approval report | `platform_operation_approval_report.py` 汇总 approval records、approved/rejected、retry operation 和 self-approval rejected 数量，导出 `platform_operation_approval_records.csv`、`platform_operation_approval_summary.csv` 和 `platform_operation_approval_report.html`；demo 已接入；`test_platform_operation_approval_report.py` 3 个测试通过，`labs/fintech-platform` 106 个测试通过，全量 `labs` 351 个测试通过 |
| 2026-06-08 | 新增阶段 16 console report views | `platform_api_app.py` 的 `FinTech Platform Console` 新增 `Operations Report Summary`、`Operation Approval Summary`、`Operations Run Rows` 和 `Approval Records` 只读区块；`test_platform_api_app.py` 24 个测试通过，`labs/fintech-platform` 107 个测试通过，全量 `labs` 352 个测试通过 |
| 2026-06-08 | 新增阶段 17 ledger reconciliation report | `platform_ledger_reconciliation_report.py` 基于 `PlatformRunSnapshot` 和 audit payload 检查 completed run 的 payment amount、ledger amount、platform bank balance 和 user wallet balance 是否一致，并检查非入账状态是否没有 ledger artifacts；demo 已接入；console 新增 `Ledger Reconciliation Findings` 只读区块；`test_platform_ledger_reconciliation_report.py` 5 个测试通过，`test_platform_api_app.py` 24 个测试通过，`labs/fintech-platform` 112 个测试通过，全量 `labs` 357 个测试通过 |
| 2026-06-08 | 新增阶段 18 operation approval state flow | `OperationApprovalRecord` 支持 `pending / approved / rejected`，`SQLiteOperationApprovalStore` 新增 `approve_pending()` 和 `reject_pending()`，并能迁移旧的 approved/rejected schema；approval report 和 console summary 新增 `pending_count`；demo 可输出 `Pending operation approval flow`；`test_platform_operation_approval.py` 9 个测试通过，`test_platform_operation_approval_report.py` 3 个测试通过，`test_platform_api_app.py` 24 个测试通过，`labs/fintech-platform` 117 个测试通过，全量 `labs` 362 个测试通过 |
| 2026-06-08 | 新增阶段 19 operation approval HTTP endpoints | `platform_api_app.py` 新增 `GET /platform/operation-approvals`、单条查询、`PATCH /approve` 和 `PATCH /reject`，支持 pending approval 通过 HTTP 流转到 approved/rejected，并写入 `view_platform_operation_approvals` / `update_platform_operation_approvals` access audit；demo 通过 HTTP 输出 `Pending operation approval flow`；`test_platform_api_app.py` 27 个测试通过，`labs/fintech-platform` 120 个测试通过，全量 `labs` 365 个测试通过 |
| 2026-06-08 | 新增阶段 20 create operation approval HTTP endpoint | `platform_api_app.py` 新增 `POST /platform/operation-approvals`，支持通过 HTTP 创建 pending operation approval；重复 `approval_id` 返回 409 且不覆盖原记录，并写入 `create_platform_operation_approvals` granted/denied access audit；demo 通过 HTTP create/query/approve 输出 `Pending operation approval flow`；`test_platform_api_app.py` 29 个测试通过，`labs/fintech-platform` 122 个测试通过，全量 `labs` 367 个测试通过 |
| 2026-06-09 | 新增阶段 21 retry approval before execution | `POST /platform/async-payment-runs/{run_id}/retry` 现在只创建 pending operation approval 并返回 202，不直接执行 retry；`PATCH /platform/operation-approvals/{approval_id}/approve` 在审批 retry approval 时执行 `failed -> accepted` 并写入 `retry_platform_async_run` access audit；console retry form 只创建 pending approval；demo 可输出 pending -> approved -> async accepted；`test_platform_api_app.py` 29 个测试通过，`labs/fintech-platform` 122 个测试通过，全量 `labs` 367 个测试通过 |
| 2026-06-09 | 新增阶段 22 operation approval console view | `FinTech Platform Console` 新增 `Pending Operation Approvals` 只读区块，展示 pending approval 的操作类型、目标 run、关联 async status、申请人、申请理由和申请时间；summary 新增 `Pending approvals` 计数；`test_platform_api_app.py` 29 个测试通过，demo 可运行，`labs/fintech-platform` 122 个测试通过，全量 `labs` 367 个测试通过 |
| 2026-06-09 | 新增阶段 23 operation approval pagination and sorting | `SQLiteOperationApprovalStore.query_records()` 和 `GET /platform/operation-approvals` 支持 `limit`、`offset`、`sort_by` 和 `sort_order`；API 响应新增 `pagination` 元数据；console approval 表格默认按 `requested_at desc` 取最新 5 条；`test_platform_operation_approval.py` + `test_platform_api_app.py` 41 个测试通过，demo 可运行，`labs/fintech-platform` 125 个测试通过，全量 `labs` 370 个测试通过 |
| 2026-06-09 | 新增阶段 24 operation approval detail view | `GET /platform/operation-approvals/{approval_id}/view` 新增只读 HTML 详情页，展示 approval record、关联 async run 和 completed platform result 摘要；console 的 `Pending Operation Approvals` 和 `Approval Records` 将 `approval_id` 链接到详情页；`test_platform_api_app.py` 31 个测试通过，demo 可运行，`labs/fintech-platform` 126 个测试通过，全量 `labs` 371 个测试通过 |
| 2026-06-09 | 新增阶段 25 operation approval lifecycle | `OperationApprovalRecord` 新增 `cancelled` 和 `expired` 终态，`SQLiteOperationApprovalStore` 新增 `cancel_pending()` 与 `expire_pending()`；FastAPI 新增 `PATCH /platform/operation-approvals/{approval_id}/cancel` 和 `/expire`；approval report 与 console summary 新增 cancelled / expired 计数；demo 可展示 approved / cancelled / expired lifecycle；`test_platform_operation_approval.py` 14 个测试通过，`test_platform_operation_approval_report.py` 3 个测试通过，`test_platform_api_app.py` 33 个测试通过，demo 可运行 |
| 2026-06-09 | 新增阶段 26 console approval actions | `FinTech Platform Console` 的 `Pending Operation Approvals` 表格新增 approve / reject 表单；FastAPI 新增 `POST /platform/operation-approvals/{approval_id}/approve-form` 和 `/reject-form` 浏览器表单适配层；JSON API 与 form endpoint 复用同一套 approve/reject helper，approve retry approval 仍会执行 `failed -> accepted`，reject 不执行 retry；`test_platform_api_app.py` 36 个测试通过，demo 可运行，`labs/fintech-platform` 134 个测试通过，全量 `labs` 379 个测试通过 |
| 2026-06-09 | 新增阶段 27 approval lifecycle timeline | `GET /platform/operation-approvals/{approval_id}/view` 新增 `Lifecycle Timeline` 只读区块，按时间展示 `approval_requested`、`approval_decided` 和匹配 `approval_id=...` 的 `retry_execution` access audit；`test_platform_api_app.py` 37 个测试通过，demo 可运行，`labs/fintech-platform` 135 个测试通过，全量 `labs` 380 个测试通过 |
| 2026-06-10 | 新增阶段 28 async run / platform result detail views | FastAPI 新增 `GET /platform/async-payment-runs/{run_id}/view` 和 `GET /platform/payment-runs/{run_id}/view` 只读 HTML 详情页；console 与 operation approval detail view 中的关联 run id 可继续跳转；详情页查看会写入 `view detail` access audit；`test_platform_api_app.py` 39 个测试通过，demo 可运行，`labs/fintech-platform` 137 个测试通过，全量 `labs` 382 个测试通过 |
| 2026-06-10 | 新增阶段 29 operation approval pagination metadata | `SQLiteOperationApprovalStore` 新增 `count_records()`；`GET /platform/operation-approvals` 的 `pagination` 响应新增 `total_count`、`has_next_page` 和 `next_offset`，并继续保留 `limit`、`offset`、`returned_count`、`sort_by`、`sort_order`；`test_platform_operation_approval.py` 与 `test_platform_api_app.py` 共 53 个测试通过，demo 可运行，`labs/fintech-platform` 137 个测试通过，全量 `labs` 382 个测试通过 |
| 2026-06-10 | 新增阶段 30 console cancel / expire approval actions | `FinTech Platform Console` 的 `Pending Operation Approvals` 行新增 cancel / expire 表单；FastAPI 新增 `POST /platform/operation-approvals/{approval_id}/cancel-form` 和 `/expire-form`，并让 JSON API 与 form endpoint 复用 `_cancel_operation_approval()` / `_expire_operation_approval()` helper；成功和失败继续写入 `update_platform_operation_approvals` access audit；`test_platform_api_app.py` 42 个测试通过，demo 可运行，`labs/fintech-platform` 140 个测试通过，全量 `labs` 385 个测试通过 |
| 2026-06-10 | 新增阶段 31 console filter controls | `GET /platform/view` 新增 `payment_status`、`async_status` 和 `operation_approval_status` 查询参数；console 顶部新增原生 GET 筛选表单，筛选会影响 payment、async、operations report、ledger reconciliation、approval summary、pending approvals 和 approval records 展示；未知筛选值会提示并被忽略；`test_platform_api_app.py` 44 个测试通过，demo 可运行，`labs/fintech-platform` 142 个测试通过，全量 `labs` 387 个测试通过 |
| 2026-06-10 | 新增阶段 32 payment detail reconciliation context | `GET /platform/payment-runs/{run_id}/view` 新增 `Ledger Reconciliation Context` 区块，复用 `evaluate_platform_ledger_reconciliation()` 展示当前 run 的 `check_id`、`status`、`severity` 和 `message`；`test_platform_api_app.py` 44 个测试通过，`labs/fintech-platform` 142 个测试通过，全量 `labs` 387 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-10 | 新增阶段 33 remaining roadmap | `docs/46-stage-33-remaining-roadmap.md` 总结当前平台已可运行的主业务、异步任务、失败重试审批、报表对账、console 详情和访问异常调查流程；明确与更完整教学版平台相比仍缺身份权限、外部支付清结算、数据一致性硬化、运营工作流、合规证据治理和交付运维；建议后续约 `6 个建设章节 + 1 个最终验收章节`，本阶段只改文档不改业务代码 |
| 2026-06-10 | 新增阶段 34 console workflow controls | `GET /platform/view` 新增 `actor`、`created_from` 和 `created_to` 筛选，并作用到 payment runs、async runs 和 operation approval records；pending approval 区块新增高影响操作风险提示，operation approval / async run / payment run 详情页新增 `Back to Console` 返回入口；`test_platform_api_app.py` 46 个测试通过，`labs/fintech-platform` 144 个测试通过，全量 `labs` 389 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 35 identity / permission / form security boundary | `platform_api_app.py` 新增教学版 `PlatformIdentityContext`、role / permission policy、权限校验和 JSON 审批更新身份一致性校验；access audit 查询、operation approval 查询/创建/更新和 console form 更新路径会写入 granted / denied access audit；`test_platform_api_app.py` 50 个测试通过，`labs/fintech-platform` 148 个测试通过，全量 `labs` 393 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 36 consistency / concurrency / recovery boundary | `platform_async_service.py` 新增 `claim_next_accepted()`，worker 先原子认领 accepted run 再处理；`platform_operation_approval.py` 的 approve / reject / cancel / expire 使用 pending 状态条件更新；补充重复 worker claim、重复 approval decision 和重复 approve retry 只执行一次的测试；相关测试 79 个通过，`labs/fintech-platform` 150 个测试通过，全量 `labs` 395 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 37 external settlement reconciliation | `platform_settlement_reconciliation_report.py` 新增教学版 `ProviderSettlementRow` 和 settlement reconciliation findings，检查内部 completed run 是否有外部 settled row、金额/币种是否一致、非 completed run 是否错误结算、外部 row 是否能映射回内部 run；demo 已导出 settlement reconciliation CSV/HTML；新增测试 7 个通过，settlement + ledger reconciliation report 测试 12 个通过，`labs/fintech-platform` 157 个测试通过，全量 `labs` 402 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 38 evidence package and retention governance | `platform_evidence_package.py` 新增教学版 evidence package，把 failed settlement reconciliation findings、access anomaly findings、operation approval records 和 denied access events 汇总为 evidence items，并导出 items CSV、summary CSV 和 HTML；demo 已导出 evidence package；新增测试 4 个通过，evidence + settlement + investigation 相关测试 16 个通过，`labs/fintech-platform` 161 个测试通过，全量 `labs` 406 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 39 operability / observability / test matrix | `platform_operability.py` 新增教学版 readiness report、metrics snapshot 和 test matrix；FastAPI 新增 `/platform/operability/readiness`、`/platform/operability/metrics` 和 `/platform/operability/test-matrix`，并写入 granted/denied access audit；demo 已输出 `Platform operability snapshot`；新增模块/API 相关测试 53 个通过，`labs/fintech-platform` 164 个测试通过，全量 `labs` 409 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 40 final acceptance and portfolio summary | `docs/53-stage-40-final-acceptance-and-portfolio.md` 汇总当前平台主业务、异步任务、运营控制台、审批工作流、报表对账、证据包和 operability 能力；列出本地验收命令、作品集能力和仍不覆盖的生产级边界；本阶段不新增业务代码，沿用阶段 39 最新验证结果：`labs/fintech-platform` 164 个测试通过，全量 `labs` 409 个测试通过，demo 可运行，`py_compile` 通过 |
| 2026-06-12 | 新增阶段 40 后前端体验改造第一版 | `platform_api_app.py` 新增共享顶部导航、响应式工作台样式和 `GET /platform/manual` 用户手册页；控制台和详情页可跳转 Dashboard、Payment Runs、Async Runs、Approvals、Reconciliation、Audit & Cases、Evidence、Operability 和 Manual；手册页说明平台功能、主要流程、权限边界、证据包、operability 和教学边界，并记录 `fintech_platform_manual` access audit。下一步可先人工浏览 UI，再决定是否继续做更细的视觉 polish 或真实前端拆分；无待查证内容。`py_compile` 通过，`test_platform_api_app.py` 52 个测试通过，`labs/fintech-platform` 165 个测试通过 |
| 2026-06-12 | 新增阶段 40 后前端体验改造第二版 | 顶部导航收敛为 `Console` / `Manual` 两个主入口，左侧目录负责 Console 与 Manual 内部章节跳转；Manual 支持 `?lang=en` / `?lang=cn` 双语切换，并新增 `Detailed Event Flow` / `详细流程图`，说明一笔订单从请求进入、幂等、KYC/AML、风控、入账、retry approval、对账、证据包到 operability review 的端到端处理路径；UI 视觉调整为更清晰的工作台布局。下一步建议人工浏览 375px、768px、1024px 和桌面宽度，再决定是否引入更完整的前端框架；无待查证内容。`py_compile` 通过，`test_platform_api_app.py` 53 个测试通过，`labs/fintech-platform` 166 个测试通过 |
| 2026-06-15 | 新增 Playwright 小型浏览器回归 | `environment.yml` 新增 `pytest-playwright`；`test_platform_ui_playwright.py` 会自动启动临时 FastAPI 服务、使用临时 SQLite 数据库，并通过本机 Edge/Chrome 验证 Console/Manual 导航、Manual CN/EN 切换，以及 failed async run 从网页提交 retry approval 并 approve 后回到 accepted 的流程。Playwright Python 依赖安装成功；Playwright 自带 Chromium 下载受本机证书链限制，当前测试改用系统浏览器执行；无待查证内容。`py_compile` 通过，Playwright 小回归 2 个测试通过，网页相关小回归 17 个测试通过，`labs/fintech-platform` 168 个测试通过 |
| 2026-06-16 | 结构、命名和文档规范复盘 | 复盘根目录、`docs/`、`labs/`、实验 README、忽略规则和生成物位置；结论是结构总体稳定，不建议继续拆出细碎阶段文档或立即重命名历史文件。已更新根 `README.md` 的当前状态，已在 `docs/README.md` 补充文档、实验文件、测试文件、demo、reports、`.test-data` 和历史重复编号的维护约定；本次只改文档入口和进度记录，不改业务代码；无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform Manual view 模块 | 新增 `platform_api_manual_views.py`，把 Manual CN/EN 内容和详细事件流程图从 `platform_api_app.py` 拆出；`platform_api_app.py` 仍保留 `create_app`、路由注册、页面 shell、导航和共享 CSS，`GET /platform/manual` 行为不变。验证：不写 pycache 的语法检查通过；Manual 相关 API 测试 2 个通过，`test_platform_api_app.py` 53 个测试通过；Playwright Manual navigation 小回归 1 个通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform Console view helper 模块 | 新增 `platform_api_console_views.py`，把 Console 的指标卡、筛选表单、筛选校验、反馈提示和通用表格 HTML helper 从 `platform_api_app.py` 拆出；`platform_api_app.py` 仍保留 Console 数据读取、report 构建、路由注册和操作型表单执行边界。验证：不写 pycache 的语法检查通过；Console 定向 API 回归 18 个测试通过；`test_platform_api_app.py` 53 个测试通过；Playwright 小回归 2 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform detail view 模块 | 新增 `platform_api_detail_views.py`，把 payment run、async run 和 operation approval 详情页的 HTML 渲染与行转换 helper 从 `platform_api_app.py` 拆出；`platform_api_app.py` 仍负责路由、权限、访问审计、关联对象查询和 ledger reconciliation context 查询。验证：不写 pycache 的语法检查通过；详情页定向 API 回归 4 个测试通过；`test_platform_api_app.py` 53 个测试通过；Playwright 小回归 2 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform detail view 测试文件 | 新增 `test_platform_api_detail_views.py`，把 async run detail、payment run detail、operation approval detail 和 lifecycle timeline 4 个详情页测试从 `test_platform_api_app.py` 移出；`test_platform_api_app.py` 继续覆盖核心 API、console、manual、approval action 和 operability。验证：新详情页测试 4 个通过，原 `test_platform_api_app.py` 49 个测试通过，两者组合 53 个测试通过；Playwright 小回归 2 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform Console 测试文件第一步 | 新增 `test_platform_api_console.py`，把 Console 页面 summary、空状态、failed async run 展示、retry form 渲染、operations / approval report view、payment / async / approval status 筛选、actor 筛选、date 筛选和 invalid filter feedback 9 个只读/筛选类测试从 `test_platform_api_app.py` 移出；Console approval/retry 表单执行测试暂留原文件。验证：新 Console 测试 9 个通过，原 `test_platform_api_app.py` 40 个测试通过，`test_platform_api_app.py` + `test_platform_api_console.py` + `test_platform_api_detail_views.py` 组合 53 个测试通过；Playwright 小回归 2 个通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform Console 表单动作测试 | 新增 `test_platform_api_console_actions.py`，把 retry form 创建 pending approval、approve / reject / cancel / expire 表单动作、确认码错误和非 failed run retry 错误路径 9 个 Console 动作测试从 `test_platform_api_app.py` 移出；主 API 测试文件继续覆盖 JSON API、manual、operability 和核心审批端点。验证：不写 pycache 的语法检查通过；新 Console action 测试 9 个通过；原 `test_platform_api_app.py` 31 个测试通过；API app + Console + Console actions + detail views 组合 53 个测试通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | 抽取 fintech-platform API 测试共用 helper | 新增 `test_platform_api_helpers.py`，集中维护 TestClient 构造、临时 SQLite 路径、标准 payment payload、pending approval payload、failed async run 构造、access / approval 读取和数据库清理 helper；`test_platform_api_app.py`、`test_platform_api_console.py`、`test_platform_api_console_actions.py` 和 `test_platform_api_detail_views.py` 改为从该 helper 文件导入，避免测试文件互相 import 和 detail view 重复 helper。验证：不写 pycache 的语法检查通过；API app + Console + Console actions + detail views 组合 53 个测试通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform operation approval API 测试 | 新增 `test_platform_api_operation_approvals.py`，把 operation approval JSON endpoint 的列表/单条查询、分页排序、创建 pending approval、重复创建冲突、approve / reject / cancel / expire 状态流转、权限拒绝和身份不一致 10 个测试从 `test_platform_api_app.py` 移出；`test_platform_api_app.py` 缩小为核心 payment / async / retry / access audit / manual / operability API 覆盖。验证：不写 pycache 的语法检查通过；新 operation approval API 测试 10 个通过；原 `test_platform_api_app.py` 21 个测试通过；API app + operation approvals + Console + Console actions + detail views 组合 53 个测试通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform async / retry API 测试 | 新增 `test_platform_api_async_runs.py`，把 async run 创建/查询、幂等重放、worker process-next / process-pending、failed run retry approval 请求、审批后 retry 执行、自审批拒绝、确认码错误、未知 run 和非 failed run retry 错误 10 个测试从 `test_platform_api_app.py` 移出；`test_platform_api_app.py` 进一步缩小为 health、operability、payment run、access audit 和 manual smoke。验证：不写 pycache 的语法检查通过；新 async / retry API 测试 10 个通过；原 `test_platform_api_app.py` 11 个测试通过；API app + async runs + operation approvals + Console + Console actions + detail views 组合 53 个测试通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | 拆分 fintech-platform payment run API 测试 | 新增 `test_platform_api_payment_runs.py`，把 payment run 创建/查询、幂等重放、request fingerprint 冲突、列表筛选和缺失 run 404 这 4 个基础 API 测试从 `test_platform_api_app.py` 移出；`test_platform_api_app.py` 现在保留 health、access audit、manual 和 operability smoke。验证：不写 pycache 的语法检查通过；新 payment run API 测试 4 个通过；原 `test_platform_api_app.py` 7 个测试通过；API app + payment runs + async runs + operation approvals + Console + Console actions + detail views 组合 53 个测试通过；`labs/fintech-platform` 全目录 168 个测试通过。无待查证内容。 |
| 2026-06-16 | fintech-platform 结构整理收尾复盘 | 当前代码和测试分层已经足够稳定：业务模块、API 路由、Console/Manual/Detail view、报表/对账/证据包/operability 模块和对应测试文件均有明确归属；`test_platform_api_app.py` 保留为 smoke 入口，不建议继续拆 access audit / manual / operability 测试，以免文件过碎。后续如继续推进，应转向功能增强、真实外部接口模拟、部署/观测/IAM 等新大章节，而不是继续做小文件拆分。无待查证内容。 |
| 2026-06-17 | 新增 FinTech 知识地图与缺口分析 | 新增 `docs/54-fintech-knowledge-map-and-gap-analysis.md`，系统梳理当前已覆盖的账本、支付、数据分析、风控、KYC/AML、合规审计和综合平台工程主线，并明确仍缺外部支付接口、核心银行、信贷、证券交易生命周期、会计总账、安全隐私、数据治理和生产化基础设施等大块。已更新 `docs/README.md` 导航和本进度文件；本次只改学习文档，不改业务代码。下一步建议先补本地验证脚本，再选择 `payment-provider-adapter`、`core-banking-basics` 或 `loan-lifecycle` 作为新大章节；涉及真实 API、监管、产品规则和标准时必须查证官方或专业来源。 |
| 2026-06-17 | 新增本地一键验证脚本 | 新增 `scripts/verify_labs.ps1`，标准化本地验证入口：编译 fintech-platform 关键入口文件、运行 fintech-platform 测试、可选运行 demo 和全量 labs 测试，并支持 `-SkipBrowser`、`-SkipDemo`、`-SkipFullLabs` 做快速验证；新增 `tests/test_verify_labs_script.py` 约束脚本包含关键验证步骤。已更新根 `README.md` 和 `docs/54-fintech-knowledge-map-and-gap-analysis.md`；验证：先确认测试因脚本缺失失败，再实现脚本后测试 1 个通过；`verify_labs.ps1 -SkipDemo -SkipFullLabs -SkipBrowser` 通过，fintech-platform 非浏览器回归 166 个测试通过。无待查证内容。 |
| 2026-06-18 | 新增 Mermaid 图集初版 | 新增 `docs/diagrams/` 图集，包含综合平台系统结构图、外部 payment provider 协议边界图、payment run 生命周期图、对账与 evidence package 流程图，并在 `docs/README.md` 增加“路径 D：看图理解系统”。本次只新增 Markdown / Mermaid 文档，不改业务代码；无待查证内容。 |
