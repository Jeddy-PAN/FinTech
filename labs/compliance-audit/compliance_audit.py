from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SourceAuditEvent(Protocol):
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor: str
    reason: str | None
    payload: str
    occurred_at: datetime


@dataclass(frozen=True)
class ComplianceAuditEvent:
    source_system: str
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor: str
    reason: str | None
    payload: str
    occurred_at: datetime


@dataclass(frozen=True)
class AuditEventFilter:
    source_system: str | None = None
    actor: str | None = None
    event_type: str | None = None
    event_type_prefix: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


@dataclass(frozen=True)
class AuditTimeline:
    subject_type: str
    subject_id: str
    events: tuple[ComplianceAuditEvent, ...]

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def first_occurred_at(self) -> datetime | None:
        if not self.events:
            return None
        return self.events[0].occurred_at

    @property
    def last_occurred_at(self) -> datetime | None:
        if not self.events:
            return None
        return self.events[-1].occurred_at


@dataclass(frozen=True)
class AuditSummary:
    total_events: int
    source_system_counts: tuple[tuple[str, int], ...]
    event_type_counts: tuple[tuple[str, int], ...]
    actor_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AuditUser:
    user_id: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AuditAccessEvent:
    event_type: str
    actor: str
    permission: str
    target: str
    outcome: str
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class AuditExportApproval:
    approved_by: AuditUser
    approved_at: datetime
    reason: str


