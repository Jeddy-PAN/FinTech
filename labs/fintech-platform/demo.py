from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

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
from platform_api_access_anomaly_report import (
    detect_platform_api_access_anomalies,
    export_platform_api_access_anomaly_report,
)
from platform_api_investigation_cases import (
    export_platform_api_access_investigation_report,
    open_platform_api_access_investigation_cases,
)
from platform_api_app import create_app
from platform_evidence_package import (
    build_platform_evidence_package,
    export_platform_evidence_package,
)
from platform_ledger_reconciliation_report import (
    export_platform_ledger_reconciliation_report,
)
from platform_settlement_reconciliation_report import (
    PROVIDER_SETTLEMENT_SETTLED,
    ProviderSettlementRow,
    evaluate_platform_settlement_reconciliation,
    export_platform_settlement_reconciliation_report,
)
from platform_investigation_cases import (
    export_platform_access_investigation_report,
    open_platform_access_investigation_cases,
)
from platform_operations_report import export_platform_operations_report
from platform_operation_approval import SQLiteOperationApprovalStore
from platform_operation_approval_report import export_operation_approval_report
from platform_report_access import (
    export_platform_consistency_report_with_access,
    export_platform_history_report_with_access,
    export_platform_report_with_access,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore
from platform_async_service import SQLitePlatformAsyncRunStore
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

    async_database_path = LAB_DIR / ".test-data" / "demo_platform_async_runs.db"
    api_access_audit_database_path = (
        LAB_DIR / ".test-data" / "demo_platform_api_access_audit.db"
    )
    operation_approval_database_path = (
        LAB_DIR / ".test-data" / "demo_platform_operation_approvals.db"
    )
    settlement_findings_for_evidence = ()
    approval_records_for_evidence = ()
    for path in (
        async_database_path,
        api_access_audit_database_path,
        operation_approval_database_path,
    ):
        if path.exists():
            path.unlink()

    api_app = create_app(
        database_path=database_path,
        access_audit_database_path=api_access_audit_database_path,
        async_database_path=async_database_path,
        operation_approval_database_path=operation_approval_database_path,
    )
    async_payload = {
        "run_id": "run_demo_async_001",
        "customer_id": "cust_async_001",
        "full_name": "Taylor Lee",
        "date_of_birth": "1990-07-15",
        "country": "US",
        "address": "200 Market Street",
        "identification_number": "ID-ASYNC-1001",
        "expected_monthly_volume_cents": 250_000,
        "amount": "125.00",
        "currency": "USD",
        "order_id": "order_async_001",
        "requested_at": "2026-05-18T15:00:00Z",
        "device_id": "device_known",
        "ip_country": "US",
        "beneficiary_id": "beneficiary_001",
        "actor": "api_client_async_001",
    }
    with TestClient(api_app) as client:
        accepted_response = client.post(
            "/platform/async-payment-runs",
            json=async_payload,
        )
        accepted_body = accepted_response.json()
        before_worker_body = client.get(
            "/platform/async-payment-runs/run_demo_async_001",
            headers={"x-actor-id": "async_status_viewer_001"},
        ).json()
        worker_body = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        ).json()
        completed_body = client.get(
            "/platform/async-payment-runs/run_demo_async_001",
            headers={"x-actor-id": "async_status_viewer_001"},
        ).json()
        final_platform_body = client.get(
            "/platform/payment-runs/run_demo_async_001",
            headers={"x-actor-id": "api_viewer_async_001"},
        ).json()
        replay_body = client.post(
            "/platform/async-payment-runs",
            json=async_payload,
        ).json()
        failed_async_sample = create_failed_async_run_sample(
            client,
            existing_platform_payload={
                **async_payload,
                "run_id": "run_demo_async_failed_001",
                "order_id": "order_async_failed_existing",
                "amount": "50.00",
            },
            async_payload={
                **async_payload,
                "run_id": "run_demo_async_failed_001",
                "order_id": "order_async_failed_conflict",
                "amount": "75.00",
            },
        )
        console_body = client.get(
            "/platform/view",
            headers={"x-actor-id": "console_reader_001"},
        ).text
        retry_approval_request_body = client.post(
            "/platform/async-payment-runs/run_demo_async_failed_001/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry demo failed async run after review",
                "confirmation": "retry_failed_async_run",
            },
        ).json()
        retry_approval_id = retry_approval_request_body["record"]["approval_id"]
        retry_pending_approval_body = client.get(
            f"/platform/operation-approvals/{retry_approval_id}",
            headers={"x-actor-id": "approval_viewer_001"},
        ).json()
        approved_retry_body = client.patch(
            f"/platform/operation-approvals/{retry_approval_id}/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved demo retry after review",
                "decided_at": "2026-05-18T12:50:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        ).json()
        cancelled_approval_body = client.post(
            "/platform/operation-approvals",
            json={
                "approval_id": "approval_demo_cancelled_001",
                "operation_type": "retry_platform_async_run",
                "operation_id": "run_demo_cancelled_001",
                "target": "fintech_platform_api_async_payment_runs/run_demo_cancelled_001",
                "requested_by": "ops_user_002",
                "request_reason": "Demo approval that will be cancelled",
                "requested_at": "2026-05-18T12:55:00Z",
            },
            headers={"x-actor-id": "ops_user_002"},
        ).json()
        cancelled_approval_body = client.patch(
            "/platform/operation-approvals/approval_demo_cancelled_001/cancel",
            json={
                "decided_by": "ops_user_002",
                "decision_reason": "Requester withdrew demo approval",
                "decided_at": "2026-05-18T12:56:00Z",
            },
            headers={"x-actor-id": "ops_user_002"},
        ).json()
        expired_approval_body = client.post(
            "/platform/operation-approvals",
            json={
                "approval_id": "approval_demo_expired_001",
                "operation_type": "retry_platform_async_run",
                "operation_id": "run_demo_expired_001",
                "target": "fintech_platform_api_async_payment_runs/run_demo_expired_001",
                "requested_by": "ops_user_003",
                "request_reason": "Demo approval that will expire",
                "requested_at": "2026-05-18T12:57:00Z",
            },
            headers={"x-actor-id": "ops_user_003"},
        ).json()
        expired_approval_body = client.patch(
            "/platform/operation-approvals/approval_demo_expired_001/expire",
            json={
                "decided_by": "system_scheduler",
                "decision_reason": "Demo approval exceeded review window",
                "decided_at": "2026-05-18T13:00:00Z",
            },
            headers={"x-actor-id": "system_scheduler"},
        ).json()
        readiness_body = client.get(
            "/platform/operability/readiness",
            headers={"x-actor-id": "audit_reader_001"},
        ).json()
        metrics_body = client.get(
            "/platform/operability/metrics",
            headers={"x-actor-id": "audit_reader_001"},
        ).json()
        test_matrix_body = client.get(
            "/platform/operability/test-matrix",
            headers={"x-actor-id": "audit_reader_001"},
        ).json()

    print("\nAsync payment run via FastAPI")
    print(f"- Create HTTP style: {accepted_body['http_status']}")
    print(f"- Accepted async status: {before_worker_body['status']}")
    print(
        f"- Worker processed: {worker_body['result']['processed']} "
        f"async_status={worker_body['result']['async_status']} "
        f"platform_status={worker_body['result']['platform_status']}"
    )
    print(f"- Completed async status: {completed_body['status']}")
    print(
        f"- Final platform result: {final_platform_body['run_id']} "
        f"status={final_platform_body['status']} "
        f"payment_order={final_platform_body['payment_order_id']}"
    )
    print(
        f"- Idempotent replay: {replay_body['idempotent_replay']} "
        f"http_status={replay_body['http_status']}"
    )
    print("\nFailed async run sample for console")
    print(
        f"- Failed async run: {failed_async_sample['failed_async']['run_id']} "
        f"status={failed_async_sample['failed_async']['status']} "
        f"attempts={failed_async_sample['failed_async']['attempt_count']}"
    )
    print(f"- Last error: {failed_async_sample['failed_async']['last_error']}")
    print(
        "- Console shows failed async run: "
        f"{'run_demo_async_failed_001' in console_body}"
    )
    print(
        f"- Retry approval request: "
        f"{retry_pending_approval_body['record']['approval_id']} "
        f"status={retry_pending_approval_body['record']['status']}"
    )
    print(
        f"- Retry approval decision: "
        f"approval_status={approved_retry_body['record']['status']} "
        f"async_status={approved_retry_body['run']['status']}"
    )

    metric_values = {
        metric["name"]: metric["value"]
        for metric in metrics_body["metrics"]
    }
    print("\nPlatform operability snapshot")
    print(f"- Readiness: {readiness_body['status']}")
    print(
        "- Key metrics: "
        f"payment_runs={metric_values['platform.payment_runs.total']} "
        f"async_runs={metric_values['platform.async_runs.total']} "
        f"pending_approvals={metric_values['platform.operation_approvals.pending']} "
        f"denied_access={metric_values['platform.access_events.denied']}"
    )
    print(f"- Test matrix rows: {len(test_matrix_body['rows'])}")

    async_access_store = SQLiteAccessAuditStore(api_access_audit_database_path)
    async_store = SQLitePlatformAsyncRunStore(async_database_path)
    operations_platform_store = SQLitePlatformStore(database_path)
    operation_approval_store = SQLiteOperationApprovalStore(
        operation_approval_database_path
    )
    try:
        print("\nAsync API access audit events")
        for event in async_access_store.access_events:
            print(
                f"- {event.occurred_at.isoformat()} actor={event.actor} "
                f"permission={event.permission} outcome={event.outcome}"
            )

        operations_snapshots = tuple(
            operations_platform_store.get_run(record.run_id)
            for record in operations_platform_store.runs
        )
        operations_paths = export_platform_operations_report(
            LAB_DIR / "reports",
            async_runs=async_store.runs,
            snapshots=operations_snapshots,
            access_events=async_access_store.access_events,
        )
        print("\nExported platform operations reports:")
        print(f"- {operations_paths.run_rows_csv}")
        print(f"- {operations_paths.findings_csv}")
        print(f"- {operations_paths.html_report}")

        ledger_reconciliation_paths = export_platform_ledger_reconciliation_report(
            LAB_DIR / "reports",
            snapshots=operations_snapshots,
        )
        print("\nExported platform ledger reconciliation reports:")
        print(f"- {ledger_reconciliation_paths.findings_csv}")
        print(f"- {ledger_reconciliation_paths.html_report}")

        provider_settlement_rows = _provider_settlement_rows(operations_snapshots)
        settlement_findings_for_evidence = evaluate_platform_settlement_reconciliation(
            operations_snapshots,
            provider_rows=provider_settlement_rows,
        )
        settlement_reconciliation_paths = (
            export_platform_settlement_reconciliation_report(
                LAB_DIR / "reports",
                snapshots=operations_snapshots,
                provider_rows=provider_settlement_rows,
            )
        )
        print("\nExported platform settlement reconciliation reports:")
        print(f"- {settlement_reconciliation_paths.findings_csv}")
        print(f"- {settlement_reconciliation_paths.html_report}")

        print("\nPending operation approval flow")
        print(
            f"- before={retry_pending_approval_body['record']['status']} "
            f"after={approved_retry_body['record']['status']} "
            f"requested_by={approved_retry_body['record']['requested_by']} "
            f"approved_by={approved_retry_body['record']['approved_by']} "
            f"async_status={approved_retry_body['run']['status']}"
        )
        print(
            f"- cancelled={cancelled_approval_body['record']['status']} "
            f"by={cancelled_approval_body['record']['approved_by']}"
        )
        print(
            f"- expired={expired_approval_body['record']['status']} "
            f"by={expired_approval_body['record']['approved_by']}"
        )

        print("\nOperation approval records")
        approval_records_for_evidence = operation_approval_store.records
        for record in approval_records_for_evidence:
            print(
                f"- {record.operation_type} "
                f"run_id={record.operation_id} "
                f"status={record.status} "
                f"requested_by={record.requested_by} "
                f"approved_by={record.approved_by}"
            )

        operation_approval_paths = export_operation_approval_report(
            LAB_DIR / "reports",
            records=approval_records_for_evidence,
        )
        print("\nExported operation approval reports:")
        print(f"- {operation_approval_paths.records_csv}")
        print(f"- {operation_approval_paths.summary_csv}")
        print(f"- {operation_approval_paths.html_report}")
    finally:
        operation_approval_store.close()
        operations_platform_store.close()
        async_store.close()
        async_access_store.close()

    access_audit_database_path = LAB_DIR / ".test-data" / "demo_platform_access_audit.db"
    if access_audit_database_path.exists():
        access_audit_database_path.unlink()
    access_audit_store = SQLiteAccessAuditStore(access_audit_database_path)
    try:
        _seed_sample_platform_access_anomalies(access_recorder)
        _seed_sample_platform_api_access_anomalies(access_recorder)
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

        platform_api_findings = detect_platform_api_access_anomalies(
            access_audit_store.access_events,
        )
        print("\nPlatform API access anomaly findings")
        for finding in platform_api_findings:
            print(
                f"- {finding.finding_type} actor={finding.actor} "
                f"severity={finding.severity} event_count={finding.event_count} "
                f"target={finding.events[0].target}"
            )
        platform_api_anomaly_paths = export_platform_api_access_anomaly_report(
            LAB_DIR / "reports",
            findings=platform_api_findings,
        )
        print("Exported platform API access anomaly reports:")
        print(f"- {platform_api_anomaly_paths.findings_csv}")
        print(f"- {platform_api_anomaly_paths.html_report}")

        evidence_package = build_platform_evidence_package(
            case_id="platform_demo_evidence_package",
            generated_by="platform_compliance_lead_001",
            generated_at=datetime(2026, 5, 18, 15, 0, tzinfo=timezone.utc),
            settlement_findings=settlement_findings_for_evidence,
            access_findings=(*platform_findings, *platform_api_findings),
            approval_records=approval_records_for_evidence,
            access_events=access_audit_store.access_events,
            legal_hold=True,
            retention_policy_id="platform-evidence-demo-hold",
        )
        evidence_paths = export_platform_evidence_package(
            LAB_DIR / "reports",
            package=evidence_package,
        )
        print("\nExported platform evidence package")
        print(f"- {evidence_paths.items_csv}")
        print(f"- {evidence_paths.summary_csv}")
        print(f"- {evidence_paths.html_report}")

        api_investigation_service = AccessAnomalyInvestigationService()
        api_investigation_cases = open_platform_api_access_investigation_cases(
            platform_api_findings,
            opened_by="api_compliance_lead_001",
            created_at=datetime(2026, 5, 18, 13, 5, tzinfo=timezone.utc),
            service=api_investigation_service,
        )
        if api_investigation_cases:
            first_api_case = api_investigation_cases[0]
            api_investigation_service.start_investigation(
                first_api_case.case_id,
                assigned_to="api_investigator_001",
                started_at=datetime(2026, 5, 18, 13, 15, tzinfo=timezone.utc),
            )
            api_investigation_service.mark_false_positive(
                first_api_case.case_id,
                closed_by="api_investigator_001",
                reason="Reviewed sample platform API access anomaly",
                closed_at=datetime(2026, 5, 18, 14, 10, tzinfo=timezone.utc),
            )

        print("\nPlatform API access investigation cases")
        for investigation_case in api_investigation_service.cases:
            print(
                f"- {investigation_case.case_id} "
                f"status={investigation_case.status} "
                f"actor={investigation_case.finding.actor}"
            )

        api_investigation_database_path = (
            LAB_DIR / ".test-data" / "demo_platform_api_investigation_cases.db"
        )
        if api_investigation_database_path.exists():
            api_investigation_database_path.unlink()
        api_investigation_store = SQLiteInvestigationCaseStore(
            api_investigation_database_path
        )
        try:
            for investigation_case in api_investigation_service.cases:
                api_investigation_store.save_case(investigation_case)

            print("\nPersisted open platform API investigation cases")
            for investigation_case in api_investigation_store.open_cases:
                print(
                    f"- {investigation_case.case_id} "
                    f"status={investigation_case.status} "
                    f"actor={investigation_case.finding.actor}"
                )
        finally:
            api_investigation_store.close()

        api_investigation_paths = export_platform_api_access_investigation_report(
            LAB_DIR / "reports",
            cases=api_investigation_service.cases,
        )
        print("Exported platform API access investigation reports:")
        print(f"- {api_investigation_paths.cases_csv}")
        print(f"- {api_investigation_paths.html_report}")

        print("\nPlatform API investigation case audit events")
        for event in api_investigation_service.audit_events:
            print(
                f"- {event.occurred_at.isoformat()} "
                f"{event.event_type} actor={event.actor} "
                f"aggregate={event.aggregate_id}"
            )

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


def create_failed_async_run_sample(
    client: TestClient,
    *,
    existing_platform_payload: dict,
    async_payload: dict,
) -> dict:
    created_platform = client.post(
        "/platform/payment-runs",
        json=existing_platform_payload,
    ).json()
    accepted_async = client.post(
        "/platform/async-payment-runs",
        json=async_payload,
    ).json()

    worker_results = []
    for _ in range(3):
        worker_body = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        ).json()
        worker_results.append(worker_body["result"])

    failed_async = client.get(
        f"/platform/async-payment-runs/{async_payload['run_id']}",
        headers={"x-actor-id": "async_status_viewer_001"},
    ).json()
    return {
        "created_platform": created_platform,
        "accepted_async": accepted_async,
        "worker_results": worker_results,
        "failed_async": failed_async,
    }


def _provider_settlement_rows(snapshots) -> tuple[ProviderSettlementRow, ...]:
    rows: list[ProviderSettlementRow] = []
    for snapshot in snapshots:
        record = snapshot.record
        if record.status != "completed" or record.payment_order_id is None:
            continue
        rows.append(
            ProviderSettlementRow(
                provider="sample_provider",
                settlement_id=f"settlement_{record.run_id}",
                provider_payment_id=f"provider_payment_{record.payment_order_id}",
                platform_run_id=record.run_id,
                payment_order_id=record.payment_order_id,
                amount=record.user_wallet_balance,
                currency="USD",
                status=PROVIDER_SETTLEMENT_SETTLED,
                settled_at=record.created_at,
            )
        )
    return tuple(rows)


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


def _seed_sample_platform_api_access_anomalies(
    recorder: AuditAccessRecorder,
) -> None:
    for minute, run_id in ((40, "missing_001"), (44, "missing_002"), (48, "missing_003")):
        recorder.record(
            event_type="audit_access.denied",
            actor="api_viewer_404",
            permission="view_platform_payment_run",
            target=f"fintech_platform_api_payment_runs/{run_id}",
            outcome="denied",
            occurred_at=datetime(2026, 5, 18, 12, minute, tzinfo=timezone.utc),
            reason="Sample missing platform payment run lookup",
        )


if __name__ == "__main__":
    main()
