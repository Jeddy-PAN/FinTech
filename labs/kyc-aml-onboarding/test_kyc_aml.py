from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from kyc_aml import (
    BeneficialOwner,
    CustomerApplication,
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


def test_approved_individual_has_explainable_passed_checks():
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )

    decision = engine.evaluate(application)

    assert decision.status == KycDecisionStatus.APPROVED
    assert decision.risk_score == 0
    assert {result.check_id for result in decision.check_results} == {
        "identity_required_fields",
        "customer_country_risk",
        "expected_activity_volume",
        "watchlist_screening",
    }


def test_missing_individual_identity_field_requires_review():
    engine = KycAmlEngine()
    application = CustomerApplication(
        customer_id="cust_002",
        customer_type=CustomerType.INDIVIDUAL,
        full_name="Jordan Smith",
        country="US",
        address="100 Market Street",
        identification_number="",
        expected_monthly_volume_cents=250_000,
        date_of_birth=date(1992, 5, 20),
    )

    decision = engine.evaluate(application)

    assert decision.status == KycDecisionStatus.REVIEW
    assert any(
        result.check_id == "identity_required_fields"
        and "identification_number" in result.reason
        for result in decision.check_results
    )


def test_legal_entity_without_beneficial_owner_requires_review():
    engine = KycAmlEngine()
    application = build_legal_entity_application(
        "cust_003",
        "Northwind Trading LLC",
        country="US",
        address="200 Commerce Avenue",
        identification_number="REG-2002",
        expected_monthly_volume_cents=300_000,
        beneficial_owners=(),
    )

    decision = engine.evaluate(application)

    assert decision.status == KycDecisionStatus.REVIEW
    assert any(
        result.check_id == "beneficial_owner_required"
        for result in decision.check_results
    )


def test_legal_entity_owner_below_threshold_requires_review():
    engine = KycAmlEngine()
    application = build_legal_entity_application(
        "cust_004",
        "Small Owner LLC",
        country="US",
        address="200 Commerce Avenue",
        identification_number="REG-2003",
        expected_monthly_volume_cents=300_000,
        beneficial_owners=(
            BeneficialOwner(
                owner_id="owner_001",
                full_name="Taylor Owner",
                ownership_percent=10,
                country="US",
                identification_number="ID-2003",
            ),
        ),
    )

    decision = engine.evaluate(application)

    assert decision.status == KycDecisionStatus.REVIEW
    assert any(
        result.check_id == "beneficial_owner_threshold"
        for result in decision.check_results
    )


def test_high_risk_country_and_high_expected_volume_require_review():
    engine = KycAmlEngine(
        KycAmlPolicy(
            high_risk_countries=("XZ",),
            high_expected_monthly_volume_cents=1_000_000,
        )
    )
    application = build_individual_application(
        "cust_005",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="XZ",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=2_000_000,
    )

    decision = engine.evaluate(application)

    assert decision.status == KycDecisionStatus.REVIEW
    assert decision.risk_score == 60
    assert {
        result.check_id
        for result in decision.check_results
        if result.status == KycDecisionStatus.REVIEW
    } == {"customer_country_risk", "expected_activity_volume"}


def test_exact_watchlist_match_blocks_application():
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_006",
        "Alex Blocked",
        date_of_birth=date(1980, 1, 1),
        country="US",
        address="300 Main Street",
        identification_number="ID-3003",
        expected_monthly_volume_cents=100_000,
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

    decision = engine.evaluate(application, watchlist=watchlist)

    assert decision.status == KycDecisionStatus.BLOCKED
    assert any(
        result.check_id == "customer_watchlist_screening"
        and result.status == KycDecisionStatus.BLOCKED
        for result in decision.check_results
    )


def test_fuzzy_watchlist_match_requires_review():
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_007",
        "Maria Reviw",
        date_of_birth=date(1978, 7, 7),
        country="GB",
        address="400 High Street",
        identification_number="ID-4004",
        expected_monthly_volume_cents=100_000,
    )
    watchlist = (
        WatchlistEntry(
            entry_id="sample_sdn_002",
            list_name="Sample Sanctions List",
            full_name="Maria Review",
            country="GB",
        ),
    )

    decision = engine.evaluate(application, watchlist=watchlist)

    assert decision.status == KycDecisionStatus.REVIEW
    assert any(
        result.check_id == "customer_watchlist_screening"
        and result.status == KycDecisionStatus.REVIEW
        for result in decision.check_results
    )


