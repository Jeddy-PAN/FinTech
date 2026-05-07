from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Iterable


CENT = Decimal("0.01")


class RiskRuleEngineError(ValueError):
    """Base error for invalid risk rule engine operations."""


class RiskDecisionStatus(str, Enum):
    APPROVED = "approved"
    REVIEW = "review"
    BLOCKED = "blocked"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RiskRequest:
    transaction_id: str
    user_id: str
    amount: Decimal
    currency: str
    created_at: datetime
    device_id: str
    ip_country: str
    beneficiary_id: str


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    status: RiskDecisionStatus
    reason: str
    score: int


@dataclass(frozen=True)
class RiskDecision:
    request_id: str
    user_id: str
    status: RiskDecisionStatus
    rule_hits: tuple[RuleHit, ...]
    risk_score: int


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    request_id: str
    user_id: str
    status: ReviewStatus
    rule_hits: tuple[RuleHit, ...]
    created_at: datetime
    reviewed_by: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None


@dataclass(frozen=True)
class RiskRuleConfig:
    single_transaction_review_threshold: Decimal
    daily_user_review_threshold: Decimal
    allowed_currencies: tuple[str, ...]
    high_risk_countries: tuple[str, ...]
    blocked_beneficiaries: tuple[str, ...]
    risk_score_review_threshold: int
    rule_scores: dict[str, int]

    @classmethod
    def from_json(cls, json_path: str | Path) -> RiskRuleConfig:
        path = Path(json_path)
        with path.open(encoding="utf-8") as file:
            data = json.load(file)

        required_fields = {
            "single_transaction_review_threshold",
            "daily_user_review_threshold",
            "allowed_currencies",
            "high_risk_countries",
            "blocked_beneficiaries",
            "risk_score_review_threshold",
            "rule_scores",
        }
        missing_fields = required_fields - set(data)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise RiskRuleEngineError(f"Risk rule config missing fields: {missing}")

        allowed_currencies = tuple(
            _normalize_currency(currency) for currency in data["allowed_currencies"]
        )
        if not allowed_currencies:
            raise RiskRuleEngineError("At least one allowed currency is required")

        return cls(
            single_transaction_review_threshold=_money(
                data["single_transaction_review_threshold"]
            ),
            daily_user_review_threshold=_money(data["daily_user_review_threshold"]),
            allowed_currencies=allowed_currencies,
            high_risk_countries=tuple(
                _normalize_country(country) for country in data["high_risk_countries"]
            ),
            blocked_beneficiaries=tuple(
                _normalize_identifier(beneficiary_id, field_name="Beneficiary id")
                for beneficiary_id in data["blocked_beneficiaries"]
            ),
            risk_score_review_threshold=_positive_int(
                data["risk_score_review_threshold"],
                field_name="risk_score_review_threshold",
            ),
            rule_scores=_normalize_rule_scores(data["rule_scores"]),
        )


