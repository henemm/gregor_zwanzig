"""TDD RED — Issue #1412 Scheibe S1: Empfänger-Guard am tatsächlich benutzten
Postausgang (Python-Seite).

SPEC: docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md
      (AC-1, AC-2, AC-2b, AC-6)

Heute entscheidet EmailOutput.send() die Empfänger-Zulässigkeit EINMAL, VOR
dem Aufbau der Nachricht und VOR der Retry-/Fallback-Schleife
(email.py:415-514), gegen den fest konfigurierten `self._host` (Primärhost).
Weder die primäre Retry-Schleife (:536) noch die beiden Fallback-Zweige
(:580-596, :622-635) werten den Guard je Dial-Versuch neu aus. Fix (S1): die
Guard-Logik wandert in eine neue `_dial_and_send(host, ...)` und wird je
tatsächlichem Verbindungsversuch mit dem für DIESEN Versuch gültigen Host
aufgerufen — Primärschleife mit `self._host`, beide Fallback-Zweige mit
`self._fallback_host` (dort neu: Allowlist ODER lokal zustellbar, PO-
Entscheidung 2026-07-29).

Nachweisform: Sink am Transportrand auf `smtplib.SMTP` (Vorbild
test_telegram_test_mode_guard.py:57-77 — Fake-Klasse statt echter
Verbindung) kombiniert mit dem Sentinel-Prinzip aus
test_telegram_test_isolation.py: Stille im Aufzeichnungs-Log beweist "kein
Verbindungsversuch", ein Eintrag beweist "Versuch fand tatsächlich statt".
Kein Netz, kein Mock-Theater — der Sink ersetzt nur den Draht, nie die
geprüfte Guard-Logik selbst.

BEFUND zu AC-1 (siehe Testklasse unten für Details): AC-1s Given/When/Then
("Empfänger weder verifiziert noch lokal → geht heute über den Ersatzweg
ungeprüft durch") lässt sich über `EmailOutput.send()` NICHT als RED
reproduzieren — empirisch geprüft. Der heutige Guard wertet EINMAL, VOR
JEDEM Dial (egal ob Primär oder Fallback), aus: ein Empfänger, der weder
Allowlist- noch Lokal-Kriterium erfüllt, wird deshalb SCHON HEUTE
vollständig blockiert, bevor überhaupt ein Verbindungsversuch stattfindet
— nur eben nicht "am tatsächlich benutzten Postausgang" im Sinn der Spec,
sondern strukturell VOR jedem Postausgang. Die tatsächliche, von der
Analyse als "live" bezeichnete Lücke betrifft ausschließlich
ALLOWLISTED-aber-externe Empfänger (AC-2) — die dürfen nach PO-Entscheidung
ausdrücklich weiter über den Ersatzweg zugestellt werden, das ist also kein
Blockfall. Der AC-1-Test unten bleibt als Regressionsschutz für die
"vollständig blockiert"-Eigenschaft bestehen, ist aber kein RED-Nachweis.
"""
from __future__ import annotations

import json
import smtplib
import time
from pathlib import Path

import pytest

from app.config import Settings
from output.channels.base import OutputConfigError
from output.channels.email import EmailOutput

# Stalwart-artiger Fallback-Host — bewusst OHNE "resend" im Namen (Vorgabe
# der Aufgabenstellung).
FALLBACK_HOST = "mail.henemm.com"
# Primärhost, der künstlich zum Scheitern gebracht wird UND die
# Allowlist-Verzweigung triggert (email.py:428 prüft nur auf den Substring
# "resend" — kein Bezug zur echten Resend-Domain, die der
# Prod-Send-Gate-Hook als Bash-Literal blockt).
FAILING_RESEND_PRIMARY = "primary-resend-fake.invalid"
# Primärhost ohne "resend" im Namen — triggert die Lokal-Verzweigung
# (email.py:476).
FAILING_LOCAL_PRIMARY = "primary-stalwart-fake.invalid"


# ---------------------------------------------------------------------------
# Sink am Transportrand auf smtplib.SMTP
# ---------------------------------------------------------------------------

class _FakeSMTPConnection:
    """Ersetzt eine echte SMTP-Verbindung vollständig — kein Netz."""

    def __init__(self, calls: list[dict], host: str) -> None:
        self._calls = calls
        self._host = host

    def __enter__(self) -> "_FakeSMTPConnection":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def starttls(self) -> None:
        return None

    def login(self, user, password) -> None:
        return None

    def sendmail(self, from_addr, to_addrs, msg) -> None:
        self._calls.append({"host": self._host, "from": from_addr, "to": tuple(to_addrs)})


class _RecordingSMTP:
    """Sink am Transportrand (Vorbild test_telegram_test_mode_guard.py:
    57-77): ersetzt smtplib.SMTP komplett. `failing_hosts` simuliert einen
    unerreichbaren Host (OSError beim Verbindungsaufbau, wie ein echter
    Primär-Ausfall) — jeder andere Host liefert eine "erfolgreiche"
    Verbindung und zeichnet den Zustellversuch auf. Sentinel-Prinzip
    (test_telegram_test_isolation.py): Stille im calls-Log beweist "kein
    Versuch", ein Eintrag beweist "Versuch fand tatsächlich statt"."""

    def __init__(self, calls: list[dict], failing_hosts=()) -> None:
        self.calls = calls
        self._failing_hosts = frozenset(failing_hosts)

    def __call__(self, host, port, *a, **kw):
        if host in self._failing_hosts:
            raise OSError(f"[Errno 111] Connection refused (fake): {host}:{port}")
        return _FakeSMTPConnection(self.calls, host)


@pytest.fixture
def smtp_sink(monkeypatch):
    """Installiert den Sink und neutralisiert den Retry-Backoff (5s/15s/30s
    real würden jeden Fallback-Test um ~50s verzögern) — reine
    Testgeschwindigkeit, greift nicht in die geprüfte Guard-/
    Fallback-Logik ein."""
    calls: list[dict] = []

    def _install(failing_hosts=()) -> list[dict]:
        monkeypatch.setattr(
            smtplib, "SMTP", _RecordingSMTP(calls, failing_hosts=failing_hosts)
        )
        monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
        return calls

    return _install


# ---------------------------------------------------------------------------
# Settings-Aufbau
# ---------------------------------------------------------------------------

def _resend_primary_settings(mail_to: str, **overrides) -> Settings:
    """EmailOutput-Settings mit resend-artigem Primärhost (Allowlist-Zweig,
    email.py:428) und Stalwart-artigem Fallback (kein "resend" im Namen).

    `Settings._resend_default_deny` (#1122, config.py:194-217) lenkt JEDEN
    "resend"-Host UNTER PYTEST zwingend um (Docstring: "pytest-Prozesse sind
    auch MIT Token gesperrt") — deshalb Konstruktion mit einem neutralen
    Platzhalter-Host, danach `model_copy(update=...)`, das laut Docstring
    bewusst "Validatoren umgeht" (Vorbild test_927_smtp_fallback.py,
    TestAC5StagingGuardUnchanged)."""
    defaults = dict(
        smtp_host=FALLBACK_HOST,  # Platzhalter — wird unten überschrieben
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_fake_for_tdd",
        mail_to=mail_to,
        mail_from="gregor_zwanzig@henemm.com",
        imap_host=FALLBACK_HOST,
        imap_user="gregor_zwanzig",
        imap_pass="fake-imap-pass",
    )
    defaults.update(overrides)
    settings = Settings(**defaults)
    return settings.model_copy(update={"smtp_host": FAILING_RESEND_PRIMARY})


