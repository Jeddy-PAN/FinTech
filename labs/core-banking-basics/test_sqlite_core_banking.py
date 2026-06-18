from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from core_banking import (
    AccountProductType,
    AccountStatus,
    CoreBankingError,
    HoldStatus,
    PostingType,
)
from sqlite_core_banking import SQLiteCoreBankingService


JAN_1 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
JAN_2 = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
JAN_3 = datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc)
JAN_4 = datetime(2026, 1, 4, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def database_path() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid4()}.db"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


@pytest.fixture()
def banking(database_path: Path):
    service = SQLiteCoreBankingService(database_path)
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
    try:
        yield service
    finally:
        service.close()


def open_checking(service: SQLiteCoreBankingService, account_id: str = "acct-001"):
    return service.open_account(
        account_id=account_id,
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )


def test_sqlite_core_banking_persists_account_postings_and_holds(
    database_path: Path,
) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = open_checking(service)
    service.deposit(account.account_id, "100.00", posted_at=JAN_1, idempotency_key="dep-001")
    service.place_hold(
        account.account_id,
        "30.00",
        hold_id="hold-001",
        created_at=JAN_2,
    )
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        balance = reopened.balance(account.account_id)

        assert len(reopened.products) == 1
        assert len(reopened.accounts) == 1
        assert len(reopened.postings) == 1
        assert len(reopened.holds) == 1
        assert balance.ledger_balance == Decimal("100.00")
        assert balance.active_hold_amount == Decimal("30.00")
        assert balance.available_balance == Decimal("70.00")
    finally:
        reopened.close()


def test_sqlite_hold_capture_persists_posting_and_hold_status(
    banking: SQLiteCoreBankingService,
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
    assert posting.posting_type == PostingType.HOLD_CAPTURE
    assert balance.ledger_balance == Decimal("70.00")
    assert balance.active_hold_amount == Decimal("0.00")
    assert balance.available_balance == Decimal("70.00")
    assert [hold.status for hold in banking.holds] == [HoldStatus.CAPTURED]


def test_sqlite_duplicate_capture_does_not_create_second_posting(
    banking: SQLiteCoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_2)

    banking.capture_hold("hold-001", posted_at=JAN_3, idempotency_key="capture-001")

    with pytest.raises(CoreBankingError, match="Hold is not active"):
        banking.capture_hold("hold-001", posted_at=JAN_4, idempotency_key="capture-002")

    assert [posting.posting_type for posting in banking.postings] == [
        PostingType.DEPOSIT,
        PostingType.HOLD_CAPTURE,
    ]
    assert banking.balance(account.account_id).ledger_balance == Decimal("70.00")


def test_sqlite_two_connections_cannot_both_capture_same_hold(database_path: Path) -> None:
    setup = SQLiteCoreBankingService(database_path)
    setup.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = open_checking(setup)
    setup.deposit(account.account_id, "100.00", posted_at=JAN_1)
    setup.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_2)
    setup.close()

    first = SQLiteCoreBankingService(database_path)
    second = SQLiteCoreBankingService(database_path)
    try:
        first.capture_hold("hold-001", posted_at=JAN_3, idempotency_key="capture-001")

        with pytest.raises(CoreBankingError, match="Hold is not active"):
            second.capture_hold("hold-001", posted_at=JAN_4, idempotency_key="capture-002")

        assert len(second.postings) == 2
        assert second.holds[0].status == HoldStatus.CAPTURED
        assert second.balance(account.account_id).ledger_balance == Decimal("70.00")
    finally:
        first.close()
        second.close()


def test_sqlite_capture_after_release_is_rejected_without_posting(
    banking: SQLiteCoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_2)

    banking.release_hold("hold-001", released_at=JAN_3)

    with pytest.raises(CoreBankingError, match="Hold is not active"):
        banking.capture_hold("hold-001", posted_at=JAN_4, idempotency_key="capture-001")

    assert [posting.posting_type for posting in banking.postings] == [PostingType.DEPOSIT]
    assert banking.holds[0].status == HoldStatus.RELEASED
    assert banking.balance(account.account_id).ledger_balance == Decimal("100.00")


def test_sqlite_withdraw_and_hold_use_available_balance(
    banking: SQLiteCoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)
    banking.place_hold(account.account_id, "80.00", hold_id="hold-001", created_at=JAN_2)

    with pytest.raises(CoreBankingError, match="Insufficient available balance"):
        banking.withdraw(account.account_id, "30.00", posted_at=JAN_3)

    banking.release_hold("hold-001", released_at=JAN_3)
    posting = banking.withdraw(account.account_id, "30.00", posted_at=JAN_4)

    assert posting.posting_type == PostingType.WITHDRAWAL
    assert banking.balance(account.account_id).available_balance == Decimal("70.00")


