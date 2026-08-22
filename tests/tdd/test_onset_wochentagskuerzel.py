"""TDD RED — die Onset-Kurznachricht schreibt das WOCHENTAGSKUERZEL statt des
Zahlensuffixes.

SPEC: docs/specs/modules/feat_2054_onset_wochentagskuerzel.md (Issue #2054)

Was bewacht wird: Bis heute traegt der Kurzkanal (SMS · Premium-SMS ·
Telegram-Kurzstil) ZWEI Schreibweisen fuer denselben Sachverhalt "diese
Uhrzeit liegt an einem anderen Kalendertag" — `@0:23+1` beim Onset,
`@Do15` beim Abweichungsalarm (#2020 S2) und `Do12-22` bei der amtlichen
Warnung (#1948 S5). Danach kennt er genau eine: das vorangestellte Kuerzel
(`R2.5@Sa0:23`).

Warum das mehr ist als Kosmetik: die *Abwesenheit* der Altform ist Teil der
Akzeptanz (AC-8). Auf der Huette am Karnischen Hoehenweg kommt nur die
Premium-SMS an — es gibt dort keinen zweiten Kanal, der eine mehrdeutige
Zeitangabe richtigstellt.

Zwei Zusicherungen tragen die ganze Aenderung und werden deshalb an den
BILDUNGSSTELLEN geprueft, nicht nur am Renderer:

  * Der Trip-Radar-Alarm bildet sein `OnsetEvent` in
    `trip_alert.check_radar_alerts()` (ueber `RadarAlertRequest`) — AC-1.
  * Der Ortsvergleich bildet seines in
    `project.to_multi_location_onset_alert_message()` — AC-7 / AC-9.

Ein reiner Renderer-Test ginge still durch, wenn eine der beiden
Bildungsstellen das Kuerzel nie setzt; genau diese Fehlerklasse fand der
Adversary bei #2046 (F001) und #2051.

Mock-frei: echte Services, echte `NowcastResult`/`OnsetEvent`-Objekte, echter
Renderer, echter FastAPI-Endpunkt. Der Kurznachrichten-INHALT wird ueber den
Telegram-Kurzstil beobachtet — `_dispatch_alert_message()` sendet dort den
bereits gerenderten `sms_body` unveraendert (notification_service.py:1556),
und ein echter SMS-Versand wird nie ausgeloest (#1477). Der Draht ist ein
lokaler Aufzeichnungs-Server, kein `Mock()`/`patch()` von Verhalten.

RED-Ursachen heute:
  * `OnsetEvent` kennt weder `onset_weekday` noch `event_end_weekday`
    (unbekanntes Schluesselwort).
  * `_sms_onset_time()`/`_sms_onset_ende()` haengen `+1` an, statt ein
    Kuerzel voranzustellen.
  * `OnsetPayload` der Alarm-Vorschau fuehrt nicht einmal den VERSATZ.
"""
from __future__ import annotations

import http.server
import json
import re
import shutil
import socket
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

import output.channels.telegram as tg_module
from app.config import Settings
from app.loader import get_briefings_dir
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_sms, render_telegram
from services.radar_service import NowcastResult

from tests.helpers.nowcast_gate_fixtures import (
    TRIP_LAT, TRIP_LON, CountingFrameSource, clean_uid, fresh_uid, location,
    make_trip, radar_service, reset_radar_cache, save_trip, write_user_tier,
)

# ═════════════════════════ Gemeinsame Ausdruecke ═════════════════════════════

# Die ALTFORM: ein Zahlensuffix unmittelbar hinter einer Uhrzeit ("0:23+1").
# Diese Schreibweise soll nach der Umstellung NIRGENDS mehr vorkommen (AC-8).
ALTFORM_RE = re.compile(r"\d{1,2}:\d{2}\+\d+")

# Die ZIELFORM: ein deutsches Wochentagskuerzel unmittelbar VOR einer Uhrzeit
# ("Sa0:23"). Bewusst ohne Trennzeichen — die Kurznachricht ist zeichenknapp.
KUERZEL_VOR_ZEIT_RE = re.compile(r"(Mo|Di|Mi|Do|Fr|Sa|So)\s?\d{1,2}:\d{2}")

# Der 2026-08-21 ist ein FREITAG, der Folgetag also ein Samstag ("Sa"). Fest
# gewaehlt statt aus der Wanduhr abgeleitet: ein aus `date.today()` gerechneter
# Erwartungswert wuerde denselben Fehler machen wie der Pruefling.
FREITAG_2330_UTC = "2026-08-21T23:30:00+00:00"
FREITAG_1200_UTC = "2026-08-21T12:00:00+00:00"
# 21:40 UTC am Freitag = 23:40 Ortszeit Wien (UTC+2 im August). Der Onset
# (+53 Min) faellt auf 22:33 UTC — UTC-Tag immer noch FREITAG, Ortstag bereits
# SAMSTAG. Genau dieser Zeitpunkt trennt Ortstag von UTC-Tag (AC-9).
FREITAG_2140_UTC = "2026-08-21T21:40:00+00:00"


