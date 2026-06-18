from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4

from core_banking_audit import CoreBankingAuditEvent, CoreBankingAuditTrail, audit_payload


CENT = Decimal("0.01")
RATE_SCALE = Decimal("0.000001")


class CoreBankingError(ValueError):
    """Base error for invalid core banking operations."""


class AccountProductType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class PostingDirection(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class PostingType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    HOLD_CAPTURE = "hold_capture"
    INTEREST = "interest"


class HoldStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    CAPTURED = "captured"


@dataclass(frozen=True)
class AccountProduct:
    product_id: str
    name: str
    product_type: AccountProductType
    annual_interest_rate: Decimal


@dataclass(frozen=True)
class BankAccount:
    account_id: str
    customer_id: str
    product_id: str
    currency: str
    status: AccountStatus
    opened_at: datetime


@dataclass(frozen=True)
class AccountPosting:
    posting_id: str
    account_id: str
    direction: PostingDirection
    posting_type: PostingType
    amount: Decimal
    currency: str
    posted_at: datetime
    description: str
    idempotency_key: str | None = None
    request_fingerprint: str | None = None


@dataclass(frozen=True)
class AccountHold:
    hold_id: str
    account_id: str
    amount: Decimal
    currency: str
    status: HoldStatus
    created_at: datetime
    reason: str
    released_at: datetime | None = None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class AccountBalance:
    account_id: str
    ledger_balance: Decimal
    active_hold_amount: Decimal
    available_balance: Decimal


@dataclass(frozen=True)
class MonthlyStatement:
    account_id: str
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    interest_credited: Decimal
    postings: tuple[AccountPosting, ...]


class CoreBankingService:
    def __init__(self) -> None:
        self._products: dict[str, AccountProduct] = {}
        self._accounts: dict[str, BankAccount] = {}
        self._postings: list[AccountPosting] = []
        self._holds: dict[str, AccountHold] = {}
        self._idempotency_index: dict[str, AccountPosting] = {}
        self._audit_trail = CoreBankingAuditTrail()

    @property
    def products(self) -> tuple[AccountProduct, ...]:
        return tuple(self._products.values())

    @property
    def accounts(self) -> tuple[BankAccount, ...]:
        return tuple(self._accounts.values())

    @property
    def postings(self) -> tuple[AccountPosting, ...]:
        return tuple(self._postings)

    @property
    def holds(self) -> tuple[AccountHold, ...]:
        return tuple(self._holds.values())

    @property
    def audit_events(self) -> tuple[CoreBankingAuditEvent, ...]:
        return self._audit_trail.events

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
        return self._audit_trail.record_audit_event(
            event_type,
            account_id=account_id,
            payload=payload,
            occurred_at=occurred_at,
            actor=actor,
            source=source,
        )

    def create_product(
        self,
        *,
        product_id: str,
        name: str,
        product_type: AccountProductType | str,
        annual_interest_rate: str | int | Decimal = "0.00",
    ) -> AccountProduct:
        normalized_product_id = _require_text(product_id, "product_id")
        if normalized_product_id in self._products:
            raise CoreBankingError(f"Product already exists: {normalized_product_id}")

        product = AccountProduct(
            product_id=normalized_product_id,
            name=_require_text(name, "name"),
            product_type=AccountProductType(product_type),
            annual_interest_rate=_rate(annual_interest_rate),
        )
        self._products[product.product_id] = product
        return product

    def open_account(
        self,
        *,
        account_id: str,
        customer_id: str,
        product_id: str,
        currency: str = "USD",
        opened_at: datetime | None = None,
    ) -> BankAccount:
        normalized_account_id = _require_text(account_id, "account_id")
        if normalized_account_id in self._accounts:
            raise CoreBankingError(f"Account already exists: {normalized_account_id}")

        product = self._get_product(product_id)
        account = BankAccount(
            account_id=normalized_account_id,
            customer_id=_require_text(customer_id, "customer_id"),
            product_id=product.product_id,
            currency=_currency(currency),
            status=AccountStatus.ACTIVE,
            opened_at=_timestamp(opened_at or datetime.now(timezone.utc), "opened_at"),
        )
        self._accounts[account.account_id] = account
        self.record_audit_event(
            "account.opened",
            account_id=account.account_id,
            occurred_at=account.opened_at,
            payload=audit_payload(
                customer_id=account.customer_id,
                product_id=account.product_id,
                currency=account.currency,
                status=account.status,
            ),
        )
        return account

    def set_account_status(
        self,
        account_id: str,
        status: AccountStatus | str,
    ) -> BankAccount:
        account = self._get_account(account_id)
        updated = BankAccount(
            account_id=account.account_id,
            customer_id=account.customer_id,
            product_id=account.product_id,
            currency=account.currency,
            status=AccountStatus(status),
            opened_at=account.opened_at,
        )
        self._accounts[account.account_id] = updated
        self.record_audit_event(
            "account.status_changed",
            account_id=account.account_id,
            payload=audit_payload(
                previous_status=account.status,
                new_status=updated.status,
            ),
        )
        return updated

    def balance(self, account_id: str) -> AccountBalance:
        account = self._get_account(account_id)
        ledger_balance = Decimal("0.00")
        for posting in self._postings:
            if posting.account_id != account.account_id:
                continue
            if posting.direction == PostingDirection.CREDIT:
                ledger_balance += posting.amount
            else:
                ledger_balance -= posting.amount
        ledger_balance = ledger_balance.quantize(CENT)
        active_hold_amount = sum(
            (hold.amount for hold in self._holds.values()
             if hold.account_id == account.account_id and hold.status == HoldStatus.ACTIVE),
            Decimal("0.00"),
        ).quantize(CENT)
        return AccountBalance(
            account_id=account.account_id,
            ledger_balance=ledger_balance,
            active_hold_amount=active_hold_amount,
            available_balance=(ledger_balance - active_hold_amount).quantize(CENT),
        )

    def deposit(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        posted_at: datetime | None = None,
        description: str = "Deposit",
        idempotency_key: str | None = None,
    ) -> AccountPosting:
        account = self._require_open_account(account_id)
        return self._post(
            account,
            direction=PostingDirection.CREDIT,
            posting_type=PostingType.DEPOSIT,
            amount=amount,
            posted_at=posted_at,
            description=description,
            idempotency_key=idempotency_key,
        )

    def withdraw(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        posted_at: datetime | None = None,
        description: str = "Withdrawal",
        idempotency_key: str | None = None,
    ) -> AccountPosting:
        account = self._require_debit_allowed_account(account_id)
        normalized_amount = money(amount)
        if self.balance(account.account_id).available_balance < normalized_amount:
            raise CoreBankingError("Insufficient available balance")
        return self._post(
            account,
            direction=PostingDirection.DEBIT,
            posting_type=PostingType.WITHDRAWAL,
            amount=normalized_amount,
            posted_at=posted_at,
            description=description,
            idempotency_key=idempotency_key,
        )

    def place_hold(
        self,
        account_id: str,
        amount: str | int | Decimal,
        *,
        hold_id: str | None = None,
        created_at: datetime | None = None,
        reason: str = "Authorization hold",
    ) -> AccountHold:
        account = self._require_debit_allowed_account(account_id)
        normalized_amount = money(amount)
        if self.balance(account.account_id).available_balance < normalized_amount:
            raise CoreBankingError("Insufficient available balance")
        normalized_hold_id = hold_id or str(uuid4())
        if normalized_hold_id in self._holds:
            raise CoreBankingError(f"Hold already exists: {normalized_hold_id}")
        hold = AccountHold(
            hold_id=normalized_hold_id,
            account_id=account.account_id,
            amount=normalized_amount,
            currency=account.currency,
            status=HoldStatus.ACTIVE,
            created_at=_timestamp(created_at or datetime.now(timezone.utc), "created_at"),
            reason=_require_text(reason, "reason"),
        )
        self._holds[hold.hold_id] = hold
        self.record_audit_event(
            "hold.placed",
            account_id=hold.account_id,
            occurred_at=hold.created_at,
            payload=audit_payload(
                hold_id=hold.hold_id,
                amount=hold.amount,
                currency=hold.currency,
                status=hold.status,
                reason=hold.reason,
            ),
        )
        return hold

    def release_hold(
        self,
        hold_id: str,
        *,
        released_at: datetime | None = None,
    ) -> AccountHold:
        hold = self._require_active_hold(hold_id)
        updated = AccountHold(
            hold_id=hold.hold_id,
            account_id=hold.account_id,
            amount=hold.amount,
            currency=hold.currency,
            status=HoldStatus.RELEASED,
            created_at=hold.created_at,
            reason=hold.reason,
            released_at=_timestamp(released_at or datetime.now(timezone.utc), "released_at"),
            captured_at=None,
        )
        self._holds[hold.hold_id] = updated
        self.record_audit_event(
            "hold.released",
            account_id=updated.account_id,
            occurred_at=updated.released_at,
            payload=audit_payload(
                hold_id=updated.hold_id,
                amount=updated.amount,
                currency=updated.currency,
                status=updated.status,
            ),
        )
        return updated

    def capture_hold(
        self,
        hold_id: str,
        *,
        posted_at: datetime | None = None,
        description: str = "Capture hold",
        idempotency_key: str | None = None,
    ) -> tuple[AccountHold, AccountPosting]:
        hold = self._require_active_hold(hold_id)
        account = self._require_debit_allowed_account(hold.account_id)
        posting = self._post(
            account,
            direction=PostingDirection.DEBIT,
            posting_type=PostingType.HOLD_CAPTURE,
            amount=hold.amount,
            posted_at=posted_at,
            description=description,
            idempotency_key=idempotency_key,
        )
        updated = AccountHold(
            hold_id=hold.hold_id,
            account_id=hold.account_id,
            amount=hold.amount,
            currency=hold.currency,
            status=HoldStatus.CAPTURED,
            created_at=hold.created_at,
            reason=hold.reason,
            released_at=None,
            captured_at=posting.posted_at,
        )
        self._holds[hold.hold_id] = updated
        self.record_audit_event(
            "hold.captured",
            account_id=updated.account_id,
            occurred_at=updated.captured_at,
            payload=audit_payload(
                hold_id=updated.hold_id,
                posting_id=posting.posting_id,
                amount=updated.amount,
                currency=updated.currency,
                status=updated.status,
            ),
        )
        return updated, posting

    def accrue_daily_interest(
        self,
        account_id: str,
        *,
        accrual_date: date,
    ) -> AccountPosting | None:
        account = self._require_open_account(account_id)
        product = self._get_product(account.product_id)
        if product.annual_interest_rate <= Decimal("0.000000"):
            return None
        balance = self.balance(account.account_id).ledger_balance
        if balance <= Decimal("0.00"):
            return None
        interest = (balance * product.annual_interest_rate / Decimal("365")).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )
        if interest <= Decimal("0.00"):
            return None
        posted_at = datetime.combine(accrual_date, time(23, 59), tzinfo=timezone.utc)
        return self._post(
            account,
            direction=PostingDirection.CREDIT,
            posting_type=PostingType.INTEREST,
            amount=interest,
            posted_at=posted_at,
            description=f"Daily interest accrual for {accrual_date.isoformat()}",
            idempotency_key=f"interest:{account.account_id}:{accrual_date.isoformat()}",
        )

    def monthly_statement(
        self,
        account_id: str,
        *,
        period_start: date,
        period_end: date,
    ) -> MonthlyStatement:
        if period_end < period_start:
            raise CoreBankingError("period_end must be on or after period_start")
        account = self._get_account(account_id)
        start_at = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(period_end, time.max, tzinfo=timezone.utc)
        period_postings = tuple(
            posting for posting in self._postings
            if posting.account_id == account.account_id
            and start_at <= posting.posted_at <= end_at
        )
        opening_balance = self._ledger_balance_at(account.account_id, before=start_at)
        closing_balance = self._ledger_balance_at(account.account_id, before=end_at)
        total_credits = sum(
            (posting.amount for posting in period_postings
             if posting.direction == PostingDirection.CREDIT),
            Decimal("0.00"),
        ).quantize(CENT)
        total_debits = sum(
            (posting.amount for posting in period_postings
             if posting.direction == PostingDirection.DEBIT),
            Decimal("0.00"),
        ).quantize(CENT)
        interest_credited = sum(
            (posting.amount for posting in period_postings
             if posting.posting_type == PostingType.INTEREST),
            Decimal("0.00"),
        ).quantize(CENT)
        return MonthlyStatement(
            account_id=account.account_id,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            interest_credited=interest_credited,
            postings=period_postings,
        )

    def _post(
        self,
        account: BankAccount,
        *,
        direction: PostingDirection,
        posting_type: PostingType,
        amount: str | int | Decimal,
        posted_at: datetime | None,
        description: str,
        idempotency_key: str | None,
    ) -> AccountPosting:
        normalized_amount = money(amount)
        normalized_key = _normalize_optional_text(idempotency_key, "idempotency_key")
        fingerprint = _fingerprint(
            {
                "account_id": account.account_id,
                "direction": direction.value,
                "posting_type": posting_type.value,
                "amount": str(normalized_amount),
                "description": _require_text(description, "description"),
            }
        )
        if normalized_key and normalized_key in self._idempotency_index:
            existing = self._idempotency_index[normalized_key]
            if existing.request_fingerprint != fingerprint:
                raise CoreBankingError("Idempotency key was reused with different request data")
            return existing

        posting = AccountPosting(
            posting_id=str(uuid4()),
            account_id=account.account_id,
            direction=direction,
            posting_type=posting_type,
            amount=normalized_amount,
            currency=account.currency,
            posted_at=_timestamp(posted_at or datetime.now(timezone.utc), "posted_at"),
            description=description.strip(),
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
        )
        self._postings.append(posting)
        if normalized_key:
            self._idempotency_index[normalized_key] = posting
        self._record_posting_created(posting)
        return posting

    def _record_posting_created(self, posting: AccountPosting) -> None:
        self.record_audit_event(
            "posting.created",
            account_id=posting.account_id,
            occurred_at=posting.posted_at,
            payload=audit_payload(
                posting_id=posting.posting_id,
                direction=posting.direction,
                posting_type=posting.posting_type,
                amount=posting.amount,
                currency=posting.currency,
                idempotency_key=posting.idempotency_key,
            ),
        )
        if posting.posting_type == PostingType.INTEREST:
            self.record_audit_event(
                "interest.accrued",
                account_id=posting.account_id,
                occurred_at=posting.posted_at,
                payload=audit_payload(
                    posting_id=posting.posting_id,
                    amount=posting.amount,
                    currency=posting.currency,
                    idempotency_key=posting.idempotency_key,
                ),
            )

    def _ledger_balance_at(self, account_id: str, *, before: datetime) -> Decimal:
        balance = Decimal("0.00")
        for posting in self._postings:
            if posting.account_id != account_id or posting.posted_at > before:
                continue
            if posting.direction == PostingDirection.CREDIT:
                balance += posting.amount
            else:
                balance -= posting.amount
        return balance.quantize(CENT)

    def _get_product(self, product_id: str) -> AccountProduct:
        normalized_product_id = _require_text(product_id, "product_id")
        try:
            return self._products[normalized_product_id]
        except KeyError as exc:
            raise CoreBankingError(f"Unknown product: {normalized_product_id}") from exc

    def _get_account(self, account_id: str) -> BankAccount:
        normalized_account_id = _require_text(account_id, "account_id")
        try:
            return self._accounts[normalized_account_id]
        except KeyError as exc:
            raise CoreBankingError(f"Unknown account: {normalized_account_id}") from exc

    def _require_open_account(self, account_id: str) -> BankAccount:
        account = self._get_account(account_id)
        if account.status == AccountStatus.CLOSED:
            raise CoreBankingError("Account is closed")
        return account

    def _require_debit_allowed_account(self, account_id: str) -> BankAccount:
        account = self._require_open_account(account_id)
        if account.status == AccountStatus.FROZEN:
            raise CoreBankingError("Account is frozen")
        return account

    def _require_active_hold(self, hold_id: str) -> AccountHold:
        normalized_hold_id = _require_text(hold_id, "hold_id")
        try:
            hold = self._holds[normalized_hold_id]
        except KeyError as exc:
            raise CoreBankingError(f"Unknown hold: {normalized_hold_id}") from exc
        if hold.status != HoldStatus.ACTIVE:
            raise CoreBankingError("Hold is not active")
        return hold


def money(value: str | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise CoreBankingError(f"Invalid money amount: {value!r}") from exc
    if amount <= Decimal("0.00"):
        raise CoreBankingError("Amount must be positive")
    return amount


def _rate(value: str | int | Decimal) -> Decimal:
    try:
        rate = Decimal(str(value)).quantize(RATE_SCALE, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise CoreBankingError(f"Invalid rate: {value!r}") from exc
    if rate < Decimal("0.000000"):
        raise CoreBankingError("Rate must be greater than or equal to 0")
    return rate


def _currency(value: str) -> str:
    currency = _require_text(value, "currency").upper()
    if len(currency) != 3:
        raise CoreBankingError("currency must be a three-letter code")
    return currency


def _timestamp(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CoreBankingError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise CoreBankingError(f"{field_name} is required")
    return normalized


def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _fingerprint(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
