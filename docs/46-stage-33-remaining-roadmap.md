# 阶段 33：剩余章节路线图与平台差距总结

最后更新：2026-06-10

阶段 33 不改业务代码，目标是把阶段 8 到阶段 32 已经形成的综合平台重新盘点一次：当前平台能跑哪些流程，和一个更完整的教学版 FinTech 平台相比还差哪些大块，以及后续大概还需要几个阶段或章节。

本阶段继续遵守“不要拆太多细碎文档”的约定，把当前能力、差距、剩余章节和下一步建议合并在这一篇文档里。

## 当前平台已经能跑的流程

当前 `labs/fintech-platform/` 已经不是单点实验，而是一个可运行的教学版平台。它能覆盖以下流程。

### 主业务流程

```text
API request
-> PlatformApiService
-> FinTechPlatform.process_payment()
-> KYC/AML decision
-> payment order
-> risk decision
-> ledger posting
-> customer audit timeline
-> SQLitePlatformStore
```

这条链路回答：一个外部支付请求如何变成业务状态、账本记录和审计证据。

### 异步任务流程

```text
POST /platform/async-payment-runs
-> accepted
-> PlatformAsyncWorker
-> processing
-> completed / failed
-> final platform result
```

这条链路回答：接口先返回 `202 Accepted` 后，后台 worker 如何独立推进业务，以及 async run 状态为什么不能等同于最终支付状态。

### 失败重试和审批流程

```text
failed async run
-> retry approval request
-> operation approval pending
-> approve / reject / cancel / expire
-> retry execution
-> failed -> accepted
```

这条链路回答：高影响操作为什么要拆成申请、审批和执行，并分别留下 operation approval record 与 access audit。

### 报表和对账流程

```text
PlatformRunSnapshot
PlatformAsyncRun
ledger audit payload
operation approval record
access audit
-> operations report
-> approval report
-> ledger reconciliation report
```

这条链路回答：运营和合规人员如何横向检查任务、业务结果、账本入账、审批记录和访问审计是否互相解释得通。

### Console 观察和处理流程

```text
FinTech Platform Console
-> status filters
-> payment / async / approval rows
-> pending approval forms
-> approval detail lifecycle timeline
-> async run detail
-> payment run detail
-> ledger reconciliation context
```

这条链路回答：运营人员如何从列表进入详情，查看 payment run、async run、approval lifecycle 和 ledger reconciliation context。

### 访问异常和调查工单流程

```text
API / report access audit
-> anomaly finding
-> investigation case
-> open / investigating / resolved / false_positive
-> case action audit
```

这条链路回答：访问审计如何从日志变成可处理的调查工单。

## 和完整版平台的主要差距

这里的“完整版平台”仍指教学目标下的较完整平台，不等于生产级银行、支付机构或券商系统。

### 1. 身份、权限和会话仍是教学版

当前 API 和 console 主要依赖请求体或 header 里的 actor 字段，适合学习 access audit，但不是真实认证。

还缺：

- login / session / token。
- role-based access control。
- route-level permission policy。
- console form 的 CSRF 防护。
- 敏感字段按角色脱敏。
- 操作人与审批人的身份来源校验。

### 2. 外部支付、清算和结算仍是模拟

当前平台能解释 payment order、risk decision 和 ledger posting，但没有真实 payment provider、银行流水、清算文件或结算批次。

还缺：

- provider request / response 的适配层。
- webhook event 去重和状态推进。
- settlement batch。
- external statement。
- 内部账本和外部账单的差异对账。
- 手续费、退款、失败回调、部分成功等复杂状态。

### 3. 数据一致性边界还没有生产化

当前 SQLite 存储和教学版 worker 已能演示幂等、状态查询和 retry，但还没有深入到并发、锁、迁移和恢复。

还缺：

- 平台级 transaction / outbox 边界。
- worker claim / lease / timeout。
- 并发审批和并发 retry 的冲突处理。
- 数据库 schema migration。
- backup / restore 和失败恢复演练。
- 更清晰的 account / balance / ledger entry 查询模型。

### 4. 运营工作流还比较轻

当前 console 已经可以查看、筛选和处理 pending approval，但仍是最小 HTML 页面。

还缺：

- 日期范围、actor、operation type、severity 等筛选。
- 更明确的风险提示和返回入口。
- 工单 comment、assignee、SLA、priority、claim / release。
- 批量查看和分页控件。
- 操作结果的用户反馈和错误解释。
- 运营 runbook。

### 5. 合规证据管理仍是教学抽象

当前已有 audit timeline、access audit、retention 示例、anomaly finding 和 investigation case，但没有把真实监管规则写成结论。

还缺：