class RiskRuleEngine:
    def __init__(
        self,
        *,
        single_transaction_review_threshold: str | int | Decimal = "1000.00",
        daily_user_review_threshold: str | int | Decimal = "3000.00",
        allowed_currencies: Iterable[str] = ("USD",),
        high_risk_countries: Iterable[str] = (),
        blocked_beneficiaries: Iterable[str] = (),
        risk_score_review_threshold: int = 50,
        rule_scores: dict[str, int] | None = None,
        config: RiskRuleConfig | None = None,
    ) -> None:
        if config is not None:
            single_transaction_review_threshold = (
                config.single_transaction_review_threshold
            )
            daily_user_review_threshold = config.daily_user_review_threshold
            allowed_currencies = config.allowed_currencies
            high_risk_countries = config.high_risk_countries
            blocked_beneficiaries = config.blocked_beneficiaries
            risk_score_review_threshold = config.risk_score_review_threshold
            rule_scores = config.rule_scores

        self.single_transaction_review_threshold = _money(
            single_transaction_review_threshold
        )
        self.daily_user_review_threshold = _money(daily_user_review_threshold)
        self.allowed_currencies = {
            _normalize_currency(currency) for currency in allowed_currencies
        }
        if not self.allowed_currencies:
            raise RiskRuleEngineError("At least one allowed currency is required")
        self.high_risk_countries = {
            _normalize_country(country) for country in high_risk_countries
        }
        self.blocked_beneficiaries = {
            _normalize_identifier(beneficiary_id, field_name="Beneficiary id")
            for beneficiary_id in blocked_beneficiaries
        }
        self.risk_score_review_threshold = _positive_int(
            risk_score_review_threshold,
            field_name="risk_score_review_threshold",
        )
        self.rule_scores = self._default_rule_scores()
        if rule_scores is not None:
            self.rule_scores.update(_normalize_rule_scores(rule_scores))

    def evaluate(
        self,
        request: RiskRequest,
        *,
        history: Iterable[RiskRequest] = (),
    ) -> RiskDecision:
        normalized_request = normalize_request(request)
        normalized_history = tuple(normalize_request(item) for item in history)
        rule_hits = []

        if normalized_request.currency not in self.allowed_currencies:
            rule_hits.append(
                RuleHit(
                    rule_id="currency_allowed",
                    status=RiskDecisionStatus.BLOCKED,
                    reason=f"Currency is not allowed: {normalized_request.currency}",
                    score=self._score_for("currency_allowed"),
                )
            )

        if normalized_request.ip_country in self.high_risk_countries:
            rule_hits.append(
                RuleHit(
                    rule_id="ip_country_allowed",
                    status=RiskDecisionStatus.BLOCKED,
                    reason=f"IP country is high risk: {normalized_request.ip_country}",
                    score=self._score_for("ip_country_allowed"),
                )
            )

        if normalized_request.beneficiary_id in self.blocked_beneficiaries:
            rule_hits.append(
                RuleHit(
                    rule_id="beneficiary_allowed",
                    status=RiskDecisionStatus.BLOCKED,
                    reason=f"Beneficiary is blocked: {normalized_request.beneficiary_id}",
                    score=self._score_for("beneficiary_allowed"),
                )
            )

        if self._is_unusual_hour(normalized_request):
            rule_hits.append(
                RuleHit(
                    rule_id="unusual_hour",
                    status=RiskDecisionStatus.APPROVED,
                    reason=(
                        "Transaction time is in the unusual activity window: "
                        f"{normalized_request.created_at.astimezone(timezone.utc).hour:02d}:00 UTC"
                    ),
                    score=self._score_for("unusual_hour"),
                )
            )

        if self._is_round_amount_signal(normalized_request):
            rule_hits.append(
                RuleHit(
                    rule_id="round_amount",
                    status=RiskDecisionStatus.APPROVED,
                    reason=(
                        f"Amount {normalized_request.amount} is a large round amount"
                    ),
                    score=self._score_for("round_amount"),
                )
            )

        if normalized_request.amount > self.single_transaction_review_threshold:
            rule_hits.append(
                RuleHit(
                    rule_id="single_transaction_amount",
                    status=RiskDecisionStatus.REVIEW,
                    reason=(
                        f"Amount {normalized_request.amount} exceeds review threshold "
                        f"{self.single_transaction_review_threshold}"
                    ),
                    score=self._score_for("single_transaction_amount"),
                )
            )

        if self._is_new_device(normalized_request, normalized_history):
            rule_hits.append(
                RuleHit(
                    rule_id="new_device",
                    status=RiskDecisionStatus.REVIEW,
                    reason=(
                        f"Device {normalized_request.device_id} has no prior "
                        f"history for user {normalized_request.user_id}"
                    ),
                    score=self._score_for("new_device"),
                )
            )

        daily_total = self._daily_total(normalized_request, normalized_history)
        if daily_total > self.daily_user_review_threshold:
            rule_hits.append(
                RuleHit(
                    rule_id="daily_user_amount",
                    status=RiskDecisionStatus.REVIEW,
                    reason=(
                        f"Daily total {daily_total} exceeds review threshold "
                        f"{self.daily_user_review_threshold}"
                    ),
                    score=self._score_for("daily_user_amount"),
                )
            )

        risk_score = sum(hit.score for hit in rule_hits)
        return RiskDecision(
            request_id=normalized_request.transaction_id,
            user_id=normalized_request.user_id,
            status=self._decision_status(rule_hits, risk_score),
            rule_hits=tuple(rule_hits),
            risk_score=risk_score,
        )

    def _daily_total(
        self,
        request: RiskRequest,
        history: tuple[RiskRequest, ...],
    ) -> Decimal:
        request_date = _utc_date(request.created_at)
        total = request.amount

        for item in history:
            if item.user_id != request.user_id:
                continue
            if item.currency != request.currency:
                continue
            if _utc_date(item.created_at) != request_date:
                continue
            total += item.amount

        return total.quantize(CENT)

    def _decision_status(
        self,
        rule_hits: list[RuleHit],
        risk_score: int,
    ) -> RiskDecisionStatus:
        if any(hit.status == RiskDecisionStatus.BLOCKED for hit in rule_hits):
            return RiskDecisionStatus.BLOCKED
        if (
            any(hit.status == RiskDecisionStatus.REVIEW for hit in rule_hits)
            or risk_score >= self.risk_score_review_threshold
        ):
            return RiskDecisionStatus.REVIEW
        return RiskDecisionStatus.APPROVED

    def _score_for(self, rule_id: str) -> int:
        return self.rule_scores[rule_id]

    def _default_rule_scores(self) -> dict[str, int]:
        return {
            "currency_allowed": 100,
            "ip_country_allowed": 100,
            "beneficiary_allowed": 100,
            "single_transaction_amount": 60,
            "daily_user_amount": 70,
            "new_device": 35,
            "unusual_hour": 25,
            "round_amount": 30,
        }

    def _is_new_device(
        self,
        request: RiskRequest,
        history: tuple[RiskRequest, ...],
    ) -> bool:
        has_user_history = False
        for item in history:
            if item.user_id != request.user_id:
                continue
            has_user_history = True
            if item.device_id == request.device_id:
                return False
        return has_user_history

    def _is_unusual_hour(self, request: RiskRequest) -> bool:
        utc_hour = request.created_at.astimezone(timezone.utc).hour
        return 0 <= utc_hour < 5

    def _is_round_amount_signal(self, request: RiskRequest) -> bool:
        return request.amount >= Decimal("500.00") and request.amount % Decimal("100.00") == 0


