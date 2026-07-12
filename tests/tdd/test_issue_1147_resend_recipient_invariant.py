"""TDD RED — Issue #1147: dritte, empfaengerseitige Resend-Guard-Linie.

Spec: docs/specs/modules/issue_1147_resend_recipient_invariant.md (AC-1..AC-7)

Hintergrund: Die bestehenden Guards (#1122, #924, #879) klassifizieren "Test"
ausschliesslich absender-/prozessseitig (is_test_mode, GZ_ENV, pytest-Kontext,
GZ_RESEND_ALLOWED) und lassen sich mit einem Kunst-User + internem Prod-Port
umgehen -- genau das war der 11. Vorfall am 2026-07-08. Diese Testdatei belegt
die fehlende dritte Linie: ein Guard, der ausschliesslich die FINALE
Empfaengerliste gegen Test-Postfaecher prueft, unabhaengig von jedem
Prozess-Signal.

Konstruktion: Settings() lenkt unter pytest jeden Resend-Host automatisch weg
(#1122 Default-Deny-Validator laeuft im __init__/model_validator). Um trotzdem
eine EmailOutput-Instanz mit einem ECHTEN Resend-Host zu bekommen -- wie im
11. Vorfall -- wird der Validator per model_copy() umgangen (model_copy()
fuehrt KEINE Validatoren aus). Vorbild: tests/unit/test_no_resend_for_tests.py
und tests/tdd/test_issue_1122_resend_default_deny.py (AC-6, model_copy-Bypass).
is_test_mode bleibt dabei bewusst False und env bleibt "production" (Default),
damit auch die #879-/#924-Guards in EmailOutput.__init__ NICHT greifen --
exakt die Konstellation ohne jedes Test-Prozess-Signal.

KEIN Mock: send() laeuft bis zum echten SMTP-Dial gegen den echten
Resend-Produktivendpunkt (smtp.resend.com:587) mit einer bewusst ungueltigen
Fake-Passphrase. Das reproduziert den heutigen Fehlerpfad (Auth-Fehler statt
Guard) OHNE eine echte Mail zu verschicken oder Resend-Kontingent zu
verbrauchen (empirisch gemessen: SMTPAuthenticationError nach ~1s, kein
Retry-Loop, siehe send()-Code). AC-1/AC-2/AC-6 sind daher deterministisch rot:
der erwartete OutputConfigError (#1147) existiert noch nicht, stattdessen
scheitert der echte Dial-Versuch anders.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from output.channels.base import OutputConfigError  # noqa: E402
from output.channels.email import EmailOutput  # noqa: E402

_MAIN_ENV = Path("/home/hem/gregor_zwanzig/.env")


def _load_main_env() -> None:
    """Laedt SMTP-/IMAP-Test-Creds aus der Hauptrepo-.env (Worktree hat keine eigene)."""
    if not _MAIN_ENV.exists():
        return
    for line in _MAIN_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_main_env()


def _resend_bypass_settings(*, host: str = "smtp.resend.com") -> Settings:
    """Resend-Settings, die den #1122-Konstruktor-Validator via model_copy() umgehen.

    is_test_mode bleibt False, env bleibt "production" (Default) -- genau die
    Konstellation ohne jedes Prozess-Test-Signal (11. Vorfall, Issue #1147).
    """
    base = Settings(
        smtp_host="mail.henemm.com",  # unkritischer Platzhalter fuer den __init__-Validator
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_1147_test_invalid_key",
        mail_to="user@example.com",
        mail_from="bot@henemm.com",
        _env_file=None,
    )
    return base.model_copy(update={"smtp_host": host, "is_test_mode": False})


def _make_output(*, host: str = "smtp.resend.com") -> EmailOutput:
    s = _resend_bypass_settings(host=host)
    assert "resend" in (s.smtp_host or "").lower(), (
        "Testaufbau defekt: Settings muss einen Resend-Host halten"
    )
    assert s.is_test_mode is False, (
        "Testaufbau defekt: is_test_mode muss False sein (kein Prozess-Test-Signal)"
    )
    assert (s.env or "").lower() != "staging", (
        "Testaufbau defekt: env darf nicht 'staging' sein"
    )
    return EmailOutput(s)


def _write_allowlist_fixture(*addresses: str) -> None:
    """Issue #1219 Nachtrag (Adversary F002): registriert jede Adresse in
    `addresses` als `mail_to` eines eigenen Fixture-Nutzerprofils UNTER DEM
    von der autouse-Isolation (Issue #1133, `tests/conftest.py`) bereits
    gesetzten `app.loader._DATA_ROOT`. Der Produktions-Guard loest sein
    `data_dir` seit der F002-Nachbesserung ueber `app.loader.get_data_root()`
    auf (Prioritaet `_DATA_ROOT` > `GZ_DATA_DIR` > Default) -- ein eigener
    `tmp_path`/`GZ_DATA_DIR`-Override wuerde vom bereits gesetzten
    `_DATA_ROOT` ignoriert. Ohne diese Registrierung wuerden diese
    "kein Guard-Block"-Tests seit der Allowlist-Umstellung (#1219)
    fehlschlagen, weil eine rein fiktive @example.com-Adresse zu keinem
    echten Profil gehoert -- die Tests wollen aber gezielt False-Positives
    der PARSING-/Normalisierungs-Pipeline pruefen, nicht die
    Allowlist-Mitgliedschaft selbst."""
    from app import loader as app_loader

    data_root = app_loader.get_data_root()
    for i, addr in enumerate(addresses):
        user_dir = data_root / "users" / f"fixture-{i}"
        user_dir.mkdir(parents=True, exist_ok=True)
        # Nachtrag Issue #1235: seit der #1219-Verified-Scheibe nimmt
        # _load_resend_allowlist() nur Profile MIT gesetztem
        # email_verified_at auf -- ohne das Feld war diese Fixture wirkungslos
        # und die "kein Guard-Block"-Negativfaelle strukturell unerfuellbar
        # (vorbestehend rot, unabhaengig vom #1235-Stalwart-Guard).
        (user_dir / "user.json").write_text(
            json.dumps({
                "mail_to": addr,
                "email_verified_at": "2026-07-10T12:00:00Z",
            }),
            encoding="utf-8",
        )


def _assert_1147_guard_fired(exc: Exception | None, ac_label: str) -> None:
    """Gemeinsame Assertion fuer AC-1/AC-2/AC-6: nur OutputConfigError('#1147')
    zaehlt als gruen, jeder andere Ausgang (kein Wurf ODER anderer Fehlertyp)
    ist ein aussagekraeftiger RED-Fehlschlag."""
    if exc is None:
        pytest.fail(
            f"{ac_label} (Issue #1147): send() ist durchgelaufen OHNE zu werfen -- "
            "Guard fehlt UND der Dial-Versuch war unerwartet erfolgreich."
        )
    if isinstance(exc, OutputConfigError):
        assert "1147" in str(exc), (
            f"{ac_label}: OutputConfigError muss Issue #1147 referenzieren, war: {exc}"
        )
        return
    pytest.fail(
        f"{ac_label} (Issue #1147, RED erwartet): der Empfaenger-Guard fehlt noch -- "
        f"send() lief bis zum echten SMTP-Dial und warf {type(exc).__name__} "
        f"statt OutputConfigError('#1147'): {exc}"
    )


def _send_and_capture(output: EmailOutput, to: list[str]) -> Exception | None:
    try:
        output.send("GZ #1147 RED-Test", "Testkoerper", to=to)
    except Exception as exc:  # noqa: BLE001 - Ausgang wird bewusst weitergereicht
        return exc
    return None


# ---------------------------------------------------------------------------
# AC-1: Einzelner Test-Empfaenger bei Resend-Host wird blockiert
# ---------------------------------------------------------------------------


class TestAC1SingleTestMailboxBlocked:
    def test_resend_send_to_gregor_test_raises_1147(self):
        """AC-1: GIVEN EmailOutput mit echtem Resend-Host (kein Prozess-Test-
        Signal) / WHEN send(to=["gregor-test@henemm.com"]) / THEN wirft send()
        eine OutputConfigError mit Verweis auf Issue #1147, kein SMTP-Dial."""
        output = _make_output()
        exc = _send_and_capture(output, to=["gregor-test@henemm.com"])
        _assert_1147_guard_fired(exc, "AC-1")


# ---------------------------------------------------------------------------
# AC-2: Gemischte Empfaengerliste schlaegt komplett fehl
# ---------------------------------------------------------------------------


class TestAC2MixedRecipientListBlocked:
    def test_resend_send_mixed_recipients_raises_1147(self):
        """AC-2: GIVEN Resend-EmailOutput / WHEN send() mit einer gemischten
        Liste (echter Empfaenger + gregor-test@henemm.com) / THEN schlaegt der
        komplette Sendevorgang hart fehl -- keine Teil-Zustellung."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=["real-user@example.com", "gregor-test@henemm.com"]
        )
        _assert_1147_guard_fired(exc, "AC-2")


# ---------------------------------------------------------------------------
# AC-6 (Python-Teil): Case-/Name-Form-Robustheit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,to,case_label",
    [
        ("SMTP.RESEND.COM", ["gregor-test@henemm.com"], "host-grossschreibung"),
        ("smtp.resend.com", ["GREGOR-TEST@HENEMM.COM"], "adresse-grossschreibung"),
        (
            "smtp.resend.com",
            ['"Gregor Test" <gregor-test@henemm.com>'],
            "adresse-name-form",
        ),
    ],
)
class TestAC6CaseAndNameFormRobustness:
    def test_variant_blocked(self, host, to, case_label):
        """AC-6 (Python-Teil): GIVEN Host-/Adress-Schreibweisen variieren
        (Grossschreibung, Name-Form) / WHEN send() aufgerufen wird / THEN wird
        trotzdem als Resend-Host bzw. Test-Postfach erkannt und blockiert --
        case-insensitiv und Name-Form-robust."""
        output = _make_output(host=host)
        exc = _send_and_capture(output, to=to)
        _assert_1147_guard_fired(exc, f"AC-6[{case_label}]")


# ---------------------------------------------------------------------------
# AC-4: Regressionsschutz -- reine Nicht-Test-Empfaenger unangetastet
# ---------------------------------------------------------------------------


class TestAC4NonTestRecipientUnaffected:
    def test_resend_send_to_real_user_no_1147_guard(self):
        """AC-4: GIVEN Resend-Host / WHEN send() ausschliesslich
        Nicht-Test-Empfaenger enthaelt / THEN greift die neue #1147-Invariante
        NICHT -- andere Fehler (z.B. Auth-Fehler gegen den echten
        Resend-Dial) sind hier unschaedlich und werden nur auf Abwesenheit
        des #1147-Textes geprueft.

        Nachtrag Issue #1219: seit der Allowlist-Umstellung muss die
        Empfaengeradresse zu einem echten (Fixture-)Nutzerprofil gehoeren,
        sonst wuerde sie unabhaengig von dieser Pruefung blockiert -- das
        waere ein legitimer NEUER Guard-Grund, kein #1147-Parsing-Fehler.
        Das Fixture-Profil landet im autouse-isolierten `_DATA_ROOT` (Issue
        #1133/#1219 Adversary F002), nicht in einem eigenen `GZ_DATA_DIR`.

        Nachtrag Issue #1235: Fixture-Domain von example.com (RFC-2606, seit
        #1219 immer geblockt -> Negativfall unerfuellbar) auf nicht-
        reservierte Domain umgestellt.
        """
        _write_allowlist_fixture("someone@kunde-real.de")
        output = _make_output()
        exc = _send_and_capture(output, to=["someone@kunde-real.de"])
        if isinstance(exc, OutputConfigError):
            assert "1147" not in str(exc), (
                f"AC-4: #1147-Guard darf bei reinem Nicht-Test-Empfaenger "
                f"nicht greifen: {exc}"
            )
        # Netzwerk-/Auth-Fehler gegen den echten Resend-Dial sind hier erwartet
        # und fuer diese Assertion irrelevant -- geprueft wird nur die
        # Abwesenheit des #1147-Guards.


# ---------------------------------------------------------------------------
# Fix-Loop 1 -- F001/F002 (Adversary Runde 2, docs/artifacts/
# fix-1147-resend-test-harness/adversary-dialog.md): Normalisierungs-Bypaesse
# des Empfaenger-Guards.
# ---------------------------------------------------------------------------


class TestF001PlusAddressingBypass:
    def test_resend_send_to_plus_addressed_test_mailbox_raises_1147(self):
        """F001: GIVEN Resend-EmailOutput / WHEN send(to=
        ["gregor-test+foo@henemm.com"]) / THEN wirft send() trotz
        Plus-Adressierung OutputConfigError #1147 -- der lokale Teil muss vor
        dem Vergleich am ersten '+' gekappt werden."""
        output = _make_output()
        exc = _send_and_capture(output, to=["gregor-test+foo@henemm.com"])
        _assert_1147_guard_fired(exc, "F001")


class TestF002CommaAndRawStringBypass:
    def test_resend_send_comma_embedded_recipient_raises_1147(self):
        """F002a: GIVEN Resend-EmailOutput / WHEN send() ein Listenelement mit
        eingebettetem Komma erhaelt ("gregor-test@henemm.com,
        real@example.com") / THEN wirft send() trotzdem OutputConfigError
        #1147 -- jeder komma-getrennte Teil muss einzeln normalisiert/geprueft
        werden."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=["gregor-test@henemm.com, real@example.com"]
        )
        _assert_1147_guard_fired(exc, "F002a")

    def test_resend_send_raw_string_to_raises_1147(self):
        """F002b: GIVEN Resend-EmailOutput / WHEN send() mit `to` als rohem
        String statt Liste aufgerufen wird (to="gregor-test@henemm.com") /
        THEN wirft send() trotzdem OutputConfigError #1147 -- ein String-`to`
        darf NICHT zeichenweise iteriert werden."""
        output = _make_output()
        exc = _send_and_capture(output, to="gregor-test@henemm.com")
        _assert_1147_guard_fired(exc, "F002b")


# ---------------------------------------------------------------------------
# Fix-Loop 2 -- F003 (Adversary Runde 2, docs/artifacts/
# fix-1147-resend-test-harness/adversary-dialog.md): Trennzeichen-KLASSE, nicht
# nur Komma. Semikolon-getrennte Empfaenger-Strings (wie sie das Frontend-
# Freitextfeld erzeugt, das selbst nur an Komma splittet) umgehen den Guard.
# ---------------------------------------------------------------------------


class TestF003SemicolonSeparatorBypass:
    def test_resend_send_semicolon_embedded_recipient_raises_1147(self):
        """F003a: GIVEN Resend-EmailOutput / WHEN send() ein Listenelement mit
        eingebettetem Semikolon erhaelt ("gregor-test@henemm.com;
        real@example.com") / THEN wirft send() trotzdem OutputConfigError
        #1147 -- der Trenner-Split muss Semikolon UND Komma abdecken, nicht
        nur Komma."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=["gregor-test@henemm.com; real@example.com"]
        )
        _assert_1147_guard_fired(exc, "F003a")

    def test_resend_send_semicolon_plus_addressed_recipient_raises_1147(self):
        """F003b: GIVEN Resend-EmailOutput / WHEN ein Semikolon-getrenntes
        Element eine Plus-adressierte Test-Postfach-Variante enthaelt
        ("gregor-test+foo@henemm.com; real@example.com") / THEN wirft send()
        trotzdem OutputConfigError #1147 -- Semikolon-Split UND
        Plus-Normalisierung muessen zusammenwirken."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=["gregor-test+foo@henemm.com; real@example.com"]
        )
        _assert_1147_guard_fired(exc, "F003b")

    def test_resend_send_whitespace_embedded_recipient_raises_1147(self):
        """F003c: GIVEN Resend-EmailOutput / WHEN ein einzelnes Listenelement
        zwei durch reines Leerzeichen (kein Komma/Semikolon) getrennte
        Adressen enthaelt ("gregor-test@henemm.com real@example.com") / THEN
        wirft send() trotzdem OutputConfigError #1147 -- scheitert die
        Adress-Erkennung an einem Fragment, muss ein Whitespace-Roh-Split
        einspringen."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=["gregor-test@henemm.com real@example.com"]
        )
        _assert_1147_guard_fired(exc, "F003c")

    def test_resend_send_two_real_recipients_semicolon_separated_no_1147(self):
        """F003d (AC-4-Negativfall): GIVEN Resend-EmailOutput / WHEN ein
        Semikolon-getrenntes Element ausschliesslich zwei echte,
        nicht-Test-Adressen enthaelt ("real-a@kunde-real.de;
        real-b@kunde-real.de") / THEN greift der #1147-Guard NICHT -- der
        Trennzeichen-Fix darf keine False-Positives fuer normale Empfaenger
        erzeugen.

        Nachtrag Issue #1219: beide Adressen werden als Fixture-Nutzerprofile
        im autouse-isolierten `_DATA_ROOT` registriert (Issue #1133/#1219
        Adversary F002), damit die Allowlist-Pruefung selbst nicht greift
        und nur die Parsing-/Trennzeichen-Logik geprueft wird.

        Nachtrag Issue #1235: Fixture-Domain von example.com auf eine nicht-
        reservierte Domain umgestellt -- example.com ist RFC-2606-reserviert
        und wird vom Resend-Zweig seit #1219 IMMER geblockt; der Negativfall
        war damit konzeptionell unerfuellbar (vorbestehend rot, unabhaengig
        vom #1235-Stalwart-Guard)."""
        _write_allowlist_fixture("real-a@kunde-real.de", "real-b@kunde-real.de")
        output = _make_output()
        exc = _send_and_capture(
            output, to=["real-a@kunde-real.de; real-b@kunde-real.de"]
        )
        if isinstance(exc, OutputConfigError):
            assert "1147" not in str(exc), (
                f"F003d: #1147-Guard darf bei zwei echten, semikolon-"
                f"getrennten Empfaengern nicht greifen: {exc}"
            )


# ---------------------------------------------------------------------------
# Fix-Loop 3 -- F004 (Adversary Runde 3, docs/artifacts/
# fix-1147-resend-test-harness/adversary-dialog.md): der reine
# Trennzeichen-Split ([,;]) zerreisst eine gequotete Anzeigename-Form MIT
# eingebettetem Komma/Semikolon (z.B. '"Foo; Bar" <addr>') VOR dem Parsen --
# das Semikolon im Anzeigenamen zaehlt dann faelschlich als
# Empfaenger-Trenner und die eigentliche Adresse verschwindet aus dem
# Ergebnis. Go ist NICHT betroffen (mail.ParseAddress parst je Fragment
# RFC5322-konform).
# ---------------------------------------------------------------------------


class TestF004QuotedDisplayNameBypass:
    def test_quoted_display_name_with_semicolon_raises_1147(self):
        """F004a: GIVEN Resend-EmailOutput / WHEN send() einen Empfaenger mit
        gequotetem Anzeigenamen, der ein Semikolon enthaelt, erhaelt
        ('"Foo; Bar" <gregor-test@henemm.com>') / THEN wirft send() trotzdem
        OutputConfigError #1147 -- das Semikolon im Anzeigenamen darf nicht
        als Empfaenger-Trenner missverstanden werden."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"Foo; Bar" <gregor-test@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F004a")

    def test_adversary_repro_mixed_list_with_quoted_semicolon_raises_1147(self):
        """F004b (exakte Adversary-Repro): GIVEN Resend-EmailOutput / WHEN
        send() eine gemischte Liste mit echten Empfaengern UND einem
        gequoteten Test-Postfach-Eintrag mit Semikolon-Anzeigenamen erhaelt
        / THEN wirft send() trotzdem OutputConfigError #1147."""
        output = _make_output()
        exc = _send_and_capture(
            output,
            to=[
                'real@example.com, "Foo; Bar" <gregor-staging@henemm.com>, '
                "other@example.com"
            ],
        )
        _assert_1147_guard_fired(exc, "F004b")

    def test_quoted_display_name_with_semicolon_real_address_no_1147(self):
        """F004c (False-Positive-Schutz): GIVEN Resend-EmailOutput / WHEN
        send() einen gequoteten Anzeigenamen mit Semikolon erhaelt, dessen
        Adresse KEIN Test-Postfach ist ('"Foo; Bar" <real@kunde-real.de>') /
        THEN greift der #1147-Guard NICHT.

        Nachtrag Issue #1219: "real@kunde-real.de" wird als Fixture-
        Nutzerprofil im autouse-isolierten `_DATA_ROOT` registriert (Issue
        #1133/#1219 Adversary F002), damit die Allowlist-Pruefung selbst
        nicht greift und nur die Quote-/Trennzeichen-Logik geprueft wird.

        Nachtrag Issue #1235: Fixture-Domain von example.com (RFC-2606, seit
        #1219 immer geblockt -> Negativfall unerfuellbar, vorbestehend rot)
        auf nicht-reservierte Domain umgestellt."""
        _write_allowlist_fixture("real@kunde-real.de")
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"Foo; Bar" <real@kunde-real.de>']
        )
        if isinstance(exc, OutputConfigError):
            assert "1147" not in str(exc), (
                f"F004c: #1147-Guard darf bei echtem Empfaenger mit "
                f"Semikolon-Anzeigenamen nicht greifen: {exc}"
            )

    def test_quoted_display_name_with_comma_plus_addressed_raises_1147(self):
        """F004d: GIVEN Resend-EmailOutput / WHEN send() einen gequoteten
        Anzeigenamen mit Komma UND Plus-Adressierung erhaelt
        ('"X, Y" <gregor-test+z@henemm.com>') / THEN wirft send() trotzdem
        OutputConfigError #1147 -- Quote-Bewusstsein und
        Plus-Normalisierung muessen zusammenwirken."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"X, Y" <gregor-test+z@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F004d")


# ---------------------------------------------------------------------------
# Fix-Loop 4 -- F005 (Adversary Runde 4, docs/artifacts/
# fix-1147-resend-test-harness/adversary-dialog.md): Steuerzeichen (\r \n
# \x0b \x0c \x00) in einem Anzeigenamen sprengen den parser-basierten Guard --
# `parseaddr()`/`getaddresses()` liefern auf ein derart korruptes Fragment
# unvorhersehbare Ergebnisse, und der reine Trennzeichen-Split kennt \r/\n
# nicht als Trenner. Die STRUKTURELLE Antwort: Steuerzeichen aus dem rohen
# Empfaenger-String entfernen, DANACH den rohen (nicht zerlegten) String
# gegen die Test-Postfach-Literale scannen -- immun gegen jede
# Zerlege-Umgehung, weil hier nichts geparst/gesplittet wird.
# ---------------------------------------------------------------------------


class TestF005ControlCharBypass:
    def test_crlf_in_display_name_raises_1147(self):
        """F005a: GIVEN Resend-EmailOutput / WHEN send() einen Anzeigenamen
        mit eingebettetem CRLF erhaelt ('"Foo\\r\\nBar" <gregor-test@…>') /
        THEN wirft send() trotzdem OutputConfigError #1147 -- Steuerzeichen
        duerfen den Guard nicht durch Parser-Verwirrung umgehen."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"Foo\r\nBar" <gregor-test@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F005a")

    def test_bare_cr_in_display_name_raises_1147(self):
        """F005b: GIVEN Resend-EmailOutput / WHEN ein Anzeigename ein
        einzelnes \\r enthaelt ('"A\\rB" <gregor-staging@…>') / THEN wirft
        send() trotzdem OutputConfigError #1147."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"A\rB" <gregor-staging@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F005b")

    def test_null_byte_in_display_name_raises_1147(self):
        """F005c: GIVEN Resend-EmailOutput / WHEN ein Anzeigename ein
        Null-Byte enthaelt ('"A\\x00B" <gregor-test@…>') / THEN wirft send()
        trotzdem OutputConfigError #1147."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"A\x00B" <gregor-test@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F005c")

    def test_plus_addressed_control_char_display_name_raises_1147(self):
        """F005d: GIVEN Resend-EmailOutput / WHEN ein Steuerzeichen-Anzeigename
        MIT einer Plus-adressierten Test-Postfach-Variante kombiniert wird
        / THEN wirft send() trotzdem OutputConfigError #1147 -- der rohe
        Substring-Scan ist plus-tolerant."""
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"X\r\nY" <gregor-test+abc@henemm.com>']
        )
        _assert_1147_guard_fired(exc, "F005d")

    def test_control_char_real_recipient_plus_tag_no_1147(self):
        """F005e (AC-4-Negativfall 1): GIVEN Resend-EmailOutput / WHEN send()
        einen echten Empfaenger mit Plus-Tag ohne Steuerzeichen erhaelt
        ('real+tag@kunde-real.de') / THEN greift der #1147-Guard NICHT.

        Nachtrag Issue #1219: die BASIS-Adresse "real@kunde-real.de" (ohne
        Plus-Tag -- Allowlist-Eintraege werden nicht plus-gekappt, der
        Empfaenger-Query aber schon, siehe _normalize_addr_for_guard) wird
        als Fixture-Nutzerprofil im autouse-isolierten `_DATA_ROOT`
        registriert (Issue #1133/#1219 Adversary F002), damit die
        Allowlist-Pruefung selbst nicht greift und nur die
        Plus-Tag-Normalisierung geprueft wird.

        Nachtrag Issue #1235: Fixture-Domain von example.com (RFC-2606, seit
        #1219 immer geblockt -> Negativfall unerfuellbar, vorbestehend rot)
        auf nicht-reservierte Domain umgestellt."""
        _write_allowlist_fixture("real@kunde-real.de")
        output = _make_output()
        exc = _send_and_capture(output, to=["real+tag@kunde-real.de"])
        if isinstance(exc, OutputConfigError):
            assert "1147" not in str(exc), (
                f"F005e: #1147-Guard darf bei echtem Plus-Tag-Empfaenger "
                f"nicht greifen: {exc}"
            )

    def test_control_char_real_recipient_no_1147(self):
        """F005f -- VERSCHAERFT durch Issue #1219 (2026-07-10): der
        eingebettete CRLF im Anzeigenamen bringt bereits Pythons
        `email.utils.parseaddr()`/`getaddresses()` dazu, "real@example.com"
        GAR NICHT mehr als Adresse zu erkennen (beide liefern faelschlich
        `('', 'Weird')` zurueck -- empirisch verifiziert, ein bestehender
        Parser-Bug, nicht durch #1219 verursacht). Fuer die alte #1147-
        DENYLIST war das folgenlos (ein Fehlschlag der Adress-Extraktion
        matcht nie TEST_MAILBOXES). Fuer die neue ALLOWLIST ist es das nicht:
        ohne eine positiv erkannte Adresse kann der Guard nicht mehr
        VERIFIZIEREN, dass der Empfaenger zu einem echten Profil gehoert --
        selbst mit "real@example.com" als Fixture registriert (s.u.) bleibt
        der Empfaenger blockiert, weil keine Kandidaten-Adresse mit "@"
        extrahiert werden kann. Das ist eine BEABSICHTIGTE Verschaerfung
        (fail-closed bei nicht positiv verifizierbarem Empfaenger), keine
        Regression -- der Test dokumentiert das jetzt."""
        _write_allowlist_fixture("real@example.com")
        output = _make_output()
        exc = _send_and_capture(
            output, to=['"Weird\r\nName" <real@example.com>']
        )
        assert isinstance(exc, OutputConfigError), (
            "F005f (post-#1219): ein Empfaenger, dessen Adresse wegen des "
            f"CRLF-Parser-Bugs nicht extrahiert werden kann, muss jetzt "
            f"fail-closed blockiert werden, statt: {exc}"
        )
        assert "1219" in str(exc), (
            f"F005f (post-#1219): Blockade muss auf die neue Allowlist-"
            f"Pruefung (#1219) zurueckgehen: {exc}"
        )


# ---------------------------------------------------------------------------
# AC-3: Stalwart-Host bleibt fuer Test-Postfaecher funktionsfaehig (live)
# ---------------------------------------------------------------------------


_EMAIL_CREDS_PRESENT = bool(
    os.environ.get("GZ_TEST_SMTP_USER")
    and os.environ.get("GZ_TEST_SMTP_PASS")
    and os.environ.get("GZ_TEST_IMAP_USER")
    and os.environ.get("GZ_TEST_IMAP_PASS")
)


@pytest.mark.skipif(
    not _EMAIL_CREDS_PRESENT,
    reason="GZ_TEST_SMTP_*/GZ_TEST_IMAP_* nicht gesetzt -- echter Stalwart-"
    "Versand nicht moeglich",
)
class TestAC3StalwartTestMailboxUnaffected:
    def test_stalwart_send_to_test_mailbox_still_works(self):
        """AC-3: GIVEN EmailOutput mit Stalwart-Host (mail.henemm.com) / WHEN
        send(to=["gregor-test@henemm.com"]) / THEN laeuft der Versand
        unveraendert durch -- der neue Guard greift ausschliesslich bei
        Resend-Hosts. Echter SMTP-Send + IMAP-Abruf, kein Mock."""
        import imaplib
        import time as time_mod
        import uuid

        smtp_user = os.environ["GZ_TEST_SMTP_USER"]
        s = Settings(
            smtp_host=os.environ.get("GZ_TEST_SMTP_HOST", "mail.henemm.com"),
            smtp_port=int(os.environ.get("GZ_TEST_SMTP_PORT", "587")),
            smtp_user=smtp_user,
            smtp_pass=os.environ["GZ_TEST_SMTP_PASS"],
            mail_to="gregor-test@henemm.com",
            mail_from=f"{smtp_user}@henemm.com",
            # inbound_address wird sonst aus der Hauptrepo-.env (GZ_INBOUND_ADDRESS
            # = Prod-Adresse) gelesen -- explizit auf den Test-Account setzen,
            # sonst weist Stalwart das MAIL FROM des Prod-Absenders zurueck.
            inbound_address=f"{smtp_user}@henemm.com",
            _env_file=None,
        )
        output = EmailOutput(s)
        marker = f"GZ-1147-AC3-{uuid.uuid4().hex[:8]}"
        output.send(
            marker, "AC-3 Stalwart Kontrollversand (#1147)", html=False,
            to=["gregor-test@henemm.com"],
        )

        imap = imaplib.IMAP4_SSL(
            os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
            int(os.environ.get("GZ_IMAP_PORT", "993")),
        )
        imap.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
        imap.select("INBOX")
        found = False
        for _ in range(10):
            _, data = imap.search(None, f'(SUBJECT "{marker}")')
            if data[0].split():
                found = True
                break
            time_mod.sleep(2)
        imap.logout()
        assert found, f"AC-3: Marker-Mail {marker!r} nicht im Test-Postfach gefunden"


# ---------------------------------------------------------------------------
# AC-7: Doku-Kapitel "Prod-Mail-Pfad-Nachweis: nur passiv"
# ---------------------------------------------------------------------------


class TestAC7OperationsPlaybookProdMailPathProof:
    # doc-compliance-test
    def test_playbook_hat_kapitel_prod_mail_pfad_nachweis(self):
        """AC-7 (doc-compliance-test): GIVEN
        docs/reference/operations_playbook.md / WHEN das Kapitel
        "Prod-Mail-Pfad-Nachweis: nur passiv" gelesen wird / THEN enthaelt es
        das passive Pruefrezept (Header-Forensik + Env-Attestation) UND ein
        explizites Verbot synthetischer Sends/Kunst-User auf Prod."""
        playbook_path = REPO_ROOT / "docs" / "reference" / "operations_playbook.md"
        playbook = playbook_path.read_text()
        assert "Prod-Mail-Pfad-Nachweis" in playbook, (
            "AC-7 (RED erwartet): Kapitel 'Prod-Mail-Pfad-Nachweis' existiert "
            "noch nicht in operations_playbook.md"
        )
        assert "DKIM" in playbook and "amazonses" in playbook, (
            "AC-7: Header-Forensik-Rezept (DKIM + amazonses) fehlt"
        )
        verbot_vorhanden = (
            "Kunst-User" in playbook
            and ("synthetisch" in playbook.lower())
        )
        assert verbot_vorhanden, (
            "AC-7: explizites Verbot synthetischer Sends/Kunst-User auf Prod fehlt"
        )
