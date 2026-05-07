from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from kyc_aml import (
    BeneficialOwner,
    KycAmlEngine,
    KycAmlPolicy,
    KycReviewService,
    WatchlistEntry,
    build_individual_application,
    build_legal_entity_application,
)
from kyc_report_export import export_kyc_reports
from kyc_replay import build_kyc_replay_report
from kyc_reporting import (
    build_kyc_summary_report,
    build_policy_version_comparison_report,
)
from sqlite_kyc_store import SQLiteKycStore


def print_decision(label, decision):
    print(f"\n{label}")
    print(f"customer_id: {decision.customer_id}")
    print(f"status: {decision.status.value}")
    print(f"risk_score: {decision.risk_score}")
    for result in decision.check_results:
        print(
            f"- {result.check_id}: {result.status.value} "
            f"(score={result.score}) {result.reason}"
        )


def print_summary_report(report):
    print("\nKYC summary report")
    print(f"total_applications: {report.total_applications}")
    print(f"average_risk_score: {report.average_risk_score:.2f}")
    print(f"max_risk_score: {report.max_risk_score}")
    print(f"pending_review_count: {report.pending_review_count}")
    print("decision_status_counts:")
    for item in report.decision_status_counts:
        print(f"- {item.status}: {item.count}")
    print("check_hit_counts:")
    for item in report.check_hit_counts:
        print(f"- {item.check_id}: {item.count}")
    print("review_status_counts:")
    for item in report.review_status_counts:
        print(f"- {item.status}: {item.count}")


def print_comparison_report(report):
    print("\nKYC version comparison report")
    print(f"version_type: {report.version_type}")
    print(f"baseline_version_id: {report.baseline_version_id}")
    print(f"comparison_version_id: {report.comparison_version_id}")
    print(f"total_applications_delta: {report.total_applications_delta:+d}")
    print(f"average_risk_score_delta: {report.average_risk_score_delta:+.2f}")
    print(f"max_risk_score_delta: {report.max_risk_score_delta:+d}")
    print(f"pending_review_delta: {report.pending_review_delta:+d}")
    print("decision_status_comparisons:")
    for item in report.decision_status_comparisons:
        print(
            f"- {item.status}: {item.baseline_count}->{item.comparison_count} "
            f"({item.delta:+d})"
        )
    print("check_hit_comparisons:")
    for item in report.check_hit_comparisons:
        print(
            f"- {item.check_id}: {item.baseline_count}->{item.comparison_count} "
            f"({item.delta:+d})"
        )


def print_replay_report(report):
    print("\nKYC replay report")
    print(f"replay_policy_version_id: {report.replay_policy_version_id or 'unversioned'}")
    print(
        "replay_watchlist_version_id: "
        f"{report.replay_watchlist_version_id or 'unversioned'}"
    )
    print(f"total_applications: {report.total_applications}")
    print(f"status_changed_count: {report.status_changed_count}")
    print(f"increased_risk_count: {report.increased_risk_count}")
    print(f"decreased_risk_count: {report.decreased_risk_count}")
    print("changed_items:")
    for item in report.items:
        if item.status_changed or item.risk_score_delta != 0:
            print(
                f"- {item.customer_id}: {item.original_status}->{item.replay_status}; "
                f"risk_delta={item.risk_score_delta:+d}; "
                f"new_checks={','.join(item.new_check_ids) or 'none'}; "
                f"resolved_checks={','.join(item.resolved_check_ids) or 'none'}"
            )


def print_replay_run(run):
    print("\nStored replay run")
    print(f"run_id: {run.run_id}")
    print(f"status: {run.status}")
    print(f"created_by: {run.created_by}")
    print(f"reviewed_by: {run.reviewed_by or 'none'}")
    print(f"review_reason: {run.review_reason or 'none'}")


