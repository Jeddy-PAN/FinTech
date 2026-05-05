from decimal import Decimal

import pytest

from payment_orders import PaymentOrderError, PaymentOrderService, PaymentOrderStatus


def test_create_order_starts_pending_without_ledger_posting() -> None:
    service = PaymentOrderService()

    order = service.create_order("100.00", order_id="order_001")

    assert order.status == PaymentOrderStatus.PENDING
    assert order.ledger_transaction_id is None
    assert service.ledger.balance_for("platform_bank") == Decimal("0.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("0.00")


def test_successful_payment_posts_to_ledger() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    succeeded = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    assert succeeded.status == PaymentOrderStatus.SUCCEEDED
    assert succeeded.ledger_transaction_id is not None
    assert service.ledger.balance_for("platform_bank") == Decimal("100.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("100.00")


def test_duplicate_success_event_does_not_double_post_to_ledger() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    first = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    second = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    assert second == first
    assert len(service.ledger.transactions) == 1
    assert service.ledger.balance_for("platform_bank") == Decimal("100.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("100.00")


def test_different_success_event_for_already_succeeded_order_does_not_double_post() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    first = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    second = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_002")

    assert second == first
    assert len(service.ledger.transactions) == 1
    assert service.ledger.balance_for("platform_bank") == Decimal("100.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("100.00")


def test_failed_payment_does_not_post_to_ledger() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    failed = service.mark_failed(
        order.id,
        event_id="evt_payment_failed_001",
        reason="card_declined",
    )

    assert failed.status == PaymentOrderStatus.FAILED
    assert failed.failure_reason == "card_declined"
    assert failed.ledger_transaction_id is None
    assert service.ledger.balance_for("platform_bank") == Decimal("0.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("0.00")


def test_failed_order_cannot_later_succeed() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_failed(
        order.id,
        event_id="evt_payment_failed_001",
        reason="card_declined",
    )

    with pytest.raises(PaymentOrderError, match="Cannot mark failed order as succeeded"):
        service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")


def test_succeeded_order_cannot_later_fail() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    with pytest.raises(PaymentOrderError, match="Cannot mark succeeded order as failed"):
        service.mark_failed(
            order.id,
            event_id="evt_payment_failed_001",
            reason="card_declined",
        )


def test_blank_event_id_is_rejected() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    with pytest.raises(PaymentOrderError, match="Event id is required"):
        service.mark_succeeded(order.id, event_id=" ")


def test_refunded_payment_posts_reversal_to_ledger() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    refunded = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    assert refunded.status == PaymentOrderStatus.REFUNDED
    assert refunded.ledger_transaction_id is not None
    assert refunded.refund_ledger_transaction_id is not None
    assert refunded.refund_ledger_transaction_id != refunded.ledger_transaction_id
    assert len(service.ledger.transactions) == 2
    assert service.ledger.balance_for("platform_bank") == Decimal("0.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("0.00")


def test_duplicate_refund_event_does_not_double_reverse_ledger() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    first = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    second = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    assert second == first
    assert len(service.ledger.transactions) == 2
    assert service.ledger.balance_for("platform_bank") == Decimal("0.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("0.00")


def test_different_refund_event_for_already_refunded_order_does_not_double_reverse() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")

    first = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    second = service.mark_refunded(order.id, event_id="evt_payment_refunded_002")

    assert second == first
    assert len(service.ledger.transactions) == 2
    assert service.ledger.balance_for("platform_bank") == Decimal("0.00")
    assert service.ledger.balance_for("user_wallet") == Decimal("0.00")


def test_pending_order_cannot_be_refunded() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")

    with pytest.raises(PaymentOrderError, match="Cannot mark pending order as refunded"):
        service.mark_refunded(order.id, event_id="evt_payment_refunded_001")


def test_failed_order_cannot_be_refunded() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_failed(
        order.id,
        event_id="evt_payment_failed_001",
        reason="card_declined",
    )

    with pytest.raises(PaymentOrderError, match="Cannot mark failed order as refunded"):
        service.mark_refunded(order.id, event_id="evt_payment_refunded_001")


def test_refunded_order_cannot_later_fail() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    with pytest.raises(PaymentOrderError, match="Cannot mark refunded order as failed"):
        service.mark_failed(
            order.id,
            event_id="evt_payment_failed_001",
            reason="card_declined",
        )


def test_refunded_order_cannot_later_succeed_again() -> None:
    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    with pytest.raises(PaymentOrderError, match="Cannot mark refunded order as succeeded"):
        service.mark_succeeded(order.id, event_id="evt_payment_succeeded_002")
