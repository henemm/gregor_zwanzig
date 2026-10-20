"""TDD RED -- Issue #1737: Abweichungsalarm zeigt Stundenzeilen (alt -> neu je Stunde).

Spec: docs/specs/modules/feat_1737_alarm_stundenzeilen.md (AC-1 bis AC-13, Test Plan 1-11).

Kein Mock-Theater. Eingaben sind versionierte Stundenreihen in genau dem Format, in
dem Anker und Snapshot sie persistieren (``{"ts": iso, <dp_feld>: wert}``,
``tests/fixtures/alert_hour_rows/*.json``) und werden ueber den ECHTEN Lader
``weather_snapshot._deserialize_timeseries`` zu ``NormalizedTimeseries``. Es sind
SYNTHETISCHE Reihen in Anker-Format (kein Provider-Mitschnitt); jede Datei nennt in
``beschreibung`` ihre Absicht (u. a.: Anker startet 1 h frueher als die frische Reihe,
damit Index-Paarung falsch waere; Abweichungen AUSSERHALB des Segmentfensters;
Zeitstempel in UTC, Erwartung in Ortszeit UTC+2). Erwartete Zellen werden NIE von
Hand getippt, sondern mit dem Briefing-Formatierer ``email.helpers.fmt_val`` gebildet
("genau so wie das Briefing desselben Kanals").

Transport: ``tests/helpers/transport_mitschrift.aufzeichner_installieren`` (ersetzt nur
die vier Ausgangs-Klassen, oeffnet KEINE Sockets -- laeuft unter ``--disable-socket``).

Von diesen Tests festgelegte Schnittstellen (die GREEN-Phase baut genau diese):

  Modell (``output.renderers.alert.model``)
    ``AlertHourRow`` (frozen dataclass): ``time: str`` ("HH:MM" ORTSZEIT),
        ``value_from: float | None`` (None = kein Anker), ``value_to: float``.
        Fuer Stufenmetriken tragen die Werte die Ordinale (Gewitter 0..3) bzw. den
        Stundenwert -- die Darstellung (Wort/Zahl/Punkt) bildet der Renderer.
    ``AlertEvent.hours: tuple[AlertHourRow, ...] = ()`` (additiv, Default leer).
    ``AlertMessage.format_modes: dict[str, dict[str, str]]`` (additiv, Default leer):
        Kanal ("email"|"telegram"|"sms") -> {col_key: format_mode}, exakt die Form von
        ``email.helpers.build_format_modes``. Leer/fehlend = "raw".

  Projektion (``output.renderers.alert.project``)
    ``to_alert_message(..., anchor_segments=None, format_modes=None)``
        ``anchor_segments``: ALTE Reihe = ``list[SegmentWeatherData]`` (Anker); die
        frische Reihe ist ``segments`` (``SegmentWeatherData.timeseries``).
    ``to_multi_point_alert_message(..., anchor_points=None, format_modes=None)``
        ``anchor_points``: ``dict[Ortsname, PointWeatherData]`` (alte Reihe je Ort); die
        frische Reihe steht im 3. Glied jeder Gruppe (``point.timeseries``). Name-keyed
        und NICHT als 4. Tupel-Glied, damit die Telegram-Aufspaltung je Ort
        (``to_multi_point_alert_message([g], ...)``) und die Vorschau denselben Anker sehen.
    Paarung der Stunden per UTC-Zeitstempel, nicht per Index.

  Renderer (``output.renderers.alert.render``) -- Stundenzeile in E-Mail (Klartext UND
    HTML-Tabelle) und Telegram: ``HH:MM | alt -> neu`` (Pfeil U+2192, ``" | "`` zwischen
    Zeit und Wert); ohne Anker ``HH:MM | neu``. HTML: eine ``<tr>`` je Stunde, erste Zelle
    = ``HH:MM``, EINFACH = CSS-Punkte (``fmt_val(..., html=True)``), ROH = Wort/Zahl.
    Kappung: hoechstens 6 Zeilen je Ereignis + Hinweiszeile ``betroffen HH:MM–HH:MM``.
    SMS/Premium-SMS: Zeitspanne ``HH–HH`` (U+2013) am bestehenden Token.

  Dienste
    ``NotificationService.send_deviation_alert(..., anchor_weather=None)``: ALTE Reihe;
        der Modus je Kanal wird aus ``trip.display_config`` (Kanal-Kaskade
        ``get_metrics_for_channel``) aufgeloest.
    ``NotificationService.send_multi_location_deviation_alert(..., anchor_points=None,
        display_config=None)``.
    ``TripAlertService.check_and_send_alerts`` reicht ``cached_weather`` selbst durch.
    ``render_compare_alert_preview``: jedes Element von ``body["changes"]`` darf
        zusaetzlich ``hourly_old``/``hourly_new`` tragen (Stundenreihe des Ortes im
        Snapshot-Format); sie speisen Anker und frische Reihe der Vorschau.

Regressionsschutz, ABSICHTLICH GRUEN: ``test_ac10_ohne_stundenreihe_ausgabe_byte_gleich_zu_heute``
(Ausgabe ohne jede Stundenreihe == eingefrorener Ist-Stand ``ohne_stundenreihe_golden.json``).
Alle anderen Tests sind rot, bis die Stundenzeilen gebaut sind.

Reihenfolge je Test: Fixture laden und Vorbedingungen pruefen, dann ERST die neue
Schnittstelle benutzen; Abwesenheits-Aussagen stehen immer NACH einer Anwesenheits-Aussage
(sonst waeren sie heute vakuum-gruen).
"""
from __future__ import annotations

