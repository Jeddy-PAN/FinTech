from __future__ import annotations

from dataclasses import dataclass
import html
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from urllib.parse import parse_qs, quote
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent, ComplianceAuditError  # noqa: E402
from compliance_access_monitoring import AccessAnomalyFinding  # noqa: E402
from compliance_investigation_cases import (  # noqa: E402
    AccessAnomalyInvestigationCase,
    AccessAnomalyInvestigationService,
)
from platform_api_service import (
    PlatformApiPaymentRequest,
    PlatformApiService,
    PlatformApiServiceError,
    service_error_response,
)
from platform_async_service import (  # noqa: E402
    ASYNC_RUN_FAILED,
    PlatformAsyncRun,
    PlatformAsyncRunStoreError,
    PlatformAsyncWorker,
    PlatformAsyncWorkerResult,
    SQLitePlatformAsyncRunStore,
)
from platform_api_access_anomaly_report import (  # noqa: E402
    detect_platform_api_access_anomalies,
)
from platform_api_investigation_cases import (  # noqa: E402
    open_platform_api_access_investigation_cases,
)
from platform_api_console_views import (  # noqa: E402
    approval_feedback_html as _approval_feedback_html,
    console_filter_feedback_html as _console_filter_feedback_html,
    console_filter_form_html,
    html_table as _html_table,
    metric_html as _metric_html,
    normalize_console_filters,
    retry_feedback_html as _retry_feedback_html,
    table as _table,
)
from platform_api_detail_views import (  # noqa: E402
    render_async_run_detail_html,
    render_operation_approval_detail_html,
    render_payment_run_detail_html,
)
from platform_api_manual_views import render_platform_manual_html  # noqa: E402
from platform_operation_approval import (  # noqa: E402
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
    OPERATION_APPROVAL_SORT_FIELDS,
    OPERATION_APPROVAL_SORT_ORDERS,
    OperationApprovalError,
    OperationApprovalRecord,
    SQLiteOperationApprovalStore,
)
from fintech_platform import PlatformPaymentStatus  # noqa: E402
from platform_operation_approval_report import (  # noqa: E402
    build_operation_approval_report,
)
from platform_ledger_reconciliation_report import (  # noqa: E402
    evaluate_platform_ledger_reconciliation,
)
from platform_operations_report import build_platform_operations_report  # noqa: E402
from platform_operability import (  # noqa: E402
    build_platform_metrics_snapshot,
    build_platform_readiness_report,
    build_platform_test_matrix,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore  # noqa: E402
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore  # noqa: E402
from sqlite_platform_store import (  # noqa: E402
    PlatformRunSnapshot,
    SQLitePlatformStore,
    SQLitePlatformStoreError,
)


DEFAULT_DATABASE_PATH = LAB_DIR / ".test-data" / "platform_api.db"
DEFAULT_ACCESS_AUDIT_DATABASE_PATH = (
    LAB_DIR / ".test-data" / "platform_api_access_audit.db"
)
DEFAULT_ASYNC_DATABASE_PATH = LAB_DIR / ".test-data" / "platform_api_async_runs.db"
DEFAULT_INVESTIGATION_DATABASE_PATH = (
    LAB_DIR / ".test-data" / "platform_api_investigation_cases.db"
)
DEFAULT_OPERATION_APPROVAL_DATABASE_PATH = (
    LAB_DIR / ".test-data" / "platform_api_operation_approvals.db"
)

CREATE_PLATFORM_PAYMENT_RUN = "create_platform_payment_run"
VIEW_PLATFORM_PAYMENT_RUN = "view_platform_payment_run"
LIST_PLATFORM_PAYMENT_RUNS = "list_platform_payment_runs"
CREATE_PLATFORM_ASYNC_PAYMENT_RUN = "create_platform_async_payment_run"
VIEW_PLATFORM_ASYNC_PAYMENT_RUN = "view_platform_async_payment_run"
LIST_PLATFORM_ASYNC_PAYMENT_RUNS = "list_platform_async_payment_runs"
PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS = "process_platform_async_payment_runs"
RETRY_PLATFORM_ASYNC_PAYMENT_RUN = "retry_platform_async_run"
VIEW_PLATFORM_API_ACCESS_EVENTS = "view_platform_api_access_events"
VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS = "view_platform_api_access_anomaly_findings"
CREATE_PLATFORM_API_INVESTIGATION_CASES = "create_platform_api_investigation_cases"
VIEW_PLATFORM_API_INVESTIGATION_CASES = "view_platform_api_investigation_cases"
UPDATE_PLATFORM_API_INVESTIGATION_CASES = "update_platform_api_investigation_cases"
CREATE_PLATFORM_OPERATION_APPROVALS = "create_platform_operation_approvals"
VIEW_PLATFORM_OPERATION_APPROVALS = "view_platform_operation_approvals"
UPDATE_PLATFORM_OPERATION_APPROVALS = "update_platform_operation_approvals"
VIEW_PLATFORM_CONSOLE = "view_platform_console"
CHECK_PLATFORM_API_HEALTH = "check_platform_api_health"
CHECK_PLATFORM_OPERABILITY_READINESS = "check_platform_operability_readiness"
VIEW_PLATFORM_OPERABILITY_METRICS = "view_platform_operability_metrics"
VIEW_PLATFORM_TEST_MATRIX = "view_platform_test_matrix"

PLATFORM_API_HEALTH_TARGET = "fintech_platform_api_health"
PLATFORM_OPERABILITY_READINESS_TARGET = "fintech_platform_operability_readiness"
PLATFORM_OPERABILITY_METRICS_TARGET = "fintech_platform_operability_metrics"
PLATFORM_TEST_MATRIX_TARGET = "fintech_platform_test_matrix"
PLATFORM_API_PAYMENT_RUNS_TARGET = "fintech_platform_api_payment_runs"
PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET = "fintech_platform_api_async_payment_runs"
PLATFORM_API_ASYNC_WORKER_TARGET = "fintech_platform_api_async_worker"
PLATFORM_API_ACCESS_EVENTS_TARGET = "fintech_platform_api_access_events"
PLATFORM_API_ACCESS_ANOMALY_FINDINGS_TARGET = (
    "fintech_platform_api_access_anomaly_findings"
)
PLATFORM_API_INVESTIGATION_CASES_TARGET = (
    "fintech_platform_api_investigation_cases"
)
PLATFORM_OPERATION_APPROVALS_TARGET = "fintech_platform_operation_approvals"
PLATFORM_CONSOLE_TARGET = "fintech_platform_api_console"
PLATFORM_MANUAL_TARGET = "fintech_platform_manual"
RETRY_FAILED_ASYNC_RUN_CONFIRMATION = "retry_failed_async_run"
APPROVE_OPERATION_APPROVAL_CONFIRMATION = "approve_operation_approval"
REJECT_OPERATION_APPROVAL_CONFIRMATION = "reject_operation_approval"
CANCEL_OPERATION_APPROVAL_CONFIRMATION = "cancel_operation_approval"
EXPIRE_OPERATION_APPROVAL_CONFIRMATION = "expire_operation_approval"
ANONYMOUS_API_CLIENT = "anonymous_api_client"
CONSOLE_PAYMENT_STATUS_OPTIONS = tuple(status.value for status in PlatformPaymentStatus)
CONSOLE_ASYNC_STATUS_OPTIONS = (
    "accepted",
    "processing",
    "completed",
    "failed",
)
CONSOLE_OPERATION_APPROVAL_STATUS_OPTIONS = (
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_REJECTED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
)

ROLE_API_CLIENT = "api_client"
ROLE_API_VIEWER = "api_viewer"
ROLE_APPROVAL_REQUESTER = "approval_requester"
ROLE_APPROVAL_VIEWER = "approval_viewer"
ROLE_AUDIT_READER = "audit_reader"
ROLE_COMPLIANCE_LEAD = "compliance_lead"
ROLE_INVESTIGATOR = "investigator"
ROLE_OPS_MANAGER = "ops_manager"
ROLE_OPS_USER = "ops_user"
ROLE_SYSTEM_SCHEDULER = "system_scheduler"
ROLE_ASYNC_WORKER = "async_worker"
ROLE_CONSOLE_READER = "console_reader"

PERMISSIONS_BY_ROLE = {
    ROLE_API_CLIENT: {
        CREATE_PLATFORM_PAYMENT_RUN,
        CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
        CREATE_PLATFORM_OPERATION_APPROVALS,
    },
    ROLE_API_VIEWER: {
        VIEW_PLATFORM_PAYMENT_RUN,
        LIST_PLATFORM_PAYMENT_RUNS,
        VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
        LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_APPROVAL_REQUESTER: {
        CREATE_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_APPROVAL_VIEWER: {
        VIEW_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_AUDIT_READER: {
        VIEW_PLATFORM_API_ACCESS_EVENTS,
        VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS,
        CHECK_PLATFORM_OPERABILITY_READINESS,
        VIEW_PLATFORM_OPERABILITY_METRICS,
        VIEW_PLATFORM_TEST_MATRIX,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_COMPLIANCE_LEAD: {
        VIEW_PLATFORM_API_ACCESS_EVENTS,
        VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS,
        CREATE_PLATFORM_API_INVESTIGATION_CASES,
        VIEW_PLATFORM_API_INVESTIGATION_CASES,
        UPDATE_PLATFORM_API_INVESTIGATION_CASES,
        CHECK_PLATFORM_OPERABILITY_READINESS,
        VIEW_PLATFORM_OPERABILITY_METRICS,
        VIEW_PLATFORM_TEST_MATRIX,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_INVESTIGATOR: {
        VIEW_PLATFORM_API_INVESTIGATION_CASES,
        UPDATE_PLATFORM_API_INVESTIGATION_CASES,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_OPS_MANAGER: {
        CREATE_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_OPERATION_APPROVALS,
        UPDATE_PLATFORM_OPERATION_APPROVALS,
        RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
        CHECK_PLATFORM_OPERABILITY_READINESS,
        VIEW_PLATFORM_OPERABILITY_METRICS,
        VIEW_PLATFORM_TEST_MATRIX,
        VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
        LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
        VIEW_PLATFORM_PAYMENT_RUN,
        LIST_PLATFORM_PAYMENT_RUNS,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_OPS_USER: {
        CREATE_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_OPERATION_APPROVALS,
        UPDATE_PLATFORM_OPERATION_APPROVALS,
        VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
        LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
        VIEW_PLATFORM_PAYMENT_RUN,
        LIST_PLATFORM_PAYMENT_RUNS,
        VIEW_PLATFORM_CONSOLE,
    },
    ROLE_SYSTEM_SCHEDULER: {
        UPDATE_PLATFORM_OPERATION_APPROVALS,
        PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    },
    ROLE_ASYNC_WORKER: {
        PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    },
    ROLE_CONSOLE_READER: {
        VIEW_PLATFORM_CONSOLE,
        VIEW_PLATFORM_PAYMENT_RUN,
        LIST_PLATFORM_PAYMENT_RUNS,
        VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
        LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
        VIEW_PLATFORM_OPERATION_APPROVALS,
    },
}


@dataclass(frozen=True)
class PlatformIdentityContext:
    actor: str
    roles: tuple[str, ...]
    source: str


class PaymentRunRequest(BaseModel):
    run_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    date_of_birth: date
    country: str = Field(min_length=1)
    address: str = Field(min_length=1)
    identification_number: str = Field(min_length=1)
    expected_monthly_volume_cents: int = Field(gt=0)
    amount: str = Field(min_length=1)
    currency: str = Field(default="USD", min_length=1)
    order_id: str = Field(min_length=1)
    requested_at: datetime
    device_id: str = Field(default="device_default", min_length=1)
    ip_country: str = Field(default="US", min_length=1)
    beneficiary_id: str = Field(default="beneficiary_default", min_length=1)
    actor: str = Field(default="api_client", min_length=1)


class RetryAsyncRunRequest(BaseModel):
    actor: str | None = None
    reason: str | None = None
    confirmation: str | None = None


class StartInvestigationRequest(BaseModel):
    assigned_to: str = Field(min_length=1)
    started_at: datetime


class CloseInvestigationRequest(BaseModel):
    closed_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    closed_at: datetime


class DecideOperationApprovalRequest(BaseModel):
    decided_by: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    decided_at: datetime


class CreateOperationApprovalRequest(BaseModel):
    approval_id: str = Field(min_length=1)
    operation_type: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    target: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    request_reason: str = Field(min_length=1)
    requested_at: datetime


def create_app(
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    access_audit_database_path: str | Path = DEFAULT_ACCESS_AUDIT_DATABASE_PATH,
    async_database_path: str | Path = DEFAULT_ASYNC_DATABASE_PATH,
    investigation_database_path: str | Path = DEFAULT_INVESTIGATION_DATABASE_PATH,
    operation_approval_database_path: str | Path = DEFAULT_OPERATION_APPROVAL_DATABASE_PATH,
) -> FastAPI:
    app = FastAPI(title="FinTech Platform API", version="0.1.0")
    app.state.database_path = Path(database_path)
    app.state.access_audit_database_path = Path(access_audit_database_path)
    app.state.async_database_path = Path(async_database_path)
    app.state.investigation_database_path = Path(investigation_database_path)
    app.state.operation_approval_database_path = Path(operation_approval_database_path)

    def get_service() -> PlatformApiService:
        app.state.database_path.parent.mkdir(parents=True, exist_ok=True)
        store = SQLitePlatformStore(app.state.database_path)
        return PlatformApiService(store=store)

    def get_async_store() -> SQLitePlatformAsyncRunStore:
        app.state.async_database_path.parent.mkdir(parents=True, exist_ok=True)
        return SQLitePlatformAsyncRunStore(app.state.async_database_path)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/platform", response_class=HTMLResponse)
    @app.get("/platform/view", response_class=HTMLResponse)
    def platform_console(
        approval_error: str | None = None,
        approval_status: str | None = None,
        actor_filter: str | None = Query(default=None, alias="actor"),
        async_status: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        operation_approval_status: str | None = None,
        payment_status: str | None = None,
        retry_error: str | None = None,
        retry_status: str | None = None,
        x_actor_id: str | None = Header(default=None),
    ) -> HTMLResponse:
        actor = _api_actor(x_actor_id)
        html_body = _render_platform_console_html(
            app,
            approval_error=approval_error,
            approval_status=approval_status,
            actor_filter=actor_filter,
            async_status_filter=async_status,
            created_from_filter=created_from,
            created_to_filter=created_to,
            operation_approval_status_filter=operation_approval_status,
            payment_status_filter=payment_status,
            retry_error=retry_error,
            retry_status=retry_status,
        )
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_CONSOLE,
            target=PLATFORM_CONSOLE_TARGET,
            outcome="granted",
        )
        return HTMLResponse(content=html_body)

    @app.get("/platform/manual", response_class=HTMLResponse)
    def platform_manual(
        lang: str | None = None,
        x_actor_id: str | None = Header(default=None),
    ) -> HTMLResponse:
        actor = _api_actor(x_actor_id)
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_CONSOLE,
            target=PLATFORM_MANUAL_TARGET,
            outcome="granted",
            reason="view manual",
        )
        return HTMLResponse(
            content=render_platform_manual_html(
                lang=lang,
                page_shell=_platform_page_shell,
            )
        )

    @app.get("/health")
    def health(x_actor_id: str | None = Header(default=None)) -> dict:
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=CHECK_PLATFORM_API_HEALTH,
            target=PLATFORM_API_HEALTH_TARGET,
            outcome="granted",
        )
        return {"status": "ok"}

    @app.get("/platform/operability/readiness")
    def platform_operability_readiness(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=CHECK_PLATFORM_OPERABILITY_READINESS,
            target=PLATFORM_OPERABILITY_READINESS_TARGET,
        )
        report = build_platform_readiness_report(
            database_path=app.state.database_path,
            access_audit_database_path=app.state.access_audit_database_path,
            async_database_path=app.state.async_database_path,
            investigation_database_path=app.state.investigation_database_path,
            operation_approval_database_path=app.state.operation_approval_database_path,
        )
        _record_api_access(
            app,
            actor=identity.actor,
            permission=CHECK_PLATFORM_OPERABILITY_READINESS,
            target=PLATFORM_OPERABILITY_READINESS_TARGET,
            outcome="granted",
            reason=report.status,
        )
        return report.to_dict()

    @app.get("/platform/operability/metrics")
    def platform_operability_metrics(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_OPERABILITY_METRICS,
            target=PLATFORM_OPERABILITY_METRICS_TARGET,
        )
        snapshot = build_platform_metrics_snapshot(
            database_path=app.state.database_path,
            access_audit_database_path=app.state.access_audit_database_path,
            async_database_path=app.state.async_database_path,
            investigation_database_path=app.state.investigation_database_path,
            operation_approval_database_path=app.state.operation_approval_database_path,
        )
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_OPERABILITY_METRICS,
            target=PLATFORM_OPERABILITY_METRICS_TARGET,
            outcome="granted",
        )
        return snapshot.to_dict()

    @app.get("/platform/operability/test-matrix")
    def platform_operability_test_matrix(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_TEST_MATRIX,
            target=PLATFORM_TEST_MATRIX_TARGET,
        )
        rows = build_platform_test_matrix()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_TEST_MATRIX,
            target=PLATFORM_TEST_MATRIX_TARGET,
            outcome="granted",
        )
        return {"rows": [row.to_dict() for row in rows]}

    @app.post(
        "/platform/payment-runs",
        status_code=status.HTTP_201_CREATED,
    )
    def create_payment_run(
        request: PaymentRunRequest,
        service: PlatformApiService = Depends(get_service),
    ) -> dict:
        try:
            response = service.create_payment_run(_service_request(request))
        except PlatformApiServiceError as error:
            _record_api_access(
                app,
                actor=request.actor,
                permission=CREATE_PLATFORM_PAYMENT_RUN,
                target=PLATFORM_API_PAYMENT_RUNS_TARGET,
                outcome="denied",
                reason=f"400 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=service_error_response(error),
            ) from error
        finally:
            service.store.close()

        _record_api_access(
            app,
            actor=request.actor,
            permission=CREATE_PLATFORM_PAYMENT_RUN,
            target=PLATFORM_API_PAYMENT_RUNS_TARGET,
            outcome="granted",
            reason="idempotent_replay" if response["idempotent_replay"] else None,
        )
        if response["idempotent_replay"]:
            response["http_status"] = "idempotent_replay"
        return response

    @app.get("/platform/payment-runs/{run_id}")
    def get_payment_run(
        run_id: str,
        x_actor_id: str | None = Header(default=None),
        service: PlatformApiService = Depends(get_service),
    ) -> dict:
        actor = _api_actor(x_actor_id)
        target = _payment_run_target(run_id)
        try:
            response = service.get_payment_run(run_id)
        except SQLitePlatformStoreError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"404 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=service_error_response(error),
            ) from error
        except PlatformApiServiceError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"400 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=service_error_response(error),
            ) from error
        finally:
            service.store.close()
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_PAYMENT_RUN,
            target=target,
            outcome="granted",
        )
        return response

    @app.get(
        "/platform/payment-runs/{run_id}/view",
        response_class=HTMLResponse,
    )
    def view_payment_run(
        run_id: str,
        x_actor_id: str | None = Header(default=None),
        service: PlatformApiService = Depends(get_service),
    ) -> HTMLResponse:
        actor = _api_actor(x_actor_id)
        target = _payment_run_target(run_id)
        try:
            response = service.get_payment_run(run_id)
        except SQLitePlatformStoreError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"404 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=service_error_response(error),
            ) from error
        except PlatformApiServiceError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"400 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=service_error_response(error),
            ) from error
        finally:
            service.store.close()
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_PAYMENT_RUN,
            target=target,
            outcome="granted",
            reason="view detail",
        )
        async_run = _async_run_or_none(app, response["run_id"])
        return HTMLResponse(
            render_payment_run_detail_html(
                platform_result=response,
                async_run=async_run,
                reconciliation_rows=_payment_run_reconciliation_rows(
                    app,
                    response["run_id"],
                ),
                chrome_css=_platform_chrome_css(),
                content_css=_platform_content_css(),
                topbar_html=_platform_topbar_html("payments"),
                side_nav_html=_platform_side_nav_html("payments"),
                page_header_html=_platform_page_header_html(
                    "Payment Run Detail",
                    "Read-only platform result, ledger context, and audit timeline.",
                    active_nav="payments",
                ),
            )
        )

    @app.get("/platform/payment-runs")
    def list_payment_runs(
        status_filter: str | None = Query(default=None, alias="status"),
        customer_id: str | None = None,
        x_actor_id: str | None = Header(default=None),
        service: PlatformApiService = Depends(get_service),
    ) -> dict:
        try:
            runs = service.list_payment_runs(
                status=status_filter,
                customer_id=customer_id,
            )
        finally:
            service.store.close()
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=LIST_PLATFORM_PAYMENT_RUNS,
            target=PLATFORM_API_PAYMENT_RUNS_TARGET,
            outcome="granted",
        )
        return {"runs": list(runs)}

    @app.post(
        "/platform/async-payment-runs",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_async_payment_run(
        request: PaymentRunRequest,
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> dict:
        try:
            result = async_store.create_run(_service_request(request))
        except PlatformAsyncRunStoreError as error:
            _record_api_access(
                app,
                actor=request.actor,
                permission=CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
                target=PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET,
                outcome="denied",
                reason=f"400 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": type(error).__name__,
                    "message": str(error),
                },
            ) from error
        finally:
            async_store.close()

        _record_api_access(
            app,
            actor=request.actor,
            permission=CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
            target=PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET,
            outcome="granted",
            reason="idempotent_replay" if result.idempotent_replay else None,
        )
        response = _async_run_response(app, result.run)
        response["idempotent_replay"] = result.idempotent_replay
        response["http_status"] = (
            "idempotent_replay" if result.idempotent_replay else "accepted"
        )
        return response

    @app.get("/platform/async-payment-runs")
    def list_async_payment_runs(
        status_filter: str | None = Query(default=None, alias="status"),
        x_actor_id: str | None = Header(default=None),
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> dict:
        actor = _api_actor(x_actor_id)
        try:
            runs = async_store.query_runs(status=status_filter)
        except PlatformAsyncRunStoreError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
                target=PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET,
                outcome="denied",
                reason=f"400 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": type(error).__name__,
                    "message": str(error),
                },
            ) from error
        finally:
            async_store.close()
        _record_api_access(
            app,
            actor=actor,
            permission=LIST_PLATFORM_ASYNC_PAYMENT_RUNS,
            target=PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET,
            outcome="granted",
        )
        return {
            "runs": [
                _async_run_response(app, run, include_platform_result=False)
                for run in runs
            ]
        }

    @app.get("/platform/async-payment-runs/{run_id}")
    def get_async_payment_run(
        run_id: str,
        x_actor_id: str | None = Header(default=None),
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> dict:
        actor = _api_actor(x_actor_id)
        target = _async_payment_run_target(run_id)
        try:
            run = async_store.get_run(run_id)
        except PlatformAsyncRunStoreError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"404 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": type(error).__name__,
                    "message": str(error),
                },
            ) from error
        finally:
            async_store.close()
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
            target=target,
            outcome="granted",
        )
        return _async_run_response(app, run)

    @app.get(
        "/platform/async-payment-runs/{run_id}/view",
        response_class=HTMLResponse,
    )
    def view_async_payment_run(
        run_id: str,
        x_actor_id: str | None = Header(default=None),
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> HTMLResponse:
        actor = _api_actor(x_actor_id)
        target = _async_payment_run_target(run_id)
        try:
            run = async_store.get_run(run_id)
        except PlatformAsyncRunStoreError as error:
            _record_api_access(
                app,
                actor=actor,
                permission=VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"404 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": type(error).__name__,
                    "message": str(error),
                },
            ) from error
        finally:
            async_store.close()
        _record_api_access(
            app,
            actor=actor,
            permission=VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
            target=target,
            outcome="granted",
            reason="view detail",
        )
        return HTMLResponse(
            render_async_run_detail_html(
                run=run,
                platform_result=_async_platform_result_or_none(app, run),
                chrome_css=_platform_chrome_css(),
                content_css=_platform_content_css(),
                topbar_html=_platform_topbar_html("async"),
                side_nav_html=_platform_side_nav_html("async"),
                page_header_html=_platform_page_header_html(
                    "Async Run Detail",
                    "Read-only async request, worker status, and platform result context.",
                    active_nav="async",
                ),
            )
        )

    @app.post(
        "/platform/async-payment-runs/{run_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def retry_async_payment_run(
        run_id: str,
        request: RetryAsyncRunRequest,
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> dict:
        try:
            record = _request_retry_async_run_approval(
                app,
                async_store,
                run_id,
                actor=request.actor,
                reason=request.reason,
                confirmation=request.confirmation,
            )
        except PlatformAsyncRunStoreError as error:
            raise _http_exception_from_async_run_store_error(error) from error
        except OperationApprovalError as error:
            raise _http_exception_from_operation_approval_error(error) from error
        finally:
            async_store.close()

        return {"record": _operation_approval_record_response(record)}

    @app.post("/platform/async-payment-runs/{run_id}/retry-form")
    async def retry_async_payment_run_form(
        run_id: str,
        request: Request,
    ) -> RedirectResponse:
        body = (await request.body()).decode("utf-8")
        form = parse_qs(body, keep_blank_values=True)
        app.state.async_database_path.parent.mkdir(parents=True, exist_ok=True)
        async_store = SQLitePlatformAsyncRunStore(app.state.async_database_path)
        try:
            _request_retry_async_run_approval(
                app,
                async_store,
                run_id,
                actor=_form_value(form, "actor"),
                reason=_form_value(form, "reason"),
                confirmation=_form_value(form, "confirmation"),
            )
        except (OperationApprovalError, PlatformAsyncRunStoreError) as error:
            message = quote(str(error), safe="")
            return RedirectResponse(
                url=f"/platform/view?retry_error={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        finally:
            async_store.close()
        return RedirectResponse(
            url="/platform/view?retry_status=pending_approval",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/platform/async-worker/process-next")
    def process_next_async_payment_run(
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        actor = _api_actor(x_actor_id)
        result = _process_async_worker(app, limit=None)
        _record_api_access(
            app,
            actor=actor,
            permission=PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
            target=PLATFORM_API_ASYNC_WORKER_TARGET,
            outcome="granted",
            reason=_worker_audit_reason((result,)),
        )
        return {"result": _worker_result_response(result)}

    @app.post("/platform/async-worker/process-pending")
    def process_pending_async_payment_runs(
        limit: int = Query(default=10, gt=0),
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        actor = _api_actor(x_actor_id)
        results = _process_async_worker(app, limit=limit)
        _record_api_access(
            app,
            actor=actor,
            permission=PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
            target=PLATFORM_API_ASYNC_WORKER_TARGET,
            outcome="granted",
            reason=_worker_audit_reason(results),
        )
        return {"results": [_worker_result_response(result) for result in results]}

    @app.get("/platform/api-access-events")
    def list_api_access_events(
        actor: str | None = None,
        permission: str | None = None,
        outcome: str | None = None,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_API_ACCESS_EVENTS,
            target=PLATFORM_API_ACCESS_EVENTS_TARGET,
        )
        store = _access_audit_store(app)
        try:
            events = store.query_access_events(
                actor=actor,
                permission=permission,
                outcome=outcome,
            )
        finally:
            store.close()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_API_ACCESS_EVENTS,
            target=PLATFORM_API_ACCESS_EVENTS_TARGET,
            outcome="granted",
        )
        return {"events": [_access_event_response(event) for event in events]}

    @app.get("/platform/api-access-anomaly-findings")
    def list_api_access_anomaly_findings(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS,
            target=PLATFORM_API_ACCESS_ANOMALY_FINDINGS_TARGET,
        )
        access_events = _access_events(app)
        findings = detect_platform_api_access_anomalies(access_events)
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_API_ACCESS_ANOMALY_FINDINGS,
            target=PLATFORM_API_ACCESS_ANOMALY_FINDINGS_TARGET,
            outcome="granted",
        )
        return {"findings": [_finding_response(finding) for finding in findings]}

    @app.post("/platform/api-access-investigation-cases")
    def create_api_access_investigation_cases(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=CREATE_PLATFORM_API_INVESTIGATION_CASES,
            target=PLATFORM_API_INVESTIGATION_CASES_TARGET,
        )
        actor = identity.actor
        access_events = _access_events(app)
        findings = detect_platform_api_access_anomalies(access_events)
        cases = _persist_platform_api_investigation_cases(
            app,
            findings=findings,
            opened_by=actor,
        )
        _record_api_access(
            app,
            actor=actor,
            permission=CREATE_PLATFORM_API_INVESTIGATION_CASES,
            target=PLATFORM_API_INVESTIGATION_CASES_TARGET,
            outcome="granted",
            reason=f"cases={len(cases)}",
        )
        return {"cases": [_investigation_case_response(case) for case in cases]}

    @app.post(
        "/platform/operation-approvals",
        status_code=status.HTTP_201_CREATED,
    )
    def create_operation_approval(
        request: CreateOperationApprovalRequest,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=CREATE_PLATFORM_OPERATION_APPROVALS,
            target=PLATFORM_OPERATION_APPROVALS_TARGET,
        )
        store = _operation_approval_store(app)
        try:
            try:
                store.get_record(request.approval_id)
            except OperationApprovalError as error:
                if not str(error).startswith("Unknown operation approval record:"):
                    raise
            else:
                raise OperationApprovalError(
                    f"Operation approval record already exists: {request.approval_id}"
                )
            record = OperationApprovalRecord(
                approval_id=request.approval_id,
                operation_type=request.operation_type,
                operation_id=request.operation_id,
                target=request.target,
                requested_by=request.requested_by,
                request_reason=request.request_reason,
                approved_by=None,
                approval_reason=None,
                status=OPERATION_APPROVAL_PENDING,
                decision_reason="pending approval",
                requested_at=_aware_timestamp(request.requested_at),
                decided_at=None,
            )
            store.save_record(record)
        except OperationApprovalError as error:
            _record_operation_approval_access_denial(
                app,
                approval_id=request.approval_id,
                actor=identity.actor,
                permission=CREATE_PLATFORM_OPERATION_APPROVALS,
                error=error,
            )
            raise _http_exception_from_operation_approval_error(error) from error
        finally:
            store.close()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=CREATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(record.approval_id),
            outcome="granted",
            reason="created pending approval",
        )
        return {"record": _operation_approval_record_response(record)}

    @app.get("/platform/operation-approvals")
    def list_operation_approvals(
        status_filter: str | None = Query(default=None, alias="status"),
        operation_type: str | None = None,
        operation_id: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        sort_by: str = Query(default="requested_at"),
        sort_order: str = Query(default="desc"),
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=PLATFORM_OPERATION_APPROVALS_TARGET,
        )
        store = _operation_approval_store(app)
        try:
            records = store.query_records(
                status=status_filter,
                operation_type=operation_type,
                operation_id=operation_id,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
            total_count = store.count_records(
                status=status_filter,
                operation_type=operation_type,
                operation_id=operation_id,
            )
        except OperationApprovalError as error:
            _record_operation_approval_access_denial(
                app,
                approval_id=None,
                actor=identity.actor,
                permission=VIEW_PLATFORM_OPERATION_APPROVALS,
                error=error,
            )
            raise _http_exception_from_operation_approval_error(error) from error
        finally:
            store.close()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=PLATFORM_OPERATION_APPROVALS_TARGET,
            outcome="granted",
            reason=(
                f"sort_by={sort_by} sort_order={sort_order} "
                f"limit={limit} offset={offset}"
            ),
        )
        return {
            "records": [_operation_approval_record_response(record) for record in records],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(records),
                "total_count": total_count,
                "has_next_page": _has_next_page(
                    limit=limit,
                    offset=offset,
                    returned_count=len(records),
                    total_count=total_count,
                ),
                "next_offset": _next_offset(
                    limit=limit,
                    offset=offset,
                    returned_count=len(records),
                    total_count=total_count,
                ),
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        }

    @app.get("/platform/operation-approvals/{approval_id}")
    def get_operation_approval(
        approval_id: str,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        store = _operation_approval_store(app)
        try:
            record = store.get_record(approval_id)
        except OperationApprovalError as error:
            _record_operation_approval_access_denial(
                app,
                approval_id=approval_id,
                actor=identity.actor,
                permission=VIEW_PLATFORM_OPERATION_APPROVALS,
                error=error,
            )
            raise _http_exception_from_operation_approval_error(error) from error
        finally:
            store.close()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            outcome="granted",
        )
        return {"record": _operation_approval_record_response(record)}

    @app.get(
        "/platform/operation-approvals/{approval_id}/view",
        response_class=HTMLResponse,
    )
    def view_operation_approval(
        approval_id: str,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> HTMLResponse:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        store = _operation_approval_store(app)
        try:
            record = store.get_record(approval_id)
        except OperationApprovalError as error:
            _record_operation_approval_access_denial(
                app,
                approval_id=approval_id,
                actor=identity.actor,
                permission=VIEW_PLATFORM_OPERATION_APPROVALS,
                error=error,
            )
            raise _http_exception_from_operation_approval_error(error) from error
        finally:
            store.close()
        _record_api_access(
            app,
            actor=identity.actor,
            permission=VIEW_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            outcome="granted",
            reason="view detail",
        )
        async_run = _async_run_or_none(app, record.operation_id)
        platform_result = None
        if async_run is not None and async_run.status == "completed":
            platform_result = _platform_result_or_none(app, async_run.run_id)
        return HTMLResponse(
            render_operation_approval_detail_html(
                record=record,
                async_run=async_run,
                platform_result=platform_result,
                access_events=_access_events(app),
                retry_permission=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
                chrome_css=_platform_chrome_css(),
                content_css=_platform_content_css(),
                topbar_html=_platform_topbar_html("approvals"),
                side_nav_html=_platform_side_nav_html("approvals"),
                page_header_html=_platform_page_header_html(
                    "Operation Approval Detail",
                    "Read-only approval context and lifecycle timeline.",
                    active_nav="approvals",
                ),
            )
        )

    @app.patch("/platform/operation-approvals/{approval_id}/approve")
    def approve_operation_approval(
        approval_id: str,
        request: DecideOperationApprovalRequest,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        _require_identity_actor_matches(
            app,
            identity,
            submitted_actor=request.decided_by,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            field_name="decided_by",
        )
        try:
            record, retried_run = _approve_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=request.decided_by,
                decision_reason=request.decision_reason,
                decided_at=_aware_timestamp(request.decided_at),
                actor=identity.actor,
            )
        except OperationApprovalError as error:
            raise _http_exception_from_operation_approval_error(error) from error
        except PlatformAsyncRunStoreError as error:
            raise _http_exception_from_async_run_store_error(error) from error
        response = {"record": _operation_approval_record_response(record)}
        if retried_run is not None:
            response["run"] = _async_run_response(app, retried_run)
        return response

    @app.patch("/platform/operation-approvals/{approval_id}/reject")
    def reject_operation_approval(
        approval_id: str,
        request: DecideOperationApprovalRequest,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        _require_identity_actor_matches(
            app,
            identity,
            submitted_actor=request.decided_by,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            field_name="decided_by",
        )
        try:
            record = _reject_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=request.decided_by,
                decision_reason=request.decision_reason,
                decided_at=_aware_timestamp(request.decided_at),
                actor=identity.actor,
            )
        except OperationApprovalError as error:
            raise _http_exception_from_operation_approval_error(error) from error
        return {"record": _operation_approval_record_response(record)}

    @app.post("/platform/operation-approvals/{approval_id}/approve-form")
    async def approve_operation_approval_form(
        approval_id: str,
        request: Request,
    ) -> RedirectResponse:
        form = _parse_form_body(await request.body())
        try:
            _validate_form_confirmation(
                form,
                expected=APPROVE_OPERATION_APPROVAL_CONFIRMATION,
            )
            identity = _identity_context(_required_form_text(form, "decided_by"), None)
            _require_permission(
                app,
                identity,
                permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
                target=_operation_approval_target(approval_id),
            )
            _approve_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=_required_form_text(form, "decided_by"),
                decision_reason=_required_form_text(form, "decision_reason"),
                decided_at=_aware_timestamp(
                    datetime.fromisoformat(_required_form_text(form, "decided_at"))
                ),
                actor=identity.actor,
            )
        except (OperationApprovalError, PlatformAsyncRunStoreError, ValueError) as error:
            message = quote(str(error), safe="")
            return RedirectResponse(
                url=f"/platform/view?approval_error={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url="/platform/view?approval_status=approved",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/platform/operation-approvals/{approval_id}/reject-form")
    async def reject_operation_approval_form(
        approval_id: str,
        request: Request,
    ) -> RedirectResponse:
        form = _parse_form_body(await request.body())
        try:
            _validate_form_confirmation(
                form,
                expected=REJECT_OPERATION_APPROVAL_CONFIRMATION,
            )
            identity = _identity_context(_required_form_text(form, "decided_by"), None)
            _require_permission(
                app,
                identity,
                permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
                target=_operation_approval_target(approval_id),
            )
            _reject_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=_required_form_text(form, "decided_by"),
                decision_reason=_required_form_text(form, "decision_reason"),
                decided_at=_aware_timestamp(
                    datetime.fromisoformat(_required_form_text(form, "decided_at"))
                ),
                actor=identity.actor,
            )
        except (OperationApprovalError, PlatformAsyncRunStoreError, ValueError) as error:
            message = quote(str(error), safe="")
            return RedirectResponse(
                url=f"/platform/view?approval_error={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url="/platform/view?approval_status=rejected",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/platform/operation-approvals/{approval_id}/cancel-form")
    async def cancel_operation_approval_form(
        approval_id: str,
        request: Request,
    ) -> RedirectResponse:
        form = _parse_form_body(await request.body())
        try:
            _validate_form_confirmation(
                form,
                expected=CANCEL_OPERATION_APPROVAL_CONFIRMATION,
            )
            identity = _identity_context(_required_form_text(form, "decided_by"), None)
            _require_permission(
                app,
                identity,
                permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
                target=_operation_approval_target(approval_id),
            )
            _cancel_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=_required_form_text(form, "decided_by"),
                decision_reason=_required_form_text(form, "decision_reason"),
                decided_at=_aware_timestamp(
                    datetime.fromisoformat(_required_form_text(form, "decided_at"))
                ),
                actor=identity.actor,
            )
        except (OperationApprovalError, PlatformAsyncRunStoreError, ValueError) as error:
            message = quote(str(error), safe="")
            return RedirectResponse(
                url=f"/platform/view?approval_error={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url="/platform/view?approval_status=cancelled",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/platform/operation-approvals/{approval_id}/expire-form")
    async def expire_operation_approval_form(
        approval_id: str,
        request: Request,
    ) -> RedirectResponse:
        form = _parse_form_body(await request.body())
        try:
            _validate_form_confirmation(
                form,
                expected=EXPIRE_OPERATION_APPROVAL_CONFIRMATION,
            )
            identity = _identity_context(_required_form_text(form, "decided_by"), None)
            _require_permission(
                app,
                identity,
                permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
                target=_operation_approval_target(approval_id),
            )
            _expire_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=_required_form_text(form, "decided_by"),
                decision_reason=_required_form_text(form, "decision_reason"),
                decided_at=_aware_timestamp(
                    datetime.fromisoformat(_required_form_text(form, "decided_at"))
                ),
                actor=identity.actor,
            )
        except (OperationApprovalError, PlatformAsyncRunStoreError, ValueError) as error:
            message = quote(str(error), safe="")
            return RedirectResponse(
                url=f"/platform/view?approval_error={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url="/platform/view?approval_status=expired",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.patch("/platform/operation-approvals/{approval_id}/cancel")
    def cancel_operation_approval(
        approval_id: str,
        request: DecideOperationApprovalRequest,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        _require_identity_actor_matches(
            app,
            identity,
            submitted_actor=request.decided_by,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            field_name="decided_by",
        )
        try:
            record = _cancel_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=request.decided_by,
                decision_reason=request.decision_reason,
                decided_at=_aware_timestamp(request.decided_at),
                actor=identity.actor,
            )
        except OperationApprovalError as error:
            raise _http_exception_from_operation_approval_error(error) from error
        return {"record": _operation_approval_record_response(record)}

    @app.patch("/platform/operation-approvals/{approval_id}/expire")
    def expire_operation_approval(
        approval_id: str,
        request: DecideOperationApprovalRequest,
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> dict:
        identity = _identity_context(x_actor_id, x_actor_role)
        _require_permission(
            app,
            identity,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
        )
        _require_identity_actor_matches(
            app,
            identity,
            submitted_actor=request.decided_by,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            field_name="decided_by",
        )
        try:
            record = _expire_operation_approval(
                app,
                approval_id=approval_id,
                decided_by=request.decided_by,
                decision_reason=request.decision_reason,
                decided_at=_aware_timestamp(request.decided_at),
                actor=identity.actor,
            )
        except OperationApprovalError as error:
            raise _http_exception_from_operation_approval_error(error) from error
        return {"record": _operation_approval_record_response(record)}

    @app.get("/platform/api-access-investigation-cases")
    def list_api_access_investigation_cases(
        status_filter: str | None = Query(default=None, alias="status"),
        actor: str | None = None,
        assigned_to: str | None = None,
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        store = _investigation_store(app)
        try:
            cases = store.query_cases(
                status=status_filter,
                actor=actor,
                assigned_to=assigned_to,
            )
        finally:
            store.close()
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=VIEW_PLATFORM_API_INVESTIGATION_CASES,
            target=PLATFORM_API_INVESTIGATION_CASES_TARGET,
            outcome="granted",
        )
        return {"cases": [_investigation_case_response(case) for case in cases]}

    @app.get("/platform/api-access-investigation-cases/{case_id}")
    def get_api_access_investigation_case(
        case_id: str,
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        store = _investigation_store(app)
        try:
            case = store.get_case(case_id)
        except ComplianceAuditError as error:
            _record_api_access(
                app,
                actor=_api_actor(x_actor_id),
                permission=VIEW_PLATFORM_API_INVESTIGATION_CASES,
                target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
                outcome="denied",
                reason=f"404 {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": type(error).__name__,
                    "message": str(error),
                },
            ) from error
        finally:
            store.close()
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=VIEW_PLATFORM_API_INVESTIGATION_CASES,
            target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
            outcome="granted",
        )
        return {"case": _investigation_case_response(case)}

    @app.patch("/platform/api-access-investigation-cases/{case_id}/start")
    def start_api_access_investigation_case(
        case_id: str,
        request: StartInvestigationRequest,
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        try:
            case = _update_investigation_case(
                app,
                case_id=case_id,
                update=lambda service: service.start_investigation(
                    case_id,
                    assigned_to=request.assigned_to,
                    started_at=_aware_timestamp(request.started_at),
                ),
            )
        except ComplianceAuditError as error:
            _record_case_update_denial(app, case_id, x_actor_id, error)
            raise _http_exception_from_compliance_error(error) from error
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=UPDATE_PLATFORM_API_INVESTIGATION_CASES,
            target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
            outcome="granted",
            reason="started",
        )
        return {"case": _investigation_case_response(case)}

    @app.patch("/platform/api-access-investigation-cases/{case_id}/resolve")
    def resolve_api_access_investigation_case(
        case_id: str,
        request: CloseInvestigationRequest,
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        try:
            case = _update_investigation_case(
                app,
                case_id=case_id,
                update=lambda service: service.resolve(
                    case_id,
                    closed_by=request.closed_by,
                    reason=request.reason,
                    closed_at=_aware_timestamp(request.closed_at),
                ),
            )
        except ComplianceAuditError as error:
            _record_case_update_denial(app, case_id, x_actor_id, error)
            raise _http_exception_from_compliance_error(error) from error
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=UPDATE_PLATFORM_API_INVESTIGATION_CASES,
            target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
            outcome="granted",
            reason="resolved",
        )
        return {"case": _investigation_case_response(case)}

    @app.patch("/platform/api-access-investigation-cases/{case_id}/false-positive")
    def mark_api_access_investigation_case_false_positive(
        case_id: str,
        request: CloseInvestigationRequest,
        x_actor_id: str | None = Header(default=None),
    ) -> dict:
        try:
            case = _update_investigation_case(
                app,
                case_id=case_id,
                update=lambda service: service.mark_false_positive(
                    case_id,
                    closed_by=request.closed_by,
                    reason=request.reason,
                    closed_at=_aware_timestamp(request.closed_at),
                ),
            )
        except ComplianceAuditError as error:
            _record_case_update_denial(app, case_id, x_actor_id, error)
            raise _http_exception_from_compliance_error(error) from error
        _record_api_access(
            app,
            actor=_api_actor(x_actor_id),
            permission=UPDATE_PLATFORM_API_INVESTIGATION_CASES,
            target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
            outcome="granted",
            reason="false_positive",
        )
        return {"case": _investigation_case_response(case)}

    return app


def _service_request(request: PaymentRunRequest) -> PlatformApiPaymentRequest:
    requested_at = request.requested_at
    if requested_at.tzinfo is None or requested_at.utcoffset() is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)
    return PlatformApiPaymentRequest(
        run_id=request.run_id,
        customer_id=request.customer_id,
        full_name=request.full_name,
        date_of_birth=request.date_of_birth,
        country=request.country,
        address=request.address,
        identification_number=request.identification_number,
        expected_monthly_volume_cents=request.expected_monthly_volume_cents,
        amount=request.amount,
        currency=request.currency,
        order_id=request.order_id,
        requested_at=requested_at,
        device_id=request.device_id,
        ip_country=request.ip_country,
        beneficiary_id=request.beneficiary_id,
        actor=request.actor,
    )


