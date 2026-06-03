# 阶段 10 总结与验收清单

最后更新：2026-06-03

阶段 10 的重点不是新增一套金融业务，而是把阶段 9 的同步 API service 拆出一个教学版异步处理边界。现在平台可以先接收 payment run 请求，把它保存为 async run，再由 worker 后台处理，最后让调用方查询任务状态和最终 platform result。

这一阶段要理解的核心区别是：

```text
HTTP request accepted != business process completed
```

也就是说，`202 Accepted` 只表示平台已经收下请求并持久化任务，不表示支付、风控、入账和审计已经完成。

## 阶段 10 做了什么

阶段 10 的主线可以概括为：

```text
POST /platform/async-payment-runs
-> SQLitePlatformAsyncRunStore saves accepted run
-> request fingerprint protects idempotency
-> PlatformAsyncWorker claims accepted run
-> PlatformApiService creates final platform run
-> SQLitePlatformStore saves business result
-> async run becomes completed / failed
-> GET /platform/async-payment-runs/{run_id}
-> API access audit records async API and worker actions
```

这条链路让阶段 9 的同步 payment run 接口旁边多了一条异步入口。同步接口仍然存在，异步接口用于学习“请求接收”和“业务完成”之间的状态边界。

阶段 10 完成了以下事情：

- 新增 SQLite async run store，保存任务状态、原始请求、request fingerprint、attempt count 和错误信息。
- 新增最小 worker，把 `accepted` run 推进到 `processing`，再处理成 `completed` 或 `failed`。
- worker 成功时复用 `PlatformApiService`，把最终业务结果写入 `SQLitePlatformStore`。
- worker 失败时记录 `last_error`，未超过 `max_attempts` 时回到 `accepted` 等待重试，达到上限后标记 `failed`。
- FastAPI 新增 async run 创建、查询、列表和教学版 worker 触发接口。
- 查询单个 async run 时，如果最终 platform run 已存在，会返回 `platform_result`。
- async API 和 worker 触发动作都会写入教学版 API access audit。
- demo 展示了 async run 创建、worker 处理、最终 platform result、幂等重放和 access audit。

## 已完成资产

阶段 10 新增和扩展的主要文件包括：

```text
docs/21-stage-10-event-driven-async-plan.md
docs/22-stage-10-summary-and-acceptance.md
labs/fintech-platform/platform_async_service.py
labs/fintech-platform/test_platform_async_service.py
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
labs/fintech-platform/demo.py
labs/fintech-platform/README.md
```

这些文件共同支持：

- `PlatformAsyncRun` 数据对象。
- `SQLitePlatformAsyncRunStore` 持久化任务队列。
- `PlatformAsyncWorker` 单进程教学版 worker。
- `POST /platform/async-payment-runs`。
- `GET /platform/async-payment-runs`。
- `GET /platform/async-payment-runs/{run_id}`。
- `POST /platform/async-worker/process-next`。
- `POST /platform/async-worker/process-pending`。
- async API access audit。
- demo 中的 async HTTP 观察路径。

## 当前异步流程

当前异步流程分成三层状态。

第一层是 HTTP 状态：

```text
202 Accepted
```

它只说明请求已经被平台保存为 async run。

第二层是 async run 状态：

```text
accepted -> processing -> completed
accepted -> processing -> accepted
accepted -> processing -> failed
```

其中第二条路径表示 worker 失败但还能重试，第三条路径表示达到最大尝试次数后失败。

第三层是 platform 业务状态：

```text
completed
kyc_blocked
risk_blocked
risk_review_required
risk_review_rejected
```

worker 自己的 `failed` 不等于支付失败。支付被 KYC/AML 或风控拦截时，worker 仍然可以是成功完成，只是 platform 业务状态不同。

## 学到的工程结论

1. `202 Accepted` 是接收确认，不是业务成功。

   金融系统里很多请求不能在一次 HTTP 调用中完成。API 可以先返回“已接收”，但调用方必须通过查询接口继续观察任务状态和最终业务结果。

2. 任务状态和业务状态必须分开。

   `platform_async_runs.status` 描述 worker 是否处理完任务；`platform_runs.status` 描述支付、风控、KYC 和账本链路的业务结果。混在一起会让排障和审计变得困难。

3. 幂等仍然不能只看 `run_id`。

   async run 创建同样使用 request fingerprint。相同 `run_id` 加相同 fingerprint 是安全重放；相同 `run_id` 加不同 fingerprint 必须拒绝。

4. Worker 必须持久化失败。

   后台任务失败不能只抛异常后消失。当前实现把错误写入 `last_error`，并用 `attempt_count` 和 `max_attempts` 控制重试或最终失败。

