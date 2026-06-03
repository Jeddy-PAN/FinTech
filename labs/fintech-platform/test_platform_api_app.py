from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api_app import (
    CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_PAYMENT_RUN,
    LIST_PLATFORM_PAYMENT_RUNS,
    PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_PAYMENT_RUN,
    create_app,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore


def test_platform_api_health() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        response = client.get("/health", headers={"x-actor-id": "monitor_001"})

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        events = _access_events(access_audit_database_path)
        assert len(events) == 1
        assert events[0].actor == "monitor_001"
        assert events[0].permission == "check_platform_api_health"
        assert events[0].outcome == "granted"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


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


def test_platform_api_creates_and_gets_async_payment_run() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        created = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )

        assert created.status_code == 202
        created_body = created.json()
        assert created_body["run_id"] == "run_async_http_001"
        assert created_body["status"] == "accepted"
        assert created_body["attempt_count"] == 0
        assert created_body["idempotent_replay"] is False
        assert created_body["http_status"] == "accepted"
        assert created_body["platform_result"] is None
        assert created_body["request"]["customer_id"] == "cust_001"

        fetched = client.get(
            "/platform/async-payment-runs/run_async_http_001",
            headers={"x-actor-id": "api_async_viewer_001"},
        )

        assert fetched.status_code == 200
        fetched_body = fetched.json()
        assert fetched_body["run_id"] == "run_async_http_001"
        assert fetched_body["status"] == "accepted"
        assert fetched_body["platform_result"] is None

        events = _access_events(access_audit_database_path)
        assert [(event.actor, event.permission, event.outcome) for event in events] == [
            ("api_client_001", CREATE_PLATFORM_ASYNC_PAYMENT_RUN, "granted"),
            ("api_async_viewer_001", VIEW_PLATFORM_ASYNC_PAYMENT_RUN, "granted"),
        ]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_replays_async_run_and_rejects_fingerprint_conflict() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        first = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )
        replay = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )
        conflict = client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_async_http_001",
                order_id="order_changed",
                amount="999.00",
            ),
        )

        assert first.status_code == 202
        assert replay.status_code == 202
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["http_status"] == "idempotent_replay"
        assert conflict.status_code == 400
        assert conflict.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "different request fingerprint" in conflict.json()["detail"]["message"]

        events = _access_events(access_audit_database_path)
        assert [event.outcome for event in events] == [
            "granted",
            "granted",
            "denied",
        ]
        assert events[1].reason == "idempotent_replay"
        assert events[2].permission == CREATE_PLATFORM_ASYNC_PAYMENT_RUN
        assert "different request fingerprint" in events[2].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_worker_processes_async_run_to_platform_result() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        accepted = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )
        processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )
        fetched_async = client.get("/platform/async-payment-runs/run_async_http_001")
        fetched_platform = client.get("/platform/payment-runs/run_async_http_001")

        assert accepted.status_code == 202
        assert processed.status_code == 200
        assert processed.json()["result"] == {
            "processed": True,
            "run_id": "run_async_http_001",
            "async_status": "completed",
            "platform_status": "completed",
            "error": None,
        }

        async_body = fetched_async.json()
        assert async_body["status"] == "completed"
        assert async_body["attempt_count"] == 1
        assert async_body["platform_result"]["run_id"] == "run_async_http_001"
        assert async_body["platform_result"]["status"] == "completed"

        assert fetched_platform.status_code == 200
        assert fetched_platform.json()["payment_order_id"] == "order_async_http_001"

        worker_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS
        ]
        assert len(worker_events) == 1
        assert worker_events[0].actor == "async_worker_001"
        assert worker_events[0].outcome == "granted"
        assert "run_async_http_001" in worker_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_lists_async_runs_and_processes_pending_limit() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_002", order_id="order_async_http_002"),
        )

        accepted_before = client.get(
            "/platform/async-payment-runs?status=accepted",
            headers={"x-actor-id": "api_async_viewer_002"},
        )
        processed = client.post(
            "/platform/async-worker/process-pending?limit=1",
            headers={"x-actor-id": "async_worker_001"},
        )
        accepted_after = client.get("/platform/async-payment-runs?status=accepted")

        assert accepted_before.status_code == 200
        assert [run["run_id"] for run in accepted_before.json()["runs"]] == [
            "run_async_http_001",
            "run_async_http_002",
        ]
        assert processed.status_code == 200
        assert [result["run_id"] for result in processed.json()["results"]] == [
            "run_async_http_001",
        ]
        assert [run["run_id"] for run in accepted_after.json()["runs"]] == [
            "run_async_http_002",
        ]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_worker_reports_no_pending_async_run() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        response = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )

        assert response.status_code == 200
        assert response.json()["result"] == {
            "processed": False,
            "run_id": None,
            "async_status": None,
            "platform_status": None,
            "error": None,
        }

        events = _access_events(access_audit_database_path)
        assert events[0].permission == PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS
        assert events[0].reason == "processed=0"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


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


