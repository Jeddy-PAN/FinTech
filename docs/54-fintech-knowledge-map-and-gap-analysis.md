# FinTech 知识地图与缺口分析

最后更新：2026-06-18

本文件用于回答一个实际问题：当前仓库的 FinTech 理论知识是否完整，以及下一步应该补什么。

结论先说清楚：当前仓库已经适合作为“程序员从零理解 FinTech 工程系统”的学习作品集，但还不是完整金融理论教材。它对账本、支付、风控、KYC/AML、审计、对账、审批和可运行交付覆盖较深；对银行、证券、信贷、保险、真实监管、安全隐私和生产基础设施覆盖仍不足。

本文只做学习路线和工程落点规划，不提供投资、法律、税务、会计、合规或持牌金融顾问意见。涉及最新监管、真实 API、产品规则、认证、市场数据和行业报告时，必须回到 [00-authoritative-sources.md](00-authoritative-sources.md) 中的官方或专业来源查证。

## 1. 当前已覆盖的知识主线

### 1.1 账户、账本和资金流

已覆盖内容：

- 双分录账本、账户余额、借贷平衡。
- 使用 `Decimal` 处理金额，避免浮点误差。
- SQLite 持久化账本。
- 幂等键和 request fingerprint。
- 支付成功、退款、冲正与账本分录关系。

对应文档和实验：

- [03-ledger-basics.md](03-ledger-basics.md)
- [04-ledger-persistence.md](04-ledger-persistence.md)
- [05-idempotency.md](05-idempotency.md)
- [06-request-fingerprint.md](06-request-fingerprint.md)
- [08-refunds-and-reversals.md](08-refunds-and-reversals.md)
- [../labs/ledger-basics/](../labs/ledger-basics/)
- [../labs/payment-orders/](../labs/payment-orders/)

当前深度判断：适合理解工程账本入门，但还没有扩展到完整总账、科目体系、收入确认、会计期间、调账、关账和财务报表。

### 1.2 支付订单、幂等和 outbox

已覆盖内容：

- payment order 状态机。
- webhook event id 去重。
- 支付成功和退款的账本联动。
- transactional outbox。
- outbox publisher 的 pending / published 状态。

对应文档和实验：

- [07-payment-order-system.md](07-payment-order-system.md)
- [09-payment-order-persistence.md](09-payment-order-persistence.md)
- [10-transactional-outbox.md](10-transactional-outbox.md)
- [11-outbox-publisher.md](11-outbox-publisher.md)
- [../labs/payment-orders/](../labs/payment-orders/)

当前深度判断：适合理解一个教学版支付系统的核心工程模式，但还没有覆盖真实 payment provider、webhook 签名验证、清算文件、卡组织网络、ACH、wire、实时支付和多币种结算。

### 1.3 数据分析、投资组合和报表

已覆盖内容：

- 交易流水 CSV 导入和 SQLite 存储。
- 交易分类、月度现金流、预算对比。
- 投资组合收益率、年化波动率、最大回撤。
- 相关性矩阵、协方差矩阵和再平衡交易。
- HTML / CSV 报告导出。

对应文档和实验：

- [12-transaction-statement-analysis.md](12-transaction-statement-analysis.md)
- [13-portfolio-analysis.md](13-portfolio-analysis.md)
- [../labs/transaction-analysis/](../labs/transaction-analysis/)
- [../labs/portfolio-analysis/](../labs/portfolio-analysis/)

当前深度判断：适合做数据分析入门和作品展示，但不等于投资建议，也没有覆盖市场微观结构、证券交易生命周期、基金估值、组合优化、绩效归因和监管披露。

### 1.4 风控、KYC/AML 和人工复核

已覆盖内容：

- 交易风控规则、风险评分和 `approved / review / blocked` 决策。
- KYC/AML onboarding、beneficial owner、教学版 watchlist screening。
- 规则版本、策略版本、watchlist 版本。
- 人工复核案例和 replay。
- 风控和 KYC/AML 报表导出。

对应文档和实验：

- [14-risk-rule-engine.md](14-risk-rule-engine.md)
- [15-kyc-aml-onboarding.md](15-kyc-aml-onboarding.md)
- [../labs/risk-rule-engine/](../labs/risk-rule-engine/)
- [../labs/kyc-aml-onboarding/](../labs/kyc-aml-onboarding/)

