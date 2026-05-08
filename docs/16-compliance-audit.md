# 合规与审计：日志、时间线、脱敏和记录留存

最后更新：2026-05-08

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
- 职责分离：segregation of duties
- 发起人与复核人：maker/checker
- 审批：approval

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

导出文件：

```text
labs/compliance-audit/reports/compliance_audit_events.csv
labs/compliance-audit/reports/compliance_audit_summary.csv
labs/compliance-audit/reports/compliance_audit_timeline.csv
labs/compliance-audit/reports/compliance_audit_report.html
```

## 当前简化了什么

当前实验刻意简化：

- 不实现真实合规管理系统。
- 只实现教学版角色权限和导出审批，不接真实身份认证、企业 IAM、复杂审批矩阵、工单系统和组织架构。
- 不实现防篡改日志、签名、WORM 存储或集中日志平台。
- 不实现真实记录留存期限、删除冻结、法律保全和监管报送。
- 不接 SIEM、数据仓库或对象存储。
- 不自动发现客户和交易关系，只通过 `aggregate_links` 显式传入。
- 只做教学版 JSON payload 脱敏，不保证覆盖所有敏感字段。
- 报表导出只生成本地 CSV 和 HTML，并只检查教学版 `export_audit_report` 与可选 `approve_audit_export`；不实现下载审计、工单审批、归档保留和监管模板。
- 访问审计事件可以写入教学版 SQLite 表，但不接集中日志平台、安全监控、签名、防篡改存储或长期留存策略。
- 不把任何样例日志解释为法律、监管、税务、会计或合规建议。

## 当前实验新增了什么

- `labs/compliance-audit/compliance_audit.py`
- `labs/compliance-audit/compliance_audit_export.py`
- `labs/compliance-audit/demo.py`
- `labs/compliance-audit/README.md`
- `labs/compliance-audit/sqlite_access_audit_store.py`
- `labs/compliance-audit/test_compliance_audit.py`
- `labs/compliance-audit/test_compliance_audit_export.py`
- `labs/compliance-audit/test_sqlite_access_audit_store.py`
- `ComplianceAuditEvent`
- `AuditEventFilter`
- `AuditTimeline`
- `AuditSummary`
- `AuditUser`
- `AuditAccessEvent`
- `AuditAccessRecorder`
- `AuditExportApproval`
- `ComplianceAuditError`
- `ComplianceAuditExportPaths`
- `SQLiteAccessAuditStore`
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
- `save_event`
- `save_events`
- `access_events`
- `query_access_events`
- `view_audit_events`
- `view_audit_payload`
- `export_audit_report`
- `approve_audit_export`

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