class ManualReviewService:
    def __init__(self) -> None:
        self._cases: dict[str, ReviewCase] = {}

    @property
    def cases(self) -> tuple[ReviewCase, ...]:
        return tuple(self._cases.values())

    def create_case(
        self,
        decision: RiskDecision,
        *,
        created_at: datetime,
    ) -> ReviewCase:
        if decision.status != RiskDecisionStatus.REVIEW:
            raise RiskRuleEngineError("Only review decisions can create review cases")

        timestamp = _validate_timestamp(created_at, field_name="created_at")
        case_id = f"review:{decision.request_id}"
        if case_id in self._cases:
            return self._cases[case_id]

        review_case = ReviewCase(
            case_id=case_id,
            request_id=decision.request_id,
            user_id=decision.user_id,
            status=ReviewStatus.PENDING_REVIEW,
            rule_hits=decision.rule_hits,
            created_at=timestamp,
        )
        self._cases[case_id] = review_case
        return review_case

    def approve(
        self,
        case_id: str,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> ReviewCase:
        return self._complete_case(
            case_id,
            status=ReviewStatus.APPROVED,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def reject(
        self,
        case_id: str,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> ReviewCase:
        return self._complete_case(
            case_id,
            status=ReviewStatus.REJECTED,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def _complete_case(
        self,
        case_id: str,
        *,
        status: ReviewStatus,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> ReviewCase:
        review_case = self._get_case(case_id)
        if review_case.status != ReviewStatus.PENDING_REVIEW:
            raise RiskRuleEngineError(f"Review case is already completed: {case_id}")

        reviewer = reviewed_by.strip()
        if not reviewer:
            raise RiskRuleEngineError("Reviewer is required")

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise RiskRuleEngineError("Review reason is required")

        completed_case = ReviewCase(
            case_id=review_case.case_id,
            request_id=review_case.request_id,
            user_id=review_case.user_id,
            status=status,
            rule_hits=review_case.rule_hits,
            created_at=review_case.created_at,
            reviewed_by=reviewer,
            review_reason=normalized_reason,
            reviewed_at=_validate_timestamp(reviewed_at, field_name="reviewed_at"),
        )
        self._cases[case_id] = completed_case
        return completed_case

    def _get_case(self, case_id: str) -> ReviewCase:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise RiskRuleEngineError(f"Unknown review case: {case_id}") from exc


def build_request(
    transaction_id: str,
    user_id: str,
    amount: str | int | Decimal,
    currency: str,
    created_at: datetime,
    device_id: str = "device_default",
    ip_country: str = "US",
    beneficiary_id: str = "beneficiary_default",
) -> RiskRequest:
    return RiskRequest(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=_money(amount),
        currency=_normalize_currency(currency),
        created_at=_validate_timestamp(created_at, field_name="created_at"),
        device_id=_normalize_identifier(device_id, field_name="Device id"),
        ip_country=_normalize_country(ip_country),
        beneficiary_id=_normalize_identifier(beneficiary_id, field_name="Beneficiary id"),
    )


def normalize_request(request: RiskRequest) -> RiskRequest:
    transaction_id = request.transaction_id.strip()
    if not transaction_id:
        raise RiskRuleEngineError("Transaction id is required")

    user_id = request.user_id.strip()
    if not user_id:
        raise RiskRuleEngineError("User id is required")

    return RiskRequest(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=_money(request.amount),
        currency=_normalize_currency(request.currency),
        created_at=_validate_timestamp(request.created_at, field_name="created_at"),
        device_id=_normalize_identifier(request.device_id, field_name="Device id"),
        ip_country=_normalize_country(request.ip_country),
        beneficiary_id=_normalize_identifier(
            request.beneficiary_id,
            field_name="Beneficiary id",
        ),
    )


def _money(value: str | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise RiskRuleEngineError(f"Invalid money amount: {value!r}") from exc

    if amount <= Decimal("0.00"):
        raise RiskRuleEngineError("Amount must be positive")

    return amount


def _normalize_currency(currency: str) -> str:
    normalized = currency.strip().upper()
    if not normalized:
        raise RiskRuleEngineError("Currency is required")
    return normalized


def _normalize_country(country: str) -> str:
    normalized = country.strip().upper()
    if not normalized:
        raise RiskRuleEngineError("IP country is required")
    if len(normalized) != 2:
        raise RiskRuleEngineError("IP country must be a 2-letter country code")
    return normalized


def _normalize_identifier(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RiskRuleEngineError(f"{field_name} is required")
    return normalized


def _validate_timestamp(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskRuleEngineError(f"{field_name} must be timezone-aware")
    return value


def _positive_int(value, *, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise RiskRuleEngineError(f"{field_name} must be a positive integer") from exc
    if normalized <= 0:
        raise RiskRuleEngineError(f"{field_name} must be a positive integer")
    return normalized


def _normalize_rule_scores(rule_scores) -> dict[str, int]:
    if not isinstance(rule_scores, dict):
        raise RiskRuleEngineError("rule_scores must be an object")
    return {
        str(rule_id).strip(): _positive_int(score, field_name=f"rule_scores.{rule_id}")
        for rule_id, score in rule_scores.items()
    }


def _utc_date(value: datetime):
    return value.astimezone(timezone.utc).date()
