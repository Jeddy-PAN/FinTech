# 阶段 9：FinTech Platform API 服务化计划

最后更新：2026-05-19

阶段 9 的目标是在阶段 8 的综合平台之上继续构建，而不是开一个全新的小项目。阶段 8 已经跑通了端到端链路；阶段 9 要把这条链路放到 API 边界后面，观察外部请求如何驱动平台运行、查询状态和复核结果。

## 为什么先做 API 服务化

脚本 demo 适合学习内部流程，但真实系统通常不是由人手动运行脚本，而是由外部请求触发。API 服务化会迫使我们处理几个更接近生产系统的问题：

- 请求字段如何进入领域模型。
- `run_id` 或 idempotency key 如何防止重复创建。
- API 返回什么状态，而不是直接暴露内部对象。
- 平台运行结果如何落盘后再查询。
- 错误如何变成稳定的响应格式。
- API 调用本身如何进入 access audit，后续才能分析谁访问了哪些平台能力。

## 当前进展

当前已新增 API service 边界：

```text
labs/fintech-platform/platform_api_service.py
labs/fintech-platform/test_platform_api_service.py
```

这一步还不是 FastAPI 路由，而是先建立可测试的 API service 边界：

```text
PlatformApiPaymentRequest
-> PlatformApiService.create_payment_run()
-> FinTechPlatform.process_payment()
-> SQLitePlatformStore.save_result()
-> response dict
```

它支持：

- 创建 payment run。
- 使用 `run_id` 做教学版幂等重放。
- 查询单个 payment run。
- 按状态或客户查询 payment runs。
- 把常见错误转成稳定的 error response。

当前也已新增 FastAPI 路由层：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
```

HTTP 层只负责接收请求、调用 service、映射状态码和返回 JSON，不把业务逻辑写进路由函数。

当前路由层也已接入教学版 API 访问审计：

- 每次 `GET /health`、创建 payment run、查询 payment run、列出 payment runs 都会写入 `SQLiteAccessAuditStore`。
- 成功调用记录 `audit_access.granted`。
- 幂等重放仍记录成功访问，并在 `reason` 中标记 `idempotent_replay`。
- 业务错误或缺失资源记录 `audit_access.denied`，但不把请求中的身份证件号、地址等敏感字段写入访问审计原因。
- `GET /platform/api-access-events` 可以按 actor、permission 或 outcome 查询 API 访问审计事件。

这一步不是登录、鉴权或企业 IAM，只是让“调用 API 这个动作”也可以被后续复核。

当前还新增了 API 访问异常检测：

```text
labs/fintech-platform/platform_api_access_anomaly_report.py
labs/fintech-platform/test_platform_api_access_anomaly_report.py
```

它只筛选 `target` 以 `fintech_platform_api_` 开头的 API 访问审计事件，然后复用合规审计阶段的 access monitoring 规则。当前可识别教学版 repeated denied access，例如同一个 actor 在短时间内反复查询不存在的 payment run。导出文件包括：

```text
platform_api_access_anomaly_findings.csv
platform_api_access_anomaly_report.html
```

这仍是学习用的离线检测，不等于生产环境的 SIEM、WAF、API gateway 或实时风控。

当前还新增了 API 访问异常调查工单：

```text
labs/fintech-platform/platform_api_investigation_cases.py
labs/fintech-platform/test_platform_api_investigation_cases.py
```

它把 API access anomaly finding 转成 `AccessAnomalyInvestigationCase`，复用合规审计阶段的工单状态机和 SQLite 持久化能力，支持：

- `open -> investigating -> resolved`
- `open -> investigating -> false_positive`
- 工单创建、接手、关闭动作进入 `access_investigation_case.*` 审计事件
- 导出 `platform_api_access_investigation_cases.csv`
- 导出 `platform_api_access_investigation_report.html`

这一步表达的是“可疑 API 访问需要可追踪处理闭环”，不是生产级客服/安全工单系统。

当前 FastAPI 路由层也已暴露 API anomaly 和 investigation case 的最小查询入口：

- `GET /platform/api-access-anomaly-findings`
- `POST /platform/api-access-investigation-cases`
- `GET /platform/api-access-investigation-cases?status=open&actor=api_viewer_404`
- `GET /platform/api-access-investigation-cases/{case_id}`
- `PATCH /platform/api-access-investigation-cases/{case_id}/start`
- `PATCH /platform/api-access-investigation-cases/{case_id}/resolve`
- `PATCH /platform/api-access-investigation-cases/{case_id}/false-positive`

这些接口会从 API access audit 事件中计算 finding，把 finding 开成工单后写入 SQLite，再支持按状态、actor 或 assignee 查询。它们仍然只是教学版 HTTP 入口，没有实现真实权限、审批流、SLA、分页或并发认领。

当前还新增了最小前端查看页：

- `GET /`
- `GET /platform`
- `GET /platform/view`

页面标题是 `FinTech Platform Console`，只读展示 payment runs、API access anomalies、investigation cases 和 recent API access events。它仍然复用 FastAPI 应用和 SQLite 存储，不引入单独前端项目、模板框架、登录态或真实 IAM。访问查看页本身会记录 `view_platform_console` access audit，用来继续观察“查看运营页面”这个动作也应进入审计轨迹。

## 当前 API

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

查询类接口可以通过 `x-actor-id` 请求头传入调用者标识；如果没有传，则使用 `anonymous_api_client` 作为教学版默认 actor。创建 payment run 时沿用请求体里的 `actor` 字段。

## 运行方式

```powershell
& 'C:\App\Anaconda\python.exe' -m uvicorn platform_api_app:app --app-dir .\labs\fintech-platform --reload
```

服务启动后，可以访问 `http://127.0.0.1:8000/docs` 查看 FastAPI 自动生成的教学版接口文档。
如果想先看最小前端页面，可以访问 `http://127.0.0.1:8000/` 或 `http://127.0.0.1:8000/platform/view`。

## 暂时不做

当前 API 仍然是教学版，暂时不做：

- 登录态
- OAuth / JWT
- 真实权限系统
- 分布式幂等存储
- 异步任务队列
- 真实支付通道回调
- 访问审计的删除、归档和法定留存
- 实时安全告警和自动封禁

这些都可以在后续阶段逐步引入。
