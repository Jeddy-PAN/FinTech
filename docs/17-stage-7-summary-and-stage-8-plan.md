# 阶段 7 总结与阶段 8 规划

最后更新：2026-05-11

本篇不是新的金融概念笔记，而是阶段交接文档。阶段 7 已经完成“合规与审计基础”的第一轮学习和实验；阶段 8 建议开始把前面分散的实验整理成一个端到端 FinTech 工程作品。

## 阶段 7 学到了什么

阶段 7 的核心问题是：

```text
系统不只要做出业务决策，还要能解释、复核和追踪这些决策如何发生。
```

前面的风控和 KYC/AML 实验已经产生了业务动作和审计事件。阶段 7 把这些事件统一成 `ComplianceAuditEvent`，并围绕 audit trail 补上了几个工程能力：

- 跨系统审计时间线：把风控和 KYC/AML 的事件按主体、时间和来源系统统一查询。
- 可复核报表：导出审计事件、主体时间线、汇总、访问异常、留存决策和调查工单报告。
- 最小权限：区分查看事件、查看 payload、导出报表和审批导出的权限。
- 访问审计：记录谁查看过审计数据、谁被拒绝、谁导出或审批了报告。
- 职责分离：用 maker/checker 思路要求敏感导出由另一个具备权限的人审批。
- 留存策略：用教学版 retention policy 说明 active、archive_due、delete_due 和 held 的工程形状。
- 异常访问检测：基于访问审计事件生成 repeated denied、unauthorized export attempt 和 repeated payload view finding。
- 调查工单：把 finding 转成 investigation case，并记录 open、investigating、resolved 和 false_positive 状态。
- 工单动作审计：调查工单的创建、接手和关闭动作本身也进入 audit trail。

## 关键工程结论

状态表和审计日志不是同一种东西。状态表回答“现在是什么状态”，审计日志回答“状态为什么变成这样”。金融系统通常同时需要两者。

Payload 不是越多越好。审计事件需要足够解释业务动作，但 payload 可能包含 PII、内部规则、风险信号和敏感操作理由，所以要做脱敏、权限控制和访问审计。

报表导出也是敏感动作。导出 CSV/HTML 看起来只是文件生成，但它可能把大量敏感审计信息带出系统边界，因此需要权限、审批、记录和后续复核。

Finding 不等于处理完成。异常检测只产生线索；真正的闭环需要工单状态、负责人、关闭理由和处理动作审计。

Retention policy 不是纯技术配置。当前实验里的天数和规则都是教学样例；真实系统必须由法律、合规、数据治理和业务负责人确认。

## 当前工程资产

阶段 7 留下的主要实验资产在：

```text
labs/compliance-audit/
```

核心模块包括：

```text
compliance_audit.py
compliance_audit_export.py
compliance_access_monitoring.py
compliance_access_report_export.py
compliance_retention.py
compliance_retention_export.py
compliance_investigation_cases.py
compliance_investigation_report_export.py
sqlite_access_audit_store.py
sqlite_investigation_case_store.py
demo.py
```

这些模块共同形成一个教学版合规审计闭环：

```text
risk / KYC audit events
-> unified compliance audit events
-> access control
-> access audit
-> export approval
-> retention report
-> access anomaly findings
-> investigation cases
-> investigation case audit events
```

## 当前边界

阶段 7 没有实现，也不应被误读为实现了以下能力：

- 真实身份认证、企业 IAM、组织架构和复杂权限矩阵。
- 不可篡改日志、签名、WORM 存储或集中日志平台。
- 真实监管记录留存期限、法律保全、归档删除或监管报送。
- 真实安全监控、SIEM、告警通知、设备指纹或 IP 情报。
- 完整工单系统、SLA、评论、附件、升级路径和证据链。
- 法律、税务、会计、合规或投资建议。

阶段 7 的价值是理解工程形状，而不是宣称满足任何真实监管要求。

## 阶段 8 目标

阶段 8 建议进入“端到端 FinTech 工程作品规划”。目标不是马上引入复杂框架，而是把已经完成的模块串成一个更像真实系统的学习作品。

建议阶段 8 的主线是：

```text
customer onboarding
-> KYC/AML decision
-> payment order
-> risk decision
-> ledger posting
-> audit trail
-> reports / investigation
```

也就是说，前面每个实验不再只是独立 demo，而是开始回答：

- 一个客户如何开户并通过或进入人工复核？
- 一笔支付订单如何经过风控、幂等、防重复和账本入账？
- 业务动作如何生成审计事件？
- 合规人员如何查看时间线、导出报告、检测异常访问并创建调查工单？
- 哪些地方必须保持事务一致性，哪些地方可以用 outbox 或后续补偿？

## 阶段 8 建议任务

第一步先做系统设计，不急着写大代码：

1. 画出综合项目的业务流程和模块边界。
2. 定义统一的客户、账户、支付订单、风控决策、KYC 决策和审计事件关系。
3. 明确哪些模块继续复用现有实验，哪些模块需要胶水代码。
4. 定义一个最小端到端场景，例如“已通过 KYC 的客户发起支付，风控审核通过后入账，并生成审计时间线”。
5. 列出暂不实现的真实生产能力，避免把教学项目伪装成真实金融系统。

第二步再考虑建立新的综合实验目录：

```text
labs/fintech-platform/
```

这个目录可以先只做 orchestration，不重写已有模块。优先复用现有实验里的 Python 类和 SQLite 存储，让学习重点放在跨模块流程、一致性边界和可复核性。

## 下一步

下一步建议编写 `labs/fintech-platform/README.md` 和一个最小架构草图，先把端到端场景、模块依赖、数据流和暂不实现范围写清楚，再进入代码实现。
