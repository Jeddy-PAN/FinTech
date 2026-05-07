import sys
from datetime import datetime, timezone
from pathlib import Path

from risk_rule_engine import ManualReviewService, RiskRuleConfig, RiskRuleEngine, build_request


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lab_dir = Path(__file__).resolve().parent
    config = RiskRuleConfig.from_json(lab_dir / "risk_rules.json")
    engine = RiskRuleEngine(config=config)
    review_service = ManualReviewService()
    history = [
        build_request(
            "txn_001",
            "user_001",
            "900.00",
            "USD",
            datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
            device_id="device_known",
        ),
        build_request(
            "txn_002",
            "user_001",
            "1200.00",
            "USD",
            datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
            device_id="device_known",
        ),
    ]
    requests = [
        build_request(
            "txn_003",
            "user_001",
            "950.00",
            "USD",
            datetime(2026, 5, 5, 11, 0, tzinfo=timezone.utc),
            device_id="device_known",
        ),
        build_request(
            "txn_004",
            "user_002",
            "1500.00",
            "USD",
            datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
            device_id="device_002",
        ),
        build_request(
            "txn_005",
            "user_003",
            "100.00",
            "JPY",
            datetime(2026, 5, 5, 13, 0, tzinfo=timezone.utc),
            device_id="device_003",
        ),
        build_request(
            "txn_006",
            "user_006",
            "500.00",
            "USD",
            datetime(2026, 5, 5, 2, 30, tzinfo=timezone.utc),
        ),
        build_request(
            "txn_007",
            "user_004",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc),
            ip_country="KP",
        ),
        build_request(
            "txn_008",
            "user_005",
            "100.00",
            "USD",
            datetime(2026, 5, 5, 14, 30, tzinfo=timezone.utc),
            beneficiary_id="beneficiary_blocked_001",
        ),
    ]

    print("Risk Decisions")
    for request in requests:
        decision = engine.evaluate(request, history=history)
        print(
            f"- {decision.request_id}: "
            f"status={decision.status.value}; risk_score={decision.risk_score}"
        )
        for hit in decision.rule_hits:
            print(f"  - {hit.rule_id}: {hit.status.value}; score={hit.score}; {hit.reason}")
        if decision.status.value == "review":
            review_case = review_service.create_case(
                decision,
                created_at=datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc),
            )
            print(f"  - review_case={review_case.case_id}; status={review_case.status.value}")

    print("\nManual Review")
    completed = review_service.approve(
        "review:txn_003",
        reviewed_by="analyst_001",
        reason="Verified customer history",
        reviewed_at=datetime(2026, 5, 5, 15, 0, tzinfo=timezone.utc),
    )
    print(
        f"- {completed.case_id}: status={completed.status.value}; "
        f"reviewed_by={completed.reviewed_by}; reason={completed.review_reason}"
    )


if __name__ == "__main__":
    main()
