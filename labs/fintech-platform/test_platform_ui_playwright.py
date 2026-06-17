from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
import requests
import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

from platform_api_app import create_app


def test_platform_console_manual_navigation_with_browser(
    platform_base_url: str,
    browser_page: Page,
) -> None:
    browser_page.goto(f"{platform_base_url}/platform/view")

    primary_nav = browser_page.locator("nav.platform-nav")
    expect(primary_nav.get_by_role("link", name="Console", exact=True)).to_be_visible()
    expect(primary_nav.get_by_role("link", name="Manual", exact=True)).to_be_visible()
    expect(browser_page.get_by_text("Console Sections")).to_be_visible()

    primary_nav.get_by_role("link", name="Manual", exact=True).click()

    expect(browser_page.get_by_role("heading", name="Platform User Manual")).to_be_visible()
    expect(browser_page.get_by_role("heading", name="Detailed Event Flow")).to_be_visible()

    browser_page.get_by_role("link", name="CN").click()

    expect(browser_page.get_by_text("平台用户手册")).to_be_visible()
    expect(browser_page.get_by_role("heading", name="详细流程图")).to_be_visible()


def test_platform_console_retry_approval_flow_with_browser(
    platform_base_url: str,
    browser_page: Page,
) -> None:
    run_id = f"run_pw_failed_{uuid4().hex[:8]}"
    _seed_failed_async_run(platform_base_url, run_id=run_id)

    browser_page.goto(f"{platform_base_url}/platform/view")

    failed_async_section = browser_page.locator("#failed-async-runs")
    expect(failed_async_section.get_by_role("link", name=run_id)).to_be_visible()
    retry_form = browser_page.locator(
        f'form[action="/platform/async-payment-runs/{run_id}/retry-form"]'
    )
    retry_form.locator('input[name="actor"]').fill("ops_user_pw")
    retry_form.locator('input[name="reason"]').fill("Retry from Playwright smoke test")
    retry_form.locator('input[name="confirmation"]').fill("retry_failed_async_run")
    retry_form.get_by_role("button", name="Request Approval").click()

    approvals_section = browser_page.locator("#approvals")
    expect(approvals_section.get_by_text("Pending Operation Approvals")).to_be_visible()
    expect(approvals_section.get_by_role("cell", name=run_id)).to_be_visible()

    approve_form = approvals_section.locator('form[action$="/approve-form"]').first
    approve_form.locator('input[name="decided_by"]').fill("ops_manager_pw")
    approve_form.locator('input[name="decision_reason"]').fill(
        "Approved from Playwright smoke test"
    )
    approve_form.locator('input[name="confirmation"]').fill("approve_operation_approval")
    approve_form.get_by_role("button", name="Approve").click()

    async_run = _get_json(f"{platform_base_url}/platform/async-payment-runs/{run_id}")
    assert async_run["status"] == "accepted"


@pytest.fixture
def platform_base_url() -> Iterator[str]:
    data_directory = Path(__file__).parent / ".test-data" / f"playwright-{uuid4()}"
    data_directory.mkdir(parents=True, exist_ok=False)
    app = create_app(
        database_path=data_directory / "platform.db",
        access_audit_database_path=data_directory / "access_audit.db",
        async_database_path=data_directory / "async_runs.db",
        investigation_database_path=data_directory / "investigation_cases.db",
        operation_approval_database_path=data_directory / "operation_approvals.db",
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server_start(server)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        _remove_data_directory(data_directory)


@pytest.fixture
def browser_page() -> Iterator[Page]:
    executable_path = _browser_executable_path()
    if executable_path is None:
        pytest.skip("Playwright browser test requires local Edge or Chrome.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable_path),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            yield page
        finally:
            browser.close()


def _seed_failed_async_run(base_url: str, *, run_id: str) -> None:
    existing_payload = _payment_payload(
        run_id=run_id,
        order_id=f"order_{run_id}_existing",
        amount="50.00",
    )
    _post_json(f"{base_url}/platform/payment-runs", existing_payload)

    async_payload = _payment_payload(
        run_id=run_id,
        order_id=f"order_{run_id}_conflict",
        amount="75.00",
    )
    _post_json(f"{base_url}/platform/async-payment-runs", async_payload)
    for _ in range(3):
        _post_json(
            f"{base_url}/platform/async-worker/process-next",
            None,
            headers={"x-actor-id": "async_worker_pw"},
        )


def _payment_payload(*, run_id: str, order_id: str, amount: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "customer_id": "cust_pw_001",
        "full_name": "Jordan Smith",
        "date_of_birth": "1992-05-20",
        "country": "US",
        "address": "100 Market Street",
        "identification_number": "ID-PW-1001",
        "expected_monthly_volume_cents": 250000,
        "amount": amount,
        "currency": "USD",
        "order_id": order_id,
        "requested_at": "2026-05-19T09:00:00Z",
        "device_id": "device_known",
        "ip_country": "US",
        "beneficiary_id": "beneficiary_001",
        "actor": "api_client_pw",
    }


def _post_json(
    url: str,
    payload: dict[str, object] | None,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def _get_json(url: str) -> dict[str, object]:
    response = requests.get(url, headers={"x-actor-id": "playwright_reader"}, timeout=10)
    response.raise_for_status()
    return response.json()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server_start(server: uvicorn.Server) -> None:
    deadline = time.monotonic() + 10
    while not server.started:
        if not server.should_exit and time.monotonic() < deadline:
            time.sleep(0.05)
            continue
        raise RuntimeError("Timed out waiting for Playwright test server to start.")


def _browser_executable_path() -> Path | None:
    candidates = (
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _remove_data_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
