# 合规与审计：日志、时间线、脱敏和记录留存

最后更新：2026-05-11

本篇进入“合规与审计”主题。目标不是解释某个国家或地区的完整监管义务，也不是替代法务、合规或审计人员判断，而是把前面风控和 KYC/AML 实验里已经产生的审计事件串起来，理解金融系统为什么需要可查询、可解释、可复核的 audit trail。

## 先给结论

合规审计的最小工程闭环是：

```text
business action -> audit event -> query/filter -> timeline/report
```

前面两个实验已经分别保存了审计事件：

- 风控：`risk_audit_events`
- KYC/AML：`kyc_audit_events`

当前实验新增一个只读统一视图，把两类事件转换成同一种 `ComplianceAuditEvent`：

```text
source_system
event_type
aggregate_type
aggregate_id
actor
reason
payload
occurred_at
```

它支持：

- 按来源系统、事件类型、事件前缀、主体、操作人和时间窗口筛选。
- 为一个主体构造跨系统 audit timeline。
- 汇总来源系统、事件类型和操作人数量。
- 对 JSON payload 中常见 PII 字段做教学版脱敏。
- 导出审计事件 CSV、主体时间线 CSV、审计汇总 CSV 和 HTML 报告。
- 使用教学版角色权限控制查看事件、查看 payload 和导出报表。
- 可选要求另一名具备审批权限的用户审批审计报告导出，演示职责分离。
- 记录教学版访问审计事件，用于追踪谁查看了事件、谁查看了 payload、谁导出了报表。
- 使用 SQLite 持久化访问审计事件，并按操作人、权限、结果和时间窗口查询。
- 使用教学版留存策略生成审计留存报告，区分 active、archive_due、delete_due 和 held。
- 使用教学版访问异常检测规则生成 access anomaly findings。
- 导出审计留存决策 CSV 和 HTML 报告，便于人工复核哪些事件仍活跃、应归档、可删除或处于 hold。
- 把访问异常发现项转成教学版 investigation case，并演示 open、investigating、resolved 和 false_positive 状态。
- 使用 SQLite 持久化 investigation case，并支持按状态、分派人和 finding actor 查询。

当前实验不改变风控或 KYC/AML 的原始表，也不新增真实 IAM 系统。它先解决一个基础问题：当一个客户经历开户筛查、人工复核、后续交易风控审核时，系统能否按时间顺序回答“发生过什么”。

当前实验还新增了报表导出。导出文件包括：

```text
compliance_audit_events.csv
compliance_audit_summary.csv
compliance_audit_timeline.csv
compliance_audit_report.html
```

CSV 适合归档、二次处理和精确比对；HTML 适合人工复核。HTML 报告会对事件字段和 payload 做转义，避免把日志里的文本直接当成页面代码执行。

当前实验还加入了最小权限模型。它不是完整 IAM 系统，只用三个角色说明“审计日志不是人人可查”：

| 角色 | 权限 |
| --- | --- |
| `audit_viewer` | 可以查看审计事件元数据，但 payload 会显示为 `[hidden]` |
| `audit_analyst` | 可以查看审计事件和 payload，但不能导出报表 |
| `audit_manager` | 可以查看审计事件、查看 payload、导出审计报表，并审批他人的导出请求 |

对应的权限标识是：

```text
view_audit_events
view_audit_payload
export_audit_report
approve_audit_export
```

这一步的重点是最小权限 least privilege：用户只拿完成工作所需的权限。查看事件列表、查看 payload、导出文件是三个不同动作，不能默认绑在一起。

当前实验还加入了教学版职责分离 segregation of duties。导出函数可以设置 `require_approval=True`，此时除了 `requested_by` 必须具备 `export_audit_report`，还需要一个 `AuditExportApproval`：

```text
AuditExportApproval
approved_by
approved_at
reason
```

审批人必须具备 `approve_audit_export`，并且不能和申请导出的人是同一个 `user_id`。这不是完整工作流，只是用 maker/checker 思路说明：高敏感操作不一定应该由同一个人发起并批准。

当前实验还记录访问审计 access audit。也就是说，审计系统本身的使用也要留下记录。当前记录三类动作：

