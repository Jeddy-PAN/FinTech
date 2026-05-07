# 风控规则引擎：限额、规则命中和可解释决策

最后更新：2026-05-07

本篇进入新的代码实验：风控规则引擎。目标不是做真实反欺诈系统，也不是替代合规规则，而是先理解金融系统里“规则如何把一笔请求变成可解释决策”。

## 先给结论

风控规则引擎的最小闭环是：

```text
request + history -> rules -> decision + rule hits
```

当前实验输入一笔交易请求，输出一个风控决策：

- `approved`：通过。
- `review`：需要人工或后续流程审核。
- `blocked`：直接阻断。

第一版只实现三类规则：

- 单笔金额超过阈值，进入 `review`。
- 同一用户当天累计金额超过阈值，进入 `review`。
- 币种不在允许列表中，进入 `blocked`。

在此基础上，当前实验已经加入最小人工复核状态机：当决策是 `review` 时，可以创建 `ReviewCase`，并从 `pending_review` 流转到 `approved` 或 `rejected`。现在也加入了 SQLite 持久化，把风控决策、规则命中和审核案例保存下来，便于后续查询和审计。

这只是教学版规则引擎。真实风控系统还会考虑用户画像、设备、IP、地理位置、收款方、历史行为、名单、模型评分、人工审核、监管要求和申诉处理。

## 中文定义

风控规则引擎 risk rule engine，是把交易、支付、提现、登录或开户等请求输入到一组规则中，根据规则命中情况输出风险决策的系统组件。

英文术语常见写法：

- 风控：risk control / risk management
- 规则引擎：rule engine
- 决策：decision
- 规则命中：rule hit
- 人工审核：manual review
- 持久化：persistence
- 审计追踪：audit trail
- 审计事件：audit event
- 追加式日志：append-only log
- 规则版本：rule version
- 风险信号：risk signal
- 设备指纹：device fingerprint
- 受益人/收款方：beneficiary
- 风险评分：risk score
- 纯评分策略：score-only strategy
- 弱风险信号：weak risk signal
- 阻断：block
- 限额：limit
- 速度规则：velocity rule
- 规则命中统计报表：rule hit reporting
- 规则版本对比报表：rule version comparison report
- 报表导出：report export

## 核心概念逐个解释

### 风险 risk

风险是未来发生损失或异常结果的可能性。在金融系统里，风险不只包括市场价格下跌，也包括欺诈、账户盗用、洗钱、操作错误、系统故障、信用违约和合规违规。

当前实验关注的是交易请求层面的操作风险和欺诈风险的最小模型：金额异常、累计金额异常、币种不被支持。

真实金融领域中，风险管理不是单个规则，而是一套流程：识别风险、评估风险、控制风险、监控风险、复盘和改进。

### 风控规则 risk rule

风控规则是一个可解释的判断条件。例如：

```text
如果单笔金额 > 1000.00，则进入人工审核
```

规则的优点是清晰、可解释、容易测试。缺点是过于简单时容易误杀正常用户，也可能被攻击者绕过。

真实系统通常会同时使用规则和模型。规则适合表达明确边界，例如禁止币种、监管限制、黑名单命中、单笔限额；模型适合处理复杂模式，例如欺诈概率、异常行为评分。

### 决策 decision

决策是规则引擎对请求给出的处理结果。

当前实验有三种：

| 决策 | 英文 | 含义 |
| --- | --- | --- |
| 通过 | approved | 请求可以继续后续业务流程 |
| 审核 | review | 请求暂不直接放行，需要人工或后续流程确认 |
| 阻断 | blocked | 请求不允许继续 |

真实金融系统里的决策可能更复杂，例如允许但降额、延迟处理、要求二次验证、冻结账户、发送提醒、提交 SAR/STR 可疑报告线索等。本实验先不做这些。

### 规则命中 rule hit

规则命中表示某条规则发现了问题，并记录原因。

例如：

```text
rule_id = single_transaction_amount
decision = review
reason = Amount 1500.00 exceeds review threshold 1000.00
```

规则命中非常重要，因为金融系统不能只告诉用户或运营“失败了”。系统需要解释：是哪条规则、因为什么字段、在什么时间、对哪个请求做出了什么判断。

