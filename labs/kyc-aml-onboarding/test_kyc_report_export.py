from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from kyc_aml import KycAmlEngine, WatchlistEntry, build_individual_application
from kyc_report_export import export_kyc_reports
from kyc_replay import KycReplayItem, KycReplayReport
from kyc_reporting import (
    CheckHitCount,
    CheckHitComparison,
    CustomerTypeComparison,
    CustomerTypeCount,
    DecisionStatusComparison,
    DecisionStatusCount,
    KycSummaryReport,
    KycVersionComparisonReport,
    ReviewStatusComparison,
    ReviewStatusCount,
    build_kyc_summary_report,
)
from sqlite_kyc_store import SQLiteKycStore


def store_path():
    data_dir = Path(__file__).parent / ".test-data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"{uuid4()}.db"


def output_path():
    data_dir = Path(__file__).parent / ".test-data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"reports-{uuid4()}"


def seed_store_with_watchlist_check_name(name: str):
    store = SQLiteKycStore(store_path())
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_export_001",
        name,
        date_of_birth=date(1980, 1, 1),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )
    watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name=name,
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
    )
    decision = engine.evaluate(application, watchlist=watchlist)
    policy_version = store.save_policy_version(
        engine.policy,
        version_id="sample-kyc-policy-export",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 2, tzinfo=timezone.utc),
    )
    watchlist_version = store.save_watchlist_version(
        watchlist,
        version_id="sample-watchlist-export",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
        watchlist_version_id=watchlist_version.version_id,
        policy_version_id=policy_version.version_id,
    )
    return store


def test_export_kyc_reports_writes_csv_and_html():
    store = seed_store_with_watchlist_check_name("Alex Blocked")
    report = build_kyc_summary_report(store)

    paths = export_kyc_reports(output_path(), summary_report=report)

    assert paths.summary_csv.exists()
    assert paths.comparison_csv is None
    assert paths.replay_csv is None
    assert paths.html_report.exists()
    csv_text = paths.summary_csv.read_text(encoding="utf-8")
    html_text = paths.html_report.read_text(encoding="utf-8")
    assert "summary,total_applications,1" in csv_text
    assert "metadata,watchlist_version_id,all" in csv_text
    assert "metadata,policy_version_id,all" in csv_text
    assert "summary,max_risk_score,100" in csv_text
    assert "decision_status,blocked,1" in csv_text
    assert "check_hit,customer_watchlist_screening,1" in csv_text
    assert "<h1>KYC Summary Report</h1>" in html_text
    assert "<td>watchlist_version_id</td><td>all</td>" in html_text
    assert "<td>policy_version_id</td><td>all</td>" in html_text
    assert "<td>customer_watchlist_screening</td><td>1</td>" in html_text
    assert "No KYC version comparison report was provided." in html_text
    assert "No KYC replay report was provided." in html_text
    store.close()


def test_export_kyc_reports_escapes_html_values():
    report = KycSummaryReport(
        total_applications=1,
        customer_type=None,
        decision_status=None,
        watchlist_version_id=None,
        policy_version_id=None,
        submitted_from=None,
        submitted_to=None,
        decided_from=None,
        decided_to=None,
        customer_type_counts=(
            CustomerTypeCount("individual", 1),
            CustomerTypeCount("legal_entity", 0),
        ),
        decision_status_counts=(
            DecisionStatusCount("approved", 0),
            DecisionStatusCount("review", 1),
            DecisionStatusCount("blocked", 0),
        ),
        check_hit_counts=(CheckHitCount("<script>alert(1)</script>", 1),),
        average_risk_score=50.0,
        max_risk_score=50,
        pending_review_count=0,
        review_status_counts=(
            ReviewStatusCount("pending_review", 0),
            ReviewStatusCount("approved", 0),
            ReviewStatusCount("rejected", 0),
            ReviewStatusCount("request_more_info", 0),
        ),
    )

    paths = export_kyc_reports(output_path(), summary_report=report)

    html_text = paths.html_report.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text


def test_export_kyc_reports_writes_comparison_csv_and_html():
    comparison_report = _comparison_report()

    paths = export_kyc_reports(
        output_path(),
        summary_report=comparison_report.comparison_summary,
        comparison_report=comparison_report,
    )

    assert paths.comparison_csv is not None
    assert paths.comparison_csv.exists()
    comparison_csv = paths.comparison_csv.read_text(encoding="utf-8")
    html_text = paths.html_report.read_text(encoding="utf-8")
    assert "section,metric,baseline_value,comparison_value,delta" in comparison_csv
    assert "metadata,version_type,policy,policy," in comparison_csv
    assert "metadata,version_id,sample-kyc-policy-v1,sample-kyc-policy-v2," in comparison_csv
    assert "summary,total_applications,4,1,-3" in comparison_csv
    assert "summary,average_risk_score,63.75,57.50,-6.25" in comparison_csv
    assert "decision_status,blocked,1,0,-1" in comparison_csv
    assert "<td>version_type</td><td>policy</td>" in html_text
    assert "<td>blocked</td><td>1</td><td>0</td><td>-1</td>" in html_text


def test_export_kyc_reports_writes_replay_csv_and_html():
    report = _summary_report(policy_version_id="sample-kyc-policy-v2")
    replay_report = _replay_report()

    paths = export_kyc_reports(
        output_path(),
        summary_report=report,
        replay_report=replay_report,
    )

    assert paths.replay_csv is not None
    assert paths.replay_csv.exists()
    replay_csv = paths.replay_csv.read_text(encoding="utf-8")
    html_text = paths.html_report.read_text(encoding="utf-8")
    assert "metadata,replay_policy_version_id,sample-kyc-policy-v2" in replay_csv
    assert "summary,status_changed_count,2" in replay_csv
    assert "item,cust_replay_001.replay_status,review" in replay_csv
    assert "item,cust_replay_002.resolved_check_ids,customer_watchlist_screening" in replay_csv
    assert "<td>replay_policy_version_id</td><td>sample-kyc-policy-v2</td>" in html_text
    assert "<td>cust_replay_001</td><td>approved</td><td>review</td><td>yes</td>" in html_text


