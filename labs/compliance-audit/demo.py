from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
RISK_LAB_DIR = LAB_DIR.parent / "risk-rule-engine"
KYC_LAB_DIR = LAB_DIR.parent / "kyc-aml-onboarding"
sys.path.insert(0, str(RISK_LAB_DIR))
sys.path.insert(0, str(KYC_LAB_DIR))

from compliance_audit import (  # noqa: E402
    AuditAccessRecorder,
    AuditEventFilter,
    AuditExportApproval,
    AuditUser,
    build_audit_timeline,
    collect_audit_events,
    filter_audit_events,
    summarize_audit_events,
    visible_events_for_user,
)
from compliance_audit_export import export_compliance_audit_report  # noqa: E402
from kyc_aml import KycAmlEngine, KycAmlPolicy, KycReviewService, build_individual_application  # noqa: E402
from risk_rule_engine import ManualReviewService, RiskRuleEngine, build_request  # noqa: E402
from sqlite_access_audit_store import SQLiteAccessAuditStore  # noqa: E402
from sqlite_kyc_store import SQLiteKycStore  # noqa: E402
from sqlite_risk_store import SQLiteRiskStore  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    risk_database_path = ":memory:"
    kyc_database_path = ":memory:"
    access_audit_database_path = ":memory:"

    risk_store = SQLiteRiskStore(risk_database_path)
    kyc_store = SQLiteKycStore(kyc_database_path)
    access_audit_store = SQLiteAccessAuditStore(access_audit_database_path)
    try:
        _seed_risk_events(risk_store)
        _seed_kyc_events(kyc_store)

        events = collect_audit_events(
            risk_events=risk_store.audit_events,
            kyc_events=kyc_store.audit_events,
        )
        summary = summarize_audit_events(events)

        print("Compliance audit summary")
        print(f"total_events: {summary.total_events}")
        print("source_system_counts:")
        for source_system, count in summary.source_system_counts:
            print(f"- {source_system}: {count}")
        print("actor_counts:")
        for actor, count in summary.actor_counts:
            print(f"- {actor}: {count}")

        review_events = filter_audit_events(
            events,
            AuditEventFilter(event_type_prefix="kyc_review_case."),
        )
        print("\nKYC review audit events")
        for event in review_events:
            print(
                f"- {event.occurred_at.isoformat()} "
                f"{event.event_type} actor={event.actor}"
            )

        timeline = build_audit_timeline(
            events,
            subject_type="customer",
            subject_id="cust_audit_001",
            aggregate_links=(
                ("kyc_application", "cust_audit_001"),
                ("kyc_decision", "cust_audit_001"),
                ("kyc_review_case", "kyc_review:cust_audit_001"),
                ("risk_decision", "txn_audit_001"),
                ("review_case", "review:txn_audit_001"),
            ),
        )
        print("\nCustomer audit timeline")
        print(f"subject_id: {timeline.subject_id}")
        for event in timeline.events:
            print(
                f"- {event.occurred_at.isoformat()} "
                f"[{event.source_system}] {event.event_type} "
                f"{event.aggregate_type}:{event.aggregate_id}"
            )

        print("\nSample redacted payload")
        for event in events:
            if event.aggregate_type == "kyc_application":
                print(event.payload)
                break

        viewer = AuditUser("viewer_001", ("audit_viewer",))
        analyst = AuditUser("analyst_001", ("audit_analyst",))
        manager = AuditUser("manager_001", ("audit_manager",))
        approver = AuditUser("manager_002", ("audit_manager",))
        access_recorder = AuditAccessRecorder.create()
        viewer_events = visible_events_for_user(
            viewer,
            events,
            recorder=access_recorder,
            occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
        )
        analyst_events = visible_events_for_user(
            analyst,
            events,
            recorder=access_recorder,
            occurred_at=datetime(2026, 5, 8, 11, 5, tzinfo=timezone.utc),
        )
        print("\nPermission example")
        print(f"viewer_payload: {viewer_events[0].payload}")
        print(f"analyst_payload: {analyst_events[0].payload}")

        export_paths = export_compliance_audit_report(
            LAB_DIR / "reports",
            events=events,
            summary=summary,
            timeline=timeline,
            requested_by=manager,
            access_recorder=access_recorder,
            accessed_at=datetime(2026, 5, 8, 11, 10, tzinfo=timezone.utc),
            require_approval=True,
            approval=AuditExportApproval(
                approved_by=approver,
                approved_at=datetime(2026, 5, 8, 11, 12, tzinfo=timezone.utc),
                reason="Approved sample compliance audit export",
            ),
        )
        print("\nExported compliance audit reports:")
        print(f"- {export_paths.events_csv}")
        print(f"- {export_paths.summary_csv}")
        if export_paths.timeline_csv is not None:
            print(f"- {export_paths.timeline_csv}")
        print(f"- {export_paths.html_report}")
        print(f"approved_by: {approver.user_id}")

        print("\nAudit access events")
        for event in access_recorder.events:
            print(
                f"- {event.occurred_at.isoformat()} {event.event_type} "
                f"actor={event.actor} permission={event.permission} "
                f"target={event.target} outcome={event.outcome}"
            )

        access_audit_store.save_events(access_recorder.events)
        denied_payload_events = access_audit_store.query_access_events(
            permission="view_audit_payload",
            outcome="denied",
        )
        print("\nPersisted denied payload access events")
        for event in denied_payload_events:
            print(
                f"- {event.occurred_at.isoformat()} {event.event_type} "
                f"actor={event.actor} target={event.target}"
            )
    finally:
        risk_store.close()
        kyc_store.close()
        access_audit_store.close()

    print("\nDemo databases: in-memory SQLite")


def _seed_risk_events(store: SQLiteRiskStore) -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    request = build_request(
        "txn_audit_001",
        "cust_audit_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
    )
    decision = engine.evaluate(request)
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 8, 10, 1, tzinfo=timezone.utc),
    )

    review_service = ManualReviewService()
    review_case = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 8, 10, 2, tzinfo=timezone.utc),
    )
    store.save_review_case(review_case)
    approved = review_service.approve(
        review_case.case_id,
        reviewed_by="risk_analyst_001",
        reason="Sample transaction reviewed",
        reviewed_at=datetime(2026, 5, 8, 10, 20, tzinfo=timezone.utc),
    )
    store.save_review_case(approved)


def _seed_kyc_events(store: SQLiteKycStore) -> None:
    engine = KycAmlEngine(
        KycAmlPolicy(
            high_risk_countries=("XZ",),
            high_expected_monthly_volume_cents=1_000_000,
        )
    )
    application = build_individual_application(
        "cust_audit_001",
        "Jordan Audit",
        date_of_birth=date(1992, 5, 20),
        country="XZ",
        address="100 Market Street",
        identification_number="ID-AUDIT-001",
        expected_monthly_volume_cents=2_000_000,
    )
    decision = engine.evaluate(application)
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 8, 9, 1, tzinfo=timezone.utc),
    )

    review_service = KycReviewService()
    review_case = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 8, 9, 2, tzinfo=timezone.utc),
    )
    store.save_review_case(review_case)
    more_info = review_service.request_more_info(
        review_case.case_id,
        reviewed_by="kyc_analyst_001",
        reason="Need updated address document",
        reviewed_at=datetime(2026, 5, 8, 9, 30, tzinfo=timezone.utc),
    )
    store.save_review_case(more_info)


if __name__ == "__main__":
    main()
