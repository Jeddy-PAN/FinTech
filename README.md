# FinTech Learning Lab

这是一个面向“程序员零基础学习金融科技”的协作仓库。目标不是只整理概念，而是把每个关键知识点尽量落到可运行的小实验里。

## 当前定位

- 学习对象：有编程背景，金融领域零基础。
- 学习目标：理解金融业务、FinTech 工程系统、数据分析、风控和合规基础。
- 学习方式：先学概念，再写最小实验，再把知识沉淀成文档。
- 当前阶段：阶段 8，规划端到端 FinTech 工程作品。

## 环境和语言约定

- Python 环境优先使用 Anaconda / conda 管理，基础配置见 [environment.yml](environment.yml)。
- 学习文档使用中文并按 UTF-8 编码阅读。
- 脚本、命令行输出、测试样例中的用户可见文本，以及未来前端 UI 文案，默认使用英文。
- 脚本注释可以使用中文，用于解释学习意图或金融概念。

如果 Anaconda PowerShell 启动时报 `UnicodeEncodeError: 'charmap' codec can't encode characters`，通常是 conda 激活脚本输出遇到 Windows `cp1252` 编码限制。当前机器已设置用户环境变量：

```powershell
PYTHONIOENCODING=utf-8
```

设置后需要重新打开 Anaconda PowerShell。

## 目录结构

```text
.
├── AGENTS.md                  # 后续 AI 终端协作规则
├── environment.yml            # conda 学习环境
├── LEARNING_PROGRESS.md       # 当前学习进度、计划和交接记录
├── README.md                  # 仓库入口
├── docs/                      # 金融科技基础知识和权威资料
│   ├── 00-authoritative-sources.md
│   ├── 01-fintech-overview.md
│   ├── 02-developer-to-finance.md
│   ├── 03-ledger-basics.md
│   ├── 04-ledger-persistence.md
│   ├── 05-idempotency.md
│   ├── 06-request-fingerprint.md
│   ├── 07-payment-order-system.md
│   ├── 08-refunds-and-reversals.md
│   ├── 09-payment-order-persistence.md
│   ├── 10-transactional-outbox.md
│   ├── 11-outbox-publisher.md
│   ├── 12-transaction-statement-analysis.md
│   ├── 13-portfolio-analysis.md
│   ├── 14-risk-rule-engine.md
│   ├── 15-kyc-aml-onboarding.md
│   ├── 16-compliance-audit.md
│   └── 17-stage-7-summary-and-stage-8-plan.md
└── labs/                      # 后续代码实验
    ├── ledger-basics/         # 第一个实验：双分录账本
    ├── payment-orders/        # 第二个实验：支付订单系统
    ├── transaction-analysis/  # 第三个实验：交易流水分析
    ├── portfolio-analysis/    # 第四个实验：投资组合分析
    ├── risk-rule-engine/      # 第五个实验：风控规则引擎
    ├── kyc-aml-onboarding/    # 第六个实验：KYC/AML 开户筛查
    ├── compliance-audit/      # 第七个实验：合规审计时间线
    └── fintech-platform/      # 第八个实验：端到端 FinTech 工程作品
```

## 建议学习顺序