def _access_audit_store(app: FastAPI) -> SQLiteAccessAuditStore:
    app.state.access_audit_database_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteAccessAuditStore(app.state.access_audit_database_path)


def _investigation_store(app: FastAPI) -> SQLiteInvestigationCaseStore:
    app.state.investigation_database_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteInvestigationCaseStore(app.state.investigation_database_path)


def _operation_approval_store(app: FastAPI) -> SQLiteOperationApprovalStore:
    app.state.operation_approval_database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    return SQLiteOperationApprovalStore(app.state.operation_approval_database_path)


def _access_events(app: FastAPI) -> tuple[AuditAccessEvent, ...]:
    store = _access_audit_store(app)
    try:
        return store.access_events
    finally:
        store.close()


def _operation_approval_records(app: FastAPI) -> tuple[OperationApprovalRecord, ...]:
    store = _operation_approval_store(app)
    try:
        return store.records
    finally:
        store.close()


def _process_async_worker(
    app: FastAPI,
    *,
    limit: int | None,
) -> PlatformAsyncWorkerResult | tuple[PlatformAsyncWorkerResult, ...]:
    app.state.async_database_path.parent.mkdir(parents=True, exist_ok=True)
    app.state.database_path.parent.mkdir(parents=True, exist_ok=True)
    async_store = SQLitePlatformAsyncRunStore(app.state.async_database_path)
    platform_store = SQLitePlatformStore(app.state.database_path)
    try:
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
        )
        if limit is None:
            return worker.process_next()
        return worker.process_pending(limit=limit)
    finally:
        async_store.close()
        platform_store.close()


