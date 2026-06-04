# 阶段 11B：Failed Async Run Retry 设计

最后更新：2026-06-04

## 背景

阶段 10 已经把同步 payment run 拆成教学版 async run：

```text
accepted -> processing -> completed / failed
```

阶段 11 已经把 async runs 接入 `FinTech Platform Console`，运营人员可以看到 failed async runs、attempt count 和 last error。下一步只做一个操作型控制台动作：重试 failed async run。

本设计不引入真实登录、IAM、审批流或前端框架。目标是通过一个最小动作讲清楚金融后台操作为什么需要权限、确认、状态约束、幂等和审计。

## 目标

新增一个明确的 retry 边界：

```text
failed async run -> accepted async run
```

该动作只把失败任务重新放回队列，不直接执行业务处理。后续仍由现有 worker endpoint 处理：

```text
POST /platform/async-worker/process-next
POST /platform/async-worker/process-pending
```

## 不做范围

本阶段不实现：

- 真实登录、会话、OAuth、JWT 或企业 IAM。
- 二人审批、工单审批或 SLA。
- 自动重试调度器。
- 新建 async run 复制失败请求。
- 直接在 retry endpoint 内调用 worker。
- 生产级任务锁、分布式队列或并发调度。
- 复杂 HTML 交互、前端框架、分页和搜索。

## 推荐方案

采用显式 retry endpoint：

```text
POST /platform/async-payment-runs/{run_id}/retry
```

原因：

- retry 是人工操作，不应混进 worker 调度语义。
- endpoint 名称能直接表达被操作对象和动作。
- 方便对成功和失败操作都记录 access audit。
- 方便测试状态约束和幂等边界。

## 请求模型

新增请求体模型：

```json
{
  "actor": "ops_user_001",
  "reason": "Retry after reviewing failed async run",
  "confirmation": "retry_failed_async_run"
}
```

字段规则：

- `actor`：必填，表示教学版操作人。
- `reason`：必填，表示人工重试原因。
- `confirmation`：必填，必须等于 `retry_failed_async_run`。

`confirmation` 是教学版确认动作，用来表达高影响操作不能误触。它不等于生产级审批。

## 状态规则

只允许：

```text
failed -> accepted
```

拒绝：

```text
accepted -> retry
processing -> retry
completed -> retry
unknown run -> retry
```

retry 成功后：

- `status` 改为 `accepted`。
- `updated_at` 改为 retry 时间。
- `last_error` 清空。
- `completed_at` 清空。
- `request_payload`、`request_fingerprint`、`run_id` 保持不变。

`attempt_count` 保留原值，不在 retry 时归零。原因是它表示这个 async run 历史上已经尝试处理过多少次。后续 worker 再处理时继续增加。这样能保留排障上下文。

## Store 边界

在 `SQLitePlatformAsyncRunStore` 增加方法：

```python
retry_failed(run_id: str, *, retried_at: datetime) -> PlatformAsyncRun
```

职责：

- 校验 `retried_at` 是 timezone-aware。
- 查询 run 是否存在。
- 校验当前状态必须是 `failed`。
- 在 SQLite 中执行状态更新。
- 返回更新后的 `PlatformAsyncRun`。

错误继续使用 `PlatformAsyncRunStoreError`，错误文本要能被 FastAPI 层映射成 HTTP 状态码。

## API 边界

FastAPI 增加 endpoint：

```text
POST /platform/async-payment-runs/{run_id}/retry
```

成功响应建议：

```json
{
  "run": {
    "run_id": "async_run_001",
    "status": "accepted",
    "attempt_count": 3,
    "max_attempts": 3,
    "last_error": null
  }
}
```

HTTP 映射：

- `200 OK`：retry 成功。
- `400 Bad Request`：confirmation 不正确、actor/reason 缺失或时间字段非法。
- `404 Not Found`：run 不存在。
- `409 Conflict`：run 存在但状态不是 `failed`。

## 幂等边界

retry endpoint 的幂等策略采用状态约束，而不是重复返回成功：

1. 第一次 retry failed run 成功，状态变为 `accepted`。
2. 同一个请求重复提交时，run 已不是 `failed`，返回 `409 Conflict`。

这样更适合教学操作型 API 的核心风险：重复点击不能重复制造处理动作。

## 审计设计

新增权限字符串：

```text
retry_platform_async_run
```

所有 retry 请求都记录 API access audit。

成功：

```text
permission = retry_platform_async_run
result = granted
target = fintech_platform_api_async_payment_run:{run_id}
reason = request.reason
```

失败：

```text
permission = retry_platform_async_run
result = denied
target = fintech_platform_api_async_payment_run:{run_id}
reason = error message
```

审计事件继续写入 `SQLiteAccessAuditStore`。本阶段不新增单独的 business audit event 表。

## Console 设计

第一版不要求在 HTML 页面中加入可点击 retry 按钮。原因是当前阶段重点是后端操作边界，而不是页面交互。

可选的轻量页面增强：

- 在 failed async runs 表格中保留 `run_id`、`attempt_count`、`max_attempts`、`last_error` 和 `updated_at`。
- 后续如加入 HTML form，form 必须提交 `actor`、`reason` 和 `confirmation`，并继续复用同一个 retry endpoint。

## 测试计划

新增或扩展 `labs/fintech-platform` 测试：

1. `SQLitePlatformAsyncRunStore.retry_failed()` 可以把 failed run 改回 accepted。
2. retry 后 `last_error` 和 `completed_at` 被清空。
3. retry 保留 `attempt_count`、`request_payload` 和 `request_fingerprint`。
4. retry unknown run 报错。
5. retry accepted / processing / completed run 报错。
6. API retry failed run 返回 `200 OK`，并返回 accepted run。
7. API retry unknown run 返回 `404 Not Found`。
8. API retry非 failed run 返回 `409 Conflict`。
9. API confirmation 错误返回 `400 Bad Request`。
10. retry 成功和失败都写入 API access audit。
11. retry 后现有 worker 可以再次处理该 run。

## 验收标准

完成后应能观察到：

1. failed async run 可以通过明确 endpoint 重新进入 accepted 状态。
2. retry 不直接执行业务处理。
3. 状态不是 failed 的 async run 不能 retry。
4. 重复 retry 不会重复制造处理动作。
5. retry 操作必须带 actor、reason 和 confirmation。
6. retry 成功和失败都能在 access audit 中查询到。
7. 现有 async worker 可以处理 retry 后的 accepted run。
8. `labs/fintech-platform` pytest 通过。
9. 全量 `labs` pytest 通过。

