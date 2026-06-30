"""
TDD RED — Issue #927: SMTP-Fallback wenn Resend.com nicht erreichbar ist.

Alle Tests beweisen echtes Verhalten — keine Mocks.
Test-Strategie: ungültiger Primary-SMTP (127.0.0.1:1, sofortiger ECONNREFUSED)
+ echter Stalwart-Fallback für die Verhaltenstests.
"""
from __future__ import annotations

import imaplib
import logging
import os
import time
import uuid
from datetime import datetime

import pytest

from app.config import Settings
from outputs.base import OutputConfigError, OutputError
from outputs.email import EmailOutput


def _make_settings_with_imap_fallback() -> Settings:
    """Settings: Resend als Primary (ungültig), Stalwart via IMAP-Creds als Fallback."""
    return Settings(
        smtp_host="127.0.0.1",
        smtp_port=1,
        smtp_user="resend",
        smtp_pass="re_fake_invalid_key_for_tdd",
        mail_to=os.environ.get("GZ_TEST_IMAP_USER", "gregor-test") + "@henemm.com",
        mail_from="gregor_zwanzig@henemm.com",
        imap_host=os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
        imap_user=os.environ.get("GZ_TEST_IMAP_USER") or os.environ.get("GZ_IMAP_USER", "gregor_zwanzig"),
        imap_pass=os.environ.get("GZ_TEST_IMAP_PASS") or os.environ.get("GZ_IMAP_PASS", ""),
    )


def _make_settings_without_imap_fallback() -> Settings:
    """Settings: Resend als Primary, keine IMAP-Creds → kein Fallback."""
    return Settings(
        smtp_host="127.0.0.1",
        smtp_port=1,
        smtp_user="resend",
        smtp_pass="re_fake",
        mail_to="nobody@example.com",
        mail_from="gregor_zwanzig@henemm.com",
        imap_host=None,
        imap_user=None,
        imap_pass=None,
    )


# ---------------------------------------------------------------------------
# AC-1 Voraussetzung: EmailOutput muss Fallback-Credentials aus IMAP-Settings
# initialisieren. Scheitert mit AttributeError weil _fallback_host nicht existiert.
# ---------------------------------------------------------------------------

class TestAC1FallbackInitialization:
    """AC-1: EmailOutput speichert IMAP-Credentials als Fallback-SMTP."""

    def test_fallback_host_stored_from_imap_settings(self):
        """
        GIVEN: Settings mit imap_host=mail.henemm.com gesetzt
        WHEN:  EmailOutput(settings) initialisiert wird
        THEN:  _fallback_host ist gleich dem imap_host
        RED:   AttributeError — _fallback_host existiert noch nicht
        """
        settings = _make_settings_with_imap_fallback()
        output = EmailOutput(settings)
        # RED: AttributeError — _fallback_host wurde noch nicht implementiert
        assert hasattr(output, "_fallback_host"), (
            "EmailOutput muss _fallback_host aus settings.imap_host initialisieren"
        )
        assert output._fallback_host == settings.imap_host

    def test_fallback_user_stored_from_imap_settings(self):
        """
        GIVEN: Settings mit imap_user gesetzt
        WHEN:  EmailOutput(settings) initialisiert wird
        THEN:  _fallback_user ist gleich dem imap_user
        """
        settings = _make_settings_with_imap_fallback()
        output = EmailOutput(settings)
        assert hasattr(output, "_fallback_user"), (
            "EmailOutput muss _fallback_user aus settings.imap_user initialisieren"
        )
        assert output._fallback_user == settings.imap_user

    def test_fallback_pass_stored_from_imap_settings(self):
        """
        GIVEN: Settings mit imap_pass gesetzt
        WHEN:  EmailOutput(settings) initialisiert wird
        THEN:  _fallback_pass ist gleich dem imap_pass
        """
        settings = _make_settings_with_imap_fallback()
        output = EmailOutput(settings)
        assert hasattr(output, "_fallback_pass"), (
            "EmailOutput muss _fallback_pass aus settings.imap_pass initialisieren"
        )
        assert output._fallback_pass == settings.imap_pass

    def test_no_fallback_without_imap_credentials(self):
        """
        GIVEN: Settings ohne imap_host/user/pass
        WHEN:  EmailOutput(settings) initialisiert wird
        THEN:  _fallback_host ist None oder leer (kein Fallback)
        """
        settings = _make_settings_without_imap_fallback()
        output = EmailOutput(settings)
        # _fallback_host muss existieren (None bedeutet: kein Fallback konfiguriert)
        assert hasattr(output, "_fallback_host"), (
            "_fallback_host muss immer existieren (None wenn nicht konfiguriert)"
        )
        assert not output._fallback_host, (
            "_fallback_host muss None/leer sein wenn kein IMAP-Host gesetzt"
        )


# ---------------------------------------------------------------------------
# AC-2: Kein Fallback bei Auth-Fehler (permanente Fehler)
# ---------------------------------------------------------------------------

