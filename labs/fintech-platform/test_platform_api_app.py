from __future__ import annotations

from platform_api_app import (
    CHECK_PLATFORM_OPERABILITY_READINESS,
    CREATE_PLATFORM_PAYMENT_RUN,
    VIEW_PLATFORM_OPERABILITY_METRICS,
    VIEW_PLATFORM_TEST_MATRIX,
)
from test_platform_api_helpers import (
    _access_events,
    _client,
    _client_with_operability,
    _payload,
    _remove_database,
)


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


def test_platform_operability_readiness_metrics_and_test_matrix() -> None:
    (
        client,
        database_path,
        access_audit_database_path,
        async_database_path,
        investigation_database_path,
        operation_approval_database_path,
    ) = _client_with_operability()
    try:
        created = client.post("/platform/payment-runs", json=_payload())
        readiness = client.get(
            "/platform/operability/readiness",
            headers={"x-actor-id": "audit_reader_001"},
        )
        denied_readiness = client.get(
            "/platform/operability/readiness",
            headers={"x-actor-id": "api_viewer_001"},
        )
        metrics = client.get(
            "/platform/operability/metrics",
            headers={"x-actor-id": "audit_reader_001"},
        )
        test_matrix = client.get(
            "/platform/operability/test-matrix",
            headers={"x-actor-id": "audit_reader_001"},
        )

        assert created.status_code == 201
        assert readiness.status_code == 200
        readiness_body = readiness.json()
        assert readiness_body["status"] == "ready"
        assert {check["name"] for check in readiness_body["checks"]} == {
            "platform_store",
            "access_audit_store",
            "async_run_store",
            "investigation_case_store",
            "operation_approval_store",
        }
        assert {check["status"] for check in readiness_body["checks"]} == {"passed"}
        assert denied_readiness.status_code == 403

        assert metrics.status_code == 200
        metric_values = {
            metric["name"]: metric["value"]
            for metric in metrics.json()["metrics"]
        }
        assert metric_values["platform.payment_runs.total"] == 1
        assert metric_values["platform.payment_runs.completed"] == 1
        assert metric_values["platform.access_events.denied"] == 1
        assert metric_values["platform.operation_approvals.pending"] == 0

        assert test_matrix.status_code == 200
        rows = test_matrix.json()["rows"]
        assert [row["area"] for row in rows] == [
            "syntax",
            "platform tests",
            "demo",
            "full labs",
        ]
        assert rows[1]["command"].endswith(
            "-m pytest -p no:cacheprovider .\\labs\\fintech-platform -q"
        )

        events = _access_events(access_audit_database_path)
        permissions = [event.permission for event in events]
        assert CHECK_PLATFORM_OPERABILITY_READINESS in permissions
        assert VIEW_PLATFORM_OPERABILITY_METRICS in permissions
        assert VIEW_PLATFORM_TEST_MATRIX in permissions
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
        _remove_database(investigation_database_path)
        _remove_database(operation_approval_database_path)


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


def test_platform_api_denies_access_audit_view_for_unprivileged_role() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        client.post("/platform/payment-runs", json=_payload())

        response = client.get(
            "/platform/api-access-events",
            headers={"x-actor-id": "api_viewer_001"},
        )

        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "PermissionDenied"
        assert "required_permission=view_platform_api_access_events" in response.json()[
            "detail"
        ]["message"]

        denied_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == "view_platform_api_access_events"
        ]
        assert len(denied_events) == 1
        assert denied_events[0].actor == "api_viewer_001"
        assert denied_events[0].outcome == "denied"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_api_allows_explicit_audit_reader_role() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        client.post("/platform/payment-runs", json=_payload())

        response = client.get(
            "/platform/api-access-events",
            headers={
                "x-actor-id": "support_user_001",
                "x-actor-role": "audit_reader",
            },
        )

        assert response.status_code == 200
        assert response.json()["events"]

        audit_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == "view_platform_api_access_events"
        ]
        assert len(audit_events) == 1
        assert audit_events[0].actor == "support_user_001"
        assert audit_events[0].outcome == "granted"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_manual_page_renders_workflows_and_records_access() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        manual = client.get(
            "/platform/manual",
            headers={"x-actor-id": "console_reader_001"},
        )

        assert manual.status_code == 200
        assert manual.headers["content-type"].startswith("text/html")
        body = manual.text
        assert "Platform User Manual" in body
        assert "Manual Sections" in body
        assert "What This Platform Does" in body
        assert "Platform Capabilities" in body
        assert "Payment Workflow" in body
        assert "Async Workflow" in body
        assert "Approval Workflow" in body
        assert "Detailed Event Flow" in body
        assert "Request intake" in body
        assert 'href="/platform/manual?lang=cn"' in body
        assert "Evidence Packages" in body
        assert "Educational Boundary" in body
        assert 'href="/platform/view"' in body

        events = _access_events(access_audit_database_path)
        assert len(events) == 1
        assert events[0].actor == "console_reader_001"
        assert events[0].permission == "view_platform_console"
        assert events[0].target == "fintech_platform_manual"
        assert events[0].outcome == "granted"
        assert events[0].reason == "view manual"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_platform_manual_page_supports_chinese_language_view() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        manual = client.get("/platform/manual?lang=cn")

        assert manual.status_code == 200
        body = manual.text
        assert "平台用户手册" in body
        assert "手册目录" in body
        assert "详细流程图" in body
        assert "请求进入平台" in body
        assert 'href="/platform/manual?lang=en"' in body

        events = _access_events(access_audit_database_path)
        assert len(events) == 1
        assert events[0].target == "fintech_platform_manual"
        assert events[0].reason == "view manual"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
