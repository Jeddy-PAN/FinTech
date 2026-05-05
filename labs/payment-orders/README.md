# Payment Orders

这是第二个 FinTech 代码实验：用最小支付订单系统连接订单状态和账本入账。

配套文档：[../../docs/07-payment-order-system.md](../../docs/07-payment-order-system.md)

## 当前功能

- 创建 `pending` 支付订单。
- 支付成功后状态变为 `succeeded`。
- 支付失败后状态变为 `failed`。
- 成功订单可以退款并变为 `refunded`。
- 创建订单时不入账。
- 支付成功时调用账本入账。
- 退款时调用账本写入反向分录。
- 重复 webhook event id 不重复入账。
- 已成功订单再次收到成功事件也不重复入账。
- 已退款订单再次收到退款事件也不重复出账。
- 提供内存版 `PaymentOrderService` 和 SQLite 持久化版 `SQLitePaymentOrderService`。
- SQLite 版使用 `payment_outbox` 表记录待发布事件。
- SQLite 版可以发布 pending outbox messages，成功后标记 `published`，失败后保留 `pending`。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo.py
```

运行 SQLite 持久化示例：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo_sqlite.py
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```