真实场景中，规则命中会用于：

- 人工审核工作台。
- 客服解释和申诉。
- 审计和内部复盘。
- 模型和规则调优。
- 监管检查和风险报告。

### 人工审核 manual review

人工审核是系统不直接放行也不直接拒绝，而是把请求交给运营、风控或合规人员判断。

它的金融作用是把“机器规则能发现异常，但不能完全判断业务真实情况”的请求交给人处理。例如一笔大额转账可能是欺诈，也可能是正常用户买房、缴税、投资或企业付款；系统直接阻断会影响正常用户，直接放行又可能扩大损失，因此先进入审核队列。

真实系统中，人工审核通常有状态流转：

```text
pending_review -> approved / rejected / need_more_info
```

当前实验实现了一个最小状态机：

```text
review decision -> ReviewCase(pending_review) -> approved / rejected
```

`ReviewCase` 会保存 `case_id`、原始 `request_id`、`user_id`、命中的规则、创建时间、审核人、审核理由和审核时间。这里的重点不是做一个完整审核后台，而是理解真实金融系统为什么必须保留“谁在什么时候因为什么理由批准或拒绝了请求”。

对程序员来说，人工审核状态机要注意几个问题：

- 审核案例不能因为重复请求被重复创建，当前实验用 `review:{request_id}` 作为最小幂等标识。
- 已经 `approved` 或 `rejected` 的案例不能再次完成，否则会造成审计口径混乱。
- 审核人和审核理由不能为空，因为真实系统需要可追踪、可解释、可复盘。
- 时间字段必须带时区，否则跨地区团队、报表和审计会出现歧义。
- 真实系统通常还会有权限、双人复核、SLA、队列分派、附件材料、用户补充信息和申诉流程；当前实验暂不实现。

### 限额 limit

限额是对金额、次数、频率或敞口设置上限。

常见限额包括：

- 单笔交易限额。
- 单日累计限额。
- 单月累计限额。
- 同一用户、同一商户、同一设备或同一账户的频率限制。

限额可以用于控制损失扩大，也可以用于合规和运营策略。当前实验实现单笔金额阈值和用户日累计金额阈值。

### 速度规则 velocity rule

速度规则关注“短时间内发生了多少次或多少钱”。例如：

```text
同一用户 24 小时内提现超过 5000.00 -> review
同一卡号 10 分钟内失败 5 次 -> block
```

当前实验的“同一用户当天累计金额超过阈值”就是一个最小速度规则。真实系统通常会使用滑动窗口、自然日、账户时区、UTC 时间和多维度聚合。

### 币种限制 currency control

币种限制表示系统只允许处理特定币种。例如当前实验只允许 `USD`。如果请求币种是未知或不支持币种，就直接 `blocked`。

真实金融系统中，币种和地区通常涉及产品能力、清算通道、合规许可、汇率、反洗钱和报表要求。不能因为金额字段看起来合法就处理未知币种。

### 风险信号 risk signal

风险信号是风控判断使用的输入特征。金额、币种、交易时间是风险信号，设备、IP 国家/地区、收款方、登录方式、账户年龄、失败次数、历史行为也都是风险信号。

真实金融风控不会只看“这笔钱有多大”。例如：

- 同一用户突然换了从未见过的设备发起提现，可能需要审核。
- IP 国家/地区和用户历史活动地区差异很大，可能需要增加验证。
- 收款方命中过内部阻断名单，可能需要直接阻断。
- 同一设备短时间操作多个账户，可能表示批量攻击。

当前实验新增三个教学版风险信号：

- `device_id`：设备标识。当前规则是“已有历史用户使用新设备时进入 `review`”。
- `ip_country`：IP 国家/地区代码。当前规则是“命中高风险国家列表时进入 `blocked`”。
- `beneficiary_id`：收款方标识。当前规则是“命中受阻收款方列表时进入 `blocked`”。

这些规则是教学版近似，不代表真实名单、真实制裁筛查或真实地理位置判断。真实系统通常会使用设备指纹服务、IP 地理库、制裁/PEP/AML 名单、商户和收款方画像、历史行为聚合、模型评分和人工复核工作台。