def main():
    database_path = Path(__file__).with_name("kyc_aml_demo.db")
    if database_path.exists():
        database_path.unlink()

    policy = KycAmlPolicy(
        high_risk_countries=("XZ",),
        high_expected_monthly_volume_cents=1_000_000,
    )
    strict_policy = KycAmlPolicy(
        high_risk_countries=("XZ",),
        high_expected_monthly_volume_cents=200_000,
    )
    engine = KycAmlEngine(policy)
    strict_engine = KycAmlEngine(strict_policy)
    review_service = KycReviewService()
    store = SQLiteKycStore(database_path)
    base_time = datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc)
    policy_version = store.save_policy_version(
        policy,
        version_id="sample-kyc-policy-2026-05-07",
        source="inline demo KycAmlPolicy",
        effective_at=base_time.replace(hour=8, minute=0),
        created_at=base_time.replace(hour=8, minute=2),
    )
    strict_policy_version = store.save_policy_version(
        strict_policy,
        version_id="sample-kyc-policy-2026-05-07-strict",
        source="inline demo strict KycAmlPolicy",
        effective_at=base_time.replace(hour=8, minute=30),
        created_at=base_time.replace(hour=8, minute=31),
    )

    watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name="Alex Blocked",
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
        WatchlistEntry(
            entry_id="sample_sdn_002",
            list_name="Sample Sanctions List",
            full_name="Maria Review",
            country="GB",
        ),
    )
    watchlist_version = store.save_watchlist_version(
        watchlist,
        version_id="sample-watchlist-2026-05-07",
        source="sample_watchlist.json",
        effective_at=base_time.replace(hour=8, minute=0),
        created_at=base_time.replace(hour=8, minute=1),
    )
    replay_watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_002",
            list_name="Sample Sanctions List",
            full_name="Maria Review",
            country="GB",
        ),
    )
    replay_watchlist_version = store.save_watchlist_version(
        replay_watchlist,
        version_id="sample-watchlist-2026-05-07-replay",
        source="sample_watchlist_replay.json",
        effective_at=base_time.replace(hour=8, minute=30),
        created_at=base_time.replace(hour=8, minute=32),
    )

    applications = (
        build_individual_application(
            "cust_sqlite_001",
            "Jordan Smith",
            date_of_birth=date(1992, 5, 20),
            country="US",
            address="100 Market Street",
            identification_number="ID-1001",
            expected_monthly_volume_cents=250_000,
        ),
        build_legal_entity_application(
            "cust_sqlite_002",
            "Northwind Trading LLC",
            country="XZ",
            address="200 Commerce Avenue",
            identification_number="REG-2002",
            expected_monthly_volume_cents=1_500_000,
            beneficial_owners=(
                BeneficialOwner(
                    owner_id="owner_001",
                    full_name="Maria Reviw",
                    ownership_percent=40,
                    country="GB",
                    identification_number="ID-2002",
                ),
            ),
        ),
        build_individual_application(
            "cust_sqlite_003",
            "Alex Blocked",
            date_of_birth=date(1980, 1, 1),
            country="US",
            address="300 Main Street",
            identification_number="ID-3003",
            expected_monthly_volume_cents=100_000,
        ),
    )

    for index, application in enumerate(applications):
        submitted_at = base_time.replace(minute=index * 5)
        decided_at = base_time.replace(minute=index * 5 + 1)
        decision = engine.evaluate(application, watchlist=watchlist)

        store.save_application(application, submitted_at=submitted_at)
        store.save_decision(
            decision,
            decided_at=decided_at,
            watchlist_version_id=watchlist_version.version_id,
            policy_version_id=policy_version.version_id,
        )
        print_decision("Saved KYC decision", decision)

        if decision.status.value == "review":
            review_case = review_service.create_case(
                decision,
                created_at=base_time.replace(minute=index * 5 + 2),
            )
            store.save_review_case(review_case)
            completed_case = review_service.request_more_info(
                review_case.case_id,
                reviewed_by="analyst_001",
                reason="Additional source of funds document is required",
                reviewed_at=base_time.replace(minute=index * 5 + 3),
            )
            store.save_review_case(completed_case)

    comparison_applications = (
        build_individual_application(
            "cust_sqlite_policy_base",
            "Policy Baseline Customer",
            date_of_birth=date(1990, 4, 10),
            country="US",
            address="410 Baseline Street",
            identification_number="ID-4100",
            expected_monthly_volume_cents=250_000,
        ),
        build_individual_application(
            "cust_sqlite_policy_strict",
            "Policy Strict Customer",
            date_of_birth=date(1990, 4, 10),
            country="US",
            address="420 Strict Street",
            identification_number="ID-4200",
            expected_monthly_volume_cents=250_000,
        ),
    )
    comparison_inputs = (
        (comparison_applications[0], engine, policy_version.version_id),
        (comparison_applications[1], strict_engine, strict_policy_version.version_id),
    )
    for index, (application, selected_engine, selected_policy_version_id) in enumerate(
        comparison_inputs
    ):
        submitted_at = base_time.replace(hour=10, minute=index * 5)
        decided_at = base_time.replace(hour=10, minute=index * 5 + 1)
        decision = selected_engine.evaluate(application, watchlist=watchlist)
        store.save_application(application, submitted_at=submitted_at)
        store.save_decision(
            decision,
            decided_at=decided_at,
            watchlist_version_id=watchlist_version.version_id,
            policy_version_id=selected_policy_version_id,
        )
        print_decision("Saved policy comparison KYC decision", decision)

    print("\nStored applications:")
    for application in store.applications:
        print(
            f"- {application.customer_id}: {application.customer_type.value}, "
            f"owners={len(application.beneficial_owners)}"
        )

    print("\nWatchlist versions:")
    for version in store.watchlist_versions:
        print(
            f"- {version.version_id}: entries={version.entry_count}, "
            f"hash={version.content_hash[:12]}..."
        )

    print("\nPolicy versions:")
    for version in store.policy_versions:
        print(
            f"- {version.version_id}: high_risk_countries="
            f"{','.join(version.high_risk_countries) or 'none'}, "
            f"volume_threshold={version.high_expected_monthly_volume_cents}"
        )

    print("\nStored review cases:")
    for review_case in store.review_cases:
        print(
            f"- {review_case.case_id}: {review_case.status.value}, "
            f"reviewed_by={review_case.reviewed_by}"
        )

    print("\nAudit events:")
    for event in store.audit_events:
        print(
            f"- {event.occurred_at.isoformat()} {event.event_type} "
            f"{event.aggregate_type}:{event.aggregate_id}"
        )

    summary_report = build_kyc_summary_report(store)
    print_summary_report(summary_report)
    comparison_report = build_policy_version_comparison_report(
        store,
        baseline_policy_version_id=policy_version.version_id,
        comparison_policy_version_id=strict_policy_version.version_id,
    )
    print_comparison_report(comparison_report)
    replay_report = build_kyc_replay_report(
        store,
        policy=strict_policy,
        watchlist=replay_watchlist,
        replay_policy_version_id=strict_policy_version.version_id,
        replay_watchlist_version_id=replay_watchlist_version.version_id,
        customer_ids=(
            "cust_sqlite_001",
            "cust_sqlite_002",
            "cust_sqlite_003",
        ),
    )
    print_replay_report(replay_report)
    replay_run = store.save_replay_run(
        replay_report,
        run_id="kyc-replay-run-2026-05-07",
        created_by="analyst_001",
        created_at=base_time.replace(hour=11, minute=0),
    )
    approved_replay_run = store.approve_replay_run(
        replay_run.run_id,
        reviewed_by="compliance_001",
        reason="Sample replay impact reviewed before policy rollout",
        reviewed_at=base_time.replace(hour=11, minute=30),
    )
    print_replay_run(approved_replay_run)
    export_paths = export_kyc_reports(
        Path(__file__).parent / "reports",
        summary_report=summary_report,
        comparison_report=comparison_report,
        replay_report=replay_report,
    )
    print("\nExported reports:")
    print(f"- {export_paths.summary_csv}")
    if export_paths.comparison_csv is not None:
        print(f"- {export_paths.comparison_csv}")
    if export_paths.replay_csv is not None:
        print(f"- {export_paths.replay_csv}")
    print(f"- {export_paths.html_report}")

    store.close()
    print(f"\nSQLite database: {database_path}")


if __name__ == "__main__":
    main()
