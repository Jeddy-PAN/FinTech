from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from ledger import AccountType, Entry, EntrySide, LedgerError, money
from sqlite_ledger import SQLiteLedger


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
def ledger(database_path):
    instance = SQLiteLedger(database_path)
    try:
        yield instance
    finally:
        instance.close()


def test_sqlite_ledger_persists_accounts_and_transactions(database_path) -> None:
    ledger = SQLiteLedger(database_path)
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
    )
    ledger.close()

    reopened = SQLiteLedger(database_path)
    try:
        assert reopened.balance_for(bank.id) == Decimal("100.00")
        assert reopened.balance_for(wallet.id) == Decimal("100.00")
        assert len(reopened.transactions) == 1
    finally:
        reopened.close()


def test_sqlite_ledger_rejects_unbalanced_transaction_without_partial_write(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    with pytest.raises(LedgerError, match="not balanced"):
        ledger.post_transaction(
            "Invalid top-up",
            [
                Entry(bank.id, EntrySide.DEBIT, money("100.00")),
                Entry(wallet.id, EntrySide.CREDIT, money("99.00")),
            ],
        )

    assert ledger.transactions == ()
    assert ledger.balance_for(bank.id) == Decimal("0.00")
    assert ledger.balance_for(wallet.id) == Decimal("0.00")


def test_sqlite_ledger_rejects_unknown_account_without_partial_write(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")

    with pytest.raises(LedgerError, match="Unknown account"):
        ledger.post_transaction(
            "Invalid transaction",
            [
                Entry(bank.id, EntrySide.DEBIT, money("10.00")),
                Entry("missing", EntrySide.CREDIT, money("10.00")),
            ],
        )

    assert ledger.transactions == ()
    assert ledger.balance_for(bank.id) == Decimal("0.00")


def test_sqlite_ledger_trial_balance_totals_match(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")
    fee_income = ledger.create_account("Fee Income", AccountType.INCOME, account_id="fee_income")

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
    )
    ledger.post_transaction(
        "Platform fee: 2.00",
        [
            Entry(wallet.id, EntrySide.DEBIT, money("2.00")),
            Entry(fee_income.id, EntrySide.CREDIT, money("2.00")),
        ],
    )

    totals = ledger.trial_balance()
    assert totals[EntrySide.DEBIT] == Decimal("102.00")
    assert totals[EntrySide.CREDIT] == Decimal("102.00")
    assert ledger.balance_for(wallet.id) == Decimal("98.00")
    assert ledger.balance_for(fee_income.id) == Decimal("2.00")


def test_sqlite_ledger_idempotency_key_returns_existing_transaction(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    first = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )
    second = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )

    assert second == first
    assert len(ledger.transactions) == 1
    assert ledger.balance_for(bank.id) == Decimal("100.00")
    assert ledger.balance_for(wallet.id) == Decimal("100.00")


def test_sqlite_ledger_idempotency_key_survives_reopen(database_path) -> None:
    ledger = SQLiteLedger(database_path)
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    first = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )
    ledger.close()

    reopened = SQLiteLedger(database_path)
    try:
        second = reopened.post_transaction(
            "User wallet top-up: 100.00",
            [
                Entry(bank.id, EntrySide.DEBIT, money("100.00")),
                Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
            ],
            idempotency_key="payment-request-001",
        )

        assert second == first
        assert len(reopened.transactions) == 1
        assert reopened.balance_for(bank.id) == Decimal("100.00")
        assert reopened.balance_for(wallet.id) == Decimal("100.00")
    finally:
        reopened.close()


def test_sqlite_ledger_blank_idempotency_key_is_rejected(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    with pytest.raises(LedgerError, match="Idempotency key cannot be blank"):
        ledger.post_transaction(
            "User wallet top-up: 100.00",
            [
                Entry(bank.id, EntrySide.DEBIT, money("100.00")),
                Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
            ],
            idempotency_key=" ",
        )


def test_sqlite_ledger_idempotency_key_allows_same_entries_in_different_order(
    ledger,
) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    first = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )
    second = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )

    assert second == first
    assert len(ledger.transactions) == 1


def test_sqlite_ledger_idempotency_key_rejects_different_request_data(ledger) -> None:
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )

    with pytest.raises(LedgerError, match="different request data"):
        ledger.post_transaction(
            "User wallet top-up: 200.00",
            [
                Entry(bank.id, EntrySide.DEBIT, money("200.00")),
                Entry(wallet.id, EntrySide.CREDIT, money("200.00")),
            ],
            idempotency_key="payment-request-001",
        )

    assert len(ledger.transactions) == 1
    assert ledger.balance_for(bank.id) == Decimal("100.00")
    assert ledger.balance_for(wallet.id) == Decimal("100.00")


def test_sqlite_ledger_idempotency_conflict_survives_reopen(database_path) -> None:
    ledger = SQLiteLedger(database_path)
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="payment-request-001",
    )
    ledger.close()

    reopened = SQLiteLedger(database_path)
    try:
        with pytest.raises(LedgerError, match="different request data"):
            reopened.post_transaction(
                "User wallet top-up: 200.00",
                [
                    Entry(bank.id, EntrySide.DEBIT, money("200.00")),
                    Entry(wallet.id, EntrySide.CREDIT, money("200.00")),
                ],
                idempotency_key="payment-request-001",
            )

        assert len(reopened.transactions) == 1
        assert reopened.balance_for(bank.id) == Decimal("100.00")
        assert reopened.balance_for(wallet.id) == Decimal("100.00")
    finally:
        reopened.close()
