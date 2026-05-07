# KYC/AML 开户筛查：身份、受益所有人和名单命中

最后更新：2026-05-07

本篇进入新的学习主题：KYC/AML 和合规基础。目标不是实现真实合规系统，也不是解释某个司法辖区的完整法律义务，而是先理解金融系统为什么在开户、账户升级、付款和提现前要做身份识别、客户风险画像、名单筛查和可解释记录。

## 先给结论

KYC/AML 开户筛查的最小闭环是：

```text
customer application + policy + watchlist -> checks -> decision + reasons
```

当前实验输入一份客户开户申请和一份样例名单，输出一个可解释决策：

- `approved`：资料和样例检查通过。
- `review`：需要人工或合规流程继续确认。
- `blocked`：命中教学版强阻断条件，不能自动开户。

第一版只实现几类教学规则：

- 必填身份字段缺失，进入 `review`。
- 法人客户 legal entity 缺少 beneficial owner 信息，进入 `review`。
- 客户或 beneficial owner 与样例名单高度匹配，进入 `blocked`。
- 客户或 beneficial owner 与样例名单模糊匹配，进入 `review`。
- 客户国家/地区命中样例高风险列表，进入 `review`。
- 预期月交易量较高，进入 `review`。

在此基础上，当前实验已经加入最小人工复核状态机：当决策是 `review` 时，可以创建 `KycReviewCase`，并从 `pending_review` 流转到 `approved`、`rejected` 或 `request_more_info`。现在也加入了 SQLite 持久化，把客户申请、beneficial owner、KYC/AML 决策、检查结果、审核案例和审计事件保存下来，便于后续查询和复核。

当前实验还加入了最小 KYC/AML 汇总报表。它不会改变任何开户决策，只从已经保存的记录中聚合：

- 客户类型数量。
- 决策状态数量。
- 检查命中次数。
- 平均和最高风险分数。
- 待审核案例数量。
- 审核状态数量。

报表支持按客户类型、决策状态、watchlist 版本、policy 版本、提交时间窗口和决策时间窗口筛选。

当前实验还支持把 KYC/AML 汇总报表导出为本地文件：

```text
kyc_summary_report.csv
kyc_version_comparison_report.csv
kyc_replay_report.csv
kyc_report.html
```

CSV 便于归档、复核和进一步处理；HTML 便于运营、合规或学习者离开命令行查看结果。

当前实验还加入了 watchlist 数据版本记录。每一版样例名单会保存：

```text
version_id
source
entry_count
content_hash
effective_at
created_at
```

每条 KYC/AML 决策可以关联 `watchlist_version_id`，用于说明“当时是用哪一版名单数据做的筛查”。

当前实验还加入了 KYC/AML 策略版本记录。每一版样例策略会保存：

```text
version_id
source
high_risk_countries
beneficial_owner_threshold_percent
high_expected_monthly_volume_cents
fuzzy_review_score_threshold
exact_block_score_threshold
risk_score_review_threshold
effective_at
created_at
```

每条 KYC/AML 决策也可以关联 `policy_version_id`，用于说明“当时是用哪一版策略参数做的判断”。

当前实验还加入了 watchlist/policy 版本对比报表。它比较两个已经保存的版本下的汇总结果，包括：

- 客户类型数量差异。
- 决策状态数量差异。
- 检查命中次数差异。
- 平均和最高风险分数差异。
- 待审核案例数量差异。
- 审核状态数量差异。

这个对比报表只是基于已经保存的决策做聚合比较，不会用新名单或新策略重新计算历史申请。

当前实验还加入了 KYC/AML replay 报表。Replay 会读取已经保存的客户申请，用一份新的样例 policy 和 watchlist 重新评估，再逐客户比较：

- 原决策状态和重放决策状态。
- 状态是否变化。
- 原风险分数和重放风险分数。
- 风险分数变化。
- 新增的非通过检查项。
- 消失的非通过检查项。

Replay 不会改写原始 `kyc_decisions`，也不会自动创建或关闭审核案例。它只是一个分析工具，用来观察“如果今天用另一版策略或名单重新看这批申请，会发生什么变化”。

当前实验进一步把 replay run 保存进 SQLite。保存 replay run 的意义是：不仅能临时生成一份 CSV，还能留下“某次重放评估在什么时间、由谁创建、覆盖多少申请、产生多少状态变化、最后是否被批准用于后续动作”的记录。

SQLite 中新增两类记录：