```text
audit_access.granted
audit_access.denied
audit_payload.viewed / audit_payload.hidden
audit_export_approval.granted / audit_export_approval.denied
```

导出报表时也会记录 `export_audit_report` 权限是否被授予。这样可以回答一个更高阶的问题：不仅知道“客户经历了哪些业务动作”，也知道“谁查看过这些审计记录、谁尝试导出过报表”。

如果导出要求审批，审批权限检查和审批结论也会进入访问审计。demo 中 `manager_001` 申请导出，`manager_002` 审批导出，因此访问审计会出现 `approve_audit_export` 和 `audit_export_approval.granted`。

当前实验还把访问审计事件写入 SQLite 的 `audit_access_events` 表。内存里的 `AuditAccessRecorder` 适合在一次请求或一次 demo 运行中收集事件；SQLite 存储则说明真实系统里为什么要把这些访问记录落盘，否则进程结束后就无法复核“谁看过日志、谁被拒绝查看 payload”。

当前实验还加入了教学版记录留存 record retention。它不采用任何真实监管期限，只用样例策略说明工程形状：不同事件类型可以有不同保留期、归档阈值和 legal hold 标记。demo 会生成 `Audit retention summary`，展示哪些事件仍在活跃窗口，哪些应归档，哪些到期可删除，哪些因为 hold 不能删除。

当前实验还可以把留存决策导出为：

```text
audit_retention_decisions.csv
audit_retention_report.html
```

CSV 记录每条审计事件匹配到的策略、状态、年龄、归档到期时间、删除到期时间和原因；HTML 报告包含状态汇总和明细表。这里仍然只是教学版报告导出，不会真的删除、归档、冻结或迁移任何审计事件，也不代表任何真实监管留存期限。

当前实验还加入了教学版访问异常检测 access anomaly detection。它读取 `AuditAccessEvent`，用简单规则发现三类模式：

```text
repeated_denied_access
unauthorized_export_attempt
repeated_payload_view
```

demo 会输出 `Access anomaly findings`。这一步不是机器学习，也不是安全监控产品，只是说明：访问审计落盘之后，可以进一步做复核、告警和调查线索生成。

当前实验还可以把访问异常发现项导出为：

```text
access_anomaly_findings.csv
access_anomaly_report.html
```

CSV 适合复核、排序和导入其他分析工具；HTML 适合人工查看。HTML 报告会转义 actor、reason、permission 等字段，避免把访问审计内容当成页面代码执行。

当前实验还加入了教学版访问异常调查工单 investigation case。检测规则只负责说“这里有可疑模式”；调查工单负责记录“谁接手、是否开始调查、最后如何关闭”。demo 会把 access anomaly findings 转成 `AccessAnomalyInvestigationCase`，并演示：

```text
open -> investigating -> resolved
open -> investigating -> false_positive
```

这不是完整工单系统，只是把“发现线索”和“处理闭环”分开：finding 可以由规则生成，case 则需要人或流程来确认、分派和关闭。

当前实验还可以把 investigation case 写入 SQLite 的 `access_investigation_cases` 和 `access_investigation_case_events` 表。demo 会关闭并重开 SQLite 连接，再输出 `Persisted open investigation cases`，说明工单状态不只存在于内存里，进程重启后仍可以查询未关闭的调查。

当前实验还可以把 investigation case 导出为：

```text
access_investigation_cases.csv
access_investigation_report.html
```

CSV 记录工单状态、finding 类型、actor、severity、负责人、关闭原因和关联权限/目标；HTML 报告包含状态汇总和工单明细。它适合复核调查处理进度，但仍不替代真实工单系统或合规调查流程。

当前实验还会为 investigation case 的处理动作生成审计事件：

```text
access_investigation_case.created
access_investigation_case.started
access_investigation_case.resolved
access_investigation_case.false_positive
```

这一步回答的是“谁创建了调查、谁接手、谁关闭、用什么理由关闭”。也就是说，异常访问调查本身也进入 audit trail，而不只是业务系统和审计报表导出被记录。

## 中文定义

