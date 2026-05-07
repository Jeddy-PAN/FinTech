from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from difflib import SequenceMatcher
from typing import Iterable


class KycAmlError(ValueError):
    """Base error for invalid KYC/AML onboarding operations."""


class CustomerType(str, Enum):
    INDIVIDUAL = "individual"
    LEGAL_ENTITY = "legal_entity"


class KycDecisionStatus(str, Enum):
    APPROVED = "approved"
    REVIEW = "review"
    BLOCKED = "blocked"


class KycReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUEST_MORE_INFO = "request_more_info"


@dataclass(frozen=True)
class BeneficialOwner:
    owner_id: str
    full_name: str
    ownership_percent: int
    country: str
    identification_number: str
    date_of_birth: date | None = None


@dataclass(frozen=True)
class CustomerApplication:
    customer_id: str
    customer_type: CustomerType
    full_name: str
    country: str
    address: str
    identification_number: str
    expected_monthly_volume_cents: int
    date_of_birth: date | None = None
    beneficial_owners: tuple[BeneficialOwner, ...] = ()


@dataclass(frozen=True)
class WatchlistEntry:
    entry_id: str
    list_name: str
    full_name: str
    country: str | None = None
    date_of_birth: date | None = None


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: KycDecisionStatus
    reason: str
    score: int


@dataclass(frozen=True)
class KycDecision:
    customer_id: str
    status: KycDecisionStatus
    check_results: tuple[CheckResult, ...]
    risk_score: int


@dataclass(frozen=True)
class KycReviewCase:
    case_id: str
    customer_id: str
    status: KycReviewStatus
    check_results: tuple[CheckResult, ...]
    created_at: datetime
    reviewed_by: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None


@dataclass(frozen=True)
class KycAmlPolicy:
    high_risk_countries: tuple[str, ...] = ()
    beneficial_owner_threshold_percent: int = 25
    high_expected_monthly_volume_cents: int = 1_000_000
    fuzzy_review_score_threshold: int = 88
    exact_block_score_threshold: int = 98
    risk_score_review_threshold: int = 60

    def __post_init__(self) -> None:
        _validate_percent(
            self.beneficial_owner_threshold_percent,
            field_name="beneficial_owner_threshold_percent",
        )
        _positive_int(
            self.high_expected_monthly_volume_cents,
            field_name="high_expected_monthly_volume_cents",
        )
        _positive_int(
            self.fuzzy_review_score_threshold,
            field_name="fuzzy_review_score_threshold",
        )
        _positive_int(
            self.exact_block_score_threshold,
            field_name="exact_block_score_threshold",
        )
        _positive_int(
            self.risk_score_review_threshold,
            field_name="risk_score_review_threshold",
        )
        if self.fuzzy_review_score_threshold > self.exact_block_score_threshold:
            raise KycAmlError(
                "fuzzy_review_score_threshold must be <= exact_block_score_threshold"
            )


