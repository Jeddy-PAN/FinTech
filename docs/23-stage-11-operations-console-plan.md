# 阶段 11：运营控制台增强设计与收尾总结

最后更新：2026-06-04

阶段 11 承接阶段 9 的最小 HTML console 和阶段 10 的 async run / worker 能力。当前平台已经可以通过 API 创建同步 payment run、创建 async run、触发教学版 worker、查询 API access events、生成 API access anomaly finding，并把 finding 转成 investigation case。

阶段 11 的问题是：如果你是平台运营、风控或合规人员，如何在一个只读控制台里快速看清平台当前状态、异常线索和需要处理的工单？

这不是另起一个前端项目，而是在 `labs/fintech-platform/platform_api_app.py` 现有最小 console 上做增强。阶段 11 仍然保持服务端渲染 HTML，不引入 React/Vue、不引入登录系统、不做真实 IAM。

## 为什么金融平台需要运营控制台

金融系统不只需要 API，还需要可观察的运营界面。原因包括：

- 业务团队需要看 payment run 是否成功、被 KYC 拦截、被风控拦截或进入人工复核。
- 技术和运营团队需要看 async run 是否堆积、失败或反复重试。
- 合规人员需要看 API access anomaly finding 和 investigation case。
- 审计人员需要看“谁查看了什么”和“谁触发了什么操作”。
- 排障时需要把任务状态、业务状态、访问审计和工单状态放在同一个上下文里。

阶段 11 的核心直觉是：

```text
运营控制台不是装饰页面，而是系统可观察性的一部分。
```

## 当前控制台能力

当前 FastAPI 已经提供：

```text
GET /
GET /platform
GET /platform/view
```

页面标题为 `FinTech Platform Console`，阶段 11 收尾时已经展示：

- payment runs summary。
- recent payment runs。
- async run summary。
- recent async runs。
- failed async runs。
- API access anomalies。
- investigation cases。
- recent API access events。

访问控制台本身会记录 `view_platform_console` access audit event。

Failed Async Runs 区域还提供一个教学版 retry form。它只允许运营人员把 failed async run 重新放回 `accepted` 队列，不直接触发 worker，也不代表真实生产审批系统。

## 阶段 11 目标

阶段 11 目标是把控制台从“最小总览页”增强为“更适合运营排查的运营页面”。

收尾时仍然只做一个页面，但把信息结构升级为：

```text
Operational summary
-> Payment runs
-> Async runs
-> Failed async run retry
-> API access anomalies
-> Investigation cases
-> Recent API access events
```

重点不是视觉复杂度，而是让页面能回答这些问题：

1. 当前平台有多少 payment runs？多少完成、多少被拦截、多少需要人工复核？
2. 当前有多少 async runs？多少 accepted、processing、completed、failed？
3. 哪些 async runs 失败了，失败原因是什么？
4. 最近有哪些 API access anomaly findings？
5. 当前有哪些 open / investigating investigation cases？
6. 最近谁访问、查询或触发了哪些接口？
7. 一个 failed async run 是否能经过显式 actor、reason 和 confirmation 后重新进入 `accepted`？

## 建议新增页面区域

### 1. Operational Summary

汇总卡片建议包括：

```text
Payment runs
Completed payment runs
Risk review payment runs
Async runs
Accepted async runs
Failed async runs
API access events
API access anomalies
Investigation cases
Open cases
```

这些指标都来自当前已有 SQLite stores，不新增业务数据库。

### 2. Async Runs

新增 async run 表格，建议字段：

```text
run_id
status
attempt_count
max_attempts
last_error
created_at
updated_at
completed_at
```

如果 async run 已完成，可以显示最终 platform status：

```text
platform_status
payment_order_id
```

这能帮助学习者理解：

```text
async run status != platform business status
```

### 3. Failed Async Runs

如果存在 failed async runs，可以单独展示一个小表格：

```text
run_id
attempt_count
max_attempts
last_error
updated_at
```

阶段 11C 已在该表格中加入原生 HTML retry form。表单要求提交：

```text
actor
reason
confirmation = retry_failed_async_run
```

表单提交到：

```text
POST /platform/async-payment-runs/{run_id}/retry-form
```

这个 form endpoint 只是浏览器表单适配层，内部复用同一套 retry 校验和 API access audit。成功后 run 回到 `accepted`，不直接触发 worker；后续仍由 `POST /platform/async-worker/process-next` 或 `process-pending` 推进。

