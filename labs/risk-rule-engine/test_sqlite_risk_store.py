from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from risk_rule_engine import (
    ManualReviewService,
    RiskDecision,
    RiskDecisionStatus,
    RiskRuleConfig,
    RiskRuleEngine,
    RiskRuleEngineError,
    ReviewStatus,
    build_request,
)
from sqlite_risk_store import SQLiteRiskStore


def test_store_can_save_and_load_risk_decision_with_rule_hits() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()

        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )

        loaded = store.get_decision(decision.request_id)
        assert loaded == decision
        assert "single_transaction_amount" in [
            hit.rule_id for hit in loaded.rule_hits
        ]
        assert loaded.risk_score == 90
        assert _rule_hit(loaded, "single_transaction_amount").score == 60
        assert [event.event_type for event in store.audit_events] == [
            "risk_decision.saved"
        ]
    finally:
        _close_and_remove(store)


def test_store_can_reopen_database_and_read_decision() -> None:
    database_path = _database_path()
    store = SQLiteRiskStore(database_path)
    decision = _review_decision()
    try:
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
    finally:
        store.close()

    reopened = SQLiteRiskStore(database_path)
    try:
        assert reopened.get_decision(decision.request_id) == decision
    finally:
        _close_and_remove(reopened)


def test_saving_same_decision_is_idempotent() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()

        first = store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
        second = store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 5, tzinfo=timezone.utc),
        )

        assert second == first
        assert store.decisions == (decision,)
        assert len(store.audit_events) == 1
    finally:
        _close_and_remove(store)


def test_saving_different_decision_for_same_request_is_rejected() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        conflicting_decision = RiskDecision(
            request_id=decision.request_id,
            user_id=decision.user_id,
            status=RiskDecisionStatus.APPROVED,
            rule_hits=(),
            risk_score=0,
        )
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )

        with pytest.raises(RiskRuleEngineError, match="already exists"):
            store.save_decision(
                conflicting_decision,
                decided_at=datetime(2026, 5, 5, 10, 5, tzinfo=timezone.utc),
            )
    finally:
        _close_and_remove(store)


def test_store_can_save_and_load_pending_review_case() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        review_case = _pending_review_case(decision)
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )

        store.save_review_case(review_case)

        loaded = store.get_review_case(review_case.case_id)
        assert loaded == review_case
        assert store.pending_review_cases == (review_case,)
        assert [event.event_type for event in store.audit_events] == [
            "risk_decision.saved",
            "review_case.created",
        ]
    finally:
        _close_and_remove(store)