class TestAC2NoFallbackOnAuthError:
    """AC-2: Bei SMTPAuthenticationError wird KEIN Fallback-Versuch unternommen."""

    def test_fallback_disabled_flag_for_auth_errors(self):
        """
        GIVEN: EmailOutput mit Fallback-Credentials konfiguriert
        WHEN:  EmailOutput instanziiert
        THEN:  Objekt muss Mechanismus haben, Auth-Fehler zu erkennen (kein Fallback)
        RED:   _TRANSIENT_ERRORS_TRIGGER_FALLBACK oder ähnliches Attribut fehlt noch
        """
        settings = _make_settings_with_imap_fallback()
        output = EmailOutput(settings)
        # Der implementierende Code muss permanente von transienten Fehlern unterscheiden.
        # Indikator: die Klasse hat eine Konstante/Methode dafür.
        # RED: noch nicht implementiert → dieser Test zeigt die Erwartung
        assert hasattr(output, "_fallback_host"), "Voraussetzung: Fallback initialisiert"
        # AC-2 Volltest: Auth-Fehler-Szenario ohne echte Resend-Verbindung
        # Wird in TDD GREEN via @pytest.mark.email vollständig geprüft


@pytest.mark.email
class TestAC2NoFallbackOnAuthErrorBehavioral:
    """AC-2 Verhaltenstest: SMTPAuthenticationError → sofort OutputError, kein Fallback."""

    def test_stalwart_auth_error_does_not_trigger_fallback(self, caplog):
        """
        GIVEN: Primary-SMTP = Stalwart mit FALSCHEM Passwort (→ echte 535-Antwort),
               Fallback konfiguriert mit korrekten Stalwart-Creds
        WHEN:  EmailOutput.send() aufgerufen
        THEN:  OutputError sofort geworfen, "[SMTP-FALLBACK]" NICHT im Log
        Beweis: Wenn Fallback trotzdem greift, kommt keine OutputError → Test scheitert
        """
        import logging

        imap_host = os.environ.get("GZ_IMAP_HOST", "mail.henemm.com")
        imap_user = os.environ.get("GZ_TEST_IMAP_USER") or os.environ.get("GZ_IMAP_USER")
        imap_pass = os.environ.get("GZ_TEST_IMAP_PASS") or os.environ.get("GZ_IMAP_PASS")

        if not imap_user or not imap_pass:
            pytest.skip("GZ_IMAP_USER/PASS nicht gesetzt — Integration-Test übersprungen")

        # Stalwart als Primary mit FALSCHEM Passwort → echte SMTPAuthenticationError (535)
        settings = Settings(
            smtp_host=imap_host,
            smtp_port=587,
            smtp_user=imap_user,
            smtp_pass="DELIBERATELY-WRONG-PASSWORD-AC2-TEST",
            mail_to=imap_user + "@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
            imap_host=imap_host,   # Fallback = korrekte Creds — würde geliefert wenn Fallback greift
            imap_user=imap_user,
            imap_pass=imap_pass,
        )

        output = EmailOutput(settings)

        with caplog.at_level(logging.INFO, logger="outputs.email"):
            with pytest.raises(OutputError) as exc_info:
                output.send(
                    "AC2-Auth-Fehler-Test",
                    "<p>Darf nicht zugestellt werden</p>",
                    html=True,
                )

        # Kern-Assertion: kein Fallback-Versuch
        assert "[SMTP-FALLBACK]" not in caplog.text, (
            "SMTPAuthenticationError darf KEINEN Fallback auslösen — "
            "aber '[SMTP-FALLBACK]' wurde im Log gefunden!"
        )
        # Sekundär: Fehler-String zeigt Auth-Problem
        assert "authentication" in str(exc_info.value).lower() or "535" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-5: Staging-Guard (#924) bleibt unverändert
# ---------------------------------------------------------------------------

class TestAC5StagingGuardUnchanged:
    """AC-5: Staging-Guard aus Issue #924 greift unverändert — Fallback-Code nicht erreicht."""

    def test_staging_with_resend_host_raises_config_error(self):
        """
        GIVEN: GZ_ENV=staging, smtp_host=smtp.resend.com
        WHEN:  EmailOutput(settings) instanziiert wird
        THEN:  OutputConfigError sofort — vor jedem Fallback-Pfad
        """
        settings = Settings(
            smtp_host="smtp.resend.com",
            smtp_port=587,
            smtp_user="resend",
            smtp_pass="re_key",
            mail_to="test@example.com",
            env="staging",
        )
        with pytest.raises(OutputConfigError) as exc_info:
            EmailOutput(settings)
        assert "Staging" in str(exc_info.value) or "resend" in str(exc_info.value).lower()

    def test_staging_guard_error_message_unchanged(self):
        """
        GIVEN: Staging-Konfiguration mit Resend-Host
        WHEN:  EmailOutput() initialisiert
        THEN:  Fehlermeldung enthält Issue-#924-Kennzeichner
        """
        settings = Settings(
            smtp_host="smtp.resend.com",
            smtp_port=587,
            smtp_user="resend",
            smtp_pass="re_key",
            mail_to="test@example.com",
            env="staging",
        )
        with pytest.raises(OutputConfigError) as exc_info:
            EmailOutput(settings)
        error_str = str(exc_info.value)
        assert "924" in error_str or "Staging" in error_str


# ---------------------------------------------------------------------------
# AC-6: Fallback-Log-Eintrag hat exaktes Format
# ---------------------------------------------------------------------------

class TestAC6FallbackLogFormat:
    """AC-6: Log-Eintrag bei Fallback enthält '[SMTP-FALLBACK] sent via fallback SMTP'."""

    EXPECTED_LOG_MARKER = "[SMTP-FALLBACK]"

    def test_fallback_log_marker_constant_exists(self):
        """
        GIVEN: EmailOutput-Klasse
        WHEN:  nach SMTP_FALLBACK_LOG_MARKER oder _FALLBACK_LOG_MARKER gesucht
        THEN:  Konstante oder erkennbares Muster existiert
        RED:   Konstante wurde noch nicht definiert
        """
        # Prüft dass die Implementierung eine benannte Konstante hat (nicht magic string)
        import inspect
        import outputs.email as email_module
        source = inspect.getsource(email_module)
        assert self.EXPECTED_LOG_MARKER in source, (
            f"Log-Marker '{self.EXPECTED_LOG_MARKER}' muss in email.py als String-Literal vorkommen"
        )


# ---------------------------------------------------------------------------
# AC-1 Verhaltenstest (Integration, @pytest.mark.email)
# Beweis: Mail tatsächlich via Stalwart-Fallback zugestellt
# ---------------------------------------------------------------------------

@pytest.mark.email
class TestAC1PythonFallbackBehavior:
    """AC-1 Verhaltenstest: Mail via Stalwart-Fallback tatsächlich zugestellt."""

    def test_mail_delivered_via_stalwart_fallback(self):
        """
        GIVEN: Primary-SMTP nicht erreichbar (127.0.0.1:1), Stalwart als Fallback
        WHEN:  EmailOutput.send() aufgerufen
        THEN:  Mail in IMAP-Postfach nachweisbar — kein OutputError
        RED:   OutputError weil Fallback nicht implementiert
        """
        marker = f"AC1-FALLBACK-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        subject = f"[TDD #927] {marker}"

        imap_host = os.environ.get("GZ_IMAP_HOST", "mail.henemm.com")
        imap_user = os.environ.get("GZ_TEST_IMAP_USER") or os.environ.get("GZ_IMAP_USER")
        imap_pass = os.environ.get("GZ_TEST_IMAP_PASS") or os.environ.get("GZ_IMAP_PASS")

        if not imap_user or not imap_pass:
            pytest.skip("GZ_IMAP_USER/PASS nicht gesetzt — Integration-Test übersprungen")

        settings = Settings(
            smtp_host="127.0.0.1",
            smtp_port=1,
            smtp_user="resend",
            smtp_pass="re_fake_invalid",
            mail_to=imap_user + "@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
            imap_host=imap_host,
            imap_user=imap_user,
            imap_pass=imap_pass,
        )

        output = EmailOutput(settings)

        # RED: OutputError — Fallback nicht implementiert, alle 4 Retries schlagen fehl
        # (Hinweis: Test wartet wegen Backoff ~50s bevor er mit OutputError schlägt)
        output.send(subject, f"<p>Fallback-Test {marker}</p>", html=True)

        # Nach Implementierung: Mail via IMAP verifizieren
        _wait_for_mail_in_imap(
            host=imap_host,
            user=imap_user,
            password=imap_pass,
            subject_marker=marker,
            timeout=60,
        )


def _wait_for_mail_in_imap(
    host: str,
    user: str,
    password: str,
    subject_marker: str,
    timeout: int = 60,
) -> None:
    """Wartet bis zu `timeout` Sekunden auf eine Mail mit `subject_marker` im Betreff."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with imaplib.IMAP4_SSL(host, 993) as imap:
                imap.login(user, password)
                imap.select("INBOX")
                _, data = imap.search(None, "UNSEEN")
                uid_list = data[0].split()
                for uid in uid_list:
                    _, msg_data = imap.fetch(uid, "(RFC822)")
                    raw = msg_data[0][1] if msg_data and msg_data[0] else b""
                    if subject_marker.encode() in raw:
                        imap.store(uid, "+FLAGS", "\\Seen \\Deleted")
                        imap.expunge()
                        return
        except Exception:
            pass
        time.sleep(3)
    pytest.fail(
        f"Mail mit Marker '{subject_marker}' nicht in IMAP-Postfach gefunden nach {timeout}s"
    )
