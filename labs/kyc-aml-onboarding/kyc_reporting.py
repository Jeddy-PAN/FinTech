from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from kyc_aml import CustomerType, KycAmlError, KycDecisionStatus, KycReviewStatus
from sqlite_kyc_store import SQLiteKycStore


@dataclass(frozen=True)
class CustomerTypeCount:
    customer_type: str
    count: int


@dataclass(frozen=True)
class DecisionStatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class CheckHitCount:
    check_id: str
    count: int


@dataclass(frozen=True)
class ReviewStatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class CustomerTypeComparison:
    customer_type: str
    baseline_count: int
    comparison_count: int
    delta: int


@dataclass(frozen=True)
class DecisionStatusComparison:
    status: str
    baseline_count: int
    comparison_count: int
    delta: int


@dataclass(frozen=True)
class CheckHitComparison:
    check_id: str
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
class KycSummaryReport:
    total_applications: int
    customer_type: str | None
    decision_status: str | None
    watchlist_version_id: str | None
    policy_version_id: str | None
    submitted_from: datetime | None
    submitted_to: datetime | None
    decided_from: datetime | None
    decided_to: datetime | None
    customer_type_counts: tuple[CustomerTypeCount, ...]
    decision_status_counts: tuple[DecisionStatusCount, ...]
    check_hit_counts: tuple[CheckHitCount, ...]
    average_risk_score: float
    max_risk_score: int
    pending_review_count: int
    review_status_counts: tuple[ReviewStatusCount, ...]


@dataclass(frozen=True)
class KycVersionComparisonReport:
    version_type: str
    baseline_version_id: str
    comparison_version_id: str
    submitted_from: datetime | None
    submitted_to: datetime | None
    decided_from: datetime | None
    decided_to: datetime | None
    baseline_summary: KycSummaryReport
    comparison_summary: KycSummaryReport
    total_applications_delta: int
    customer_type_comparisons: tuple[CustomerTypeComparison, ...]
    decision_status_comparisons: tuple[DecisionStatusComparison, ...]
    check_hit_comparisons: tuple[CheckHitComparison, ...]
    average_risk_score_delta: float
    max_risk_score_delta: int
    pending_review_delta: int
    review_status_comparisons: tuple[ReviewStatusComparison, ...]