### 风险评分 risk score

风险评分是把多个风险信号转成一个分数，用于表示请求的总体风险强度。规则命中回答“命中了哪些条件”，风险评分回答“这些条件合在一起有多严重”。

例如：

```text
new_device -> 35
single_transaction_amount -> 60
daily_user_amount -> 70
currency_allowed -> 100
```

真实金融系统里，风险评分可能来自规则加权、统计模型、机器学习模型，或多套系统的组合。它常用于：

- 排序人工审核队列，把高风险案例排在前面。
- 设置策略阈值，例如低分放行、中分审核、高分阻断。
- 比较不同规则或模型版本的效果。
- 给运营和风控团队一个可量化的风险强度。

当前实验实现的是教学版规则分数：每条命中的规则带一个 `score`，风控决策汇总为 `risk_score`。阻断规则仍然直接决定 `blocked`，审核规则仍然直接决定 `review`；`risk_score_review_threshold` 先作为配置和版本记录保存，为后续学习“纯评分策略”和“模型评分”打基础。

当前实验现在加入了最小纯评分策略。所谓纯评分策略，是指某些规则命中本身不直接要求 `review` 或 `blocked`，而是只贡献风险分数；当多个弱风险信号合计达到 `risk_score_review_threshold` 后，最终决策才进入 `review`。

当前新增两个教学版弱风险信号：

- `unusual_hour`：交易发生在 UTC 00:00 到 04:59 的非典型时间段，贡献 25 分。
- `round_amount`：金额大于等于 `500.00` 且是 `100.00` 的整数倍，贡献 30 分。

例如一笔 `500.00 USD` 的交易发生在 UTC 02:30：

```text
unusual_hour -> 25
round_amount -> 30
total risk_score = 55
score threshold = 50
decision = review
```

这两个命中在代码中仍记录为 `RuleHit`，但它们的单条状态是 `approved`，含义是“该信号被记录并计分，但单独不足以要求审核”。最终进入 `review` 是因为总分超过了阈值。阻断规则仍然优先，如果同时命中 `currency_allowed`、`ip_country_allowed` 或 `beneficiary_allowed` 这类阻断规则，最终决策仍然是 `blocked`。

真实风控系统中，弱信号可能包括登录设备变化、登录时间异常、收款方关系较新、交易金额模式异常、IP 与历史地区差异、失败重试次数偏高、账户资料不完整等。真实评分通常还会涉及特征工程、模型校准、误伤分析、策略阈值实验和模型监控。当前实验只用固定分值帮助理解“多个不致命信号累加后触发审核”的工程形状。

### 规则命中统计报表 rule hit reporting

规则命中统计报表是把已经保存的风控决策、规则命中、风险分数和人工审核状态做聚合，回答“规则运行后整体效果是什么样”的问题。它不是新的拦截逻辑，而是风控团队观察和调优规则的入口。

当前实验的最小报表包括：

- 决策状态数量：多少请求是 `approved`、`review`、`blocked`。
- 规则命中次数：每个 `rule_id` 被命中了多少次。
- 风险分数分布的最小指标：平均 `risk_score` 和最高 `risk_score`。
- 人工审核工作量：当前待审核案例数量。
- 审核结果数量：多少审核案例仍是 `pending_review`，多少已 `approved` 或 `rejected`。

当前报表也支持两个最小筛选维度：

- `rule_version_id`：只统计某个规则版本下产生的风控决策。
- `decided_from` / `decided_to`：只统计某个决策时间窗口内的风控决策。

这两个筛选维度很重要，因为真实风控团队不会只看“历史全量结果”。如果规则版本发生变化，团队需要知道新版本上线后 `review`、`blocked`、规则命中次数和人工审核工作量是否明显变化；如果某个时间段发生风险事件，团队也需要把报表限制在事件窗口内，而不是把长期历史混在一起看。当前实验中的审核状态统计会跟随已筛选的决策集合，只统计这些决策对应的审核案例。

在真实金融领域，这类报表通常用于几类工作：

