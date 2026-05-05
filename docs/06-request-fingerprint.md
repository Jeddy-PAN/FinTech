# 请求指纹：防止幂等键被错误复用

最后更新：2026-05-05

本篇是 `labs/ledger-basics/` 的第四轮学习笔记。上一轮我们加入了 `idempotency_key`，解决重复请求不会重复入账的问题。这一轮加入 request fingerprint，用来检查同一个 key 下的请求参数是否一致。

## 先给结论

`idempotency_key` 只能说明“客户端声称这是同一个请求”。但服务端还应该确认：这个 key 对应的请求内容和第一次是否一致。

如果第一次请求是充值 100 元：

```text
idempotency_key = payment-request-001
amount = 100.00
```

第二次却变成充值 200 元：

```text
idempotency_key = payment-request-001
amount = 200.00
```

服务端不能直接返回第一次的交易，也不能创建第二笔交易。更合理的行为是报错：这个 key 被不同请求数据复用了。

## 为什么只靠 idempotency key 不够

没有 request fingerprint 时，系统可能出现这种危险行为：

1. 客户端用 key `payment-request-001` 提交充值 100 元。
2. 服务端成功入账。
3. 客户端因为 bug 又用同一个 key 提交充值 200 元。
4. 服务端只看到 key 已存在，于是返回第一次的 100 元交易。

这会让客户端误以为 200 元请求成功了，但实际账本没有变化。更糟的是，如果系统选择覆盖或重新入账，可能造成重复扣款或账务混乱。

## request fingerprint 是什么

请求指纹 request fingerprint 是服务端根据关键请求参数计算出的稳定摘要。

本实验使用这些字段：

- 交易描述 description
- 分录列表 entries
- 每条分录的账户 account id
- 分录方向 debit / credit
- 金额 amount

代码会把这些字段规范化后计算 SHA-256：

```text
request data -> normalized JSON -> SHA-256 fingerprint
```

后续同一个 `idempotency_key` 再次提交时：

- fingerprint 相同：返回已有交易。
- fingerprint 不同：拒绝请求。

## 为什么分录要排序

同一笔双分录交易里，分录顺序通常不应改变业务含义：

```text
debit bank 100, credit wallet 100
```

和：

```text
credit wallet 100, debit bank 100
```

表达的是同一组账户变化。所以本实验在计算 fingerprint 前，会按账户、方向、金额排序，避免因为列表顺序不同导致误判。

## 本实验如何实现

### Transaction 新增字段

```text
request_fingerprint
```

### 内存版 Ledger

第一次提交：

1. 计算 request fingerprint。
2. 校验交易。
3. 保存 transaction。
4. 建立 `idempotency_key -> transaction` 索引。

重复提交：

1. 根据 key 找到已有交易。
2. 重新计算当前请求的 fingerprint。
3. 如果 fingerprint 相同，返回已有交易。
4. 如果不同，抛出错误。

### SQLiteLedger

`transactions` 表新增：

```text
request_fingerprint TEXT
```

这样关闭程序后再打开数据库，仍然能判断同一个 key 的请求参数是否一致。

## 真实系统还会更严格

本实验的 fingerprint 只覆盖账本分录相关字段。真实支付系统通常还会考虑：

- merchant id
- customer id
- currency
- payment method
- request path
- request body
- API version
- authentication context

哪些字段应该进入 fingerprint，取决于业务语义。原则是：会改变业务结果或风险判断的字段，都应该参与一致性检查。

## 本轮实验新增了什么

- `Transaction.request_fingerprint`
- 内存版 `Ledger` 的 fingerprint 检查
- SQLite 版 `SQLiteLedger` 的 fingerprint 持久化
- 同 key 同参数返回已有交易
- 同 key 不同金额或描述时报错
- 分录顺序不同但业务相同时允许重试

运行：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\ledger-basics
```

## 下一步

账本基础已经覆盖了：

- 双分录
- 持久化
- 数据库事务
- 幂等键
- 请求指纹

下一阶段建议进入“支付订单系统”：

- 订单状态机
- pending / succeeded / failed / refunded
- 支付成功后入账
- webhook 重复回调
- 退款和冲正

这样可以把账本能力放进更完整的支付业务流程里。

## 资料来源

- Stripe Docs, Idempotent requests: https://docs.stripe.com/api/idempotent_requests
- PayPal Developer, REST API idempotency: https://developer.paypal.com/api/rest/reference/idempotency/
- Adyen Docs, API idempotency: https://docs.adyen.com/development-resources/api-idempotency/

访问日期：2026-05-05
