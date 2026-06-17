from __future__ import annotations

from platform_api_app import (
    CREATE_PLATFORM_PAYMENT_RUN,
    LIST_PLATFORM_PAYMENT_RUNS,
    VIEW_PLATFORM_PAYMENT_RUN,
)
from test_platform_api_helpers import (
    _access_events,
    _client,
    _payload,
    _remove_database,
)


def test_platform_api_creates_and_gets_payment_run() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        created = client.post("/platform/payment-runs", json=_payload())

        assert created.status_code == 201
        created_body = created.json()
        assert created_body["run_id"] == "run_http_001"
        assert created_body["status"] == "completed"
        assert created_body["payment_order_status"] == "succeeded"
        assert created_body["idempotent_replay"] is False
        assert [event["event_type"] for event in created_body["audit_events"]] == [
            "kyc_decision.saved",
            "payment_order.created",
            "risk_decision.saved",
            "payment_order.succeeded",
            "ledger_transaction.posted",
        ]

        fetched = client.get(
            "/platform/payment-runs/run_http_001",
            headers={"x-actor-id": "api_viewer_001"},
        )
        assert fetched.status_code == 200
        fetched_body = fetched.json()
        assert fetched_body["run_id"] == "run_http_001"
        assert fetched_body["status"] == "completed"

        events = _access_events(access_audit_database_path)
        assert [(event.actor, event.permission, event.outcome) for event in events] == [
            ("api_client_001", CREATE_PLATFORM_PAYMENT_RUN, "granted"),
            ("api_viewer_001", VIEW_PLATFORM_PAYMENT_RUN, "granted"),
        ]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_replays_same_request_and_rejects_fingerprint_conflict() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        first = client.post("/platform/payment-runs", json=_payload())
        replay = client.post("/platform/payment-runs", json=_payload())
        conflict = client.post(
            "/platform/payment-runs",
            json=_payload(amount="999.00", order_id="order_changed"),
        )

        assert first.status_code == 201
        assert replay.status_code == 201
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["http_status"] == "idempotent_replay"
        assert conflict.status_code == 400
        assert conflict.json()["detail"]["error"] == "PlatformApiServiceError"
        assert "different request fingerprint" in conflict.json()["detail"]["message"]

        events = _access_events(access_audit_database_path)
        assert [event.outcome for event in events] == [
            "granted",
            "granted",
            "denied",
        ]
        assert events[1].reason == "idempotent_replay"
        assert events[2].permission == CREATE_PLATFORM_PAYMENT_RUN
        assert "different request fingerprint" in events[2].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_lists_payment_runs_with_filters() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        client.post(
            "/platform/payment-runs",
            json=_payload(run_id="run_completed", order_id="order_completed"),
        )
        client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_review",
                order_id="order_review",
                amount="1500.00",
            ),
        )

        all_runs = client.get(
            "/platform/payment-runs",
            headers={"x-actor-id": "api_viewer_002"},
        )
        review_runs = client.get("/platform/payment-runs?status=risk_review_required")
        customer_runs = client.get("/platform/payment-runs?customer_id=cust_001")

        assert all_runs.status_code == 200
        assert [run["run_id"] for run in all_runs.json()["runs"]] == [
            "run_completed",
            "run_review",
        ]
        assert [run["run_id"] for run in review_runs.json()["runs"]] == [
            "run_review",
        ]
        assert [run["run_id"] for run in customer_runs.json()["runs"]] == [
            "run_completed",
            "run_review",
        ]

        list_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == LIST_PLATFORM_PAYMENT_RUNS
        ]
        assert [event.actor for event in list_events] == [
            "api_viewer_002",
            "anonymous_api_client",
            "anonymous_api_client",
        ]
        assert [event.outcome for event in list_events] == [
            "granted",
            "granted",
            "granted",
        ]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_returns_404_for_missing_run() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        response = client.get(
            "/platform/payment-runs/missing_run",
            headers={"x-actor-id": "api_viewer_404"},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "SQLitePlatformStoreError"

        events = _access_events(access_audit_database_path)
        assert len(events) == 1
        assert events[0].actor == "api_viewer_404"
        assert events[0].permission == VIEW_PLATFORM_PAYMENT_RUN
        assert events[0].target == "fintech_platform_api_payment_runs/missing_run"
        assert events[0].outcome == "denied"
        assert events[0].reason.startswith("404 SQLitePlatformStoreError:")
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
