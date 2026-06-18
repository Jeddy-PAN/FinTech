from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from core_banking_audit import CoreBankingAuditEvent, audit_payload
from core_banking import (
    CENT,
    AccountBalance,
    AccountHold,
    AccountPosting,
    AccountProduct,
    AccountProductType,
    AccountStatus,
    BankAccount,
    CoreBankingError,
    HoldStatus,
    MonthlyStatement,
    PostingDirection,
    PostingType,
    _currency,
    _fingerprint,
    _normalize_optional_text,
    _rate,
    _require_text,
    _timestamp,
    money,
)


@dataclass(frozen=True)
class AccountVersionSnapshot:
    account_id: str
    status: AccountStatus
    version: int


class SQLiteCoreBankingService:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def products(self) -> tuple[AccountProduct, ...]:
        rows = self._connection.execute(
            """
            SELECT product_id, name, product_type, annual_interest_rate
            FROM core_banking_products
            ORDER BY product_id
            """
        ).fetchall()
        return tuple(self._product_from_row(row) for row in rows)

    @property
    def accounts(self) -> tuple[BankAccount, ...]:
        rows = self._connection.execute(
            """
            SELECT account_id, customer_id, product_id, currency, status, opened_at
            FROM core_banking_accounts
            ORDER BY opened_at, account_id
            """
        ).fetchall()
        return tuple(self._account_from_row(row) for row in rows)

    @property
    def postings(self) -> tuple[AccountPosting, ...]:
        rows = self._connection.execute(
            """
            SELECT
                posting_id,
                account_id,
                direction,
                posting_type,
                amount,
                currency,
                posted_at,
                description,
                idempotency_key,
                request_fingerprint
            FROM core_banking_postings
            ORDER BY posted_at, posting_id
            """
        ).fetchall()
        return tuple(self._posting_from_row(row) for row in rows)

    @property
    def holds(self) -> tuple[AccountHold, ...]:
        rows = self._connection.execute(
            """
            SELECT
                hold_id,
                account_id,
                amount,
                currency,
                status,
                created_at,
                reason,
                released_at,
                captured_at
            FROM core_banking_holds
            ORDER BY created_at, hold_id
            """
        ).fetchall()
        return tuple(self._hold_from_row(row) for row in rows)

    @property
    def audit_events(self) -> tuple[CoreBankingAuditEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                event_id,
                event_type,
                account_id,
                occurred_at,
                actor,
                source,
                payload_json
            FROM core_banking_audit_events
            ORDER BY occurred_at, event_id
            """
        ).fetchall()
        return tuple(self._audit_event_from_row(row) for row in rows)

    def record_audit_event(
        self,
        event_type: str,
        *,
        account_id: str | None = None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
        actor: str = "system",
        source: str = "core_banking",
    ) -> CoreBankingAuditEvent:
        event = self._build_audit_event(
            event_type,
            account_id=account_id,
            payload=payload,
            occurred_at=occurred_at,
            actor=actor,
            source=source,
        )
        with self._connection:
            self._insert_audit_event(event)
        return event

    def account_version_snapshot(self, account_id: str) -> AccountVersionSnapshot:
        normalized_account_id = _require_text(account_id, "account_id")
        row = self._connection.execute(
            """
            SELECT account_id, status, version
            FROM core_banking_accounts
            WHERE account_id = ?
            """,
            (normalized_account_id,),
        ).fetchone()
        if row is None:
            raise CoreBankingError(f"Unknown account: {normalized_account_id}")
        return AccountVersionSnapshot(
            account_id=row["account_id"],
            status=AccountStatus(row["status"]),
            version=int(row["version"]),
        )

    def create_product(
        self,
        *,
        product_id: str,
        name: str,
        product_type: AccountProductType | str,
        annual_interest_rate: str | int | Decimal = "0.00",
    ) -> AccountProduct:
        product = AccountProduct(
            product_id=_require_text(product_id, "product_id"),
            name=_require_text(name, "name"),
            product_type=AccountProductType(product_type),
            annual_interest_rate=_rate(annual_interest_rate),
        )
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO core_banking_products (
                        product_id,
                        name,
                        product_type,
                        annual_interest_rate
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        product.product_id,
                        product.name,
                        product.product_type.value,
                        self._rate_to_storage(product.annual_interest_rate),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise CoreBankingError(f"Product already exists: {product.product_id}") from exc
        return product

    def open_account(
        self,
        *,
        account_id: str,
        customer_id: str,
        product_id: str,
        currency: str = "USD",
        opened_at: datetime | None = None,
    ) -> BankAccount:
        product = self._get_product(product_id)
        account = BankAccount(
            account_id=_require_text(account_id, "account_id"),
            customer_id=_require_text(customer_id, "customer_id"),
            product_id=product.product_id,
            currency=_currency(currency),
            status=AccountStatus.ACTIVE,
            opened_at=_timestamp(opened_at or datetime.now(timezone.utc), "opened_at"),
        )
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO core_banking_accounts (
                        account_id,
                        customer_id,
                        product_id,
                        currency,
                        status,
                        opened_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account.account_id,
                        account.customer_id,
                        account.product_id,
                        account.currency,
                        account.status.value,
                        account.opened_at.isoformat(),
                    ),
                )
                self._insert_audit_event(
                    self._build_audit_event(
                        "account.opened",
                        account_id=account.account_id,
                        occurred_at=account.opened_at,
                        payload=audit_payload(
                            customer_id=account.customer_id,
                            product_id=account.product_id,
                            currency=account.currency,
                            status=account.status,
                        ),
                    )
                )
        except sqlite3.IntegrityError as exc:
            raise CoreBankingError(f"Account already exists: {account.account_id}") from exc
        return account

    def set_account_status(
        self,
        account_id: str,
        status: AccountStatus | str,
        *,
        expected_version: int | None = None,
    ) -> BankAccount:
        account = self._get_account(account_id)
        before_version = self.account_version_snapshot(account.account_id).version
        normalized_expected_version = (
            self._version(expected_version)
            if expected_version is not None
            else None
        )
        updated = BankAccount(
            account_id=account.account_id,
            customer_id=account.customer_id,
            product_id=account.product_id,
            currency=account.currency,
            status=AccountStatus(status),
            opened_at=account.opened_at,
        )
        with self._connection:
            if normalized_expected_version is None:
                cursor = self._connection.execute(
                    """
                    UPDATE core_banking_accounts
                    SET status = ?, version = version + 1
                    WHERE account_id = ?
                    """,
                    (updated.status.value, updated.account_id),
                )
            else:
                cursor = self._connection.execute(
                    """
                    UPDATE core_banking_accounts
                    SET status = ?, version = version + 1
                    WHERE account_id = ? AND version = ?
                    """,
                    (
                        updated.status.value,
                        updated.account_id,
                        normalized_expected_version,
                    ),
                )
            if cursor.rowcount != 1:
                raise CoreBankingError("Account version conflict")
            after_version = before_version + 1
            self._insert_audit_event(
                self._build_audit_event(
                    "account.status_changed",
                    account_id=updated.account_id,
                    payload=audit_payload(
                        previous_status=account.status,
                        new_status=updated.status,
                        previous_version=before_version,
                        new_version=after_version,
                    ),
                )
            )
        return updated

    def balance(self, account_id: str) -> AccountBalance:
        account = self._get_account(account_id)
        return self._balance_for_account(account.account_id)

    def deposit(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        posted_at: datetime | None = None,
        description: str = "Deposit",
        idempotency_key: str | None = None,
    ) -> AccountPosting:
        account = self._require_open_account(account_id)
        with self._connection:
            return self._post_in_transaction(
                account,
                direction=PostingDirection.CREDIT,
                posting_type=PostingType.DEPOSIT,
                amount=amount,
                posted_at=posted_at,
                description=description,
                idempotency_key=idempotency_key,
            )

    def withdraw(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        posted_at: datetime | None = None,
        description: str = "Withdrawal",
        idempotency_key: str | None = None,
    ) -> AccountPosting:
        account = self._require_debit_allowed_account(account_id)
        normalized_amount = money(amount)
        with self._connection:
            if self._balance_for_account(account.account_id).available_balance < normalized_amount:
                raise CoreBankingError("Insufficient available balance")
            return self._post_in_transaction(
                account,
                direction=PostingDirection.DEBIT,
                posting_type=PostingType.WITHDRAWAL,
                amount=normalized_amount,
                posted_at=posted_at,
                description=description,
                idempotency_key=idempotency_key,
            )

    def place_hold(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        hold_id: str | None = None,
        created_at: datetime | None = None,
        reason: str = "Authorization hold",
    ) -> AccountHold:
        account = self._require_debit_allowed_account(account_id)
        normalized_amount = money(amount)
        with self._connection:
            if self._balance_for_account(account.account_id).available_balance < normalized_amount:
                raise CoreBankingError("Insufficient available balance")
            hold = AccountHold(
                hold_id=hold_id or str(uuid4()),
                account_id=account.account_id,
                amount=normalized_amount,
                currency=account.currency,
                status=HoldStatus.ACTIVE,
                created_at=_timestamp(created_at or datetime.now(timezone.utc), "created_at"),
                reason=_require_text(reason, "reason"),
            )
            try:
                self._connection.execute(
                    """
                    INSERT INTO core_banking_holds (
                        hold_id,
                        account_id,
                        amount,
                        currency,
                        status,
                        created_at,
                        reason,
                        released_at,
                        captured_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        hold.hold_id,
                        hold.account_id,
                        self._decimal_to_storage(hold.amount),
                        hold.currency,
                        hold.status.value,
                        hold.created_at.isoformat(),
                        hold.reason,
                    ),
                )
                self._insert_audit_event(
                    self._build_audit_event(
                        "hold.placed",
                        account_id=hold.account_id,
                        occurred_at=hold.created_at,
                        payload=audit_payload(
                            hold_id=hold.hold_id,
                            amount=hold.amount,
                            currency=hold.currency,
                            status=hold.status,
                            reason=hold.reason,
                        ),
                    )
                )
            except sqlite3.IntegrityError as exc:
                raise CoreBankingError(f"Hold already exists: {hold.hold_id}") from exc
        return hold

    def release_hold(
        self,
        hold_id: str,
        *,
        released_at: datetime | None = None,
    ) -> AccountHold:
        hold = self._require_active_hold(hold_id)
        updated = AccountHold(
            hold_id=hold.hold_id,
            account_id=hold.account_id,
            amount=hold.amount,
            currency=hold.currency,
            status=HoldStatus.RELEASED,
            created_at=hold.created_at,
            reason=hold.reason,
            released_at=_timestamp(released_at or datetime.now(timezone.utc), "released_at"),
            captured_at=None,
        )
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE core_banking_holds
                SET status = 'released', released_at = ?, captured_at = NULL
                WHERE hold_id = ? AND status = 'active'
                """,
                (updated.released_at.isoformat(), updated.hold_id),
            )
            if cursor.rowcount != 1:
                raise CoreBankingError("Hold is not active")
            self._insert_audit_event(
                self._build_audit_event(
                    "hold.released",
                    account_id=updated.account_id,
                    occurred_at=updated.released_at,
                    payload=audit_payload(
                        hold_id=updated.hold_id,
                        amount=updated.amount,
                        currency=updated.currency,
                        status=updated.status,
                    ),
                )
            )
        return updated

    def capture_hold(
        self,
        hold_id: str,
        *,
        posted_at: datetime | None = None,
        description: str = "Capture hold",
        idempotency_key: str | None = None,
    ) -> tuple[AccountHold, AccountPosting]:
        hold = self._require_active_hold(hold_id)
        account = self._require_debit_allowed_account(hold.account_id)
        with self._connection:
            posting = self._post_in_transaction(
                account,
                direction=PostingDirection.DEBIT,
                posting_type=PostingType.HOLD_CAPTURE,
                amount=hold.amount,
                posted_at=posted_at,
                description=description,
                idempotency_key=idempotency_key,
            )
            updated = AccountHold(
                hold_id=hold.hold_id,
                account_id=hold.account_id,
                amount=hold.amount,
                currency=hold.currency,
                status=HoldStatus.CAPTURED,
                created_at=hold.created_at,
                reason=hold.reason,
                released_at=None,
                captured_at=posting.posted_at,
            )
            cursor = self._connection.execute(
                """
                UPDATE core_banking_holds
                SET status = 'captured', released_at = NULL, captured_at = ?
                WHERE hold_id = ? AND status = 'active'
                """,
                (updated.captured_at.isoformat(), updated.hold_id),
            )
            if cursor.rowcount != 1:
                raise CoreBankingError("Hold is not active")
            self._insert_audit_event(
                self._build_audit_event(
                    "hold.captured",
                    account_id=updated.account_id,
                    occurred_at=updated.captured_at,
                    payload=audit_payload(
                        hold_id=updated.hold_id,
                        posting_id=posting.posting_id,
                        amount=updated.amount,
                        currency=updated.currency,
                        status=updated.status,
                    ),
                )
            )
        return updated, posting

    def accrue_daily_interest(
        self,
        account_id: str,
        *,
        accrual_date: date,
    ) -> AccountPosting | None:
        account = self._require_open_account(account_id)
        product = self._get_product(account.product_id)
        if product.annual_interest_rate <= Decimal("0.000000"):
            return None
        balance = self.balance(account.account_id).ledger_balance
        if balance <= Decimal("0.00"):
            return None
        interest = (balance * product.annual_interest_rate / Decimal("365")).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )
        if interest <= Decimal("0.00"):
            return None
        posted_at = datetime.combine(accrual_date, time(23, 59), tzinfo=timezone.utc)
        with self._connection:
            return self._post_in_transaction(
                account,
                direction=PostingDirection.CREDIT,
                posting_type=PostingType.INTEREST,
                amount=interest,
                posted_at=posted_at,
                description=f"Daily interest accrual for {accrual_date.isoformat()}",
                idempotency_key=f"interest:{account.account_id}:{accrual_date.isoformat()}",
            )

    def monthly_statement(
        self,
        account_id: str,
        *,
        period_start: date,
        period_end: date,
    ) -> MonthlyStatement:
        if period_end < period_start:
            raise CoreBankingError("period_end must be on or after period_start")
        account = self._get_account(account_id)
        start_at = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(period_end, time.max, tzinfo=timezone.utc)
        rows = self._connection.execute(
            """
            SELECT
                posting_id,
                account_id,
                direction,
                posting_type,
                amount,
                currency,
                posted_at,
                description,
                idempotency_key,
                request_fingerprint
            FROM core_banking_postings
            WHERE account_id = ? AND posted_at >= ? AND posted_at <= ?
            ORDER BY posted_at, posting_id
            """,
            (account.account_id, start_at.isoformat(), end_at.isoformat()),
        ).fetchall()
        period_postings = tuple(self._posting_from_row(row) for row in rows)
        total_credits = sum(
            (posting.amount for posting in period_postings
             if posting.direction == PostingDirection.CREDIT),
            Decimal("0.00"),
        ).quantize(CENT)
        total_debits = sum(
            (posting.amount for posting in period_postings
             if posting.direction == PostingDirection.DEBIT),
            Decimal("0.00"),
        ).quantize(CENT)
        interest_credited = sum(
            (posting.amount for posting in period_postings
             if posting.posting_type == PostingType.INTEREST),
            Decimal("0.00"),
        ).quantize(CENT)
        return MonthlyStatement(
            account_id=account.account_id,
            period_start=period_start,
            period_end=period_end,
            opening_balance=self._ledger_balance_at(account.account_id, before=start_at),
            closing_balance=self._ledger_balance_at(account.account_id, before=end_at),
            total_credits=total_credits,
            total_debits=total_debits,
            interest_credited=interest_credited,
            postings=period_postings,
        )

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS core_banking_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    product_type TEXT NOT NULL CHECK (product_type IN ('checking', 'savings')),
                    annual_interest_rate TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS core_banking_accounts (
                    account_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'frozen', 'closed')),
                    version INTEGER NOT NULL DEFAULT 0,
                    opened_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES core_banking_products(product_id)
                );

                CREATE TABLE IF NOT EXISTS core_banking_postings (
                    posting_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK (direction IN ('credit', 'debit')),
                    posting_type TEXT NOT NULL CHECK (
                        posting_type IN ('deposit', 'withdrawal', 'hold_capture', 'interest')
                    ),
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    posted_at TEXT NOT NULL,
                    description TEXT NOT NULL,
                    idempotency_key TEXT,
                    request_fingerprint TEXT,
                    FOREIGN KEY (account_id) REFERENCES core_banking_accounts(account_id),
                    CHECK (CAST(amount AS REAL) > 0)
                );

                CREATE TABLE IF NOT EXISTS core_banking_holds (
                    hold_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'released', 'captured')),
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    released_at TEXT,
                    captured_at TEXT,
                    FOREIGN KEY (account_id) REFERENCES core_banking_accounts(account_id),
                    CHECK (CAST(amount AS REAL) > 0)
                );

                CREATE TABLE IF NOT EXISTS core_banking_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    account_id TEXT,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (account_id) REFERENCES core_banking_accounts(account_id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_core_banking_postings_idempotency_key
                ON core_banking_postings (idempotency_key)
                WHERE idempotency_key IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_core_banking_postings_account_time
                ON core_banking_postings (account_id, posted_at);

                CREATE INDEX IF NOT EXISTS idx_core_banking_holds_account_status
                ON core_banking_holds (account_id, status);

                CREATE INDEX IF NOT EXISTS idx_core_banking_audit_events_account_time
                ON core_banking_audit_events (account_id, occurred_at);
                """
            )
            self._ensure_account_version_column()

    def _post_in_transaction(
        self,
        account: BankAccount,
        *,
        direction: PostingDirection,
        posting_type: PostingType,
        amount: str | int | Decimal,
        posted_at: datetime | None,
        description: str,
        idempotency_key: str | None,
    ) -> AccountPosting:
        normalized_amount = money(amount)
        normalized_key = _normalize_optional_text(idempotency_key, "idempotency_key")
        fingerprint = _fingerprint(
            {
                "account_id": account.account_id,
                "direction": direction.value,
                "posting_type": posting_type.value,
                "amount": str(normalized_amount),
                "description": _require_text(description, "description"),
            }
        )
        if normalized_key:
            existing = self._get_posting_by_idempotency_key(normalized_key)
            if existing:
                if existing.request_fingerprint != fingerprint:
                    raise CoreBankingError(
                        "Idempotency key was reused with different request data"
                    )
                return existing

        posting = AccountPosting(
            posting_id=str(uuid4()),
            account_id=account.account_id,
            direction=direction,
            posting_type=posting_type,
            amount=normalized_amount,
            currency=account.currency,
            posted_at=_timestamp(posted_at or datetime.now(timezone.utc), "posted_at"),
            description=description.strip(),
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
        )
        try:
            self._connection.execute(
                """
                INSERT INTO core_banking_postings (
                    posting_id,
                    account_id,
                    direction,
                    posting_type,
                    amount,
                    currency,
                    posted_at,
                    description,
                    idempotency_key,
                    request_fingerprint
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    posting.posting_id,
                    posting.account_id,
                    posting.direction.value,
                    posting.posting_type.value,
                    self._decimal_to_storage(posting.amount),
                    posting.currency,
                    posting.posted_at.isoformat(),
                    posting.description,
                    posting.idempotency_key,
                    posting.request_fingerprint,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CoreBankingError(f"Posting could not be saved: {posting.posting_id}") from exc
        self._record_posting_created_in_transaction(posting)
        return posting

    def _record_posting_created_in_transaction(self, posting: AccountPosting) -> None:
        self._insert_audit_event(
            self._build_audit_event(
                "posting.created",
                account_id=posting.account_id,
                occurred_at=posting.posted_at,
                payload=audit_payload(
                    posting_id=posting.posting_id,
                    direction=posting.direction,
                    posting_type=posting.posting_type,
                    amount=posting.amount,
                    currency=posting.currency,
                    idempotency_key=posting.idempotency_key,
                ),
            )
        )
        if posting.posting_type == PostingType.INTEREST:
            self._insert_audit_event(
                self._build_audit_event(
                    "interest.accrued",
                    account_id=posting.account_id,
                    occurred_at=posting.posted_at,
                    payload=audit_payload(
                        posting_id=posting.posting_id,
                        amount=posting.amount,
                        currency=posting.currency,
                        idempotency_key=posting.idempotency_key,
                    ),
                )
            )

    def _balance_for_account(self, account_id: str) -> AccountBalance:
        ledger_balance = self._ledger_balance_at(
            account_id,
            before=datetime.max.replace(tzinfo=timezone.utc),
        )
        active_hold_amount = self._active_hold_amount(account_id)
        return AccountBalance(
            account_id=account_id,
            ledger_balance=ledger_balance,
            active_hold_amount=active_hold_amount,
            available_balance=(ledger_balance - active_hold_amount).quantize(CENT),
        )

    def _ledger_balance_at(self, account_id: str, *, before: datetime) -> Decimal:
        rows = self._connection.execute(
            """
            SELECT direction, amount
            FROM core_banking_postings
            WHERE account_id = ? AND posted_at <= ?
            """,
            (account_id, before.isoformat()),
        ).fetchall()
        balance = Decimal("0.00")
        for row in rows:
            amount = self._decimal_from_storage(row["amount"])
            if PostingDirection(row["direction"]) == PostingDirection.CREDIT:
                balance += amount
            else:
                balance -= amount
        return balance.quantize(CENT)

    def _active_hold_amount(self, account_id: str) -> Decimal:
        rows = self._connection.execute(
            """
            SELECT amount
            FROM core_banking_holds
            WHERE account_id = ? AND status = 'active'
            """,
            (account_id,),
        ).fetchall()
        return sum(
            (self._decimal_from_storage(row["amount"]) for row in rows),
            Decimal("0.00"),
        ).quantize(CENT)

    def _get_product(self, product_id: str) -> AccountProduct:
        normalized_product_id = _require_text(product_id, "product_id")
        row = self._connection.execute(
            """
            SELECT product_id, name, product_type, annual_interest_rate
            FROM core_banking_products
            WHERE product_id = ?
            """,
            (normalized_product_id,),
        ).fetchone()
        if row is None:
            raise CoreBankingError(f"Unknown product: {normalized_product_id}")
        return self._product_from_row(row)

    def _get_account(self, account_id: str) -> BankAccount:
        normalized_account_id = _require_text(account_id, "account_id")
        row = self._connection.execute(
            """
            SELECT account_id, customer_id, product_id, currency, status, opened_at
            FROM core_banking_accounts
            WHERE account_id = ?
            """,
            (normalized_account_id,),
        ).fetchone()
        if row is None:
            raise CoreBankingError(f"Unknown account: {normalized_account_id}")
        return self._account_from_row(row)

    def _require_open_account(self, account_id: str) -> BankAccount:
        account = self._get_account(account_id)
        if account.status == AccountStatus.CLOSED:
            raise CoreBankingError("Account is closed")
        return account

    def _require_debit_allowed_account(self, account_id: str) -> BankAccount:
        account = self._require_open_account(account_id)
        if account.status == AccountStatus.FROZEN:
            raise CoreBankingError("Account is frozen")
        return account

    def _require_active_hold(self, hold_id: str) -> AccountHold:
        normalized_hold_id = _require_text(hold_id, "hold_id")
        row = self._connection.execute(
            """
            SELECT
                hold_id,
                account_id,
                amount,
                currency,
                status,
                created_at,
                reason,
                released_at,
                captured_at
            FROM core_banking_holds
            WHERE hold_id = ?
            """,
            (normalized_hold_id,),
        ).fetchone()
        if row is None:
            raise CoreBankingError(f"Unknown hold: {normalized_hold_id}")
        hold = self._hold_from_row(row)
        if hold.status != HoldStatus.ACTIVE:
            raise CoreBankingError("Hold is not active")
        return hold

    def _get_posting_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AccountPosting | None:
        row = self._connection.execute(
            """
            SELECT
                posting_id,
                account_id,
                direction,
                posting_type,
                amount,
                currency,
                posted_at,
                description,
                idempotency_key,
                request_fingerprint
            FROM core_banking_postings
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return self._posting_from_row(row)

    def _product_from_row(self, row: sqlite3.Row) -> AccountProduct:
        return AccountProduct(
            product_id=row["product_id"],
            name=row["name"],
            product_type=AccountProductType(row["product_type"]),
            annual_interest_rate=Decimal(row["annual_interest_rate"]),
        )

    def _account_from_row(self, row: sqlite3.Row) -> BankAccount:
        return BankAccount(
            account_id=row["account_id"],
            customer_id=row["customer_id"],
            product_id=row["product_id"],
            currency=row["currency"],
            status=AccountStatus(row["status"]),
            opened_at=datetime.fromisoformat(row["opened_at"]),
        )

    def _posting_from_row(self, row: sqlite3.Row) -> AccountPosting:
        return AccountPosting(
            posting_id=row["posting_id"],
            account_id=row["account_id"],
            direction=PostingDirection(row["direction"]),
            posting_type=PostingType(row["posting_type"]),
            amount=self._decimal_from_storage(row["amount"]),
            currency=row["currency"],
            posted_at=datetime.fromisoformat(row["posted_at"]),
            description=row["description"],
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
        )

    def _hold_from_row(self, row: sqlite3.Row) -> AccountHold:
        return AccountHold(
            hold_id=row["hold_id"],
            account_id=row["account_id"],
            amount=self._decimal_from_storage(row["amount"]),
            currency=row["currency"],
            status=HoldStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            reason=row["reason"],
            released_at=(
                datetime.fromisoformat(row["released_at"])
                if row["released_at"] is not None
                else None
            ),
            captured_at=(
                datetime.fromisoformat(row["captured_at"])
                if row["captured_at"] is not None
                else None
            ),
        )

    def _build_audit_event(
        self,
        event_type: str,
        *,
        account_id: str | None = None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
        actor: str = "system",
        source: str = "core_banking",
    ) -> CoreBankingAuditEvent:
        return CoreBankingAuditEvent(
            event_id=str(uuid4()),
            event_type=_require_text(event_type, "event_type"),
            account_id=(
                _require_text(account_id, "account_id")
                if account_id is not None
                else None
            ),
            occurred_at=_timestamp(occurred_at or datetime.now(timezone.utc), "occurred_at"),
            actor=_require_text(actor, "actor"),
            source=_require_text(source, "source"),
            payload=audit_payload(**(payload or {})),
        )

    def _insert_audit_event(self, event: CoreBankingAuditEvent) -> None:
        self._connection.execute(
            """
            INSERT INTO core_banking_audit_events (
                event_id,
                event_type,
                account_id,
                occurred_at,
                actor,
                source,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.account_id,
                event.occurred_at.isoformat(),
                event.actor,
                event.source,
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
            ),
        )

    def _audit_event_from_row(self, row: sqlite3.Row) -> CoreBankingAuditEvent:
        return CoreBankingAuditEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            account_id=row["account_id"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            actor=row["actor"],
            source=row["source"],
            payload=dict(json.loads(row["payload_json"])),
        )

    def _ensure_account_version_column(self) -> None:
        rows = self._connection.execute("PRAGMA table_info(core_banking_accounts)").fetchall()
        column_names = {row["name"] for row in rows}
        if "version" not in column_names:
            self._connection.execute(
                """
                ALTER TABLE core_banking_accounts
                ADD COLUMN version INTEGER NOT NULL DEFAULT 0
                """
            )

    def _decimal_to_storage(self, amount: Decimal) -> str:
        return str(amount.quantize(CENT))

    def _decimal_from_storage(self, amount: str) -> Decimal:
        return Decimal(amount).quantize(CENT)

    def _rate_to_storage(self, rate: Decimal) -> str:
        return str(rate)

    def _version(self, value: int) -> int:
        version = int(value)
        if version < 0:
            raise CoreBankingError("Version must be greater than or equal to 0")
        return version
