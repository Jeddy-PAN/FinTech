from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from risk_rule_engine import (
    ReviewCase,
    ReviewStatus,
    RiskDecision,
    RiskDecisionStatus,
    RiskRuleConfig,
    RiskRuleEngineError,
    RuleHit,
)


@dataclass(frozen=True)
class RiskAuditEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor: str
    reason: str | None
    payload: str
    occurred_at: datetime


@dataclass(frozen=True)
class RiskRuleVersion:
    version_id: str
    single_transaction_review_threshold: str
    daily_user_review_threshold: str
    allowed_currencies: tuple[str, ...]
    high_risk_countries: tuple[str, ...]
    blocked_beneficiaries: tuple[str, ...]
    risk_score_review_threshold: int
    rule_scores: dict[str, int]
    source: str
    effective_at: datetime
    created_at: datetime


class SQLiteRiskStore:
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
    def decisions(self) -> tuple[RiskDecision, ...]:
        rows = self._connection.execute(
            """
            SELECT request_id
            FROM risk_decisions
            ORDER BY decided_at, request_id
            """
        ).fetchall()
        return tuple(self.get_decision(row["request_id"]) for row in rows)

    @property
    def review_cases(self) -> tuple[ReviewCase, ...]:
        rows = self._connection.execute(
            """
            SELECT case_id
            FROM review_cases
            ORDER BY created_at, case_id
            """
        ).fetchall()
        return tuple(self.get_review_case(row["case_id"]) for row in rows)

    @property
    def pending_review_cases(self) -> tuple[ReviewCase, ...]:
        rows = self._connection.execute(
            """
            SELECT case_id
            FROM review_cases
            WHERE status = 'pending_review'
            ORDER BY created_at, case_id
            """
        ).fetchall()
        return tuple(self.get_review_case(row["case_id"]) for row in rows)

    @property
    def audit_events(self) -> tuple[RiskAuditEvent, ...]:
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
            FROM risk_audit_events
            ORDER BY occurred_at, rowid
            """
        ).fetchall()
        return tuple(self._audit_event_from_row(row) for row in rows)

    def audit_events_for(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
    ) -> tuple[RiskAuditEvent, ...]:
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
            FROM risk_audit_events
            WHERE aggregate_type = ? AND aggregate_id = ?
            ORDER BY occurred_at, rowid
            """,
            (aggregate_type, aggregate_id),
        ).fetchall()
        return tuple(self._audit_event_from_row(row) for row in rows)

    @property
    def rule_versions(self) -> tuple[RiskRuleVersion, ...]:
        rows = self._connection.execute(
            """
            SELECT
                version_id,
                single_transaction_review_threshold,
                daily_user_review_threshold,
                allowed_currencies,
                high_risk_countries,
                blocked_beneficiaries,
                risk_score_review_threshold,
                rule_scores,
                source,
                effective_at,
                created_at
            FROM risk_rule_versions
            ORDER BY effective_at, version_id
            """
        ).fetchall()
        return tuple(self._rule_version_from_row(row) for row in rows)

    def save_rule_version(
        self,
        config: RiskRuleConfig,
        *,
        version_id: str,
        effective_at: datetime,
        created_at: datetime,
        source: str = "risk_rules.json",
    ) -> RiskRuleVersion:
        normalized_version_id = version_id.strip()
        if not normalized_version_id:
            raise RiskRuleEngineError("Rule version id is required")
        normalized_source = source.strip()
        if not normalized_source:
            raise RiskRuleEngineError("Rule version source is required")
        _validate_timestamp(effective_at, field_name="effective_at")
        _validate_timestamp(created_at, field_name="created_at")

        rule_version = RiskRuleVersion(
            version_id=normalized_version_id,
            single_transaction_review_threshold=str(
                config.single_transaction_review_threshold
            ),
            daily_user_review_threshold=str(config.daily_user_review_threshold),
            allowed_currencies=tuple(config.allowed_currencies),
            high_risk_countries=tuple(config.high_risk_countries),
            blocked_beneficiaries=tuple(config.blocked_beneficiaries),
            risk_score_review_threshold=config.risk_score_review_threshold,
            rule_scores=dict(config.rule_scores),
            source=normalized_source,
            effective_at=effective_at,
            created_at=created_at,
        )
        existing = self.find_rule_version(rule_version.version_id)
        if existing is not None:
            if existing == rule_version:
                return existing
            raise RiskRuleEngineError(
                f"Risk rule version already exists: {rule_version.version_id}"
            )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO risk_rule_versions (
                    version_id,
                    single_transaction_review_threshold,
                    daily_user_review_threshold,
                    allowed_currencies,
                    high_risk_countries,
                    blocked_beneficiaries,
                    risk_score_review_threshold,
                    rule_scores,
                    source,
                    effective_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._rule_version_to_row(rule_version),
            )
            self._insert_audit_event(
                event_type="risk_rule_version.saved",
                aggregate_type="risk_rule_version",
                aggregate_id=rule_version.version_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"version_id":"{rule_version.version_id}",'
                    f'"source":"{rule_version.source}",'
                    f'"single_transaction_review_threshold":"{rule_version.single_transaction_review_threshold}",'
                    f'"daily_user_review_threshold":"{rule_version.daily_user_review_threshold}",'
                    f'"allowed_currencies":"{",".join(rule_version.allowed_currencies)}",'
                    f'"high_risk_countries":"{",".join(rule_version.high_risk_countries)}",'
                    f'"blocked_beneficiaries":"{",".join(rule_version.blocked_beneficiaries)}",'
                    f'"risk_score_review_threshold":{rule_version.risk_score_review_threshold}'
                    "}"
                ),
                occurred_at=created_at,
            )

        return rule_version

    def find_rule_version(self, version_id: str) -> RiskRuleVersion | None:
        row = self._connection.execute(
            """
            SELECT
                version_id,
                single_transaction_review_threshold,
                daily_user_review_threshold,
                allowed_currencies,
                high_risk_countries,
                blocked_beneficiaries,
                risk_score_review_threshold,
                rule_scores,
                source,
                effective_at,
                created_at
            FROM risk_rule_versions
            WHERE version_id = ?
            """,
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        return self._rule_version_from_row(row)

    def get_rule_version(self, version_id: str) -> RiskRuleVersion:
        rule_version = self.find_rule_version(version_id)
        if rule_version is None:
            raise RiskRuleEngineError(f"Unknown risk rule version: {version_id}")
        return rule_version

    def rule_version_for_decision(self, request_id: str) -> RiskRuleVersion | None:
        row = self._connection.execute(
            """
            SELECT rule_version_id
            FROM risk_decisions
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise RiskRuleEngineError(f"Unknown risk decision: {request_id}")
        if row["rule_version_id"] is None:
            return None
        return self.get_rule_version(row["rule_version_id"])

    def save_decision(
        self,
        decision: RiskDecision,
        *,
        decided_at: datetime,
        rule_version_id: str | None = None,
    ) -> RiskDecision:
        _validate_timestamp(decided_at, field_name="decided_at")
        existing = self.find_decision(decision.request_id)
        if existing is not None:
            if existing == decision:
                self._ensure_existing_decision_version(
                    decision.request_id,
                    rule_version_id,
                )
                return existing
            raise RiskRuleEngineError(
                f"Risk decision already exists: {decision.request_id}"
            )
        normalized_rule_version_id = self._normalize_rule_version_id(rule_version_id)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO risk_decisions (
                    request_id,
                    user_id,
                    status,
                    decided_at,
                    risk_score,
                    rule_version_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.request_id,
                    decision.user_id,
                    decision.status.value,
                    decided_at.isoformat(),
                    decision.risk_score,
                    normalized_rule_version_id,
                ),
            )
            self._insert_rule_hits(
                "risk_decision_rule_hits",
                "request_id",
                decision.request_id,
                decision.rule_hits,
            )
            self._insert_audit_event(
                event_type="risk_decision.saved",
                aggregate_type="risk_decision",
                aggregate_id=decision.request_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"request_id":"{decision.request_id}",'
                    f'"user_id":"{decision.user_id}",'
                    f'"status":"{decision.status.value}",'
                    f'"rule_version_id":{self._json_string_or_null(normalized_rule_version_id)},'
                    f'"risk_score":{decision.risk_score},'
                    f'"rule_hit_count":{len(decision.rule_hits)}'
                    "}"
                ),
                occurred_at=decided_at,
            )

        return decision

    def find_decision(self, request_id: str) -> RiskDecision | None:
        row = self._connection.execute(
            """
            SELECT request_id, user_id, status, risk_score
            FROM risk_decisions
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return self._decision_from_row(row)

    def get_decision(self, request_id: str) -> RiskDecision:
        decision = self.find_decision(request_id)
        if decision is None:
            raise RiskRuleEngineError(f"Unknown risk decision: {request_id}")
        return decision

    def save_review_case(self, review_case: ReviewCase) -> ReviewCase:
        _validate_timestamp(review_case.created_at, field_name="created_at")
        if review_case.reviewed_at is not None:
            _validate_timestamp(review_case.reviewed_at, field_name="reviewed_at")
        decision = self.find_decision(review_case.request_id)
        if decision is None:
            raise RiskRuleEngineError(
                f"Unknown risk decision for review case: {review_case.request_id}"
            )
        if decision.status != RiskDecisionStatus.REVIEW:
            raise RiskRuleEngineError("Only review decisions can create review cases")

        existing = self.find_review_case(review_case.case_id)
        if existing is not None:
            if existing == review_case:
                return existing
            return self._update_review_case(existing, review_case)

        if review_case.status != ReviewStatus.PENDING_REVIEW:
            raise RiskRuleEngineError("Review case must be pending before completion")
        self._validate_pending_review_case(review_case)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO review_cases (
                    case_id,
                    request_id,
                    user_id,
                    status,
                    created_at,
                    reviewed_by,
                    review_reason,
                    reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._review_case_to_row(review_case),
            )
            self._insert_rule_hits(
                "review_case_rule_hits",
                "case_id",
                review_case.case_id,
                review_case.rule_hits,
            )
            self._insert_audit_event(
                event_type="review_case.created",
                aggregate_type="review_case",
                aggregate_id=review_case.case_id,
                actor="system",
                reason=None,
                payload=(
                    "{"
                    f'"case_id":"{review_case.case_id}",'
                    f'"request_id":"{review_case.request_id}",'
                    f'"user_id":"{review_case.user_id}",'
                    f'"status":"{review_case.status.value}"'
                    "}"
                ),
                occurred_at=review_case.created_at,
            )

        return review_case

    def find_review_case(self, case_id: str) -> ReviewCase | None:
        row = self._connection.execute(
            """
            SELECT
                case_id,
                request_id,
                user_id,
                status,
                created_at,
                reviewed_by,
                review_reason,
                reviewed_at
            FROM review_cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        if row is None:
            return None
        return self._review_case_from_row(row)

    def get_review_case(self, case_id: str) -> ReviewCase:
        review_case = self.find_review_case(case_id)
        if review_case is None:
            raise RiskRuleEngineError(f"Unknown review case: {case_id}")
        return review_case

    def _update_review_case(
        self,
        existing: ReviewCase,
        incoming: ReviewCase,
    ) -> ReviewCase:
        if existing.status != ReviewStatus.PENDING_REVIEW:
            raise RiskRuleEngineError(f"Review case is already completed: {existing.case_id}")

        if incoming.status == ReviewStatus.PENDING_REVIEW:
            raise RiskRuleEngineError(f"Review case already exists: {existing.case_id}")

        expected_pending = ReviewCase(
            case_id=incoming.case_id,
            request_id=incoming.request_id,
            user_id=incoming.user_id,
            status=ReviewStatus.PENDING_REVIEW,
            rule_hits=incoming.rule_hits,
            created_at=incoming.created_at,
        )
        if existing != expected_pending:
            raise RiskRuleEngineError(f"Review case already exists: {existing.case_id}")
        self._validate_completed_review_case(incoming)

        with self._connection:
            self._connection.execute(
                """
                UPDATE review_cases
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
                    incoming.reviewed_at.isoformat()
                    if incoming.reviewed_at is not None
                    else None,
                    incoming.case_id,
                ),
            )
            self._insert_audit_event(
                event_type=f"review_case.{incoming.status.value}",
                aggregate_type="review_case",
                aggregate_id=incoming.case_id,
                actor=incoming.reviewed_by or "unknown",
                reason=incoming.review_reason,
                payload=(
                    "{"
                    f'"case_id":"{incoming.case_id}",'
                    f'"request_id":"{incoming.request_id}",'
                    f'"user_id":"{incoming.user_id}",'
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
                CREATE TABLE IF NOT EXISTS risk_decisions (
                    request_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    decided_at TEXT NOT NULL,
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    rule_version_id TEXT,
                    FOREIGN KEY (rule_version_id) REFERENCES risk_rule_versions(version_id)
                );

                CREATE TABLE IF NOT EXISTS risk_rule_versions (
                    version_id TEXT PRIMARY KEY,
                    single_transaction_review_threshold TEXT NOT NULL,
                    daily_user_review_threshold TEXT NOT NULL,
                    allowed_currencies TEXT NOT NULL,
                    high_risk_countries TEXT NOT NULL,
                    blocked_beneficiaries TEXT NOT NULL,
                    risk_score_review_threshold INTEGER NOT NULL DEFAULT 50,
                    rule_scores TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_decision_rule_hits (
                    request_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    rule_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    reason TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (request_id, sequence),
                    FOREIGN KEY (request_id) REFERENCES risk_decisions(request_id)
                );

                CREATE TABLE IF NOT EXISTS review_cases (
                    case_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending_review', 'approved', 'rejected')),
                    created_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    review_reason TEXT,
                    reviewed_at TEXT,
                    FOREIGN KEY (request_id) REFERENCES risk_decisions(request_id)
                );

                CREATE TABLE IF NOT EXISTS review_case_rule_hits (
                    case_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    rule_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'review', 'blocked')),
                    reason TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (case_id, sequence),
                    FOREIGN KEY (case_id) REFERENCES review_cases(case_id)
                );

                CREATE TABLE IF NOT EXISTS risk_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_risk_decisions_status
                ON risk_decisions (status, decided_at);

                CREATE INDEX IF NOT EXISTS idx_risk_decisions_rule_version
                ON risk_decisions (rule_version_id);

                CREATE INDEX IF NOT EXISTS idx_risk_rule_versions_effective_at
                ON risk_rule_versions (effective_at);

                CREATE INDEX IF NOT EXISTS idx_review_cases_status
                ON review_cases (status, created_at);

                CREATE INDEX IF NOT EXISTS idx_risk_audit_events_aggregate
                ON risk_audit_events (aggregate_type, aggregate_id, occurred_at);

                CREATE INDEX IF NOT EXISTS idx_risk_audit_events_type
                ON risk_audit_events (event_type, occurred_at);
                """
            )

    def _migrate_schema(self) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(risk_decisions)")
        }
        rule_version_columns = {
            row["name"]
            for row in self._connection.execute(
                "PRAGMA table_info(risk_rule_versions)"
            )
        }
        with self._connection:
            if "rule_version_id" not in columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_decisions
                    ADD COLUMN rule_version_id TEXT
                    """
                )
            if "risk_score" not in columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_decisions
                    ADD COLUMN risk_score INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "high_risk_countries" not in rule_version_columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_rule_versions
                    ADD COLUMN high_risk_countries TEXT NOT NULL DEFAULT ''
                    """
                )
            if "risk_score_review_threshold" not in rule_version_columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_rule_versions
                    ADD COLUMN risk_score_review_threshold INTEGER NOT NULL DEFAULT 50
                    """
                )
            if "rule_scores" not in rule_version_columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_rule_versions
                    ADD COLUMN rule_scores TEXT NOT NULL DEFAULT ''
                    """
                )
            self._migrate_rule_hit_score_column("risk_decision_rule_hits")
            self._migrate_rule_hit_score_column("review_case_rule_hits")
            if "blocked_beneficiaries" not in rule_version_columns:
                self._connection.execute(
                    """
                    ALTER TABLE risk_rule_versions
                    ADD COLUMN blocked_beneficiaries TEXT NOT NULL DEFAULT ''
                    """
                )

    def _decision_from_row(self, row: sqlite3.Row) -> RiskDecision:
        return RiskDecision(
            request_id=row["request_id"],
            user_id=row["user_id"],
            status=RiskDecisionStatus(row["status"]),
            rule_hits=self._rule_hits_for(
                "risk_decision_rule_hits",
                "request_id",
                row["request_id"],
            ),
            risk_score=row["risk_score"],
        )

    def _review_case_from_row(self, row: sqlite3.Row) -> ReviewCase:
        return ReviewCase(
            case_id=row["case_id"],
            request_id=row["request_id"],
            user_id=row["user_id"],
            status=ReviewStatus(row["status"]),
            rule_hits=self._rule_hits_for(
                "review_case_rule_hits",
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

    def _rule_hits_for(
        self,
        table_name: str,
        owner_column: str,
        owner_id: str,
    ) -> tuple[RuleHit, ...]:
        rows = self._connection.execute(
            f"""
            SELECT rule_id, status, reason, score
            FROM {table_name}
            WHERE {owner_column} = ?
            ORDER BY sequence
            """,
            (owner_id,),
        ).fetchall()
        return tuple(
            RuleHit(
                rule_id=row["rule_id"],
                status=RiskDecisionStatus(row["status"]),
                reason=row["reason"],
                score=row["score"],
            )
            for row in rows
        )

    def _insert_rule_hits(
        self,
        table_name: str,
        owner_column: str,
        owner_id: str,
        rule_hits: tuple[RuleHit, ...],
    ) -> None:
        for sequence, rule_hit in enumerate(rule_hits):
            self._connection.execute(
                f"""
                INSERT INTO {table_name} (
                    {owner_column},
                    sequence,
                    rule_id,
                    status,
                    reason,
                    score
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    sequence,
                    rule_hit.rule_id,
                    rule_hit.status.value,
                    rule_hit.reason,
                    rule_hit.score,
                ),
            )

    def _review_case_to_row(
        self,
        review_case: ReviewCase,
    ) -> tuple[str, str, str, str, str, str | None, str | None, str | None]:
        return (
            review_case.case_id,
            review_case.request_id,
            review_case.user_id,
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

    def _rule_version_to_row(
        self,
        rule_version: RiskRuleVersion,
    ) -> tuple[str, str, str, str, str, str, int, str, str, str, str]:
        return (
            rule_version.version_id,
            rule_version.single_transaction_review_threshold,
            rule_version.daily_user_review_threshold,
            ",".join(rule_version.allowed_currencies),
            ",".join(rule_version.high_risk_countries),
            ",".join(rule_version.blocked_beneficiaries),
            rule_version.risk_score_review_threshold,
            _encode_rule_scores(rule_version.rule_scores),
            rule_version.source,
            rule_version.effective_at.isoformat(),
            rule_version.created_at.isoformat(),
        )

    def _rule_version_from_row(self, row: sqlite3.Row) -> RiskRuleVersion:
        return RiskRuleVersion(
            version_id=row["version_id"],
            single_transaction_review_threshold=row[
                "single_transaction_review_threshold"
            ],
            daily_user_review_threshold=row["daily_user_review_threshold"],
            allowed_currencies=_split_csv(row["allowed_currencies"]),
            high_risk_countries=_split_csv(row["high_risk_countries"]),
            blocked_beneficiaries=_split_csv(row["blocked_beneficiaries"]),
            risk_score_review_threshold=row["risk_score_review_threshold"],
            rule_scores=_decode_rule_scores(row["rule_scores"]),
            source=row["source"],
            effective_at=datetime.fromisoformat(row["effective_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
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
            raise RiskRuleEngineError("occurred_at is required")
        _validate_timestamp(occurred_at, field_name="occurred_at")
        self._connection.execute(
            """
            INSERT INTO risk_audit_events (
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

    def _audit_event_from_row(self, row: sqlite3.Row) -> RiskAuditEvent:
        return RiskAuditEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"],
            actor=row["actor"],
            reason=row["reason"],
            payload=row["payload"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )

    def _validate_pending_review_case(self, review_case: ReviewCase) -> None:
        if (
            review_case.reviewed_by is not None
            or review_case.review_reason is not None
            or review_case.reviewed_at is not None
        ):
            raise RiskRuleEngineError("Pending review case cannot have review result")

    def _validate_completed_review_case(self, review_case: ReviewCase) -> None:
        if review_case.reviewed_by is None or not review_case.reviewed_by.strip():
            raise RiskRuleEngineError("Reviewer is required")
        if review_case.review_reason is None or not review_case.review_reason.strip():
            raise RiskRuleEngineError("Review reason is required")
        if review_case.reviewed_at is None:
            raise RiskRuleEngineError("reviewed_at is required")

    def _normalize_rule_version_id(self, rule_version_id: str | None) -> str | None:
        if rule_version_id is None:
            return None
        normalized = rule_version_id.strip()
        if not normalized:
            raise RiskRuleEngineError("Rule version id is required")
        if self.find_rule_version(normalized) is None:
            raise RiskRuleEngineError(f"Unknown risk rule version: {normalized}")
        return normalized

    def _ensure_existing_decision_version(
        self,
        request_id: str,
        rule_version_id: str | None,
    ) -> None:
        normalized_rule_version_id = self._normalize_rule_version_id(rule_version_id)
        row = self._connection.execute(
            """
            SELECT rule_version_id
            FROM risk_decisions
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row["rule_version_id"] != normalized_rule_version_id:
            raise RiskRuleEngineError(
                f"Risk decision already exists with different rule version: {request_id}"
            )

    def _json_string_or_null(self, value: str | None) -> str:
        if value is None:
            return "null"
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _migrate_rule_hit_score_column(self, table_name: str) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute(f"PRAGMA table_info({table_name})")
        }
        if "score" in columns:
            return
        self._connection.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN score INTEGER NOT NULL DEFAULT 0
            """
        )


def _validate_timestamp(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskRuleEngineError(f"{field_name} must be timezone-aware")


def _split_csv(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item for item in value.split(",") if item)


def _encode_rule_scores(rule_scores: dict[str, int]) -> str:
    return ",".join(f"{rule_id}:{score}" for rule_id, score in sorted(rule_scores.items()))


def _decode_rule_scores(value: str) -> dict[str, int]:
    if not value:
        return {}
    scores = {}
    for item in value.split(","):
        rule_id, score = item.split(":", 1)
        scores[rule_id] = int(score)
    return scores
