from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from kyc_aml import (
    KycAmlEngine,
    KycAmlError,
    KycAmlPolicy,
    KycDecision,
    WatchlistEntry,
)
from sqlite_kyc_store import SQLiteKycStore


@dataclass(frozen=True)
class KycReplayItem:
    customer_id: str
    original_status: str
    replay_status: str
    status_changed: bool
    original_risk_score: int
    replay_risk_score: int
    risk_score_delta: int
    original_check_ids: tuple[str, ...]
    replay_check_ids: tuple[str, ...]
    new_check_ids: tuple[str, ...]
    resolved_check_ids: tuple[str, ...]


@dataclass(frozen=True)
class KycReplayReport:
    replay_policy_version_id: str | None
    replay_watchlist_version_id: str | None
    total_applications: int
    status_changed_count: int
    increased_risk_count: int
    decreased_risk_count: int
    unchanged_risk_count: int
    items: tuple[KycReplayItem, ...]


def build_kyc_replay_report(
    store: SQLiteKycStore,
    *,
    policy: KycAmlPolicy,
    watchlist: Iterable[WatchlistEntry] = (),
    replay_policy_version_id: str | None = None,
    replay_watchlist_version_id: str | None = None,
    customer_ids: Iterable[str] | None = None,
) -> KycReplayReport:
    normalized_policy_version_id = _normalize_policy_version_id(
        store,
        replay_policy_version_id,
    )
    normalized_watchlist_version_id = _normalize_watchlist_version_id(
        store,
        replay_watchlist_version_id,
    )
    selected_customer_ids = _customer_ids_for_replay(store, customer_ids)
    engine = KycAmlEngine(policy)
    normalized_watchlist = tuple(watchlist)

    items = []
    for customer_id in selected_customer_ids:
        application = store.get_application(customer_id)
        original_decision = store.get_decision(customer_id)
        replay_decision = engine.evaluate(application, watchlist=normalized_watchlist)
        items.append(_replay_item(original_decision, replay_decision))

    return KycReplayReport(
        replay_policy_version_id=normalized_policy_version_id,
        replay_watchlist_version_id=normalized_watchlist_version_id,
        total_applications=len(items),
        status_changed_count=sum(1 for item in items if item.status_changed),
        increased_risk_count=sum(1 for item in items if item.risk_score_delta > 0),
        decreased_risk_count=sum(1 for item in items if item.risk_score_delta < 0),
        unchanged_risk_count=sum(1 for item in items if item.risk_score_delta == 0),
        items=tuple(items),
    )


def _normalize_policy_version_id(
    store: SQLiteKycStore,
    replay_policy_version_id: str | None,
) -> str | None:
    if replay_policy_version_id is None:
        return None
    normalized = replay_policy_version_id.strip()
    if not normalized:
        raise KycAmlError("KYC replay policy version id is required")
    if store.find_policy_version(normalized) is None:
        raise KycAmlError(f"Unknown KYC policy version: {normalized}")
    return normalized


def _normalize_watchlist_version_id(
    store: SQLiteKycStore,
    replay_watchlist_version_id: str | None,
) -> str | None:
    if replay_watchlist_version_id is None:
        return None
    normalized = replay_watchlist_version_id.strip()
    if not normalized:
        raise KycAmlError("KYC replay watchlist version id is required")
    if store.find_watchlist_version(normalized) is None:
        raise KycAmlError(f"Unknown KYC watchlist version: {normalized}")
    return normalized


def _customer_ids_for_replay(
    store: SQLiteKycStore,
    customer_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    if customer_ids is None:
        rows = store._connection.execute(
            """
            SELECT a.customer_id
            FROM kyc_applications AS a
            JOIN kyc_decisions AS d ON d.customer_id = a.customer_id
            ORDER BY a.submitted_at, a.customer_id
            """
        ).fetchall()
        return tuple(row["customer_id"] for row in rows)

    normalized_ids = tuple(customer_id.strip() for customer_id in customer_ids)
    if any(not customer_id for customer_id in normalized_ids):
        raise KycAmlError("KYC replay customer id is required")
    for customer_id in normalized_ids:
        if store.find_application(customer_id) is None:
            raise KycAmlError(f"Unknown KYC application: {customer_id}")
        if store.find_decision(customer_id) is None:
            raise KycAmlError(f"Unknown KYC decision: {customer_id}")
    return normalized_ids


def _replay_item(
    original_decision: KycDecision,
    replay_decision: KycDecision,
) -> KycReplayItem:
    original_check_ids = _non_approved_check_ids(original_decision)
    replay_check_ids = _non_approved_check_ids(replay_decision)
    original_set = set(original_check_ids)
    replay_set = set(replay_check_ids)

    return KycReplayItem(
        customer_id=original_decision.customer_id,
        original_status=original_decision.status.value,
        replay_status=replay_decision.status.value,
        status_changed=original_decision.status != replay_decision.status,
        original_risk_score=original_decision.risk_score,
        replay_risk_score=replay_decision.risk_score,
        risk_score_delta=replay_decision.risk_score - original_decision.risk_score,
        original_check_ids=original_check_ids,
        replay_check_ids=replay_check_ids,
        new_check_ids=tuple(sorted(replay_set - original_set)),
        resolved_check_ids=tuple(sorted(original_set - replay_set)),
    )


def _non_approved_check_ids(decision: KycDecision) -> tuple[str, ...]:
    return tuple(
        result.check_id
        for result in decision.check_results
        if result.status.value != "approved"
    )