### 4. Payment Runs

保留 recent payment runs，但可以增强字段：

```text
run_id
customer_id
status
kyc_status
payment_order_status
risk_status
risk_review_case_id
ledger_transaction_id
created_at
```

阶段 11 第一版仍然只展示最近若干条，不做分页。

### 5. API Access Events

保留 recent API access events，用来观察：

- 谁创建了 payment run。
- 谁创建或查询 async run。
- 谁触发了教学版 worker。
- 谁查看了 console。
- 谁查询了不存在的 run。

### 6. Investigation Cases

保留 investigation cases，但优先展示未关闭工单：

```text
case_id
status
actor
opened_by
assigned_to
resolution_reason
created_at
```

阶段 11 第一版不在页面里流转工单状态。工单 start / resolve / false-positive 仍然通过已有 API endpoint 完成。

## 数据来源

阶段 11 继续复用当前 stores：

```text
SQLitePlatformStore
SQLitePlatformAsyncRunStore
SQLiteAccessAuditStore
SQLiteInvestigationCaseStore
```

数据关系：

```text
platform_runs
-> final business result

platform_async_runs
-> async task status and retry metadata

audit_access_events
-> API and console access audit

access_investigation_cases
-> anomaly investigation workflow
```

控制台只读读取这些数据，不修改状态。

## API / 路由设计

阶段 11 继续使用现有页面路由：

```text
GET /
GET /platform
GET /platform/view
```

不新增前端项目，不新增静态资源构建流程。

阶段 11B/11C 新增 retry 相关路由：

```text
POST /platform/async-payment-runs/{run_id}/retry
POST /platform/async-payment-runs/{run_id}/retry-form
```

JSON endpoint 面向 API 调用；form endpoint 面向浏览器原生表单。两者共享同一套 retry 校验：

- `actor` 必填。
- `reason` 必填。
- `confirmation` 必须等于 `retry_failed_async_run`。
- 只允许 `failed -> accepted`。
- 成功和失败都写入 `retry_platform_async_run` access audit。
- retry 不直接执行业务处理。

可以新增内部 helper 函数：

```text
_async_runs(app)
_latest_async_runs(...)
_count_async_status(...)
_failed_async_runs(...)
```

并扩展 `_render_platform_console_html(app)`。

## 验收标准

阶段 11 收尾时，应能观察到：

1. Console summary 包含 async run 数量。
2. Console summary 包含 accepted / failed async run 数量。
3. Console 页面展示 recent async runs。
4. Completed async run 可以显示最终 platform status。
5. Failed async run 可以显示 last_error。
6. Console 仍然展示 payment runs、API access anomalies、investigation cases 和 recent API access events。
7. 访问 console 仍然写入 `view_platform_console` access audit。
8. 空状态页面仍然可读，不因没有 async runs 报错。
9. HTML 仍然转义用户可控字段。
10. Failed async run 可以通过 JSON retry API 重新进入 `accepted`。
11. Failed async run 可以通过 console retry form 重新进入 `accepted`。
12. retry 必须带 actor、reason 和 confirmation。
13. retry 成功和失败都能在 API access audit 中查询到。
14. retry 不直接触发 worker。
15. `labs/fintech-platform` pytest 通过。
16. 全量 `labs` pytest 通过。

## 当前不做的事

阶段 11 仍然是教学版运营控制台，不实现：

- 登录、会话、OAuth、JWT 或企业 IAM。
- 工单状态流转的页面按钮，例如 start / resolve / false-positive。
- 页面内导出报表、下载附件或审批流。
- retry 的二人审批、SLA、通知或真实权限系统。
- 真实分页、排序、搜索和复杂筛选。
- 前端框架、构建工具、CSS 框架或组件库。
- WebSocket、Server-Sent Events 或实时刷新。
- 生产级可观测性系统，例如 Prometheus、Grafana、OpenTelemetry。

这些不是目标缺失，而是为了先把“金融平台运营视图应该看什么”讲清楚。

## 推荐实现顺序

