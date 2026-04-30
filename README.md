# FinTech Learning Lab

这是一个面向“程序员零基础学习金融科技”的协作仓库。目标不是只整理概念，而是把每个关键知识点尽量落到可运行的小实验里。

## 当前定位

- 学习对象：有编程背景，金融领域零基础。
- 学习目标：理解金融业务、FinTech 工程系统、数据分析、风控和合规基础。
- 学习方式：先学概念，再写最小实验，再把知识沉淀成文档。
- 当前阶段：阶段 0，建立学习框架、资料来源和协作规则。

## 目录结构

```text
.
├── AGENTS.md                  # 后续 AI 终端协作规则
├── LEARNING_PROGRESS.md       # 当前学习进度、计划和交接记录
├── README.md                  # 仓库入口
├── docs/                      # 金融科技基础知识和权威资料
│   ├── 00-authoritative-sources.md
│   ├── 01-fintech-overview.md
│   └── 02-developer-to-finance.md
└── labs/                      # 后续代码实验
    └── ledger-basics/         # 第一个实验：双分录账本
```

## 建议学习顺序

1. 先读 [LEARNING_PROGRESS.md](LEARNING_PROGRESS.md)，确认当前进度和下一步任务。
2. 再读 [docs/00-authoritative-sources.md](docs/00-authoritative-sources.md)，理解哪些资料可以作为权威来源。
3. 读 [docs/01-fintech-overview.md](docs/01-fintech-overview.md)，建立 FinTech 地图。
4. 读 [docs/02-developer-to-finance.md](docs/02-developer-to-finance.md)，理解程序员转金融领域需要补什么。
5. 开始 `labs/ledger-basics/`，用代码理解账户、交易、余额和审计。

## 协作原则

- 所有“最新监管、API、市场数据、产品规则、考试认证”都必须查证官方或专业来源。
- 概念解释要区分“稳定金融基础知识”和“可能变化的行业信息”。
- 不把 AI 生成内容当作权威结论；没有来源的内容只能作为待验证假设。
- 每完成一个学习单元或代码实验，都要更新 `LEARNING_PROGRESS.md`。
