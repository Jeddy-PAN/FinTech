from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from risk_reporting import (
    build_risk_summary_report,
    build_rule_version_comparison_report,
)
from risk_rule_engine import (
    ManualReviewService,
    RiskRuleConfig,
    RiskRuleEngine,
    RiskRuleEngineError,
    build_request,
)
from sqlite_risk_store import SQLiteRiskStore


def test_empty_risk_summary_report_has_zero_values() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        report = build_risk_summary_report(store)

        assert report.total_decisions == 0
        assert report.average_risk_score == 0.0
        assert report.max_risk_score == 0
        assert report.pending_review_count == 0
        assert [item.count for item in report.decision_status_counts] == [0, 0, 0]
        assert report.rule_hit_counts == ()
        assert [item.count for item in report.review_status_counts] == [0, 0, 0]
    finally:
        _close_and_remove(store)


def test_risk_summary_report_counts_decisions_rules_scores_and_reviews() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        engine = RiskRuleEngine(
            single_transaction_review_threshold="1000.00",
            allowed_currencies=("USD",),
        )
        review_service = ManualReviewService()
        request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
        history = [
            build_request(
                "txn_history",
                "user_001",
                "100.00",
                "USD",
                request_time,
                device_id="device_old",
            ),
        ]
        requests = [
            build_request("txn_001", "user_002", "100.00", "USD", request_time),
            build_request(
                "txn_002",
                "user_001",
                "100.00",
                "USD",
                request_time,
                device_id="device_new",
            ),
            build_request("txn_003", "user_003", "1500.00", "USD", request_time),
            build_request("txn_004", "user_004", "100.00", "JPY", request_time),
        ]

        for request in requests:
            decision = engine.evaluate(request, history=history)
            store.save_decision(decision, decided_at=request_time)
            if decision.status.value == "review":
                review_case = review_service.create_case(
                    decision,
                    created_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                )
                store.save_review_case(review_case)

        approved_case = review_service.approve(
            "review:txn_002",
            reviewed_by="analyst_001",
            reason="Verified customer history",
            reviewed_at=datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
        )
        store.save_review_case(approved_case)

        report = build_risk_summary_report(store)

        assert report.total_decisions == 4
        assert [(item.status, item.count) for item in report.decision_status_counts] == [
            ("approved", 1),
            ("review", 2),
            ("blocked", 1),
        ]
        assert [(item.rule_id, item.count) for item in report.rule_hit_counts] == [
            ("currency_allowed", 1),
            ("new_device", 1),
            ("round_amount", 1),
            ("single_transaction_amount", 1),
        ]
        assert report.average_risk_score == 56.25
        assert report.max_risk_score == 100
        assert report.pending_review_count == 1
        assert [(item.status, item.count) for item in report.review_status_counts] == [
            ("pending_review", 1),
            ("approved", 1),
            ("rejected", 0),
        ]
    finally:
        _close_and_remove(store)