import dataclasses
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

from app.config import Settings
from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from services.weather_snapshot import _deserialize_timeseries
from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "alert_hour_rows"
TZ = ZoneInfo("Europe/Vienna")
UTC = timezone.utc
STAND = "09:30"
UTC_OFFSET_H = 2  # Mai, Europe/Vienna

COLS = ("thunder", "gust", "precip", "temp", "pop")
RAW = {c: "raw" for c in COLS}
SIMPLE = {"thunder": "symbol", "gust": "simplified", "precip": "simplified",
          "temp": "raw", "pop": "symbol"}


def modes(email: dict, telegram: dict | None = None) -> dict:
    """``format_modes``-Argument: Kanal -> {col_key: mode}."""
    return {"email": dict(email), "telegram": dict(telegram or email)}


# ---------------------------------------------------------------------------
# Fixture- und Modell-Bausteine
# ---------------------------------------------------------------------------

def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _series(rows: list[dict]) -> NormalizedTimeseries:
    ts = _deserialize_timeseries({"hourly": rows}, "openmeteo")
    assert ts is not None and len(ts.data) == len(rows), "Vorbedingung: Fixture-Reihe ladbar"
    return ts


def _segment_data(fx: dict, rows: list[dict] | None, seg_id: str = "1") -> SegmentWeatherData:
    s = fx["segment"]
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=s["lat"], lon=s["lon"], elevation_m=1000,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=s["lat"] + 0.05, lon=s["lon"] + 0.05, elevation_m=1500,
                           distance_from_start_km=6.0),
        start_time=datetime.fromisoformat(s["start"]), end_time=datetime.fromisoformat(s["end"]),
        duration_hours=7.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=_series(rows) if rows is not None else None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _wc(c: dict) -> WeatherChange:
    return WeatherChange(
        metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
        delta=c["delta"], threshold=c["threshold"], severity=ChangeSeverity.MAJOR,
        direction=c["direction"], segment_id=c["segment_id"],
        occurred_at=datetime.fromisoformat(c["occurred_at"]),
    )


def _point(name: str, lat: float, lon: float, rows: list[dict] | None):
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=name.lower().replace(" ", "-"), name=name, lat=lat, lon=lon,
        timeseries=_series(rows) if rows is not None else None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _trip_msg(fx: dict, *, fresh_key: str = "fresh", anchor: bool = True,
              fm: dict | None = None, changes: list[WeatherChange] | None = None):
    """Trip-Projektion ueber die NEUE Schnittstelle."""
    from output.renderers.alert.project import to_alert_message

    kwargs: dict = {}
    if anchor:
        kwargs["anchor_segments"] = [_segment_data(fx, fx["anchor"])]
    if fm is not None:
        kwargs["format_modes"] = fm
    return to_alert_message(
        changes if changes is not None else [_wc(fx["change"])],
        [_segment_data(fx, fx[fresh_key])], "Trip X", tz=TZ, stand_at=STAND, **kwargs,
    )


def _baseline_msg(fx: dict):
    """Dieselbe Lage OHNE Stundenreihe und OHNE neue Parameter (= heutiger Alarm)."""
    from output.renderers.alert.project import to_alert_message

    return to_alert_message(
        [_wc(fx["change"])], [_segment_data(fx, None)], "Trip X", tz=TZ, stand_at=STAND,
    )


# ---------------------------------------------------------------------------
# Erwartung aus dem Briefing-Formatierer + Zeilen-Extraktion
# ---------------------------------------------------------------------------

def _value_at(rows: list[dict], utc_hour: int, field: str):
    for r in rows:
        if datetime.fromisoformat(r["ts"]).hour == utc_hour:
            return r[field]
    raise AssertionError(f"Fixture hat keine Stunde {utc_hour}Z")


def _briefing_value(col: str, raw):
    return ThunderLevel[raw] if col == "thunder" else raw


def _cell(col: str, raw, mode: str) -> str:
    """Zelle wie das Briefing (Klartext/Telegram, ohne HTML)."""
    from output.renderers.email.helpers import fmt_val

    return fmt_val(col, _briefing_value(col, raw), format_modes={col: mode})


def _html_cell(col: str, raw, mode: str) -> str:
    """Zelle wie das HTML-Briefing (EINFACH = CSS-Punkt)."""
    from output.renderers.email.helpers import fmt_val

    return fmt_val(
        col, _briefing_value(col, raw), format_modes={col: mode},
        indicator_keys=set() if mode == "raw" else {col}, html=True,
    )


def _local(utc_hour: int) -> str:
    return f"{utc_hour + UTC_OFFSET_H:02d}:00"


def _expected(fx: dict, hours: list[int], col: str, field: str, mode: str = "raw",
              *, fresh_key: str = "fresh", with_old: bool = True) -> list[tuple[str, str]]:
    out = []
    for h in hours:
        new = _cell(col, _value_at(fx[fresh_key], h, field), mode)
        if with_old:
            old = _cell(col, _value_at(fx["anchor"], h, field), mode)
            out.append((_local(h), f"{old} → {new}"))
        else:
            out.append((_local(h), new))
    return out


_TAG = re.compile(r"<[^>]+>")
_ROW = re.compile(r"^\s*(\d{2}:\d{2})\s*\|\s*(\S.*?)\s*$")


def _row_lines(text: str) -> list[str]:
    return [ln for ln in _TAG.sub("", text).splitlines() if _ROW.match(ln)]


