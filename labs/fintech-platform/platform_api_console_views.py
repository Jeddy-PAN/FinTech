from __future__ import annotations

from datetime import date
import html


def metric_html(label: str, value: str) -> str:
    return f"""
      <div class="metric">
        <div class="metric-label">{html.escape(label)}</div>
        <div class="metric-value">{html.escape(value)}</div>
      </div>
    """


def normalize_console_filters(
    *,
    payment_status: str | None,
    async_status: str | None,
    operation_approval_status: str | None,
    actor: str | None,
    created_from: str | None,
    created_to: str | None,
    payment_status_options: tuple[str, ...],
    async_status_options: tuple[str, ...],
    operation_approval_status_options: tuple[str, ...],
) -> tuple[dict[str, str | None], dict[str, date | None], list[str]]:
    filters = {
        "payment_status": _normalize_console_filter_value(payment_status),
        "async_status": _normalize_console_filter_value(async_status),
        "operation_approval_status": _normalize_console_filter_value(
            operation_approval_status
        ),
        "actor": _normalize_console_filter_value(actor),
        "created_from": _normalize_console_filter_value(created_from),
        "created_to": _normalize_console_filter_value(created_to),
    }
    errors: list[str] = []
    if filters["payment_status"] not in {None, *payment_status_options}:
        errors.append(f"Unknown payment_status filter: {filters['payment_status']}")
        filters["payment_status"] = None
    if filters["async_status"] not in {None, *async_status_options}:
        errors.append(f"Unknown async_status filter: {filters['async_status']}")
        filters["async_status"] = None
    if filters["operation_approval_status"] not in {
        None,
        *operation_approval_status_options,
    }:
        errors.append(
            "Unknown operation_approval_status filter: "
            f"{filters['operation_approval_status']}"
        )
        filters["operation_approval_status"] = None
    date_filters = {
        "created_from": _parse_console_filter_date(
            filters["created_from"],
            "created_from",
            errors,
        ),
        "created_to": _parse_console_filter_date(
            filters["created_to"],
            "created_to",
            errors,
        ),
    }
    if filters["created_from"] is not None and date_filters["created_from"] is None:
        filters["created_from"] = None
    if filters["created_to"] is not None and date_filters["created_to"] is None:
        filters["created_to"] = None
    if (
        date_filters["created_from"] is not None
        and date_filters["created_to"] is not None
        and date_filters["created_from"] > date_filters["created_to"]
    ):
        errors.append("created_from must be on or before created_to")
        filters["created_from"] = None
        filters["created_to"] = None
        date_filters["created_from"] = None
        date_filters["created_to"] = None
    return filters, date_filters, errors


def console_filter_feedback_html(errors: list[str]) -> str:
    if not errors:
        return ""
    items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
    return (
        '<div class="notice notice-error">'
        f"Console filter ignored invalid value:<ul>{items}</ul>"
        "</div>"
    )


def console_filter_form_html(
    filters: dict[str, str | None],
    *,
    payment_status_options: tuple[str, ...],
    async_status_options: tuple[str, ...],
    operation_approval_status_options: tuple[str, ...],
) -> str:
    return f"""
      <form class="filter-form" method="get" action="/platform/view">
        <div class="filter-fields">
          {_console_filter_select_html(
              name="payment_status",
              label="Payment status",
              options=payment_status_options,
              selected=filters["payment_status"],
          )}
          {_console_filter_select_html(
              name="async_status",
              label="Async status",
              options=async_status_options,
              selected=filters["async_status"],
          )}
          {_console_filter_select_html(
              name="operation_approval_status",
              label="Approval status",
              options=operation_approval_status_options,
              selected=filters["operation_approval_status"],
          )}
          {_console_filter_input_html(
              name="actor",
              label="Actor",
              value=filters["actor"],
              placeholder="actor id",
          )}
          {_console_filter_input_html(
              name="created_from",
              label="Created from",
              value=filters["created_from"],
              input_type="date",
          )}
          {_console_filter_input_html(
              name="created_to",
              label="Created to",
              value=filters["created_to"],
              input_type="date",
          )}
        </div>
        <div class="filter-actions">
          <button type="submit">Apply Filters</button>
          <a href="/platform/view">Clear Filters</a>
        </div>
      </form>
    """


def retry_feedback_html(
    *,
    retry_status: str | None,
    retry_error: str | None,
) -> str:
    if retry_error:
        return (
            '<div class="notice notice-error">'
            f"Retry failed: {html.escape(retry_error)}"
            "</div>"
        )
    if retry_status == "pending_approval":
        return (
            '<div class="notice notice-success">'
            "Retry approval request created."
            "</div>"
        )
    return ""


def approval_feedback_html(
    *,
    approval_status: str | None,
    approval_error: str | None,
) -> str:
    if approval_error:
        return (
            '<div class="notice notice-error">'
            f"Approval update failed: {html.escape(approval_error)}"
            "</div>"
        )
    if approval_status == "approved":
        return (
            '<div class="notice notice-success">Operation approval approved.</div>'
        )
    if approval_status == "rejected":
        return (
            '<div class="notice notice-success">Operation approval rejected.</div>'
        )
    if approval_status == "cancelled":
        return (
            '<div class="notice notice-success">Operation approval cancelled.</div>'
        )
    if approval_status == "expired":
        return '<div class="notice notice-success">Operation approval expired.</div>'
    return ""


def table(
    headers: list[str],
    rows: list[tuple[object, ...]],
    *,
    empty_message: str,
) -> str:
    if not rows:
        return f'<div class="muted">{html.escape(empty_message)}</div>'
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def html_table(
    headers: list[str],
    rows: list[tuple[str, ...]],
    *,
    empty_message: str,
) -> str:
    if not rows:
        return f'<div class="muted">{html.escape(empty_message)}</div>'
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{value}</td>" for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _parse_console_filter_date(
    value: str | None,
    field_name: str,
    errors: list[str],
) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"Invalid {field_name} filter: {value}")
        return None


def _normalize_console_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _console_filter_input_html(
    *,
    name: str,
    label: str,
    value: str | None,
    input_type: str = "text",
    placeholder: str | None = None,
) -> str:
    escaped_name = html.escape(name, quote=True)
    escaped_value = "" if value is None else html.escape(value, quote=True)
    placeholder_attr = ""
    if placeholder is not None:
        placeholder_attr = f' placeholder="{html.escape(placeholder, quote=True)}"'
    return f"""
      <div class="filter-field">
        <label for="{escaped_name}">{html.escape(label)}</label>
        <input id="{escaped_name}" name="{escaped_name}" type="{html.escape(input_type, quote=True)}" value="{escaped_value}"{placeholder_attr}>
      </div>
    """


def _console_filter_select_html(
    *,
    name: str,
    label: str,
    options: tuple[str, ...],
    selected: str | None,
) -> str:
    escaped_name = html.escape(name, quote=True)
    option_html = [
        _console_filter_option_html(value="", label="All", selected=selected is None)
    ]
    option_html.extend(
        _console_filter_option_html(
            value=option,
            label=option,
            selected=selected == option,
        )
        for option in options
    )
    return f"""
      <div class="filter-field">
        <label for="{escaped_name}">{html.escape(label)}</label>
        <select id="{escaped_name}" name="{escaped_name}">
          {''.join(option_html)}
        </select>
      </div>
    """


def _console_filter_option_html(
    *,
    value: str,
    label: str,
    selected: bool,
) -> str:
    selected_attr = " selected" if selected else ""
    return (
        f'<option value="{html.escape(value, quote=True)}"{selected_attr}>'
        f"{html.escape(label)}</option>"
    )
