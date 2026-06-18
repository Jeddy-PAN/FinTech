# Core Banking Basics

最后更新：2026-06-18

本文件说明 `labs/core-banking-basics/` 的核心银行账户实验。它不是一个真实 core banking system，也不代表任何银行产品、利息披露、监管规则、审计规则或会计处理规则；它只是用一个可运行的教学模型解释：银行账户为什么不只是“一个余额字段”，以及这些账户对象落到 SQLite 后会遇到什么事务、幂等和可追溯性问题。

## 1. 中文定义

核心银行系统，英文通常叫 core banking system，是银行或类银行机构管理客户账户、账户产品、余额、资金冻结、利息和账单的基础系统。

在支付系统里，我们之前主要关心：

```text
payment order -> success / failed -> ledger posting
```

在核心银行账户里，我们还要关心：

```text
account product
account status
ledger balance
available balance
hold
interest accrual
statement
audit event
```

这意味着账户不是一个简单的 `balance = 100`。一个账户可能账面余额是 100，但有 30 被 card authorization hold 占用，那么可用余额只有 70。

## 2. 英文术语

- core banking
- account product
- deposit account
- checking account
- savings account
- ledger balance
- available balance
- authorization hold
- account hold
- interest accrual
- monthly statement
- account status
- audit event

## 3. 为什么金融系统需要它

### 3.1 账户产品决定账户规则

Account product 表示账户属于什么产品。例如 checking account 和 savings account 的业务规则可能不同。

当前实验只保留一个最小字段：

```text
annual_interest_rate
```

真实银行产品还会有费用、最低余额、限额、披露、税务和监管要求。这些规则不能凭空编写，后续如果进入真实产品规则，必须查证官方或专业来源。

### 3.2 账面余额和可用余额不同

Ledger balance 是已经记到账上的余额。

Available balance 是当前可动用余额。它通常会扣除 active hold。

教学版公式：

```text
available_balance = ledger_balance - active_hold_amount
```

这就是普通程序员最容易踩坑的地方：不能只看账面余额就允许提现或消费。

### 3.3 Hold 解释“钱还在账户里，但暂时不能用”

Hold 是资金占用或冻结的一种抽象。比如一笔卡交易授权成功后，资金可能先被 hold，之后再 capture。

教学版流程：

```text
deposit 100
-> ledger balance 100, available balance 100
place hold 30
-> ledger balance 100, available balance 70
capture hold 30
-> ledger balance 70, available balance 70
```

这里 capture 才真正产生 debit posting。

### 3.4 利息是批处理和幂等问题

Interest accrual 是把利息算出来并记入账户的过程。真实银行计息规则很复杂，可能涉及产品条款、计息基础、天数规则、舍入规则、税务和披露。

当前实验使用明确的教学假设：

```text
daily_interest = ledger_balance * annual_interest_rate / 365
```

并且用幂等键保证同一个账户同一天只入账一次：

```text
interest:{account_id}:{date}
```

重点不是学真实银行如何计息，而是学“批处理金融任务必须能安全重跑”。

### 3.5 Statement 是面向客户和运营的解释层

Monthly statement 把某个期间内的 postings 汇总出来：

- opening balance
- closing balance
- total credits
- total debits
- interest credited
- period postings

这让账户变化可以被解释、复核和导出。

当前实验还支持把 statement 导出为两张 CSV 和一份静态 HTML report：

```text
statement summary CSV
statement postings CSV
statement HTML report
```

summary CSV 适合快速查看期初余额、期末余额和汇总金额；postings CSV 适合逐笔复核每条入账、出账、利息或 hold capture；HTML report 适合人工阅读和教学演示。它们仍是教学版导出，不是正式银行对账单或法定披露文件。

## 4. 程序员实现时会遇到什么问题

### 4.1 金额必须用 Decimal

浮点数不适合金额。当前实验使用 `Decimal`，并把金额量化到两位小数。

