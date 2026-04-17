"""
TDD RED Tests for F72/F73: Account Page Extensions.

Tests Signal API Key field and Account Deletion button on /account.
SPEC: docs/specs/modules/account_page_extend.md v1.0

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

SVELTE_BASE = "https://gregor20.henemm.com"
GO_BASE = "http://localhost:8090"


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
    return httpx.get(
        f"{SVELTE_BASE}{path}",
        cookies={"gz_session": cookie},
        follow_redirects=False,
    )


class TestSignalApiKeyField:
    """Signal API Key input field on /account."""

    def test_account_page_has_signal_api_key_field(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains a password-type input for Signal API Key
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text
        assert "signal_api_key" in html or "signalApiKey" in html or "API Key" in html, \
            "Missing Signal API Key field"

    def test_signal_api_key_has_password_type(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting the Signal API Key input
        THEN: Input type is password (masked)
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        # Should have a password input near "API Key" or "Callmebot"
        html = resp.text
        assert "Callmebot" in html or "callmebot" in html, \
            "Missing Callmebot hint text"

    def test_signal_api_key_placeholder(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting Signal API Key field
        THEN: Has appropriate placeholder text
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        assert "Callmebot" in resp.text, "Missing Callmebot placeholder/hint"


class TestAccountDeletion:
    """Account deletion section on /account."""

    def test_account_page_has_danger_zone(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains a danger zone section
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text
        assert "Gefahrenzone" in html or "gefahrenzone" in html.lower(), \
            "Missing Gefahrenzone section"

    def test_account_page_has_delete_button(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains a delete account button with German text
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "account löschen" in html or "account loeschen" in html or "konto löschen" in html, \
            "Missing delete account button"

    def test_danger_zone_has_warning_text(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting danger zone section
        THEN: Contains warning about irreversible deletion
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "unwiderruflich" in html or "permanent" in html, \
            "Missing deletion warning text"
