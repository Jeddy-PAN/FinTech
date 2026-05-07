# Learning Progress

最后更新：2026-05-07

## 当前状态

- 学习者背景：程序员，金融和 FinTech 目前按零基础处理。
- 当前阶段：阶段 5，进入风控规则引擎基础。
- 当前主线：用最小规则引擎理解限额、规则命中、可解释决策、人工审核和持久化审计。
- 当前仓库状态：已完成账本基础实验、支付订单实验、交易流水分析实验、投资组合分析实验，以及风控规则引擎、人工复核状态机、SQLite 持久化、风控审计事件日志、规则版本记录、第一组非金额风险信号、教学版风险评分、纯评分策略、可筛选规则命中统计报表、规则版本对比报表和风控报表导出。

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

当前已完成第一版学习材料和代码实验，支持从 JSON 配置读取规则参数，已加入最小人工复核状态机、SQLite 持久化、追加式风控审计事件、规则版本记录、第一组非金额风险信号、教学版风险评分、纯评分策略、可筛选规则命中统计报表、规则版本对比报表和风控报表导出；下一步可进入 KYC/AML/合规基础。

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

- pytest 曾生成 `pytest-cache-files-*` 临时目录且当前无法删除，已通过 `.ignore` 和 `.gitignore` 忽略，避免影响 `rg --files`。
- pytest 的默认用户临时目录曾出现访问权限问题；测试数据优先写入仓库内各实验的 `.test-data/`，并已忽略该目录。

## 中期路线

1. 双分录账本：理解金融系统底层记账。
2. 支付订单系统：理解订单状态、退款、回调、幂等。
3. 交易流水分析：理解个人金融数据和报表。
4. 投资组合实验：理解收益率、波动率、最大回撤。
5. 风控规则引擎：理解异常检测、额度、评分和审核。
6. 合规与审计：理解 KYC、AML、日志、权限和数据保护。

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