5. Worker 调用业务服务时仍然要依赖业务幂等。

   当前 worker 调用的是 `PlatformApiService.create_payment_run()`，它自身也会检查 request fingerprint 和已存在 platform run。这样即使 worker 重复执行，也不应重复入账。

6. 操作入口也要进入 audit trail。

   创建 async run、查询 async run、触发 worker、查询最终 payment run 都会形成 access audit event。异步系统不是逃离审计的后台黑箱。

7. 教学版 worker endpoint 不是生产模式。

   `POST /platform/async-worker/process-next` 和 `process-pending` 是为了学习和演示。真实系统通常会用独立 worker 进程、调度器、队列消费者或编排平台处理任务。

## 验收清单

下面这些结果应当能在当前仓库中观察到：

1. `SQLitePlatformAsyncRunStore` 可以创建 `accepted` async run，并保存 request payload 和 request fingerprint。
2. 同一个 `run_id`、同一个 fingerprint 重复提交会返回 idempotent replay，不创建第二个任务。
3. 同一个 `run_id`、不同 fingerprint 会被拒绝。
4. `PlatformAsyncWorker.process_next()` 可以把最早的 `accepted` run 处理为 `completed`。
5. worker 成功后可以在 `SQLitePlatformStore` 查询到最终 platform run。
6. worker 失败时会增加 `attempt_count`，保存 `last_error`，未达上限时回到 `accepted`。
7. worker 达到 `max_attempts` 后会把 async run 标记为 `failed`。
8. `POST /platform/async-payment-runs` 返回 `202 Accepted` 风格响应。
9. `GET /platform/async-payment-runs/{run_id}` 可以返回 async run 状态；完成后包含 `platform_result`。
10. `POST /platform/async-worker/process-next` 可以触发教学版 worker 处理一个 pending run。
11. `POST /platform/async-worker/process-pending` 可以按 limit 批量处理 pending runs。
12. async API 创建、查询、列表和 worker 触发动作会写入 access audit。
13. `labs/fintech-platform/demo.py` 能输出 `Async payment run via FastAPI` 和 `Async API access audit events`。
14. `labs/fintech-platform` pytest 应通过。
15. 全量 `labs` pytest 应通过。

当前最后一次验证结果：

```text
demo.py: 可运行
labs/fintech-platform: 82 passed
labs: 327 passed
```

## 当前边界

阶段 10 仍然是教学版异步任务系统，不是生产级事件平台。当前没有实现：

- Kafka、RabbitMQ、Redis Stream、Celery 或云队列。
- 多 worker 并发 claim、分布式锁或 lease timeout。
- processing 超时恢复。
- 死信队列、告警、SLA、升级和人工补偿后台。
- 真实调度器或常驻 worker 进程。
- exactly-once delivery。
- 真实支付通道异步回调。
- 真实 API gateway、认证、授权、rate limit 或 IAM。

这些不是遗漏，而是阶段 10 的刻意边界。当前目标是先把 durable task、worker、retry、idempotency、状态查询和 audit trail 的关系讲清楚。

## 后续路线建议

阶段 10 已经完成最小异步闭环。下一阶段可以从三条路线中选择。

### 路线 1：运营控制台增强

把当前最小 HTML console 扩展成更有用的只读运营视图：

- 展示 async runs。
- 展示 async run 详情和最终 platform result。
- 增加状态筛选。
- 展示最近 worker 处理结果和失败原因。

这条路线适合把阶段 9 和阶段 10 的可观察性串起来。

### 路线 2：异步任务可靠性增强

继续深化 async worker：

- processing 超时恢复。
- retry backoff。
- dead letter 状态或死信表。
- worker run history。
- 更明确的 worker audit event。

这条路线适合继续学习后台任务系统，但会更偏工程可靠性。

### 路线 3：认证与权限模型

从教学版 `x-actor-id` 过渡到简化认证授权：

- API key 或教学版 token。
- 角色权限表。
- 权限不足返回 `403`。
- 拒绝访问也写入 access audit。
- 不同角色可访问不同 API 和页面。

这条路线适合进入真实系统边界，但会把主线转向 IAM。

## 建议下一步

建议阶段 11 优先选择“运营控制台增强”。原因是阶段 9 已经有最小 console，阶段 10 又新增了 async run 和 worker 状态。下一步把 payment runs、async runs、API access events 和 investigation cases 放到同一个只读运营视图里，可以帮助学习者更直观看到一个 FinTech 平台运行时的状态、风险和审计线索。
