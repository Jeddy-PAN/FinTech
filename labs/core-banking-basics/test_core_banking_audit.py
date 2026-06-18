from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from core_banking import AccountProductType, AccountStatus, CoreBankingService
from core_banking_statement_export import export_monthly_statement_csv
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


def test_memory_core_banking_records_account_posting_and_hold_audit_events() -> None:
    service = CoreBankingService()
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = service.open_account(
        account_id="acct-001",
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    deposit = service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_2,
        idempotency_key="dep-001",
    )
    service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_3,
        idempotency_key="dep-001",
    )
    service.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_3)
    service.capture_hold("hold-001", posted_at=JAN_4, idempotency_key="capture-001")
    service.set_account_status(account.account_id, AccountStatus.FROZEN)

    assert [event.event_type for event in service.audit_events] == [
        "account.opened",
        "posting.created",
        "hold.placed",
        "posting.created",
        "hold.captured",
        "account.status_changed",
    ]
    assert service.audit_events[1].payload["posting_id"] == deposit.posting_id
    assert service.audit_events[1].payload["amount"] == "100.00"
    assert service.audit_events[1].payload["idempotency_key"] == "dep-001"
    assert service.audit_events[-1].payload == {
        "previous_status": "active",
        "new_status": "frozen",
    }


def test_interest_accrual_audit_event_is_idempotent() -> None:
    service = CoreBankingService()
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

    service.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))
    service.accrue_daily_interest(account.account_id, accrual_date=date(2026, 1, 2))

    interest_events = [
        event for event in service.audit_events if event.event_type == "interest.accrued"
    ]
    assert len(interest_events) == 1
    assert interest_events[0].payload["amount"] == "0.20"


def test_sqlite_core_banking_persists_audit_events(database_path: Path) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = service.open_account(
        account_id="acct-001",
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    service.deposit(account.account_id, "100.00", posted_at=JAN_2, idempotency_key="dep-001")
    service.place_hold(account.account_id, "30.00", hold_id="hold-001", created_at=JAN_3)
    service.release_hold("hold-001", released_at=JAN_4)
    service.close()

    reopened = SQLiteCoreBankingService(database_path)
    try:
        assert [event.event_type for event in reopened.audit_events] == [
            "account.opened",
            "posting.created",
            "hold.placed",
            "hold.released",
        ]
        assert reopened.audit_events[0].payload["customer_id"] == "cust-001"
        assert reopened.audit_events[1].payload["posting_type"] == "deposit"
        assert reopened.audit_events[2].payload["hold_id"] == "hold-001"
    finally:
        reopened.close()


def test_statement_export_can_record_audit_event(database_path: Path) -> None:
    output_directory = Path(__file__).with_name(".test-data") / f"audit-export-{uuid4()}"
    output_directory.mkdir(parents=True, exist_ok=True)
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = service.open_account(
        account_id="acct-001",
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    service.deposit(account.account_id, "100.00", posted_at=JAN_2)
    statement = service.monthly_statement(
        account.account_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )

    result = export_monthly_statement_csv(
        statement,
        output_directory,
        file_prefix="acct-001-jan",
        audit_recorder=service,
    )

    exported_events = [
        event for event in service.audit_events if event.event_type == "statement.exported"
    ]
    assert len(exported_events) == 1
    assert exported_events[0].source == "core_banking_statement_export"
    assert exported_events[0].payload["posting_count"] == "1"
    assert exported_events[0].payload["summary_csv_path"] == str(result.summary_csv_path)
    assert exported_events[0].payload["closing_balance"] == "100.00"
    service.close()
