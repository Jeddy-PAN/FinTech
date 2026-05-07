# KYC/AML Onboarding

这是第六个 FinTech 代码实验：用最小 KYC/AML 引擎评估开户申请，并输出 `approved`、`review` 或 `blocked` 决策。

配套文档：[../../docs/15-kyc-aml-onboarding.md](../../docs/15-kyc-aml-onboarding.md)

## 当前功能

- 输入个人或法人客户开户申请。
- 校验基本身份字段是否缺失。
- 校验法人客户是否提供 beneficial owner 信息。
- 对客户和 beneficial owner 做教学版 watchlist screening。
- 使用模糊匹配分数区分潜在命中和高度命中。
- 对样例高风险国家/地区和较高预期月交易量输出 `review`。
- 输出每条检查的原因、分值和总风险分数。
- 为 `review` 决策创建人工复核案例。
- 审核案例支持 `pending_review -> approved / rejected / request_more_info`。
- 使用 SQLite 保存客户申请、beneficial owner、KYC/AML 决策、检查结果和审核案例。
- 使用追加式审计事件记录 `kyc_application.saved`、`kyc_decision.saved` 和 `kyc_review_case.*`。
- 保存 watchlist 数据版本，并让 KYC/AML 决策记录当时使用的 `watchlist_version_id`。
- 保存 KYC/AML 策略版本，并让 KYC/AML 决策记录当时使用的 `policy_version_id`。
- 生成最小 KYC/AML 汇总报表，汇总客户类型、决策状态、检查命中次数、风险分数和人工审核状态。
- KYC/AML 汇总报表支持按客户类型、决策状态、watchlist 版本、policy 版本、提交时间窗口和决策时间窗口筛选。
- 生成 watchlist/policy 版本对比报表，比较两个已保存版本下的决策状态、检查命中、风险分数和审核状态差异。
- 生成 KYC/AML replay 报表，用新的样例 watchlist 或 policy 重新评估已保存申请，并逐客户比较原决策和重放决策。
- 保存 replay run 和逐客户 replay 明细，并支持 `pending_review -> approved / rejected` 的审批结论。
- 导出 KYC/AML 汇总报表 CSV、版本对比 CSV、replay CSV 和 HTML 文件，便于复核、分享和归档。
- 使用样例名单，不接真实制裁名单。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo.py
```

运行 SQLite 持久化示例：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo_sqlite.py
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\kyc-aml-onboarding
```