def onset_event(**kw) -> OnsetEvent:
    """Ein Onset-Ereignis mit festen Feldern (keine Wanduhr).

    Die Renderer lesen ausschliesslich das uebergebene Objekt — dieselbe
    Bauweise wie `tests/tdd/test_alert_onset_day_rollover.py::_onset_event`.
    """
    fields = dict(
        onset_minutes=53, onset_time="00:23", km_from=8.0, km_to=8.0,
        is_convective=False, intensity_label="Starker Regen",
        source_label="INCA", onset_precip_mm=2.5,
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def onset_msg(event: OnsetEvent, *, trip_short: str = "KHW 403") -> AlertMessage:
    """`source is not None` routet die Renderer in den Onset-Zweig."""
    return AlertMessage(
        trip_short=trip_short, stand_at="23:30", events=(event,), source="radar",
    )


# ══════════════════ Echter lokaler Telegram-Bot-API-Stub ═════════════════════
#
# Transport-Umlenkung auf einen echten HTTP-Server — kein Verhaltens-Mock.
# Gemessen wird die Nutzlast, die tatsaechlich am Draht ankam.


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 7000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                body = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
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
def telegram_stub():
    stub = _TelegramStub()
    yield stub
    stub.stop()


def _telegram_only_settings(marke: str) -> Settings:
    """Nur Telegram sendebereit — E-Mail, SMS und Premium-SMS ausdruecklich
    AUS. Jedes weggelassene Feld faellt bei pydantic still auf die Prod-`.env`
    des Arbeitsverzeichnisses zurueck (#1477).

    `telegram_test_chat_id` ist Pflicht fuer die Herkunftssperre des
    Telegram-Kanals aus einem Nicht-Prod-Checkout (#1476)."""
    return Settings(
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
        telegram_bot_token=f"test-token-2054-{marke}",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        sms_gateway_url="", seven_api_key="", seven_sandbox_key="",
        sms_to="", sms_from=None,
        premium_sms_reply_to=None, premium_sms_reply_at=None,
    )


# ═══════════════ Der ECHTE Trip-Versandpfad (Bildungsstelle 1) ═══════════════


def _kurznachricht_vom_trip_pfad(
    zeitpunkt: str, telegram_stub, monkeypatch, *,
    ankunft_start: str, ankunft_ende: str,
) -> str:
    """Faehrt `TripAlertService.check_radar_alerts()` unter gestellter Uhr und
    gibt den Kurznachrichten-TEXT zurueck, der am Draht ankam.

    Der Trip-Radar-Alarm ist der einzige Produktivpfad, der einen
    `RadarAlertRequest` baut — dort entsteht der Tagesbezug des BEGINNS
    (trip_alert.py:~1517). Reykjavik-Koordinaten (`make_trip`-Default,
    ganzjaehrig UTC+0): die Ortszeit ist direkt aus der gestellten UTC-Zeit
    ablesbar, ohne Zonenrechnung im Test.

    `telegram_style="kurzform"` laesst `_dispatch_alert_message()` den bereits
    gerenderten `sms_body` senden — der Kurznachrichten-Inhalt wird damit
    beobachtbar, OHNE je einen SMS-Versand auszuloesen (#1477).
    """
    from services.trip_alert import TripAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid = fresh_uid("2054-trip")
    clean_uid(uid)
    reset_radar_cache()
    try:
        with freeze_time(zeitpunkt):
            write_user_tier(uid, "premium")
            trip = make_trip(
                "trip-2054-kuerzel",
                stage_date=datetime.now(timezone.utc).date(),
                arrival_start=ankunft_start, arrival_end=ankunft_ende,
            )
            save_trip(trip, uid)
            # Der Fixture-Schreiber kennt `telegram_style` nicht; die Datei
            # wird deshalb nachtraeglich um genau die Kanal-Felder ergaenzt,
            # die `check_radar_alerts()` von Platte zurueckliest.
            pfad = get_briefings_dir(uid) / f"{trip.id}.json"
            daten = json.loads(pfad.read_text())
            daten["report_config"].update({
                "send_email": False, "send_telegram": True,
                "send_sms": False, "send_premium_sms": False,
                "telegram_style": "kurzform",
            })
            pfad.write_text(json.dumps(daten))

            svc = TripAlertService(
                settings=_telegram_only_settings("trip"), throttle_hours=0,
                user_id=uid, radar_service=radar_service(
                    CountingFrameSource(onset_minutes=53),
                ),
            )
            vorher = len(telegram_stub.sent)
            sent = svc.check_radar_alerts()

        assert sent == 1, (
            f"Testvoraussetzung bei {zeitpunkt}: genau EIN Trip-Radar-Alarm "
            f"haette abgesetzt werden muessen, war {sent}"
        )
        neu = telegram_stub.sent[vorher:]
        assert len(neu) == 1, (
            f"Erwartet genau EINE Kurznachricht am Draht: {neu!r}"
        )
        return neu[0].get("text") or ""
    finally:
        clean_uid(uid)


# ═══════════════════════════════ AC-1 ════════════════════════════════════════


def test_ac1_trip_versandpfad_zeigt_wochentagskuerzel_statt_suffix(
    telegram_stub, monkeypatch,
):
    """AC-1 GIVEN einen Trip-Radar-Alarm, dessen Regenbeginn hinter
    Mitternacht auf einen Samstag faellt (Freitag 23:30 Ortszeit + 53 Min =
    00:23 am Samstag)
    WHEN die Kurznachricht ueber den ECHTEN Versandpfad
    (`TripAlertService.check_radar_alerts()`) erzeugt und zugestellt wird
    THEN traegt die Uhrzeit das vorangestellte Kuerzel `Sa` und KEIN
    Zahlensuffix.

    Die Etappe laeuft 22:00 -> 02:00, das aktive Segment endet also NACH dem
    Onset — sonst unterdrueckte der Segment-Ende-Riegel den Alarm und der Test
    maesse diesen statt der Schreibweise.

    Bewacht die erste der beiden Beginn-Bildungsstellen: ein reiner
    Renderer-Test bliebe gruen, wenn `RadarAlertRequest`/
    `check_radar_alerts()` das Kuerzel nie setzten.

    RED heute: die Nachricht traegt `@0:23+1`.
    """
    text = _kurznachricht_vom_trip_pfad(
        FREITAG_2330_UTC, telegram_stub, monkeypatch,
        ankunft_start="22:00", ankunft_ende="02:00",
    )

    assert "@Sa0:23" in text, (
        f"Der Trip-Versandpfad haette den Beginn als '@Sa0:23' ausweisen "
        f"muessen (Freitag 23:30 Ortszeit + 53 Min). Kurznachricht: {text!r}"
    )
    assert not ALTFORM_RE.search(text), (
        f"Die Altform (Zahlensuffix hinter der Uhrzeit) steht noch in der "
        f"Kurznachricht: {text!r}"
    )


# ═══════════════════════════════ AC-2 ════════════════════════════════════════


def test_ac2_versandtag_bleibt_zeichengleich_zum_bestand(
    telegram_stub, monkeypatch,
):
    """AC-2 GIVEN denselben Alarm, aber mit einem Regenbeginn AM VERSANDTAG
    WHEN die Kurznachricht erzeugt wird
    THEN ist sie zeichengleich zum heutigen Bestand — kein Kuerzel, kein
    Suffix, keine sonstige Abweichung.

    Diese Eigenschaft macht die Umstellung regressionsfrei (ausdruecklich im
    Ticket-Kommentar gefordert) und wird an BEIDEN Enden geprueft: am Renderer
    gegen den festgeschriebenen Bestands-String und am echten Trip-Pfad
    (12:00 Ortszeit + 53 Min = 12:53, kein Tageswechsel).

    POSITIVKONTROLLE (Pflicht bei einem Test auf ein AUSBLEIBEN): derselbe
    Renderer-Aufruf mit Versatz 1 und hinterlegtem Kuerzel MUSS ein anderes,
    kuerzeltragendes Ergebnis liefern. Ohne sie waere die Zusicherung
    "unveraendert" auch dann gruen, wenn das Kuerzel NIRGENDS erschiene.
    """
    # Renderer: der festgeschriebene Bestands-String, Zeichen fuer Zeichen.
    bestand = render_sms(onset_msg(onset_event(onset_time="18:00")))
    assert bestand == "km 8-8: R2.5@18:00", (
        f"Ohne Tageswechsel muss die Kurznachricht zeichengleich zum Bestand "
        f"bleiben: {bestand!r}"
    )

    # Derselbe Nachweis am ECHTEN Versandpfad — bewusst VOR der
    # Positivkontrolle, damit er schon in der RED-Phase durchlaeuft und belegt
    # ist, dass der Pfad ueberhaupt angefahren wird.
    text = _kurznachricht_vom_trip_pfad(
        FREITAG_1200_UTC, telegram_stub, monkeypatch,
        ankunft_start="11:00", ankunft_ende="14:00",
    )
    assert "@12:53" in text, (
        f"Ohne Tageswechsel (12:00 + 53 Min = 12:53) muss die nackte Uhrzeit "
        f"stehen bleiben: {text!r}"
    )
    assert not KUERZEL_VOR_ZEIT_RE.search(text), (
        f"Am Versandtag darf KEIN Wochentagskuerzel erscheinen — der Versatz "
        f"entscheidet, nicht die Bildungsstelle: {text!r}"
    )
    assert not ALTFORM_RE.search(text), (
        f"Am Versandtag darf auch kein Zahlensuffix erscheinen: {text!r}"
    )

    # Positivkontrolle: mit Versatz UND Kuerzel sieht dasselbe Feld anders aus.
    mit_kuerzel = render_sms(onset_msg(onset_event(
        onset_time="18:00", onset_day_offset=1, onset_weekday="Sa",
    )))
    assert mit_kuerzel != bestand and "@Sa18:00" in mit_kuerzel, (
        f"Positivkontrolle: mit Versatz 1 MUSS das Kuerzel erscheinen — sonst "
        f"bewacht die Gleichheitspruefung oben nichts: {mit_kuerzel!r}"
    )


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_endzeit_traegt_das_kuerzel():
    """AC-3 GIVEN einen Alarm, dessen EREIGNIS-ENDE hinter Mitternacht faellt
    WHEN die Kurznachricht erzeugt wird
    THEN traegt auch die Endzeit das Kuerzel (`@Sa0:40`).

    Bewacht den zweiten Wirkort (`_sms_onset_ende`, render.py:796), den das
    Ticket nicht kennt: das Ende-Token entstand erst mit #2051 S1 und
    formatiert seine Uhrzeit ueber DENSELBEN Baustein wie der Beginn.

    RED heute: `OnsetEvent` kennt `event_end_weekday` nicht; nach dem
    Anlegen des Feldes stuende dort weiter `@0:40+1`.
    """
    sms = render_sms(onset_msg(onset_event(
        onset_time="23:50", event_end_time="00:40",
        event_end_day_offset=1, event_end_weekday="Sa",
    )))

    assert "@Sa0:40" in sms, (
        f"Die Endzeit haette das Kuerzel tragen muessen: {sms!r}"
    )
    assert not ALTFORM_RE.search(sms), (
        f"Die Altform steht noch am Ende-Token: {sms!r}"
    )


# ═══════════════════════════════ AC-4 ════════════════════════════════════════


def test_ac4_beginn_und_ende_werden_unabhaengig_bewertet():
    """AC-4 GIVEN einen Alarm, der um 23:50 beginnt und um 00:40 endet
    WHEN die Kurznachricht erzeugt wird
    THEN traegt NUR die Endzeit ein Kuerzel, die Beginnzeit nicht — beide
    Zeitpunkte werden unabhaengig voneinander bewertet.

    Ein gemeinsamer Tagesbezug fuer beide Zeitpunkte waere fuer genau diesen,
    haeufigsten Ueberlauf-Fall still falsch.
    """
    sms = render_sms(onset_msg(onset_event(
        onset_time="23:50", onset_day_offset=0, onset_weekday=None,
        event_end_time="00:40", event_end_day_offset=1, event_end_weekday="Sa",
    )))

    assert sms == "km 8-8: R2.5@23:50@Sa0:40", (
        f"Erwartet 'km 8-8: R2.5@23:50@Sa0:40' — nur die Endzeit traegt das "
        f"Kuerzel: {sms!r}"
    )


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_untergrenzen_zeichen_bleibt_vor_dem_kuerzel():
    """AC-5 GIVEN ein Ereignis, dessen Ende nur als UNTERGRENZE bekannt ist
    ("regnet mindestens bis") und das hinter Mitternacht reicht
    WHEN die Kurznachricht erzeugt wird
    THEN bleibt das Untergrenzen-Zeichen `>` erhalten und das Kuerzel steht
    dahinter (` >@Sa0:40`).

    An diesem einen Zeichen haengt die Bedeutung: ohne `>` kippt die Aussage
    von "regnet mindestens bis" zu "hoert auf um" (#2051 AC-20). Das Kuerzel
    darf diese Unterscheidung nicht verdraengen.
    """
    sms = render_sms(onset_msg(onset_event(
        onset_time="23:50", event_end_time="00:40",
        event_end_day_offset=1, event_end_weekday="Sa",
        event_ongoing_beyond_horizon=True,
    )))

    assert sms == "km 8-8: R2.5@23:50 >@Sa0:40", (
        f"Erwartet die Untergrenzen-Form ' >@Sa0:40' mit erhaltenem '>': "
        f"{sms!r}"
    )


# ═══════════════════════════════ AC-6 ════════════════════════════════════════


def test_ac6_gewitterzweig_traegt_das_kuerzel():
    """AC-6 GIVEN einen GEWITTER-Onset mit Mitternachts-Ueberlauf
    WHEN die Kurznachricht erzeugt wird
    THEN traegt die Uhrzeit das Kuerzel genauso wie beim Regen
    (`TH@Sa0:23 R2.5`).

    Das Ticket verlangt die Umstellung ausdruecklich fuer BEIDE Zweige; der
    Gewitter-Zweig baut sein Token an einer eigenen Stelle zusammen
    (`_render_sms_onset`, Menge NACH der Zeit) und kann deshalb getrennt
    zurueckbleiben.
    """
    sms = render_sms(onset_msg(onset_event(
        is_convective=True, onset_day_offset=1, onset_weekday="Sa",
    )))

    assert sms == "km 8-8: TH@Sa0:23 R2.5", (
        f"Erwartet 'km 8-8: TH@Sa0:23 R2.5' — der Gewitter-Zweig traegt "
        f"dasselbe Kuerzel wie der Regen-Zweig: {sms!r}"
    )


# ═══════════════════════════════ AC-7 ════════════════════════════════════════


def test_ac7_ortsvergleich_buendel_traegt_das_kuerzel():
    """AC-7 GIVEN einen ORTSVERGLEICH-Onset-Alarm mit Mitternachts-Ueberlauf
    WHEN die Kurznachricht erzeugt wird
    THEN traegt sie das Kuerzel genauso wie der Trip-Alarm.

    Wirkort ist `to_multi_location_onset_alert_message()` selbst: dort baut
    der Ortsvergleich sein `OnsetEvent` (project.py:~544) — die ZWEITE
    Beginn-Bildungsstelle, die ohne eigenen Nachweis still ausbleibt. Genau
    diese Fehlerklasse fand der Adversary bei #2046 (F001).

    Reykjavik (ganzjaehrig UTC+0): Freitag 23:30 + 53 Min = 00:23 am Samstag.
    Ein Ort -> `location_label is None`, der Kopf ist der Ortsname.
    """
    rvk = location("loc-2054", "Reykjavik", lat=TRIP_LAT, lon=TRIP_LON)
    nc = NowcastResult(
        onset_minutes=53, intensity_label="Starker Regen", source="INCA",
    )

    with freeze_time(FREITAG_2330_UTC):
        sms = render_sms(to_multi_location_onset_alert_message(
            [("Reykjavik", rvk, nc)],
            tz=ZoneInfo("Atlantic/Reykjavik"), stand_at="23:30",
        ))

    assert "@Sa0:23" in sms, (
        f"Der Ortsvergleich-Buendelpfad haette den Beginn als '@Sa0:23' "
        f"ausweisen muessen: {sms!r}"
    )
    assert not ALTFORM_RE.search(sms), (
        f"Die Altform steht noch in der Ortsvergleich-Kurznachricht: {sms!r}"
    )


# ═══════════════════════════════ AC-8 ════════════════════════════════════════


def _fallmatrix(mit_kuerzel: bool) -> list[tuple[str, OnsetEvent]]:
    """Beginn-Versatz × Ende-Versatz × Ende-Form × Regen/Gewitter ×
    laeuft-bereits — die Zusammenstellungen, in denen eine Uhrzeit ueberhaupt
    vorkommen kann.

    `mit_kuerzel=False` baut dieselben Faelle OHNE die neuen Felder: so haengt
    die Altform-Pruefung nicht am Anlegen der Felder und meldet schon heute
    den konkreten Token statt eines Konstruktionsfehlers.
    """
    faelle: list[tuple[str, OnsetEvent]] = []
    for konvektiv in (False, True):
        for laeuft in (False, True):
            for beginn_versatz in (0, 1):
                for ende in (None, ("00:40", 0), ("00:40", 1)):
                    for untergrenze in (False, True):
                        if ende is None and untergrenze:
                            continue  # ohne Ende gibt es keine Ende-Form
                        felder: dict = dict(
                            onset_time="23:50" if beginn_versatz == 0 else "00:23",
                            onset_day_offset=beginn_versatz,
                            is_convective=konvektiv,
                            already_running=laeuft,
                            event_ongoing_beyond_horizon=untergrenze,
                        )
                        if ende is not None:
                            felder["event_end_time"] = ende[0]
                            felder["event_end_day_offset"] = ende[1]
                        if mit_kuerzel:
                            felder["onset_weekday"] = (
                                "Sa" if beginn_versatz else None
                            )
                            felder["event_end_weekday"] = (
                                "So" if (ende and ende[1]) else None
                            )
                        name = (
                            f"konvektiv={konvektiv} laeuft={laeuft} "
                            f"beginn+{beginn_versatz} ende={ende} "
                            f"untergrenze={untergrenze}"
                        )
                        faelle.append((name, onset_event(**felder)))
    return faelle


def test_ac8_keine_uhrzeit_traegt_irgendwo_ein_zahlensuffix():
    """AC-8 GIVEN IRGENDEINEN Onset-Alarm in irgendeiner Zusammenstellung
    WHEN die Kurznachricht erzeugt wird
    THEN enthaelt sie NIRGENDS ein Zahlensuffix hinter einer Uhrzeit.

    Dies ist die zentrale Zusicherung "genau EINE Schreibweise" — sie geht
    rot, egal an welcher Bildungsstelle oder in welchem der drei Render-Zweige
    (`already_running` / ohne Menge / mit Menge) eine Regression entsteht.

    POSITIVKONTROLLE (Pflicht bei einem Test auf ein AUSBLEIBEN): der Ausdruck
    selbst wird gegen die bekannte Altform gehalten. Ein Ausdruck, der nichts
    faengt, waere sonst ueber die ganze Matrix hinweg still gruen.
    """
    assert ALTFORM_RE.search("km 8-8: R2.5@0:23+1"), (
        "Positivkontrolle: der Altform-Ausdruck muss die bekannte Altform "
        "'0:23+1' finden — sonst bewacht die Matrix unten nichts"
    )

    # Erster Durchgang OHNE die neuen Felder: haengt nicht am Modell und
    # meldet schon heute den konkreten Token.
    treffer = [
        (name, render_sms(onset_msg(ev)))
        for name, ev in _fallmatrix(mit_kuerzel=False)
        if ALTFORM_RE.search(render_sms(onset_msg(ev)))
    ]
    assert not treffer, (
        "Die Altform (Zahlensuffix hinter einer Uhrzeit) kommt noch vor — "
        "es gibt damit weiter ZWEI Schreibweisen fuer denselben Sachverhalt:\n"
        + "\n".join(f"  {name}: {text!r}" for name, text in treffer)
    )

    # Zweiter Durchgang MIT Kuerzeln: keine Altform, und jeder Versatz ist
    # als Kuerzel sichtbar.
    ohne_kuerzel: list[tuple[str, str]] = []
    for name, ev in _fallmatrix(mit_kuerzel=True):
        text = render_sms(onset_msg(ev))
        assert not ALTFORM_RE.search(text), (
            f"Altform trotz gesetzter Kuerzel — {name}: {text!r}"
        )
        erwartet_kuerzel = (
            (ev.onset_day_offset == 1 and not ev.already_running)
            or ev.event_end_day_offset == 1
        )
        if erwartet_kuerzel and not KUERZEL_VOR_ZEIT_RE.search(text):
            ohne_kuerzel.append((name, text))
    assert not ohne_kuerzel, (
        "Diese Faelle tragen einen Tagesversatz, aber KEIN Kuerzel — der "
        "Tagesbezug wird still verschluckt:\n"
        + "\n".join(f"  {name}: {text!r}" for name, text in ohne_kuerzel)
    )


# ═══════════════════════════════ AC-9 ════════════════════════════════════════


def test_ac9_kuerzel_nennt_den_ortstag_nicht_den_utc_tag():
    """AC-9 GIVEN einen Ort, dessen Ortszeit von UTC abweicht, und einen
    Zeitpunkt kurz nach Mitternacht ORTSZEIT
    WHEN das Kuerzel gebildet wird
    THEN nennt es den Wochentag der ORTSZEIT, nicht den der UTC-Zeit.

    Aufbau: Freitag 21:40 UTC = 23:40 Ortszeit Wien (UTC+2 im August). Der
    Onset (+53 Min) liegt bei 22:33 UTC — UTC-Tag ist immer noch FREITAG,
    Ortstag bereits SAMSTAG. Wer das Kuerzel aus dem UTC-Zeitpunkt bildet,
    schreibt `Fr` und liegt bei korrektem Versatz um einen Tag daneben; nur
    ein aus `local_dt(dt, tz)` gebildetes Kuerzel schreibt `Sa`.

    Gemessen wird am Ortsvergleich-Buendelpfad, weil der die Zone JE ORT
    aufloest — dieselbe Stelle, an der auch der Versatz entsteht.
    """
    wien = location("loc-2054-wien", "Wien")
    nc = NowcastResult(
        onset_minutes=53, intensity_label="Starker Regen", source="INCA",
    )

    with freeze_time(FREITAG_2140_UTC):
        sms = render_sms(to_multi_location_onset_alert_message(
            [("Wien", wien, nc)],
            tz=ZoneInfo("Europe/Vienna"), stand_at="23:40",
        ))

    assert "@Sa0:33" in sms, (
        f"Erwartet den ORTSTAG 'Sa' vor 0:33 (Wien 00:33 am Samstag): {sms!r}"
    )
    assert "Fr0:33" not in sms, (
        f"'Fr' waere der UTC-Tag (22:33 UTC am Freitag) — das Kuerzel muss aus "
        f"der Ortszeit kommen: {sms!r}"
    )


# ══════════════════════════════ AC-10 ════════════════════════════════════════


def test_ac10_der_versatz_entscheidet_nicht_das_vorhandene_kuerzel():
    """AC-10 GIVEN ein Ereignis AM VERSANDTAG, bei dem versehentlich dennoch
    ein Wochentag am Datensatz hinterlegt ist
    WHEN die Kurznachricht erzeugt wird
    THEN erscheint KEIN Kuerzel — die Ausgabe bleibt die nackte Uhrzeit.

    Sichert die Gate-Richtung zu: der VERSATZ entscheidet, ob ein Tagesbezug
    gezeigt wird; das Kuerzel ist nur seine Darstellung. Ein Gate auf den
    Wahrheitswert von `weekday` wuerde bei fehlendem Kuerzel still den
    Tagesbezug verschlucken — und hier ein falsches "Sa" an einer Uhrzeit von
    heute zeigen.

    POSITIVKONTROLLE (Pflicht bei einem Test auf ein AUSBLEIBEN): DASSELBE
    Kuerzel am DEMSELBEN Feld erscheint sehr wohl, sobald der Versatz 1 ist —
    fuer Beginn und Ende getrennt. Ohne sie waere der Test auch dann gruen,
    wenn das Kuerzel ueberhaupt nie ausgegeben wuerde.
    """
    beginn_heute = render_sms(onset_msg(onset_event(
        onset_time="18:00", onset_day_offset=0, onset_weekday="Sa",
    )))
    assert beginn_heute == "km 8-8: R2.5@18:00", (
        f"Versatz 0 mit hinterlegtem Kuerzel muss die nackte Uhrzeit "
        f"ausgeben: {beginn_heute!r}"
    )

    ende_heute = render_sms(onset_msg(onset_event(
        onset_time="18:00", event_end_time="20:00",
        event_end_day_offset=0, event_end_weekday="Sa",
    )))
    assert ende_heute == "km 8-8: R2.5@18:00@20:00", (
        f"Auch am Ende-Token entscheidet der Versatz, nicht das hinterlegte "
        f"Kuerzel: {ende_heute!r}"
    )

    # Positivkontrolle, je Feld getrennt.
    beginn_morgen = render_sms(onset_msg(onset_event(
        onset_time="18:00", onset_day_offset=1, onset_weekday="Sa",
    )))
    assert "@Sa18:00" in beginn_morgen, (
        f"Positivkontrolle Beginn: mit Versatz 1 MUSS 'Sa' erscheinen — sonst "
        f"bewacht die Abwesenheitspruefung oben nichts: {beginn_morgen!r}"
    )
    ende_morgen = render_sms(onset_msg(onset_event(
        onset_time="18:00", event_end_time="20:00",
        event_end_day_offset=1, event_end_weekday="Sa",
    )))
    assert "@Sa20:00" in ende_morgen, (
        f"Positivkontrolle Ende: mit Versatz 1 MUSS 'Sa' erscheinen: "
        f"{ende_morgen!r}"
    )


# ══════════════════════════════ AC-11 ════════════════════════════════════════


def test_ac11_laengster_fall_bleibt_unter_160_zeichen_und_ascii():
    """AC-11 GIVEN den laengsten Fall (Gewitter, Menge, Beginn UND Ende mit
    Kuerzel, Untergrenzen-Form)
    WHEN die Kurznachricht erzeugt wird
    THEN bleibt sie unter 160 Zeichen und besteht ausschliesslich aus
    ASCII-Zeichen.

    Die Laengengrenze allein waere trivial erfuellt (der Renderer kuerzt schon
    bei 140) — deshalb wird ZUSAETZLICH geprueft, dass der vollstaendige Token
    unbeschnitten dasteht. Sonst waere eine abgeschnittene und damit falsche
    Uhrzeit als "kurz genug" durchgegangen.

    Beginn und Ende tragen ABSICHTLICH verschiedene Kuerzel (`Sa`/`So`): das
    belegt in einem Zug, dass beide Zeitpunkte ihr eigenes Kuerzel fuehren.
    """
    sms = render_sms(onset_msg(onset_event(
        is_convective=True, onset_time="23:50",
        onset_day_offset=1, onset_weekday="Sa",
        event_end_time="00:40", event_end_day_offset=1, event_end_weekday="So",
        event_ongoing_beyond_horizon=True, onset_precip_mm=12.3,
    )))

    assert "TH@Sa23:50 >@So0:40 R12.3" in sms, (
        f"Der laengste Fall muss unbeschnitten dastehen — sonst zeigt die "
        f"Kurznachricht eine angeschnittene Uhrzeit: {sms!r}"
    )
    assert len(sms) <= 160, (
        f"Kurznachricht ueberschreitet die 160-Zeichen-Grenze: {len(sms)} — "
        f"{sms!r}"
    )
    assert sms.isascii(), (
        f"Kurznachricht enthaelt Nicht-ASCII-Zeichen (GSM-7): {sms!r}"
    )


# ══════════════════════════════ AC-12 ════════════════════════════════════════


@pytest.fixture
def preview_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def preview_trip():
    user_id = f"test_2054_onset_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-2054-vorschau"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Vorschau-Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.mark.real_data_root
def test_ac12_alarmvorschau_zeigt_dieselbe_schreibweise(
    preview_client, preview_trip,
):
    """AC-12 GIVEN denselben Mitternachts-Ueberlauf
    WHEN die Alarm-VORSCHAU (`POST /api/trips/{id}/alert-preview`) abgerufen
    wird
    THEN zeigt sie dieselbe Schreibweise wie der echte Versand (`@Sa0:23`).

    WAS DIESER TEST HEUTE MISST: die fehlende DURCHREICHUNG. `OnsetPayload`
    (api/routers/validator.py:~226) fuehrt weder `onset_day_offset` noch
    `onset_weekday` — pydantic verwirft unbekannte Schluessel STILL, und
    `validator_render_service.render_alert_preview()` (Zeile ~116) baut sein
    `OnsetEvent` ohne beide Felder. Die Vorschau kann den Sachverhalt damit
    heute gar nicht darstellen; sie zeigt `R@0:23` und behauptet einen
    Zeitpunkt von heute, wo der Versand einen von morgen meldet.

    Der Test bleibt deshalb bewusst auf der ANTWORT des Endpunkts (nicht auf
    dem Modell): rot ist er, solange die Ergaenzung an `OnsetPayload` und am
    Vorschau-Renderer fehlt — genau die von der Spec geforderte Arbeit.

    Muster: `tests/tdd/test_alert_preview_onset_payload.py` (#2046 F002,
    dieselbe Fehlerklasse: ein still verworfenes Payload-Feld).
    """
    user_id, trip_id = preview_trip
    resp = preview_client.post(
        f"/api/trips/{trip_id}/alert-preview",
        params={"user_id": user_id},
        json={"onset": {
            "onset_minutes": 53,
            "onset_time": "00:23",
            "onset_day_offset": 1,
            "onset_weekday": "Sa",
            "km_from": 0.0,
            "km_to": 6.0,
            "is_convective": False,
            "intensity_label": "starker Regen",
            "source_label": "Radar (DWD)",
        }},
    )

    assert resp.status_code == 200, f"Body: {resp.text[:300]}"
    sms = resp.json().get("sms") or ""
    assert "@Sa0:23" in sms, (
        "Die Alarm-Vorschau reicht Tagesversatz und Wochentagskuerzel nicht "
        f"bis zum Renderer durch und zeigt eine andere Schreibweise als der "
        f"echte Versand: {sms!r}"
    )
    assert not ALTFORM_RE.search(sms), (
        f"Die Vorschau zeigt die Altform: {sms!r}"
    )


# ══════════════════════════════ AC-14 ════════════════════════════════════════


def test_ac14_laufendes_ereignis_behaelt_now_und_endzeit_traegt_kuerzel():
    """AC-14 GIVEN ein Ereignis, das BEREITS LAEUFT (die Kurzform zeigt `now`
    statt einer Beginnzeit) und dessen Ende hinter Mitternacht faellt
    WHEN die Kurznachricht erzeugt wird
    THEN traegt die Endzeit das Kuerzel, und das `now` bleibt unveraendert
    stehen (`R2.5 now >@Sa0:40`).

    Dieser dritte Render-Zweig entstand durch #2050 S2b erst NACH der Freigabe
    der Spec und erbt das Ende-Token ueber denselben Aufruf. `now` ist
    ENGLISCH wie die ganze Kurzform und darf durch die Umstellung nicht
    beruehrt werden.
    """
    sms = render_sms(onset_msg(onset_event(
        already_running=True,
        event_end_time="00:40", event_end_day_offset=1, event_end_weekday="Sa",
        event_ongoing_beyond_horizon=True,
    )))

    assert sms == "km 8-8: R2.5 now >@Sa0:40", (
        f"Erwartet 'km 8-8: R2.5 now >@Sa0:40' — `now` unveraendert, Endzeit "
        f"mit Kuerzel: {sms!r}"
    )


# ══════════════════════════════ AC-13 ════════════════════════════════════════


def test_ac13_langform_bleibt_beim_tageswort():
    """AC-13 GIVEN denselben Alarm
    WHEN E-Mail und Telegram-LANGFORM erzeugt werden
    THEN schreiben sie den Tagesbezug unveraendert als WORT ("morgen 00:23"),
    nicht als Kuerzel.

    Kurzform = Kuerzel, Langform = Wort ist eine bewusste Trennung (die
    Langform hat kein Zeichenbudget-Problem) und darf nicht angeglichen
    werden.

    POSITIVKONTROLLE (Pflicht bei einem Test auf ein AUSBLEIBEN): DIESELBE
    `AlertMessage` traegt in der KURZform sehr wohl das Kuerzel. Ohne sie
    waere der Test auch dann gruen, wenn das Kuerzel nirgends entstuende —
    und bewiese dann nur, dass sich nichts geaendert hat.
    """
    msg = onset_msg(onset_event(onset_day_offset=1, onset_weekday="Sa"))

    _, plain = render_email(msg)
    telegram = render_telegram(msg)

    assert "morgen 00:23" in plain, (
        f"Die E-Mail-Langform muss beim Tageswort bleiben: {plain!r}"
    )
    assert "morgen 00:23" in telegram, (
        f"Die Telegram-Langform muss beim Tageswort bleiben: {telegram!r}"
    )
    for name, text in (("E-Mail", plain), ("Telegram-Langform", telegram)):
        assert not KUERZEL_VOR_ZEIT_RE.search(text), (
            f"{name} schreibt ein Wochentagskuerzel vor einer Uhrzeit — die "
            f"Langform bleibt beim Wort: {text!r}"
        )

    # Positivkontrolle: dieselbe Meldung, Kurzform.
    kurz = render_sms(msg)
    assert "@Sa0:23" in kurz, (
        f"Positivkontrolle: die KURZform derselben Meldung MUSS das Kuerzel "
        f"tragen — sonst bewacht die Abwesenheitspruefung oben nichts: "
        f"{kurz!r}"
    )
