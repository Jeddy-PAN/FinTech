from __future__ import annotations

from datetime import datetime, timezone

from platform_operation_approval import SQLiteOperationApprovalStore

from test_platform_api_helpers import (
    _access_events,
    _client_with_async,
    _client_with_async_and_investigation,
    _client_with_async_and_operation_approval,
    _client_with_investigation,
    _fail_async_run,
    _payload,
    _remove_database,
    _retry_payload,
    _save_pending_approval,
    create_failed_async_run_sample,
)


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
        assert 'href="/platform/manual"' in body
        assert "Manual" in body
        assert "API access anomalies" in body
        assert "Investigation cases" in body
        assert "run_http_001" in body
        assert "run_async_http_001" in body
        assert "/platform/payment-runs/run_http_001/view" in body
        assert "/platform/async-payment-runs/run_async_http_001/view" in body
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
        assert 'href="/platform/manual"' in body
        assert "Console Sections" in body
        assert 'href="#payment-runs"' in body
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


def test_platform_console_renders_operations_and_approval_report_views() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
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
        assert "/platform/async-payment-runs/run_retry_http/view" in body
        assert "/platform/payment-runs/run_console_completed/view" in body
        assert "Operation Approval Summary" in body
        assert "Pending Operation Approvals" in body
        assert "Approval Records" in body
        assert "pending_count" in body
        assert "Pending approvals" in body
        assert "approved_count" in body
        assert "self_approval_rejected_count" in body
        assert pending_approval_id in body
        assert f"/platform/operation-approvals/{pending_approval_id}/view" in body
        assert (
            f'action="/platform/operation-approvals/{pending_approval_id}/approve-form"'
            in body
        )
        assert (
            f'action="/platform/operation-approvals/{pending_approval_id}/reject-form"'
            in body
        )
        assert (
            f'action="/platform/operation-approvals/{pending_approval_id}/cancel-form"'
            in body
        )
        assert (
            f'action="/platform/operation-approvals/{pending_approval_id}/expire-form"'
            in body
        )
        assert "approve_operation_approval" in body
        assert "reject_operation_approval" in body
        assert "cancel_operation_approval" in body
        assert "expire_operation_approval" in body
        assert "High-impact approval actions can change retry eligibility" in body
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


def test_platform_console_filters_operation_tables() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        completed = client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_console_completed",
                order_id="order_console_completed",
            ),
        )
        review = client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_console_review",
                order_id="order_console_review",
                amount="1500.00",
            ),
        )
        assert completed.status_code == 201
        assert review.status_code == 201

        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_async_failed", order_id="order_async_failed"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
            run_id="run_async_failed",
        )
        client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_async_accepted",
                order_id="order_async_accepted",
            ),
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_pending_filter",
            operation_id="run_async_failed",
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_approved_filter",
            operation_id="run_async_accepted",
        )
        approval_store = SQLiteOperationApprovalStore(
            operation_approval_database_path
        )
        try:
            approval_store.approve_pending(
                "approval_approved_filter",
                approved_by="ops_manager_001",
                approval_reason="Approved for filter test",
                decided_at=datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
            )
        finally:
            approval_store.close()

        console = client.get(
            "/platform/view",
            params={
                "payment_status": "risk_review_required",
                "async_status": "failed",
                "operation_approval_status": "pending",
            },
        )

        assert console.status_code == 200
        body = console.text
        assert '<option value="risk_review_required" selected>' in body
        assert '<option value="failed" selected>' in body
        assert '<option value="pending" selected>' in body
        assert "run_console_review" in body
        assert "run_console_completed" not in body
        assert "run_async_failed" in body
        assert "run_async_accepted" not in body
        assert "approval_pending_filter" in body
        assert "approval_approved_filter" not in body
        assert "Risk review runs" in body
        assert "Failed async runs" in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_filters_by_actor_across_payment_async_and_approvals() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        matching_payment = client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_actor_payment_match",
                order_id="order_actor_payment_match",
                actor="ops_user_001",
            ),
        )
        other_payment = client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_actor_payment_other",
                order_id="order_actor_payment_other",
                actor="api_client_002",
            ),
        )
        matching_async = client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_actor_async_match",
                order_id="order_actor_async_match",
                actor="ops_user_001",
            ),
        )
        other_async = client.post(
            "/platform/async-payment-runs",
            json=_payload(
                run_id="run_actor_async_other",
                order_id="order_actor_async_other",
                actor="api_client_002",
            ),
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_actor_match",
            operation_id="run_actor_async_match",
            requested_by="ops_user_001",
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_actor_other",
            operation_id="run_actor_async_other",
            requested_by="api_client_002",
        )

        console = client.get("/platform/view", params={"actor": "ops_user_001"})

        assert matching_payment.status_code == 201
        assert other_payment.status_code == 201
        assert matching_async.status_code == 202
        assert other_async.status_code == 202
        assert console.status_code == 200
        body = console.text
        assert 'name="actor"' in body
        assert 'value="ops_user_001"' in body
        assert "run_actor_payment_match" in body
        assert "run_actor_payment_other" not in body
        assert "run_actor_async_match" in body
        assert "run_actor_async_other" not in body
        assert "approval_actor_match" in body
        assert "approval_actor_other" not in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_filters_approvals_by_created_date_range() -> None:
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
            approval_id="approval_date_match",
            operation_id="run_date_match",
            requested_at=datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc),
        )
        _save_pending_approval(
            operation_approval_database_path,
            approval_id="approval_date_other",
            operation_id="run_date_other",
            requested_at=datetime(2026, 6, 7, 9, 0, tzinfo=timezone.utc),
        )

        console = client.get(
            "/platform/view",
            params={
                "operation_approval_status": "pending",
                "created_from": "2026-06-08",
                "created_to": "2026-06-08",
            },
        )

        assert console.status_code == 200
        body = console.text
        assert 'name="created_from"' in body
        assert 'name="created_to"' in body
        assert 'value="2026-06-08"' in body
        assert "approval_date_match" in body
        assert "approval_date_other" not in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_console_reports_invalid_filters_and_keeps_full_view() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        created = client.post(
            "/platform/payment-runs",
            json=_payload(
                run_id="run_console_completed",
                order_id="order_console_completed",
            ),
        )
        assert created.status_code == 201

        console = client.get(
            "/platform/view",
            params={
                "payment_status": "not_a_payment_status",
                "async_status": "not_an_async_status",
                "operation_approval_status": "not_an_approval_status",
                "created_from": "bad-date",
                "created_to": "2026-06-07",
            },
        )

        assert console.status_code == 200
        body = console.text
        assert "Console filter ignored invalid value:" in body
        assert "Unknown payment_status filter: not_a_payment_status" in body
        assert "Unknown async_status filter: not_an_async_status" in body
        assert (
            "Unknown operation_approval_status filter: not_an_approval_status"
            in body
        )
        assert "Invalid created_from filter: bad-date" in body
        assert "run_console_completed" in body
        assert '<option value="" selected>All</option>' in body
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)
