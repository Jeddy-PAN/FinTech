# 阶段 12：操作审计与审批边界计划与实现记录

最后更新：2026-06-04

阶段 12 承接阶段 11 的 failed async run retry。阶段 11 已经让运营人员可以通过 JSON API 或控制台 form，把 `failed` async run 重新放回 `accepted` 队列，并记录成功或失败的 API access audit。

阶段 12 的问题是：如果一个后台操作会改变任务状态，不能只依赖“操作者自己填写原因并确认”。金融后台通常还需要把操作人、审批人、审批原因和审计记录分开，避免一个人既发起又批准高影响操作。

本阶段仍然是教学版，不实现真实 IAM、登录、OAuth、JWT、企业审批流系统或权限中心。目标是用最小代码讲清楚一个工程边界：

```text
high-impact operation
-> requester reason
-> separate approver
-> approval reason
-> state transition
-> access audit
```

## 中文定义

操作审批边界，是指系统在执行高影响操作前，要求另一个人或另一个控制点明确批准，并把申请、审批、成功和失败全部记录下来。

对应英文术语：

- operation approval
- maker-checker
- four-eyes principle
- separation of duties
- access audit
- high-impact operation

在本仓库里，阶段 12 先只把这个概念落到一个操作上：

```text
retry failed async run
```

也就是：

```text
failed -> accepted
```

## 为什么金融系统需要它

金融后台操作经常会影响资金、客户状态、风险决策、合规记录或审计链路。即使本仓库的 retry 只是教学版任务重排，它代表的工程问题是真实的：

1. retry 可能让一个原本失败的任务重新进入处理队列。
2. retry 可能触发后续 payment run、ledger posting 或风险链路。
3. retry 的原因需要可复核，不能只看最终状态。
4. 如果操作人和审批人是同一个人，审批就失去了制衡意义。
5. 失败的审批尝试也要进入 audit trail，否则事后无法解释是谁尝试做了什么。

## 程序员实现时会遇到什么问题

1. 状态转换和审批校验要分层。
   `SQLitePlatformAsyncRunStore.retry_failed()` 只负责 `failed -> accepted` 状态转换；审批字段校验应放在 API 操作边界附近。

2. 成功和失败都要审计。
   缺少审批、自己审批自己、确认文本错误、目标 run 不存在、目标状态不是 failed，都应写入 denied audit event。

3. requester 和 approver 不能混淆。
   `actor` 表示发起 retry 的人；`approved_by` 表示批准 retry 的人。二者不能相同。

4. 教学版不等于生产权限系统。
   本阶段只校验文本字段和职责分离，不引入真实角色权限、登录态或审批流数据库。

5. 控制台 form 不能绕过 JSON API 校验。
   form endpoint 仍然应复用同一套 `_retry_async_run()` 校验，避免浏览器路径和 API 路径行为不一致。

## 当前基础

当前已有能力：

```text
POST /platform/async-payment-runs/{run_id}/retry
POST /platform/async-payment-runs/{run_id}/retry-form
```

当前 retry 请求字段：

```text
actor
reason
confirmation = retry_failed_async_run
```

当前 access audit：

```text
permission = retry_platform_async_run
target = fintech_platform_api_async_payment_runs/{run_id}
outcome = granted / denied
reason = retry reason or error reason
```

阶段 12 已在此基础上增加审批字段：

```text
approved_by
approval_reason
approval_confirmation = approve_retry_failed_async_run
```

## 阶段 12 目标

阶段 12 只做一个小而完整的闭环：

1. retry JSON API 要求二人审批字段。
2. retry form 要求二人审批字段。
3. 操作人和审批人不能相同。
4. 审批原因不能为空。
5. 审批确认文本必须正确。
6. 成功 retry 的 audit reason 同时包含 requester reason 和 approver。
7. 失败 retry 继续写入 denied audit event。
8. retry 仍然只做 `failed -> accepted`，不直接触发 worker。
9. console 页面展示新的审批输入字段。
10. 更新 README、`labs/fintech-platform/README.md` 和 `LEARNING_PROGRESS.md`。