def test_store_can_update_pending_review_case_to_approved() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        review_service = ManualReviewService()
        pending_case = review_service.create_case(
            decision,
            created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
        approved_case = review_service.approve(
            pending_case.case_id,
            reviewed_by="analyst_001",
            reason="Verified customer history",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
        )
        store.save_review_case(pending_case)

        stored_case = store.save_review_case(approved_case)

        assert stored_case == approved_case
        assert store.pending_review_cases == ()
        audit_events = store.audit_events_for(
            aggregate_type="review_case",
            aggregate_id=approved_case.case_id,
        )
        assert [event.event_type for event in audit_events] == [
            "review_case.created",
            "review_case.approved",
        ]
        assert audit_events[-1].actor == "analyst_001"
        assert audit_events[-1].reason == "Verified customer history"
    finally:
        _close_and_remove(store)


def test_store_records_rejected_review_case_audit_event() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        review_service = ManualReviewService()
        pending_case = review_service.create_case(
            decision,
            created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
        rejected_case = review_service.reject(
            pending_case.case_id,
            reviewed_by="analyst_001",
            reason="Customer could not verify activity",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
        )
        store.save_review_case(pending_case)

        store.save_review_case(rejected_case)

        assert store.audit_events[-1].event_type == "review_case.rejected"
        assert store.audit_events[-1].reason == "Customer could not verify activity"
    finally:
        _close_and_remove(store)


def test_store_can_reopen_database_and_read_audit_events() -> None:
    database_path = _database_path()
    store = SQLiteRiskStore(database_path)
    decision = _review_decision()
    try:
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
    finally:
        store.close()

    reopened = SQLiteRiskStore(database_path)
    try:
        assert [event.event_type for event in reopened.audit_events] == [
            "risk_decision.saved"
        ]
        assert reopened.audit_events[0].aggregate_id == decision.request_id
    finally:
        _close_and_remove(reopened)


def test_store_can_save_and_load_rule_version() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        rule_version = _save_rule_version(store)

        loaded = store.get_rule_version(rule_version.version_id)
        assert loaded == rule_version
        assert loaded.allowed_currencies == ("USD", "EUR")
        assert loaded.high_risk_countries == ("KP", "IR")
        assert loaded.blocked_beneficiaries == ("beneficiary_blocked_001",)
        assert loaded.risk_score_review_threshold == 50
        assert loaded.rule_scores["new_device"] == 35
        assert loaded.rule_scores["unusual_hour"] == 25
        assert loaded.rule_scores["round_amount"] == 30
        assert store.audit_events[-1].event_type == "risk_rule_version.saved"
    finally:
        _close_and_remove(store)


def test_saving_same_rule_version_is_idempotent() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        first = _save_rule_version(store)
        second = store.save_rule_version(
            _rule_config(),
            version_id=first.version_id,
            effective_at=first.effective_at,
            created_at=first.created_at,
        )

        assert second == first
        assert store.rule_versions == (first,)
        assert len(store.audit_events) == 1
    finally:
        _close_and_remove(store)


def test_saving_conflicting_rule_version_is_rejected() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        rule_version = _save_rule_version(store)
        conflicting_config = RiskRuleConfig(
            single_transaction_review_threshold=rule_version.single_transaction_review_threshold,
            daily_user_review_threshold="9999.00",
            allowed_currencies=("USD", "EUR"),
            high_risk_countries=("KP", "IR"),
            blocked_beneficiaries=("beneficiary_blocked_001",),
            risk_score_review_threshold=50,
            rule_scores={"new_device": 35, "unusual_hour": 25, "round_amount": 30},
        )

        with pytest.raises(RiskRuleEngineError, match="already exists"):
            store.save_rule_version(
                conflicting_config,
                version_id=rule_version.version_id,
                effective_at=rule_version.effective_at,
                created_at=rule_version.created_at,
            )
    finally:
        _close_and_remove(store)


def test_decision_can_reference_rule_version() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        rule_version = _save_rule_version(store)
        decision = _review_decision()

        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
            rule_version_id=rule_version.version_id,
        )

        assert store.rule_version_for_decision(decision.request_id) == rule_version
        assert f'"rule_version_id":"{rule_version.version_id}"' in store.audit_events[-1].payload
    finally:
        _close_and_remove(store)


def test_decision_rejects_unknown_rule_version() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        with pytest.raises(RiskRuleEngineError, match="Unknown risk rule version"):
            store.save_decision(
                _review_decision(),
                decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                rule_version_id="missing-version",
            )
    finally:
        _close_and_remove(store)


def test_same_decision_with_different_rule_version_is_rejected() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        first_version = _save_rule_version(store, version_id="rules-2026-05-05")
        second_version = _save_rule_version(store, version_id="rules-2026-05-06")
        decision = _review_decision()
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
            rule_version_id=first_version.version_id,
        )

        with pytest.raises(RiskRuleEngineError, match="different rule version"):
            store.save_decision(
                decision,
                decided_at=datetime(2026, 5, 5, 10, 5, tzinfo=timezone.utc),
                rule_version_id=second_version.version_id,
            )
    finally:
        _close_and_remove(store)


def test_store_can_reopen_database_and_read_rule_version_for_decision() -> None:
    database_path = _database_path()
    store = SQLiteRiskStore(database_path)
    decision = _review_decision()
    try:
        rule_version = _save_rule_version(store)
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
            rule_version_id=rule_version.version_id,
        )
    finally:
        store.close()

    reopened = SQLiteRiskStore(database_path)
    try:
        assert (
            reopened.rule_version_for_decision(decision.request_id).version_id
            == "rules-2026-05-05"
        )
    finally:
        _close_and_remove(reopened)