def test_risk_summary_report_can_filter_by_rule_version_and_decided_time() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        first_version = _save_rule_version(store, version_id="rules-2026-05-05")
        second_version = _save_rule_version(store, version_id="rules-2026-05-06")
        engine = RiskRuleEngine(
            single_transaction_review_threshold="1000.00",
            allowed_currencies=("USD",),
        )
        review_service = ManualReviewService()
        early_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
        target_time = datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)
        late_time = datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc)

        early_decision = engine.evaluate(
            build_request("txn_001", "user_001", "100.00", "USD", early_time)
        )
        target_decision = engine.evaluate(
            build_request("txn_002", "user_002", "1500.00", "USD", target_time)
        )
        late_decision = engine.evaluate(
            build_request("txn_003", "user_003", "100.00", "JPY", late_time)
        )
        store.save_decision(
            early_decision,
            decided_at=early_time,
            rule_version_id=first_version.version_id,
        )
        store.save_decision(
            target_decision,
            decided_at=target_time,
            rule_version_id=first_version.version_id,
        )
        store.save_decision(
            late_decision,
            decided_at=late_time,
            rule_version_id=second_version.version_id,
        )
        store.save_review_case(
            review_service.create_case(
                target_decision,
                created_at=datetime(2026, 5, 5, 10, 5, tzinfo=timezone.utc),
            )
        )

        report = build_risk_summary_report(
            store,
            rule_version_id=first_version.version_id,
            decided_from=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
            decided_to=datetime(2026, 5, 5, 10, 30, tzinfo=timezone.utc),
        )

        assert report.rule_version_id == "rules-2026-05-05"
        assert report.decided_from == datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc)
        assert report.decided_to == datetime(2026, 5, 5, 10, 30, tzinfo=timezone.utc)
        assert report.total_decisions == 1
        assert [(item.status, item.count) for item in report.decision_status_counts] == [
            ("approved", 0),
            ("review", 1),
            ("blocked", 0),
        ]
        assert [(item.rule_id, item.count) for item in report.rule_hit_counts] == [
            ("round_amount", 1),
            ("single_transaction_amount", 1),
        ]
        assert report.average_risk_score == 90.0
        assert report.max_risk_score == 90
        assert report.pending_review_count == 1
    finally:
        _close_and_remove(store)


def test_risk_summary_report_can_filter_by_rule_version_only() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        first_version = _save_rule_version(store, version_id="rules-2026-05-05")
        second_version = _save_rule_version(store, version_id="rules-2026-05-06")
        engine = RiskRuleEngine(allowed_currencies=("USD",))
        request_time = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
        approved_decision = engine.evaluate(
            build_request("txn_001", "user_001", "100.00", "USD", request_time)
        )
        blocked_decision = engine.evaluate(
            build_request("txn_002", "user_002", "100.00", "JPY", request_time)
        )
        store.save_decision(
            approved_decision,
            decided_at=request_time,
            rule_version_id=first_version.version_id,
        )
        store.save_decision(
            blocked_decision,
            decided_at=request_time,
            rule_version_id=second_version.version_id,
        )

        report = build_risk_summary_report(
            store,
            rule_version_id=second_version.version_id,
        )

        assert report.total_decisions == 1
        assert [(item.status, item.count) for item in report.decision_status_counts] == [
            ("approved", 0),
            ("review", 0),
            ("blocked", 1),
        ]
        assert [(item.rule_id, item.count) for item in report.rule_hit_counts] == [
            ("currency_allowed", 1),
        ]
    finally:
        _close_and_remove(store)


def test_risk_summary_report_rejects_invalid_filters() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        with pytest.raises(RiskRuleEngineError, match="Unknown risk rule version"):
            build_risk_summary_report(store, rule_version_id="missing-version")

        with pytest.raises(RiskRuleEngineError, match="decided_from must be timezone-aware"):
            build_risk_summary_report(store, decided_from=datetime(2026, 5, 5, 9, 0))

        with pytest.raises(RiskRuleEngineError, match="decided_from must be before"):
            build_risk_summary_report(
                store,
                decided_from=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                decided_to=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            )
    finally:
        _close_and_remove(store)