def _persist_platform_api_investigation_cases(
    app: FastAPI,
    *,
    findings: tuple[AccessAnomalyFinding, ...],
    opened_by: str,
) -> tuple[AccessAnomalyInvestigationCase, ...]:
    if not findings:
        return ()
    cases = open_platform_api_access_investigation_cases(
        findings,
        opened_by=opened_by,
        created_at=datetime.now(timezone.utc),
    )
    store = _investigation_store(app)
    try:
        for investigation_case in cases:
            store.save_case(investigation_case)
    finally:
        store.close()
    return cases


def _update_investigation_case(
    app: FastAPI,
    *,
    case_id: str,
    update,
) -> AccessAnomalyInvestigationCase:
    store = _investigation_store(app)
    try:
        existing_case = store.get_case(case_id)
        service = AccessAnomalyInvestigationService()
        service.create_case(
            existing_case.finding,
            opened_by=existing_case.opened_by,
            created_at=existing_case.created_at,
        )
        if existing_case.status != "open":
            service.start_investigation(
                existing_case.case_id,
                assigned_to=existing_case.assigned_to or "unknown_assignee",
                started_at=existing_case.investigation_started_at
                or existing_case.created_at,
            )
        if existing_case.status == "resolved":
            service.resolve(
                existing_case.case_id,
                closed_by=existing_case.closed_by or "unknown_closer",
                reason=existing_case.resolution_reason or "Persisted resolution",
                closed_at=existing_case.closed_at or existing_case.created_at,
            )
        elif existing_case.status == "false_positive":
            service.mark_false_positive(
                existing_case.case_id,
                closed_by=existing_case.closed_by or "unknown_closer",
                reason=existing_case.resolution_reason or "Persisted false positive",
                closed_at=existing_case.closed_at or existing_case.created_at,
            )
        updated_case = update(service)
        store.save_case(updated_case)
        return updated_case
    finally:
        store.close()