class KycAmlEngine:
    def __init__(self, policy: KycAmlPolicy | None = None) -> None:
        self.policy = policy or KycAmlPolicy()
        self.high_risk_countries = {
            _normalize_country(country, field_name="high_risk_countries")
            for country in self.policy.high_risk_countries
        }

    def evaluate(
        self,
        application: CustomerApplication,
        *,
        watchlist: Iterable[WatchlistEntry] = (),
    ) -> KycDecision:
        normalized_application = normalize_application(application)
        normalized_watchlist = tuple(normalize_watchlist_entry(item) for item in watchlist)

        check_results = [
            *self._identity_checks(normalized_application),
            *self._beneficial_owner_checks(normalized_application),
            *self._country_checks(normalized_application),
            *self._expected_activity_checks(normalized_application),
            *self._watchlist_checks(normalized_application, normalized_watchlist),
        ]
        risk_score = sum(
            result.score
            for result in check_results
            if result.status != KycDecisionStatus.APPROVED
        )

        return KycDecision(
            customer_id=normalized_application.customer_id,
            status=self._decision_status(check_results, risk_score),
            check_results=tuple(check_results),
            risk_score=risk_score,
        )

    def _identity_checks(
        self,
        application: CustomerApplication,
    ) -> tuple[CheckResult, ...]:
        missing_fields = []
        if not application.full_name:
            missing_fields.append("full_name")
        if not application.country:
            missing_fields.append("country")
        if not application.address:
            missing_fields.append("address")
        if not application.identification_number:
            missing_fields.append("identification_number")
        if (
            application.customer_type == CustomerType.INDIVIDUAL
            and application.date_of_birth is None
        ):
            missing_fields.append("date_of_birth")

        if missing_fields:
            return (
                CheckResult(
                    check_id="identity_required_fields",
                    status=KycDecisionStatus.REVIEW,
                    reason="Missing required identity fields: " + ", ".join(missing_fields),
                    score=35,
                ),
            )

        return (
            CheckResult(
                check_id="identity_required_fields",
                status=KycDecisionStatus.APPROVED,
                reason="Required identity fields are present",
                score=0,
            ),
        )

    def _beneficial_owner_checks(
        self,
        application: CustomerApplication,
    ) -> tuple[CheckResult, ...]:
        if application.customer_type == CustomerType.INDIVIDUAL:
            return ()

        if not application.beneficial_owners:
            return (
                CheckResult(
                    check_id="beneficial_owner_required",
                    status=KycDecisionStatus.REVIEW,
                    reason="Legal entity has no beneficial owner records",
                    score=45,
                ),
            )

        incomplete_owner_ids = []
        threshold_owner_ids = []
        for owner in application.beneficial_owners:
            if owner.ownership_percent >= self.policy.beneficial_owner_threshold_percent:
                threshold_owner_ids.append(owner.owner_id)
                if (
                    not owner.full_name
                    or not owner.country
                    or not owner.identification_number
                ):
                    incomplete_owner_ids.append(owner.owner_id)

        if not threshold_owner_ids:
            return (
                CheckResult(
                    check_id="beneficial_owner_threshold",
                    status=KycDecisionStatus.REVIEW,
                    reason=(
                        "Legal entity has no beneficial owner at or above "
                        f"{self.policy.beneficial_owner_threshold_percent}% ownership"
                    ),
                    score=35,
                ),
            )

        if incomplete_owner_ids:
            return (
                CheckResult(
                    check_id="beneficial_owner_required_fields",
                    status=KycDecisionStatus.REVIEW,
                    reason="Incomplete beneficial owner records: "
                    + ", ".join(incomplete_owner_ids),
                    score=35,
                ),
            )

        return (
            CheckResult(
                check_id="beneficial_owner_required",
                status=KycDecisionStatus.APPROVED,
                reason="Required beneficial owner records are present",
                score=0,
            ),
        )

    def _country_checks(
        self,
        application: CustomerApplication,
    ) -> tuple[CheckResult, ...]:
        if application.country in self.high_risk_countries:
            return (
                CheckResult(
                    check_id="customer_country_risk",
                    status=KycDecisionStatus.REVIEW,
                    reason=f"Customer country requires enhanced review: {application.country}",
                    score=35,
                ),
            )

        return (
            CheckResult(
                check_id="customer_country_risk",
                status=KycDecisionStatus.APPROVED,
                reason="Customer country did not match the sample high-risk list",
                score=0,
            ),
        )

    def _expected_activity_checks(
        self,
        application: CustomerApplication,
    ) -> tuple[CheckResult, ...]:
        if (
            application.expected_monthly_volume_cents
            > self.policy.high_expected_monthly_volume_cents
        ):
            return (
                CheckResult(
                    check_id="expected_activity_volume",
                    status=KycDecisionStatus.REVIEW,
                    reason=(
                        "Expected monthly volume exceeds review threshold: "
                        f"{application.expected_monthly_volume_cents} cents"
                    ),
                    score=25,
                ),
            )

        return (
            CheckResult(
                check_id="expected_activity_volume",
                status=KycDecisionStatus.APPROVED,
                reason="Expected monthly volume is within the sample threshold",
                score=0,
            ),
        )

    def _watchlist_checks(
        self,
        application: CustomerApplication,
        watchlist: tuple[WatchlistEntry, ...],
    ) -> tuple[CheckResult, ...]:
        checks = []
        customer_match = _best_watchlist_match(
            name=application.full_name,
            country=application.country,
            date_of_birth=application.date_of_birth,
            watchlist=watchlist,
            minimum_score=self.policy.fuzzy_review_score_threshold,
        )
        if customer_match is not None:
            checks.append(
                self._watchlist_result(
                    check_id="customer_watchlist_screening",
                    subject_label=f"Customer {application.customer_id}",
                    match=customer_match,
                )
            )

        for owner in application.beneficial_owners:
            owner_match = _best_watchlist_match(
                name=owner.full_name,
                country=owner.country,
                date_of_birth=owner.date_of_birth,
                watchlist=watchlist,
                minimum_score=self.policy.fuzzy_review_score_threshold,
            )
            if owner_match is not None:
                checks.append(
                    self._watchlist_result(
                        check_id=f"beneficial_owner_watchlist_screening:{owner.owner_id}",
                        subject_label=f"Beneficial owner {owner.owner_id}",
                        match=owner_match,
                    )
                )

        if checks:
            return tuple(checks)

        return (
            CheckResult(
                check_id="watchlist_screening",
                status=KycDecisionStatus.APPROVED,
                reason="No sample watchlist match was found",
                score=0,
            ),
        )

    def _watchlist_result(
        self,
        *,
        check_id: str,
        subject_label: str,
        match: tuple[WatchlistEntry, int, bool],
    ) -> CheckResult:
        entry, score, strong_identity_match = match
        if (
            score >= self.policy.exact_block_score_threshold
            and strong_identity_match
        ):
            return CheckResult(
                check_id=check_id,
                status=KycDecisionStatus.BLOCKED,
                reason=(
                    f"{subject_label} matched sample watchlist entry "
                    f"{entry.entry_id} from {entry.list_name} with score {score}"
                ),
                score=100,
            )

        return CheckResult(
            check_id=check_id,
            status=KycDecisionStatus.REVIEW,
            reason=(
                f"{subject_label} has a possible sample watchlist match "
                f"{entry.entry_id} from {entry.list_name} with score {score}"
            ),
            score=50,
        )

    def _decision_status(
        self,
        check_results: list[CheckResult],
        risk_score: int,
    ) -> KycDecisionStatus:
        if any(result.status == KycDecisionStatus.BLOCKED for result in check_results):
            return KycDecisionStatus.BLOCKED
        if (
            any(result.status == KycDecisionStatus.REVIEW for result in check_results)
            or risk_score >= self.policy.risk_score_review_threshold
        ):
            return KycDecisionStatus.REVIEW
        return KycDecisionStatus.APPROVED


