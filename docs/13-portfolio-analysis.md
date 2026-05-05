# 投资组合分析：收益率、波动率和最大回撤

最后更新：2026-05-05

本篇开始进入投资组合实验。目标不是挑选股票，也不是预测市场，而是学习金融数据分析里最基础的一组指标：收益率、组合收益、波动率和最大回撤。

## 先给结论

投资组合分析的最小闭环是：

```text
price history -> asset returns -> portfolio returns -> risk metrics
```

当前实验使用一份教学用 CSV 价格数据，计算：

- 单个资产每日收益率。
- 给定权重下的组合每日收益率。
- 累计收益率 cumulative return。
- 年化波动率 annualized volatility。
- 最大回撤 maximum drawdown。

这些指标只用于学习计算方法，不代表投资建议。

## 中文定义

投资组合，是多个资产按一定权重组成的一组投资。英文常见写法是 portfolio。

收益率 return，是资产价格相对上一期的变化比例：

```text
return_t = price_t / price_{t-1} - 1
```

例如价格从 `100` 涨到 `102`：

```text
102 / 100 - 1 = 0.02 = 2%
```

## 核心概念逐个解释

### 资产 asset

资产是投资组合里持有的对象，例如股票、债券、基金、现金、商品、外汇或数字资产。当前实验里的 `STOCK_A` 和 `BOND_B` 是教学用的虚拟资产名称，不代表真实证券。

真实金融领域中，资产是投资、估值、风险和合规系统的基础对象。不同资产有不同的交易规则、价格来源、流动性、风险特征和监管要求。

程序员实现时要注意：资产代码并不总是全局唯一。真实系统通常需要区分交易所、币种、资产类型、价格来源和有效日期。

### 价格历史 price history

价格历史是一组按日期排列的资产价格。它可以是收盘价、复权价、净值、成交价或估值价格。

当前实验用 `close` 表示期末价格。真实场景中，选择什么价格非常重要：

- 股票分析常用收盘价或复权收盘价。
- 基金常用净值 NAV。
- 债券可能用净价、全价或估值价。
- 非流动资产可能没有每日市场价格。

收益率计算依赖价格序列。如果价格缺失、排序错误、币种混乱或没有处理分红拆股，指标都会失真。

### 收益率 return

收益率表示价格相对上一期变化了多少。它不是金额，而是比例。

例如：

```text
100 -> 102  收益率是 2%
100 -> 98   收益率是 -2%
```

真实金融系统使用收益率，是因为不同资产价格单位不同。一个资产从 `10` 到 `11`，另一个从 `1000` 到 `1010`，直接比较价格变化没有意义；比较收益率才有可比性。

程序员实现时要区分：

- 简单收益率 simple return：`price_t / price_{t-1} - 1`
- 对数收益率 log return：`log(price_t / price_{t-1})`

当前实验只使用简单收益率。

### 投资组合 portfolio

投资组合是多个资产和权重的集合。它回答的是“钱分别配置到哪些资产上”。

例如：

```text
STOCK_A 60%
BOND_B  40%
```

真实金融领域中，投资组合用于财富管理、基金管理、Robo-advisor、养老金、保险资金管理和机构投研。系统不仅要计算收益，还要监控风险、集中度、限制条件和再平衡需求。

程序员容易误解的一点是：组合不是简单把资产放在列表里。组合还需要权重、持仓数量、市值、币种、估值日期和交易约束。

### 权重 weight

权重表示某个资产在组合总市值中的占比。

```text
weight_i = asset_value_i / total_portfolio_value
```

真实场景中，权重用于资产配置、风险控制和再平衡。例如一个策略规定股票 60%、债券 40%，系统就需要监控当前权重是否偏离目标。

当前实验要求权重非负且合计为 `1.0`。真实系统中还可能有现金权重、杠杆、做空、衍生品敞口等复杂情况。

### 累计收益率 cumulative return

累计收益率表示从起点到终点总共赚了或亏了多少。

它不是简单把每日收益率相加，而是复利连乘：

```text
(1 + r_1) * (1 + r_2) * ... * (1 + r_n) - 1
```

真实场景中，累计收益率常用于展示账户、基金或策略在某段时间内的表现。但单独看累计收益率是不够的，因为同样的收益可能对应完全不同的波动和回撤路径。

### 波动率 volatility

波动率衡量收益率上下波动的程度。当前实验使用每日收益率标准差，并乘以 `sqrt(252)` 得到年化波动率。

真实金融领域中，波动率常被当作风险指标之一。波动越大，说明收益路径越不稳定。但波动率不是全部风险：它不能完整描述流动性风险、信用风险、极端尾部风险和操作风险。

