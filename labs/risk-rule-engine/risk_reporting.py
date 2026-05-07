from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from risk_rule_engine import ReviewStatus, RiskDecisionStatus, RiskRuleEngineError
from sqlite_risk_store import SQLiteRiskStore


@dataclass(frozen=True)
class DecisionStatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class RuleHitCount:
    rule_id: str
    count: int


@dataclass(frozen=True)
class ReviewStatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class RiskSummaryReport:
    total_decisions: int
    rule_version_id: str | None
    decided_from: datetime | None
    decided_to: datetime | None
    decision_status_counts: tuple[DecisionStatusCount, ...]
    rule_hit_counts: tuple[RuleHitCount, ...]
    average_risk_score: float
    max_risk_score: int
    pending_review_count: int
    review_status_counts: tuple[ReviewStatusCount, ...]


@dataclass(frozen=True)
class DecisionStatusComparison:
    status: str
    baseline_count: int
    comparison_count: int
    delta: int


@dataclass(frozen=True)
class RuleHitComparison:
    rule_id: str
    baseline_count: int
    comparison_count: int
    delta: int


@dataclass(frozen=True)
class ReviewStatusComparison:
    status: str
    baseline_count: int
    comparison_count: int
    delta: int


@dataclass(frozen=True)
class RiskRuleVersionComparisonReport:
    baseline_rule_version_id: str
    comparison_rule_version_id: str
    decided_from: datetime | None
    decided_to: datetime | None
    baseline_summary: RiskSummaryReport
    comparison_summary: RiskSummaryReport
    total_decisions_delta: int
    decision_status_comparisons: tuple[DecisionStatusComparison, ...]
    rule_hit_comparisons: tuple[RuleHitComparison, ...]
    average_risk_score_delta: float
    max_risk_score_delta: int
    pending_review_delta: int
    review_status_comparisons: tuple[ReviewStatusComparison, ...]


