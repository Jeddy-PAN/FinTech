from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api_app import (
    CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_PAYMENT_RUN,
    LIST_PLATFORM_PAYMENT_RUNS,
    PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_PAYMENT_RUN,
    create_app,
)
from platform_async_service import PlatformAsyncWorker, SQLitePlatformAsyncRunStore
from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_REJECTED,
    SQLiteOperationApprovalStore,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore
from sqlite_platform_store import SQLitePlatformStore


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


def test_platform_api_retries_failed_async_run_and_worker_processes_it() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = (
        _client_with_async_and_operation_approval()
    )
    try:
        created = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
                "approved_by": "ops_manager_001",
                "approval_reason": "Approved retry after reviewing worker failure",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
        )
        processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )

        assert created.status_code == 202
        assert retry.status_code == 200
        retry_body = retry.json()["run"]
        assert retry_body["run_id"] == "run_retry_http"
        assert retry_body["status"] == "accepted"
        assert retry_body["attempt_count"] == 3
        assert retry_body["last_error"] is None
        assert retry_body["completed_at"] is None

        assert processed.status_code == 200
        assert processed.json()["result"]["run_id"] == "run_retry_http"
        assert processed.json()["result"]["async_status"] == "completed"

        events = _access_events(access_audit_database_path)
        retry_events = [
            event
            for event in events
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].actor == "ops_user_001"
        assert retry_events[0].target == (
            "fintech_platform_api_async_payment_runs/run_retry_http"
        )
        assert retry_events[0].outcome == "granted"
        assert retry_events[0].reason == (
            "reason=Retry after transient worker failure; "
            "approved_by=ops_manager_001; "
            "approval_reason=Approved retry after reviewing worker failure"
        )

        approval_records = _approval_records(operation_approval_database_path)
        assert len(approval_records) == 1
        assert approval_records[0].operation_type == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        assert approval_records[0].operation_id == "run_retry_http"
        assert approval_records[0].requested_by == "ops_user_001"
        assert approval_records[0].approved_by == "ops_manager_001"
        assert approval_records[0].status == OPERATION_APPROVAL_APPROVED
        assert approval_records[0].decision_reason == "approved"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_rejects_retry_confirmation_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        response = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "wrong_confirmation",
                "approved_by": "ops_manager_001",
                "approval_reason": "Approved retry after reviewing worker failure",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "confirmation must be retry_failed_async_run" in response.json()[
            "detail"
        ]["message"]

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "confirmation must be retry_failed_async_run" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_rejects_retry_self_approval() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = (
        _client_with_async_and_operation_approval()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        response = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
                "approved_by": "ops_user_001",
                "approval_reason": "Self approval should fail",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "retry approver must differ from actor" in response.json()["detail"][
            "message"
        ]

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            failed = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert failed.status == "failed"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "retry approver must differ from actor" in retry_events[0].reason

        approval_records = _approval_records(operation_approval_database_path)
        assert len(approval_records) == 1
        assert approval_records[0].operation_id == "run_retry_http"
        assert approval_records[0].requested_by == "ops_user_001"
        assert approval_records[0].approved_by == "ops_user_001"
        assert approval_records[0].status == OPERATION_APPROVAL_REJECTED
        assert "retry approver must differ from actor" in approval_records[
            0
        ].decision_reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_rejects_retry_approval_confirmation_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        response = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
                "approved_by": "ops_manager_001",
                "approval_reason": "Approved retry after reviewing worker failure",
                "approval_confirmation": "wrong_approval_confirmation",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert (
            "approval_confirmation must be approve_retry_failed_async_run"
            in response.json()["detail"]["message"]
        )

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert (
            "approval_confirmation must be approve_retry_failed_async_run"
            in retry_events[0].reason
        )
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_rejects_retry_for_unknown_or_non_failed_async_run() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )

        unknown = client.post(
            "/platform/async-payment-runs/missing_run/retry",
            json=_retry_payload(),
        )
        conflict = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )

        assert unknown.status_code == 404
        assert unknown.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "Unknown platform async run" in unknown.json()["detail"]["message"]

        assert conflict.status_code == 409
        assert conflict.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "Cannot retry accepted async run" in conflict.json()["detail"][
            "message"
        ]

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert [event.outcome for event in retry_events] == ["denied", "denied"]
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
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        investigation_database_path,
    ) = _client_with_async_and_investigation()
    try:
        created = client.post("/platform/payment-runs", json=_payload())
        assert created.status_code == 201
        async_created = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_http_001", order_id="order_async_http_001"),
        )
        async_processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )
        assert async_created.status_code == 202
        assert async_processed.status_code == 200

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
        assert "Async runs" in body
        assert "Accepted async runs" in body
        assert "Failed async runs" in body
        assert "Recent Async Runs" in body
        assert "Failed Async Runs" in body
        assert "API access anomalies" in body
        assert "Investigation cases" in body
        assert "run_http_001" in body
        assert "run_async_http_001" in body
        assert "order_async_http_001" in body
        assert "completed" in body
        assert "No failed async runs have been recorded yet." in body
        assert "repeated_denied_access" in body
        assert "api_viewer_404" in body
        assert "access_investigation:" in body

        events = _access_events(access_audit_database_path)
        assert events[-1].permission == "view_platform_console"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
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
        assert "No async runs have been recorded yet." in body
        assert "No failed async runs have been recorded yet." in body
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


