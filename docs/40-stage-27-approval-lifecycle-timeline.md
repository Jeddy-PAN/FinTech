# 阶段 27：Approval Lifecycle Timeline

最后更新：2026-06-09

阶段 27 承接阶段 26。阶段 26 已经把 pending operation approval 的 approve / reject 表单接入 `FinTech Platform Console`。阶段 27 不继续增加操作按钮，而是回到只读解释能力：在 operation approval detail view 中增加 lifecycle timeline，帮助运营人员看清一条 approval 从申请、决策到 retry execution 的轨迹。

本阶段继续只新增一篇阶段文档，把目标、范围、实现和验证记录合并在一起。

## 中文定义

approval lifecycle timeline，是指围绕一条 operation approval record，把申请、审批决定和相关执行审计按时间顺序展示出来的只读轨迹。

对应英文术语：

- approval lifecycle timeline
- approval requested event
- approval decided event
- retry execution audit
- operational traceability

## 为什么做 timeline

阶段 24 的详情页已经能展示 approval record、关联 async run 和 completed platform result 摘要。阶段 26 又让 console 可以直接 approve / reject pending approval。

但运营人员在排查时还需要回答：

1. 这条 approval 是什么时候申请的？
2. 谁申请的，原因是什么？
3. 如果已经决策，是谁处理的，结果是什么？
4. 如果是 retry approval，审批通过后是否真的执行了 retry？

这些问题不适合只靠 record 字段散落展示，因此阶段 27 增加一张只读 timeline 表。

## 第一版范围

更新代码：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/40-stage-27-approval-lifecycle-timeline.md
```

## Timeline 数据来源

timeline 第一版有三类行：

### approval_requested

来自 `OperationApprovalRecord`：

```text
requested_at
requested_by
request_reason
status=pending
```

### approval_decided

如果 approval 已经有 `decided_at`，从 `OperationApprovalRecord` 生成：

```text
decided_at
approved_by
status
approval_reason / decision_reason
```

这里的 `status` 可以是：

```text
approved
rejected
cancelled
expired
```

### retry_execution

如果存在 access audit event：

```text
permission = retry_platform_async_run
reason contains approval_id={approval_id}
```

则把该 retry execution audit event 加入 timeline，展示：

```text
occurred_at
actor
outcome
reason
```

这让 detail view 能说明“approval 已经 approved”之后，retry 是否真的被执行。

## 页面变化

`GET /platform/operation-approvals/{approval_id}/view` 新增区块：

```text
Lifecycle Timeline
```

字段：

```text
occurred_at
event_type
actor
outcome
reason
```

该区块仍然是只读展示，不新增按钮。

## 第一版不做

- 不新增数据库表。
- 不把 timeline 持久化成单独模型。
- 不新增 HTTP JSON timeline endpoint。
- 不做 cancel / expire 表单。
- 不做真实 IAM、登录、session、CSRF 或角色权限。
- 不把所有 access audit event 都塞进 timeline，只选与 approval lifecycle 直接相关的事件。

## 验证记录

截至 2026-06-09，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
```

结果：

```text
test_platform_api_app.py: 37 passed
labs/fintech-platform: 135 passed
labs: 380 passed
demo.py: 可运行
```

## 后续候选方向

阶段 27 完成后，可以选择：

1. 补 async run detail 和 platform result detail，让 approval detail 能继续跳转。
2. 为 operation approval 查询增加总数统计或 cursor pagination。
3. 如果继续增强 console，再考虑 cancel / expire 表单，但要先明确权限和误操作边界。
4. 为 operations console 增加更完整的筛选入口，而不是只显示最新 5 条。
