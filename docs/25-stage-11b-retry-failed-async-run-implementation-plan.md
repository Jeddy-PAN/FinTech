# Retry Failed Async Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a teaching-focused retry action that moves a failed platform async run back to accepted, with confirmation, state constraints, and API access audit.

**Architecture:** Add the state transition at the `SQLitePlatformAsyncRunStore` boundary first, then expose it through a narrow FastAPI endpoint. The endpoint validates the teaching confirmation fields, maps store errors to HTTP statuses, records access audit for both success and failure, and leaves actual business processing to the existing worker endpoints.

**Tech Stack:** Python 3.13, SQLite, FastAPI, Pydantic, pytest.

---

## Files

- Modify: `labs/fintech-platform/platform_async_service.py`
  - Add `SQLitePlatformAsyncRunStore.retry_failed()`.
- Modify: `labs/fintech-platform/test_platform_async_service.py`
  - Add store-level retry tests.
- Modify: `labs/fintech-platform/platform_api_app.py`
  - Add retry request model, permission constant, endpoint, and async-store error mapping helper.
- Modify: `labs/fintech-platform/test_platform_api_app.py`
  - Add API retry success, conflict, not found, confirmation failure, audit, and worker-after-retry tests.
- Modify: `labs/fintech-platform/README.md`
  - Document the new endpoint.
- Modify: `README.md`
  - Add the learning step for retrying failed async runs.
- Modify: `LEARNING_PROGRESS.md`
  - Record completion, test result, and next step.

## Task 1: Store Retry Transition

**Files:**
- Modify: `labs/fintech-platform/test_platform_async_service.py`
- Modify: `labs/fintech-platform/platform_async_service.py`

- [ ] **Step 1: Add failing store tests**

Add these tests after `test_async_worker_retries_failure_until_max_attempts()` in `labs/fintech-platform/test_platform_async_service.py`:

```python
def test_async_run_store_retries_failed_run_to_accepted() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        async_store.create_run(
            _api_request(run_id="run_retry"),
            created_at=_created_at(),
            max_attempts=1,
        )
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )
        failed = worker.process_next(processed_at=_processed_at())

        retried_at = datetime(2026, 5, 20, 9, 10, tzinfo=timezone.utc)
        retried = async_store.retry_failed("run_retry", retried_at=retried_at)

        assert failed.async_status == ASYNC_RUN_FAILED
        assert retried.run_id == "run_retry"
        assert retried.status == ASYNC_RUN_ACCEPTED
        assert retried.attempt_count == 1
        assert retried.max_attempts == 1
        assert retried.last_error is None
        assert retried.completed_at is None
        assert retried.updated_at == retried_at
        assert retried.request_payload["amount"] == "100.00"
        assert retried.request_fingerprint == async_store.get_run(
            "run_retry"
        ).request_fingerprint
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_run_store_rejects_retry_for_non_failed_runs() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        store.create_run(
            _api_request(run_id="run_accepted", order_id="order_accepted"),
            created_at=_created_at(),
        )
        store.create_run(
            _api_request(run_id="run_processing", order_id="order_processing"),
            created_at=datetime(2026, 5, 20, 9, 2, tzinfo=timezone.utc),
        )
        store.create_run(
            _api_request(run_id="run_completed", order_id="order_completed"),
            created_at=datetime(2026, 5, 20, 9, 3, tzinfo=timezone.utc),
        )

        store.mark_processing("run_processing", started_at=_processed_at())
        store.mark_processing("run_completed", started_at=_processed_at())
        store.mark_completed("run_completed", completed_at=_processed_at())

        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry accepted"):
            store.retry_failed("run_accepted", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry processing"):
            store.retry_failed("run_processing", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry completed"):
            store.retry_failed("run_completed", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Unknown platform async run"):
            store.retry_failed("missing_run", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="timezone-aware"):
            store.retry_failed(
                "run_accepted",
                retried_at=datetime(2026, 5, 20, 9, 10),
            )
    finally:
        _close_and_remove(store)
```