审计日志 audit log，是系统对关键动作的记录。它通常保存“谁在什么时候对什么对象做了什么，以及理由和上下文是什么”。

审计追踪 audit trail，是把多个审计日志按主体、对象或时间串起来后的可追溯链路。它回答的不是单个对象当前状态，而是状态如何一步步形成。

常见英文术语：

- 审计日志：audit log
- 审计事件：audit event
- 审计追踪：audit trail
- 主体时间线：subject timeline
- 操作人：actor
- 业务对象：aggregate
- 事件载荷：payload
- 脱敏：redaction / masking
- 个人可识别信息：Personally Identifiable Information / PII
- 记录留存：record retention
- 访问控制：access control
- 最小权限：least privilege
- 职责分离：segregation of duties
- 访问审计：access audit
- 下载审计：download audit
- 发起人与复核人：maker/checker
- 审批：approval
- 归档：archive
- 法律/调查冻结：legal hold
- 访问异常检测：access anomaly detection
- 调查工单：investigation case
- 告警/发现项：finding
- 严重程度：severity

### least privilege

Least privilege，最小权限，表示用户、服务或系统组件只获得完成当前任务所需的最低权限。

在审计系统里，这尤其重要。审计日志可能包含客户标识、审核理由、风险信号和内部策略线索。一个运营人员也许只需要知道“某客户有审核事件”，不一定需要看到完整 payload；一个分析师可能需要查看 payload 排查问题，但不一定应该能导出全量报表。

当前实验用 `AuditUser`、角色和权限集合做教学版实现：

```text
AuditUser("viewer_001", ("audit_viewer",))
AuditUser("analyst_001", ("audit_analyst",))
AuditUser("manager_001", ("audit_manager",))
```

如果用户缺少权限，`authorize_user` 会抛出 `ComplianceAuditError`。如果用户只有 `view_audit_events`，`visible_events_for_user` 会返回事件元数据，但把 payload 替换成 `[hidden]`。

### access audit

Access audit，访问审计，是对“谁访问了敏感系统或敏感数据”的记录。它关注的不只是业务动作，还包括查看、查询、导出、下载等操作。

在审计系统里，访问审计很关键。因为审计日志本身可能包含敏感信息，如果一个人能查看 payload 或导出报表，系统也应该记录这次访问。否则我们只能审计业务系统，却无法审计审计系统本身。

当前实验新增 `AuditAccessEvent` 和 `AuditAccessRecorder`。它们记录：

```text
event_type
actor
permission
target
outcome
occurred_at
reason
```

例如：

```text
audit_access.granted actor=viewer_001 permission=view_audit_events
audit_payload.hidden actor=viewer_001 permission=view_audit_payload
audit_access.granted actor=manager_001 permission=export_audit_report
```

当前实验用 `SQLiteAccessAuditStore` 把这些事件写入 `audit_access_events` 表，并支持：

```text
save_event
save_events
access_events
query_access_events
```

`query_access_events` 可以按 `actor`、`permission`、`outcome` 和 `occurred_at` 时间窗口筛选。demo 里会查询 `view_audit_payload` 被拒绝的记录，用来观察 viewer 只能看事件元数据、不能看 payload 的审计痕迹。

真实系统中，访问审计通常会写入独立日志、集中日志平台或安全监控系统，并包含 IP、设备、会话、请求来源、下载文件标识和审批工单。当前实验只做 SQLite 教学版持久化，用于理解这个工程形状。

### segregation of duties

Segregation of duties，职责分离，表示高风险动作不由同一个人完成所有关键步骤。常见形式是 maker/checker：一个人发起，另一个人复核或批准。

在审计报告导出场景里，风险点是导出文件可能包含大量审计记录、客户标识、审核理由和内部策略线索。即使某个用户有导出权限，团队也可能要求另一个具备审批权限的人确认导出目的和范围。

当前实验的最小规则是：

```text
requested_by.user_id != approval.approved_by.user_id
requested_by has export_audit_report
approval.approved_by has approve_audit_export
approval.reason is required
```

程序员实现时要注意，职责分离不是只在 UI 上隐藏按钮。后端导出函数必须校验申请人、审批人、权限、审批时间和理由，并把授权与审批结果写入访问审计。

