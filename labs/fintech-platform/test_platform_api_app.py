from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api_app import (
    CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_PAYMENT_RUN,
    LIST_PLATFORM_PAYMENT_RUNS,
    PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_OPERATION_APPROVALS,
    UPDATE_PLATFORM_OPERATION_APPROVALS,
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_OPERATION_APPROVALS,
    VIEW_PLATFORM_PAYMENT_RUN,
    create_app,
)
from platform_async_service import PlatformAsyncWorker, SQLitePlatformAsyncRunStore
from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
    OperationApprovalRecord,
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

        retry_request = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
            },
        )
        retry_approval = retry_request.json()["record"]
        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            pending_retry = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert pending_retry.status == "failed"

        approve = client.patch(
            f"/platform/operation-approvals/{retry_approval['approval_id']}/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved retry after reviewing worker failure",
                "decided_at": "2026-06-08T10:00:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )
        processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )

        assert created.status_code == 202
        assert retry_request.status_code == 202
        assert retry_approval["operation_id"] == "run_retry_http"
        assert retry_approval["requested_by"] == "ops_user_001"
        assert retry_approval["status"] == OPERATION_APPROVAL_PENDING

        assert approve.status_code == 200
        approve_body = approve.json()
        assert approve_body["record"]["status"] == OPERATION_APPROVAL_APPROVED
        assert approve_body["record"]["approved_by"] == "ops_manager_001"
        assert approve_body["run"]["run_id"] == "run_retry_http"
        assert approve_body["run"]["status"] == "accepted"
        assert approve_body["run"]["attempt_count"] == 3
        assert approve_body["run"]["last_error"] is None
        assert approve_body["run"]["completed_at"] is None

        assert processed.status_code == 200
        assert processed.json()["result"]["run_id"] == "run_retry_http"
        assert processed.json()["result"]["async_status"] == "completed"

        events = _access_events(access_audit_database_path)
        create_approval_events = [
            event
            for event in events
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(create_approval_events) == 1
        assert create_approval_events[0].actor == "ops_user_001"
        assert create_approval_events[0].outcome == "granted"

        retry_events = [
            event
            for event in events
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].actor == "ops_manager_001"
        assert retry_events[0].target == (
            "fintech_platform_api_async_payment_runs/run_retry_http"
        )
        assert retry_events[0].outcome == "granted"
        assert f"approval_id={retry_approval['approval_id']}" in retry_events[0].reason

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
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
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

        request = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
            },
        )
        approval_id = request.json()["record"]["approval_id"]
        response = client.patch(
            f"/platform/operation-approvals/{approval_id}/approve",
            json={
                "decided_by": "ops_user_001",
                "decision_reason": "Self approval should fail",
                "decided_at": "2026-06-08T10:00:00Z",
            },
            headers={"x-actor-id": "ops_user_001"},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "OperationApprovalError"
        assert "approved_by must differ from requested_by" in response.json()["detail"][
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
        assert retry_events == []

        approval_records = _approval_records(operation_approval_database_path)
        assert len(approval_records) == 1
        assert approval_records[0].operation_id == "run_retry_http"
        assert approval_records[0].requested_by == "ops_user_001"
        assert approval_records[0].approved_by is None
        assert approval_records[0].status == OPERATION_APPROVAL_PENDING
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_retry_request_ignores_approval_decision_fields() -> None:
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
            },
        )

        assert response.status_code == 202
        assert response.json()["record"]["status"] == OPERATION_APPROVAL_PENDING

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert retry_events == []
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
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
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
        assert "retry_failed_async_run" in body
        assert "approve_retry_failed_async_run" not in body
        assert "Request Approval" in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_console_retry_form_creates_pending_retry_approval() -> None:
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
            },
            follow_redirects=False,
        )
        console = client.get(retry.headers["location"])
        current_console = client.get("/platform/view")

        assert retry.status_code == 303
        assert retry.headers["location"] == (
            "/platform/view?retry_status=pending_approval"
        )
        assert "Retry approval request created." in console.text
        assert "run_retry_http" in current_console.text

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            run = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert run.status == "failed"
        assert run.last_error == "temporary failure"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert retry_events == []

        approval_records = _approval_records(operation_approval_database_path)
        assert len(approval_records) == 1
        assert approval_records[0].operation_id == "run_retry_http"
        assert approval_records[0].request_reason == "Retry from console"
        assert approval_records[0].approval_reason is None
        assert approval_records[0].status == OPERATION_APPROVAL_PENDING
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_renders_operations_and_approval_report_views() -> None:
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
            "/platform/payment-runs",
            json=_payload(
                run_id="run_console_completed",
                order_id="order_console_completed",
            ),
        )
        assert created.status_code == 201

        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )
        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )
        approval_id = retry.json()["record"]["approval_id"]

        assert retry.status_code == 202

        client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_retry_pending_console",
                order_id="order_retry_pending_console",
            ),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
            run_id="run_retry_pending_console",
        )
        pending_retry = client.post(
            "/platform/async-payment-runs/run_retry_pending_console/retry",
            json=_retry_payload(),
        )
        pending_approval_id = pending_retry.json()["record"]["approval_id"]

        assert pending_retry.status_code == 202

        approved = client.patch(
            f"/platform/operation-approvals/{approval_id}/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved retry after reviewing worker failure",
                "decided_at": "2026-06-08T10:00:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )

        assert approved.status_code == 200

        console = client.get("/platform/view")

        assert console.status_code == 200
        body = console.text
        assert "Operations Report Summary" in body
        assert "Operations Run Rows" in body
        assert "Ledger Reconciliation Findings" in body
        assert "Ledger reconciliation findings" in body
        assert "completed_balances_match_ledger_amount" in body
        assert "retry_granted_count" in body
        assert "warning_finding_count" in body
        assert "run_retry_http" in body
        assert "Operation Approval Summary" in body
        assert "Pending Operation Approvals" in body
        assert "Approval Records" in body
        assert "pending_count" in body
        assert "Pending approvals" in body
        assert "approved_count" in body
        assert "self_approval_rejected_count" in body
        assert pending_approval_id in body
        assert (
            f"/platform/operation-approvals/{pending_approval_id}/view"
            in body
        )
        assert "run_retry_pending_console" in body
        assert "failed" in body
        assert "Retry after transient worker failure" in body
        assert "ops_manager_001" in body
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
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "confirmation must be retry_failed_async_run" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_console_retry_form_reports_non_failed_run_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry-form",
            data={
                "actor": "ops_user_001",
                "reason": "Retry from console",
                "confirmation": "retry_failed_async_run",
            },
            follow_redirects=False,
        )
        console = client.get(retry.headers["location"])

        assert retry.status_code == 303
        assert retry.headers["location"].startswith("/platform/view?retry_error=")
        assert "Retry failed:" in console.text
        assert "Cannot retry accepted async run" in console.text

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            accepted = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert accepted.status == "accepted"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "Cannot retry accepted async run" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_lists_and_gets_operation_approval_records() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        listed = client.get(
            "/platform/operation-approvals",
            params={"status": OPERATION_APPROVAL_PENDING},
            headers={"x-actor-id": "approval_viewer_001"},
        )
        single = client.get(
            "/platform/operation-approvals/approval_pending_001",
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert listed.status_code == 200
        assert listed.json()["records"][0]["approval_id"] == "approval_pending_001"
        assert listed.json()["records"][0]["status"] == OPERATION_APPROVAL_PENDING
        assert listed.json()["records"][0]["approved_by"] is None
        assert listed.json()["records"][0]["decided_at"] is None
        assert single.status_code == 200
        assert single.json()["record"]["approval_id"] == "approval_pending_001"

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == VIEW_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 2
        assert {event.outcome for event in events} == {"granted"}
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_paginates_and_sorts_operation_approval_records() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_oldest",
            operation_id="run_oldest",
            requested_at=datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc),
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_middle",
            operation_id="run_middle",
            requested_at=datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_newest",
            operation_id="run_newest",
            requested_at=datetime(2026, 6, 8, 11, 0, tzinfo=timezone.utc),
        )

        listed = client.get(
            "/platform/operation-approvals",
            params={
                "sort_by": "requested_at",
                "sort_order": "desc",
                "limit": "2",
                "offset": "1",
            },
            headers={"x-actor-id": "approval_viewer_001"},
        )
        invalid_sort = client.get(
            "/platform/operation-approvals",
            params={"sort_by": "created_at"},
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert listed.status_code == 200
        body = listed.json()
        assert [record["approval_id"] for record in body["records"]] == [
            "approval_middle",
            "approval_oldest",
        ]
        assert body["pagination"] == {
            "limit": 2,
            "offset": 1,
            "returned_count": 2,
            "sort_by": "requested_at",
            "sort_order": "desc",
        }
        assert invalid_sort.status_code == 400
        assert "Unknown approval sort field" in invalid_sort.json()["detail"]["message"]

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == VIEW_PLATFORM_OPERATION_APPROVALS
        ]
        assert [event.outcome for event in events] == ["granted", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_operation_approval_detail_view_shows_async_and_platform_context() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        created = client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_detail_completed",
                order_id="order_detail_completed",
            ),
        )
        processed = client.post("/platform/async-worker/process-next")
        approval = client.post(
            "/platform/operation-approvals",
            json={
                **_pending_approval_payload(),
                "approval_id": "approval_detail_completed",
                "operation_id": "run_detail_completed",
                "target": (
                    "fintech_platform_api_async_payment_runs/"
                    "run_detail_completed"
                ),
                "request_reason": "Review completed retry context",
            },
            headers={"x-actor-id": "approval_requester_001"},
        )
        detail = client.get(
            "/platform/operation-approvals/approval_detail_completed/view",
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert created.status_code == 202
        assert processed.status_code == 200
        assert approval.status_code == 201
        assert detail.status_code == 200
        body = detail.text
        assert "Operation Approval Detail" in body
        assert "approval_detail_completed" in body
        assert "Review completed retry context" in body
        assert "Associated Async Run" in body
        assert "run_detail_completed" in body
        assert "completed" in body
        assert "Platform Result Summary" in body
        assert "order_detail_completed" in body

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == VIEW_PLATFORM_OPERATION_APPROVALS
        ]
        assert events[-1].actor == "approval_viewer_001"
        assert events[-1].outcome == "granted"
        assert events[-1].reason == "view detail"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_creates_pending_operation_approval() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        response = client.post(
            "/platform/operation-approvals",
            json=_pending_approval_payload(),
            headers={"x-actor-id": "approval_requester_001"},
        )

        assert response.status_code == 201
        body = response.json()["record"]
        assert body["approval_id"] == "approval_pending_001"
        assert body["operation_type"] == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        assert body["status"] == OPERATION_APPROVAL_PENDING
        assert body["approved_by"] is None
        assert body["approval_reason"] is None
        assert body["decided_at"] is None

        saved = _approval_records(operation_approval_database_path)
        assert len(saved) == 1
        assert saved[0].approval_id == "approval_pending_001"
        assert saved[0].status == OPERATION_APPROVAL_PENDING

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 1
        assert events[0].actor == "approval_requester_001"
        assert events[0].outcome == "granted"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_rejects_duplicate_operation_approval_id() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        first = client.post(
            "/platform/operation-approvals",
            json=_pending_approval_payload(),
            headers={"x-actor-id": "approval_requester_001"},
        )
        duplicate = client.post(
            "/platform/operation-approvals",
            json={
                **_pending_approval_payload(),
                "request_reason": "Duplicate approval request",
            },
            headers={"x-actor-id": "approval_requester_001"},
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
        assert "already exists" in duplicate.json()["detail"]["message"]

        records = _approval_records(operation_approval_database_path)
        assert len(records) == 1
        assert records[0].request_reason == "Request retry approval"

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == CREATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert [event.outcome for event in events] == ["granted", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_approves_pending_operation_approval() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )
        _save_pending_approval(operation_approval_database_path)

        response = client.patch(
            "/platform/operation-approvals/approval_pending_001/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved pending retry after review",
                "decided_at": "2026-06-08T09:30:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )

        assert response.status_code == 200
        body = response.json()["record"]
        assert body["approval_id"] == "approval_pending_001"
        assert body["status"] == OPERATION_APPROVAL_APPROVED
        assert body["approved_by"] == "ops_manager_001"
        assert body["approval_reason"] == "Approved pending retry after review"
        assert body["decided_at"] == "2026-06-08T09:30:00+00:00"
        assert response.json()["run"]["run_id"] == "run_retry_http"
        assert response.json()["run"]["status"] == "accepted"

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_APPROVED
        assert saved[0].approved_by == "ops_manager_001"

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 1
        assert events[0].actor == "ops_manager_001"
        assert events[0].outcome == "granted"

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].actor == "ops_manager_001"
        assert retry_events[0].outcome == "granted"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_rejects_pending_and_denies_invalid_transition() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        rejected = client.patch(
            "/platform/operation-approvals/approval_pending_001/reject",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Retry evidence is incomplete",
                "decided_at": "2026-06-08T09:30:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )
        duplicate = client.patch(
            "/platform/operation-approvals/approval_pending_001/approve",
            json={
                "decided_by": "ops_manager_002",
                "decision_reason": "Duplicate approval",
                "decided_at": "2026-06-08T09:35:00Z",
            },
            headers={"x-actor-id": "ops_manager_002"},
        )

        assert rejected.status_code == 200
        assert rejected.json()["record"]["status"] == OPERATION_APPROVAL_REJECTED
        assert duplicate.status_code == 409
        assert "Cannot approve rejected" in duplicate.json()["detail"]["message"]

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert [event.outcome for event in events] == ["granted", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_cancels_pending_operation_approval() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        cancelled = client.patch(
            "/platform/operation-approvals/approval_pending_001/cancel",
            json={
                "decided_by": "ops_user_001",
                "decision_reason": "Requester withdrew retry request",
                "decided_at": "2026-06-08T09:30:00Z",
            },
            headers={"x-actor-id": "ops_user_001"},
        )
        duplicate = client.patch(
            "/platform/operation-approvals/approval_pending_001/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Late approval",
                "decided_at": "2026-06-08T09:35:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )
        listed = client.get(
            "/platform/operation-approvals?status=cancelled",
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert cancelled.status_code == 200
        body = cancelled.json()["record"]
        assert body["approval_id"] == "approval_pending_001"
        assert body["status"] == OPERATION_APPROVAL_CANCELLED
        assert body["approved_by"] == "ops_user_001"
        assert body["approval_reason"] == "Requester withdrew retry request"
        assert body["decision_reason"] == "cancelled"
        assert body["decided_at"] == "2026-06-08T09:30:00+00:00"
        assert duplicate.status_code == 409
        assert "Cannot approve cancelled" in duplicate.json()["detail"]["message"]
        assert listed.status_code == 200
        assert listed.json()["records"][0]["status"] == OPERATION_APPROVAL_CANCELLED

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert [event.outcome for event in events] == ["granted", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_expires_pending_operation_approval() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        expired = client.patch(
            "/platform/operation-approvals/approval_pending_001/expire",
            json={
                "decided_by": "system_scheduler",
                "decision_reason": "Approval request exceeded review window",
                "decided_at": "2026-06-08T10:00:00Z",
            },
            headers={"x-actor-id": "system_scheduler"},
        )
        duplicate = client.patch(
            "/platform/operation-approvals/approval_pending_001/reject",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Late rejection",
                "decided_at": "2026-06-08T10:05:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )

        assert expired.status_code == 200
        body = expired.json()["record"]
        assert body["approval_id"] == "approval_pending_001"
        assert body["status"] == OPERATION_APPROVAL_EXPIRED
        assert body["approved_by"] == "system_scheduler"
        assert body["approval_reason"] == "Approval request exceeded review window"
        assert body["decision_reason"] == "expired"
        assert duplicate.status_code == 409
        assert "Cannot reject expired" in duplicate.json()["detail"]["message"]

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert [event.outcome for event in events] == ["granted", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


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
    }


def _pending_approval_payload() -> dict:
    return {
        "approval_id": "approval_pending_001",
        "operation_type": RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
        "operation_id": "run_retry_http",
        "target": "fintech_platform_api_async_payment_runs/run_retry_http",
        "requested_by": "ops_user_001",
        "request_reason": "Request retry approval",
        "requested_at": "2026-06-08T09:00:00Z",
    }


def _fail_async_run(
    *,
    database_path: Path,
    async_database_path: Path,
    run_id: str = "run_retry_http",
) -> None:
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
        assert async_store.get_run(run_id).status == "failed"
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


def _save_pending_approval(
    database_path: Path,
    *,
    approval_id: str = "approval_pending_001",
    operation_id: str = "run_retry_http",
    requested_at: datetime | None = None,
) -> None:
    store = SQLiteOperationApprovalStore(database_path)
    try:
        store.save_record(
            OperationApprovalRecord(
                approval_id=approval_id,
                operation_type=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
                operation_id=operation_id,
                target=f"fintech_platform_api_async_payment_runs/{operation_id}",
                requested_by="ops_user_001",
                request_reason="Request retry approval",
                approved_by=None,
                approval_reason=None,
                status=OPERATION_APPROVAL_PENDING,
                decision_reason="pending approval",
                requested_at=_now() if requested_at is None else requested_at,
                decided_at=None,
            )
        )
    finally:
        store.close()


def _now():
    return datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()


def _investigation_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-investigation-{uuid4()}.db"
