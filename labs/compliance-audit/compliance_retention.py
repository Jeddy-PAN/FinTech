from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from compliance_audit import ComplianceAuditError, ComplianceAuditEvent


RETENTION_ACTIVE = "active"
RETENTION_ARCHIVE_DUE = "archive_due"
RETENTION_DELETE_DUE = "delete_due"
RETENTION_HELD = "held"


@dataclass(frozen=True)
class AuditRetentionPolicy:
    policy_id: str
    event_type_prefix: str
    retention_days: int
    archive_after_days: int | None = None
    legal_hold: bool = False


@dataclass(frozen=True)
class AuditRetentionDecision:
    event: ComplianceAuditEvent
    policy: AuditRetentionPolicy
    status: str
    age_days: int
    archive_due_at: datetime | None
    delete_due_at: datetime
    reason: str


@dataclass(frozen=True)
class AuditRetentionReport:
    generated_at: datetime
    decisions: tuple[AuditRetentionDecision, ...]

    @property
    def total_events(self) -> int:
        return len(self.decisions)

    @property
    def status_counts(self) -> tuple[tuple[str, int], ...]:
        counts: dict[str, int] = {}
        for decision in self.decisions:
            counts[decision.status] = counts.get(decision.status, 0) + 1
        return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_retention_report(
    events: Iterable[ComplianceAuditEvent],
    *,
    policies: Iterable[AuditRetentionPolicy],
    generated_at: datetime,
) -> AuditRetentionReport:
    _validate_timestamp(generated_at, field_name="generated_at")
    policy_tuple = tuple(policies)
    if not policy_tuple:
        raise ComplianceAuditError("At least one retention policy is required")
    for policy in policy_tuple:
        _validate_policy(policy)
    decisions = tuple(
        evaluate_retention(event, policies=policy_tuple, generated_at=generated_at)
        for event in events
    )
    return AuditRetentionReport(
        generated_at=generated_at,
        decisions=tuple(sorted(decisions, key=_decision_sort_key)),
    )


def evaluate_retention(
    event: ComplianceAuditEvent,
    *,
    policies: Iterable[AuditRetentionPolicy],
    generated_at: datetime,
) -> AuditRetentionDecision:
    _validate_timestamp(generated_at, field_name="generated_at")
    _validate_timestamp(event.occurred_at, field_name="occurred_at")
    if generated_at < event.occurred_at:
        raise ComplianceAuditError("generated_at cannot be before event occurred_at")
    policy = _matching_policy(event, tuple(policies))
    delete_due_at = event.occurred_at + timedelta(days=policy.retention_days)
    archive_due_at = (
        event.occurred_at + timedelta(days=policy.archive_after_days)
        if policy.archive_after_days is not None
        else None
    )
    age_days = (generated_at - event.occurred_at).days

    if policy.legal_hold:
        return AuditRetentionDecision(
            event=event,
            policy=policy,
            status=RETENTION_HELD,
            age_days=age_days,
            archive_due_at=archive_due_at,
            delete_due_at=delete_due_at,
            reason="Policy is under legal hold",
        )
    if generated_at >= delete_due_at:
        return AuditRetentionDecision(
            event=event,
            policy=policy,
            status=RETENTION_DELETE_DUE,
            age_days=age_days,
            archive_due_at=archive_due_at,
            delete_due_at=delete_due_at,
            reason="Retention period has ended",
        )
    if archive_due_at is not None and generated_at >= archive_due_at:
        return AuditRetentionDecision(
            event=event,
            policy=policy,
            status=RETENTION_ARCHIVE_DUE,
            age_days=age_days,
            archive_due_at=archive_due_at,
            delete_due_at=delete_due_at,
            reason="Archive threshold has been reached",
        )
    return AuditRetentionDecision(
        event=event,
        policy=policy,
        status=RETENTION_ACTIVE,
        age_days=age_days,
        archive_due_at=archive_due_at,
        delete_due_at=delete_due_at,
        reason="Event is still inside active retention window",
    )


def _matching_policy(
    event: ComplianceAuditEvent,
    policies: tuple[AuditRetentionPolicy, ...],
) -> AuditRetentionPolicy:
    matches = [
        policy
        for policy in policies
        if event.event_type.startswith(policy.event_type_prefix)
    ]
    if not matches:
        raise ComplianceAuditError(
            f"No retention policy matched event type: {event.event_type}"
        )
    return sorted(matches, key=lambda policy: len(policy.event_type_prefix), reverse=True)[0]


def _validate_policy(policy: AuditRetentionPolicy) -> None:
    if not policy.policy_id.strip():
        raise ComplianceAuditError("Retention policy id is required")
    if not policy.event_type_prefix.strip():
        raise ComplianceAuditError("Retention policy event type prefix is required")
    if policy.retention_days <= 0:
        raise ComplianceAuditError("retention_days must be greater than zero")
    if policy.archive_after_days is not None:
        if policy.archive_after_days < 0:
            raise ComplianceAuditError("archive_after_days cannot be negative")
        if policy.archive_after_days >= policy.retention_days:
            raise ComplianceAuditError(
                "archive_after_days must be less than retention_days"
            )


def _validate_timestamp(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ComplianceAuditError(f"{field_name} must be timezone-aware")


def _decision_sort_key(decision: AuditRetentionDecision):
    return (
        decision.status,
        decision.event.occurred_at,
        decision.event.source_system,
        decision.event.event_id,
    )
