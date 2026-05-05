# Learning Progress

最后更新：2026-05-05

## 当前状态

- 学习者背景：程序员，金融和 FinTech 目前按零基础处理。
- 当前阶段：阶段 3，进入交易流水分析和金融数据分析基础。
- 当前主线：把账户交易流水导入 SQLite，理解交易分类、SQL 月度聚合、Pandas 分组分析和个人现金流报表。
- 当前仓库状态：已完成账本基础实验、支付订单实验、outbox publisher 第一版，以及交易流水分析第一版。

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

当前已完成第一版学习材料和代码实验，并新增了按类别的月度支出矩阵和预算对比；下一步可加入简单图表或导出报表。

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
- 下一步可扩展简单图表、CSV 导出或更细的分类规则

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
