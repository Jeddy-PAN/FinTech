import sys
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from risk_reporting import (
    RiskRuleVersionComparisonReport,
    RiskSummaryReport,
    build_risk_summary_report,
    build_rule_version_comparison_report,
)
from risk_report_export import export_risk_reports
from risk_rule_engine import ManualReviewService, RiskRuleConfig, RiskRuleEngine, build_request
from sqlite_risk_store import SQLiteRiskStore


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lab_dir = Path(__file__).resolve().parent
    database_path = lab_dir / "risk_rule_engine_demo.db"
    if database_path.exists():
        database_path.unlink()

    config = RiskRuleConfig.from_json(lab_dir / "risk_rules.json")
    comparison_config = replace(
        config,
        single_transaction_review_threshold=Decimal("800.00"),
    )
    baseline_engine = RiskRuleEngine(config=config)
    comparison_engine = RiskRuleEngine(config=comparison_config)
    review_service = ManualReviewService()
    store = SQLiteRiskStore(database_path)

    try:
        baseline_rule_version = store.save_rule_version(
            config,
            version_id="rules-2026-05-05",
            effective_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
        )
        comparison_rule_version = store.save_rule_version(
            comparison_config,
            version_id="rules-2026-05-05-strict",
            effective_at=datetime(2026, 5, 5, 1, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 5, 1, 0, tzinfo=timezone.utc),
        )
        history = [
            build_request(
                "txn_001",
                "user_001",
                "900.00",
                "USD",
                datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
                device_id="device_known",
            ),
            build_request(
                "txn_002",
                "user_001",
                "1200.00",
                "USD",
                datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                device_id="device_known",
            ),
        ]
        baseline_requests = [
            build_request(
                "txn_003",
                "user_001",
                "950.00",
                "USD",
                datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
                device_id="device_known",
            ),
            build_request(
                "txn_004",
                "user_002",
                "1500.00",
                "USD",
                datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
                device_id="device_002",
            ),
            build_request(
                "txn_005",
                "user_003",
                "100.00",
                "JPY",
                datetime(2026, 5, 5, 13, 0, tzinfo=timezone.utc),
                device_id="device_003",
            ),
        ]
        comparison_requests = [
            build_request(
                "txn_006",
                "user_006",
                "500.00",
                "USD",
                datetime(2026, 5, 5, 2, 30, tzinfo=timezone.utc),
            ),
            build_request(
                "txn_007",
                "user_004",
                "100.00",
                "USD",
                datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc),
                ip_country="KP",
            ),
            build_request(
                "txn_008",
                "user_005",
                "100.00",
                "USD",
                datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc),
                beneficiary_id="beneficiary_blocked_001",
            ),
        ]

        print(f"SQLite database: {database_path}")
        print("\nRule Versions")
        print(
            f"- {baseline_rule_version.version_id}: "
            f"single_threshold={baseline_rule_version.single_transaction_review_threshold}; "
            f"daily_threshold={baseline_rule_version.daily_user_review_threshold}; "
            f"allowed_currencies={','.join(baseline_rule_version.allowed_currencies)}; "
            f"high_risk_countries={','.join(baseline_rule_version.high_risk_countries)}; "
            f"blocked_beneficiaries={','.join(baseline_rule_version.blocked_beneficiaries)}; "
            f"score_threshold={baseline_rule_version.risk_score_review_threshold}"
        )
        print(
            f"- {comparison_rule_version.version_id}: "
            f"single_threshold={comparison_rule_version.single_transaction_review_threshold}; "
            f"daily_threshold={comparison_rule_version.daily_user_review_threshold}; "
            f"allowed_currencies={','.join(comparison_rule_version.allowed_currencies)}; "
            f"high_risk_countries={','.join(comparison_rule_version.high_risk_countries)}; "
            f"blocked_beneficiaries={','.join(comparison_rule_version.blocked_beneficiaries)}; "
            f"score_threshold={comparison_rule_version.risk_score_review_threshold}"
        )
        print("\nSaved Risk Decisions")
        decision_inputs = [
            (request, baseline_engine, baseline_rule_version.version_id)
            for request in baseline_requests
        ] + [
            (request, comparison_engine, comparison_rule_version.version_id)
            for request in comparison_requests
        ]
        for request, engine, rule_version_id in decision_inputs:
            decision = engine.evaluate(request, history=history)
            store.save_decision(
                decision,
                decided_at=request.created_at,
                rule_version_id=rule_version_id,
            )
            print(
                f"- {decision.request_id}: status={decision.status.value}; "
                f"risk_score={decision.risk_score}; rule_version={rule_version_id}"
            )
            if decision.status.value == "review":
                review_case = review_service.create_case(
                    decision,
                    created_at=datetime(2026, 5, 5, 14, 5, tzinfo=timezone.utc),
                )
                store.save_review_case(review_case)
                print(f"  - review_case={review_case.case_id}; status={review_case.status.value}")

        print("\nPending Review Cases")
        for review_case in store.pending_review_cases:
            print(f"- {review_case.case_id}: request_id={review_case.request_id}")

        completed = review_service.approve(
            "review:txn_003",
            reviewed_by="analyst_001",
            reason="Verified customer history",
            reviewed_at=datetime(2026, 5, 5, 15, 0, tzinfo=timezone.utc),
        )
        store.save_review_case(completed)

        print("\nCompleted Review Case")
        stored_case = store.get_review_case(completed.case_id)
        print(
            f"- {stored_case.case_id}: status={stored_case.status.value}; "
            f"reviewed_by={stored_case.reviewed_by}; reason={stored_case.review_reason}"
        )

        summary_report = build_risk_summary_report(store)
        filtered_report = build_risk_summary_report(
            store,
            rule_version_id=comparison_rule_version.version_id,
            decided_from=datetime(2026, 5, 5, 2, 0, tzinfo=timezone.utc),
            decided_to=datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc),
        )
        comparison_report = build_rule_version_comparison_report(
            store,
            baseline_rule_version_id=baseline_rule_version.version_id,
            comparison_rule_version_id=comparison_rule_version.version_id,
            decided_from=datetime(2026, 5, 5, 2, 0, tzinfo=timezone.utc),
            decided_to=datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc),
        )

        _print_report("Risk Summary Report", summary_report)
        _print_report(
            "Filtered Risk Summary Report",
            filtered_report,
        )
        _print_comparison_report(
            "Rule Version Comparison Report",
            comparison_report,
        )
        export_paths = export_risk_reports(
            lab_dir / "reports",
            summary_report=summary_report,
            comparison_report=comparison_report,
        )
        print("\nExported Risk Reports")
        print(f"- summary_csv={export_paths.summary_csv}")
        if export_paths.comparison_csv is not None:
            print(f"- comparison_csv={export_paths.comparison_csv}")
        print(f"- html_report={export_paths.html_report}")

        print("\nAudit Events")
        for event in store.audit_events:
            print(
                f"- {event.event_type}: "
                f"aggregate={event.aggregate_type}/{event.aggregate_id}; "
                f"actor={event.actor}"
            )
    finally:
        store.close()


