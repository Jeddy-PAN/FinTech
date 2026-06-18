import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from core_banking import AccountProductType, CoreBankingService
from core_banking_statement_export import (
    export_monthly_statement_csv,
    export_monthly_statement_html,
)
from sqlite_core_banking import SQLiteCoreBankingService


JAN_1 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
JAN_2 = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
JAN_3 = datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def output_directory() -> Path:
    directory = Path(__file__).with_name(".test-data") / f"statement-export-{uuid4()}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


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


def test_export_monthly_statement_writes_summary_and_postings_csv(
    output_directory: Path,
) -> None:
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
    service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Opening deposit",
        idempotency_key="dep-001",
    )
    service.withdraw(
        account.account_id,
        "25.00",
        posted_at=JAN_2,
        description="ATM withdrawal",
        idempotency_key="wd-001",
    )
    service.deposit(
        account.account_id,
        "40.00",
        posted_at=JAN_3,
        description="Payroll",
        idempotency_key="dep-002",
    )

    statement = service.monthly_statement(
        account.account_id,
        period_start=date(2026, 1, 2),
        period_end=date(2026, 1, 31),
    )
    result = export_monthly_statement_csv(
        statement,
        output_directory,
        file_prefix="acct-001-jan-2026",
    )

    summary_rows = _read_csv(result.summary_csv_path)
    posting_rows = _read_csv(result.postings_csv_path)

    assert summary_rows == [
        {
            "account_id": "acct-001",
            "period_start": "2026-01-02",
            "period_end": "2026-01-31",
            "opening_balance": "100.00",
            "closing_balance": "115.00",
            "total_credits": "40.00",
            "total_debits": "25.00",
            "interest_credited": "0.00",
            "posting_count": "2",
        }
    ]
    assert [row["posting_type"] for row in posting_rows] == ["withdrawal", "deposit"]
    assert [row["signed_amount"] for row in posting_rows] == ["-25.00", "40.00"]
    assert [row["description"] for row in posting_rows] == ["ATM withdrawal", "Payroll"]
    assert posting_rows[0]["idempotency_key"] == "wd-001"


def test_export_monthly_statement_uses_safe_default_file_names(
    output_directory: Path,
) -> None:
    statement = _build_empty_statement_for_account("acct:001")

    result = export_monthly_statement_csv(statement, output_directory)

    assert result.summary_csv_path.name == "statement_acct_001_2026-01-01_2026-01-31_summary.csv"
    assert result.postings_csv_path.name == "statement_acct_001_2026-01-01_2026-01-31_postings.csv"


def test_export_monthly_statement_rejects_blank_file_prefix(output_directory: Path) -> None:
    statement = _build_empty_statement_for_account("acct-001")

    with pytest.raises(ValueError, match="file_prefix cannot be blank"):
        export_monthly_statement_csv(statement, output_directory, file_prefix="   ")


def test_export_sqlite_monthly_statement_csv(database_path: Path, output_directory: Path) -> None:
    service = SQLiteCoreBankingService(database_path)
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    account = service.open_account(
        account_id="acct-sqlite",
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    service.deposit(account.account_id, "100.00", posted_at=JAN_1)
    service.withdraw(account.account_id, "25.00", posted_at=JAN_2)

    statement = service.monthly_statement(
        account.account_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    result = export_monthly_statement_csv(statement, output_directory)
    service.close()

    summary_rows = _read_csv(result.summary_csv_path)
    posting_rows = _read_csv(result.postings_csv_path)

    assert summary_rows[0]["account_id"] == "acct-sqlite"
    assert summary_rows[0]["closing_balance"] == "75.00"
    assert [row["signed_amount"] for row in posting_rows] == ["100.00", "-25.00"]


def test_export_monthly_statement_html_writes_readable_report(
    output_directory: Path,
) -> None:
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
    service.deposit(
        account.account_id,
        "100.00",
        posted_at=JAN_1,
        description="Opening <deposit>",
        idempotency_key="dep-001",
    )
    service.withdraw(
        account.account_id,
        "25.00",
        posted_at=JAN_2,
        description="ATM withdrawal",
        idempotency_key="wd-001",
    )

    statement = service.monthly_statement(
        account.account_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    result = export_monthly_statement_html(
        statement,
        output_directory,
        file_prefix="acct-001-jan-2026",
    )
    html = result.html_path.read_text(encoding="utf-8")

    assert result.html_path.name == "acct-001-jan-2026.html"
    assert "<h1>Account Statement</h1>" in html
    assert "Account acct-001" in html
    assert "Opening Balance" in html
    assert "Closing Balance" in html
    assert "75.00" in html
    assert "deposit" in html
    assert "withdrawal" in html
    assert "100.00" in html
    assert "-25.00" in html
    assert "Opening &lt;deposit&gt;" in html
    assert "Teaching report only" in html


def test_export_monthly_statement_html_records_audit_event(
    output_directory: Path,
) -> None:
    service = CoreBankingService()
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    service.open_account(
        account_id="acct-001",
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    statement = service.monthly_statement(
        "acct-001",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )

    result = export_monthly_statement_html(
        statement,
        output_directory,
        audit_recorder=service,
    )

    exported_events = [
        event for event in service.audit_events if event.event_type == "statement.html_exported"
    ]
    assert len(exported_events) == 1
    assert exported_events[0].payload["posting_count"] == "0"
    assert exported_events[0].payload["html_path"] == str(result.html_path)


def _build_empty_statement_for_account(account_id: str):
    service = CoreBankingService()
    service.create_product(
        product_id="basic-checking",
        name="Basic Checking",
        product_type=AccountProductType.CHECKING,
    )
    service.open_account(
        account_id=account_id,
        customer_id="cust-001",
        product_id="basic-checking",
        opened_at=JAN_1,
    )
    return service.monthly_statement(
        account_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
