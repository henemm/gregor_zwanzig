"""
TDD RED Tests for Issue #74: Design-Optimierungen.

Tests verify the 4 visual changes in the SvelteKit frontend:
1. Sidebar border-r removed
2. Background pure white in light mode
3. Account footer styled with icon + separator
4. "Einstellungen" renamed to "System-Status"

All tests use Playwright against the running frontend (port 3000).
These tests MUST FAIL before implementation (RED phase).
"""
import subprocess
import pytest
from playwright.sync_api import sync_playwright


FRONTEND_URL = "http://127.0.0.1:3000"


@pytest.fixture(scope="module")
def session_cookie():
    """Get a valid session cookie from the Go API."""
    import json
    # Register user (ignore if exists)
    subprocess.run(
        ["curl", "-s", "-X", "POST", "http://127.0.0.1:8090/api/auth/register",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"username": "design_tdd", "password": "test1234"})],
        capture_output=True,
    )
    # Login
    result = subprocess.run(
        ["curl", "-s", "-v", "-X", "POST", "http://127.0.0.1:8090/api/auth/login",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"username": "design_tdd", "password": "test1234"})],
        capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        if "set-cookie" in line.lower() and "gz_session=" in line:
            cookie_val = line.split("gz_session=")[1].split(";")[0]
            return cookie_val
    pytest.skip("Could not obtain session cookie")


@pytest.fixture(scope="module")
def browser_context(session_cookie):
    """Create an authenticated Playwright browser context."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_cookies([{
            "name": "gz_session",
            "value": session_cookie,
            "domain": "127.0.0.1",
            "path": "/",
        }])
        yield ctx
        browser.close()


class TestSidebarBorderRemoved:
    """Change 1: The sidebar should NOT have a right border."""

    def test_nav_has_no_border_r_class(self, browser_context):
        """
        GIVEN: The SvelteKit dashboard is loaded
        WHEN: Inspecting the sidebar nav element
        THEN: The nav should NOT contain 'border-r' in its class list
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        nav = page.locator("nav").first
        classes = nav.get_attribute("class") or ""
        page.close()

        # RED: Currently border-r IS present → this assertion will FAIL
        assert "border-r" not in classes, (
            f"Sidebar nav still has 'border-r' class: {classes}"
        )


class TestWhiteBackground:
    """Change 2: Light mode background should be pure white."""

    def test_background_is_pure_white(self, browser_context):
        """
        GIVEN: The dashboard in light mode
        WHEN: Checking the computed background color of the body
        THEN: It should be pure white (rgb(255, 255, 255))
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        bg_color = page.evaluate(
            "window.getComputedStyle(document.body).backgroundColor"
        )
        page.close()

        # oklch(1 0 0) and rgb(255, 255, 255) are both pure white
        # Chromium may return either format depending on version
        pure_white_values = {"rgb(255, 255, 255)", "oklch(1 0 0)"}
        assert bg_color in pure_white_values, (
            f"Body background is not pure white: {bg_color}"
        )

    def test_main_has_no_muted_bg(self, browser_context):
        """
        GIVEN: The dashboard is loaded
        WHEN: Inspecting the main content element
        THEN: It should NOT have the bg-muted/20 class
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        main_el = page.locator("main").first
        classes = main_el.get_attribute("class") or ""
        page.close()

        # RED: Currently bg-muted/20 IS present
        assert "bg-muted" not in classes, (
            f"Main element still has muted background class: {classes}"
        )


class TestAccountFooter:
    """Change 3: Sidebar footer should have avatar badge with dropdown."""

    def test_footer_has_border_separator(self, browser_context):
        """
        GIVEN: The dashboard with sidebar visible
        WHEN: Looking at the account footer area
        THEN: There should be a border-t separator element wrapping the user info
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        footer_with_border = page.locator("nav div.border-t").first
        is_visible = footer_with_border.is_visible() if footer_with_border.count() > 0 else False
        page.close()

        assert is_visible, "Sidebar footer does not have a border-t separator"

    def test_footer_has_user_icon(self, browser_context):
        """
        GIVEN: The dashboard with sidebar visible
        WHEN: Looking at the account footer
        THEN: There should be an avatar circle with the user's initial
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        # Look for the avatar circle (rounded-full span) inside the footer
        avatar = page.locator("nav div.border-t span.rounded-full").first
        has_avatar = avatar.count() > 0
        page.close()

        assert has_avatar, "Sidebar footer does not contain an avatar badge"


class TestSettingsRenamed:
    """Change 4: Nav item should say 'System-Status' not 'Einstellungen'."""

    def test_sidebar_shows_system_status_in_dropdown(self, browser_context):
        """
        GIVEN: The dashboard with sidebar visible
        WHEN: Opening the user dropdown
        THEN: There should be a 'System-Status' link in the dropdown
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        # Open user dropdown
        page.locator("nav button:has(span.rounded-full)").click()
        page.wait_for_timeout(500)

        system_link = page.locator("nav a", has_text="System-Status")
        has_system = system_link.count() > 0
        page.close()

        assert has_system, "User dropdown should show 'System-Status'"

    def test_nav_does_not_show_einstellungen(self, browser_context):
        """
        GIVEN: The dashboard with sidebar visible
        WHEN: Looking at the navigation items and user dropdown
        THEN: 'Einstellungen' should NOT appear anywhere
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(2000)

        # Open dropdown to check there too
        page.locator("nav button:has(span.rounded-full)").click()
        page.wait_for_timeout(500)

        einstellungen_link = page.locator("nav a", has_text="Einstellungen")
        has_old_label = einstellungen_link.count() > 0
        page.close()

        assert not has_old_label, "Nav/dropdown still shows 'Einstellungen' — should be renamed"

    def test_settings_page_heading(self, browser_context):
        """
        GIVEN: /settings is visited (301 redirect to /account since F76 settings-merge)
        WHEN: Looking at the page heading
        THEN: It should say 'Mein Konto' (settings content merged into account page)
        """
        page = browser_context.new_page()
        page.goto(f"{FRONTEND_URL}/settings")
        page.wait_for_timeout(2000)

        heading = page.locator("main h1").first
        text = heading.text_content() or ""
        page.close()

        assert text.strip() == "Mein Konto", (
            f"Settings redirect destination heading is '{text.strip()}', expected 'Mein Konto'"
        )