- 观察规则命中率。如果某条规则突然命中过多，可能表示风险上升，也可能表示规则过严、数据异常或上游字段变化。
- 评估人工审核压力。`review` 过多会让审核队列堆积，影响用户体验和运营成本。
- 调整规则阈值。风控团队会结合误伤率、损失率、审核结论和业务目标调整阈值。
- 复盘规则版本。规则变更后，需要比较变更前后的命中率、阻断率、审核量和审核结果。
- 支持合规、审计和管理层报告。它提供的是可解释、可复核的统计口径。

对程序员来说，规则命中报表提醒我们：风控系统不能只写“在线决策路径”。如果没有可查询、可聚合的历史记录，团队就无法知道规则到底是否有效，也很难发现规则配置、数据源或模型输出是否异常。当前实验先在 SQLite 上做只读聚合和最小筛选，不实现误伤率、损失率、审核 SLA、导出文件和可视化仪表盘。

当前实验还新增了规则版本对比报表。它把两个 `rule_version_id` 分别生成汇总报表，然后计算差异：

- 总决策数量差异。
- `approved`、`review`、`blocked` 数量差异。
- 每条 `rule_id` 的命中次数差异。
- 平均风险分数和最高风险分数差异。
- 待审核案例数量差异。
- `pending_review`、`approved`、`rejected` 审核状态差异。

这个报表的真实意义是帮助风控团队观察规则版本变化后的影响。例如把单笔审核阈值从 `1000.00` 调低到 `800.00` 后，理论上可能会有更多请求进入 `review`，人工审核工作量也可能上升。报表不会直接告诉团队“新规则一定更好”，但它能把变化暴露出来，让团队继续结合损失、误伤、客户体验、审核结论和业务目标做判断。

对程序员来说，这一步引入了一个重要工程意识：版本对比不是简单比较配置文件，而是比较“使用这些配置后产生的实际决策记录”。当前实验只比较已经落库的决策结果，不做流量回放、不做 A/B 实验分流，也不判断哪个规则版本更优。

当前实验还新增了风控报表导出。它把已经生成的汇总报表和规则版本对比报表写成文件：

```text
risk_summary_report.csv
rule_version_comparison_report.csv
risk_report.html
```

报表导出的真实作用是让风控、运营、审计或管理团队可以离开命令行查看结果。数据库记录适合系统查询，审计事件适合追溯动作历史，报表适合人阅读、复核、分享和归档。三者不是替代关系：

- 数据库表保存原始决策、命中明细、审核案例和审计事件。
- 审计日志回答“谁在什么时候做了什么动作”。
- 报表回答“某个统计口径下整体表现是什么样”。

真实金融机构中的报表通常还会有权限控制、数据脱敏、定时任务、审批流程、归档策略、下载审计和监管/内部模板。当前实验只做本地 CSV 和 HTML 导出，用于理解报表层和在线决策层的职责差异。

### 规则配置 rule configuration

规则配置是把阈值、允许列表、开关等规则参数从代码里分离出来。

例如单笔审核阈值：

```text
single_transaction_review_threshold = 1000.00
```

如果这个数字写死在代码里，每次调整都需要改代码、跑测试、发布系统。真实金融机构中，很多规则参数会随着风险策略、产品策略、地区、用户等级或运营活动变化。把参数放进配置文件，可以让规则更容易审查、测试和调整。

但配置化不等于可以随意修改。真实系统通常还需要：

- 配置审批。
- 版本记录。
- 生效时间。
- 回滚能力。
- 变更审计。
- 灰度或分组实验。

当前实验只实现最小 JSON 配置，不实现审批和版本管理。

### 规则版本 rule version

规则版本是给一组风控配置打上稳定标识，让历史决策可以追溯“当时用的是哪一版规则”。例如今天的单笔审核阈值是 `1000.00`，下个月可能调整成 `800.00`。如果历史决策只保存最终结果，而不保存规则版本，后续复盘时就会出现一个问题：现在看到的配置已经不是当时运行时的配置。

真实金融领域里，规则版本常用于：

