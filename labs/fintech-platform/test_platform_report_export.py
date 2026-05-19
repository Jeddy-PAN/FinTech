from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_report_export import export_platform_report


def test_export_platform_report_writes_result_timeline_and_html() -> None:
    output_directory = _output_directory()
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id="order_001",
            requested_at=_requested_at(),
        )
    )

    paths = export_platform_report(output_directory, result=result)

    try:
        assert paths.result_csv.exists()
        assert paths.timeline_csv.exists()
        assert paths.html_report.exists()

        result_csv = paths.result_csv.read_text(encoding="utf-8")
        timeline_csv = paths.timeline_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "section,metric,value" in result_csv
        assert "platform,status,completed" in result_csv
        assert "payment,order_status,succeeded" in result_csv
        assert "ledger,platform_bank_balance,100.00" in result_csv
        assert "audit,event_count,5" in result_csv
        assert "subject_type,subject_id,occurred_at,source_system" in timeline_csv
        assert "customer,cust_001,2026-05-18T09:00:00+00:00,kyc" in timeline_csv
        assert "ledger_transaction.posted" in timeline_csv
        assert "FinTech Platform Report" in html_report
        assert "Payment Result" in html_report
        assert "Customer Audit Timeline" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_report_includes_risk_review_case() -> None:
    output_directory = _output_directory()
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_risk_review",
            requested_at=_requested_at(),
        )
    )

    paths = export_platform_report(output_directory, result=result)

    try:
        result_csv = paths.result_csv.read_text(encoding="utf-8")
        timeline_csv = paths.timeline_csv.read_text(encoding="utf-8")

        assert "platform,status,risk_review_required" in result_csv
        assert "risk,review_case_id,review:order_risk_review" in result_csv
        assert "review_case.created" in timeline_csv
    finally:
        _remove_directory(output_directory)


def test_export_platform_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    result = FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=build_individual_application(
                "cust_<script>",
                "Jordan <b>Smith</b>",
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

    paths = export_platform_report(output_directory, result=result)

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "cust_&lt;script&gt;" in html_report
        assert "order_&lt;script&gt;" in html_report
        assert "actor_&lt;script&gt;" in html_report
        assert "cust_<script>" not in html_report
        assert "order_<script>" not in html_report
        assert "actor_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


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


def _output_directory() -> Path:
    directory = _test_data_directory() / f"report-{uuid4()}"
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
