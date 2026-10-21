"""Pi select and confirm dialogs render and answer through the real browser."""

from __future__ import annotations

import threading

import httpx
import pytest
from playwright.sync_api import Page, expect

_APPROVAL_CARD = '[data-testid="approval-card"]'
_FORM = '[data-testid="ask-user-question-form"]'
_SUBMIT = '[data-testid="ask-user-question-submit"]'

_MOCK_ELICITATION_TIMEOUT_MS = 15_000

# The permission-gate shape a Pi extension uses: the tool asks before acting.
_SELECT_TITLE = 'deploy_prod requests approval for build "v2.4.0"'
_ALLOW_ONCE = "Allow once"
_DENY = "Deny"
_CONFIRM_TITLE = "Confirm production deploy"
_CONFIRM_MESSAGE = "Really deploy v2.4.0 to production right now?"


def _post_extension_ui(
    base_url: str,
    session_id: str,
    request: dict,
    holder: dict,
) -> threading.Thread:
    """Post the blocking hook on a thread while the browser answers it."""
    elicitation_id = f"elicit_pi_{request['method']}_{'cd' * 12}"

    def _post() -> None:
        try:
            resp = httpx.post(
                f"{base_url}/v1/sessions/{session_id}/hooks/pi-extension-ui",
                json={"elicitation_id": elicitation_id, "request": request},
                timeout=60.0,
            )
            resp.raise_for_status()
            holder["response"] = resp.json()
        except Exception as exc:
            holder["error"] = exc

    thread = threading.Thread(target=_post, daemon=True)
    thread.start()
    return thread


def _join_hook(thread: threading.Thread, holder: dict) -> dict:
    """Join the hook thread and return its JSON verdict."""
    thread.join(timeout=30)
    if "error" in holder:
        error = holder["error"]
        raise AssertionError(f"pi extension UI hook failed: {error}") from error
    assert "response" in holder, "pi extension UI hook returned no verdict"
    return holder["response"]


@pytest.mark.timeout(90)
@pytest.mark.parametrize("method", ["confirm", "select", "editor"])
def test_pi_extension_dialog_renders_and_returns_the_answer(
    page: Page,
    seeded_session: tuple[str, str],
    method: str,
) -> None:
    base_url, session_id = seeded_session

    holder: dict = {}
    hook_thread = _post_extension_ui(
        base_url,
        session_id,
        {
            "id": "uuid-select",
            "method": method,
            "title": _CONFIRM_TITLE if method == "confirm" else _SELECT_TITLE,
            **({"message": _CONFIRM_MESSAGE} if method == "confirm" else {}),
            **({"options": [_ALLOW_ONCE, "Allow always", _DENY]} if method == "select" else {}),
            **({"prefill": "original note"} if method == "editor" else {}),
        },
        holder,
    )

    page.goto(f"{base_url}/c/{session_id}")

    card = page.locator(f'{_APPROVAL_CARD}[data-state="pending"]').first
    expect(card).to_be_visible(timeout=_MOCK_ELICITATION_TIMEOUT_MS)
    if method == "confirm":
        expect(card.locator(_FORM)).to_have_count(0)
        expect(card.get_by_text(_CONFIRM_TITLE, exact=False)).to_be_visible()
        expect(card.get_by_text(_CONFIRM_MESSAGE, exact=False)).to_be_visible()
        card.get_by_role("button", name="Approve").click()
    else:
        expect(card.get_by_text("Pi needs your input")).to_be_visible()
        form = card.locator(_FORM)
        expect(form.get_by_text(_SELECT_TITLE, exact=True)).to_be_visible()
        if method == "select":
            for label in (_ALLOW_ONCE, "Allow always", _DENY):
                expect(form.get_by_text(label, exact=True)).to_be_visible()
            form.get_by_role("radio", name=_ALLOW_ONCE).check()
            expected = _ALLOW_ONCE
        else:
            expected = "two\nlines"
            form.get_by_role("textbox").fill(expected)
        form.locator(_SUBMIT).click()

    expect(page.locator(f'{_APPROVAL_CARD}[data-state="responded"]').first).to_be_visible(
        timeout=_MOCK_ELICITATION_TIMEOUT_MS
    )

    verdict = _join_hook(hook_thread, holder)
    assert verdict["action"] == "accept", verdict
    if method != "confirm":
        assert expected in (verdict.get("content") or {}).values(), verdict
