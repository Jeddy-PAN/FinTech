from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from core_banking import (
    AccountProductType,
    AccountStatus,
    CoreBankingError,
    CoreBankingService,
    HoldStatus,
    PostingDirection,
    PostingType,
)


JAN_1 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
JAN_2 = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
JAN_3 = datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def banking() -> CoreBankingService:
    service = CoreBankingService()
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    service.create_product(
        product_id="savings-2pct",
        name="Savings 2 Percent",
        product_type=AccountProductType.SAVINGS,
        annual_interest_rate="0.02",
    )
    return service


def open_checking(service: CoreBankingService, account_id: str = "acct-001"):
    return service.open_account(
        account_id=account_id,
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )


def test_product_and_account_creation(banking: CoreBankingService) -> None:
    account = open_checking(banking)

    assert account.account_id == "acct-001"
    assert account.currency == "USD"
    assert account.status == AccountStatus.ACTIVE
    assert len(banking.products) == 2


def test_deposit_updates_ledger_and_available_balance(banking: CoreBankingService) -> None:
    account = open_checking(banking)

    posting = banking.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        idempotency_key="deposit-001",
    )
    balance = banking.balance(account.account_id)

    assert posting.direction == PostingDirection.CREDIT
    assert posting.posting_type == PostingType.DEPOSIT
    assert balance.ledger_balance == Decimal("100.00")
    assert balance.active_hold_amount == Decimal("0.00")
    assert balance.available_balance == Decimal("100.00")


def test_hold_reduces_available_balance_without_changing_ledger(
    banking: CoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)

    hold = banking.place_hold(
        account.account_id,
        "30.00",
        hold_id="hold-001",
        created_at=JAN_2,
        reason="Card authorization",
    )
    balance = banking.balance(account.account_id)

    assert hold.status == HoldStatus.ACTIVE
    assert balance.ledger_balance == Decimal("100.00")
    assert balance.active_hold_amount == Decimal("30.00")
    assert balance.available_balance == Decimal("70.00")


def test_release_hold_restores_available_balance(banking: CoreBankingService) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_2)

    released = banking.release_hold("hold-001", released_at=JAN_3)
    balance = banking.balance(account.account_id)

    assert released.status == HoldStatus.RELEASED
    assert released.released_at == JAN_3
    assert balance.ledger_balance == Decimal("100.00")
    assert balance.active_hold_amount == Decimal("0.00")
    assert balance.available_balance == Decimal("100.00")


def test_capture_hold_debits_ledger_and_removes_active_hold(
    banking: CoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_2)

    captured, posting = banking.capture_hold(
        "hold-001",
        posted_at=JAN_3,
        idempotency_key="capture-001",
    )
    balance = banking.balance(account.account_id)

    assert captured.status == HoldStatus.CAPTURED
    assert posting.direction == PostingDirection.DEBIT
    assert posting.posting_type == PostingType.HOLD_CAPTURE
    assert balance.ledger_balance == Decimal("70.00")
    assert balance.active_hold_amount == Decimal("0.00")
    assert balance.available_balance == Decimal("70.00")


def test_withdraw_checks_available_balance(banking: CoreBankingService) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "80.00", hold_id="hold-001", created_at=JAN_2)

    with pytest.raises(CoreBankingError, match="Insufficient available balance"):
        banking.withdraw(account.account_id, "30.00", posted_at=JAN_3)

    posting = banking.withdraw(account.account_id, "20.00", posted_at=JAN_3)

    assert posting.posting_type == PostingType.WITHDRAWAL
    assert banking.balance(account.account_id).available_balance == Decimal("0.00")


def test_frozen_account_blocks_debit_operations(banking: CoreBankingService) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.set_account_status(account.account_id, AccountStatus.FROZEN)

    with pytest.raises(CoreBankingError, match="Account is frozen"):
        banking.withdraw(account.account_id, "10.00", posted_at=JAN_2)

    with pytest.raises(CoreBankingError, match="Account is frozen"):
        banking.place_hold(account.account_id, "10.00", created_at=JAN_2)


def test_closed_account_blocks_deposit_and_withdraw(banking: CoreBankingService) -> None:
    account = open_checking(banking)
    banking.set_account_status(account.account_id, AccountStatus.CLOSED)

    with pytest.raises(CoreBankingError, match="Account is closed"):
        banking.deposit(account.account_id, "10.00", posted_at=JAN_2)

    with pytest.raises(CoreBankingError, match="Account is closed"):
        banking.withdraw(account.account_id, "10.00", posted_at=JAN_2)


def test_interest_accrual_posts_credit_once_per_account_date(
    banking: CoreBankingService,
) -> None:
    account = banking.open_account(
        account_id="acct-savings",
        customer_id="cust-001",
        product_id="savings-2pct",
        opened_at=JAN_1,
    )
    banking.deposit(account.account_id, "3650.00", posted_at=JAN_1)

    first = banking.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))
    second = banking.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))

    assert first is not None
    assert first is second
    assert first.posting_type == PostingType.INTEREST
    assert first.amount == Decimal("0.20")
    assert banking.balance(account.account_id).ledger_balance == Decimal("3650.20")


def test_monthly_statement_summarizes_period_activity(
    banking: CoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.withdraw(account.account_id, "25.00", posted_at=JAN_2)
    banking.deposit(account.account_id, "40.00", posted_at=JAN_3)

    statement = banking.monthly_statement(
        account.account_id,
        period_start=date(2026, 1, 2),
        period_end=date(2026, 1, 31),
    )

    assert statement.opening_balance == Decimal("100.00")
    assert statement.closing_balance == Decimal("115.00")
    assert statement.total_credits == Decimal("40.00")
    assert statement.total_debits == Decimal("25.00")
    assert statement.interest_credited == Decimal("0.00")
    assert [posting.amount for posting in statement.postings] == [
        Decimal("25.00"),
        Decimal("40.00"),
    ]


def test_idempotency_replay_returns_same_posting(banking: CoreBankingService) -> None:
    account = open_checking(banking)

    first = banking.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Payroll",
        idempotency_key="deposit-001",
    )
    replay = banking.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_2,
        description="Payroll",
        idempotency_key="deposit-001",
    )

    assert replay is first
    assert len(banking.postings) == 1


def test_idempotency_key_reuse_with_different_request_fails(
    banking: CoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Payroll",
        idempotency_key="deposit-001",
    )

    with pytest.raises(CoreBankingError, match="Idempotency key was reused"):
        banking.deposit(
            account.account_id,
            "101.00",
            posted_at=JAN_2,
            description="Payroll",
            idempotency_key="deposit-001",
        )