def test_rule_version_comparison_report_shows_deltas() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        baseline_config = _rule_config(single_transaction_review_threshold="1000.00")
        comparison_config = _rule_config(single_transaction_review_threshold="800.00")
        baseline_version = _save_rule_version(
            store,
            version_id="rules-2026-05-05",
            config=baseline_config,
        )
        comparison_version = _save_rule_version(
            store,
            version_id="rules-2026-05-06",
            config=comparison_config,
        )
        baseline_engine = RiskRuleEngine(config=baseline_config)
        comparison_engine = RiskRuleEngine(config=comparison_config)
        review_service = ManualReviewService()
        outside_time = datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc)
        report_start = datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)
        report_end = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)

        baseline_approved = baseline_engine.evaluate(
            build_request("txn_base_001", "user_001", "900.00", "USD", report_start)
        )
        baseline_review = baseline_engine.evaluate(
            build_request("txn_base_002", "user_002", "1100.00", "USD", report_start)
        )
        comparison_review = comparison_engine.evaluate(
            build_request("txn_comp_001", "user_003", "900.00", "USD", report_start)
        )
        comparison_blocked = comparison_engine.evaluate(
            build_request("txn_comp_002", "user_004", "100.00", "JPY", report_start)
        )
        outside_decision = comparison_engine.evaluate(
            build_request("txn_comp_003", "user_005", "100.00", "JPY", outside_time)
        )

        store.save_decision(
            baseline_approved,
            decided_at=report_start,
            rule_version_id=baseline_version.version_id,
        )
        store.save_decision(
            baseline_review,
            decided_at=report_start,
            rule_version_id=baseline_version.version_id,
        )
        store.save_decision(
            comparison_review,
            decided_at=report_start,
            rule_version_id=comparison_version.version_id,
        )
        store.save_decision(
            comparison_blocked,
            decided_at=report_start,
            rule_version_id=comparison_version.version_id,
        )
        store.save_decision(
            outside_decision,
            decided_at=outside_time,
            rule_version_id=comparison_version.version_id,
        )

        baseline_case = review_service.create_case(
            baseline_review,
            created_at=datetime(2026, 5, 5, 9, 10, tzinfo=timezone.utc),
        )
        store.save_review_case(baseline_case)
        store.save_review_case(
            review_service.approve(
                baseline_case.case_id,
                reviewed_by="analyst_001",
                reason="Verified customer history",
                reviewed_at=datetime(2026, 5, 5, 9, 30, tzinfo=timezone.utc),
            )
        )
        store.save_review_case(
            review_service.create_case(
                comparison_review,
                created_at=datetime(2026, 5, 5, 9, 10, tzinfo=timezone.utc),
            )
        )

        report = build_rule_version_comparison_report(
            store,
            baseline_rule_version_id=baseline_version.version_id,
            comparison_rule_version_id=comparison_version.version_id,
            decided_from=report_start,
            decided_to=report_end,
        )

        assert report.baseline_rule_version_id == "rules-2026-05-05"
        assert report.comparison_rule_version_id == "rules-2026-05-06"
        assert report.total_decisions_delta == 0
        assert [
            (item.status, item.baseline_count, item.comparison_count, item.delta)
            for item in report.decision_status_comparisons
        ] == [
            ("approved", 1, 0, -1),
            ("review", 1, 1, 0),
            ("blocked", 0, 1, 1),
        ]
        assert [
            (item.rule_id, item.baseline_count, item.comparison_count, item.delta)
            for item in report.rule_hit_comparisons
        ] == [
            ("currency_allowed", 0, 1, 1),
            ("round_amount", 2, 1, -1),
            ("single_transaction_amount", 1, 1, 0),
        ]
        assert report.average_risk_score_delta == 35.0
        assert report.max_risk_score_delta == 10
        assert report.pending_review_delta == 1
        assert [
            (item.status, item.baseline_count, item.comparison_count, item.delta)
            for item in report.review_status_comparisons
        ] == [
            ("pending_review", 0, 1, 1),
            ("approved", 1, 0, -1),
            ("rejected", 0, 0, 0),
        ]
    finally:
        _close_and_remove(store)


def test_rule_version_comparison_rejects_same_rule_version() -> None:
    store = SQLiteRiskStore(_database_path())
    try:
        version = _save_rule_version(store, version_id="rules-2026-05-05")

        with pytest.raises(RiskRuleEngineError, match="Rule versions must be different"):
            build_rule_version_comparison_report(
                store,
                baseline_rule_version_id=version.version_id,
                comparison_rule_version_id=version.version_id,
            )
    finally:
        _close_and_remove(store)


def _rule_config(
    *,
    single_transaction_review_threshold: str = "1000.00",
) -> RiskRuleConfig:
    return RiskRuleConfig(
        single_transaction_review_threshold=single_transaction_review_threshold,
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
    version_id: str,
    config: RiskRuleConfig | None = None,
):
    return store.save_rule_version(
        config or _rule_config(),
        version_id=version_id,
        effective_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
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
