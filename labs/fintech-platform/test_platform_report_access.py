from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import (
    AuditAccessRecorder,
    AuditExportApproval,
    AuditUser,
    ComplianceAuditError,
)
from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_report_access import (
    export_platform_consistency_report_with_access,
    export_platform_history_report_with_access,
    export_platform_report_with_access,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore
from sqlite_platform_store import SQLitePlatformStore


def test_platform_report_export_requires_manager_export_permission() -> None:
    output_directory = _output_directory()

    try:
        with pytest.raises(ComplianceAuditError, match="export_audit_report"):
            export_platform_report_with_access(
                output_directory,
                result=_completed_result(),
                requested_by=AuditUser("viewer_001", ("audit_viewer",)),
                accessed_at=_accessed_at(),
            )

        paths = export_platform_report_with_access(
            output_directory,
            result=_completed_result(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            accessed_at=_accessed_at(),
        )

        assert paths.html_report.exists()
    finally:
        _remove_directory(output_directory)


def test_platform_report_export_records_denied_and_granted_access() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        with pytest.raises(ComplianceAuditError):
            export_platform_report_with_access(
                output_directory,
                result=_completed_result(),
                requested_by=AuditUser("viewer_001", ("audit_viewer",)),
                access_recorder=recorder,
                accessed_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            )
        paths = export_platform_report_with_access(
            output_directory,
            result=_completed_result(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 18, 12, 5, tzinfo=timezone.utc),
        )

        assert paths.result_csv.exists()
        assert [event.event_type for event in recorder.events] == [
            "audit_access.denied",
            "audit_access.granted",
        ]
        assert recorder.events[0].target == "fintech_platform_payment_report"
        assert recorder.events[1].target == "fintech_platform_payment_report"
    finally:
        _remove_directory(output_directory)


def test_platform_history_and_consistency_exports_record_access() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()
    snapshots = _snapshots()

    try:
        history_paths = export_platform_history_report_with_access(
            output_directory,
            snapshots=snapshots,
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 18, 12, 10, tzinfo=timezone.utc),
        )
        consistency_paths = export_platform_consistency_report_with_access(
            output_directory,
            snapshots=snapshots,
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 18, 12, 15, tzinfo=timezone.utc),
        )

        assert history_paths.html_report.exists()
        assert consistency_paths.html_report.exists()
        assert [event.target for event in recorder.events] == [
            "fintech_platform_history_report",
            "fintech_platform_consistency_report",
        ]
    finally:
        _remove_directory(output_directory)


def test_platform_report_export_can_require_separate_approval() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        paths = export_platform_report_with_access(
            output_directory,
            result=_completed_result(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            require_approval=True,
            approval=AuditExportApproval(
                approved_by=AuditUser("manager_002", ("audit_manager",)),
                approved_at=datetime(2026, 5, 18, 12, 5, tzinfo=timezone.utc),
                reason="Approved sample platform report export",
            ),
        )

        assert paths.html_report.exists()
        assert [event.event_type for event in recorder.events] == [
            "audit_access.granted",
            "audit_access.granted",
            "audit_export_approval.granted",
        ]
        assert recorder.events[-1].actor == "manager_002"
    finally:
        _remove_directory(output_directory)


def test_platform_report_export_rejects_self_approval() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        with pytest.raises(ComplianceAuditError, match="approver must differ"):
            export_platform_report_with_access(
                output_directory,
                result=_completed_result(),
                requested_by=AuditUser("manager_001", ("audit_manager",)),
                access_recorder=recorder,
                accessed_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
                require_approval=True,
                approval=AuditExportApproval(
                    approved_by=AuditUser("manager_001", ("audit_manager",)),
                    approved_at=datetime(2026, 5, 18, 12, 5, tzinfo=timezone.utc),
                    reason="Self approval should fail",
                ),
            )

        assert recorder.events[-1].event_type == "audit_export_approval.denied"
        assert recorder.events[-1].outcome == "denied"
    finally:
        _remove_directory(output_directory)


def test_platform_report_access_events_can_be_persisted() -> None:
    output_directory = _output_directory()
    access_database_path = _test_data_directory() / f"access-audit-{uuid4()}.db"
    recorder = AuditAccessRecorder.create()
    access_store = SQLiteAccessAuditStore(access_database_path)

    try:
        export_platform_report_with_access(
            output_directory,
            result=_completed_result(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
        )
        access_store.save_events(recorder.events)

        persisted_events = access_store.query_access_events(
            actor="manager_001",
            permission="export_audit_report",
            outcome="granted",
        )
        assert len(persisted_events) == 1
        assert persisted_events[0].target == "fintech_platform_payment_report"
    finally:
        access_store.close()
        if access_database_path.exists():
            access_database_path.unlink()
        _remove_directory(output_directory)


def _snapshots():
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            _completed_result(order_id="order_completed"),
            run_id="run_completed",
            created_at=_requested_at(),
        )
        return (store.get_run("run_completed"),)
    finally:
        store.close()


def _completed_result(order_id: str = "order_001"):
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id=order_id,
            requested_at=_requested_at(),
        )
    )


def _approved_application():
    return build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )


def _requested_at() -> datetime:
    return datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)


def _accessed_at() -> datetime:
    return datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)


def _database_path() -> Path:
    return _test_data_directory() / f"platform-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"report-access-{uuid4()}"
    directory.mkdir()
    return directory


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
