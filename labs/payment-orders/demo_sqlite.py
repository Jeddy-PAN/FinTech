import sys
from pathlib import Path

from sqlite_payment_orders import OutboxMessage, SQLitePaymentOrderService


class ConsolePublisher:
    def publish(self, message: OutboxMessage) -> None:
        print(f"Publishing {message.event_type}: {message.aggregate_id}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    database_path = Path(__file__).with_name("payment_orders_demo.db")
    if database_path.exists():
        database_path.unlink()

    service = SQLitePaymentOrderService(database_path)
    try:
        order = service.create_order("100.00", order_id="order_001")
        service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
        refunded = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")
    finally:
        service.close()

    reopened = SQLitePaymentOrderService(database_path)
    try:
        persisted = reopened.orders[0]
        print(f"Database: {database_path}")
        print("Payment Order")
        print(f"- Order id: {persisted.id}")
        print(f"- Status: {persisted.status.value}")
        print(f"- Ledger transaction id: {persisted.ledger_transaction_id}")
        print(f"- Refund ledger transaction id: {persisted.refund_ledger_transaction_id}")

        print("\nLedger Balances")
        print(f"- Platform Bank Account: {reopened.ledger.balance_for('platform_bank')}")
        print(f"- User Wallet Balance: {reopened.ledger.balance_for('user_wallet')}")

        retry = reopened.mark_refunded(
            refunded.id,
            event_id="evt_payment_refunded_001",
        )
        print(f"\nRefund retry returned same order: {retry == persisted}")

        print("\nPending Outbox Messages")
        for message in reopened.pending_outbox_messages:
            print(f"- {message.event_type}: {message.aggregate_id}")

        result = reopened.publish_pending_outbox_messages(ConsolePublisher())
        print("\nOutbox Publish Result")
        print(f"- Attempted: {result.attempted}")
        print(f"- Published: {result.published}")
        print(f"- Failed: {result.failed}")
    finally:
        reopened.close()


if __name__ == "__main__":
    main()
