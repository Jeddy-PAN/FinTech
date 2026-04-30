# Learning Progress

最后更新：2026-04-30

## 当前状态

- 学习者背景：程序员，金融和 FinTech 目前按零基础处理。
- 当前阶段：阶段 1，学习账本基础并完成第一个最小代码实验。
- 当前主线：用“双分录账本”理解账户、交易、分录、余额和借贷平衡。
- 当前仓库状态：已建立账本基础文档和 `labs/ledger-basics/` 内存版实验。

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

当前已完成前六项的第一版学习材料和代码实验；幂等 idempotency 后续在支付回调或重复提交场景中加入。

## 近期计划

### 第 1 周

- 阅读 `docs/01-fintech-overview.md`
- 阅读 `docs/02-developer-to-finance.md`
- 阅读 `docs/03-ledger-basics.md`
- 运行 `labs/ledger-basics/demo.py`
- 理解 demo 中两笔交易：用户充值、平台收取手续费
- 在测试里观察“不平衡交易会被拒绝”

### 第 2 周

- 给账本实验加入 SQLite 存储
- 添加 pytest 测试
- 学习双分录记账的最小规则：每笔交易借贷平衡
- 加入幂等键 idempotency key，模拟重复支付回调不会重复入账

## 本机环境记录

- 用户偏好使用 Anaconda / conda 管理 Python 环境。
- 默认 `python` 命令当前指向不可用的 Windows Store alias。
- 已验证可用 Python：`C:\App\Anaconda\python.exe`
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

- pytest 曾生成 `pytest-cache-files-*` 临时目录且当前无法删除，已通过 `.ignore` 和 `.gitignore` 忽略，避免影响 `rg --files`。

### 第 3-4 周

- 实现交易流水导入和分类
- 学习 SQL 查询、聚合、分组和窗口函数
- 用 Pandas 计算月度支出、收入、现金流

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
