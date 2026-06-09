# FinTech Learning Lab

这是一个面向“程序员零基础学习金融科技”的协作仓库。目标不是只整理概念，而是把每个关键知识点尽量落到可运行的小实验里。

## 当前定位

- 学习对象：有编程背景，金融领域零基础。
- 学习目标：理解金融业务、FinTech 工程系统、数据分析、风控和合规基础。
- 学习方式：先学概念，再写最小实验，再把知识沉淀成文档。
- 当前阶段：阶段 24 第一版已完成，operation approval 支持只读详情页，可查看 approval、关联 async run 和 completed platform result 摘要。

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
│   ├── README.md              # 文档入口、阅读路径和平台能力地图
│   ├── 00-authoritative-sources.md
│   ├── 01-16-*.md             # 基础概念和早期实验笔记
│   └── 17-37-*.md             # 阶段计划、总结和平台演进记录
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

## 快速阅读路径

详细文档导航、阶段文档说明和当前平台能力地图见 [docs/README.md](docs/README.md)。

建议按目标选择路径：

1. 从零开始学 FinTech：先读 [docs/00-authoritative-sources.md](docs/00-authoritative-sources.md)、[docs/01-fintech-overview.md](docs/01-fintech-overview.md)、[docs/02-developer-to-finance.md](docs/02-developer-to-finance.md)，再按 `docs/03` 到 `docs/16` 逐步进入账本、支付、风控、KYC/AML 和合规审计。
2. 直接理解综合平台：先读 [labs/fintech-platform/README.md](labs/fintech-platform/README.md)，再读 [docs/37-stage-24-operation-approval-detail-view.md](docs/37-stage-24-operation-approval-detail-view.md) 了解当前最新 operation approval detail view。
3. 运行工程作品：执行 `& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py`，观察端到端支付、async run、retry、access audit、investigation case、operations report、approval report、ledger reconciliation report、operation approval HTTP flow 和 console report views。
4. 继续协作前：先看 [LEARNING_PROGRESS.md](LEARNING_PROGRESS.md) 的“当前状态”和“最新记录”，确认当前阶段和下一步候选方向。

## 协作原则

- 所有“最新监管、API、市场数据、产品规则、考试认证”都必须查证官方或专业来源。
- 概念解释要区分“稳定金融基础知识”和“可能变化的行业信息”。
- 不把 AI 生成内容当作权威结论；没有来源的内容只能作为待验证假设。
- 每完成一个学习单元或代码实验，都要更新 `LEARNING_PROGRESS.md`。
