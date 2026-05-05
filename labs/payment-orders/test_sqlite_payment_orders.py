from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from payment_orders import PaymentOrderError, PaymentOrderStatus
from sqlite_payment_orders import SQLitePaymentOrderService


class RecordingPublisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, message) -> None:
        self.messages.append(message)


class FailingPublisher:
    def publish(self, message) -> None:
        raise RuntimeError("publish failed")


class FailsOnEventTypePublisher:
    def __init__(self, failed_event_type: str) -> None:
        self.failed_event_type = failed_event_type
        self.messages = []

    def publish(self, message) -> None:
        self.messages.append(message)
        if message.event_type == self.failed_event_type:
            raise RuntimeError("publish failed")


@pytest.fixture
def database_path() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid4()}.db"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


@pytest.fixture
def service(database_path):
    instance = SQLitePaymentOrderService(database_path)
    try:
        yield instance
    finally:
        instance.close()


def test_sqlite_create_order_persists_pending_order(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        persisted = reopened.orders[0]
        assert persisted == order
        assert persisted.status == PaymentOrderStatus.PENDING
        assert reopened.ledger.balance_for("platform_bank") == Decimal("0.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("0.00")
    finally:
        reopened.close()


def test_sqlite_successful_payment_persists_order_and_ledger(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    succeeded = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        persisted = reopened.orders[0]
        assert persisted.status == PaymentOrderStatus.SUCCEEDED
        assert persisted.ledger_transaction_id == succeeded.ledger_transaction_id
        assert reopened.ledger.balance_for("platform_bank") == Decimal("100.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("100.00")
    finally:
        reopened.close()


def test_sqlite_duplicate_success_event_survives_reopen(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    first = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        second = reopened.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
        assert second == first
        assert len(reopened.ledger.transactions) == 1
        assert reopened.ledger.balance_for("platform_bank") == Decimal("100.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("100.00")
    finally:
        reopened.close()


def test_sqlite_refund_persists_order_and_reversal(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    refunded = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        persisted = reopened.orders[0]
        assert persisted.status == PaymentOrderStatus.REFUNDED
        assert persisted.refund_ledger_transaction_id == refunded.refund_ledger_transaction_id
        assert len(reopened.ledger.transactions) == 2
        assert reopened.ledger.balance_for("platform_bank") == Decimal("0.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("0.00")
    finally:
        reopened.close()


def test_sqlite_duplicate_refund_event_survives_reopen(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    first = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        second = reopened.mark_refunded(order.id, event_id="evt_payment_refunded_001")
        assert second == first
        assert len(reopened.ledger.transactions) == 2
        assert reopened.ledger.balance_for("platform_bank") == Decimal("0.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("0.00")
    finally:
        reopened.close()


def test_sqlite_failed_order_persists_without_ledger_posting(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    failed = service.mark_failed(
        order.id,
        event_id="evt_payment_failed_001",
        reason="card_declined",
    )
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        persisted = reopened.orders[0]
        assert persisted.status == PaymentOrderStatus.FAILED
        assert persisted.failure_reason == failed.failure_reason
        assert len(reopened.ledger.transactions) == 0
        assert reopened.ledger.balance_for("platform_bank") == Decimal("0.00")
        assert reopened.ledger.balance_for("user_wallet") == Decimal("0.00")
    finally:
        reopened.close()


def test_sqlite_blank_event_id_is_rejected(service) -> None:
    order = service.create_order("100.00", order_id="order_001")

    with pytest.raises(PaymentOrderError, match="Event id is required"):
        service.mark_succeeded(order.id, event_id=" ")


def test_sqlite_create_order_writes_outbox_message(service) -> None:
    order = service.create_order("100.00", order_id="order_001")

    messages = service.pending_outbox_messages
    assert len(messages) == 1
    assert messages[0].event_type == "payment_order.created"
    assert messages[0].aggregate_id == order.id
    assert '"status":"pending"' in messages[0].payload


def test_sqlite_success_and_refund_write_outbox_messages(service) -> None:
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    event_types = [message.event_type for message in service.pending_outbox_messages]
    assert event_types == [
        "payment_order.created",
        "payment_order.succeeded",
        "payment_order.refunded",
    ]


def test_sqlite_failed_order_writes_outbox_message(service) -> None:
    order = service.create_order("100.00", order_id="order_001")
    service.mark_failed(
        order.id,
        event_id="evt_payment_failed_001",
        reason="card_declined",
    )

    event_types = [message.event_type for message in service.pending_outbox_messages]
    assert event_types == [
        "payment_order.created",
        "payment_order.failed",
    ]


def test_sqlite_outbox_messages_survive_reopen(database_path) -> None:
    service = SQLitePaymentOrderService(database_path)
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        event_types = [message.event_type for message in reopened.pending_outbox_messages]
        assert event_types == [
            "payment_order.created",
            "payment_order.succeeded",
        ]
    finally:
        reopened.close()


def test_sqlite_published_outbox_message_is_removed_from_pending(service) -> None:
    service.create_order("100.00", order_id="order_001")
    message = service.pending_outbox_messages[0]

    published = service.mark_outbox_message_published(message.id)

    assert published.status == "published"
    assert published.published_at is not None
    assert service.pending_outbox_messages == ()


def test_sqlite_publish_pending_outbox_messages_marks_successes_published(service) -> None:
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    publisher = RecordingPublisher()

    result = service.publish_pending_outbox_messages(publisher)

    assert result.attempted == 2
    assert result.published == 2
    assert result.failed == 0
    assert [message.event_type for message in publisher.messages] == [
        "payment_order.created",
        "payment_order.succeeded",
    ]
    assert service.pending_outbox_messages == ()


def test_sqlite_failed_publish_keeps_message_pending(service) -> None:
    service.create_order("100.00", order_id="order_001")

    result = service.publish_pending_outbox_messages(FailingPublisher())

    assert result.attempted == 1
    assert result.published == 0
    assert result.failed == 1
    assert len(service.pending_outbox_messages) == 1


def test_sqlite_partial_publish_failure_keeps_only_failed_message_pending(service) -> None:
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    publisher = FailsOnEventTypePublisher("payment_order.succeeded")

    result = service.publish_pending_outbox_messages(publisher)

    assert result.attempted == 3
    assert result.published == 2
    assert result.failed == 1
    assert [message.event_type for message in service.pending_outbox_messages] == [
        "payment_order.succeeded"
    ]


def test_sqlite_publish_pending_outbox_messages_respects_limit(service) -> None:
    order = service.create_order("100.00", order_id="order_001")
    service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    publisher = RecordingPublisher()

    result = service.publish_pending_outbox_messages(publisher, limit=1)

    assert result.attempted == 1
    assert result.published == 1
    assert result.failed == 0
    assert len(service.pending_outbox_messages) == 1


def test_sqlite_publish_limit_must_be_positive(service) -> None:
    with pytest.raises(PaymentOrderError, match="Outbox publish limit must be positive"):
        service.publish_pending_outbox_messages(RecordingPublisher(), limit=0)
