"""
TDD RED Tests for F61: SvelteKit Account Page.

Tests the /account route against the live SvelteKit + Go servers.
SPEC: docs/specs/modules/account_page.md v1.0

Requires:
- SvelteKit frontend on gregor20.henemm.com
- Go API server on localhost:8090
"""
import os
import re
import pytest
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SVELTE_BASE = os.environ.get("GZ_SVELTE_BASE", "https://gregor20.henemm.com")
GO_BASE = "http://localhost:8090"
FORM_HEADERS = {"Origin": SVELTE_BASE}


@pytest.fixture(scope="module")
def session_cookie():
    """Login and return gz_session cookie for authenticated tests."""
    user = os.environ.get("GZ_AUTH_USER", "default")
    pw = os.environ.get("GZ_AUTH_PASS")
    assert pw, "GZ_AUTH_PASS must be set in environment"
    resp = httpx.post(
        f"{GO_BASE}/api/auth/login",
        json={"username": user, "password": pw},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    sc = resp.headers.get("set-cookie", "")
    m = re.search(r"gz_session=([^;]+)", sc)
    assert m, "No gz_session cookie in login response"
    return m.group(1)


def authed_get(path: str, cookie: str) -> httpx.Response:
    """GET with session cookie via production URL."""
    return httpx.get(
        f"{SVELTE_BASE}{path}",
        cookies={"gz_session": cookie},
        follow_redirects=False,
    )


class TestAccountPageExists:
    """Account page must be accessible when authenticated."""

    def test_account_route_returns_200(self, session_cookie):
        """
        GIVEN: Authenticated user
        WHEN: GET /account
        THEN: Returns 200
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_account_page_shows_username(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Shows the username (read-only)
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        assert "default" in resp.text, "Missing username display"

    def test_account_page_has_editable_fields(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains mail_to, signal_phone, telegram_chat_id input fields
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text
        assert "mail_to" in html or "mailTo" in html, "Missing mail_to field"
        assert "signal_phone" in html or "signalPhone" in html, "Missing signal_phone field"
        assert "telegram_chat_id" in html or "telegramChatId" in html, "Missing telegram_chat_id field"

    def test_account_page_has_save_button(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains a save button with German text
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        assert "Speichern" in resp.text, "Missing save button"

    def test_account_page_shows_member_since(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Shows member-since date
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        # Should show formatted date like "16.04.2026" or "2026"
        assert "2026" in resp.text or "Mitglied" in resp.text, \
            "Missing member-since date"


class TestAccountPageUnauthenticated:
    """Account page must redirect when not authenticated."""

    def test_account_redirects_without_auth(self):
        """
        GIVEN: No authentication
        WHEN: GET /account
        THEN: Redirects to /login
        """
        resp = httpx.get(f"{SVELTE_BASE}/account", follow_redirects=False)
        assert resp.status_code == 302, f"Expected 302, got {resp.status_code}"
        location = resp.headers.get("location", "")
        assert "/login" in location, f"Expected redirect to /login, got {location}"


class TestNavigation:
    """Navigation should include account link."""

    def test_nav_has_account_link(self, session_cookie):
        """
        GIVEN: Authenticated user on any page
        WHEN: Inspecting navigation HTML
        THEN: Contains link to /account
        """
        resp = authed_get("/", session_cookie)
        assert resp.status_code == 200
        assert '/account' in resp.text, "Missing /account link in navigation"

    def test_nav_shows_konto_label(self, session_cookie):
        """
        GIVEN: Authenticated user on any page
        WHEN: Inspecting navigation HTML
        THEN: Shows 'Konto' label for account link
        """
        resp = authed_get("/", session_cookie)
        assert resp.status_code == 200
        assert 'Konto' in resp.text, "Missing 'Konto' label in navigation"
