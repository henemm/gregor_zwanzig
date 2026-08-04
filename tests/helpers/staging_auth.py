"""tests/helpers/staging_auth.py — zentraler Staging-Basic-Auth-Helper.

Liefert Nginx-Basic-Auth-Credentials für Staging aus .claude/validator.env,
getrennt von App-Login-Credentials (siehe test_issue_1010_1006_stille_fehler.py).
Kein Mock — echte Datei, echte Werte für echte HTTP-Calls.
"""
from __future__ import annotations

from pathlib import Path

# Hauptrepo-Pfad bewusst fest (#1409, Klasse B): Zugangsdaten kommen aus EINER Quelle,
# der produktiven Konfiguration -- nicht aus einer Worktree-Kopie.
_VALIDATOR_ENV = Path("/home/hem/gregor_zwanzig/.claude/validator.env")


def _load_validator_env() -> dict:
    """Fehlt die Datei (jede Maschine ausser dem Server), liefert {} statt zu
    werfen: staging_base_url() faellt dann auf Env-Vars/Literal-Default,
    httpx_auth() skippt den Test. Vorher brach der Read ueber Modulebenen-
    Aufrufer (z.B. test_issue_1069:47) die Collection der GESAMTEN Suite auf
    jedem Rechner ohne validator.env (#1196)."""
    if not _VALIDATOR_ENV.exists():
        return {}
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
    """Basic-Auth-Tupel für httpx.get(url, auth=httpx_auth()).

    Ohne verfügbare Credentials wird der aufrufende Test uebersprungen statt
    mit KeyError zu scheitern — Staging-Tests laufen nur auf dem Server."""
    env = _load_validator_env()
    try:
        return (env["GZ_VALIDATOR_USER"], env["GZ_VALIDATOR_PASS"])
    except KeyError:
        import pytest

        pytest.skip(
            "Staging-Basic-Auth nicht verfuegbar (validator.env fehlt) — "
            "laeuft nur auf dem Server"
        )


def playwright_http_credentials() -> dict:
    """Dict für playwright.request.newContext(http_credentials=...) bzw.
    httpCredentials im Playwright-Config (TS-seitig äquivalent per process.env)."""
    user, password = httpx_auth()
    return {"username": user, "password": password}