def build_kyc_summary_report(
    store: SQLiteKycStore,
    *,
    customer_type: str | CustomerType | None = None,
    decision_status: str | KycDecisionStatus | None = None,
    watchlist_version_id: str | None = None,
    policy_version_id: str | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    decided_from: datetime | None = None,
    decided_to: datetime | None = None,
) -> KycSummaryReport:
    normalized_customer_type = _normalize_customer_type_filter(customer_type)
    normalized_decision_status = _normalize_decision_status_filter(decision_status)
    normalized_watchlist_version_id = _normalize_watchlist_version_filter(
        store,
        watchlist_version_id,
    )
    normalized_policy_version_id = _normalize_policy_version_filter(
        store,
        policy_version_id,
    )
    _validate_timestamp_filter(submitted_from, field_name="submitted_from")
    _validate_timestamp_filter(submitted_to, field_name="submitted_to")
    _validate_timestamp_filter(decided_from, field_name="decided_from")
    _validate_timestamp_filter(decided_to, field_name="decided_to")
    _validate_time_window(submitted_from, submitted_to, field_name="submitted")
    _validate_time_window(decided_from, decided_to, field_name="decided")

    where_sql, parameters = _application_decision_filter_sql(
        customer_type=normalized_customer_type,
        decision_status=normalized_decision_status,
        watchlist_version_id=normalized_watchlist_version_id,
        policy_version_id=normalized_policy_version_id,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
    )
    rows = store._connection.execute(
        f"""
        SELECT
            a.customer_id,
            a.customer_type,
            d.status,
            d.risk_score
        FROM kyc_applications AS a
        JOIN kyc_decisions AS d ON d.customer_id = a.customer_id
        {where_sql}
        ORDER BY a.submitted_at, a.customer_id
        """,
        parameters,
    ).fetchall()
    customer_ids = tuple(row["customer_id"] for row in rows)
    customer_type_counts = Counter(row["customer_type"] for row in rows)
    decision_status_counts = Counter(row["status"] for row in rows)
    check_hit_counts = _check_hit_counts(store, customer_ids)
    review_status_counts = _review_status_counts(store, customer_ids)
    risk_scores = [row["risk_score"] for row in rows]

    return KycSummaryReport(
        total_applications=len(rows),
        customer_type=normalized_customer_type,
        decision_status=normalized_decision_status,
        watchlist_version_id=normalized_watchlist_version_id,
        policy_version_id=normalized_policy_version_id,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
        customer_type_counts=tuple(
            CustomerTypeCount(customer_type.value, customer_type_counts[customer_type.value])
            for customer_type in CustomerType
        ),
        decision_status_counts=tuple(
            DecisionStatusCount(status.value, decision_status_counts[status.value])
            for status in KycDecisionStatus
        ),
        check_hit_counts=tuple(
            CheckHitCount(check_id, count)
            for check_id, count in sorted(
                check_hit_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        average_risk_score=(
            round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
        ),
        max_risk_score=max(risk_scores) if risk_scores else 0,
        pending_review_count=review_status_counts[KycReviewStatus.PENDING_REVIEW.value],
        review_status_counts=tuple(
            ReviewStatusCount(status.value, review_status_counts[status.value])
            for status in KycReviewStatus
        ),
    )


def build_watchlist_version_comparison_report(
    store: SQLiteKycStore,
    *,
    baseline_watchlist_version_id: str,
    comparison_watchlist_version_id: str,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    decided_from: datetime | None = None,
    decided_to: datetime | None = None,
) -> KycVersionComparisonReport:
    baseline_version_id = _normalize_required_watchlist_version_filter(
        store,
        baseline_watchlist_version_id,
        field_name="baseline_watchlist_version_id",
    )
    comparison_version_id = _normalize_required_watchlist_version_filter(
        store,
        comparison_watchlist_version_id,
        field_name="comparison_watchlist_version_id",
    )
    if baseline_version_id == comparison_version_id:
        raise KycAmlError("Watchlist versions must be different")

    return _build_version_comparison_report(
        store,
        version_type="watchlist",
        baseline_version_id=baseline_version_id,
        comparison_version_id=comparison_version_id,
        baseline_kwargs={"watchlist_version_id": baseline_version_id},
        comparison_kwargs={"watchlist_version_id": comparison_version_id},
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
    )


def build_policy_version_comparison_report(
    store: SQLiteKycStore,
    *,
    baseline_policy_version_id: str,
    comparison_policy_version_id: str,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    decided_from: datetime | None = None,
    decided_to: datetime | None = None,
) -> KycVersionComparisonReport:
    baseline_version_id = _normalize_required_policy_version_filter(
        store,
        baseline_policy_version_id,
        field_name="baseline_policy_version_id",
    )
    comparison_version_id = _normalize_required_policy_version_filter(
        store,
        comparison_policy_version_id,
        field_name="comparison_policy_version_id",
    )
    if baseline_version_id == comparison_version_id:
        raise KycAmlError("Policy versions must be different")

    return _build_version_comparison_report(
        store,
        version_type="policy",
        baseline_version_id=baseline_version_id,
        comparison_version_id=comparison_version_id,
        baseline_kwargs={"policy_version_id": baseline_version_id},
        comparison_kwargs={"policy_version_id": comparison_version_id},
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
    )


def _build_version_comparison_report(
    store: SQLiteKycStore,
    *,
    version_type: str,
    baseline_version_id: str,
    comparison_version_id: str,
    baseline_kwargs: dict[str, str],
    comparison_kwargs: dict[str, str],
    submitted_from: datetime | None,
    submitted_to: datetime | None,
    decided_from: datetime | None,
    decided_to: datetime | None,
) -> KycVersionComparisonReport:
    baseline_summary = build_kyc_summary_report(
        store,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
        **baseline_kwargs,
    )
    comparison_summary = build_kyc_summary_report(
        store,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
        **comparison_kwargs,
    )

    return KycVersionComparisonReport(
        version_type=version_type,
        baseline_version_id=baseline_version_id,
        comparison_version_id=comparison_version_id,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        decided_from=decided_from,
        decided_to=decided_to,
        baseline_summary=baseline_summary,
        comparison_summary=comparison_summary,
        total_applications_delta=(
            comparison_summary.total_applications - baseline_summary.total_applications
        ),
        customer_type_comparisons=_customer_type_comparisons(
            baseline_summary,
            comparison_summary,
        ),
        decision_status_comparisons=_decision_status_comparisons(
            baseline_summary,
            comparison_summary,
        ),
        check_hit_comparisons=_check_hit_comparisons_for_report(
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
        review_status_comparisons=_review_status_comparisons_for_report(
            baseline_summary,
            comparison_summary,
        ),
    )


def _normalize_customer_type_filter(
    customer_type: str | CustomerType | None,
) -> str | None:
    if customer_type is None:
        return None
    try:
        return CustomerType(customer_type).value
    except ValueError as exc:
        raise KycAmlError(f"Unknown customer type: {customer_type}") from exc


def _normalize_decision_status_filter(
    decision_status: str | KycDecisionStatus | None,
) -> str | None:
    if decision_status is None:
        return None
    try:
        return KycDecisionStatus(decision_status).value
    except ValueError as exc:
        raise KycAmlError(f"Unknown KYC decision status: {decision_status}") from exc


def _normalize_watchlist_version_filter(
    store: SQLiteKycStore,
    watchlist_version_id: str | None,
) -> str | None:
    if watchlist_version_id is None:
        return None
    normalized = watchlist_version_id.strip()
    if not normalized:
        raise KycAmlError("Watchlist version id is required")
    if store.find_watchlist_version(normalized) is None:
        raise KycAmlError(f"Unknown KYC watchlist version: {normalized}")
    return normalized


def _normalize_required_watchlist_version_filter(
    store: SQLiteKycStore,
    watchlist_version_id: str,
    *,
    field_name: str,
) -> str:
    normalized = _normalize_watchlist_version_filter(store, watchlist_version_id)
    if normalized is None:
        raise KycAmlError(f"{field_name} is required")
    return normalized


def _normalize_policy_version_filter(
    store: SQLiteKycStore,
    policy_version_id: str | None,
) -> str | None:
    if policy_version_id is None:
        return None
    normalized = policy_version_id.strip()
    if not normalized:
        raise KycAmlError("KYC policy version id is required")
    if store.find_policy_version(normalized) is None:
        raise KycAmlError(f"Unknown KYC policy version: {normalized}")
    return normalized


def _normalize_required_policy_version_filter(
    store: SQLiteKycStore,
    policy_version_id: str,
    *,
    field_name: str,
) -> str:
    normalized = _normalize_policy_version_filter(store, policy_version_id)
    if normalized is None:
        raise KycAmlError(f"{field_name} is required")
    return normalized


def _validate_timestamp_filter(value: datetime | None, *, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise KycAmlError(f"{field_name} must be timezone-aware")


def _validate_time_window(
    start: datetime | None,
    end: datetime | None,
    *,
    field_name: str,
) -> None:
    if start is not None and end is not None and start > end:
        raise KycAmlError(f"{field_name}_from must be before {field_name}_to")


def _application_decision_filter_sql(
    *,
    customer_type: str | None,
    decision_status: str | None,
    watchlist_version_id: str | None,
    policy_version_id: str | None,
    submitted_from: datetime | None,
    submitted_to: datetime | None,
    decided_from: datetime | None,
    decided_to: datetime | None,
) -> tuple[str, tuple[str, ...]]:
    clauses = []
    parameters = []
    if customer_type is not None:
        clauses.append("a.customer_type = ?")
        parameters.append(customer_type)
    if decision_status is not None:
        clauses.append("d.status = ?")
        parameters.append(decision_status)
    if watchlist_version_id is not None:
        clauses.append("d.watchlist_version_id = ?")
        parameters.append(watchlist_version_id)
    if policy_version_id is not None:
        clauses.append("d.policy_version_id = ?")
        parameters.append(policy_version_id)
    if submitted_from is not None:
        clauses.append("a.submitted_at >= ?")
        parameters.append(submitted_from.isoformat())
    if submitted_to is not None:
        clauses.append("a.submitted_at <= ?")
        parameters.append(submitted_to.isoformat())
    if decided_from is not None:
        clauses.append("d.decided_at >= ?")
        parameters.append(decided_from.isoformat())
    if decided_to is not None:
        clauses.append("d.decided_at <= ?")
        parameters.append(decided_to.isoformat())

    if not clauses:
        return "", ()
    return "WHERE " + " AND ".join(clauses), tuple(parameters)


def _check_hit_counts(
    store: SQLiteKycStore,
    customer_ids: tuple[str, ...],
) -> Counter:
    if not customer_ids:
        return Counter()
    placeholders = ", ".join("?" for _ in customer_ids)
    rows = store._connection.execute(
        f"""
        SELECT check_id
        FROM kyc_check_results
        WHERE customer_id IN ({placeholders})
        AND status != 'approved'
        """,
        customer_ids,
    ).fetchall()
    return Counter(row["check_id"] for row in rows)


def _review_status_counts(
    store: SQLiteKycStore,
    customer_ids: tuple[str, ...],
) -> Counter:
    if not customer_ids:
        return Counter()
    placeholders = ", ".join("?" for _ in customer_ids)
    rows = store._connection.execute(
        f"""
        SELECT status
        FROM kyc_review_cases
        WHERE customer_id IN ({placeholders})
        """,
        customer_ids,
    ).fetchall()
    return Counter(row["status"] for row in rows)


def _customer_type_comparisons(
    baseline: KycSummaryReport,
    comparison: KycSummaryReport,
) -> tuple[CustomerTypeComparison, ...]:
    baseline_counts = {
        item.customer_type: item.count for item in baseline.customer_type_counts
    }
    comparison_counts = {
        item.customer_type: item.count for item in comparison.customer_type_counts
    }
    return tuple(
        CustomerTypeComparison(
            customer_type=customer_type.value,
            baseline_count=baseline_counts[customer_type.value],
            comparison_count=comparison_counts[customer_type.value],
            delta=(
                comparison_counts[customer_type.value]
                - baseline_counts[customer_type.value]
            ),
        )
        for customer_type in CustomerType
    )


def _decision_status_comparisons(
    baseline: KycSummaryReport,
    comparison: KycSummaryReport,
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
        for status in KycDecisionStatus
    )


def _check_hit_comparisons_for_report(
    baseline: KycSummaryReport,
    comparison: KycSummaryReport,
) -> tuple[CheckHitComparison, ...]:
    baseline_counts = {item.check_id: item.count for item in baseline.check_hit_counts}
    comparison_counts = {item.check_id: item.count for item in comparison.check_hit_counts}
    check_ids = sorted(set(baseline_counts) | set(comparison_counts))
    return tuple(
        CheckHitComparison(
            check_id=check_id,
            baseline_count=baseline_counts.get(check_id, 0),
            comparison_count=comparison_counts.get(check_id, 0),
            delta=comparison_counts.get(check_id, 0) - baseline_counts.get(check_id, 0),
        )
        for check_id in check_ids
    )


def _review_status_comparisons_for_report(
    baseline: KycSummaryReport,
    comparison: KycSummaryReport,
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
        for status in KycReviewStatus
    )
