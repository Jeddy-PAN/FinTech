from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from kyc_aml import (
    BeneficialOwner,
    KycAmlEngine,
    KycAmlError,
    KycAmlPolicy,
    KycDecisionStatus,
    KycReviewCase,
    KycReviewService,
    KycReviewStatus,
    WatchlistEntry,
    build_individual_application,
    build_legal_entity_application,
)
from kyc_replay import build_kyc_replay_report
from sqlite_kyc_store import SQLiteKycStore


def store_path():
    data_dir = Path(__file__).parent / ".test-data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"{uuid4()}.db"


def review_decision():
    engine = KycAmlEngine(
        KycAmlPolicy(
            high_risk_countries=("XZ",),
            high_expected_monthly_volume_cents=1_000_000,
        )
    )
    application = build_individual_application(
        "cust_review",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="XZ",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=2_000_000,
    )
    return application, engine.evaluate(application)


def blocked_decision_for_legal_entity():
    engine = KycAmlEngine()
    application = build_legal_entity_application(
        "cust_blocked_entity",
        "Entity With Blocked Owner LLC",
        country="US",
        address="500 Corporate Plaza",
        identification_number="REG-5005",
        expected_monthly_volume_cents=300_000,
        beneficial_owners=(
            BeneficialOwner(
                owner_id="owner_001",
                full_name="Alex Blocked",
                ownership_percent=75,
                country="US",
                identification_number="ID-5005",
                date_of_birth=date(1980, 1, 1),
            ),
        ),
    )
    watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name="Alex Blocked",
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
    )
    return application, engine.evaluate(application, watchlist=watchlist)


def sample_watchlist():
    return (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name="Alex Blocked",
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
    )


def sample_policy():
    return KycAmlPolicy(
        high_risk_countries=("XZ",),
        beneficial_owner_threshold_percent=25,
        high_expected_monthly_volume_cents=1_000_000,
        fuzzy_review_score_threshold=88,
        exact_block_score_threshold=98,
        risk_score_review_threshold=60,
    )


def test_store_saves_and_restores_application_with_beneficial_owners():
    application, decision = blocked_decision_for_legal_entity()
    store = SQLiteKycStore(store_path())

    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )

    restored_application = store.get_application(application.customer_id)
    restored_decision = store.get_decision(decision.customer_id)

    assert restored_application == application
    assert restored_decision == decision
    assert restored_decision.status == KycDecisionStatus.BLOCKED
    assert restored_decision.risk_score == 100
    store.close()


def test_store_saves_watchlist_version_and_links_decision():
    application, decision = blocked_decision_for_legal_entity()
    store = SQLiteKycStore(store_path())
    watchlist = sample_watchlist()

    watchlist_version = store.save_watchlist_version(
        watchlist,
        version_id="sample-watchlist-2026-05-07",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    duplicate_version = store.save_watchlist_version(
        watchlist,
        version_id="sample-watchlist-2026-05-07",
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
    )

    restored_version = store.watchlist_version_for_decision(application.customer_id)
    event_types = [event.event_type for event in store.audit_events]

    assert duplicate_version == watchlist_version
    assert watchlist_version.entry_count == 1
    assert len(watchlist_version.content_hash) == 64
    assert restored_version == watchlist_version
    assert event_types == [
        "kyc_watchlist_version.saved",
        "kyc_application.saved",
        "kyc_decision.saved",
    ]
    store.close()


def test_store_rejects_watchlist_version_id_conflicts():
    store = SQLiteKycStore(store_path())
    store.save_watchlist_version(
        sample_watchlist(),
        version_id="sample-watchlist-2026-05-07",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="KYC watchlist version already exists"):
        store.save_watchlist_version(
            (),
            version_id="sample-watchlist-2026-05-07",
            source="sample_watchlist.json",
            effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
        )

    store.close()


def test_store_rejects_unknown_watchlist_version_for_decision():
    application, decision = blocked_decision_for_legal_entity()
    store = SQLiteKycStore(store_path())
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="Unknown KYC watchlist version"):
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
            watchlist_version_id="missing-watchlist-version",
        )

    store.close()


def test_store_rejects_duplicate_decision_with_different_watchlist_version():
    application, decision = blocked_decision_for_legal_entity()
    store = SQLiteKycStore(store_path())
    first_version = store.save_watchlist_version(
        sample_watchlist(),
        version_id="sample-watchlist-2026-05-07",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    second_version = store.save_watchlist_version(
        (),
        version_id="sample-watchlist-2026-05-08",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 1, tzinfo=timezone.utc),
    )
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
        watchlist_version_id=first_version.version_id,
    )

    with pytest.raises(
        KycAmlError,
        match="KYC decision already exists with different watchlist version",
    ):
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, 2, tzinfo=timezone.utc),
            watchlist_version_id=second_version.version_id,
        )

    store.close()