def test_platform_api_lists_api_access_events() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        client.post("/platform/payment-runs", json=_payload())

        response = client.get(
            "/platform/api-access-events?permission=create_platform_payment_run",
            headers={"x-actor-id": "audit_reader_001"},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["events"]) == 1
        assert body["events"][0]["actor"] == "api_client_001"
        assert body["events"][0]["permission"] == CREATE_PLATFORM_PAYMENT_RUN
        assert body["events"][0]["outcome"] == "granted"

        events = _access_events(access_audit_database_path)
        assert events[-1].actor == "audit_reader_001"
        assert events[-1].permission == "view_platform_api_access_events"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_console_page_renders_platform_summary() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client_with_investigation()
    )
    try:
        created = client.post("/platform/payment-runs", json=_payload())
        assert created.status_code == 201

        client.get(
            "/platform/payment-runs/missing_run",
            headers={"x-actor-id": "api_viewer_404"},
        )
        client.get(
            "/platform/payment-runs/missing_run",
            headers={"x-actor-id": "api_viewer_404"},
        )
        client.get(
            "/platform/payment-runs/missing_run",
            headers={"x-actor-id": "api_viewer_404"},
        )
        client.post(
            "/platform/api-access-investigation-cases",
            headers={"x-actor-id": "api_compliance_lead_001"},
        )

        console = client.get("/", headers={"x-actor-id": "console_reader_001"})

        assert console.status_code == 200
        assert console.headers["content-type"].startswith("text/html")
        body = console.text
        assert "FinTech Platform Console" in body
        assert "Payment runs" in body
        assert "Completed runs" in body
        assert "API access anomalies" in body
        assert "Investigation cases" in body
        assert "run_http_001" in body
        assert "repeated_denied_access" in body
        assert "api_viewer_404" in body
        assert "access_investigation:" in body

        events = _access_events(access_audit_database_path)
        assert events[-1].permission == "view_platform_console"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_console_page_renders_empty_state() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client_with_investigation()
    )
    try:
        console = client.get("/platform/view")

        assert console.status_code == 200
        assert console.headers["content-type"].startswith("text/html")
        body = console.text
        assert "FinTech Platform Console" in body
        assert "No payment runs have been recorded yet." in body
        assert "No API access anomalies have been detected yet." in body
        assert "No investigation cases have been created yet." in body

        events = _access_events(access_audit_database_path)
        assert len(events) == 1
        assert events[0].permission == "view_platform_console"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def _client():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
    )


def _client_with_investigation():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    investigation_database_path = _investigation_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                investigation_database_path=investigation_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        investigation_database_path,
    )


def _client_with_async():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
    )


def _payload(
    *,
    run_id: str = "run_http_001",
    order_id: str = "order_http_001",
    amount: str = "100.00",
) -> dict:
    return {
        "run_id": run_id,
        "customer_id": "cust_001",
        "full_name": "Jordan Smith",
        "date_of_birth": "1992-05-20",
        "country": "US",
        "address": "100 Market Street",
        "identification_number": "ID-1001",
        "expected_monthly_volume_cents": 250000,
        "amount": amount,
        "currency": "USD",
        "order_id": order_id,
        "requested_at": "2026-05-19T09:00:00Z",
        "device_id": "device_known",
        "ip_country": "US",
        "beneficiary_id": "beneficiary_001",
        "actor": "api_client_001",
    }


def _database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-{uuid4()}.db"


def _access_audit_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-access-audit-{uuid4()}.db"


def _async_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-async-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _access_events(database_path: Path):
    store = SQLiteAccessAuditStore(database_path)
    try:
        return store.access_events
    finally:
        store.close()


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()


def _investigation_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-investigation-{uuid4()}.db"
