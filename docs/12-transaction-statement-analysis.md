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

## 当前实验新增了什么

- `labs/transaction-analysis/sample_transactions.csv`
- `labs/transaction-analysis/transaction_analysis.py`
- `labs/transaction-analysis/demo.py`
- `labs/transaction-analysis/test_transaction_analysis.py`
- `category_monthly_expense_matrix()`
- `compare_monthly_budget()`

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
