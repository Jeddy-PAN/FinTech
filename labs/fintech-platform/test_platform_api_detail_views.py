from __future__ import annotations

from platform_api_app import (
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_OPERATION_APPROVALS,
    VIEW_PLATFORM_PAYMENT_RUN,
)
from test_platform_api_helpers import (
    _access_events,
    _client_with_async,
    _client_with_async_and_operation_approval,
    _fail_async_run,
    _payload,
    _pending_approval_payload,
    _remove_database,
    _retry_payload,
)


def test_platform_async_run_detail_view_links_to_platform_result() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        accepted = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_detail", order_id="order_async_detail"),
        )
        processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )
        detail = client.get(
            "/platform/async-payment-runs/run_async_detail/view",
            headers={"x-actor-id": "async_detail_viewer_001"},
        )

        assert accepted.status_code == 202
        assert processed.status_code == 200
        assert detail.status_code == 200
        assert detail.headers["content-type"].startswith("text/html")
        body = detail.text
        assert "Async Run Detail" in body
        assert "Request Payload" in body
        assert "Platform Result Summary" in body
        assert "run_async_detail" in body
        assert "order_async_detail" in body
        assert "/platform/payment-runs/run_async_detail/view" in body
        assert "Back to Console" in body

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == VIEW_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert events[-1].actor == "async_detail_viewer_001"
        assert events[-1].outcome == "granted"
        assert events[-1].reason == "view detail"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_payment_run_detail_view_shows_audit_timeline() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        accepted = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_payment_detail", order_id="order_payment_detail"),
        )
        processed = client.post("/platform/async-worker/process-next")
        detail = client.get(
            "/platform/payment-runs/run_payment_detail/view",
            headers={"x-actor-id": "payment_detail_viewer_001"},
        )

        assert accepted.status_code == 202
        assert processed.status_code == 200
        assert detail.status_code == 200
        assert detail.headers["content-type"].startswith("text/html")
        body = detail.text
        assert "Payment Run Detail" in body
        assert "Platform Result" in body
        assert "Associated Async Run" in body
        assert "Ledger Reconciliation Context" in body
        assert "Customer Audit Timeline" in body
        assert "run_payment_detail" in body
        assert "order_payment_detail" in body
        assert "/platform/async-payment-runs/run_payment_detail/view" in body
        assert "completed_ledger_amount_matches_payment_order" in body
        assert "completed_balances_match_ledger_amount" in body
        assert "Payment amount matches ledger amount" in body
        assert "Platform bank and user wallet balances match ledger amount" in body
        assert "payment_order.succeeded" in body
        assert "ledger_transaction.posted" in body
        assert "Back to Console" in body

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == VIEW_PLATFORM_PAYMENT_RUN
        ]
        assert events[-1].actor == "payment_detail_viewer_001"
        assert events[-1].outcome == "granted"
        assert events[-1].reason == "view detail"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


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
        assert "Lifecycle Timeline" in body
        assert "approval_requested" in body
        assert "ops_user_001" in body
        assert "Associated Async Run" in body
        assert "run_detail_completed" in body
        assert "/platform/async-payment-runs/run_detail_completed/view" in body
        assert "completed" in body
        assert "Platform Result Summary" in body
        assert "order_detail_completed" in body
        assert "/platform/payment-runs/run_detail_completed/view" in body
        assert "Back to Console" in body

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


def test_platform_operation_approval_detail_view_shows_retry_execution_timeline() -> None:
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
        approved = client.patch(
            f"/platform/operation-approvals/{approval_id}/approve",
            json={
                "decided_by": "ops_manager_001",
                "decision_reason": "Approved retry after reviewing timeline",
                "decided_at": "2026-06-08T10:00:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )
        detail = client.get(
            f"/platform/operation-approvals/{approval_id}/view",
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert retry.status_code == 202
        assert approved.status_code == 200
        assert detail.status_code == 200
        body = detail.text
        assert "Lifecycle Timeline" in body
        assert "approval_requested" in body
        assert "approval_decided" in body
        assert "retry_execution" in body
        assert "ops_user_001" in body
        assert "ops_manager_001" in body
        assert "Approved retry after reviewing timeline" in body
        assert f"approval_id={approval_id}" in body
        assert "requested_by=ops_user_001" in body
        assert "approval_reason=Approved retry after reviewing timeline" in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)

