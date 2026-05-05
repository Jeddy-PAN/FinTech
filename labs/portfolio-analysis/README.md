# 投资组合分析

这是第四个 FinTech 代码实验：用样例价格数据计算资产收益率、组合收益率、年化波动率和最大回撤。

配套文档：[../../docs/13-portfolio-analysis.md](../../docs/13-portfolio-analysis.md)

## 当前功能

- 从 `sample_prices.csv` 读取长表格式价格数据。
- 将价格数据整理为“日期 × 资产”的宽表。
- 计算单个资产每日收益率。
- 按固定权重计算组合每日收益率。
- 计算累计收益率、年化波动率和最大回撤。
- 计算资产相关性矩阵和协方差矩阵。
- 用协方差矩阵计算组合年化波动率。
- 根据当前持仓、最新价格和目标权重计算再平衡交易。
- 生成 HTML 投资组合分析报告和 CSV 导出文件。
- 校验组合权重必须非负且合计为 `1.0`。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\portfolio-analysis\demo.py
```

运行后会生成：

- `labs/portfolio-analysis/reports/portfolio_analysis_report.html`
- `labs/portfolio-analysis/reports/asset_returns.csv`
- `labs/portfolio-analysis/reports/portfolio_returns.csv`
- `labs/portfolio-analysis/reports/correlation_matrix.csv`
- `labs/portfolio-analysis/reports/annualized_covariance_matrix.csv`
- `labs/portfolio-analysis/reports/rebalance_trades.csv`

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\portfolio-analysis
```
