from __future__ import annotations

from datetime import datetime, timezone

from platform_api_app import (
    CREATE_PLATFORM_OPERATION_APPROVALS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    UPDATE_PLATFORM_OPERATION_APPROVALS,
    VIEW_PLATFORM_OPERATION_APPROVALS,
)
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
    _client_with_async_and_operation_approval,
    _fail_async_run,
    _payload,
    _pending_approval_payload,
    _remove_database,
    _save_pending_approval,
)


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
        first_page = client.get(
            "/platform/operation-approvals",
            params={
                "sort_by": "requested_at",
                "sort_order": "desc",
                "limit": "2",
                "offset": "0",
            },
            headers={"x-actor-id": "approval_viewer_001"},
        )
        invalid_sort = client.get(
            "/platform/operation-approvals",
            params={"sort_by": "created_at"},
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert listed.status_code == 200
        assert first_page.status_code == 200
        body = listed.json()
        assert [record["approval_id"] for record in body["records"]] == [
            "approval_middle",
            "approval_oldest",
        ]
        assert body["pagination"] == {
            "limit": 2,
            "offset": 1,
            "returned_count": 2,
            "total_count": 3,
            "has_next_page": False,
            "next_offset": None,
            "sort_by": "requested_at",
            "sort_order": "desc",
        }
        first_page_body = first_page.json()
        assert [record["approval_id"] for record in first_page_body["records"]] == [
            "approval_newest",
            "approval_middle",
        ]
        assert first_page_body["pagination"] == {
            "limit": 2,
            "offset": 0,
            "returned_count": 2,
            "total_count": 3,
            "has_next_page": True,
            "next_offset": 2,
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
        assert [event.outcome for event in events] == [
            "granted",
            "granted",
            "denied",
        ]
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
        duplicate = client.patch(
            "/platform/operation-approvals/approval_pending_001/approve",
            json={
                "decided_by": "ops_manager_002",
                "decision_reason": "Concurrent duplicate retry approval",
                "decided_at": "2026-06-08T09:35:00Z",
            },
            headers={"x-actor-id": "ops_manager_002"},
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
        assert duplicate.status_code == 409
        assert "Cannot approve approved" in duplicate.json()["detail"]["message"]

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_APPROVED
        assert saved[0].approved_by == "ops_manager_001"

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 2
        assert events[0].actor == "ops_manager_001"
        assert events[0].outcome == "granted"
        assert events[1].actor == "ops_manager_002"
        assert events[1].outcome == "denied"

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


def test_platform_api_denies_approval_update_for_viewer_role() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        response = client.patch(
            "/platform/operation-approvals/approval_pending_001/approve",
            json={
                "decided_by": "approval_viewer_001",
                "decision_reason": "Viewer should not approve",
                "decided_at": "2026-06-08T09:30:00Z",
            },
            headers={"x-actor-id": "approval_viewer_001"},
        )

        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "PermissionDenied"
        assert "required_permission=update_platform_operation_approvals" in response.json()[
            "detail"
        ]["message"]

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_PENDING

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 1
        assert events[0].actor == "approval_viewer_001"
        assert events[0].outcome == "denied"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(operation_approval_database_path)


def test_platform_api_denies_approval_update_when_identity_mismatches_decider() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    ) = _client_with_async_and_operation_approval()
    try:
        _save_pending_approval(operation_approval_database_path)

        response = client.patch(
            "/platform/operation-approvals/approval_pending_001/reject",
            json={
                "decided_by": "ops_manager_002",
                "decision_reason": "Header actor should match decided_by",
                "decided_at": "2026-06-08T09:30:00Z",
            },
            headers={"x-actor-id": "ops_manager_001"},
        )

        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "IdentityMismatch"
        assert "x-actor-id=ops_manager_001" in response.json()["detail"]["message"]
        assert "decided_by=ops_manager_002" in response.json()["detail"]["message"]

        saved = _approval_records(operation_approval_database_path)
        assert saved[0].status == OPERATION_APPROVAL_PENDING

        events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_OPERATION_APPROVALS
        ]
        assert len(events) == 1
        assert events[0].actor == "ops_manager_001"
        assert events[0].outcome == "denied"
        assert "identity mismatch" in events[0].reason
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
