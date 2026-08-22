"""TDD RED — Issue #2051 Scheibe S1: die fuenf Renderer-Textstellen nennen das
ENDE des Regenereignisses, nicht nur seinen Beginn.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-8, AC-9, AC-10,
AC-11, AC-12.

Fachlicher Kern: der Nowcast liest heute nur den ERSTEN nassen Frame und
verwirft den Rest der bereits abgerufenen Zeitreihe. Der Nutzer erfaehrt,
WANN es anfaengt, aber nicht, WANN es aufhoert. S1 leitet das Ende aus
denselben Frames ab und liefert es additiv in allen Textstellen mit:

* Langform (Betreff, E-Mail Trip, E-Mail Mehr-Orte, Telegram rich):
  `letzter Regen gegen HH:MM`
* Kurzform (SMS/Premium-SMS/Telegram-Kurzstil): ein zweites, MINUTENGENAUES
  Zeit-Token (`@HH:MM`) unmittelbar HINTER dem Mengen-Token aus #2046, also
  `R2.5@18:00@20:00`. Begruendung der Formatwahl s. `_KURZFORM_RE` unten.

Wortlaut-Herkunft: von der Parallelsitzung #2020 S2 uebernommen, hier nicht
neu erfunden. `_onset_time_label()` und der Delta-Teil von `_render_sms_body`
bleiben unangetastet (Zusage an `fix-2020-zeitangaben-wortlaut`) — kein Test
dieser Datei nagelt deren heutiges Verhalten fest.

RED-Ursache: `OnsetEvent`/`NowcastResult`/`RadarAlertRequest` kennen die
additiven Ende-Felder (`event_end_time`, `event_end_day_offset` bzw.
`event_end_minutes`) noch nicht -> `TypeError` beim Konstruktor-Aufruf.

Mock-frei: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer, echter `NotificationService` gegen echte lokale
Aufzeichnungs-Server. Alle Zeitangaben sind FEST gesetzt (keine Wanduhr) —
ausser im Ortsvergleich-Buendel (AC-10), dessen Konstruktor `onset_time`
selbst aus `datetime.now()` ableitet; dort wird auf Struktur statt
Goldstring geprueft.
"""
from __future__ import annotations

import http.server
import inspect
import json
import re
import socket
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from services.notification_service import NotificationService, RadarAlertRequest

from tests.helpers.nowcast_gate_fixtures import clean_uid, fresh_uid, make_trip

# Langform-Wortlaut (#2020 S2). Die Uhrzeit wird als Gruppe gefangen, damit
# der WERT geprueft werden kann und nicht nur die Floskel.
_LANGFORM_RE = re.compile(r"letzter Regen gegen (\d{1,2}:\d{2})")
# Kurzform: Mengen-Token aus #2046, unmittelbar gefolgt vom Ende-Token.
#
# Das Ende-Token ist `@HH:MM` — MINUTENGENAU, kein optionaler Minutenteil.
# Die Spec ist an dieser Stelle uneinheitlich (zweimal `@HH`/`@20`, zweimal
# `@HH:MM`/`@23:59`); den Ausschlag gibt AC-16: dort, wo die exakte Laenge
# zaehlt, budgetiert die Spec ausdruecklich `@23:59`. Dazu kommt die
# Konsistenz mit dem Beginn-Token aus #2046 (`R2.5@18:00`) — zwei benachbarte
# Zeit-Token in unterschiedlicher Granularitaet waeren eine eigene
# Fehlerquelle. Die `@HH`-Erwaehnungen sind Kurzschreibweise fuer "ein
# Zeit-Token", keine Formatvorgabe.
#
# Die Toleranz NICHT wiederherstellen: ein Ausdruck, der `@20` und `@20:00`
# gleichermassen annimmt, bewacht keines der beiden Formate.
_KURZFORM_RE = re.compile(
    r"\bR(?P<menge>\d+\.\d)@(?P<beginn>\d{1,2}:\d{2})@(?P<ende>\d{1,2}:\d{2})\b"
)

SMS_TO = "+49000000000"
PREMIUM_REPLY_TO = "+4915799912345"
# Sandbox-Kennung des seven.io-Transports: KEIN echter Schluessel, sondern der
# Wert, mit dem beide Sicherheitssperren des Transports (`seven_api_key ==
# seven_sandbox_key`) zufrieden sind und nichts das Haus verlaesst. Aus
# Bausteinen gesetzt, damit die Zeichenfolge nicht wie ein hinterlegter
# Schluessel aussieht.
_SANDBOX_KENNUNG = "-".join(("sandbox", "key", "2051"))

