# 阶段 13：运行报告与对账视角设计和实现计划

最后更新：2026-06-04

阶段 13 承接阶段 12。当前平台已经能创建同步 payment run、创建 async run、手动触发 worker、查询任务状态、retry failed async run，并把关键 API 操作写入 access audit。

阶段 13 的目标不是新增业务流程，而是补一个运营和对账视角：把 async run、最终 platform result、ledger posting 和 access audit 放到同一份可复核报告中，回答以下问题：

```text
今天系统接收了哪些任务？
哪些任务完成了？
哪些任务失败了？
完成的任务是否有最终业务结果？
完成的业务结果是否真的有账本入账记录？
高影响操作 retry 是否有 granted / denied 审计记录？
```

本阶段仍然是教学版，不实现真实日切、真实清算、真实银行对账、监管报送、调度系统或下载权限。报告只基于当前仓库已有的 SQLite store 和内存对象。

## 中文定义

运行报告，是面向运营人员和工程人员的系统处理结果汇总。

对账视角，是把多个系统或多个状态来源放到一起，检查它们是否互相解释得通。

对应英文术语：

- operations report
- reconciliation
- run summary
- exception report
- ledger reconciliation
- audit reconciliation

在本仓库里，阶段 13 的最小对账对象是：

```text
PlatformAsyncRun
PlatformRunSnapshot
ledger_transaction.posted audit event
retry_platform_async_run access audit
```

## 为什么金融系统需要它

金融系统不能只看“接口返回成功”。后台还需要能回答：

1. 请求有没有被接收。
2. 异步任务有没有被 worker 处理。
3. 业务结果有没有落盘。
4. 完成的支付有没有账本入账。
5. 人工 retry 有没有审计记录。
6. 失败任务是否仍然停留在待处理状态。

这些问题就是日终运营、异常处理和对账的入口。生产系统会更复杂，会涉及支付通道、银行流水、总账、子账、清算批次和人工差错处理。本阶段先用教学版数据结构把思路讲清楚。

## 当前基础

当前已有能力：

```text
SQLitePlatformAsyncRunStore.runs
SQLitePlatformStore.runs
SQLitePlatformStore.get_run(run_id)
SQLiteAccessAuditStore.access_events
platform_history_report_export.py
platform_consistency_report.py
```

已有报表更偏两个方向：

1. `platform_history_report_export.py`：记录发生过哪些 platform runs 和 audit events。
2. `platform_consistency_report.py`：检查单个 platform run 的状态、ledger id 和 audit events 是否自洽。

阶段 13 要补的是横向运营视角：同一个 `run_id` 在 async run、platform result、ledger posting 和 retry audit 中是否能串起来。

## 第一版范围

新增文件：

```text
labs/fintech-platform/platform_operations_report.py
labs/fintech-platform/test_platform_operations_report.py
```

更新文件：

```text
labs/fintech-platform/demo.py
labs/fintech-platform/README.md
README.md
LEARNING_PROGRESS.md
```

生成报告：

```text
labs/fintech-platform/reports/platform_operations_run_report.csv
labs/fintech-platform/reports/platform_operations_reconciliation_findings.csv
labs/fintech-platform/reports/platform_operations_report.html
```

## 报告模型

第一版使用纯 Python dataclass，不新增 SQLite 表。

建议对象：

```text
PlatformOperationsReport
PlatformOperationsSummary
PlatformOperationsRunRow
PlatformOperationsFinding
PlatformOperationsReportExportPaths
```

`PlatformOperationsRunRow` 用于展示每个 `run_id` 的横向状态：

```text
run_id
async_status
platform_status
payment_order_status
ledger_transaction_id
attempt_count
max_attempts
last_error
retry_granted_count
retry_denied_count
reconciliation_status
```

`PlatformOperationsFinding` 用于记录对账检查结果：

```text
run_id
check_id
status
severity
message
```

## 第一版检查规则

第一版只做明确、稳定、可教学的规则：

1. `completed` async run 必须有同 `run_id` 的 platform result。
2. `failed` async run 必须进入 report，并生成 warning finding，提示需要运营复核。
3. `completed` platform run 必须有 `ledger_transaction_id`。
4. platform run 如果有 `ledger_transaction_id`，audit events 里必须有匹配的 `ledger_transaction.posted`。
5. retry access audit 按 `retry_platform_async_run` 统计 granted / denied 次数，并按 target 关联到 `run_id`。

这些规则不会尝试判断真实资金是否清算，也不会读取底层账本数据库逐笔核对。那是后续阶段。

## 当前不做

阶段 13 第一版不做：

- 新增 HTTP endpoint。
- 改造 `FinTech Platform Console`。
- 新增真实导出权限。
- 新增 approval table。
- 新增调度器或日切任务。
- 接入真实银行流水、支付通道流水或总账。
- 修改现有 async run、platform run、access audit 的 SQLite schema。

## 实现计划

> 本计划直接放在阶段文档中，避免为一个小阶段再拆出多个细碎文档。用户已明确不需要 AI 代做 git 操作，因此所有步骤都不包含 git add、commit 或 checkout。

