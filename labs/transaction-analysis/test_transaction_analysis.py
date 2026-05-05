from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from transaction_analysis import (
    TransactionAnalysisError,
    TransactionRepository,
    categorize_transaction,
)


@pytest.fixture
def database_path() -> Path:
    directory = _test_data_directory()
    path = directory / f"{uuid4()}.db"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


@pytest.fixture
def csv_path() -> Path:
    path = _test_data_directory() / f"{uuid4()}.csv"
    path.write_text(
        "\n".join(
            [
                "transaction_id,posted_date,description,amount",
                "txn_001,2026-01-02,Payroll ACME Corp,3200.00",
                "txn_002,2026-01-03,City Grocery Market,-86.45",
                "txn_003,2026-01-05,Metro Transit,-32.00",
                "txn_004,2026-01-10,January Rent,-1450.00",
                "txn_005,2026-02-01,Payroll ACME Corp,3200.00",
                "txn_006,2026-02-03,Online Store,-124.99",
            ]
        ),
        encoding="utf-8",
    )
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


@pytest.fixture
def repository(database_path):
    instance = TransactionRepository(database_path)
    try:
        yield instance
    finally:
        instance.close()


def test_import_csv_persists_transactions(repository, csv_path) -> None:
    result = repository.import_csv(csv_path, source="bank_csv")

    assert result.total_rows == 6
    assert result.inserted_rows == 6
    assert result.skipped_rows == 0
    assert len(repository.transactions) == 6
    assert repository.transactions[0].id == "txn_001"
    assert repository.transactions[0].amount == Decimal("3200.00")
    assert repository.transactions[1].category == "groceries"


def test_reimport_csv_skips_duplicate_transaction_ids(repository, csv_path) -> None:
    first = repository.import_csv(csv_path)
    second = repository.import_csv(csv_path)

    assert first.inserted_rows == 6
    assert second.total_rows == 6
    assert second.inserted_rows == 0
    assert second.skipped_rows == 6
    assert len(repository.transactions) == 6


def test_monthly_cashflow_uses_income_expense_and_net(repository, csv_path) -> None:
    repository.import_csv(csv_path)

    summary = repository.monthly_cashflow()

    assert summary[0].month == "2026-01"
    assert summary[0].income == Decimal("3200.00")
    assert summary[0].expense == Decimal("1568.45")
    assert summary[0].net_cashflow == Decimal("1631.55")
    assert summary[1].month == "2026-02"
    assert summary[1].income == Decimal("3200.00")
    assert summary[1].expense == Decimal("124.99")
    assert summary[1].net_cashflow == Decimal("3075.01")


def test_category_summary_groups_signed_amounts(repository, csv_path) -> None:
    repository.import_csv(csv_path)

    summary = repository.category_summary()

    assert summary["income"] == Decimal("6400.00")
    assert summary["rent"] == Decimal("-1450.00")
    assert summary["shopping"] == Decimal("-124.99")


def test_pandas_monthly_cashflow_matches_sql_summary(repository, csv_path) -> None:
    repository.import_csv(csv_path)

    frame = repository.pandas_monthly_cashflow()

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == ["month", "income", "expense", "net_cashflow"]
    assert frame.to_dict("records") == [
        {
            "month": "2026-01",
            "income": Decimal("3200.00"),
            "expense": Decimal("1568.45"),
            "net_cashflow": Decimal("1631.55"),
        },
        {
            "month": "2026-02",
            "income": Decimal("3200.00"),
            "expense": Decimal("124.99"),
            "net_cashflow": Decimal("3075.01"),
        },
    ]


def test_category_monthly_expense_matrix_pivots_expenses(repository, csv_path) -> None:
    repository.import_csv(csv_path)

    matrix = repository.category_monthly_expense_matrix()

    assert list(matrix.columns) == [
        "month",
        "groceries",
        "rent",
        "shopping",
        "transport",
    ]
    assert matrix.to_dict("records") == [
        {
            "month": "2026-01",
            "groceries": Decimal("86.45"),
            "rent": Decimal("1450.00"),
            "shopping": Decimal("0.00"),
            "transport": Decimal("32.00"),
        },
        {
            "month": "2026-02",
            "groceries": Decimal("0.00"),
            "rent": Decimal("0.00"),
            "shopping": Decimal("124.99"),
            "transport": Decimal("0.00"),
        },
    ]


def test_compare_monthly_budget_calculates_remaining_amounts(
    repository,
    csv_path,
) -> None:
    repository.import_csv(csv_path)

    result = repository.compare_monthly_budget(
        "2026-01",
        {
            "groceries": "100.00",
            "rent": "1400.00",
            "transport": "50.00",
        },
    )

    assert result[0].category == "groceries"
    assert result[0].budget == Decimal("100.00")
    assert result[0].actual == Decimal("86.45")
    assert result[0].remaining == Decimal("13.55")
    assert result[0].is_over_budget is False
    assert result[1].category == "rent"
    assert result[1].remaining == Decimal("-50.00")
    assert result[1].is_over_budget is True


def test_compare_monthly_budget_rejects_negative_budget(repository) -> None:
    with pytest.raises(TransactionAnalysisError, match="Budget amount cannot be negative"):
        repository.compare_monthly_budget("2026-01", {"groceries": "-1.00"})


def test_invalid_amount_is_rejected(repository) -> None:
    path = _test_data_directory() / f"{uuid4()}.csv"
    path.write_text(
        "\n".join(
            [
                "transaction_id,posted_date,description,amount",
                "txn_001,2026-01-02,Payroll ACME Corp,not-money",
            ]
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(TransactionAnalysisError, match="Invalid money amount"):
            repository.import_csv(path)
    finally:
        if path.exists():
            path.unlink()


def test_missing_required_csv_column_is_rejected(repository) -> None:
    path = _test_data_directory() / f"{uuid4()}.csv"
    path.write_text(
        "\n".join(
            [
                "transaction_id,posted_date,amount",
                "txn_001,2026-01-02,3200.00",
            ]
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(TransactionAnalysisError, match="CSV missing required columns"):
            repository.import_csv(path)
    finally:
        if path.exists():
            path.unlink()


def test_categorize_transaction_uses_keyword_rules() -> None:
    assert categorize_transaction("Payroll ACME Corp") == "income"
    assert categorize_transaction("Metro Transit") == "transport"
    assert categorize_transaction("Unknown Merchant") == "other"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory
