from __future__ import annotations

from platform_api_app import (
    CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_OPERATION_APPROVALS,
    PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
)
from platform_async_service import SQLitePlatformAsyncRunStore
from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_PENDING,
)
from test_platform_api_helpers import (
    _access_events,
    _approval_records,
    _client_with_async,
    _client_with_async_and_operation_approval,
    _fail_async_run,
    _payload,
    _remove_database,
    _retry_payload,
)


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
    ) = _client_with_async_and_operation_approval()
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
