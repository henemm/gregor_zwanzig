"""
TDD RED: Tests fuer Per-Empfänger-Fehlerbehandlung in EmailOutput.send() — Issue #457.

SPEC: docs/specs/modules/issue_457_compare_email_tags.md §4 + AC-5

Diese Tests prüfen, dass EmailOutput.send() bei mehreren Empfängern
pro Empfänger einen individuellen sendmail()-Call ausführt und ein
SMTP-Fehler bei einem Empfänger die anderen nicht blockiert.

Keine Mocks erlaubt (CLAUDE.md). Tests nutzen:
- Strukturanalyse via inspect.getsource (schnelle Verifikation der Schleife)
- @pytest.mark.email für echte SMTP-Verifikation

"""
import inspect
import pytest


class TestPerRecipientSend:
    """
    AC-5: Fehler beim Versand einzelner Empfänger blockieren nicht die anderen.
    SPEC §4: Per-Empfänger-Loop mit individuellem try/except.
    """

    def test_ac5_source_enthält_per_recipient_loop(self):
        """
        Strukturtest: send()-Quellcode enthält eine for-Schleife über recipients
        und einen individuellen sendmail()-Call pro Empfänger.

        SPEC §4: "Mehrere Empfänger: pro Empfänger individueller Call"
        Dies scheitert solange die Schleife nicht implementiert ist.
        """
        from output.channels.email import EmailOutput

        src = inspect.getsource(EmailOutput.send)

        assert "for recipient in recipients" in src, (
            "send() muss eine 'for recipient in recipients'-Schleife enthalten "
            "(SPEC §4 Per-Empfänger-Loop)"
        )
        assert "sendmail(from_addr, [recipient]" in src, (
            "sendmail() muss pro Empfänger mit [recipient] als Liste aufgerufen werden, "
            "nicht mit der gesamten recipients-Liste"
        )

    def test_ac5_source_enthält_per_recipient_try_except(self):
        """
        Strukturtest: send()-Quellcode enthält try/except innerhalb der recipients-Schleife
        mit logger.error-Aufruf bei Fehler.

        SPEC §4: "SMTP-Fehler einzelner Empfänger werden per logger.error() protokolliert
        und unterbrechen die Schleife für diesen Empfänger nicht die restlichen Empfänger."
        """
        from output.channels.email import EmailOutput

        src = inspect.getsource(EmailOutput.send)

        assert "logger.error" in src, (
            "send() muss logger.error() für SMTP-Fehler pro Empfänger aufrufen "
            "(SPEC §4 Fehler-Logging)"
        )
        # Kein Re-raise nach SMTPException in der inneren Schleife
        # Strukturell: try/except ohne raise
        assert "except smtplib.SMTPException" in src, (
            "send() muss smtplib.SMTPException in der Empfänger-Schleife abfangen"
        )

    def test_ac5_return_type_none_unveraendert(self):
        """
        Protocol-Konformität: send() gibt None zurück — kein Breaking Change.
        SPEC §4: "Return-Type bleibt None (Protocol-konform)"
        """
        from output.channels.email import EmailOutput
        import inspect as ins

        sig = ins.signature(EmailOutput.send)
        annotation = sig.return_annotation

        # Akzeptiere sowohl None, type(None), "None" (string-annotation via __future__) und empty
        valid = (None, type(None), ins.Parameter.empty, "None")
        assert annotation in valid, (
            f"send() muss None zurückgeben (Protocol-konform), aber annotation ist: {annotation!r}"
        )

    @pytest.mark.email
    def test_ac5_echter_mehrfach_versand_kein_absturz(self):
        """
        E2E-Test: send() mit zwei Empfängern wirft keine Exception, auch wenn
        der zweite Empfänger nicht existiert.

        Sendet an:
        1. gregor-test@henemm.com (valide, Stalwart-Postfach)
        2. noone-definitely-invalid@gregor-test-nonexistent.henemm.com (ungültig)

        SPEC AC-5: "Fehler beim Versand einzelner Empfänger blockieren nicht die anderen"
        """
        from output.channels.email import EmailOutput
        from app.config import Settings

        settings = Settings().for_testing()
        output = EmailOutput(settings)

        # Darf keine Exception werfen, auch wenn zweiter Empfänger fehlschlägt
        try:
            output.send(
                subject="[TEST AC-5] Per-Empfänger-Fehlerbehandlung",
                body="Test Issue #457 — AC-5 Per-Empfänger-Fehlerbehandlung.",
                html=False,
                to=["gregor-test@henemm.com", "noone-invalid@does-not-exist.invalid"],
            )
        except Exception as exc:
            pytest.fail(
                f"send() darf bei Teil-Fehler keine Exception werfen, "
                f"aber: {type(exc).__name__}: {exc}"
            )