1. 先读 [LEARNING_PROGRESS.md](LEARNING_PROGRESS.md)，确认当前进度和下一步任务。
2. 再读 [docs/00-authoritative-sources.md](docs/00-authoritative-sources.md)，理解哪些资料可以作为权威来源。
3. 读 [docs/01-fintech-overview.md](docs/01-fintech-overview.md)，建立 FinTech 地图。
4. 读 [docs/02-developer-to-finance.md](docs/02-developer-to-finance.md)，理解程序员转金融领域需要补什么。
5. 读 [docs/03-ledger-basics.md](docs/03-ledger-basics.md)，理解账户、交易、分录和借贷平衡。
6. 读 [docs/04-ledger-persistence.md](docs/04-ledger-persistence.md)，理解 SQLite、数据库事务和原子写入。
7. 读 [docs/05-idempotency.md](docs/05-idempotency.md)，理解重复请求和幂等键。
8. 读 [docs/06-request-fingerprint.md](docs/06-request-fingerprint.md)，理解同一个幂等键下的参数一致性检查。
9. 读 [docs/07-payment-order-system.md](docs/07-payment-order-system.md)，理解支付订单状态机和成功入账。
10. 读 [docs/08-refunds-and-reversals.md](docs/08-refunds-and-reversals.md)，理解退款和反向账本分录。
11. 读 [docs/09-payment-order-persistence.md](docs/09-payment-order-persistence.md)，理解订单、webhook event 和账本如何持久化。
12. 读 [docs/10-transactional-outbox.md](docs/10-transactional-outbox.md)，理解业务变更和待发布事件如何一起保存。
13. 读 [docs/11-outbox-publisher.md](docs/11-outbox-publisher.md)，理解 pending outbox message 如何发布和重试。
14. 读 [docs/12-transaction-statement-analysis.md](docs/12-transaction-statement-analysis.md)，理解 CSV 交易流水、SQLite 聚合和 Pandas 月度现金流。
15. 运行 `labs/transaction-analysis/`，从样例流水生成月度现金流报表。
16. 读 [docs/13-portfolio-analysis.md](docs/13-portfolio-analysis.md)，理解收益率、波动率和最大回撤。
17. 运行 `labs/portfolio-analysis/`，用样例价格数据计算投资组合指标。
18. 读 [docs/14-risk-rule-engine.md](docs/14-risk-rule-engine.md)，理解风控规则、决策、命中原因和限额。
19. 运行 `labs/risk-rule-engine/`，用最小规则引擎评估交易请求。
20. 运行 `labs/risk-rule-engine/demo_sqlite.py`，观察风控决策、规则命中和审核案例如何保存到 SQLite。
21. 读 [docs/15-kyc-aml-onboarding.md](docs/15-kyc-aml-onboarding.md)，理解 KYC、AML、CDD、beneficial owner 和 sanctions screening 的工程形状。
22. 运行 `labs/kyc-aml-onboarding/`，用教学版开户筛查引擎评估客户申请。
23. 运行 `labs/kyc-aml-onboarding/demo_sqlite.py`，观察客户申请、KYC/AML 决策、审核案例和审计事件如何保存到 SQLite。
24. 观察 `labs/kyc-aml-onboarding/demo_sqlite.py` 输出的 KYC 汇总报表，理解客户类型、决策状态、检查命中、风险分数和审核状态如何聚合。
25. 查看 `labs/kyc-aml-onboarding/reports/`，理解 KYC 汇总报表如何导出为 CSV 和 HTML 文件。
26. 观察 `watchlist_version_id`，理解 KYC/AML 决策为什么要记录当时使用的名单数据版本。
27. 观察 `policy_version_id`，理解 KYC/AML 决策为什么也要记录当时使用的策略参数版本。
28. 观察 `kyc_version_comparison_report.csv`，理解 watchlist/policy 版本对比报表如何比较已保存决策的差异。
29. 观察 `kyc_replay_report.csv`，理解 replay 如何用新策略或新名单重新评估已保存申请，但不改写原始决策。
30. 观察 replay run 的 `pending_review -> approved / rejected`，理解规则或名单上线前为什么要保存评估结果和审批记录。
31. 读 [docs/16-compliance-audit.md](docs/16-compliance-audit.md)，理解 audit event、audit trail、actor、payload、PII 脱敏和记录留存。
32. 运行 `labs/compliance-audit/demo.py`，观察风控和 KYC/AML 审计事件如何合并成跨系统客户时间线。
33. 查看 `labs/compliance-audit/reports/`，理解审计事件、主体时间线和汇总结果如何导出为 CSV 和 HTML 报告。
34. 观察 `audit_viewer`、`audit_analyst` 和 `audit_manager` 的权限差异，理解为什么查看事件、查看 payload 和导出报表应当分开授权。
35. 观察 demo 输出的 `Audit access events`，理解为什么查看审计日志和导出审计报表本身也需要被记录。
36. 观察 demo 输出的 `Persisted denied payload access events`，理解访问审计事件为什么需要落盘后再查询和复核。
37. 观察 demo 输出的 `approved_by: manager_002` 和 `audit_export_approval.granted`，理解为什么敏感导出可以要求申请人与审批人分离。
38. 观察 demo 输出的 `Audit retention summary`，理解样例留存策略如何把审计事件分成 active、archive_due、delete_due 和 held。
39. 观察 demo 输出的 `Access anomaly findings`，理解访问审计数据如何进一步生成可疑访问模式线索。
40. 查看 `labs/compliance-audit/reports/access_anomaly_findings.csv` 和 `access_anomaly_report.html`，理解异常访问发现项如何导出为可复核报告。
41. 查看 `labs/compliance-audit/reports/audit_retention_decisions.csv` 和 `audit_retention_report.html`，理解留存决策如何导出为可复核报告，但不会真的删除或归档任何记录。
42. 观察 demo 输出的 `Access anomaly investigation cases`，理解 finding 如何进入 open、investigating、resolved 或 false_positive 的处理闭环。
43. 观察 demo 输出的 `Persisted open investigation cases`，理解 investigation case 为什么需要落盘后再查询未关闭工单。
44. 查看 `labs/compliance-audit/reports/access_investigation_cases.csv` 和 `access_investigation_report.html`，理解调查工单状态如何导出为可复核报告。
45. 观察 demo 输出的 `Investigation case audit events`，理解调查工单创建、接手和关闭动作本身也需要进入 audit trail。
46. 读 [docs/17-stage-7-summary-and-stage-8-plan.md](docs/17-stage-7-summary-and-stage-8-plan.md)，确认阶段 7 的工程结论和阶段 8 的端到端项目方向。
47. 读 [docs/18-stage-8-summary-and-acceptance.md](docs/18-stage-8-summary-and-acceptance.md)，查看阶段 8 的收尾总结、验收清单和后续路线。
48. 读 [labs/fintech-platform/README.md](labs/fintech-platform/README.md)，理解综合平台的最小业务流程、模块边界、数据对象和一致性边界。
49. 运行 `labs/fintech-platform/demo.py`，观察 KYC/AML、payment order、risk decision、ledger posting 和 audit trail 如何串成一条端到端链路。
50. 查看 `labs/fintech-platform/reports/platform_payment_result.csv`、`platform_audit_timeline.csv` 和 `platform_report.html`，理解端到端结果如何导出为可复核报告。
51. 观察 demo 输出的 `Persisted platform run`，理解端到端运行结果和 customer audit timeline 为什么需要落盘后再查询。
52. 查看 `labs/fintech-platform/reports/platform_run_history.csv`、`platform_run_audit_events.csv` 和 `platform_run_history.html`，理解多次端到端运行如何导出为历史运行报表。
53. 观察 demo 输出的 `Risk review completion`，理解 `risk_review_required -> completed` 如何经过人工通过、支付成功和账本入账形成闭环。
54. 查看 `labs/fintech-platform/reports/platform_consistency_findings.csv` 和 `platform_consistency_report.html`，理解 platform status、payment order status、ledger transaction 和 audit events 为什么需要互相吻合。
55. 观察 demo 输出的 `Platform report access audit events`，理解谁导出了平台报表、导出目标是什么、访问记录如何落到 SQLite。
56. 观察 demo 输出的 `Platform access anomaly findings`，理解非授权导出尝试和重复拒绝访问如何变成 finding。
57. 查看 `labs/fintech-platform/reports/platform_access_anomaly_findings.csv` 和 `platform_access_anomaly_report.html`，理解平台访问异常如何导出为可复核报告。
58. 观察 demo 输出的 `Platform access investigation cases`，理解平台 access anomaly finding 如何进入调查工单闭环。
59. 观察 demo 输出的 `Persisted open platform investigation cases`，理解平台调查工单为什么需要落盘后再查询未关闭工单。
60. 查看 `labs/fintech-platform/reports/platform_access_investigation_cases.csv` 和 `platform_access_investigation_report.html`，理解平台调查工单状态如何导出为可复核报告。
61. 观察 demo 输出的 `Platform investigation case audit events`，理解工单创建、接手和关闭动作为什么也要进入 audit trail。
62. 阶段 8 的收尾已经完成，接下来可以把这套学习平台拆成一个简单的 API 服务或补一个最小前端查看页。

## 协作原则

- 所有“最新监管、API、市场数据、产品规则、考试认证”都必须查证官方或专业来源。
- 概念解释要区分“稳定金融基础知识”和“可能变化的行业信息”。
- 不把 AI 生成内容当作权威结论；没有来源的内容只能作为待验证假设。
- 每完成一个学习单元或代码实验，都要更新 `LEARNING_PROGRESS.md`。