def _record_case_update_denial(
    app: FastAPI,
    case_id: str,
    actor: str | None,
    error: ComplianceAuditError,
) -> None:
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=UPDATE_PLATFORM_API_INVESTIGATION_CASES,
        target=f"{PLATFORM_API_INVESTIGATION_CASES_TARGET}/{case_id}",
        outcome="denied",
        reason=f"{_status_for_compliance_error(error)} {type(error).__name__}: {error}",
    )


def _record_operation_approval_access_denial(
    app: FastAPI,
    *,
    approval_id: str | None,
    actor: str | None,
    permission: str,
    error: OperationApprovalError,
) -> None:
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=permission,
        target=(
            PLATFORM_OPERATION_APPROVALS_TARGET
            if approval_id is None
            else _operation_approval_target(approval_id)
        ),
        outcome="denied",
        reason=(
            f"{_status_for_operation_approval_error(error)} "
            f"{type(error).__name__}: {error}"
        ),
    )


def _http_exception_from_compliance_error(error: ComplianceAuditError) -> HTTPException:
    return HTTPException(
        status_code=_status_for_compliance_error(error),
        detail={
            "error": type(error).__name__,
            "message": str(error),
        },
    )


def _http_exception_from_operation_approval_error(
    error: OperationApprovalError,
) -> HTTPException:
    return HTTPException(
        status_code=_status_for_operation_approval_error(error),
        detail={
            "error": type(error).__name__,
            "message": str(error),
        },
    )


def _http_exception_from_async_run_store_error(
    error: PlatformAsyncRunStoreError,
) -> HTTPException:
    return HTTPException(
        status_code=_status_for_async_run_store_error(error),
        detail={
            "error": type(error).__name__,
            "message": str(error),
        },
    )


def _status_for_compliance_error(error: ComplianceAuditError) -> int:
    if str(error).startswith("Unknown investigation case:"):
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


def _status_for_operation_approval_error(error: OperationApprovalError) -> int:
    message = str(error)
    if message.startswith("Unknown operation approval record:"):
        return status.HTTP_404_NOT_FOUND
    if message.startswith("Operation approval record already exists:"):
        return status.HTTP_409_CONFLICT
    if (
        message.startswith("Cannot approve ")
        or message.startswith("Cannot reject ")
        or message.startswith("Cannot cancel ")
        or message.startswith("Cannot expire ")
    ):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _status_for_async_run_store_error(error: PlatformAsyncRunStoreError) -> int:
    message = str(error)
    if message.startswith("Unknown platform async run:"):
        return status.HTTP_404_NOT_FOUND
    if message.startswith("Cannot retry "):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _request_retry_async_run_approval(
    app: FastAPI,
    async_store: SQLitePlatformAsyncRunStore,
    run_id: str,
    *,
    actor: str | None,
    reason: str | None,
    confirmation: str | None,
) -> OperationApprovalRecord:
    normalized_actor = _api_actor(actor)
    target = _async_payment_run_target(run_id)
    try:
        normalized_actor = _required_request_text(actor, "actor")
        normalized_reason = _required_request_text(reason, "reason")
        normalized_confirmation = _required_request_text(
            confirmation,
            "confirmation",
        )
        if normalized_confirmation != RETRY_FAILED_ASYNC_RUN_CONFIRMATION:
            raise PlatformAsyncRunStoreError(
                "confirmation must be retry_failed_async_run"
            )
        run = async_store.get_run(run_id)
        if run.status != ASYNC_RUN_FAILED:
            raise PlatformAsyncRunStoreError(
                f"Cannot retry {run.status} async run: {run.run_id}"
            )
        record = OperationApprovalRecord(
            approval_id=str(uuid4()),
            operation_type=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
            operation_id=run.run_id,
            target=target,
            requested_by=normalized_actor,
            request_reason=normalized_reason,
            approved_by=None,
            approval_reason=None,
            status=OPERATION_APPROVAL_PENDING,
            decision_reason="pending approval",
            requested_at=datetime.now(timezone.utc),
            decided_at=None,
        )
        store = _operation_approval_store(app)
        try:
            store.save_record(record)
        finally:
            store.close()
    except PlatformAsyncRunStoreError as error:
        http_status = _status_for_async_run_store_error(error)
        _record_api_access(
            app,
            actor=normalized_actor,
            permission=CREATE_PLATFORM_OPERATION_APPROVALS,
            target=target,
            outcome="denied",
            reason=f"{http_status} {type(error).__name__}: {error}",
        )
        raise
    except OperationApprovalError as error:
        _record_api_access(
            app,
            actor=normalized_actor,
            permission=CREATE_PLATFORM_OPERATION_APPROVALS,
            target=target,
            outcome="denied",
            reason=(
                f"{_status_for_operation_approval_error(error)} "
                f"{type(error).__name__}: {error}"
            ),
        )
        raise
    _record_api_access(
        app,
        actor=normalized_actor,
        permission=CREATE_PLATFORM_OPERATION_APPROVALS,
        target=_operation_approval_target(record.approval_id),
        outcome="granted",
        reason=f"requested retry approval for run_id={run.run_id}",
    )
    return record


def _approve_operation_approval(
    app: FastAPI,
    *,
    approval_id: str,
    decided_by: str,
    decision_reason: str,
    decided_at: datetime,
    actor: str | None,
) -> tuple[OperationApprovalRecord, PlatformAsyncRun | None]:
    store = _operation_approval_store(app)
    retried_run: PlatformAsyncRun | None = None
    try:
        existing = store.get_record(approval_id)
        if existing.status != OPERATION_APPROVAL_PENDING:
            raise OperationApprovalError(
                f"Cannot approve {existing.status} operation approval record"
            )
        if existing.operation_type == RETRY_PLATFORM_ASYNC_PAYMENT_RUN:
            retried_run = _validate_retry_approval_can_execute(app, existing)
        record = store.approve_pending(
            approval_id,
            approved_by=decided_by,
            approval_reason=decision_reason,
            decided_at=decided_at,
        )
        if existing.operation_type == RETRY_PLATFORM_ASYNC_PAYMENT_RUN:
            retried_run = _execute_approved_retry(app, record)
    except OperationApprovalError as error:
        _record_operation_approval_access_denial(
            app,
            approval_id=approval_id,
            actor=actor,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            error=error,
        )
        raise
    except PlatformAsyncRunStoreError as error:
        _record_api_access(
            app,
            actor=_api_actor(actor),
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            target=_operation_approval_target(approval_id),
            outcome="denied",
            reason=(
                f"{_status_for_async_run_store_error(error)} "
                f"{type(error).__name__}: {error}"
            ),
        )
        raise
    finally:
        store.close()
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
        target=_operation_approval_target(approval_id),
        outcome="granted",
        reason="approved",
    )
    return record, retried_run


def _reject_operation_approval(
    app: FastAPI,
    *,
    approval_id: str,
    decided_by: str,
    decision_reason: str,
    decided_at: datetime,
    actor: str | None,
) -> OperationApprovalRecord:
    store = _operation_approval_store(app)
    try:
        record = store.reject_pending(
            approval_id,
            rejected_by=decided_by,
            rejection_reason=decision_reason,
            decided_at=decided_at,
        )
    except OperationApprovalError as error:
        _record_operation_approval_access_denial(
            app,
            approval_id=approval_id,
            actor=actor,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            error=error,
        )
        raise
    finally:
        store.close()
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
        target=_operation_approval_target(approval_id),
        outcome="granted",
        reason="rejected",
    )
    return record