当前深度判断：适合理解规则引擎、可解释决策和人工复核闭环，但不代表真实制裁名单、真实客户尽调、真实反洗钱规则、真实监管报送或模型风险管理。

### 1.5 合规审计、访问审计和调查工单

已覆盖内容：

- 合并风控和 KYC/AML audit events。
- 主体时间线、筛选、payload 脱敏。
- 角色权限、访问审计和报告导出审批。
- 访问异常检测和 investigation case。
- 留存策略报告。

对应文档和实验：

- [16-compliance-audit.md](16-compliance-audit.md)
- [../labs/compliance-audit/](../labs/compliance-audit/)

当前深度判断：适合理解 audit trail、access audit 和 investigation workflow 的工程轮廓，但不代表真实法律保全、WORM 存储、电子签名、证据链 custody 或真实监管留存期限。

### 1.6 端到端 FinTech 平台工程

已覆盖内容：

- KYC/AML -> payment order -> risk decision -> ledger posting -> audit timeline。
- FastAPI service boundary。
- async run store、worker、失败重试。
- operation approval maker-checker 审批。
- Console / Manual / detail views。
- role / permission policy 和身份一致性校验。
- operations report、ledger reconciliation、settlement reconciliation。
- access anomaly、investigation case、evidence package。
- readiness、metrics、test matrix。

对应文档和实验：

- [18-stage-8-summary-and-acceptance.md](18-stage-8-summary-and-acceptance.md) 到 [53-stage-40-final-acceptance-and-portfolio.md](53-stage-40-final-acceptance-and-portfolio.md)
- [../labs/fintech-platform/](../labs/fintech-platform/)

当前深度判断：这是仓库最强的部分，已经能展示一个教学版 FinTech 工程作品。但它仍不是生产系统，不覆盖真实 IAM、真实支付通道、真实部署、真实监控、secret 管理、CI/CD、分布式队列和生产级数据库迁移。

## 2. 仍然缺失的主要知识域

下表按“对程序员理解 FinTech 工程系统的价值”排序，不按金融学科完整性排序。

| 知识域 | 当前覆盖 | 为什么重要 | 建议落地方式 | 是否需要查证 |
| --- | --- | --- | --- | --- |
| 外部支付接口和 webhook | 已有教学版 provider intent link、webhook signature、FastAPI webhook endpoint、timestamp tolerance / replay window、event dedupe、settlement CSV parser、demo 中的 CSV 驱动 settlement reconciliation，以及 provider webhook evidence item；尚未接真实 provider API 或生产级 webhook 安全规则 | 真实支付系统的状态经常来自外部 provider，必须处理签名、重放、乱序、对账和证据留存 | 下一步可开始核心银行账户大章节，或查证真实 provider docs 后设计 adapter | 真实 API 和签名规则需要查证官方文档 |
| 银行业务和核心账户 | 已新增教学版 core banking basics 和 SQLite persistence：account product、bank account、ledger balance、available balance、account hold、daily interest accrual、monthly statement、account status、posting 幂等、SQLite products/accounts/postings/holds/audit events 落库、重复/跨连接 hold capture 状态保护、account optimistic version 条件更新，以及 statement summary / postings CSV、statement HTML report、statement.exported 和 statement.html_exported 审计事件；尚未做真实产品规则或信贷 | 存款、贷款、利息、账户状态和资金头寸是银行科技基础 | 下一步可做 statement activity filters、平台接入设计，或进入信贷生命周期 | 监管和产品规则需要查证 |
| 信贷生命周期 | 基本未覆盖 | 授信、放款、还款、逾期和损失准备是重要 FinTech 场景 | 新增 loan lifecycle lab：application、underwriting、repayment schedule、delinquency | 信用法规、披露、会计处理需要查证 |
| 证券交易生命周期 | 只有投资组合分析 | 交易、撮合、清算、结算、托管和保证金是资本市场系统核心 | 新增 securities trade lifecycle lab：order、fill、position、settlement | 交易所、清算机构和监管规则需要查证 |
| 会计和总账 | 有双分录但不完整 | 金融系统最终要能解释账务、科目、期间和报表 | 扩展 ledger：chart of accounts、journal entry、period close、adjustment | IFRS/GAAP 等准则需要查证 |
| 安全、隐私和身份 | 有教学版 role / permission | 金融系统必须处理登录、token、MFA、PII、密钥和审计 | 新增 auth/privacy boundary lab：token、CSRF、PII masking、key rotation demo | 标准和监管要求需要查证 |
| 数据治理和模型风险 | 有 replay 和报表雏形 | 风控和 AML 常依赖数据、规则和模型，必须管理版本、漂移和解释 | 新增 model governance lab：feature snapshot、model decision log、drift report | 模型风险管理框架需要查证 |
| 保险科技 | 未覆盖 | 保险有独立的保单、核保、理赔和准备金流程 | 可作为后续大章节，不建议马上做 | 产品和监管规则需要查证 |
| 加密资产和链上金融 | 未覆盖 | 概念热，但监管和产品形态变化快 | 暂不优先；如做，先做 custody / wallet 风险边界 | 高度需要查证 |
| 生产化基础设施 | 有 operability 教学版 | 作品要变成可交付系统，需要部署、CI、日志、metrics、alerting | 新增 CI / deployment / observability chapter | 工具文档可能需要查证 |

