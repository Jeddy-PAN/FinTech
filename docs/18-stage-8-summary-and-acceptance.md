# 阶段 8 总结与验收清单

最后更新：2026-05-18

这份文档是阶段 8 的收尾材料。阶段 8 的重点不是再拆新概念，而是把前面学过的 FinTech、风控、KYC/AML、合规审计和调查工单整合成一个可以跑通、可以复核、可以回看历史的端到端学习作品。

## 阶段 8 做了什么

阶段 8 的主线可以概括为：

```text
customer onboarding
-> KYC/AML decision
-> payment order
-> risk decision
-> ledger posting
-> audit trail
-> reports
-> investigation
```

这条链路里，平台不再只是单点实验的调用者，而是一个把多个实验串起来的 orchestration 层。它完成了以下事情：

- 复用 KYC/AML 开户筛查结果，决定客户能否发起支付。
- 复用支付订单和账本实验，完成订单状态推进与入账。
- 复用风控规则引擎，处理 `approved`、`review`、`blocked` 和人工复核后续流程。
- 复用合规审计实验，生成统一审计时间线、访问审计、留存报告和异常访问线索。
- 复用调查工单实验，把异常访问发现项转成 investigation case，并记录工单动作审计。
- 复用 SQLite，把平台运行快照、访问记录和调查工单落盘，便于回看和复核。

## 已完成资产

阶段 8 当前已经完成的目录主要是：

```text
labs/fintech-platform/
```

核心内容包括：

- `fintech_platform.py`
- `demo.py`
- `platform_report_export.py`
- `platform_history_report_export.py`
- `platform_consistency_report.py`
- `platform_report_access.py`
- `platform_access_anomaly_report.py`
- `platform_investigation_cases.py`
- `sqlite_platform_store.py`

这些模块共同支持：

- 最小端到端支付编排
- 平台运行结果导出
- 平台历史运行导出
- 教学版一致性检查
- 平台报表访问控制与访问审计
- 平台访问异常检测
- 平台访问异常调查工单

## 学到的工程结论

1. 状态表和 audit trail 不是一回事。
2. 业务动作需要状态推进，审计动作需要可追溯记录。
3. 报表导出是敏感动作，必须有权限和留痕。
4. finding 只是线索，不等于处理完成。
5. 工单需要独立状态机、持久化和动作审计。
6. 一个学习平台真正有价值的地方，不是堆模块，而是把模块之间的边界讲清楚。

## 验收清单

下面这些结果都应当能在当前仓库里观察到：

1. 运行 `labs/fintech-platform/demo.py`，能看到一条正常支付链路。
2. demo 能输出 `Risk review completion` 和 `Risk review rejection`。
3. demo 能输出 `Platform report access audit events`。
4. demo 能输出 `Platform access anomaly findings`。
5. demo 能输出 `Platform access investigation cases`。
6. demo 能输出 `Persisted open platform investigation cases`。
7. demo 能输出 `Platform investigation case audit events`。
8. `labs/fintech-platform/reports/` 下能生成平台报表、异常报告和调查工单报告。
9. `labs/fintech-platform/.test-data/` 下能保存平台运行和工单的 SQLite 数据库。
10. `labs/fintech-platform` 和全量 pytest 都应当通过。

## 目前边界

这仍然是学习实验，不是生产系统。当前没有实现：

- 真正的 API 服务
- 真正的身份认证和企业 IAM
- 真正的支付通道、清算和结算
- 真正的监管报送与法定留存
- 真正的工单系统和通知系统
- 真正的不可篡改审计存储

## 下一步路线

阶段 8 之后，合理的两条路线是：

1. 把当前平台拆成一个简单的 API 服务，让外部请求可以驱动整条链路。
2. 给平台补一个最小前端或报告查看页，用来观察不同运行结果、调查工单和审计时间线。

如果继续走学习路线，建议优先选第 1 条，因为它更能暴露请求、幂等、状态推进、审计和报表之间的工程关系。