- `kyc_replay_runs`：保存一次 replay 运行的汇总、创建人、创建时间和审批状态。
- `kyc_replay_run_items`：保存这次运行中每个客户的原决策、重放决策、风险分数变化和检查项变化。

Replay run 的状态是：

```text
pending_review -> approved / rejected
```

审批动作会记录 `reviewed_by`、`review_reason` 和 `reviewed_at`，并追加审计事件：

```text
kyc_replay_run.created
kyc_replay_run.approved
kyc_replay_run.rejected
```

这仍然不等于“自动发布新策略”。当前实验只保存评估和审批结论，不会自动把 replay 决策写回 `kyc_decisions`，也不会自动更新开户状态、创建新审核任务或关闭已有审核任务。

注意：实验中的名单、国家/地区、阈值和分值都是教学数据，不代表 OFAC、FATF、FinCEN 或任何监管机构的真实清单和规则。

## 中文定义

KYC，Know Your Customer，通常译为“了解你的客户”或“客户身份识别”。它要求金融机构在建立客户关系时识别客户身份，并根据风险情况理解客户关系的性质和目的。

AML，Anti-Money Laundering，反洗钱，是识别、预防和报告洗钱、恐怖融资和相关非法金融活动的一组制度、流程和系统。

常见英文术语：

- 客户身份识别：Customer Identification Program / CIP
- 客户尽职调查：Customer Due Diligence / CDD
- 强化尽职调查：Enhanced Due Diligence / EDD
- 受益所有人：beneficial owner
- 制裁筛查：sanctions screening
- 可疑活动报告：Suspicious Activity Report / SAR
- 交易监测：transaction monitoring
- 风险为本方法：risk-based approach / RBA
- 名单匹配：watchlist matching
- 误命中：false positive
- 人工复核：manual review
- 审计事件：audit event
- 汇总报表：summary report
- 报表筛选：report filter
- 报表导出：report export
- CSV 报表：CSV report
- HTML 报表：HTML report
- 名单版本：watchlist version
- 策略版本：policy version
- 内容哈希：content hash

## 核心概念逐个解释

### KYC

KYC 是金融机构确认“客户是谁”的过程。对个人客户，通常会涉及姓名、出生日期、证件信息、地址等身份资料。对法人客户，还会涉及公司本身的信息，以及谁最终拥有或控制这家公司。

程序员实现时要注意：KYC 不是单个表单校验。它通常包括资料采集、身份验证、名单筛查、风险评级、人工复核、记录留存和后续更新。

### CDD

CDD，Customer Due Diligence，客户尽职调查，是在识别身份之外进一步理解客户关系。例如客户为什么开账户、预期交易规模是多少、业务所在地区是什么、是否存在更高风险特征。

FATF Recommendations 把 CDD 放在反洗钱和反恐融资预防措施中，并强调不同国家需要按自身法律和风险环境落地。FinCEN 的 CDD 资料也强调识别客户、识别 beneficial owner、理解客户关系性质和目的，以及持续监测。

### beneficial owner

beneficial owner 是最终拥有、控制或从法人客户中受益的自然人或相关控制方。金融系统关注它，是因为非法资金可能通过空壳公司、复杂股权结构或代理人隐藏真实控制者。

美国 FinCEN CDD 规则资料中提到 covered financial institutions 的 beneficial ownership 要求和 25% 所有权口径；但 2026-02-13 FinCEN 发布了 exceptive relief，2026-05-06 CDD FAQ 也更新了相关解释。因此本仓库只把它作为“为什么要在实验里建 beneficial owner 字段”的来源示例，不能把实验逻辑当成美国合规结论。

### sanctions screening

sanctions screening 是把客户、beneficial owner、收款方或交易对手与制裁名单、内部名单或其他限制名单做匹配。

OFAC 的 Sanctions List Search 工具说明其名称搜索使用 fuzzy logic 来寻找潜在匹配。这个点对程序员很重要：名单筛查不是简单字符串相等。真实系统会处理别名、拼写差异、转写、出生日期、国家/地区、证件号、实体类型、误命中和人工确认。

当前实验使用 Python 标准库里的 `difflib.SequenceMatcher` 做最小模糊匹配，只用于学习“为什么需要 match score 和人工复核”。

### 人工复核 manual review

人工复核表示系统不直接自动通过或拒绝，而是把开户申请交给运营、合规或风控人员继续判断。

当前实验实现了一个最小状态机：

```text
review decision -> KycReviewCase(pending_review) -> approved / rejected / request_more_info
```