## 3. 稳定基础知识与时效性知识

### 稳定基础知识

这些内容相对稳定，适合先学并落到代码：

- account、transaction、ledger、journal entry。
- debit / credit 和双分录平衡。
- payment order 状态机。
- idempotency 和 request fingerprint。
- refund、reversal、settlement、reconciliation。
- audit trail、access audit、maker-checker approval。
- risk score、rule version、manual review。
- KYC/AML 的基本工程对象：application、customer、beneficial owner、screening result、review case。

这些知识仍然需要谨慎表述，但可以先用教学抽象建立直觉。

### 时效性知识

这些内容不能凭记忆写成事实，必须查证官方或专业来源：

- 最新监管政策、监管报送要求、制裁名单和 AML 规则。
- 真实支付 API、webhook 签名规则、清算文件格式和 dispute 流程。
- 银行、证券、保险产品规则。
- 市场数据、利率、汇率、价格、费用。
- PCI DSS、隐私法规、认证考试、行业报告。
- 具体机构、产品、平台的当前能力和价格。

文档中如暂时没有查证，应明确写成“待查证”，不能伪装成权威结论。

## 4. 建议学习顺序

### 第一优先级：外部支付和对账闭环

原因：当前综合平台已经有 internal run、ledger reconciliation 和 teaching settlement row，最自然的下一步是把“外部系统如何驱动内部状态”补齐。

已在现有综合平台内新增第一版：

```text
labs/fintech-platform/platform_payment_provider.py
docs/55-payment-provider-boundary.md
```

已覆盖能力：

- 教学版 provider payment intent 和 `provider_payment_intents.csv` link 表。
- webhook signature verifier。
- 教学版 FastAPI webhook endpoint。
- 教学版 timestamp tolerance / replay window。
- webhook event 去重、乱序处理和状态推进。
- settlement CSV parser。
- demo 生成 `provider_settlement_sample.csv`，解析后与现有 settlement reconciliation 对接。
- provider webhook access event 被打包为专门的 evidence item。

仍可继续扩展：

- provider intent 与 payment run 的更明确关联。
- 真实 provider adapter 前的官方文档查证。

需要查证：如果模拟 Stripe、PayPal、Visa 或其他真实接口，只能引用官方 developer docs，并标明访问日期。第一版可以先做“虚构 provider 协议”，避免误用真实规则。

### 第二优先级：核心银行账户和利息

原因：当前账本有 account，但还没有银行产品语义。补上 deposit account、interest accrual 和 account hold，可以让用户理解银行系统和普通支付系统的差别。

已新增第一版实验：

```text
labs/core-banking-basics/
docs/56-core-banking-basics.md
```

已覆盖能力：