程序员实现时要固定口径，例如：

- 用日收益、周收益还是月收益？
- 是否年化？
- 年化假设用 252 个交易日还是其他口径？
- 标准差使用样本标准差还是总体标准差？

当前实验使用 Pandas 默认样本标准差 `ddof=1`。

### 最大回撤 maximum drawdown

最大回撤表示从历史高点到后续低点的最大跌幅。

它回答的是：

```text
如果在历史最高点买入，后面最痛的一段亏损有多大？
```

真实场景中，最大回撤对投资者体验很重要。两个组合最终收益可能一样，但其中一个中途跌过 40%，另一个只跌过 5%，风险感受完全不同。

最大回撤是历史指标，不能保证未来不会出现更大亏损。

### 相关性 correlation

相关性衡量两个资产收益是否倾向于一起涨跌。

如果两个资产相关性很高，它们可能在压力时期一起下跌，分散化效果有限。如果相关性较低或为负，组合波动可能降低。

真实投资组合管理中，相关性用于理解分散化是否有效。但相关性会随市场环境变化，危机时很多资产相关性可能突然上升。

### 协方差 covariance

协方差和相关性类似，也描述两个资产收益的共同变化，但它保留了波动率大小。组合风险公式使用的是协方差矩阵，而不是相关性矩阵。

对程序员来说，可以先记住：

```text
相关性更适合解释关系强弱
协方差更适合计算组合风险
```

### 再平衡 rebalancing

再平衡是把当前组合调回目标权重。

真实场景中，再平衡可以按时间触发，例如每月一次；也可以按偏离阈值触发，例如股票权重超过目标 5% 后调整。

再平衡不是简单数学动作。真实系统还要考虑交易成本、税费、最小交易单位、流动性、账户限制、合规限制和用户授权。当前实验只计算理论上的买卖金额和份额。

## 为什么金融系统需要它

很多金融科技系统都会涉及投资组合分析：

- 财富管理：展示账户收益、风险和资产配置。
- Robo-advisor：根据目标权重构建组合并定期再平衡。
- 风控系统：监控组合波动、回撤和集中度。
- 投研工具：比较不同资产或策略的历史表现。

美国 SEC 的投资者教育材料强调，资产配置、分散化和再平衡都和投资组合风险有关。这里我们只做指标计算，不做任何资产推荐。

## 程序员实现时要注意什么

第一，价格数据必须按日期排序。收益率是相邻日期之间的变化，顺序错误会直接导致结果错误。

第二，收益率不是百分号字符串，而是小数。例如 `0.02` 表示 `2%`。

第三，组合收益率依赖权重。当前实验使用固定目标权重，并把每日组合收益近似为各资产每日收益率的加权和：

```text
portfolio_return_t = sum(weight_i * return_i_t)
```

这等价于一个教学版假设：组合每天都维持目标权重，不考虑交易成本、税费、滑点和再平衡限制。

第四，波动率是风险指标之一，但不是全部风险。流动性、信用风险、集中度、极端事件和数据质量都可能影响真实投资风险。

第五，最大回撤关注的是“从历史高点跌到低点”的最大跌幅。它对理解亏损路径很直观，但仍然是历史指标，不能保证未来。

第六，组合风险不只取决于每个资产自己的波动，也取决于资产之间是否同涨同跌。这就需要相关性矩阵和协方差矩阵。

## 当前实验数据格式

示例 CSV：

```csv
date,asset,close
2026-01-02,STOCK_A,100.00
2026-01-02,BOND_B,100.00
2026-01-05,STOCK_A,102.00
2026-01-05,BOND_B,100.50
```

字段含义：

- `date`：价格日期。
- `asset`：资产代码或资产名。
- `close`：收盘价或期末价格。

## 核心指标

### 累计收益率

如果每天收益率分别是 `r_1, r_2, ..., r_n`，累计收益率是：

```text
(1 + r_1) * (1 + r_2) * ... * (1 + r_n) - 1
```

它回答的是：从起点持有到终点，总共涨跌了多少。

### 年化波动率

当前实验用每日收益率标准差乘以 `sqrt(252)`：

```text
annualized_volatility = std(daily_returns) * sqrt(252)
```

`252` 是常用的年度交易日近似值。它是简化假设，不是自然定律。

### 最大回撤

先把组合收益转成净值曲线：

```text
portfolio_value_t = cumulative product of (1 + portfolio_return_t)
```

再计算每一天相对历史高点的跌幅：

```text
drawdown_t = portfolio_value_t / running_peak_t - 1
```

最大回撤就是所有 `drawdown_t` 里最小的那个值。

