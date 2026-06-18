# Payment Provider Boundary

最后更新：2026-06-18

本文件说明 `labs/fintech-platform/platform_payment_provider.py`、`POST /platform/provider-webhooks` 和 `demo.py` 中的 provider settlement CSV 演示。它不是要接入真实 Stripe、PayPal、Visa、银行或清算网络，而是用一个教学版 provider boundary 解释：内部 FinTech 平台如何可靠处理来自外部支付系统的事件和结算文件。

## 1. 中文定义

Payment provider boundary 是内部系统和外部支付服务方之间的协议边界。

在真实系统里，内部平台通常不能直接控制外部 provider 的状态，只能通过 API、webhook、文件、报表或后台查询接收外部结果。因此内部系统必须把外部协议转换成自己的内部状态，并对每一步做校验、幂等和审计。

当前教学版还会导出一张 provider intent link 表，把内部 `run_id`、内部 `payment_order_id` 和外部 `provider_intent_id` 放在同一行，帮助理解“内部订单”和“外部支付对象”如何互相追踪。

## 2. 英文术语

- payment provider
- provider adapter
- payment intent
- provider intent link
- webhook
- webhook signature
- event idempotency
- settlement file
- reconciliation

## 3. 为什么金融系统需要它

支付链路经常不是同步完成的。

一个内部 payment run 创建后，外部 provider 可能稍后才告诉系统支付成功、失败或取消。这个通知可能重复发送，也可能被伪造，甚至可能和内部状态不一致。结算文件也可能晚于业务状态到达。

因此系统需要一个明确的 provider boundary：

```text
external provider event
-> verify signature
-> parse event
-> deduplicate event_id
-> map provider status to internal status
-> keep audit and reconciliation evidence
```

这条边界的重点不是“调用 API 成功”，而是“外部事实如何被可信地纳入内部金融状态”。

## 4. 程序员实现时会遇到什么问题

### 4.1 外部请求不能直接信任

Webhook 本质上是外部 HTTP 请求。内部系统必须验证签名，不能因为 payload 写着 `payment_intent.succeeded` 就直接把订单改成成功。

当前教学版使用 Python 标准库：

```text
hmac + hashlib.sha256
```

真实 provider 的签名算法、header 格式、时间窗口和重放防护规则必须查证官方开发者文档。

### 4.2 已签名请求也可能被重放

签名只能证明 payload 没被篡改，并不能证明它是“刚刚发送的”。攻击者如果拿到一段旧的 signed payload，仍可能尝试再次发送。

当前教学版 `ProviderWebhookEventProcessor` 支持 `timestamp_tolerance_seconds`，默认 HTTP endpoint 使用 300 秒窗口：如果 signed payload 中的 `occurred_at` 距离服务器接收时间太远，系统会拒绝该事件。

真实 provider 的时间戳字段、签名 header、容忍窗口和 replay 防护规则必须查证官方开发者文档。

### 4.3 外部事件可能重复

Provider 可能重复发送同一个事件。系统必须用 `event_id` 做幂等去重，避免重复推进状态、重复入账或重复审计。

当前教学版 `ProviderWebhookEventProcessor` 会记住已处理的 `event_id`。第二次处理同一个 event 时返回 `duplicate=True`。

### 4.4 外部状态和内部状态不是同一个状态机

Provider 的状态命名不一定等于内部 payment order 状态。系统需要显式映射。

当前教学版映射：

```text
payment_intent.succeeded -> provider succeeded -> internal succeeded
payment_intent.failed    -> provider failed    -> internal failed
payment_intent.cancelled -> provider cancelled -> internal cancelled
```

### 4.5 结算文件是另一个事实来源

内部订单成功不等于外部已经结算。Settlement CSV 用来模拟外部 provider 的结算文件，再解析成已有的 `ProviderSettlementRow`，供 settlement reconciliation 使用。

当前教学版 CSV 字段：

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

### 4.6 内部 run 和外部 intent 必须能互相追踪

