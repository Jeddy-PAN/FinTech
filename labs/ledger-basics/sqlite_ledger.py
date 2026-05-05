from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from ledger import Account, AccountType, CENT, Entry, EntrySide, LedgerError, Transaction


class SQLiteLedger:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def create_account(
        self,
        name: str,
        account_type: AccountType,
        account_id: str | None = None,
    ) -> Account:
        if not name.strip():
            raise LedgerError("Account name is required")

        account = Account(
            id=account_id or str(uuid4()),
            name=name.strip(),
            type=account_type,
        )

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO accounts (id, name, type)
                    VALUES (?, ?, ?)
                    """,
                    (account.id, account.name, account.type.value),
                )
        except sqlite3.IntegrityError as exc:
            raise LedgerError(f"Account already exists: {account.id}") from exc

        return account

    @property
    def accounts(self) -> tuple[Account, ...]:
        rows = self._connection.execute(
            """
            SELECT id, name, type
            FROM accounts
            ORDER BY created_at, id
            """
        ).fetchall()
        return tuple(self._account_from_row(row) for row in rows)

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        rows = self._connection.execute(
            """
            SELECT id, description, posted_at, idempotency_key, request_fingerprint
            FROM transactions
            ORDER BY posted_at, id
            """
        ).fetchall()
        return tuple(self._transaction_from_row(row) for row in rows)

    def post_transaction(
        self,
        description: str,
        entries: Iterable[Entry],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Transaction:
        normalized_key = self._normalize_idempotency_key(idempotency_key)
        normalized_entries = tuple(entries)
        request_fingerprint = self._request_fingerprint(description, normalized_entries)

        if normalized_key:
            existing = self._get_transaction_by_idempotency_key(normalized_key)
            if existing:
                self._validate_idempotent_retry(existing, request_fingerprint)
                return existing

        self._validate_transaction(description, normalized_entries)

        posted_at = datetime.now(timezone.utc)
        transaction = Transaction(
            id=transaction_id or str(uuid4()),
            description=description.strip(),
            entries=normalized_entries,
            idempotency_key=normalized_key,
            request_fingerprint=request_fingerprint,
            posted_at=posted_at,
        )

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO transactions (
                        id,
                        description,
                        posted_at,
                        idempotency_key,
                        request_fingerprint
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        transaction.id,
                        transaction.description,
                        transaction.posted_at.isoformat(),
                        transaction.idempotency_key,
                        transaction.request_fingerprint,
                    ),
                )
                self._connection.executemany(
                    """
                    INSERT INTO entries (transaction_id, account_id, side, amount)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            transaction.id,
                            entry.account_id,
                            entry.side.value,
                            self._amount_to_storage(entry.amount),
                        )
                        for entry in transaction.entries
                    ],
                )
        except sqlite3.IntegrityError as exc:
            raise LedgerError(f"Transaction could not be posted: {transaction.id}") from exc

        return transaction

    def balance_for(self, account_id: str) -> Decimal:
        account = self._get_account(account_id)
        rows = self._connection.execute(
            """
            SELECT side, amount
            FROM entries
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchall()

        balance = Decimal("0.00")
        for row in rows:
            entry = Entry(
                account_id=account_id,
                side=EntrySide(row["side"]),
                amount=self._amount_from_storage(row["amount"]),
            )
            balance += self._signed_amount(account.type, entry)

        return balance.quantize(CENT)

    def trial_balance(self) -> dict[EntrySide, Decimal]:
        rows = self._connection.execute(
            """
            SELECT side, amount
            FROM entries
            """
        ).fetchall()

        totals = {
            EntrySide.DEBIT: Decimal("0.00"),
            EntrySide.CREDIT: Decimal("0.00"),
        }
        for row in rows:
            totals[EntrySide(row["side"])] += self._amount_from_storage(row["amount"])

        return {side: amount.quantize(CENT) for side, amount in totals.items()}

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('asset', 'liability', 'equity', 'income', 'expense')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    posted_at TEXT NOT NULL,
                    idempotency_key TEXT,
                    request_fingerprint TEXT
                );

                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('debit', 'credit')),
                    amount TEXT NOT NULL,
                    FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    CHECK (CAST(amount AS REAL) > 0)
                );

                CREATE INDEX IF NOT EXISTS idx_entries_account_id
                ON entries (account_id);

                CREATE INDEX IF NOT EXISTS idx_entries_transaction_id
                ON entries (transaction_id);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_idempotency_key
                ON transactions (idempotency_key)
                WHERE idempotency_key IS NOT NULL;
                """
            )
            self._ensure_idempotency_key_column()
            self._ensure_request_fingerprint_column()

    def _ensure_idempotency_key_column(self) -> None:
        columns = self._connection.execute("PRAGMA table_info(transactions)").fetchall()
        column_names = {column["name"] for column in columns}
        if "idempotency_key" not in column_names:
            self._connection.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN idempotency_key TEXT
                """
            )
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_idempotency_key
            ON transactions (idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )

    def _ensure_request_fingerprint_column(self) -> None:
        columns = self._connection.execute("PRAGMA table_info(transactions)").fetchall()
        column_names = {column["name"] for column in columns}
        if "request_fingerprint" not in column_names:
            self._connection.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN request_fingerprint TEXT
                """
            )

    def _validate_transaction(self, description: str, entries: tuple[Entry, ...]) -> None:
        if not description.strip():
            raise LedgerError("Transaction description is required")

        if len(entries) < 2:
            raise LedgerError("A transaction needs at least two entries")

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for entry in entries:
            self._get_account(entry.account_id)

            if entry.amount <= 0:
                raise LedgerError("Entry amount must be positive")

            if entry.amount != entry.amount.quantize(CENT):
                raise LedgerError("Entry amount must use two decimal places")

            if entry.side == EntrySide.DEBIT:
                total_debit += entry.amount
            elif entry.side == EntrySide.CREDIT:
                total_credit += entry.amount
            else:
                raise LedgerError(f"Unknown entry side: {entry.side}")

        if total_debit != total_credit:
            raise LedgerError(
                f"Transaction is not balanced: debit={total_debit}, credit={total_credit}"
            )

    def _get_account(self, account_id: str) -> Account:
        row = self._connection.execute(
            """
            SELECT id, name, type
            FROM accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()

        if row is None:
            raise LedgerError(f"Unknown account: {account_id}")

        return self._account_from_row(row)

    def _transaction_from_row(self, row: sqlite3.Row) -> Transaction:
        entry_rows = self._connection.execute(
            """
            SELECT account_id, side, amount
            FROM entries
            WHERE transaction_id = ?
            ORDER BY id
            """,
            (row["id"],),
        ).fetchall()

        return Transaction(
            id=row["id"],
            description=row["description"],
            posted_at=datetime.fromisoformat(row["posted_at"]),
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
            entries=tuple(
                Entry(
                    account_id=entry_row["account_id"],
                    side=EntrySide(entry_row["side"]),
                    amount=self._amount_from_storage(entry_row["amount"]),
                )
                for entry_row in entry_rows
            ),
        )

    def _account_from_row(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            name=row["name"],
            type=AccountType(row["type"]),
        )

    def _signed_amount(self, account_type: AccountType, entry: Entry) -> Decimal:
        debit_positive_types = {AccountType.ASSET, AccountType.EXPENSE}
        is_debit_positive = account_type in debit_positive_types

        if entry.side == EntrySide.DEBIT:
            return entry.amount if is_debit_positive else -entry.amount

        return -entry.amount if is_debit_positive else entry.amount

    def _amount_to_storage(self, amount: Decimal) -> str:
        return str(amount.quantize(CENT))

    def _amount_from_storage(self, amount: str) -> Decimal:
        return Decimal(amount).quantize(CENT)

    def _get_transaction_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Transaction | None:
        row = self._connection.execute(
            """
            SELECT id, description, posted_at, idempotency_key, request_fingerprint
            FROM transactions
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()

        if row is None:
            return None

        return self._transaction_from_row(row)

    def _normalize_idempotency_key(self, idempotency_key: str | None) -> str | None:
        if idempotency_key is None:
            return None

        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise LedgerError("Idempotency key cannot be blank")

        return normalized_key

    def _request_fingerprint(self, description: str, entries: tuple[Entry, ...]) -> str:
        payload = {
            "description": description.strip(),
            "entries": sorted(
                [
                    {
                        "account_id": entry.account_id,
                        "side": entry.side.value,
                        "amount": str(entry.amount.quantize(CENT)),
                    }
                    for entry in entries
                ],
                key=lambda item: (item["account_id"], item["side"], item["amount"]),
            ),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _validate_idempotent_retry(
        self,
        existing: Transaction,
        request_fingerprint: str,
    ) -> None:
        if existing.request_fingerprint != request_fingerprint:
            raise LedgerError("Idempotency key was reused with different request data")
