# 交易流水分析

这是第三个 FinTech 代码实验：导入账户交易流水，把流水保存到 SQLite，做简单分类，并计算月度现金流。

配套文档：[../../docs/12-transaction-statement-analysis.md](../../docs/12-transaction-statement-analysis.md)

## 当前功能

- 导入包含 `transaction_id`、`posted_date`、`description` 和 `amount` 的 CSV 流水。
- 在 SQLite 中把有符号金额保存为整数分，避免浮点误差。
- 重复导入同一份流水时，用 `transaction_id` 跳过已存在交易。
- 使用简单关键词规则给交易分类。
- 用 SQL 计算月度收入、支出和净现金流。
- 用 Pandas 计算同样的月度现金流汇总。
- 生成“月份 × 支出类别”的月度支出矩阵。
- 对指定月份做预算和实际支出对比。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\transaction-analysis\demo.py
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\transaction-analysis
```