class KycReviewService:
    def __init__(self) -> None:
        self._cases: dict[str, KycReviewCase] = {}

    @property
    def cases(self) -> tuple[KycReviewCase, ...]:
        return tuple(self._cases.values())

    def create_case(
        self,
        decision: KycDecision,
        *,
        created_at: datetime,
    ) -> KycReviewCase:
        if decision.status != KycDecisionStatus.REVIEW:
            raise KycAmlError("Only review decisions can create KYC review cases")

        timestamp = _validate_timestamp(created_at, field_name="created_at")
        case_id = f"kyc_review:{decision.customer_id}"
        if case_id in self._cases:
            return self._cases[case_id]

        review_case = KycReviewCase(
            case_id=case_id,
            customer_id=decision.customer_id,
            status=KycReviewStatus.PENDING_REVIEW,
            check_results=decision.check_results,
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
    ) -> KycReviewCase:
        return self._complete_case(
            case_id,
            status=KycReviewStatus.APPROVED,
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
    ) -> KycReviewCase:
        return self._complete_case(
            case_id,
            status=KycReviewStatus.REJECTED,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def request_more_info(
        self,
        case_id: str,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> KycReviewCase:
        return self._complete_case(
            case_id,
            status=KycReviewStatus.REQUEST_MORE_INFO,
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def _complete_case(
        self,
        case_id: str,
        *,
        status: KycReviewStatus,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> KycReviewCase:
        review_case = self._get_case(case_id)
        if review_case.status != KycReviewStatus.PENDING_REVIEW:
            raise KycAmlError(f"KYC review case is already completed: {case_id}")

        reviewer = reviewed_by.strip()
        if not reviewer:
            raise KycAmlError("Reviewer is required")

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise KycAmlError("Review reason is required")

        completed_case = KycReviewCase(
            case_id=review_case.case_id,
            customer_id=review_case.customer_id,
            status=status,
            check_results=review_case.check_results,
            created_at=review_case.created_at,
            reviewed_by=reviewer,
            review_reason=normalized_reason,
            reviewed_at=_validate_timestamp(reviewed_at, field_name="reviewed_at"),
        )
        self._cases[case_id] = completed_case
        return completed_case

    def _get_case(self, case_id: str) -> KycReviewCase:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise KycAmlError(f"Unknown KYC review case: {case_id}") from exc


def build_individual_application(
    customer_id: str,
    full_name: str,
    *,
    date_of_birth: date,
    country: str,
    address: str,
    identification_number: str,
    expected_monthly_volume_cents: int,
) -> CustomerApplication:
    return CustomerApplication(
        customer_id=customer_id,
        customer_type=CustomerType.INDIVIDUAL,
        full_name=full_name,
        country=country,
        address=address,
        identification_number=identification_number,
        expected_monthly_volume_cents=expected_monthly_volume_cents,
        date_of_birth=date_of_birth,
    )


def build_legal_entity_application(
    customer_id: str,
    full_name: str,
    *,
    country: str,
    address: str,
    identification_number: str,
    expected_monthly_volume_cents: int,
    beneficial_owners: Iterable[BeneficialOwner],
) -> CustomerApplication:
    return CustomerApplication(
        customer_id=customer_id,
        customer_type=CustomerType.LEGAL_ENTITY,
        full_name=full_name,
        country=country,
        address=address,
        identification_number=identification_number,
        expected_monthly_volume_cents=expected_monthly_volume_cents,
        beneficial_owners=tuple(beneficial_owners),
    )


def normalize_application(application: CustomerApplication) -> CustomerApplication:
    customer_id = application.customer_id.strip()
    if not customer_id:
        raise KycAmlError("Customer id is required")

    customer_type = CustomerType(application.customer_type)
    expected_volume = _positive_int(
        application.expected_monthly_volume_cents,
        field_name="expected_monthly_volume_cents",
    )
    country = _normalize_optional_country(application.country, field_name="country")

    return CustomerApplication(
        customer_id=customer_id,
        customer_type=customer_type,
        full_name=application.full_name.strip(),
        country=country,
        address=application.address.strip(),
        identification_number=application.identification_number.strip(),
        expected_monthly_volume_cents=expected_volume,
        date_of_birth=application.date_of_birth,
        beneficial_owners=tuple(
            normalize_beneficial_owner(owner)
            for owner in application.beneficial_owners
        ),
    )


def normalize_beneficial_owner(owner: BeneficialOwner) -> BeneficialOwner:
    owner_id = owner.owner_id.strip()
    if not owner_id:
        raise KycAmlError("Beneficial owner id is required")
    _validate_percent(owner.ownership_percent, field_name="ownership_percent")

    return BeneficialOwner(
        owner_id=owner_id,
        full_name=owner.full_name.strip(),
        ownership_percent=owner.ownership_percent,
        country=_normalize_optional_country(owner.country, field_name="owner.country"),
        identification_number=owner.identification_number.strip(),
        date_of_birth=owner.date_of_birth,
    )


def normalize_watchlist_entry(entry: WatchlistEntry) -> WatchlistEntry:
    entry_id = entry.entry_id.strip()
    if not entry_id:
        raise KycAmlError("Watchlist entry id is required")
    list_name = entry.list_name.strip()
    if not list_name:
        raise KycAmlError("Watchlist name is required")
    full_name = entry.full_name.strip()
    if not full_name:
        raise KycAmlError("Watchlist full name is required")

    country = None
    if entry.country is not None and entry.country.strip():
        country = _normalize_country(entry.country, field_name="watchlist.country")

    return WatchlistEntry(
        entry_id=entry_id,
        list_name=list_name,
        full_name=full_name,
        country=country,
        date_of_birth=entry.date_of_birth,
    )


def _best_watchlist_match(
    *,
    name: str,
    country: str,
    date_of_birth: date | None,
    watchlist: tuple[WatchlistEntry, ...],
    minimum_score: int,
) -> tuple[WatchlistEntry, int, bool] | None:
    best_entry = None
    best_score = 0
    best_strong_identity_match = False

    for entry in watchlist:
        score = _name_match_score(name, entry.full_name)
        if score < best_score:
            continue
        strong_identity_match = _strong_identity_match(
            country=country,
            date_of_birth=date_of_birth,
            entry=entry,
        )
        best_entry = entry
        best_score = score
        best_strong_identity_match = strong_identity_match

    if best_entry is None or best_score < minimum_score:
        return None

    return (best_entry, best_score, best_strong_identity_match)


def _name_match_score(left: str, right: str) -> int:
    return round(
        SequenceMatcher(
            None,
            _normalize_name_for_matching(left),
            _normalize_name_for_matching(right),
        ).ratio()
        * 100
    )


def _strong_identity_match(
    *,
    country: str,
    date_of_birth: date | None,
    entry: WatchlistEntry,
) -> bool:
    country_matches = entry.country is not None and country == entry.country
    dob_matches = entry.date_of_birth is not None and date_of_birth == entry.date_of_birth
    return country_matches or dob_matches


def _normalize_name_for_matching(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _normalize_optional_country(value: str, *, field_name: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        return ""
    return _normalize_country(normalized, field_name=field_name)


def _normalize_country(value: str, *, field_name: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 2:
        raise KycAmlError(f"{field_name} must be a 2-letter country code")
    return normalized


def _positive_int(value: int, *, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise KycAmlError(f"{field_name} must be a positive integer") from exc
    if normalized <= 0:
        raise KycAmlError(f"{field_name} must be a positive integer")
    return normalized


def _validate_percent(value: int, *, field_name: str) -> None:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise KycAmlError(f"{field_name} must be between 0 and 100") from exc
    if normalized < 0 or normalized > 100:
        raise KycAmlError(f"{field_name} must be between 0 and 100")


def _validate_timestamp(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KycAmlError(f"{field_name} must be timezone-aware")
    return value
