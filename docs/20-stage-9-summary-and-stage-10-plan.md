# 阶段 9 总结与阶段 10 路线

最后更新：2026-05-19

这份文档是阶段 9 的收尾材料。阶段 9 的重点不是新增一套金融业务，而是把阶段 8 已经跑通的端到端综合平台放到 API 边界后面，观察外部请求、幂等、状态查询、访问审计、异常检测、调查工单和最小查看页如何协同。

## 阶段 9 做了什么

阶段 9 的主线可以概括为：

```text
external request
-> API request model
-> PlatformApiService
-> FinTechPlatform.process_payment()
-> SQLitePlatformStore
-> HTTP response
-> API access audit
-> API access anomaly finding
-> API investigation case
-> read-only console
```

这条链路让阶段 8 的脚本式学习平台变成了一个可以通过 HTTP 观察的教学版 API service。它完成了以下事情：

- 把外部 payment run 请求转换成平台内部的 `PlatformPaymentRequest`。
- 用 `run_id` 和 request fingerprint 做教学版幂等校验，区分安全重放和参数冲突。
- 用 FastAPI 暴露创建、查询和筛选 payment runs 的 HTTP 接口。
- 把 API 调用本身写入 `SQLiteAccessAuditStore`，形成 access audit trail。
- 从 API access audit 中检测 repeated denied access finding。
- 把 API access anomaly finding 转成 investigation case，并支持查询和状态流转。
- 增加最小前端查看页，把 payment runs、API access anomalies、investigation cases 和 recent API access events 放到一个只读页面里。

## 已完成资产

阶段 9 新增和扩展的主要文件包括：

```text
docs/19-stage-9-platform-api-plan.md
docs/20-stage-9-summary-and-stage-10-plan.md
labs/fintech-platform/platform_api_service.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/platform_api_access_anomaly_report.py
labs/fintech-platform/platform_api_investigation_cases.py
labs/fintech-platform/test_platform_api_service.py
labs/fintech-platform/test_platform_api_app.py
labs/fintech-platform/test_platform_api_access_anomaly_report.py
labs/fintech-platform/test_platform_api_investigation_cases.py
labs/fintech-platform/test_platform_api_investigation_endpoints.py
```

这些文件共同支持：

- API service 边界。
- FastAPI 路由层。
- payment run 创建、查询和列表筛选。
- 教学版 `run_id` 幂等与 request fingerprint 冲突检测。
- API access audit 持久化与查询。
- API access anomaly detection。
- API investigation case 创建、查询和状态流转。
- 最小只读 HTML console。

## 当前 API 能力

当前 FastAPI 应用支持：

```text
GET  /
GET  /platform
GET  /platform/view
GET  /health
POST /platform/payment-runs
GET  /platform/payment-runs/{run_id}
GET  /platform/payment-runs?status=completed&customer_id=cust_001
GET  /platform/api-access-events?permission=create_platform_payment_run
GET  /platform/api-access-anomaly-findings
POST /platform/api-access-investigation-cases
GET  /platform/api-access-investigation-cases?status=open&actor=api_viewer_404
GET  /platform/api-access-investigation-cases/{case_id}
PATCH /platform/api-access-investigation-cases/{case_id}/start
PATCH /platform/api-access-investigation-cases/{case_id}/resolve
PATCH /platform/api-access-investigation-cases/{case_id}/false-positive
```

其中 `/`、`/platform` 和 `/platform/view` 返回最小 HTML 查看页；其他接口返回 JSON。查询类接口可以通过 `x-actor-id` 请求头传入教学版 actor；没有传入时使用 `anonymous_api_client`。

## 学到的工程结论

1. API 层不应直接吞掉领域边界。

   `platform_api_app.py` 只负责 HTTP 请求、响应和状态码映射；真正的业务入口放在 `PlatformApiService`，再由它调用 `FinTechPlatform`。这能避免路由函数变成业务流程本身。

2. 幂等不能只看一个 key。

   `run_id` 能识别是否重复提交，但不能证明两次请求内容一致。request fingerprint 用来判断同一个 `run_id` 下的参数是否变化，避免把冲突请求误当成安全重放。

3. HTTP 状态和内部状态不是一回事。

   API 返回 `201` 表示请求被服务接受并产生响应，不等于支付一定成功。真正的业务状态仍然要看 platform status、payment order status、risk status 和 ledger transaction。

4. 查询接口本身也要被审计。

   访问 health、查询 run、列出 run、查看工单和打开 console 都会形成 access audit event。金融系统里“谁查看了什么”往往和“谁修改了什么”一样重要。

