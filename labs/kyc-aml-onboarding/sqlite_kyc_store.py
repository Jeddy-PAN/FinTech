from __future__ import annotations

import sqlite3
import json
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from kyc_aml import (
    BeneficialOwner,
    CheckResult,
    CustomerApplication,
    CustomerType,
    KycAmlError,
    KycAmlPolicy,
    KycDecision,
    KycDecisionStatus,
    KycReviewCase,
    KycReviewStatus,
    WatchlistEntry,
    normalize_watchlist_entry,
    normalize_application,
)

if TYPE_CHECKING:
    from kyc_replay import KycReplayItem, KycReplayReport


@dataclass(frozen=True)
class KycAuditEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor: str
    reason: str | None
    payload: str
    occurred_at: datetime


@dataclass(frozen=True)
class KycWatchlistVersion:
    version_id: str
    source: str
    entry_count: int
    content_hash: str
    effective_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class KycPolicyVersion:
    version_id: str
    high_risk_countries: tuple[str, ...]
    beneficial_owner_threshold_percent: int
    high_expected_monthly_volume_cents: int
    fuzzy_review_score_threshold: int
    exact_block_score_threshold: int
    risk_score_review_threshold: int
    source: str
    effective_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class KycReplayRun:
    run_id: str
    replay_policy_version_id: str | None
    replay_watchlist_version_id: str | None
    total_applications: int
    status_changed_count: int
    increased_risk_count: int
    decreased_risk_count: int
    unchanged_risk_count: int
    status: str
    created_by: str
    created_at: datetime
    reviewed_by: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None


class SQLiteKycStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row
        self._create_schema()
        self._migrate_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def applications(self) -> tuple[CustomerApplication, ...]:
        rows = self._connection.execute(
            """
            SELECT customer_id
            FROM kyc_applications
            ORDER BY submitted_at, customer_id
            """
        ).fetchall()
        return tuple(self.get_application(row["customer_id"]) for row in rows)

    @property
    def decisions(self) -> tuple[KycDecision, ...]:
        rows = self._connection.execute(
            """
            SELECT customer_id
            FROM kyc_decisions
            ORDER BY decided_at, customer_id
            """
        ).fetchall()
        return tuple(self.get_decision(row["customer_id"]) for row in rows)

    @property
    def review_cases(self) -> tuple[KycReviewCase, ...]:
        rows = self._connection.execute(
            """
            SELECT case_id
            FROM kyc_review_cases
            ORDER BY created_at, case_id
            """
        ).fetchall()
        return tuple(self.get_review_case(row["case_id"]) for row in rows)

    @property
    def pending_review_cases(self) -> tuple[KycReviewCase, ...]:
        rows = self._connection.execute(
            """
            SELECT case_id
            FROM kyc_review_cases
            WHERE status = 'pending_review'
            ORDER BY created_at, case_id
            """
        ).fetchall()
        return tuple(self.get_review_case(row["case_id"]) for row in rows)

    @property
    def audit_events(self) -> tuple[KycAuditEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                actor,
                reason,
                payload,
                occurred_at
            FROM kyc_audit_events
            ORDER BY occurred_at, rowid
            """
        ).fetchall()
        return tuple(self._audit_event_from_row(row) for row in rows)

    def audit_events_for(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
    ) -> tuple[KycAuditEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                actor,
                reason,
                payload,
                occurred_at
            FROM kyc_audit_events
            WHERE aggregate_type = ? AND aggregate_id = ?
            ORDER BY occurred_at, rowid
            """,
            (aggregate_type, aggregate_id),
        ).fetchall()
        return tuple(self._audit_event_from_row(row) for row in rows)

    @property
    def watchlist_versions(self) -> tuple[KycWatchlistVersion, ...]:
        rows = self._connection.execute(
            """
            SELECT
                version_id,
                source,
                entry_count,
                content_hash,
                effective_at,
                created_at
            FROM kyc_watchlist_versions
            ORDER BY effective_at, version_id
            """
        ).fetchall()
        return tuple(self._watchlist_version_from_row(row) for row in rows)

    @property
    def policy_versions(self) -> tuple[KycPolicyVersion, ...]:
        rows = self._connection.execute(
            """
            SELECT
                version_id,
                high_risk_countries,
                beneficial_owner_threshold_percent,
                high_expected_monthly_volume_cents,
                fuzzy_review_score_threshold,
                exact_block_score_threshold,
                risk_score_review_threshold,
                source,
                effective_at,
                created_at
            FROM kyc_policy_versions
            ORDER BY effective_at, version_id
            """
        ).fetchall()
        return tuple(self._policy_version_from_row(row) for row in rows)

    def save_watchlist_version(
        self,
        watchlist: tuple[WatchlistEntry, ...],
        *,
        version_id: str,
        source: str,
        effective_at: datetime,
        created_at: datetime,
    ) -> KycWatchlistVersion:
        normalized_version_id = version_id.strip()
        if not normalized_version_id:
            raise KycAmlError("Watchlist version id is required")
        normalized_source = source.strip()
        if not normalized_source:
            raise KycAmlError("Watchlist source is required")
        _validate_timestamp(effective_at, field_name="effective_at")
        _validate_timestamp(created_at, field_name="created_at")
        normalized_watchlist = tuple(normalize_watchlist_entry(item) for item in watchlist)

        watchlist_version = KycWatchlistVersion(
            version_id=normalized_version_id,
            source=normalized_source,
            entry_count=len(normalized_watchlist),
            content_hash=_watchlist_content_hash(normalized_watchlist),
            effective_at=effective_at,
            created_at=created_at,
        )
        existing = self.find_watchlist_version(watchlist_version.version_id)
        if existing is not None:
            if existing == watchlist_version:
                return existing
            raise KycAmlError(
                f"KYC watchlist version already exists: {watchlist_version.version_id}"
            )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_watchlist_versions (
                    version_id,
                    source,
                    entry_count,
                    content_hash,
                    effective_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    watchlist_version.version_id,
                    watchlist_version.source,
                    watchlist_version.entry_count,
                    watchlist_version.content_hash,
                    watchlist_version.effective_at.isoformat(),
                    watchlist_version.created_at.isoformat(),
                ),
            )
            self._insert_audit_event(
                event_type="kyc_watchlist_version.saved",
                aggregate_type="kyc_watchlist_version",
                aggregate_id=watchlist_version.version_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"version_id":"{watchlist_version.version_id}",'
                    f'"source":"{watchlist_version.source}",'
                    f'"entry_count":{watchlist_version.entry_count},'
                    f'"content_hash":"{watchlist_version.content_hash}"'
                    "}"
                ),
                occurred_at=created_at,
            )

        return watchlist_version

    def find_watchlist_version(self, version_id: str) -> KycWatchlistVersion | None:
        row = self._connection.execute(
            """
            SELECT
                version_id,
                source,
                entry_count,
                content_hash,
                effective_at,
                created_at
            FROM kyc_watchlist_versions
            WHERE version_id = ?
            """,
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        return self._watchlist_version_from_row(row)

    def get_watchlist_version(self, version_id: str) -> KycWatchlistVersion:
        watchlist_version = self.find_watchlist_version(version_id)
        if watchlist_version is None:
            raise KycAmlError(f"Unknown KYC watchlist version: {version_id}")
        return watchlist_version

    def watchlist_version_for_decision(
        self,
        customer_id: str,
    ) -> KycWatchlistVersion | None:
        row = self._connection.execute(
            """
            SELECT watchlist_version_id
            FROM kyc_decisions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        if row is None:
            raise KycAmlError(f"Unknown KYC decision: {customer_id}")
        if row["watchlist_version_id"] is None:
            return None
        return self.get_watchlist_version(row["watchlist_version_id"])

    def save_policy_version(
        self,
        policy: KycAmlPolicy,
        *,
        version_id: str,
        source: str,
        effective_at: datetime,
        created_at: datetime,
    ) -> KycPolicyVersion:
        normalized_version_id = version_id.strip()
        if not normalized_version_id:
            raise KycAmlError("KYC policy version id is required")
        normalized_source = source.strip()
        if not normalized_source:
            raise KycAmlError("KYC policy source is required")
        _validate_timestamp(effective_at, field_name="effective_at")
        _validate_timestamp(created_at, field_name="created_at")
        normalized_policy = _normalize_policy(policy)

        policy_version = KycPolicyVersion(
            version_id=normalized_version_id,
            high_risk_countries=normalized_policy.high_risk_countries,
            beneficial_owner_threshold_percent=(
                normalized_policy.beneficial_owner_threshold_percent
            ),
            high_expected_monthly_volume_cents=(
                normalized_policy.high_expected_monthly_volume_cents
            ),
            fuzzy_review_score_threshold=normalized_policy.fuzzy_review_score_threshold,
            exact_block_score_threshold=normalized_policy.exact_block_score_threshold,
            risk_score_review_threshold=normalized_policy.risk_score_review_threshold,
            source=normalized_source,
            effective_at=effective_at,
            created_at=created_at,
        )
        existing = self.find_policy_version(policy_version.version_id)
        if existing is not None:
            if existing == policy_version:
                return existing
            raise KycAmlError(
                f"KYC policy version already exists: {policy_version.version_id}"
            )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_policy_versions (
                    version_id,
                    high_risk_countries,
                    beneficial_owner_threshold_percent,
                    high_expected_monthly_volume_cents,
                    fuzzy_review_score_threshold,
                    exact_block_score_threshold,
                    risk_score_review_threshold,
                    source,
                    effective_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_version.version_id,
                    json.dumps(
                        policy_version.high_risk_countries,
                        separators=(",", ":"),
                    ),
                    policy_version.beneficial_owner_threshold_percent,
                    policy_version.high_expected_monthly_volume_cents,
                    policy_version.fuzzy_review_score_threshold,
                    policy_version.exact_block_score_threshold,
                    policy_version.risk_score_review_threshold,
                    policy_version.source,
                    policy_version.effective_at.isoformat(),
                    policy_version.created_at.isoformat(),
                ),
            )
            self._insert_audit_event(
                event_type="kyc_policy_version.saved",
                aggregate_type="kyc_policy_version",
                aggregate_id=policy_version.version_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"version_id":"{policy_version.version_id}",'
                    f'"source":"{policy_version.source}",'
                    f'"high_risk_country_count":{len(policy_version.high_risk_countries)},'
                    f'"risk_score_review_threshold":{policy_version.risk_score_review_threshold}'
                    "}"
                ),
                occurred_at=created_at,
            )

        return policy_version

    def find_policy_version(self, version_id: str) -> KycPolicyVersion | None:
        row = self._connection.execute(
            """
            SELECT
                version_id,
                high_risk_countries,
                beneficial_owner_threshold_percent,
                high_expected_monthly_volume_cents,
                fuzzy_review_score_threshold,
                exact_block_score_threshold,
                risk_score_review_threshold,
                source,
                effective_at,
                created_at
            FROM kyc_policy_versions
            WHERE version_id = ?
            """,
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        return self._policy_version_from_row(row)

    def get_policy_version(self, version_id: str) -> KycPolicyVersion:
        policy_version = self.find_policy_version(version_id)
        if policy_version is None:
            raise KycAmlError(f"Unknown KYC policy version: {version_id}")
        return policy_version

    def policy_version_for_decision(
        self,
        customer_id: str,
    ) -> KycPolicyVersion | None:
        row = self._connection.execute(
            """
            SELECT policy_version_id
            FROM kyc_decisions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        if row is None:
            raise KycAmlError(f"Unknown KYC decision: {customer_id}")
        if row["policy_version_id"] is None:
            return None
        return self.get_policy_version(row["policy_version_id"])

    @property
    def replay_runs(self) -> tuple[KycReplayRun, ...]:
        rows = self._connection.execute(
            """
            SELECT
                run_id,
                replay_policy_version_id,
                replay_watchlist_version_id,
                total_applications,
                status_changed_count,
                increased_risk_count,
                decreased_risk_count,
                unchanged_risk_count,
                status,
                created_by,
                created_at,
                reviewed_by,
                review_reason,
                reviewed_at
            FROM kyc_replay_runs
            ORDER BY created_at, run_id
            """
        ).fetchall()
        return tuple(self._replay_run_from_row(row) for row in rows)

    def save_replay_run(
        self,
        report: "KycReplayReport",
        *,
        run_id: str,
        created_by: str,
        created_at: datetime,
    ) -> KycReplayRun:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise KycAmlError("KYC replay run id is required")
        normalized_created_by = created_by.strip()
        if not normalized_created_by:
            raise KycAmlError("KYC replay run creator is required")
        _validate_timestamp(created_at, field_name="created_at")
        if report.replay_policy_version_id is not None:
            self._normalize_policy_version_id(report.replay_policy_version_id)
        if report.replay_watchlist_version_id is not None:
            self._normalize_watchlist_version_id(report.replay_watchlist_version_id)

        replay_run = KycReplayRun(
            run_id=normalized_run_id,
            replay_policy_version_id=report.replay_policy_version_id,
            replay_watchlist_version_id=report.replay_watchlist_version_id,
            total_applications=report.total_applications,
            status_changed_count=report.status_changed_count,
            increased_risk_count=report.increased_risk_count,
            decreased_risk_count=report.decreased_risk_count,
            unchanged_risk_count=report.unchanged_risk_count,
            status="pending_review",
            created_by=normalized_created_by,
            created_at=created_at,
        )
        existing = self.find_replay_run(replay_run.run_id)
        if existing is not None:
            if (
                existing == replay_run
                and self.replay_run_items(replay_run.run_id) == report.items
            ):
                return existing
            raise KycAmlError(f"KYC replay run already exists: {replay_run.run_id}")

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_replay_runs (
                    run_id,
                    replay_policy_version_id,
                    replay_watchlist_version_id,
                    total_applications,
                    status_changed_count,
                    increased_risk_count,
                    decreased_risk_count,
                    unchanged_risk_count,
                    status,
                    created_by,
                    created_at,
                    reviewed_by,
                    review_reason,
                    reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._replay_run_to_row(replay_run),
            )
            self._insert_replay_run_items(replay_run.run_id, report.items)
            self._insert_audit_event(
                event_type="kyc_replay_run.created",
                aggregate_type="kyc_replay_run",
                aggregate_id=replay_run.run_id,
                actor=replay_run.created_by,
                reason=None,
                payload=(
                    "{"
                    f'"run_id":"{replay_run.run_id}",'
                    f'"status":"{replay_run.status}",'
                    f'"total_applications":{replay_run.total_applications},'
                    f'"status_changed_count":{replay_run.status_changed_count}'
                    "}"
                ),
                occurred_at=created_at,
            )

        return replay_run

    def find_replay_run(self, run_id: str) -> KycReplayRun | None:
        row = self._connection.execute(
            """
            SELECT
                run_id,
                replay_policy_version_id,
                replay_watchlist_version_id,
                total_applications,
                status_changed_count,
                increased_risk_count,
                decreased_risk_count,
                unchanged_risk_count,
                status,
                created_by,
                created_at,
                reviewed_by,
                review_reason,
                reviewed_at
            FROM kyc_replay_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._replay_run_from_row(row)

    def get_replay_run(self, run_id: str) -> KycReplayRun:
        replay_run = self.find_replay_run(run_id)
        if replay_run is None:
            raise KycAmlError(f"Unknown KYC replay run: {run_id}")
        return replay_run

    def replay_run_items(self, run_id: str) -> tuple["KycReplayItem", ...]:
        if self.find_replay_run(run_id) is None:
            raise KycAmlError(f"Unknown KYC replay run: {run_id}")
        rows = self._connection.execute(
            """
            SELECT
                customer_id,
                original_status,
                replay_status,
                status_changed,
                original_risk_score,
                replay_risk_score,
                risk_score_delta,
                original_check_ids,
                replay_check_ids,
                new_check_ids,
                resolved_check_ids
            FROM kyc_replay_run_items
            WHERE run_id = ?
            ORDER BY sequence
            """,
            (run_id,),
        ).fetchall()
        return tuple(self._replay_item_from_row(row) for row in rows)

    def approve_replay_run(
        self,
        run_id: str,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> KycReplayRun:
        return self._complete_replay_run(
            run_id,
            status="approved",
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def reject_replay_run(
        self,
        run_id: str,
        *,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> KycReplayRun:
        return self._complete_replay_run(
            run_id,
            status="rejected",
            reviewed_by=reviewed_by,
            reason=reason,
            reviewed_at=reviewed_at,
        )

    def save_application(
        self,
        application: CustomerApplication,
        *,
        submitted_at: datetime,
    ) -> CustomerApplication:
        _validate_timestamp(submitted_at, field_name="submitted_at")
        application = normalize_application(application)
        existing = self.find_application(application.customer_id)
        if existing is not None:
            if existing == application:
                return existing
            raise KycAmlError(f"KYC application already exists: {application.customer_id}")

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_applications (
                    customer_id,
                    customer_type,
                    full_name,
                    country,
                    address,
                    identification_number,
                    expected_monthly_volume_cents,
                    date_of_birth,
                    submitted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application.customer_id,
                    application.customer_type.value,
                    application.full_name,
                    application.country,
                    application.address,
                    application.identification_number,
                    application.expected_monthly_volume_cents,
                    _date_or_none(application.date_of_birth),
                    submitted_at.isoformat(),
                ),
            )
            self._insert_beneficial_owners(application)
            self._insert_audit_event(
                event_type="kyc_application.saved",
                aggregate_type="kyc_application",
                aggregate_id=application.customer_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"customer_id":"{application.customer_id}",'
                    f'"customer_type":"{application.customer_type.value}",'
                    f'"beneficial_owner_count":{len(application.beneficial_owners)}'
                    "}"
                ),
                occurred_at=submitted_at,
            )

        return application

    def find_application(self, customer_id: str) -> CustomerApplication | None:
        row = self._connection.execute(
            """
            SELECT
                customer_id,
                customer_type,
                full_name,
                country,
                address,
                identification_number,
                expected_monthly_volume_cents,
                date_of_birth
            FROM kyc_applications
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        if row is None:
            return None
        return self._application_from_row(row)

    def get_application(self, customer_id: str) -> CustomerApplication:
        application = self.find_application(customer_id)
        if application is None:
            raise KycAmlError(f"Unknown KYC application: {customer_id}")
        return application

    def save_decision(
        self,
        decision: KycDecision,
        *,
        decided_at: datetime,
        watchlist_version_id: str | None = None,
        policy_version_id: str | None = None,
    ) -> KycDecision:
        _validate_timestamp(decided_at, field_name="decided_at")
        if self.find_application(decision.customer_id) is None:
            raise KycAmlError(
                f"Unknown KYC application for decision: {decision.customer_id}"
            )

        existing = self.find_decision(decision.customer_id)
        if existing is not None:
            if existing == decision:
                self._ensure_existing_decision_versions(
                    decision.customer_id,
                    watchlist_version_id,
                    policy_version_id,
                )
                return existing
            raise KycAmlError(f"KYC decision already exists: {decision.customer_id}")
        normalized_watchlist_version_id = self._normalize_watchlist_version_id(
            watchlist_version_id
        )
        normalized_policy_version_id = self._normalize_policy_version_id(
            policy_version_id
        )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_decisions (
                    customer_id,
                    status,
                    risk_score,
                    decided_at,
                    watchlist_version_id,
                    policy_version_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.customer_id,
                    decision.status.value,
                    decision.risk_score,
                    decided_at.isoformat(),
                    normalized_watchlist_version_id,
                    normalized_policy_version_id,
                ),
            )
            self._insert_check_results(
                "kyc_check_results",
                "customer_id",
                decision.customer_id,
                decision.check_results,
            )
            self._insert_audit_event(
                event_type="kyc_decision.saved",
                aggregate_type="kyc_decision",
                aggregate_id=decision.customer_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"customer_id":"{decision.customer_id}",'
                    f'"status":"{decision.status.value}",'
                    f'"watchlist_version_id":{self._json_string_or_null(normalized_watchlist_version_id)},'
                    f'"policy_version_id":{self._json_string_or_null(normalized_policy_version_id)},'
                    f'"risk_score":{decision.risk_score},'
                    f'"check_result_count":{len(decision.check_results)}'
                    "}"
                ),
                occurred_at=decided_at,
            )

        return decision

    def find_decision(self, customer_id: str) -> KycDecision | None:
        row = self._connection.execute(
            """
            SELECT customer_id, status, risk_score
            FROM kyc_decisions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        if row is None:
            return None
        return self._decision_from_row(row)

    def get_decision(self, customer_id: str) -> KycDecision:
        decision = self.find_decision(customer_id)
        if decision is None:
            raise KycAmlError(f"Unknown KYC decision: {customer_id}")
        return decision

    def save_review_case(self, review_case: KycReviewCase) -> KycReviewCase:
        _validate_timestamp(review_case.created_at, field_name="created_at")
        if review_case.reviewed_at is not None:
            _validate_timestamp(review_case.reviewed_at, field_name="reviewed_at")

        decision = self.find_decision(review_case.customer_id)
        if decision is None:
            raise KycAmlError(
                f"Unknown KYC decision for review case: {review_case.customer_id}"
            )
        if decision.status != KycDecisionStatus.REVIEW:
            raise KycAmlError("Only review decisions can create KYC review cases")

        existing = self.find_review_case(review_case.case_id)
        if existing is not None:
            if existing == review_case:
                return existing
            return self._update_review_case(existing, review_case)

        if review_case.status != KycReviewStatus.PENDING_REVIEW:
            raise KycAmlError("KYC review case must be pending before completion")
        self._validate_pending_review_case(review_case)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO kyc_review_cases (
                    case_id,
                    customer_id,
                    status,
                    created_at,
                    reviewed_by,
                    review_reason,
                    reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._review_case_to_row(review_case),
            )
            self._insert_check_results(
                "kyc_review_case_check_results",
                "case_id",
                review_case.case_id,
                review_case.check_results,
            )
            self._insert_audit_event(
                event_type="kyc_review_case.created",
                aggregate_type="kyc_review_case",
                aggregate_id=review_case.case_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"case_id":"{review_case.case_id}",'
                    f'"customer_id":"{review_case.customer_id}",'
                    f'"status":"{review_case.status.value}"'
                    "}"
                ),
                occurred_at=review_case.created_at,
            )

        return review_case

    def find_review_case(self, case_id: str) -> KycReviewCase | None:
        row = self._connection.execute(
            """
            SELECT
                case_id,
                customer_id,
                status,
                created_at,
                reviewed_by,
                review_reason,
                reviewed_at
            FROM kyc_review_cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        if row is None:
            return None
        return self._review_case_from_row(row)

    def get_review_case(self, case_id: str) -> KycReviewCase:
        review_case = self.find_review_case(case_id)
        if review_case is None:
            raise KycAmlError(f"Unknown KYC review case: {case_id}")
        return review_case

    def _update_review_case(
        self,
        existing: KycReviewCase,
        incoming: KycReviewCase,
    ) -> KycReviewCase:
        if existing.status != KycReviewStatus.PENDING_REVIEW:
            raise KycAmlError(
                f"KYC review case is already completed: {existing.case_id}"
            )
        if incoming.status == KycReviewStatus.PENDING_REVIEW:
            raise KycAmlError(f"KYC review case already exists: {existing.case_id}")

        expected_pending = KycReviewCase(
            case_id=incoming.case_id,
            customer_id=incoming.customer_id,
            status=KycReviewStatus.PENDING_REVIEW,
            check_results=incoming.check_results,
            created_at=incoming.created_at,
        )
        if existing != expected_pending:
            raise KycAmlError(f"KYC review case already exists: {existing.case_id}")
        self._validate_completed_review_case(incoming)

        with self._connection:
            self._connection.execute(
                """
                UPDATE kyc_review_cases
                SET
                    status = ?,
                    reviewed_by = ?,
                    review_reason = ?,
                    reviewed_at = ?
                WHERE case_id = ?
                """,
                (
                    incoming.status.value,
                    incoming.reviewed_by,
                    incoming.review_reason,
                    incoming.reviewed_at.isoformat(),
                    incoming.case_id,
                ),
            )
            self._insert_audit_event(
                event_type=f"kyc_review_case.{incoming.status.value}",
                aggregate_type="kyc_review_case",
                aggregate_id=incoming.case_id,
                actor=incoming.reviewed_by or "unknown",
                reason=incoming.review_reason,
                payload=(
                    "{"
                    f'"case_id":"{incoming.case_id}",'
                    f'"customer_id":"{incoming.customer_id}",'
                    f'"status":"{incoming.status.value}"'
                    "}"
                ),
                occurred_at=incoming.reviewed_at,
            )

        return self.get_review_case(incoming.case_id)

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS kyc_applications (
                    customer_id TEXT PRIMARY KEY,
                    customer_type TEXT NOT NULL CHECK (customer_type IN ('individual', 'legal_entity')),
                    full_name TEXT NOT NULL,
                    country TEXT NOT NULL,
                    address TEXT NOT NULL,
                    identification_number TEXT NOT NULL,
                    expected_monthly_volume_cents INTEGER NOT NULL,
                    date_of_birth TEXT,
                    submitted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kyc_beneficial_owners (
                    customer_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    owner_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    ownership_percent INTEGER NOT NULL,
                    country TEXT NOT NULL,
                    identification_number TEXT NOT NULL,
                    date_of_birth TEXT,
                    PRIMARY KEY (customer_id, sequence),
                    FOREIGN KEY (customer_id) REFERENCES kyc_applications(customer_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_decisions (
                    customer_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    risk_score INTEGER NOT NULL,
                    decided_at TEXT NOT NULL,
                    watchlist_version_id TEXT,
                    policy_version_id TEXT,
                    FOREIGN KEY (customer_id) REFERENCES kyc_applications(customer_id),
                    FOREIGN KEY (watchlist_version_id) REFERENCES kyc_watchlist_versions(version_id),
                    FOREIGN KEY (policy_version_id) REFERENCES kyc_policy_versions(version_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_watchlist_versions (
                    version_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kyc_policy_versions (
                    version_id TEXT PRIMARY KEY,
                    high_risk_countries TEXT NOT NULL,
                    beneficial_owner_threshold_percent INTEGER NOT NULL,
                    high_expected_monthly_volume_cents INTEGER NOT NULL,
                    fuzzy_review_score_threshold INTEGER NOT NULL,
                    exact_block_score_threshold INTEGER NOT NULL,
                    risk_score_review_threshold INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kyc_check_results (
                    customer_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    check_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    reason TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    PRIMARY KEY (customer_id, sequence),
                    FOREIGN KEY (customer_id) REFERENCES kyc_decisions(customer_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_review_cases (
                    case_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending_review', 'approved', 'rejected', 'request_more_info')),
                    created_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    review_reason TEXT,
                    reviewed_at TEXT,
                    FOREIGN KEY (customer_id) REFERENCES kyc_decisions(customer_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_review_case_check_results (
                    case_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    check_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    reason TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    PRIMARY KEY (case_id, sequence),
                    FOREIGN KEY (case_id) REFERENCES kyc_review_cases(case_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_replay_runs (
                    run_id TEXT PRIMARY KEY,
                    replay_policy_version_id TEXT,
                    replay_watchlist_version_id TEXT,
                    total_applications INTEGER NOT NULL,
                    status_changed_count INTEGER NOT NULL,
                    increased_risk_count INTEGER NOT NULL,
                    decreased_risk_count INTEGER NOT NULL,
                    unchanged_risk_count INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending_review', 'approved', 'rejected')),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    review_reason TEXT,
                    reviewed_at TEXT,
                    FOREIGN KEY (replay_policy_version_id) REFERENCES kyc_policy_versions(version_id),
                    FOREIGN KEY (replay_watchlist_version_id) REFERENCES kyc_watchlist_versions(version_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_replay_run_items (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    customer_id TEXT NOT NULL,
                    original_status TEXT NOT NULL,
                    replay_status TEXT NOT NULL,
                    status_changed INTEGER NOT NULL,
                    original_risk_score INTEGER NOT NULL,
                    replay_risk_score INTEGER NOT NULL,
                    risk_score_delta INTEGER NOT NULL,
                    original_check_ids TEXT NOT NULL,
                    replay_check_ids TEXT NOT NULL,
                    new_check_ids TEXT NOT NULL,
                    resolved_check_ids TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES kyc_replay_runs(run_id),
                    FOREIGN KEY (customer_id) REFERENCES kyc_applications(customer_id)
                );

                CREATE TABLE IF NOT EXISTS kyc_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_kyc_applications_submitted_at
                ON kyc_applications (submitted_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_decisions_status
                ON kyc_decisions (status, decided_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_decisions_watchlist_version
                ON kyc_decisions (watchlist_version_id);

                CREATE INDEX IF NOT EXISTS idx_kyc_decisions_policy_version
                ON kyc_decisions (policy_version_id);

                CREATE INDEX IF NOT EXISTS idx_kyc_watchlist_versions_effective_at
                ON kyc_watchlist_versions (effective_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_policy_versions_effective_at
                ON kyc_policy_versions (effective_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_review_cases_status
                ON kyc_review_cases (status, created_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_replay_runs_status
                ON kyc_replay_runs (status, created_at);

                CREATE INDEX IF NOT EXISTS idx_kyc_audit_events_aggregate
                ON kyc_audit_events (aggregate_type, aggregate_id, occurred_at);
                """
            )

    def _migrate_schema(self) -> None:
        decision_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(kyc_decisions)")
        }
        with self._connection:
            if "watchlist_version_id" not in decision_columns:
                self._connection.execute(
                    """
                    ALTER TABLE kyc_decisions
                    ADD COLUMN watchlist_version_id TEXT
                    """
                )
            if "policy_version_id" not in decision_columns:
                self._connection.execute(
                    """
                    ALTER TABLE kyc_decisions
                    ADD COLUMN policy_version_id TEXT
                    """
                )

    def _application_from_row(self, row: sqlite3.Row) -> CustomerApplication:
        return CustomerApplication(
            customer_id=row["customer_id"],
            customer_type=CustomerType(row["customer_type"]),
            full_name=row["full_name"],
            country=row["country"],
            address=row["address"],
            identification_number=row["identification_number"],
            expected_monthly_volume_cents=row["expected_monthly_volume_cents"],
            date_of_birth=_date_from_row(row["date_of_birth"]),
            beneficial_owners=self._beneficial_owners_for(row["customer_id"]),
        )

    def _beneficial_owners_for(
        self,
        customer_id: str,
    ) -> tuple[BeneficialOwner, ...]:
        rows = self._connection.execute(
            """
            SELECT
                owner_id,
                full_name,
                ownership_percent,
                country,
                identification_number,
                date_of_birth
            FROM kyc_beneficial_owners
            WHERE customer_id = ?
            ORDER BY sequence
            """,
            (customer_id,),
        ).fetchall()
        return tuple(
            BeneficialOwner(
                owner_id=row["owner_id"],
                full_name=row["full_name"],
                ownership_percent=row["ownership_percent"],
                country=row["country"],
                identification_number=row["identification_number"],
                date_of_birth=_date_from_row(row["date_of_birth"]),
            )
            for row in rows
        )

    def _decision_from_row(self, row: sqlite3.Row) -> KycDecision:
        return KycDecision(
            customer_id=row["customer_id"],
            status=KycDecisionStatus(row["status"]),
            check_results=self._check_results_for(
                "kyc_check_results",
                "customer_id",
                row["customer_id"],
            ),
            risk_score=row["risk_score"],
        )

    def _review_case_from_row(self, row: sqlite3.Row) -> KycReviewCase:
        return KycReviewCase(
            case_id=row["case_id"],
            customer_id=row["customer_id"],
            status=KycReviewStatus(row["status"]),
            check_results=self._check_results_for(
                "kyc_review_case_check_results",
                "case_id",
                row["case_id"],
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            reviewed_by=row["reviewed_by"],
            review_reason=row["review_reason"],
            reviewed_at=(
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"] is not None
                else None
            ),
        )

    def _insert_beneficial_owners(self, application: CustomerApplication) -> None:
        for sequence, owner in enumerate(application.beneficial_owners):
            self._connection.execute(
                """
                INSERT INTO kyc_beneficial_owners (
                    customer_id,
                    sequence,
                    owner_id,
                    full_name,
                    ownership_percent,
                    country,
                    identification_number,
                    date_of_birth
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application.customer_id,
                    sequence,
                    owner.owner_id,
                    owner.full_name,
                    owner.ownership_percent,
                    owner.country,
                    owner.identification_number,
                    _date_or_none(owner.date_of_birth),
                ),
            )

    def _insert_check_results(
        self,
        table_name: str,
        owner_column: str,
        owner_id: str,
        check_results: tuple[CheckResult, ...],
    ) -> None:
        for sequence, result in enumerate(check_results):
            self._connection.execute(
                f"""
                INSERT INTO {table_name} (
                    {owner_column},
                    sequence,
                    check_id,
                    status,
                    reason,
                    score
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    sequence,
                    result.check_id,
                    result.status.value,
                    result.reason,
                    result.score,
                ),
            )

    def _check_results_for(
        self,
        table_name: str,
        owner_column: str,
        owner_id: str,
    ) -> tuple[CheckResult, ...]:
        rows = self._connection.execute(
            f"""
            SELECT check_id, status, reason, score
            FROM {table_name}
            WHERE {owner_column} = ?
            ORDER BY sequence
            """,
            (owner_id,),
        ).fetchall()
        return tuple(
            CheckResult(
                check_id=row["check_id"],
                status=KycDecisionStatus(row["status"]),
                reason=row["reason"],
                score=row["score"],
            )
            for row in rows
        )

    def _review_case_to_row(
        self,
        review_case: KycReviewCase,
    ) -> tuple[str, str, str, str, str | None, str | None, str | None]:
        return (
            review_case.case_id,
            review_case.customer_id,
            review_case.status.value,
            review_case.created_at.isoformat(),
            review_case.reviewed_by,
            review_case.review_reason,
            (
                review_case.reviewed_at.isoformat()
                if review_case.reviewed_at is not None
                else None
            ),
        )

    def _complete_replay_run(
        self,
        run_id: str,
        *,
        status: str,
        reviewed_by: str,
        reason: str,
        reviewed_at: datetime,
    ) -> KycReplayRun:
        replay_run = self.get_replay_run(run_id)
        if replay_run.status != "pending_review":
            raise KycAmlError(f"KYC replay run is already completed: {run_id}")
        reviewer = reviewed_by.strip()
        if not reviewer:
            raise KycAmlError("KYC replay run reviewer is required")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise KycAmlError("KYC replay run review reason is required")
        _validate_timestamp(reviewed_at, field_name="reviewed_at")

        with self._connection:
            self._connection.execute(
                """
                UPDATE kyc_replay_runs
                SET
                    status = ?,
                    reviewed_by = ?,
                    review_reason = ?,
                    reviewed_at = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    reviewer,
                    normalized_reason,
                    reviewed_at.isoformat(),
                    run_id,
                ),
            )
            self._insert_audit_event(
                event_type=f"kyc_replay_run.{status}",
                aggregate_type="kyc_replay_run",
                aggregate_id=run_id,
                actor=reviewer,
                reason=normalized_reason,
                payload=(
                    "{"
                    f'"run_id":"{run_id}",'
                    f'"status":"{status}"'
                    "}"
                ),
                occurred_at=reviewed_at,
            )

        return self.get_replay_run(run_id)

    def _replay_run_to_row(
        self,
        replay_run: KycReplayRun,
    ) -> tuple[
        str,
        str | None,
        str | None,
        int,
        int,
        int,
        int,
        int,
        str,
        str,
        str,
        str | None,
        str | None,
        str | None,
    ]:
        return (
            replay_run.run_id,
            replay_run.replay_policy_version_id,
            replay_run.replay_watchlist_version_id,
            replay_run.total_applications,
            replay_run.status_changed_count,
            replay_run.increased_risk_count,
            replay_run.decreased_risk_count,
            replay_run.unchanged_risk_count,
            replay_run.status,
            replay_run.created_by,
            replay_run.created_at.isoformat(),
            replay_run.reviewed_by,
            replay_run.review_reason,
            (
                replay_run.reviewed_at.isoformat()
                if replay_run.reviewed_at is not None
                else None
            ),
        )

    def _replay_run_from_row(self, row: sqlite3.Row) -> KycReplayRun:
        return KycReplayRun(
            run_id=row["run_id"],
            replay_policy_version_id=row["replay_policy_version_id"],
            replay_watchlist_version_id=row["replay_watchlist_version_id"],
            total_applications=row["total_applications"],
            status_changed_count=row["status_changed_count"],
            increased_risk_count=row["increased_risk_count"],
            decreased_risk_count=row["decreased_risk_count"],
            unchanged_risk_count=row["unchanged_risk_count"],
            status=row["status"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            reviewed_by=row["reviewed_by"],
            review_reason=row["review_reason"],
            reviewed_at=(
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"] is not None
                else None
            ),
        )

    def _insert_replay_run_items(
        self,
        run_id: str,
        items: tuple["KycReplayItem", ...],
    ) -> None:
        for sequence, item in enumerate(items):
            self._connection.execute(
                """
                INSERT INTO kyc_replay_run_items (
                    run_id,
                    sequence,
                    customer_id,
                    original_status,
                    replay_status,
                    status_changed,
                    original_risk_score,
                    replay_risk_score,
                    risk_score_delta,
                    original_check_ids,
                    replay_check_ids,
                    new_check_ids,
                    resolved_check_ids
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    item.customer_id,
                    item.original_status,
                    item.replay_status,
                    1 if item.status_changed else 0,
                    item.original_risk_score,
                    item.replay_risk_score,
                    item.risk_score_delta,
                    _encode_text_tuple(item.original_check_ids),
                    _encode_text_tuple(item.replay_check_ids),
                    _encode_text_tuple(item.new_check_ids),
                    _encode_text_tuple(item.resolved_check_ids),
                ),
            )

    def _replay_item_from_row(self, row: sqlite3.Row) -> "KycReplayItem":
        from kyc_replay import KycReplayItem

        return KycReplayItem(
            customer_id=row["customer_id"],
            original_status=row["original_status"],
            replay_status=row["replay_status"],
            status_changed=bool(row["status_changed"]),
            original_risk_score=row["original_risk_score"],
            replay_risk_score=row["replay_risk_score"],
            risk_score_delta=row["risk_score_delta"],
            original_check_ids=_decode_text_tuple(row["original_check_ids"]),
            replay_check_ids=_decode_text_tuple(row["replay_check_ids"]),
            new_check_ids=_decode_text_tuple(row["new_check_ids"]),
            resolved_check_ids=_decode_text_tuple(row["resolved_check_ids"]),
        )

    def _insert_audit_event(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor: str,
        reason: str | None,
        payload: str,
        occurred_at: datetime | None,
    ) -> None:
        if occurred_at is None:
            raise KycAmlError("occurred_at is required")
        _validate_timestamp(occurred_at, field_name="occurred_at")
        self._connection.execute(
            """
            INSERT INTO kyc_audit_events (
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                actor,
                reason,
                payload,
                occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                event_type,
                aggregate_type,
                aggregate_id,
                actor.strip() or "unknown",
                reason,
                payload,
                occurred_at.isoformat(),
            ),
        )

    def _audit_event_from_row(self, row: sqlite3.Row) -> KycAuditEvent:
        return KycAuditEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"],
            actor=row["actor"],
            reason=row["reason"],
            payload=row["payload"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )

    def _watchlist_version_from_row(self, row: sqlite3.Row) -> KycWatchlistVersion:
        return KycWatchlistVersion(
            version_id=row["version_id"],
            source=row["source"],
            entry_count=row["entry_count"],
            content_hash=row["content_hash"],
            effective_at=datetime.fromisoformat(row["effective_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _policy_version_from_row(self, row: sqlite3.Row) -> KycPolicyVersion:
        return KycPolicyVersion(
            version_id=row["version_id"],
            high_risk_countries=tuple(json.loads(row["high_risk_countries"])),
            beneficial_owner_threshold_percent=row[
                "beneficial_owner_threshold_percent"
            ],
            high_expected_monthly_volume_cents=row[
                "high_expected_monthly_volume_cents"
            ],
            fuzzy_review_score_threshold=row["fuzzy_review_score_threshold"],
            exact_block_score_threshold=row["exact_block_score_threshold"],
            risk_score_review_threshold=row["risk_score_review_threshold"],
            source=row["source"],
            effective_at=datetime.fromisoformat(row["effective_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _normalize_watchlist_version_id(
        self,
        watchlist_version_id: str | None,
    ) -> str | None:
        if watchlist_version_id is None:
            return None
        normalized = watchlist_version_id.strip()
        if not normalized:
            raise KycAmlError("Watchlist version id is required")
        if self.find_watchlist_version(normalized) is None:
            raise KycAmlError(f"Unknown KYC watchlist version: {normalized}")
        return normalized

    def _normalize_policy_version_id(
        self,
        policy_version_id: str | None,
    ) -> str | None:
        if policy_version_id is None:
            return None
        normalized = policy_version_id.strip()
        if not normalized:
            raise KycAmlError("KYC policy version id is required")
        if self.find_policy_version(normalized) is None:
            raise KycAmlError(f"Unknown KYC policy version: {normalized}")
        return normalized

    def _ensure_existing_decision_versions(
        self,
        customer_id: str,
        watchlist_version_id: str | None,
        policy_version_id: str | None,
    ) -> None:
        normalized_watchlist_version_id = self._normalize_watchlist_version_id(
            watchlist_version_id
        )
        normalized_policy_version_id = self._normalize_policy_version_id(
            policy_version_id
        )
        row = self._connection.execute(
            """
            SELECT watchlist_version_id, policy_version_id
            FROM kyc_decisions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
        if row["watchlist_version_id"] != normalized_watchlist_version_id:
            raise KycAmlError(
                f"KYC decision already exists with different watchlist version: {customer_id}"
            )
        if row["policy_version_id"] != normalized_policy_version_id:
            raise KycAmlError(
                f"KYC decision already exists with different policy version: {customer_id}"
            )

    def _json_string_or_null(self, value: str | None) -> str:
        if value is None:
            return "null"
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _validate_pending_review_case(self, review_case: KycReviewCase) -> None:
        if (
            review_case.reviewed_by is not None
            or review_case.review_reason is not None
            or review_case.reviewed_at is not None
        ):
            raise KycAmlError("Pending KYC review case cannot have review result")

    def _validate_completed_review_case(self, review_case: KycReviewCase) -> None:
        if review_case.reviewed_by is None or not review_case.reviewed_by.strip():
            raise KycAmlError("Reviewer is required")
        if review_case.review_reason is None or not review_case.review_reason.strip():
            raise KycAmlError("Review reason is required")
        if review_case.reviewed_at is None:
            raise KycAmlError("reviewed_at is required")


def _validate_timestamp(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KycAmlError(f"{field_name} must be timezone-aware")


def _date_or_none(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _date_from_row(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _watchlist_content_hash(watchlist: tuple[WatchlistEntry, ...]) -> str:
    payload = [
        {
            "entry_id": item.entry_id,
            "list_name": item.list_name,
            "full_name": item.full_name,
            "country": item.country,
            "date_of_birth": _date_or_none(item.date_of_birth),
        }
        for item in sorted(watchlist, key=lambda entry: entry.entry_id)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _encode_text_tuple(values: tuple[str, ...]) -> str:
    return json.dumps(values, separators=(",", ":"))


def _decode_text_tuple(value: str) -> tuple[str, ...]:
    return tuple(json.loads(value))


def _normalize_policy(policy: KycAmlPolicy) -> KycAmlPolicy:
    normalized_countries = tuple(
        sorted({country.strip().upper() for country in policy.high_risk_countries})
    )
    return KycAmlPolicy(
        high_risk_countries=normalized_countries,
        beneficial_owner_threshold_percent=policy.beneficial_owner_threshold_percent,
        high_expected_monthly_volume_cents=policy.high_expected_monthly_volume_cents,
        fuzzy_review_score_threshold=policy.fuzzy_review_score_threshold,
        exact_block_score_threshold=policy.exact_block_score_threshold,
        risk_score_review_threshold=policy.risk_score_review_threshold,
    )
