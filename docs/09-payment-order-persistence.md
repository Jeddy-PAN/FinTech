# 支付订单持久化：orders、events 和 ledger 共用数据库

最后更新：2026-05-05

本篇是 `labs/payment-orders/` 的第三轮学习笔记。前两轮支付订单系统只存在内存里，程序关闭后订单状态和已处理 webhook event 都会丢失。这一轮加入 `SQLitePaymentOrderService`，把订单和事件保存到 SQLite。

## 先给结论

支付订单系统至少要持久化三类信息：

- 订单当前状态。
- 已处理过的 webhook event。
- 成功支付和退款对应的账本交易。

如果只保存订单，不保存 event，服务重启后重复 webhook 可能再次处理。如果只保存 event，不保存账本，系统无法解释余额变化。如果只保存账本，不保存订单，业务状态会丢失。

## 本实验新增了什么

`labs/payment-orders/sqlite_payment_orders.py` 新增：

```text
SQLitePaymentOrderService
```

它和内存版 `PaymentOrderService` 的行为保持一致，但把数据保存到 SQLite：

- `payment_orders` 表保存订单。
- `processed_payment_events` 表保存已处理事件。
- 前面账本实验的 `accounts`、`transactions`、`entries` 表保存账本数据。

本实验使用同一个 SQLite database file 保存订单和账本，方便学习时观察完整数据。

## payment_orders 表

```text
id                            order id
amount                        order amount
status                        pending / succeeded / failed / refunded
ledger_transaction_id          success ledger transaction id
refund_ledger_transaction_id   refund ledger transaction id
failure_reason                 failure reason
created_at                     creation timestamp
updated_at                     update timestamp
```

订单状态重启后仍能恢复。

## processed_payment_events 表

```text
event_id       webhook event id
order_id       related order id
processed_at   processing timestamp
```

`event_id` 是主键。重复 event id 到达时，系统直接返回已有订单状态，不重复入账。

## 为什么 event 要持久化

支付 webhook 可能在服务重启后重试。如果 event 只保存在内存里，重启后系统会忘记自己处理过这个 event。

持久化 event 后，系统可以回答：

- 这个 event 是否处理过。
- 它关联的是哪个订单。
- 当前订单状态是什么。

这就是 webhook 防重的基础。

## 为什么订单和账本共用数据库

本实验让 `SQLitePaymentOrderService` 和 `SQLiteLedger` 使用同一个 SQLite 文件。这样方便学习：

- 订单状态在 `payment_orders` 表。
- 已处理事件在 `processed_payment_events` 表。
- 账本分录在 `transactions` 和 `entries` 表。

真实系统里，订单服务和账本服务可能拆分到不同数据库或不同服务。拆分后需要更复杂的一致性机制，例如 outbox、消息队列、补偿任务或分布式事务。当前实验先不引入这些复杂度。

## 当前一致性边界

这一版已经能在重启后恢复订单、event 和账本数据。但它还没有把“更新订单状态、记录 event、写账本”严格包进同一个数据库事务。

原因是当前 `SQLiteLedger` 自己管理连接和事务，`SQLitePaymentOrderService` 也自己管理连接。两个连接操作同一个数据库文件时，能持久化，但还不是一个统一事务边界。

这不是最终生产形态。下一轮可以改进为：

- 共享同一个 SQLite connection。
- 或者让订单服务控制完整事务。
- 或者引入 outbox pattern，保证失败后可重试修复。

## 本轮实验覆盖什么

- 创建订单后关闭程序，再打开仍能看到 pending 订单。
- 支付成功后关闭程序，再打开仍能看到 succeeded 状态和账本余额。
- 重复成功 event 在重启后不会重复入账。
- 退款后关闭程序，再打开仍能看到 refunded 状态和反向账本分录。
- 重复退款 event 在重启后不会重复出账。
- 失败订单持久化后不产生账本交易。

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo_sqlite.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```

## 下一步

下一轮建议学习“事务一致性和 outbox pattern”：

- 为什么订单状态更新和账本入账可能出现一半成功。
- 如何用共享事务减少不一致。
- 为什么真实系统经常用 outbox 记录待投递事件。
- 如何设计失败后的重试和对账。

## 资料来源

- SQLite, Transactions: https://www.sqlite.org/lang_transaction.html
- SQLite, Atomic Commit In SQLite: https://www.sqlite.org/atomiccommit.html
- Stripe Docs, Webhooks: https://docs.stripe.com/webhooks
- PayPal Developer, Webhooks: https://developer.paypal.com/api/rest/webhooks/

访问日期：2026-05-05
