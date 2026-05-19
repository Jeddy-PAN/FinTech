from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Iterable


LABS_DIR = Path(__file__).resolve().parents[1]
for lab_name in (
    "kyc-aml-onboarding",
    "payment-orders",
    "risk-rule-engine",
    "compliance-audit",
):
    lab_path = LABS_DIR / lab_name
    if str(lab_path) not in sys.path:
        sys.path.insert(0, str(lab_path))

from compliance_audit import (  # noqa: E402
    AuditSummary,
    AuditTimeline,
    ComplianceAuditEvent,
    build_audit_timeline,
    redact_payload,
    summarize_audit_events,
)
from kyc_aml import (  # noqa: E402
    CustomerApplication,
    KycAmlEngine,
    KycDecision,
    KycDecisionStatus,
    WatchlistEntry,
)
from payment_orders import (  # noqa: E402
    PaymentOrder,
    PaymentOrderService,
    PaymentOrderStatus,
)
from risk_rule_engine import (  # noqa: E402
    ManualReviewService,
    ReviewCase,
    ReviewStatus,
    RiskDecision,
    RiskDecisionStatus,
    RiskRequest,
    RiskRuleEngine,
    build_request,
)


class PlatformPaymentStatus(str, Enum):
    COMPLETED = "completed"
    KYC_REVIEW_REQUIRED = "kyc_review_required"
    KYC_BLOCKED = "kyc_blocked"
    RISK_REVIEW_REQUIRED = "risk_review_required"
    RISK_REVIEW_REJECTED = "risk_review_rejected"
    RISK_BLOCKED = "risk_blocked"


class FinTechPlatformError(ValueError):
    """Base error for invalid platform orchestration input."""


@dataclass(frozen=True)
class PlatformPaymentRequest:
    application: CustomerApplication
    amount: str | int | Decimal
    currency: str = "USD"
    order_id: str = "order_001"
    requested_at: datetime | None = None
    device_id: str = "device_default"
    ip_country: str = "US"
    beneficiary_id: str = "beneficiary_default"
    actor: str = "platform_system"
    risk_history: tuple[RiskRequest, ...] = ()


@dataclass(frozen=True)
class PlatformPaymentResult:
    status: PlatformPaymentStatus
    kyc_decision: KycDecision
    payment_order: PaymentOrder | None
    risk_decision: RiskDecision | None
    risk_review_case: ReviewCase | None
    ledger_transaction_id: str | None
    platform_bank_balance: Decimal
    user_wallet_balance: Decimal
    audit_events: tuple[ComplianceAuditEvent, ...]
    customer_timeline: AuditTimeline
    audit_summary: AuditSummary


