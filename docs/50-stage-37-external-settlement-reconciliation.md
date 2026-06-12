# 阶段 37：外部支付、清结算和真实对账模型

本阶段继续保持“单篇阶段文档 + 最小可运行代码”的方式。这里的“真实对账模型”不是接入真实支付机构、银行或清算网络，而是把平台内部账本对账扩展到一个更接近真实支付系统的问题：内部系统认为一笔支付完成后，外部 provider 的 settlement file 是否也能解释这笔钱。

所有 provider、settlement row 和金额都是教学样例，不代表任何真实支付通道规则、清算周期、手续费规则或监管要求。

## 1. 基础概念

### 中文定义

- 外部支付 provider：平台外部负责处理支付请求的一方，例如教学模型里的 `sample_provider`。
- 清算 clearing：把参与方之间的交易明细进行汇总、净额或确认的过程。
- 结算 settlement：资金最终在参与方账户之间完成划转或确认的过程。
- 对账 reconciliation：把内部账本、内部业务状态和外部文件逐笔或汇总比较，找出能解释和不能解释的差异。

### 英文术语

- payment provider
- clearing
- settlement
- settlement file
- external statement
- reconciliation finding

### 为什么金融系统需要它

内部系统显示 `completed` 不等于外部世界一定已经结算。真实支付平台通常需要把内部 payment order、ledger entry、provider response、webhook event、settlement file 和银行流水放在一起检查。否则会出现：

1. 内部已入账，但 provider 没有结算。
2. provider 已结算，但内部没有对应 payment run。
3. 内部金额和外部结算金额不一致。
4. 内部失败或待复核，但外部却显示 settled。

阶段 37 先覆盖这些稳定工程问题，不引入真实通道细节。

## 2. 本阶段实现

新增文件：

```text
labs/fintech-platform/platform_settlement_reconciliation_report.py
labs/fintech-platform/test_platform_settlement_reconciliation_report.py
```

新增核心对象：

```text
ProviderSettlementRow
PlatformSettlementReconciliationFinding
PlatformSettlementReconciliationReportExportPaths
```

`ProviderSettlementRow` 表示教学版外部 settlement file 的一行：

```text
provider
settlement_id
provider_payment_id
platform_run_id
payment_order_id
amount
currency
status
settled_at
```

当前支持的 provider settlement status：

```text
settled
failed
reversed
```

## 3. 对账规则

`evaluate_platform_settlement_reconciliation()` 会比较：

```text
PlatformRunSnapshot
ProviderSettlementRow
-> PlatformSettlementReconciliationFinding
```

当前检查：

| check_id | 含义 |
| --- | --- |
| `completed_internal_run_has_provider_settlement` | 内部 completed run 必须有外部 settled row |
| `completed_internal_run_has_settled_provider_row` | 内部 completed run 如果有 provider row，至少要有 settled row |
| `provider_settlement_amount_matches_internal_payment` | provider settlement amount 必须匹配内部 payment amount |
| `provider_settlement_currency_matches_internal_payment` | provider settlement currency 必须匹配内部 payment currency |
| `non_completed_internal_run_has_no_provider_settlement` | 内部非 completed run 不应有外部 settled row |
| `provider_settlement_has_internal_run` | 外部 provider row 必须能找到内部 platform run |

这里的内部 payment amount 来自 `payment_order.succeeded` audit payload。当前平台的 payment order payload 没有独立保存真实通道币种，因此本阶段把缺省内部币种视作 `USD`，只用于教学样例。

## 4. 导出和 demo

新增导出：

```text
platform_settlement_reconciliation_findings.csv
platform_settlement_reconciliation_report.html
```

`demo.py` 已接入阶段 37 报告，会基于当前已持久化的 completed platform runs 构造教学版 `sample_provider` settlement rows，然后导出 settlement reconciliation 报告。

## 5. 当前边界

本阶段仍不实现：

- 真实 payment provider adapter。
- 真实 webhook 验签、重放保护或事件去重。
- 真实清算周期、结算批次、手续费、退款、拒付或部分成功。
- 银行流水文件解析。
- 多币种汇率和 FX 损益。
- provider 规则、卡组织规则、监管要求或法律结论。

如果后续要讨论真实 provider API、卡组织清算文件、银行对账单格式、监管报送或留存期限，必须查证官方或专业来源。

## 6. 已完成代码与测试

本阶段修改：

```text
labs/fintech-platform/platform_settlement_reconciliation_report.py
labs/fintech-platform/test_platform_settlement_reconciliation_report.py
labs/fintech-platform/demo.py
```

已验证：

```text
py_compile: passed
test_platform_settlement_reconciliation_report.py: 7 passed
settlement + ledger reconciliation report tests: 12 passed
labs/fintech-platform: 157 passed
demo.py: runnable
labs: 402 passed
```

后续建议阶段 38 进入合规证据、调查工单和留存治理，把当前 settlement reconciliation findings 如何转成 evidence package 或 investigation case 作为下一步学习重点。