5. finding 不是结论，只是线索。

   API access anomaly finding 只说明出现了可疑访问模式，例如 repeated denied access。它必须进入 investigation case，才有后续处理、责任人、状态和关闭原因。

6. 查看页也是系统边界的一部分。

   最小前端查看页不是单纯 UI，它会读持久化数据，并且访问页面本身也会被记录为 `view_platform_console`。这说明运营视图、审计和权限边界需要一起设计。

## 验收清单

下面这些结果应当能在当前仓库中观察到：

1. 运行 `labs/fintech-platform/test_platform_api_service.py`，API service 的创建、查询、筛选和幂等测试通过。
2. 运行 `labs/fintech-platform/test_platform_api_app.py`，FastAPI health、payment runs、access audit 和 console 测试通过。
3. 运行 `labs/fintech-platform/test_platform_api_access_anomaly_report.py`，API access anomaly detection 测试通过。
4. 运行 `labs/fintech-platform/test_platform_api_investigation_cases.py`，API investigation case 领域能力测试通过。
5. 运行 `labs/fintech-platform/test_platform_api_investigation_endpoints.py`，API 工单 HTTP 查询和状态流转测试通过。
6. 启动 `uvicorn` 后访问 `http://127.0.0.1:8000/`，可以看到 `FinTech Platform Console`。
7. 访问 `http://127.0.0.1:8000/docs`，可以看到 FastAPI 自动生成的教学版接口文档。
8. `labs/fintech-platform` pytest 应通过。
9. 全量 `labs` pytest 应通过。

当前最后一次验证结果：

```text
labs/fintech-platform: 66 passed
labs: 311 passed
```

## 当前边界

阶段 9 仍然是教学版 API service，不是生产系统。当前没有实现：

- 真实登录态、OAuth、JWT 或企业 IAM。
- 真实 API gateway、rate limit、WAF 或 mTLS。
- 真实支付通道回调、清算和结算。
- 分布式幂等存储、消息队列或异步任务系统。
- 真实分页、排序、并发认领和工单 SLA。
- 真实记录留存、归档、删除、WORM 存储或监管报送。
- 前端交互式筛选、详情页、登录权限和操作确认。

这些不是缺陷，而是当前学习阶段刻意保留的边界。阶段 9 的目标是先把 API 边界、审计和调查闭环讲清楚。

## 阶段 10 候选路线

阶段 10 可以从三条路线中选择。推荐优先选择路线 1。

### 路线 1：事件驱动与异步任务

目标是把当前同步 API service 进一步拆出异步边界，学习金融系统中常见的后台处理方式。

可以学习和实现：

- API 接收请求后写入任务或 outbox。
- 后台 worker 处理 payment run。
- run 状态从 `accepted`、`processing` 到最终状态。
- 失败重试、重复消费和幂等处理。
- API 查询任务进度和最终结果。

这条路线最适合承接阶段 9，因为它会继续深化 request、state、idempotency、audit trail 和 consistency 的关系。

### 路线 2：只读运营控制台

目标是把当前最小 HTML console 扩展为更实用的只读运营页面。

可以学习和实现：

- payment run 列表筛选。
- run 详情页。
- API access event 筛选。
- investigation case 详情页。
- 只读页面中的空状态、错误状态和表格转义。

这条路线能提升可观察性，但金融系统核心学习深度略低于异步任务。

### 路线 3：认证与权限模型

目标是从教学版 `x-actor-id` 过渡到更接近真实系统的认证和授权边界。

可以学习和实现：

- 教学版 API key。
- 简化角色权限表。
- 权限不足返回 `403`。
- 权限拒绝也进入 access audit。
- 不同角色可访问不同接口和页面。

这条路线很重要，但会引入安全模型细节。建议在异步任务或只读控制台之后再做，避免太早把学习主线转向 IAM。

## 建议下一步

建议阶段 10 选择“事件驱动与异步任务”。原因是阶段 9 已经把外部请求放到 API 边界后面，下一步最自然的问题是：如果一次 payment run 不能在请求内同步完成，系统应该如何接收请求、保存任务、异步处理、查询状态、重试失败并保持 audit trail 完整。

阶段 10 的第一步可以先写一份设计文档，明确：

- 为什么金融系统经常需要异步处理。
- 哪些动作适合同步返回，哪些动作适合后台执行。
- outbox、worker、retry 和 idempotency 如何配合。
- 这个仓库里暂时不做哪些生产级能力。