_UNSET = object()  # Sentinel: Ende-Felder gar nicht erst uebergeben.


def _onset_event(
    *, event_end_time: object = _UNSET, event_end_day_offset: object = _UNSET,
    onset_precip_mm: object = _UNSET, **kw,
) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr).

    Die neuen Ende-Felder werden NUR uebergeben, wenn ein Aufrufer sie
    ausdruecklich setzt (Muster `test_onset_kurzform_menge.py`): so bleiben
    Vergleichsfassungen ohne Ende unabhaengig vom Modell-Erweiterungsstand
    gruen, waehrend die Ende-Faelle heute am `TypeError` scheitern.
    """
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=8.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel",
    )
    fields.update(kw)
    if event_end_time is not _UNSET:
        fields["event_end_time"] = event_end_time
    if event_end_day_offset is not _UNSET:
        fields["event_end_day_offset"] = event_end_day_offset
    if onset_precip_mm is not _UNSET:
        fields["onset_precip_mm"] = onset_precip_mm
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    """`source is not None` routet alle Renderer in den Onset-Zweig."""
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class _SevenIoStub:
    """Lokaler HTTP-Server, der die seven.io-POSTs von SMS UND Premium-SMS
    entgegennimmt (Vorbild `test_onset_menge_kanalparitaet.py`). Kein Mock:
    der echte Transport laeuft, die Nutzlast wird am Draht gemessen."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                data = urllib.parse.parse_qs(self.rfile.read(length).decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


