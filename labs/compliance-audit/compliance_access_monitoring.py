from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from compliance_audit import AuditAccessEvent, ComplianceAuditError


SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

FINDING_REPEATED_DENIED_ACCESS = "repeated_denied_access"
FINDING_UNAUTHORIZED_EXPORT_ATTEMPT = "unauthorized_export_attempt"
FINDING_REPEATED_PAYLOAD_VIEW = "repeated_payload_view"


@dataclass(frozen=True)
class AccessMonitoringRule:
    rule_id: str
    finding_type: str
    threshold: int
    window_minutes: int
    severity: str


@dataclass(frozen=True)
class AccessAnomalyFinding:
    finding_type: str
    actor: str
    severity: str
    event_count: int
    reason: str
    first_occurred_at: datetime
    last_occurred_at: datetime
    events: tuple[AuditAccessEvent, ...]


def default_access_monitoring_rules() -> tuple[AccessMonitoringRule, ...]:
    return (
        AccessMonitoringRule(
            rule_id="repeated-denied-access",
            finding_type=FINDING_REPEATED_DENIED_ACCESS,
            threshold=3,
            window_minutes=15,
            severity=SEVERITY_HIGH,
        ),
        AccessMonitoringRule(
            rule_id="unauthorized-export-attempt",
            finding_type=FINDING_UNAUTHORIZED_EXPORT_ATTEMPT,
            threshold=1,
            window_minutes=60,
            severity=SEVERITY_HIGH,
        ),
        AccessMonitoringRule(
            rule_id="repeated-payload-view",
            finding_type=FINDING_REPEATED_PAYLOAD_VIEW,
            threshold=5,
            window_minutes=30,
            severity=SEVERITY_MEDIUM,
        ),
    )


def detect_access_anomalies(
    events: Iterable[AuditAccessEvent],
    *,
    rules: Iterable[AccessMonitoringRule] | None = None,
    manager_actor_prefixes: tuple[str, ...] = ("manager_",),
) -> tuple[AccessAnomalyFinding, ...]:
    event_tuple = tuple(sorted(events, key=_event_sort_key))
    rule_tuple = tuple(rules or default_access_monitoring_rules())
    if not rule_tuple:
        raise ComplianceAuditError("At least one access monitoring rule is required")
    for rule in rule_tuple:
        _validate_rule(rule)

    findings: list[AccessAnomalyFinding] = []
    for rule in rule_tuple:
        if rule.finding_type == FINDING_REPEATED_DENIED_ACCESS:
            findings.extend(_detect_repeated_denied_access(event_tuple, rule))
        elif rule.finding_type == FINDING_UNAUTHORIZED_EXPORT_ATTEMPT:
            findings.extend(
                _detect_unauthorized_export_attempts(
                    event_tuple,
                    rule,
                    manager_actor_prefixes=manager_actor_prefixes,
                )
            )
        elif rule.finding_type == FINDING_REPEATED_PAYLOAD_VIEW:
            findings.extend(_detect_repeated_payload_views(event_tuple, rule))
        else:
            raise ComplianceAuditError(
                f"Unknown access monitoring finding type: {rule.finding_type}"
            )
    return tuple(sorted(findings, key=_finding_sort_key))


def _detect_repeated_denied_access(
    events: tuple[AuditAccessEvent, ...],
    rule: AccessMonitoringRule,
) -> tuple[AccessAnomalyFinding, ...]:
    candidate_events = [
        event for event in events if event.outcome == "denied"
    ]
    return _window_findings(
        candidate_events,
        rule,
        reason_template=(
            "Actor has {event_count} denied access events within "
            f"{rule.window_minutes} minutes"
        ),
    )


def _detect_unauthorized_export_attempts(
    events: tuple[AuditAccessEvent, ...],
    rule: AccessMonitoringRule,
    *,
    manager_actor_prefixes: tuple[str, ...],
) -> tuple[AccessAnomalyFinding, ...]:
    candidate_events = [
        event
        for event in events
        if event.permission == "export_audit_report"
        and not _actor_has_prefix(event.actor, manager_actor_prefixes)
    ]
    return _window_findings(
        candidate_events,
        rule,
        reason_template=(
            "Non-manager actor attempted audit report export "
            "{event_count} time(s)"
        ),
    )


def _detect_repeated_payload_views(
    events: tuple[AuditAccessEvent, ...],
    rule: AccessMonitoringRule,
) -> tuple[AccessAnomalyFinding, ...]:
    candidate_events = [
        event
        for event in events
        if event.permission == "view_audit_payload" and event.outcome == "granted"
    ]
    return _window_findings(
        candidate_events,
        rule,
        reason_template=(
            "Actor viewed audit payload {event_count} times within "
            f"{rule.window_minutes} minutes"
        ),
    )


def _window_findings(
    events: Iterable[AuditAccessEvent],
    rule: AccessMonitoringRule,
    *,
    reason_template: str,
) -> tuple[AccessAnomalyFinding, ...]:
    events_by_actor: dict[str, list[AuditAccessEvent]] = {}
    for event in events:
        _validate_timestamp(event.occurred_at, field_name="occurred_at")
        events_by_actor.setdefault(event.actor, []).append(event)

    findings = []
    for actor, actor_events in events_by_actor.items():
        sorted_events = sorted(actor_events, key=_event_sort_key)
        window_events = _first_threshold_window(sorted_events, rule)
        if window_events is None:
            continue
        findings.append(
            AccessAnomalyFinding(
                finding_type=rule.finding_type,
                actor=actor,
                severity=rule.severity,
                event_count=len(window_events),
                reason=reason_template.format(event_count=len(window_events)),
                first_occurred_at=window_events[0].occurred_at,
                last_occurred_at=window_events[-1].occurred_at,
                events=tuple(window_events),
            )
        )
    return tuple(findings)


def _first_threshold_window(
    events: list[AuditAccessEvent],
    rule: AccessMonitoringRule,
) -> list[AuditAccessEvent] | None:
    window = timedelta(minutes=rule.window_minutes)
    for start_index, start_event in enumerate(events):
        window_events = [
            event
            for event in events[start_index:]
            if event.occurred_at - start_event.occurred_at <= window
        ]
        if len(window_events) >= rule.threshold:
            return window_events[: rule.threshold]
    return None


def _validate_rule(rule: AccessMonitoringRule) -> None:
    if not rule.rule_id.strip():
        raise ComplianceAuditError("Access monitoring rule id is required")
    if not rule.finding_type.strip():
        raise ComplianceAuditError("Access monitoring finding type is required")
    if rule.threshold <= 0:
        raise ComplianceAuditError("Access monitoring threshold must be positive")
    if rule.window_minutes <= 0:
        raise ComplianceAuditError("Access monitoring window_minutes must be positive")
    if rule.severity not in {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH}:
        raise ComplianceAuditError(f"Unknown access monitoring severity: {rule.severity}")


def _validate_timestamp(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ComplianceAuditError(f"{field_name} must be timezone-aware")


def _actor_has_prefix(actor: str, prefixes: tuple[str, ...]) -> bool:
    return any(actor.startswith(prefix) for prefix in prefixes)


def _event_sort_key(event: AuditAccessEvent):
    return (
        event.occurred_at,
        event.actor,
        event.permission,
        event.event_type,
    )


def _finding_sort_key(finding: AccessAnomalyFinding):
    severity_order = {
        SEVERITY_HIGH: 0,
        SEVERITY_MEDIUM: 1,
        SEVERITY_LOW: 2,
    }
    return (
        severity_order[finding.severity],
        finding.first_occurred_at,
        finding.actor,
        finding.finding_type,
    )