`request_more_info` 表示资料暂时不足，需要客户或业务团队补充材料。真实系统中，它通常会带来通知、补件任务、截止时间、再次提交和重新审核流程。当前实验只记录状态、审核人、审核理由和审核时间。

### 审计事件 audit event

审计事件是对关键动作的追加式记录。它回答“这份申请经历了哪些动作”，而不只是“当前状态是什么”。

当前实验会记录：

```text
kyc_application.saved
kyc_decision.saved
kyc_review_case.created
kyc_review_case.approved / rejected / request_more_info
```

对程序员来说，KYC/AML 场景里的审计记录尤其重要，因为后续可能需要解释某个客户为什么被放行、拒绝、要求补充材料或命中某条名单筛查规则。

### KYC/AML 报表 KYC/AML reporting

KYC/AML 报表是把已经保存的开户申请、决策、检查结果、风险分数和审核案例做聚合，回答“整体队列和规则效果是什么样”的问题。

当前实验的最小报表包括：

- 客户类型数量：多少是 `individual`，多少是 `legal_entity`。
- 决策状态数量：多少是 `approved`、`review`、`blocked`。
- 检查命中次数：哪些检查项最常产生 `review` 或 `blocked`。
- 风险分数：平均 `risk_score` 和最高 `risk_score`。
- 人工审核工作量：当前待审核案例数量。
- 审核状态数量：多少是 `pending_review`、`approved`、`rejected`、`request_more_info`。

当前报表支持几个最小筛选维度：

- `customer_type`：只看个人客户或法人客户。
- `decision_status`：只看某一种决策状态。
- `watchlist_version_id`：只看某一版名单数据下保存的决策。
- `policy_version_id`：只看某一版策略参数下保存的决策。
- `submitted_from` / `submitted_to`：按申请提交时间窗口筛选。
- `decided_from` / `decided_to`：按决策时间窗口筛选。

这些筛选维度很重要，因为合规团队通常不会只看全量历史。团队可能需要观察某天提交的开户申请、某类法人客户、某个审核队列，或只看被阻断的申请。当前实验中的审核状态统计会跟随已筛选的客户集合，只统计这些客户对应的审核案例。

对程序员来说，报表层提醒我们：合规系统不能只保存单笔记录。没有聚合查询，团队就很难知道规则是否过严、审核队列是否积压、补件是否过多、哪些检查项带来了最多人工工作量。

当前实验也新增了报表导出。它把 `KycSummaryReport`、可选的 `KycVersionComparisonReport` 和可选的 `KycReplayReport` 写成本地文件：

```text
kyc_summary_report.csv
kyc_version_comparison_report.csv
kyc_replay_report.csv
kyc_report.html
```

报表导出的真实作用是把系统里的聚合口径转换成人可阅读、可归档、可分享的文件。数据库记录适合系统查询，审计事件适合追溯动作历史，报表适合复核整体情况。当前实验在 HTML 中使用转义，避免检查项名称等文本直接进入 HTML 造成展示层注入风险。

### Watchlist 数据版本 watchlist version

Watchlist 数据版本是给一份名单数据打上稳定标识，让未来可以追溯某条 KYC/AML 决策“当时使用的是哪一份名单”。

名单筛查数据会变化。今天没有命中，不代表开户当时使用的名单也是今天这一版；今天命中，也不代表历史决策当时就应该命中。真实系统如果只保存“最终命中结果”，却不保存名单来源、版本和内容摘要，未来复盘时就很难还原当时系统看到的世界。

当前实验新增 `KycWatchlistVersion`，保存：

- `version_id`：名单版本标识，例如 `sample-watchlist-2026-05-07`。
- `source`：数据来源，例如 `sample_watchlist.json`。
- `entry_count`：名单条目数量。
- `content_hash`：名单内容的 SHA-256 摘要，用于发现内容是否变化。
- `effective_at`：名单生效时间。
- `created_at`：版本记录创建时间。

每条 KYC/AML 决策可以保存 `watchlist_version_id`，指向当时使用的名单版本。当前实验还会追加 `kyc_watchlist_version.saved` 审计事件，用于记录名单版本被保存这一动作。

当前实现仍然是教学版：它记录样例名单版本和内容哈希，但不下载真实 OFAC、UN、EU、HM Treasury 或其他名单，不实现名单增量更新、审批、回滚、版本差异展示和筛查回放。

### risk-based approach

risk-based approach 是按风险程度决定控制强度。低风险客户可能只需要标准流程，高风险客户可能需要更多资料、人工复核或更频繁监测。

