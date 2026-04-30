from decimal import Decimal

import pytest

from ledger import AccountType, Entry, EntrySide, Ledger, LedgerError, money


def test_recharge_records_asset_and_liability() -> None:
    ledger = Ledger()
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")
    wallet = ledger.create_account("User Wallet Balance", AccountType.LIABILITY, account_id="wallet")

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
    )

    assert ledger.balance_for(bank.id) == Decimal("100.00")
    assert ledger.balance_for(wallet.id) == Decimal("100.00")


def test_unbalanced_transaction_is_rejected() -> None:
    ledger = Ledger()
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


def test_trial_balance_totals_match() -> None:
    ledger = Ledger()
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


def test_unknown_account_is_rejected() -> None:
    ledger = Ledger()
    bank = ledger.create_account("Platform Bank Account", AccountType.ASSET, account_id="bank")

    with pytest.raises(LedgerError, match="Unknown account"):
        ledger.post_transaction(
            "Invalid transaction",
            [
                Entry(bank.id, EntrySide.DEBIT, money("10.00")),
                Entry("missing", EntrySide.CREDIT, money("10.00")),
            ],
        )