def build_risk_summary_report(
    store: SQLiteRiskStore,
    *,
    rule_version_id: str | None = None,
    decided_from: datetime | None = None,
    decided_to: datetime | None = None,
) -> RiskSummaryReport:
    normalized_rule_version_id = _normalize_rule_version_filter(store, rule_version_id)
    _validate_timestamp_filter(decided_from, field_name="decided_from")
    _validate_timestamp_filter(decided_to, field_name="decided_to")
    if decided_from is not None and decided_to is not None and decided_from > decided_to:
        raise RiskRuleEngineError("decided_from must be before decided_to")

    where_sql, parameters = _decision_filter_sql(
        rule_version_id=normalized_rule_version_id,
        decided_from=decided_from,
        decided_to=decided_to,
    )
    decision_rows = store._connection.execute(
        f"""
        SELECT request_id, status, risk_score
        FROM risk_decisions
        {where_sql}
        ORDER BY decided_at, request_id
        """,
        parameters,
    ).fetchall()
    request_ids = tuple(row["request_id"] for row in decision_rows)
    decision_status_counts = Counter(row["status"] for row in decision_rows)
    rule_hit_counts = _rule_hit_counts(store, request_ids)
    review_status_counts = _review_status_counts(store, request_ids)
    risk_scores = [row["risk_score"] for row in decision_rows]

    return RiskSummaryReport(
        total_decisions=len(decision_rows),
        rule_version_id=normalized_rule_version_id,
        decided_from=decided_from,
        decided_to=decided_to,
        decision_status_counts=tuple(
            DecisionStatusCount(status.value, decision_status_counts[status.value])
            for status in RiskDecisionStatus
        ),
        rule_hit_counts=tuple(
            RuleHitCount(rule_id, count)
            for rule_id, count in sorted(
                rule_hit_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        average_risk_score=(
            round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
        ),
        max_risk_score=max(risk_scores) if risk_scores else 0,
        pending_review_count=review_status_counts[ReviewStatus.PENDING_REVIEW.value],
        review_status_counts=tuple(
            ReviewStatusCount(status.value, review_status_counts[status.value])
            for status in ReviewStatus
        ),
    )


def build_rule_version_comparison_report(
    store: SQLiteRiskStore,
    *,
    baseline_rule_version_id: str,
    comparison_rule_version_id: str,
    decided_from: datetime | None = None,
    decided_to: datetime | None = None,
) -> RiskRuleVersionComparisonReport:
    baseline_version_id = _normalize_required_rule_version_filter(
        store,
        baseline_rule_version_id,
        field_name="baseline_rule_version_id",
    )
    comparison_version_id = _normalize_required_rule_version_filter(
        store,
        comparison_rule_version_id,
        field_name="comparison_rule_version_id",
    )
    if baseline_version_id == comparison_version_id:
        raise RiskRuleEngineError("Rule versions must be different")

    baseline_summary = build_risk_summary_report(
        store,
        rule_version_id=baseline_version_id,
        decided_from=decided_from,
        decided_to=decided_to,
    )
    comparison_summary = build_risk_summary_report(
        store,
        rule_version_id=comparison_version_id,
        decided_from=decided_from,
        decided_to=decided_to,
    )

    return RiskRuleVersionComparisonReport(
        baseline_rule_version_id=baseline_version_id,
        comparison_rule_version_id=comparison_version_id,
        decided_from=decided_from,
        decided_to=decided_to,
        baseline_summary=baseline_summary,
        comparison_summary=comparison_summary,
        total_decisions_delta=(
            comparison_summary.total_decisions - baseline_summary.total_decisions
        ),
        decision_status_comparisons=_decision_status_comparisons(
            baseline_summary,
            comparison_summary,
        ),
        rule_hit_comparisons=_rule_hit_comparisons(
            baseline_summary,
            comparison_summary,
        ),
        average_risk_score_delta=round(
            comparison_summary.average_risk_score - baseline_summary.average_risk_score,
            2,
        ),
        max_risk_score_delta=(
            comparison_summary.max_risk_score - baseline_summary.max_risk_score
        ),
        pending_review_delta=(
            comparison_summary.pending_review_count
            - baseline_summary.pending_review_count
        ),
        review_status_comparisons=_review_status_comparisons(
            baseline_summary,
            comparison_summary,
        ),
    )


def _normalize_rule_version_filter(
    store: SQLiteRiskStore,
    rule_version_id: str | None,
) -> str | None:
    if rule_version_id is None:
        return None
    normalized = rule_version_id.strip()
    if not normalized:
        raise RiskRuleEngineError("Rule version id is required")
    if store.find_rule_version(normalized) is None:
        raise RiskRuleEngineError(f"Unknown risk rule version: {normalized}")
    return normalized


def _normalize_required_rule_version_filter(
    store: SQLiteRiskStore,
    rule_version_id: str,
    *,
    field_name: str,
) -> str:
    normalized = _normalize_rule_version_filter(store, rule_version_id)
    if normalized is None:
        raise RiskRuleEngineError(f"{field_name} is required")
    return normalized


def _validate_timestamp_filter(value: datetime | None, *, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskRuleEngineError(f"{field_name} must be timezone-aware")


def _decision_filter_sql(
    *,
    rule_version_id: str | None,
    decided_from: datetime | None,
    decided_to: datetime | None,
) -> tuple[str, tuple[str, ...]]:
    clauses = []
    parameters = []
    if rule_version_id is not None:
        clauses.append("rule_version_id = ?")
        parameters.append(rule_version_id)
    if decided_from is not None:
        clauses.append("decided_at >= ?")
        parameters.append(decided_from.isoformat())
    if decided_to is not None:
        clauses.append("decided_at <= ?")
        parameters.append(decided_to.isoformat())
    if not clauses:
        return "", ()
    return "WHERE " + " AND ".join(clauses), tuple(parameters)


def _rule_hit_counts(
    store: SQLiteRiskStore,
    request_ids: tuple[str, ...],
) -> Counter:
    if not request_ids:
        return Counter()
    placeholders = ", ".join("?" for _ in request_ids)
    rows = store._connection.execute(
        f"""
        SELECT rule_id
        FROM risk_decision_rule_hits
        WHERE request_id IN ({placeholders})
        """,
        request_ids,
    ).fetchall()
    return Counter(row["rule_id"] for row in rows)


def _review_status_counts(
    store: SQLiteRiskStore,
    request_ids: tuple[str, ...],
) -> Counter:
    if not request_ids:
        return Counter()
    placeholders = ", ".join("?" for _ in request_ids)
    rows = store._connection.execute(
        f"""
        SELECT status
        FROM review_cases
        WHERE request_id IN ({placeholders})
        """,
        request_ids,
    ).fetchall()
    return Counter(row["status"] for row in rows)


def _decision_status_comparisons(
    baseline: RiskSummaryReport,
    comparison: RiskSummaryReport,
) -> tuple[DecisionStatusComparison, ...]:
    baseline_counts = {item.status: item.count for item in baseline.decision_status_counts}
    comparison_counts = {
        item.status: item.count for item in comparison.decision_status_counts
    }
    return tuple(
        DecisionStatusComparison(
            status=status.value,
            baseline_count=baseline_counts[status.value],
            comparison_count=comparison_counts[status.value],
            delta=comparison_counts[status.value] - baseline_counts[status.value],
        )
        for status in RiskDecisionStatus
    )


def _rule_hit_comparisons(
    baseline: RiskSummaryReport,
    comparison: RiskSummaryReport,
) -> tuple[RuleHitComparison, ...]:
    baseline_counts = {item.rule_id: item.count for item in baseline.rule_hit_counts}
    comparison_counts = {item.rule_id: item.count for item in comparison.rule_hit_counts}
    rule_ids = sorted(set(baseline_counts) | set(comparison_counts))
    return tuple(
        RuleHitComparison(
            rule_id=rule_id,
            baseline_count=baseline_counts.get(rule_id, 0),
            comparison_count=comparison_counts.get(rule_id, 0),
            delta=comparison_counts.get(rule_id, 0) - baseline_counts.get(rule_id, 0),
        )
        for rule_id in rule_ids
    )


def _review_status_comparisons(
    baseline: RiskSummaryReport,
    comparison: RiskSummaryReport,
) -> tuple[ReviewStatusComparison, ...]:
    baseline_counts = {item.status: item.count for item in baseline.review_status_counts}
    comparison_counts = {item.status: item.count for item in comparison.review_status_counts}
    return tuple(
        ReviewStatusComparison(
            status=status.value,
            baseline_count=baseline_counts[status.value],
            comparison_count=comparison_counts[status.value],
            delta=comparison_counts[status.value] - baseline_counts[status.value],
        )
        for status in ReviewStatus
    )
