"""
TDD RED — Bug #698: Validator-User-Sync + fehlende Fehlerunterscheidung.

SPEC: docs/specs/modules/fix_698_validator_user_sync.md

Root Causes (noch nicht gefixt):
  AC-1: setup-validator-user.sh sagt bei 409 nur "existiert bereits" — kein Login-Check.
  AC-2: validate-external.sh erkennt nicht ob Gregor-Login fehlschlug (kein Cookie) und
        schlägt mit generischem Fehler durch statt spezifischer Meldung.
  AC-3: validate-external.sh erkennt nicht ob claude --print mit Anthropic-401 fehlschlug
        und gibt den rohen Fehlertext statt einer actionablen Meldung aus.

Ausführung:
    uv run pytest tests/tdd/test_fix_698_validator_user_sync.py -v
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup-validator-user.sh"
VALIDATE_SCRIPT = REPO_ROOT / ".claude" / "validate-external.sh"
VALIDATOR_ENV = REPO_ROOT / ".claude" / "validator.env"
SPEC_PATH = "docs/specs/modules/fix_698_validator_user_sync.md"


def _run(cmd: list[str], env: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        env=merged_env,
    )


# ---------------------------------------------------------------------------
# AC-1: setup-validator-user.sh verifiziert Login nach 409
# ---------------------------------------------------------------------------

class TestAC1SetupScriptVerifiesLoginAfter409:
    """
    GIVEN: validator-issue110 existiert bereits auf Staging (409)
    WHEN:  setup-validator-user.sh läuft
    THEN:  Login wird verifiziert; stdout enthält "Login OK" (oder ähnlich)

    RED-Ursache: Script gibt nur "existiert bereits — OK" ohne Login-Prüfung.
    """

    def test_setup_script_reports_login_ok_after_409(self):
        result = _run(["bash", str(SETUP_SCRIPT)])
        combined = result.stdout + result.stderr
        # Script läuft durch (409 = User existiert bereits, oder 429 = Rate-Limit)
        assert result.returncode == 0, (
            f"setup-validator-user.sh schlägt fehl (exit {result.returncode}):\n{combined}"
        )
        # Nach Fix: "Login OK" (200) ODER "rate-limitiert"+"übersprungen" (429) — beide sind akzeptabel
        has_login_ok = (
            ("login" in combined.lower() or "Login" in combined)
            and ("ok" in combined.lower() or "verifiziert" in combined.lower() or "übersprungen" in combined.lower())
        )
        assert has_login_ok, (
            f"BUG #698 AC-1: setup-validator-user.sh verifiziert Login nach 409/429 NICHT.\n"
            f"Erwartet: 'Login OK' (bei HTTP 200) oder 'übersprungen' (bei HTTP 429).\n"
            f"Tatsächlich:\n{combined}"
        )


# ---------------------------------------------------------------------------
# AC-2: validate-external.sh erkennt fehlgeschlagenen Gregor-Login (kein Cookie)
# ---------------------------------------------------------------------------

class TestAC2ValidateExternalDetectsGregorLoginFailure:
    """
    GIVEN: validate-external.sh läuft mit falschem Gregor-Passwort (kein Cookie)
    WHEN:  Script ausgeführt wird
    THEN:  Exit 1 + Meldung enthält "kein Cookie" + "setup-validator-user.sh"

    RED-Ursache: Script fährt mit leerem Cookie weiter, gibt rohen claude-Fehler aus
                 statt einer spezifischen "kein Cookie"-Meldung.
    """

    def test_validate_external_exits_with_no_cookie_message(self):
        # Falsches Passwort via ENV-Override (Datei bleibt unverändert)
        result = _run(
            ["bash", str(VALIDATE_SCRIPT), SPEC_PATH],
            env={
                "GZ_VALIDATOR_USER": "validator-issue110",
                "GZ_VALIDATOR_PASS": "falsches-passwort-xyz-123",
                "GZ_VALIDATION_URL": "https://staging.gregor20.henemm.com",
            },
            timeout=60,
        )
        combined = result.stdout + result.stderr
        assert result.returncode != 0, (
            f"BUG #698 AC-2: validate-external.sh sollte mit Exit 1 fehlschlagen "
            f"wenn Gregor-Login fehlschlägt.\nAusgabe:\n{combined}"
        )
        # Normaler Pfad (login → 401 → kein Cookie → exit 1):
        normal_path = "kein Cookie" in combined and "setup-validator-user" in combined
        # Rate-Limit-Pfad (login → 429 → WARN → claude --print → ANTHROPIC_API_KEY → exit 1):
        # Staging rate-limitiert manchmal auch falsche Passwörter mit 429.
        rate_limit_path = (
            ("429" in combined or "rate-limit" in combined.lower() or "rate_limit" in combined.lower())
            and "ANTHROPIC_API_KEY" in combined
        )
        assert normal_path or rate_limit_path, (
            f"BUG #698 AC-2: validate-external.sh gibt keine verwertbare Auth-Fehlermeldung.\n"
            f"Erwartet: 'kein Cookie'+'setup-validator-user.sh' ODER '429'+'ANTHROPIC_API_KEY'.\n"
            f"Tatsächlich:\n{combined}"
        )


# ---------------------------------------------------------------------------
# AC-3: validate-external.sh erkennt Anthropic-API-Fehler von claude --print
# ---------------------------------------------------------------------------

class TestAC3ValidateExternalDetectsAnthropicApiError:
    """
    GIVEN: validate-external.sh läuft mit korrekten Gregor-Credentials
           aber claude --print schlägt fehl (kein ANTHROPIC_API_KEY)
    WHEN:  Script ausgeführt wird
    THEN:  Exit 1 + Meldung enthält "ANTHROPIC_API_KEY" und "Subagent"
           (kein "kein Cookie"-Fehler davor)

    RED-Ursache: Script gibt rohen claude-Fehlertext aus statt actionabler Meldung.
    """

    def test_validate_external_exits_with_api_key_message(self):
        # Korrekter Gregor-Login, aber ANTHROPIC_API_KEY fehlt
        env = {
            "GZ_VALIDATOR_USER": "validator-issue110",
            "GZ_VALIDATOR_PASS": "457442e8830f5ee3afe9afe2d5f0d923",
            "GZ_VALIDATION_URL": "https://staging.gregor20.henemm.com",
        }
        # ANTHROPIC_API_KEY explizit löschen falls gesetzt
        env.pop("ANTHROPIC_API_KEY", None)

        result = _run(
            ["bash", str(VALIDATE_SCRIPT), SPEC_PATH],
            env=env,
            timeout=60,
        )
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            f"BUG #698 AC-3: validate-external.sh sollte mit Exit 1 fehlschlagen "
            f"wenn claude --print kein API-Key hat.\nAusgabe:\n{combined}"
        )
        has_api_key_msg = "ANTHROPIC_API_KEY" in combined or "api_key" in combined.lower()
        has_subagent_hint = "Subagent" in combined or "subagent" in combined.lower()
        assert has_api_key_msg and has_subagent_hint, (
            f"BUG #698 AC-3: validate-external.sh gibt keine spezifische API-Key-Meldung.\n"
            f"Erwartet: 'ANTHROPIC_API_KEY' + 'Subagent' in Ausgabe.\n"
            f"Tatsächlich:\n{combined}"
        )
        # Kein "kein Cookie"-Fehler davor — Gregor-Login lief sauber durch
        assert "kein Cookie" not in combined, (
            f"BUG #698 AC-3: Gregor-Login-Fehler taucht auf, obwohl Credentials korrekt waren.\n"
            f"Ausgabe:\n{combined}"
        )
