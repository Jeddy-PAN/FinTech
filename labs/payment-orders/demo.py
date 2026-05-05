import sys

from payment_orders import PaymentOrderService


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    service = PaymentOrderService()
    order = service.create_order("100.00", order_id="order_001")
    succeeded = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    retry = service.mark_succeeded(order.id, event_id="evt_payment_succeeded_001")
    refunded = service.mark_refunded(order.id, event_id="evt_payment_refunded_001")

    print("Payment Order")
    print(f"- Order id: {refunded.id}")
    print(f"- Status: {refunded.status.value}")
    print(f"- Ledger transaction id: {refunded.ledger_transaction_id}")
    print(f"- Refund ledger transaction id: {refunded.refund_ledger_transaction_id}")
    print(f"- Retry returned same order: {retry == succeeded}")

    print("\nLedger Balances")
    print(f"- Platform Bank Account: {service.ledger.balance_for('platform_bank')}")
    print(f"- User Wallet Balance: {service.ledger.balance_for('user_wallet')}")


if __name__ == "__main__":
    main()
