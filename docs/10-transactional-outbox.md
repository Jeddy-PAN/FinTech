# Transactional Outbox：把业务变更和待发布事件一起保存

最后更新：2026-05-05

本篇继续完善 `labs/payment-orders/`。前一轮我们已经把订单、webhook event 和账本数据持久化到 SQLite。这一轮加入 `payment_outbox` 表，学习 transactional outbox pattern 的基础思想。

## 先给结论

在真实系统里，支付订单状态变化后，通常还要通知其他系统：

- 通知用户支付成功。
- 通知风控释放额度。
- 通知履约系统发货或开通服务。
- 通知数据平台更新报表。

危险做法是：

```text
更新订单状态 -> 直接调用外部系统
```

如果订单已经更新成功，但外部调用失败，系统就会出现“一半成功”。Transactional outbox 的做法是：

```text
同一个数据库事务里：
  更新订单状态
  插入 outbox message

之后由 relay/publisher：
  读取 pending outbox message
  发布消息
  标记为 published
```

这样即使发布失败，outbox message 还在数据库里，后续可以重试。

## 本实验为什么加入 outbox

当前支付订单系统已经能处理：

- 创建订单。
- 支付成功。
- 支付失败。
- 退款。
- webhook event 防重。
- 账本入账和反向分录。

但订单状态变化后，还缺少“对外通知”的可靠记录。`payment_outbox` 表就是这个记录。

## payment_outbox 表

```text
id            message id
event_type    payment_order.created / succeeded / failed / refunded
aggregate_id  payment order id
payload       event payload
status        pending / published
created_at    creation timestamp
published_at  publish timestamp
```

当前实验只实现本地状态，不真正发送消息到 Kafka、RabbitMQ 或 HTTP endpoint。

## 什么时候写 outbox

本实验会在这些动作后写入 pending outbox message：

- `create_order()` -> `payment_order.created`
- `mark_succeeded()` -> `payment_order.succeeded`
- `mark_failed()` -> `payment_order.failed`
- `mark_refunded()` -> `payment_order.refunded`

重复 webhook event 返回已有订单时，不新增 outbox message。

## 为什么 outbox 比直接发消息稳

直接发消息有两个典型失败场景：

### 场景 1：订单更新成功，消息发送失败

```text
UPDATE payment_orders SET status = succeeded
send message -> timeout
```

结果：订单已经成功，但其他系统不知道。

### 场景 2：消息发送成功，订单更新失败

```text
send message -> success
UPDATE payment_orders -> failed
```

结果：其他系统以为订单成功，但数据库里不是。

outbox pattern 先避免“数据库变更和待发消息分离”的问题：只要数据库提交成功，outbox message 就在那里。

## 当前实验的边界

这一轮实现了 outbox 表和 pending/published 状态，但还没有实现真正的消息发布器。

当前 API：

```text
pending_outbox_messages
mark_outbox_message_published(message_id)
```

你可以把 `pending_outbox_messages` 想象成 relay 要扫描的队列。

下一步如果继续，可以实现：

- `publish_pending_outbox_messages(publisher)`
- 发布成功后标记 published。
- 发布失败时保留 pending。
- 消费方幂等处理同一个 message id。

## 和当前一致性边界的关系

严格的 transactional outbox 要求业务变更和 outbox 插入在同一个数据库事务里。当前实验中：

- `create_order()` 的订单插入和 outbox 插入已经在同一个 SQLite transaction 中。
- `_replace_order()` 的订单更新和 outbox 插入也在同一个 SQLite transaction 中。

但支付成功和退款时，账本写入仍由 `SQLiteLedger` 的独立连接完成。也就是说：

- 订单状态和 outbox 是同一事务。
- 账本写入和订单状态还不是同一事务。

下一轮可以继续收紧这个边界，学习共享连接或补偿任务。

## 本轮实验新增了什么

- `OutboxMessage`
- `payment_outbox` 表
- `pending_outbox_messages`
- `mark_outbox_message_published()`
- 创建、成功、失败、退款都会写 outbox message
- published message 不再出现在 pending 列表

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo_sqlite.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```

## 下一步

下一篇继续实现 outbox publisher：[11-outbox-publisher.md](11-outbox-publisher.md)。

Outbox publisher 要解决：

- 定义一个 publisher interface。
- 成功发布后标记 `published`。
- 发布失败时保持 `pending`。
- 对同一个 outbox message 重试发布。

这会把 outbox 从“可靠记录”推进到“可重试消息发布流程”。

## 资料来源

- AWS Prescriptive Guidance, Transactional outbox pattern: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- Microsoft Learn, Transactional Outbox pattern: https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-outbox-cosmos
- microservices.io, Transactional outbox: https://microservices.io/patterns/data/transactional-outbox.html
- SQLite, Transactions: https://www.sqlite.org/lang_transaction.html

访问日期：2026-05-05
