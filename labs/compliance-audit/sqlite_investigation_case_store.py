from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import AuditAccessEvent, ComplianceAuditError
from compliance_investigation_cases import (
    INVESTIGATION_FALSE_POSITIVE,
    INVESTIGATION_INVESTIGATING,
    INVESTIGATION_OPEN,
    INVESTIGATION_RESOLVED,
    AccessAnomalyInvestigationCase,
)


class SQLiteInvestigationCaseStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(str(database_path))
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def cases(self) -> tuple[AccessAnomalyInvestigationCase, ...]:
        rows = self._connection.execute(
            """
            SELECT case_id
            FROM access_investigation_cases
            ORDER BY created_at, case_id
            """
        ).fetchall()
        return tuple(self.get_case(row["case_id"]) for row in rows)

    @property
    def open_cases(self) -> tuple[AccessAnomalyInvestigationCase, ...]:
        return self.query_cases(statuses=(INVESTIGATION_OPEN, INVESTIGATION_INVESTIGATING))

    def save_case(self, investigation_case: AccessAnomalyInvestigationCase) -> None:
        row = self._case_to_row(investigation_case)
        event_rows = [
            self._event_to_row(investigation_case.case_id, sequence, event)
            for sequence, event in enumerate(investigation_case.finding.events, start=1)
        ]
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO access_investigation_cases (
                    case_id,
                    finding_type,
                    actor,
                    severity,
                    event_count,
                    finding_reason,
                    first_occurred_at,
                    last_occurred_at,
                    status,
                    created_at,
                    opened_by,
                    assigned_to,
                    investigation_started_at,
                    closed_by,
                    closed_at,
                    resolution_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    finding_type = excluded.finding_type,
                    actor = excluded.actor,
                    severity = excluded.severity,
                    event_count = excluded.event_count,
                    finding_reason = excluded.finding_reason,
                    first_occurred_at = excluded.first_occurred_at,
                    last_occurred_at = excluded.last_occurred_at,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    opened_by = excluded.opened_by,
                    assigned_to = excluded.assigned_to,
                    investigation_started_at = excluded.investigation_started_at,
                    closed_by = excluded.closed_by,
                    closed_at = excluded.closed_at,
                    resolution_reason = excluded.resolution_reason
                """,
                row,
            )
            self._connection.execute(
                "DELETE FROM access_investigation_case_events WHERE case_id = ?",
                (investigation_case.case_id,),
            )
            self._connection.executemany(
                """
                INSERT INTO access_investigation_case_events (
                    case_id,
                    sequence,
                    event_type,
                    actor,
                    permission,
                    target,
                    outcome,
                    occurred_at,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                event_rows,
            )

    def get_case(self, case_id: str) -> AccessAnomalyInvestigationCase:
        row = self._connection.execute(
            """
            SELECT
                case_id,
                finding_type,
                actor,
                severity,
                event_count,
                finding_reason,
                first_occurred_at,
                last_occurred_at,
                status,
                created_at,
                opened_by,
                assigned_to,
                investigation_started_at,
                closed_by,
                closed_at,
                resolution_reason
            FROM access_investigation_cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        if row is None:
            raise ComplianceAuditError(f"Unknown investigation case: {case_id}")
        return self._case_from_row(row)

    def query_cases(
        self,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
        assigned_to: str | None = None,
        actor: str | None = None,
    ) -> tuple[AccessAnomalyInvestigationCase, ...]:
        conditions: list[str] = []
        parameters: list[str] = []
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status)
        if statuses is not None:
            if not statuses:
                return ()
            placeholders = ", ".join("?" for _ in statuses)
            conditions.append(f"status IN ({placeholders})")
            parameters.extend(statuses)
        if assigned_to is not None:
            conditions.append("assigned_to = ?")
            parameters.append(assigned_to)
        if actor is not None:
            conditions.append("actor = ?")
            parameters.append(actor)

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._connection.execute(
            f"""
            SELECT case_id
            FROM access_investigation_cases
            {where_sql}
            ORDER BY created_at, case_id
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(self.get_case(row["case_id"]) for row in rows)

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS access_investigation_cases (
                    case_id TEXT PRIMARY KEY,
                    finding_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    finding_reason TEXT NOT NULL,
                    first_occurred_at TEXT NOT NULL,
                    last_occurred_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('open', 'investigating', 'resolved', 'false_positive')
                    ),
                    created_at TEXT NOT NULL,
                    opened_by TEXT NOT NULL,
                    assigned_to TEXT,
                    investigation_started_at TEXT,
                    closed_by TEXT,
                    closed_at TEXT,
                    resolution_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS access_investigation_case_events (
                    case_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    target TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    reason TEXT,
                    PRIMARY KEY (case_id, sequence),
                    FOREIGN KEY (case_id) REFERENCES access_investigation_cases(case_id)
                );

                CREATE INDEX IF NOT EXISTS idx_access_investigation_cases_status
                ON access_investigation_cases (status, created_at);

                CREATE INDEX IF NOT EXISTS idx_access_investigation_cases_actor
                ON access_investigation_cases (actor, created_at);
                """
            )

    def _case_to_row(
        self,
        investigation_case: AccessAnomalyInvestigationCase,
    ) -> tuple:
        finding = investigation_case.finding
        _validate_status(investigation_case.status)
        return (
            _require_text(investigation_case.case_id, "case_id"),
            _require_text(finding.finding_type, "finding_type"),
            _require_text(finding.actor, "actor"),
            _require_text(finding.severity, "severity"),
            finding.event_count,
            _require_text(finding.reason, "finding_reason"),
            _timestamp_to_storage(finding.first_occurred_at, "first_occurred_at"),
            _timestamp_to_storage(finding.last_occurred_at, "last_occurred_at"),
            investigation_case.status,
            _timestamp_to_storage(investigation_case.created_at, "created_at"),
            _require_text(investigation_case.opened_by, "opened_by"),
            _optional_text(investigation_case.assigned_to),
            _optional_timestamp_to_storage(
                investigation_case.investigation_started_at,
                "investigation_started_at",
            ),
            _optional_text(investigation_case.closed_by),
            _optional_timestamp_to_storage(investigation_case.closed_at, "closed_at"),
            _optional_text(investigation_case.resolution_reason),
        )

    def _event_to_row(
        self,
        case_id: str,
        sequence: int,
        event: AuditAccessEvent,
    ) -> tuple:
        return (
            case_id,
            sequence,
            _require_text(event.event_type, "event_type"),
            _require_text(event.actor, "event.actor"),
            _require_text(event.permission, "permission"),
            _require_text(event.target, "target"),
            _require_text(event.outcome, "outcome"),
            _timestamp_to_storage(event.occurred_at, "occurred_at"),
            event.reason,
        )

    def _case_from_row(self, row: sqlite3.Row) -> AccessAnomalyInvestigationCase:
        events = self._events_for_case(row["case_id"])
        finding = AccessAnomalyFinding(
            finding_type=row["finding_type"],
            actor=row["actor"],
            severity=row["severity"],
            event_count=row["event_count"],
            reason=row["finding_reason"],
            first_occurred_at=datetime.fromisoformat(row["first_occurred_at"]),
            last_occurred_at=datetime.fromisoformat(row["last_occurred_at"]),
            events=events,
        )
        return AccessAnomalyInvestigationCase(
            case_id=row["case_id"],
            finding=finding,
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            opened_by=row["opened_by"],
            assigned_to=row["assigned_to"],
            investigation_started_at=_optional_datetime_from_row(
                row["investigation_started_at"]
            ),
            closed_by=row["closed_by"],
            closed_at=_optional_datetime_from_row(row["closed_at"]),
            resolution_reason=row["resolution_reason"],
        )

    def _events_for_case(self, case_id: str) -> tuple[AuditAccessEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                event_type,
                actor,
                permission,
                target,
                outcome,
                occurred_at,
                reason
            FROM access_investigation_case_events
            WHERE case_id = ?
            ORDER BY sequence
            """,
            (case_id,),
        ).fetchall()
        return tuple(
            AuditAccessEvent(
                event_type=row["event_type"],
                actor=row["actor"],
                permission=row["permission"],
                target=row["target"],
                outcome=row["outcome"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                reason=row["reason"],
            )
            for row in rows
        )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ComplianceAuditError(f"{field_name} is required")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_status(status: str) -> None:
    if status not in {
        INVESTIGATION_OPEN,
        INVESTIGATION_INVESTIGATING,
        INVESTIGATION_RESOLVED,
        INVESTIGATION_FALSE_POSITIVE,
    }:
        raise ComplianceAuditError(f"Unknown investigation case status: {status}")


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ComplianceAuditError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _optional_timestamp_to_storage(value: datetime | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _timestamp_to_storage(value, field_name)


def _optional_datetime_from_row(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)