def test_completed_review_case_cannot_be_updated_again() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        review_service = ManualReviewService()
        pending_case = review_service.create_case(
            decision,
            created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )
        approved_case = review_service.approve(
            pending_case.case_id,
            reviewed_by="analyst_001",
            reason="Verified customer history",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )
        rejected_case = approved_case.__class__(
            case_id=approved_case.case_id,
            request_id=approved_case.request_id,
            user_id=approved_case.user_id,
            status=ReviewStatus.REJECTED,
            rule_hits=approved_case.rule_hits,
            created_at=approved_case.created_at,
            reviewed_by="analyst_002",
            review_reason="Changed decision",
            reviewed_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        )
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
        )
        store.save_review_case(pending_case)
        store.save_review_case(approved_case)

        with pytest.raises(RiskRuleEngineError, match="already completed"):
            store.save_review_case(rejected_case)
    finally:
        _close_and_remove(store)


def test_review_case_requires_saved_review_decision() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        decision = _review_decision()
        review_case = _pending_review_case(decision)

        with pytest.raises(RiskRuleEngineError, match="Unknown risk decision"):
            store.save_review_case(review_case)
    finally:
        _close_and_remove(store)


def test_review_case_cannot_be_created_for_approved_decision() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        approved_decision = RiskDecision(
            request_id="txn_approved",
            user_id="user_001",
            status=RiskDecisionStatus.APPROVED,
            rule_hits=(),
            risk_score=0,
        )
        review_case = _pending_review_case(
            RiskDecision(
                request_id=approved_decision.request_id,
                user_id=approved_decision.user_id,
                status=RiskDecisionStatus.REVIEW,
                rule_hits=(_review_decision().rule_hits[0],),
                risk_score=_review_decision().rule_hits[0].score,
            )
        )
        store.save_decision(
            approved_decision,
            decided_at=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
        )

        with pytest.raises(RiskRuleEngineError, match="Only review decisions"):
            store.save_review_case(review_case)
    finally:
        _close_and_remove(store)


def test_decided_at_must_be_timezone_aware() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        with pytest.raises(RiskRuleEngineError, match="decided_at must be timezone-aware"):
            store.save_decision(
                _review_decision(),
                decided_at=datetime(2026, 5, 5, 10, 0),
            )
    finally:
        _close_and_remove(store)


def _review_decision() -> RiskDecision:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    return engine.evaluate(request)


def _rule_config() -> RiskRuleConfig:
    return RiskRuleConfig(
        single_transaction_review_threshold="1000.00",
        daily_user_review_threshold="3000.00",
        allowed_currencies=("USD", "EUR"),
        high_risk_countries=("KP", "IR"),
        blocked_beneficiaries=("beneficiary_blocked_001",),
        risk_score_review_threshold=50,
        rule_scores={
            "currency_allowed": 100,
            "ip_country_allowed": 100,
            "beneficiary_allowed": 100,
            "single_transaction_amount": 60,
            "daily_user_amount": 70,
            "new_device": 35,
            "unusual_hour": 25,
            "round_amount": 30,
        },
    )


def _save_rule_version(
    store: SQLiteRiskStore,
    *,
    version_id: str = "rules-2026-05-05",
):
    return store.save_rule_version(
        _rule_config(),
        version_id=version_id,
        effective_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
    )


def _pending_review_case(decision: RiskDecision):
    review_service = ManualReviewService()
    return review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )


def _database_path() -> Path:
    return _test_data_directory() / f"{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _close_and_remove(store: SQLiteRiskStore) -> None:
    database_path = store.database_path
    store.close()
    if database_path.exists():
        database_path.unlink()


def _rule_hit(decision: RiskDecision, rule_id: str):
    for hit in decision.rule_hits:
        if hit.rule_id == rule_id:
            return hit
    raise AssertionError(f"Missing rule hit: {rule_id}")