- 回答客户或内部团队：某笔交易为什么在当时被审核或阻断。
- 比较规则调整前后的命中率、误伤率和人工审核量。
- 在事故复盘时还原当时生效的阈值、名单、开关和策略。
- 支持灰度发布、回滚、审批和变更审计。

当前实验新增 `RiskRuleVersion`，保存：

- `version_id`：规则版本标识，例如 `rules-2026-05-05`。
- `single_transaction_review_threshold`：单笔审核阈值。
- `daily_user_review_threshold`：用户日累计审核阈值。
- `allowed_currencies`：允许币种。
- `high_risk_countries`：高风险 IP 国家/地区列表。
- `blocked_beneficiaries`：受阻收款方列表。
- `risk_score_review_threshold`：风险分数审核阈值。
- `rule_scores`：每条规则的分值配置。
- `source`：配置来源，例如 `risk_rules.json`。
- `effective_at`：规则生效时间。
- `created_at`：版本记录创建时间。

每条风控决策可以保存 `rule_version_id`，指向当时使用的规则版本。当前实验还会追加 `risk_rule_version.saved` 审计事件，用于记录规则版本被保存这一动作。

当前实现仍然是教学版：它记录版本，并支持最小报表对比，但不实现审批流、生效窗口选择、灰度发布、配置差异比对和自动回滚。

### 风控持久化 risk persistence

风控持久化是把规则引擎输出的决策、命中的规则、人工审核案例和审核结果保存到数据库里。它不是新的风控判断逻辑，而是把“系统当时为什么这么判断、后来谁怎么处理”变成可查询记录。

在真实金融领域，持久化的作用非常重要：

- 运营人员需要查询哪些请求还在待审核。
- 客服或申诉团队需要知道请求为什么被拦截或审核。
- 风控团队需要统计哪些规则命中最多、误伤最多。
- 审计和合规团队需要追溯某个请求的决策依据和人工处理记录。
- 事故复盘时需要还原当时系统看到的信息和做出的动作。

对程序员来说，风控持久化不是简单地把对象 `json.dumps()` 进一列。规则命中通常需要拆成明细表，因为后续会按 `rule_id`、状态、时间、用户等维度查询。审核案例也要单独建表，因为它有自己的状态流转、审核人、审核理由和时间。

当前实验新增 `SQLiteRiskStore`，它只负责保存和读取：

- `RiskDecision`
- `RuleHit`
- `ReviewCase`
- `RiskAuditEvent`
- `RiskRuleVersion`

规则计算仍由 `RiskRuleEngine` 完成，人工审核状态仍由 `ManualReviewService` 完成。这样可以保持职责清晰：规则引擎负责判断，审核服务负责状态流转，SQLite 存储负责记录和恢复。

### 审计事件 audit event

审计事件是对重要动作的追加式记录。它回答的问题不是“对象现在是什么状态”，而是“状态是怎么一步步变成现在这样的”。

例如审核案例当前状态可能是：

```text
review:txn_003 -> approved
```

但审计事件会记录过程：

```text
risk_decision.saved
review_case.created
review_case.approved
```

在金融系统里，这类记录用于内部审计、问题复盘、操作追责、客户申诉和合规检查。状态表只保留当前状态，审计日志保留动作历史。两者不能互相替代。

当前实验新增 `risk_audit_events` 表。它记录：

- `event_type`：发生了什么动作，例如 `risk_decision.saved`、`review_case.created`、`review_case.approved`。
- `aggregate_type` 和 `aggregate_id`：动作属于哪个对象，例如某个风控决策或某个审核案例。
- `actor`：动作是谁触发的，例如 `system` 或 `analyst_001`。
- `reason`：动作原因，审核批准或拒绝时尤其重要。
- `payload`：事件快照，保存少量便于排查的结构化信息。
- `occurred_at`：事件发生时间。

对程序员来说，审计日志通常应尽量 append-only，也就是追加新事件，而不是修改旧事件。真实生产系统还会考虑防篡改、访问权限、日志保留期限、PII 脱敏、加密、签名、集中日志平台和监管取证要求。当前实验只实现 SQLite 里的最小追加式事件表。

## 为什么金融系统需要规则引擎

风控规则引擎在金融系统里很常见，因为它能把风险控制从业务代码里拆出来，并提供可解释的决策记录。

