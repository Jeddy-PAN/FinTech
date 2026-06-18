from __future__ import annotations

import csv
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any

LABS_DIR = Path(__file__).resolve().parents[1]
COMPLIANCE_LAB_DIR = LABS_DIR / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from platform_settlement_reconciliation_report import (  # noqa: E402
    PROVIDER_SETTLEMENT_FAILED,
    PROVIDER_SETTLEMENT_REVERSED,
    PROVIDER_SETTLEMENT_SETTLED,
    ProviderSettlementRow,
)


PROVIDER_INTENT_REQUIRES_CAPTURE = "requires_capture"
PROVIDER_INTENT_SUCCEEDED = "succeeded"
PROVIDER_INTENT_FAILED = "failed"
PROVIDER_INTENT_CANCELLED = "cancelled"
PROVIDER_INTENT_STATUSES = {
    PROVIDER_INTENT_REQUIRES_CAPTURE,
    PROVIDER_INTENT_SUCCEEDED,
    PROVIDER_INTENT_FAILED,
    PROVIDER_INTENT_CANCELLED,
}

PROVIDER_EVENT_TO_PROVIDER_STATUS = {
    "payment_intent.succeeded": PROVIDER_INTENT_SUCCEEDED,
    "payment_intent.failed": PROVIDER_INTENT_FAILED,
    "payment_intent.cancelled": PROVIDER_INTENT_CANCELLED,
}

PROVIDER_STATUS_TO_INTERNAL_STATUS = {
    PROVIDER_INTENT_SUCCEEDED: "succeeded",
    PROVIDER_INTENT_FAILED: "failed",
    PROVIDER_INTENT_CANCELLED: "cancelled",
}

SETTLEMENT_STATUS_ALIASES = {
    PROVIDER_SETTLEMENT_SETTLED: PROVIDER_SETTLEMENT_SETTLED,
    PROVIDER_SETTLEMENT_FAILED: PROVIDER_SETTLEMENT_FAILED,
    PROVIDER_SETTLEMENT_REVERSED: PROVIDER_SETTLEMENT_REVERSED,
}

SETTLEMENT_CSV_COLUMNS = {
    "provider",
    "settlement_id",
    "provider_payment_id",
    "platform_run_id",
    "payment_order_id",
    "amount",
    "currency",
    "status",
    "settled_at",
}

DEFAULT_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300
PROVIDER_PAYMENT_INTENTS_CSV_COLUMNS = (
    "provider",
    "provider_intent_id",
    "internal_run_id",
    "payment_order_id",
    "amount",
    "currency",
    "status",
    "created_at",
)


@dataclass(frozen=True)
class ProviderPaymentIntent:
    provider: str
    provider_intent_id: str
    internal_run_id: str
    payment_order_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _require_text(self.provider, "provider"))
        object.__setattr__(
            self,
            "provider_intent_id",
            _require_text(self.provider_intent_id, "provider_intent_id"),
        )
        object.__setattr__(
            self,
            "internal_run_id",
            _require_text(self.internal_run_id, "internal_run_id"),
        )
        object.__setattr__(
            self,
            "payment_order_id",
            _require_text(self.payment_order_id, "payment_order_id"),
        )
        object.__setattr__(self, "amount", _money_amount(self.amount, "amount"))
        object.__setattr__(self, "currency", _currency(self.currency))
        object.__setattr__(self, "status", _provider_intent_status(self.status))
        _validate_aware_timestamp(self.created_at, "created_at")


@dataclass(frozen=True)
class ProviderWebhookEvent:
    event_id: str
    provider_intent_id: str
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            _require_text(self.event_id, "event_id"),
        )
        object.__setattr__(
            self,
            "provider_intent_id",
            _require_text(self.provider_intent_id, "provider_intent_id"),
        )
        object.__setattr__(
            self,
            "event_type",
            _require_text(self.event_type, "event_type"),
        )
        _validate_aware_timestamp(self.occurred_at, "occurred_at")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")


@dataclass(frozen=True)
class ProviderWebhookProcessingResult:
    event: ProviderWebhookEvent
    provider_status: str
    internal_status: str
    duplicate: bool


class ProviderWebhookEventProcessor:
    def __init__(
        self,
        *,
        secret: str,
        timestamp_tolerance_seconds: int | None = None,
    ) -> None:
        self.secret = _require_text(secret, "secret")
        self.timestamp_tolerance_seconds = _timestamp_tolerance(
            timestamp_tolerance_seconds
        )
        self._processed_events: dict[str, ProviderWebhookProcessingResult] = {}

    def process_signed_payload(
        self,
        payload: str,
        signature: str,
        *,
        received_at: datetime | None = None,
    ) -> ProviderWebhookProcessingResult:
        if not verify_provider_webhook_signature(self.secret, payload, signature):
            raise ValueError("Invalid provider webhook signature")

        event = parse_provider_webhook_payload(payload)
        _validate_event_replay_window(
            event,
            received_at=received_at,
            tolerance_seconds=self.timestamp_tolerance_seconds,
        )
        if event.event_id in self._processed_events:
            previous = self._processed_events[event.event_id]
            return ProviderWebhookProcessingResult(
                event=previous.event,
                provider_status=previous.provider_status,
                internal_status=previous.internal_status,
                duplicate=True,
            )

        provider_status = provider_status_from_event_type(event.event_type)
        result = ProviderWebhookProcessingResult(
            event=event,
            provider_status=provider_status,
            internal_status=internal_status_from_provider_status(provider_status),
            duplicate=False,
        )
        self._processed_events[event.event_id] = result
        return result


