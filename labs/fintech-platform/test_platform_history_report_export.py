from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_history_report_export import export_platform_history_report
from sqlite_platform_store import SQLitePlatformStore


def test_export_platform_history_report_writes_runs_events_and_html() -> None:
    output_directory = _output_directory()
    snapshots = _snapshots()

    paths = export_platform_history_report(output_directory, snapshots=snapshots)

    try:
        assert paths.runs_csv.exists()
        assert paths.audit_events_csv.exists()
        assert paths.html_report.exists()

        runs_csv = paths.runs_csv.read_text(encoding="utf-8")
        audit_events_csv = paths.audit_events_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "run_id,customer_id,status,kyc_status" in runs_csv
        assert "run_completed,cust_001,completed,approved" in runs_csv
        assert "run_review,cust_001,risk_review_required,approved" in runs_csv
        assert "run_id,sequence,occurred_at,source_system,event_type" in audit_events_csv
        assert "run_completed,1,2026-05-18T09:00:00+00:00,kyc" in audit_events_csv
        assert "review_case.created" in audit_events_csv
        assert "FinTech Platform Run History" in html_report
        assert "Run Summary" in html_report
        assert "Audit Events" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_history_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        result = FinTechPlatform().process_payment(
            PlatformPaymentRequest(
                application=build_individual_application(
                    "cust_<script>",
                    "Jordan Smith",
                    date_of_birth=date(1992, 5, 20),
                    country="US",
                    address="100 Market Street",
                    identification_number="ID-1001",
                    expected_monthly_volume_cents=250_000,
                ),
                amount="100.00",
                currency="USD",
                order_id="order_<script>",
                requested_at=_requested_at(),
                actor="actor_<script>",
            )
        )
        store.save_result(
            result,
            run_id="run_<script>",
            created_at=_requested_at(),
        )
        paths = export_platform_history_report(
            output_directory,
            snapshots=(store.get_run("run_<script>"),),
        )

        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "run_&lt;script&gt;" in html_report
        assert "cust_&lt;script&gt;" in html_report
        assert "order_&lt;script&gt;" in html_report
        assert "actor_&lt;script&gt;" in html_report
        assert "run_<script>" not in html_report
        assert "cust_<script>" not in html_report
        assert "order_<script>" not in html_report
    finally:
        store.close()
        _remove_directory(output_directory)


def _snapshots():
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            _approved_result(order_id="order_completed"),
            run_id="run_completed",
            created_at=_requested_at(),
        )
        store.save_result(
            _risk_review_result(),
            run_id="run_review",
            created_at=datetime(2026, 5, 18, 9, 5, tzinfo=timezone.utc),
        )
        return (
            store.get_run("run_completed"),
            store.get_run("run_review"),
        )
    finally:
        store.close()


def _approved_result(order_id: str):
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id=order_id,
            requested_at=_requested_at(),
        )
    )


def _risk_review_result():
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_review",
            requested_at=_requested_at(),
        )
    )


def _approved_application():
    return build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )


def _requested_at() -> datetime:
    return datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)


def _database_path() -> Path:
    return _test_data_directory() / f"platform-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"history-report-{uuid4()}"
    directory.mkdir()
    return directory


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