在真实系统里，内部 payment run 通常会保存外部 provider 返回的 payment intent / charge / transaction id。后续 webhook、settlement file、客服调查和对账报告都依赖这个外部 ID 找回内部订单。

当前教学版使用可重复生成的 `provider_intent_id`：

```text
{provider}_intent_{run_id}
```

demo 会导出：

```text
reports/provider_payment_intents.csv
```

这张 CSV 展示：

```text
provider_intent_id -> internal_run_id -> payment_order_id
```

后续 webhook payload 和 settlement row 都使用同一个 `provider_intent_id`，从而可以解释外部事件和内部 payment run 的关系。

## 5. 当前实现范围

代码位置：

```text
labs/fintech-platform/platform_payment_provider.py
labs/fintech-platform/test_platform_payment_provider.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_provider_webhooks.py
labs/fintech-platform/platform_evidence_package.py
labs/fintech-platform/demo.py
```

当前已实现：

- `ProviderPaymentIntent`
- `ProviderWebhookEvent`
- `ProviderWebhookProcessingResult`
- `ProviderWebhookEventProcessor`
- `provider_intent_id_for_run()`
- `build_provider_payment_intent()`
- `build_provider_payment_intents()`
- `export_provider_payment_intents_csv()`
- webhook timestamp tolerance / replay window 教学规则
- `build_provider_webhook_payload()`
- `sign_provider_webhook_payload()`
- `verify_provider_webhook_signature()`
- `parse_provider_webhook_payload()`
- `provider_status_from_event_type()`
- `internal_status_from_provider_status()`
- `parse_provider_settlement_csv()`
- `POST /platform/provider-webhooks`
- provider webhook evidence item
- demo 生成 `reports/provider_payment_intents.csv`，展示 provider intent 和 internal run 的映射
- demo 生成 `reports/provider_settlement_sample.csv`，再解析成 `ProviderSettlementRow` 后进入 settlement reconciliation report

当前 HTTP endpoint 行为：

```text
POST /platform/provider-webhooks
Header: x-provider-signature
Body: signed provider webhook payload
-> verify signature
-> check timestamp replay window
-> parse event
-> deduplicate event_id
-> return provider/internal status mapping
-> write access audit granted / denied
-> build provider webhook evidence item
```

当前复用已有：

- `ProviderSettlementRow`
- `evaluate_platform_settlement_reconciliation()`
- `export_platform_settlement_reconciliation_report()`
- `build_platform_evidence_package()`

## 6. 当前不实现

第一版刻意不实现：

- 真实 Stripe、PayPal、Visa、银行或清算机构 API。
- 真实生产级 HTTP webhook endpoint 和真实 provider replay 规则。
- 真实密钥管理和 secret rotation。
- 多 provider adapter 抽象层。
- 把 webhook 自动接入现有 `FinTechPlatform.process_payment()` 主流程。
- 真实卡组织、ACH、wire、实时支付或银行清结算规则。

这些内容如果后续要做，必须先查证官方或专业来源。

## 7. 最小例子

```python
from datetime import datetime, timezone

from platform_payment_provider import (
    ProviderWebhookEventProcessor,
    build_provider_webhook_payload,
    sign_provider_webhook_payload,
)

payload = build_provider_webhook_payload(
    event_id="evt_001",
    provider_intent_id="intent_001",
    event_type="payment_intent.succeeded",
    occurred_at=datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
    payload={"amount": "100.00", "currency": "USD"},
)
signature = sign_provider_webhook_payload("secret_001", payload)

processor = ProviderWebhookEventProcessor(secret="secret_001")
result = processor.process_signed_payload(payload, signature)

assert result.internal_status == "succeeded"
```

这个例子展示的是：外部 provider 发来的事件先被验签，再被解析和映射成内部状态。

## 8. 下一步

后续可以在不重复支付订单系统的前提下继续扩展：

1. 设计真实 provider adapter 前，先选择一个官方 developer docs 做资料查证。
2. 进入核心银行账户或信贷生命周期等新大章节。
