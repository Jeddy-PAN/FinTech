from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessRecorder, AuditExportApproval, AuditUser
from compliance_investigation_cases import AccessAnomalyInvestigationService
from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_access_anomaly_report import (
    detect_platform_report_access_anomalies,
    export_platform_access_anomaly_report,
)
from platform_investigation_cases import (
    export_platform_access_investigation_report,
    open_platform_access_investigation_cases,
)
from platform_report_access import (
    export_platform_consistency_report_with_access,
    export_platform_history_report_with_access,
    export_platform_report_with_access,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore
from sqlite_platform_store import SQLitePlatformStore


def main() -> None:
    platform = FinTechPlatform()
    application = build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )
    result = platform.process_payment(
        PlatformPaymentRequest(
            application=application,
            amount="100.00",
            currency="USD",
            order_id="order_001",
            requested_at=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
            device_id="device_known",
            ip_country="US",
            beneficiary_id="beneficiary_001",
        )
    )

    print("FinTech Platform Demo")
    print(f"- Platform status: {result.status.value}")
    print(f"- KYC decision: {result.kyc_decision.status.value}")
    if result.payment_order is not None:
        print(
            f"- Payment order: {result.payment_order.id} "
            f"status={result.payment_order.status.value}"
        )
    if result.risk_decision is not None:
        print(
            f"- Risk decision: {result.risk_decision.status.value} "
            f"score={result.risk_decision.risk_score}"
        )
    print(f"- Ledger transaction: {result.ledger_transaction_id}")
    print(f"- Platform bank balance: {result.platform_bank_balance}")
    print(f"- User wallet balance: {result.user_wallet_balance}")

    manager = AuditUser("manager_001", ("audit_manager",))
    approver = AuditUser("manager_002", ("audit_manager",))
    access_recorder = AuditAccessRecorder.create()

    print("\nCustomer audit timeline")
    for event in result.customer_timeline.events:
        print(
            f"- {event.occurred_at.isoformat()} "
            f"{event.source_system}:{event.event_type} "
            f"aggregate={event.aggregate_type}/{event.aggregate_id}"
        )

    print("\nAudit summary")
    print(f"- Total events: {result.audit_summary.total_events}")
    for source_system, count in result.audit_summary.source_system_counts:
        print(f"- {source_system}: {count}")

    report_paths = export_platform_report_with_access(
        LAB_DIR / "reports",
        result=result,
        requested_by=manager,
        access_recorder=access_recorder,
        accessed_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
        require_approval=True,
        approval=AuditExportApproval(
            approved_by=approver,
            approved_at=datetime(2026, 5, 18, 12, 5, tzinfo=timezone.utc),
            reason="Approved sample platform payment report export",
        ),
    )
    print("\nExported platform reports:")
    print(f"- {report_paths.result_csv}")
    print(f"- {report_paths.timeline_csv}")
    print(f"- {report_paths.html_report}")

    database_path = LAB_DIR / ".test-data" / "demo_platform_runs.db"
    database_path.parent.mkdir(exist_ok=True)
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            result,
            run_id="run_demo_001",
            created_at=datetime(2026, 5, 18, 9, 10, tzinfo=timezone.utc),
        )
    finally:
        store.close()

    review_platform = FinTechPlatform()
    review_result = review_platform.process_payment(
        PlatformPaymentRequest(
            application=application,
            amount="1500.00",
            currency="USD",
            order_id="order_review_001",
            requested_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        )
    )
    completed_review = review_platform.approve_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Verified customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 30, tzinfo=timezone.utc),
    )
    print("\nRisk review completion")
    print(f"- Initial status: {review_result.status.value}")
    print(f"- Completed status: {completed_review.status.value}")
    print(f"- Payment order: {completed_review.payment_order.id if completed_review.payment_order else ''}")
    print(f"- Ledger transaction: {completed_review.ledger_transaction_id}")

    rejected_review_platform = FinTechPlatform()
    rejected_review_result = rejected_review_platform.process_payment(
        PlatformPaymentRequest(
            application=application,
            amount="1500.00",
            currency="USD",
            order_id="order_review_rejected_001",
            requested_at=datetime(2026, 5, 18, 11, 0, tzinfo=timezone.utc),
        )
    )
    rejected_review = rejected_review_platform.reject_risk_review(
        rejected_review_result,
        reviewed_by="risk_manager_001",
        reason="Could not verify customer activity",
        reviewed_at=datetime(2026, 5, 18, 11, 30, tzinfo=timezone.utc),
    )
    print("\nRisk review rejection")
    print(f"- Initial status: {rejected_review_result.status.value}")
    print(f"- Rejected status: {rejected_review.status.value}")
    print(f"- Payment order: {rejected_review.payment_order.id if rejected_review.payment_order else ''}")
    print(f"- Ledger transaction: {rejected_review.ledger_transaction_id}")

    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            completed_review,
            run_id="run_demo_review_approved",
            created_at=datetime(2026, 5, 18, 10, 40, tzinfo=timezone.utc),
        )
        store.save_result(
            rejected_review,
            run_id="run_demo_review_rejected",
            created_at=datetime(2026, 5, 18, 11, 40, tzinfo=timezone.utc),
        )
        snapshot = store.get_run("run_demo_001")
        print("\nPersisted platform run")
        print(f"- Run id: {snapshot.record.run_id}")
        print(f"- Status: {snapshot.record.status}")
        print(f"- Customer id: {snapshot.record.customer_id}")
        print(f"- Payment order: {snapshot.record.payment_order_id}")
        print(f"- Audit events: {len(snapshot.audit_events)}")

        snapshots = tuple(store.get_run(record.run_id) for record in store.runs)
        history_paths = export_platform_history_report_with_access(
            LAB_DIR / "reports",
            snapshots=snapshots,
            requested_by=manager,
            access_recorder=access_recorder,
            accessed_at=datetime(2026, 5, 18, 12, 10, tzinfo=timezone.utc),
        )
        print("\nExported platform run history reports:")
        print(f"- {history_paths.runs_csv}")
        print(f"- {history_paths.audit_events_csv}")
        print(f"- {history_paths.html_report}")

        consistency_paths = export_platform_consistency_report_with_access(
            LAB_DIR / "reports",
            snapshots=snapshots,
            requested_by=manager,
            access_recorder=access_recorder,
            accessed_at=datetime(2026, 5, 18, 12, 15, tzinfo=timezone.utc),
        )
        print("\nExported platform consistency reports:")
        print(f"- {consistency_paths.findings_csv}")
        print(f"- {consistency_paths.html_report}")
    finally:
        store.close()

    access_audit_database_path = LAB_DIR / ".test-data" / "demo_platform_access_audit.db"
    if access_audit_database_path.exists():
        access_audit_database_path.unlink()
    access_audit_store = SQLiteAccessAuditStore(access_audit_database_path)
    try:
        _seed_sample_platform_access_anomalies(access_recorder)
        access_audit_store.save_events(access_recorder.events)
        print("\nPlatform report access audit events")
        for event in access_audit_store.query_access_events(
            permission="export_audit_report",
            outcome="granted",
        ):
            print(
                f"- {event.occurred_at.isoformat()} actor={event.actor} "
                f"target={event.target} outcome={event.outcome}"
            )
        platform_findings = detect_platform_report_access_anomalies(
            access_audit_store.access_events,
        )
        print("\nPlatform access anomaly findings")
        for finding in platform_findings:
            print(
                f"- {finding.finding_type} actor={finding.actor} "
                f"severity={finding.severity} event_count={finding.event_count} "
                f"target={finding.events[0].target}"
            )
        platform_anomaly_paths = export_platform_access_anomaly_report(
            LAB_DIR / "reports",
            findings=platform_findings,
        )
        print("Exported platform access anomaly reports:")
        print(f"- {platform_anomaly_paths.findings_csv}")
        print(f"- {platform_anomaly_paths.html_report}")

        investigation_service = AccessAnomalyInvestigationService()
        investigation_cases = open_platform_access_investigation_cases(
            platform_findings,
            opened_by="platform_compliance_lead_001",
            created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
            service=investigation_service,
        )
        if investigation_cases:
            first_case = investigation_cases[0]
            investigation_service.start_investigation(
                first_case.case_id,
                assigned_to="platform_investigator_001",
                started_at=datetime(2026, 5, 18, 13, 10, tzinfo=timezone.utc),
            )
            investigation_service.resolve(
                first_case.case_id,
                closed_by="platform_investigator_001",
                reason="Reviewed sample platform access anomaly",
                closed_at=datetime(2026, 5, 18, 14, 0, tzinfo=timezone.utc),
            )

        print("\nPlatform access investigation cases")
        for investigation_case in investigation_service.cases:
            print(
                f"- {investigation_case.case_id} "
                f"status={investigation_case.status} "
                f"actor={investigation_case.finding.actor}"
            )

        investigation_database_path = (
            LAB_DIR / ".test-data" / "demo_platform_investigation_cases.db"
        )
        if investigation_database_path.exists():
            investigation_database_path.unlink()
        investigation_store = SQLiteInvestigationCaseStore(investigation_database_path)
        try:
            for investigation_case in investigation_service.cases:
                investigation_store.save_case(investigation_case)

            print("\nPersisted open platform investigation cases")
            for investigation_case in investigation_store.open_cases:
                print(
                    f"- {investigation_case.case_id} "
                    f"status={investigation_case.status} "
                    f"actor={investigation_case.finding.actor}"
                )
        finally:
            investigation_store.close()

        investigation_paths = export_platform_access_investigation_report(
            LAB_DIR / "reports",
            cases=investigation_service.cases,
        )
        print("Exported platform access investigation reports:")
        print(f"- {investigation_paths.cases_csv}")
        print(f"- {investigation_paths.html_report}")

        print("\nPlatform investigation case audit events")
        for event in investigation_service.audit_events:
            print(
                f"- {event.occurred_at.isoformat()} "
                f"{event.event_type} actor={event.actor} "
                f"aggregate={event.aggregate_id}"
            )
    finally:
        access_audit_store.close()


def _seed_sample_platform_access_anomalies(
    recorder: AuditAccessRecorder,
) -> None:
    for minute in (20, 24, 28):
        recorder.record(
            event_type="audit_access.denied",
            actor="viewer_002",
            permission="export_audit_report",
            target="fintech_platform_history_report",
            outcome="denied",
            occurred_at=datetime(2026, 5, 18, 12, minute, tzinfo=timezone.utc),
            reason="Sample viewer export attempt",
        )
    recorder.record(
        event_type="audit_access.denied",
        actor="analyst_002",
        permission="export_audit_report",
        target="fintech_platform_consistency_report",
        outcome="denied",
        occurred_at=datetime(2026, 5, 18, 12, 35, tzinfo=timezone.utc),
        reason="Sample analyst export attempt",
    )


if __name__ == "__main__":
    main()
