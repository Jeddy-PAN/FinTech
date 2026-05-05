# Outbox Publisher：发布 pending message 并支持失败重试

最后更新：2026-05-05

本篇继续完善 transactional outbox。上一轮我们已经把待发布事件写入 `payment_outbox` 表。这一轮实现最小 outbox publisher：扫描 pending message，发布成功后标记 published，发布失败则保留 pending。

## 先给结论

Outbox pattern 分两步：

1. 业务操作时，把状态变化和 outbox message 一起写入数据库。
2. 后台 publisher 读取 pending message，发布成功后标记 published。

这一轮实现第 2 步的最小版本：

```text
publish_pending_outbox_messages(publisher)
```

如果 publisher 成功：

```text
pending -> published
```

如果 publisher 失败：

```text
保持 pending，等待下次重试
```

## 为什么发布失败不能删除 message

发布失败时删除 message 会丢失事件。其他系统就永远不知道订单状态变化了。

正确做法是保留 message：

- 网络恢复后重试。
- 外部服务恢复后重试。
- 人工排查后重试。
- 后续通过监控发现 pending 积压。

这就是 outbox 的价值：失败可以被发现和重试，而不是静默丢失。

## 本实验的 publisher 接口

当前使用一个最小协议：

```python
class OutboxPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> None:
        ...
```

如果 `publish()` 不抛异常，认为发布成功。如果抛异常，认为发布失败。

## 发布结果

`publish_pending_outbox_messages()` 返回：

```text
attempted  尝试发布的数量
published  成功发布的数量
failed     发布失败的数量
```

这样调用方可以做日志、监控和报警。

## 为什么需要 limit

当前方法支持：

```python
publish_pending_outbox_messages(publisher, limit=100)
```

原因是生产系统里 pending message 可能很多。publisher 通常要分批处理，避免一次扫描过多数据导致锁、内存或延迟问题。

## 消费方仍然要幂等

Outbox publisher 可以保证“消息不会轻易丢”，但不能保证“消息只被外部系统处理一次”。

可能出现：

1. publisher 调用外部系统成功。
2. 标记 published 之前进程崩溃。
3. 下次重启后又发布同一条 message。

因此消费者必须使用 message id 或业务 key 做幂等处理。

这是分布式系统里的常见原则：

```text
producer tries at-least-once delivery
consumer handles duplicates idempotently
```

## 当前实验新增了什么

- `OutboxPublisher`
- `OutboxPublishResult`
- `publish_pending_outbox_messages()`
- 发布成功后标记 published
- 发布失败后保留 pending
- 支持 limit 分批发布

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\payment-orders\demo_sqlite.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\payment-orders
```

## 下一步

下一轮建议进入“交易流水分析”：

- 导入 CSV 交易流水。
- 用 SQLite 查询收入、支出、分类。
- 用 Pandas 计算月度现金流。

这样可以从“支付系统工程”切换到“金融数据分析”，覆盖 FinTech 的另一个重要方向。

## 资料来源

- AWS Prescriptive Guidance, Transactional outbox pattern: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- Microsoft Learn, Transactional Outbox pattern: https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-outbox-cosmos
- microservices.io, Transactional outbox: https://microservices.io/patterns/data/transactional-outbox.html

访问日期：2026-05-05