### 任务 1：写运行报告核心测试

文件：

```text
labs/fintech-platform/test_platform_operations_report.py
```

测试目标：

1. completed async run 缺少 platform result 时生成 failed finding。
2. failed async run 出现在 run rows 中，并生成 warning finding。
3. retry granted / denied access audit 能按 run_id 统计。
4. completed platform run 缺少 ledger id 或缺少 matching ledger event 时生成 failed finding。

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operations_report.py -q
```

预期 RED：

```text
ModuleNotFoundError: No module named 'platform_operations_report'
```

### 任务 2：实现 `platform_operations_report.py`

文件：

```text
labs/fintech-platform/platform_operations_report.py
```

实现内容：

1. 定义 report dataclass。
2. 实现 `build_platform_operations_report(async_runs, snapshots, access_events)`。
3. 实现 retry audit target 到 `run_id` 的解析。
4. 实现 completed async run、failed async run、completed platform run 和 ledger event 检查。
5. 给每个 run row 计算 `reconciliation_status`：有 error finding 为 `failed`，只有 warning 为 `warning`，否则为 `passed`。

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operations_report.py -q
```

预期 GREEN：

```text
3 passed
```

### 任务 3：实现 CSV/HTML 导出

文件：

```text
labs/fintech-platform/platform_operations_report.py
labs/fintech-platform/test_platform_operations_report.py
```

新增函数：

```text
export_platform_operations_report(output_directory, async_runs, snapshots, access_events)
```

输出：

```text
platform_operations_run_report.csv
platform_operations_reconciliation_findings.csv
platform_operations_report.html
```

测试目标：

1. 三个文件都生成。
2. CSV 包含 run row 和 finding header。
3. HTML 包含 summary、run rows 和 findings。
4. HTML 会转义用户可控字段。

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operations_report.py -q
```

### 任务 4：接入 demo

文件：

```text
labs/fintech-platform/demo.py
```

实现内容：

1. 从 `demo_platform_runs.db` 读取 platform snapshots。
2. 从 `demo_platform_async_runs.db` 读取 async runs。
3. 从 `demo_platform_api_access_audit.db` 读取 async/API access audit events。
4. 调用 `export_platform_operations_report()`。
5. 在 demo 输出中打印三个新报告路径。

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
```

### 任务 5：更新入口文档和进度

文件：

```text
README.md
labs/fintech-platform/README.md
LEARNING_PROGRESS.md
docs/26-stage-13-operations-reconciliation-report.md
```

更新内容：

1. 当前阶段改为阶段 13 第一版已完成。
2. 学习顺序新增运行报告观察项。
3. `labs/fintech-platform/README.md` 增加新报告文件说明。
4. `LEARNING_PROGRESS.md` 增加历史记录。
5. 本文档增加实现进度和验证记录。

### 任务 6：最终验证

验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

验收标准：

1. `test_platform_operations_report.py` 通过。
2. `labs/fintech-platform` 通过。
3. 全量 `labs` 通过。
4. demo 可运行并生成阶段 13 报告。
5. 未做任何 git 操作。

## 实现进度

第一版已完成。

新增代码：

```text
labs/fintech-platform/platform_operations_report.py
labs/fintech-platform/test_platform_operations_report.py
```

已接入 demo：

```text
labs/fintech-platform/demo.py
```

demo 会读取：

```text
labs/fintech-platform/.test-data/demo_platform_runs.db
labs/fintech-platform/.test-data/demo_platform_async_runs.db
labs/fintech-platform/.test-data/demo_platform_api_access_audit.db
```

并导出：

```text
labs/fintech-platform/reports/platform_operations_run_report.csv
labs/fintech-platform/reports/platform_operations_reconciliation_findings.csv
labs/fintech-platform/reports/platform_operations_report.html
```

第一版 `PlatformOperationsRunRow` 会展示：

```text
run_id
async_status
platform_status
payment_order_status
ledger_transaction_id
attempt_count
max_attempts
last_error
retry_granted_count
retry_denied_count
reconciliation_status
```

第一版 `PlatformOperationsFinding` 会覆盖：

1. `completed_async_has_platform_result`
2. `failed_async_run_requires_review`
3. `completed_platform_has_ledger_transaction`
4. `ledger_transaction_has_posted_event`

## 验证记录

截至 2026-06-08，已确认：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_operations_report.py -q
```

结果：

```text
5 passed
```

本阶段收尾验证：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\fintech-platform\demo.py
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -q
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -q
```

结果：

```text
demo 可运行，并生成三份 platform operations reports
labs/fintech-platform: 99 passed
labs: 344 passed
```

## 后续候选方向

阶段 13 完成后，可以选择：

1. 把 approval 从 access audit reason 拆成独立 operation approval record。
2. 把运行报告接入只读 console。
3. 引入真实 ledger store 查询，做更接近会计对账的检查。
4. 做文档整理阶段，减少 docs 入口噪音。
