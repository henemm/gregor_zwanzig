"""tests/helpers/staging_auth.py — zentraler Staging-Basic-Auth-Helper.

Liefert Nginx-Basic-Auth-Credentials für Staging aus .claude/validator.env,
getrennt von App-Login-Credentials (siehe test_issue_1010_1006_stille_fehler.py).
Kein Mock — echte Datei, echte Werte für echte HTTP-Calls.
"""
from __future__ import annotations

from pathlib import Path

_VALIDATOR_ENV = Path("/home/hem/gregor_zwanzig/.claude/validator.env")


def _load_validator_env() -> dict:
    env = {}
    for line in _VALIDATOR_ENV.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def staging_base_url() -> str:
    """Fallback-Kette: GZ_VALIDATION_URL -> GZ_SVELTE_BASE -> Literal-Default.

    Beide Env-Var-Namen bleiben im Repo bestehen (Konsolidierung aller 19+
    Vorkommen ist bewusst NICHT Teil dieses Fixes — Scope-Disziplin)."""
    import os
    env = _load_validator_env()
    return (
        os.environ.get("GZ_VALIDATION_URL")
        or os.environ.get("GZ_SVELTE_BASE")
        or env.get("GZ_VALIDATION_URL")
        or "https://staging.gregor20.henemm.com"
    )


def httpx_auth() -> tuple[str, str]:
    """Basic-Auth-Tupel für httpx.get(url, auth=httpx_auth())."""
    env = _load_validator_env()
    return (env["GZ_VALIDATOR_USER"], env["GZ_VALIDATOR_PASS"])


def playwright_http_credentials() -> dict:
    """Dict für playwright.request.newContext(http_credentials=...) bzw.
    httpCredentials im Playwright-Config (TS-seitig äquivalent per process.env)."""
    user, password = httpx_auth()
    return {"username": user, "password": password}
