from __future__ import annotations

from datetime import date

from kyc_aml import (
    BeneficialOwner,
    KycAmlEngine,
    KycAmlPolicy,
    WatchlistEntry,
    build_individual_application,
    build_legal_entity_application,
)


def print_decision(label, decision):
    print(f"\n{label}")
    print(f"customer_id: {decision.customer_id}")
    print(f"status: {decision.status.value}")
    print(f"risk_score: {decision.risk_score}")
    for result in decision.check_results:
        print(
            f"- {result.check_id}: {result.status.value} "
            f"(score={result.score}) {result.reason}"
        )


def main():
    policy = KycAmlPolicy(
        high_risk_countries=("XZ",),
        high_expected_monthly_volume_cents=1_000_000,
    )
    engine = KycAmlEngine(policy)
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

    approved_application = build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )

    review_application = build_legal_entity_application(
        "cust_002",
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
    )

    blocked_application = build_individual_application(
        "cust_003",
        "Alex Blocked",
        date_of_birth=date(1980, 1, 1),
        country="US",
        address="300 Main Street",
        identification_number="ID-3003",
        expected_monthly_volume_cents=100_000,
    )

    print_decision(
        "Approved sample",
        engine.evaluate(approved_application, watchlist=watchlist),
    )
    print_decision(
        "Review sample",
        engine.evaluate(review_application, watchlist=watchlist),
    )
    print_decision(
        "Blocked sample",
        engine.evaluate(blocked_application, watchlist=watchlist),
    )


if __name__ == "__main__":
    main()
