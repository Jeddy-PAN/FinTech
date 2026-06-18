from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_payment_provider import (
    ProviderPaymentIntent,
    ProviderWebhookEventProcessor,
    build_provider_payment_intent,
    build_provider_payment_intents,
    build_provider_webhook_payload,
    export_provider_payment_intents_csv,
    parse_provider_settlement_csv,
    provider_intent_id_for_run,
    sign_provider_webhook_payload,
    verify_provider_webhook_signature,
)
from platform_settlement_reconciliation_report import (
    PROVIDER_SETTLEMENT_SETTLED,
)


def test_provider_payment_intent_normalizes_amount_currency_and_status() -> None:
    intent = ProviderPaymentIntent(
        provider="teaching-pay",
        provider_intent_id="intent_001",
        internal_run_id="run_001",
        payment_order_id="order_001",
        amount=Decimal("100"),
        currency="usd",
        status="requires_capture",
        created_at=_timestamp(),
    )

    assert intent.amount == Decimal("100.00")
    assert intent.currency == "USD"
    assert intent.status == "requires_capture"


def test_build_provider_payment_intent_links_provider_intent_to_platform_run() -> None:
    snapshot = _snapshot(
        run_id="run_001",
        payment_order_id="order_001",
        payment_order_status="succeeded",
        audit_payload='{"amount":"125.00","currency":"usd"}',
        user_wallet_balance=Decimal("100.00"),
    )

    intent = build_provider_payment_intent(snapshot, provider="teaching-pay")

    assert intent.provider == "teaching-pay"
    assert intent.provider_intent_id == "teaching-pay_intent_run_001"
    assert intent.internal_run_id == "run_001"
    assert intent.payment_order_id == "order_001"
    assert intent.amount == Decimal("125.00")
    assert intent.currency == "USD"
    assert intent.status == "succeeded"


def test_build_provider_payment_intents_skips_snapshots_without_payment_order() -> None:
    intents = build_provider_payment_intents(
        (
            _snapshot(
                run_id="run_001",
                payment_order_id="order_001",
                payment_order_status="succeeded",
            ),
            _snapshot(
                run_id="run_kyc_rejected",
                payment_order_id=None,
                payment_order_status=None,
            ),
        ),
        provider="teaching-pay",
    )

    assert [intent.internal_run_id for intent in intents] == ["run_001"]


def test_export_provider_payment_intents_csv_writes_internal_external_link() -> None:
    output_directory = _output_directory()
    try:
        intent = build_provider_payment_intent(
            _snapshot(
                run_id="run_001",
                payment_order_id="order_001",
                payment_order_status="succeeded",
            ),
            provider="teaching-pay",
        )

        csv_path = export_provider_payment_intents_csv(
            output_directory,
            intents=(intent,),
        )
        csv_text = csv_path.read_text(encoding="utf-8")

        assert csv_path.name == "provider_payment_intents.csv"
        assert (
            "provider,provider_intent_id,internal_run_id,payment_order_id,"
            "amount,currency,status,created_at"
        ) in csv_text
        assert "teaching-pay,teaching-pay_intent_run_001,run_001,order_001" in csv_text
    finally:
        _remove_directory(output_directory)


def test_provider_intent_id_for_run_is_deterministic() -> None:
    assert (
        provider_intent_id_for_run("teaching-pay", "run_001")
        == "teaching-pay_intent_run_001"
    )


def test_provider_webhook_signature_detects_tampering() -> None:
    payload = build_provider_webhook_payload(
        event_id="evt_001",
        provider_intent_id="intent_001",
        event_type="payment_intent.succeeded",
        occurred_at=_timestamp(),
        payload={"amount": "100.00", "currency": "USD"},
    )

    signature = sign_provider_webhook_payload("secret_001", payload)

    assert verify_provider_webhook_signature("secret_001", payload, signature) is True
    assert (
        verify_provider_webhook_signature(
            "secret_001",
            payload.replace("100.00", "900.00"),
            signature,
        )
        is False
    )


def test_provider_webhook_processor_maps_status_and_deduplicates_event_id() -> None:
    payload = build_provider_webhook_payload(
        event_id="evt_001",
        provider_intent_id="intent_001",
        event_type="payment_intent.succeeded",
        occurred_at=_timestamp(),
        payload={"amount": "100.00", "currency": "USD"},
    )
    signature = sign_provider_webhook_payload("secret_001", payload)
    processor = ProviderWebhookEventProcessor(secret="secret_001")

    first_result = processor.process_signed_payload(payload, signature)
    replay_result = processor.process_signed_payload(payload, signature)

    assert first_result.duplicate is False
    assert first_result.provider_status == "succeeded"
    assert first_result.internal_status == "succeeded"
    assert first_result.event.event_id == "evt_001"
    assert replay_result.duplicate is True
    assert replay_result.event == first_result.event
    assert replay_result.provider_status == first_result.provider_status
    assert replay_result.internal_status == first_result.internal_status


