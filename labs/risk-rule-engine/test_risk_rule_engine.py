from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from risk_rule_engine import (
    ManualReviewService,
    RiskDecisionStatus,
    RiskRuleConfig,
    RiskRuleEngine,
    RiskRuleEngineError,
    ReviewStatus,
    build_request,
)


def test_small_allowed_currency_request_is_approved() -> None:
    engine = RiskRuleEngine()
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "usd",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.rule_hits == ()


def test_large_single_transaction_goes_to_review() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    request = build_request(
        "txn_001",
        "user_001",
        "1000.01",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.REVIEW
    assert decision.rule_hits[0].rule_id == "single_transaction_amount"


def test_daily_user_total_goes_to_review() -> None:
    engine = RiskRuleEngine(daily_user_review_threshold="1000.00")
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request("txn_001", "user_001", "600.00", "USD", request_time),
    ]
    request = build_request(
        "txn_002",
        "user_001",
        "500.00",
        "USD",
        request_time + timedelta(hours=1),
    )

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.REVIEW
    daily_user_hit = _rule_hit(decision, "daily_user_amount")
    assert "Daily total 1100.00" in daily_user_hit.reason


def test_daily_user_total_ignores_other_user_date_and_currency() -> None:
    engine = RiskRuleEngine(daily_user_review_threshold="1000.00")
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request("txn_001", "user_002", "900.00", "USD", request_time),
        build_request("txn_002", "user_001", "900.00", "USD", request_time - timedelta(days=1)),
        build_request("txn_003", "user_001", "900.00", "EUR", request_time),
    ]
    request = build_request("txn_004", "user_001", "200.00", "USD", request_time)

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.APPROVED


def test_disallowed_currency_is_blocked() -> None:
    engine = RiskRuleEngine(allowed_currencies=("USD",))
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "JPY",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.BLOCKED
    assert decision.rule_hits[0].rule_id == "currency_allowed"


def test_blocked_takes_precedence_over_review() -> None:
    engine = RiskRuleEngine(
        single_transaction_review_threshold="1000.00",
        allowed_currencies=("USD",),
    )
    request = build_request(
        "txn_001",
        "user_001",
        "2000.00",
        "JPY",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.BLOCKED
    assert "currency_allowed" in [hit.rule_id for hit in decision.rule_hits]
    assert "single_transaction_amount" in [hit.rule_id for hit in decision.rule_hits]


def test_amount_must_be_positive() -> None:
    with pytest.raises(RiskRuleEngineError, match="Amount must be positive"):
        build_request(
            "txn_001",
            "user_001",
            "0.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        )


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(RiskRuleEngineError, match="created_at must be timezone-aware"):
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 9, 0),
        )


def test_blank_user_id_is_rejected() -> None:
    engine = RiskRuleEngine()
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    invalid_request = request.__class__(
        transaction_id=request.transaction_id,
        user_id=" ",
        amount=request.amount,
        currency=request.currency,
        created_at=request.created_at,
        device_id=request.device_id,
        ip_country=request.ip_country,
        beneficiary_id=request.beneficiary_id,
    )

    with pytest.raises(RiskRuleEngineError, match="User id is required"):
        engine.evaluate(invalid_request)


def test_allowed_currencies_are_required() -> None:
    with pytest.raises(RiskRuleEngineError, match="At least one allowed currency"):
        RiskRuleEngine(allowed_currencies=())


def test_engine_can_load_config_from_json() -> None:
    path = _test_data_directory() / f"{uuid4()}.json"
    path.write_text(
        "\n".join(
            [
                "{",
                '  "single_transaction_review_threshold": "500.00",',
                '  "daily_user_review_threshold": "1000.00",',
                '  "allowed_currencies": ["usd", "eur"],',
                '  "high_risk_countries": ["kp"],',
                '  "blocked_beneficiaries": ["beneficiary_blocked_001"],',
                '  "risk_score_review_threshold": 50,',
                '  "rule_scores": {"single_transaction_amount": 60}',
                "}",
            ]
        ),
        encoding="utf-8",
    )

    try:
        engine = RiskRuleEngine(config=RiskRuleConfig.from_json(path))
        request = build_request(
            "txn_001",
            "user_001",
            "500.01",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        )

        decision = engine.evaluate(request)

        assert decision.status == RiskDecisionStatus.REVIEW
        assert engine.allowed_currencies == {"USD", "EUR"}
        assert engine.high_risk_countries == {"KP"}
        assert engine.blocked_beneficiaries == {"beneficiary_blocked_001"}
        assert engine.risk_score_review_threshold == 50
        assert engine.rule_scores["single_transaction_amount"] == 60
    finally:
        if path.exists():
            path.unlink()


def test_config_rejects_missing_required_field() -> None:
    path = _test_data_directory() / f"{uuid4()}.json"
    path.write_text(
        "\n".join(
            [
                "{",
                '  "single_transaction_review_threshold": "500.00",',
                '  "allowed_currencies": ["USD"]',
                "}",
            ]
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(RiskRuleEngineError, match="Risk rule config missing fields"):
            RiskRuleConfig.from_json(path)
    finally:
        if path.exists():
            path.unlink()


def test_config_rejects_empty_allowed_currencies() -> None:
    path = _test_data_directory() / f"{uuid4()}.json"
    path.write_text(
        "\n".join(
            [
                "{",
                '  "single_transaction_review_threshold": "500.00",',
                '  "daily_user_review_threshold": "1000.00",',
                '  "allowed_currencies": [],',
                '  "high_risk_countries": [],',
                '  "blocked_beneficiaries": [],',
                '  "risk_score_review_threshold": 50,',
                '  "rule_scores": {}',
                "}",
            ]
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(RiskRuleEngineError, match="At least one allowed currency"):
            RiskRuleConfig.from_json(path)
    finally:
        if path.exists():
            path.unlink()


def test_high_risk_ip_country_is_blocked() -> None:
    engine = RiskRuleEngine(high_risk_countries=("KP",))
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        ip_country="kp",
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.BLOCKED
    assert decision.rule_hits[0].rule_id == "ip_country_allowed"
    assert decision.risk_score == 100


def test_blocked_beneficiary_is_blocked() -> None:
    engine = RiskRuleEngine(blocked_beneficiaries=("beneficiary_blocked_001",))
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        beneficiary_id="beneficiary_blocked_001",
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.BLOCKED
    assert decision.rule_hits[0].rule_id == "beneficiary_allowed"
    assert decision.risk_score == 100


def test_new_device_for_existing_user_goes_to_review() -> None:
    engine = RiskRuleEngine()
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            request_time,
            device_id="device_old",
        ),
    ]
    request = build_request(
        "txn_002",
        "user_001",
        "100.00",
        "USD",
        request_time,
        device_id="device_new",
    )

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.REVIEW
    assert decision.rule_hits[0].rule_id == "new_device"
    assert decision.risk_score == 35


def test_known_device_for_existing_user_is_not_reviewed() -> None:
    engine = RiskRuleEngine()
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            request_time,
            device_id="device_known",
        ),
    ]
    request = build_request(
        "txn_002",
        "user_001",
        "100.00",
        "USD",
        request_time,
        device_id="device_known",
    )

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.risk_score == 0


def test_multiple_weak_signals_can_cross_review_score_threshold() -> None:
    engine = RiskRuleEngine(
        risk_score_review_threshold=50,
        rule_scores={
            "new_device": 30,
            "single_transaction_amount": 30,
        },
        single_transaction_review_threshold="1000.00",
    )
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            request_time,
            device_id="device_old",
        ),
    ]
    request = build_request(
        "txn_002",
        "user_001",
        "1000.01",
        "USD",
        request_time,
        device_id="device_new",
    )

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.REVIEW
    assert decision.risk_score == 60


def test_review_rule_below_score_threshold_still_goes_to_review() -> None:
    engine = RiskRuleEngine(
        risk_score_review_threshold=100,
        rule_scores={"new_device": 10},
    )
    request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
    history = [
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            request_time,
            device_id="device_old",
        ),
    ]
    request = build_request(
        "txn_002",
        "user_001",
        "100.00",
        "USD",
        request_time,
        device_id="device_new",
    )

    decision = engine.evaluate(request, history=history)

    assert decision.status == RiskDecisionStatus.REVIEW
    assert decision.risk_score == 10


