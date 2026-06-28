"""
TDD RED — Issue #879: Test-/Staging-Mail-Versand strikt von Resend isolieren

Spec: docs/specs/modules/issue_879_test_mail_resend_isolation.md
Workflow: issue-879-test-mail-resend-leak

Kontext: GZ_SMTP_HOST zeigt seit #876 auf smtp.resend.com. for_testing() schaltet
den Absender/User auf den Stalwart-Test-Account, lässt aber smtp_host unverändert —
dadurch landen Test-Mails im Resend-Wächter und schlagen fehl, statt lokal über
Stalwart zugestellt zu werden. Staging hat keine Bremse gegen Resend-Versand.

Tests prüfen VERHALTEN — keine Mocks:

  AC-1 (Unit):  for_testing() setzt smtp_host/-port auf test_smtp_host/-port (Stalwart).
                RED: aktuell bleibt smtp_host = smtp.resend.com.
  AC-1 (E2E):   @pytest.mark.email — echter Versand über Stalwart + IMAP-Nachweis.
                RED: aktuell wirft EmailOutput OutputConfigError (Host = Resend).
  AC-2 (Unit):  GZ_ENV=staging erzwingt is_test_mode auch für nicht-test User.
                RED: aktuell keine Staging-Erzwingung → is_test_mode False.
  AC-3 (Regression): Resend-Wächter bleibt — is_test_mode + Resend-Host → OutputConfigError.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# AC-1 (Unit): for_testing() lenkt smtp_host/-port auf Stalwart-Test-Host
# ---------------------------------------------------------------------------


class TestAC1ForTestingRedirectsHost:
    """for_testing() muss den SMTP-Host auf den lokalen Stalwart-Test-Host umstellen,
    nicht nur den User/Absender. Sonst gehen Test-Mails über Resend (oder schlagen
    am Resend-Wächter fehl)."""

    def test_for_testing_sets_smtp_host_to_test_host(self):
        """
        GIVEN: Settings mit smtp_host=smtp.resend.com und test_smtp_host=mail.henemm.com
        WHEN: for_testing() aufgerufen wird
        THEN: result.smtp_host == mail.henemm.com (NICHT resend)

        RED: for_testing() ändert smtp_host aktuell nicht → bleibt resend.
        """
        from app.config import Settings

        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_port=587,
            smtp_user="resend",
            smtp_pass="prod-key",
            mail_to="gregor-test@henemm.com",
            test_smtp_host="mail.henemm.com",
            test_smtp_port=587,
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        result = s.for_testing()
        assert "resend" not in (result.smtp_host or "").lower(), (
            f"for_testing() darf NIE einen Resend-Host behalten, war: {result.smtp_host}"
        )
        assert result.smtp_host == "mail.henemm.com", (
            f"for_testing() muss smtp_host auf test_smtp_host setzen, war: {result.smtp_host}"
        )

    def test_for_testing_defaults_test_host_to_stalwart(self):
        """
        GIVEN: Settings ohne explizites test_smtp_host, aber mit Test-Credentials
        WHEN: for_testing() aufgerufen wird
        THEN: smtp_host fällt auf den lokalen Stalwart-Host (mail.henemm.com) zurück

        RED: kein test_smtp_host-Default vorhanden, smtp_host bleibt resend.
        """
        from app.config import Settings

        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod-key",
            mail_to="gregor-test@henemm.com",
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        result = s.for_testing()
        assert "resend" not in (result.smtp_host or "").lower(), (
            f"for_testing() muss ohne explizite Config trotzdem von Resend weg, war: {result.smtp_host}"
        )


# ---------------------------------------------------------------------------
# AC-2 (Unit): Staging erzwingt Test-Modus
# ---------------------------------------------------------------------------


class TestAC2StagingForcesTestMode:
    """Auf Staging (GZ_ENV=staging) darf NIE über Resend an reale Empfänger gesendet
    werden — auch nicht für nicht-test User. with_user_profile() muss is_test_mode
    erzwingen."""

    def test_staging_forces_test_mode_for_non_test_user(self):
        """
        GIVEN: Settings(env=staging) und ein nicht-test User
        WHEN: with_user_profile('echtnutzer') aufgerufen wird
        THEN: result.is_test_mode is True und smtp_host nicht resend

        RED: aktuell keine Staging-Logik → is_test_mode bleibt False, Host = resend.
        """
        from app.config import Settings

        s = Settings(
            env="staging",
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod-key",
            mail_to="echt@example.com",
            test_smtp_host="mail.henemm.com",
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        result = s.with_user_profile("echtnutzer")
        assert result.is_test_mode is True, (
            "Auf Staging MUSS is_test_mode erzwungen werden — sonst Resend-Versand an reale Empfänger."
        )
        assert "resend" not in (result.smtp_host or "").lower(), (
            f"Staging darf nicht über Resend senden, Host war: {result.smtp_host}"
        )

    def test_production_keeps_resend_for_real_user(self):
        """
        GIVEN: Settings(env=production) und ein nicht-test User
        WHEN: with_user_profile('echtnutzer')
        THEN: is_test_mode bleibt False, Resend bleibt der Produktiv-Versandweg

        Schutz gegen Übersteuerung: Produktion soll weiter über Resend laufen.
        """
        from app.config import Settings

        s = Settings(
            env="production",
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod-key",
            mail_to="echt@example.com",
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        result = s.with_user_profile("echtnutzer")
        assert result.is_test_mode is False, (
            "Produktion darf NICHT in den Test-Modus fallen — sonst kommen echte Briefings nicht an."
        )


# ---------------------------------------------------------------------------
# AC-3 (Regression): Resend-Wächter bleibt als Defense-in-Depth
# ---------------------------------------------------------------------------


class TestAC3ResendGuardRemains:
    """Der bestehende Wächter in EmailOutput muss erhalten bleiben: is_test_mode +
    Resend-Host → OutputConfigError. Greift, falls test_smtp_host fehlkonfiguriert ist."""

    def test_guard_blocks_test_send_over_resend(self):
        """
        GIVEN: Settings(is_test_mode=True, smtp_host=smtp.resend.com)
        WHEN: EmailOutput(settings) instanziiert wird
        THEN: OutputConfigError

        Regression: dieser Wächter ist schon vorhanden und MUSS bestehen bleiben.
        """
        from app.config import Settings
        from outputs.email import EmailOutput
        from outputs.base import OutputConfigError

        s = Settings(
            is_test_mode=True,
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="key",
            mail_to="gregor-test@henemm.com",
        )
        with pytest.raises(OutputConfigError):
            EmailOutput(s)


# ---------------------------------------------------------------------------
# AC-1 (E2E): echter Versand über Stalwart + IMAP-Nachweis
# ---------------------------------------------------------------------------


@pytest.mark.email
class TestAC1RealStalwartDelivery:
    """End-to-End: for_testing()-Settings senden echte Mail über Stalwart an
    gregor-test@henemm.com; IMAP-Nachweis. Beweis, dass der Test-Pfad zustellt OHNE
    Resend zu belasten."""

    def test_test_mail_delivered_via_stalwart(self):
        """
        GIVEN: Settings().for_testing() (Stalwart-Test-Account)
        WHEN: EmailOutput.send() an gregor-test@henemm.com mit Unique-Marker
        THEN: Mail kommt per IMAP im gregor-test-Postfach an (max 60s)

        RED: aktuell wirft EmailOutput OutputConfigError (Host = Resend) →
             kein Versand → IMAP findet nichts.
        Kein Mock. Echter SMTP via Stalwart.
        """
        import imaplib
        from app.config import Settings
        from outputs.email import EmailOutput

        settings = Settings().for_testing()
        if not settings.test_smtp_user or not settings.test_smtp_pass:
            pytest.skip("Stalwart-Test-Credentials (GZ_TEST_SMTP_*) nicht konfiguriert")

        marker = uuid.uuid4().hex[:8]
        subject = f"#879 Stalwart-Isolationstest {marker}"

        output = EmailOutput(settings)
        output.send(
            subject=subject,
            body=f"<p>Test #879 marker {marker}</p>",
            html=True,
            to=["gregor-test@henemm.com"],
        )

        imap_host = settings.imap_host or settings.smtp_host
        imap_port = settings.imap_port or 993
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not all([imap_host, imap_user, imap_pass]):
            pytest.skip("IMAP-Credentials nicht konfiguriert")

        found = False
        for _ in range(12):  # 12 × 5s = 60s
            time.sleep(5)
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            try:
                imap.login(imap_user, imap_pass)
                imap.select("INBOX")
                _, data = imap.search(None, f'SUBJECT "{marker}"')
                if data[0].split():
                    found = True
                    break
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        assert found, (
            f"Test-Mail mit Marker '{marker}' nach 60s nicht in gregor-test INBOX. "
            "for_testing() stellt nicht über Stalwart zu (Resend-Wächter blockiert)."
        )
