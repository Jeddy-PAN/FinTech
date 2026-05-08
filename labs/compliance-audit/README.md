# Compliance Audit

这是第七个 FinTech 代码实验：把风控和 KYC/AML 实验中的审计事件统一成一个只读视图，用来理解 audit trail、主体时间线、筛选和最小脱敏。

配套文档：[../../docs/16-compliance-audit.md](../../docs/16-compliance-audit.md)

## 当前功能

- 读取风控实验的 `risk_audit_events`。
- 读取 KYC/AML 实验的 `kyc_audit_events`。
- 统一成 `ComplianceAuditEvent`。
- 按来源系统、事件类型、事件前缀、主体、操作人和时间窗口筛选。
- 为一个主体构造跨系统 audit timeline。
- 汇总来源系统、事件类型和操作人数量。
- 对 JSON payload 中常见 PII 字段做教学版脱敏。
- 导出审计事件 CSV、主体时间线 CSV、审计汇总 CSV 和 HTML 报告。
- 使用教学版角色权限控制查看事件、查看 payload 和导出报表。
- 可选要求另一名具备审批权限的用户审批审计报告导出，演示职责分离。
- 记录教学版访问审计事件，用于追踪谁查看了事件、谁查看了 payload、谁导出了报表。
- 使用 SQLite 保存访问审计事件，并按操作人、权限、结果和时间窗口查询。

## 运行示例

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\compliance-audit\demo.py
```

## 运行测试

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\compliance-audit
```
