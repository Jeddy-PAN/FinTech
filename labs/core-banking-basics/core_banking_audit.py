from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class CoreBankingAuditEvent:
    event_id: str
    event_type: str
    account_id: str | None
    occurred_at: datetime
    actor: str
    source: str
    payload: dict[str, str]


class CoreBankingAuditRecorder(Protocol):
    def record_audit_event(
        self,
        event_type: str,
        *,
        account_id: str | None = None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
        actor: str = "system",
        source: str = "core_banking",
    ) -> CoreBankingAuditEvent:
        ...


class CoreBankingAuditTrail:
    def __init__(self) -> None:
        self._events: list[CoreBankingAuditEvent] = []

    @property
    def events(self) -> tuple[CoreBankingAuditEvent, ...]:
        return tuple(self._events)

    def record_audit_event(
        self,
        event_type: str,
        *,
        account_id: str | None = None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
        actor: str = "system",
        source: str = "core_banking",
    ) -> CoreBankingAuditEvent:
        event = CoreBankingAuditEvent(
            event_id=str(uuid4()),
            event_type=_require_text(event_type, "event_type"),
            account_id=_optional_text(account_id, "account_id"),
            occurred_at=_timestamp(occurred_at or datetime.now(timezone.utc), "occurred_at"),
            actor=_require_text(actor, "actor"),
            source=_require_text(source, "source"),
            payload=audit_payload(**(payload or {})),
        )
        self._events.append(event)
        return event

    def for_account(self, account_id: str) -> tuple[CoreBankingAuditEvent, ...]:
        normalized_account_id = _require_text(account_id, "account_id")
        return tuple(event for event in self._events if event.account_id == normalized_account_id)

    def by_type(self, event_type: str) -> tuple[CoreBankingAuditEvent, ...]:
        normalized_event_type = _require_text(event_type, "event_type")
        return tuple(event for event in self._events if event.event_type == normalized_event_type)


def audit_payload(**values: object) -> dict[str, str]:
    return {
        key: _payload_value(value)
        for key, value in values.items()
        if value is not None
    }


def _payload_value(value: object) -> str:
    if isinstance(value, datetime):
        return _timestamp(value, "payload_datetime").isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _timestamp(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized
