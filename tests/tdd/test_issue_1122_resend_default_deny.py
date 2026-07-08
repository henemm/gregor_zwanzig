"""TDD: Issue #1122 — Resend Default-Deny: Versand nur mit explizitem Token.

Spec: docs/specs/modules/issue_1122_resend_default_deny.md

Kernumkehrung (PO-Entscheidung): Resend ist grundsätzlich gesperrt. Nur ein
Prozess mit GZ_RESEND_ALLOWED=1 (ausschließlich Prod-Systemd-Units) darf einen
Resend-Host halten. pytest-Prozesse sind AUCH MIT Token gesperrt.

Keine Mocks: echte Settings-Konstruktion, echte EmailOutput-Instanzen,
echter Subprocess für den Nicht-pytest-Fall (AC-3).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from output.channels.base import OutputConfigError  # noqa: E402
from output.channels.email import EmailOutput  # noqa: E402


def _resend_kwargs(**overrides) -> dict:
    base = dict(
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_xxx",
        mail_to="user@example.com",
        mail_from="bot@henemm.com",
        _env_file=None,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-1: Prozess ohne Token kann keinen Resend-Host halten
# ---------------------------------------------------------------------------


class TestAC1DefaultDeny:
    def test_settings_ohne_token_lenken_resend_host_um(self):
        """AC-1: Given kein GZ_RESEND_ALLOWED / When Settings mit Resend-Host /
        Then smtp_host = Stalwart-Test-Host, Port = Test-Port."""
        s = Settings(**_resend_kwargs())
        assert "resend" not in (s.smtp_host or "").lower(), (
            f"Default-Deny verletzt: Settings hält Resend-Host {s.smtp_host!r} "
            "ohne GZ_RESEND_ALLOWED"
        )
        assert s.smtp_host == s.test_smtp_host
        assert s.smtp_port == s.test_smtp_port

    def test_rohe_settings_plus_emailoutput_erreichen_resend_nicht(self):
        """AC-1 (Leak-Reproduktion): das Muster aller 9 Vorfälle — rohe Settings()
        + EmailOutput OHNE for_testing() — darf Resend nicht mehr erreichen können."""
        s = Settings(**_resend_kwargs())
        out = EmailOutput(s)
        assert "resend" not in out._host.lower(), (
            "Der historische Leak-Pfad (Settings roh → EmailOutput → send) "
            f"zeigt noch auf Resend: {out._host!r}"
        )

    def test_nicht_resend_host_bleibt_unangetastet(self):
        """Given ein Nicht-Resend-Host / When Settings konstruiert /
        Then keine Umlenkung (kein Kollateralschaden)."""
        s = Settings(**_resend_kwargs(smtp_host="mail.henemm.com", smtp_port=465))
        assert s.smtp_host == "mail.henemm.com"
        assert s.smtp_port == 465


# ---------------------------------------------------------------------------
# AC-2: pytest-Prozess schlägt Token — Umlenkung auch mit GZ_RESEND_ALLOWED
# ---------------------------------------------------------------------------


class TestAC2PytestSchlaegtToken:
    def test_umlenkung_trotz_token_unter_pytest(self):
        """AC-2: Given pytest-Lauf mit resend_allowed=True / When Settings mit
        Resend-Host / Then trotzdem Umlenkung — Tests dürfen NIE über Resend."""
        s = Settings(**_resend_kwargs(resend_allowed=True))
        assert "resend" not in (s.smtp_host or "").lower(), (
            "Ein in die Test-Shell geleaktes GZ_RESEND_ALLOWED darf pytest "
            "NICHT zum Resend-Versand befähigen"
        )

    def test_umlenkung_trotz_env_token_unter_pytest(self, monkeypatch):
        """AC-2 (env-Variante): Token via GZ_RESEND_ALLOWED-Env statt Konstruktor."""
        monkeypatch.setenv("GZ_RESEND_ALLOWED", "1")
        s = Settings(**_resend_kwargs())
        assert "resend" not in (s.smtp_host or "").lower()


# ---------------------------------------------------------------------------
# AC-3: Nicht-Test-Prozess MIT Token behält Resend (Produktion funktioniert)
# ---------------------------------------------------------------------------


_SUBPROC_CODE = (
    "import sys; sys.path.insert(0, {src!r}); "
    "from app.config import Settings; "
    "s = Settings(smtp_host='smtp.resend.com', smtp_port=587, smtp_user='resend', "
    "smtp_pass='k', mail_to='u@example.com', resend_allowed={token}, _env_file=None); "
    "print(s.smtp_host)"
)


def _run_subprocess(token: bool) -> str:
    """Echter Nicht-pytest-Prozess: PYTEST_CURRENT_TEST wird explizit entfernt,
    damit das Kind den Produktionsfall repräsentiert."""
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env.pop("GZ_RESEND_ALLOWED", None)
    code = _SUBPROC_CODE.format(src=str(REPO_ROOT / "src"), token=token)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=60,
    )
    assert result.returncode == 0, f"Subprocess-Fehler: {result.stderr}"
    return result.stdout.strip()


class TestAC3ProdMitTokenBehaeltResend:
    def test_subprocess_mit_token_behaelt_resend_host(self):
        """AC-3: Given Nicht-pytest-Prozess mit Token / When Settings mit
        Resend-Host / Then Host bleibt — echter User-Versand unverändert."""
        host = _run_subprocess(token=True)
        assert host == "smtp.resend.com", (
            f"Produktion mit GZ_RESEND_ALLOWED muss Resend behalten, war: {host!r}"
        )

    def test_subprocess_ohne_token_lenkt_um(self):
        """AC-1-Gegenprobe im echten Nicht-pytest-Prozess: ohne Token Umlenkung."""
        host = _run_subprocess(token=False)
        assert "resend" not in host.lower(), (
            f"Nicht-Test-Prozess OHNE Token darf Resend nicht halten, war: {host!r}"
        )


# ---------------------------------------------------------------------------
# AC-6: Zweite Linie (#879) bleibt — model_copy umgeht den Validator
# ---------------------------------------------------------------------------


class TestAC6ZweiteLinieBleibt:
    def test_model_copy_bypass_wird_von_emailoutput_gefangen(self):
        """AC-6: Given Resend-Host via model_copy (Validator läuft nicht) +
        is_test_mode / When EmailOutput / Then OutputConfigError (#879-Guard)."""
        s = Settings(**_resend_kwargs(smtp_host="mail.henemm.com")).model_copy(
            update={"smtp_host": "smtp.resend.com", "is_test_mode": True}
        )
        assert "resend" in s.smtp_host.lower(), "Testaufbau: Bypass muss Resend-Host halten"
        with pytest.raises(OutputConfigError):
            EmailOutput(s)
