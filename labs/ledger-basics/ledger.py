from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Iterable
from uuid import uuid4


CENT = Decimal("0.01")


class LedgerError(ValueError):
    """Base error for invalid ledger operations."""


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class EntrySide(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    type: AccountType


@dataclass(frozen=True)
class Entry:
    account_id: str
    side: EntrySide
    amount: Decimal


@dataclass(frozen=True)
class Transaction:
    id: str
    description: str
    entries: tuple[Entry, ...]
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def money(value: str | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise LedgerError(f"Invalid money amount: {value!r}") from exc

    if amount <= 0:
        raise LedgerError("Entry amount must be positive")

    return amount


class Ledger:
    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._transactions: list[Transaction] = []

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(self._accounts.values())

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions)

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

        if account.id in self._accounts:
            raise LedgerError(f"Account already exists: {account.id}")

        self._accounts[account.id] = account
        return account

    def post_transaction(
        self,
        description: str,
        entries: Iterable[Entry],
        transaction_id: str | None = None,
    ) -> Transaction:
        normalized_entries = tuple(entries)
        self._validate_transaction(description, normalized_entries)

        transaction = Transaction(
            id=transaction_id or str(uuid4()),
            description=description.strip(),
            entries=normalized_entries,
        )
        self._transactions.append(transaction)
        return transaction

    def balance_for(self, account_id: str) -> Decimal:
        account = self._get_account(account_id)
        balance = Decimal("0.00")

        for transaction in self._transactions:
            for entry in transaction.entries:
                if entry.account_id != account_id:
                    continue
                balance += self._signed_amount(account.type, entry)

        return balance.quantize(CENT)

    def trial_balance(self) -> dict[EntrySide, Decimal]:
        totals = {
            EntrySide.DEBIT: Decimal("0.00"),
            EntrySide.CREDIT: Decimal("0.00"),
        }

        for transaction in self._transactions:
            for entry in transaction.entries:
                totals[entry.side] += entry.amount

        return {side: amount.quantize(CENT) for side, amount in totals.items()}

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
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise LedgerError(f"Unknown account: {account_id}") from exc

    def _signed_amount(self, account_type: AccountType, entry: Entry) -> Decimal:
        debit_positive_types = {AccountType.ASSET, AccountType.EXPENSE}
        is_debit_positive = account_type in debit_positive_types

        if entry.side == EntrySide.DEBIT:
            return entry.amount if is_debit_positive else -entry.amount

        return -entry.amount if is_debit_positive else entry.amount
