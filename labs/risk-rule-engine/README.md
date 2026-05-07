# 风控规则引擎

这是第五个 FinTech 代码实验：用最小规则引擎对交易请求做 `approved`、`review` 或 `blocked` 决策。

配套文档：[../../docs/14-risk-rule-engine.md](../../docs/14-risk-rule-engine.md)

## 当前功能

- 输入交易请求：`transaction_id`、`user_id`、`amount`、`currency`、`created_at`、`device_id`、`ip_country`、`beneficiary_id`。
- 单笔金额超过阈值时输出 `review`。
- 同一用户当天累计金额超过阈值时输出 `review`。
- 币种不在允许列表时输出 `blocked`。
- 已有历史用户使用新设备时输出 `review`。
- IP 国家/地区命中高风险列表时输出 `blocked`。
- 收款方命中受阻列表时输出 `blocked`。
- 从 `risk_rules.json` 读取规则阈值、允许币种、高风险国家/地区、受阻收款方和规则分值。
- 支持只贡献分数的弱风险信号：`unusual_hour` 和 `round_amount`。
- 多个弱风险信号的总分达到 `risk_score_review_threshold` 时输出 `review`。
- 输出命中的规则、原因、单条规则分数和总风险分数。
- 为 `review` 决策创建人工审核案例。
- 审核案例支持 `pending_review -> approved / rejected`。
- 使用 SQLite 保存风控决策、规则命中和人工审核案例。
- 使用追加式审计事件记录 `risk_decision.saved`、`review_case.created`、`review_case.approved/rejected`。
- 保存规则版本，并让风控决策记录当时使用的 `rule_version_id`。
- 生成最小规则命中统计报表，汇总决策状态、规则命中次数、风险分数和人工审核状态。
- 规则命中统计报表支持按 `rule_version_id` 和决策时间窗口筛选。
- 生成规则版本对比报表，对比两个规则版本的决策状态、规则命中、风险分数和审核状态变化。
- 导出风控报表 CSV 和 HTML 文件，便于复核、分享和归档。
- 校验金额必须为正数，时间必须带时区。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo.py
```

运行 SQLite 持久化示例：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo_sqlite.py
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\risk-rule-engine
```
