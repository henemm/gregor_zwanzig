"""
Wächter-Test: Test-Mails dürfen NIEMALS über Resend versendet werden.

Spec: docs/specs/tests/no_resend_for_tests.md

Hintergrund:
    Resend ist der bezahlte Produktiv-Versanddienst (smtp.resend.com).
    Test-/TDD-Mails würden das Kontingent verbrennen und die Zustellraten verfälschen.
    Die Regel wurde in der Vergangenheit mehrfach durch Refactorings gebrochen — dieser
    Test bricht jeden zukünftigen Bruch sofort.

Mechanik:
    - Settings.for_testing() setzt is_test_mode=True
    - EmailOutput.__init__ verweigert Construct, wenn is_test_mode=True UND smtp_host "resend" enthält
    - Seit #1122 (Default-Deny) lenkt Settings JEDEN Resend-Host ohne GZ_RESEND_ALLOWED
      schon bei Konstruktion um; unter pytest auch mit Token. Die EmailOutput-Guards
      bleiben zweite Linie und werden hier über den model_copy-Bypass getestet
      (model_copy läuft ohne Validator).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.config import Settings
from output.channels.base import OutputConfigError
from output.channels.email import EmailOutput


def _resend_settings(**overrides) -> Settings:
    """Settings, die einen Resend-Versand simulieren."""
    base = dict(
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_xxx",
        mail_to="user@example.com",
        mail_from="bot@henemm.com",
        test_smtp_user="gregor-test",
        test_smtp_pass="testpass",
        test_mail_from="gregor-test@henemm.com",
    )
    base.update(overrides)
    return Settings(**base)


def test_for_testing_setzt_is_test_mode():
    """for_testing() muss is_test_mode=True setzen."""
    s = _resend_settings()
    assert s.is_test_mode is False, "Default Settings dürfen NICHT im Test-Modus sein"

    t = s.for_testing()
    assert t.is_test_mode is True, "for_testing() MUSS is_test_mode=True setzen"


def test_for_testing_swappt_auf_gmail():
    """for_testing() muss smtp_user auf Test-Credentials umstellen, wenn test_smtp_* gesetzt.

    Seit Issue #879 lenkt for_testing() den Host IMMER auf den lokalen Stalwart-Test-Host
    (test_smtp_host, Default mail.henemm.com) — NIE mehr Resend, da GZ_SMTP_HOST seit #876
    wieder auf smtp.resend.com zeigt.
    """
    s = _resend_settings().for_testing()
    assert s.smtp_user == "gregor-test"
    assert "resend" not in s.smtp_host.lower()  # #879: Host weg von Resend
    assert s.smtp_host == "mail.henemm.com"


def test_for_testing_ohne_gmail_credentials_setzt_trotzdem_flag():
    """Wenn test_smtp_* fehlen, wird is_test_mode gesetzt UND der Host (seit #879) trotzdem
    von Resend weg auf den Stalwart-Test-Host umgelenkt — der EmailOutput-Wächter bleibt als
    zweite Sicherung erhalten."""
    s = _resend_settings(
        test_smtp_user=None,
        test_smtp_pass=None,
    ).for_testing()
    assert s.is_test_mode is True
    assert "resend" not in s.smtp_host.lower()


def test_email_output_blockiert_resend_im_test_modus():
    """EmailOutput MUSS Construct verweigern, wenn is_test_mode=True und Host = Resend.

    Seit #1122 hält eine via __init__ konstruierte Settings nie mehr einen
    Resend-Host — der Second-Line-Guard wird deshalb über den model_copy-Bypass
    erreicht (Validator läuft bei model_copy nicht, genau dafür existiert er)."""
    s = _resend_settings().model_copy(
        update={"smtp_host": "smtp.resend.com", "is_test_mode": True}
    )
    with pytest.raises(OutputConfigError) as exc_info:
        EmailOutput(s)
    msg = str(exc_info.value).lower()
    assert "resend" in msg
    assert "stalwart" in msg or "test" in msg


def test_email_output_erlaubt_gmail_im_test_modus():
    """EmailOutput MUSS funktionieren, wenn is_test_mode=True und Host = Stalwart (kein Resend)."""
    s = _resend_settings(smtp_host="mail.henemm.com").for_testing()
    output = EmailOutput(s)
    assert output is not None


def test_email_output_erlaubt_resend_in_production():
    """Produktions-Settings (is_test_mode=False) müssen EmailOutput konstruieren können.

    Seit #1122 lenkt der Default-Deny-Validator den Resend-Host unter pytest um —
    der Beweis „Prod MIT Token behält Resend" läuft als echter Subprocess-Test in
    tests/tdd/test_issue_1122_resend_default_deny.py (AC-3)."""
    s = _resend_settings()
    assert s.is_test_mode is False
    output = EmailOutput(s)
    assert output is not None


def test_test_user_routing_aktiviert_test_modus(tmp_path, monkeypatch):
    """with_user_profile() für Test-User (ID enthält 'test'/'tdd') MUSS is_test_mode setzen."""
    monkeypatch.chdir(tmp_path)
    profile_dir = tmp_path / "data" / "users" / "test_alice"
    profile_dir.mkdir(parents=True)
    (profile_dir / "user.json").write_text('{"mail_to": "alice@example.com"}')

    s = _resend_settings().with_user_profile("test_alice")
    assert s.is_test_mode is True, "Test-User MUSS Test-Modus aktivieren"

    s_normal = _resend_settings().with_user_profile("alice")
    assert s_normal.is_test_mode is False, "Normaler User darf Test-Modus NICHT aktivieren"