def _cancel_operation_approval(
    app: FastAPI,
    *,
    approval_id: str,
    decided_by: str,
    decision_reason: str,
    decided_at: datetime,
    actor: str | None,
) -> OperationApprovalRecord:
    store = _operation_approval_store(app)
    try:
        record = store.cancel_pending(
            approval_id,
            cancelled_by=decided_by,
            cancellation_reason=decision_reason,
            decided_at=decided_at,
        )
    except OperationApprovalError as error:
        _record_operation_approval_access_denial(
            app,
            approval_id=approval_id,
            actor=actor,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            error=error,
        )
        raise
    finally:
        store.close()
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
        target=_operation_approval_target(approval_id),
        outcome="granted",
        reason="cancelled",
    )
    return record


def _expire_operation_approval(
    app: FastAPI,
    *,
    approval_id: str,
    decided_by: str,
    decision_reason: str,
    decided_at: datetime,
    actor: str | None,
) -> OperationApprovalRecord:
    store = _operation_approval_store(app)
    try:
        record = store.expire_pending(
            approval_id,
            expired_by=decided_by,
            expiration_reason=decision_reason,
            decided_at=decided_at,
        )
    except OperationApprovalError as error:
        _record_operation_approval_access_denial(
            app,
            approval_id=approval_id,
            actor=actor,
            permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
            error=error,
        )
        raise
    finally:
        store.close()
    _record_api_access(
        app,
        actor=_api_actor(actor),
        permission=UPDATE_PLATFORM_OPERATION_APPROVALS,
        target=_operation_approval_target(approval_id),
        outcome="granted",
        reason="expired",
    )
    return record


def _validate_retry_approval_can_execute(
    app: FastAPI,
    record: OperationApprovalRecord,
) -> PlatformAsyncRun:
    async_store = _async_run_store(app)
    try:
        run = async_store.get_run(record.operation_id)
        if run.status != ASYNC_RUN_FAILED:
            raise PlatformAsyncRunStoreError(
                f"Cannot retry {run.status} async run: {run.run_id}"
            )
        return run
    finally:
        async_store.close()


def _execute_approved_retry(
    app: FastAPI,
    record: OperationApprovalRecord,
) -> PlatformAsyncRun:
    async_store = _async_run_store(app)
    try:
        run = async_store.retry_failed(
            record.operation_id,
            retried_at=datetime.now(timezone.utc),
        )
    finally:
        async_store.close()
    _record_api_access(
        app,
        actor=_api_actor(record.approved_by),
        permission=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
        target=record.target,
        outcome="granted",
        reason=(
            f"approval_id={record.approval_id}; "
            f"requested_by={record.requested_by}; "
            f"approval_reason={record.approval_reason}"
        ),
    )
    return run


def _async_run_store(app: FastAPI) -> SQLitePlatformAsyncRunStore:
    app.state.async_database_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLitePlatformAsyncRunStore(app.state.async_database_path)


def _form_value(form: dict[str, list[str]], field_name: str) -> str | None:
    values = form.get(field_name)
    if not values:
        return None
    return values[0]


def _parse_form_body(body: bytes) -> dict[str, list[str]]:
    return parse_qs(body.decode("utf-8"), keep_blank_values=True)


def _required_form_text(form: dict[str, list[str]], field_name: str) -> str:
    return _required_request_text(_form_value(form, field_name), field_name)


def _validate_form_confirmation(
    form: dict[str, list[str]],
    *,
    expected: str,
) -> None:
    confirmation = _required_form_text(form, "confirmation")
    if confirmation != expected:
        raise PlatformAsyncRunStoreError(f"confirmation must be {expected}")


def _required_request_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise PlatformAsyncRunStoreError(f"{field_name} is required")
    normalized = value.strip()
    if not normalized:
        raise PlatformAsyncRunStoreError(f"{field_name} is required")
    return normalized


def _approval_text_or_default(value: str | None, default: str) -> str:
    if value is None:
        return default
    normalized = value.strip()
    return normalized or default


def _record_api_access(
    app: FastAPI,
    *,
    actor: str,
    permission: str,
    target: str,
    outcome: str,
    reason: str | None = None,
) -> None:
    store = _access_audit_store(app)
    try:
        store.save_event(
            AuditAccessEvent(
                event_type=(
                    "audit_access.granted"
                    if outcome == "granted"
                    else "audit_access.denied"
                ),
                actor=_api_actor(actor),
                permission=permission,
                target=target,
                outcome=outcome,
                occurred_at=datetime.now(timezone.utc),
                reason=reason,
            )
        )
    finally:
        store.close()


def _api_actor(value: str | None) -> str:
    if value is None:
        return ANONYMOUS_API_CLIENT
    normalized = value.strip()
    return normalized or ANONYMOUS_API_CLIENT


def _identity_context(
    actor_value: str | None,
    role_value: str | None = None,
) -> PlatformIdentityContext:
    actor = _api_actor(actor_value)
    roles = _roles_from_header(role_value)
    source = "x-actor-role"
    if not roles:
        roles = _roles_for_actor(actor)
        source = "actor_inference"
    return PlatformIdentityContext(actor=actor, roles=roles, source=source)


def _roles_from_header(role_value: str | None) -> tuple[str, ...]:
    if role_value is None:
        return ()
    roles = tuple(
        role.strip()
        for role in role_value.split(",")
        if role.strip()
    )
    return roles


def _roles_for_actor(actor: str) -> tuple[str, ...]:
    if actor == ANONYMOUS_API_CLIENT:
        return (ROLE_API_VIEWER,)
    if actor == "system_scheduler":
        return (ROLE_SYSTEM_SCHEDULER,)
    if actor.startswith("async_worker"):
        return (ROLE_ASYNC_WORKER,)
    if actor.startswith("ops_manager"):
        return (ROLE_OPS_MANAGER,)
    if actor.startswith("ops_user"):
        return (ROLE_OPS_USER,)
    if actor.startswith("approval_requester"):
        return (ROLE_APPROVAL_REQUESTER,)
    if actor.startswith("approval_viewer"):
        return (ROLE_APPROVAL_VIEWER,)
    if actor.startswith("audit_reader") or actor.startswith("api_audit_reader"):
        return (ROLE_AUDIT_READER,)
    if actor.startswith("api_compliance_lead") or actor.startswith(
        "platform_compliance_lead"
    ):
        return (ROLE_COMPLIANCE_LEAD,)
    if actor.startswith("api_investigator") or actor.startswith(
        "platform_investigator"
    ):
        return (ROLE_INVESTIGATOR,)
    if actor.startswith("console_reader"):
        return (ROLE_CONSOLE_READER,)
    if actor.startswith("api_viewer") or actor.endswith("_viewer_001"):
        return (ROLE_API_VIEWER,)
    if actor.startswith("api_client"):
        return (ROLE_API_CLIENT,)
    return (ROLE_API_VIEWER,)


def _identity_has_permission(
    identity: PlatformIdentityContext,
    permission: str,
) -> bool:
    return any(permission in PERMISSIONS_BY_ROLE.get(role, set()) for role in identity.roles)


def _require_permission(
    app: FastAPI,
    identity: PlatformIdentityContext,
    *,
    permission: str,
    target: str,
) -> None:
    if _identity_has_permission(identity, permission):
        return
    reason = (
        f"403 permission denied: actor={identity.actor}; "
        f"roles={','.join(identity.roles) or 'none'}; "
        f"required_permission={permission}; source={identity.source}"
    )
    _record_api_access(
        app,
        actor=identity.actor,
        permission=permission,
        target=target,
        outcome="denied",
        reason=reason,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "PermissionDenied",
            "message": reason,
        },
    )


def _require_identity_actor_matches(
    app: FastAPI,
    identity: PlatformIdentityContext,
    *,
    submitted_actor: str,
    permission: str,
    target: str,
    field_name: str,
) -> None:
    normalized_submitted_actor = _api_actor(submitted_actor)
    if identity.actor == normalized_submitted_actor:
        return
    reason = (
        f"403 identity mismatch: x-actor-id={identity.actor}; "
        f"{field_name}={normalized_submitted_actor}"
    )
    _record_api_access(
        app,
        actor=identity.actor,
        permission=permission,
        target=target,
        outcome="denied",
        reason=reason,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "IdentityMismatch",
            "message": reason,
        },
    )


def _payment_run_target(run_id: str) -> str:
    return f"{PLATFORM_API_PAYMENT_RUNS_TARGET}/{run_id}"


def _async_payment_run_target(run_id: str) -> str:
    return f"{PLATFORM_API_ASYNC_PAYMENT_RUNS_TARGET}/{run_id}"


def _operation_approval_target(approval_id: str) -> str:
    return f"{PLATFORM_OPERATION_APPROVALS_TARGET}/{approval_id}"


def _aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _async_run_response(
    app: FastAPI,
    run: PlatformAsyncRun,
    *,
    include_platform_result: bool = True,
) -> dict:
    response = {
        "run_id": run.run_id,
        "status": run.status,
        "request_fingerprint": run.request_fingerprint,
        "attempt_count": run.attempt_count,
        "max_attempts": run.max_attempts,
        "last_error": run.last_error,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "request": dict(run.request_payload),
    }
    if include_platform_result:
        response["platform_result"] = _platform_result_or_none(app, run.run_id)
    return response


def _platform_result_or_none(app: FastAPI, run_id: str) -> dict | None:
    app.state.database_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLitePlatformStore(app.state.database_path)
    try:
        try:
            snapshot = store.get_run(run_id)
        except SQLitePlatformStoreError:
            return None
        return PlatformApiService(store=store).get_payment_run(snapshot.record.run_id)
    finally:
        store.close()


def _platform_snapshot_or_none(app: FastAPI, run_id: str) -> PlatformRunSnapshot | None:
    app.state.database_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLitePlatformStore(app.state.database_path)
    try:
        try:
            return store.get_run(run_id)
        except SQLitePlatformStoreError:
            return None
    finally:
        store.close()


def _async_run_or_none(app: FastAPI, run_id: str) -> PlatformAsyncRun | None:
    store = _async_run_store(app)
    try:
        try:
            return store.get_run(run_id)
        except PlatformAsyncRunStoreError:
            return None
    finally:
        store.close()


def _worker_result_response(result: PlatformAsyncWorkerResult) -> dict:
    return {
        "processed": result.processed,
        "run_id": result.run_id,
        "async_status": result.async_status,
        "platform_status": result.platform_status,
        "error": result.error,
    }


def _worker_audit_reason(
    results: tuple[PlatformAsyncWorkerResult, ...],
) -> str:
    processed = [result for result in results if result.processed]
    if not processed:
        return "processed=0"
    run_ids = ",".join(result.run_id or "" for result in processed)
    return f"processed={len(processed)} run_ids={run_ids}"


def _access_event_response(event: AuditAccessEvent) -> dict:
    return {
        "event_type": event.event_type,
        "actor": event.actor,
        "permission": event.permission,
        "target": event.target,
        "outcome": event.outcome,
        "occurred_at": event.occurred_at.isoformat(),
        "reason": event.reason,
    }


def _finding_response(finding: AccessAnomalyFinding) -> dict:
    return {
        "finding_type": finding.finding_type,
        "actor": finding.actor,
        "severity": finding.severity,
        "event_count": finding.event_count,
        "reason": finding.reason,
        "first_occurred_at": finding.first_occurred_at.isoformat(),
        "last_occurred_at": finding.last_occurred_at.isoformat(),
        "events": [_access_event_response(event) for event in finding.events],
    }


def _investigation_case_response(case: AccessAnomalyInvestigationCase) -> dict:
    return {
        "case_id": case.case_id,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "opened_by": case.opened_by,
        "assigned_to": case.assigned_to,
        "investigation_started_at": (
            case.investigation_started_at.isoformat()
            if case.investigation_started_at is not None
            else None
        ),
        "closed_by": case.closed_by,
        "closed_at": (
            case.closed_at.isoformat() if case.closed_at is not None else None
        ),
        "resolution_reason": case.resolution_reason,
        "finding": _finding_response(case.finding),
    }


def _operation_approval_record_response(record: OperationApprovalRecord) -> dict:
    return {
        "approval_id": record.approval_id,
        "operation_type": record.operation_type,
        "operation_id": record.operation_id,
        "target": record.target,
        "requested_by": record.requested_by,
        "request_reason": record.request_reason,
        "approved_by": record.approved_by,
        "approval_reason": record.approval_reason,
        "status": record.status,
        "decision_reason": record.decision_reason,
        "requested_at": record.requested_at.isoformat(),
        "decided_at": (
            None if record.decided_at is None else record.decided_at.isoformat()
        ),
    }


def _payment_run_reconciliation_rows(
    app: FastAPI,
    run_id: str,
) -> list[tuple[object, ...]]:
    snapshot = _platform_snapshot_or_none(app, run_id)
    if snapshot is None:
        return []
    return [
        (
            finding.check_id,
            finding.status,
            finding.severity,
            finding.message,
        )
        for finding in evaluate_platform_ledger_reconciliation((snapshot,))
    ]


def _platform_page_shell(
    *,
    title: str,
    subtitle: str,
    active_nav: str,
    content_html: str,
    lang: str = "en",
) -> str:
    return f"""<!doctype html>
<html lang="{html.escape(lang, quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    {_platform_chrome_css()}
    {_platform_content_css()}
  </style>
</head>
<body class="platform-shell">
  {_platform_topbar_html(active_nav)}
  <main class="platform-main">
    <div class="platform-workspace">
      {_platform_side_nav_html(active_nav, lang=lang)}
      <div class="platform-content">
        {_platform_page_header_html(title, subtitle, active_nav=active_nav, lang=lang)}
        {content_html}
      </div>
    </div>
  </main>
</body>
</html>"""


def _platform_topbar_html(active_nav: str) -> str:
    active_area = "manual" if active_nav == "manual" else "console"
    return f"""
  <header class="platform-topbar">
    <div class="platform-brand-block">
      <div class="platform-brand">FinTech Platform</div>
      <div class="platform-caption">Educational operations lab</div>
    </div>
    {_platform_nav_html(active_area)}
  </header>
"""


def _platform_nav_html(active_area: str) -> str:
    nav_items = (
        ("console", "Console", "/platform/view"),
        ("manual", "Manual", "/platform/manual"),
    )
    links = []
    for key, label, href in nav_items:
        current_attr = ' aria-current="page"' if key == active_area else ""
        links.append(
            f'<a href="{html.escape(href, quote=True)}"{current_attr}>'
            f"{html.escape(label)}</a>"
        )
    return f'<nav class="platform-nav" aria-label="Primary navigation">{"".join(links)}</nav>'