## 相关性和协方差

相关性 correlation 衡量两个资产收益率是否倾向于同向变化。常见范围是：

```text
+1  完全同向
 0  线性关系很弱
-1  完全反向
```

协方差 covariance 同样描述两个资产收益率的共同变化，但它保留了收益率单位和波动大小。相关性更适合直观比较“关系强弱”，协方差更适合放进组合风险公式。

当前实验新增：

```python
calculate_correlation_matrix(asset_returns)
calculate_covariance_matrix(asset_returns, annualize=True)
```

组合方差可以写成：

```text
portfolio_variance = w^T * Sigma * w
```

其中：

- `w` 是资产权重向量。
- `Sigma` 是资产收益率协方差矩阵。
- `w^T` 是权重向量的转置。

组合波动率就是：

```text
portfolio_volatility = sqrt(w^T * Sigma * w)
```

如果 `Sigma` 是日度协方差矩阵，得到的是日度波动率。如果 `Sigma` 已经乘以 `252` 年化，得到的是年化波动率。

这个公式很重要，因为它说明分散化的核心不是“资产数量越多越好”，而是资产之间的共同波动也会影响组合风险。

## 组合再平衡

组合再平衡 rebalancing，是把当前持仓重新调整回目标权重的过程。

例如目标权重是：

```text
STOCK_A 60%
BOND_B  40%
```

但经过价格涨跌后，当前权重可能变成：

```text
STOCK_A 41.58%
BOND_B  58.42%
```

这时如果想回到目标权重，就需要卖出一部分 `BOND_B`，买入一部分 `STOCK_A`。

当前实验的再平衡计算分几步：

1. 用最新价格和当前份额计算每个资产的当前市值。
2. 把每个资产当前市值除以总市值，得到当前权重。
3. 用总市值乘以目标权重，得到目标市值。
4. 用目标市值减当前市值，得到交易金额。
5. 用交易金额除以最新价格，得到交易份额。

公式是：

```text
current_value_i = current_quantity_i * latest_price_i
target_value_i = total_portfolio_value * target_weight_i
trade_value_i = target_value_i - current_value_i
trade_quantity_i = trade_value_i / latest_price_i
```

在当前实验里：

- `trade_value > 0` 表示需要买入。
- `trade_value < 0` 表示需要卖出。

注意：这是教学版再平衡，不考虑交易费用、税费、最小交易单位、买卖价差、流动性和真实下单风险。

## HTML 报告和 CSV 导出

投资组合分析通常不会只停留在终端输出。为了便于复核和展示，当前实验新增报告导出：

```text
prices -> returns -> metrics/risk/rebalance -> HTML report + CSV exports
```

运行 demo 后会生成：

```text
labs/portfolio-analysis/reports/portfolio_analysis_report.html
labs/portfolio-analysis/reports/asset_returns.csv
labs/portfolio-analysis/reports/portfolio_returns.csv
labs/portfolio-analysis/reports/correlation_matrix.csv
labs/portfolio-analysis/reports/annualized_covariance_matrix.csv
labs/portfolio-analysis/reports/rebalance_trades.csv
```

HTML 报告适合直接打开查看；CSV 文件适合继续用 Pandas、Excel、LibreOffice 或 BI 工具分析。

这里仍然不引入 Web 框架，原因和交易流水实验一样：当前重点是数据计算和结果导出，而不是构建完整产品界面。

## 当前实验新增了什么

- `labs/portfolio-analysis/sample_prices.csv`
- `labs/portfolio-analysis/portfolio_analysis.py`
- `labs/portfolio-analysis/portfolio_reporting.py`
- `labs/portfolio-analysis/demo.py`
- `labs/portfolio-analysis/test_portfolio_analysis.py`
- `load_price_history()`
- `calculate_returns()`
- `calculate_portfolio_returns()`
- `calculate_portfolio_metrics()`
- `calculate_correlation_matrix()`
- `calculate_covariance_matrix()`
- `calculate_portfolio_volatility_from_covariance()`
- `calculate_rebalance_trades()`
- `generate_portfolio_report()`

运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\portfolio-analysis\demo.py
```

运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\portfolio-analysis
```

## 资料来源

- SEC, Asset Allocation and Diversification: https://www.investor.gov/introduction-investing/getting-started/asset-allocation
- SEC, Beginners' Guide to Asset Allocation, Diversification, and Rebalancing: https://www.sec.gov/investor/pubs/assetallocation.htm
- pandas, `DataFrame.pct_change`: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pct_change.html
- pandas, `DataFrame.cov`: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cov.html

访问日期：2026-05-05