def test_store_saves_policy_version_and_links_decision():
    application, decision = review_decision()
    store = SQLiteKycStore(store_path())
    policy = sample_policy()

    policy_version = store.save_policy_version(
        policy,
        version_id="sample-kyc-policy-2026-05-07",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    duplicate_version = store.save_policy_version(
        policy,
        version_id="sample-kyc-policy-2026-05-07",
        source="sample_kyc_policy.json",
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
        policy_version_id=policy_version.version_id,
    )

    restored_version = store.policy_version_for_decision(application.customer_id)
    event_types = [event.event_type for event in store.audit_events]

    assert duplicate_version == policy_version
    assert policy_version.high_risk_countries == ("XZ",)
    assert policy_version.risk_score_review_threshold == 60
    assert restored_version == policy_version
    assert event_types == [
        "kyc_policy_version.saved",
        "kyc_application.saved",
        "kyc_decision.saved",
    ]
    store.close()


def test_store_rejects_policy_version_id_conflicts():
    store = SQLiteKycStore(store_path())
    store.save_policy_version(
        sample_policy(),
        version_id="sample-kyc-policy-2026-05-07",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="KYC policy version already exists"):
        store.save_policy_version(
            KycAmlPolicy(
                high_risk_countries=("ZZ",),
                high_expected_monthly_volume_cents=2_000_000,
            ),
            version_id="sample-kyc-policy-2026-05-07",
            source="sample_kyc_policy.json",
            effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
        )

    store.close()


def test_store_rejects_unknown_policy_version_for_decision():
    application, decision = review_decision()
    store = SQLiteKycStore(store_path())
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="Unknown KYC policy version"):
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
            policy_version_id="missing-policy-version",
        )

    store.close()


def test_store_rejects_duplicate_decision_with_different_policy_version():
    application, decision = review_decision()
    store = SQLiteKycStore(store_path())
    first_version = store.save_policy_version(
        sample_policy(),
        version_id="sample-kyc-policy-v1",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    second_version = store.save_policy_version(
        KycAmlPolicy(
            high_risk_countries=("XZ", "ZZ"),
            high_expected_monthly_volume_cents=1_000_000,
        ),
        version_id="sample-kyc-policy-v2",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 8, 8, 1, tzinfo=timezone.utc),
    )
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
        policy_version_id=first_version.version_id,
    )

    with pytest.raises(
        KycAmlError,
        match="KYC decision already exists with different policy version",
    ):
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, 2, tzinfo=timezone.utc),
            policy_version_id=second_version.version_id,
        )

    store.close()


def test_store_saves_replay_run_items_and_approval():
    application, decision = review_decision()
    store = SQLiteKycStore(store_path())
    replay_policy = KycAmlPolicy(
        high_risk_countries=("XZ",),
        high_expected_monthly_volume_cents=500_000,
    )
    policy_version = store.save_policy_version(
        replay_policy,
        version_id="sample-kyc-policy-replay",
        source="sample_kyc_policy.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 1, tzinfo=timezone.utc),
    )
    watchlist_version = store.save_watchlist_version(
        (),
        version_id="sample-watchlist-replay",
        source="sample_watchlist.json",
        effective_at=datetime(2026, 5, 7, 8, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 7, 8, 2, tzinfo=timezone.utc),
    )
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )
    report = build_kyc_replay_report(
        store,
        policy=replay_policy,
        replay_policy_version_id=policy_version.version_id,
        replay_watchlist_version_id=watchlist_version.version_id,
    )

    replay_run = store.save_replay_run(
        report,
        run_id="kyc-replay-2026-05-07",
        created_by="analyst_001",
        created_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    duplicate_run = store.save_replay_run(
        report,
        run_id="kyc-replay-2026-05-07",
        created_by="analyst_001",
        created_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    approved_run = store.approve_replay_run(
        replay_run.run_id,
        reviewed_by="compliance_001",
        reason="Replay impact is acceptable for the sample policy change",
        reviewed_at=datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc),
    )

    items = store.replay_run_items(replay_run.run_id)
    event_types = [event.event_type for event in store.audit_events]

    assert duplicate_run == replay_run
    assert replay_run.status == "pending_review"
    assert approved_run.status == "approved"
    assert approved_run.reviewed_by == "compliance_001"
    assert store.replay_runs == (approved_run,)
    assert items == report.items
    assert event_types[-2:] == [
        "kyc_replay_run.created",
        "kyc_replay_run.approved",
    ]
    store.close()


def test_store_rejects_conflicting_replay_run_and_double_completion():
    application, decision = review_decision()
    store = SQLiteKycStore(store_path())
    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )
    report = build_kyc_replay_report(store, policy=sample_policy())
    changed_report = build_kyc_replay_report(
        store,
        policy=KycAmlPolicy(
            high_risk_countries=(),
            high_expected_monthly_volume_cents=500_000,
        ),
    )
    replay_run = store.save_replay_run(
        report,
        run_id="kyc-replay-conflict",
        created_by="analyst_001",
        created_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="KYC replay run already exists"):
        store.save_replay_run(
            changed_report,
            run_id=replay_run.run_id,
            created_by="analyst_001",
            created_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
        )

    store.reject_replay_run(
        replay_run.run_id,
        reviewed_by="compliance_001",
        reason="Replay impact is too broad",
        reviewed_at=datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="KYC replay run is already completed"):
        store.approve_replay_run(
            replay_run.run_id,
            reviewed_by="compliance_002",
            reason="Second review should fail",
            reviewed_at=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        )

    store.close()


