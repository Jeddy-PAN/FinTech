# 阶段 36：一致性、并发和恢复

本阶段继续沿用“少拆文档、代码可验证”的方式，把一致性、并发和恢复放进同一篇记录。目标不是把教学平台改成生产级分布式系统，而是让关键状态流转具备更清晰的事务边界，并能用测试说明：同一个 async run 不应被两个 worker 同时 claim，同一条 pending approval 不应被两个决策同时消费。

## 1. 本阶段要解决什么

当前平台已经有三类重要持久化边界：

| 边界 | 主要对象 | 已有职责 | 阶段 36 补强点 |
| --- | --- | --- | --- |
| platform store | `platform_runs`、`platform_run_audit_events` | 保存最终业务结果和客户审计时间线 | 本阶段只梳理边界，不重写主业务事务 |
| async run store | `platform_async_runs` | 保存 accepted / processing / completed / failed | 增加 worker claim 语义，避免多个 worker 同时处理同一个 accepted run |
| approval store | `operation_approvals` | 保存 pending / approved / rejected / cancelled / expired | 决策更新使用 `WHERE status = 'pending'` 的条件写入，避免重复 approve / reject / cancel / expire |

这里的一致性不是“所有表一次性强事务”。更现实的学习边界是：

1. 一个状态机内部的状态变更必须强约束，例如 pending 只能被一个最终决策消费。
2. 跨 store 的动作要用状态和审计记录解释，例如 approval approved 后执行 retry，并留下 retry execution access audit。
3. 报表和对账可以滞后，但要能发现状态、业务结果和 audit trail 之间的不一致。

## 2. Worker claim / lease / timeout 的教学边界

### 中文定义

worker claim 是后台 worker 从任务队列中“认领”一条待处理任务的动作。claim 成功后，任务从 `accepted` 进入 `processing`，其他 worker 不应再处理它。

### 英文术语

- claim：认领任务。
- lease：租约，表示任务被某个 worker 临时持有。
- timeout：超时，表示 processing 太久没有完成时需要恢复或重新排队。

### 为什么金融系统需要它

支付、入账、清结算、对账修复等后台任务通常不能重复执行。即使底层业务有幂等保护，也不应该让两个 worker 同时推进同一条任务，因为这会造成重复外部调用、重复审计事件、运营视图混乱和恢复困难。

### 本阶段实现

`SQLitePlatformAsyncRunStore.claim_next_accepted(started_at=...)` 新增了教学版 claim：

```text
accepted
-> claim_next_accepted()
-> processing
```

写入时带状态条件：

```sql
WHERE run_id = ? AND status = 'accepted'
```

如果另一个连接已经把同一条 run 改成 `processing`，后来的 claim 返回 `None`，不会重复处理。`PlatformAsyncWorker.process_next()` 现在直接调用 claim，而不是先 `next_accepted_run()` 再 `mark_processing()`。

本阶段没有完整实现 lease owner、lease deadline 和 timeout recovery 表字段。原因是当前教学平台还没有长期运行的多 worker 进程模型，也没有调度器。阶段 36 先把“只能 claim 一次”做实，后续如果进入可运行交付章节，再考虑：

1. 增加 `claimed_by`、`lease_expires_at`。
2. 对超时的 `processing` run 执行 recovery scan。
3. 记录 `async_run.claimed`、`async_run.lease_expired`、`async_run.requeued` 审计事件。

## 3. Approval 决策的并发冲突

### 中文定义

审批决策并发冲突，是指两个操作人或两个请求几乎同时尝试消费同一条 pending approval。例如一个请求 approve，另一个请求 reject。

### 英文术语

- optimistic concurrency：乐观并发控制。
- conditional update：条件更新。
- terminal state：终态。

### 为什么金融系统需要它

retry approval 是高影响操作。一个 pending approval 只能有一个最终结果。若两个请求都以为自己成功，就可能出现审批记录显示 approved，但另一个 reject 的审计也存在，或者 retry 被执行两次。

### 本阶段实现

`SQLiteOperationApprovalStore` 的 `approve_pending()`、`reject_pending()`、`cancel_pending()` 和 `expire_pending()` 现在都通过 `_transition_pending()` 执行条件更新：

```sql
WHERE approval_id = ? AND status = 'pending'
```

如果记录已经进入 `approved / rejected / cancelled / expired`，第二个决策会收到 `OperationApprovalError`，API 层继续映射为 `409 Conflict`，并写入 denied access audit。

API 层也补强了重复 approve retry 的测试：第一次 approve 会执行 `failed -> accepted`，第二次 approve 返回 409，且 `retry_platform_async_run` execution audit 只出现一次。

## 4. 恢复视角

阶段 36 之后，平台的恢复思路更清晰：

| 失败点 | 当前表现 | 当前恢复方式 | 后续可增强 |
| --- | --- | --- | --- |
| worker 处理失败 | async run 回到 `accepted` 或进入 `failed` | worker 可继续处理 accepted；failed 需要 retry approval | 增加 lease timeout 和 recovery scan |
| retry approval 重复提交 | 第二次决策 409 | access audit 记录 denied | 增加审批冲突报表 |
| retry approved 后执行失败 | approval 可能已 approved，但 async run retry 失败 | API 返回错误并记录 denied access audit | 更严格地把 approval decision 和 retry execution 拆成 saga / outbox |
| schema 变更 | approval store 已有一个教学版迁移函数 | 初始化 store 时迁移旧 schema | 引入版本化 migration 表 |
| 数据损坏或误删 | 当前依赖 SQLite 文件 | 手工备份 SQLite 文件 | 增加 backup / restore 演练脚本 |

这里要注意：approval decision 和 retry execution 目前仍跨两个 SQLite store，不是一个真正的分布式事务。阶段 36 的价值是缩小冲突窗口、让重复请求可检测、让恢复方向可解释，而不是声称已经具备生产级事务编排。

## 5. 已完成代码与测试

本阶段修改：

```text
labs/fintech-platform/platform_async_service.py
labs/fintech-platform/platform_operation_approval.py
labs/fintech-platform/test_platform_async_service.py
labs/fintech-platform/test_platform_operation_approval.py
labs/fintech-platform/test_platform_api_app.py
```

新增或补强的验证点：

1. 两个 async store 连接对同一条 accepted run 只有一个能 claim 成功。
2. claim 后的 run 进入 `processing`，重复 `mark_processing()` 会被拒绝。
3. 两个 approval store 连接对同一条 pending approval 只有第一个终态决策成功。
4. API 层重复 approve retry approval 返回 409，并且 retry execution audit 只写一次。

已验证：

```text
py_compile: passed
test_platform_async_service.py + test_platform_operation_approval.py + test_platform_api_app.py: 79 passed
labs/fintech-platform: 150 passed
demo.py: runnable
labs: 395 passed
```

## 6. 当前仍不实现

- 生产级分布式锁。
- 多 worker lease owner 和 lease deadline 字段。
- 自动 timeout scanner。
- 真正的 saga / workflow engine。
- 版本化 migration 框架。
- 自动 backup / restore 脚本。
- 跨多个 SQLite 数据库文件的强事务。

这些内容不适合一次性塞进当前教学平台。后续如果继续按阶段 33 的路线推进，阶段 37 更适合进入“外部支付、清结算和真实对账模型”，把当前内部一致性边界和外部世界的文件、回调、对账差异连接起来。
