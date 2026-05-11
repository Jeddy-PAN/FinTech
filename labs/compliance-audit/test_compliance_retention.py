from __future__ import annotations

from datetime import datetime, timezone

import pytest

from compliance_audit import ComplianceAuditError, ComplianceAuditEvent
from compliance_retention import (
    RETENTION_ACTIVE,
    RETENTION_ARCHIVE_DUE,
    RETENTION_DELETE_DUE,
    RETENTION_HELD,
    AuditRetentionPolicy,
    build_retention_report,
    evaluate_retention,
)


def test_retention_report_classifies_active_archive_delete_and_hold() -> None:
    generated_at = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    policies = (
        AuditRetentionPolicy(
            policy_id="kyc-standard",
            event_type_prefix="kyc_",
            retention_days=90,
            archive_after_days=30,
        ),
        AuditRetentionPolicy(
            policy_id="risk-standard",
            event_type_prefix="risk_",
            retention_days=45,
            archive_after_days=10,
        ),
        AuditRetentionPolicy(
            policy_id="review-hold",
            event_type_prefix="review_case.",
            retention_days=30,
            archive_after_days=7,
            legal_hold=True,
        ),
    )

    report = build_retention_report(
        (
            _event(
                event_id="kyc_active",
                event_type="kyc_decision.saved",
                occurred_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            _event(
                event_id="kyc_archive",
                event_type="kyc_decision.saved",
                occurred_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            ),
            _event(
                event_id="risk_delete",
                event_type="risk_decision.saved",
                occurred_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            _event(
                event_id="review_hold",
                event_type="review_case.approved",
                occurred_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ),
        policies=policies,
        generated_at=generated_at,
    )

    statuses = {decision.event.event_id: decision.status for decision in report.decisions}
    assert statuses == {
        "kyc_active": RETENTION_ACTIVE,
        "kyc_archive": RETENTION_ARCHIVE_DUE,
        "risk_delete": RETENTION_DELETE_DUE,
        "review_hold": RETENTION_HELD,
    }
    assert report.total_events == 4
    assert report.status_counts == (
        (RETENTION_ACTIVE, 1),
        (RETENTION_ARCHIVE_DUE, 1),
        (RETENTION_DELETE_DUE, 1),
        (RETENTION_HELD, 1),
    )


def test_retention_policy_uses_most_specific_event_type_prefix() -> None:
    decision = evaluate_retention(
        _event(
            event_id="kyc_review",
            event_type="kyc_review_case.request_more_info",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        policies=(
            AuditRetentionPolicy(
                policy_id="kyc-standard",
                event_type_prefix="kyc_",
                retention_days=30,
            ),
            AuditRetentionPolicy(
                policy_id="kyc-review-hold",
                event_type_prefix="kyc_review_case.",
                retention_days=30,
                legal_hold=True,
            ),
        ),
        generated_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )

    assert decision.policy.policy_id == "kyc-review-hold"
    assert decision.status == RETENTION_HELD


def test_retention_report_rejects_missing_policy_match() -> None:
    with pytest.raises(ComplianceAuditError, match="No retention policy matched"):
        build_retention_report(
            (
                _event(
                    event_id="risk_001",
                    event_type="risk_decision.saved",
                    occurred_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                ),
            ),
            policies=(
                AuditRetentionPolicy(
                    policy_id="kyc-standard",
                    event_type_prefix="kyc_",
                    retention_days=30,
                ),
            ),
            generated_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        )


def test_retention_report_rejects_invalid_policy() -> None:
    with pytest.raises(ComplianceAuditError, match="less than retention_days"):
        build_retention_report(
            (),
            policies=(
                AuditRetentionPolicy(
                    policy_id="invalid",
                    event_type_prefix="kyc_",
                    retention_days=30,
                    archive_after_days=30,
                ),
            ),
            generated_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        )


def test_retention_report_requires_timezone_aware_generated_at() -> None:
    with pytest.raises(ComplianceAuditError, match="timezone-aware"):
        build_retention_report(
            (),
            policies=(
                AuditRetentionPolicy(
                    policy_id="kyc-standard",
                    event_type_prefix="kyc_",
                    retention_days=30,
                ),
            ),
            generated_at=datetime(2026, 5, 8),
        )


def _event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
) -> ComplianceAuditEvent:
    return ComplianceAuditEvent(
        source_system="compliance",
        event_id=event_id,
        event_type=event_type,
        aggregate_type="customer",
        aggregate_id="cust_001",
        actor="system",
        reason=None,
        payload="{}",
        occurred_at=occurred_at,
    )