def _verified_profile(data_root: Path, mail_to: str) -> None:
    """Registriert `mail_to` als bestätigte (email_verified_at gesetzt)
    Profiladresse im aktuell isolierten Datenwurzel-Verzeichnis (autouse-
    Fixture tests/conftest.py `_isolate_data_root`, Issue #1133). Vorbild:
    test_issue_1147_resend_recipient_invariant.py."""
    user_dir = data_root / "users" / "fixture-verified"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(
        json.dumps({"mail_to": mail_to, "email_verified_at": "2026-07-10T12:00:00Z"}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# AC-1 — weder Profil noch lokal: Ersatzweg blockt
# ---------------------------------------------------------------------------

class TestAC1UnauthorizedRecipientBlockedOnFallback:
    """AC-1: Empfänger weder verifiziert noch lokal → Ersatzweg blockt.

    BEFUND (kein RED, s. Moduldocstring): EmailOutput.send() wertet den
    Guard heute EINMAL vor JEDEM Dial (email.py:415-514, vor dem
    Nachrichtenaufbau und vor der Retry-Schleife) — ein Empfänger, der
    weder Allowlist- noch Lokal-Kriterium erfüllt, wird deshalb SCHON HEUTE
    vollständig blockiert, BEVOR überhaupt ein Verbindungsversuch (Primär
    ODER Fallback) stattfindet. Der Sink bleibt daher auch VOR dem Fix
    vollständig still — dieser Test ist folglich KEIN RED-Nachweis, sondern
    eine Regressionsschutz-Formulierung von AC-1s SOLL-Zustand (Empfänger
    bleibt blockiert), die schon heute erfüllt ist. Empirisch verifiziert
    (Fund an main gemeldet)."""

    def test_neither_verified_nor_local_recipient_stays_blocked(self, smtp_sink):
        calls = smtp_sink(failing_hosts={FAILING_RESEND_PRIMARY})
        settings = _resend_primary_settings(
            mail_to="outsider@notaprofile-example-abc.net"
        )
        output = EmailOutput(settings)

        with pytest.raises(OutputConfigError):
            output.send("S1 AC-1", "Testkoerper")

        assert calls == [], (
            "AC-1: kein Verbindungsversuch (weder primär noch Ersatzweg) "
            f"darf stattfinden, gesehen: {calls!r}"
        )


# ---------------------------------------------------------------------------
# AC-2 — verifizierte externe Adresse: Ersatzweg bleibt nutzbar
# ---------------------------------------------------------------------------

class TestAC2VerifiedExternalRecipientStillDeliveredViaFallback:
    """AC-2: Verifizierte externe Profil-Adresse (Regelfall der realen
    Nutzer, beide haben mail_to auf gmail.com) — Ersatzweg bleibt nutzbar.

    Regressionsschutz, KEIN RED-Nachweis: dieser Fall ist bereits heute
    grün — die Allowlist-Prüfung lässt den Empfänger schon beim einmaligen
    Upfront-Check durch, der Fallback-Dial läuft danach ungeprüft mit. Das
    ist exakt die von der Analyse als "live" beschriebene Situation, die
    per PO-Entscheidung (2026-07-29) ausdrücklich SANKTIONIERT bleibt."""

    def test_verified_recipient_delivered_via_fallback_after_primary_failure(
        self, smtp_sink,
    ):
        from app import loader as app_loader

        calls = smtp_sink(failing_hosts={FAILING_RESEND_PRIMARY})
        recipient = "verified-user@gmail.com"
        _verified_profile(app_loader.get_data_root(), recipient)

        settings = _resend_primary_settings(mail_to=recipient)
        output = EmailOutput(settings)

        output.send("S1 AC-2", "Testkoerper")

        assert calls == [
            {"host": FALLBACK_HOST, "from": settings.mail_from, "to": (recipient,)}
        ], f"AC-2: Zustellversuch über den Ersatzweg erwartet, gesehen: {calls!r}"


# ---------------------------------------------------------------------------
# AC-2b — lokaler, unverifizierter Empfänger: heutiges Verhalten bleibt
# ---------------------------------------------------------------------------

class TestAC2bLocalRecipientStillDeliveredViaFallback:
    """AC-2b: Lokaler (@henemm.com) Empfänger, in keinem Profil bestätigt —
    heutiges Lokal-Verhalten bleibt unverändert erhalten (insb. für die
    Test-Postfächer gregor-test@/gregor-staging@).

    Primärhost ist hier NICHT resend-artig (Lokal-Zweig, email.py:476) —
    kein model_copy-Bypass nötig, da `_resend_default_deny` nur
    "resend"-Hosts umlenkt."""

    def test_local_recipient_delivered_via_fallback_after_primary_failure(
        self, smtp_sink,
    ):
        calls = smtp_sink(failing_hosts={FAILING_LOCAL_PRIMARY})
        recipient = "gregor-test@henemm.com"

        settings = Settings(
            smtp_host=FAILING_LOCAL_PRIMARY,
            smtp_port=587,
            smtp_user="doesnotmatter",
            smtp_pass="doesnotmatter",
            mail_to=recipient,
            mail_from="gregor_zwanzig@henemm.com",
            imap_host=FALLBACK_HOST,
            imap_user="gregor_zwanzig",
            imap_pass="fake-imap-pass",
        )
        output = EmailOutput(settings)

        output.send("S1 AC-2b", "Testkoerper")

        assert calls == [
            {"host": FALLBACK_HOST, "from": settings.mail_from, "to": (recipient,)}
        ], f"AC-2b: Zustellversuch über den Ersatzweg erwartet, gesehen: {calls!r}"


# ---------------------------------------------------------------------------
# AC-6 — Normalbetrieb: kein Ausweichen, unverändertes Verhalten
# ---------------------------------------------------------------------------

class TestAC6NormalOperationUnchanged:
    """AC-6: Primärer Postausgang funktioniert — kein Ausweichen, keine
    Guard-Änderung gegenüber heute.

    Regressionsschutz, bereits heute grün."""

    def test_single_primary_delivery_no_fallback_touched(self, smtp_sink):
        calls = smtp_sink()  # kein Host scheitert
        recipient = "gregor-test@henemm.com"
        settings = Settings(
            smtp_host=FALLBACK_HOST,  # funktionierender Primärhost
            smtp_port=587,
            smtp_user="doesnotmatter",
            smtp_pass="doesnotmatter",
            mail_to=recipient,
            mail_from="gregor_zwanzig@henemm.com",
        )
        output = EmailOutput(settings)

        output.send("S1 AC-6", "Testkoerper")

        assert calls == [
            {"host": FALLBACK_HOST, "from": settings.mail_from, "to": (recipient,)}
        ], (
            "AC-6: genau EIN Zustellversuch über den Primärhost erwartet, "
            f"gesehen: {calls!r}"
        )
