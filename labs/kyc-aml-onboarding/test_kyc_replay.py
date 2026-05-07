from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from kyc_aml import (
    KycAmlError,
    KycAmlEngine,
    KycAmlPolicy,
    WatchlistEntry,
    build_individual_application,
)
from kyc_replay import build_kyc_replay_report
from sqlite_kyc_store import SQLiteKycStore


def store_path():
    data_dir = Path(__file__).parent / ".test-data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"{uuid4()}.db"


def seed_store():
    store = SQLiteKycStore(store_path())
    baseline_policy = KycAmlPolicy(high_expected_monthly_volume_cents=1_000_000)
    baseline_engine = KycAmlEngine(baseline_policy)
    baseline_watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name="Alex Blocked",
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
    )
    baseline_policy_version = store.save_policy_version(
        baseline_policy,
        version_id="sample-kyc-policy-v1",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    baseline_watchlist_version = store.save_watchlist_version(
        baseline_watchlist,
        version_id="sample-watchlist-v1",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 2, tzinfo=timezone.utc),
    )
    applications = (
        build_individual_application(
            "cust_replay_001",
            "Jordan Smith",
            date_of_birth=date(1992, 5, 20),
            country="US",
            address="100 Market Street",
            identification_number="ID-1001",
            expected_monthly_volume_cents=250_000,
        ),
        build_individual_application(
            "cust_replay_002",
            "Alex Blocked",
            date_of_birth=date(1980, 1, 1),
            country="US",
            address="200 Main Street",
            identification_number="ID-2002",
            expected_monthly_volume_cents=100_000,
        ),
    )
    for index, application in enumerate(applications):
        decision = baseline_engine.evaluate(application, watchlist=baseline_watchlist)
        store.save_application(
            application,
            submitted_at=datetime(2026, 5, 7, 9, index * 5, tzinfo=timezone.utc),
        )
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, index * 5 + 1, tzinfo=timezone.utc),
            watchlist_version_id=baseline_watchlist_version.version_id,
            policy_version_id=baseline_policy_version.version_id,
        )
    return store


def test_kyc_replay_report_compares_original_and_replayed_decisions():
    store = seed_store()
    replay_policy = KycAmlPolicy(high_expected_monthly_volume_cents=200_000)
    replay_watchlist = ()
    replay_policy_version = store.save_policy_version(
        replay_policy,
        version_id="sample-kyc-policy-v2",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 1, tzinfo=timezone.utc),
    )
    replay_watchlist_version = store.save_watchlist_version(
        replay_watchlist,
        version_id="sample-watchlist-v2",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 2, tzinfo=timezone.utc),
    )

    report = build_kyc_replay_report(
        store,
        policy=replay_policy,
        watchlist=replay_watchlist,
        replay_policy_version_id=replay_policy_version.version_id,
        replay_watchlist_version_id=replay_watchlist_version.version_id,
    )

    assert report.replay_policy_version_id == "sample-kyc-policy-v2"
    assert report.replay_watchlist_version_id == "sample-watchlist-v2"
    assert report.total_applications == 2
    assert report.status_changed_count == 2
    assert report.increased_risk_count == 1
    assert report.decreased_risk_count == 1
    assert report.unchanged_risk_count == 0
    assert [
        (
            item.customer_id,
            item.original_status,
            item.replay_status,
            item.risk_score_delta,
            item.new_check_ids,
            item.resolved_check_ids,
        )
        for item in report.items
    ] == [
        (
            "cust_replay_001",
            "approved",
            "review",
            25,
            ("expected_activity_volume",),
            (),
        ),
        (
            "cust_replay_002",
            "blocked",
            "approved",
            -100,
            (),
            ("customer_watchlist_screening",),
        ),
    ]
    assert store.get_decision("cust_replay_001").status.value == "approved"
    store.close()


def test_kyc_replay_report_can_filter_customer_ids():
    store = seed_store()

    report = build_kyc_replay_report(
        store,
        policy=KycAmlPolicy(high_expected_monthly_volume_cents=200_000),
        customer_ids=("cust_replay_001",),
    )

    assert report.total_applications == 1
    assert report.items[0].customer_id == "cust_replay_001"
    store.close()


def test_kyc_replay_report_validates_inputs():
    store = seed_store()

    with pytest.raises(KycAmlError, match="Unknown KYC policy version"):
        build_kyc_replay_report(
            store,
            policy=KycAmlPolicy(),
            replay_policy_version_id="missing-policy-version",
        )
    with pytest.raises(KycAmlError, match="Unknown KYC watchlist version"):
        build_kyc_replay_report(
            store,
            policy=KycAmlPolicy(),
            replay_watchlist_version_id="missing-watchlist-version",
        )
    with pytest.raises(KycAmlError, match="Unknown KYC application"):
        build_kyc_replay_report(
            store,
            policy=KycAmlPolicy(),
            customer_ids=("missing-customer",),
        )

    store.close()
