# 账本持久化：SQLite、数据库事务和原子写入

最后更新：2026-05-05

本篇是 `labs/ledger-basics/` 的第二轮学习笔记。第一版账本只存在内存里，程序退出后账户和交易都会消失。第二版加入 SQLite，是为了理解金融系统为什么依赖持久化存储和数据库事务。

## 先给结论

账本系统不能只把交易写到内存里。金融系统必须能在程序重启、服务器故障、网络中断之后继续回答：

- 账户是否存在。
- 某笔交易是否已经入账。
- 每条分录写到了哪个账户。
- 余额为什么是当前结果。
- 一笔失败交易有没有留下半截数据。

所以第 2 轮实验新增了 `SQLiteLedger`，把账户、交易和分录写入 SQLite。

## 金融交易和数据库事务不是一回事

中文里都叫“交易”，但这里有两个不同概念：

| 中文 | 英文 | 含义 |
| --- | --- | --- |
| 金融交易 | financial transaction | 一次业务事件，例如充值、付款、退款、收手续费 |
| 数据库事务 | database transaction | 数据库的一组写入操作，要么全部成功，要么全部失败 |

例如用户充值 100 元是一笔金融交易。为了保存它，系统可能要写入：

- `transactions` 表 1 行。
- `entries` 表 2 行。

这几行数据库写入必须放在一个数据库事务里。否则可能出现只写了 `transactions`，但没有写完 `entries` 的半成品状态。

## 为什么要原子化 atomic

原子化的意思是：一组操作不可分割，要么全部完成，要么全部不发生。

在账本系统里，提交一笔交易至少要做三件事：

1. 校验账户存在。
2. 校验借方合计等于贷方合计。
3. 写入交易和所有分录。

如果第 3 步写到一半失败，系统必须回滚 rollback。否则账本可能不平衡，后续余额、对账、审计都会出问题。

## 本实验的 SQLite 表

### accounts

记录账户。

```text
id          account id
name        account name
type        asset / liability / equity / income / expense
created_at  creation timestamp
```

### transactions

记录金融交易的主记录。

```text
id           transaction id
description  business description
posted_at    posting timestamp
```

### entries

记录交易分录。

```text
id              entry id
transaction_id  parent transaction
account_id      affected account
side            debit / credit
amount          decimal amount stored as text
```

`entries.transaction_id` 指向 `transactions.id`，`entries.account_id` 指向 `accounts.id`。这就是外键 foreign key，用来防止分录引用不存在的交易或账户。

## 为什么金额用文本保存

SQLite 是轻量数据库，不提供专门的 Decimal 类型。它的 REAL 类型是浮点数，不适合直接保存金额。

本实验的策略是：

- Python 代码里用 `Decimal` 处理金额。
- 入库时把金额按两位小数转成文本，例如 `"100.00"`。
- 读出时再转回 `Decimal`。

真实生产系统还会进一步记录币种 currency、最小单位、舍入规则和精度约束。

## 为什么不直接存余额

本实验每次查询余额时，都是从 entries 汇总计算：

```text
balance = sum(signed entries for account)
```

这样做的好处是容易审计：余额来自哪些分录可以追溯。

真实系统为了性能，常常会同时保存：

- 原始分录 ledger entries
- 当前余额 balance snapshot

但余额快照必须能被分录重新验证，否则就会变成不可解释的数字。

## 程序员需要特别注意

### 先校验，再写入

在 `SQLiteLedger.post_transaction()` 里，先调用 `_validate_transaction()`：

- 描述不能为空。
- 至少两条分录。
- 每个账户都必须存在。
- 金额必须为正数且两位小数。
- 借方合计必须等于贷方合计。

校验通过后，才进入数据库事务写入。

### 写入必须在一个数据库事务里

Python 标准库 `sqlite3` 的连接对象可以作为上下文管理器使用：

```python
with connection:
    connection.execute(...)
    connection.executemany(...)
```

这个块内如果出现异常，sqlite3 会回滚事务；如果没有异常，会提交事务。

### 外键要显式打开

SQLite 的外键约束需要开启：

```sql
PRAGMA foreign_keys = ON;
```

否则定义了 foreign key，也可能不会按预期检查。

### 历史交易不要随意修改

账本系统更偏向 append-only：新增交易和分录，而不是直接修改旧记录。后续如果要纠错，应学习冲正 reversal 或调整交易 adjustment。

## 本轮实验新增了什么

- `sqlite_ledger.py`：SQLite 版账本。
- `demo_sqlite.py`：SQLite 持久化演示。
- `test_sqlite_ledger.py`：持久化、回滚、试算平衡测试。

你可以运行：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo_sqlite.py
```

再运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\ledger-basics
```

## 下一步

下一轮建议加入 `idempotency key`：

- 模拟支付回调重复到达。
- 同一个业务请求只能成功入账一次。
- 让系统返回已有交易，而不是重复创建交易。

这会把账本实验连接到支付系统里非常常见的重复请求问题。

## 资料来源

- SQLite, Atomic Commit In SQLite: https://www.sqlite.org/atomiccommit.html
- SQLite, Foreign Key Support: https://www.sqlite.org/foreignkeys.html
- SQLite, Datatypes In SQLite: https://www.sqlite.org/datatype3.html
- Python 3.13 Documentation, sqlite3: https://docs.python.org/3/library/sqlite3.html

访问日期：2026-05-05