### record retention

Record retention，记录留存，表示系统需要按规则保留、归档、冻结或清理记录。审计日志不是“越久越好”这么简单：保留太短会影响复核和追溯，保留太久又可能增加敏感数据暴露面和存储成本。

当前实验新增 `AuditRetentionPolicy`，用教学字段描述一个留存策略：

```text
policy_id
event_type_prefix
retention_days
archive_after_days
legal_hold
```

`build_retention_report` 会为每条 `ComplianceAuditEvent` 生成一个 `AuditRetentionDecision`：

```text
active       still inside active retention window
archive_due  archive threshold has been reached
delete_due   retention period has ended
held         policy is under legal hold
```

如果多个策略都能匹配同一个事件类型，实验会选择 `event_type_prefix` 最长的策略。例如 `kyc_review_case.` 会优先于更宽泛的 `kyc_`。这可以表达“某类复核事件比普通 KYC 事件更敏感，需要特殊处理”。

程序员实现时要注意：真实 retention policy 属于法律、监管、合规和数据治理问题，需要按业务所在地、产品类型、客户类型、数据类型和调查状态确认。本实验里的 `30`、`45`、`90` 天只是样例数字，不代表任何真实要求。

### access anomaly detection

Access anomaly detection，访问异常检测，是在访问审计事件上寻找可疑模式。它不只看单条事件，而是把同一个 actor 在一个时间窗口内的行为聚合起来。

当前实验新增 `AccessMonitoringRule` 和 `AccessAnomalyFinding`。默认规则包括：

```text
repeated_denied_access
unauthorized_export_attempt
repeated_payload_view
```

每个 finding 会记录：

```text
finding_type
actor
severity
event_count
reason
first_occurred_at
last_occurred_at
events
```

程序员实现时要注意，异常检测规则要可解释、可调参，并且需要控制误报。比如当前实验用 `manager_` 前缀简化识别 manager，只是为了教学；真实系统应使用 IAM、组织架构、角色授权和会话上下文。

### investigation case

Investigation case，调查工单，是把 finding 交给人或流程处理的跟踪对象。它不等同于 finding：finding 是规则输出的线索，case 是处理这条线索的工作记录。

当前实验新增 `AccessAnomalyInvestigationCase` 和 `AccessAnomalyInvestigationService`。每个 case 记录：

```text
case_id
finding
status
created_at
opened_by
assigned_to
investigation_started_at
closed_by
closed_at
resolution_reason
```

状态包括：

```text
open
investigating
resolved
false_positive
```

程序员实现时要注意：真实工单系统还会包含 SLA、优先级、评论、附件、证据链、权限、通知、升级路径和更完整的审计历史。当前实验只保留最小状态机和处理动作审计事件，用来理解为什么 anomaly finding 不应该停留在一份静态报告里。

当前实验还新增 `SQLiteInvestigationCaseStore`，把 case 和相关 access events 分表保存：

```text
access_investigation_cases
access_investigation_case_events
```

它支持：

```text
save_case
get_case
cases
open_cases
query_cases
```

`query_cases` 可以按 `status`、`assigned_to` 和 finding 的 `actor` 查询。这里的持久化仍是教学版：它不实现工单评论、附件、权限模型、审计历史表或 SLA 计时。

`AccessAnomalyInvestigationService` 还会在内存中维护 `audit_events`，用于查看工单处理动作：

```text
audit_events
access_investigation_case.created
access_investigation_case.started
access_investigation_case.resolved
access_investigation_case.false_positive
```

当前这些工单审计事件还没有写入单独 SQLite 审计表；demo 先直接打印它们，帮助理解“调查动作本身也要可追踪”。

## 核心概念逐个解释

### audit event

Audit event 是一条不可忽略的动作记录。例如：

```text
kyc_application.saved
kyc_decision.saved
kyc_review_case.request_more_info
risk_decision.saved
review_case.approved
```

它和普通 debug log 不同。Debug log 主要帮助开发排错，可能会很快轮转或删除；audit event 面向复核、追责、解释和报表，通常需要结构化字段、稳定语义和更严格的访问控制。