### 4.2 账户状态会影响操作权限

当前教学版状态：

```text
active
frozen
closed
```

教学规则：

- `active`：允许 deposit、withdraw、hold 和 capture。
- `frozen`：允许 deposit，但阻止 withdraw、hold 和 capture。
- `closed`：阻止 deposit、withdraw、hold 和 capture。

真实系统里的冻结、关闭、法律限制和异常处理会复杂得多，需要查证规则和机构要求。

### 4.3 幂等键不能只判断“是否存在”

同一个 idempotency key 重放时，如果请求内容相同，应返回同一条 posting；如果请求内容不同，应拒绝。

当前实验保存 request fingerprint，用来检测：

```text
same idempotency_key + different amount
-> reject
```

### 4.4 Hold capture 要注意状态变化顺序

Capture hold 时既要产生 debit posting，又要把 hold 从 active 改成 captured。

生产系统里这通常需要数据库事务。当前 SQLite 版把 capture hold 做成同一段持久化操作：先写 debit posting，再用 `WHERE status = 'active'` 的条件更新把 hold 从 active 改成 captured；如果条件更新没有消费到 active hold，整段事务会抛错并回滚，避免留下第二条 debit posting。第一版仍是教学事务边界，不代表生产级分布式并发控制。

### 4.5 Statement 的时间边界必须明确

当前实验按 UTC 时间计算 period postings。真实系统可能要处理本地时区、业务日、节假日、月末关账和 backdated posting。第一版先固定为教学规则，避免过早复杂化。

### 4.6 Audit event 让账户变化可追溯

Audit event 是对关键业务动作的结构化记录。当前实验记录的是教学版账户事件，例如：

```text
account.opened
account.status_changed
posting.created
hold.placed
hold.released
hold.captured
interest.accrued
statement.exported
statement.html_exported
```

它解决的问题不是“把日志打印出来”，而是让程序员能回答：

- 这个账户什么时候开立？
- 哪一次操作产生了 posting？
- hold 是释放了还是捕获了？
- 利息入账是否因为幂等重跑被重复记录？
- statement CSV 是什么时候导出的？
- statement HTML report 是什么时候导出的？

当前 audit events 仍是教学版追踪记录，不代表真实法律证据链、监管留存、电子签名、WORM 存储或正式审计报告。

## 5. 当前实现范围

代码位置：

```text
labs/core-banking-basics/core_banking.py
labs/core-banking-basics/sqlite_core_banking.py
labs/core-banking-basics/core_banking_audit.py
labs/core-banking-basics/core_banking_statement_export.py
labs/core-banking-basics/test_core_banking.py
labs/core-banking-basics/test_sqlite_core_banking.py
labs/core-banking-basics/test_core_banking_audit.py
labs/core-banking-basics/test_core_banking_statement_export.py
```

当前已实现：

- `AccountProduct`
- `BankAccount`
- `AccountPosting`
- `AccountHold`
- `AccountBalance`
- `MonthlyStatement`
- `CoreBankingAuditEvent`
- `CoreBankingAuditTrail`
- `CoreBankingService.create_product()`
- `CoreBankingService.open_account()`
- `CoreBankingService.set_account_status()`
- `CoreBankingService.deposit()`
- `CoreBankingService.withdraw()`
- `CoreBankingService.place_hold()`
- `CoreBankingService.release_hold()`
- `CoreBankingService.capture_hold()`
- `CoreBankingService.accrue_daily_interest()`
- `CoreBankingService.monthly_statement()`
- posting 幂等键和 request fingerprint
- `SQLiteCoreBankingService`
- SQLite tables：`core_banking_products`、`core_banking_accounts`、`core_banking_postings`、`core_banking_holds`
- SQLite table：`core_banking_audit_events`
- SQLite 版 products、accounts、postings 和 holds 持久化
- SQLite 版 account / posting / hold / interest audit events 持久化
- SQLite 版重开数据库后继续查询 balance、statement 和幂等记录
- SQLite 版 hold capture 的 posting + hold status 更新边界
- SQLite 版重复 capture / release 的状态条件保护
- SQLite 版两个连接不能重复 capture 同一个 active hold 的教学测试
- `export_monthly_statement_csv()`
- `export_monthly_statement_html()`
- statement summary CSV 和 postings CSV 导出
- statement HTML report 导出
- statement export 可选记录 `statement.exported` audit event
- statement HTML export 可选记录 `statement.html_exported` audit event