1. 已完成：扩展 console 数据读取，加入 `SQLitePlatformAsyncRunStore`。
2. 已完成：在 summary 中加入 async run 指标。
3. 已完成：增加 recent async runs 表格。
4. 已完成：增加 failed async runs 空状态或表格。
5. 已完成：补充 failed async run demo 样例。
6. 已完成：新增 `failed -> accepted` retry API。
7. 已完成：在 Failed Async Runs 区域加入 retry form。
8. 已完成：调整测试覆盖 async run 展示、failed sample、retry API 和 retry form。
9. 已完成：更新 README 与学习进度。

## 当前实现进度

当前已经完成阶段 11 主线：现有 `FinTech Platform Console` 已接入 `SQLitePlatformAsyncRunStore`，summary 会展示 async run 数量、accepted async runs 和 failed async runs；页面会展示 recent async runs 和 failed async runs；completed async run 会关联显示最终 platform status 和 payment order id。对应 console 测试已经覆盖 async run 展示、空状态和 failed async run 展示。

demo 现在也会通过真实 API 流程构造一个 request fingerprint 冲突导致的 failed async run，并输出 `Failed async run sample for console`，用于观察 `attempt_count`、`last_error` 和 console 的 failed async run 表格。

阶段 11B 已新增 `POST /platform/async-payment-runs/{run_id}/retry`。该 endpoint 只允许把 `failed` async run 改回 `accepted`，要求 actor、reason 和 `retry_failed_async_run` confirmation；成功和失败都会写入 API access audit；retry 后由现有 worker endpoint 继续处理。

阶段 11C 已把 retry 接入 Failed Async Runs 区域的原生 HTML form。表单 endpoint `POST /platform/async-payment-runs/{run_id}/retry-form` 不重复实现业务规则，只作为浏览器适配层复用 JSON retry endpoint 的核心校验、状态转换和 access audit。

## 阶段 11 收尾总结

阶段 11 从一个最小只读 console，推进到“可观察 + 最小人工操作”的教学版运营控制台。它把阶段 9 的 API access audit、阶段 10 的 async run / worker，以及阶段 8 的最终 platform run 快照放到同一个页面里，帮助学习者理解金融后台系统常见的运营视角：

```text
外部请求
-> async run 状态
-> worker 处理结果
-> 最终业务状态
-> API access audit
-> anomaly finding
-> investigation case
```

本阶段最重要的工程结论：

1. 运营控制台不是装饰页面，而是系统可观察性的一部分。
2. async run status 和 platform business status 必须分开看；`completed` 任务不等于所有业务场景都成功，`failed` 任务也需要保留 request fingerprint、attempt count 和 last error。
3. 人工 retry 不能只是“再跑一次”；它需要状态约束、显式操作人、原因、确认文本和审计记录。
4. retry 只应把任务重新放回队列，不应在同一个 HTTP 操作里直接执行业务处理；这样能保持操作边界清晰。
5. 成功和失败的后台操作都要写入 audit trail，否则排障和复核只能依赖口头解释。
6. 教学阶段可以用原生 HTML form 讲清楚后台操作边界，不需要过早引入前端框架。

## 验证记录

截至 2026-06-04，阶段 11 收尾前已完成以下验证：

```text
test_platform_api_app.py: 20 passed
labs/fintech-platform: 91 passed
labs: 336 passed
```

这些测试覆盖 console 页面渲染、空状态、async run 展示、failed async run 展示、retry API、retry form、access audit、worker 处理和既有平台能力。

## 文档整理约定

由于阶段 11 后期已经暴露出 docs 文件偏碎的问题，后续采用更保守的文档策略：

- 小功能优先更新对应实验目录 README 和 `LEARNING_PROGRESS.md`。
- 同一阶段内的小增量优先合并到现有阶段文档，不再为每个子步骤新增单独 docs 文件。
- 只有进入新阶段、形成跨模块设计或需要长期保留的验收总结时，才考虑新增 docs 文件。
- 已经存在的历史文档不在本阶段强行迁移，避免制造无关改动。

## 后续候选方向

阶段 11 可以收尾。下一步建议不要继续堆 console 小功能，而是选择一个更明确的新主题：

1. 阶段 12：操作审计与审批边界。围绕 retry、工单流转、报表导出这类高影响操作，设计二人审批、职责分离、操作原因、审计事件和撤销边界。
2. 阶段 12：运行报告与对账视角。把 async run、platform result、ledger posting 和 access audit 做成更系统的日终检查或异常清单。
3. 文档整理阶段：先压缩 docs 索引和阶段文档说明，把学习路径从“文件列表”改成“主题路线”，降低后续阅读负担。
