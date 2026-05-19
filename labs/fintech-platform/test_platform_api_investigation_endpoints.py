from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api_app import (
    CREATE_PLATFORM_API_INVESTIGATION_CASES,
    UPDATE_PLATFORM_API_INVESTIGATION_CASES,
    VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS,
    VIEW_PLATFORM_API_INVESTIGATION_CASES,
    create_app,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore


def test_platform_api_lists_api_access_anomaly_findings() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        _seed_repeated_missing_run_lookups(client)

        response = client.get(
            "/platform/api-access-anomaly-findings",
            headers={"x-actor-id": "api_audit_reader_001"},
        )

        assert response.status_code == 200
        findings = response.json()["findings"]
        assert len(findings) == 1
        assert findings[0]["finding_type"] == "repeated_denied_access"
        assert findings[0]["actor"] == "api_viewer_404"
        assert findings[0]["event_count"] == 3
        assert findings[0]["events"][0]["target"].startswith(
            "fintech_platform_api_payment_runs/missing_"
        )

        assert _access_events(access_audit_database_path)[-1].permission == (
            VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS
        )
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_opens_and_lists_api_investigation_cases() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        _seed_repeated_missing_run_lookups(client)

        created = client.post(
            "/platform/api-access-investigation-cases",
            headers={"x-actor-id": "api_compliance_lead_001"},
        )
        listed = client.get(
            "/platform/api-access-investigation-cases?status=open&actor=api_viewer_404",
            headers={"x-actor-id": "api_case_reader_001"},
        )

        assert created.status_code == 200
        created_cases = created.json()["cases"]
        assert len(created_cases) == 1
        assert created_cases[0]["status"] == "open"
        assert created_cases[0]["opened_by"] == "api_compliance_lead_001"
        assert created_cases[0]["finding"]["actor"] == "api_viewer_404"

        assert listed.status_code == 200
        listed_cases = listed.json()["cases"]
        assert [case["case_id"] for case in listed_cases] == [
            created_cases[0]["case_id"],
        ]

        permissions = [event.permission for event in _access_events(access_audit_database_path)]
        assert CREATE_PLATFORM_API_INVESTIGATION_CASES in permissions
        assert VIEW_PLATFORM_API_INVESTIGATION_CASES in permissions
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_gets_single_api_investigation_case_and_404s_missing_case() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        _seed_repeated_missing_run_lookups(client)
        created = client.post(
            "/platform/api-access-investigation-cases",
            headers={"x-actor-id": "api_compliance_lead_001"},
        )
        case_id = created.json()["cases"][0]["case_id"]

        fetched = client.get(
            f"/platform/api-access-investigation-cases/{case_id}",
            headers={"x-actor-id": "api_case_reader_001"},
        )
        missing = client.get(
            "/platform/api-access-investigation-cases/missing_case",
            headers={"x-actor-id": "api_case_reader_001"},
        )

        assert fetched.status_code == 200
        assert fetched.json()["case"]["case_id"] == case_id
        assert fetched.json()["case"]["finding"]["event_count"] == 3
        assert missing.status_code == 404
        assert missing.json()["detail"]["error"] == "ComplianceAuditError"

        assert _access_events(access_audit_database_path)[-1].outcome == "denied"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_starts_and_resolves_api_investigation_case() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        case_id = _opened_case_id(client)

        started = client.patch(
            f"/platform/api-access-investigation-cases/{case_id}/start",
            json={
                "assigned_to": "api_investigator_001",
                "started_at": "2026-05-19T13:10:00Z",
            },
            headers={"x-actor-id": "api_case_manager_001"},
        )
        resolved = client.patch(
            f"/platform/api-access-investigation-cases/{case_id}/resolve",
            json={
                "closed_by": "api_investigator_001",
                "reason": "Reviewed repeated missing-run lookups",
                "closed_at": "2026-05-19T14:00:00Z",
            },
            headers={"x-actor-id": "api_case_manager_001"},
        )

        assert started.status_code == 200
        assert started.json()["case"]["status"] == "investigating"
        assert started.json()["case"]["assigned_to"] == "api_investigator_001"
        assert resolved.status_code == 200
        assert resolved.json()["case"]["status"] == "resolved"
        assert resolved.json()["case"]["closed_by"] == "api_investigator_001"

        fetched = client.get(
            f"/platform/api-access-investigation-cases/{case_id}",
            headers={"x-actor-id": "api_case_reader_001"},
        )
        assert fetched.json()["case"]["status"] == "resolved"

        update_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == UPDATE_PLATFORM_API_INVESTIGATION_CASES
        ]
        assert [event.reason for event in update_events] == [
            "started",
            "resolved",
        ]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_starts_and_marks_api_investigation_case_false_positive() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        case_id = _opened_case_id(client)

        started = client.patch(
            f"/platform/api-access-investigation-cases/{case_id}/start",
            json={
                "assigned_to": "api_investigator_001",
                "started_at": "2026-05-19T13:10:00Z",
            },
            headers={"x-actor-id": "api_case_manager_001"},
        )
        false_positive = client.patch(
            f"/platform/api-access-investigation-cases/{case_id}/false-positive",
            json={
                "closed_by": "api_investigator_001",
                "reason": "Confirmed sample traffic",
                "closed_at": "2026-05-19T14:00:00Z",
            },
            headers={"x-actor-id": "api_case_manager_001"},
        )

        assert started.status_code == 200
        assert false_positive.status_code == 200
        assert false_positive.json()["case"]["status"] == "false_positive"
        assert false_positive.json()["case"]["resolution_reason"] == (
            "Confirmed sample traffic"
        )
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def test_platform_api_rejects_invalid_api_investigation_case_transition() -> None:
    client, database_path, access_audit_database_path, investigation_database_path = (
        _client()
    )
    try:
        case_id = _opened_case_id(client)

        response = client.patch(
            f"/platform/api-access-investigation-cases/{case_id}/resolve",
            json={
                "closed_by": "api_investigator_001",
                "reason": "Cannot resolve before start",
                "closed_at": "2026-05-19T14:00:00Z",
            },
            headers={"x-actor-id": "api_case_manager_001"},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "ComplianceAuditError"
        assert "must be investigating" in response.json()["detail"]["message"]
        assert _access_events(access_audit_database_path)[-1].outcome == "denied"
        assert _access_events(access_audit_database_path)[-1].permission == (
            UPDATE_PLATFORM_API_INVESTIGATION_CASES
        )
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(investigation_database_path)


def _seed_repeated_missing_run_lookups(client: TestClient) -> None:
    for run_id in ("missing_001", "missing_002", "missing_003"):
        response = client.get(
            f"/platform/payment-runs/{run_id}",
            headers={"x-actor-id": "api_viewer_404"},
        )
        assert response.status_code == 404


def _opened_case_id(client: TestClient) -> str:
    _seed_repeated_missing_run_lookups(client)
    created = client.post(
        "/platform/api-access-investigation-cases",
        headers={"x-actor-id": "api_compliance_lead_001"},
    )
    assert created.status_code == 200
    return created.json()["cases"][0]["case_id"]


def _client():
    database_path = _database_path("platform-api-investigation-endpoint")
    access_audit_database_path = _database_path(
        "platform-api-investigation-endpoint-access-audit"
    )
    investigation_database_path = _database_path(
        "platform-api-investigation-endpoint-cases"
    )
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


def _database_path(prefix: str) -> Path:
    return _test_data_directory() / f"{prefix}-{uuid4()}.db"


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