def test_score_only_signal_below_threshold_stays_approved() -> None:
    engine = RiskRuleEngine(risk_score_review_threshold=50)
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "USD",
        datetime(2026, 5, 5, 2, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert [(hit.rule_id, hit.status, hit.score) for hit in decision.rule_hits] == [
        ("unusual_hour", RiskDecisionStatus.APPROVED, 25),
    ]
    assert decision.risk_score == 25


def test_score_only_signals_can_cross_review_threshold() -> None:
    engine = RiskRuleEngine(risk_score_review_threshold=50)
    request = build_request(
        "txn_001",
        "user_001",
        "500.00",
        "USD",
        datetime(2026, 5, 5, 2, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.REVIEW
    assert [(hit.rule_id, hit.status, hit.score) for hit in decision.rule_hits] == [
        ("unusual_hour", RiskDecisionStatus.APPROVED, 25),
        ("round_amount", RiskDecisionStatus.APPROVED, 30),
    ]
    assert decision.risk_score == 55


def test_blocked_rule_still_takes_precedence_over_score_only_signals() -> None:
    engine = RiskRuleEngine(
        allowed_currencies=("USD",),
        risk_score_review_threshold=50,
    )
    request = build_request(
        "txn_001",
        "user_001",
        "500.00",
        "JPY",
        datetime(2026, 5, 5, 2, 0, tzinfo=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.status == RiskDecisionStatus.BLOCKED
    assert [hit.rule_id for hit in decision.rule_hits] == [
        "currency_allowed",
        "unusual_hour",
        "round_amount",
    ]
    assert decision.risk_score == 155


def test_blank_device_country_and_beneficiary_are_rejected() -> None:
    with pytest.raises(RiskRuleEngineError, match="Device id is required"):
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            device_id=" ",
        )

    with pytest.raises(RiskRuleEngineError, match="IP country is required"):
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            ip_country=" ",
        )

    with pytest.raises(RiskRuleEngineError, match="Beneficiary id is required"):
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            beneficiary_id=" ",
        )


def test_ip_country_must_be_two_letter_code() -> None:
    with pytest.raises(RiskRuleEngineError, match="2-letter country code"):
        build_request(
            "txn_001",
            "user_001",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            ip_country="USA",
        )


def test_review_decision_can_create_manual_review_case() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    decision = engine.evaluate(request)

    review_case = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )

    assert review_case.case_id == "review:txn_001"
    assert review_case.status == ReviewStatus.PENDING_REVIEW
    assert review_case.rule_hits == decision.rule_hits


def test_review_case_creation_is_idempotent_for_same_request() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    decision = engine.evaluate(request)

    first = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )
    second = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 5, 10, 5, tzinfo=timezone.utc),
    )

    assert second == first
    assert len(review_service.cases) == 1


def test_non_review_decision_cannot_create_manual_review_case() -> None:
    engine = RiskRuleEngine()
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "100.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    decision = engine.evaluate(request)

    with pytest.raises(RiskRuleEngineError, match="Only review decisions"):
        review_service.create_case(
            decision,
            created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
        )


def test_manual_review_case_can_be_approved() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    review_case = review_service.create_case(
        engine.evaluate(request),
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )

    completed = review_service.approve(
        review_case.case_id,
        reviewed_by="analyst_001",
        reason="Verified customer history",
        reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
    )

    assert completed.status == ReviewStatus.APPROVED
    assert completed.reviewed_by == "analyst_001"
    assert completed.review_reason == "Verified customer history"
    assert completed.reviewed_at == datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc)


def test_manual_review_case_can_be_rejected() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    review_case = review_service.create_case(
        engine.evaluate(request),
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )

    completed = review_service.reject(
        review_case.case_id,
        reviewed_by="analyst_001",
        reason="Customer could not verify activity",
        reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
    )

    assert completed.status == ReviewStatus.REJECTED
    assert completed.review_reason == "Customer could not verify activity"


def test_completed_review_case_cannot_be_completed_again() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    review_case = review_service.create_case(
        engine.evaluate(request),
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )
    review_service.approve(
        review_case.case_id,
        reviewed_by="analyst_001",
        reason="Verified customer history",
        reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(RiskRuleEngineError, match="already completed"):
        review_service.reject(
            review_case.case_id,
            reviewed_by="analyst_002",
            reason="Changed decision",
            reviewed_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        )


def test_manual_review_requires_reviewer_and_reason() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    review_case = review_service.create_case(
        engine.evaluate(request),
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(RiskRuleEngineError, match="Reviewer is required"):
        review_service.approve(
            review_case.case_id,
            reviewed_by=" ",
            reason="Verified",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )

    with pytest.raises(RiskRuleEngineError, match="Review reason is required"):
        review_service.approve(
            review_case.case_id,
            reviewed_by="analyst_001",
            reason=" ",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )


def test_manual_review_timestamps_must_be_timezone_aware() -> None:
    engine = RiskRuleEngine(single_transaction_review_threshold="1000.00")
    review_service = ManualReviewService()
    request = build_request(
        "txn_001",
        "user_001",
        "1500.00",
        "USD",
        datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
    )
    decision = engine.evaluate(request)

    with pytest.raises(RiskRuleEngineError, match="created_at must be timezone-aware"):
        review_service.create_case(
            decision,
            created_at=datetime(2026, 5, 5, 10, 0),
        )

    review_case = review_service.create_case(
        decision,
        created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(RiskRuleEngineError, match="reviewed_at must be timezone-aware"):
        review_service.approve(
            review_case.case_id,
            reviewed_by="analyst_001",
            reason="Verified customer history",
            reviewed_at=datetime(2026, 5, 5, 11, 0),
        )


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _rule_hit(decision, rule_id: str):
    for hit in decision.rule_hits:
        if hit.rule_id == rule_id:
            return hit
    raise AssertionError(f"Missing rule hit: {rule_id}")
