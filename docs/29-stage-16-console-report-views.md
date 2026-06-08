# 阶段 16：Console Report Views

最后更新：2026-06-08

阶段 16 承接阶段 13 和阶段 15。阶段 13 已经有离线 operations report；阶段 15 已经有离线 operation approval report。阶段 16 的目标不是再新增报表文件，而是把这两类报表的核心观察结果接入现有 `FinTech Platform Console`，让运营人员在一个只读页面里同时看到任务状态、对账摘要和审批摘要。

本阶段仍然只新增一篇阶段文档，把计划、实现进度和验证记录放在一起。

## 中文定义

Console report views，是把离线报表的核心摘要嵌入运营控制台的只读视图。

对应英文术语：

- console report views
- operations report summary
- approval report summary
- read-only operations console
- operational observability

## 为什么需要接入 console

离线 CSV/HTML 报表适合审计留档和批量分析，但运营人员处理 failed async run 时，通常先看控制台：

```text
任务是否失败
失败是否已经 retry
retry 是否有审批记录
当前是否还有对账 warning
```

把 summary 接入 console 后，可以在不下载报表文件的情况下看到：

1. async run 和 platform run 的总量关系。
2. retry granted / denied 数量。
3. reconciliation finding 数量。
4. approval record 总量、approved / rejected 分布。
5. 最近的 approval records。

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
docs/29-stage-16-console-report-views.md
```

## 页面新增区块

`GET /platform/view` 现在新增：

```text
Operations Report Summary
Operation Approval Summary
Operations Run Rows
Approval Records
```

这些区块复用已有 builder：

```text
build_platform_operations_report()
build_operation_approval_report()
```

控制台只显示内存中构造出的 summary 和最近记录，不写出新的 CSV/HTML 文件。

## 第一版不做

- 不新增下载按钮。
- 不新增 HTTP report endpoint。
- 不新增数据库表。
- 不改变 retry API。
- 不改变 operation approval schema。
- 不把 console 做成完整前端项目。
- 不实现分页、搜索、权限和真实 IAM。

## 响应式约定

本次只在现有服务端 HTML 上做小范围增强：

- 页面继续使用单文件内联 CSS。
- metric summary 使用流式 grid。
- 报表 summary 在小屏单列展示，在宽屏两列展示。
- 宽表继续用横向滚动容器承载，避免移动端内容互相覆盖。
- 表单控件保持至少 44px 高度。

## 实现进度

第一版已完成。

`platform_api_app.py` 现在会在渲染 console 时读取：

```text
SQLitePlatformStore
SQLitePlatformAsyncRunStore
SQLiteAccessAuditStore
SQLiteOperationApprovalStore
```

然后构造：

```text
PlatformOperationsReport
OperationApprovalReport
```

并把 summary 和最近记录嵌入 `FinTech Platform Console`。

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py::test_platform_console_renders_operations_and_approval_report_views -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operations_report.py .\labs\fintech-platform\test_platform_operation_approval_report.py -q
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
test_platform_console_renders_operations_and_approval_report_views: 1 passed
test_platform_api_app.py: 24 passed
test_platform_operations_report.py + test_platform_operation_approval_report.py: 8 passed
demo 可运行
labs/fintech-platform: 107 passed
labs: 352 passed
```

## 后续候选方向

阶段 16 完成后，可以选择：

1. 做更深入的 ledger reconciliation。
2. 为 approval record 增加 pending / approved / rejected 状态流转。
3. 给 console 增加只读筛选和分页。
4. 继续整理历史阶段文档，减少阅读噪音。