def _print_report(title: str, report: RiskSummaryReport) -> None:
    print(f"\n{title}")
    print(f"- rule_version_id={report.rule_version_id or 'all'}")
    print(f"- decided_from={report.decided_from.isoformat() if report.decided_from else 'all'}")
    print(f"- decided_to={report.decided_to.isoformat() if report.decided_to else 'all'}")
    print(f"- total_decisions={report.total_decisions}")
    print(
        "- decision_status_counts="
        + ", ".join(
            f"{item.status}:{item.count}" for item in report.decision_status_counts
        )
    )
    print(
        "- rule_hit_counts="
        + ", ".join(f"{item.rule_id}:{item.count}" for item in report.rule_hit_counts)
    )
    print(f"- average_risk_score={report.average_risk_score:.2f}")
    print(f"- max_risk_score={report.max_risk_score}")
    print(f"- pending_review_count={report.pending_review_count}")
    print(
        "- review_status_counts="
        + ", ".join(f"{item.status}:{item.count}" for item in report.review_status_counts)
    )


def _print_comparison_report(
    title: str,
    report: RiskRuleVersionComparisonReport,
) -> None:
    print(f"\n{title}")
    print(f"- baseline_rule_version_id={report.baseline_rule_version_id}")
    print(f"- comparison_rule_version_id={report.comparison_rule_version_id}")
    print(f"- decided_from={report.decided_from.isoformat() if report.decided_from else 'all'}")
    print(f"- decided_to={report.decided_to.isoformat() if report.decided_to else 'all'}")
    print(f"- total_decisions_delta={report.total_decisions_delta}")
    print(
        "- decision_status_comparisons="
        + ", ".join(
            f"{item.status}:{item.baseline_count}->{item.comparison_count} ({item.delta:+d})"
            for item in report.decision_status_comparisons
        )
    )
    print(
        "- rule_hit_comparisons="
        + ", ".join(
            f"{item.rule_id}:{item.baseline_count}->{item.comparison_count} ({item.delta:+d})"
            for item in report.rule_hit_comparisons
        )
    )
    print(f"- average_risk_score_delta={report.average_risk_score_delta:.2f}")
    print(f"- max_risk_score_delta={report.max_risk_score_delta}")
    print(f"- pending_review_delta={report.pending_review_delta}")
    print(
        "- review_status_comparisons="
        + ", ".join(
            f"{item.status}:{item.baseline_count}->{item.comparison_count} ({item.delta:+d})"
            for item in report.review_status_comparisons
        )
    )


if __name__ == "__main__":
    main()
