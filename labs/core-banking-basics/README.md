# Core Banking Basics

这是核心银行账户实验。目标是用最小 Python 代码理解 account product、bank account、ledger balance、available balance、hold、interest accrual、monthly statement、audit events、optimistic version，以及这些对象落到 SQLite 后的事务和幂等边界。

配套文档：[../../docs/56-core-banking-basics.md](../../docs/56-core-banking-basics.md)

## 当前功能

- 创建 checking / savings account product。
- 开立 bank account。
- 查询 ledger balance、active hold amount 和 available balance。
- deposit 和 withdraw。
- place hold、release hold 和 capture hold。
- frozen / closed account 状态控制。
- daily interest accrual 教学版计算。
- monthly statement 汇总。
- monthly statement summary / postings CSV 导出。
- monthly statement HTML report 导出。
- 记录教学版 account / posting / hold / interest / statement audit events。
- 使用 `Decimal` 处理金额。
- 使用 `idempotency_key` 和 request fingerprint 防止重复入账或错误重放。
- 提供内存版 `CoreBankingService` 和 SQLite 持久化版 `SQLiteCoreBankingService`。
- SQLite 版会持久化 products、accounts、postings 和 holds。
- SQLite 版支持重开数据库后继续查询余额、statement 和幂等记录。
- SQLite 版用状态条件更新保护 hold capture / release，避免重复消费同一个 active hold。
- SQLite 版会持久化 `core_banking_audit_events`。
- SQLite 版会给 account 维护 `version`，并支持 `expected_version` 条件更新账户状态。
- SQLite 版测试覆盖两个连接不能基于同一个旧 account version 同时更新账户状态。

## 教学边界

当前实验是教学版，不是生产 core banking system。

不覆盖：

- 真实银行产品规则。
- 真实利息、费用、税务、披露或监管要求。
- 生产级并发控制、分布式锁、灾备、迁移框架和审计留痕。
- 生产级 lease、retry policy、死锁处理或跨服务并发恢复。
- 真实法律、监管、电子签名或证据链意义上的审计留痕。
- overdraft、limits、joint account、account ownership。
- 总账科目、会计期间、关账和财务报表。

真实银行规则属于需要查证的内容，不能直接从本实验推断。

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -B -m pytest -p no:cacheprovider .\labs\core-banking-basics -q
```

## 最小学习路径

1. 先读 [../../docs/56-core-banking-basics.md](../../docs/56-core-banking-basics.md)。
2. 再读 [core_banking.py](core_banking.py)，重点看 `CoreBankingService.balance()` 和 hold 相关方法。
3. 再读 [sqlite_core_banking.py](sqlite_core_banking.py)，重点看 `core_banking_postings`、`core_banking_holds`、`idempotency_key` 和 account `version` 的落库方式。
4. 再读 [core_banking_audit.py](core_banking_audit.py)，理解 audit event 如何记录事件类型、账户、时间、来源和 payload。
5. 再读 [core_banking_statement_export.py](core_banking_statement_export.py)，理解 statement 如何导出为 summary / postings CSV 和静态 HTML report，并可选记录 `statement.exported` / `statement.html_exported`。
6. 最后读 [test_core_banking.py](test_core_banking.py)、[test_sqlite_core_banking.py](test_sqlite_core_banking.py)、[test_core_banking_statement_export.py](test_core_banking_statement_export.py) 和 [test_core_banking_audit.py](test_core_banking_audit.py)，通过测试理解每个金融概念对应的工程行为。
