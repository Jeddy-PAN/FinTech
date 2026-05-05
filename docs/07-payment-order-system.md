# 支付订单系统：状态机、成功入账和重复回调

最后更新：2026-05-05

本篇进入第二个代码实验 `labs/payment-orders/`。前面的账本实验解决了“如何正确记录账户变化”。支付订单实验解决另一个问题：业务订单什么时候应该入账。

## 先给结论

支付订单 payment order 和账本交易 ledger transaction 不是同一个东西。

支付订单描述的是一次支付请求的业务状态：

- 用户要支付多少钱。
- 当前支付是否还在处理中。
- 支付成功还是失败。
- 是否已经退款。

账本交易描述的是账户余额如何变化：

- 哪个账户借记 debit。
- 哪个账户贷记 credit。
- 金额是多少。
- 是否借贷平衡。

所以创建支付订单时，不应该立即入账。只有支付真正成功后，才应该调用账本入账。

## 最小订单状态

本实验先用四个状态：

| 状态 | 英文 | 含义 |
| --- | --- | --- |
| 待处理 | pending | 订单已创建，支付结果还没确定 |
| 成功 | succeeded | 支付成功，可以入账 |
| 失败 | failed | 支付失败，不入账 |
| 已退款 | refunded | 成功订单已经全额退款 |

当前已实现 `pending`、`succeeded`、`failed`、`refunded`。退款和反向账本分录见 [08-refunds-and-reversals.md](08-refunds-and-reversals.md)。

## 为什么创建订单时不入账

创建订单只说明“用户发起了支付请求”，不说明钱已经到账。

如果创建订单时就入账，可能出现：

- 用户支付失败，但钱包余额已经增加。
- 支付渠道超时，系统不知道结果，却已经记账。
- 后续收到失败回调时，需要复杂回滚。

更稳妥的流程是：

```text
create order -> pending
payment provider confirms success -> succeeded -> post ledger transaction
payment provider confirms failure -> failed -> no ledger transaction
```

## webhook 为什么会重复

支付系统经常通过 webhook 通知结果。由于网络、超时和重试机制，同一个事件可能被投递多次。

所以服务端不能假设：

- 每个 webhook 只来一次。
- webhook 顺序一定正确。
- 客户端请求和 webhook 一定同步。

本实验用 `event_id` 记录已处理事件。重复的 `event_id` 会直接返回之前的处理结果，不重复入账。

## 本实验如何入账

支付成功时，系统调用前面账本实验里的 `Ledger.post_transaction()`：

```text
借方：Platform Bank Account  100.00
贷方：User Wallet Balance    100.00
```

平台银行存款是 asset，借方增加。用户钱包余额在平台视角是 liability，贷方增加。

同时使用账本的 `idempotency_key`：

```text
payment-order:{order_id}:succeeded
```

这样即使订单层出现重复处理，账本层也有第二道防线，避免重复入账。

## 订单状态机规则

当前实验规则：

- 新订单只能从 `pending` 开始。
- `pending` 可以变成 `succeeded`。
- `pending` 可以变成 `failed`。
- `failed` 不能再变成 `succeeded`。
- `succeeded` 不能再变成 `failed`。
- `succeeded` 收到重复成功事件，不重复入账。

退款实验已加入：

- `succeeded` 可以变成 `refunded`。
- `refunded` 不能再次退款。
- 退款会写入反向分录。

## 程序员实现时要注意什么

### 状态变更要显式

不要用随意的字符串到处改状态。状态机应该限制哪些状态能转到哪些状态。

### 订单和账本要分层

订单是业务层，账本是资金记录层。订单成功后调用账本入账，但账本不应该知道所有订单业务细节。

### 成功入账要幂等

本实验有两层防重：

- 订单层：`event_id` 防止重复 webhook 重复处理。
- 账本层：`idempotency_key` 防止重复入账。

这类多层防线在金融系统里很常见。

### 失败订单不入账

失败不是一笔资金变化。失败订单可以记录失败原因，但不应该产生充值入账分录。

## 本轮实验新增了什么

- `labs/payment-orders/payment_orders.py`
- `PaymentOrder`
- `PaymentOrderStatus`
- `PaymentOrderService`
- `demo.py`
- `test_payment_orders.py`

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```

## 下一步

下一篇继续学习退款 refund 和反向分录 reversal：[08-refunds-and-reversals.md](08-refunds-and-reversals.md)。

## 资料来源

- Stripe Docs, PaymentIntents API: https://docs.stripe.com/api/payment_intents
- Stripe Docs, Webhooks: https://docs.stripe.com/webhooks
- PayPal Developer, Orders API: https://developer.paypal.com/docs/api/orders/v2/
- Adyen Docs, Result codes: https://docs.adyen.com/online-payments/build-your-integration/payment-result-codes/

访问日期：2026-05-05
