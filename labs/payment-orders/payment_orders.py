from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import uuid4


LEDGER_PATH = Path(__file__).resolve().parents[1] / "ledger-basics"
if str(LEDGER_PATH) not in sys.path:
    sys.path.insert(0, str(LEDGER_PATH))

from ledger import AccountType, Entry, EntrySide, Ledger, LedgerError, Transaction, money


class PaymentOrderError(ValueError):
    """Base error for invalid payment order operations."""


class PaymentOrderStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class PaymentOrder:
    id: str
    amount: Decimal
    status: PaymentOrderStatus
    ledger_transaction_id: str | None = None
    refund_ledger_transaction_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LedgerProtocol(Protocol):
    def post_transaction(
        self,
        description: str,
        entries: list[Entry],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Transaction:
        ...


class PaymentOrderService:
    def __init__(
        self,
        ledger: LedgerProtocol | None = None,
        *,
        platform_bank_account_id: str = "platform_bank",
        user_wallet_account_id: str = "user_wallet",
    ) -> None:
        self.ledger = ledger or self._build_default_ledger(
            platform_bank_account_id,
            user_wallet_account_id,
        )
        self.platform_bank_account_id = platform_bank_account_id
        self.user_wallet_account_id = user_wallet_account_id
        self._orders: dict[str, PaymentOrder] = {}
        self._processed_events: dict[str, PaymentOrder] = {}

    @property
    def orders(self) -> tuple[PaymentOrder, ...]:
        return tuple(self._orders.values())

    def create_order(
        self,
        amount: str | int | Decimal,
        *,
        order_id: str | None = None,
    ) -> PaymentOrder:
        normalized_amount = money(amount)
        payment_order = PaymentOrder(
            id=order_id or str(uuid4()),
            amount=normalized_amount,
            status=PaymentOrderStatus.PENDING,
        )

        if payment_order.id in self._orders:
            raise PaymentOrderError(f"Payment order already exists: {payment_order.id}")

        self._orders[payment_order.id] = payment_order
        return payment_order

    def mark_succeeded(self, order_id: str, *, event_id: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        if normalized_event_id in self._processed_events:
            return self._processed_events[normalized_event_id]

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.SUCCEEDED:
            self._processed_events[normalized_event_id] = order
            return order

        if order.status != PaymentOrderStatus.PENDING:
            raise PaymentOrderError(
                f"Cannot mark {order.status.value} order as succeeded: {order.id}"
            )

        transaction = self.ledger.post_transaction(
            f"Payment order succeeded: {order.id}",
            [
                Entry(self.platform_bank_account_id, EntrySide.DEBIT, order.amount),
                Entry(self.user_wallet_account_id, EntrySide.CREDIT, order.amount),
            ],
            idempotency_key=f"payment-order:{order.id}:succeeded",
        )
        updated_order = self._replace_order(
            order,
            status=PaymentOrderStatus.SUCCEEDED,
            ledger_transaction_id=transaction.id,
        )
        self._processed_events[normalized_event_id] = updated_order
        return updated_order

    def mark_failed(self, order_id: str, *, event_id: str, reason: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        if normalized_event_id in self._processed_events:
            return self._processed_events[normalized_event_id]

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.FAILED:
            self._processed_events[normalized_event_id] = order
            return order

        if order.status != PaymentOrderStatus.PENDING:
            raise PaymentOrderError(
                f"Cannot mark {order.status.value} order as failed: {order.id}"
            )

        if not reason.strip():
            raise PaymentOrderError("Failure reason is required")

        updated_order = self._replace_order(
            order,
            status=PaymentOrderStatus.FAILED,
            failure_reason=reason.strip(),
        )
        self._processed_events[normalized_event_id] = updated_order
        return updated_order

    def mark_refunded(self, order_id: str, *, event_id: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        if normalized_event_id in self._processed_events:
            return self._processed_events[normalized_event_id]

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.REFUNDED:
            self._processed_events[normalized_event_id] = order
            return order

        if order.status != PaymentOrderStatus.SUCCEEDED:
            raise PaymentOrderError(
                f"Cannot mark {order.status.value} order as refunded: {order.id}"
            )

        transaction = self.ledger.post_transaction(
            f"Payment order refunded: {order.id}",
            [
                Entry(self.user_wallet_account_id, EntrySide.DEBIT, order.amount),
                Entry(self.platform_bank_account_id, EntrySide.CREDIT, order.amount),
            ],
            idempotency_key=f"payment-order:{order.id}:refunded",
        )
        updated_order = self._replace_order(
            order,
            status=PaymentOrderStatus.REFUNDED,
            ledger_transaction_id=order.ledger_transaction_id,
            refund_ledger_transaction_id=transaction.id,
        )
        self._processed_events[normalized_event_id] = updated_order
        return updated_order

    def _replace_order(
        self,
        order: PaymentOrder,
        *,
        status: PaymentOrderStatus,
        ledger_transaction_id: str | None = None,
        refund_ledger_transaction_id: str | None = None,
        failure_reason: str | None = None,
    ) -> PaymentOrder:
        updated_order = PaymentOrder(
            id=order.id,
            amount=order.amount,
            status=status,
            ledger_transaction_id=ledger_transaction_id,
            refund_ledger_transaction_id=refund_ledger_transaction_id,
            failure_reason=failure_reason,
            created_at=order.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[updated_order.id] = updated_order
        return updated_order

    def _get_order(self, order_id: str) -> PaymentOrder:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise PaymentOrderError(f"Unknown payment order: {order_id}") from exc

    def _normalize_event_id(self, event_id: str) -> str:
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            raise PaymentOrderError("Event id is required")
        return normalized_event_id

    def _build_default_ledger(
        self,
        platform_bank_account_id: str,
        user_wallet_account_id: str,
    ) -> Ledger:
        ledger = Ledger()
        try:
            ledger.create_account(
                "Platform Bank Account",
                AccountType.ASSET,
                account_id=platform_bank_account_id,
            )
            ledger.create_account(
                "User Wallet Balance",
                AccountType.LIABILITY,
                account_id=user_wallet_account_id,
            )
        except LedgerError as exc:
            raise PaymentOrderError("Default ledger could not be initialized") from exc
        return ledger