典型使用场景：

- 支付：大额支付、异常频率、可疑收款方。
- 提现：新设备登录后大额提现、短时间多次提现。
- 开户：身份信息缺失、地区限制、名单命中。
- 信贷：收入不稳定、负债过高、逾期历史。
- 交易：异常下单频率、超过风险限额。
- AML：可疑交易模式、制裁名单或高风险地区。

FFIEC 的认证和访问风险管理指导强调金融机构应基于风险评估采取合适的访问和认证控制。FATF 的风险为本方法也强调不同机构需要根据自身风险识别和控制风险。当前实验不是这些规则的实现，只是学习“规则、决策、命中原因”这个工程骨架。

## 当前实验数据结构

输入请求：

```text
transaction_id
user_id
amount
currency
created_at
device_id
ip_country
beneficiary_id
```

历史请求用于计算日累计金额：

```text
history = previous requests for the same user
```

输出决策：

```text
request_id
user_id
status
rule_hits
risk_score
```

人工复核案例：

```text
case_id
request_id
user_id
status
rule_hits
created_at
reviewed_by
review_reason
reviewed_at
```

SQLite 表结构：

```text
risk_decisions
risk_rule_versions
risk_decision_rule_hits
review_cases
review_case_rule_hits
risk_audit_events
```

只读报表对象：

```text
RiskSummaryReport
RiskRuleVersionComparisonReport
RiskReportExportPaths
DecisionStatusCount
RuleHitCount
ReviewStatusCount
DecisionStatusComparison
RuleHitComparison
ReviewStatusComparison
```

报表筛选字段：

```text
rule_version_id
decided_from
decided_to
baseline_rule_version_id
comparison_rule_version_id
```

导出文件：

```text
labs/risk-rule-engine/reports/risk_summary_report.csv
labs/risk-rule-engine/reports/rule_version_comparison_report.csv
labs/risk-rule-engine/reports/risk_report.html
```

含义：

- `risk_decisions`：保存每个请求的最终风控决策，例如 `approved`、`review`、`blocked`。
- `risk_rule_versions`：保存规则配置版本，包括阈值、允许币种、来源和生效时间。
- `risk_decision_rule_hits`：保存该决策命中了哪些规则、每条规则的状态和原因。
- `review_cases`：保存人工审核案例本身，包括状态、创建时间、审核人、审核理由和审核时间。
- `review_case_rule_hits`：保存审核案例创建时看到的规则命中快照，避免后续规则变更后无法还原当时的审核依据。
- `risk_audit_events`：按追加方式保存关键动作事件，例如保存风控决策、创建审核案例、批准或拒绝审核案例。
- `RiskSummaryReport`：从 SQLite 中读取已有记录并聚合，不改变任何决策或审核状态。

## 当前简化了什么

当前实验刻意简化：

- 仍只处理少量交易请求字段，不处理完整商户画像、账户画像、登录行为和跨产品风险数据。
- 当前只加入最小设备、IP 国家/地区和收款方信号，不接真实设备指纹、IP 地理库、名单筛查或用户画像服务。
- 只使用固定阈值，不使用机器学习模型。
- 只按 UTC 日期计算日累计，不处理用户本地时区。
- 不接真实名单、KYC、AML 或制裁筛查。
- 人工审核只实现案例状态机和 SQLite 存储，不实现审核工作台、队列分派、权限控制、SLA、双人复核和申诉。
- SQLite 持久化保存决策、规则命中、审核案例和审计事件，但不实现数据库迁移、加密、权限隔离、归档、数据保留策略和防篡改审计。
- 规则版本只记录配置快照和生效时间，不实现审批、生效窗口选择、灰度发布和回滚。
- 风险评分只使用固定规则分值，不实现机器学习模型、概率校准、特征工程和模型监控。
- 纯评分策略只实现两个教学版弱信号，不接入真实设备指纹、行为画像、地理位置差异、失败次数、账户年龄或模型服务。
- 规则命中统计报表支持按规则版本和决策时间窗口筛选，但不实现按用户、地区、产品线、审核人维度筛选，也不计算真实误伤率和损失率。
- 规则版本对比报表只比较聚合数量和风险分数差异，不实现流量回放、A/B 实验、统计显著性检验、配置差异展示或自动推荐规则版本。
- 报表导出只生成本地 CSV 和 HTML 文件，不实现权限控制、数据脱敏、定时任务、报表审批、归档保留、下载审计和监管报送。

