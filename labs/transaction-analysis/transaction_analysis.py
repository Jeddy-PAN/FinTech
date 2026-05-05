from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd


CENT = Decimal("0.01")


class TransactionAnalysisError(ValueError):
    """Base error for invalid transaction analysis operations."""


@dataclass(frozen=True)
class BankTransaction:
    id: str
    posted_date: date
    description: str
    amount: Decimal
    category: str
    source: str


@dataclass(frozen=True)
class ImportResult:
    total_rows: int
    inserted_rows: int
    skipped_rows: int


@dataclass(frozen=True)
class MonthlyCashflow:
    month: str
    income: Decimal
    expense: Decimal
    net_cashflow: Decimal


@dataclass(frozen=True)
class BudgetVariance:
    month: str
    category: str
    budget: Decimal
    actual: Decimal
    remaining: Decimal
    is_over_budget: bool


@dataclass(frozen=True)
class CategoryRule:
    category: str
    keyword: str


class CategoryRuleSet:
    def __init__(self, rules: list[CategoryRule]) -> None:
        if not rules:
            raise TransactionAnalysisError("At least one category rule is required")
        self._rules = tuple(rules)

    @classmethod
    def default(cls) -> CategoryRuleSet:
        return cls(
            [
                CategoryRule("income", "payroll"),
                CategoryRule("income", "salary"),
                CategoryRule("income", "interest"),
                CategoryRule("income", "dividend"),
                CategoryRule("rent", "rent"),
                CategoryRule("rent", "landlord"),
                CategoryRule("groceries", "grocery"),
                CategoryRule("groceries", "market"),
                CategoryRule("groceries", "supermarket"),
                CategoryRule("transport", "metro"),
                CategoryRule("transport", "transit"),
                CategoryRule("transport", "taxi"),
                CategoryRule("transport", "ride share"),
                CategoryRule("transport", "gas"),
                CategoryRule("dining", "restaurant"),
                CategoryRule("dining", "coffee"),
                CategoryRule("dining", "cafe"),
                CategoryRule("utilities", "electric"),
                CategoryRule("utilities", "utility"),
                CategoryRule("utilities", "water"),
                CategoryRule("utilities", "internet"),
                CategoryRule("shopping", "online store"),
                CategoryRule("shopping", "shopping"),
                CategoryRule("shopping", "shop"),
                CategoryRule("transfer", "transfer"),
            ]
        )

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> CategoryRuleSet:
        path = Path(csv_path)
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            required_columns = {"category", "keyword"}
            if reader.fieldnames is None:
                raise TransactionAnalysisError("Category rules CSV header is required")

            missing_columns = required_columns - set(reader.fieldnames)
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise TransactionAnalysisError(
                    f"Category rules CSV missing required columns: {missing}"
                )

            rules = []
            for row in reader:
                category = row["category"].strip()
                keyword = row["keyword"].strip()
                if not category:
                    raise TransactionAnalysisError("Category rule category is required")
                if not keyword:
                    raise TransactionAnalysisError("Category rule keyword is required")
                rules.append(CategoryRule(category, keyword))

        return cls(rules)

    @property
    def rules(self) -> tuple[CategoryRule, ...]:
        return self._rules

    def categorize(self, description: str) -> str:
        normalized = description.casefold()
        for rule in self._rules:
            if rule.keyword.casefold() in normalized:
                return rule.category
        return "other"


