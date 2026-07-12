"""TDD RED — Issue #1235: Empfänger-Guard auch auf dem Stalwart-Pfad.

SPEC: docs/specs/modules/issue_1235_stalwart_recipient_guard.md
Root-Cause (infra MQ 48151): email.py:407 — der gesamte Empfänger-Guard liegt
unter `if "resend" in host`; Staging/Tests senden zwingend über Stalwart
(mail.henemm.com, #924/#1122) → Guard übersprungen → externe Fake-Empfänger
werden via Stalwart→Resend-Relay geleakt (henemm-infra#114).

RED-Erwartung vor dem Fix: Die Block-Fälle (AC-1/AC-2/AC-6) laufen heute am
Guard vorbei bis zum SMTP-Dial (Auth-Fehler statt OutputConfigError) → rot.
AC-3 (lokale Empfänger passieren den Guard) ist vor UND nach dem Fix grün
(Anker: kein Guard-Fehler; SMTP-Auth-Fehler mit Fake-Creds ist erlaubt).

Testmuster wie tests/tdd/test_resend_recipient_allowlist.py: echtes send()
mit Fake-Credentials, Exception einfangen — Guard-Fälle MÜSSEN eine
OutputConfigError VOR dem SMTP-Dial werfen (kein Mock).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Settings  # noqa: E402
from output.channels.email import EmailOutput  # noqa: E402
from output.channels.base import OutputConfigError  # noqa: E402


def _stalwart_output(mail_to: str = "gregor-test@henemm.com") -> EmailOutput:
    """EmailOutput auf Stalwart-Host mit Fake-Credentials — jeder Fehler NACH
    dem Guard ist ein SMTP-/Auth-Fehler, jeder Guard-Fehler eine
    OutputConfigError VOR dem Dial."""
    s = Settings(
        smtp_host="mail.henemm.com",
        smtp_port=587,
        smtp_user="doesnotexist-1235",
        smtp_pass="wrong-password-1235",
        mail_to=mail_to,
        mail_from="bot@henemm.com",
        _env_file=None,
    )
    return EmailOutput(s)


def _send_and_capture(output: EmailOutput, to: list[str]) -> Exception | None:
    try:
        output.send("GZ #1235 RED-Test", "Testkoerper", to=to)
    except Exception as exc:  # noqa: BLE001 — Ausgang wird bewusst weitergereicht
        return exc
    return None


def _assert_guard_blocked(exc: Exception | None, case: str) -> None:
    assert isinstance(exc, OutputConfigError), (
        f"#1235 {case}: erwartet OutputConfigError des Empfänger-Guards VOR "
        f"dem SMTP-Dial, bekam: {type(exc).__name__}: {exc}"
    )


# ---------------------------------------------------------------------------
# AC-1: Stalwart + reservierte Test-Domains werden geblockt
# ---------------------------------------------------------------------------


class TestAC1StalwartBlocksReservedTestDomains:
    @pytest.mark.parametrize("addr", [
        "test@example.com",
        "e@x.invalid",
    ])
    def test_reserved_test_domain_blocked_on_stalwart(self, addr):
        """AC-1: GIVEN Stalwart-Host + Empfänger auf RFC-2606-reservierter
        Test-Domain (die realen Leck-Adressen) / WHEN send() aufgerufen wird /
        THEN OutputConfigError VOR dem SMTP-Dial."""
        exc = _send_and_capture(_stalwart_output(), to=[addr])
        _assert_guard_blocked(exc, f"AC-1 {addr}")


# ---------------------------------------------------------------------------
# AC-2: Stalwart + externe (nicht-lokale) Empfänger werden geblockt
# ---------------------------------------------------------------------------


class TestAC2StalwartBlocksExternalRecipients:
    def test_external_real_domain_blocked_on_stalwart(self):
        """AC-2: GIVEN Stalwart-Host + externer echter Empfänger
        (user@gmail.com) / WHEN send() läuft / THEN blockt der Guard —
        Staging/Test-Pfade dürfen NIE die Außenwelt anschreiben (Stalwart
        relayt extern an Resend, infra#114)."""
        exc = _send_and_capture(_stalwart_output(), to=["user@gmail.com"])
        _assert_guard_blocked(exc, "AC-2 user@gmail.com")


# ---------------------------------------------------------------------------
# AC-3: Stalwart + lokale Empfänger passieren den Guard (Anker, grün vor+nach)
# ---------------------------------------------------------------------------


class TestAC3StalwartAllowsLocalRecipients:
    @pytest.mark.parametrize("addr", [
        "gregor-test@henemm.com",
        "gregor-staging@henemm.com",
        "gregor-test+e2e@henemm.com",
    ])
    def test_local_recipient_passes_guard(self, addr):
        """AC-3: GIVEN Stalwart-Host + lokaler henemm.com-Empfänger (inkl.
        Plus-Adresse) / WHEN send() läuft / THEN wirft der Guard NICHT —
        ein SMTP-/Auth-Fehler (Fake-Creds) ist der erwartete Ausgang und
        beweist, dass der Guard passiert wurde. Zustell-Postfächer der
        Validatoren müssen funktionsfähig bleiben."""
        exc = _send_and_capture(_stalwart_output(), to=[addr])
        assert not isinstance(exc, OutputConfigError), (
            f"AC-3 {addr}: lokaler Empfänger darf auf dem Stalwart-Pfad "
            f"NICHT vom Guard geblockt werden, aber: {exc}"
        )

    @pytest.mark.parametrize("addr", [
        "GREGOR-TEST@HENEMM.COM",                     # Case-Variante
        "gregor-test@henemm.com.",                    # Trailing-Dot-FQDN
        '"Gregor Test" <gregor-test@henemm.com>',     # gequoteter Anzeigename
    ])
    def test_local_recipient_variants_pass_guard(self, addr):
        """AC-6 (Allow-Richtung, Adversary F001): GIVEN Stalwart-Host + eine
        REINE lokale Empfänger-Variante (nur Case / nur Trailing-Dot / nur
        Anzeigename, kein externer Kandidat) / WHEN send() läuft / THEN wirft
        der Guard NICHT — die Normalisierung (lower/rstrip('.')/parseaddr)
        muss diese Formen als lokal erkennen. Regressionsschutz für die vom
        Adversary manuell verifizierte, aber bis dahin ungetestete
        Allow-Richtung von AC-6."""
        exc = _send_and_capture(_stalwart_output(), to=[addr])
        assert not isinstance(exc, OutputConfigError), (
            f"AC-6-Allow {addr!r}: reine lokale Variante darf NICHT geblockt "
            f"werden, aber: {exc}"
        )


# ---------------------------------------------------------------------------
# AC-6: Bypass-Härtung auch auf dem Stalwart-Pfad (#1147-F-Serie-Muster)
# ---------------------------------------------------------------------------


class TestAC6StalwartGuardBypassHardening:
    @pytest.mark.parametrize("addr", [
        "Test User <TEST@EXAMPLE.COM.>",          # Anzeigename + Case + Trailing-Dot
        "gregor-test@henemm.com;evil@example.com",  # Mischliste: EIN externer Kandidat reicht zum Block
        '"x@henemm.com" <real@gmail.com>',        # lokal aussehender Anzeigename, externe Adresse
        "user@HENEMM.COM.evil.org",               # henemm.com nur als Substring-Präfix der Fremd-Domain
    ])
    def test_bypass_variants_blocked_on_stalwart(self, addr):
        """AC-6: GIVEN bekannte Umgehungs-Varianten (Case, Trennzeichen-
        Listen, Anzeigename-Tricks, Domain-Suffix-Tricks) auf dem
        Stalwart-Pfad / WHEN send() läuft / THEN blockt der Guard."""
        exc = _send_and_capture(_stalwart_output(), to=[addr])
        _assert_guard_blocked(exc, f"AC-6 {addr!r}")
