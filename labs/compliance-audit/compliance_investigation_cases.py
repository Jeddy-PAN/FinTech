from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import ComplianceAuditError, ComplianceAuditEvent


INVESTIGATION_OPEN = "open"
INVESTIGATION_INVESTIGATING = "investigating"
INVESTIGATION_RESOLVED = "resolved"
INVESTIGATION_FALSE_POSITIVE = "false_positive"


@dataclass(frozen=True)
class AccessAnomalyInvestigationCase:
    case_id: str
    finding: AccessAnomalyFinding
    status: str
    created_at: datetime
    opened_by: str
    assigned_to: str | None = None
    investigation_started_at: datetime | None = None
    closed_by: str | None = None
    closed_at: datetime | None = None
    resolution_reason: str | None = None


class AccessAnomalyInvestigationService:
    def __init__(self) -> None:
        self._cases: dict[str, AccessAnomalyInvestigationCase] = {}
        self._audit_events: list[ComplianceAuditEvent] = []

    @property
    def cases(self) -> tuple[AccessAnomalyInvestigationCase, ...]:
        return tuple(sorted(self._cases.values(), key=_case_sort_key))

    @property
    def open_cases(self) -> tuple[AccessAnomalyInvestigationCase, ...]:
        return tuple(
            case
            for case in self.cases
            if case.status in {INVESTIGATION_OPEN, INVESTIGATION_INVESTIGATING}
        )

    @property
    def audit_events(self) -> tuple[ComplianceAuditEvent, ...]:
        return tuple(sorted(self._audit_events, key=_audit_event_sort_key))

    def create_case(
        self,
        finding: AccessAnomalyFinding,
        *,
        opened_by: str,
        created_at: datetime,
    ) -> AccessAnomalyInvestigationCase:
        opener = _required_text(opened_by, field_name="opened_by")
        timestamp = _validate_timestamp(created_at, field_name="created_at")
        case_id = investigation_case_id(finding)
        if case_id in self._cases:
            return self._cases[case_id]

        investigation_case = AccessAnomalyInvestigationCase(
            case_id=case_id,
            finding=finding,
            status=INVESTIGATION_OPEN,
            created_at=timestamp,
            opened_by=opener,
        )
        self._cases[case_id] = investigation_case
        self._record_audit_event(
            investigation_case,
            event_type="access_investigation_case.created",
            actor=opener,
            occurred_at=timestamp,
            reason=finding.reason,
        )
        return investigation_case

    def start_investigation(
        self,
        case_id: str,
        *,
        assigned_to: str,
        started_at: datetime,
    ) -> AccessAnomalyInvestigationCase:
        investigation_case = self._get_case(case_id)
        if investigation_case.status != INVESTIGATION_OPEN:
            raise ComplianceAuditError(
                f"Investigation case cannot be started from status: {investigation_case.status}"
            )

        updated_case = AccessAnomalyInvestigationCase(
            case_id=investigation_case.case_id,
            finding=investigation_case.finding,
            status=INVESTIGATION_INVESTIGATING,
            created_at=investigation_case.created_at,
            opened_by=investigation_case.opened_by,
            assigned_to=_required_text(assigned_to, field_name="assigned_to"),
            investigation_started_at=_validate_timestamp(
                started_at,
                field_name="started_at",
            ),
        )
        self._cases[case_id] = updated_case
        self._record_audit_event(
            updated_case,
            event_type="access_investigation_case.started",
            actor=updated_case.assigned_to,
            occurred_at=updated_case.investigation_started_at,
            reason=f"Investigation assigned to {updated_case.assigned_to}",
        )
        return updated_case

    def resolve(
        self,
        case_id: str,
        *,
        closed_by: str,
        reason: str,
        closed_at: datetime,
    ) -> AccessAnomalyInvestigationCase:
        return self._close_case(
            case_id,
            status=INVESTIGATION_RESOLVED,
            closed_by=closed_by,
            reason=reason,
            closed_at=closed_at,
        )

    def mark_false_positive(
        self,
        case_id: str,
        *,
        closed_by: str,
        reason: str,
        closed_at: datetime,
    ) -> AccessAnomalyInvestigationCase:
        return self._close_case(
            case_id,
            status=INVESTIGATION_FALSE_POSITIVE,
            closed_by=closed_by,
            reason=reason,
            closed_at=closed_at,
        )

    def _close_case(
        self,
        case_id: str,
        *,
        status: str,
        closed_by: str,
        reason: str,
        closed_at: datetime,
    ) -> AccessAnomalyInvestigationCase:
        investigation_case = self._get_case(case_id)
        if investigation_case.status != INVESTIGATION_INVESTIGATING:
            raise ComplianceAuditError(
                "Investigation case must be investigating before it can be closed"
            )

        updated_case = AccessAnomalyInvestigationCase(
            case_id=investigation_case.case_id,
            finding=investigation_case.finding,
            status=status,
            created_at=investigation_case.created_at,
            opened_by=investigation_case.opened_by,
            assigned_to=investigation_case.assigned_to,
            investigation_started_at=investigation_case.investigation_started_at,
            closed_by=_required_text(closed_by, field_name="closed_by"),
            closed_at=_validate_timestamp(closed_at, field_name="closed_at"),
            resolution_reason=_required_text(reason, field_name="reason"),
        )
        self._cases[case_id] = updated_case
        self._record_audit_event(
            updated_case,
            event_type=f"access_investigation_case.{status}",
            actor=updated_case.closed_by,
            occurred_at=updated_case.closed_at,
            reason=updated_case.resolution_reason,
        )
        return updated_case

    def _get_case(self, case_id: str) -> AccessAnomalyInvestigationCase:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise ComplianceAuditError(f"Unknown investigation case: {case_id}") from exc

    def _record_audit_event(
        self,
        investigation_case: AccessAnomalyInvestigationCase,
        *,
        event_type: str,
        actor: str,
        occurred_at: datetime,
        reason: str | None,
    ) -> None:
        self._audit_events.append(
            ComplianceAuditEvent(
                source_system="compliance",
                event_id=str(uuid4()),
                event_type=event_type,
                aggregate_type="access_investigation_case",
                aggregate_id=investigation_case.case_id,
                actor=actor,
                reason=reason,
                payload=_audit_payload(investigation_case),
                occurred_at=occurred_at,
            )
        )


def investigation_case_id(finding: AccessAnomalyFinding) -> str:
    timestamp = finding.first_occurred_at.isoformat().replace("+00:00", "Z")
    return f"access_investigation:{finding.finding_type}:{finding.actor}:{timestamp}"


def _required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ComplianceAuditError(f"{field_name} is required")
    return normalized


def _validate_timestamp(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ComplianceAuditError(f"{field_name} must be timezone-aware")
    return value


def _case_sort_key(investigation_case: AccessAnomalyInvestigationCase):
    return (
        investigation_case.created_at,
        investigation_case.finding.severity,
        investigation_case.case_id,
    )


def _audit_event_sort_key(event: ComplianceAuditEvent):
    return (
        event.occurred_at,
        event.event_type,
        event.aggregate_id,
        event.event_id,
    )


def _audit_payload(investigation_case: AccessAnomalyInvestigationCase) -> str:
    finding = investigation_case.finding
    return json.dumps(
        {
            "case_id": investigation_case.case_id,
            "status": investigation_case.status,
            "finding_type": finding.finding_type,
            "actor": finding.actor,
            "severity": finding.severity,
            "event_count": finding.event_count,
            "assigned_to": investigation_case.assigned_to,
            "closed_by": investigation_case.closed_by,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