当前不实现：

- 真实银行产品规则。
- 真实计息、税务、费用、披露或监管规则。
- 正式银行对账单格式、客户通知、下载权限或电子签名。
- 生产级报表模板、客户门户下载、报表权限和正式通知流程。
- 真实法律、监管、电子签名或证据链意义上的审计留痕。
- overdraft、fees、limits、joint account、beneficiary、account ownership。
- 总账科目、会计期间、关账和财务报表。
- 与现有 `fintech-platform` 的自动集成。
- 生产级并发控制、分布式锁、schema migration、backup / restore 或灾备。

## 6. 最小例子

```python
from datetime import date, datetime, timezone

from core_banking import AccountProductType, CoreBankingService

banking = CoreBankingService()
banking.create_product(
    product_id="savings-2pct",
    name="Savings 2 Percent",
    product_type=AccountProductType.SAVINGS,
    annual_interest_rate="0.02",
)
account = banking.open_account(
    account_id="acct-001",
    customer_id="cust-001",
    product_id="savings-2pct",
    opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)

banking.deposit(account.account_id, "100.00", idempotency_key="deposit-001")
banking.place_hold(account.account_id, "30.00", hold_id="hold-001")

balance = banking.balance(account.account_id)
assert balance.ledger_balance == 100
assert balance.available_balance == 70

banking.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))

audit_event_types = [event.event_type for event in banking.audit_events]
assert "posting.created" in audit_event_types
assert "hold.placed" in audit_event_types
```

这个例子展示的是：账户产品、入金、hold、可用余额、利息批处理和教学版 audit events 如何互相影响。

## 7. 这一章会学到什么

完成本章第一版后，你会理解：

1. 为什么银行账户不是一个简单余额字段。
2. ledger balance 和 available balance 的差别。
3. hold 为什么会影响提现和消费判断。
4. interest accrual 为什么需要幂等和批处理思维。
5. statement 如何把账户变化解释给用户、运营和审计人员。
6. account status 为什么属于金融系统的权限边界。
7. audit event 如何把账户动作变成可查询的事件时间线。

对普通 FinTech 岗位来说，这一章的要求不高，但很实用：你不需要先懂复杂银行法规，也不需要会做真实银行计息；你需要先能把账户、余额、hold、posting、statement、audit event 和幂等这些工程对象讲清楚并写出可靠代码。

## 8. 下一步

已补 SQLite 持久化版本和账户 audit events。当前学习重点已经从“对象模型”进入“事务边界 + 可追溯性”：

- deposit / withdraw / hold capture 如何在事务中保存。
- idempotency key 如何落库并防止并发重复入账。
- statement 如何从数据库查询生成。
- account / posting / hold / interest / statement export 如何形成事件时间线。
- statement CSV 和 HTML report 分别适合机器复核和人工阅读。

更准确地说，代码文件名采用：

```text
SQLiteCoreBankingService
```

因为它既保存数据，也提供教学版业务操作。

后续可以继续扩展：

1. 增加更严格的并发控制演示，例如 optimistic version、lease 或 retry policy。
2. 增加更完整的 statement activity filters。
3. 再考虑是否把 core banking account 接入现有 `fintech-platform` 的支付资金流。
4. 进入 `loan-lifecycle`，学习授信、还款计划和逾期状态。
