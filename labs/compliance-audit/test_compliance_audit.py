from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from compliance_audit import (
    AuditAccessRecorder,
    AuditUser,
    ComplianceAuditError,
    EXPORT_AUDIT_REPORT,
    AuditEventFilter,
    VIEW_AUDIT_EVENTS,
    VIEW_AUDIT_PAYLOAD,
    authorize_user,
    authorize_user_with_audit,
    build_audit_timeline,
    can_user,
    collect_audit_events,
    filter_audit_events,
    permissions_for_user,
    redact_payload,
    summarize_audit_events,
    visible_events_for_user,
)


@dataclass(frozen=True)
class SourceEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor: str
    reason: str | None
    payload: str
    occurred_at: datetime


def test_collects_and_sorts_cross_system_audit_events() -> None:
    events = collect_audit_events(
        risk_events=(
            SourceEvent(
                "risk_001",
                "risk_decision.saved",
                "risk_decision",
                "txn_001",
                "system",
                None,
                '{"request_id":"txn_001","user_id":"user_001"}',
                datetime(2026, 5, 8, 10, 5, tzinfo=timezone.utc),
            ),
        ),
        kyc_events=(
            SourceEvent(
                "kyc_001",
                "kyc_application.saved",
                "kyc_application",
                "cust_001",
                "system",
                None,
                '{"customer_id":"cust_001"}',
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
        ),
    )

    assert [event.source_system for event in events] == ["kyc", "risk"]
    assert [event.event_type for event in events] == [
        "kyc_application.saved",
        "risk_decision.saved",
    ]


def test_filters_by_actor_event_prefix_source_and_time_window() -> None:
    events = collect_audit_events(
        risk_events=(
            SourceEvent(
                "risk_001",
                "review_case.created",
                "review_case",
                "review:txn_001",
                "system",
                None,
                "{}",
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
            SourceEvent(
                "risk_002",
                "review_case.approved",
                "review_case",
                "review:txn_001",
                "analyst_001",
                "Reviewed",
                "{}",
                datetime(2026, 5, 8, 10, 30, tzinfo=timezone.utc),
            ),
        )
    )

    filtered = filter_audit_events(
        events,
        AuditEventFilter(
            source_system="risk",
            actor="analyst_001",
            event_type_prefix="review_case.",
            occurred_from=datetime(2026, 5, 8, 10, 10, tzinfo=timezone.utc),
        ),
    )

    assert [event.event_type for event in filtered] == ["review_case.approved"]


def test_builds_subject_timeline_from_linked_aggregates() -> None:
    events = collect_audit_events(
        risk_events=(
            SourceEvent(
                "risk_001",
                "risk_decision.saved",
                "risk_decision",
                "txn_001",
                "system",
                None,
                "{}",
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
            SourceEvent(
                "risk_002",
                "review_case.approved",
                "review_case",
                "review:txn_001",
                "analyst_001",
                "Reviewed",
                "{}",
                datetime(2026, 5, 8, 10, 30, tzinfo=timezone.utc),
            ),
        ),
        kyc_events=(
            SourceEvent(
                "kyc_001",
                "kyc_decision.saved",
                "kyc_decision",
                "cust_001",
                "system",
                None,
                "{}",
                datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
            ),
        ),
    )

    timeline = build_audit_timeline(
        events,
        subject_type="customer",
        subject_id="cust_001",
        aggregate_links=(
            ("kyc_decision", "cust_001"),
            ("risk_decision", "txn_001"),
            ("review_case", "review:txn_001"),
        ),
    )

    assert timeline.event_count == 3
    assert timeline.first_occurred_at == datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc)
    assert [event.event_type for event in timeline.events] == [
        "kyc_decision.saved",
        "risk_decision.saved",
        "review_case.approved",
    ]


def test_summarizes_events_by_source_type_and_actor() -> None:
    events = collect_audit_events(
        risk_events=(
            SourceEvent(
                "risk_001",
                "risk_decision.saved",
                "risk_decision",
                "txn_001",
                "system",
                None,
                "{}",
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
        ),
        kyc_events=(
            SourceEvent(
                "kyc_001",
                "kyc_application.saved",
                "kyc_application",
                "cust_001",
                "system",
                None,
                "{}",
                datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
            ),
            SourceEvent(
                "kyc_002",
                "kyc_review_case.request_more_info",
                "kyc_review_case",
                "kyc_review:cust_001",
                "analyst_001",
                "Need more info",
                "{}",
                datetime(2026, 5, 8, 9, 30, tzinfo=timezone.utc),
            ),
        ),
    )

    summary = summarize_audit_events(events)

    assert summary.total_events == 3
    assert summary.source_system_counts == (("kyc", 2), ("risk", 1))
    assert ("system", 2) in summary.actor_counts
    assert ("kyc_application.saved", 1) in summary.event_type_counts


def test_redacts_known_pii_keys_inside_json_payload() -> None:
    payload = redact_payload(
        '{"customer_id":"cust_001","full_name":"Jordan Smith",'
        '"nested":{"identification_number":"ID-1001"},"risk_score":20}'
    )

    assert payload == (
        '{"customer_id":"cust_001","full_name":"[redacted]",'
        '"nested":{"identification_number":"[redacted]"},"risk_score":20}'
    )


def test_audit_user_permissions_are_derived_from_roles() -> None:
    viewer = AuditUser("viewer_001", ("audit_viewer",))
    analyst = AuditUser("analyst_001", ("audit_analyst",))
    manager = AuditUser("manager_001", ("audit_manager",))

    assert permissions_for_user(viewer) == frozenset({VIEW_AUDIT_EVENTS})
    assert can_user(analyst, VIEW_AUDIT_PAYLOAD)
    assert can_user(manager, EXPORT_AUDIT_REPORT)
    assert not can_user(viewer, VIEW_AUDIT_PAYLOAD)


def test_visible_events_hide_payload_without_payload_permission() -> None:
    events = collect_audit_events(
        kyc_events=(
            SourceEvent(
                "kyc_001",
                "kyc_application.saved",
                "kyc_application",
                "cust_001",
                "system",
                None,
                '{"customer_id":"cust_001"}',
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
        ),
        redact_payload=False,
    )

    viewer_events = visible_events_for_user(
        AuditUser("viewer_001", ("audit_viewer",)),
        events,
    )
    analyst_events = visible_events_for_user(
        AuditUser("analyst_001", ("audit_analyst",)),
        events,
    )

    assert viewer_events[0].payload == "[hidden]"
    assert analyst_events[0].payload == '{"customer_id":"cust_001"}'


def test_authorize_user_rejects_missing_permission() -> None:
    viewer = AuditUser("viewer_001", ("audit_viewer",))

    try:
        authorize_user(viewer, EXPORT_AUDIT_REPORT)
    except ComplianceAuditError as error:
        assert "missing permission" in str(error)
    else:
        raise AssertionError("Expected ComplianceAuditError")


def test_visible_events_records_access_audit_events() -> None:
    events = collect_audit_events(
        kyc_events=(
            SourceEvent(
                "kyc_001",
                "kyc_application.saved",
                "kyc_application",
                "cust_001",
                "system",
                None,
                '{"customer_id":"cust_001"}',
                datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            ),
        ),
        redact_payload=False,
    )
    recorder = AuditAccessRecorder.create()

    visible_events_for_user(
        AuditUser("viewer_001", ("audit_viewer",)),
        events,
        recorder=recorder,
        occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
    )
    visible_events_for_user(
        AuditUser("analyst_001", ("audit_analyst",)),
        events,
        recorder=recorder,
        occurred_at=datetime(2026, 5, 8, 11, 5, tzinfo=timezone.utc),
    )

    assert [event.event_type for event in recorder.events] == [
        "audit_access.granted",
        "audit_payload.hidden",
        "audit_access.granted",
        "audit_payload.viewed",
    ]
    assert recorder.events[1].actor == "viewer_001"
    assert recorder.events[1].outcome == "denied"
    assert recorder.events[3].actor == "analyst_001"
    assert recorder.events[3].outcome == "granted"


def test_authorize_user_with_audit_records_denied_access() -> None:
    recorder = AuditAccessRecorder.create()

    try:
        authorize_user_with_audit(
            AuditUser("viewer_001", ("audit_viewer",)),
            EXPORT_AUDIT_REPORT,
            recorder=recorder,
            target="compliance_audit_report",
            occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
        )
    except ComplianceAuditError:
        pass
    else:
        raise AssertionError("Expected ComplianceAuditError")

    assert len(recorder.events) == 1
    assert recorder.events[0].event_type == "audit_access.denied"
    assert recorder.events[0].permission == EXPORT_AUDIT_REPORT
    assert recorder.events[0].outcome == "denied"
