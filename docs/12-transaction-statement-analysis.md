# 交易流水分析：CSV 导入、分类和月度现金流

最后更新：2026-05-05

本篇开始从“支付系统工程”切换到“金融数据分析”。我们先做一个很小但完整的实验：把一份银行交易流水 CSV 导入 SQLite，然后用 SQL 和 Pandas 计算月度收入、支出和净现金流。

## 先给结论

交易流水分析的最小闭环是：

```text
CSV statement -> normalized transactions table -> SQL aggregation -> cashflow report
```

当前实验只处理个人账户或银行卡流水里最常见的字段：

- `transaction_id`：交易唯一标识。
- `posted_date`：入账日期。
- `description`：交易描述或商户名称。
- `amount`：有符号金额，正数表示流入，负数表示流出。

导入后，系统会用一组简单关键词规则给交易打分类，再按月份计算：

- `income`：正金额合计。
- `expense`：负金额的绝对值合计。
- `net_cashflow`：收入减支出。

## 中文定义

交易流水分析，是把账户里的每一笔交易记录结构化，然后按时间、金额方向、商户、类别或账户维度做汇总和解释。

英文术语常见写法：

- 交易流水：transaction statement / account transactions
- 现金流：cashflow
- 收入：income / inflow
- 支出：expense / outflow
- 分类：categorization
- 对账：reconciliation

## 核心概念逐个解释

### 交易流水 transaction statement / account transactions

交易流水是账户在一段时间内发生的交易记录列表。它可以来自银行账户、信用卡账户、支付钱包、证券账户或第三方金融数据 API。

一条流水通常至少回答这些问题：

- 什么时候发生或入账？
- 谁发起或接收？
- 金额是多少？
- 是流入还是流出？
- 交易描述是什么？
- 交易是否已经入账、撤销或调整？

在真实金融领域，交易流水是很多系统的输入数据。个人财务管理用它分析消费结构；信贷风控用它观察收入和支出稳定性；支付运营用它做渠道对账；合规和审计用它追踪资金流向。

程序员容易误解的一点是：流水不一定等于“实时发生的业务动作”。有些交易有授权时间、交易时间、清算时间和入账时间。当前实验只使用 `posted_date`，代表“入账日期”的简化版本。

### 入账日期 posted date

`posted_date` 是交易正式记到账户上的日期。它不一定等于用户刷卡、转账或下单的时间。

例如信用卡消费可能在 1 月 2 日发生，但 1 月 3 日才入账。银行系统、信用卡系统和支付网络中，授权、清算、结算、入账可能是不同阶段。

真实场景里，日期字段非常重要，因为报表、利息、账单周期、还款周期、对账周期都依赖日期。程序员实现时要先弄清楚字段语义：是交易发生日、授权日、入账日，还是结算日。

### 有符号金额 signed amount

当前实验用正负号表示资金方向：

```text
正数：资金流入账户
负数：资金流出账户
```

这是一种常见建模方式，但不是唯一方式。有些银行或 API 会把金额永远保存为正数，再单独提供 `debit/credit`、`inflow/outflow` 或 `direction` 字段。

真实金融系统里，金额方向不能靠猜。错误理解金额方向会直接导致收入、支出、余额和风控指标全部错误。

### 现金流 cashflow

现金流关注的是一段时间内资金流入和流出的情况。当前实验里的月度现金流是：

```text
net_cashflow = income - expense
```

真实场景中，现金流分析常用于：

- 判断个人或企业收入是否稳定。
- 判断支出结构是否健康。
- 评估还款能力。
- 做预算、经营分析或资金计划。

现金流不等同于利润，也不等同于净资产。它只回答“钱在这个时间段里如何进出”。

### 分类 categorization

分类是把交易归到收入、房租、餐饮、交通、购物等类别里。

真实产品里，分类会影响用户看到的消费分析，也可能影响风控模型、预算提醒和运营报表。分类错误会导致用户不信任报表，也会污染后续分析。

当前实验用关键词规则，例如描述里包含 `grocery` 就归为 `groceries`。真实系统通常会更复杂，可能结合：

- 商户标准化。
- 商户类别码 MCC。
- 用户手动修正。
- 历史分类偏好。
- 机器学习模型。

### 对账 reconciliation

对账是确认两套或多套记录是否一致。比如平台订单系统记录用户支付了 `100.00`，支付渠道回调也说成功，银行流水最终也入账了 `100.00`，这三方需要能对上。

真实金融系统里，对账是非常核心的后台能力。原因是网络延迟、重复回调、退款、手续费、汇率、清算批次和人工调整都会造成账目不一致。

当前交易流水实验没有实现完整对账，但前面的账本和支付订单实验已经为对账打了基础：订单、事件、账本分录和银行流水最终应该能互相解释。

### 预算 budget

预算是预先设定的支出计划或额度。当前实验里的预算对比只做最小计算：

```text
remaining = budget - actual
```

真实场景中，预算可以用于个人财务管理、企业费用控制、信用卡消费提醒和运营支出监控。预算不是强制风控规则，但它可以成为提醒、分析或审核的依据。

## 为什么金融系统需要它

交易流水是很多 FinTech 产品的基础数据：

- 个人财务管理：识别收入、餐饮、房租、交通、购物等支出类别。
- 信贷风控：观察收入稳定性、负债支出、异常大额交易。
- 银行数据开放：让用户授权第三方读取账户交易数据。
- 对账和运营：核对系统订单、支付渠道、银行入账是否一致。

本实验不做信用评估，也不提供投资建议，只学习数据建模和分析方法。

## 程序员实现时要注意什么

第一，金额不要用浮点数存储。当前实验在 SQLite 中使用 `amount_cents` 整数分保存金额，例如 `12.34` 保存为 `1234`，`-8.50` 保存为 `-850`。

第二，不同数据来源的字段含义可能不同。有的银行用正负号表示收入和支出，有的银行会分成 debit/credit 两列，有的 API 会用独立方向字段。本实验选择最小 CSV 格式，不代表所有真实机构格式。

第三，交易分类一开始可以用关键词规则，但这只是教学版本。真实系统通常还会结合商户标准化、MCC、账户类型、用户修正记录和机器学习模型。

第四，导入要考虑幂等。当前实验用 `transaction_id` 做主键；同一份 CSV 重复导入时，已存在的交易会被跳过，不会重复计入月度汇总。

第五，分类规则最好和代码分离。规则经常会调整，例如新增商户、修正误分类、拆分更细的类别。如果每次都改 Python 代码，维护成本会很高，也不利于非工程角色参与配置。

## 当前实验数据格式

示例 CSV：

```csv
transaction_id,posted_date,description,amount
txn_001,2026-01-02,Payroll ACME Corp,3200.00
txn_002,2026-01-03,City Grocery Market,-86.45
txn_003,2026-01-05,Metro Transit,-32.00
```

金额规则：

```text
amount > 0  流入，例如工资、利息、退款
amount < 0  流出，例如房租、餐饮、购物
```

## 可配置分类规则

当前实验把分类规则放在：

```text
labs/transaction-analysis/category_rules.csv
```

格式很简单：

```csv
category,keyword
income,payroll
groceries,grocery
dining,restaurant
transport,metro
```

导入流水时，系统会按规则顺序检查 `description` 是否包含某个 `keyword`。匹配到第一条规则后，就使用对应的 `category`。如果没有任何规则匹配，则分类为 `other`。

这仍然是教学版规则引擎，但它比写死在代码里更接近真实系统：

- 规则可以单独查看。
- 新增规则不需要改核心导入逻辑。
- 测试可以验证“配置文件缺列、空规则、未知商户”等场景。
- 后续可以扩展优先级、商户标准化或用户手动修正。

## SQLite 表结构

当前实验使用一张核心表：

```sql
CREATE TABLE bank_transactions (
    id TEXT PRIMARY KEY,
    posted_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents != 0),
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
```

`posted_date` 使用 ISO 日期字符串，例如 `2026-01-02`。SQLite 官方文档说明 SQLite 没有专门的日期时间类型，日期时间值可以用 ISO-8601 文本、Julian day number 或 Unix timestamp 等形式保存；本实验选择 ISO 文本，便于阅读和用 `strftime('%Y-%m', posted_date)` 做月度分组。

## 月度现金流 SQL

核心查询：

