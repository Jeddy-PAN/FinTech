from __future__ import annotations

from datetime import datetime, timedelta, timezone

from platform_api_app import (
    PLATFORM_PROVIDER_WEBHOOKS_TARGET,
    PROCESS_PLATFORM_PROVIDER_WEBHOOK,
)
from platform_payment_provider import (
    build_provider_webhook_payload,
    sign_provider_webhook_payload,
)
from test_platform_api_helpers import _access_events, _client, _remove_database


def test_platform_api_accepts_signed_provider_webhook_and_deduplicates_replay() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        payload = _provider_payload(event_id="evt_provider_001")
        signature = sign_provider_webhook_payload("teaching_provider_secret", payload)

        first_response = client.post(
            "/platform/provider-webhooks",
            content=payload,
            headers={
                "content-type": "application/json",
                "x-provider-signature": signature,
            },
        )
        replay_response = client.post(
            "/platform/provider-webhooks",
            content=payload,
            headers={
                "content-type": "application/json",
                "x-provider-signature": signature,
            },
        )

        assert first_response.status_code == 202
        assert first_response.json() == {
            "event_id": "evt_provider_001",
            "provider_intent_id": "intent_001",
            "event_type": "payment_intent.succeeded",
            "provider_status": "succeeded",
            "internal_status": "succeeded",
            "duplicate": False,
        }
        assert replay_response.status_code == 200
        assert replay_response.json()["duplicate"] is True

        access_events = _access_events(access_audit_database_path)
        assert any(
            event.permission == PROCESS_PLATFORM_PROVIDER_WEBHOOK
            and event.target == PLATFORM_PROVIDER_WEBHOOKS_TARGET
            and event.outcome == "granted"
            for event in access_events
        )
    finally:
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_rejects_provider_webhook_with_invalid_signature() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        response = client.post(
            "/platform/provider-webhooks",
            content=_provider_payload(event_id="evt_provider_bad"),
            headers={
                "content-type": "application/json",
                "x-provider-signature": "invalid-signature",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid provider webhook signature"

        access_events = _access_events(access_audit_database_path)
        assert any(
            event.permission == PROCESS_PLATFORM_PROVIDER_WEBHOOK
            and event.target == PLATFORM_PROVIDER_WEBHOOKS_TARGET
            and event.outcome == "denied"
            for event in access_events
        )
    finally:
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_rejects_signed_provider_webhook_outside_replay_window() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        payload = _provider_payload(
            event_id="evt_provider_old",
            occurred_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        )
        signature = sign_provider_webhook_payload("teaching_provider_secret", payload)

        response = client.post(
            "/platform/provider-webhooks",
            content=payload,
            headers={
                "content-type": "application/json",
                "x-provider-signature": signature,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Provider webhook timestamp is outside the replay window"
        )

        access_events = _access_events(access_audit_database_path)
        assert any(
            event.permission == PROCESS_PLATFORM_PROVIDER_WEBHOOK
            and event.target == PLATFORM_PROVIDER_WEBHOOKS_TARGET
            and event.outcome == "denied"
            and event.reason == "Provider webhook timestamp is outside the replay window"
            for event in access_events
        )
    finally:
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def _provider_payload(
    *,
    event_id: str,
    occurred_at: datetime | None = None,
) -> str:
    return build_provider_webhook_payload(
        event_id=event_id,
        provider_intent_id="intent_001",
        event_type="payment_intent.succeeded",
        occurred_at=datetime.now(timezone.utc) if occurred_at is None else occurred_at,
        payload={"amount": "100.00", "currency": "USD"},
    )
