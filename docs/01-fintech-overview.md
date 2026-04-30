# FinTech 基础概览

最后更新：2026-04-30

FinTech 是 financial technology 的缩写，通常指用软件、数据、网络、自动化和新型基础设施改造金融服务。对程序员来说，FinTech 不是一个单独技术栈，而是一组金融业务问题和工程约束。

## FinTech 在解决什么问题

金融系统的核心任务包括：

- 记录钱和资产属于谁。
- 处理付款、转账、交易和结算。
- 衡量收益、风险、信用和流动性。
- 帮助个人和机构获得金融服务。
- 满足监管、审计、安全和消费者保护要求。

程序员进入金融领域时，最重要的变化是：系统不仅要“能运行”，还要可追溯、可审计、可解释，并且在金额、状态和权限上非常谨慎。

## 主要方向

### 支付和清结算

关键词：payment、clearing、settlement、refund、chargeback、idempotency。

关注资金从付款方到收款方的流程。工程重点包括订单状态机、回调、重复请求处理、对账、退款、失败重试和风控。

### 数字银行和开放银行

关键词：digital banking、open banking、account aggregation、API。

关注银行账户、交易流水、用户授权和第三方服务接入。工程重点包括身份认证、授权、数据权限、API 安全和合规。

### 信贷和风控

关键词：credit、underwriting、fraud detection、risk scoring。

关注借款人是否有还款能力和还款意愿。工程重点包括数据特征、评分模型、规则引擎、异常检测、人工审核和模型监控。

### 财富管理和投资科技

关键词：wealth management、portfolio、robo-advisor、return、volatility。

关注投资组合、资产配置、风险收益分析和自动化建议。学习时要先区分“投资分析工具”和“个性化投资建议”。

### 资本市场基础设施

关键词：order、trade、market data、brokerage、custody。

关注证券交易、行情、订单、成交、托管和结算。工程重点包括低延迟、正确性、行情数据处理和合规记录。

### 保险科技

关键词：insurtech、premium、claim、actuarial。

关注保费定价、理赔、欺诈检测和客户服务自动化。

### 数字资产和区块链

关键词：crypto asset、tokenization、custody、wallet、smart contract。

关注数字资产、钱包、托管、链上交易和智能合约。该领域监管和风险变化很快，学习时必须查证最新官方资料。

### RegTech 和 SupTech

关键词：regulatory technology、supervisory technology、KYC、AML、audit。

RegTech 服务金融机构做合规，SupTech 服务监管机构做监督。工程重点包括规则引擎、身份验证、反洗钱监控、报送和审计。

## 最基础的金融对象

- 账户 account：记录某个主体的资产、负债或权益。
- 交易 transaction：导致账户状态变化的事件。
- 分录 entry：交易在账本里的具体借贷记录。
- 余额 balance：账户在某个时间点或区间内的金额。
- 订单 order：用户请求购买、出售、支付或转账的业务指令。
- 清算 clearing：计算各方应收应付。
- 结算 settlement：真正完成资金或资产交割。
- 风险 risk：不确定性带来的损失可能性。
- 审计 audit：证明系统发生过什么、谁做了什么、结果是什么。

## 程序员优先理解的工程约束

- 金额不能随意用浮点数处理。
- 金融状态变化要可追溯。
- 重复请求不能导致重复扣款或重复入账。
- 外部 API 回调可能乱序、重复或延迟。
- 权限、隐私和数据保护是核心功能，不是附加功能。
- 报表和账务要能解释，不只是算出一个结果。

## 下一步

建议从“双分录账本”开始，因为它能连接账户、交易、余额、审计和数据一致性，是理解金融系统的底层入口。
