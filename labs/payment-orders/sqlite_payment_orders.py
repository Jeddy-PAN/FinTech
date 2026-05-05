from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import uuid4


LEDGER_PATH = Path(__file__).resolve().parents[1] / "ledger-basics"
if str(LEDGER_PATH) not in sys.path:
    sys.path.insert(0, str(LEDGER_PATH))

from ledger import AccountType, Entry, EntrySide, LedgerError, money
from sqlite_ledger import SQLiteLedger

from payment_orders import PaymentOrder, PaymentOrderError, PaymentOrderStatus


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    event_type: str
    aggregate_id: str
    payload: str
    status: str
    created_at: datetime
    published_at: datetime | None = None


class OutboxPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> None:
        ...


@dataclass(frozen=True)
class OutboxPublishResult:
    attempted: int
    published: int
    failed: int


class SQLitePaymentOrderService:
    def __init__(
        self,
        database_path: str | Path,
        *,
        platform_bank_account_id: str = "platform_bank",
        user_wallet_account_id: str = "user_wallet",
    ) -> None:
        self.database_path = Path(database_path)
        self.ledger = SQLiteLedger(self.database_path)
        self.platform_bank_account_id = platform_bank_account_id
        self.user_wallet_account_id = user_wallet_account_id
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row
        self._create_schema()
        self._ensure_default_ledger_accounts()

    def close(self) -> None:
        self._connection.close()
        self.ledger.close()

    @property
    def orders(self) -> tuple[PaymentOrder, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                amount,
                status,
                ledger_transaction_id,
                refund_ledger_transaction_id,
                failure_reason,
                created_at,
                updated_at
            FROM payment_orders
            ORDER BY created_at, id
            """
        ).fetchall()
        return tuple(self._order_from_row(row) for row in rows)

    @property
    def pending_outbox_messages(self) -> tuple[OutboxMessage, ...]:
        rows = self._connection.execute(
            """
            SELECT id, event_type, aggregate_id, payload, status, created_at, published_at
            FROM payment_outbox
            WHERE status = 'pending'
            ORDER BY created_at, id
            """
        ).fetchall()
        return tuple(self._outbox_message_from_row(row) for row in rows)

    def create_order(
        self,
        amount: str | int | Decimal,
        *,
        order_id: str | None = None,
    ) -> PaymentOrder:
        normalized_amount = money(amount)
        now = datetime.now(timezone.utc)
        order = PaymentOrder(
            id=order_id or str(uuid4()),
            amount=normalized_amount,
            status=PaymentOrderStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO payment_orders (
                        id,
                        amount,
                        status,
                        ledger_transaction_id,
                        refund_ledger_transaction_id,
                        failure_reason,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._order_to_row(order),
                )
                self._insert_outbox_message(
                    order.id,
                    "payment_order.created",
                    self._order_payload(order),
                )
        except sqlite3.IntegrityError as exc:
            raise PaymentOrderError(f"Payment order already exists: {order.id}") from exc

        return order

    def mark_succeeded(self, order_id: str, *, event_id: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        existing = self._get_processed_event(normalized_event_id)
        if existing:
            return existing

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.SUCCEEDED:
            self._record_processed_event(normalized_event_id, order)
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
            outbox_event_type="payment_order.succeeded",
        )
        self._record_processed_event(normalized_event_id, updated_order)
        return updated_order

    def mark_failed(self, order_id: str, *, event_id: str, reason: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        existing = self._get_processed_event(normalized_event_id)
        if existing:
            return existing

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.FAILED:
            self._record_processed_event(normalized_event_id, order)
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
            outbox_event_type="payment_order.failed",
        )
        self._record_processed_event(normalized_event_id, updated_order)
        return updated_order

    def mark_refunded(self, order_id: str, *, event_id: str) -> PaymentOrder:
        normalized_event_id = self._normalize_event_id(event_id)
        existing = self._get_processed_event(normalized_event_id)
        if existing:
            return existing

        order = self._get_order(order_id)
        if order.status == PaymentOrderStatus.REFUNDED:
            self._record_processed_event(normalized_event_id, order)
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
            outbox_event_type="payment_order.refunded",
        )
        self._record_processed_event(normalized_event_id, updated_order)
        return updated_order

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS payment_orders (
                    id TEXT PRIMARY KEY,
                    amount TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed', 'refunded')),
                    ledger_transaction_id TEXT,
                    refund_ledger_transaction_id TEXT,
                    failure_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS processed_payment_events (
                    event_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES payment_orders(id)
                );

                CREATE TABLE IF NOT EXISTS payment_outbox (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'published')),
                    created_at TEXT NOT NULL,
                    published_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_payment_orders_status
                ON payment_orders (status);

                CREATE INDEX IF NOT EXISTS idx_payment_outbox_status
                ON payment_outbox (status, created_at);
                """
            )

    def _ensure_default_ledger_accounts(self) -> None:
        existing_account_ids = {account.id for account in self.ledger.accounts}
        if self.platform_bank_account_id not in existing_account_ids:
            try:
                self.ledger.create_account(
                    "Platform Bank Account",
                    AccountType.ASSET,
                    account_id=self.platform_bank_account_id,
                )
            except LedgerError as exc:
                raise PaymentOrderError("Platform bank account could not be created") from exc

        existing_account_ids = {account.id for account in self.ledger.accounts}
        if self.user_wallet_account_id not in existing_account_ids:
            try:
                self.ledger.create_account(
                    "User Wallet Balance",
                    AccountType.LIABILITY,
                    account_id=self.user_wallet_account_id,
                )
            except LedgerError as exc:
                raise PaymentOrderError("User wallet account could not be created") from exc

    def _replace_order(
        self,
        order: PaymentOrder,
        *,
        status: PaymentOrderStatus,
        ledger_transaction_id: str | None = None,
        refund_ledger_transaction_id: str | None = None,
        failure_reason: str | None = None,
        outbox_event_type: str | None = None,
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
        with self._connection:
            self._connection.execute(
                """
                UPDATE payment_orders
                SET
                    status = ?,
                    ledger_transaction_id = ?,
                    refund_ledger_transaction_id = ?,
                    failure_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    updated_order.status.value,
                    updated_order.ledger_transaction_id,
                    updated_order.refund_ledger_transaction_id,
                    updated_order.failure_reason,
                    updated_order.updated_at.isoformat(),
                    updated_order.id,
                ),
            )
            if outbox_event_type:
                self._insert_outbox_message(
                    updated_order.id,
                    outbox_event_type,
                    self._order_payload(updated_order),
                )
        return updated_order

    def _get_order(self, order_id: str) -> PaymentOrder:
        row = self._connection.execute(
            """
            SELECT
                id,
                amount,
                status,
                ledger_transaction_id,
                refund_ledger_transaction_id,
                failure_reason,
                created_at,
                updated_at
            FROM payment_orders
            WHERE id = ?
            """,
            (order_id,),
        ).fetchone()

        if row is None:
            raise PaymentOrderError(f"Unknown payment order: {order_id}")

        return self._order_from_row(row)

    def _record_processed_event(self, event_id: str, order: PaymentOrder) -> None:
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO processed_payment_events (event_id, order_id, processed_at)
                    VALUES (?, ?, ?)
                    """,
                    (event_id, order.id, datetime.now(timezone.utc).isoformat()),
                )
        except sqlite3.IntegrityError:
            return

    def mark_outbox_message_published(self, message_id: str) -> OutboxMessage:
        message = self._get_outbox_message(message_id)
        if message.status == "published":
            return message

        published_at = datetime.now(timezone.utc)
        with self._connection:
            self._connection.execute(
                """
                UPDATE payment_outbox
                SET status = 'published', published_at = ?
                WHERE id = ?
                """,
                (published_at.isoformat(), message_id),
            )

        return OutboxMessage(
            id=message.id,
            event_type=message.event_type,
            aggregate_id=message.aggregate_id,
            payload=message.payload,
            status="published",
            created_at=message.created_at,
            published_at=published_at,
        )

    def publish_pending_outbox_messages(
        self,
        publisher: OutboxPublisher,
        *,
        limit: int | None = None,
    ) -> OutboxPublishResult:
        messages = self.pending_outbox_messages
        if limit is not None:
            if limit <= 0:
                raise PaymentOrderError("Outbox publish limit must be positive")
            messages = messages[:limit]

        published = 0
        failed = 0
        for message in messages:
            try:
                publisher.publish(message)
            except Exception:
                failed += 1
                continue

            self.mark_outbox_message_published(message.id)
            published += 1

        return OutboxPublishResult(
            attempted=len(messages),
            published=published,
            failed=failed,
        )

    def _get_processed_event(self, event_id: str) -> PaymentOrder | None:
        row = self._connection.execute(
            """
            SELECT order_id
            FROM processed_payment_events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()

        if row is None:
            return None

        return self._get_order(row["order_id"])

    def _normalize_event_id(self, event_id: str) -> str:
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            raise PaymentOrderError("Event id is required")
        return normalized_event_id

    def _order_from_row(self, row: sqlite3.Row) -> PaymentOrder:
        return PaymentOrder(
            id=row["id"],
            amount=Decimal(row["amount"]),
            status=PaymentOrderStatus(row["status"]),
            ledger_transaction_id=row["ledger_transaction_id"],
            refund_ledger_transaction_id=row["refund_ledger_transaction_id"],
            failure_reason=row["failure_reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _order_to_row(self, order: PaymentOrder) -> tuple[str, str, str, str | None, str | None, str | None, str, str]:
        return (
            order.id,
            str(order.amount),
            order.status.value,
            order.ledger_transaction_id,
            order.refund_ledger_transaction_id,
            order.failure_reason,
            order.created_at.isoformat(),
            order.updated_at.isoformat(),
        )

    def _insert_outbox_message(
        self,
        aggregate_id: str,
        event_type: str,
        payload: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO payment_outbox (
                id,
                event_type,
                aggregate_id,
                payload,
                status,
                created_at,
                published_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, NULL)
            """,
            (
                str(uuid4()),
                event_type,
                aggregate_id,
                payload,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _order_payload(self, order: PaymentOrder) -> str:
        return (
            "{"
            f'"id":"{order.id}",'
            f'"amount":"{order.amount}",'
            f'"status":"{order.status.value}",'
            f'"ledger_transaction_id":{self._json_string_or_null(order.ledger_transaction_id)},'
            f'"refund_ledger_transaction_id":{self._json_string_or_null(order.refund_ledger_transaction_id)},'
            f'"failure_reason":{self._json_string_or_null(order.failure_reason)}'
            "}"
        )

    def _json_string_or_null(self, value: str | None) -> str:
        if value is None:
            return "null"
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _get_outbox_message(self, message_id: str) -> OutboxMessage:
        row = self._connection.execute(
            """
            SELECT id, event_type, aggregate_id, payload, status, created_at, published_at
            FROM payment_outbox
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()

        if row is None:
            raise PaymentOrderError(f"Unknown outbox message: {message_id}")

        return self._outbox_message_from_row(row)

    def _outbox_message_from_row(self, row: sqlite3.Row) -> OutboxMessage:
        return OutboxMessage(
            id=row["id"],
            event_type=row["event_type"],
            aggregate_id=row["aggregate_id"],
            payload=row["payload"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            published_at=(
                datetime.fromisoformat(row["published_at"])
                if row["published_at"] is not None
                else None
            ),
        )
