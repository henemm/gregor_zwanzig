"""
TDD RED: Tests fuer Per-Empfänger-Fehlerbehandlung in EmailOutput.send() — Issue #457.

SPEC: docs/specs/modules/issue_457_compare_email_tags.md §4 + AC-5

Diese Tests prüfen, dass EmailOutput.send() bei mehreren Empfängern
pro Empfänger einen individuellen sendmail()-Call ausführt und ein
SMTP-Fehler bei einem Empfänger die anderen nicht blockiert.

Keine Mocks erlaubt (CLAUDE.md). Tests nutzen:
- Protocol-Konformitätsprüfung (Signatur)
- @pytest.mark.email für echte SMTP-Verifikation

Issue #1196 S1 AC-6: Die frueheren Quelltext-Strukturtests (`inspect.getsource`)
sind entfernt, s. Klassen-Docstring unten.
"""
import pytest


class TestPerRecipientSend:
    """
    AC-5: Fehler beim Versand einzelner Empfänger blockieren nicht die anderen.
    SPEC §4: Per-Empfänger-Loop mit individuellem try/except.

    Issue #1196 S1 AC-6: Die zwei ehemaligen Quelltext-Textprüfungen
    (`inspect.getsource(EmailOutput.send)` auf Teilstrings) wurden entfernt —
    verbotene Verhaltensnachweisform (CLAUDE.md „Zwei Schichten"), und das
    Verhalten selbst ist laengst umgezogen nach
    `src/output/channels/email.py::_dial_and_send` (isolate_per_recipient).
    Der echte Verhaltensnachweis existiert bereits:
    `tests/tdd/test_mail_transport_dial_behaviour.py::
    test_ac2_primaerweg_stellt_trotz_einer_ablehnung_an_die_uebrigen_zu`.
    """

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