@dataclass
class AuditAccessRecorder:
    _events: list[AuditAccessEvent]

    @classmethod
    def create(cls) -> "AuditAccessRecorder":
        return cls(_events=[])

    @property
    def events(self) -> tuple[AuditAccessEvent, ...]:
        return tuple(self._events)

    def record(
        self,
        *,
        event_type: str,
        actor: str,
        permission: str,
        target: str,
        outcome: str,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> AuditAccessEvent:
        event = AuditAccessEvent(
            event_type=event_type,
            actor=actor,
            permission=permission,
            target=target,
            outcome=outcome,
            occurred_at=occurred_at,
            reason=reason,
        )
        self._events.append(event)
        return event


class ComplianceAuditError(Exception):
    pass


VIEW_AUDIT_EVENTS = "view_audit_events"
VIEW_AUDIT_PAYLOAD = "view_audit_payload"
EXPORT_AUDIT_REPORT = "export_audit_report"
APPROVE_AUDIT_EXPORT = "approve_audit_export"

ROLE_PERMISSIONS = {
    "audit_viewer": frozenset({VIEW_AUDIT_EVENTS}),
    "audit_analyst": frozenset({VIEW_AUDIT_EVENTS, VIEW_AUDIT_PAYLOAD}),
    "audit_manager": frozenset(
        {
            VIEW_AUDIT_EVENTS,
            VIEW_AUDIT_PAYLOAD,
            EXPORT_AUDIT_REPORT,
            APPROVE_AUDIT_EXPORT,
        }
    ),
}


PII_KEYS = frozenset(
    {
        "address",
        "date_of_birth",
        "full_name",
        "identification_number",
        "reason",
        "review_reason",
    }
)


def permissions_for_user(user: AuditUser) -> frozenset[str]:
    permissions: set[str] = set()
    for role in user.roles:
        permissions.update(ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(permissions)


def can_user(user: AuditUser, permission: str) -> bool:
    return permission in permissions_for_user(user)


def authorize_user(user: AuditUser, permission: str) -> None:
    if not can_user(user, permission):
        raise ComplianceAuditError(
            f"User {user.user_id} is missing permission: {permission}"
        )


def authorize_user_with_audit(
    user: AuditUser,
    permission: str,
    *,
    recorder: AuditAccessRecorder,
    target: str,
    occurred_at: datetime,
) -> None:
    try:
        authorize_user(user, permission)
    except ComplianceAuditError as error:
        recorder.record(
            event_type="audit_access.denied",
            actor=user.user_id,
            permission=permission,
            target=target,
            outcome="denied",
            occurred_at=occurred_at,
            reason=str(error),
        )
        raise
    recorder.record(
        event_type="audit_access.granted",
        actor=user.user_id,
        permission=permission,
        target=target,
        outcome="granted",
        occurred_at=occurred_at,
    )


def validate_export_approval(
    *,
    requested_by: AuditUser,
    approval: AuditExportApproval | None,
    recorder: AuditAccessRecorder | None = None,
) -> None:
    if approval is None:
        raise ComplianceAuditError("Export approval is required")
    _require_occurred_at(approval.approved_at)
    reason = approval.reason.strip()
    if not reason:
        raise ComplianceAuditError("Export approval reason is required")
    if approval.approved_by.user_id == requested_by.user_id:
        error = ComplianceAuditError("Export approver must differ from requester")
        if recorder is not None:
            recorder.record(
                event_type="audit_export_approval.denied",
                actor=approval.approved_by.user_id,
                permission=APPROVE_AUDIT_EXPORT,
                target="compliance_audit_report",
                outcome="denied",
                occurred_at=approval.approved_at,
                reason=str(error),
            )
        raise error
    if recorder is not None:
        authorize_user_with_audit(
            approval.approved_by,
            APPROVE_AUDIT_EXPORT,
            recorder=recorder,
            target="compliance_audit_report.approval",
            occurred_at=approval.approved_at,
        )
        recorder.record(
            event_type="audit_export_approval.granted",
            actor=approval.approved_by.user_id,
            permission=APPROVE_AUDIT_EXPORT,
            target="compliance_audit_report",
            outcome="granted",
            occurred_at=approval.approved_at,
            reason=reason,
        )
    else:
        authorize_user(approval.approved_by, APPROVE_AUDIT_EXPORT)


def visible_events_for_user(
    user: AuditUser,
    events: Iterable[ComplianceAuditEvent],
    *,
    recorder: AuditAccessRecorder | None = None,
    occurred_at: datetime | None = None,
) -> tuple[ComplianceAuditEvent, ...]:
    if recorder is not None:
        _require_occurred_at(occurred_at)
        authorize_user_with_audit(
            user,
            VIEW_AUDIT_EVENTS,
            recorder=recorder,
            target="audit_events",
            occurred_at=occurred_at,
        )
    else:
        authorize_user(user, VIEW_AUDIT_EVENTS)
    event_tuple = tuple(events)
    if can_user(user, VIEW_AUDIT_PAYLOAD):
        if recorder is not None:
            recorder.record(
                event_type="audit_payload.viewed",
                actor=user.user_id,
                permission=VIEW_AUDIT_PAYLOAD,
                target="audit_events.payload",
                outcome="granted",
                occurred_at=occurred_at,
            )
        return tuple(sorted(event_tuple, key=_event_sort_key))
    if recorder is not None:
        recorder.record(
            event_type="audit_payload.hidden",
            actor=user.user_id,
            permission=VIEW_AUDIT_PAYLOAD,
            target="audit_events.payload",
            outcome="denied",
            occurred_at=occurred_at,
            reason=f"User {user.user_id} is missing permission: {VIEW_AUDIT_PAYLOAD}",
        )
    return tuple(
        sorted(
            (
                _hide_event_payload(event)
                for event in event_tuple
            ),
            key=_event_sort_key,
        )
    )


def _require_occurred_at(value: datetime | None) -> None:
    if value is None:
        raise ComplianceAuditError("occurred_at is required when recording access")


def collect_audit_events(
    *,
    risk_events: Iterable[SourceAuditEvent] = (),
    kyc_events: Iterable[SourceAuditEvent] = (),
    redact_payload: bool = True,
) -> tuple[ComplianceAuditEvent, ...]:
    events = [
        _normalize_event("risk", event, redact_payload=redact_payload)
        for event in risk_events
    ]
    events.extend(
        _normalize_event("kyc", event, redact_payload=redact_payload)
        for event in kyc_events
    )
    return tuple(sorted(events, key=_event_sort_key))


def filter_audit_events(
    events: Iterable[ComplianceAuditEvent],
    event_filter: AuditEventFilter,
) -> tuple[ComplianceAuditEvent, ...]:
    filtered = []
    for event in events:
        if event_filter.source_system is not None and (
            event.source_system != event_filter.source_system
        ):
            continue
        if event_filter.actor is not None and event.actor != event_filter.actor:
            continue
        if event_filter.event_type is not None and (
            event.event_type != event_filter.event_type
        ):
            continue
        if event_filter.event_type_prefix is not None and not event.event_type.startswith(
            event_filter.event_type_prefix
        ):
            continue
        if event_filter.aggregate_type is not None and (
            event.aggregate_type != event_filter.aggregate_type
        ):
            continue
        if event_filter.aggregate_id is not None and (
            event.aggregate_id != event_filter.aggregate_id
        ):
            continue
        if event_filter.occurred_from is not None and (
            event.occurred_at < event_filter.occurred_from
        ):
            continue
        if event_filter.occurred_to is not None and (
            event.occurred_at > event_filter.occurred_to
        ):
            continue
        filtered.append(event)
    return tuple(sorted(filtered, key=_event_sort_key))


def build_audit_timeline(
    events: Iterable[ComplianceAuditEvent],
    *,
    subject_type: str,
    subject_id: str,
    aggregate_links: Iterable[tuple[str, str]],
) -> AuditTimeline:
    links = set(aggregate_links)
    timeline_events = [
        event
        for event in events
        if (event.aggregate_type, event.aggregate_id) in links
    ]
    return AuditTimeline(
        subject_type=subject_type,
        subject_id=subject_id,
        events=tuple(sorted(timeline_events, key=_event_sort_key)),
    )


def summarize_audit_events(events: Iterable[ComplianceAuditEvent]) -> AuditSummary:
    event_tuple = tuple(events)
    return AuditSummary(
        total_events=len(event_tuple),
        source_system_counts=_count_by(event_tuple, lambda event: event.source_system),
        event_type_counts=_count_by(event_tuple, lambda event: event.event_type),
        actor_counts=_count_by(event_tuple, lambda event: event.actor),
    )


def redact_payload(payload: str) -> str:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    redacted = _redact_value(value)
    return json.dumps(redacted, sort_keys=True, separators=(",", ":"))


def _hide_event_payload(event: ComplianceAuditEvent) -> ComplianceAuditEvent:
    return ComplianceAuditEvent(
        source_system=event.source_system,
        event_id=event.event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        actor=event.actor,
        reason=event.reason,
        payload="[hidden]",
        occurred_at=event.occurred_at,
    )


def _normalize_event(
    source_system: str,
    event: SourceAuditEvent,
    *,
    redact_payload: bool,
) -> ComplianceAuditEvent:
    payload = event.payload
    if redact_payload:
        payload = globals()["redact_payload"](payload)
    return ComplianceAuditEvent(
        source_system=source_system,
        event_id=event.event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        actor=event.actor,
        reason=event.reason,
        payload=payload,
        occurred_at=event.occurred_at,
    )


def _redact_value(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key in PII_KEYS else _redact_value(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(child) for child in value]
    return value


def _count_by(events, key_func):
    counts: dict[str, int] = {}
    for event in events:
        key = key_func(event)
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _event_sort_key(event: ComplianceAuditEvent):
    return (
        event.occurred_at,
        event.source_system,
        event.aggregate_type,
        event.aggregate_id,
        event.event_id,
    )