程序员实现时要注意：审计事件最好包含稳定对象标识，而不是只保存一段人类可读文本。否则后续很难按客户、交易、审核案例或操作人查询。

### aggregate

Aggregate 是事件所属的业务对象。例如：

```text
kyc_decision:cust_001
kyc_review_case:kyc_review:cust_001
risk_decision:txn_001
review_case:review:txn_001
```

前半部分是 `aggregate_type`，后半部分是 `aggregate_id`。这样做的好处是同一个审计表可以保存多类对象事件，同时还能精确筛选。

### actor

Actor 表示动作由谁触发。当前实验里常见两类：

- `system`：系统自动保存决策、创建版本或创建审核案例。
- `analyst_001` / `kyc_analyst_001`：样例人工审核人。

真实系统里 actor 通常还要和权限、认证、会话、工单和操作来源关联。当前实验只保存字符串，帮助理解“审计记录不能只有结果，还要有操作人”。

### payload

Payload 是事件附带的结构化快照。它不能替代业务表，但可以保存排查时最常用的少量上下文，例如状态、风险分数、命中数量或版本号。

程序员实现时要克制：payload 不是把整个客户资料、证件照片、完整地址或敏感备注塞进日志。日志越集中，越容易成为高敏感数据集合。当前实验只做教学版 JSON 脱敏，把 `full_name`、`address`、`date_of_birth`、`identification_number` 等字段替换成 `[redacted]`。

### subject timeline

Subject timeline 是围绕一个主体生成的事件时间线。主体可以是客户、交易、账户、审核案例或策略版本。

例如一个客户的时间线可能是：

```text
09:00 kyc_application.saved
09:01 kyc_decision.saved
09:02 kyc_review_case.created
09:30 kyc_review_case.request_more_info
10:01 risk_decision.saved
10:02 review_case.created
10:20 review_case.approved
```

这类时间线对合规、运营和工程排查都很有用。它能把多个系统分散的状态变化串成一个故事：先开户、后补件、再交易审核。

## 为什么金融系统需要它

金融系统不仅要做出正确决策，还要能解释决策。没有 audit trail，团队会遇到几个问题：

- 只能看到当前状态，看不到状态变化过程。
- 不知道某个审核结论是谁做出的。
- 不知道当时使用的是哪个规则版本、名单版本或策略版本。
- 无法把 KYC、风控、人工复核和报表导出串起来。
- 出现争议、事故或内部复盘时，很难还原事实。

FFIEC IT Examination Handbook 的资料把审计、治理、风险管理和控制有效性放在金融机构 IT 管理语境下讨论；FATF Recommendations 也把客户尽调和记录留存放在 AML/CFT 标准框架中。当前实验不实现这些框架的具体要求，只借它们说明：金融系统里的日志不是可有可无的开发辅助，而是治理和复核能力的一部分。

## 程序员实现时会遇到什么问题

### 1. 审计表和业务状态表不能互相替代

状态表回答“现在是什么”，审计表回答“怎么变成这样”。

例如审核案例当前状态是 `approved`，但审计事件需要保留：

```text
review_case.created
review_case.approved
```

如果只保存当前状态，就丢失了动作历史；如果只保存事件，又会让在线查询当前状态变复杂。真实系统通常两者都需要。

### 2. 时间必须明确

审计事件必须有 `occurred_at`。当前仓库统一使用带时区的 `datetime`，避免跨地区团队和报表出现歧义。

### 3. 日志也需要数据保护

审计日志经常包含客户、交易、审核理由和风险信号。如果没有访问控制、脱敏和留存策略，日志本身会变成风险。

当前实验只做最小脱敏，不实现真实权限、加密、密钥管理、数据分类和删除流程。

### 4. 跨系统时间线需要链接关系

风控事件按 `request_id` 记录，KYC 事件按 `customer_id` 记录。要做客户时间线，系统需要知道哪些交易属于哪个客户。当前实验用显式 `aggregate_links` 传入链接关系，先把问题讲清楚。

## 当前实验数据结构

统一审计事件：

```text
ComplianceAuditEvent
source_system
event_id
event_type
aggregate_type
aggregate_id
actor
reason
payload
occurred_at
```