class FinTechPlatform:
    def __init__(
        self,
        *,
        kyc_engine: KycAmlEngine | None = None,
        payment_service: PaymentOrderService | None = None,
        risk_engine: RiskRuleEngine | None = None,
        risk_review_service: ManualReviewService | None = None,
        watchlist: Iterable[WatchlistEntry] | None = None,
    ) -> None:
        self.kyc_engine = kyc_engine or KycAmlEngine()
        self.payment_service = payment_service or PaymentOrderService()
        self.risk_engine = risk_engine or RiskRuleEngine()
        self.risk_review_service = risk_review_service or ManualReviewService()
        self.watchlist = tuple(sample_watchlist() if watchlist is None else watchlist)

    def process_payment(self, request: PlatformPaymentRequest) -> PlatformPaymentResult:
        requested_at = _validate_requested_at(request.requested_at)
        audit_events: list[ComplianceAuditEvent] = []

        kyc_decision = self.kyc_engine.evaluate(
            request.application,
            watchlist=self.watchlist,
        )
        audit_events.append(
            _audit_event(
                source_system="kyc",
                event_id=f"kyc_decision:{kyc_decision.customer_id}",
                event_type="kyc_decision.saved",
                aggregate_type="kyc_decision",
                aggregate_id=kyc_decision.customer_id,
                actor="kyc_engine",
                reason=f"KYC/AML decision: {kyc_decision.status.value}",
                payload=_kyc_payload(request.application, kyc_decision),
                occurred_at=requested_at,
            )
        )
        if kyc_decision.status != KycDecisionStatus.APPROVED:
            status = (
                PlatformPaymentStatus.KYC_BLOCKED
                if kyc_decision.status == KycDecisionStatus.BLOCKED
                else PlatformPaymentStatus.KYC_REVIEW_REQUIRED
            )
            return self._result(
                status=status,
                application=request.application,
                kyc_decision=kyc_decision,
                payment_order=None,
                risk_decision=None,
                risk_review_case=None,
                ledger_transaction_id=None,
                audit_events=tuple(audit_events),
            )

        payment_order = self.payment_service.create_order(
            request.amount,
            order_id=request.order_id,
        )
        audit_events.append(
            _audit_event(
                source_system="payment",
                event_id=f"payment_order.created:{payment_order.id}",
                event_type="payment_order.created",
                aggregate_type="payment_order",
                aggregate_id=payment_order.id,
                actor=request.actor,
                reason="Payment order created after KYC approval",
                payload=_payment_order_payload(payment_order),
                occurred_at=requested_at + timedelta(minutes=1),
            )
        )

        risk_request = build_request(
            payment_order.id,
            request.application.customer_id,
            payment_order.amount,
            request.currency,
            requested_at + timedelta(minutes=2),
            device_id=request.device_id,
            ip_country=request.ip_country,
            beneficiary_id=request.beneficiary_id,
        )
        risk_decision = self.risk_engine.evaluate(
            risk_request,
            history=request.risk_history,
        )
        audit_events.append(
            _audit_event(
                source_system="risk",
                event_id=f"risk_decision:{risk_decision.request_id}",
                event_type="risk_decision.saved",
                aggregate_type="risk_decision",
                aggregate_id=risk_decision.request_id,
                actor="risk_engine",
                reason=f"Risk decision: {risk_decision.status.value}",
                payload=_risk_payload(risk_decision),
                occurred_at=requested_at + timedelta(minutes=2),
            )
        )

        if risk_decision.status == RiskDecisionStatus.BLOCKED:
            failed_order = self.payment_service.mark_failed(
                payment_order.id,
                event_id=f"evt_{payment_order.id}_risk_blocked",
                reason="Risk decision blocked payment",
            )
            audit_events.append(
                _audit_event(
                    source_system="payment",
                    event_id=f"payment_order.failed:{failed_order.id}",
                    event_type="payment_order.failed",
                    aggregate_type="payment_order",
                    aggregate_id=failed_order.id,
                    actor="risk_engine",
                    reason=failed_order.failure_reason,
                    payload=_payment_order_payload(failed_order),
                    occurred_at=requested_at + timedelta(minutes=3),
                )
            )
            return self._result(
                status=PlatformPaymentStatus.RISK_BLOCKED,
                application=request.application,
                kyc_decision=kyc_decision,
                payment_order=failed_order,
                risk_decision=risk_decision,
                risk_review_case=None,
                ledger_transaction_id=None,
                audit_events=tuple(audit_events),
            )

        if risk_decision.status == RiskDecisionStatus.REVIEW:
            review_case = self.risk_review_service.create_case(
                risk_decision,
                created_at=requested_at + timedelta(minutes=3),
            )
            audit_events.append(
                _audit_event(
                    source_system="risk",
                    event_id=f"review_case.created:{review_case.case_id}",
                    event_type="review_case.created",
                    aggregate_type="review_case",
                    aggregate_id=review_case.case_id,
                    actor="risk_engine",
                    reason="Risk review case created for payment order",
                    payload=_risk_review_case_payload(review_case),
                    occurred_at=review_case.created_at,
                )
            )
            return self._result(
                status=PlatformPaymentStatus.RISK_REVIEW_REQUIRED,
                application=request.application,
                kyc_decision=kyc_decision,
                payment_order=payment_order,
                risk_decision=risk_decision,
                risk_review_case=review_case,
                ledger_transaction_id=None,
                audit_events=tuple(audit_events),
            )

        succeeded_order = self.payment_service.mark_succeeded(
            payment_order.id,
            event_id=f"evt_{payment_order.id}_succeeded",
        )
        audit_events.append(
            _audit_event(
                source_system="payment",
                event_id=f"payment_order.succeeded:{succeeded_order.id}",
                event_type="payment_order.succeeded",
                aggregate_type="payment_order",
                aggregate_id=succeeded_order.id,
                actor="payment_service",
                reason="Payment order succeeded after risk approval",
                payload=_payment_order_payload(succeeded_order),
                occurred_at=requested_at + timedelta(minutes=3),
            )
        )
        ledger_transaction_id = succeeded_order.ledger_transaction_id
        audit_events.append(
            _audit_event(
                source_system="ledger",
                event_id=f"ledger_transaction.posted:{ledger_transaction_id}",
                event_type="ledger_transaction.posted",
                aggregate_type="ledger_transaction",
                aggregate_id=ledger_transaction_id or "",
                actor="payment_service",
                reason="Ledger transaction posted for approved payment order",
                payload={
                    "ledger_transaction_id": ledger_transaction_id,
                    "payment_order_id": succeeded_order.id,
                    "amount": str(succeeded_order.amount),
                },
                occurred_at=requested_at + timedelta(minutes=4),
            )
        )
        return self._result(
            status=PlatformPaymentStatus.COMPLETED,
            application=request.application,
            kyc_decision=kyc_decision,
            payment_order=succeeded_order,
            risk_decision=risk_decision,
            risk_review_case=None,
            ledger_transaction_id=ledger_transaction_id,
            audit_events=tuple(audit_events),
        )

    def approve_risk_review(
        self,
        result: PlatformPaymentResult,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> PlatformPaymentResult:
        self._validate_review_result(result)
        reviewed_at = _validate_timestamp(reviewed_at, "reviewed_at")
        assert result.payment_order is not None
        assert result.risk_review_case is not None
        review_case = self.risk_review_service.approve(
            result.risk_review_case.case_id,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )
        audit_events = [
            *result.audit_events,
            _audit_event(
                source_system="risk",
                event_id=f"review_case.approved:{review_case.case_id}",
                event_type="review_case.approved",
                aggregate_type="review_case",
                aggregate_id=review_case.case_id,
                actor=review_case.reviewed_by or "",
                reason=review_case.review_reason,
                payload=_risk_review_case_payload(review_case),
                occurred_at=reviewed_at,
            ),
        ]
        succeeded_order = self.payment_service.mark_succeeded(
            result.payment_order.id,
            event_id=f"evt_{result.payment_order.id}_risk_review_approved",
        )
        audit_events.append(
            _audit_event(
                source_system="payment",
                event_id=f"payment_order.succeeded:{succeeded_order.id}",
                event_type="payment_order.succeeded",
                aggregate_type="payment_order",
                aggregate_id=succeeded_order.id,
                actor="payment_service",
                reason="Payment order succeeded after risk review approval",
                payload=_payment_order_payload(succeeded_order),
                occurred_at=reviewed_at + timedelta(minutes=1),
            )
        )
        ledger_transaction_id = succeeded_order.ledger_transaction_id
        audit_events.append(
            _audit_event(
                source_system="ledger",
                event_id=f"ledger_transaction.posted:{ledger_transaction_id}",
                event_type="ledger_transaction.posted",
                aggregate_type="ledger_transaction",
                aggregate_id=ledger_transaction_id or "",
                actor="payment_service",
                reason="Ledger transaction posted after risk review approval",
                payload={
                    "ledger_transaction_id": ledger_transaction_id,
                    "payment_order_id": succeeded_order.id,
                    "amount": str(succeeded_order.amount),
                },
                occurred_at=reviewed_at + timedelta(minutes=2),
            )
        )
        return self._result(
            status=PlatformPaymentStatus.COMPLETED,
            customer_id=result.kyc_decision.customer_id,
            kyc_decision=result.kyc_decision,
            payment_order=succeeded_order,
            risk_decision=result.risk_decision,
            risk_review_case=review_case,
            ledger_transaction_id=ledger_transaction_id,
            audit_events=tuple(audit_events),
        )

    def reject_risk_review(
        self,
        result: PlatformPaymentResult,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> PlatformPaymentResult:
        self._validate_review_result(result)
        reviewed_at = _validate_timestamp(reviewed_at, "reviewed_at")
        assert result.payment_order is not None
        assert result.risk_review_case is not None
        review_case = self.risk_review_service.reject(
            result.risk_review_case.case_id,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )
        audit_events = [
            *result.audit_events,
            _audit_event(
                source_system="risk",
                event_id=f"review_case.rejected:{review_case.case_id}",
                event_type="review_case.rejected",
                aggregate_type="review_case",
                aggregate_id=review_case.case_id,
                actor=review_case.reviewed_by or "",
                reason=review_case.review_reason,
                payload=_risk_review_case_payload(review_case),
                occurred_at=reviewed_at,
            ),
        ]
        failed_order = self.payment_service.mark_failed(
            result.payment_order.id,
            event_id=f"evt_{result.payment_order.id}_risk_review_rejected",
            reason="Risk review rejected payment",
        )
        audit_events.append(
            _audit_event(
                source_system="payment",
                event_id=f"payment_order.failed:{failed_order.id}",
                event_type="payment_order.failed",
                aggregate_type="payment_order",
                aggregate_id=failed_order.id,
                actor=review_case.reviewed_by or "",
                reason=failed_order.failure_reason,
                payload=_payment_order_payload(failed_order),
                occurred_at=reviewed_at + timedelta(minutes=1),
            )
        )
        return self._result(
            status=PlatformPaymentStatus.RISK_REVIEW_REJECTED,
            customer_id=result.kyc_decision.customer_id,
            kyc_decision=result.kyc_decision,
            payment_order=failed_order,
            risk_decision=result.risk_decision,
            risk_review_case=review_case,
            ledger_transaction_id=None,
            audit_events=tuple(audit_events),
        )

    def _validate_review_result(self, result: PlatformPaymentResult) -> None:
        if result.status != PlatformPaymentStatus.RISK_REVIEW_REQUIRED:
            raise FinTechPlatformError("Only risk review results can be completed")
        if result.payment_order is None:
            raise FinTechPlatformError("Risk review result is missing payment order")
        if result.risk_review_case is None:
            raise FinTechPlatformError("Risk review result is missing review case")
        if result.risk_review_case.status != ReviewStatus.PENDING_REVIEW:
            raise FinTechPlatformError("Risk review case is already completed")

    def _result(
        self,
        *,
        status: PlatformPaymentStatus,
        application: CustomerApplication | None = None,
        customer_id: str | None = None,
        kyc_decision: KycDecision,
        payment_order: PaymentOrder | None,
        risk_decision: RiskDecision | None,
        risk_review_case: ReviewCase | None,
        ledger_transaction_id: str | None,
        audit_events: tuple[ComplianceAuditEvent, ...],
    ) -> PlatformPaymentResult:
        resolved_customer_id = (
            application.customer_id if application is not None else customer_id
        )
        if resolved_customer_id is None:
            raise FinTechPlatformError("customer_id is required")
        timeline = build_audit_timeline(
            audit_events,
            subject_type="customer",
            subject_id=resolved_customer_id,
            aggregate_links=_aggregate_links(
                customer_id=resolved_customer_id,
                payment_order=payment_order,
                risk_decision=risk_decision,
                risk_review_case=risk_review_case,
                ledger_transaction_id=ledger_transaction_id,
            ),
        )
        return PlatformPaymentResult(
            status=status,
            kyc_decision=kyc_decision,
            payment_order=payment_order,
            risk_decision=risk_decision,
            risk_review_case=risk_review_case,
            ledger_transaction_id=ledger_transaction_id,
            platform_bank_balance=self.payment_service.ledger.balance_for(
                self.payment_service.platform_bank_account_id
            ),
            user_wallet_balance=self.payment_service.ledger.balance_for(
                self.payment_service.user_wallet_account_id
            ),
            audit_events=tuple(sorted(audit_events, key=_event_sort_key)),
            customer_timeline=timeline,
            audit_summary=summarize_audit_events(audit_events),
        )


def sample_watchlist() -> tuple[WatchlistEntry, ...]:
    return (
        WatchlistEntry(
            entry_id="sample_sdn_001",
            list_name="Sample Sanctions List",
            full_name="Alex Blocked",
            country="US",
            date_of_birth=date(1980, 1, 1),
        ),
        WatchlistEntry(
            entry_id="sample_sdn_002",
            list_name="Sample Sanctions List",
            full_name="Maria Review",
            country="GB",
        ),
    )


def _validate_requested_at(value: datetime | None) -> datetime:
    if value is None:
        raise FinTechPlatformError("requested_at is required")
    return _validate_timestamp(value, "requested_at")


def _validate_timestamp(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FinTechPlatformError(f"{field_name} must be timezone-aware")
    return value


def _audit_event(
    *,
    source_system: str,
    event_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    actor: str,
    reason: str | None,
    payload: dict,
    occurred_at: datetime,
) -> ComplianceAuditEvent:
    raw_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ComplianceAuditEvent(
        source_system=source_system,
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        actor=actor,
        reason=reason,
        payload=redact_payload(raw_payload),
        occurred_at=occurred_at,
    )


def _kyc_payload(
    application: CustomerApplication,
    decision: KycDecision,
) -> dict:
    return {
        "customer_id": application.customer_id,
        "full_name": application.full_name,
        "identification_number": application.identification_number,
        "status": decision.status.value,
        "risk_score": decision.risk_score,
        "check_results": [
            {
                "check_id": result.check_id,
                "status": result.status.value,
                "reason": result.reason,
                "score": result.score,
            }
            for result in decision.check_results
        ],
    }


def _payment_order_payload(order: PaymentOrder) -> dict:
    return {
        "payment_order_id": order.id,
        "amount": str(order.amount),
        "status": order.status.value,
        "ledger_transaction_id": order.ledger_transaction_id,
        "refund_ledger_transaction_id": order.refund_ledger_transaction_id,
        "failure_reason": order.failure_reason,
    }


def _risk_payload(decision: RiskDecision) -> dict:
    return {
        "request_id": decision.request_id,
        "user_id": decision.user_id,
        "status": decision.status.value,
        "risk_score": decision.risk_score,
        "rule_hits": [
            {
                "rule_id": hit.rule_id,
                "status": hit.status.value,
                "reason": hit.reason,
                "score": hit.score,
            }
            for hit in decision.rule_hits
        ],
    }


def _risk_review_case_payload(review_case: ReviewCase) -> dict:
    return {
        "case_id": review_case.case_id,
        "request_id": review_case.request_id,
        "user_id": review_case.user_id,
        "status": review_case.status.value,
        "reviewed_by": review_case.reviewed_by,
        "review_reason": review_case.review_reason,
    }


def _aggregate_links(
    *,
    customer_id: str,
    payment_order: PaymentOrder | None,
    risk_decision: RiskDecision | None,
    risk_review_case: ReviewCase | None,
    ledger_transaction_id: str | None,
) -> tuple[tuple[str, str], ...]:
    links = [("kyc_decision", customer_id)]
    if payment_order is not None:
        links.append(("payment_order", payment_order.id))
    if risk_decision is not None:
        links.append(("risk_decision", risk_decision.request_id))
    if risk_review_case is not None:
        links.append(("review_case", risk_review_case.case_id))
    if ledger_transaction_id is not None:
        links.append(("ledger_transaction", ledger_transaction_id))
    return tuple(links)


def _event_sort_key(event: ComplianceAuditEvent):
    return (
        event.occurred_at,
        event.source_system,
        event.aggregate_type,
        event.aggregate_id,
        event.event_id,
    )
