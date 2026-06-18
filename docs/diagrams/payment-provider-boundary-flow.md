# 外部 Payment Provider 协议边界图

这张图说明后续要补的“外部”到底是什么：不是再做一个内部订单入口，而是模拟外部 payment provider / bank / clearing system 如何通过协议、webhook 和 settlement file 影响内部金融状态。

```mermaid
sequenceDiagram
    participant Client as External client
    participant Platform as FinTech Platform
    participant ProviderAdapter as Provider boundary
    participant Provider as Payment provider simulator
    participant Webhook as Webhook endpoint
    participant Store as Internal stores
    participant Recon as Settlement reconciliation

    Client->>Platform: Create payment run
    Platform->>ProviderAdapter: Create provider payment intent
    ProviderAdapter->>Provider: Provider-specific request
    Provider-->>ProviderAdapter: provider_intent_id
    ProviderAdapter-->>Platform: Internal provider reference
    Platform->>Store: Save pending internal run

    Provider->>Webhook: Signed payment event
    Webhook->>Webhook: Verify signature
    Webhook->>Webhook: Deduplicate event_id
    Webhook->>Platform: Map provider status to internal status
    Platform->>Store: Update payment order / audit trail

    Provider->>ProviderAdapter: Settlement CSV
    ProviderAdapter->>ProviderAdapter: Parse rows
    ProviderAdapter->>Recon: ProviderSettlementRow
    Recon->>Store: Compare internal completed runs
    Recon-->>Platform: Findings
```

## 读图要点

- `Provider boundary` 是内部系统和第三方支付系统之间的隔离层。
- `Webhook endpoint` 不能直接相信外部请求，必须先验签，再按 `event_id` 幂等去重。
- `provider status` 和内部 `payment order status` 不是同一个状态机，需要显式映射。
- `Settlement CSV` 用来模拟外部结算文件，检查内部成功记录是否真的能和外部结算记录对上。

## 当前项目状态

当前项目已经有：

- 内部 payment run。
- async worker。
- retry approval。
- ledger reconciliation。
- teaching version `ProviderSettlementRow`。
- settlement reconciliation report。

当前缺口是：

- provider intent 创建。
- webhook 签名验证。
- webhook event 去重和状态映射。
- settlement CSV parser。

这些缺口可以先作为教学版实现，不绑定真实 Stripe、PayPal、Visa 或银行接口。若后续引用真实 API，必须查证官方开发者文档。
