from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from risk_report_export import export_risk_reports
from risk_reporting import (
    DecisionStatusComparison,
    DecisionStatusCount,
    ReviewStatusComparison,
    ReviewStatusCount,
    RiskRuleVersionComparisonReport,
    RiskSummaryReport,
    RuleHitComparison,
    RuleHitCount,
)


def test_export_risk_summary_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    paths = export_risk_reports(
        output_directory,
        summary_report=_summary_report(rule_version_id="rules-2026-05-05"),
    )

    try:
        assert paths.summary_csv.exists()
        assert paths.comparison_csv is None
        assert paths.html_report.exists()

        summary_csv = paths.summary_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "section,metric,value" in summary_csv
        assert "metadata,rule_version_id,rules-2026-05-05" in summary_csv
        assert "summary,total_decisions,3" in summary_csv
        assert "decision_status,review,1" in summary_csv
        assert "Risk Rule Report" in html_report
        assert "No rule version comparison report was provided." in html_report
    finally:
        _remove_directory(output_directory)


def test_export_risk_reports_writes_comparison_csv_and_html() -> None:
    output_directory = _output_directory()
    comparison_report = _comparison_report()
    paths = export_risk_reports(
        output_directory,
        summary_report=comparison_report.comparison_summary,
        comparison_report=comparison_report,
    )

    try:
        assert paths.summary_csv.exists()
        assert paths.comparison_csv is not None
        assert paths.comparison_csv.exists()
        assert paths.html_report.exists()

        comparison_csv = paths.comparison_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert (
            "section,metric,baseline_value,comparison_value,delta"
            in comparison_csv
        )
        assert (
            "metadata,rule_version_id,rules-2026-05-05,rules-2026-05-05-strict,"
            in comparison_csv
        )
        assert "summary,average_risk_score,70.00,85.00,15.00" in comparison_csv
        assert "decision_status,blocked,1,2,1" in comparison_csv
        assert "Rule Version Comparison" in html_report
        assert "rules-2026-05-05-strict" in html_report
        assert "average_risk_score_delta" in html_report
    finally:
        _remove_directory(output_directory)


def _summary_report(*, rule_version_id: str | None) -> RiskSummaryReport:
    return RiskSummaryReport(
        total_decisions=3,
        rule_version_id=rule_version_id,
        decided_from=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        decided_to=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        decision_status_counts=(
            DecisionStatusCount("approved", 1),
            DecisionStatusCount("review", 1),
            DecisionStatusCount("blocked", 1),
        ),
        rule_hit_counts=(
            RuleHitCount("single_transaction_amount", 1),
            RuleHitCount("currency_allowed", 1),
        ),
        average_risk_score=70.0,
        max_risk_score=100,
        pending_review_count=1,
        review_status_counts=(
            ReviewStatusCount("pending_review", 1),
            ReviewStatusCount("approved", 0),
            ReviewStatusCount("rejected", 0),
        ),
    )


def _comparison_report() -> RiskRuleVersionComparisonReport:
    baseline = _summary_report(rule_version_id="rules-2026-05-05")
    comparison = RiskSummaryReport(
        total_decisions=3,
        rule_version_id="rules-2026-05-05-strict",
        decided_from=baseline.decided_from,
        decided_to=baseline.decided_to,
        decision_status_counts=(
            DecisionStatusCount("approved", 0),
            DecisionStatusCount("review", 1),
            DecisionStatusCount("blocked", 2),
        ),
        rule_hit_counts=(
            RuleHitCount("single_transaction_amount", 1),
            RuleHitCount("ip_country_allowed", 1),
            RuleHitCount("beneficiary_allowed", 1),
        ),
        average_risk_score=85.0,
        max_risk_score=100,
        pending_review_count=1,
        review_status_counts=(
            ReviewStatusCount("pending_review", 1),
            ReviewStatusCount("approved", 0),
            ReviewStatusCount("rejected", 0),
        ),
    )
    return RiskRuleVersionComparisonReport(
        baseline_rule_version_id="rules-2026-05-05",
        comparison_rule_version_id="rules-2026-05-05-strict",
        decided_from=baseline.decided_from,
        decided_to=baseline.decided_to,
        baseline_summary=baseline,
        comparison_summary=comparison,
        total_decisions_delta=0,
        decision_status_comparisons=(
            DecisionStatusComparison("approved", 1, 0, -1),
            DecisionStatusComparison("review", 1, 1, 0),
            DecisionStatusComparison("blocked", 1, 2, 1),
        ),
        rule_hit_comparisons=(
            RuleHitComparison("beneficiary_allowed", 0, 1, 1),
            RuleHitComparison("currency_allowed", 1, 0, -1),
            RuleHitComparison("ip_country_allowed", 0, 1, 1),
            RuleHitComparison("single_transaction_amount", 1, 1, 0),
        ),
        average_risk_score_delta=15.0,
        max_risk_score_delta=0,
        pending_review_delta=0,
        review_status_comparisons=(
            ReviewStatusComparison("pending_review", 1, 1, 0),
            ReviewStatusComparison("approved", 0, 0, 0),
            ReviewStatusComparison("rejected", 0, 0, 0),
        ),
    )


def _output_directory() -> Path:
    directory = _test_data_directory() / f"report-{uuid4()}"
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