def _rows(text: str) -> list[tuple[str, str]]:
    """Stundenzeilen eines Klartext-/Telegram-Textes: [(HH:MM, 'alt -> neu')]."""
    out = []
    for ln in _TAG.sub("", text).splitlines():
        m = _ROW.match(ln)
        if m:
            out.append((m.group(1), re.sub(r"\s+", " ", m.group(2))))
    return out


def _row_groups(text: str) -> list[list[tuple[str, str]]]:
    """Zusammenhaengende Zeilenbloecke (getrennt durch jede Nicht-Stundenzeile)."""
    groups: list[list[tuple[str, str]]] = []
    prev_row = False
    for ln in _TAG.sub("", text).splitlines():
        m = _ROW.match(ln)
        if m:
            if not prev_row:
                groups.append([])
            groups[-1].append((m.group(1), re.sub(r"\s+", " ", m.group(2))))
        prev_row = bool(m)
    return groups


def _html_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        first = cells[0].get_text(" ", strip=True)
        if re.fullmatch(r"\d{2}:\d{2}", first):
            out.append({
                "time": first, "html": str(tr),
                "text": re.sub(r"\s+", " ", " ".join(c.get_text(" ", strip=True) for c in cells[1:])),
                "table": id(tr.find_parent("table")),
            })
    return out


def _norm_html(fragment: str) -> str:
    return str(BeautifulSoup(fragment, "html.parser"))


_EMOJI = re.compile("[☀-➿\U0001f300-\U0001faff\U0001f7e0-\U0001f7eb]")


def _non_row_lines(text: str) -> set[str]:
    return {ln.strip() for ln in _TAG.sub("", text).splitlines()
            if ln.strip() and not _ROW.match(ln)}


# ---------------------------------------------------------------------------
# Dienst-Bausteine (aufzeichner statt Sockets)
# ---------------------------------------------------------------------------

def _settings() -> Settings:
    return Settings().model_copy(update={
        "is_test_mode": False,
        "smtp_host": "smtp.rig-1737.test", "smtp_port": 2525,
        "smtp_user": "rig", "smtp_pass": "rig",
        "mail_to": "gregor-test@henemm.com", "mail_from": "gregor_zwanzig@henemm.com",
        "telegram_bot_token": "rig-1737-token", "telegram_chat_id": "4405",
        "telegram_test_bot_token": "rig-1737-token", "telegram_test_chat_id": "4405",
        "sms_gateway_url": "http://127.0.0.1:9/api/sms", "seven_api_key": "rig-1737",
        "seven_sandbox_key": "rig-1737", "sms_to": "+41790001405", "sms_from": None,
        "premium_sms_reply_to": "+41790002405",
        "premium_sms_reply_at": datetime.now(UTC) - timedelta(minutes=5),
    })


def _user(prefix: str) -> str:
    from tests.helpers.kanal_fake_transporte import premium_profil_schreiben
    from tests.helpers.nutzer_tier import nutzer_mit_tier

    uid = nutzer_mit_tier(f"tdd-1737-{prefix}-{uuid.uuid4().hex[:6]}", "premium")
    premium_profil_schreiben(uid, reply_at=datetime.now(UTC) - timedelta(minutes=5))
    return uid


def _trip(uid: str, email_mode: str, telegram_mode: str):
    """Trip mit kanalgenauer Darstellung fuer Gewitter (Kanal-Kaskade, ADR-0050)."""
    from app.trip import Stage, Trip, Waypoint

    tid = f"trip-1737-{uuid.uuid4().hex[:6]}"
    stage = Stage(
        id="T1", name="Tag 1", date=datetime(2026, 5, 1).date(),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    return Trip(
        id=tid, name="Stunden-Trip", stages=[stage], official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=tid,
            metrics=[MetricConfig(metric_id="thunder", enabled=True)],
            per_channel_layouts={
                "email": [MetricConfig(metric_id="thunder", enabled=True, format_mode=email_mode)],
                "telegram": [MetricConfig(metric_id="thunder", enabled=True, format_mode=telegram_mode)],
            },
        ),
    )


def _send_trip(monkeypatch, fx: dict, *, email_mode: str, telegram_mode: str,
               channels: set[str], prefix: str = "svc"):
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_chat(_user(prefix), settings)
    svc = NotificationService(settings, uid)
    svc.send_deviation_alert(
        trip=_trip(uid, email_mode, telegram_mode),
        weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
        effective_channels=channels,
        anchor_weather=[_segment_data(fx, fx["anchor"])],
    )
    return mit


# ===========================================================================
# AC-1 -- drei Stundenzeilen 14:00/15:00/16:00 in der E-Mail  (Test Plan 1)
# ===========================================================================

