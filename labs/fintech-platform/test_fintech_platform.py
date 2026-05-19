from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fintech_platform import (
    FinTechPlatform,
    PlatformPaymentRequest,
    PlatformPaymentStatus,
)
from kyc_aml import KycDecisionStatus, build_individual_application
from payment_orders import PaymentOrderStatus
from risk_rule_engine import RiskDecisionStatus


def test_approved_customer_payment_posts_ledger_and_audit_timeline() -> None:
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id="order_001",
            requested_at=_requested_at(),
        )
    )

    assert result.status == PlatformPaymentStatus.COMPLETED
    assert result.kyc_decision.status == KycDecisionStatus.APPROVED
    assert result.risk_decision is not None
    assert result.risk_decision.status == RiskDecisionStatus.APPROVED
    assert result.payment_order is not None
    assert result.payment_order.status == PaymentOrderStatus.SUCCEEDED
    assert result.ledger_transaction_id == result.payment_order.ledger_transaction_id
    assert result.platform_bank_balance == Decimal("100.00")
    assert result.user_wallet_balance == Decimal("100.00")
    assert [event.event_type for event in result.customer_timeline.events] == [
        "kyc_decision.saved",
        "payment_order.created",
        "risk_decision.saved",
        "payment_order.succeeded",
        "ledger_transaction.posted",
    ]
    assert result.audit_summary.total_events == 5
    assert "Jordan Smith" not in result.audit_events[0].payload
    assert "ID-1001" not in result.audit_events[0].payload


def test_blocked_kyc_stops_before_payment_order() -> None:
    blocked_application = build_individual_application(
        "cust_blocked",
        "Alex Blocked",
        date_of_birth=date(1980, 1, 1),
        country="US",
        address="300 Main Street",
        identification_number="ID-3003",
        expected_monthly_volume_cents=100_000,
    )

    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=blocked_application,
            amount="100.00",
            currency="USD",
            order_id="order_kyc_blocked",
            requested_at=_requested_at(),
        )
    )

    assert result.status == PlatformPaymentStatus.KYC_BLOCKED
    assert result.kyc_decision.status == KycDecisionStatus.BLOCKED
    assert result.payment_order is None
    assert result.risk_decision is None
    assert result.ledger_transaction_id is None
    assert [event.event_type for event in result.customer_timeline.events] == [
        "kyc_decision.saved",
    ]


def test_risk_blocked_marks_payment_failed_without_ledger_posting() -> None:
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="JPY",
            order_id="order_risk_blocked",
            requested_at=_requested_at(),
        )
    )

    assert result.status == PlatformPaymentStatus.RISK_BLOCKED
    assert result.risk_decision is not None
    assert result.risk_decision.status == RiskDecisionStatus.BLOCKED
    assert result.payment_order is not None
    assert result.payment_order.status == PaymentOrderStatus.FAILED
    assert result.ledger_transaction_id is None
    assert result.platform_bank_balance == Decimal("0.00")
    assert result.user_wallet_balance == Decimal("0.00")
    assert [event.event_type for event in result.customer_timeline.events] == [
        "kyc_decision.saved",
        "payment_order.created",
        "risk_decision.saved",
        "payment_order.failed",
    ]


def test_risk_review_creates_review_case_and_keeps_payment_pending() -> None:
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_risk_review",
            requested_at=_requested_at(),
        )
    )

    assert result.status == PlatformPaymentStatus.RISK_REVIEW_REQUIRED
    assert result.risk_decision is not None
    assert result.risk_decision.status == RiskDecisionStatus.REVIEW
    assert result.risk_review_case is not None
    assert result.risk_review_case.case_id == "review:order_risk_review"
    assert result.payment_order is not None
    assert result.payment_order.status == PaymentOrderStatus.PENDING
    assert result.ledger_transaction_id is None
    assert [event.event_type for event in result.customer_timeline.events] == [
        "kyc_decision.saved",
        "payment_order.created",
        "risk_decision.saved",
        "review_case.created",
    ]


def test_approved_risk_review_posts_ledger_and_extends_audit_timeline() -> None:
    platform = FinTechPlatform()
    review_result = platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_risk_review",
            requested_at=_requested_at(),
        )
    )

    completed = platform.approve_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Verified customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )

    assert completed.status == PlatformPaymentStatus.COMPLETED
    assert completed.payment_order is not None
    assert completed.payment_order.status == PaymentOrderStatus.SUCCEEDED
    assert completed.risk_review_case is not None
    assert completed.risk_review_case.status.value == "approved"
    assert completed.ledger_transaction_id == completed.payment_order.ledger_transaction_id
    assert completed.platform_bank_balance == Decimal("1500.00")
    assert completed.user_wallet_balance == Decimal("1500.00")
    assert [event.event_type for event in completed.customer_timeline.events] == [
        "kyc_decision.saved",
        "payment_order.created",
        "risk_decision.saved",
        "review_case.created",
        "review_case.approved",
        "payment_order.succeeded",
        "ledger_transaction.posted",
    ]


def test_rejected_risk_review_marks_payment_failed_without_ledger_posting() -> None:
    platform = FinTechPlatform()
    review_result = platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_risk_review",
            requested_at=_requested_at(),
        )
    )

    rejected = platform.reject_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Could not verify customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )

    assert rejected.status == PlatformPaymentStatus.RISK_REVIEW_REJECTED
    assert rejected.payment_order is not None
    assert rejected.payment_order.status == PaymentOrderStatus.FAILED
    assert rejected.risk_review_case is not None
    assert rejected.risk_review_case.status.value == "rejected"
    assert rejected.ledger_transaction_id is None
    assert rejected.platform_bank_balance == Decimal("0.00")
    assert rejected.user_wallet_balance == Decimal("0.00")
    assert [event.event_type for event in rejected.customer_timeline.events] == [
        "kyc_decision.saved",
        "payment_order.created",
        "risk_decision.saved",
        "review_case.created",
        "review_case.rejected",
        "payment_order.failed",
    ]


def test_non_review_result_cannot_be_completed_as_risk_review() -> None:
    platform = FinTechPlatform()
    result = platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id="order_001",
            requested_at=_requested_at(),
        )
    )

    try:
        platform.approve_risk_review(
            result,
            reviewed_by="risk_manager_001",
            reason="Invalid completion",
            reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        )
    except ValueError as error:
        assert "Only risk review results" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def _approved_application():
    return build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )


def _requested_at() -> datetime:
    return datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)