## 当前实现进度

阶段 12 第一版已完成：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
```

当前 JSON retry API 和 console retry form 都要求：

```text
actor
reason
confirmation = retry_failed_async_run
approved_by
approval_reason
approval_confirmation = approve_retry_failed_async_run
```

实现要点：

1. `RetryAsyncRunRequest` 已增加 `approved_by`、`approval_reason` 和 `approval_confirmation`。
2. `_retry_async_run()` 继续作为 JSON endpoint 和 form endpoint 的共享校验入口。
3. `actor == approved_by` 会被拒绝，错误信息为 `retry approver must differ from actor`。
4. 错误 `approval_confirmation` 会被拒绝，错误信息为 `approval_confirmation must be approve_retry_failed_async_run`。
5. 成功 retry 的 access audit reason 使用结构化文本记录 requester reason、approved_by 和 approval_reason。
6. retry 仍然只调用 `SQLitePlatformAsyncRunStore.retry_failed()`，只把 run 改回 `accepted`，不直接触发 worker。

本阶段仍不单独创建 approval record，也不新增审批事件表；审批信息先落在 `retry_platform_async_run` access audit 的 reason 中。

## 当前不做的事

阶段 12 不实现：

- 真实用户登录、session、OAuth、JWT 或企业 IAM。
- 角色权限校验，例如判断 `approved_by` 是否真的拥有审批角色。
- 审批单表、待审批队列、审批状态机或 SLA。
- 多级审批。
- 撤销 retry。
- worker 自动消费 retry 后的任务。
- 对所有后台操作全面改造审批；本阶段只改 failed async run retry。

这些能力可以作为后续阶段扩展，但现在会分散学习重点。

## 建议实现方案

### 1. 请求模型扩展

修改文件：

```text
labs/fintech-platform/platform_api_app.py
```

扩展 `RetryAsyncRunRequest`：

```python
class RetryAsyncRunRequest(BaseModel):
    actor: str | None = None
    reason: str | None = None
    confirmation: str | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    approval_confirmation: str | None = None