- [ ] **Step 2: Run the new store tests and verify they fail**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_async_service.py -k "retry" -v
```

Expected: FAIL because `SQLitePlatformAsyncRunStore` has no `retry_failed` method.

- [ ] **Step 3: Add `retry_failed()` to the async store**

In `labs/fintech-platform/platform_async_service.py`, add this method inside `SQLitePlatformAsyncRunStore`, after `mark_failed()` and before `_get_run_or_none()`:

```python
    def retry_failed(
        self,
        run_id: str,
        *,
        retried_at: datetime,
    ) -> PlatformAsyncRun:
        run = self.get_run(run_id)
        retried_at_text = _timestamp_to_storage(retried_at, "retried_at")
        if run.status != ASYNC_RUN_FAILED:
            raise PlatformAsyncRunStoreError(
                f"Cannot retry {run.status} async run: {run.run_id}"
            )
        with self._connection:
            self._connection.execute(
                """
                UPDATE platform_async_runs
                SET
                    status = ?,
                    updated_at = ?,
                    completed_at = NULL,
                    last_error = NULL
                WHERE run_id = ?
                """,
                (
                    ASYNC_RUN_ACCEPTED,
                    retried_at_text,
                    run.run_id,
                ),
            )
        return self.get_run(run.run_id)
```

- [ ] **Step 4: Run store tests and verify they pass**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_async_service.py -k "retry" -v
```

Expected: PASS for the new retry tests.

- [ ] **Step 5: Run full async service tests**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_async_service.py -v
```

Expected: PASS for all async service tests.

- [ ] **Step 6: Commit store retry transition**

Run:

```powershell
git add .\labs\fintech-platform\platform_async_service.py .\labs\fintech-platform\test_platform_async_service.py
git commit -m "Add failed async run retry transition"
```

## Task 2: FastAPI Retry Endpoint

**Files:**
- Modify: `labs/fintech-platform/test_platform_api_app.py`
- Modify: `labs/fintech-platform/platform_api_app.py`

- [ ] **Step 1: Add imports and API tests**

In `labs/fintech-platform/test_platform_api_app.py`, update the import from `platform_api_app` to include the new permission constant:

```python
from platform_api_app import (
    CREATE_PLATFORM_ASYNC_PAYMENT_RUN,
    CREATE_PLATFORM_PAYMENT_RUN,
    LIST_PLATFORM_PAYMENT_RUNS,
    PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS,
    RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_ASYNC_PAYMENT_RUN,
    VIEW_PLATFORM_PAYMENT_RUN,
    create_app,
)
```

Add these imports near the existing store import:

```python
from platform_async_service import PlatformAsyncWorker, SQLitePlatformAsyncRunStore
from sqlite_platform_store import SQLitePlatformStore
```

Add these tests after `test_platform_api_worker_processes_async_run_to_platform_result()`:

```python
def test_platform_api_retries_failed_async_run_and_worker_processes_it() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        created = client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        retry = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "retry_failed_async_run",
            },
        )
        processed = client.post(
            "/platform/async-worker/process-next",
            headers={"x-actor-id": "async_worker_001"},
        )

        assert created.status_code == 202
        assert retry.status_code == 200
        retry_body = retry.json()["run"]
        assert retry_body["run_id"] == "run_retry_http"
        assert retry_body["status"] == "accepted"
        assert retry_body["attempt_count"] == 3
        assert retry_body["last_error"] is None
        assert retry_body["completed_at"] is None

        assert processed.status_code == 200
        assert processed.json()["result"]["run_id"] == "run_retry_http"
        assert processed.json()["result"]["async_status"] == "completed"

        events = _access_events(access_audit_database_path)
        retry_events = [
            event
            for event in events
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].actor == "ops_user_001"
        assert retry_events[0].target == (
            "fintech_platform_api_async_payment_runs/run_retry_http"
        )
        assert retry_events[0].outcome == "granted"
        assert retry_events[0].reason == "Retry after transient worker failure"
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_rejects_retry_confirmation_error() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )
        _fail_async_run(
            database_path=database_path,
            async_database_path=async_database_path,
        )

        response = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json={
                "actor": "ops_user_001",
                "reason": "Retry after transient worker failure",
                "confirmation": "wrong_confirmation",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "confirmation must be retry_failed_async_run" in response.json()[
            "detail"
        ]["message"]

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert len(retry_events) == 1
        assert retry_events[0].outcome == "denied"
        assert "confirmation must be retry_failed_async_run" in retry_events[0].reason
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)


