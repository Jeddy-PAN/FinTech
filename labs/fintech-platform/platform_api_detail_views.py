from __future__ import annotations

import html
from urllib.parse import quote

from compliance_audit import AuditAccessEvent
from platform_api_console_views import html_table, table
from platform_async_service import PlatformAsyncRun
from platform_operation_approval import OperationApprovalRecord


def render_operation_approval_detail_html(
    *,
    record: OperationApprovalRecord,
    async_run: PlatformAsyncRun | None,
    platform_result: dict | None,
    access_events: tuple[AuditAccessEvent, ...],
    retry_permission: str,
    chrome_css: str,
    content_css: str,
    topbar_html: str,
    side_nav_html: str,
    page_header_html: str,
) -> str:
    lifecycle_rows = _operation_approval_lifecycle_timeline_rows(
        record,
        access_events,
        retry_permission=retry_permission,
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Operation Approval Detail</title>
  <style>
    {chrome_css}
    {content_css}
  </style>
</head>
<body class="platform-shell">
  {topbar_html}
  <main class="platform-main">
    <div class="platform-workspace">
      {side_nav_html}
      <div class="platform-content">
  {page_header_html}
  <div class="meta">
    Read-only approval context. Back to <a href="/platform/view">FinTech Platform Console</a>.
  </div>
  <div class="page-actions">
    <a href="/platform/view">Back to Console</a>
  </div>

  <div class="section">
    <h2>Approval Record</h2>
    {table(
        ["field", "value"],
        _operation_approval_detail_rows(record),
        empty_message="No approval record is available.",
    )}
  </div>

  <div class="section">
    <h2>Lifecycle Timeline</h2>
    {table(
        ["occurred_at", "event_type", "actor", "outcome", "reason"],
        lifecycle_rows,
        empty_message="No lifecycle events are available.",
    )}
  </div>

  <div class="section">
    <h2>Associated Async Run</h2>
    {html_table(
        ["field", "value"],
        _operation_approval_async_run_detail_rows_html(async_run),
        empty_message="No associated async run was found.",
    )}
  </div>

  <div class="section">
    <h2>Platform Result Summary</h2>
    {html_table(
        ["field", "value"],
        _platform_result_detail_rows_html(
            platform_result,
            link_run_id=True,
            summary_only=True,
        ),
        empty_message="No completed platform result is available.",
    )}
  </div>
      </div>
    </div>
  </main>
</body>
</html>"""


def render_async_run_detail_html(
    *,
    run: PlatformAsyncRun,
    platform_result: dict | None,
    chrome_css: str,
    content_css: str,
    topbar_html: str,
    side_nav_html: str,
    page_header_html: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Async Run Detail</title>
  <style>
    {chrome_css}
    {content_css}
  </style>
</head>
<body class="platform-shell">
  {topbar_html}
  <main class="platform-main">
    <div class="platform-workspace">
      {side_nav_html}
      <div class="platform-content">
  {page_header_html}
  <div class="meta">
    Read-only async run context. Back to <a href="/platform/view">FinTech Platform Console</a>.
  </div>
  <div class="page-actions">
    <a href="/platform/view">Back to Console</a>
  </div>

  <div class="section">
    <h2>Async Run</h2>
    {html_table(
        ["field", "value"],
        _async_run_detail_rows_html(run),
        empty_message="No async run is available.",
    )}
  </div>

  <div class="section">
    <h2>Request Payload</h2>
    {html_table(
        ["field", "value"],
        _request_payload_rows_html(run),
        empty_message="No request payload is available.",
    )}
  </div>

  <div class="section">
    <h2>Platform Result Summary</h2>
    {html_table(
        ["field", "value"],
        _platform_result_detail_rows_html(
            platform_result,
            link_run_id=True,
            summary_only=True,
        ),
        empty_message="No completed platform result is available.",
    )}
  </div>
      </div>
    </div>
  </main>
</body>
</html>"""


def render_payment_run_detail_html(
    *,
    platform_result: dict,
    async_run: PlatformAsyncRun | None,
    reconciliation_rows: list[tuple[object, ...]],
    chrome_css: str,
    content_css: str,
    topbar_html: str,
    side_nav_html: str,
    page_header_html: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Payment Run Detail</title>
  <style>
    {chrome_css}
    {content_css}
  </style>
</head>
<body class="platform-shell">
  {topbar_html}
  <main class="platform-main">
    <div class="platform-workspace">
      {side_nav_html}
      <div class="platform-content">
  {page_header_html}
  <div class="meta">
    Read-only platform result context. Back to <a href="/platform/view">FinTech Platform Console</a>.
  </div>
  <div class="page-actions">
    <a href="/platform/view">Back to Console</a>
  </div>

  <div class="section">
    <h2>Platform Result</h2>
    {html_table(
        ["field", "value"],
        _platform_result_detail_rows_html(
            platform_result,
            link_run_id=False,
            summary_only=False,
        ),
        empty_message="No platform result is available.",
    )}
  </div>

  <div class="section">
    <h2>Associated Async Run</h2>
    {html_table(
        ["field", "value"],
        _operation_approval_async_run_detail_rows_html(async_run),
        empty_message="No associated async run was found.",
    )}
  </div>

  <div class="section">
    <h2>Ledger Reconciliation Context</h2>
    {table(
        ["check_id", "status", "severity", "message"],
        reconciliation_rows,
        empty_message="No ledger reconciliation context is available.",
    )}
  </div>

  <div class="section">
    <h2>Customer Audit Timeline</h2>
    {table(
        [
            "occurred_at",
            "source_system",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "actor",
            "reason",
        ],
        _platform_result_audit_event_rows(platform_result),
        empty_message="No customer audit events are available.",
    )}
  </div>
      </div>
    </div>
  </main>
</body>
</html>"""


def _operation_approval_detail_rows(
    record: OperationApprovalRecord,
) -> list[tuple[object, ...]]:
    decided_at = "" if record.decided_at is None else record.decided_at.isoformat()
    return [
        ("approval_id", record.approval_id),
        ("operation_type", record.operation_type),
        ("operation_id", record.operation_id),
        ("target", record.target),
        ("requested_by", record.requested_by),
        ("request_reason", record.request_reason),
        ("approved_by", record.approved_by or ""),
        ("approval_reason", record.approval_reason or ""),
        ("status", record.status),
        ("decision_reason", record.decision_reason),
        ("requested_at", record.requested_at.isoformat()),
        ("decided_at", decided_at),
    ]


def _operation_approval_async_run_detail_rows_html(
    run: PlatformAsyncRun | None,
) -> list[tuple[str, ...]]:
    if run is None:
        return []
    return [
        ("run_id", _async_run_detail_link(run.run_id)),
        ("status", html.escape(run.status)),
        ("attempt_count", html.escape(str(run.attempt_count))),
        ("max_attempts", html.escape(str(run.max_attempts))),
        ("last_error", html.escape(run.last_error or "")),
        ("created_at", html.escape(run.created_at.isoformat())),
        ("updated_at", html.escape(run.updated_at.isoformat())),
        (
            "started_at",
            "" if run.started_at is None else html.escape(run.started_at.isoformat()),
        ),
        (
            "completed_at",
            ""
            if run.completed_at is None
            else html.escape(run.completed_at.isoformat()),
        ),
    ]


def _async_run_detail_rows_html(run: PlatformAsyncRun) -> list[tuple[str, ...]]:
    return _operation_approval_async_run_detail_rows_html(run)


def _request_payload_rows_html(run: PlatformAsyncRun) -> list[tuple[str, ...]]:
    return [
        (html.escape(str(field)), html.escape(str(value)))
        for field, value in sorted(run.request_payload.items())
    ]


def _platform_result_detail_rows_html(
    platform_result: dict | None,
    *,
    link_run_id: bool,
    summary_only: bool,
) -> list[tuple[str, ...]]:
    if platform_result is None:
        return []
    fields = [
        "run_id",
        "customer_id",
        "status",
        "payment_order_id",
        "payment_order_status",
        "risk_status",
        "ledger_transaction_id",
        "audit_event_count",
        "created_at",
    ]
    if not summary_only:
        fields = [
            "run_id",
            "customer_id",
            "status",
            "kyc_status",
            "payment_order_id",
            "payment_order_status",
            "risk_status",
            "risk_review_case_id",
            "ledger_transaction_id",
            "platform_bank_balance",
            "user_wallet_balance",
            "audit_event_count",
            "created_at",
        ]
    rows: list[tuple[str, ...]] = []
    for field in fields:
        value = platform_result.get(field) or ""
        if field == "run_id" and link_run_id and value:
            rows.append((field, _payment_run_detail_link(str(value))))
        else:
            rows.append((field, html.escape(str(value))))
    return rows


def _platform_result_audit_event_rows(
    platform_result: dict,
) -> list[tuple[object, ...]]:
    return [
        (
            event["occurred_at"],
            event["source_system"],
            event["event_type"],
            event["aggregate_type"],
            event["aggregate_id"],
            event["actor"],
            event["reason"],
        )
        for event in platform_result.get("audit_events", [])
    ]


def _operation_approval_lifecycle_timeline_rows(
    record: OperationApprovalRecord,
    access_events: tuple[AuditAccessEvent, ...],
    *,
    retry_permission: str,
) -> list[tuple[object, ...]]:
    rows = [
        (
            record.requested_at,
            "approval_requested",
            record.requested_by,
            "pending",
            record.request_reason,
        )
    ]
    if record.decided_at is not None:
        rows.append(
            (
                record.decided_at,
                "approval_decided",
                record.approved_by or "",
                record.status,
                record.approval_reason or record.decision_reason,
            )
        )
    for event in _retry_execution_events_for_approval(
        record,
        access_events,
        retry_permission=retry_permission,
    ):
        rows.append(
            (
                event.occurred_at,
                "retry_execution",
                event.actor,
                event.outcome,
                event.reason,
            )
        )
    return [
        (
            occurred_at.isoformat(),
            event_type,
            actor,
            outcome,
            reason,
        )
        for occurred_at, event_type, actor, outcome, reason in sorted(
            rows,
            key=lambda row: (row[0], row[1], row[2]),
        )
    ]


def _retry_execution_events_for_approval(
    record: OperationApprovalRecord,
    access_events: tuple[AuditAccessEvent, ...],
    *,
    retry_permission: str,
) -> tuple[AuditAccessEvent, ...]:
    approval_marker = f"approval_id={record.approval_id}"
    return tuple(
        event
        for event in access_events
        if event.permission == retry_permission and approval_marker in event.reason
    )


def _payment_run_detail_link(run_id: str) -> str:
    escaped_run_id = html.escape(run_id)
    href_run_id = quote(run_id, safe="")
    return f'<a href="/platform/payment-runs/{href_run_id}/view">{escaped_run_id}</a>'


def _async_run_detail_link(run_id: str) -> str:
    escaped_run_id = html.escape(run_id)
    href_run_id = quote(run_id, safe="")
    return (
        f'<a href="/platform/async-payment-runs/{href_run_id}/view">'
        f"{escaped_run_id}</a>"
    )