- account product：checking / savings。
- bank account：customer、product、currency、status。
- ledger balance vs available balance。
- account hold：place / release / capture。
- deposit / withdraw。
- daily interest accrual 教学版计算和幂等键。
- monthly statement。
- frozen / closed account 状态控制。
- posting idempotency key + request fingerprint。
- SQLite products、accounts、postings 和 holds 持久化。
- 重开数据库后保持 balance、statement、interest accrual 和 idempotency 记录。
- 重复 capture / release 同一个 hold 的状态条件保护。
- 两个 SQLite 连接不能重复 capture 同一个 active hold 的教学测试。
- statement summary CSV 和 postings CSV 导出。
- account.opened、account.status_changed、posting.created、hold.placed、hold.released、hold.captured、interest.accrued 和 statement.exported 教学版 audit events。
- SQLite `core_banking_audit_events` 表持久化账户审计事件，重开数据库后仍可查询。
- statement HTML report，把 summary 和 posting details 输出成可人工阅读的静态 HTML。
- statement HTML export 可选记录 `statement.html_exported` audit event。
- SQLite account `version` 字段和 `expected_version` 条件更新。
- 两个 SQLite 连接不能基于同一个旧账户版本同时更新账户状态的 optimistic concurrency 教学测试。

仍可继续扩展：

- 更完整的 statement activity filters。
- lease、retry policy 或更接近生产的并发恢复演示。
- account limit、fees、overdraft、account ownership 等更完整银行对象。
- 与 `labs/fintech-platform/` 的资金流关系。

需要查证：真实利息规则、计息天数、产品披露、费用、税务和监管要求需要查证；教学版只能使用明确假设。

### 第三优先级：信贷生命周期

原因：信贷是 FinTech 重要主线，能复用 KYC、风控、账本、审计和报表。

建议新增实验：

```text
labs/loan-lifecycle/
```

候选能力：

- loan application。
- underwriting decision。
- repayment schedule。
- payment allocation。
- delinquency aging。
- charge-off 教学边界。

需要查证：真实消费者信贷、披露、催收、会计和监管规则都属于时效性或高风险内容。

### 第四优先级：生产化基础设施

原因：当前平台已能跑通，但还没有 CI、配置、日志结构、部署和更真实的可观测性。

已新增内容：

```text
scripts/verify_labs.ps1
```

已覆盖能力：

- 一键本地验证。
- 设置 `PYTHONIOENCODING=utf-8`，降低 Windows 控制台编码问题。
- 使用 `-B` 避免 bytecode cache 干扰验证。
- 支持跳过 demo、全量 labs 测试和浏览器回归，便于快速验证。

仍可作为后续候选能力：

- `docs/57-production-readiness-roadmap.md`。
- 结构化日志示例。
- CI 测试矩阵。
- demo 数据清理。

需要查证：具体 CI 平台、部署平台、监控工具文档可能随版本变化。

## 5. 不建议马上做的事情

- 不建议重排整个仓库目录。当前 `docs/` + `labs/` 的结构清楚，重排会破坏历史引用。
- 不建议继续新增很多细碎阶段文档。后续应按大章节推进。
- 不建议立刻把教学平台包装成真实金融产品。真实合规、支付、身份、隐私和部署边界都需要更严肃的资料查证。
- 不建议优先做加密资产、量化交易或复杂 AI 风控。它们容易吸引注意力，但对当前“程序员理解 FinTech 工程系统”的主线帮助不如支付、银行账户和信贷。

## 6. 下一步建议

建议下一步选择其一：

1. 新增 `payment-provider-adapter` 实验，补外部 provider、webhook 和 settlement parser。
2. 扩展 `core-banking-basics`，补 activity filters、平台接入设计或更接近生产的并发恢复演示。
3. 补 `docs/57-production-readiness-roadmap.md`，把 CI、配置、日志、metrics 和交付边界整理成后续工程路线。

如果目标是最快让作品集更完整，推荐顺序是：

```text
labs/payment-provider-adapter/
-> labs/core-banking-basics/
-> labs/core-banking-basics activity filters / platform integration
-> labs/loan-lifecycle/
```

当前已先补 `scripts/verify_labs.ps1` 来稳定本地验证入口，并完成 `payment provider boundary`、`core banking basics`、SQLite persistence、重复 hold 消费保护、statement CSV/HTML export、core banking audit events 和 account optimistic version 第一版。后续可以继续补 core banking activity filters / 平台接入，或进入信贷生命周期。
