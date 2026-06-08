# 阶段 15：Operation Approval Report

最后更新：2026-06-08

阶段 15 承接阶段 14。阶段 14 已经把 failed async run retry 的审批事实从 access audit 中拆出来，形成独立 `OperationApprovalRecord`。阶段 15 的目标是把这些审批记录整理成离线报表，让运营和合规复核时能直接看到审批总量、通过/拒绝分布、retry 操作数量和 self-approval 拒绝数量。

本阶段仍然只新增一篇阶段文档，把设计、实现进度和验证记录合并在一起，避免继续增加细碎文档。

## 中文定义

操作审批报表，是对高影响操作审批记录的汇总和明细导出。

对应英文术语：

- operation approval report
- approval summary
- approval record export
- maker-checker review
- separation of duties review

在本仓库里，第一版只分析一种操作：

```text
retry failed async payment run
```

## 为什么需要 approval report

单条 `OperationApprovalRecord` 回答的是：

```text
这一次 retry 是谁申请、谁审批、审批结论是什么。
```

`OperationApprovalReport` 回答的是：

```text
一批 retry 审批记录整体是否可解释，是否存在职责分离风险，是否有被拒绝的 self-approval 尝试。
```

它和阶段 13 的 operations report 分工不同：

1. operations report 关注 async run、platform result、ledger posting 和 retry access audit 是否对得上。
2. approval report 关注 retry 审批记录本身是否清楚，特别是 approved / rejected 和 self-approval rejected 的分布。

## 第一版范围

新增代码：

```text
labs/fintech-platform/platform_operation_approval_report.py
labs/fintech-platform/test_platform_operation_approval_report.py
```

更新代码：

```text
labs/fintech-platform/demo.py
```

更新文档：

```text
README.md
docs/README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/28-stage-15-operation-approval-report.md
```

## 报表口径

第一版 summary 包含：

```text
total_record_count
approved_count
rejected_count
retry_operation_count
self_approval_rejected_count
```

其中：

- `approved_count` 统计 `status=approved` 的 approval record。
- `rejected_count` 统计 `status=rejected` 的 approval record。
- `retry_operation_count` 统计 `operation_type=retry_platform_async_run` 的记录。
- `self_approval_rejected_count` 统计 `status=rejected` 且 `requested_by == approved_by` 的记录。

报表明细按：

```text
requested_at
approval_id
```

排序，方便人工复核同一时间附近的操作。

## 导出文件

`export_operation_approval_report()` 会生成：

```text
platform_operation_approval_records.csv
platform_operation_approval_summary.csv
platform_operation_approval_report.html
```

CSV 用于机器检查和后续分析；HTML 用于人工查看。HTML 会转义 `approval_id`、`operation_id`、`requested_by`、`request_reason`、`approved_by`、`approval_reason` 和 `decision_reason` 等用户可控字段。

## 第一版不做

- 不新增 HTTP endpoint。
- 不新增数据库表。
- 不改变 `OperationApprovalRecord` schema。
- 不改变 retry API 的审批校验。
- 不实现 pending approval。
- 不实现多级审批。
- 不把 approval report 接入 console。

## 实现进度

第一版已完成。

新增模块：

```text
platform_operation_approval_report.py
```

核心对象：

```text
OperationApprovalReportSummary
OperationApprovalReport
OperationApprovalReportExportPaths
```

核心函数：

```text
build_operation_approval_report()
export_operation_approval_report()
```

demo 已接入 `export_operation_approval_report()`，会在输出 `Operation approval records` 后继续输出：

```text
Exported operation approval reports
```

并生成三份 approval report 文件。

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval_report.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operation_approval.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_operation_approval_report.py: 3 passed
test_platform_operation_approval.py: 4 passed
test_platform_api_app.py: 23 passed
demo 可运行，并输出 Exported operation approval reports
labs/fintech-platform: 106 passed
labs: 351 passed
```

## 后续候选方向

阶段 15 完成后，可以选择：

1. 把 operations report 或 approval report 接入只读 console。
2. 为 approval record 增加 pending / approved / rejected 状态流转。
3. 做更深入的 ledger reconciliation。
4. 继续整理历史阶段文档，减少阅读噪音。
