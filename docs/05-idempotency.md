# 幂等性：防止重复请求导致重复入账

最后更新：2026-05-05

本篇是 `labs/ledger-basics/` 的第三轮学习笔记。前两轮我们已经有了内存版账本和 SQLite 持久化账本。这一轮加入 `idempotency key`，用来解决支付、转账、退款等系统里非常常见的重复请求问题。

## 先给结论

幂等性 idempotency 的意思是：同一个业务请求执行一次和执行多次，最终效果相同。

在 FinTech 系统里，这通常意味着：

- 第一次请求正常创建交易并入账。
- 网络超时、用户重复点击、支付回调重试时，客户端或上游系统再次发送同一个请求。
- 服务端识别这是同一个业务请求，返回第一次创建的交易。
- 余额不能重复变化。

本实验里，同一个 `idempotency_key` 重复提交时，账本会返回已有交易，不会新增分录。

## 为什么金融系统特别需要幂等性

普通系统里重复创建一条记录可能只是数据脏了。金融系统里重复请求可能变成：

- 用户被扣两次款。
- 商户收到两次入账。
- 退款重复发出。
- 风控额度被重复占用。
- 对账时出现无法解释的差异。

所以创建交易、扣款、退款、转账这类接口通常都需要幂等设计。

## 一个支付场景

假设用户发起充值 100 元：

```text
client request:
  idempotency_key = "payment-request-001"
  amount = 100.00
```

服务端第一次收到请求：

```text
创建交易 tx_001
借方：Platform Bank Account 100.00
贷方：User Wallet Balance 100.00
保存 idempotency_key = payment-request-001
```

客户端没有收到响应，于是重试同一个请求：

```text
client retry:
  idempotency_key = "payment-request-001"
  amount = 100.00
```

服务端发现这个 key 已经存在，直接返回 `tx_001`，不再新增交易和分录。

## idempotency key 和 transaction id 的区别

| 字段 | 谁生成 | 作用 |
| --- | --- | --- |
| idempotency key | 通常由客户端或上游系统生成 | 表示“这是同一个业务请求” |
| transaction id | 通常由服务端生成 | 表示“服务端已经创建的交易记录” |

如果客户端请求超时，它可能还不知道 transaction id。但它知道自己第一次发送时用的 idempotency key，所以重试时可以带同一个 key。

## 本实验如何实现

### 内存版 Ledger

`Ledger` 里新增了一个索引：

```text
idempotency_key -> Transaction
```

提交交易时：

1. 如果没有传 `idempotency_key`，按普通交易处理。
2. 如果传了 key，并且 key 已存在，直接返回已有交易。
3. 如果传了 key，但 key 不存在，正常校验并入账，然后保存 key。

### SQLiteLedger

`SQLiteLedger` 在 `transactions` 表新增：

```text
idempotency_key TEXT
```

并创建唯一索引：

```sql
CREATE UNIQUE INDEX idx_transactions_idempotency_key
ON transactions (idempotency_key)
WHERE idempotency_key IS NOT NULL;
```

这表示：

- 有 key 的交易不能重复。
- 没有 key 的普通交易仍然允许存在多笔。

## 为什么不能只靠前端禁用按钮

前端禁用按钮只能减少重复点击，不能解决真正的重复请求问题：

- 网络超时后客户端自动重试。
- 支付渠道或 webhook 重复回调。
- 后端任务队列重复投递。
- 用户刷新页面或重复提交。
- 分布式系统里多个 worker 同时处理。

所以幂等必须在服务端实现，并且最好由数据库唯一约束兜底。

## 程序员实现时要注意什么

### key 不能是空字符串

空字符串无法区分业务请求。本实验会拒绝空白 key。

### key 要足够唯一

真实系统里，key 通常应该包含请求方、业务类型或随机 UUID。不要用容易冲突的简单数字。

### 重试请求的参数一致性

本实验已经在下一篇 [06-request-fingerprint.md](06-request-fingerprint.md) 中加入 request fingerprint：同一个 key 对应的请求参数必须一致。如果 key 相同但金额或分录不同，应该返回错误，而不是悄悄复用。

### key 需要保存多久

真实系统通常不会永久保存所有 idempotency key，而是设置保留期。但账本交易本身必须长期保留。不同系统的保留策略取决于业务、监管和审计要求。

## 本轮实验新增了什么

- `Transaction` 增加 `idempotency_key` 字段。
- `Ledger.post_transaction()` 支持 `idempotency_key`。
- `SQLiteLedger.post_transaction()` 支持持久化幂等键。
- demo 中模拟充值请求重复提交。
- 测试覆盖重复提交不会重复入账。

运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo.py
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo_sqlite.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\ledger-basics
```

## 下一步

下一篇继续学习“请求指纹 request fingerprint”：同一个 idempotency key 如果请求参数完全一样，返回已有交易；如果金额或分录不同，返回错误。

## 资料来源

- Stripe Docs, Idempotent requests: https://docs.stripe.com/api/idempotent_requests
- PayPal Developer, REST API idempotency: https://developer.paypal.com/api/rest/reference/idempotency/
- Adyen Docs, API idempotency: https://docs.adyen.com/development-resources/api-idempotency/

访问日期：2026-05-05
