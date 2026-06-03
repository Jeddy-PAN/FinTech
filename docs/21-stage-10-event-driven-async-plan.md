# 阶段 10：事件驱动与异步任务设计

最后更新：2026-06-03

阶段 10 承接阶段 9 的 API service。阶段 9 的 `POST /platform/payment-runs` 会在一次 HTTP 请求里同步完成 KYC/AML、payment order、risk decision、ledger posting 和持久化。阶段 10 要学习的问题是：如果一次 payment run 不能在请求内同步完成，平台应该如何先接收请求，再由后台 worker 处理，并让调用方查询进度。

这不是另起一个新项目，而是在 `labs/fintech-platform/` 上继续构建教学版异步边界。

## 为什么金融系统需要异步处理

金融系统经常不能把所有事情都放在一次 HTTP 请求里完成，原因包括：

- 外部依赖可能慢，例如支付通道、KYC 服务、风控模型、通知系统。
- 处理过程可能需要重试，例如网络超时、临时数据库锁、下游服务不可用。
- 调用方需要明确知道“请求已被接收”和“业务最终完成”是两件事。
- 系统需要保存中间状态，便于审计、排查和人工处理。
- 后台任务失败后不能静默丢失，必须可以查询、重试或标记失败。

阶段 10 的核心直觉是：

```text
API 接收请求，不等于业务已经完成。
API 可以先返回 accepted，后台 worker 再推进业务状态。
```

## 目标流程

阶段 10 的目标流程先保持简单：

```text
POST /platform/async-payment-runs
-> validate request
-> save async run as accepted
-> save request fingerprint
-> return 202 Accepted

worker
-> claim accepted run
-> mark processing
-> call FinTechPlatform.process_payment()
-> save final platform result
-> mark completed / failed

GET /platform/async-payment-runs/{run_id}
-> return accepted / processing / completed / failed
-> include final platform result when available
```

这个流程要让调用方看到两层状态：

| 层级 | 示例状态 | 含义 |
| --- | --- | --- |
| HTTP 状态 | `202 Accepted` | API 已接收请求，但业务还没完成 |
| async run 状态 | `accepted` / `processing` / `completed` / `failed` | 后台任务当前进度 |
| platform 业务状态 | `completed` / `kyc_blocked` / `risk_blocked` / `risk_review_required` | `FinTechPlatform` 的最终业务结果 |

## 建议新增对象

阶段 10 建议新增这些教学版对象：

```text
PlatformAsyncRun
PlatformAsyncRunStatus
PlatformAsyncRunStore
SQLitePlatformAsyncRunStore
PlatformAsyncWorker
PlatformAsyncWorkerResult
```

建议状态：

```text
accepted
processing
completed
failed
```

其中 `failed` 表示 worker 自身处理失败，例如请求数据无法转换、内部异常或超过重试次数。它不等于支付失败。支付被 KYC/AML 或风控拦截，应当仍然是 worker 成功完成，只是 platform 业务状态不同。

## 建议新增 SQLite 表

阶段 10 可以先在一个 SQLite 文件里实现教学版任务存储：

```text
platform_async_runs
```

建议字段：

```text
run_id
status
request_payload
request_fingerprint
attempt_count
max_attempts
last_error
created_at
updated_at
started_at
completed_at
```

可以选择继续复用 `SQLitePlatformStore` 保存最终 platform run 快照。也就是说：

```text
platform_async_runs       保存任务状态和原始请求
platform_runs             保存最终业务结果快照
platform_run_audit_events 保存最终业务 audit timeline
```

这样任务状态和业务结果分开，便于理解“任务是否处理完”和“业务结果是什么”不是同一个概念。

## 幂等设计

阶段 10 仍然沿用阶段 9 的原则：幂等不能只看 `run_id`。

规则建议：

1. 第一次提交某个 `run_id`：
   - 保存 request payload。
   - 保存 request fingerprint。
   - 创建 `accepted` async run。
2. 再次提交同一个 `run_id` 且 fingerprint 一致：
   - 不创建新任务。
   - 返回已有 async run 状态。
3. 再次提交同一个 `run_id` 但 fingerprint 不一致：
   - 拒绝请求。
   - 记录 denied API access audit。

这样可以避免同一个业务 key 被不同参数重复使用。