def test_provider_webhook_processor_rejects_events_outside_replay_window() -> None:
    received_at = datetime(2026, 6, 18, 8, 10, tzinfo=timezone.utc)
    payload = build_provider_webhook_payload(
        event_id="evt_old",
        provider_intent_id="intent_001",
        event_type="payment_intent.succeeded",
        occurred_at=received_at - timedelta(minutes=10, seconds=1),
        payload={"amount": "100.00", "currency": "USD"},
    )
    signature = sign_provider_webhook_payload("secret_001", payload)
    processor = ProviderWebhookEventProcessor(
        secret="secret_001",
        timestamp_tolerance_seconds=600,
    )

    with pytest.raises(ValueError, match="outside the replay window"):
        processor.process_signed_payload(
            payload,
            signature,
            received_at=received_at,
        )


def test_provider_webhook_processor_rejects_future_events_outside_replay_window() -> None:
    received_at = datetime(2026, 6, 18, 8, 10, tzinfo=timezone.utc)
    payload = build_provider_webhook_payload(
        event_id="evt_future",
        provider_intent_id="intent_001",
        event_type="payment_intent.succeeded",
        occurred_at=received_at + timedelta(minutes=10, seconds=1),
        payload={"amount": "100.00", "currency": "USD"},
    )
    signature = sign_provider_webhook_payload("secret_001", payload)
    processor = ProviderWebhookEventProcessor(
        secret="secret_001",
        timestamp_tolerance_seconds=600,
    )

    with pytest.raises(ValueError, match="outside the replay window"):
        processor.process_signed_payload(
            payload,
            signature,
            received_at=received_at,
        )


def test_provider_webhook_processor_rejects_invalid_signature() -> None:
    payload = build_provider_webhook_payload(
        event_id="evt_bad",
        provider_intent_id="intent_001",
        event_type="payment_intent.failed",
        occurred_at=_timestamp(),
        payload={"failure_code": "insufficient_funds"},
    )
    processor = ProviderWebhookEventProcessor(secret="secret_001")

    with pytest.raises(ValueError, match="Invalid provider webhook signature"):
        processor.process_signed_payload(payload, "not-a-valid-signature")


def test_parse_provider_settlement_csv_returns_provider_settlement_rows() -> None:
    csv_text = """provider,settlement_id,provider_payment_id,platform_run_id,payment_order_id,amount,currency,status,settled_at
teaching-pay,set_001,intent_001,run_001,order_001,100.00,usd,settled,2026-06-18T08:30:00+00:00
"""

    rows = parse_provider_settlement_csv(csv_text)

    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "teaching-pay"
    assert row.settlement_id == "set_001"
    assert row.provider_payment_id == "intent_001"
    assert row.platform_run_id == "run_001"
    assert row.payment_order_id == "order_001"
    assert row.amount == Decimal("100.00")
    assert row.currency == "USD"
    assert row.status == PROVIDER_SETTLEMENT_SETTLED
    assert row.settled_at == datetime(2026, 6, 18, 8, 30, tzinfo=timezone.utc)


def test_parse_provider_settlement_csv_rejects_missing_required_column() -> None:
    csv_text = "provider,settlement_id\nteaching-pay,set_001\n"

    with pytest.raises(ValueError, match="Missing required settlement CSV column"):
        parse_provider_settlement_csv(csv_text)


def _timestamp() -> datetime:
    return datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)


def _snapshot(
    *,
    run_id: str,
    payment_order_id: str | None,
    payment_order_status: str | None,
    audit_payload: str = '{"amount":"100.00"}',
    user_wallet_balance: Decimal = Decimal("100.00"),
):
    record = SimpleNamespace(
        run_id=run_id,
        status="completed" if payment_order_status == "succeeded" else "failed",
        payment_order_id=payment_order_id,
        payment_order_status=payment_order_status,
        user_wallet_balance=user_wallet_balance,
        created_at=_timestamp(),
    )
    audit_events = ()
    if payment_order_id is not None:
        audit_events = (
            SimpleNamespace(
                event_type="payment_order.created",
                aggregate_id=payment_order_id,
                payload=audit_payload,
            ),
        )
    return SimpleNamespace(record=record, audit_events=audit_events)


def _output_directory():
    directory = Path(__file__).with_name(".test-data") / f"provider-payment-intents-{uuid4()}"
    directory.mkdir(parents=True)
    return directory


def _remove_directory(directory) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