这些简化是为了先把规则引擎、人工复核、持久化、审计事件、规则版本和报表观察的基本形状写清楚。后续可以逐步加入更复杂的风险信号、生产级审计控制和更接近真实风控运营的效果评估。

## 风控规则配置文件

当前实验新增：

```text
labs/risk-rule-engine/risk_rules.json
```

示例：

```json
{
  "single_transaction_review_threshold": "1000.00",
  "daily_user_review_threshold": "3000.00",
  "allowed_currencies": ["USD", "EUR"],
  "high_risk_countries": ["KP", "IR"],
  "blocked_beneficiaries": ["beneficiary_blocked_001"],
  "risk_score_review_threshold": 50,
  "rule_scores": {
    "currency_allowed": 100,
    "ip_country_allowed": 100,
    "beneficiary_allowed": 100,
    "single_transaction_amount": 60,
    "daily_user_amount": 70,
    "new_device": 35,
    "unusual_hour": 25,
    "round_amount": 30
  }
}
```

字段含义：

- `single_transaction_review_threshold`：单笔金额超过该阈值时进入 `review`。
- `daily_user_review_threshold`：同一用户当天累计金额超过该阈值时进入 `review`。
- `allowed_currencies`：允许处理的币种列表，不在列表里的币种进入 `blocked`。
- `high_risk_countries`：高风险 IP 国家/地区列表，命中时进入 `blocked`。
- `blocked_beneficiaries`：受阻收款方列表，命中时进入 `blocked`。
- `risk_score_review_threshold`：风险评分达到该阈值时可进入审核策略；当前实验先保存该配置。
- `rule_scores`：每条规则命中时贡献的分数。
- `unusual_hour`：教学版非典型时间弱信号分值。
- `round_amount`：教学版整数金额弱信号分值。

demo 会从这个 JSON 文件读取配置，然后创建 `RiskRuleEngine`。代码仍然保留直接传参数的方式，便于测试和学习。

## 当前实验新增了什么

- `labs/risk-rule-engine/risk_rule_engine.py`
- `labs/risk-rule-engine/risk_rules.json`
- `labs/risk-rule-engine/demo.py`
- `labs/risk-rule-engine/demo_sqlite.py`
- `labs/risk-rule-engine/risk_reporting.py`
- `labs/risk-rule-engine/risk_report_export.py`
- `labs/risk-rule-engine/test_risk_rule_engine.py`
- `labs/risk-rule-engine/test_sqlite_risk_store.py`
- `labs/risk-rule-engine/test_risk_reporting.py`
- `labs/risk-rule-engine/test_risk_report_export.py`
- `RiskRuleEngine`
- `RiskRuleConfig`
- `RiskRequest`
- `RiskDecision`
- `RuleHit`
- `ManualReviewService`
- `ReviewCase`
- `ReviewStatus`
- `SQLiteRiskStore`
- `RiskAuditEvent`
- `RiskRuleVersion`
- `RiskSummaryReport`
- `RiskRuleVersionComparisonReport`
- `RiskReportExportPaths`
- `approved / review / blocked`
- `pending_review / approved / rejected`

运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo.py
```

运行 SQLite demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\risk-rule-engine\demo_sqlite.py
```

运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\risk-rule-engine
```

## 资料来源

- FFIEC, Authentication and Access to Financial Institution Services and Systems: https://www.ffiec.gov/news/press-releases/2021/pr-08-11
- FATF, Guidance on the Risk-Based Approach to Combating Money Laundering and Terrorist Financing: https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatfguidanceontherisk-basedapproachtocombatingmoneylaunderingandterroristfinancing-highlevelprinciplesandprocedures.html
- CFPB, Fraud and scams: https://www.consumerfinance.gov/consumer-tools/fraud/

访问日期：2026-05-05