def _platform_side_nav_html(active_nav: str, *, lang: str = "en") -> str:
    if active_nav == "manual":
        if lang == "cn":
            heading = "手册目录"
            nav_items = (
                ("#overview", "平台概览"),
                ("#capabilities", "能力清单"),
                ("#workflows", "主要流程"),
                ("#flow-diagram", "详细流程图"),
                ("#audit-cases", "审计与工单"),
                ("#evidence-packages", "证据包"),
                ("#operability", "可运行性"),
                ("#roles-permissions", "角色权限"),
                ("#local-commands", "本地命令"),
                ("#boundary", "教学边界"),
            )
        else:
            heading = "Manual Sections"
            nav_items = (
                ("#overview", "Overview"),
                ("#capabilities", "Capabilities"),
                ("#workflows", "Workflows"),
                ("#flow-diagram", "Flow Diagram"),
                ("#audit-cases", "Audit & Cases"),
                ("#evidence-packages", "Evidence"),
                ("#operability", "Operability"),
                ("#roles-permissions", "Roles"),
                ("#local-commands", "Commands"),
                ("#boundary", "Boundary"),
            )
    else:
        heading = "Console Sections"
        nav_items = (
            ("#dashboard", "Dashboard"),
            ("#payment-runs", "Payment Runs"),
            ("#async-runs", "Async Runs"),
            ("#approvals", "Approvals"),
            ("#reconciliation", "Reconciliation"),
            ("#audit-cases", "Audit & Cases"),
            ("/platform/manual#flow-diagram", "Flow Diagram"),
            ("/platform/manual", "Manual"),
        )
    links = "".join(
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
        for href, label in nav_items
    )
    return f"""
      <aside class="platform-side-nav" aria-label="{html.escape(heading, quote=True)}">
        <div class="platform-side-title">{html.escape(heading)}</div>
        {links}
      </aside>
"""


def _platform_page_header_html(
    title: str,
    subtitle: str,
    *,
    active_nav: str,
    lang: str = "en",
    actions_html: str | None = None,
) -> str:
    kicker = "User Manual" if active_nav == "manual" else "Operations Console"
    if active_nav == "manual" and lang == "cn":
        kicker = "用户手册"
    if actions_html is None:
        actions_html = _platform_default_header_actions_html(active_nav, lang=lang)
    return f"""
    <section class="platform-page-header">
      <div>
        <p class="platform-kicker">{html.escape(kicker)}</p>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)}</p>
      </div>
      <div class="platform-header-actions">
        {actions_html}
      </div>
    </section>
"""


def _platform_default_header_actions_html(active_nav: str, *, lang: str = "en") -> str:
    if active_nav == "manual":
        cn_current = ' aria-current="page"' if lang == "cn" else ""
        en_current = ' aria-current="page"' if lang != "cn" else ""
        return (
            f'<a href="/platform/manual?lang=en"{en_current}>EN</a>'
            f'<a href="/platform/manual?lang=cn"{cn_current}>CN</a>'
            '<a href="/platform/manual#flow-diagram">Flow Diagram</a>'
        )
    return '<a href="/platform/view">Refresh Console</a><a href="/platform/manual">Manual</a>'


def _platform_chrome_css() -> str:
    return """
    :root {
      color-scheme: light;
      --platform-bg: #f3f0e8;
      --platform-panel: #ffffff;
      --platform-panel-subtle: #fbfaf6;
      --platform-ink: #1c211d;
      --platform-muted: #68706a;
      --platform-line: #d8d4c8;
      --platform-strong: #13251f;
      --platform-accent: #0d766b;
      --platform-accent-soft: #e1f2ee;
      --platform-copper: #a35b2b;
      --platform-copper-soft: #f7eadf;
      --platform-warn: #805700;
      --platform-warn-soft: #fff4d2;
      --platform-shadow: 0 14px 34px rgba(28, 33, 29, 0.08);
    }
    * {
      box-sizing: border-box;
    }
    html {
      scroll-behavior: smooth;
    }
    body.platform-shell {
      background: var(--platform-bg);
      color: var(--platform-ink);
      font-family: "Segoe UI", "Aptos", "Helvetica Neue", sans-serif;
      line-height: 1.5;
      margin: 0;
      max-width: none;
      padding: 0;
      width: 100%;
    }
    .platform-topbar {
      align-items: flex-start;
      background: var(--platform-strong);
      color: #ffffff;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      padding: 1rem;
      position: relative;
      z-index: 2;
    }
    .platform-brand-block {
      min-width: 12rem;
    }
    .platform-brand {
      font-size: 1.125rem;
      font-weight: 700;
    }
    .platform-caption {
      color: #b8c7be;
      font-size: 0.875rem;
      margin-top: 0.125rem;
    }
    .platform-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      width: 100%;
    }
    .platform-nav a,
    .platform-header-actions a {
      align-items: center;
      border-radius: 0.375rem;
      display: inline-flex;
      min-height: 44px;
      text-decoration: none;
    }
    .platform-nav a {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.22);
      color: #eef5f0;
      font-size: 0.95rem;
      font-weight: 650;
      padding: 0.625rem 0.875rem;
    }
    .platform-nav a[aria-current="page"] {
      background: #ffffff;
      border-color: #ffffff;
      color: var(--platform-strong);
      font-weight: 700;
    }
    .platform-main {
      margin: 0 auto;
      max-width: 90rem;
      padding: 1rem;
      width: 100%;
    }
    .platform-workspace {
      display: grid;
      gap: 1rem;
      grid-template-columns: 1fr;
    }
    .platform-content {
      min-width: 0;
    }
    .platform-side-nav {
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--platform-line);
      border-radius: 0.5rem;
      box-shadow: var(--platform-shadow);
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
      padding: 0.625rem;
    }
    .platform-side-title {
      align-items: center;
      color: var(--platform-muted);
      display: inline-flex;
      flex: 0 0 auto;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0 0.375rem;
      text-transform: uppercase;
    }
    .platform-side-nav a {
      align-items: center;
      border: 1px solid transparent;
      border-radius: 0.375rem;
      color: var(--platform-strong);
      display: inline-flex;
      flex: 0 0 auto;
      font-size: 0.875rem;
      min-height: 44px;
      padding: 0.5rem 0.625rem;
      text-decoration: none;
    }
    .platform-side-nav a:hover,
    .platform-header-actions a:hover,
    .platform-nav a:hover {
      border-color: var(--platform-accent);
    }
    .platform-page-header {
      align-items: flex-start;
      background: var(--platform-panel);
      border: 1px solid var(--platform-line);
      border-radius: 0.5rem;
      box-shadow: var(--platform-shadow);
      display: flex;
      flex-direction: column;
      gap: 1rem;
      margin-bottom: 1rem;
      padding: 1rem;
    }
    .platform-page-header h1 {
      font-size: 2rem;
      line-height: 1.15;
      margin: 0 0 0.5rem;
    }
    .platform-page-header p {
      color: var(--platform-muted);
      margin: 0;
      max-width: 68ch;
    }
    .platform-kicker {
      color: var(--platform-accent) !important;
      font-size: 0.75rem;
      font-weight: 700;
      margin-bottom: 0.375rem !important;
      text-transform: uppercase;
    }
    .platform-header-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .platform-header-actions a {
      border: 1px solid var(--platform-line);
      color: var(--platform-strong);
      padding: 0.5rem 0.75rem;
    }
    .platform-header-actions a[aria-current="page"] {
      background: var(--platform-accent-soft);
      border-color: var(--platform-accent);
      color: #065f57;
      font-weight: 700;
    }
    @media (min-width: 768px) {
      .platform-topbar {
        padding: 1rem 1.5rem;
      }
      .platform-main {
        padding: 1.5rem;
      }
    }
    @media (min-width: 1024px) {
      .platform-topbar {
        align-items: center;
        flex-direction: row;
        justify-content: space-between;
      }
      .platform-nav {
        justify-content: flex-end;
        width: auto;
      }
      .platform-page-header {
        align-items: flex-end;
        flex-direction: row;
        justify-content: space-between;
      }
      .platform-workspace {
        align-items: start;
        grid-template-columns: 15.5rem minmax(0, 1fr);
      }
      .platform-side-nav {
        align-self: start;
        display: grid;
        gap: 0.25rem;
        overflow: visible;
        padding: 0.875rem;
        position: sticky;
        top: 1rem;
      }
      .platform-side-title {
        padding: 0.375rem 0.5rem;
      }
      .platform-side-nav a {
        width: 100%;
      }
    }
    """


def _platform_content_css() -> str:
    return """
    h2 {
      margin: 0 0 0.75rem;
    }
    .platform-section,
    .section {
      background: var(--platform-panel);
      border: 1px solid var(--platform-line);
      border-radius: 0.5rem;
      box-shadow: 0 10px 24px rgba(28, 33, 29, 0.05);
      margin-top: 1rem;
      overflow-x: auto;
      padding: 1rem;
    }
    .platform-section h2,
    .section h2 {
      color: var(--platform-strong);
      font-size: 1.1rem;
    }
    .section-grid,
    .manual-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: 1fr;
      margin-top: 1rem;
    }
    .summary {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(10.625rem, 1fr));
      margin-top: 1rem;
    }
    .metric {
      background: var(--platform-panel-subtle);
      border: 1px solid var(--platform-line);
      border-radius: 0.5rem;
      padding: 0.875rem;
    }
    .metric-label {
      color: var(--platform-muted);
      font-size: 0.875rem;
      margin-bottom: 0.375rem;
    }
    .metric-value {
      color: var(--platform-strong);
      font-size: 1.5rem;
      font-weight: 700;
    }
    table {
      border-collapse: collapse;
      margin-top: 0.5rem;
      min-width: 42.5rem;
      width: 100%;
    }
    th, td {
      border: 1px solid var(--platform-line);
      padding: 0.5rem 0.625rem;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #eef3ed;
      color: var(--platform-strong);
    }
    .meta,
    .muted {
      color: var(--platform-muted);
      font-size: 0.875rem;
    }
    .page-actions,
    .filter-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .page-actions {
      margin-bottom: 1rem;
    }
    .page-actions a,
    .filter-actions a,
    .filter-actions button,
    .operation-form button {
      align-items: center;
      border-radius: 0.375rem;
      box-sizing: border-box;
      display: inline-flex;
      font: inherit;
      min-height: 44px;
      padding: 0.5rem 0.75rem;
      text-decoration: none;
    }
    .page-actions a,
    .filter-actions a {
      border: 1px solid var(--platform-line);
      color: var(--platform-strong);
    }
    .filter-actions button,
    .operation-form button {
      background: var(--platform-strong);
      border: 0;
      color: #ffffff;
      cursor: pointer;
    }
    .notice,
    .risk-note {
      border-radius: 0.5rem;
      margin: 1rem 0;
      padding: 0.75rem;
    }
    .notice-success {
      background: var(--platform-accent-soft);
      border: 1px solid #a7d9d2;
      color: #075e55;
    }
    .notice-error {
      background: #fff0f0;
      border: 1px solid #f1b6b6;
      color: #8a1f1f;
    }
    .risk-note {
      background: var(--platform-warn-soft);
      border: 1px solid #efd383;
      color: var(--platform-warn);
    }
    .operation-form,
    .filter-form {
      display: grid;
      gap: 0.75rem;
    }
    .operation-form {
      min-width: 16.25rem;
    }
    .filter-form {
      background: var(--platform-panel);
      border: 1px solid var(--platform-line);
      border-radius: 0.5rem;
      margin: 1rem 0;
      padding: 1rem;
    }
    .filter-fields {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: 1fr;
    }
    .filter-field label {
      color: var(--platform-strong);
      display: block;
      font-size: 0.875rem;
      margin-bottom: 0.375rem;
    }
    .filter-field input,
    .filter-field select,
    .operation-form input {
      border: 1px solid var(--platform-line);
      border-radius: 0.375rem;
      font: inherit;
      min-height: 44px;
      padding: 0.5rem;
      width: 100%;
    }
    code {
      background: #eef3ed;
      border-radius: 0.25rem;
      padding: 0.125rem 0.25rem;
    }
    pre {
      background: #16221d;
      border-radius: 0.5rem;
      color: #eef5f0;
      overflow-x: auto;
      padding: 1rem;
    }
    .manual-callout {
      background: var(--platform-copper-soft);
      border: 1px solid #e2b88f;
      border-radius: 0.5rem;
      color: #6f3519;
      margin-top: 1rem;
      padding: 0.875rem;
    }
    .flow-diagram {
      display: grid;
      gap: 0.75rem;
      margin-top: 1rem;
    }
    .flow-step {
      background: var(--platform-panel-subtle);
      border: 1px solid var(--platform-line);
      border-left: 0.25rem solid var(--platform-accent);
      border-radius: 0.5rem;
      padding: 0.875rem;
    }
    .flow-step strong {
      color: var(--platform-strong);
      display: block;
      margin-bottom: 0.25rem;
    }
    .flow-arrow {
      color: var(--platform-muted);
      font-size: 0.875rem;
      font-weight: 700;
      padding-left: 0.875rem;
    }
    .flow-branch {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: 1fr;
    }
    .flow-step-warning {
      border-left-color: var(--platform-copper);
    }
    .flow-step-muted {
      border-left-color: var(--platform-muted);
    }
    .manual-list {
      margin: 0;
      padding-left: 1.25rem;
    }
    .manual-list li {
      margin: 0.375rem 0;
    }
    @media (min-width: 768px) {
      .filter-fields,
      .manual-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .flow-branch {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }
    @media (min-width: 1024px) {
      .section-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .filter-fields {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }
    """


