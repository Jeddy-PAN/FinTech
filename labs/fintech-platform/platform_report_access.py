from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


LABS_DIR = Path(__file__).resolve().parents[1]
COMPLIANCE_LAB_DIR = LABS_DIR / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import (  # noqa: E402
    AuditAccessRecorder,
    AuditExportApproval,
    AuditUser,
    APPROVE_AUDIT_EXPORT,
    ComplianceAuditError,
    EXPORT_AUDIT_REPORT,
    authorize_user,
    authorize_user_with_audit,
)
from fintech_platform import PlatformPaymentResult  # noqa: E402
from platform_consistency_report import (  # noqa: E402
    PlatformConsistencyReportExportPaths,
    export_platform_consistency_report,
)
from platform_history_report_export import (  # noqa: E402
    PlatformHistoryReportExportPaths,
    export_platform_history_report,
)
from platform_report_export import PlatformReportExportPaths, export_platform_report  # noqa: E402
from sqlite_platform_store import PlatformRunSnapshot  # noqa: E402


PLATFORM_PAYMENT_REPORT_TARGET = "fintech_platform_payment_report"
PLATFORM_HISTORY_REPORT_TARGET = "fintech_platform_history_report"
PLATFORM_CONSISTENCY_REPORT_TARGET = "fintech_platform_consistency_report"


def export_platform_report_with_access(
    output_directory: str | Path,
    *,
    result: PlatformPaymentResult,
    requested_by: AuditUser,
    accessed_at: datetime,
    access_recorder: AuditAccessRecorder | None = None,
    require_approval: bool = False,
    approval: AuditExportApproval | None = None,
) -> PlatformReportExportPaths:
    _authorize_platform_report_export(
        requested_by=requested_by,
        accessed_at=accessed_at,
        access_recorder=access_recorder,
        target=PLATFORM_PAYMENT_REPORT_TARGET,
        require_approval=require_approval,
        approval=approval,
    )
    return export_platform_report(output_directory, result=result)


def export_platform_history_report_with_access(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
    requested_by: AuditUser,
    accessed_at: datetime,
    access_recorder: AuditAccessRecorder | None = None,
    require_approval: bool = False,
    approval: AuditExportApproval | None = None,
) -> PlatformHistoryReportExportPaths:
    _authorize_platform_report_export(
        requested_by=requested_by,
        accessed_at=accessed_at,
        access_recorder=access_recorder,
        target=PLATFORM_HISTORY_REPORT_TARGET,
        require_approval=require_approval,
        approval=approval,
    )
    return export_platform_history_report(output_directory, snapshots=snapshots)


def export_platform_consistency_report_with_access(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
    requested_by: AuditUser,
    accessed_at: datetime,
    access_recorder: AuditAccessRecorder | None = None,
    require_approval: bool = False,
    approval: AuditExportApproval | None = None,
) -> PlatformConsistencyReportExportPaths:
    _authorize_platform_report_export(
        requested_by=requested_by,
        accessed_at=accessed_at,
        access_recorder=access_recorder,
        target=PLATFORM_CONSISTENCY_REPORT_TARGET,
        require_approval=require_approval,
        approval=approval,
    )
    return export_platform_consistency_report(output_directory, snapshots=snapshots)


def _authorize_platform_report_export(
    *,
    requested_by: AuditUser,
    accessed_at: datetime,
    access_recorder: AuditAccessRecorder | None,
    target: str,
    require_approval: bool,
    approval: AuditExportApproval | None,
) -> None:
    if access_recorder is not None:
        authorize_user_with_audit(
            requested_by,
            EXPORT_AUDIT_REPORT,
            recorder=access_recorder,
            target=target,
            occurred_at=accessed_at,
        )
    else:
        authorize_user(requested_by, EXPORT_AUDIT_REPORT)
    if require_approval:
        _validate_platform_export_approval(
            requested_by=requested_by,
            approval=approval,
            recorder=access_recorder,
            target=target,
        )


def _validate_platform_export_approval(
    *,
    requested_by: AuditUser,
    approval: AuditExportApproval | None,
    recorder: AuditAccessRecorder | None,
    target: str,
) -> None:
    if approval is None:
        raise ComplianceAuditError("Export approval is required")
    if approval.approved_at.tzinfo is None or approval.approved_at.utcoffset() is None:
        raise ComplianceAuditError("approved_at must be timezone-aware")
    reason = approval.reason.strip()
    if not reason:
        raise ComplianceAuditError("Export approval reason is required")
    if approval.approved_by.user_id == requested_by.user_id:
        error = ComplianceAuditError("Export approver must differ from requester")
        if recorder is not None:
            recorder.record(
                event_type="audit_export_approval.denied",
                actor=approval.approved_by.user_id,
                permission=APPROVE_AUDIT_EXPORT,
                target=target,
                outcome="denied",
                occurred_at=approval.approved_at,
                reason=str(error),
            )
        raise error
    if recorder is not None:
        authorize_user_with_audit(
            approval.approved_by,
            APPROVE_AUDIT_EXPORT,
            recorder=recorder,
            target=f"{target}.approval",
            occurred_at=approval.approved_at,
        )
        recorder.record(
            event_type="audit_export_approval.granted",
            actor=approval.approved_by.user_id,
            permission=APPROVE_AUDIT_EXPORT,
            target=target,
            outcome="granted",
            occurred_at=approval.approved_at,
            reason=reason,
        )
    else:
        authorize_user(approval.approved_by, APPROVE_AUDIT_EXPORT)
