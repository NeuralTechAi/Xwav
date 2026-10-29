"""Built-SPA billing navigation and form contract; all backend calls are scripted."""

from __future__ import annotations

import copy
import json
from importlib.resources import files

from playwright.sync_api import Page, expect

from tests.browser_ui.conftest import BrowserContract
from tests.browser_ui.test_sessions_appearance import appearance_url as appearance_url


def test_billing_navigation_pricing_and_byok(
    page: Page, appearance_url: str, browser_contract: BrowserContract
):
    plans = json.loads(files("omnigent.billing").joinpath("plans.json").read_text())["plans"]
    status = {
        "enabled": True,
        "plan": "pro",
        "mode": "managed",
        "model": "test/model",
        "status": "active",
        "period": "2026-10",
        "usage": {"spent_micro_usd": 2300000, "requests": 4, "tokens": 25000},
        "token_allowance": 10000000,
        "included_micro_usd": 0,
        "included_credits": None,
        "credits_used": None,
        "request_limit": 10000,
        "keys": [],
        "seats": 1,
        "members": [],
        "team": None,
        "has_gateway_token": False,
        "checkout_enabled": True,
        "portal_enabled": False,
        "plans": [{**p, "purchasable": True} for p in plans],
        "providers": [
            {
                "id": "test",
                "label": "Test provider",
                "managed_ready": True,
                "models": [
                    {
                        "id": "auto",
                        "label": "Auto",
                        "protocol": "chat/completions",
                        "free": True,
                        "input_usd_per_million": 0,
                        "output_usd_per_million": 0,
                        "auto_candidates": ["model"],
                    },
                    {
                        "id": "model",
                        "label": "Verified test model",
                        "protocol": "chat/completions",
                        "free": True,
                        "input_usd_per_million": 0.5,
                        "output_usd_per_million": 2,
                    },
                ],
            }
        ],
    }
    browser_contract.json("/v1/billing", lambda _: copy.deepcopy(status))
    saved = []

    def save_key(request):
        saved.append(request.post_data_json)
        status["keys"] = ["test"]
        return {"saved": True}

    browser_contract.json("/v1/billing/keys/test", save_key, method="PUT")
    page.goto(appearance_url + "/settings/billing")
    expect(page.get_by_role("heading", name="Plans & models")).to_be_visible()
    expect(page.get_by_text("Current plan: Pro · active")).to_be_visible()
    page.get_by_role("checkbox", name="Annual billing").check()
    expect(page.get_by_text("$216 billed annually.")).to_be_visible()
    expect(page.get_by_text("$324 per member billed annually.")).to_be_visible()
    expect(page.get_by_role("heading", name="Max · 1,000 credits")).to_be_visible()
    page.get_by_label("Usage mode", exact=True).select_option("free")
    page.get_by_label("Provider and model", exact=True).select_option("test/auto")
    pool = page.get_by_label("Auto model pool", exact=True)
    expect(pool).to_contain_text("Verified test model")
    page.get_by_label("Provider and model", exact=True).select_option("test/model")
    expect(pool).to_have_count(0)
    page.get_by_label("Usage mode", exact=True).select_option("byok")
    page.get_by_label("Key provider", exact=True).select_option("test")
    page.get_by_label("Provider API key", exact=True).fill("fake-disposable-browser-key")
    page.get_by_role("button", name="Save key", exact=True).click()
    expect(page.get_by_text("Provider key saved.")).to_be_visible()
    expect(page.get_by_label("Provider API key", exact=True)).to_have_value("")
    assert saved == [{"key": "fake-disposable-browser-key"}]
    page.screenshot(path="/tmp/xwav-subscriptions-settings.png", full_page=True)
    page.get_by_role("heading", name="Plans & models").scroll_into_view_if_needed()
    page.screenshot(path="/tmp/xwav-subscriptions-plans.png", full_page=True)
    page.get_by_role("link", name="General", exact=True).click()
    page.get_by_role("link", name="Plans & models", exact=True).click()
    expect(page.get_by_role("heading", name="Plans & models")).to_be_visible()
