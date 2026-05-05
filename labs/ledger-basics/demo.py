import sys

from ledger import AccountType, Entry, EntrySide, Ledger, money


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ledger = Ledger()

    platform_bank = ledger.create_account(
        "Platform Bank Account",
        AccountType.ASSET,
        account_id="platform_bank",
    )
    user_wallet = ledger.create_account(
        "User Wallet Balance",
        AccountType.LIABILITY,
        account_id="user_wallet",
    )
    fee_income = ledger.create_account(
        "Fee Income",
        AccountType.INCOME,
        account_id="fee_income",
    )

    ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(platform_bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(user_wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="demo-top-up-001",
    )

    ledger.post_transaction(
        "Platform fee: 2.00",
        [
            Entry(user_wallet.id, EntrySide.DEBIT, money("2.00")),
            Entry(fee_income.id, EntrySide.CREDIT, money("2.00")),
        ],
        idempotency_key="demo-fee-001",
    )

    retry = ledger.post_transaction(
        "User wallet top-up: 100.00",
        [
            Entry(platform_bank.id, EntrySide.DEBIT, money("100.00")),
            Entry(user_wallet.id, EntrySide.CREDIT, money("100.00")),
        ],
        idempotency_key="demo-top-up-001",
    )

    print("Account Balances")
    for account in ledger.accounts:
        print(f"- {account.name}: {ledger.balance_for(account.id)}")

    trial_balance = ledger.trial_balance()
    print("\nTrial Balance")
    print(f"- Total debits: {trial_balance[EntrySide.DEBIT]}")
    print(f"- Total credits: {trial_balance[EntrySide.CREDIT]}")
    print(f"\nIdempotent retry returned transaction: {retry.id}")


if __name__ == "__main__":
    main()