def test_store_requires_application_before_decision():
    _, decision = review_decision()
    store = SQLiteKycStore(store_path())

    with pytest.raises(KycAmlError, match="Unknown KYC application for decision"):
        store.save_decision(
            decision,
            decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
        )

    store.close()


def test_store_saves_review_case_and_audit_events():
    application, decision = review_decision()
    service = KycReviewService()
    pending_case = service.create_case(
        decision,
        created_at=datetime(2026, 5, 7, 9, 2, tzinfo=timezone.utc),
    )
    approved_case = service.approve(
        pending_case.case_id,
        reviewed_by="analyst_001",
        reason="Enhanced review completed",
        reviewed_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    store = SQLiteKycStore(store_path())

    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )
    store.save_review_case(pending_case)
    store.save_review_case(approved_case)

    restored_case = store.get_review_case(pending_case.case_id)
    event_types = [event.event_type for event in store.audit_events]

    assert restored_case.status == KycReviewStatus.APPROVED
    assert restored_case.reviewed_by == "analyst_001"
    assert store.pending_review_cases == ()
    assert event_types == [
        "kyc_application.saved",
        "kyc_decision.saved",
        "kyc_review_case.created",
        "kyc_review_case.approved",
    ]
    store.close()


def test_store_can_persist_request_more_info_case():
    application, decision = review_decision()
    service = KycReviewService()
    pending_case = service.create_case(
        decision,
        created_at=datetime(2026, 5, 7, 9, 2, tzinfo=timezone.utc),
    )
    request_more_info_case = service.request_more_info(
        pending_case.case_id,
        reviewed_by="analyst_002",
        reason="Business registration document is missing",
        reviewed_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    store = SQLiteKycStore(store_path())

    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )
    store.save_review_case(pending_case)
    store.save_review_case(request_more_info_case)

    restored_case = store.get_review_case(pending_case.case_id)
    case_events = store.audit_events_for(
        aggregate_type="kyc_review_case",
        aggregate_id=pending_case.case_id,
    )

    assert restored_case.status == KycReviewStatus.REQUEST_MORE_INFO
    assert [event.event_type for event in case_events] == [
        "kyc_review_case.created",
        "kyc_review_case.request_more_info",
    ]
    store.close()


def test_store_rejects_review_case_for_blocked_decision():
    application, decision = blocked_decision_for_legal_entity()
    store = SQLiteKycStore(store_path())
    review_case = KycReviewCase(
        case_id="kyc_review:cust_blocked_entity",
        customer_id=decision.customer_id,
        status=KycReviewStatus.PENDING_REVIEW,
        check_results=decision.check_results,
        created_at=datetime(2026, 5, 7, 9, 2, tzinfo=timezone.utc),
    )

    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(
        KycAmlError,
        match="Only review decisions can create KYC review cases",
    ):
        store.save_review_case(review_case)

    store.close()


def test_store_rejects_duplicate_decision_with_different_content():
    application, decision = review_decision()
    changed_decision = type(decision)(
        customer_id=decision.customer_id,
        status=KycDecisionStatus.APPROVED,
        check_results=decision.check_results,
        risk_score=decision.risk_score,
    )
    store = SQLiteKycStore(store_path())

    store.save_application(
        application,
        submitted_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    store.save_decision(
        decision,
        decided_at=datetime(2026, 5, 7, 9, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(KycAmlError, match="KYC decision already exists"):
        store.save_decision(
            changed_decision,
            decided_at=datetime(2026, 5, 7, 9, 5, tzinfo=timezone.utc),
        )

    store.close()


def test_store_requires_timezone_aware_timestamps():
    application, _ = review_decision()
    store = SQLiteKycStore(store_path())

    with pytest.raises(KycAmlError, match="submitted_at must be timezone-aware"):
        store.save_application(
            application,
            submitted_at=datetime(2026, 5, 7, 9, 0),
        )

    store.close()
