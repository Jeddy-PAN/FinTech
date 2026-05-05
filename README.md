# FinTech Learning Lab

这是一个面向“程序员零基础学习金融科技”的协作仓库。目标不是只整理概念，而是把每个关键知识点尽量落到可运行的小实验里。

## 当前定位

- 学习对象：有编程背景，金融领域零基础。
- 学习目标：理解金融业务、FinTech 工程系统、数据分析、风控和合规基础。
- 学习方式：先学概念，再写最小实验，再把知识沉淀成文档。
- 当前阶段：阶段 3，进入交易流水分析和金融数据分析基础。

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
│   └── 12-transaction-statement-analysis.md
└── labs/                      # 后续代码实验
    ├── ledger-basics/         # 第一个实验：双分录账本
    ├── payment-orders/        # 第二个实验：支付订单系统
    └── transaction-analysis/  # 第三个实验：交易流水分析
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

## 协作原则

- 所有“最新监管、API、市场数据、产品规则、考试认证”都必须查证官方或专业来源。
- 概念解释要区分“稳定金融基础知识”和“可能变化的行业信息”。
- 不把 AI 生成内容当作权威结论；没有来源的内容只能作为待验证假设。
- 每完成一个学习单元或代码实验，都要更新 `LEARNING_PROGRESS.md`。
