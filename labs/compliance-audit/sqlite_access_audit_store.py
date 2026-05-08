from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from compliance_audit import AuditAccessEvent, ComplianceAuditError


class SQLiteAccessAuditStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(str(database_path))
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def access_events(self) -> tuple[AuditAccessEvent, ...]:
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
            FROM audit_access_events
            ORDER BY occurred_at, rowid
            """
        ).fetchall()
        return tuple(self._access_event_from_row(row) for row in rows)

    def save_event(self, event: AuditAccessEvent) -> None:
        self.save_events((event,))

    def save_events(self, events: Iterable[AuditAccessEvent]) -> None:
        event_tuple = tuple(events)
        rows = [self._event_to_row(event) for event in event_tuple]
        with self._connection:
            self._connection.executemany(
                """
                INSERT INTO audit_access_events (
                    event_id,
                    event_type,
                    actor,
                    permission,
                    target,
                    outcome,
                    occurred_at,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def query_access_events(
        self,
        *,
        actor: str | None = None,
        permission: str | None = None,
        outcome: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[AuditAccessEvent, ...]:
        conditions: list[str] = []
        parameters: list[str] = []
        if actor is not None:
            conditions.append("actor = ?")
            parameters.append(actor)
        if permission is not None:
            conditions.append("permission = ?")
            parameters.append(permission)
        if outcome is not None:
            conditions.append("outcome = ?")
            parameters.append(outcome)
        if occurred_from is not None:
            conditions.append("occurred_at >= ?")
            parameters.append(_timestamp_to_storage(occurred_from, "occurred_from"))
        if occurred_to is not None:
            conditions.append("occurred_at <= ?")
            parameters.append(_timestamp_to_storage(occurred_to, "occurred_to"))
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._connection.execute(
            f"""
            SELECT
                event_type,
                actor,
                permission,
                target,
                outcome,
                occurred_at,
                reason
            FROM audit_access_events
            {where_sql}
            ORDER BY occurred_at, rowid
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(self._access_event_from_row(row) for row in rows)

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_access_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    target TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    reason TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_access_events_actor
                ON audit_access_events (actor, occurred_at);

                CREATE INDEX IF NOT EXISTS idx_audit_access_events_permission
                ON audit_access_events (permission, outcome, occurred_at);
                """
            )

    def _event_to_row(
        self,
        event: AuditAccessEvent,
    ) -> tuple[str, str, str, str, str, str, str, str | None]:
        return (
            str(uuid4()),
            _require_text(event.event_type, "event_type"),
            _require_text(event.actor, "actor"),
            _require_text(event.permission, "permission"),
            _require_text(event.target, "target"),
            _require_text(event.outcome, "outcome"),
            _timestamp_to_storage(event.occurred_at, "occurred_at"),
            event.reason,
        )

    def _access_event_from_row(self, row: sqlite3.Row) -> AuditAccessEvent:
        return AuditAccessEvent(
            event_type=row["event_type"],
            actor=row["actor"],
            permission=row["permission"],
            target=row["target"],
            outcome=row["outcome"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            reason=row["reason"],
        )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ComplianceAuditError(f"{field_name} is required")
    return normalized


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ComplianceAuditError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()