def build_provider_webhook_payload(
    *,
    event_id: str,
    provider_intent_id: str,
    event_type: str,
    occurred_at: datetime,
    payload: dict[str, Any],
) -> str:
    event = ProviderWebhookEvent(
        event_id=event_id,
        provider_intent_id=provider_intent_id,
        event_type=event_type,
        occurred_at=occurred_at,
        payload=payload,
    )
    return json.dumps(
        {
            "event_id": event.event_id,
            "provider_intent_id": event.provider_intent_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "payload": event.payload,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def sign_provider_webhook_payload(secret: str, payload: str) -> str:
    normalized_secret = _require_text(secret, "secret")
    normalized_payload = _require_text(payload, "payload")
    return hmac.new(
        normalized_secret.encode("utf-8"),
        normalized_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_provider_webhook_signature(
    secret: str,
    payload: str,
    signature: str,
) -> bool:
    if not signature.strip():
        return False
    expected = sign_provider_webhook_payload(secret, payload)
    return hmac.compare_digest(expected, signature.strip())


def parse_provider_webhook_payload(payload: str) -> ProviderWebhookEvent:
    raw_payload = _require_text(payload, "payload")
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError as error:
        raise ValueError("Provider webhook payload must be valid JSON") from error

    if not isinstance(data, dict):
        raise ValueError("Provider webhook payload must be a JSON object")

    try:
        occurred_at = _parse_timestamp(data["occurred_at"], "occurred_at")
        event_payload = data["payload"]
        if not isinstance(event_payload, dict):
            raise ValueError("payload must be an object")
        return ProviderWebhookEvent(
            event_id=str(data["event_id"]),
            provider_intent_id=str(data["provider_intent_id"]),
            event_type=str(data["event_type"]),
            occurred_at=occurred_at,
            payload=event_payload,
        )
    except KeyError as error:
        raise ValueError(f"Missing provider webhook field: {error.args[0]}") from error


def provider_status_from_event_type(event_type: str) -> str:
    normalized = _require_text(event_type, "event_type")
    try:
        return PROVIDER_EVENT_TO_PROVIDER_STATUS[normalized]
    except KeyError as error:
        raise ValueError(f"Unknown provider webhook event type: {normalized}") from error


def internal_status_from_provider_status(provider_status: str) -> str:
    normalized = _provider_intent_status(provider_status)
    try:
        return PROVIDER_STATUS_TO_INTERNAL_STATUS[normalized]
    except KeyError as error:
        raise ValueError(
            f"Provider status cannot be mapped to internal status: {normalized}"
        ) from error


def provider_intent_id_for_run(provider: str, run_id: str) -> str:
    return (
        f"{_require_text(provider, 'provider')}_intent_"
        f"{_require_text(run_id, 'run_id')}"
    )


def build_provider_payment_intent(
    snapshot,
    *,
    provider: str,
    provider_intent_id: str | None = None,
    status: str | None = None,
    created_at: datetime | None = None,
) -> ProviderPaymentIntent:
    record = snapshot.record
    payment_order_id = record.payment_order_id
    if payment_order_id is None:
        raise ValueError("snapshot must have a payment_order_id")

    normalized_provider = _require_text(provider, "provider")
    return ProviderPaymentIntent(
        provider=normalized_provider,
        provider_intent_id=(
            provider_intent_id
            if provider_intent_id is not None
            else provider_intent_id_for_run(normalized_provider, record.run_id)
        ),
        internal_run_id=record.run_id,
        payment_order_id=payment_order_id,
        amount=_payment_amount_from_snapshot(snapshot),
        currency=_payment_currency_from_snapshot(snapshot),
        status=status or _provider_intent_status_from_snapshot(record),
        created_at=created_at or record.created_at,
    )


def build_provider_payment_intents(
    snapshots,
    *,
    provider: str,
) -> tuple[ProviderPaymentIntent, ...]:
    intents: list[ProviderPaymentIntent] = []
    for snapshot in snapshots:
        if snapshot.record.payment_order_id is None:
            continue
        intents.append(build_provider_payment_intent(snapshot, provider=provider))
    return tuple(intents)


def export_provider_payment_intents_csv(
    output_directory: str | Path,
    *,
    intents: tuple[ProviderPaymentIntent, ...],
) -> Path:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "provider_payment_intents.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(PROVIDER_PAYMENT_INTENTS_CSV_COLUMNS)
        for intent in intents:
            writer.writerow(
                [
                    intent.provider,
                    intent.provider_intent_id,
                    intent.internal_run_id,
                    intent.payment_order_id,
                    intent.amount,
                    intent.currency,
                    intent.status,
                    intent.created_at.isoformat(),
                ]
            )
    return csv_path


def parse_provider_settlement_csv(csv_text: str) -> tuple[ProviderSettlementRow, ...]:
    raw_csv = _require_text(csv_text, "csv_text")
    reader = csv.DictReader(StringIO(raw_csv))
    _validate_settlement_columns(reader.fieldnames)

    rows: list[ProviderSettlementRow] = []
    for row_number, row in enumerate(reader, start=2):
        rows.append(_provider_settlement_row(row, row_number))
    return tuple(rows)


def _payment_amount_from_snapshot(snapshot) -> Decimal:
    payment_order_id = snapshot.record.payment_order_id
    for event in snapshot.audit_events:
        if event.aggregate_id != payment_order_id:
            continue
        if event.event_type not in {"payment_order.created", "payment_order.succeeded"}:
            continue
        payload = _json_payload(event.payload)
        if "amount" in payload:
            return _money_amount(payload["amount"], "amount")
    return _money_amount(snapshot.record.user_wallet_balance, "amount")


def _payment_currency_from_snapshot(snapshot) -> str:
    payment_order_id = snapshot.record.payment_order_id
    for event in snapshot.audit_events:
        if event.aggregate_id != payment_order_id:
            continue
        payload = _json_payload(event.payload)
        if "currency" in payload:
            return _currency(payload["currency"])
    return "USD"


def _provider_intent_status_from_snapshot(record) -> str:
    payment_status = (record.payment_order_status or "").strip().lower()
    if payment_status == "succeeded":
        return PROVIDER_INTENT_SUCCEEDED
    if payment_status == "failed":
        return PROVIDER_INTENT_FAILED
    if payment_status in {"cancelled", "canceled"}:
        return PROVIDER_INTENT_CANCELLED
    if record.status == "completed":
        return PROVIDER_INTENT_SUCCEEDED
    if record.status.endswith("rejected"):
        return PROVIDER_INTENT_FAILED
    return PROVIDER_INTENT_REQUIRES_CAPTURE


def _json_payload(payload: object) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    try:
        loaded = json.loads(str(payload))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _provider_settlement_row(
    row: dict[str, str],
    row_number: int,
) -> ProviderSettlementRow:
    try:
        return ProviderSettlementRow(
            provider=_require_text(row["provider"], "provider"),
            settlement_id=_require_text(row["settlement_id"], "settlement_id"),
            provider_payment_id=_require_text(
                row["provider_payment_id"],
                "provider_payment_id",
            ),
            platform_run_id=_require_text(row["platform_run_id"], "platform_run_id"),
            payment_order_id=_require_text(row["payment_order_id"], "payment_order_id"),
            amount=_money_amount(row["amount"], "amount"),
            currency=_currency(row["currency"]),
            status=_settlement_status(row["status"]),
            settled_at=_parse_timestamp(row["settled_at"], "settled_at"),
        )
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Invalid settlement CSV row {row_number}: {error}") from error


def _validate_settlement_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Settlement CSV must include a header row")
    columns = set(fieldnames)
    missing = sorted(SETTLEMENT_CSV_COLUMNS - columns)
    if missing:
        raise ValueError(f"Missing required settlement CSV column: {missing[0]}")


def _money_amount(value: Decimal | str, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} must be a decimal amount") from error
    if amount < Decimal("0.00"):
        raise ValueError(f"{field_name} must be greater than or equal to 0")
    return amount


def _currency(value: str) -> str:
    currency = _require_text(value, "currency").upper()
    if len(currency) != 3:
        raise ValueError("currency must be a three-letter code")
    return currency


def _provider_intent_status(value: str) -> str:
    status = _require_text(value, "status").lower()
    if status not in PROVIDER_INTENT_STATUSES:
        raise ValueError(f"Unknown provider intent status: {status}")
    return status


def _settlement_status(value: str) -> str:
    status = _require_text(value, "status").lower()
    try:
        return SETTLEMENT_STATUS_ALIASES[status]
    except KeyError as error:
        raise ValueError(f"Unknown settlement status: {status}") from error


def _parse_timestamp(value: object, field_name: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO timestamp") from error
    _validate_aware_timestamp(timestamp, field_name)
    return timestamp


def _validate_aware_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _timestamp_tolerance(value: int | None) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError("timestamp_tolerance_seconds must be greater than 0")
    return value


def _validate_event_replay_window(
    event: ProviderWebhookEvent,
    *,
    received_at: datetime | None,
    tolerance_seconds: int | None,
) -> None:
    if tolerance_seconds is None:
        return

    now = received_at or datetime.now(timezone.utc)
    _validate_aware_timestamp(now, "received_at")
    event_time = event.occurred_at.astimezone(timezone.utc)
    received_time = now.astimezone(timezone.utc)
    age_seconds = abs((received_time - event_time).total_seconds())
    if age_seconds > tolerance_seconds:
        raise ValueError("Provider webhook timestamp is outside the replay window")


def _require_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text