class TransactionRepository:
    def __init__(
        self,
        database_path: str | Path,
        *,
        category_rules: CategoryRuleSet | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.category_rules = category_rules or CategoryRuleSet.default()
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def transactions(self) -> tuple[BankTransaction, ...]:
        rows = self._connection.execute(
            """
            SELECT id, posted_date, description, amount_cents, category, source
            FROM bank_transactions
            ORDER BY posted_date, id
            """
        ).fetchall()
        return tuple(self._transaction_from_row(row) for row in rows)

    def import_csv(self, csv_path: str | Path, *, source: str = "csv") -> ImportResult:
        normalized_source = source.strip()
        if not normalized_source:
            raise TransactionAnalysisError("Source is required")

        rows = self._read_csv_rows(csv_path)
        inserted = 0
        with self._connection:
            for row in rows:
                transaction = self._parse_csv_row(row, normalized_source)
                cursor = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO bank_transactions (
                        id,
                        posted_date,
                        description,
                        amount_cents,
                        category,
                        source,
                        imported_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transaction.id,
                        transaction.posted_date.isoformat(),
                        transaction.description,
                        _money_to_cents(transaction.amount),
                        transaction.category,
                        transaction.source,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                inserted += cursor.rowcount

        return ImportResult(
            total_rows=len(rows),
            inserted_rows=inserted,
            skipped_rows=len(rows) - inserted,
        )

    def monthly_cashflow(self) -> tuple[MonthlyCashflow, ...]:
        rows = self._connection.execute(
            """
            SELECT
                strftime('%Y-%m', posted_date) AS month,
                SUM(CASE WHEN amount_cents > 0 THEN amount_cents ELSE 0 END) AS income_cents,
                SUM(CASE WHEN amount_cents < 0 THEN -amount_cents ELSE 0 END) AS expense_cents,
                SUM(amount_cents) AS net_cents
            FROM bank_transactions
            GROUP BY month
            ORDER BY month
            """
        ).fetchall()

        return tuple(
            MonthlyCashflow(
                month=row["month"],
                income=_cents_to_money(row["income_cents"]),
                expense=_cents_to_money(row["expense_cents"]),
                net_cashflow=_cents_to_money(row["net_cents"]),
            )
            for row in rows
        )

    def category_summary(self) -> dict[str, Decimal]:
        rows = self._connection.execute(
            """
            SELECT category, SUM(amount_cents) AS net_cents
            FROM bank_transactions
            GROUP BY category
            ORDER BY category
            """
        ).fetchall()
        return {row["category"]: _cents_to_money(row["net_cents"]) for row in rows}

    def pandas_monthly_cashflow(self) -> pd.DataFrame:
        frame = pd.read_sql_query(
            """
            SELECT posted_date, amount_cents
            FROM bank_transactions
            ORDER BY posted_date, id
            """,
            self._connection,
            parse_dates=["posted_date"],
        )
        if frame.empty:
            return pd.DataFrame(
                columns=["month", "income", "expense", "net_cashflow"]
            )

        frame["month"] = frame["posted_date"].dt.to_period("M").astype(str)
        frame["income_cents"] = frame["amount_cents"].where(
            frame["amount_cents"] > 0,
            0,
        )
        frame["expense_cents"] = (-frame["amount_cents"]).where(
            frame["amount_cents"] < 0,
            0,
        )

        grouped = (
            frame.groupby("month", as_index=False)[
                ["income_cents", "expense_cents", "amount_cents"]
            ]
            .sum()
            .rename(columns={"amount_cents": "net_cents"})
        )
        grouped["income"] = grouped["income_cents"].map(_cents_to_money)
        grouped["expense"] = grouped["expense_cents"].map(_cents_to_money)
        grouped["net_cashflow"] = grouped["net_cents"].map(_cents_to_money)
        return grouped[["month", "income", "expense", "net_cashflow"]]

    def category_monthly_expense_matrix(self) -> pd.DataFrame:
        frame = pd.read_sql_query(
            """
            SELECT
                strftime('%Y-%m', posted_date) AS month,
                category,
                -amount_cents AS expense_cents
            FROM bank_transactions
            WHERE amount_cents < 0
            ORDER BY month, category
            """,
            self._connection,
        )
        if frame.empty:
            return pd.DataFrame(columns=["month"])

        matrix = frame.pivot_table(
            index="month",
            columns="category",
            values="expense_cents",
            aggfunc="sum",
            fill_value=0,
        )
        matrix = matrix.sort_index().sort_index(axis=1).reset_index()

        for column in matrix.columns:
            if column != "month":
                matrix[column] = matrix[column].map(_cents_to_money)

        return matrix

    def compare_monthly_budget(
        self,
        month: str,
        budget_by_category: dict[str, str | int | Decimal],
    ) -> tuple[BudgetVariance, ...]:
        normalized_month = month.strip()
        if not normalized_month:
            raise TransactionAnalysisError("Month is required")

        budgets = {
            category.strip(): _parse_budget_money(amount)
            for category, amount in budget_by_category.items()
            if category.strip()
        }
        if not budgets:
            raise TransactionAnalysisError("Budget is required")

        rows = self._connection.execute(
            """
            SELECT category, SUM(-amount_cents) AS expense_cents
            FROM bank_transactions
            WHERE amount_cents < 0
              AND strftime('%Y-%m', posted_date) = ?
            GROUP BY category
            """,
            (normalized_month,),
        ).fetchall()
        actuals = {
            row["category"]: _cents_to_money(row["expense_cents"])
            for row in rows
        }

        categories = sorted(set(budgets) | set(actuals))
        return tuple(
            BudgetVariance(
                month=normalized_month,
                category=category,
                budget=budgets.get(category, Decimal("0.00")),
                actual=actuals.get(category, Decimal("0.00")),
                remaining=(
                    budgets.get(category, Decimal("0.00"))
                    - actuals.get(category, Decimal("0.00"))
                ).quantize(CENT),
                is_over_budget=actuals.get(category, Decimal("0.00"))
                > budgets.get(category, Decimal("0.00")),
            )
            for category in categories
        )

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS bank_transactions (
                    id TEXT PRIMARY KEY,
                    posted_date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK (amount_cents != 0),
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_bank_transactions_posted_date
                ON bank_transactions (posted_date);

                CREATE INDEX IF NOT EXISTS idx_bank_transactions_category
                ON bank_transactions (category);
                """
            )

    def _read_csv_rows(self, csv_path: str | Path) -> list[dict[str, str]]:
        path = Path(csv_path)
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            required_columns = {
                "transaction_id",
                "posted_date",
                "description",
                "amount",
            }
            if reader.fieldnames is None:
                raise TransactionAnalysisError("CSV header is required")

            missing_columns = required_columns - set(reader.fieldnames)
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise TransactionAnalysisError(f"CSV missing required columns: {missing}")

            return list(reader)

    def _parse_csv_row(self, row: dict[str, str], source: str) -> BankTransaction:
        transaction_id = row["transaction_id"].strip()
        if not transaction_id:
            raise TransactionAnalysisError("Transaction id is required")

        description = row["description"].strip()
        if not description:
            raise TransactionAnalysisError("Description is required")

        return BankTransaction(
            id=transaction_id,
            posted_date=_parse_date(row["posted_date"]),
            description=description,
            amount=_parse_signed_money(row["amount"]),
            category=self.category_rules.categorize(description),
            source=source,
        )

    def _transaction_from_row(self, row: sqlite3.Row) -> BankTransaction:
        return BankTransaction(
            id=row["id"],
            posted_date=date.fromisoformat(row["posted_date"]),
            description=row["description"],
            amount=_cents_to_money(row["amount_cents"]),
            category=row["category"],
            source=row["source"],
        )


def categorize_transaction(description: str) -> str:
    return CategoryRuleSet.default().categorize(description)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise TransactionAnalysisError(f"Invalid posted date: {value!r}") from exc


def _parse_signed_money(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip()).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise TransactionAnalysisError(f"Invalid money amount: {value!r}") from exc

    if amount == Decimal("0.00"):
        raise TransactionAnalysisError("Transaction amount cannot be zero")

    return amount


def _parse_budget_money(value: str | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise TransactionAnalysisError(f"Invalid budget amount: {value!r}") from exc

    if amount < Decimal("0.00"):
        raise TransactionAnalysisError("Budget amount cannot be negative")

    return amount


def _money_to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def _cents_to_money(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal(100)).quantize(CENT)