程序员实现时要注意：风险为本不是“分数越高越合规”。系统必须能解释分数来自哪些检查、哪些阈值、哪个版本的策略，并保留当时的输入和输出。

## 为什么金融系统需要 KYC/AML

没有 KYC/AML，金融系统很难回答几个基础问题：

- 账户实际属于谁？
- 公司背后的实际控制人是谁？
- 客户是否可能命中制裁、恐怖融资或其他限制名单？
- 客户交易行为是否和开户时声明的目的明显不一致？
- 如果后续发生欺诈、洗钱或监管检查，系统能否还原当时做过哪些检查？

对工程系统来说，KYC/AML 的核心不是“写几个 if”。它要求数据、流程、权限、审计和人工复核协同工作。

## 当前实验数据结构

输入客户申请：

```text
customer_id
customer_type
full_name
date_of_birth
country
address
identification_number
expected_monthly_volume_cents
beneficial_owners
```

样例名单：

```text
entry_id
list_name
full_name
country
date_of_birth
```

输出决策：

```text
customer_id
status
check_results
risk_score
```

人工复核案例：

```text
case_id
customer_id
status
check_results
created_at
reviewed_by
review_reason
reviewed_at
```

SQLite 表结构：

```text
kyc_applications
kyc_beneficial_owners
kyc_decisions
kyc_check_results
kyc_review_cases
kyc_review_case_check_results
kyc_audit_events
kyc_watchlist_versions
kyc_policy_versions
kyc_replay_runs
kyc_replay_run_items
```

只读报表对象：

```text
KycSummaryReport
KycVersionComparisonReport
KycReplayReport
KycReplayRun
CustomerTypeCount
DecisionStatusCount
CheckHitCount
ReviewStatusCount
```

报表筛选字段：

```text
customer_type
decision_status
submitted_from
submitted_to
decided_from
decided_to
watchlist_version_id
policy_version_id
```

导出文件：

```text
labs/kyc-aml-onboarding/reports/kyc_summary_report.csv
labs/kyc-aml-onboarding/reports/kyc_version_comparison_report.csv
labs/kyc-aml-onboarding/reports/kyc_replay_report.csv
labs/kyc-aml-onboarding/reports/kyc_report.html
```

每条检查结果：

```text
check_id
status
reason
score
```

含义：

- `customer_id`：开户申请的稳定标识。
- `customer_type`：`individual` 或 `legal_entity`。
- `beneficial_owners`：法人客户背后的受益所有人列表。
- `watchlist`：教学版名单，不是真实制裁名单。
- `check_results`：每条检查的状态、原因和分值。
- `risk_score`：所有非通过检查的分值总和。
- `kyc_applications`：保存客户申请快照。
- `kyc_beneficial_owners`：保存法人客户的 beneficial owner 明细。
- `kyc_decisions`：保存 KYC/AML 最终决策。
- `kyc_check_results`：保存每条检查的原因和分值。
- `kyc_review_cases`：保存人工复核案例和审核结果。
- `kyc_audit_events`：追加保存关键动作历史。
- `kyc_watchlist_versions`：保存样例名单版本、来源、条目数、内容哈希和生效时间。
- `kyc_policy_versions`：保存样例 KYC/AML 策略参数版本、来源和生效时间。
- `kyc_replay_runs`：保存 replay 运行汇总、创建人、审批状态和审批理由。
- `kyc_replay_run_items`：保存某次 replay 中每个客户的状态变化、风险分数变化和检查项变化。
- `KycSummaryReport`：从 SQLite 中读取已有记录并聚合，不改变任何申请、决策或审核状态。
- `KycVersionComparisonReport`：比较两个已保存版本下的汇总结果差异，不做历史申请重放。
- `KycReplayReport`：用新的样例策略和名单重新评估已保存申请，逐客户比较原决策和重放决策，但不改写原始决策。
- `KycReplayRun`：保存一次 replay 分析的运行记录和审批结论。
- `KycReportExportPaths`：记录导出的 CSV 和 HTML 文件路径。

## 当前简化了什么

当前实验刻意简化：

- 不接真实身份证、护照、企业注册、税号或地址验证服务。
- 不接真实 OFAC、UN、EU、HM Treasury 或其他制裁名单。
- 不实现 PEP、负面新闻、设备风险、IP 风险和交易监测。
- 不实现 SAR/STR 申报流程，也不提供申报判断。
- SQLite 持久化保存申请、决策、审核案例、replay run 和审计事件，但不实现数据保留、脱敏、加密、访问权限和真实工作流自动化。
- KYC/AML 汇总报表支持客户类型、决策状态、提交时间窗口和决策时间窗口筛选，但不实现按地区、审核人、名单来源、产品线、风险等级或 SLA 的复杂筛选。
- KYC/AML 版本对比报表比较已保存决策；KYC/AML replay 可以重新计算历史申请，也可以保存 replay run 和审批结论，但不写回原始决策，不自动发布策略，不自动创建或关闭审核任务。
- 当前报表只统计已有记录，不计算真实误伤率、损失率、SAR/STR 线索数量或监管报送口径。
- 报表导出只生成本地 CSV 和 HTML 文件，不实现权限控制、数据脱敏、定时任务、报表审批、归档保留和下载审计。
- Watchlist 版本记录只保存样例名单的内容哈希，不接真实名单源，不实现名单审批、发布、回滚和自动重筛。
- Policy 版本记录只保存样例策略参数，不实现策略审批、灰度发布和回滚。
- Replay run 审批只表示样例评估结果已经被记录和确认，不代表真实合规审批、模型治理、策略上线或生产发布流程。
- 不处理跨司法辖区差异。
- 不把 `blocked` 解释为真实法律结论，只表示教学版规则不允许自动开户。

这些简化是为了先把 KYC/AML 系统的工程形状写清楚：资料采集、检查、分值、决策、原因和测试。

## 当前实验新增了什么

- `labs/kyc-aml-onboarding/kyc_aml.py`
- `labs/kyc-aml-onboarding/demo.py`
- `labs/kyc-aml-onboarding/demo_sqlite.py`
- `labs/kyc-aml-onboarding/README.md`
- `labs/kyc-aml-onboarding/test_kyc_aml.py`
- `labs/kyc-aml-onboarding/test_sqlite_kyc_store.py`
- `labs/kyc-aml-onboarding/sqlite_kyc_store.py`
- `labs/kyc-aml-onboarding/kyc_reporting.py`
- `labs/kyc-aml-onboarding/kyc_report_export.py`
- `KycAmlEngine`
- `KycAmlPolicy`
- `CustomerApplication`
- `BeneficialOwner`
- `WatchlistEntry`
- `KycDecision`
- `CheckResult`
- `KycReviewService`
- `KycReviewCase`
- `SQLiteKycStore`
- `KycAuditEvent`
- `KycWatchlistVersion`
- `KycPolicyVersion`
- `KycSummaryReport`
- `KycVersionComparisonReport`
- `KycReplayReport`
- `KycReplayItem`
- `KycReplayRun`
- `CustomerTypeCount`
- `DecisionStatusCount`
- `CheckHitCount`
- `ReviewStatusCount`
- `KycReportExportPaths`
- `approved / review / blocked`
- `pending_review / approved / rejected / request_more_info`

运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo.py
```

运行 SQLite demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\kyc-aml-onboarding\demo_sqlite.py
```

运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\kyc-aml-onboarding
```

## 资料来源

- FATF, The FATF Recommendations: https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html
  - 页面显示 Recommendations last updated in October 2025。
  - 访问日期：2026-05-07。
  - 支持结论：FATF Recommendations 是 AML/CFT/CPF 的国际标准框架，并包含 CDD、beneficial ownership 和 risk-based approach 相关要求。
- FinCEN, CDD Final Rule: https://www.fincen.gov/index.php/resources/statutes-and-regulations/cdd-final-rule
  - 页面提示 2026-02-13 exceptive relief。
  - 访问日期：2026-05-07。
  - 支持结论：CDD 包括识别客户、识别 beneficial owner、理解客户关系和持续监测等核心要求；同时美国 covered financial institutions 的具体义务有最新例外救济，不能泛化。
- FinCEN, CDD Rule FAQs: https://www.fincen.gov/resources/statutes-and-regulations/cdd-rule-faqs
  - 页面显示 updated May 6, 2026。
  - 访问日期：2026-05-07。
  - 支持结论：beneficial ownership 信息识别和验证在美国 CDD 语境下有具体范围，并受到 2026 Account Opening Exceptive Relief Order 影响。
- OFAC, Sanctions List Search Tool: https://ofac.treasury.gov/sanctions-list-search-tool
  - 访问日期：2026-05-07。
  - 支持结论：OFAC 官方搜索工具使用 fuzzy logic 做名称潜在匹配。
- OFAC, Sanctions List Service: https://ofac.treasury.gov/sanctions-list-service
  - 访问日期：2026-05-07。
  - 支持结论：OFAC 提供可下载的 sanctions list data；真实系统应接官方数据源，而不是手写名单。