def test_platform_demo_failed_async_sample_is_visible_in_console() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        sample = create_failed_async_run_sample(
            client,
            existing_platform_payload=_payload(
                run_id="run_failed_async_http_001",
                order_id="order_existing_failed_async",
                amount="100.00",
            ),
            async_payload=_payload(
                run_id="run_failed_async_http_001",
                order_id="order_failed_async",
                amount="125.00",
            ),
        )
        console = client.get("/platform/view")

        assert sample["created_platform"]["status"] == "completed"
        assert sample["accepted_async"]["status"] == "accepted"
        assert [result["async_status"] for result in sample["worker_results"]] == [
            "accepted",
            "accepted",
            "failed",
        ]
        assert sample["failed_async"]["status"] == "failed"
        assert sample["failed_async"]["attempt_count"] == 3
        assert "different request fingerprint" in sample["failed_async"]["last_error"]

        body = console.text
        assert "Failed Async Runs" in body
        assert "run_failed_async_http_001" in body
        assert "failed" in body
        assert "different request fingerprint" in body
        assert "No failed async runs have been recorded yet." not in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_console_renders_retry_form_for_failed_async_run() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        console = client.get("/platform/view")

        assert console.status_code == 200
        body = console.text
        assert "Failed Async Runs" in body
        assert 'action="/platform/async-payment-runs/run_retry_http/retry-form"' in body
        assert 'name="actor"' in body
        assert 'name="reason"' in body
        assert 'name="confirmation"' in body
        assert 'name="approved_by"' in body
        assert 'name="approval_reason"' in body
        assert 'name="approval_confirmation"' in body
        assert "retry_failed_async_run" in body
        assert "approve_retry_failed_async_run" in body
        assert "Retry" in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_console_retry_form_requeues_failed_async_run() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = (
        _client_with_async_and_operation_approval()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry-form",
            data={
                "actor": "ops_user_001",
                "reason": "Retry from console",
                "confirmation": "retry_failed_async_run",
                "approved_by": "ops_manager_001",
                "approval_reason": "Approved retry from console",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
            follow_redirects=False,
        )
        console = client.get("/platform/view")

        assert retry.status_code == 303
        assert retry.headers["location"] == "/platform/view?retry_status=success"
        assert "No failed async runs have been recorded yet." in console.text

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            retried = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert retried.status == "accepted"
        assert retried.last_error is None

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].actor == "ops_user_001"
        assert retry_events[0].outcome == "granted"
        assert retry_events[0].reason == (
            "reason=Retry from console; "
            "approved_by=ops_manager_001; "
            "approval_reason=Approved retry from console"
        )

        approval_records = _approval_records(operation_approval_database_path)
        assert len(approval_records) == 1
        assert approval_records[0].operation_id == "run_retry_http"
        assert approval_records[0].request_reason == "Retry from console"
        assert approval_records[0].approval_reason == "Approved retry from console"
        assert approval_records[0].status == OPERATION_APPROVAL_APPROVED
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_retry_form_reports_confirmation_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry-form",
            data={
                "actor": "ops_user_001",
                "reason": "Retry from console",
                "confirmation": "wrong_confirmation",
                "approved_by": "ops_manager_001",
                "approval_reason": "Approved retry from console",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
            follow_redirects=False,
        )
        console = client.get(retry.headers["location"])

        assert retry.status_code == 303
        assert retry.headers["location"].startswith("/platform/view?retry_error=")
        assert "Retry failed:" in console.text
        assert "confirmation must be retry_failed_async_run" in console.text
        assert "run_retry_http" in console.text

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            failed = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert failed.status == "failed"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "confirmation must be retry_failed_async_run" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_console_retry_form_reports_self_approval_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry-form",
            data={
                "actor": "ops_user_001",
                "reason": "Retry from console",
                "confirmation": "retry_failed_async_run",
                "approved_by": "ops_user_001",
                "approval_reason": "Self approval should fail",
                "approval_confirmation": "approve_retry_failed_async_run",
            },
            follow_redirects=False,
        )
        console = client.get(retry.headers["location"])

        assert retry.status_code == 303
        assert retry.headers["location"].startswith("/platform/view?retry_error=")
        assert "Retry failed:" in console.text
        assert "retry approver must differ from actor" in console.text

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            failed = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert failed.status == "failed"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "retry approver must differ from actor" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def create_failed_async_run_sample(client: TestClient, **kwargs):
    spec = importlib.util.spec_from_file_location(
        "fintech_platform_demo",
        Path(__file__).with_name("demo.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load fintech platform demo module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_failed_async_run_sample(client, **kwargs)


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


def _client_with_async_and_operation_approval():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    operation_approval_database_path = _operation_approval_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
                operation_approval_database_path=operation_approval_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    )


def _client_with_async_and_investigation():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    investigation_database_path = _investigation_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
                investigation_database_path=investigation_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
        investigation_database_path,
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


def _retry_payload() -> dict:
    return {
        "actor": "ops_user_001",
        "reason": "Retry after transient worker failure",
        "confirmation": "retry_failed_async_run",
        "approved_by": "ops_manager_001",
        "approval_reason": "Approved retry after reviewing worker failure",
        "approval_confirmation": "approve_retry_failed_async_run",
    }


def _fail_async_run(*, database_path: Path, async_database_path: Path) -> None:
    async_store = SQLitePlatformAsyncRunStore(async_database_path)
    platform_store = SQLitePlatformStore(database_path)
    try:
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )
        for _ in range(3):
            worker.process_next()
        assert async_store.get_run("run_retry_http").status == "failed"
    finally:
        async_store.close()
        platform_store.close()


class _FailingService:
    def create_payment_run(self, request):  # noqa: ARG002
        raise RuntimeError("temporary failure")


def _database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-{uuid4()}.db"


def _access_audit_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-access-audit-{uuid4()}.db"


def _async_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-async-{uuid4()}.db"


def _operation_approval_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-operation-approval-{uuid4()}.db"


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


def _approval_records(database_path: Path):
    store = SQLiteOperationApprovalStore(database_path)
    try:
        return store.records
    finally:
        store.close()


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()


def _investigation_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-investigation-{uuid4()}.db"