def test_sqlite_idempotency_key_survives_reopen(database_path: Path) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = open_checking(service)
    first = service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Payroll",
        idempotency_key="deposit-001",
    )
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        replay = reopened.deposit(
            account.account_id,
            "100.00",
            posted_at=JAN_2,
            description="Payroll",
            idempotency_key="deposit-001",
        )

        assert replay == first
        assert len(reopened.postings) == 1
        assert reopened.balance(account.account_id).ledger_balance == Decimal("100.00")
    finally:
        reopened.close()


def test_sqlite_idempotency_conflict_survives_reopen(database_path: Path) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = open_checking(service)
    service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Payroll",
        idempotency_key="deposit-001",
    )
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        with pytest.raises(CoreBankingError, match="Idempotency key was reused"):
            reopened.deposit(
                account.account_id,
                "101.00",
                posted_at=JAN_2,
                description="Payroll",
                idempotency_key="deposit-001",
            )

        assert len(reopened.postings) == 1
        assert reopened.balance(account.account_id).ledger_balance == Decimal("100.00")
    finally:
        reopened.close()


def test_sqlite_interest_accrual_is_persisted_and_idempotent(
    database_path: Path,
) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="savings-2pct",
        name="Savings 2 Percent",
        product_type=AccountProductType.SAVINGS,
        annual_interest_rate="0.02",
    )
    account = service.open_account(
        account_id="acct-savings",
        customer_id="cust-001",
        product_id="savings-2pct",
        opened_at=JAN_1,
    )
    service.deposit(account.account_id, "3650.00", posted_at=JAN_1)

    first = service.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        second = reopened.accrue_daily_interest(
            account.account_id,
            accrual_date=date(2026, 1, 2),
        )

        assert first is not None
        assert second == first
        assert second.amount == Decimal("0.20")
        assert reopened.balance(account.account_id).ledger_balance == Decimal("3650.20")
    finally:
        reopened.close()


def test_sqlite_monthly_statement_reads_period_from_database(
    banking: SQLiteCoreBankingService,
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
    assert [posting.amount for posting in statement.postings] == [
        Decimal("25.00"),
        Decimal("40.00"),
    ]


def test_sqlite_account_status_rules_match_memory_version(
    banking: SQLiteCoreBankingService,
) -> None:
    account = open_checking(banking)
    banking.deposit(account.account_id, "100.00", posted_at=JAN_1)

    banking.set_account_status(account.account_id, AccountStatus.FROZEN)
    with pytest.raises(CoreBankingError, match="Account is frozen"):
        banking.place_hold(account.account_id, "10.00", created_at=JAN_2)

    banking.set_account_status(account.account_id, AccountStatus.CLOSED)
    with pytest.raises(CoreBankingError, match="Account is closed"):
        banking.deposit(account.account_id, "10.00", posted_at=JAN_3)


def test_sqlite_account_version_increments_on_status_change(
    banking: SQLiteCoreBankingService,
) -> None:
    account = open_checking(banking)

    opened_snapshot = banking.account_version_snapshot(account.account_id)
    banking.set_account_status(
        account.account_id,
        AccountStatus.FROZEN,
        expected_version=opened_snapshot.version,
    )
    frozen_snapshot = banking.account_version_snapshot(account.account_id)

    assert opened_snapshot.version == 0
    assert frozen_snapshot.status == AccountStatus.FROZEN
    assert frozen_snapshot.version == 1
    status_events = [
        event for event in banking.audit_events
        if event.event_type == "account.status_changed"
    ]
    assert status_events[-1].payload["previous_version"] == "0"
    assert status_events[-1].payload["new_version"] == "1"


def test_sqlite_two_connections_cannot_update_account_with_same_old_version(
    database_path: Path,
) -> None:
    setup = SQLiteCoreBankingService(database_path)
    setup.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = open_checking(setup)
    setup.close()

    first = SQLiteCoreBankingService(database_path)
    second = SQLiteCoreBankingService(database_path)
    try:
        first_snapshot = first.account_version_snapshot(account.account_id)
        second_snapshot = second.account_version_snapshot(account.account_id)

        first.set_account_status(
            account.account_id,
            AccountStatus.FROZEN,
            expected_version=first_snapshot.version,
        )

        with pytest.raises(CoreBankingError, match="Account version conflict"):
            second.set_account_status(
                account.account_id,
                AccountStatus.CLOSED,
                expected_version=second_snapshot.version,
            )

        latest = second.account_version_snapshot(account.account_id)
        assert latest.status == AccountStatus.FROZEN
        assert latest.version == 1
        assert [
            event.event_type for event in second.audit_events
            if event.event_type == "account.status_changed"
        ] == ["account.status_changed"]
    finally:
        first.close()
        second.close()


def test_sqlite_preserves_small_interest_rate_precision(database_path: Path) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="micro-rate",
        name="Micro Rate",
        product_type=AccountProductType.SAVINGS,
        annual_interest_rate="0.000001",
    )
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        assert reopened.products[0].annual_interest_rate == Decimal("0.000001")
    finally:
        reopened.close()
