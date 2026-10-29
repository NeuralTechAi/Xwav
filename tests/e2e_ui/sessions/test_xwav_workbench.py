"""Built Xwav workbench navigation, draft safety, themes and responsive geometry."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests._helpers.polling import poll_until
from tests.e2e_ui.messages.test_native_codex_workspace_cwd import (
    codex_workspace_session as codex_workspace_session,
)


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_workbench_drafts_and_responsive_layout(
    page: Page, live_server: str, output_path: str, width: int, height: int, mode: str
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.emulate_media(color_scheme=mode, reduced_motion="reduce")
    page.goto(live_server)
    landing = page.get_by_test_id("new-chat-landing")
    expect(landing).to_be_visible(timeout=30_000)
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    starters = page.get_by_role("region", name="Task starting points")
    expect(starters).to_be_visible()
    rail = page.get_by_role("navigation", name="Xwav workbench")
    if width >= 768:
        expect(rail).to_be_visible()
        expect(rail.get_by_role("link", name="Workspace home")).to_have_attribute(
            "aria-current", "page"
        )
    else:
        expect(rail).to_be_hidden()

    creates = []
    page.on(
        "request",
        lambda request: (
            creates.append(request.url)
            if request.method == "POST" and request.url.split("?")[0].endswith("/v1/sessions")
            else None
        ),
    )
    starters.get_by_role("button", name="Explore a codebase", exact=False).click()
    draft = page.get_by_test_id("new-chat-landing-input")
    expect(draft).to_have_value(
        "Explore this repository. Explain its architecture, the main entry points, "
        "and how to run its tests. Make no changes yet."
    )
    expect(draft).to_be_focused()
    draft.fill("My editable draft — " + "a long repository name " * 8)
    expect(draft).to_have_value("My editable draft — " + "a long repository name " * 8)
    assert not creates, "A task starter must never create a session"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    composer_box = page.get_by_test_id("new-chat-landing-composer-surface").bounding_box()
    submit_box = page.get_by_test_id("new-chat-landing-submit").bounding_box()
    assert composer_box is not None and submit_box is not None
    assert submit_box["x"] + submit_box["width"] <= composer_box["x"] + composer_box["width"]
    assert submit_box["x"] >= composer_box["x"]
    for button in starters.get_by_role("button").all():
        box = button.bounding_box()
        assert box is not None and box["width"] >= 44 and box["height"] >= 44
    image = Path(output_path) / f"workbench-{width}x{height}-{mode}.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(image), full_page=True)

    page.get_by_test_id("new-chat-landing-attach").click()
    expect(page.get_by_test_id("composer-goal-action")).to_be_enabled()
    page.get_by_test_id("composer-goal-action").click()
    page.get_by_test_id("goal-condition").fill("All checks pass")
    page.get_by_role("button", name="Save goal", exact=True).click()
    goal = page.get_by_role("button", name="Goal: All checks pass", exact=True)
    expect(goal).to_be_visible()
    expect(draft).to_have_value("My editable draft — " + "a long repository name " * 8)
    goal.click()
    expect(page.get_by_test_id("goal-condition")).to_have_value("All checks pass")
    page.get_by_role("button", name="Save goal", exact=True).click()
    page.get_by_test_id("new-chat-landing-attach").click()
    expect(page.get_by_test_id("composer-plan-action")).to_be_enabled()
    page.get_by_test_id("composer-plan-action").click()
    expect(page.get_by_test_id("new-chat-landing-add-menu")).to_be_hidden()
    page.get_by_test_id("new-chat-landing-attach").click()
    expect(page.get_by_test_id("composer-plan-action")).to_have_attribute("data-active", "true")
    page.keyboard.press("Escape")
    page.screenshot(path=str(image.with_stem(image.stem + "-goal-plan")), full_page=True)
    page.get_by_role("button", name="Remove goal", exact=True).click()
    expect(goal).to_have_count(0)
    assert not creates, "Goal and Plan must not submit a task"

    # A read-only host fixture exposes the launch picker without running a CLI.
    page.route(
        "**/v1/hosts",
        lambda route: route.fulfill(
            json={
                "hosts": [
                    {
                        "host_id": "xwav-picker-host",
                        "name": "Picker test host",
                        "owner": "local",
                        "status": "online",
                        "configured_harnesses": {"codex-native": True},
                    }
                ]
            }
        ),
    )
    page.route(
        "**/v1/hosts/xwav-picker-host/harnesses/*/model-options",
        lambda route: route.fulfill(
            json={
                "models": [
                    {
                        "id": "test-default-model",
                        "model": "test-default-model",
                        "displayName": "Test default model",
                        "isDefault": True,
                    }
                ]
            }
        ),
    )
    page.reload()
    page.get_by_test_id("new-chat-landing-agent-select").click()
    page.get_by_test_id("harness2-workflow-link").click()
    expect(page.get_by_test_id("harness2-workflow")).to_be_visible()
    page.get_by_test_id("harness2-workflow").get_by_role(
        "link", name="Harnesses", exact=True
    ).click()
    expect(page).to_have_url(f"{live_server}/settings/harnesses")
    search = page.get_by_test_id("harness-search")
    search.fill("google")
    benchmark = page.get_by_test_id("harness-card-harness2")
    expect(benchmark).to_be_visible()
    benchmark.click()
    expect(page.get_by_test_id("harness2-workflow")).to_be_visible()
    expect(page.get_by_role("heading", name="Google Harness²", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Refresh status", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Refresh status", exact=True).click()
    response = page.request.get(f"{live_server}/v1/harnesses/harness2/status")
    assert response.ok
    assert response.json()["interactive_chat"] is False
    page.get_by_role("button", name="Copy xwav harness2 demo", exact=True).click()
    expect(page.get_by_text("Copied xwav harness2 demo", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(image.with_stem(image.stem + "-harness2")), full_page=True)

    page.goto(f"{live_server}/settings/harnesses")
    default = page.get_by_role("combobox", name="Default chat harness", exact=True)
    default.select_option("codex-native")
    expect(page.get_by_text("Default harness saved.", exact=True)).to_be_visible()
    page.reload()
    expect(default).to_have_value("codex-native")
    configured_tab = page.get_by_role("tab", name="Configured", exact=True).bounding_box()
    assert configured_tab is not None
    assert configured_tab["x"] + configured_tab["width"] <= width
    page.screenshot(path=str(image.with_stem(image.stem + "-default-harness")), full_page=True)
    page.goto(live_server)
    expect(page.get_by_test_id("new-chat-landing-agent-select")).to_have_accessible_name(
        re.compile(r"^Codex")
    )
    page.goto(f"{live_server}/settings/general")
    page.get_by_role("combobox", name="Default chat harness", exact=True).select_option(
        "pi-native"
    )
    page.goto(live_server)
    expect(page.get_by_test_id("new-chat-landing-agent-select")).to_have_accessible_name(
        re.compile(r"^Pi")
    )
    page.goto(f"{live_server}/settings/harnesses")
    page.get_by_role("combobox", name="Default chat harness", exact=True).select_option("")
    page.reload()
    expect(page.get_by_role("combobox", name="Default chat harness", exact=True)).to_have_value("")
    assert not creates, "Changing a default must never create a session"


def test_workbench_rail_theme_and_git_navigation(page: Page, live_server: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.emulate_media(color_scheme="light")
    page.goto(live_server)
    rail = page.get_by_role("navigation", name="Xwav workbench")
    expect(rail).to_be_visible(timeout=30_000)
    rail.get_by_role("link", name="Xwav home", exact=True).focus()
    page.keyboard.press("Tab")
    expect(rail.get_by_role("link", name="Workspace home")).to_be_focused()
    rail.get_by_role("button", name="Switch to dark mode").click()
    expect(page.locator("html")).to_have_class("dark")
    page.reload()
    expect(rail.get_by_role("button", name="Switch to light mode")).to_be_visible()
    rail.get_by_role("button", name="Switch to light mode").click()
    expect(page.locator("html")).not_to_have_class("dark")
    rail.get_by_role("link", name="Git connections").click()
    expect(page).to_have_url(f"{live_server}/settings/git")
    expect(rail.get_by_role("link", name="Git connections")).to_have_attribute(
        "aria-current", "page"
    )
    rail.get_by_role("link", name="Harness settings").click()
    expect(page).to_have_url(f"{live_server}/settings/harnesses")
    rail.get_by_role("link", name="Workspace home").click()
    expect(page.get_by_test_id("new-chat-landing")).to_be_visible()
    rail.get_by_role("button", name="Search workspace").click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_job_notification_scheduler_navigation(page: Page, live_server: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(live_server)
    navigation = page.get_by_test_id("sidebar-primary-nav")
    expect(navigation.get_by_role("link", name=re.compile(r"^New Job"))).to_be_visible(
        timeout=30_000
    )
    navigation.get_by_role("link", name="Notifications", exact=True).click()
    expect(page.get_by_role("heading", name="Notifications", exact=True)).to_be_visible()
    navigation.get_by_role("link", name="Scheduler", exact=True).click()
    expect(page.get_by_role("heading", name="Scheduler", exact=True)).to_be_visible()
    navigation.get_by_role("link", name=re.compile(r"^New Job")).click()
    expect(page.get_by_test_id("new-chat-landing")).to_be_visible()


@pytest.mark.parametrize("width,mode", [(1440, "light"), (390, "dark")])
def test_preview_viewports_and_window_controls(
    page: Page,
    seeded_session: tuple[str, str],
    output_path: str,
    width: int,
    mode: str,
    mock_llm_server_url: str,
) -> None:
    import httpx

    base_url, session_id = seeded_session
    resource = f"{base_url}/v1/sessions/{session_id}/resources/environments/default"

    def app_html(version: str) -> str:
        return f"""<!doctype html><html><body><h1>{version}</h1>
        <p id="width"></p><button onclick="this.textContent='Clicked'">Test interaction</button>
        <script>document.getElementById('width').textContent=innerWidth</script></body></html>"""

    index = resource + "/filesystem/preview-app/src/index.html"
    manifest = resource + "/filesystem/preview-app/package.json"
    previous = httpx.get(index, timeout=20)
    assert previous.status_code == 404, "The test requires an empty fixture workspace"
    httpx.put(
        index, json={"content": app_html("Version one"), "encoding": "utf-8"}, timeout=20
    ).raise_for_status()
    httpx.put(
        manifest,
        json={"content": '{"scripts":{"start":"electron ."}}', "encoding": "utf-8"},
        timeout=20,
    ).raise_for_status()
    try:
        page.set_viewport_size({"width": width, "height": 1000})
        page.emulate_media(color_scheme=mode)
        page.goto(f"{base_url}/c/{session_id}")
        preview_link = page.get_by_test_id("composer-preview-link")
        expect(preview_link).to_be_visible(timeout=30_000)
        composer = page.get_by_role("textbox", name="Message the agent")
        icon_box, input_box = preview_link.bounding_box(), composer.bounding_box()
        assert icon_box is not None and input_box is not None
        assert icon_box["y"] < input_box["y"]
        assert abs(icon_box["x"] - input_box["x"]) < 40
        source_page = page
        source_url = source_page.url
        with source_page.expect_popup() as popup:
            preview_link.click()
        page = popup.value
        page.set_viewport_size({"width": width, "height": 1000})
        page.emulate_media(color_scheme=mode)
        expect(source_page).to_have_url(source_url)
        assert page.evaluate("window.opener === null")
        expect(page).to_have_url(f"{base_url}/preview?session={session_id}")
        expect(page.get_by_role("heading", name="See it in action.")).to_be_visible()
        expect(page.get_by_role("textbox", name="App URL")).to_have_count(0)
        for name, pixels in [("Web", "1440"), ("Android", "412"), ("iOS", "393")]:
            frame = page.frame_locator(f'iframe[title="{name} app preview"]')
            expect(frame.get_by_role("heading")).to_have_text("Version one", timeout=30_000)
            expect(frame.locator("#width")).to_have_text(pixels)
            frame.get_by_role("button", name="Test interaction").click()
            expect(frame.get_by_role("button", name="Clicked")).to_be_visible()
        # Select through a cross-origin iframe at its rendered scale, then send
        # the request through the real job event route and observe the chat reply.
        import json
        import uuid

        from tests.e2e_ui.conftest import configure_mock_llm

        request_nonce = uuid.uuid4().hex
        browser = page.context.browser
        touch = (
            page.context.new_cdp_session(page)
            if width == 390 and browser is not None and browser.browser_type.name == "chromium"
            else None
        )
        for name in ("Android", "iOS", "Web"):
            if name == "Android":
                page.get_by_role("button", name="Rotate Android", exact=True).click()
            request_text = (
                f"Preview request {request_nonce} {name} {width}: make the selected button green"
            )
            reply = f"Received {name} region {width}"
            applied_heading = f"Applied {name} change"
            configure_mock_llm(
                mock_llm_server_url,
                [
                    {
                        "tool_calls": [
                            {
                                "call_id": f"preview_edit_{name}_{width}",
                                "name": "sys_os_write",
                                "arguments": json.dumps(
                                    {
                                        "path": "preview-app/src/index.html",
                                        "content": app_html(applied_heading),
                                    }
                                ),
                            }
                        ]
                    },
                    {"text": reply, "block": True},
                ],
                match=request_text,
                key=f"preview-selection-{session_id}",
                required_tools=["sys_os_write"],
            )
            select_button = page.get_by_role("button", name=f"Select area in {name}", exact=True)
            select_button.scroll_into_view_if_needed()
            before_pick = page.get_by_title(f"{name} app preview", exact=True).bounding_box()
            scroll_before = page.locator(".preview-page").evaluate("node => node.scrollTop")
            select_button.click()
            page.evaluate(
                """() => new Promise(resolve => {
                    requestAnimationFrame(() => requestAnimationFrame(resolve));
                })"""
            )
            after_pick = page.get_by_title(f"{name} app preview", exact=True).bounding_box()
            assert before_pick is not None and after_pick is not None
            assert (
                abs(
                    page.locator(".preview-page").evaluate("node => node.scrollTop")
                    - scroll_before
                )
                <= 1
            ), f"Selecting {name} must not scroll the preview page"
            for axis in ("x", "y", "width", "height"):
                assert abs(before_pick[axis] - after_pick[axis]) <= 1, (
                    f"Selecting {name} moved the viewport's {axis}"
                )
            surface = page.get_by_role("button", name=f"Select area in {name} preview", exact=True)
            surface.scroll_into_view_if_needed()
            bounds = surface.bounding_box()
            assert bounds is not None
            # A point remains one CSS pixel, even in a heavily scaled Web frame.
            point = {
                "x": bounds["x"] + bounds["width"] * 0.3,
                "y": bounds["y"] + bounds["height"] * 0.2,
            }
            if touch is not None:
                touch.send(
                    "Input.dispatchTouchEvent",
                    {"type": "touchStart", "touchPoints": [{**point, "id": 1}]},
                )
                touch.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            else:
                page.mouse.click(point["x"], point["y"])
            form = page.get_by_role("form", name=f"{name} change request")
            expect(form.get_by_role("spinbutton", name=f"{name} selection width")).to_have_value(
                "1"
            )
            expect(form.get_by_role("spinbutton", name=f"{name} selection height")).to_have_value(
                "1"
            )
            form.get_by_role("button", name=f"Clear {name} selection", exact=True).click()
            select_button.click()
            surface = page.get_by_role("button", name=f"Select area in {name} preview", exact=True)
            surface.scroll_into_view_if_needed()
            bounds = surface.bounding_box()
            assert bounds is not None
            start_x = bounds["x"] + bounds["width"] * (0.7 if name == "Web" else 0.1)
            start_y = bounds["y"] + bounds["height"] * (0.3 if name == "Web" else 0.1)
            end_x = bounds["x"] + bounds["width"] * (0.1 if name == "Web" else 0.7)
            end_y = bounds["y"] + bounds["height"] * (0.1 if name == "Web" else 0.3)
            if touch is not None:
                touch.send(
                    "Input.dispatchTouchEvent",
                    {"type": "touchStart", "touchPoints": [{"x": start_x, "y": start_y, "id": 1}]},
                )
                for step in range(1, 6):
                    touch.send(
                        "Input.dispatchTouchEvent",
                        {
                            "type": "touchMove",
                            "touchPoints": [
                                {
                                    "x": start_x + (end_x - start_x) * step / 5,
                                    "y": start_y + (end_y - start_y) * step / 5,
                                    "id": 1,
                                }
                            ],
                        },
                    )
            else:
                page.mouse.move(start_x, start_y)
                page.mouse.down()
                page.mouse.move(end_x, end_y, steps=5)
            # Touch events may arrive faster than the display refresh. The
            # coalesced outline must show the latest point by the next paint.
            page.evaluate("""() => new Promise(resolve => {
                requestAnimationFrame(() => requestAnimationFrame(resolve));
            })""")
            draft = page.get_by_test_id(f"preview-selection-draft-{name.lower()}")
            expect(draft).to_be_visible()
            drawn = draft.bounding_box()
            assert drawn is not None
            for actual, target in zip(
                (drawn["x"], drawn["y"], drawn["width"], drawn["height"]),
                (
                    min(start_x, end_x),
                    min(start_y, end_y),
                    bounds["width"] * 0.6,
                    bounds["height"] * 0.2,
                ),
                strict=True,
            ):
                assert abs(actual - target) <= 1, (
                    "The live highlight must follow the pointer within one display pixel"
                )
            if touch is not None:
                touch.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            else:
                page.mouse.up()
            region = page.get_by_test_id(f"preview-selection-{name.lower()}")
            expect(region).to_be_visible()
            form = page.get_by_role("form", name=f"{name} change request")
            form.get_by_role("textbox").fill(request_text)
            # Source polling must not discard an in-progress selection/editor.
            held_url = page.get_by_title(f"{name} app preview", exact=True).get_attribute("src")
            background_heading = f"Background update during {name} selection"
            httpx.put(
                index,
                json={"content": app_html(background_heading), "encoding": "utf-8"},
                timeout=20,
            ).raise_for_status()
            for other in ("Android", "iOS", "Web"):
                if other != name:
                    expect(
                        page.frame_locator(f'iframe[title="{other} app preview"]').get_by_role(
                            "heading"
                        )
                    ).to_have_text(background_heading, timeout=15_000)
            expect(form.get_by_role("textbox")).to_have_value(request_text)
            expect(page.get_by_title(f"{name} app preview", exact=True)).to_have_attribute(
                "src", held_url
            )
            with page.expect_request(
                lambda request: (
                    request.method == "POST"
                    and request.url.endswith(f"/v1/sessions/{session_id}/events")
                )
            ) as sent:
                form.get_by_role("button", name="Request change", exact=True).click()
            payload = sent.value.post_data_json
            assert payload["data"]["content"][0]["text"].endswith(request_text)
            content = payload["data"]["content"][0]["text"]
            assert f"Device: {name}" in content
            assert (
                "Apply the requested change consistently across Web, Android, and iOS previews."
                in content
            )
            viewport_width, viewport_height = {
                "Android": (915, 412),
                "iOS": (393, 852),
                "Web": (1440, 900),
            }[name]
            assert f"Viewport: {viewport_width} × {viewport_height}" in content
            selected = re.search(r"x=(\d+), y=(\d+), width=(\d+), height=(\d+)", content)
            assert selected is not None
            expected = (
                viewport_width * 0.1,
                viewport_height * 0.1,
                viewport_width * 0.6,
                viewport_height * 0.2,
            )
            assert all(
                abs(int(actual) - target) <= 1
                for actual, target in zip(selected.groups(), expected, strict=True)
            )
            expect(
                page.get_by_role("region", name=f"{name} preview panel").get_by_text(
                    "Request sent to the job for Web, Android, and iOS.", exact=False
                )
            ).to_be_visible(timeout=30_000)
            # Keep the original chat mounted: external preview requests and
            # agent activity must arrive through its live stream, without reload.
            source_page.bring_to_front()
            expect(source_page).to_have_url(f"{base_url}/c/{session_id}")
            user_request = source_page.locator('[data-role="user"]').filter(has_text=request_text)
            expect(user_request).to_be_visible(timeout=30_000)
            expect(user_request).to_have_count(1)
            expect(source_page.get_by_test_id("working-indicator")).to_be_visible(timeout=30_000)
            expect(
                source_page.locator('[data-role="assistant"]').filter(has_text="index.html").last
            ).to_be_visible(timeout=30_000)
            progress_image = (
                Path(output_path) / f"preview-chat-progress-{name.lower()}-{width}.png"
            )
            progress_image.parent.mkdir(parents=True, exist_ok=True)
            source_page.screenshot(path=str(progress_image), full_page=True)
            poll_until(
                lambda: httpx.get(f"{mock_llm_server_url}/gate/pending", timeout=5).json()[
                    "pending"
                ]
            )
            assert httpx.post(f"{mock_llm_server_url}/gate/release", timeout=5).json()["released"]
            expect(source_page.get_by_text(reply, exact=True)).to_be_visible(timeout=60_000)
            expect(user_request).to_have_count(1)
            expect(source_page.get_by_test_id("working-indicator")).to_have_count(0)
            page.bring_to_front()
            for other in ("Android", "iOS", "Web"):
                expect(
                    page.frame_locator(f'iframe[title="{other} app preview"]').get_by_role(
                        "heading"
                    )
                ).to_have_text(applied_heading, timeout=15_000)
            expect(region).to_have_count(0)
            if name == "Android":
                page.get_by_role("button", name="Rotate Android", exact=True).click()

        if touch is not None:
            touch.detach()
        panels = {
            name: page.get_by_role("region", name=f"{name} preview panel").bounding_box()
            for name in ("Android", "iOS", "Web")
        }
        assert all(panels.values())
        if width > 600:
            assert abs(panels["Android"]["y"] - panels["iOS"]["y"]) < 2
            assert panels["Web"]["y"] >= panels["Android"]["y"] + panels["Android"]["height"]
            assert panels["Web"]["width"] > panels["Android"]["width"] * 1.9
        else:
            assert panels["Android"]["y"] < panels["iOS"]["y"] < panels["Web"]["y"]
        page.get_by_role("button", name="Reload Web app", exact=True).click()
        expect(
            page.frame_locator('iframe[title="Web app preview"]').get_by_role(
                "button", name="Test interaction"
            )
        ).to_be_visible()
        page.frame_locator('iframe[title="Android app preview"]').get_by_role(
            "button", name="Test interaction"
        ).click()
        page.get_by_role("button", name="Minimize Android", exact=True).click()
        expect(page.get_by_title("Android app preview", exact=True)).to_be_hidden()
        page.get_by_role("button", name="Restore Android", exact=True).click()
        expect(
            page.frame_locator('iframe[title="Android app preview"]').get_by_role(
                "button", name="Clicked"
            )
        ).to_be_visible()
        page.get_by_role("button", name="Maximize Android", exact=True).click()
        expect(page.get_by_title("Web app preview", exact=True)).to_be_hidden()
        page.get_by_role("button", name="Unmaximize Android", exact=True).click()
        page.get_by_role("button", name="Close iOS", exact=True).click()
        expect(page.get_by_title("iOS app preview", exact=True)).to_have_count(0)
        page.get_by_role("button", name="Reopen iOS preview", exact=True).click()
        source_page.bring_to_front()
        source_page.goto(base_url)
        httpx.put(
            index, json={"content": app_html("Version two"), "encoding": "utf-8"}, timeout=20
        ).raise_for_status()
        for name in ("Web", "Android", "iOS"):
            expect(
                page.frame_locator(f'iframe[title="{name} app preview"]').get_by_role("heading")
            ).to_have_text("Version two", timeout=15_000)
        source_page.close()
        httpx.put(
            index, json={"content": app_html("Parent tab closed"), "encoding": "utf-8"}, timeout=20
        ).raise_for_status()
        for name in ("Web", "Android", "iOS"):
            expect(
                page.frame_locator(f'iframe[title="{name} app preview"]').get_by_role("heading")
            ).to_have_text("Parent tab closed", timeout=15_000)
        page.bring_to_front()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        image = Path(output_path) / f"preview-{width}-{mode}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(image), full_page=True)
        page.close()
    finally:
        httpx.post(f"{mock_llm_server_url}/gate/release", timeout=5)
        cleanup = """python3 - <<'PY_CLEANUP'
