# 退款和冲正：成功支付如何反向入账

最后更新：2026-05-05

本篇是 `labs/payment-orders/` 的第二轮学习笔记。上一轮我们实现了支付成功后入账，这一轮加入全额退款 refund 和反向账本分录 reversal。

## 先给结论

退款不是“删除原来的成功交易”。退款应该是一笔新的业务事件，并写入新的账本交易，把之前的账户变化反向冲回去。

成功支付时：

```text
借方：Platform Bank Account  100.00
贷方：User Wallet Balance    100.00
```

全额退款时：

```text
借方：User Wallet Balance    100.00
贷方：Platform Bank Account  100.00
```

退款后两个账户余额回到 0，但账本里仍然保留两笔交易：

- 一笔成功支付交易。
- 一笔退款反向交易。

这样系统可以解释“为什么当前余额是 0”。

## 为什么不能删除原交易

金融系统强调可审计。删除原交易会带来几个问题：

- 无法证明曾经成功支付过。
- 无法解释退款发生前后的余额变化。
- 对账时找不到支付渠道原始事件。
- 后续纠纷、审计、报表都缺少历史记录。

更稳妥的方式是 append-only：不改旧账，通过新交易表达修正或反向变化。

## refund 和 reversal 的区别

在本实验里：

- refund 指业务事件：对一笔成功支付进行退款。
- reversal 指账本表达：用反向分录抵消原来的资金变化。

真实系统里，不同机构和支付渠道对 reversal、void、refund 的定义可能不同。例如有些系统在资金未清算前叫 void，清算后叫 refund。遇到具体支付渠道时，应查官方文档。

## 订单状态机更新

当前状态机：

```text
pending -> succeeded -> refunded
pending -> failed
```

禁止：

- `pending -> refunded`
- `failed -> refunded`
- `refunded -> succeeded`
- `refunded -> failed`
- `refunded -> refunded` 重复出账

重复退款事件只返回已有退款结果，不再次写账本。

## 本实验如何防重复退款

和成功支付类似，本实验有两层防线：

### 订单层 event_id

同一个 webhook event id 重复到达时，直接返回第一次处理结果。

### 账本层 idempotency_key

退款入账使用：

```text
payment-order:{order_id}:refunded
```

即使订单层重复调用，账本层也不会重复生成退款分录。

## 为什么先做全额退款

退款可以分为：

- 全额退款 full refund
- 部分退款 partial refund

全额退款更适合第一版学习，因为状态和金额都更简单。部分退款需要额外考虑：

- 已退款金额累计。
- 多次部分退款。
- 不能超过原支付金额。
- 每次退款的独立 event id 和 ledger transaction。

这些会放到后续扩展。

## 本轮实验新增了什么

- `PaymentOrder.refund_ledger_transaction_id`
- `PaymentOrderService.mark_refunded()`
- `refunded` 状态实际可用
- 退款反向账本分录
- 重复退款事件不重复出账
- pending / failed 订单不能退款

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```

## 下一步

下一轮建议做持久化支付订单：

- 用 SQLite 保存 orders。
- 用 SQLite 保存 processed webhook events。
- 订单状态和账本入账要在同一个业务操作中保持一致。

这会把支付订单系统从内存实验推进到更接近真实服务。

## 资料来源

- Stripe Docs, Refunds API: https://docs.stripe.com/api/refunds
- Stripe Docs, Webhooks: https://docs.stripe.com/webhooks
- PayPal Developer, Payments captures refund: https://developer.paypal.com/docs/api/payments/v2/#captures_refund
- Adyen Docs, Refund: https://docs.adyen.com/online-payments/refund/

访问日期：2026-05-05