## Worker 处理边界

worker 的最小职责：

```text
claim one accepted or retryable failed run
-> mark processing
-> rebuild PlatformApiPaymentRequest
-> call existing PlatformApiService or FinTechPlatform
-> save final result
-> mark completed
```

worker 失败时：

```text
attempt_count += 1
last_error = error message

if attempt_count < max_attempts:
  status = accepted
else:
  status = failed
```

当前阶段不需要真正的并发锁和多进程 worker。可以先用单进程方法，例如：

```python
worker.process_next()
worker.process_pending(limit=10)
```

后续再学习并发 claim、锁、租约、超时恢复和死信队列。

## 和 outbox 的关系

本仓库早期已经在支付订单实验里学习过 transactional outbox 和 outbox publisher。阶段 10 会复用这个思想，但先不急着接入真实消息队列。

当前可以把 `platform_async_runs` 看成一种教学版本地任务队列：

```text
API writes durable task
worker reads pending task
worker updates task status
```

如果后续继续扩展，可以再加入真正的 outbox：

```text
platform_async_runs
platform_async_outbox
```

`platform_async_outbox` 可以记录：

- `platform_async_run.accepted`
- `platform_async_run.processing`
- `platform_async_run.completed`
- `platform_async_run.failed`

但阶段 10 第一版建议先实现 async run store 和 worker，等状态流转稳定后再加入 outbox message 发布。

## API 设计建议

阶段 10 可以新增一组接口，不破坏阶段 9 的同步接口：

```text
POST /platform/async-payment-runs
GET  /platform/async-payment-runs/{run_id}
GET  /platform/async-payment-runs?status=accepted
POST /platform/async-worker/process-next
POST /platform/async-worker/process-pending
```

其中 worker 触发接口只是教学用途。生产系统通常不会把 worker 处理入口暴露给普通 API 调用方。

## 第一版验收标准

阶段 10 第一版完成后，应能观察到：

1. 创建 async payment run 返回 `202` 风格的 accepted 响应。
2. 同一个 `run_id`、同一 fingerprint 重复提交不会创建第二个任务。
3. 同一个 `run_id`、不同 fingerprint 会被拒绝。
4. worker 可以把 `accepted` 任务推进到 `processing`，再推进到 `completed`。
5. worker 完成后可以在 `SQLitePlatformStore` 中查到最终 platform run。
6. worker 失败时会增加 attempt count，并保存 last error。
7. 查询接口可以看到 async run 的当前状态和最终结果。
8. API 调用和 worker 关键动作应进入教学版 audit trail。
9. `labs/fintech-platform` pytest 通过。
10. 全量 `labs` pytest 通过。

## 当前不做的事

阶段 10 仍然是教学版，不实现：

- Kafka、RabbitMQ、Redis Stream、Celery 或云队列。
- 多 worker 并发抢占和分布式锁。
- 真实调度器、cron、后台服务守护进程。
- 真实死信队列、告警、SLA 和自动升级。
- 真实支付通道异步回调。
- 真实 exactly-once delivery。
- 真实生产级认证、API gateway、rate limit 或 IAM。

这些不是目标缺失，而是为了先讲清楚最小异步边界。

## 推荐实现顺序

1. 已完成 `platform_async_service.py`，定义 async run 数据对象、状态和 SQLite store。
2. 已完成 async run store 测试，覆盖创建、查询、幂等和 fingerprint 冲突。
3. 已完成最小 worker，支持 `process_next()` 把 accepted run 推进到 processing，再处理为 completed 或 failed。
4. 已完成 worker 写入现有 `SQLitePlatformStore`，成功后可以查询最终 platform run。
5. 已完成 FastAPI async endpoints，支持 async run 创建、查询、按状态列表和教学版 worker 触发接口。
6. 已更新 demo，展示 HTTP accepted、worker 处理、最终 platform run 查询和 access audit 记录。
7. 已在 service 测试中覆盖失败重试和 attempt count。

阶段 10 的阶段小结与验收清单已经整理到：

```text
docs/22-stage-10-summary-and-acceptance.md
```

后续建议进入阶段 11 运营控制台增强设计，把 payment runs、async runs、API access events 和 investigation cases 放到更完整的只读运营视图里。