import hashlib, json, os, tempfile
from pathlib import Path
import psutil
root = Path.cwd().resolve()
key = hashlib.sha256(str(root).encode()).hexdigest()
record = Path(tempfile.gettempdir()) / f'xwav-preview-{os.getuid()}' / (key + '.json')
if record.exists():
    data = json.loads(record.read_text())
    try:
        process = psutil.Process(data['pid'])
        if abs(process.create_time() - data['created']) < .1:
            process.terminate()
    except psutil.NoSuchProcess:
        pass
    record.unlink()
PY_CLEANUP"""
        httpx.post(resource + "/shell", json={"command": cleanup, "timeout": 10}, timeout=15)
        httpx.delete(index, timeout=15)
        httpx.delete(manifest, timeout=15)


@pytest.mark.parametrize("width,mode", [(1440, "light"), (390, "dark")])
def test_preview_standby_device_frames(
    page: Page, live_server: str, output_path: str, width: int, mode: str
) -> None:
    page.set_viewport_size({"width": width, "height": 1100})
    page.emulate_media(color_scheme=mode)
    page.goto(live_server)
    with page.expect_popup() as popup:
        page.get_by_test_id("composer-preview-link").click()
    preview = popup.value
    try:
        preview.set_viewport_size({"width": width, "height": 1100})
        preview.emulate_media(color_scheme=mode)
        expect(preview.get_by_role("img", name="Android preview standby screen")).to_be_visible()
        expect(preview.get_by_role("img", name="iOS preview standby screen")).to_be_visible()
        expect(preview.locator("iframe")).to_have_count(0)
        assert preview.evaluate("document.documentElement.scrollWidth <= innerWidth")
        image = Path(output_path) / f"preview-standby-{width}-{mode}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        preview.screenshot(path=str(image), full_page=True)
        for name in ("Android", "iOS", "Web"):
            preview.get_by_role("region", name=f"{name} preview panel").screenshot(
                path=str(image.with_stem(image.stem + f"-{name}"))
            )
    finally:
        preview.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_chat_file_revert_review_cancel_restore_and_undo(
    page: Page,
    seeded_session: tuple[str, str],
    mock_llm_server_url: str,
    output_path: str,
    width: int,
) -> None:
    base_url, session_id = seeded_session
    _exercise_chat_file_revert(page, base_url, session_id, mock_llm_server_url, output_path, width)


def test_native_codex_chat_file_revert(
    page: Page, codex_workspace_session, mock_llm_server_url: str, output_path: str
):
    base_url, session_id, workspace = codex_workspace_session
    _exercise_chat_file_revert(
        page, base_url, session_id, mock_llm_server_url, output_path, 1440, workspace
    )


def _exercise_chat_file_revert(
    page: Page,
    base_url: str,
    session_id: str,
    mock_llm_server_url: str,
    output_path: str,
    width: int,
    workspace: Path | None = None,
) -> None:
    import uuid
    from urllib.parse import quote

    import httpx

    from tests.e2e_ui.conftest import configure_mock_llm

    files = f"{base_url}/v1/sessions/{session_id}/resources/environments/default/filesystem"
    if workspace is not None:
        files += "/" + quote(str(workspace), safe="")
    prompt = "Remember this checkpoint " + uuid.uuid4().hex
    reply = "Checkpoint ready " + uuid.uuid4().hex
    configure_mock_llm(mock_llm_server_url, [{"text": reply}] * 3, match=prompt)
    httpx.put(
        files + "/revert-app.txt", json={"content": "before", "encoding": "utf-8"}, timeout=20
    ).raise_for_status()
    try:
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{base_url}/c/{session_id}")
        composer = page.get_by_role("textbox", name="Message the agent")
        expect(composer).to_be_visible(timeout=30_000)
        composer.fill(prompt)
        page.get_by_role("button", name="Send", exact=True).click()
        expect(page.get_by_text(reply, exact=True)).to_be_visible(timeout=60_000)
        httpx.put(
            files + "/revert-app.txt", json={"content": "after", "encoding": "utf-8"}, timeout=20
        ).raise_for_status()
        httpx.put(
            files + "/revert-added.txt",
            json={"content": "new file", "encoding": "utf-8"},
            timeout=20,
        ).raise_for_status()
        bubble = page.locator('[data-role="user"]').filter(has_text=prompt)
        bubble.hover()
        revert = bubble.get_by_role("button", name="Revert changes", exact=True)
        expect(revert).to_be_enabled(timeout=15_000)
        assert revert.evaluate(
            """node => !!(node.compareDocumentPosition(
                node.closest('[data-role=user]').querySelector('[data-testid=copy-message-link]')
            ) & Node.DOCUMENT_POSITION_FOLLOWING)"""
        )
        revert.click()
        dialog = page.get_by_role("dialog")
        expect(dialog.get_by_text("Restore · revert-app.txt", exact=True)).to_be_visible(
            timeout=30_000
        )
        expect(dialog.get_by_text("Remove · revert-added.txt", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="Cancel", exact=True).click()
        assert httpx.get(files + "/revert-app.txt", timeout=15).json()["content"] == "after"
        assistant = page.locator('[data-role="assistant"]').filter(has_text=reply)
        changes = assistant.get_by_test_id("chat-change-summary")
        expect(changes).to_be_visible()
        changes.get_by_role("button", name="Refresh changes", exact=True).click()
        expect(changes.get_by_text("2 files changed", exact=True)).to_be_visible(timeout=30_000)
        changes.get_by_title("View changes to revert-app.txt").click()
        expect(dialog.get_by_label("Code changes")).to_contain_text("-before", timeout=30_000)
        expect(dialog.get_by_label("Code changes")).to_contain_text("+after")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        image = Path(output_path) / f"chat-change-diff-{width}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(image), full_page=True)
        dialog.get_by_role("button", name="Close", exact=True).click()
        assistant.hover()
        assistant.get_by_role("button", name="Revert changes", exact=True).click()
        expect(dialog.get_by_text("Restore · revert-app.txt", exact=True)).to_be_visible(
            timeout=30_000
        )
        image = Path(output_path) / f"chat-revert-review-{width}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(image), full_page=True)
        dialog.get_by_role("button", name="Restore files", exact=True).click()
        expect(
            dialog.get_by_text("Project files restored. Your chat history is unchanged.")
        ).to_be_visible(timeout=30_000)
        assert httpx.get(files + "/revert-app.txt", timeout=15).json()["content"] == "before"
        assert httpx.get(files + "/revert-added.txt", timeout=15).status_code == 404
        expect(bubble).to_be_visible()
        expect(page.get_by_text(reply, exact=True)).to_be_visible()
        dialog.get_by_role("button", name="Undo revert", exact=True).click()
        expect(dialog.get_by_text("Restore · revert-app.txt", exact=True)).to_be_visible(
            timeout=30_000
        )
        dialog.get_by_role("button", name="Restore files", exact=True).click()
        expect(
            dialog.get_by_text("Project files restored. Your chat history is unchanged.")
        ).to_be_visible(timeout=30_000)
        assert httpx.get(files + "/revert-app.txt", timeout=15).json()["content"] == "after"
        assert httpx.get(files + "/revert-added.txt", timeout=15).json()["content"] == "new file"
    finally:
        for name in ["revert-app.txt", "revert-added.txt"]:
            httpx.delete(files + "/" + name, timeout=15)


@pytest.mark.parametrize("width", [1440, 390])
def test_preproduction_dashboard(
    page: Page,
    seeded_session: tuple[str, str],
    output_path: str,
    width: int,
    mock_llm_server_url: str,
) -> None:
    import json

    import httpx

    base_url, session_id = seeded_session
    files = f"{base_url}/v1/sessions/{session_id}/resources/environments/default/filesystem"
    config = {
        "checks": [
            {
                "name": "Passing unit suite",
                "category": "unit",
                "command": ["python3", "-m", "unittest", "test_quality_pass"],
            },
            {
                "name": "Reused regression suite",
                "category": "regression",
                "command": ["python3", "-m", "unittest", "test_quality_pass"],
            },
            {
                "name": "Failing integration suite",
                "category": "integration",
                "command": ["python3", "-m", "unittest", "test_quality_fail"],
            },
        ]
    }

    def write(path: str, content: str) -> None:
        httpx.put(
            files + "/" + path, json={"content": content, "encoding": "utf-8"}, timeout=20
        ).raise_for_status()

    write(
        "test_quality_pass.py",
        "import unittest\nclass Quality(unittest.TestCase):\n"
        " def test_app(self): self.assertEqual(2 + 2, 4)\n",
    )
    write(
        "test_quality_fail.py",
        "import unittest\nfrom quality_app import result\nclass Quality(unittest.TestCase):\n"
        " def test_app(self): self.assertEqual(result(), 4)\n",
    )
    write("quality_app.py", "def result(): return 5\n")
    write(".xwav/preproduction.json", json.dumps(config))
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{base_url}/c/{session_id}")
    icon = page.get_by_test_id("composer-preproduction-link")
    expect(icon).to_be_visible(timeout=30_000)
    expect(icon).to_have_attribute("title", re.compile("download"))
    with page.expect_popup() as popup:
        icon.click()
    dashboard = popup.value
    dashboard.set_viewport_size({"width": width, "height": 1000})
    expect(dashboard).to_have_url(f"{base_url}/preproduction?session={session_id}")
    assert dashboard.evaluate("window.opener === null")
    expect(dashboard.get_by_text("Failures need attention", exact=True)).to_be_visible(
        timeout=40_000
    )
    expect(
        dashboard.get_by_text("Result reused from an identical command in this run.")
    ).to_be_visible()
    expect(dashboard.get_by_role("heading", name="Failing integration suite")).to_be_visible()
    dashboard.get_by_role("combobox", name="Filter test platform").select_option("ios")
    expect(dashboard.get_by_role("heading", name="Native iOS device tests")).to_be_visible()
    dashboard.get_by_role("button", name="Show all checks").click()
    with dashboard.expect_download() as download:
        dashboard.get_by_role("button", name="Download JSON").click()
    report = json.loads(Path(download.value.path()).read_text())
    assert report["state"] == "complete"
    assert report["checks"][0]["status"] == "passed"
    assert report["checks"][2]["status"] == "failed"
    assert any(check["status"] == "blocked" for check in report["checks"])
    dashboard.reload()
    expect(dashboard.get_by_text("Failures need attention", exact=True)).to_be_visible(
        timeout=30_000
    )
    assert dashboard.evaluate("document.documentElement.scrollWidth <= innerWidth")
    image = Path(output_path) / f"preproduction-{width}.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    dashboard.screenshot(path=str(image), full_page=True)
    from tests.e2e_ui.conftest import configure_mock_llm

    reply = "Repaired the app from the dashboard evidence."
    configure_mock_llm(
        mock_llm_server_url,
        [
            {
                "tool_calls": [
                    {
                        "call_id": f"repair_quality_{width}",
                        "name": "sys_os_write",
                        "arguments": json.dumps(
                            {
                                "path": "quality_app.py",
                                "content": "def result(): return 4\n",
                            }
                        ),
                    }
                ]
            },
            {"text": reply},
        ],
        match="Check the Pre-Production Tests dashboard",
        required_tools=["sys_os_write"],
    )
    dashboard.get_by_role("button", name="Fix issues", exact=True).click()
    expect(dashboard.get_by_role("link", name="View repair in job")).to_be_visible(timeout=30000)
    page.bring_to_front()
    expect(page.get_by_text(reply, exact=True)).to_be_visible(timeout=60000)
    requests = httpx.get(f"{mock_llm_server_url}/mock/requests", timeout=10).json()["requests"]
    assert any(
        "Xwav-dashboard-evidence" in json.dumps(request)
        and "Failing integration suite" in json.dumps(request)
        and "AssertionError" in json.dumps(request)
        for request in requests
    )
    assert (
        httpx.get(files + "/quality_app.py", timeout=10).json()["content"]
        == "def result(): return 4\n"
    )
    evidence = httpx.get(
        f"{base_url}/v1/sessions/{session_id}/diagnostics?kind=preproduction", timeout=20
    ).json()["reports"][0]
    assert evidence["source_changed"] is True
    # Verify through the exact dashboard coordinator, not a substitute npm test.
    import shlex

    shell = f"{base_url}/v1/sessions/{session_id}/resources/environments/default/shell"
    rerun = httpx.post(
        shell, json={"command": shlex.join(evidence["rerun_command"]), "timeout": 10}, timeout=20
    )
    rerun.raise_for_status()
    dashboard.bring_to_front()
    dashboard.reload()
    expect(dashboard.get_by_text("Coverage incomplete", exact=True)).to_be_visible(timeout=40000)
    refreshed = httpx.get(f"{base_url}/v1/sessions/{session_id}/preproduction", timeout=20).json()
    assert refreshed["id"] != report["id"]
    assert refreshed["checks"][2]["status"] == "passed"
    config["checks"] = [
        {
            "name": "Long smoke suite",
            "category": "smoke",
            "command": ["python3", "-c", "import time; time.sleep(60)"],
        }
    ]
    write(".xwav/preproduction.json", json.dumps(config))
    dashboard.get_by_role("button", name="Run again").click()
    expect(dashboard.get_by_text("Tests running", exact=True)).to_be_visible(timeout=20_000)
    dashboard.get_by_role("button", name="Stop tests").click()
    expect(dashboard.get_by_text("Test run cancelled", exact=True)).to_be_visible(timeout=20_000)
    dashboard.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_loadtesting_dashboard(
    page: Page, seeded_session: tuple[str, str], output_path: str, width: int
) -> None:
    import json

    import httpx

    base_url, session_id = seeded_session
    files = f"{base_url}/v1/sessions/{session_id}/resources/environments/default/filesystem"
    config = {"durations": dict.fromkeys(("load", "stress", "spike", "soak"), 1)}
    for path, text in {
        "index.html": "<!doctype html><title>Load fixture</title><h1>App ready</h1>",
        ".xwav/loadtesting.json": json.dumps(config),
    }.items():
        httpx.put(
            files + "/" + path, json={"content": text, "encoding": "utf-8"}, timeout=20
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{base_url}/c/{session_id}")
    icon = page.get_by_test_id("composer-loadtesting-link")
    expect(icon).to_be_visible(timeout=30000)
    expect(icon).to_have_attribute("title", re.compile("endurance"))
    with page.expect_popup() as popup:
        icon.click()
    dashboard = popup.value
    try:
        dashboard.set_viewport_size({"width": width, "height": 1000})
        expect(dashboard).to_have_url(f"{base_url}/loadtesting?session={session_id}")
        assert dashboard.evaluate("window.opener === null")
        expect(dashboard.get_by_role("heading", name="Configured profiles passed")).to_be_visible(
            timeout=40000
        )
        for profile in ("Load", "Stress", "Spike", "Soak"):
            expect(
                dashboard.get_by_role("heading", name=f"{profile} test", exact=True)
            ).to_be_visible()
        for format in ("JSON", "HTML", "CSV"):
            with dashboard.expect_download() as download:
                dashboard.get_by_role("button", name=f"Download {format}").click()
            content = Path(download.value.path()).read_text()
            if format == "JSON":
                report = json.loads(content)
                assert all(row["status"] == "passed" for row in report["checks"])
                assert all(row["metrics"]["requests"] > 0 for row in report["checks"])
                report_id = report["id"]
            else:
                assert "Load test" in content
        dashboard.reload()
        expect(dashboard.get_by_text(report_id[:12], exact=False)).to_be_visible(timeout=30000)
        assert dashboard.evaluate("document.documentElement.scrollWidth <= innerWidth")
        evidence = Path(output_path) / f"loadtesting-{width}.png"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        dashboard.screenshot(path=str(evidence), full_page=True)
        config["durations"] = dict.fromkeys(("load", "stress", "spike", "soak"), 10)
        httpx.put(
            files + "/.xwav/loadtesting.json",
            json={"content": json.dumps(config), "encoding": "utf-8"},
            timeout=20,
        ).raise_for_status()
        request_count = dashboard.get_by_role("spinbutton", name="Total requests")
        for total in (8, 17):
            request_count.fill(str(total))
            dashboard.get_by_role("button", name="Run again").click()
            expect(dashboard.get_by_role("button", name="Stop run")).to_be_visible(timeout=10000)
            expect(
                dashboard.get_by_role("heading", name="Configured profiles passed")
            ).to_be_visible(timeout=30000)
            with dashboard.expect_download() as exact_download:
                dashboard.get_by_role("button", name="Download JSON").click()
            exact = json.loads(Path(exact_download.value.path()).read_text())
            assert (
                sum(row.get("metrics", {}).get("requests", 0) for row in exact["checks"]) == total
            )
        request_count.fill("100000000")
        dashboard.get_by_role("button", name="Run again").click()
        expect(dashboard.get_by_role("button", name="Stop run")).to_be_visible(timeout=10000)
        expect(request_count).to_be_disabled()
        active = httpx.get(f"{base_url}/v1/sessions/{session_id}/loadtesting", timeout=20).json()
        assert active["checks"][0]["config"]["max_requests"] == 100_000_000
        dashboard.get_by_role("button", name="Stop run").click()
        expect(dashboard.get_by_role("heading", name="Run stopped")).to_be_visible(timeout=15000)
    finally:
        dashboard.close()


@pytest.mark.parametrize("width", [1280, 390], ids=["desktop", "mobile"])
def test_job_workspace_zip_download(
    page: Page, codex_workspace_session: tuple[str, str, Path], width: int
) -> None:
    import zipfile

    base_url, session_id, workspace = codex_workspace_session
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "src" / "app.txt").write_text("uncommitted current project\n")
    (workspace / "asset.bin").write_bytes(bytes(range(256)))
    (workspace / "node_modules").mkdir(exist_ok=True)
    (workspace / "node_modules" / "dependency.txt").write_text("not exported")
    (workspace / ".xwav/releases/adapters").mkdir(parents=True, exist_ok=True)
    (workspace / ".xwav/releases/adapters/cache.txt").write_text("generated build cache")
    (workspace / ".xwav/release.json").write_text('{"app_version":"2.3.4"}')
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{base_url}/c/{session_id}")
    page.get_by_test_id("header-conversation-actions").click()
    item = page.get_by_test_id("download-job-workspace")
    expect(item).to_be_enabled()
    page.screenshot(path=f"/tmp/xwav-download-menu-{width}.png", full_page=True)
    with page.expect_download(timeout=60_000) as captured:
        item.click()
    downloaded = captured.value
    assert downloaded.suggested_filename.endswith(".zip")
    with zipfile.ZipFile(downloaded.path()) as archive:
        assert "src/app.txt" in archive.namelist(), archive.namelist()
        assert archive.read("src/app.txt") == b"uncommitted current project\n"
        assert archive.read("asset.bin") == bytes(range(256))
        assert not any(
            name.startswith(("node_modules/", ".git/", ".xwav/releases/"))
            for name in archive.namelist()
        )
        assert b"2.3.4" in archive.read(".xwav/release.json")
    assert (workspace / "src" / "app.txt").read_text() == "uncommitted current project\n"

    # The project-folder entry resolves its latest job from the server, then
    # downloads the same current workspace through the real browser path.
    project_name = f"Download-{session_id[:8]}"
    created = page.request.post(f"{base_url}/v1/projects", data={"name": project_name})
    assert created.ok
    project_id = created.json()["id"]
    try:
        updated = page.request.patch(
            f"{base_url}/v1/sessions/{session_id}", data={"project_id": project_id}
        )
        assert updated.ok
        page.reload()
        open_sidebar = page.get_by_role("button", name="Open sidebar", exact=True)
        if open_sidebar.is_visible():
            open_sidebar.click()
        for menu_kind in ["dropdown", "context"] if width >= 768 else ["dropdown"]:
            if menu_kind == "dropdown":
                page.get_by_role("button", name=f"Project actions for {project_name}").click()
            else:
                page.get_by_role("button", name=project_name, exact=True).click(button="right")
            with page.expect_download(timeout=60_000) as project_download:
                page.get_by_test_id("download-project").click()
            with zipfile.ZipFile(project_download.value.path()) as archive:
                assert archive.read("src/app.txt") == b"uncommitted current project\n"
    finally:
        page.request.patch(f"{base_url}/v1/sessions/{session_id}", data={"project_id": None})
        page.request.delete(f"{base_url}/v1/projects/{project_id}")


@pytest.mark.parametrize("width", [1280, 390], ids=["desktop", "mobile"])
def test_release_pages_build_and_download_in_job_runtime(
    page: Page, codex_workspace_session: tuple[str, str, Path], width: int
) -> None:
    """Local fixture workflows exercise real jobs; no vendor/store publishing."""
    import json
    import sys
    import zipfile

    base_url, session_id, workspace = codex_workspace_session
    (workspace / "index.html").write_text("<h1>Fixture frontend</h1>")
    settings = workspace / ".xwav"
    settings.mkdir(exist_ok=True)
    (settings / "release.json").write_text(
        json.dumps(
            {
                "targets": {
                    "web": {
                        "build": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; "
                            "Path('dist').mkdir(exist_ok=True); "
                            "Path('dist/index.html').write_text('<h1>Built frontend</h1>')",
                        ],
                        "deploy": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; "
                            "Path('dist/deployed.txt').write_text('local fixture workflow'); "
                            "print('Local deployment workflow completed')",
                        ],
                    },
                    "android": {
                        "build": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; "
                            "import zipfile; "
                            "Path('build').mkdir(exist_ok=True); "
                            "z=zipfile.ZipFile('build/fixture.apk','w'); "
                            "z.writestr('AndroidManifest.xml',b'\\x03\\x00\\x08\\x00'); "
                            "z.writestr('classes.dex',b'dex\\n'); "
                            "z.close()",
                        ],
                        "artifacts": ["build/*.apk"],
                    },
                }
            }
        )
    )
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{base_url}/c/{session_id}")
    links = page.locator('[data-testid^="composer-"][data-testid$="-link"]')
    expect(page.get_by_test_id("composer-deployments-link")).to_be_visible(timeout=30000)
    names = links.evaluate_all("nodes => nodes.map(node => node.getAttribute('data-testid'))")
    assert names.index("composer-deployments-link") == names.index("composer-loadtesting-link") + 1
    assert (
        names.index("composer-installables-link") == names.index("composer-deployments-link") + 1
    )
    with page.expect_popup() as opened:
        page.get_by_test_id("composer-deployments-link").click()
    deploy = opened.value
    deploy.set_viewport_size({"width": width, "height": 1000})
    try:
        expect(deploy.get_by_role("heading", name="Deploy your app", exact=True)).to_be_visible()
        expect(deploy.get_by_role("button", name="Build & deploy")).to_be_disabled()
        assert not (workspace / "dist/deployed.txt").exists()
        for provider in ("Vercel", "Netlify", "Cloudflare Pages", "Railway"):
            expect(deploy.get_by_role("option", name=provider, exact=True)).to_have_count(1)
        import subprocess

        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        deploy.get_by_label("Build computer").select_option("github")
        expect(deploy.get_by_role("region", name="Cloud setup")).to_be_visible()
        deploy.get_by_label("GitHub repository").fill("owner/xwav-verification-only")
        deploy.get_by_role("button", name="Prepare cloud workflow", exact=True).click()
        expect(deploy.get_by_text("Cloud workflow prepared.", exact=False)).to_be_visible(
            timeout=30000
        )
        assert (workspace / ".github/workflows/xwav-release.yml").is_file()
        assert (workspace / ".xwav/cloud/entry.py").is_file()
        assert not (workspace / ".xwav/cloud-export").exists()
        deploy.get_by_label("Publishing destination").select_option("production")
        expect(
            deploy.get_by_role("checkbox", name="Publish this committed revision", exact=False)
        ).to_be_visible()
        expect(deploy.get_by_role("button", name="Build & deploy", exact=True)).to_be_disabled()
        assert deploy.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        deploy.screenshot(path=f"/tmp/xwav-cloud-setup-{width}.png", full_page=True)
        deploy.get_by_label("Build computer").select_option("local")
        deploy.get_by_label("Web deployment destination").select_option("cloudflare")
        deploy.get_by_label("Destination project").fill("xwav-verification-only")
        expect(deploy.get_by_label("Destination project")).to_have_value("xwav-verification-only")
        expect(deploy.get_by_role("button", name="Build & deploy")).to_be_enabled(timeout=30000)
        deploy.screenshot(path=f"/tmp/xwav-reviewed-destination-{width}.png", full_page=True)
        deploy.get_by_label("Web deployment destination").select_option("project")
        expect(deploy.get_by_role("button", name="Build & deploy")).to_be_enabled(timeout=30000)
        deploy.get_by_role("button", name="Build & deploy").click()
        expect(deploy.get_by_role("heading", name="Deployed", exact=True)).to_be_visible(
            timeout=30000
        )
        assert (workspace / "dist/deployed.txt").read_text() == "local fixture workflow"
        deploy.screenshot(path=f"/tmp/xwav-deployment-{width}.png", full_page=True)
        # Mobile buttons must open setup instead of becoming dead controls.
        for target, label in [("android", "Android"), ("ios", "iOS")]:
            deploy.get_by_role("button", name=label, exact=True).click()
            start_mobile = deploy.get_by_role("button", name="Build & deploy", exact=True)
            expect(start_mobile).to_be_enabled(timeout=30000)
            start_mobile.click()
            setup = deploy.get_by_role("dialog", name=f"Set up {label} deployment")
            expect(setup).to_be_visible()
            expect(setup.get_by_role("status")).not_to_contain_text("Checking", timeout=30000)
            expect(setup.get_by_role("button", name="Continue deployment")).to_be_disabled()
            expect(setup.get_by_role("button", name="Use GitHub Actions")).to_be_visible()
            assert deploy.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            deploy.screenshot(
                path=f"/tmp/xwav-mobile-{target}-deployment-setup-{width}.png", full_page=True
            )
            setup.get_by_role("button", name="Close setup").click()
            configuration = json.loads((settings / "release.json").read_text())
            if target == "ios":
                configuration["targets"][target] = {
                    "build": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; import zipfile; "
                        "Path('build').mkdir(exist_ok=True); "
                        "z=zipfile.ZipFile('build/fixture.ipa','w'); "
                        "z.writestr('Payload/Fixture.app/Info.plist',b'fixture'); "
                        "z.writestr('Payload/Fixture.app/_CodeSignature/CodeResources',"
                        "b'fixture'); "
                        "z.close()",
                    ],
                    "artifacts": ["build/*.ipa"],
                }
            configuration["targets"][target]["deploy"] = [
                sys.executable,
                "-c",
                "from pathlib import Path; "
                f"Path('.xwav/releases/{target}-submitted.txt')"
                ".write_text('local fixture submission')",
            ]
            (settings / "release.json").write_text(json.dumps(configuration))
            deploy.get_by_role("button", name="Check readiness", exact=True).click()
            expect(deploy.get_by_role("status").filter(has_text="Ready to start")).to_be_visible(
                timeout=30000
            )
            start_mobile.click()
            extension = "apk" if target == "android" else "ipa"
            expect(deploy.get_by_text(f"fixture.{extension}", exact=True)).to_be_visible(
                timeout=30000
            )
            assert (
                settings / f"releases/{target}-submitted.txt"
            ).read_text() == "local fixture submission"
    finally:
        deploy.close()
    with page.expect_popup() as opened:
        page.get_by_test_id("composer-installables-link").click()
    installs = opened.value
    installs.set_viewport_size({"width": width, "height": 1000})
    try:
        expect(
            installs.get_by_role("heading", name="Installable downloads", exact=True)
        ).to_be_visible()
        for target in ("Windows", "Android", "iOS"):
            expect(installs.get_by_role("button", name=target, exact=True)).to_be_visible()
        installs.get_by_label("Build computer").select_option("github")
        expect(installs.get_by_role("region", name="Cloud setup")).to_be_visible()
        expect(installs.get_by_label("Publishing destination")).to_have_count(0)
        installs.get_by_role("button", name="Check connection & signing setup").click()
        expect(
            installs.get_by_role("link", name="Open GitHub environments & secrets", exact=False)
        ).to_have_attribute(
            "href", "https://github.com/owner/xwav-verification-only/settings/environments"
        )
        expect(installs.get_by_role("button", name="Build installer")).to_be_disabled()
        installs.get_by_label("Build computer").select_option("local")
        # A Mac/signing gap is actionable on the download page as well.
        ios_configuration = json.loads((settings / "release.json").read_text())
        without_ios = json.loads(json.dumps(ios_configuration))
        del without_ios["targets"]["ios"]
        (settings / "release.json").write_text(json.dumps(without_ios))
        installs.get_by_role("button", name="iOS", exact=True).click()
        expect(installs.get_by_role("button", name="Build installer")).to_be_enabled()
        installs.get_by_role("button", name="Build installer").click()
        setup = installs.get_by_role("dialog", name="Set up iOS build")
        expect(setup).to_be_visible()
        expect(setup.get_by_role("status")).not_to_contain_text("Checking", timeout=30000)
        expect(setup.get_by_role("button", name="Continue build")).to_be_disabled()
        setup.get_by_role("button", name="Close setup").click()
        (settings / "release.json").write_text(json.dumps(ios_configuration))
        installs.get_by_role("button", name="Check readiness", exact=True).click()
        expect(installs.get_by_role("status").filter(has_text="Ready to start")).to_be_visible(
            timeout=30000
        )
        installs.get_by_role("button", name="Build installer").click()
        expect(installs.get_by_text("fixture.ipa", exact=True)).to_be_visible(timeout=30000)
        with installs.expect_download() as captured_ios:
            installs.get_by_role("button", name="Download package", exact=True).click()
        assert captured_ios.value.suggested_filename == "fixture.ipa"
        with zipfile.ZipFile(captured_ios.value.path()) as archive:
            assert "Payload/Fixture.app/Info.plist" in archive.namelist()
        release_config = settings / "release.json"
        original = release_config.read_text()
        automatic = json.loads(original)
        del automatic["targets"]["android"]
        release_config.write_text(json.dumps(automatic))
        installs.get_by_role("button", name="Android", exact=True).click()
        acceptance = installs.get_by_role("checkbox", name="I accept the")
        expect(acceptance).to_be_visible(timeout=30000)
        expect(installs.get_by_role("button", name="Build installer")).to_be_enabled()
        installs.get_by_role("button", name="Build installer").click()
        setup = installs.get_by_role("dialog", name="Set up Android build")
        expect(setup).to_be_visible()
        expect(setup.get_by_role("button", name="Continue build")).to_be_disabled()
        assert not (workspace / "build/android-app.apk").exists()
        setup.get_by_role("button", name="Close setup").click()
        acceptance.check()
        expect(installs.get_by_role("button", name="Build installer")).to_be_enabled()
        installs.screenshot(path=f"/tmp/xwav-android-setup-{width}.png", full_page=True)
        release_config.write_text(original)
        installs.get_by_role("button", name="Check readiness").click()
        expect(acceptance).to_have_count(0, timeout=30000)
        expect(installs.get_by_role("button", name="Build installer")).to_be_enabled(timeout=30000)
        installs.get_by_role("button", name="Build installer").click()
        download = installs.get_by_role("button", name="Download package", exact=True)
        expect(download).to_be_enabled(timeout=30000)
        with installs.expect_download() as captured:
            download.click()
        assert captured.value.suggested_filename == "fixture.apk"
        with zipfile.ZipFile(captured.value.path()) as archive:
            assert "AndroidManifest.xml" in archive.namelist()
            assert "classes.dex" in archive.namelist()
        installs.screenshot(path=f"/tmp/xwav-installables-{width}.png", full_page=True)
        installs.get_by_role("button", name="Web", exact=True).click()
        expect(installs.get_by_role("button", name="Build web package")).to_be_enabled(
            timeout=30000
        )
        installs.get_by_role("button", name="Build web package").click()
        expect(installs.get_by_role("heading", name="Build ready", exact=True)).to_be_visible(
            timeout=30000
        )
        download = installs.get_by_role("button", name="Download package", exact=True)
        with installs.expect_download() as captured_web:
            download.click()
        assert captured_web.value.suggested_filename == "web.zip"
        with zipfile.ZipFile(captured_web.value.path()) as archive:
            assert b"Built frontend" in archive.read("index.html")
        installs.screenshot(path=f"/tmp/xwav-reviewed-web-package-{width}.png", full_page=True)
        package = next(workspace.glob(".xwav/releases/artifacts/*/web.zip"))
        package.write_bytes(b"tampered package")
        with installs.expect_response(
            lambda response: response.url.endswith("/web.zip")
        ) as rejected:
            download.click()
        assert rejected.value.status == 409
        expect(installs.get_by_role("alert")).to_contain_text("Package changed")
    finally:
        installs.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_penetration_report_dashboard(
    page: Page, seeded_session: tuple[str, str], output_path: str, width: int
):
    import json

    import httpx

    base_url, session_id = seeded_session
    files = f"{base_url}/v1/sessions/{session_id}/resources/environments/default/filesystem"
    run = "strix_runs/xwav-dashboard-verification"

    def write(name, data):
        httpx.put(
            files + "/" + run + "/" + name,
            json={"content": json.dumps(data), "encoding": "utf-8"},
            timeout=20,
        ).raise_for_status()

    write("run.json", {"status": "running", "scan_mode": "quick"})
    write(
        "vulnerabilities.json",
        [
            {
                "id": "fixture-1",
                "title": "Fixture ownership finding",
                "severity": "high",
                "evidence": "Fixture evidence only",
                "remediation_steps": "Apply fixture ownership check",
            }
        ],
    )
    # This fixture journey verifies browser actions and real report reading.
    # The worker lifecycle itself is exercised in test_strix_jobs.py.
    actions = []

    def acknowledge_fixture_scan(route):
        if route.request.method == "POST":
            actions.append(route.request.post_data_json["action"])
            response = route.fetch(method="GET", post_data=None)
            route.fulfill(response=response)
        else:
            route.continue_()

    page.context.route(f"**/v1/sessions/{session_id}/penetration", acknowledge_fixture_scan)
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{base_url}/c/{session_id}")
    icon = page.get_by_test_id("composer-penetration-link")
    expect(icon).to_be_visible(timeout=30000)
    expect(icon).to_have_attribute("title", re.compile("Strix"))
    assert icon.evaluate(
        "node => node.previousElementSibling.dataset.testid === 'composer-loadtesting-link'"
    )
    with page.expect_popup() as popup:
        icon.click()
    dashboard = popup.value
    try:
        dashboard.set_viewport_size({"width": width, "height": 1000})
        expect(dashboard).to_have_url(f"{base_url}/penetration?session={session_id}")
        assert dashboard.evaluate("window.opener === null")
        expect(dashboard.get_by_text("Scan in progress", exact=True)).to_be_visible(timeout=30000)
        dashboard.locator("summary").filter(has_text="Fixture ownership finding").click()
        expect(dashboard.get_by_text("Fixture evidence only", exact=True)).to_be_visible()
        assert dashboard.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        write(
            "run.json",
            {
                "status": "completed",
                "scan_results": {"executive_summary": "Fixture scan finished"},
            },
        )
        expect(dashboard.get_by_text("Scan completed", exact=True)).to_be_visible(timeout=20000)
        assert actions == ["start"]
        dashboard.get_by_role("button", name="Run again", exact=True).click()
        expect(dashboard.get_by_role("button", name="Run again", exact=True)).to_be_enabled()
        assert actions == ["start", "start"]
        with dashboard.expect_download() as download:
            dashboard.get_by_role("button", name="Download JSON", exact=True).click()
        exported = json.loads(Path(download.value.path()).read_text())
        assert exported["findings"][0]["evidence"] == "Fixture evidence only"
        image = Path(output_path) / f"strix-dashboard-{width}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        dashboard.screenshot(path=str(image), full_page=True)
    finally:
        dashboard.close()
        httpx.delete(files + "/" + run, timeout=20)
