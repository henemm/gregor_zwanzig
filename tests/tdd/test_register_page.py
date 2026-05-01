"""
TDD RED Tests for F62: SvelteKit Registration Page.

Tests the /register route against the live SvelteKit + Go servers.
SPEC: docs/specs/modules/register_page.md v1.0

Requires:
- SvelteKit frontend on gregor20.henemm.com
- Go API server on localhost:8090
"""
import json
import os
import httpx
import uuid

SVELTE_BASE = os.environ.get("GZ_SVELTE_BASE", "https://gregor20.henemm.com")
GO_BASE = "http://localhost:8090"

# SvelteKit CSRF requires Origin header matching the server
FORM_HEADERS = {"Origin": SVELTE_BASE}


def unique_username():
    """Generate a unique username for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


def post_register(data: dict) -> httpx.Response:
    """POST to /register with correct Origin header for CSRF."""
    return httpx.post(
        f"{SVELTE_BASE}/register",
        data=data,
        headers=FORM_HEADERS,
        follow_redirects=False,
    )


def parse_sveltekit_response(resp: httpx.Response) -> dict:
    """Parse SvelteKit form action response (JSON protocol)."""
    try:
        return json.loads(resp.text)
    except json.JSONDecodeError:
        return {}


class TestRegisterPageExists:
    """Register page must be accessible without authentication."""

    def test_register_route_returns_200(self):
        """
        GIVEN: No authentication
        WHEN: GET /register
        THEN: Returns 200 with HTML form
        """
        resp = httpx.get(f"{SVELTE_BASE}/register", follow_redirects=False)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_register_page_has_form_fields(self):
        """
        GIVEN: Register page loaded
        WHEN: Inspecting HTML
        THEN: Contains username, password, confirmPassword fields
        """
        resp = httpx.get(f"{SVELTE_BASE}/register", follow_redirects=False)
        assert resp.status_code == 200
        html = resp.text
        assert 'name="username"' in html, "Missing username field"
        assert 'name="password"' in html, "Missing password field"
        assert 'name="confirmPassword"' in html, "Missing confirmPassword field"

    def test_register_page_has_submit_button(self):
        """
        GIVEN: Register page loaded
        WHEN: Inspecting HTML
        THEN: Contains a submit button with German text
        """
        resp = httpx.get(f"{SVELTE_BASE}/register", follow_redirects=False)
        assert resp.status_code == 200
        html = resp.text
        assert "Konto erstellen" in html or "Registrieren" in html, \
            "Missing submit button with German text"

    def test_register_page_links_to_login(self):
        """
        GIVEN: Register page loaded
        WHEN: Inspecting HTML
        THEN: Contains link to /login
        """
        resp = httpx.get(f"{SVELTE_BASE}/register", follow_redirects=False)
        assert resp.status_code == 200
        assert '/login' in resp.text, "Missing link to login page"


class TestRegisterFormAction:
    """Registration form submission via POST."""

    def test_successful_registration_redirects_to_login(self):
        """
        GIVEN: Valid username and matching passwords
        WHEN: POST /register
        THEN: SvelteKit returns redirect JSON to /login?registered=1
        """
        username = unique_username()
        resp = post_register({
            "username": username,
            "password": "testpass123",
            "confirmPassword": "testpass123",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = parse_sveltekit_response(resp)
        assert data.get("type") == "redirect", f"Expected redirect, got {data}"
        assert "/login" in data.get("location", ""), "Expected /login in location"
        assert "registered=1" in data.get("location", ""), "Expected ?registered=1"

    def test_password_mismatch_shows_error(self):
        """
        GIVEN: Passwords don't match
        WHEN: POST /register
        THEN: Returns form with German error message
        """
        resp = post_register({
            "username": unique_username(),
            "password": "testpass123",
            "confirmPassword": "different456",
        })
        assert resp.status_code == 200
        assert "stimmen nicht" in resp.text, "Missing password mismatch error"

    def test_duplicate_username_shows_error(self):
        """
        GIVEN: Username already taken
        WHEN: POST /register with same username
        THEN: Returns form with 'bereits vergeben' error
        """
        username = unique_username()
        # First: register via Go API directly
        go_resp = httpx.post(
            f"{GO_BASE}/api/auth/register",
            json={"username": username, "password": "testpass123"},
        )
        assert go_resp.status_code == 201, f"Setup failed: {go_resp.status_code}"

        # Then: try to register same username via SvelteKit form
        resp = post_register({
            "username": username,
            "password": "testpass123",
            "confirmPassword": "testpass123",
        })
        assert resp.status_code == 200
        assert "bereits vergeben" in resp.text, "Missing duplicate username error"

    def test_short_password_shows_error(self):
        """
        GIVEN: Password too short (< 8 chars)
        WHEN: POST /register
        THEN: Returns form with validation error
        """
        resp = post_register({
            "username": unique_username(),
            "password": "short",
            "confirmPassword": "short",
        })
        assert resp.status_code == 200
        assert "8 Zeichen" in resp.text or "erforderlich" in resp.text, \
            "Missing password length error"


class TestLoginPageIntegration:
    """Login page should link to register and show success banner."""

    def test_login_page_has_register_link(self):
        """
        GIVEN: Login page loaded
        WHEN: Inspecting HTML
        THEN: Contains link to /register
        """
        resp = httpx.get(f"{SVELTE_BASE}/login")
        assert resp.status_code == 200
        assert '/register' in resp.text, "Missing register link on login page"

    def test_login_page_shows_success_banner(self):
        """
        GIVEN: Login page with ?registered=1
        WHEN: Page loads
        THEN: Shows success message about account creation
        """
        resp = httpx.get(f"{SVELTE_BASE}/login?registered=1")
        assert resp.status_code == 200
        assert "erfolgreich" in resp.text.lower() or "erstellt" in resp.text.lower(), \
            "Missing success banner on login page"
