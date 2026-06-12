# 阶段 38：合规证据、调查工单和留存治理

本阶段把前面已经形成的 access audit、operation approval、settlement reconciliation 和 investigation case 串成一个教学版 evidence package。目标是学习“证据如何组织、如何导出、如何和调查工单/留存策略发生关系”，不是声明真实监管要求、真实留存期限或法律意见。

## 1. 基础概念

### 中文定义

- 证据 evidence：能解释某个风险、异常、审批或对账差异的结构化记录。
- 证据包 evidence package：围绕一个 case 或 review 目标，把多类证据项按统一格式整理成可审查材料。
- legal hold：因为调查、争议或法律原因，暂时禁止删除相关记录的治理标记。
- retention：记录留存策略，说明记录应保持 active、archive、delete due 或 held。

### 英文术语

- evidence
- evidence package
- legal hold
- retention policy
- investigation case
- audit trail

### 为什么金融系统需要它

单条日志不能独立解释复杂问题。比如一次异常访问、一次 retry approval、一次外部 settlement mismatch，往往需要把 access audit、approval record、reconciliation finding 和 investigation case 放在一起看。证据包的价值是：

1. 让调查人员知道哪些材料支撑结论。
2. 让审批、对账和访问审计之间能互相引用。
3. 让导出材料有统一格式，方便复核。
4. 让 legal hold / retention 的教学边界更清晰。

## 2. 本阶段实现

新增文件：

```text
labs/fintech-platform/platform_evidence_package.py
labs/fintech-platform/test_platform_evidence_package.py
```

新增核心对象：

```text
PlatformEvidenceItem
PlatformEvidencePackage
PlatformEvidencePackageExportPaths
```

`build_platform_evidence_package()` 支持合并这些输入：

| 输入 | 进入证据包的规则 |
| --- | --- |
| `PlatformSettlementReconciliationFinding` | 只收集 failed settlement findings |
| `AccessAnomalyFinding` | 收集 access anomaly finding |
| `OperationApprovalRecord` | 收集 approval record，approved 视作 high severity |
| `AuditAccessEvent` | 只收集 denied access events |

当前 evidence item 字段：

```text
evidence_id
evidence_type
source_system
subject_id
severity
summary
recorded_at
reference
```

## 3. 导出

新增导出：

```text
platform_evidence_package_items.csv
platform_evidence_package_summary.csv
platform_evidence_package_report.html
```

`demo.py` 已接入 `Exported platform evidence package`，把阶段 37 的 settlement findings、operation approval records、platform access anomaly findings、platform API access anomaly findings 和 access audit events 汇总成一个教学版 evidence package。

## 4. 当前边界

本阶段仍不实现：

- 真实监管证据清单。
- 真实 legal hold 审批流程。
- 真实记录留存期限。
- 不可篡改日志、WORM 存储或电子签名。
- 附件上传、文件哈希校验或证据链 custody 流程。
- 真实工单 comment、SLA、priority、升级路径。

如果后续要讨论具体监管留存期限、报送要求、法律保全、电子签名或 WORM 存储，需要查证官方或专业来源。本阶段只保留工程学习抽象。

## 5. 已完成代码与测试

本阶段修改：

```text
labs/fintech-platform/platform_evidence_package.py
labs/fintech-platform/test_platform_evidence_package.py
labs/fintech-platform/demo.py
```

已验证：

```text
py_compile: passed
test_platform_evidence_package.py: 4 passed
evidence + settlement + investigation related tests: 16 passed
labs/fintech-platform: 161 passed
demo.py: runnable, exported evidence package CSV/HTML
labs: 406 passed
```

后续建议阶段 39 进入可运行交付、观测和测试矩阵：把当前平台如何启动、测试、演示、观测和验收整理成更接近工程交付的形态。