def test_export_kyc_reports_handles_empty_report():
    store = SQLiteKycStore(store_path())
    report = build_kyc_summary_report(store)

    paths = export_kyc_reports(output_path(), summary_report=report)

    csv_text = paths.summary_csv.read_text(encoding="utf-8")
    html_text = paths.html_report.read_text(encoding="utf-8")
    assert "summary,total_applications,0" in csv_text
    assert "summary,average_risk_score,0.00" in csv_text
    assert "check_hit" not in csv_text
    assert "<td>total_applications</td><td>0</td>" in html_text
    store.close()


def _summary_report(*, policy_version_id: str | None) -> KycSummaryReport:
    return KycSummaryReport(
        total_applications=4 if policy_version_id == "sample-kyc-policy-v1" else 1,
        customer_type=None,
        decision_status=None,
        watchlist_version_id=None,
        policy_version_id=policy_version_id,
        submitted_from=None,
        submitted_to=None,
        decided_from=None,
        decided_to=None,
        customer_type_counts=(
            CustomerTypeCount(
                "individual",
                3 if policy_version_id == "sample-kyc-policy-v1" else 0,
            ),
            CustomerTypeCount("legal_entity", 1),
        ),
        decision_status_counts=(
            DecisionStatusCount(
                "approved",
                1 if policy_version_id == "sample-kyc-policy-v1" else 0,
            ),
            DecisionStatusCount(
                "review",
                2 if policy_version_id == "sample-kyc-policy-v1" else 1,
            ),
            DecisionStatusCount(
                "blocked",
                1 if policy_version_id == "sample-kyc-policy-v1" else 0,
            ),
        ),
        check_hit_counts=(
            CheckHitCount("customer_country_risk", 2),
            CheckHitCount("customer_watchlist_screening", 1),
        ),
        average_risk_score=(
            63.75 if policy_version_id == "sample-kyc-policy-v1" else 57.50
        ),
        max_risk_score=110 if policy_version_id == "sample-kyc-policy-v1" else 45,
        pending_review_count=1 if policy_version_id == "sample-kyc-policy-v1" else 0,
        review_status_counts=(
            ReviewStatusCount(
                "pending_review",
                1 if policy_version_id == "sample-kyc-policy-v1" else 0,
            ),
            ReviewStatusCount("approved", 0),
            ReviewStatusCount(
                "rejected",
                0 if policy_version_id == "sample-kyc-policy-v1" else 1,
            ),
            ReviewStatusCount(
                "request_more_info",
                1 if policy_version_id == "sample-kyc-policy-v1" else 0,
            ),
        ),
    )


def _comparison_report() -> KycVersionComparisonReport:
    baseline = _summary_report(policy_version_id="sample-kyc-policy-v1")
    comparison = _summary_report(policy_version_id="sample-kyc-policy-v2")
    return KycVersionComparisonReport(
        version_type="policy",
        baseline_version_id="sample-kyc-policy-v1",
        comparison_version_id="sample-kyc-policy-v2",
        submitted_from=None,
        submitted_to=None,
        decided_from=None,
        decided_to=None,
        baseline_summary=baseline,
        comparison_summary=comparison,
        total_applications_delta=-3,
        customer_type_comparisons=(
            CustomerTypeComparison("individual", 3, 0, -3),
            CustomerTypeComparison("legal_entity", 1, 1, 0),
        ),
        decision_status_comparisons=(
            DecisionStatusComparison("approved", 1, 0, -1),
            DecisionStatusComparison("review", 2, 1, -1),
            DecisionStatusComparison("blocked", 1, 0, -1),
        ),
        check_hit_comparisons=(
            CheckHitComparison("customer_country_risk", 2, 1, -1),
            CheckHitComparison("customer_watchlist_screening", 1, 0, -1),
        ),
        average_risk_score_delta=-6.25,
        max_risk_score_delta=-65,
        pending_review_delta=-1,
        review_status_comparisons=(
            ReviewStatusComparison("pending_review", 1, 0, -1),
            ReviewStatusComparison("approved", 0, 0, 0),
            ReviewStatusComparison("rejected", 0, 1, 1),
            ReviewStatusComparison("request_more_info", 1, 0, -1),
        ),
    )


def _replay_report() -> KycReplayReport:
    return KycReplayReport(
        replay_policy_version_id="sample-kyc-policy-v2",
        replay_watchlist_version_id="sample-watchlist-v2",
        total_applications=2,
        status_changed_count=2,
        increased_risk_count=1,
        decreased_risk_count=1,
        unchanged_risk_count=0,
        items=(
            KycReplayItem(
                customer_id="cust_replay_001",
                original_status="approved",
                replay_status="review",
                status_changed=True,
                original_risk_score=0,
                replay_risk_score=25,
                risk_score_delta=25,
                original_check_ids=(),
                replay_check_ids=("expected_activity_volume",),
                new_check_ids=("expected_activity_volume",),
                resolved_check_ids=(),
            ),
            KycReplayItem(
                customer_id="cust_replay_002",
                original_status="blocked",
                replay_status="approved",
                status_changed=True,
                original_risk_score=100,
                replay_risk_score=0,
                risk_score_delta=-100,
                original_check_ids=("customer_watchlist_screening",),
                replay_check_ids=(),
                new_check_ids=(),
                resolved_check_ids=("customer_watchlist_screening",),
            ),
        ),
    )