def test_beneficial_owner_watchlist_match_blocks_legal_entity():
    engine = KycAmlEngine()
    application = build_legal_entity_application(
        "cust_008",
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

    decision = engine.evaluate(application, watchlist=watchlist)

    assert decision.status == KycDecisionStatus.BLOCKED
    assert any(
        result.check_id == "beneficial_owner_watchlist_screening:owner_001"
        for result in decision.check_results
    )


def test_country_codes_must_use_two_letters_when_present():
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_009",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="USA",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )

    with pytest.raises(KycAmlError, match="country must be a 2-letter country code"):
        engine.evaluate(application)


def test_expected_volume_must_be_positive():
    engine = KycAmlEngine()
    application = build_individual_application(
        "cust_010",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=0,
    )

    with pytest.raises(
        KycAmlError,
        match="expected_monthly_volume_cents must be a positive integer",
    ):
        engine.evaluate(application)


def test_review_service_creates_and_approves_case():
    engine = KycAmlEngine(
        KycAmlPolicy(
            high_risk_countries=("XZ",),
            high_expected_monthly_volume_cents=1_000_000,
        )
    )
    decision = engine.evaluate(
        build_individual_application(
            "cust_011",
            "Jordan Smith",
            date_of_birth=date(1992, 5, 20),
            country="XZ",
            address="100 Market Street",
            identification_number="ID-1001",
            expected_monthly_volume_cents=250_000,
        )
    )
    service = KycReviewService()

    review_case = service.create_case(
        decision,
        created_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )
    duplicate_case = service.create_case(
        decision,
        created_at=datetime(2026, 5, 7, 9, 5, tzinfo=timezone.utc),
    )
    approved_case = service.approve(
        review_case.case_id,
        reviewed_by="analyst_001",
        reason="Identity documents were verified",
        reviewed_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )

    assert duplicate_case == review_case
    assert approved_case.status == KycReviewStatus.APPROVED
    assert approved_case.reviewed_by == "analyst_001"
    assert approved_case.review_reason == "Identity documents were verified"


def test_review_service_can_request_more_info():
    engine = KycAmlEngine()
    decision = engine.evaluate(
        CustomerApplication(
            customer_id="cust_012",
            customer_type=CustomerType.INDIVIDUAL,
            full_name="Jordan Smith",
            country="US",
            address="100 Market Street",
            identification_number="",
            expected_monthly_volume_cents=250_000,
            date_of_birth=date(1992, 5, 20),
        )
    )
    service = KycReviewService()
    review_case = service.create_case(
        decision,
        created_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
    )

    updated_case = service.request_more_info(
        review_case.case_id,
        reviewed_by="analyst_002",
        reason="Government id number is missing",
        reviewed_at=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )

    assert updated_case.status == KycReviewStatus.REQUEST_MORE_INFO


def test_review_service_rejects_non_review_decision():
    engine = KycAmlEngine()
    decision = engine.evaluate(
        build_individual_application(
            "cust_013",
            "Jordan Smith",
            date_of_birth=date(1992, 5, 20),
            country="US",
            address="100 Market Street",
            identification_number="ID-1001",
            expected_monthly_volume_cents=250_000,
        )
    )
    service = KycReviewService()

    with pytest.raises(
        KycAmlError,
        match="Only review decisions can create KYC review cases",
    ):
        service.create_case(
            decision,
            created_at=datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
        )


def test_review_service_requires_timezone_aware_timestamps():
    engine = KycAmlEngine()
    decision = engine.evaluate(
        CustomerApplication(
            customer_id="cust_014",
            customer_type=CustomerType.INDIVIDUAL,
            full_name="Jordan Smith",
            country="US",
            address="100 Market Street",
            identification_number="",
            expected_monthly_volume_cents=250_000,
            date_of_birth=date(1992, 5, 20),
        )
    )
    service = KycReviewService()

    with pytest.raises(KycAmlError, match="created_at must be timezone-aware"):
        service.create_case(
            decision,
            created_at=datetime(2026, 5, 7, 9, 0),
        )
