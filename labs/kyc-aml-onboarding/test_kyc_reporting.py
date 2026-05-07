from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from kyc_aml import (
    BeneficialOwner,
    CustomerType,
    KycAmlEngine,
    KycAmlError,
    KycAmlPolicy,
    KycDecisionStatus,
    KycReviewService,
    KycReviewStatus,
    WatchlistEntry,
    build_individual_application,
    build_legal_entity_application,
)
from kyc_reporting import build_kyc_summary_report
from kyc_reporting import (
    build_policy_version_comparison_report,
    build_watchlist_version_comparison_report,
)
from sqlite_kyc_store import SQLiteKycStore


def store_path():
    data_dir = Path(__file__).parent / ".test-data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"{uuid4()}.db"


def seed_store():
    store = SQLiteKycStore(store_path())
    engine = KycAmlEngine(
        KycAmlPolicy(
            high_risk_countries=("XZ",),
            high_expected_monthly_volume_cents=1_000_000,
        )
    )
    policy = engine.policy
    review_service = KycReviewService()
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
    first_version = store.save_watchlist_version(
        watchlist,
        version_id="sample-watchlist-v1",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    second_version = store.save_watchlist_version(
        (),
        version_id="sample-watchlist-v2",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 1, tzinfo=timezone.utc),
    )
    first_policy_version = store.save_policy_version(
        policy,
        version_id="sample-kyc-policy-v1",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 2, tzinfo=timezone.utc),
    )
    second_policy_version = store.save_policy_version(
        KycAmlPolicy(
            high_risk_countries=("XZ", "ZZ"),
            high_expected_monthly_volume_cents=1_000_000,
        ),
        version_id="sample-kyc-policy-v2",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 2, tzinfo=timezone.utc),
    )
    base_time = datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc)

    rows = (
        (
            build_individual_application(
                "cust_report_001",
                "Jordan Smith",
                date_of_birth=date(1992, 5, 20),
                country="US",
                address="100 Market Street",
                identification_number="ID-1001",
                expected_monthly_volume_cents=250_000,
            ),
            None,
        ),
        (
            build_legal_entity_application(
                "cust_report_002",
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
            KycReviewStatus.REQUEST_MORE_INFO,
        ),
        (
            build_individual_application(
                "cust_report_003",
                "Alex Blocked",
                date_of_birth=date(1980, 1, 1),
                country="US",
                address="300 Main Street",
                identification_number="ID-3003",
                expected_monthly_volume_cents=100_000,
            ),
            None,
        ),
        (
            build_individual_application(
                "cust_report_004",
                "Taylor Review",
                date_of_birth=date(1991, 3, 15),
                country="XZ",
                address="400 Review Road",
                identification_number="ID-4004",
                expected_monthly_volume_cents=300_000,
            ),
            KycReviewStatus.PENDING_REVIEW,
        ),
        (
            build_legal_entity_application(
                "cust_report_005",
                "Missing Owner LLC",
                country="US",
                address="500 Entity Street",
                identification_number="REG-5005",
                expected_monthly_volume_cents=300_000,
                beneficial_owners=(),
            ),
            KycReviewStatus.REJECTED,
        ),
    )

    for index, (application, review_status) in enumerate(rows):
        submitted_at = base_time.replace(minute=index * 5)
        decided_at = base_time.replace(minute=index * 5 + 1)
        decision = engine.evaluate(application, watchlist=watchlist)

        store.save_application(application, submitted_at=submitted_at)
        store.save_decision(
            decision,
            decided_at=decided_at,
            watchlist_version_id=(
                first_version.version_id if index < 3 else second_version.version_id
            ),
            policy_version_id=(
                first_policy_version.version_id
                if index < 4
                else second_policy_version.version_id
            ),
        )
        if decision.status == KycDecisionStatus.REVIEW:
            review_case = review_service.create_case(
                decision,
                created_at=base_time.replace(minute=index * 5 + 2),
            )
            store.save_review_case(review_case)
            if review_status == KycReviewStatus.REQUEST_MORE_INFO:
                store.save_review_case(
                    review_service.request_more_info(
                        review_case.case_id,
                        reviewed_by="analyst_001",
                        reason="Additional document is required",
                        reviewed_at=base_time.replace(minute=index * 5 + 3),
                    )
                )
            elif review_status == KycReviewStatus.REJECTED:
                store.save_review_case(
                    review_service.reject(
                        review_case.case_id,
                        reviewed_by="analyst_002",
                        reason="Beneficial owner information is missing",
                        reviewed_at=base_time.replace(minute=index * 5 + 3),
                    )
                )

    return store


def count_map(items, key_name="status"):
    return {getattr(item, key_name): item.count for item in items}


def test_summary_report_counts_decisions_checks_scores_and_reviews():
    store = seed_store()

    report = build_kyc_summary_report(store)

    assert report.total_applications == 5
    assert count_map(report.customer_type_counts, "customer_type") == {
        "individual": 3,
        "legal_entity": 2,
    }
    assert count_map(report.decision_status_counts) == {
        "approved": 1,
        "review": 3,
        "blocked": 1,
    }
    assert count_map(report.check_hit_counts, "check_id") == {
        "customer_country_risk": 2,
        "beneficial_owner_required": 1,
        "beneficial_owner_watchlist_screening:owner_001": 1,
        "customer_watchlist_screening": 1,
        "expected_activity_volume": 1,
    }
    assert report.average_risk_score == 58.0
    assert report.max_risk_score == 110
    assert report.pending_review_count == 1
    assert count_map(report.review_status_counts) == {
        "pending_review": 1,
        "approved": 0,
        "rejected": 1,
        "request_more_info": 1,
    }
    store.close()


def test_summary_report_filters_by_customer_type():
    store = seed_store()

    report = build_kyc_summary_report(store, customer_type=CustomerType.LEGAL_ENTITY)

    assert report.customer_type == "legal_entity"
    assert report.total_applications == 2
    assert count_map(report.decision_status_counts) == {
        "approved": 0,
        "review": 2,
        "blocked": 0,
    }
    assert report.pending_review_count == 0
    assert count_map(report.review_status_counts) == {
        "pending_review": 0,
        "approved": 0,
        "rejected": 1,
        "request_more_info": 1,
    }
    store.close()


def test_summary_report_filters_by_decision_status_and_review_counts_follow():
    store = seed_store()

    blocked_report = build_kyc_summary_report(
        store,
        decision_status=KycDecisionStatus.BLOCKED,
    )
    review_report = build_kyc_summary_report(store, decision_status="review")

    assert blocked_report.total_applications == 1
    assert count_map(blocked_report.check_hit_counts, "check_id") == {
        "customer_watchlist_screening": 1,
    }
    assert blocked_report.pending_review_count == 0
    assert review_report.total_applications == 3
    assert review_report.pending_review_count == 1
    assert count_map(review_report.review_status_counts) == {
        "pending_review": 1,
        "approved": 0,
        "rejected": 1,
        "request_more_info": 1,
    }
    store.close()


def test_summary_report_filters_by_watchlist_version_and_review_counts_follow():
    store = seed_store()

    first_report = build_kyc_summary_report(
        store,
        watchlist_version_id="sample-watchlist-v1",
    )
    second_report = build_kyc_summary_report(
        store,
        watchlist_version_id="sample-watchlist-v2",
    )

    assert first_report.watchlist_version_id == "sample-watchlist-v1"
    assert first_report.total_applications == 3
    assert count_map(first_report.decision_status_counts) == {
        "approved": 1,
        "review": 1,
        "blocked": 1,
    }
    assert first_report.pending_review_count == 0
    assert count_map(first_report.review_status_counts) == {
        "pending_review": 0,
        "approved": 0,
        "rejected": 0,
        "request_more_info": 1,
    }
    assert second_report.total_applications == 2
    assert count_map(second_report.decision_status_counts) == {
        "approved": 0,
        "review": 2,
        "blocked": 0,
    }
    assert second_report.pending_review_count == 1
    assert count_map(second_report.review_status_counts) == {
        "pending_review": 1,
        "approved": 0,
        "rejected": 1,
        "request_more_info": 0,
    }
    store.close()


def test_summary_report_filters_by_policy_version_and_review_counts_follow():
    store = seed_store()

    first_report = build_kyc_summary_report(
        store,
        policy_version_id="sample-kyc-policy-v1",
    )
    second_report = build_kyc_summary_report(
        store,
        policy_version_id="sample-kyc-policy-v2",
    )

    assert first_report.policy_version_id == "sample-kyc-policy-v1"
    assert first_report.total_applications == 4
    assert count_map(first_report.decision_status_counts) == {
        "approved": 1,
        "review": 2,
        "blocked": 1,
    }
    assert first_report.pending_review_count == 1
    assert count_map(first_report.review_status_counts) == {
        "pending_review": 1,
        "approved": 0,
        "rejected": 0,
        "request_more_info": 1,
    }
    assert second_report.policy_version_id == "sample-kyc-policy-v2"
    assert second_report.total_applications == 1
    assert count_map(second_report.decision_status_counts) == {
        "approved": 0,
        "review": 1,
        "blocked": 0,
    }
    assert second_report.pending_review_count == 0
    assert count_map(second_report.review_status_counts) == {
        "pending_review": 0,
        "approved": 0,
        "rejected": 1,
        "request_more_info": 0,
    }
    store.close()


def test_watchlist_version_comparison_report_shows_deltas():
    store = seed_store()

    report = build_watchlist_version_comparison_report(
        store,
        baseline_watchlist_version_id="sample-watchlist-v1",
        comparison_watchlist_version_id="sample-watchlist-v2",
    )

    assert report.version_type == "watchlist"
    assert report.baseline_version_id == "sample-watchlist-v1"
    assert report.comparison_version_id == "sample-watchlist-v2"
    assert report.total_applications_delta == -1
    assert [
        (item.status, item.baseline_count, item.comparison_count, item.delta)
        for item in report.decision_status_comparisons
    ] == [
        ("approved", 1, 0, -1),
        ("review", 1, 2, 1),
        ("blocked", 1, 0, -1),
    ]
    assert [
        (item.check_id, item.baseline_count, item.comparison_count, item.delta)
        for item in report.check_hit_comparisons
    ] == [
        ("beneficial_owner_required", 0, 1, 1),
        ("beneficial_owner_watchlist_screening:owner_001", 1, 0, -1),
        ("customer_country_risk", 1, 1, 0),
        ("customer_watchlist_screening", 1, 0, -1),
        ("expected_activity_volume", 1, 0, -1),
    ]
    assert report.average_risk_score_delta == -30.0
    assert report.max_risk_score_delta == -65
    assert report.pending_review_delta == 1
    store.close()


def test_policy_version_comparison_report_shows_deltas():
    store = seed_store()

    report = build_policy_version_comparison_report(
        store,
        baseline_policy_version_id="sample-kyc-policy-v1",
        comparison_policy_version_id="sample-kyc-policy-v2",
    )

    assert report.version_type == "policy"
    assert report.baseline_version_id == "sample-kyc-policy-v1"
    assert report.comparison_version_id == "sample-kyc-policy-v2"
    assert report.total_applications_delta == -3
    assert [
        (item.customer_type, item.baseline_count, item.comparison_count, item.delta)
        for item in report.customer_type_comparisons
    ] == [
        ("individual", 3, 0, -3),
        ("legal_entity", 1, 1, 0),
    ]
    assert [
        (item.status, item.baseline_count, item.comparison_count, item.delta)
        for item in report.decision_status_comparisons
    ] == [
        ("approved", 1, 0, -1),
        ("review", 2, 1, -1),
        ("blocked", 1, 0, -1),
    ]
    assert report.average_risk_score_delta == -16.25
    assert report.max_risk_score_delta == -65
    assert report.pending_review_delta == -1
    assert [
        (item.status, item.baseline_count, item.comparison_count, item.delta)
        for item in report.review_status_comparisons
    ] == [
        ("pending_review", 1, 0, -1),
        ("approved", 0, 0, 0),
        ("rejected", 0, 1, 1),
        ("request_more_info", 1, 0, -1),
    ]
    store.close()


def test_version_comparison_validates_versions():
    store = seed_store()

    with pytest.raises(KycAmlError, match="Watchlist versions must be different"):
        build_watchlist_version_comparison_report(
            store,
            baseline_watchlist_version_id="sample-watchlist-v1",
            comparison_watchlist_version_id="sample-watchlist-v1",
        )
    with pytest.raises(KycAmlError, match="Policy versions must be different"):
        build_policy_version_comparison_report(
            store,
            baseline_policy_version_id="sample-kyc-policy-v1",
            comparison_policy_version_id="sample-kyc-policy-v1",
        )
    with pytest.raises(KycAmlError, match="Unknown KYC watchlist version"):
        build_watchlist_version_comparison_report(
            store,
            baseline_watchlist_version_id="missing-watchlist-version",
            comparison_watchlist_version_id="sample-watchlist-v1",
        )
    with pytest.raises(KycAmlError, match="Unknown KYC policy version"):
        build_policy_version_comparison_report(
            store,
            baseline_policy_version_id="missing-policy-version",
            comparison_policy_version_id="sample-kyc-policy-v1",
        )

    store.close()


def test_summary_report_filters_by_submitted_time_window():
    store = seed_store()

    report = build_kyc_summary_report(
        store,
        submitted_from=datetime(2026, 5, 7, 9, 5, tzinfo=timezone.utc),
        submitted_to=datetime(2026, 5, 7, 9, 10, tzinfo=timezone.utc),
    )

    assert report.total_applications == 2
    assert count_map(report.decision_status_counts) == {
        "approved": 0,
        "review": 1,
        "blocked": 1,
    }
    assert report.max_risk_score == 110
    store.close()


def test_summary_report_filters_by_decided_time_window():
    store = seed_store()

    report = build_kyc_summary_report(
        store,
        decided_from=datetime(2026, 5, 7, 9, 16, tzinfo=timezone.utc),
        decided_to=datetime(2026, 5, 7, 9, 21, tzinfo=timezone.utc),
    )

    assert report.total_applications == 2
    assert count_map(report.decision_status_counts) == {
        "approved": 0,
        "review": 2,
        "blocked": 0,
    }
    assert report.pending_review_count == 1
    store.close()


def test_summary_report_returns_empty_counts_for_no_matches():
    store = seed_store()

    report = build_kyc_summary_report(
        store,
        submitted_from=datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert report.total_applications == 0
    assert report.average_risk_score == 0.0
    assert report.max_risk_score == 0
    assert report.check_hit_counts == ()
    assert count_map(report.decision_status_counts) == {
        "approved": 0,
        "review": 0,
        "blocked": 0,
    }
    store.close()


def test_summary_report_validates_filters():
    store = seed_store()

    with pytest.raises(KycAmlError, match="Unknown customer type"):
        build_kyc_summary_report(store, customer_type="merchant")
    with pytest.raises(KycAmlError, match="Unknown KYC decision status"):
        build_kyc_summary_report(store, decision_status="pending")
    with pytest.raises(KycAmlError, match="Unknown KYC watchlist version"):
        build_kyc_summary_report(store, watchlist_version_id="missing-watchlist-version")
    with pytest.raises(KycAmlError, match="Unknown KYC policy version"):
        build_kyc_summary_report(store, policy_version_id="missing-policy-version")
    with pytest.raises(KycAmlError, match="submitted_from must be timezone-aware"):
        build_kyc_summary_report(store, submitted_from=datetime(2026, 5, 7, 9, 0))
    with pytest.raises(KycAmlError, match="decided_from must be before decided_to"):
        build_kyc_summary_report(
            store,
            decided_from=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
            decided_to=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
        )

    store.close()
