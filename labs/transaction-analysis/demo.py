import sys
from pathlib import Path

from reporting import generate_analysis_report
from transaction_analysis import CategoryRuleSet, TransactionRepository


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lab_dir = Path(__file__).resolve().parent
    database_path = lab_dir / "transaction_analysis_demo.db"
    csv_path = lab_dir / "sample_transactions.csv"
    category_rules_path = lab_dir / "category_rules.csv"

    if database_path.exists():
        database_path.unlink()

    repository = TransactionRepository(
        database_path,
        category_rules=CategoryRuleSet.from_csv(category_rules_path),
    )
    try:
        result = repository.import_csv(csv_path, source="sample_statement")

        print("Import Result")
        print(f"- Total rows: {result.total_rows}")
        print(f"- Inserted rows: {result.inserted_rows}")
        print(f"- Skipped rows: {result.skipped_rows}")

        print("\nMonthly Cashflow")
        for item in repository.monthly_cashflow():
            print(
                f"- {item.month}: "
                f"income={item.income}, "
                f"expense={item.expense}, "
                f"net={item.net_cashflow}"
            )

        print("\nCategory Summary")
        for category, amount in repository.category_summary().items():
            print(f"- {category}: {amount}")

        print("\nPandas Monthly Cashflow")
        print(repository.pandas_monthly_cashflow().to_string(index=False))

        print("\nMonthly Expense Matrix")
        print(repository.category_monthly_expense_matrix().to_string(index=False))

        print("\nBudget Variance: 2026-01")
        budget = {
            "dining": "80.00",
            "groceries": "200.00",
            "rent": "1450.00",
            "transport": "60.00",
            "utilities": "120.00",
        }
        for item in repository.compare_monthly_budget("2026-01", budget):
            print(
                f"- {item.category}: "
                f"budget={item.budget}, "
                f"actual={item.actual}, "
                f"remaining={item.remaining}, "
                f"over_budget={item.is_over_budget}"
            )

        report_path = generate_analysis_report(
            repository,
            lab_dir / "reports",
            budget_month="2026-01",
            budget_by_category=budget,
        )
        print(f"\nHTML report: {report_path}")
        print(f"CSV exports: {report_path.parent}")
    finally:
        repository.close()

    print(f"\nSQLite database: {database_path}")


if __name__ == "__main__":
    main()