- 证据包 evidence package。
- export approval 和 legal hold 的更完整生命周期。
- 审计事件查询和导出治理。
- KYC/AML、sanctions、retention 等规则的官方来源查证。
- 数据最小化、脱敏和访问理由的统一策略。

如果后续进入真实监管、制裁名单、KYC/AML 规则或留存期限，必须重新查证官方或专业来源，不能凭当前教学样例外推。

### 6. 工程交付还不是可部署产品

当前 demo、测试和 FastAPI app 能帮助学习，但还没有部署、配置、监控和运维边界。

还缺：

- 环境配置和 secret 管理。
- structured logging。
- metrics / health / readiness。
- API 文档整理和错误码约定。
- 集成测试场景矩阵。
- 本地开发、测试、演示和部署说明。
- 最终验收清单。

## 建议剩余章节数量

从当前状态到一个更完整的教学版平台，建议还剩：

```text
6 个建设章节 + 1 个最终验收章节
```

也就是大约 7 个阶段或大章节。

如果后续继续把每个章节拆成多个小阶段，实际阶段号可能会超过 7 个；但从学习主线看，不建议再把每个小控件都拆成独立文档。

## 建议章节路线

### 阶段 34：运营 Console 和工作流补强

目标：

- 增加日期范围、actor、operation type 或 severity 筛选。
- 给高影响操作增加更明确的风险提示。
- 给详情页增加返回 console 的路径。
- 保持最小 HTML，不引入复杂前端框架。

为什么先做它：

- 当前 console 已经能处理 approval，但运营检索能力还弱。
- 这个阶段能直接提升已有平台的可用性，风险低。

### 阶段 35：身份、权限和表单安全边界

目标：

- 设计教学版 user / role / permission。
- 把 actor 从“请求自报字段”升级为更接近真实系统的身份上下文。
- 说明 route-level permission、CSRF、敏感字段脱敏和 self-approval 校验的边界。

为什么需要它：

- 当前 access audit 已经有了，但身份来源还不可信。
- 审批和操作动作越多，权限边界越重要。

### 阶段 36：一致性、并发和恢复

目标：

- 梳理 platform store、async run store、approval store 的事务边界。
- 增加 worker claim / lease / timeout 的教学实现或设计。
- 增加并发 approve / retry 的冲突测试。
- 规划 schema migration、backup / restore 和失败恢复。

为什么需要它：

- 金融系统的难点不只是功能跑通，而是失败时不能重复入账、不能丢审计、不能产生互相矛盾的状态。

### 阶段 37：外部支付、清算、结算和真实对账模型

目标：

- 增加教学版 payment provider adapter。
- 增加 webhook event 去重和状态推进。
- 增加 settlement batch / external statement 样例。
- 把 ledger reconciliation 从内部 audit payload 扩展到内部账本 vs 外部账单。

为什么需要它：

- 当前 ledger reconciliation 只能解释平台内部记录。
- 更完整的支付平台需要学习清算、结算和外部账单对账。

### 阶段 38：合规证据、调查工单和留存治理

目标：

- 增强 investigation case 的 comment、assignee、priority、SLA 和证据包。
- 把 audit export、legal hold、retention decision 和 approval record 串起来。
- 对任何监管时效性内容先查证官方来源。

为什么需要它：

- 当前合规链路已经有 finding 和 case，但还缺“如何把证据组织成可审查材料”的视角。

### 阶段 39：可运行交付、观测和测试矩阵

目标：

- 整理本地运行、测试、demo、API 文档和错误码。
- 增加 structured logging、metrics、health / readiness 的教学边界。
- 汇总端到端测试矩阵。
- 规划环境配置和部署注意事项。

为什么需要它：

- 工程作品不仅要能写，还要能交给别人运行、验证和复盘。

### 阶段 40：最终验收和学习作品集总结

目标：

- 总结从账本、支付、风控、KYC/AML、合规审计到综合平台的完整学习路径。
- 给出最终平台能力地图。
- 给出验收清单、已知边界和后续可选扩展。
- 整理 README / docs / labs 的最终阅读入口。

为什么需要它：

- 阶段 40 可以作为当前学习项目的一个完整里程碑，而不是继续无限加功能。

## 下一步建议

阶段 34 建议优先做运营 Console 和工作流补强，范围保持小：

1. 给 console 增加 `actor` 和日期范围筛选。
2. 给 pending approval 操作区域增加更明确的风险提示。
3. 给 detail views 增加返回 console 的链接。
4. 不新增数据库表，不引入前端框架，不处理真实登录。

这个顺序比直接进入身份系统更稳，因为它先把已有运营页面梳理清楚；之后再做身份和权限时，哪些页面、动作和角色需要保护会更明确。

## 本阶段验证

阶段 33 只更新文档和进度记录，不改业务代码、不新增测试。

已更新：

```text
docs/46-stage-33-remaining-roadmap.md
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
```