```sql
SELECT
    strftime('%Y-%m', posted_date) AS month,
    SUM(CASE WHEN amount_cents > 0 THEN amount_cents ELSE 0 END) AS income_cents,
    SUM(CASE WHEN amount_cents < 0 THEN -amount_cents ELSE 0 END) AS expense_cents,
    SUM(amount_cents) AS net_cents
FROM bank_transactions
GROUP BY month
ORDER BY month;
```

这里把支出取绝对值，是为了报表里展示“支出 1800.00”，而不是“支出 -1800.00”。净现金流仍然保留正负含义：

```text
net_cashflow = income - expense
```

## Pandas 版本

Pandas 适合做更复杂的分析，例如：

- 按月份、类别和账户多维分组。
- 计算滚动平均。
- 做图表和探索式分析。
- 处理较复杂的 CSV 清洗。

本实验的 Pandas 版本会从 SQLite 读取交易，按 `posted_date` 转成月份，再 groupby 得到收入、支出和净现金流。

## 按类别的月度支出矩阵

月度现金流回答的是：

```text
这个月总收入多少，总支出多少，净现金流多少？
```

但交易流水分析还需要回答：

```text
这个月钱花在了哪些类别上？
哪些类别连续几个月上升？
哪些类别超过预算？
```

因此当前实验新增了“月份 × 支出类别”的矩阵：

```text
month    dining  groceries  rent     shopping  transport  utilities
2026-01  5.75    86.45      1450.00  0.00      32.00      94.20
2026-02  48.80   91.30      0.00     124.99    0.00       0.00
```

这类表在数据分析里通常叫 pivot table。直觉上，它就是把 `category` 这一列展开成多列，让每个月的支出结构能横向比较。

## 预算和实际支出对比

预算对比的最小公式是：

```text
remaining = budget - actual
```

如果 `remaining < 0`，说明实际支出超过预算。

当前实验的 `compare_monthly_budget()` 接收一个预算字典：

```python
{
    "groceries": "200.00",
    "rent": "1450.00",
    "transport": "60.00",
}
```

然后输出每个类别的：

- budget：预算。
- actual：实际支出。
- remaining：剩余额度。
- is_over_budget：是否超预算。

注意：这是学习用的个人现金流分析，不是会计准则意义上的正式预算管理，也不是个人理财建议。

## HTML 报告和 CSV 导出

分析结果如果只停留在 Python 对象或终端输出里，很难给其他人阅读，也不方便后续复核。真实金融系统常常需要把分析结果落成报表、文件、审计附件或运营看板。

当前实验新增一个最小报告生成器：

```text
SQLite transactions -> monthly summary -> HTML report + CSV exports
```

运行 demo 后会生成：

```text
labs/transaction-analysis/reports/transaction_analysis_report.html
labs/transaction-analysis/reports/monthly_cashflow.csv
labs/transaction-analysis/reports/monthly_expense_matrix.csv
```

HTML 报告适合直接打开阅读；CSV 文件适合继续用 Excel、LibreOffice、Pandas 或其他 BI 工具分析。

这里刻意没有引入 Web 框架。原因是当前学习目标是掌握交易流水分析闭环，而不是做一个完整报表系统。先把数据、计算和导出打通，比过早做前端更稳。

## 当前实验新增了什么

- `labs/transaction-analysis/sample_transactions.csv`
- `labs/transaction-analysis/category_rules.csv`
- `labs/transaction-analysis/transaction_analysis.py`
- `labs/transaction-analysis/reporting.py`
- `labs/transaction-analysis/demo.py`
- `labs/transaction-analysis/test_transaction_analysis.py`
- `category_monthly_expense_matrix()`
- `compare_monthly_budget()`
- `generate_analysis_report()`
- `CategoryRuleSet.from_csv()`

运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\transaction-analysis\demo.py
```

运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\transaction-analysis
```

## 资料来源

- CFPB, Personal Financial Data Rights, § 1033.211 Covered data: https://www.consumerfinance.gov/rules-policy/regulations/1033/211
- SQLite, Date And Time Functions: https://www.sqlite.org/lang_datefunc.html
- pandas, `read_csv`: https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
- pandas, Group by: split-apply-combine: https://pandas.pydata.org/pandas-docs/stable/user_guide/groupby.html

访问日期：2026-05-05