筛选条件：

```text
AuditEventFilter
source_system
actor
event_type
event_type_prefix
aggregate_type
aggregate_id
occurred_from
occurred_to
```

主体时间线：

```text
AuditTimeline
subject_type
subject_id
events
```

汇总结果：

```text
AuditSummary
total_events
source_system_counts
event_type_counts
actor_counts
```

访问审计事件：

```text
AuditAccessEvent
event_type
actor
permission
target
outcome
occurred_at
reason
```

访问审计持久化表：

```text
audit_access_events
event_id
event_type
actor
permission
target
outcome
occurred_at
reason
```

导出审批：

```text
AuditExportApproval
approved_by
approved_at
reason
```

留存策略：

```text
AuditRetentionPolicy
policy_id
event_type_prefix
retention_days
archive_after_days
legal_hold
```

留存决策：

```text
AuditRetentionDecision
event
policy
status
age_days
archive_due_at
delete_due_at
reason
```

留存报告：

```text
AuditRetentionReport
generated_at
decisions
status_counts
```

导出文件：

```text
labs/compliance-audit/reports/compliance_audit_events.csv
labs/compliance-audit/reports/compliance_audit_summary.csv
labs/compliance-audit/reports/compliance_audit_timeline.csv
labs/compliance-audit/reports/compliance_audit_report.html
labs/compliance-audit/reports/access_anomaly_findings.csv
labs/compliance-audit/reports/access_anomaly_report.html
labs/compliance-audit/reports/audit_retention_decisions.csv
labs/compliance-audit/reports/audit_retention_report.html
labs/compliance-audit/reports/access_investigation_cases.csv
labs/compliance-audit/reports/access_investigation_report.html
```

## 当前简化了什么

当前实验刻意简化：

- 不实现真实合规管理系统。
- 只实现教学版角色权限和导出审批，不接真实身份认证、企业 IAM、复杂审批矩阵、工单系统和组织架构。
- 不实现防篡改日志、签名、WORM 存储或集中日志平台。
- 不实现真实记录留存期限、删除冻结、法律保全和监管报送；当前 retention policy 只使用教学样例天数。
- 不接 SIEM、数据仓库或对象存储。
- 不自动发现客户和交易关系，只通过 `aggregate_links` 显式传入。
- 只做教学版 JSON payload 脱敏，不保证覆盖所有敏感字段。
- 报表导出只生成本地 CSV 和 HTML，并只检查教学版 `export_audit_report` 与可选 `approve_audit_export`；不实现下载审计、工单审批、归档保留和监管模板。
- 留存报告只计算和导出状态，不真的删除、归档、加密迁移或冻结任何文件/数据库记录。
- 访问审计事件可以写入教学版 SQLite 表，但不接集中日志平台、安全监控、签名、防篡改存储或长期留存策略。
- 访问异常检测和报告只做教学版规则匹配与本地文件导出，不接真实告警、工单、SIEM、身份上下文、设备指纹或 IP 情报。
- 访问异常调查工单只做教学版状态机、SQLite 持久化、本地报告导出和内存版处理动作审计事件，不接真实工单系统、SLA、通知、升级路径、证据附件、权限模型或完整审计历史。
- 不把任何样例日志解释为法律、监管、税务、会计或合规建议。

## 当前实验新增了什么