def test_platform_api_rejects_retry_for_unknown_or_non_failed_async_run() -> None:
    client, database_path, access_audit_database_path, async_database_path = (
        _client_with_async()
    )
    try:
        client.post(
            "/platform/async-payment-runs",
            json=_payload(run_id="run_retry_http", order_id="order_retry_http"),
        )

        unknown = client.post(
            "/platform/async-payment-runs/missing_run/retry",
            json=_retry_payload(),
        )
        conflict = client.post(
            "/platform/async-payment-runs/run_retry_http/retry",
            json=_retry_payload(),
        )

        assert unknown.status_code == 404
        assert unknown.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "Unknown platform async run" in unknown.json()["detail"]["message"]

        assert conflict.status_code == 409
        assert conflict.json()["detail"]["error"] == "PlatformAsyncRunStoreError"
        assert "Cannot retry accepted async run" in conflict.json()["detail"]["message"]

        retry_events = [
            event
            for event in _access_events(access_audit_database_path)
            if event.permission == RETRY_PLATFORM_ASYNC_PAYMENT_RUN
        ]
        assert [event.outcome for event in retry_events] == ["denied", "denied"]
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)
        _remove_database(async_database_path)
```

Add these helpers near `_payload()`:

```python
def _retry_payload() -> dict:
    return {
        "actor": "ops_user_001",
        "reason": "Retry after transient worker failure",
        "confirmation": "retry_failed_async_run",
    }


def _fail_async_run(*, database_path: Path, async_database_path: Path) -> None:
    async_store = SQLitePlatformAsyncRunStore(async_database_path)
    platform_store = SQLitePlatformStore(database_path)
    try:
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )
        for _ in range(3):
            worker.process_next()
        assert async_store.get_run("run_retry_http").status == "failed"
    finally:
        async_store.close()
        platform_store.close()


class _FailingService:
    def create_payment_run(self, request):  # noqa: ARG002
        raise RuntimeError("temporary failure")
```

- [ ] **Step 2: Run API retry tests and verify they fail**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -k "retry" -v
```

Expected: FAIL because `RETRY_PLATFORM_ASYNC_PAYMENT_RUN` and the retry endpoint do not exist yet.

- [ ] **Step 3: Add constants and request model**

In `labs/fintech-platform/platform_api_app.py`, add this constant after `PROCESS_PLATFORM_ASYNC_PAYMENT_RUNS`:

```python
RETRY_PLATFORM_ASYNC_PAYMENT_RUN = "retry_platform_async_run"
```

Add this confirmation constant near the target constants:

```python
RETRY_FAILED_ASYNC_RUN_CONFIRMATION = "retry_failed_async_run"
```

Add this request model after `PaymentRunRequest`:

```python
class RetryAsyncRunRequest(BaseModel):
    actor: str | None = None
    reason: str | None = None
    confirmation: str | None = None
```

- [ ] **Step 4: Add retry endpoint**

In `create_app()`, add this route after `get_async_payment_run()` and before the worker endpoints:

```python
    @app.post("/platform/async-payment-runs/{run_id}/retry")
    def retry_async_payment_run(
        run_id: str,
        request: RetryAsyncRunRequest,
        async_store: SQLitePlatformAsyncRunStore = Depends(get_async_store),
    ) -> dict:
        actor = _required_request_text(request.actor, "actor")
        reason = _required_request_text(request.reason, "reason")
        target = _async_payment_run_target(run_id)
        try:
            confirmation = _required_request_text(
                request.confirmation,
                "confirmation",
            )
            if confirmation != RETRY_FAILED_ASYNC_RUN_CONFIRMATION:
                raise PlatformAsyncRunStoreError(
                    "confirmation must be retry_failed_async_run"
                )
            run = async_store.retry_failed(
                run_id,
                retried_at=datetime.now(timezone.utc),
            )
        except PlatformAsyncRunStoreError as error:
            http_status = _status_for_async_run_store_error(error)
            _record_api_access(
                app,
                actor=actor,
                permission=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
                target=target,
                outcome="denied",
                reason=f"{http_status} {type(error).__name__}: {error}",
            )
            raise HTTPException(
                status_code=http_status,
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
            permission=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
            target=target,
            outcome="granted",
            reason=reason,
        )
        return {"run": _async_run_response(app, run)}
```

- [ ] **Step 5: Add helper functions for request text and error mapping**

In `labs/fintech-platform/platform_api_app.py`, add these helpers after `_status_for_compliance_error()`:

```python
def _status_for_async_run_store_error(error: PlatformAsyncRunStoreError) -> int:
    message = str(error)
    if message.startswith("Unknown platform async run:"):
        return status.HTTP_404_NOT_FOUND
    if message.startswith("Cannot retry "):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _required_request_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise PlatformAsyncRunStoreError(f"{field_name} is required")
    normalized = value.strip()
    if not normalized:
        raise PlatformAsyncRunStoreError(f"{field_name} is required")
    return normalized
```

- [ ] **Step 6: Run API retry tests and verify they pass**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -k "retry" -v
```

Expected: PASS for the new retry endpoint tests.

- [ ] **Step 7: Run full API app tests**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform\test_platform_api_app.py -v
```

Expected: PASS for all API app tests.

- [ ] **Step 8: Commit API retry endpoint**

Run:

```powershell
git add .\labs\fintech-platform\platform_api_app.py .\labs\fintech-platform\test_platform_api_app.py
git commit -m "Add async run retry API"
```

## Task 3: Docs, Progress, and Verification

**Files:**
- Modify: `labs/fintech-platform/README.md`
- Modify: `README.md`
- Modify: `LEARNING_PROGRESS.md`

- [ ] **Step 1: Update `labs/fintech-platform/README.md` endpoint list**

Find the async endpoint list and add:

```text
POST /platform/async-payment-runs/{run_id}/retry
```

Add this paragraph near the async endpoint explanation:

```markdown
阶段 11B 新增教学版 failed async run retry endpoint：`POST /platform/async-payment-runs/{run_id}/retry`。

该接口只允许把 `failed` async run 重新放回 `accepted` 队列，要求请求体包含 `actor`、`reason` 和 `confirmation: retry_failed_async_run`。retry 不直接执行业务处理，后续仍由 worker endpoint 推进；成功和失败都会写入 API access audit。
```

- [ ] **Step 2: Update root `README.md` learning sequence**

After the current step that describes viewing async runs in the console, add:

```markdown
79. 调用 `POST /platform/async-payment-runs/{run_id}/retry`，理解 failed async run 为什么要通过权限、确认、状态约束、幂等和 access audit 才能重新进入 `accepted` 队列。
```

- [ ] **Step 3: Update `LEARNING_PROGRESS.md` current status**

Update the current status bullets so they mention that stage 11B implements failed async run retry after the tests pass.

Add a completion bullet:

```markdown
- 新增阶段 11B failed async run retry API：`POST /platform/async-payment-runs/{run_id}/retry` 支持把 `failed` async run 重新放回 `accepted`，要求 actor、reason 和 confirmation，并记录成功/失败 API access audit
```

Add a history row:

```markdown
| 2026-06-04 | 新增阶段 11B failed async run retry API | `SQLitePlatformAsyncRunStore.retry_failed()` 支持 `failed -> accepted` 状态转换；FastAPI 新增 `POST /platform/async-payment-runs/{run_id}/retry`，要求 actor、reason 和 `retry_failed_async_run` confirmation，成功和失败都写入 API access audit；retry 后现有 worker 可继续处理该 run；fintech-platform pytest 通过 |
```

- [ ] **Step 4: Run focused fintech-platform tests**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\fintech-platform -v
```

Expected: PASS for all `labs/fintech-platform` tests.

- [ ] **Step 5: Run full labs test suite**

Run:

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs -v
```

Expected: PASS for all `labs` tests.

- [ ] **Step 6: Commit docs and progress**

Run:

```powershell
git add .\labs\fintech-platform\README.md .\README.md .\LEARNING_PROGRESS.md
git commit -m "Document async run retry workflow"
```

## Self-Review Notes

- Spec coverage: The plan covers store transition, API endpoint, confirmation, status constraints, error mapping, access audit, worker-after-retry behavior, docs, and verification.
- Scope: The plan does not add HTML retry buttons, real IAM, auto scheduling, or new async run cloning.
- Type consistency: The planned method is `retry_failed(run_id: str, *, retried_at: datetime) -> PlatformAsyncRun`; the endpoint calls that exact method and returns the existing `_async_run_response()` shape under a `run` key.
- Test commands: The plan starts with focused failing tests, then runs module-level tests, then runs `labs/fintech-platform`, then full `labs`.
