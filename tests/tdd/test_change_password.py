"""
TDD RED Tests for F71: Password Change on Account Page.

Tests the password change UI section on /account.
SPEC: docs/specs/modules/change_password.md v1.0
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


@pytest.fixture(scope="module")
def session_cookie():
    user = os.environ.get("GZ_AUTH_USER", "default")
    pw = os.environ.get("GZ_AUTH_PASS")
    assert pw, "GZ_AUTH_PASS must be set"
    resp = httpx.post(f"{GO_BASE}/api/auth/login", json={"username": user, "password": pw})
    assert resp.status_code == 200
    sc = resp.headers.get("set-cookie", "")
    m = re.search(r"gz_session=([^;]+)", sc)
    assert m
    return m.group(1)


def authed_get(path: str, cookie: str) -> httpx.Response:
    return httpx.get(f"{SVELTE_BASE}{path}", cookies={"gz_session": cookie}, follow_redirects=False)


class TestPasswordChangeUI:
    """Password change section on /account page."""

    def test_account_has_password_change_section(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains 'Passwort ändern' section
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "passwort ändern" in html or "passwort aendern" in html, \
            "Missing password change section"

    def test_account_has_old_password_field(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains old password input field
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "aktuelles passwort" in html or "altes passwort" in html, \
            "Missing old password field label"

    def test_account_has_new_password_fields(self, session_cookie):
        """
        GIVEN: Account page loaded
        WHEN: Inspecting HTML
        THEN: Contains new password and confirm fields
        """
        resp = authed_get("/account", session_cookie)
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "neues passwort" in html, "Missing new password field"
        assert "bestätigen" in html or "bestaetigen" in html, \
            "Missing confirm password field"


class TestPasswordChangeEndpoint:
    """Go endpoint PUT /api/auth/password."""

    def test_change_password_endpoint_exists(self, session_cookie):
        """
        GIVEN: Authenticated user
        WHEN: PUT /api/auth/password with valid data
        THEN: Returns 200 (not 404)
        """
        resp = httpx.put(
            f"{GO_BASE}/api/auth/password",
            json={"old_password": "wrong", "new_password": "testtest123"},
            cookies={"gz_session": session_cookie},
        )
        # 403 (wrong password) or 200 is acceptable — NOT 404
        assert resp.status_code != 404, f"Endpoint not found: {resp.status_code}"
