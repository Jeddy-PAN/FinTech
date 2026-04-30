# 账本基础：账户、交易和双分录

最后更新：2026-04-30

本篇是第一个代码实验 `labs/ledger-basics/` 的配套笔记。目标是先理解金融系统为什么需要账本，再用一个最小 Python 实验把规则写出来。

## 先给结论

金融系统里的账本不是“流水列表”那么简单。它要回答几个问题：

- 谁的钱或资产发生了变化。
- 为什么发生变化。
- 哪些账户增加，哪些账户减少。
- 每一笔变化能不能追溯。
- 系统里的总数是否仍然平衡。

双分录记账 double-entry bookkeeping 的核心规则是：每笔交易至少影响两个账户，并且借方 debit 合计必须等于贷方 credit 合计。

## 为什么程序员要先学账本

很多 FinTech 系统本质上都在处理“状态变化”：

- 支付系统：用户付款、商户收款、手续费入账。
- 钱包系统：充值、提现、转账、冻结、解冻。
- 信贷系统：放款、还款、利息、逾期费用。
- 投资系统：买入、卖出、分红、费用、持仓变化。

如果只保存一条“用户 A 给用户 B 转了 100 元”的流水，后续很难可靠回答：

- A 的账户为什么少了 100？
- B 的账户为什么多了 100？
- 平台手续费在哪里？
- 重复请求有没有重复入账？
- 某个时间点的余额能不能还原？

账本的价值是把业务事件变成可验证、可追溯的账户变化。

## 基础术语

### 账户 account

账户是记录某类金额变化的容器。它不一定等于银行账户，也可以是系统内部账户。

常见账户类型：

- 资产 asset：现金、银行存款、应收款、投资资产。
- 负债 liability：应付款、用户钱包余额、借款。
- 权益 equity：所有者投入和留存收益。
- 收入 income：销售收入、手续费收入、利息收入。
- 费用 expense：服务费、利息费用、运营成本。

### 交易 transaction

交易是一次业务事件，例如充值、付款、退款、转账。交易本身应该有唯一 ID、描述、时间和若干分录。

### 分录 entry

分录是交易对某个账户的一条影响。每条分录至少包含：

- 账户。
- 方向：借方 debit 或贷方 credit。
- 金额。

一笔交易通常包含两条或更多分录。

### 借方 debit 和贷方 credit

借方和贷方不是“好”和“坏”，也不是“收入”和“支出”。它们只是会计记录的两个方向。

对不同账户类型，借贷方向的含义不同：

| 账户类型 | 借方增加 | 贷方增加 |
| --- | --- | --- |
| 资产 asset | 是 | 否 |
| 费用 expense | 是 | 否 |
| 负债 liability | 否 | 是 |
| 权益 equity | 否 | 是 |
| 收入 income | 否 | 是 |

所以“借方”不能简单理解为“扣钱”，“贷方”也不能简单理解为“加钱”。必须先看账户类型。

## 会计恒等式

最常见的会计恒等式是：

```text
资产 = 负债 + 权益
Assets = Liabilities + Equity
```

SEC 的投资者教育材料用资产、负债和股东权益解释资产负债表，IFRS Conceptual Framework 也定义了资产、负债、权益、收入和费用这些财务报表要素。对我们写系统来说，重点不是先成为会计，而是理解：账本设计必须让资金来源和资金去向能够互相解释。

## 最小例子：用户向钱包充值 100 元

假设用户向平台钱包充值 100 元。平台收到银行存款，同时对用户产生一项负债，因为这 100 元以后用户可以消费或提现。

```text
借方：平台银行存款 asset       100.00
贷方：用户钱包余额 liability   100.00
```

这笔交易平衡：

```text
借方合计 100.00 = 贷方合计 100.00
```

注意：用户钱包余额在平台视角是负债 liability，不是资产。因为平台欠用户这笔钱或服务价值。

## 最小例子：平台收取 2 元手续费

如果平台从用户钱包余额中收取 2 元手续费：

```text
借方：用户钱包余额 liability   2.00
贷方：手续费收入 income         2.00
```

为什么借记负债？因为负债账户借方减少，表示平台欠用户的钱减少了。为什么贷记收入？因为收入账户贷方增加。

## 程序员实现时的关键点

### 金额不要用浮点数

金额应使用定点小数或整数最小货币单位。Python 实验里使用 `Decimal`，生产系统通常会明确币种、精度和舍入规则。

### 每笔交易必须平衡

提交交易时必须校验：

```text
sum(debit entries) == sum(credit entries)
```

不平衡的交易不能入账。

### 账户必须存在

分录引用不存在的账户，说明业务或数据有问题，不能静默创建。

### 分录金额必须为正数

方向由 debit / credit 表达，金额本身保持正数。不要用负数金额混合表达方向，否则后续报表和审计会更容易出错。

### 交易应该不可随意修改

真实金融系统通常不会直接改历史交易，而是用冲正、调整分录或新交易修正。这样才能保留审计链路。

### 需要考虑幂等

支付回调、网络重试、用户重复点击都可能导致同一业务事件被提交多次。后续实验会加入 idempotency key，保证同一业务事件只入账一次。

## 本实验先实现什么

`labs/ledger-basics/` 的第一版只做内存账本：

- 创建账户。
- 提交双分录交易。
- 拒绝借贷不平衡的交易。
- 拒绝不存在账户。
- 查询账户余额。
- 计算试算平衡 trial balance。

暂时不做：

- 数据库存储。
- 用户权限。
- 多币种。
- 真实支付 API。
- 幂等键。
- 冲正交易。

这些会在后续实验逐步加入。

## 资料来源

- SEC, Beginners' Guide to Financial Statements: https://www.sec.gov/about/reports-publications/investorpubsbegfinstmtguide
- IFRS Foundation, Conceptual Framework for Financial Reporting: https://www.ifrs.org/content/ifrs/home/issued-standards/list-of-standards/conceptual-framework.html
- ACCA Global, Principles and concepts of accounting: https://www.accaglobal.com/ca/en/student/exam-support-resources/foundation-level-study-resources/fa2/fa2-technical-articles/a-matter-of-principle.html
- OpenStax, Principles of Finance, Key Terms: https://openstax.org/books/principles-finance/pages/4-key-terms

访问日期：2026-04-30
