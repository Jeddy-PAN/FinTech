from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


LABS_DIR = Path(__file__).resolve().parents[1]
KYC_LAB_DIR = LABS_DIR / "kyc-aml-onboarding"
if str(KYC_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(KYC_LAB_DIR))

from fintech_platform import (  # noqa: E402
    FinTechPlatform,
    FinTechPlatformError,
    PlatformPaymentRequest,
)
from kyc_aml import KycAmlError, build_individual_application  # noqa: E402
from sqlite_platform_store import (  # noqa: E402
    PlatformRunRecord,
    PlatformRunSnapshot,
    SQLitePlatformStore,
    SQLitePlatformStoreError,
)


class PlatformApiServiceError(ValueError):
    """Base error for invalid platform API service operations."""


@dataclass(frozen=True)
class PlatformApiPaymentRequest:
    run_id: str
    customer_id: str
    full_name: str
    date_of_birth: date
    country: str
    address: str
    identification_number: str
    expected_monthly_volume_cents: int
    amount: str
    currency: str
    order_id: str
    requested_at: datetime
    device_id: str = "device_default"
    ip_country: str = "US"
    beneficiary_id: str = "beneficiary_default"
    actor: str = "api_client"


class PlatformApiService:
    def __init__(
        self,
        *,
        platform: FinTechPlatform | None = None,
        store: SQLitePlatformStore,
    ) -> None:
        self.platform = platform or FinTechPlatform()
        self.store = store
        self._create_api_schema()

    def create_payment_run(
        self,
        request: PlatformApiPaymentRequest,
    ) -> dict:
        run_id = _require_text(request.run_id, "run_id")
        request_fingerprint = _request_fingerprint(request)
        existing_fingerprint = self._get_request_fingerprint(run_id)
        if (
            existing_fingerprint is not None
            and existing_fingerprint != request_fingerprint
        ):
            raise PlatformApiServiceError(
                "run_id was already used with a different request fingerprint"
            )
        if self._run_exists(run_id):
            snapshot = self.store.get_run(run_id)
            return _snapshot_response(snapshot, idempotent_replay=True)

        platform_request = _platform_request_from_api_request(request)
        result = self.platform.process_payment(platform_request)
        self.store.save_result(
            result,
            run_id=run_id,
            created_at=request.requested_at,
        )
        self._save_request_fingerprint(run_id, request_fingerprint)
        snapshot = self.store.get_run(run_id)
        return _snapshot_response(snapshot, idempotent_replay=False)

    def get_payment_run(self, run_id: str) -> dict:
        return _snapshot_response(
            self.store.get_run(_require_text(run_id, "run_id")),
            idempotent_replay=False,
        )

    def list_payment_runs(
        self,
        *,
        status: str | None = None,
        customer_id: str | None = None,
    ) -> tuple[dict, ...]:
        records = self.store.query_runs(
            status=status,
            customer_id=customer_id,
        )
        return tuple(_record_response(record) for record in records)

    def _run_exists(self, run_id: str) -> bool:
        try:
            self.store.get_run(run_id)
        except SQLitePlatformStoreError:
            return False
        return True

    def _create_api_schema(self) -> None:
        connection = sqlite3.connect(str(self.store.database_path))
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_api_requests (
                    run_id TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        finally:
            connection.close()

    def _get_request_fingerprint(self, run_id: str) -> str | None:
        connection = sqlite3.connect(str(self.store.database_path))
        try:
            row = connection.execute(
                """
                SELECT request_fingerprint
                FROM platform_api_requests
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        finally:
            connection.close()
        return row[0] if row is not None else None

    def _save_request_fingerprint(
        self,
        run_id: str,
        request_fingerprint: str,
    ) -> None:
        connection = sqlite3.connect(str(self.store.database_path))
        try:
            connection.execute(
                """
                INSERT INTO platform_api_requests (
                    run_id,
                    request_fingerprint,
                    created_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO NOTHING
                """,
                (
                    run_id,
                    request_fingerprint,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()


def _platform_request_from_api_request(
    request: PlatformApiPaymentRequest,
) -> PlatformPaymentRequest:
    _validate_timestamp(request.requested_at, "requested_at")
    application = build_individual_application(
        _require_text(request.customer_id, "customer_id"),
        _require_text(request.full_name, "full_name"),
        date_of_birth=request.date_of_birth,
        country=_require_text(request.country, "country"),
        address=_require_text(request.address, "address"),
        identification_number=_require_text(
            request.identification_number,
            "identification_number",
        ),
        expected_monthly_volume_cents=_positive_int(
            request.expected_monthly_volume_cents,
            "expected_monthly_volume_cents",
        ),
    )
    return PlatformPaymentRequest(
        application=application,
        amount=_amount_text(request.amount),
        currency=_require_text(request.currency, "currency"),
        order_id=_require_text(request.order_id, "order_id"),
        requested_at=request.requested_at,
        device_id=_require_text(request.device_id, "device_id"),
        ip_country=_require_text(request.ip_country, "ip_country"),
        beneficiary_id=_require_text(request.beneficiary_id, "beneficiary_id"),
        actor=_require_text(request.actor, "actor"),
    )


def _snapshot_response(
    snapshot: PlatformRunSnapshot,
    *,
    idempotent_replay: bool,
) -> dict:
    response = _record_response(snapshot.record)
    response["idempotent_replay"] = idempotent_replay
    response["audit_events"] = [
        {
            "source_system": event.source_system,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "actor": event.actor,
            "reason": event.reason,
            "occurred_at": event.occurred_at.isoformat(),
        }
        for event in snapshot.audit_events
    ]
    return response


def _record_response(record: PlatformRunRecord) -> dict:
    return {
        "run_id": record.run_id,
        "customer_id": record.customer_id,
        "status": record.status,
        "kyc_status": record.kyc_status,
        "payment_order_id": record.payment_order_id,
        "payment_order_status": record.payment_order_status,
        "risk_status": record.risk_status,
        "risk_review_case_id": record.risk_review_case_id,
        "ledger_transaction_id": record.ledger_transaction_id,
        "platform_bank_balance": str(record.platform_bank_balance),
        "user_wallet_balance": str(record.user_wallet_balance),
        "audit_event_count": record.audit_event_count,
        "created_at": record.created_at.isoformat(),
    }


def _request_fingerprint(request: PlatformApiPaymentRequest) -> str:
    payload = {
        "run_id": request.run_id.strip(),
        "customer_id": request.customer_id.strip(),
        "full_name": request.full_name.strip(),
        "date_of_birth": request.date_of_birth.isoformat(),
        "country": request.country.strip(),
        "address": request.address.strip(),
        "identification_number": request.identification_number.strip(),
        "expected_monthly_volume_cents": request.expected_monthly_volume_cents,
        "amount": _amount_text(request.amount),
        "currency": request.currency.strip(),
        "order_id": request.order_id.strip(),
        "requested_at": request.requested_at.isoformat(),
        "device_id": request.device_id.strip(),
        "ip_country": request.ip_country.strip(),
        "beneficiary_id": request.beneficiary_id.strip(),
        "actor": request.actor.strip(),
    }
    raw_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PlatformApiServiceError(f"{field_name} is required")
    return normalized


def _positive_int(value: int, field_name: str) -> int:
    if value <= 0:
        raise PlatformApiServiceError(f"{field_name} must be positive")
    return value


def _amount_text(value: str) -> str:
    normalized = _require_text(value, "amount")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise PlatformApiServiceError("amount must be a decimal value") from exc
    if amount <= 0:
        raise PlatformApiServiceError("amount must be positive")
    return normalized


def _validate_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PlatformApiServiceError(f"{field_name} must be timezone-aware")


def service_error_response(error: Exception) -> dict:
    if isinstance(
        error,
        (
            PlatformApiServiceError,
            FinTechPlatformError,
            KycAmlError,
            SQLitePlatformStoreError,
        ),
    ):
        return {
            "error": type(error).__name__,
            "message": str(error),
        }
    return {
        "error": "InternalServiceError",
        "message": "Unexpected platform API service error",
    }
