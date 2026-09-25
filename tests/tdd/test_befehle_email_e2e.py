"""E-Mail-E2E-Matrix durch den echten Kanal-Eingang (#2417).

Deckt AC-6 (Apple-Mail-Reproduktion von B2), AC-7 (jeder ``_COMMAND_SPECS``-
Befehl in allen drei MIME-Formen, inkl. Regressionsschutz "text/plain
gewinnt"), AC-13 E-Mail-Anteil (Read-Modify-Write auf dem Plattenzustand),
AC-19 (Zitat/Signatur tragen ein ANDERES Befehlswort, das NICHT ausgefuehrt
werden darf) und AC-32 (genau ein Versand, nur E-Mail, nur an den Absender).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
CONTEXT: docs/context/feature-2417-interaktions-testabdeckung.md

Kein Mock/Patch am Produktcode -- abgefangen wird ausschliesslich am
``smtplib.SMTP``-Netzrand (``install_transport_fakes``), Fake-IMAP nur an der
IMAP-Transportgrenze (``_FakeImap``, Fundament-Vorbild).
"""
from __future__ import annotations

import email as email_lib
import quopri
from datetime import timedelta
from email.header import decode_header, make_header

import pytest

from app.loader import load_all_trips
from services.trip_command_processor import _COMMAND_SPECS
from tests.fixtures.authentication_results_fixtures import AR_PASS
from tests.tdd._befehl_e2e_fixtures import (
    FEHLERTEXTE,
    MAIL_FORMEN,
    _FakeImap,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    merkmal_fuer,
    sende_email,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


# ---------------------------------------------------------------------------
# Lokale MIME-Bauer -- NUR fuer Faelle, die das gemeinsame Fundament bewusst
# nicht anbietet (unterschiedliche Befehle je Teil / fremdes Wort in Zitat
# UND Signatur). Kopieren statt Fundament aendern (Team-Lead-Vorgabe).
# ---------------------------------------------------------------------------

def _mime_alternative_beide_unterschiedliche_befehle(
    from_addr: str, subject: str, plain_befehl: str, html_befehl: str,
) -> bytes:
    """``multipart/alternative`` mit UNTERSCHIEDLICHEN Befehlen je Teil --
    Regressionsschutz-Fall aus AC-7: text/plain MUSS gewinnen."""
    boundary = "Alt-Mail-Diff=_GZ2417"
    raw = (
        f"From: {from_addr}\r\n"
        "To: cmd@example.com\r\n"
        f"Subject: {subject}\r\n"
        f"Authentication-Results: {AR_PASS}\r\n"
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{plain_befehl}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"<p>{html_befehl}</p>\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return raw


def _mime_apple_html_zitat_und_signatur_mit_fremdem_befehl(
    from_addr: str, subject: str, befehl: str, fremder_befehl: str,
) -> bytes:
    """Wie das Fundament-Vorbild ``_mime_apple_html_only``, aber Signatur UND
    Zitat tragen zusaetzlich ein ANDERES Befehlswort (AC-19: darf nicht
    ausgefuehrt werden)."""
    html = (
        f'<body dir="auto">{befehl}<br id="lineBreakAtBeginningOfSignature">'
        f'<div dir="ltr"><div>Gesendet von meinem iPhone</div>'
        f"<div>{fremder_befehl}</div></div>"
        '<div dir="ltr"><br><blockquote type="cite">Am 25.09.2026 um 06:06 '
        f"schrieb Absender:<br><br>{fremder_befehl}<br></blockquote></div></body>"
    )
    qp = quopri.encodestring(html.encode("utf-8")).decode("ascii")
    boundary = "Apple-Mail-AC19=_GZ2417"
    raw = (
        f"From: {from_addr}\r\n"
        "To: cmd@example.com\r\n"
        f"Subject: {subject}\r\n"
        f"Authentication-Results: {AR_PASS}\r\n"
        "MIME-Version: 1.0\r\n"
        f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html;\r\n"
        "\tcharset=utf-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
        f"{qp}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return raw


def _sende_rohe_mail(settings, raw: bytes) -> int:
    """Wie ``sende_email``, aber mit selbst gebauten Rohbytes (fuer die
    beiden lokalen MIME-Bauer oben) -- derselbe echte ``_process_single``-
    Pfad mit Fake-IMAP."""
    from services.inbound_email_reader import InboundEmailReader

    imap = _FakeImap(raw)
    return InboundEmailReader()._process_single(imap, b"1", settings)


def _gesendeter_email_text(gesendet: dict) -> str:
    """Betreff (RFC-2047-dekodiert) + jeder lesbare Text-Anteil der
    tatsaechlich versendeten Antwortmail -- robust gegen Single- oder
    Multipart, unabhaengig davon, ob der Produktcode ``html=True/False``
    waehlt (nicht Gegenstand dieser Tests)."""
    msg = email_lib.message_from_string(gesendet["raw"])
    subject = str(make_header(decode_header(msg.get("Subject", ""))))
    teile = [subject]
    if msg.is_multipart():
        for teil in msg.walk():
            if teil.get_content_maintype() == "text":
                payload = teil.get_payload(decode=True)
                if payload:
                    teile.append(
                        payload.decode(teil.get_content_charset() or "utf-8", errors="replace")
                    )
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            teile.append(payload.decode(msg.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


def _assert_frei_von_fehlertexten(text: str, *, kontext: str) -> None:
    """Spec-Abschnitt "Inhaltsmerkmal je Befehl": jede Antwort muss frei von
    den Fehlertexten sein. WICHTIG: ``unknown_command_body()`` listet ALLE
    12 Befehlswoerter im "Verfügbar: ..."-Absatz auf -- ein reiner
    Wortlisten-Treffer allein kann eine "Unbekannter Befehl"-Antwort deshalb
    NICHT von echter Hilfe unterscheiden. Diese Pruefung ist deshalb PFLICHT
    zusaetzlich zum Inhaltsmerkmal, nicht optional."""
    for fehler in FEHLERTEXTE:
        assert fehler not in text, (
            f"{kontext}: Antwort enthaelt den Fehlertext {fehler!r} -- das "
            f"ist ein Fehlschlag, keine echte Ausfuehrung: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------

def test_apple_mail_nur_html_wird_erkannt(monkeypatch, user_ids):
    """AC-6: Apple-Mail-Antwort (``multipart/alternative``, NUR ``text/html``)
    mit ``Hilfe`` als erstem sichtbaren Wort vor Zitat/Signatur wird erkannt
    -- reproduziert B2 als roten Test vor dem Fix."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    ergebnis = sende_email(settings, nutzer, "Hilfe", form="apple_html")

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, "Die Mail wurde nicht als Befehl verarbeitet."
    assert recorder.emails, f"Es wurde keine Antwortmail versendet: {recorder.emails!r}"
    text = _gesendeter_email_text(recorder.emails[-1])
    _assert_frei_von_fehlertexten(text, kontext="AC-6 apple_html/hilfe")
    for wort in merkmal_fuer("hilfe", nutzer=nutzer):
        assert wort in text, f"Hilfetext fehlt {wort!r} in der Antwort: {text!r}"


# ---------------------------------------------------------------------------
# AC-7 -- jeder _COMMAND_SPECS-Befehl x 3 MIME-Formen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form", sorted(MAIL_FORMEN))
@pytest.mark.parametrize("spec", _COMMAND_SPECS, ids=[s[0] for s in _COMMAND_SPECS])
def test_jeder_befehl_in_allen_mailformen(monkeypatch, user_ids, spec, form):
    """AC-7: jeder angebotene Steuerbefehl wird in allen drei Mailformen
    korrekt ausgefuehrt -- die tatsaechlich versendete Antwortmail traegt das
    fuer diesen Befehl festgelegte Inhaltsmerkmal. ``apple_html`` ist VOR dem
    Fix (fehlender HTML-Fallback, AC-19) fuer JEDEN Befehl rot -- das ist der
    Beweis fuer B2, nicht ein Defekt dieses Tests."""
    wort, _arg, _beschreibung, _kinds = spec
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()
    body = f"{wort} 2d" if wort == "pause" else wort

    ergebnis = sende_email(settings, nutzer, body, form=form)

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, f"Mail mit Befehl {wort!r} (Form {form!r}) nicht verarbeitet."
    assert recorder.emails, f"Keine Antwortmail fuer {wort!r}/{form!r}: {recorder.emails!r}"
    text = _gesendeter_email_text(recorder.emails[-1])
    _assert_frei_von_fehlertexten(text, kontext=f"AC-7 {wort!r}/{form!r}")
    merkmal = merkmal_fuer(wort, nutzer=nutzer)
    erwartete_teile = merkmal if isinstance(merkmal, tuple) else (merkmal,)
    for teil in erwartete_teile:
        assert teil in text, (
            f"Befehl {wort!r} (Form {form!r}): Inhaltsmerkmal {teil!r} fehlt "
            f"in der Antwort: {text!r}"
        )


def test_alternative_beide_bevorzugt_text_plain_bei_unterschiedlichen_befehlen(
    monkeypatch, user_ids,
):
    """AC-7 Regressionsschutz: traegt eine ``multipart/alternative``-Mail in
    ``text/plain`` und ``text/html`` UNTERSCHIEDLICHE Befehle, gewinnt
    ``text/plain`` -- der neue HTML-Fallback (AC-19) darf dieses bestehende
    Verhalten nicht verdraengen."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()
    subject = f"Re: [{nutzer.trip.name}] Etappe"
    raw = _mime_alternative_beide_unterschiedliche_befehle(
        nutzer.mail_to, subject, plain_befehl="status", html_befehl="hilfe",
    )

    ergebnis = _sende_rohe_mail(settings, raw)

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, "Die Mail wurde nicht als Befehl verarbeitet."
    assert recorder.emails, f"Es wurde keine Antwortmail versendet: {recorder.emails!r}"
    text = _gesendeter_email_text(recorder.emails[-1])
    _assert_frei_von_fehlertexten(text, kontext="AC-7 Regressionsschutz plain/html")
    erwartet_status = merkmal_fuer("status", nutzer=nutzer)
    assert erwartet_status in text, (
        f"text/plain ('status') haette gewinnen muessen, aber "
        f"{erwartet_status!r} fehlt in der Antwort: {text!r}"
    )
    hilfe_woerter = merkmal_fuer("hilfe", nutzer=nutzer)
    assert not all(wort in text for wort in hilfe_woerter), (
        f"text/html ('hilfe') hat text/plain ('status') verdraengt: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-19 -- Zitat und Signatur duerfen kein anderes Befehlswort ausloesen
# ---------------------------------------------------------------------------

def test_apple_mail_ignoriert_befehlswort_in_zitat_und_signatur(monkeypatch, user_ids):
    """AC-19: Signatur UND Zitat tragen ``Stop`` -- ausgefuehrt werden darf
    nur das ERSTE sichtbare Wort ``Hilfe`` davor. Vor dem Fix rot (derselbe
    fehlende HTML-Fallback wie AC-6), aber die Zusicherung ist zusaetzlich
    scharf genug, eine falsch geschnittene Grenze zu fangen: eine Truncation,
    die zu FRUEH oder zu SPAET schneidet, kann diesen Test nicht zufaellig
    gruen bestehen, weil sowohl Hilfe-Woerter als auch ein "beendet/
    deaktiviert"-Nachweis gefordert sind."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()
    subject = f"Re: [{nutzer.trip.name}] Etappe"
    raw = _mime_apple_html_zitat_und_signatur_mit_fremdem_befehl(
        nutzer.mail_to, subject, befehl="Hilfe", fremder_befehl="Stop",
    )

    ergebnis = _sende_rohe_mail(settings, raw)

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, "Die Mail wurde nicht als Befehl verarbeitet."
    assert recorder.emails, f"Es wurde keine Antwortmail versendet: {recorder.emails!r}"
    text = _gesendeter_email_text(recorder.emails[-1])
    _assert_frei_von_fehlertexten(text, kontext="AC-19 Zitat/Signatur")
    for wort in merkmal_fuer("hilfe", nutzer=nutzer):
        assert wort in text, f"Hilfetext fehlt {wort!r} in der Antwort: {text!r}"
    text_klein = text.lower()
    assert "beendet" not in text_klein and "deaktiviert" not in text_klein, (
        f"Das Befehlswort aus Signatur/Zitat ('Stop') wurde ausgefuehrt: {text!r}"
    )
    trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    assert trip.report_config.enabled is True, (
        "Stop aus Zitat/Signatur hat den Trip trotzdem deaktiviert (RMW-Seiteneffekt)."
    )


# ---------------------------------------------------------------------------
# AC-13 (E-Mail-Anteil) -- Read-Modify-Write auf dem Plattenzustand
# ---------------------------------------------------------------------------

def test_mutierende_befehle_schreiben_read_modify_write_auf_platte(monkeypatch, user_ids):
    """AC-13: jeder mutierende Befehl (STOP, WEITER, SKIP, RUHETAG, PAUSE)
    schreibt NUR sein eigenes Feld -- vorherige Aenderungen und unbeteiligte
    Felder bleiben ueber die gesamte Kommandofolge hinweg erhalten
    (Read-Modify-Write, kein Replace, Issue BUG-DATALOSS-GR221/#102)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    def _reload():
        return next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)

    basis = _reload()
    assert basis.report_config.enabled is True
    assert basis.report_config.skip_next is False
    assert basis.report_config.paused_until is None
    original_stage_dates = [s.date for s in basis.stages]

    def _sende(body: str) -> None:
        ergebnis = sende_email(settings, nutzer, body, form="plain")
        assert ergebnis == 1, f"Mail mit Befehl {body!r} nicht verarbeitet."

    # 1) STOP -- nur `enabled` aendert sich
    _sende("stop")
    nach_stop = _reload()
    assert nach_stop.report_config.enabled is False
    assert nach_stop.report_config.skip_next is False
    assert nach_stop.report_config.paused_until is None
    assert nach_stop.report_config.send_email is True
    assert nach_stop.report_config.send_sms is True
    assert nach_stop.report_config.send_premium_sms is True
    assert nach_stop.report_config.send_telegram is True

    # 2) WEITER -- reaktiviert, alles andere bleibt wie nach STOP
    _sende("weiter")
    nach_weiter = _reload()
    assert nach_weiter.report_config.enabled is True
    assert nach_weiter.report_config.skip_next is False
    assert nach_weiter.report_config.paused_until is None

    # 3) SKIP -- nur `skip_next` aendert sich, `enabled` bleibt True
    _sende("skip")
    nach_skip = _reload()
    assert nach_skip.report_config.skip_next is True
    assert nach_skip.report_config.enabled is True
    assert nach_skip.report_config.paused_until is None

    # 4) RUHETAG -- verschiebt nur Etappen NACH heute, `enabled`/`skip_next`
    # bleiben aus Schritt 3 erhalten (Trip- UND Config-Ebene der RMW-Pruefung)
    _sende("ruhetag")
    nach_ruhetag = _reload()
    assert nach_ruhetag.stages[0].date == original_stage_dates[0], "Vergangene Etappe verschoben."
    assert nach_ruhetag.stages[1].date == original_stage_dates[1], "Heutige Etappe verschoben."
    assert nach_ruhetag.stages[2].date == original_stage_dates[2] + timedelta(days=1), (
        "Zukuenftige Etappe NICHT um einen Tag verschoben."
    )
    assert nach_ruhetag.report_config.enabled is True
    assert nach_ruhetag.report_config.skip_next is True

    # 5) PAUSE 2d -- nur `paused_until` aendert sich, Etappen-/Skip-Zustand
    # aus den vorigen Schritten bleibt unangetastet
    _sende("pause 2d")
    nach_pause = _reload()
    assert nach_pause.report_config.paused_until is not None
    assert nach_pause.report_config.enabled is True
    assert nach_pause.report_config.skip_next is True
    assert nach_pause.stages[2].date == nach_ruhetag.stages[2].date, (
        "PAUSE hat die von RUHETAG verschobene Etappe wieder zurueckgesetzt."
    )


# ---------------------------------------------------------------------------
# AC-32 -- genau ein Versand, nur E-Mail, nur an den Absender
# ---------------------------------------------------------------------------

def test_mandantentrennung_und_alleiniger_versand(monkeypatch, user_ids):
    """AC-32 (+ Zwei-Nutzer-Variante analog AC-12): die Antwort geht
    ausschliesslich an den From-Absender ueber den E-Mail-Kanal -- kein
    Versand an den zweiten Nutzer, kein Versand auf einem anderen Kanal."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer_a = lege_lage_an(user_ids, "L2")
    nutzer_b = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    ergebnis = sende_email(settings, nutzer_a, "status", form="plain")

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, "Die Mail wurde nicht als Befehl verarbeitet."
    assert len(recorder.emails) == 1, (
        f"Erwartet genau EINEN Versand, tatsaechlich: {recorder.emails!r}"
    )
    gesendet = recorder.emails[-1]
    assert gesendet["to"] == (nutzer_a.mail_to,), (
        f"Antwort ging nicht ausschliesslich an den Absender A: {gesendet['to']!r}"
    )
    assert nutzer_b.mail_to not in gesendet["to"], (
        f"Nutzer B hat faelschlich eine Antwort erhalten: {gesendet['to']!r}"
    )
    assert not recorder.telegram, (
        f"Ein E-Mail-Befehl hat zusaetzlich Telegram-Versand ausgeloest: {recorder.telegram!r}"
    )
    assert not recorder.premium_sms_out, (
        f"Ein E-Mail-Befehl hat zusaetzlich Premium-SMS ausgeloest: "
        f"{recorder.premium_sms_out!r}"
    )