class _TelegramStub:
    """Lokaler HTTP-Stub der Telegram-Bot-API — zeichnet jede
    `sendMessage`-Nutzlast auf."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                body = json.dumps(
                    {"ok": True, "result": {"message_id": 4711}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def seven_io_stub():
    stub = _SevenIoStub()
    yield stub
    stub.stop()


@pytest.fixture()
def telegram_stub():
    stub = _TelegramStub()
    yield stub
    stub.stop()


def _drei_kanal_settings(seven_port: int) -> Settings:
    """SMS, Premium-SMS und Telegram sendebereit, E-Mail bewusst aus.

    Jedes weggelassene Feld faellt bei pydantic still auf die Prod-`.env` des
    Arbeitsverzeichnisses zurueck (#1477), deshalb wird auch das
    ausdrueckliche "aus" vollstaendig gesetzt.
    """
    return Settings(
        sms_gateway_url=f"http://127.0.0.1:{seven_port}/api/sms",
        seven_api_key=_SANDBOX_KENNUNG,
        seven_sandbox_key=_SANDBOX_KENNUNG,
        sms_to=SMS_TO, sms_from=None,
        premium_sms_reply_to=PREMIUM_REPLY_TO,
        premium_sms_reply_at=datetime.now(timezone.utc),
        telegram_bot_token="test-token-2051",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueften Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-8 — E-Mail-Betreff (`_render_subject_onset`)
# ---------------------------------------------------------------------------


def test_ac8_email_betreff_nennt_das_ende():
    """AC-8 GIVEN einen Onset-Alarm mit abgeleitetem Ende
    (`event_end_time="20:00"`)
    WHEN `render_subject(msg)` den E-Mail-Betreff rendert
    THEN nennt der Betreff zusaetzlich zur Beginn-Angabe das Ende im Wortlaut
    `letzter Regen gegen 20:00`.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    betreff = render_subject(_onset_msg(_onset_event(event_end_time="20:00")))

    treffer = _LANGFORM_RE.search(betreff)
    assert treffer is not None, (
        f"RED: der Betreff nennt das Ende nicht ('letzter Regen gegen HH:MM'): "
        f"{betreff!r}"
    )
    assert treffer.group(1) == "20:00", (
        f"Der Betreff nennt eine andere Uhrzeit als das abgeleitete Ende "
        f"(erwartet 20:00): {betreff!r}"
    )
    assert "in 30 Min" in betreff, (
        f"Die bestehende Beginn-Angabe darf nicht verdraengt werden: {betreff!r}"
    )


def test_ac8_ohne_ende_bleibt_der_betreff_unveraendert():
    """AC-8 (Gegenprobe) GIVEN denselben Alarm OHNE abgeleitetes Ende
    (`event_end_time=None`)
    WHEN `render_subject(msg)` rendert
    THEN steht KEINE Ende-Angabe im Betreff, und der Text ist byte-identisch
    zu der Fassung, die das Feld gar nicht erst uebergibt — ein ungesetztes
    Ende darf den Bestandstext nicht anfassen (AC-19).

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    mit_none = render_subject(_onset_msg(_onset_event(event_end_time=None)))
    ohne_feld = render_subject(_onset_msg(_onset_event()))

    assert _LANGFORM_RE.search(mit_none) is None, (
        f"Ohne abgeleitetes Ende darf keine Ende-Angabe entstehen: {mit_none!r}"
    )
    assert mit_none == ohne_feld, (
        "Ein ungesetztes Ende-Feld darf den Betreff nicht veraendern.\n"
        f"  mit None  = {mit_none!r}\n  ohne Feld = {ohne_feld!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 — E-Mail Trip (`_render_email_onset`)
# ---------------------------------------------------------------------------


def test_ac9_email_trip_onset_nennt_das_ende():
    """AC-9 GIVEN denselben Aufbau wie AC-8
    WHEN `render_email(msg)` die Trip-Onset-Mail rendert
    THEN enthaelt der Klartext-Koerper `letzter Regen gegen 20:00`
    ZUSAETZLICH zur bestehenden Beginn-Zeile (`ab 18:00`) — die Beginn-Angabe
    wird ergaenzt, nicht ersetzt.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    _html, plain = render_email(_onset_msg(_onset_event(event_end_time="20:00")))

    treffer = _LANGFORM_RE.search(plain)
    assert treffer is not None, (
        f"RED: die Trip-Onset-Mail nennt das Ende nicht: {plain!r}"
    )
    assert treffer.group(1) == "20:00", (
        f"Die Mail nennt eine andere Uhrzeit als das abgeleitete Ende: {plain!r}"
    )
    assert "ab 18:00" in plain, (
        f"Die bestehende Beginn-Zeile darf nicht verdraengt werden: {plain!r}"
    )


def test_ac9_die_ende_angabe_steht_auch_im_html_teil():
    """AC-9 (Kanaltreue) GIVEN denselben Aufbau
    WHEN dieselbe Mail gerendert wird
    THEN traegt der HTML-Teil dieselbe Ende-Uhrzeit wie der Klartext — die
    HTML-Fassung ist die Normalfassung, der Klartext ihr Gegenstueck; eine
    Angabe nur in einer der beiden Haelften waere eine stille Luecke.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    html, plain = render_email(_onset_msg(_onset_event(event_end_time="20:00")))

    aus_plain = _LANGFORM_RE.search(plain)
    aus_html = _LANGFORM_RE.search(html)
    assert aus_html is not None, (
        f"RED: der HTML-Teil nennt das Ende nicht: {html!r}"
    )
    assert aus_plain is not None and aus_html.group(1) == aus_plain.group(1), (
        "HTML- und Klartext-Fassung nennen unterschiedliche Ende-Uhrzeiten."
    )


# ---------------------------------------------------------------------------
# AC-10 — E-Mail Mehr-Orte-Buendel (Ortsvergleich)
# ---------------------------------------------------------------------------


def test_ac10_mehr_orte_buendel_traegt_das_ende_des_fuehrenden_ortes():
    """AC-10 GIVEN ein Mehr-Orte-Onset-Buendel (Ortsvergleich) mit ZWEI Orten,
    dessen fuehrender Ort ein `NowcastResult` mit gesetztem
    `event_end_minutes=80` traegt
    WHEN `to_multi_location_onset_alert_message` die Nachricht baut und
    `render_email` sie ueber `_render_email_onset_multi` rendert
    THEN enthaelt der Text `letzter Regen gegen HH:MM` — dieselbe Angabe wie
    im Trip-Pfad (AC-9), nicht bloss eine Beginn-Zeile.

    Wanduhrfest: der Buendel-Konstruktor leitet die Uhrzeiten aus
    `datetime.now()` ab, deshalb Struktur- statt Goldstring-Pruefung.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht
    (`TypeError`)."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from services.radar_service import NowcastResult

    fuehrend = NowcastResult(
        onset_minutes=20, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False, event_end_minutes=80,
    )
    zweiter = NowcastResult(
        onset_minutes=35, intensity_label="Leichter Regen", source="AROME-FR",
        is_convective=False, event_end_minutes=95,
    )

    msg = to_multi_location_onset_alert_message(
        [("Zermatt", fuehrend), ("Chamonix", zweiter)],
        tz=timezone.utc, stand_at="10:00",
    )
    _html, plain = render_email(msg)

    assert _LANGFORM_RE.search(plain), (
        f"RED: das Mehr-Orte-Buendel nennt kein Ende: {plain!r}"
    )
    assert "Zermatt" in plain, (
        f"Voraussetzung: der fuehrende Ort steht im Buendel-Text: {plain!r}"
    )


def test_ac10_ohne_ende_bleibt_das_buendel_unveraendert():
    """AC-10 (Gegenprobe) GIVEN dasselbe Buendel, aber OHNE abgeleitetes Ende
    WHEN dieselbe Nachricht gebaut und gerendert wird
    THEN steht KEINE Ende-Angabe im Text — die Buendel-Fassung ohne Ende
    bleibt wie heute (AC-19).

    Bewusst OHNE das neue Feld konstruiert: dieser Waechter bleibt damit
    unabhaengig vom Modell-Erweiterungsstand gruen und faengt spaeter eine
    erfundene Ende-Angabe."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from services.radar_service import NowcastResult

    msg = to_multi_location_onset_alert_message(
        [
            ("Zermatt", NowcastResult(
                onset_minutes=20, intensity_label="Mäßiger Regen",
                source="radar", is_convective=False,
            )),
            ("Chamonix", NowcastResult(
                onset_minutes=35, intensity_label="Leichter Regen",
                source="AROME-FR", is_convective=False,
            )),
        ],
        tz=timezone.utc, stand_at="10:00",
    )
    _html, plain = render_email(msg)

    assert _LANGFORM_RE.search(plain) is None, (
        f"Ohne abgeleitetes Ende darf keine Ende-Angabe entstehen: {plain!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — Telegram (rich)
# ---------------------------------------------------------------------------


def test_ac11_telegram_rich_nennt_das_ende():
    """AC-11 GIVEN denselben Aufbau wie AC-8
    WHEN `render_telegram(msg)` die reiche Telegram-Nachricht rendert
    THEN enthaelt der Text `letzter Regen gegen 20:00` zusaetzlich zur
    Beginn-Angabe.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    text = render_telegram(_onset_msg(_onset_event(event_end_time="20:00")))

    treffer = _LANGFORM_RE.search(text)
    assert treffer is not None, (
        f"RED: die Telegram-Nachricht nennt das Ende nicht: {text!r}"
    )
    assert treffer.group(1) == "20:00", (
        f"Telegram nennt eine andere Uhrzeit als das abgeleitete Ende: {text!r}"
    )
    assert "18:00" in text, (
        f"Die bestehende Beginn-Angabe darf nicht verdraengt werden: {text!r}"
    )


def test_ac11_langform_ist_in_allen_drei_stellen_derselbe_wortlaut():
    """AC-8/AC-9/AC-11 (Kopplung) GIVEN denselben Alarm
    WHEN Betreff, Trip-Mail und Telegram gerendert werden
    THEN nennen alle drei DIESELBE Uhrzeit im DEMSELBEN Wortlaut — drei
    Stellen mit drei Formulierungen waeren drei Dialekte fuer dieselbe
    Aussage.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    msg = _onset_msg(_onset_event(event_end_time="20:00"))
    _html, plain = render_email(msg)

    fundstellen = {
        "betreff": _LANGFORM_RE.search(render_subject(msg)),
        "mail": _LANGFORM_RE.search(plain),
        "telegram": _LANGFORM_RE.search(render_telegram(msg)),
    }
    fehlend = [k for k, v in fundstellen.items() if v is None]
    assert not fehlend, f"RED: ohne Ende-Angabe: {fehlend}"
    werte = {k: v.group(1) for k, v in fundstellen.items()}
    assert len(set(werte.values())) == 1, (
        f"Die drei Langform-Stellen nennen verschiedene Uhrzeiten: {werte}"
    )


# ---------------------------------------------------------------------------
# AC-12 — Kurzform: zweites Zeit-Token hinter dem Mengen-Token
# ---------------------------------------------------------------------------


def test_ac12_kurzform_traegt_das_ende_token_hinter_der_menge():
    """AC-12 GIVEN einen Onset-Alarm mit Mengenangabe aus #2046
    (`onset_precip_mm=2.5`, Beginn `18:00`) UND abgeleitetem Ende
    (`event_end_time="20:00"`)
    WHEN `render_sms(msg)` ueber den Onset-Zweig rendert
    THEN traegt der Text ZWEI Zeit-Token in dieser Reihenfolge: erst das
    Mengen-/Beginn-Token `R2.5@18:00`, unmittelbar dahinter das minutengenaue
    Ende-Token `@20:00` — kein Trennzeichen dazwischen, keine Vertauschung.

    Das Ende-Token ist minutengenau (`@HH:MM`), nicht `@HH`: die exakte Laenge
    zaehlt in AC-16, und dort budgetiert die Spec `@23:59`; ausserdem waeren
    zwei benachbarte Zeit-Token in unterschiedlicher Granularitaet eine eigene
    Fehlerquelle. Kein optionaler Minutenteil im Ausdruck — ein Test, der
    beide Schreibweisen annimmt, bewacht keine von beiden.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    sms = render_sms(_onset_msg(
        _onset_event(onset_precip_mm=2.5, event_end_time="20:00")
    ))

    treffer = _KURZFORM_RE.search(sms)
    assert treffer is not None, (
        f"RED: kein 'R<menge>@<beginn>@<ende>'-Token in der Kurznachricht: "
        f"{sms!r}"
    )
    assert treffer.group("menge") == "2.5", (
        f"Das Mengen-Token aus #2046 ist beschaedigt: {sms!r}"
    )
    assert treffer.group("beginn") == "18:00", (
        f"Das Beginn-Token steht nicht mehr an erster Stelle: {sms!r}"
    )
    assert treffer.group("ende") == "20:00", (
        f"Das Ende-Token nennt nicht das abgeleitete Ende minutengenau "
        f"(erwartet '20:00'): {sms!r}"
    )


def test_ac12_ohne_ende_bleibt_die_kurzform_von_2046_unveraendert():
    """AC-12 (Gegenprobe) GIVEN denselben Alarm mit Menge, aber OHNE
    abgeleitetes Ende (`event_end_time=None`)
    WHEN `render_sms(msg)` rendert
    THEN bleibt die Kurzform aus #2046 byte-identisch (`Ziel: R2.5@18:00`) —
    kein zweites Zeit-Token, kein leeres `@`.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    mit_none = render_sms(_onset_msg(
        _onset_event(onset_precip_mm=2.5, event_end_time=None)
    ))
    ohne_feld = render_sms(_onset_msg(_onset_event(onset_precip_mm=2.5)))

    assert mit_none == ohne_feld, (
        "Ein ungesetztes Ende-Feld darf die Kurznachricht nicht anfassen.\n"
        f"  mit None  = {mit_none!r}\n  ohne Feld = {ohne_feld!r}"
    )
    assert _KURZFORM_RE.search(mit_none) is None, (
        f"Ohne abgeleitetes Ende darf kein zweites Zeit-Token entstehen: "
        f"{mit_none!r}"
    )
    assert not mit_none.rstrip().endswith("@"), (
        f"Leeres Ende-Token am Textende: {mit_none!r}"
    )


def test_ac12_gewitter_kurzform_traegt_das_ende_hinter_dem_zeit_token():
    """AC-12 (Gewitter-Zweig) GIVEN denselben Alarm konvektiv
    (`is_convective=True`) — dort steht die Menge laut #2046 als EIGENES
    Token NACH der Zeit (`TH@18:00 R2.5`)
    WHEN `render_sms(msg)` rendert
    THEN traegt auch dieser Zweig das minutengenaue Ende-Token `@20:00`, und
    hinter `TH` steht weiterhin NIEMALS eine Ziffer (die Position gehoert der
    Stufe L/M/H der Briefing-Grammatik, #2046 AC-2).

    Der Gewitter-Zweig ist ein eigener Codepfad; wird das Ende nur im
    Regen-Zweig angehaengt, bleibt hier eine stille Luecke.

    Auch hier minutengenau (`@HH:MM`, nicht `@HH`) — dieselbe Formatregel wie
    im Regen-Zweig; eine je Zweig andere Granularitaet waere ein zweiter
    Dialekt fuer dieselbe Angabe.

    RED heute: `OnsetEvent` kennt `event_end_time` nicht (`TypeError`)."""
    sms = render_sms(_onset_msg(_onset_event(
        onset_precip_mm=2.5, event_end_time="20:00", is_convective=True,
        intensity_label="Starker Hagel/Gewitter",
    )))

    assert "18:00" in sms, f"Voraussetzung: der Beginn steht im Text: {sms!r}"
    hinter_beginn = sms.split("18:00", 1)[1]
    assert "@20:00" in hinter_beginn, (
        f"RED: der Gewitter-Zweig der Kurzform nennt das Ende nicht "
        f"minutengenau hinter dem Beginn-Token (erwartet '@20:00'): {sms!r}"
    )
    assert re.search(r"\bTH\d", sms) is None, (
        f"Ziffer unmittelbar hinter 'TH' — diese Position gehoert der Stufe: "
        f"{sms!r}"
    )


def test_ac12_sms_premium_sms_und_telegram_kurzstil_zeigen_dasselbe_ende(
    seven_io_stub, telegram_stub, monkeypatch,
):
    """AC-12 (Kanalvergleich, Muster #2046 AC-7) GIVEN denselben Onset-Alarm
    fuer SMS, Premium-SMS und Telegram im Kurzstil (Beginn `16:45`, Menge
    `2.5`, Ende `19:15`)
    WHEN `send_radar_alert(...)` alle drei konfigurierten Kanaele bedient
    THEN zeigen ALLE DREI denselben `sms_body` INKLUSIVE Ende-Token — kein
    Kanal zeigt ein anderes Ende, keiner laesst es aus.

    Warum das zaehlt: auf der Huette am Karnischen Hoehenweg kommt NUR
    Premium-SMS (Garmin inReach) an. Eine Angabe, die diesen Kanal nicht
    erreicht, erreicht dort niemanden.

    Die Zusicherung ist der VERGLEICH der drei tatsaechlich abgesetzten
    Nutzlasten, gemessen am Draht der lokalen Aufzeichnungs-Server.

    RED heute: `RadarAlertRequest` kennt `event_end_time` nicht
    (`TypeError`)."""
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid = fresh_uid("2051-ac12")
    clean_uid(uid)
    try:
        svc = NotificationService(_drei_kanal_settings(seven_io_stub.port), uid)

        svc.send_radar_alert(
            trip=make_trip("trip-2051-ac12"),
            request=RadarAlertRequest(
                onset_minutes=25, onset_time="16:45", km_from=0.0, km_to=6.0,
                is_convective=False, intensity_label="Mäßiger Regen",
                source_label="Radar (DWD)", tz=ZoneInfo("Europe/Vienna"),
                segment_id="Ziel", onset_precip_mm=2.5,
                event_end_time="19:15",
            ),
            source="Radar (DWD)",
            cooldown_display="2 Stunden",
            effective_channels={"sms", "premium_sms", "telegram"},
            telegram_style="kurzform",
        )

        nach_ziel = {p.get("to"): p.get("text") for p in seven_io_stub.received}
        assert set(nach_ziel) == {SMS_TO, PREMIUM_REPLY_TO}, (
            "Erwartet je EINEN seven.io-POST fuer SMS und Premium-SMS, "
            f"empfangen: {seven_io_stub.received!r}"
        )
        assert len(telegram_stub.sent) == 1, (
            f"Erwartet genau EINE Telegram-Nachricht: {telegram_stub.sent!r}"
        )

        sms_text = nach_ziel[SMS_TO]
        premium_text = nach_ziel[PREMIUM_REPLY_TO]
        telegram_text = telegram_stub.sent[0].get("text") or ""

        treffer = _KURZFORM_RE.search(sms_text)
        assert treffer is not None, (
            f"RED: die SMS nennt kein Ende hinter der Menge: {sms_text!r}"
        )
        assert treffer.group("ende") == "19:15", (
            f"Die SMS nennt ein anderes Ende als abgeleitet (erwartet "
            f"'19:15', minutengenau): {sms_text!r}"
        )
        assert premium_text == sms_text, (
            "RED: Premium-SMS und SMS muessen denselben Renderer-Ausgang "
            f"tragen.\n  premium = {premium_text!r}\n  sms     = {sms_text!r}"
        )
        assert telegram_text == sms_text, (
            "RED: der Telegram-Kurzstil muss denselben Text tragen wie die "
            f"SMS.\n  telegram = {telegram_text!r}\n  sms      = {sms_text!r}"
        )
    finally:
        clean_uid(uid)