- `labs/compliance-audit/compliance_audit.py`
- `labs/compliance-audit/compliance_access_monitoring.py`
- `labs/compliance-audit/compliance_access_report_export.py`
- `labs/compliance-audit/compliance_audit_export.py`
- `labs/compliance-audit/compliance_investigation_cases.py`
- `labs/compliance-audit/compliance_investigation_report_export.py`
- `labs/compliance-audit/compliance_retention.py`
- `labs/compliance-audit/compliance_retention_export.py`
- `labs/compliance-audit/demo.py`
- `labs/compliance-audit/README.md`
- `labs/compliance-audit/sqlite_access_audit_store.py`
- `labs/compliance-audit/sqlite_investigation_case_store.py`
- `labs/compliance-audit/test_compliance_audit.py`
- `labs/compliance-audit/test_compliance_access_monitoring.py`
- `labs/compliance-audit/test_compliance_access_report_export.py`
- `labs/compliance-audit/test_compliance_audit_export.py`
- `labs/compliance-audit/test_compliance_investigation_cases.py`
- `labs/compliance-audit/test_compliance_investigation_report_export.py`
- `labs/compliance-audit/test_compliance_retention.py`
- `labs/compliance-audit/test_compliance_retention_export.py`
- `labs/compliance-audit/test_sqlite_access_audit_store.py`
- `labs/compliance-audit/test_sqlite_investigation_case_store.py`
- `ComplianceAuditEvent`
- `AuditEventFilter`
- `AuditTimeline`
- `AuditSummary`
- `AuditUser`
- `AuditAccessEvent`
- `AuditAccessRecorder`
- `AuditExportApproval`
- `AuditRetentionPolicy`
- `AuditRetentionDecision`
- `AuditRetentionReport`
- `AccessMonitoringRule`
- `AccessAnomalyFinding`
- `AccessAnomalyInvestigationCase`
- `AccessAnomalyInvestigationService`
- `ComplianceAuditError`
- `ComplianceAuditExportPaths`
- `AccessAnomalyExportPaths`
- `AuditRetentionExportPaths`
- `InvestigationCaseExportPaths`
- `SQLiteAccessAuditStore`
- `SQLiteInvestigationCaseStore`
- `collect_audit_events`
- `filter_audit_events`
- `build_audit_timeline`
- `summarize_audit_events`
- `redact_payload`
- `permissions_for_user`
- `can_user`
- `authorize_user`
- `authorize_user_with_audit`
- `validate_export_approval`
- `visible_events_for_user`
- `export_compliance_audit_report`
- `export_access_anomaly_report`
- `export_audit_retention_report`
- `export_investigation_case_report`
- `detect_access_anomalies`
- `default_access_monitoring_rules`
- `investigation_case_id`
- `save_case`
- `get_case`
- `open_cases`
- `query_cases`
- `build_retention_report`
- `evaluate_retention`
- `save_event`
- `save_events`
- `access_events`
- `query_access_events`
- `view_audit_events`
- `view_audit_payload`
- `export_audit_report`
- `approve_audit_export`
- `active`
- `archive_due`
- `delete_due`
- `held`
- `repeated_denied_access`
- `unauthorized_export_attempt`
- `repeated_payload_view`
- `open`
- `investigating`
- `resolved`
- `false_positive`
- `access_investigation_case.created`
- `access_investigation_case.started`
- `access_investigation_case.resolved`
- `access_investigation_case.false_positive`
- `access_investigation_cases.csv`
- `access_investigation_report.html`

运行 demo：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\compliance-audit\demo.py
```

运行测试：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\compliance-audit
```

## 资料来源

- FFIEC, IT Examination Handbook InfoBase: https://www.ffiec.gov/node/33
  - 访问日期：2026-05-08。
  - 支持结论：FFIEC 维护 IT Examination Handbook 资料，用于金融机构 IT 检查相关主题的参考和培训。
- FFIEC, Information Security Booklet: https://www.ffiec.gov/press/pdf/ffiec_it_handbook_information_security_booklet.pdf
  - 访问日期：2026-05-08。
  - 支持结论：信息安全审计应评估政策、标准、程序、控制有效性和整改跟踪；本实验只借此说明 audit trail 与控制复核相关。
- FDIC, Updated FFIEC IT Examination Handbook - Architecture, Infrastructure, and Operations Booklet: https://www.fdic.gov/news/financial-institution-letters/2021/fil21047.html
  - 访问日期：2026-05-08。
  - 支持结论：AIO booklet 用于帮助评估 IT 架构、基础设施、运营、治理和风险管理。
- FATF, The FATF Recommendations: https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html
  - 页面显示 Recommendations as amended October 2025。
  - 访问日期：2026-05-08。
  - 支持结论：FATF Recommendations 是 AML/CFT/CPF 的国际标准框架，并包含客户尽调和记录保存相关主题；本实验不实现任何具体司法辖区要求。
