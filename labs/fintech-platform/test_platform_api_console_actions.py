from __future__ import annotations

from platform_api_app import (
    CREATE_PLATFORM_OPERATION_APPROVALS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    UPDATE_PLATFORM_OPERATION_APPROVALS,
)
from platform_async_service import SQLitePlatformAsyncRunStore
from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
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
    _save_pending_approval,
)


def test_platform_console_retry_form_creates_pending_retry_approval() -> None:
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


def test_platform_console_approval_approve_form_executes_retry() -> None:
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
        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )
        approval_id = retry.json()["record"]["approval_id"]

        approved = client.post(
            f"/platform/operation-approvals/{approval_id}/approve-form",
            data={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "approve_operation_approval",
            },
            follow_redirects=False,
        )
        console = client.get(approved.headers["location"])

        assert approved.status_code == 303
        assert approved.headers["location"] == "/platform/view?approval_status=approved"
        assert "Operation approval approved." in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_APPROVED
        assert saved[0].approved_by == "ops_manager_001"
        assert saved[0].approval_reason == "Approved from console"

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            run = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert run.status == "accepted"

        update_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(update_events) == 1
        assert update_events[0].actor == "ops_manager_001"
        assert update_events[0].outcome == "granted"

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


def test_platform_console_approval_reject_form_does_not_execute_retry() -> None:
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
        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )
        approval_id = retry.json()["record"]["approval_id"]

        rejected = client.post(
            f"/platform/operation-approvals/{approval_id}/reject-form",
            data={
                "decided_by": "ops_manager_001",
                "decision_reason": "Rejected from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "reject_operation_approval",
            },
            follow_redirects=False,
        )
        console = client.get(rejected.headers["location"])

        assert rejected.status_code == 303
        assert rejected.headers["location"] == "/platform/view?approval_status=rejected"
        assert "Operation approval rejected." in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_REJECTED
        assert saved[0].approved_by == "ops_manager_001"
        assert saved[0].approval_reason == "Rejected from console"

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            run = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert run.status == "failed"

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
        _remove_database(operation_approval_database_path)


def test_platform_console_approval_cancel_form_does_not_execute_retry() -> None:
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
        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )
        approval_id = retry.json()["record"]["approval_id"]

        cancelled = client.post(
            f"/platform/operation-approvals/{approval_id}/cancel-form",
            data={
                "decided_by": "ops_user_001",
                "decision_reason": "Cancelled from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "cancel_operation_approval",
            },
            follow_redirects=False,
        )
        console = client.get(cancelled.headers["location"])

        assert cancelled.status_code == 303
        assert (
            cancelled.headers["location"]
            == "/platform/view?approval_status=cancelled"
        )
        assert "Operation approval cancelled." in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_CANCELLED
        assert saved[0].approved_by == "ops_user_001"
        assert saved[0].approval_reason == "Cancelled from console"

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            run = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert run.status == "failed"

        update_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(update_events) == 1
        assert update_events[0].actor == "ops_user_001"
        assert update_events[0].outcome == "granted"
        assert update_events[0].reason == "cancelled"

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
        _remove_database(operation_approval_database_path)


def test_platform_console_approval_expire_form_does_not_execute_retry() -> None:
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
        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )
        approval_id = retry.json()["record"]["approval_id"]

        expired = client.post(
            f"/platform/operation-approvals/{approval_id}/expire-form",
            data={
                "decided_by": "system_scheduler",
                "decision_reason": "Expired from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "expire_operation_approval",
            },
            follow_redirects=False,
        )
        console = client.get(expired.headers["location"])

        assert expired.status_code == 303
        assert expired.headers["location"] == "/platform/view?approval_status=expired"
        assert "Operation approval expired." in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_EXPIRED
        assert saved[0].approved_by == "system_scheduler"
        assert saved[0].approval_reason == "Expired from console"

        async_store = SQLitePlatformAsyncRunStore(async_database_path)
        try:
            run = async_store.get_run("run_retry_http")
        finally:
            async_store.close()
        assert run.status == "failed"

        update_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(update_events) == 1
        assert update_events[0].actor == "system_scheduler"
        assert update_events[0].outcome == "granted"
        assert update_events[0].reason == "expired"

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
        _remove_database(operation_approval_database_path)


def test_platform_console_approval_form_reports_confirmation_error() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        response = client.post(
            "/platform/operation-approvals/approval_pending_001/approve-form",
            data={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "wrong_confirmation",
            },
            follow_redirects=False,
        )
        console = client.get(response.headers["location"])

        assert response.status_code == 303
        assert response.headers["location"].startswith("/platform/view?approval_error=")
        assert "Approval update failed:" in console.text
        assert "confirmation must be approve_operation_approval" in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_PENDING
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_approval_cancel_form_reports_confirmation_error() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        response = client.post(
            "/platform/operation-approvals/approval_pending_001/cancel-form",
            data={
                "decided_by": "ops_user_001",
                "decision_reason": "Cancelled from console",
                "decided_at": "2026-06-08T10:00:00+00:00",
                "confirmation": "wrong_confirmation",
            },
            follow_redirects=False,
        )
        console = client.get(response.headers["location"])

        assert response.status_code == 303
        assert response.headers["location"].startswith("/platform/view?approval_error=")
        assert "Approval update failed:" in console.text
        assert "confirmation must be cancel_operation_approval" in console.text

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_PENDING
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
