"""tests/helpers/staging_admin_session.py — echte Staging-Admin-App-Sitzung.

Issue #2155 S2 (AC-12): /api/debug/ steht hinter Session + RequireAdmin. Live-
Tests (`-m staging`) melden sich deshalb mit einem dedizierten Staging-Admin-
Konto an (Least Privilege, NICHT das GZ_AUTH_USER-Konto) und schicken das
Sitzungscookie mit.

Zugangsdaten: /home/hem/gregor_zwanzig/.claude/staging_admin.env (gitignoriert,
Modus 600, Format KEY=WERT):
    GZ_STAGING_ADMIN_USER=<Login-Kennung des Staging-Admin-Kontos>
    GZ_STAGING_ADMIN_PASS=<Passwort>

Die Datei wird ERST beim Aufruf gelesen, nie beim Import — CI hat sie nicht,
die Collection muss dort trotzdem durchlaufen. Fehlt die Datei oder ein
Schluessel, SCHEITERT der aufrufende Test (kein Skip, sonst waere AC-12
vakuum-gruen).
"""
from __future__ import annotations

from pathlib import Path

# Hauptrepo-Pfad bewusst fest (#1409, Klasse B): Zugangsdaten aus EINER Quelle.
_STAGING_ADMIN_ENV = Path("/home/hem/gregor_zwanzig/.claude/staging_admin.env")
_USER_KEY = "GZ_STAGING_ADMIN_USER"
_PASS_KEY = "GZ_STAGING_ADMIN_PASS"
_SESSION_COOKIE = "gz_session"  # internal/handler/auth.go issueSession

_cached: dict | None = None


def _load_admin_credentials() -> tuple[str, str]:
    if not _STAGING_ADMIN_ENV.exists():
        raise AssertionError(
            f"Staging-Admin-Zugangsdaten fehlen: {_STAGING_ADMIN_ENV} existiert nicht "
            f"(erwartet {_USER_KEY}/{_PASS_KEY}, Issue #2155 S2)"
        )
    env: dict[str, str] = {}
    for line in _STAGING_ADMIN_ENV.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in (_USER_KEY, _PASS_KEY) if not env.get(k)]
    if missing:
        raise AssertionError(
            f"Staging-Admin-Zugangsdaten unvollstaendig in {_STAGING_ADMIN_ENV}: "
            f"fehlt {', '.join(missing)}"
        )
    return env[_USER_KEY], env[_PASS_KEY]


def admin_session_cookies() -> dict:
    """Meldet das Staging-Admin-Konto an (POST /api/auth/login, hinter Nginx-
    Basic-Auth) und liefert {"gz_session": <cookie>} fuer httpx(cookies=...).
    Das Ergebnis wird pro Prozess wiederverwendet (Login-Rate-Limit)."""
    global _cached
    if _cached is not None:
        return dict(_cached)

    import httpx  # noqa: PLC0415

    from tests.helpers.staging_auth import httpx_auth, staging_base_url  # noqa: PLC0415

    user, password = _load_admin_credentials()
    resp = httpx.post(
        f"{staging_base_url()}/api/auth/login",
        json={"username": user, "password": password},
        auth=httpx_auth(),
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise AssertionError(
            f"Staging-Admin-Login fehlgeschlagen: HTTP {resp.status_code} "
            f"Body: {resp.text[:200]}"
        )
    session = resp.cookies.get(_SESSION_COOKIE)
    if not session:
        raise AssertionError(
            f"Staging-Admin-Login lieferte kein {_SESSION_COOKIE}-Cookie"
        )
    _cached = {_SESSION_COOKIE: session}
    return dict(_cached)