def test_ac1_gewitter_mail_hat_je_betroffener_stunde_eine_zeile_alt_neu():
    """AC-1: Gewitter aendert sich 14-16 Uhr Ortszeit -> unter der Kopfzeile je Stunde
    eine Zeile ``HH:MM | alt -> neu`` (Klartext UND HTML). Anker startet 1 h frueher als
    die frische Reihe (Index-Paarung waere falsch); 10/11 Uhr unveraendert und 18Z
    (ausserhalb des Segmentfensters) abweichend duerfen NICHT erscheinen."""
    from output.renderers.alert.render import render_email

    fx = _load("gewitter_14_16.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == [], "Vorbedingung: heute keine Stundenzeilen"
    erwartet = _expected(fx, fx["betroffen_utc_stunden"], "thunder", "thunder_level")
    assert [t for t, _ in erwartet] == ["14:00", "15:00", "16:00"]

    msg = _trip_msg(fx, fm=modes(RAW))
    html, plain = render_email(msg)

    assert _rows(plain) == erwartet
    hrows = _html_rows(html)
    assert [r["time"] for r in hrows] == ["14:00", "15:00", "16:00"]
    for r, (_t, rest) in zip(hrows, erwartet):
        assert rest in r["text"], f"HTML-Zeile {r['time']}: {r['text']!r} enthaelt nicht {rest!r}"
    assert [h.time for h in msg.events[0].hours] == ["14:00", "15:00", "16:00"]


def test_ac1_trip_alert_service_reicht_alte_reihe_bis_zur_mail_durch():
    """AC-1 (Verdrahtung am Wirkort): ``TripAlertService.check_and_send_alerts`` bekommt
    nur ``cached_weather``/``fresh_weather`` -- die Mail an der Senke muss trotzdem die
    Stundenzeilen mit alt -> neu tragen (Boeen 10 -> 50/70/90 km/h)."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import (
        LAT, LON, gust_alert_trip, settings_email_only, weather,
    )
    from utils.timezone import local_fmt, tz_for_coords

    base = weather(1, gust_max_kmh=10.0)
    first = base.segment.start_time.replace(minute=0, second=0, microsecond=0)
    hours = [first + timedelta(hours=k) for k in range(0, 5)]

    def rows(values):
        return [{"ts": h.isoformat(), "gust_kmh": v} for h, v in zip(hours, values)]

    cached = dataclasses.replace(
        weather(1, gust_max_kmh=10.0), timeseries=_series(rows([10.0] * 5)),
        fetched_at=datetime.now(UTC) - timedelta(hours=2),
    )
    fresh = dataclasses.replace(
        weather(1, gust_max_kmh=90.0), timeseries=_series(rows([10.0, 50.0, 70.0, 90.0, 10.0])),
    )
    mails: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=settings_email_only(), user_id=f"tdd-1737-{uuid.uuid4().hex[:6]}",
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    assert svc.check_and_send_alerts(
        gust_alert_trip(f"t1737-{uuid.uuid4().hex[:6]}"), [cached], fresh_weather=[fresh],
    ), "Vorbedingung: der Boeen-Alarm wird ausgeloest"
    assert len(mails) == 1
    tz = tz_for_coords(LAT, LON)
    erwartet = [
        (local_fmt(hours[k], tz), f"{_cell('gust', 10.0, 'raw')} → {_cell('gust', v, 'raw')}")
        for k, v in ((1, 50.0), (2, 70.0), (3, 90.0))
    ]
    assert _rows(mails[0][1]) == erwartet


# ===========================================================================
# AC-2 / AC-3 -- Darstellung wie das Briefing je Kanal  (Test Plan 2)
# ===========================================================================

def test_ac2_ac3_mail_einfach_punkte_telegram_roh_wort_ueber_den_versandweg(monkeypatch):
    """AC-2/AC-3: Briefing-Darstellung EINFACH in der Mail, ROH in Telegram. Der Alarm
    folgt dem je Kanal: Mail = CSS-Punkte (keine Emoji), Telegram = Stufenwort wie im
    Telegram-Briefing, gleiche Stunden in beiden Kanaelen."""
    fx = _load("gewitter_14_16.json")
    mit = _send_trip(monkeypatch, fx, email_mode="symbol", telegram_mode="raw",
                     channels={"email", "telegram"})
    mails, tgs = mit.sendungen("email"), mit.sendungen("telegram")
    assert len(mails) == 1 and len(tgs) == 1, f"Vorbedingung: je Kanal eine Sendung ({mit!r})"

    hrows = _html_rows(mails[0]["body"])
    assert [r["time"] for r in hrows] == ["14:00", "15:00", "16:00"]
    for r, h in zip(hrows, fx["betroffen_utc_stunden"]):
        alt = _norm_html(_html_cell("thunder", _value_at(fx["anchor"], h, "thunder_level"), "symbol"))
        neu = _norm_html(_html_cell("thunder", _value_at(fx["fresh"], h, "thunder_level"), "symbol"))
        assert alt in r["html"] and neu in r["html"], f"{r['time']}: Punkte alt/neu fehlen: {r['html']}"
        assert r["html"].index(alt) < r["html"].rindex(neu)
        assert not _EMOJI.search(r["html"]), f"{r['time']}: Emoji statt CSS-Punkt"
        assert not re.search(r"hoch|mittel|leicht|kein", r["text"]), "EINFACH zeigt kein Stufenwort"

    erwartet = _expected(fx, fx["betroffen_utc_stunden"], "thunder", "thunder_level", "raw")
    assert _rows(tgs[0]["body"]) == erwartet, "Telegram: gleiche Stunden, Zellen wie Telegram-Briefing"


# ===========================================================================
# AC-4 -- SMS / Premium-SMS  (Test Plan 3)
# ===========================================================================

def test_ac4_sms_token_traegt_zeitspanne_stufen_token_bleibt():
    """AC-4 (Renderer): ``render_sms`` traegt ``14–16``, das Stufen-Token
    ``TH:H->M`` des heutigen Alarms bleibt, Laenge <= 160."""
    from output.renderers.alert.render import render_sms

    fx = _load("gewitter_14_16.json")
    heute = render_sms(_baseline_msg(fx))
    assert "TH:H->M" in heute and "–" not in heute, f"Vorbedingung: {heute!r}"
    sms = render_sms(_trip_msg(fx, fm=modes(RAW)))
    assert "14–16" in sms, f"Zeitspanne fehlt: {sms!r}"
    assert "TH:H->M" in sms and len(sms) <= 160


def test_ac4_sms_und_premium_sms_ueber_den_versandweg(monkeypatch):
    """AC-4 (Versandweg): SMS UND Premium-SMS tragen ``14–16``, das Stufen-Token
    bleibt, jeweils <= 160 Zeichen (das Dispatch-Limit 140 gilt real)."""
    fx = _load("gewitter_14_16.json")
    mit = _send_trip(monkeypatch, fx, email_mode="raw", telegram_mode="raw",
                     channels={"sms", "premium_sms"}, prefix="sms")
    for kanal in ("sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, f"Vorbedingung: {kanal} genau einmal gesendet ({mit!r})"
        text = sendungen[0]["body"]
        assert "14–16" in text, f"{kanal}: Zeitspanne fehlt: {text!r}"
        assert "TH:H->M" in text and len(text) <= 160, f"{kanal}: {text!r}"


# ===========================================================================
# AC-5 -- Ortsvergleich: nur betroffene Orte  (Test Plan 4)
# ===========================================================================

def _compare_inputs(fx: dict):
    orte = fx["orte"]
    anchors = {o["name"]: _point(o["name"], o["lat"], o["lon"], o["anchor"]) for o in orte}
    fresh = {o["name"]: _point(o["name"], o["lat"], o["lon"], o["fresh"]) for o in orte}
    changes = {o["name"]: [_wc(dict(o["change"]))] for o in orte if o["change"]}
    return anchors, fresh, changes


def test_ac5_ortsvergleich_stundenzeilen_nur_bei_betroffenen_orten_ueber_den_versand(monkeypatch):
    """AC-5: zwei von drei Orten betroffen -> Stundenzeilen je betroffenem Ort (Gewitter 3
    Zeilen, Boeen 1 Zeile), der dritte Ort (Stundenwerte weichen ab, aber kein Alarm)
    bekommt keine. Gemessen an Mail UND an den Telegram-Blasen JE ORT (die Aufspaltung
    projiziert jeden Ort einzeln neu -- der Anker muss dort mitreisen)."""
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    fx = _load("ortsvergleich_drei_orte.json")
    anchors, fresh, changes = _compare_inputs(fx)
    assert set(changes) == {"Alpe Nord", "Joch Mitte"} and "Tal Sued" in anchors

    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_chat(_user("cmp"), settings)
    mails: list[str] = []
    NotificationService(settings, uid).send_multi_location_deviation_alert(
        entities=[(n, [fresh[n]], changes[n]) for n in ("Alpe Nord", "Joch Mitte")],
        effective_channels={"email", "telegram"},
        mail_sink=lambda subject, body: mails.append(body),
        anchor_points=anchors,
    )
    exp = fx["erwartet_utc_stunden"]
    nord = [(_local(h), f"{_cell('thunder', _value_at(fx['orte'][0]['anchor'], h, 'thunder_level'), 'raw')} → "
             f"{_cell('thunder', _value_at(fx['orte'][0]['fresh'], h, 'thunder_level'), 'raw')}")
            for h in exp["Alpe Nord"]]
    joch = [(_local(h), f"{_cell('gust', _value_at(fx['orte'][1]['anchor'], h, 'gust_kmh'), 'raw')} → "
            f"{_cell('gust', _value_at(fx['orte'][1]['fresh'], h, 'gust_kmh'), 'raw')}")
            for h in exp["Joch Mitte"]]

    assert len(mails) == 1
    assert sorted(_rows(mails[0])) == sorted(nord + joch)
    assert "Tal Sued" not in mails[0]

    bubbles = [s["body"] for s in mit.sendungen("telegram")]
    assert len(bubbles) == 2, f"Vorbedingung: eine Blase je Ort, gefunden {len(bubbles)}"
    by_name = {n: next(b for b in bubbles if n in b) for n in ("Alpe Nord", "Joch Mitte")}
    assert _rows(by_name["Alpe Nord"]) == nord
    assert _rows(by_name["Joch Mitte"]) == joch
    assert all("Tal Sued" not in b for b in bubbles)


def test_ac5_ortsvergleich_einfach_html_punkte_und_ereignis_zuordnung():
    """AC-5 (Renderer, EINFACH): im HTML tragen die Zeilen die Punkte des Briefings; jedes
    Ereignis haengt an SEINEM Ort (``hours`` des Ortes), der dritte Ort hat keines."""
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_email

    fx = _load("ortsvergleich_drei_orte.json")
    anchors, fresh, changes = _compare_inputs(fx)
    groups = [(n, changes[n], fresh[n]) for n in ("Alpe Nord", "Joch Mitte")]
    msg = to_multi_point_alert_message(
        groups, tz=TZ, stand_at=STAND, anchor_points=anchors, format_modes=modes(SIMPLE),
    )
    by_label = {e.location_label: e for e in msg.events}
    assert [h.time for h in by_label["Alpe Nord"].hours] == ["14:00", "15:00", "16:00"]
    assert [h.time for h in by_label["Joch Mitte"].hours] == ["15:00"]
    html, _plain = render_email(msg)
    hrows = _html_rows(html)
    assert len(hrows) == 4
    neu = _norm_html(_html_cell("gust", 70.0, "simplified"))
    joch = next(r for r in hrows if r["time"] == "15:00" and neu in r["html"])
    assert not _EMOJI.search(joch["html"])
    assert not any("Tal Sued" in e.location_label for e in msg.events if e.location_label)


# ===========================================================================
# AC-6 -- Auswahl betroffener Stunden  (Test Plan 5)
# ===========================================================================

def test_ac6_stufenmetrik_zaehlt_den_stufenwechsel_nicht_den_wertabstand():
    """AC-6: bei einer Metrik mit Stufe ist die Stunde mit STUFENWECHSEL betroffen (12Z:
    28 gruen -> 31 gelb, Abstand nur 3), nicht die Stunden mit grossem Abstand ohne
    Stufenwechsel (13Z: 10 -> 29, 14Z: 10 -> 25)."""
    from output.renderers.alert.render import render_email

    fx = _load("boeen_stufe_statt_schwelle.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == []
    erwartet = _expected(fx, fx["angezeigt_utc_stunden"], "gust", "gust_kmh")
    assert erwartet == [("14:00", f"{_cell('gust', 28.0, 'raw')} → {_cell('gust', 31.0, 'raw')}")]
    assert _rows(render_email(_trip_msg(fx, fm=modes(RAW)))[1]) == erwartet


def test_ac6_ohne_stufe_zaehlt_der_stundenabstand_ab_schwelle_und_der_zusammenhaengende_bereich():
    """AC-6: Temperatur (keine Stufe), Schwelle 3.0 aus dem Alarm: Stunden mit Abstand >= 3
    sind 11Z (4), 13Z (3), 16Z (5); angezeigt wird der Bereich 11Z..16Z INKLUSIVE der
    Zwischenstunden mit kleinem Abstand (12Z: 1, 14Z: 2.5, 15Z: 0). 10Z (2) und 17Z
    (0.5) liegen ausserhalb des Bereichs."""
    from output.renderers.alert.render import render_email

    fx = _load("temperatur_schwelle.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == []
    erwartet = _expected(fx, fx["angezeigt_utc_stunden"], "temp", "t2m_c")
    assert [t for t, _ in erwartet] == ["13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    assert _rows(render_email(_trip_msg(fx, fm=modes(RAW)))[1]) == erwartet


def test_ac6_verteilte_abweichung_faellt_auf_jede_abweichende_stunde_zurueck():
    """AC-6: erreicht KEINE einzelne Stunde die Schwelle (alle Abstaende 2 < 3), gilt jede
    Stunde mit Abweichung (11Z-14Z) als betroffen."""
    from output.renderers.alert.render import render_email

    fx = _load("temperatur_schwelle.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == []
    erwartet = _expected(fx, fx["verteilt_utc_stunden"], "temp", "t2m_c", fresh_key="fresh_verteilt")
    assert [t for t, _ in erwartet] == ["13:00", "14:00", "15:00", "16:00"]
    msg = _trip_msg(fx, fresh_key="fresh_verteilt", fm=modes(RAW))
    assert _rows(render_email(msg)[1]) == erwartet


# ===========================================================================
# AC-7 -- Kappung auf 6 Zeilen + Hinweiszeile  (Test Plan 6)
# ===========================================================================

def test_ac7_neun_betroffene_stunden_zeigen_sechs_staerkste_in_zeitfolge_plus_hinweis():
    """AC-7: 9 betroffene Stunden (08Z-16Z) -> genau 6 Zeilen (die 6 staerksten, nach
    Uhrzeit sortiert: 09,10,12,13,14,16Z), darunter ``betroffen 10:00–18:00``
    (erste/letzte betroffene Stunde, nicht der angezeigten). Gilt fuer Mail UND Telegram."""
    from output.renderers.alert.render import render_email, render_telegram

    fx = _load("boeen_neun_stunden.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == []
    erwartet = _expected(fx, fx["angezeigt_utc_stunden"], "gust", "gust_kmh")
    assert len(erwartet) == 6

    msg = _trip_msg(fx, fm=modes(RAW))
    html, plain = render_email(msg)
    assert _rows(plain) == erwartet
    assert plain.count(fx["hinweis"]) == 1, f"Hinweiszeile fehlt/doppelt: {plain!r}"
    assert [r["time"] for r in _html_rows(html)] == [t for t, _ in erwartet]
    assert fx["hinweis"] in BeautifulSoup(html, "html.parser").get_text(" ")
    tg = render_telegram(msg)
    assert _rows(tg) == erwartet and fx["hinweis"] in _TAG.sub("", tg)


# ===========================================================================
# AC-8 / AC-9 -- Ereignis-Bloecke, Summen-Metrik  (Test Plan 7)
# ===========================================================================

def test_ac8_zwei_ereignisse_haben_je_einen_eigenen_zeilenblock_ohne_gemeinsame_tabelle():
    """AC-8: Regenwahrscheinlichkeit (3 Stunden) und Boeen (1 Stunde) -> zwei getrennte
    Zeilenbloecke (Klartext), im HTML keine gemeinsame Tabelle."""
    from output.renderers.alert.render import render_email

    fx = _load("pop_und_boeen.json")
    msg = _trip_msg(fx, fm=modes(RAW), changes=[_wc(c) for c in fx["changes"]])
    assert len(msg.events) == 2
    html, plain = render_email(msg)

    pop = [(_local(h), f"{_cell('pop', 20, 'raw')} → {_cell('pop', 70, 'raw')}") for h in (12, 13, 14)]
    gust = [(_local(13), f"{_cell('gust', 10.0, 'raw')} → {_cell('gust', 65.0, 'raw')}")]
    groups = _row_groups(plain)
    assert sorted(groups, key=len) == sorted([pop, gust], key=len), groups
    hrows = _html_rows(html)
    assert len(hrows) == 4
    tables_pop = {r["table"] for r in hrows if r["time"] in {t for t, _ in pop} and "70" in r["text"]}
    tables_gust = {r["table"] for r in hrows if "65" in r["text"]}
    assert tables_pop and tables_gust and tables_pop.isdisjoint(tables_gust), (
        "jedes Ereignis braucht seinen eigenen Zeilenblock (keine gemeinsame Tabelle)"
    )


def test_ac9_summe_bleibt_in_der_kopfzeile_zeilen_zeigen_stundenwerte():
    """AC-9: Niederschlagssumme 1.2 -> 10.8 steht in der Ereignis-Kopfzeile; die drei
    Stundenzeilen zeigen die Stundenwerte 0.4 -> 1.1/2.3/7.4, nicht die Summe."""
    from output.renderers.alert.render import _val, render_email

    fx = _load("niederschlag_summe.json")
    assert _rows(render_email(_baseline_msg(fx))[1]) == []
    erwartet = _expected(fx, fx["angezeigt_utc_stunden"], "precip", "precip_1h_mm")
    assert [r for _t, r in erwartet] == [
        f"{_cell('precip', 0.4, 'raw')} → {_cell('precip', v, 'raw')}" for v in (1.1, 2.3, 7.4)
    ]
    msg = _trip_msg(fx, fm=modes(RAW))
    _html, plain = render_email(msg)
    assert _rows(plain) == erwartet
    summe_neu = _val(msg.events[0], 10.8)
    kopf = "\n".join(ln for ln in plain.splitlines() if not _ROW.match(ln))
    assert summe_neu in kopf, f"Summe {summe_neu!r} fehlt in der Kopfzeile: {kopf!r}"
    assert all(summe_neu not in rest for _t, rest in _rows(plain))


# ===========================================================================
# AC-10 -- ohne Anker / ohne Stundenreihe  (Test Plan 8)
# ===========================================================================

def test_ac10_ohne_anker_zeigt_jede_stundenzeile_nur_den_neuen_wert():
    """AC-10: erster Alarm, kein Anker. Frische Reihe: 12Z-14Z Gewitter ``hoch``. Jede Zeile
    zeigt nur den neuen Wert, ohne ``alt ->``/Pfeil und ohne Zusatzhinweis (die Klartext-
    Zeilen ausserhalb der Stundenzeilen sind eine Teilmenge der heutigen)."""
    from output.renderers.alert.render import render_email

    fx = _load("gewitter_14_16.json")
    heute = render_email(_baseline_msg(fx))[1]
    assert _rows(heute) == []
    msg = _trip_msg(fx, fresh_key="fresh_hoch", anchor=False, fm=modes(RAW))
    _html, plain = render_email(msg)
    erwartet = [(_local(h), _cell("thunder", "HIGH", "raw")) for h in (12, 13, 14)]
    assert _rows(plain) == erwartet
    assert all("→" not in rest for _t, rest in _rows(plain))
    assert _non_row_lines(plain) <= _non_row_lines(heute), (
        f"Zusatzhinweis erfunden: {_non_row_lines(plain) - _non_row_lines(heute)!r}"
    )


def _ohne_reihe_ausgabe(msg) -> dict:
    from output.renderers.alert.render import render_email, render_sms, render_subject, render_telegram

    html, plain = render_email(msg)
    return {"subject": render_subject(msg), "html": html, "plain": plain,
            "telegram": render_telegram(msg), "sms": render_sms(msg)}


def test_ac10_ohne_stundenreihe_ausgabe_byte_gleich_zu_heute():
    """AC-10 Teil 2 -- REGRESSIONSSCHUTZ, ABSICHTLICH GRUEN: ohne jede Stundenreihe ist die
    Ausgabe in allen Kanaelen byte-gleich zum eingefrorenen Ist-Stand
    (``ohne_stundenreihe_golden.json``)."""
    fx = _load("gewitter_14_16.json")
    golden = _load("ohne_stundenreihe_golden.json")
    ist = _ohne_reihe_ausgabe(_baseline_msg(fx))
    assert set(golden) == set(ist) and all(golden[k] for k in golden)
    for kanal, text in ist.items():
        assert text == golden[kanal], f"Kanal {kanal!r} weicht vom Ist-Stand ab"


def test_ac10_ohne_stundenreihe_bleibt_gleich_auch_mit_den_neuen_parametern():
    """AC-10 Teil 2 (neue Schnittstelle): ``anchor_segments=None`` + ``format_modes`` ohne
    jede Stundenreihe aendern die Ausgabe nicht -- identisch zum Golden."""
    from output.renderers.alert.project import to_alert_message

    fx = _load("gewitter_14_16.json")
    golden = _load("ohne_stundenreihe_golden.json")
    msg = to_alert_message(
        [_wc(fx["change"])], [_segment_data(fx, None)], "Trip X", tz=TZ, stand_at=STAND,
        anchor_segments=None, format_modes=modes(RAW),
    )
    assert _ohne_reihe_ausgabe(msg) == golden


# ===========================================================================
# AC-11 -- Vorschau == Versand  (Test Plan 9)
# ===========================================================================

def test_ac11_alarm_vorschau_zeigt_dieselben_stundenzeilen_wie_der_versand(env, monkeypatch):  # noqa: F811
    """AC-11: Ortsvergleich-Alarm (zwei Orte). Referenz = der echte Versand
    ``send_multi_location_deviation_alert`` (Anker + frische Reihe); Vorschau =
    ``render_compare_alert_preview`` mit denselben Reihen im Body. Klartext-Mail und jede
    Telegram-Blase tragen dieselben Stundenzeilen -- und es SIND welche."""
    from services.compare_alert_preview_service import render_compare_alert_preview
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd.test_alert_preview_compare_paritaet import LOCATIONS, PRESET_ID, _seed

    fx = _load("gewitter_14_16.json")
    user_id = env
    preset = _seed(user_id)
    orte = [loc for loc in LOCATIONS if loc.id in ("loc-ibk", "loc-bz")]
    chg = dict(fx["change"])

    entities, anchors = [], {}
    for loc in orte:
        entities.append((loc.name, [_point(loc.name, loc.lat, loc.lon, fx["fresh"])], [_wc(chg)]))
        anchors[loc.name] = _point(loc.name, loc.lat, loc.lon, fx["anchor"])

    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    mit_profil_chat(user_id, settings)
    mails: list[str] = []
    NotificationService(settings, user_id).send_multi_location_deviation_alert(
        entities=entities, effective_channels={"email", "telegram"},
        mail_sink=lambda subject, body: mails.append(body), anchor_points=anchors,
    )
    versand_rows = _rows(mails[0])
    erwartet = _expected(fx, fx["betroffen_utc_stunden"], "thunder", "thunder_level")
    assert versand_rows and sorted(versand_rows) == sorted(erwartet * 2), "Vorbedingung: Versand traegt die Zeilen"

    body = {"changes": [{
        "location_id": loc.id, "metric": chg["metric"], "old_value": chg["old_value"],
        "new_value": chg["new_value"], "delta": chg["delta"], "threshold": chg["threshold"],
        "severity": "major", "direction": chg["direction"],
        "hourly_old": fx["anchor"], "hourly_new": fx["fresh"],
    } for loc in orte]}
    vorschau = render_compare_alert_preview(PRESET_ID, user_id=user_id, body=body)

    assert _rows(vorschau["email_plain"]) == versand_rows
    ref_bubbles = sorted(_rows(s["body"]) for s in mit.sendungen("telegram"))
    assert ref_bubbles and all(ref_bubbles)
    assert sorted(_rows(b) for b in vorschau["telegram_bubbles"]) == ref_bubbles


# ===========================================================================
# AC-12 -- nur Daten  (Test Plan 10)
# ===========================================================================

EMPFEHLUNGS_PHRASEN = ("empfohlen", "empfehl", "sollten", "meiden", "bitte", "verhalten",
                       "vermeide", "ratsam", "verschieb")
_SIGNIERTES_PROZENT = re.compile(r"[+\-−–]\s?\d+(?:[.,]\d+)?\s?%")


def test_ac12_stundenzeilen_enthalten_nur_daten_keine_empfehlung_keine_berechnete_prozentangabe():
    """AC-12: in allen Kanaelen steht nur Uhrzeit + Wert/Stufe -- keine Empfehlung, keine
    berechnete Prozentaenderung. Prozent als EINHEIT (Regenwahrscheinlichkeit) bleibt
    erlaubt. Anwesenheit der Zeilen wird zuerst geprueft."""
    from output.renderers.alert.render import render_email, render_sms, render_telegram

    fx = _load("pop_und_boeen.json")
    msg = _trip_msg(fx, fm=modes(RAW), changes=[_wc(c) for c in fx["changes"]])
    html, plain = render_email(msg)
    tg = render_telegram(msg)
    assert len(_rows(plain)) == 4 and len(_rows(tg)) == 4, "Vorbedingung: Stundenzeilen vorhanden"
    texte = {"plain": plain, "html": BeautifulSoup(html, "html.parser").get_text(" "),
             "telegram": _TAG.sub("", tg), "sms": render_sms(msg)}
    for kanal, text in texte.items():
        assert not _SIGNIERTES_PROZENT.search(text), f"{kanal}: berechnete Prozentangabe: {text!r}"
        for phrase in EMPFEHLUNGS_PHRASEN:
            assert phrase not in text.lower(), f"{kanal}: Handlungsempfehlung {phrase!r}"


# ===========================================================================
# AC-13 -- Mandantentrennung der Darstellung  (Test Plan 11)
# ===========================================================================

def test_ac13_zwei_nutzer_jeder_alarm_folgt_nur_der_eigenen_anzeige_konfiguration(monkeypatch):
    """AC-13: Nutzer A hat die Mail auf EINFACH (Punkte), Nutzer B auf ROH (Worte). Ablauf
    A, B, A: die Mail von A zeigt Punkte (auch NACH B), die von B Worte -- die Konfiguration
    des anderen aendert nichts."""
    fx = _load("gewitter_14_16.json")

    def lauf(email_mode: str, prefix: str):
        mit = _send_trip(monkeypatch, fx, email_mode=email_mode, telegram_mode="raw",
                         channels={"email"}, prefix=prefix)
        sendungen = mit.sendungen("email")
        assert len(sendungen) == 1, f"Vorbedingung: eine Mail ({mit!r})"
        return _html_rows(sendungen[0]["body"])

    a1, b, a2 = lauf("symbol", "a"), lauf("raw", "b"), lauf("symbol", "a")
    assert len(a1) == len(b) == len(a2) == 3, "Vorbedingung: je drei Stundenzeilen"
    hoch = _norm_html(_html_cell("thunder", "HIGH", "symbol"))
    for r in a1 + a2:
        assert "<span" in r["html"] and not re.search(r"hoch|mittel|leicht|kein", r["text"]), "A: Punkte"
    assert hoch in a1[0]["html"]
    for r in b:
        assert "<span" not in r["html"] and re.search(r"hoch|mittel|leicht|kein", r["text"]), "B: Worte"
    assert [r["html"] for r in a1] == [r["html"] for r in a2], "A ist nach B unveraendert"