def _render_platform_console_html(
    app: FastAPI,
    *,
    approval_error: str | None = None,
    approval_status: str | None = None,
    actor_filter: str | None = None,
    async_status_filter: str | None = None,
    created_from_filter: str | None = None,
    created_to_filter: str | None = None,
    operation_approval_status_filter: str | None = None,
    payment_status_filter: str | None = None,
    retry_error: str | None = None,
    retry_status: str | None = None,
) -> str:
    filters, date_filters, filter_errors = normalize_console_filters(
        payment_status=payment_status_filter,
        async_status=async_status_filter,
        operation_approval_status=operation_approval_status_filter,
        actor=actor_filter,
        created_from=created_from_filter,
        created_to=created_to_filter,
        payment_status_options=CONSOLE_PAYMENT_STATUS_OPTIONS,
        async_status_options=CONSOLE_ASYNC_STATUS_OPTIONS,
        operation_approval_status_options=CONSOLE_OPERATION_APPROVAL_STATUS_OPTIONS,
    )
    app.state.database_path.parent.mkdir(parents=True, exist_ok=True)
    service = PlatformApiService(
        store=SQLitePlatformStore(app.state.database_path),
    )
    try:
        runs = service.list_payment_runs()
    finally:
        service.store.close()

    access_events = _access_events(app)
    async_runs = _async_runs(app)
    operation_approval_records = _operation_approval_records(app)
    display_runs = _filter_payment_runs(
        app,
        runs,
        status_filter=filters["payment_status"],
        actor_filter=filters["actor"],
        created_from=date_filters["created_from"],
        created_to=date_filters["created_to"],
    )
    display_async_runs = _filter_async_runs(
        async_runs,
        status_filter=filters["async_status"],
        actor_filter=filters["actor"],
        created_from=date_filters["created_from"],
        created_to=date_filters["created_to"],
    )
    display_operation_approval_records = _filter_operation_approval_records(
        operation_approval_records,
        status_filter=filters["operation_approval_status"],
        actor_filter=filters["actor"],
        created_from=date_filters["created_from"],
        created_to=date_filters["created_to"],
    )
    display_platform_snapshots = _platform_snapshots(app, display_runs)
    operations_report = build_platform_operations_report(
        async_runs=display_async_runs,
        snapshots=display_platform_snapshots,
        access_events=access_events,
    )
    display_operations_run_rows = _filter_operations_run_rows(
        operations_report.run_rows,
        payment_status_filter=filters["payment_status"],
        async_status_filter=filters["async_status"],
    )
    ledger_reconciliation_findings = evaluate_platform_ledger_reconciliation(
        display_platform_snapshots,
    )
    operation_approval_report = build_operation_approval_report(
        records=display_operation_approval_records,
    )
    findings = detect_platform_api_access_anomalies(access_events)
    cases = _investigation_cases(app)

    summary_rows = [
        ("Payment runs", str(len(display_runs))),
        ("Completed runs", str(_count_by_status(display_runs, "completed"))),
        (
            "Risk review runs",
            str(_count_by_status(display_runs, "risk_review_required")),
        ),
        ("Async runs", str(len(display_async_runs))),
        (
            "Accepted async runs",
            str(_count_async_status(display_async_runs, "accepted")),
        ),
        ("Failed async runs", str(_count_async_status(display_async_runs, "failed"))),
        ("API access events", str(len(access_events))),
        ("API access anomalies", str(len(findings))),
        ("Investigation cases", str(len(cases))),
        ("Open cases", str(_count_case_status(cases, "open"))),
        ("Investigating cases", str(_count_case_status(cases, "investigating"))),
        ("Ops report findings", str(len(operations_report.findings))),
        (
            "Ledger reconciliation findings",
            str(len(ledger_reconciliation_findings)),
        ),
        (
            "Ledger reconciliation failed",
            str(_count_failed_findings(ledger_reconciliation_findings)),
        ),
        ("Approval records", str(len(operation_approval_report.records))),
        ("Pending approvals", str(operation_approval_report.summary.pending_count)),
        (
            "Cancelled approvals",
            str(operation_approval_report.summary.cancelled_count),
        ),
        ("Expired approvals", str(operation_approval_report.summary.expired_count)),
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Console</title>
  <style>
    body {{
      color: #1f2937;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 0;
      max-width: 1320px;
      padding: 16px;
    }}
    @media (min-width: 768px) {{
      body {{
        padding: 24px;
      }}
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    h2 {{
      margin-top: 28px;
    }}
    .meta {{
      color: #6b7280;
      font-size: 14px;
      margin-bottom: 18px;
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      margin-top: 12px;
    }}
    .metric {{
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 12px;
    }}
    .metric-label {{
      color: #6b7280;
      font-size: 13px;
      margin-bottom: 6px;
    }}
    .metric-value {{
      font-size: 24px;
      font-weight: 700;
    }}
    table {{
      border-collapse: collapse;
      margin-top: 8px;
      min-width: 680px;
      width: 100%;
    }}
    th, td {{
      border: 1px solid #d1d5db;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f3f4f6;
    }}
    .section {{
      margin-top: 24px;
      overflow-x: auto;
    }}
    .section-grid {{
      display: grid;
      gap: 24px;
      grid-template-columns: 1fr;
      margin-top: 24px;
    }}
    @media (min-width: 1024px) {{
      .section-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    .muted {{
      color: #6b7280;
      font-size: 14px;
    }}
    .notice {{
      border-radius: 6px;
      margin: 16px 0;
      padding: 10px 12px;
    }}
    .notice-success {{
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      color: #065f46;
    }}
    .notice-error {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
    }}
    .risk-note {{
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 6px;
      color: #78350f;
      margin: 8px 0 12px;
      padding: 10px 12px;
    }}
    .operation-form {{
      display: grid;
      gap: 8px;
      min-width: 260px;
    }}
    .operation-form input {{
      border: 1px solid #d1d5db;
      border-radius: 4px;
      box-sizing: border-box;
      font: inherit;
      min-height: 44px;
      padding: 8px;
      width: 100%;
    }}
    .operation-form button {{
      background: #1f2937;
      border: 0;
      border-radius: 4px;
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      min-height: 44px;
      padding: 8px 12px;
    }}
    .filter-form {{
      border: 1px solid #d1d5db;
      border-radius: 6px;
      display: grid;
      gap: 12px;
      margin: 16px 0;
      padding: 12px;
    }}
    .filter-fields {{
      display: grid;
      gap: 12px;
      grid-template-columns: 1fr;
    }}
    @media (min-width: 768px) {{
      .filter-fields {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
    }}
    .filter-field label {{
      color: #374151;
      display: block;
      font-size: 14px;
      margin-bottom: 6px;
    }}
    .filter-field input,
    .filter-field select {{
      border: 1px solid #d1d5db;
      border-radius: 4px;
      box-sizing: border-box;
      font: inherit;
      min-height: 44px;
      padding: 8px;
      width: 100%;
    }}
    .filter-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .filter-actions button,
    .filter-actions a {{
      align-items: center;
      border-radius: 4px;
      box-sizing: border-box;
      display: inline-flex;
      font: inherit;
      min-height: 44px;
      padding: 8px 12px;
      text-decoration: none;
    }}
    .filter-actions button {{
      background: #1f2937;
      border: 0;
      color: #ffffff;
      cursor: pointer;
    }}
    .filter-actions a {{
      border: 1px solid #d1d5db;
      color: #1f2937;
    }}
    code {{
      background: #f3f4f6;
      border-radius: 4px;
      padding: 2px 4px;
    }}
    {_platform_chrome_css()}
    {_platform_content_css()}
  </style>
</head>
<body class="platform-shell">
  {_platform_topbar_html("dashboard")}
  <main class="platform-main">
    <div class="platform-workspace">
      {_platform_side_nav_html("dashboard")}
      <div class="platform-content" id="dashboard">
  {_platform_page_header_html(
        "FinTech Platform Console",
        "Minimal operations workbench for the learning platform. API docs remain available at /docs.",
        active_nav="dashboard",
    )}
  {_retry_feedback_html(retry_status=retry_status, retry_error=retry_error)}
  {_approval_feedback_html(
        approval_status=approval_status,
        approval_error=approval_error,
    )}
  {_console_filter_feedback_html(filter_errors)}
  {console_filter_form_html(
        filters,
        payment_status_options=CONSOLE_PAYMENT_STATUS_OPTIONS,
        async_status_options=CONSOLE_ASYNC_STATUS_OPTIONS,
        operation_approval_status_options=CONSOLE_OPERATION_APPROVAL_STATUS_OPTIONS,
    )}

  <div class="summary">
    {''.join(_metric_html(label, value) for label, value in summary_rows)}
  </div>

  <div class="section" id="payment-runs">
    <h2>Recent Payment Runs</h2>
    {_html_table(
        [
            "run_id",
            "customer_id",
            "status",
            "payment_order_status",
            "risk_status",
            "audit_event_count",
            "created_at",
        ],
        _payment_console_rows(_latest_rows(display_runs, key="created_at")),
        empty_message="No payment runs have been recorded yet.",
    )}
  </div>

  <div class="section" id="async-runs">
    <h2>Recent Async Runs</h2>
    {_html_table(
        [
            "run_id",
            "status",
            "attempt_count",
            "platform_status",
            "payment_order_id",
            "last_error",
            "updated_at",
        ],
        _async_console_rows(app, _latest_async_runs(display_async_runs)),
        empty_message="No async runs have been recorded yet.",
    )}
  </div>

  <div class="section" id="failed-async-runs">
    <h2>Failed Async Runs</h2>
    {_failed_async_runs_table(
        _failed_async_runs(display_async_runs),
        empty_message="No failed async runs have been recorded yet.",
    )}
  </div>

  <div class="section-grid">
    <div class="section" id="operations-summary">
      <h2>Operations Report Summary</h2>
      {_table(
        ["metric", "value"],
        _operations_summary_rows(operations_report.summary),
        empty_message="No operations report summary is available yet.",
      )}
    </div>

    <div class="section" id="approval-summary">
      <h2>Operation Approval Summary</h2>
      {_table(
        ["metric", "value"],
        _approval_summary_rows(operation_approval_report.summary),
        empty_message="No operation approval summary is available yet.",
      )}
    </div>
  </div>

  <div class="section" id="operations-run-rows">
    <h2>Operations Run Rows</h2>
    {_table(
        [
            "run_id",
            "async_status",
            "platform_status",
            "attempt_count",
            "retry_granted_count",
            "retry_denied_count",
            "reconciliation_status",
        ],
        _operations_run_rows(display_operations_run_rows),
        empty_message="No operations run rows are available yet.",
    )}
  </div>

  <div class="section" id="reconciliation">
    <h2>Ledger Reconciliation Findings</h2>
    {_table(
        [
            "run_id",
            "check_id",
            "status",
            "severity",
            "message",
        ],
        _ledger_reconciliation_finding_rows(ledger_reconciliation_findings),
        empty_message="No ledger reconciliation findings are available yet.",
    )}
  </div>

  <div class="section" id="approvals">
    <h2>Pending Operation Approvals</h2>
    <div class="risk-note">
      High-impact approval actions can change retry eligibility. Review the async status, request reason, and confirmation text before deciding.
    </div>
    {_html_table(
        [
            "approval_id",
            "operation_type",
            "operation_id",
            "async_status",
            "requested_by",
            "request_reason",
            "requested_at",
            "action",
        ],
        _pending_operation_approval_rows(
            operation_approval_report.records,
            display_async_runs,
        ),
        empty_message="No pending operation approvals have been recorded yet.",
    )}
  </div>

  <div class="section" id="approval-records">
    <h2>Approval Records</h2>
    {_html_table(
        [
            "approval_id",
            "operation_id",
            "requested_by",
            "request_reason",
            "approved_by",
            "status",
            "decision_reason",
        ],
        _approval_record_rows(operation_approval_report.records),
        empty_message="No operation approval records have been recorded yet.",
    )}
  </div>

  <div class="section" id="audit-cases">
    <h2>API Access Anomalies</h2>
    {_table(
        [
            "finding_type",
            "actor",
            "severity",
            "event_count",
            "reason",
            "first_occurred_at",
            "last_occurred_at",
        ],
        [
            (
                finding.finding_type,
                finding.actor,
                finding.severity,
                finding.event_count,
                finding.reason,
                finding.first_occurred_at.isoformat(),
                finding.last_occurred_at.isoformat(),
            )
            for finding in _latest_findings(findings)
        ],
        empty_message="No API access anomalies have been detected yet.",
    )}
  </div>

  <div class="section" id="investigation-cases">
    <h2>Investigation Cases</h2>
    {_table(
        [
            "case_id",
            "status",
            "actor",
            "opened_by",
            "assigned_to",
            "resolution_reason",
            "created_at",
        ],
        [
            (
                case.case_id,
                case.status,
                case.finding.actor,
                case.opened_by,
                case.assigned_to or "",
                case.resolution_reason or "",
                case.created_at.isoformat(),
            )
            for case in _latest_cases(cases)
        ],
        empty_message="No investigation cases have been created yet.",
    )}
  </div>

  <div class="section" id="access-events">
    <h2>Recent API Access Events</h2>
    {_table(
        [
            "occurred_at",
            "actor",
            "permission",
            "target",
            "outcome",
            "reason",
        ],
        [
            (
                event.occurred_at.isoformat(),
                event.actor,
                event.permission,
                event.target,
                event.outcome,
                event.reason or "",
            )
            for event in _latest_access_events(access_events)
        ],
        empty_message="No API access events have been recorded yet.",
    )}
  </div>
      </div>
    </div>
  </main>
</body>
</html>
"""


def _failed_async_runs_table(
    runs: tuple[PlatformAsyncRun, ...],
    *,
    empty_message: str,
) -> str:
    if not runs:
        return f'<div class="muted">{html.escape(empty_message)}</div>'
    headers = [
        "run_id",
        "attempt_count",
        "max_attempts",
        "last_error",
        "updated_at",
        "action",
    ]
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for run in runs:
        cells = [
            _async_run_detail_link(run.run_id),
            html.escape(str(run.attempt_count)),
            html.escape(str(run.max_attempts)),
            html.escape(run.last_error or ""),
            html.escape(run.updated_at.isoformat()),
            _retry_form_html(run.run_id),
        ]
        row_html.append(f"<tr>{''.join(f'<td>{cell}</td>' for cell in cells)}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _retry_form_html(run_id: str) -> str:
    escaped_run_id = html.escape(run_id, quote=True)
    action = f"/platform/async-payment-runs/{escaped_run_id}/retry-form"
    confirmation = html.escape(RETRY_FAILED_ASYNC_RUN_CONFIRMATION, quote=True)
    return f"""
      <form class="operation-form" method="post" action="{action}">
        <input name="actor" type="text" placeholder="actor" required>
        <input name="reason" type="text" placeholder="reason" required>
        <input name="confirmation" type="text" value="{confirmation}" required>
        <button type="submit">Request Approval</button>
      </form>
    """


def _latest_rows(rows: tuple[dict, ...], *, key: str, limit: int = 5) -> tuple[dict, ...]:
    return tuple(sorted(rows, key=lambda row: row[key], reverse=True)[:limit])


def _filter_payment_runs(
    app: FastAPI,
    runs: tuple[dict, ...],
    *,
    status_filter: str | None,
    actor_filter: str | None,
    created_from: date | None,
    created_to: date | None,
) -> tuple[dict, ...]:
    return tuple(
        run
        for run in runs
        if (status_filter is None or run["status"] == status_filter)
        and _date_in_range(
            _date_from_iso_text(run.get("created_at")),
            created_from=created_from,
            created_to=created_to,
        )
        and _payment_run_matches_actor(app, run, actor_filter)
    )


def _filter_async_runs(
    runs: tuple[PlatformAsyncRun, ...],
    *,
    status_filter: str | None,
    actor_filter: str | None,
    created_from: date | None,
    created_to: date | None,
) -> tuple[PlatformAsyncRun, ...]:
    return tuple(
        run
        for run in runs
        if (status_filter is None or run.status == status_filter)
        and _date_in_range(
            run.created_at.date(),
            created_from=created_from,
            created_to=created_to,
        )
        and _async_run_matches_actor(run, actor_filter)
    )


def _filter_operation_approval_records(
    records: tuple[OperationApprovalRecord, ...],
    *,
    status_filter: str | None,
    actor_filter: str | None,
    created_from: date | None,
    created_to: date | None,
) -> tuple[OperationApprovalRecord, ...]:
    return tuple(
        record
        for record in records
        if (status_filter is None or record.status == status_filter)
        and _date_in_range(
            record.requested_at.date(),
            created_from=created_from,
            created_to=created_to,
        )
        and _operation_approval_matches_actor(record, actor_filter)
    )


def _payment_run_matches_actor(
    app: FastAPI,
    run: dict,
    actor_filter: str | None,
) -> bool:
    if actor_filter is None:
        return True
    snapshot = _platform_snapshot_or_none(app, run["run_id"])
    if snapshot is None:
        return False
    return any(
        _text_matches_actor(getattr(event, "actor", None), actor_filter)
        for event in snapshot.audit_events
    )


def _async_run_matches_actor(
    run: PlatformAsyncRun,
    actor_filter: str | None,
) -> bool:
    return _text_matches_actor(run.request_payload.get("actor"), actor_filter)


def _operation_approval_matches_actor(
    record: OperationApprovalRecord,
    actor_filter: str | None,
) -> bool:
    if actor_filter is None:
        return True
    return _text_matches_actor(
        record.requested_by,
        actor_filter,
    ) or _text_matches_actor(record.approved_by, actor_filter)


def _text_matches_actor(value: object, actor_filter: str | None) -> bool:
    if actor_filter is None:
        return True
    if value is None:
        return False
    return actor_filter.lower() in str(value).lower()


def _date_in_range(
    value: date | None,
    *,
    created_from: date | None,
    created_to: date | None,
) -> bool:
    if value is None:
        return created_from is None and created_to is None
    if created_from is not None and value < created_from:
        return False
    if created_to is not None and value > created_to:
        return False
    return True


def _date_from_iso_text(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _filter_operations_run_rows(
    run_rows,
    *,
    payment_status_filter: str | None,
    async_status_filter: str | None,
):
    return [
        row
        for row in run_rows
        if (
            payment_status_filter is None
            or row.platform_status == payment_status_filter
        )
        and (async_status_filter is None or row.async_status == async_status_filter)
    ]


def _has_next_page(
    *,
    limit: int | None,
    offset: int,
    returned_count: int,
    total_count: int,
) -> bool:
    if limit is None:
        return False
    return offset + returned_count < total_count


def _next_offset(
    *,
    limit: int | None,
    offset: int,
    returned_count: int,
    total_count: int,
) -> int | None:
    if not _has_next_page(
        limit=limit,
        offset=offset,
        returned_count=returned_count,
        total_count=total_count,
    ):
        return None
    return offset + returned_count


def _payment_console_rows(rows: tuple[dict, ...]) -> list[tuple[str, ...]]:
    return [
        (
            _payment_run_detail_link(run["run_id"]),
            html.escape(run["customer_id"]),
            html.escape(run["status"]),
            html.escape(run["payment_order_status"] or ""),
            html.escape(run["risk_status"] or ""),
            html.escape(str(run["audit_event_count"])),
            html.escape(run["created_at"]),
        )
        for run in rows
    ]


def _platform_snapshots(
    app: FastAPI,
    runs: tuple[dict, ...],
) -> tuple[PlatformRunSnapshot, ...]:
    store = SQLitePlatformStore(app.state.database_path)
    snapshots: list[PlatformRunSnapshot] = []
    try:
        for run in runs:
            try:
                snapshots.append(store.get_run(run["run_id"]))
            except SQLitePlatformStoreError:
                continue
    finally:
        store.close()
    return tuple(snapshots)


def _async_runs(app: FastAPI) -> tuple[PlatformAsyncRun, ...]:
    app.state.async_database_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLitePlatformAsyncRunStore(app.state.async_database_path)
    try:
        return store.runs
    finally:
        store.close()


def _latest_async_runs(
    runs: tuple[PlatformAsyncRun, ...],
    limit: int = 5,
) -> tuple[PlatformAsyncRun, ...]:
    return tuple(
        sorted(
            runs,
            key=lambda run: (run.updated_at, run.created_at, run.run_id),
            reverse=True,
        )[:limit]
    )


def _failed_async_runs(
    runs: tuple[PlatformAsyncRun, ...],
    limit: int = 5,
) -> tuple[PlatformAsyncRun, ...]:
    return _latest_async_runs(
        tuple(run for run in runs if run.status == "failed"),
        limit=limit,
    )


def _async_console_rows(
    app: FastAPI,
    runs: tuple[PlatformAsyncRun, ...],
) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for run in runs:
        platform_result = _async_platform_result_or_none(app, run)
        rows.append(
            (
                _async_run_detail_link(run.run_id),
                html.escape(run.status),
                html.escape(str(run.attempt_count)),
                html.escape(_platform_result_field(platform_result, "status")),
                html.escape(_platform_result_field(platform_result, "payment_order_id")),
                html.escape(run.last_error or ""),
                html.escape(run.updated_at.isoformat()),
            )
        )
    return rows


def _async_platform_result_or_none(
    app: FastAPI,
    run: PlatformAsyncRun,
) -> dict | None:
    if run.status != "completed":
        return None
    return _platform_result_or_none(app, run.run_id)


def _platform_result_field(platform_result: dict | None, field_name: str) -> str:
    if platform_result is None:
        return ""
    value = platform_result.get(field_name)
    return "" if value is None else str(value)


def _operations_summary_rows(summary) -> list[tuple[object, ...]]:
    return [
        ("async_run_count", summary.async_run_count),
        ("platform_run_count", summary.platform_run_count),
        ("completed_async_run_count", summary.completed_async_run_count),
        ("failed_async_run_count", summary.failed_async_run_count),
        ("retry_granted_count", summary.retry_granted_count),
        ("retry_denied_count", summary.retry_denied_count),
        ("failed_finding_count", summary.failed_finding_count),
        ("warning_finding_count", summary.warning_finding_count),
    ]


def _approval_summary_rows(summary) -> list[tuple[object, ...]]:
    return [
        ("total_record_count", summary.total_record_count),
        ("pending_count", summary.pending_count),
        ("approved_count", summary.approved_count),
        ("rejected_count", summary.rejected_count),
        ("cancelled_count", summary.cancelled_count),
        ("expired_count", summary.expired_count),
        ("retry_operation_count", summary.retry_operation_count),
        ("self_approval_rejected_count", summary.self_approval_rejected_count),
    ]


def _operations_run_rows(run_rows) -> list[tuple[object, ...]]:
    return [
        (
            row.run_id,
            row.async_status or "",
            row.platform_status or "",
            "" if row.attempt_count is None else row.attempt_count,
            row.retry_granted_count,
            row.retry_denied_count,
            row.reconciliation_status,
        )
        for row in run_rows
    ]


def _ledger_reconciliation_finding_rows(findings) -> list[tuple[object, ...]]:
    return [
        (
            finding.run_id,
            finding.check_id,
            finding.status,
            finding.severity,
            finding.message,
        )
        for finding in findings
    ]


def _approval_record_rows(
    records: tuple[OperationApprovalRecord, ...],
) -> list[tuple[str, ...]]:
    return [
        (
            _operation_approval_detail_link(record.approval_id),
            html.escape(record.operation_id),
            html.escape(record.requested_by),
            html.escape(record.request_reason),
            html.escape(record.approved_by or ""),
            html.escape(record.status),
            html.escape(record.decision_reason),
        )
        for record in _sorted_approval_records(records, limit=5)
    ]


def _pending_operation_approval_rows(
    records: tuple[OperationApprovalRecord, ...],
    async_runs: tuple[PlatformAsyncRun, ...],
) -> list[tuple[str, ...]]:
    async_status_by_run_id = {run.run_id: run.status for run in async_runs}
    pending_records = tuple(
        record for record in records if record.status == OPERATION_APPROVAL_PENDING
    )
    return [
        (
            _operation_approval_detail_link(record.approval_id),
            html.escape(record.operation_type),
            html.escape(record.operation_id),
            html.escape(async_status_by_run_id.get(record.operation_id, "")),
            html.escape(record.requested_by),
            html.escape(record.request_reason),
            html.escape(record.requested_at.isoformat()),
            _operation_approval_decision_forms_html(record.approval_id),
        )
        for record in _sorted_approval_records(pending_records, limit=5)
    ]


def _operation_approval_decision_forms_html(approval_id: str) -> str:
    return (
        _operation_approval_decision_form_html(
            approval_id,
            action_name="approve",
            confirmation=APPROVE_OPERATION_APPROVAL_CONFIRMATION,
            button_label="Approve",
        )
        + _operation_approval_decision_form_html(
            approval_id,
            action_name="reject",
            confirmation=REJECT_OPERATION_APPROVAL_CONFIRMATION,
            button_label="Reject",
        )
        + _operation_approval_decision_form_html(
            approval_id,
            action_name="cancel",
            confirmation=CANCEL_OPERATION_APPROVAL_CONFIRMATION,
            button_label="Cancel",
        )
        + _operation_approval_decision_form_html(
            approval_id,
            action_name="expire",
            confirmation=EXPIRE_OPERATION_APPROVAL_CONFIRMATION,
            button_label="Expire",
        )
    )


def _operation_approval_decision_form_html(
    approval_id: str,
    *,
    action_name: str,
    confirmation: str,
    button_label: str,
) -> str:
    href_approval_id = quote(approval_id, safe="")
    escaped_confirmation = html.escape(confirmation, quote=True)
    default_decided_at = html.escape(
        datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        quote=True,
    )
    return f"""
      <form class="operation-form" method="post" action="/platform/operation-approvals/{href_approval_id}/{action_name}-form">
        <input name="decided_by" type="text" placeholder="decided_by" required>
        <input name="decision_reason" type="text" placeholder="decision_reason" required>
        <input name="decided_at" type="text" value="{default_decided_at}" required>
        <input name="confirmation" type="text" value="{escaped_confirmation}" required>
        <button type="submit">{html.escape(button_label)}</button>
      </form>
    """


def _operation_approval_detail_link(approval_id: str) -> str:
    escaped_approval_id = html.escape(approval_id)
    href_approval_id = quote(approval_id, safe="")
    return (
        f'<a href="/platform/operation-approvals/{href_approval_id}/view">'
        f"{escaped_approval_id}</a>"
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


def _sorted_approval_records(
    records: tuple[OperationApprovalRecord, ...],
    *,
    sort_by: str = "requested_at",
    sort_order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
) -> tuple[OperationApprovalRecord, ...]:
    normalized_sort_order = sort_order.lower()
    if sort_by not in OPERATION_APPROVAL_SORT_FIELDS:
        raise ValueError(f"Unknown approval sort field: {sort_by}")
    if normalized_sort_order not in OPERATION_APPROVAL_SORT_ORDERS:
        raise ValueError(f"Unknown approval sort order: {sort_order}")
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than 0")

    sorted_records = sorted(
        records,
        key=lambda record: (
            _operation_approval_sort_value(record, sort_by),
            record.approval_id,
        ),
        reverse=normalized_sort_order == "desc",
    )
    if limit is None:
        return tuple(sorted_records[offset:])
    return tuple(sorted_records[offset : offset + limit])


def _operation_approval_sort_value(
    record: OperationApprovalRecord,
    sort_by: str,
) -> object:
    value = getattr(record, sort_by)
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return value


def _latest_findings(
    findings: tuple[AccessAnomalyFinding, ...],
    limit: int = 5,
) -> tuple[AccessAnomalyFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.last_occurred_at,
                finding.event_count,
                finding.actor,
            ),
            reverse=True,
        )[:limit]
    )


def _latest_cases(
    cases: tuple[AccessAnomalyInvestigationCase, ...],
    limit: int = 5,
) -> tuple[AccessAnomalyInvestigationCase, ...]:
    return tuple(sorted(cases, key=lambda case: case.created_at, reverse=True)[:limit])


def _latest_access_events(
    events: tuple[AuditAccessEvent, ...],
    limit: int = 10,
) -> tuple[AuditAccessEvent, ...]:
    return tuple(sorted(events, key=lambda event: event.occurred_at, reverse=True)[:limit])


def _count_by_status(runs: tuple[dict, ...], status_name: str) -> int:
    return sum(1 for run in runs if run["status"] == status_name)


def _count_async_status(runs: tuple[PlatformAsyncRun, ...], status_name: str) -> int:
    return sum(1 for run in runs if run.status == status_name)


def _count_case_status(
    cases: tuple[AccessAnomalyInvestigationCase, ...],
    status_name: str,
) -> int:
    return sum(1 for case in cases if case.status == status_name)


def _count_failed_findings(findings) -> int:
    return sum(1 for finding in findings if finding.status == "failed")


def _investigation_cases(app: FastAPI) -> tuple[AccessAnomalyInvestigationCase, ...]:
    store = _investigation_store(app)
    try:
        return store.cases
    finally:
        store.close()


app = create_app()