```

新增常量：

```python
APPROVE_RETRY_FAILED_ASYNC_RUN_CONFIRMATION = "approve_retry_failed_async_run"
```

### 2. 核心校验规则

继续让 JSON endpoint 和 form endpoint 共享 `_retry_async_run()`。

建议 `_retry_async_run()` 增加参数：

```python
approved_by: str | None
approval_reason: str | None
approval_confirmation: str | None
```

校验顺序建议：

1. `actor` 必填。
2. `reason` 必填。
3. `confirmation` 必须等于 `retry_failed_async_run`。
4. `approved_by` 必填。
5. `approval_reason` 必填。
6. `approval_confirmation` 必须等于 `approve_retry_failed_async_run`。
7. `approved_by` 不能等于 `actor`。
8. 调用 `async_store.retry_failed()`。

错误信息建议保持明确：

```text
approved_by is required
approval_reason is required
approval_confirmation must be approve_retry_failed_async_run
retry approver must differ from actor
```

### 3. 审计记录

成功时继续写入：

```text
permission = retry_platform_async_run
outcome = granted
actor = actor
target = fintech_platform_api_async_payment_runs/{run_id}
```

成功 audit reason 建议包含两个信息：

```text
reason={requester reason}; approved_by={approved_by}; approval_reason={approval_reason}
```

失败时继续写入：

```text
outcome = denied
reason = error message
```

审批人本身不单独写一条 `approval.granted` 事件，避免本阶段过度扩展 audit event 类型。后续如果要把审批本身建模成独立事件，再新增 dedicated operation approval model。

### 4. 控制台 form

修改 `_retry_form_html(run_id)`，新增字段：

```html
<input name="approved_by" type="text" placeholder="approved_by" required>
<input name="approval_reason" type="text" placeholder="approval_reason" required>
<input name="approval_confirmation" type="text" value="approve_retry_failed_async_run" required>
```

form endpoint 继续把字段传给 `_retry_async_run()`。

### 5. 测试计划

主要修改：

```text
labs/fintech-platform/test_platform_api_app.py
```

建议先写失败测试，再改实现。

#### 测试 1：JSON retry 要求独立审批并成功重排

覆盖：

- failed run 可以 retry。
- 请求体包含 `actor`、`reason`、`confirmation`、`approved_by`、`approval_reason`、`approval_confirmation`。
- 返回状态仍是 `accepted`。
- audit event outcome 是 `granted`。
- audit reason 包含 `approved_by=ops_manager_001`。

#### 测试 2：JSON retry 拒绝自己审批自己

覆盖：

- `actor == approved_by` 时返回 `400`。
- run 保持 `failed`。
- audit event outcome 是 `denied`。
- audit reason 包含 `retry approver must differ from actor`。

#### 测试 3：JSON retry 拒绝缺少审批确认

覆盖：

- `approval_confirmation` 错误或缺失时返回 `400`。
- audit event outcome 是 `denied`。
- 错误信息包含 `approval_confirmation must be approve_retry_failed_async_run`。

#### 测试 4：form 页面展示审批字段

覆盖 HTML 包含：

```text
name="approved_by"
name="approval_reason"
name="approval_confirmation"
approve_retry_failed_async_run
```

#### 测试 5：form retry 使用二人审批成功

覆盖：

- form 提交成功后 `303` 到 `/platform/view?retry_status=success`。
- run 回到 `accepted`。
- audit event outcome 是 `granted`。

#### 测试 6：form retry 拒绝自己审批自己

覆盖：

- form 返回 `/platform/view?retry_error=...`。
- console 显示 `retry approver must differ from actor`。
- run 保持 `failed`。
- audit event outcome 是 `denied`。

## 推荐实现顺序

1. 修改 `_retry_payload()` 测试 helper，加入审批字段。
2. 修改现有成功 retry 测试，让它先失败。
3. 增加 self-approval 和 approval confirmation 测试。
4. 扩展 `RetryAsyncRunRequest`。
5. 扩展 `_retry_async_run()` 参数和校验。
6. 扩展 JSON retry endpoint 调用。
7. 扩展 form endpoint 字段读取。
8. 扩展 `_retry_form_html()`。
9. 跑 `test_platform_api_app.py`。
10. 跑 `labs/fintech-platform`。
11. 如无异常，跑全量 `labs`。
12. 更新 README、`labs/fintech-platform/README.md` 和 `LEARNING_PROGRESS.md`。

用户已明确不需要 AI 代做 git 操作，因此本阶段不包含 git add、commit 或 checkout 步骤。

## 验收标准

阶段 12 完成时，应满足：

1. JSON retry API 必须包含审批字段才能成功。
2. console retry form 必须包含审批字段才能成功。
3. `actor == approved_by` 被拒绝。
4. 缺少 `approval_reason` 被拒绝。
5. 错误 `approval_confirmation` 被拒绝。
6. 成功和失败都写入 `retry_platform_async_run` access audit。
7. 成功 retry 只把 run 改为 `accepted`，不触发 worker。
8. 既有 async run 创建、查询、worker、console 展示能力不回退。
9. `labs/fintech-platform` pytest 通过。
10. 全量 `labs` pytest 通过。

## 验证记录

截至 2026-06-04，已完成以下阶段性验证：

```text
test_platform_api_app.py -k "retry": 8 passed
test_platform_api_app.py: 23 passed
labs/fintech-platform: 94 passed
labs: 339 passed
```

## 后续候选方向

阶段 12 完成后，可以在以下方向中选择一个：

1. 运行报告与对账视角：把 async run、platform result、ledger posting 和 access audit 做成日终检查报告。
2. 审批事件独立建模：把 approval 从 access audit reason 中拆成单独的 operation approval record。
3. 文档整理阶段：压缩 docs 索引，把学习路径从文件列表整理成主题路线。
