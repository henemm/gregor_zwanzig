"""TDD RED -- Issue #1737: Abweichungsalarm zeigt Stundenzeilen (alt -> neu je Stunde).

Spec: docs/specs/modules/feat_1737_alarm_stundenzeilen.md (v1.1, AC-1 bis AC-14, Test Plan 1-13).

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
    ``AlertEvent.hours: tuple[AlertHourRow, ...] = ()`` (additiv, Default leer).
    ``AlertMessage.format_modes`` (additiv): Kanal -> {col_key: format_mode}.

  Projektion (``output.renderers.alert.project``)
    ``to_alert_message(..., anchor_segments=None, format_modes=None)``;
    ``to_multi_point_alert_message(..., anchor_points=None, format_modes=None)``
        (``anchor_points``: ``dict[Ortsname, PointWeatherData]``). Paarung per
        UTC-Zeitstempel, nicht per Index.

  Renderer (``output.renderers.alert.render``) -- Stundenzeile in E-Mail (Klartext UND
    HTML-Tabelle) und Telegram: ``HH:MM | alt -> neu`` (Pfeil U+2192); ohne Anker
    ``HH:MM | neu``. Kappung: hoechstens 6 Zeilen je Ereignis + Hinweiszeile
    ``betroffen HH:MM–HH:MM`` (U+2013 NUR hier). SMS/Premium-SMS: Zeitspanne ``HH-HH``
    mit ASCII-Bindestrich (GSM-7; v1.1: NICHT U+2013).

  Dienste
    ``NotificationService.send_deviation_alert(..., anchor_weather=None)``: ALTE Reihe;
        Modus je Kanal aus ``trip.display_config`` (Kanal-Kaskade).
    ``NotificationService.send_multi_location_deviation_alert(..., anchor_points=None)``:
        Ortsvergleich-Stundenwerte sind IMMER ROH (v1.1, PO-Entscheid 2026-10-21) --
        eine Anzeige-Konfiguration (``display_config``), falls der Parameter noch
        existiert, darf sie nicht aendern.
    ``TripAlertService.check_and_send_alerts`` reicht ``cached_weather`` selbst durch.

  Vorschau (v1.1, Spec Schritt 8) -- STREICHT den alten Body-Vertrag ``hourly_old`` /
    ``hourly_new``: die Oberflaeche (``buildAlertPreviewBody``) sendet nie Stundenreihen.
    Die Vorschau beschafft Anker und frische Reihe SERVERSEITIG, strikt je Nutzer:
      * Trip: ``api.routers.validator.alert_preview`` reicht die ECHTE ``user_id`` an
        ``render_alert_preview`` durch; alte Reihe = ``TripAlertService(user_id).
        _get_cached_weather(trip, tagesgleicher_anker_noetig=True, now_utc)``, frische
        Reihe = ``_fetch_fresh_weather(anker)``.
      * Ortsvergleich: ``render_compare_alert_preview`` liest den Anker aus
        ``CompareWeatherSnapshotService(user_id).load(preset_id, location_id)`` und holt
        die frische Reihe ueber ``CompareLocationWeatherSource().fetch`` (wie der Versand).
    Die Stundenzeilen entstehen AUSSCHLIESSLICH aus (Anker, frischer Reihe); die
    synthetischen Werte der Regeln bleiben in Kopfzeile/Ereignis. Kein Anker bzw.
    scheiternder Frisch-Abruf: Ausgabe wie ohne Stundenreihe, kein Fehler.

  Offline-Naht fuer den Frisch-Abruf (PRODUKTIV, keine Test-Weiche im Pruefling):
    ``GZ_TEST_FIXTURE_DIR`` -> ``providers.base.get_provider("openmeteo")`` liefert den
    ``FixtureProvider`` (``src/providers/fixture.py``). Beide Wege -- Trip
    (``_fetch_fresh_weather``) und Ortsvergleich (``CompareLocationWeatherSource.fetch``)
    -- laufen durch ``get_provider``; die Tests schreiben pro Szenario ein
    Fixture-Verzeichnis mit eigenen Stundenreihen (Boeen je Stunde) und setzen die
    Variable per ``monkeypatch.setenv``. Der FixtureProvider stempelt Eintrag i auf
    HEUTE 00:00 UTC + i h -- die Tests bilden alle Zeiten relativ zu jetzt und leiten die
    Ortszeit aus ``tz_for_coords`` ab (am 25.10. Zeitumstellung; kein fester Offset).
    Der geteilte Wetter-Cache (Singleton, 600 s) wird je Szenario geleert.

ABSICHTLICH GRUEN (Regressionsschutz): ``test_ac10_ohne_stundenreihe_*`` (Golden),
``test_ac5_ortsvergleich_ereignis_zuordnung_*``, ``test_ac5_ortsvergleich_roh_*_versandweg``
(der Produktionsweg uebergibt heute schon keine Anzeige-Konfiguration),
``test_ac13_zwei_nutzer_ortsvergleich_*`` (Mandantentrennung im Versand ist Bestand).
ROT sein muessen: die Vorschau-Tests AC-11/AC-14 (Trip und Ortsvergleich: keine
Stundenzeilen in der Vorschau, Body-Reihen werden noch gelesen) und
``test_ac5_ortsvergleich_ignoriert_trip_anzeige_konfiguration`` (EINFACH-Punkte statt roh).

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
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
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
    """AC-4 (Renderer): ``render_sms`` traegt ``14-16`` (ASCII, GSM-7), das Stufen-Token
    ``TH:H->M`` des heutigen Alarms bleibt, Laenge <= 140 (Default-Limit von ``render_sms``)."""
    from output.renderers.alert.render import render_sms

    fx = _load("gewitter_14_16.json")
    heute = render_sms(_baseline_msg(fx))
    assert "TH:H->M" in heute and "–" not in heute, f"Vorbedingung: {heute!r}"
    sms = render_sms(_trip_msg(fx, fm=modes(RAW)))
    assert "14-16" in sms and "–" not in sms, f"Zeitspanne fehlt: {sms!r}"
    assert "TH:H->M" in sms and len(sms) <= 140, f"{len(sms)}: {sms!r}"


def test_ac4_sms_und_premium_sms_ueber_den_versandweg(monkeypatch):
    """AC-4 (Versandweg): SMS UND Premium-SMS tragen ``14-16`` (ASCII, GSM-7), das Stufen-Token
    bleibt, jeweils <= 140 Zeichen (reales Dispatch-Limit, notification_service)."""
    fx = _load("gewitter_14_16.json")
    mit = _send_trip(monkeypatch, fx, email_mode="raw", telegram_mode="raw",
                     channels={"sms", "premium_sms"}, prefix="sms")
    for kanal in ("sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, f"Vorbedingung: {kanal} genau einmal gesendet ({mit!r})"
        text = sendungen[0]["body"]
        assert "14-16" in text and "–" not in text, f"{kanal}: Zeitspanne fehlt: {text!r}"
        from tests.tdd._gsm7_charset import assert_gsm7_clean
        assert_gsm7_clean(text, f"{kanal} (Issue #1737, GSM-7 #1796)")
        assert "TH:H->M" in text and len(text) <= 140, f"{kanal} ({len(text)}): {text!r}"


# AC-4 Ueberlauf: sechs Etappen-Segmente mit je zwei Ereignissen (Regenwahrscheinlichkeit
# ``@14-16``, Boeen ``@15``) -- zwoelf Tokens mit Zeitspanne, ungekuerzt deutlich ueber 140.
_UEBERLAUF_SEGMENTE = [str(i) for i in range(1, 7)]
_SMS_SUFFIX = re.compile(r" \+(\d+)$")
# Ein ganzes Token: ``PR20->70@14-16`` bzw. an einem anderen Tag ``PR20->70@Fr15 14-16``
# (Spanne NACH dem Tagesbezug, render.py ``_sms_token``).
_SMS_TOKEN = r"(?:PR|G)\d+->\d+@(?:[A-Z][a-z])?\d{2}(?:-\d{2}| \d{2}-\d{2}| \d{2})?"


def _ueberlauf_eingaben():
    fx = _load("pop_und_boeen.json")
    changes = [_wc(dict(c, segment_id=s)) for s in _UEBERLAUF_SEGMENTE for c in fx["changes"]]
    frisch = [_segment_data(fx, fx["fresh"], s) for s in _UEBERLAUF_SEGMENTE]
    anker = [_segment_data(fx, fx["anchor"], s) for s in _UEBERLAUF_SEGMENTE]
    return changes, frisch, anker


def _assert_sms_sauber_gekuerzt(text: str, n_ereignisse: int, wo: str) -> None:
    """<= 140, endet auf dem Kuerzungs-Suffix `` +k`` und behaelt nur GANZE Tokens:
    behaltene + weggelassene = alle Ereignisse (ein bloss abgeschnittener Text faellt hier)."""
    assert len(text) <= 140, f"{wo} ({len(text)}): {text!r}"
    m = _SMS_SUFFIX.search(text)
    assert m, f"{wo}: Kuerzungs-Suffix ' +k' fehlt: {text!r}"
    rumpf = text[:m.start()].split(": ", 1)[1]
    assert re.fullmatch(f"{_SMS_TOKEN}(?: {_SMS_TOKEN})*", rumpf), (
        f"{wo}: angeschnittenes Token: {rumpf!r}")
    behalten = re.findall(_SMS_TOKEN, rumpf)
    assert len(behalten) + int(m.group(1)) == n_ereignisse, f"{wo}: {text!r}"
    assert any(re.search(r"\d{2}-\d{2}$", t) for t in behalten), f"{wo}: keine Zeitspanne"


def test_ac4_sms_ueberlauf_mit_zeitspannen_wird_im_limit_gekuerzt():
    """AC-4: viele Ereignisse mit Zeitspanne -- ``render_sms`` (Default-Limit) bleibt <= 140,
    kuerzt ganze Tokens weg und haengt `` +k`` an."""
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_sms

    changes, frisch, anker = _ueberlauf_eingaben()
    msg = to_alert_message(changes, frisch, "Trip X", tz=TZ, stand_at=STAND,
                           anchor_segments=anker)
    ungekuerzt = render_sms(msg, limit=10_000)
    assert len(ungekuerzt) > 140 and "@14-16" in ungekuerzt, (
        f"Vorbedingung: ungekuerzt ueber 140 ({len(ungekuerzt)}): {ungekuerzt!r}")
    sms = render_sms(msg)
    _assert_sms_sauber_gekuerzt(sms, len(changes), "render_sms")
    assert "@14-16" in sms


def test_ac4_sms_und_premium_sms_ueberlauf_ueber_den_versandweg(monkeypatch):
    """AC-4 (Versandweg): derselbe Ueberlauf durch ``send_deviation_alert`` -- SMS UND
    Premium-SMS <= 140 mit Kuerzungs-Suffix, nur ganze Tokens."""
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    changes, frisch, anker = _ueberlauf_eingaben()
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_chat(_user("smsvoll"), settings)
    NotificationService(settings, uid).send_deviation_alert(
        trip=_trip(uid, "raw", "raw"), weather=frisch, changes=changes,
        effective_channels={"sms", "premium_sms"}, anchor_weather=anker,
    )
    for kanal in ("sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, f"Vorbedingung: {kanal} genau einmal gesendet ({mit!r})"
        _assert_sms_sauber_gekuerzt(sendungen[0]["body"], len(changes), kanal)


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


def test_ac5_ortsvergleich_ereignis_zuordnung_nur_betroffene_orte():
    """AC-5 (Renderer, REGRESSIONSSCHUTZ -- ABSICHTLICH GRUEN): jedes Ereignis haengt an
    SEINEM Ort (``hours`` des Ortes), der dritte Ort (Stundenwerte weichen ab, aber kein
    Alarm) hat kein Ereignis. Keine Darstellungs-Konfiguration beteiligt (v1.1: der
    Ortsvergleich kennt keine Roh/Einfach-Wahl fuer Stundenwerte)."""
    from output.renderers.alert.project import to_multi_point_alert_message

    fx = _load("ortsvergleich_drei_orte.json")
    anchors, fresh, changes = _compare_inputs(fx)
    groups = [(n, changes[n], fresh[n]) for n in ("Alpe Nord", "Joch Mitte")]
    msg = to_multi_point_alert_message(groups, tz=TZ, stand_at=STAND, anchor_points=anchors)
    by_label = {e.location_label: e for e in msg.events}
    assert [h.time for h in by_label["Alpe Nord"].hours] == ["14:00", "15:00", "16:00"]
    assert [h.time for h in by_label["Joch Mitte"].hours] == ["15:00"]
    assert not any("Tal Sued" in (e.location_label or "") for e in msg.events)


def _ort_fuer_lauf(ort: dict, gust_anker: float, gust_frisch: float) -> dict:
    return dict(ort, gust_anker=gust_anker, gust_frisch=gust_frisch)


def _compare_lauf(monkeypatch, uid: str, orte: list[dict], *, preset_id: str,
                  display_config: dict | None = None):
    """REALER Lauf von ``CompareAlertService.check_all_compare_presets`` fuer ein Preset mit
    mehreren Orten: echter Snapshot-Anker je Ort (``CompareWeatherSnapshotService.save``,
    Stundenreihe inklusive), Wetterquelle mit der frischen Reihe aus der Fixture, Transport-
    Aufzeichner (HTML-Koerper der Mail). ``orte``: Eintraege aus ``ortsvergleich_drei_orte.json``
    plus ``gust_anker``/``gust_frisch`` (Tageswerte, die den Alarm ausloesen bzw. nicht).
    Gibt die Kanalmitschrift zurueck."""
    from app.loader import get_data_dir, save_location
    from app.user import SavedLocation
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData
    from tests.helpers.compare_briefings import write_compare_briefings
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    mit_profil_chat(uid, settings)
    ids = {o["name"]: f"loc-1737-{k}-{uuid.uuid4().hex[:5]}" for k, o in enumerate(orte)}
    for o in orte:
        save_location(SavedLocation(id=ids[o["name"]], name=o["name"], lat=o["lat"],
                                    lon=o["lon"], elevation_m=1000), user_id=uid)
    preset = {
        "id": preset_id, "name": preset_id, "user_id": uid,
        "location_ids": [ids[o["name"]] for o in orte], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-07-09T00:00:00Z",
        "cooldown_minutes": 0,
    }
    if display_config is not None:
        preset["display_config"] = display_config
    write_compare_briefings(get_data_dir(uid), [preset])
    now = datetime.now(UTC)

    def punkt(o, rows, gust_max, fetched_at):
        return PointWeatherData(
            id=ids[o["name"]], name=o["name"], lat=o["lat"], lon=o["lon"],
            timeseries=_series(rows), aggregated=SegmentWeatherSummary(gust_max_kmh=gust_max),
            fetched_at=fetched_at, provider="openmeteo",
        )

    frisch = {}
    for o in orte:
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, ids[o["name"]], punkt(o, o["anchor"], o["gust_anker"], now - timedelta(hours=1)))
        frisch[ids[o["name"]]] = punkt(o, o["fresh"], o["gust_frisch"], now)

    class _Quelle:
        def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None, **kw):
            return frisch[point_id]

    gesendet = CompareAlertService(
        settings=settings, user_id=uid, weather_source=_Quelle(),
    ).check_all_compare_presets()
    assert gesendet == 1 and len(mit.sendungen("email")) == 1, (
        f"Vorbedingung: ein Alarm-Versand ({mit!r})")
    return mit


def test_ac5_ortsvergleich_roh_trotz_einfach_im_preset_ueber_den_versandweg(monkeypatch):
    """AC-5 (Versandweg, REGRESSIONSSCHUTZ -- ABSICHTLICH GRUEN): ein Preset, dessen
    ``outlook_metric_formats`` Boeen auf EINFACH stellen, aendert die Stundenzeilen des Alarms
    nicht -- Zelle == Briefing-Zelle in ROH, keine CSS-Punkte im HTML (der Ortsvergleich kennt
    die Roh/Einfach-Wahl nur fuer den 3-Tages-Ausblick, nicht fuer die Stundentabelle). Nur der
    betroffene Ort (Joch Mitte) hat Stundenzeilen, der Ort ohne Alarm (Tal Sued) keine."""
    fx = _load("ortsvergleich_drei_orte.json")
    orte = [_ort_fuer_lauf(fx["orte"][1], 10.0, 70.0), _ort_fuer_lauf(fx["orte"][2], 10.0, 10.0)]
    assert _cell("gust", 70.0, "raw") != _cell("gust", 70.0, "simplified"), (
        "Vorbedingung: ROH und EINFACH sehen bei Boeen verschieden aus")
    mit = _compare_lauf(
        monkeypatch, _user("cmp5"), orte, preset_id=f"cp-1737-{uuid.uuid4().hex[:6]}",
        display_config={"outlook_metric_formats": {
            "gust": True, "wind": True, "precipitation": True, "rain_probability": True}},
    )
    body = mit.sendungen("email")[0]["body"]
    hrows = _html_rows(body)
    roh = f"{_cell('gust', 10.0, 'raw')} → {_cell('gust', 70.0, 'raw')}"
    assert [r["time"] for r in hrows] == [_local(13)], f"Vorbedingung: eine Stundenzeile: {hrows!r}"
    assert roh in hrows[0]["text"], hrows[0]["text"]
    assert "<span" not in hrows[0]["html"], "Stundenzeile traegt CSS-Punkte statt roher Zahl"
    assert "Tal Sued" not in body


def test_ac5_ortsvergleich_ignoriert_trip_anzeige_konfiguration(monkeypatch):
    """AC-5/Test Plan 13: der Ortsvergleich-Alarm zeigt Stundenwerte IMMER roh (PO 2026-10-21).
    Reicht jemand an ``send_multi_location_deviation_alert`` eine Trip-artige Anzeige-
    Konfiguration mit Gewitter auf EINFACH, bleiben die Zeilen roh (Wort wie in der Stundentabelle
    der Vergleichs-Mail, kein CSS-Punkt). ROT bis die Konfiguration dort wirkungslos ist; wurde
    der Parameter ganz entfernt, gibt es nichts mehr zu ignorieren (Aufruf ohne ihn)."""
    import inspect

    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    fx = _load("ortsvergleich_drei_orte.json")
    anchors, fresh, changes = _compare_inputs(fx)
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_chat(_user("cmp5k"), settings)
    cfg = _trip(uid, "symbol", "symbol").display_config
    params = inspect.signature(NotificationService.send_multi_location_deviation_alert).parameters
    extra = {"display_config": cfg} if "display_config" in params else {}
    NotificationService(settings, uid).send_multi_location_deviation_alert(
        entities=[("Alpe Nord", [fresh["Alpe Nord"]], changes["Alpe Nord"])],
        effective_channels={"email"}, anchor_points=anchors, **extra,
    )
    mails = mit.sendungen("email")
    assert len(mails) == 1, f"Vorbedingung: eine Mail ({mit!r})"
    hrows = _html_rows(mails[0]["body"])
    assert [r["time"] for r in hrows] == ["14:00", "15:00", "16:00"], "Vorbedingung: drei Zeilen"
    for r, h in zip(hrows, fx["erwartet_utc_stunden"]["Alpe Nord"]):
        alt = _cell("thunder", _value_at(fx["orte"][0]["anchor"], h, "thunder_level"), "raw")
        neu = _cell("thunder", _value_at(fx["orte"][0]["fresh"], h, "thunder_level"), "raw")
        assert f"{alt} → {neu}" in r["text"], f"{r['time']}: nicht roh: {r['text']!r}"
        assert "<span" not in r["html"], f"{r['time']}: CSS-Punkte statt roher Worte"


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


def test_ac6_gewitter_zaehlt_jeden_stufenwechsel_auch_unter_der_alarmschwelle():
    """AC-6 (Gewitter = Metrik mit Stufe): betroffen ist JEDE Stunde mit Stufenwechsel,
    unabhaengig von der Alarmschwelle. Aus ``gewitter_14_16.json`` abgeleitet: frisch
    12Z MED (Anker HIGH, ein Schritt), 13Z LOW (HIGH, zwei), 14Z NONE (MED, zwei); die
    Schwelle 2 erreicht 12Z NICHT -- trotzdem steht 14:00 Ortszeit in den Zeilen.
    10Z/11Z und 15Z-17Z (kein Wechsel) erscheinen nicht. Ohne Stufen-Behandlung fiele
    12Z heraus (nur Abstand >= 2)."""
    from output.renderers.alert.render import render_email

    fx = _load("gewitter_14_16.json")
    neu = {12: "MED", 13: "LOW", 14: "NONE"}
    fx["fresh_stufen"] = [
        dict(r, thunder_level=neu.get(datetime.fromisoformat(r["ts"]).hour, r["thunder_level"]))
        for r in fx["fresh"]
    ]
    change = _wc(dict(fx["change"], threshold=2.0))
    erwartet = _expected(fx, [12, 13, 14], "thunder", "thunder_level", fresh_key="fresh_stufen")
    assert [t for t, _ in erwartet] == ["14:00", "15:00", "16:00"]
    msg = _trip_msg(fx, fresh_key="fresh_stufen", fm=modes(RAW), changes=[change])
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
# AC-11 / AC-14 -- Vorschau == Versand, je Nutzer  (Test Plan 9 + 12)
#
# Der Anfrage-Inhalt ist EXAKT die Form, die die Oberflaeche sendet
# (``frontend/.../alertPreviewHelpers.ts`` ``buildAlertPreviewBody``): synthetische ``changes``
# aus den Alarm-Regeln, OHNE Stundenreihen (Trip: ``segment_id`` = ``stages[0].id`` + feste
# ``segment_times`` 08:00-17:00; Ortsvergleich: ``location_id`` je Ort, kein ``segment_times``).
# Anker liegen im nutzergebundenen Speicher; der Frisch-Abruf laeuft durch die produktive
# Offline-Naht ``GZ_TEST_FIXTURE_DIR`` (Modul-Docstring).
# ===========================================================================

REPO_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"
BASIS_BOEEN = 10.0
TRIP_LAT, TRIP_LON = 47.2692, 11.4041
TRIP_ID = "trip-1737-vorschau"
# UTC-Stunden des heutigen Tages (Fixture-Eintrag i = HEUTE 00:00Z + i h) -> Boeen km/h.
# Trip: 18Z-20Z liegt AUSSERHALB des festen UI-Platzhalterfensters 08:00-17:00 (die
# Vorschau darf nicht dieses Fenster, sondern muss das Fenster der echten Etappe benutzen).
TRIP_STURM = {18: 50.0, 19: 70.0, 20: 90.0}
# Ortsvergleich: im Tagesfenster 9-16 Ortszeit (UTC+1/+2), damit der Versand ausloest.
CMP_STURM = {10: 50.0, 11: 70.0, 12: 90.0}


@pytest.fixture(autouse=True)
def _wetter_cache_leeren():
    """Der Segment-Wetter-Cache ist ein Prozess-Singleton (600 s) und wird von conftest NICHT
    geleert -- geplante Reihen duerfen weder aus fremden Tests kommen noch in sie lecken."""
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


def _heute0() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _plant(tmp_path: Path, monkeypatch, name: str, boeen: dict[int, float] | None = None) -> Path:
    """Fixture-Verzeichnis fuer ``GZ_TEST_FIXTURE_DIR``: Kopie der Demo-Fixtures, Boeen je
    Stunde = Basis, an den genannten UTC-Stunden des heutigen Tages der gegebene Wert. Alle
    drei Orte (der FixtureProvider nimmt den naechstgelegenen). ``boeen=None`` -> LEERES
    Verzeichnis: der Abruf scheitert (``ProviderError``, Datei nicht gefunden)."""
    from services.weather_cache import reset_shared_weather_cache_for_tests

    ziel = tmp_path / f"fx-{name}"
    ziel.mkdir(exist_ok=True)
    if boeen is not None:
        for datei in REPO_FIXTURES.glob("*.json"):
            raw = json.loads(datei.read_text(encoding="utf-8"))
            for i, p in enumerate(raw["data"]):
                p["gust_kmh"] = boeen.get(i, BASIS_BOEEN)
            (ziel / datei.name).write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(ziel))
    reset_shared_weather_cache_for_tests()
    return ziel


def _erwartete_zeilen(tz, stunden: dict[int, float], alt: dict[int, float]) -> list[tuple[str, str]]:
    """``[(HH:MM Ortszeit, 'alt → neu')]`` aus den GEPLANTEN Werten (Boeen, ROH)."""
    from utils.timezone import local_fmt

    return [
        (local_fmt(_heute0() + timedelta(hours=h), tz),
         f"{_cell('gust', alt.get(h, BASIS_BOEEN), 'raw')} → {_cell('gust', neu, 'raw')}")
        for h, neu in sorted(stunden.items())
    ]


def _stunden_reihe(boeen: dict[int, float]) -> list[dict]:
    """Stundenreihe im Snapshot-Format -- NUR fuer den toten Altvertrag ``hourly_*`` im Body."""
    return [{"ts": (_heute0() + timedelta(hours=i)).isoformat(),
             "gust_kmh": boeen.get(i, BASIS_BOEEN)} for i in range(24)]


def _stabil_gleich(mit_reihen, ohne_reihen, versuche: int = 3):
    """(a, b) mit ``b`` stabil (zweimal gleich, kein Minutenwechsel in der Stand-Zeile)."""
    for _ in range(versuche):
        a, b, c = mit_reihen(), ohne_reihen(), ohne_reihen()
        if b == c:
            return a, b
    pytest.fail("Vorschau-Ausgabe war in drei Laeufen nicht stabil (Uhr springt?)")


# ---- Trip ------------------------------------------------------------------

def _trip_bauen(trip_id: str):
    """Trip mit Etappe "1" HEUTE (Ortstag) und zwei Wegpunkten; ``segment_id`` der Oberflaeche
    (= ``stages[0].id``) trifft damit die echte Segment-Kennung "1"."""
    from datetime import time

    from app.trip import Stage, Trip, Waypoint
    from tests.helpers.ortstag import ortstag

    # Startzeit EXPLIZIT (#1709-Haertung): die Etappe haengt nicht am still
    # berechneten Naismith-Default; 08:00 passt zu ``segment_times`` 08:00-17:00.
    stage = Stage(
        id="1", name="Etappe 1", date=ortstag(TRIP_LAT, TRIP_LON), start_time=time(8, 0),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=TRIP_LAT, lon=TRIP_LON, elevation_m=600.0),
            Waypoint(id="G2", name="Ziel", lat=47.30, lon=11.45, elevation_m=1200.0),
        ],
    )
    return Trip(
        id=trip_id, name="Stunden-Trip", stages=[stage], official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id, metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )


def _trip_anker_schreiben(monkeypatch, tmp_path, snap_uid: str, trip, boeen: dict, name: str,
                          budget_uid: str | None = None) -> None:
    """Tages-Anker (``WeatherSnapshotService.save_dated``, Datum = Ortstag des Trips) mit den
    Boeen ``boeen``: erzeugt ueber den ECHTEN Abruf (FixtureProvider) fuer eine ganztaegige
    Etappe, wie ein Briefing ihn schreibt."""
    from providers.base import get_provider
    from services.segment_weather import SegmentWeatherService
    from services.trip_day import trip_local_today
    from services.weather_snapshot import WeatherSnapshotService

    _plant(tmp_path, monkeypatch, name, boeen)
    start = _heute0()
    punkt = GPXPoint(lat=TRIP_LAT, lon=TRIP_LON, elevation_m=600, distance_from_start_km=0.0)
    ende = GPXPoint(lat=47.30, lon=11.45, elevation_m=1200, distance_from_start_km=5.0)
    seg = TripSegment(
        segment_id="1", start_point=punkt, end_point=ende, start_time=start,
        end_time=start + timedelta(hours=23, minutes=59), duration_hours=23.98,
        distance_km=5.0, ascent_m=600, descent_m=0,
    )
    anker = SegmentWeatherService(get_provider("openmeteo")).fetch_segment_weather(
        seg, enrich_ensemble=False, enrich_snow=False, priority="alert_check",
        user_id=budget_uid or snap_uid,
    )
    assert not anker.has_error and anker.timeseries and len(anker.timeseries.data) >= 24, (
        "Vorbedingung: Anker-Abruf ueber die Fixture-Naht"
    )
    heute = trip_local_today(trip, datetime.now(UTC))
    WeatherSnapshotService(snap_uid).save_dated(trip.id, heute, [anker])
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()


def _trip_welt(monkeypatch, tmp_path, uid: str, *, anker_boeen: dict | None, trip_id: str = TRIP_ID):
    """Trip des Nutzers im Speicher (``save_trip``) und, falls ``anker_boeen`` gegeben, sein
    Tages-Anker. ``anker_boeen=None`` -> KEIN Anker."""
    from app.loader import save_trip

    trip = _trip_bauen(trip_id)
    save_trip(trip, user_id=uid)
    if anker_boeen is not None:
        _trip_anker_schreiben(monkeypatch, tmp_path, uid, trip, anker_boeen, f"anker-{uid[-6:]}")
    return trip


def _trip_body(*, mit_altvertrag: dict | None = None) -> dict:
    """Body wie ``buildAlertPreviewBody('route', ...)``: eine Boeen-Regel (Schwelle 50), die
    synthetischen Werte 0.8x/1.2x der Schwelle, ``segment_id`` = ``stages[0].id``,
    ``segment_times`` fix 08:00-17:00. ``mit_altvertrag`` haengt den ALTEN, toten ``hourly_*``-
    Vertrag an (die Oberflaeche sendet ihn nie)."""
    change = {
        "metric": "gust_max_kmh", "old_value": 40.0, "new_value": 60.0, "delta": 20.0,
        "threshold": 50.0, "severity": "moderate", "direction": "above", "segment_id": "1",
    }
    if mit_altvertrag is not None:
        change["hourly_old"] = _stunden_reihe({})
        change["hourly_new"] = _stunden_reihe(mit_altvertrag)
    return {"changes": [change],
            "segment_times": [{"segment_id": "1", "start": "08:00", "end": "17:00"}]}


def _vorschau_trip(uid: str, body: dict, einstieg: str = "briefing", trip_id: str = TRIP_ID) -> dict:
    """ECHTER Einstieg: Router-Funktion, kein test-eigener kwarg."""
    from api.routers.validator import AlertPreviewBody, alert_preview, briefing_alert_preview

    if einstieg == "alert_preview":
        return alert_preview(trip_id, AlertPreviewBody.model_validate(body), user_id=uid)
    return briefing_alert_preview(trip_id, body, kind="route", user_id=uid)


def _trip_versand(monkeypatch, uid: str, trip) -> tuple[list[str], list[str]]:
    """Referenz: derselbe Weg wie ``check_and_send_alerts`` -- Anker aus dem Speicher
    (``_get_cached_weather``), frische Reihe (``_fetch_fresh_weather``), Versand ueber
    ``NotificationService.send_deviation_alert`` (E-Mail-Klartext ueber ``mail_sink``, Telegram am
    Transport-Aufzeichner). Aenderung = die, die die Engine bei 10 -> 90 km/h erzeugt; fuer die
    Stufenmetrik Boeen haengen die Zeilen nicht an deren Zahlen. Gibt (Mails, Telegram-Koerper)."""
    from services.notification_service import NotificationService
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import settings_email_only
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    svc = TripAlertService(settings=settings_email_only(), user_id=uid)
    anker = svc._get_cached_weather(
        trip, tagesgleicher_anker_noetig=True, now_utc=datetime.now(UTC))
    assert anker, "Vorbedingung: der Tages-Anker liegt im nutzergebundenen Speicher"
    frisch = svc._fetch_fresh_weather(anker)
    assert frisch and frisch[0].timeseries, "Vorbedingung: Frisch-Abruf ueber die Fixture-Naht"
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    mit_profil_chat(uid, settings)
    change = WeatherChange(
        metric="gust_max_kmh", old_value=10.0, new_value=90.0, delta=80.0, threshold=20.0,
        severity=ChangeSeverity.MAJOR, direction="increase", segment_id="1",
        occurred_at=_heute0() + timedelta(hours=19),
    )
    mails: list[str] = []
    NotificationService(settings, uid).send_deviation_alert(
        trip=trip, weather=frisch, changes=[change], effective_channels={"email", "telegram"},
        mail_sink=lambda subject, body: mails.append(body), anchor_weather=anker,
    )
    return mails, [s["body"] for s in mit.sendungen("telegram")]


@pytest.mark.parametrize("einstieg", ["briefing", "alert_preview"])
def test_ac11_trip_vorschau_zeigt_dieselben_stundenzeilen_wie_der_versand(
    env, monkeypatch, tmp_path, einstieg,  # noqa: F811
):
    """AC-11 (Trip): Anker im Speicher des Nutzers (Tages-Snapshot, heute), frische Reihe ueber
    die Fixture-Naht. Body = Oberflaechen-Form OHNE Stundenreihen. Die Vorschau (E-Mail-Klartext
    und Telegram) traegt dieselben Stundenzeilen wie der Versand auf demselben Datenstand --
    und es SIND welche (18Z-20Z, ausserhalb des UI-Platzhalterfensters). Beide Einstiege."""
    from utils.timezone import tz_for_coords

    uid = env
    trip = _trip_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    erwartet = _erwartete_zeilen(tz_for_coords(TRIP_LAT, TRIP_LON), TRIP_STURM, {})
    assert len(erwartet) == 3

    mails, tgs = _trip_versand(monkeypatch, uid, trip)
    assert len(mails) == 1 and len(tgs) == 1, "Vorbedingung: je Kanal eine Sendung"
    assert _rows(mails[0]) == erwartet, f"Vorbedingung: Versand-Mail traegt die Zeilen: {mails[0]!r}"
    assert _rows(tgs[0]) == erwartet, f"Vorbedingung: Versand-Telegram traegt die Zeilen: {tgs[0]!r}"

    vorschau = _vorschau_trip(uid, _trip_body(), einstieg)
    assert _rows(vorschau["email_plain"]) == _rows(mails[0])
    assert _rows(vorschau["telegram"]) == _rows(tgs[0])
    assert [r["time"] for r in _html_rows(vorschau["email_html"])] == [t for t, _ in erwartet]


def test_ac11_trip_ohne_anker_ist_die_vorschau_wie_ohne_stundenreihe_auch_mit_body_reihen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-11/AC-10 (Trip): ohne Anker im Speicher kann keine alte Reihe entstehen. Die Vorschau
    ist byte-gleich zur Vorschau OHNE ``hourly_*`` im Body -- die Reihen des Altvertrags im Body
    erzeugen nichts. Zuerst die Anwesenheit mit Anker (sonst vakuum-gruen), dann ohne."""
    from utils.timezone import tz_for_coords

    uid = env
    trip = _trip_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    erwartet = _erwartete_zeilen(tz_for_coords(TRIP_LAT, TRIP_LON), TRIP_STURM, {})
    assert _rows(_vorschau_trip(uid, _trip_body())["email_plain"]) == erwartet, (
        "Vorbedingung: mit Anker traegt die Vorschau die Stundenzeilen")

    from app.loader import get_snapshots_dir

    for datei in get_snapshots_dir(uid).glob(f"{trip.id}*.json"):
        datei.unlink()
    mit_reihen, ohne_reihen = _stabil_gleich(
        lambda: _vorschau_trip(uid, _trip_body(mit_altvertrag=TRIP_STURM)),
        lambda: _vorschau_trip(uid, _trip_body()),
    )
    assert mit_reihen == ohne_reihen, "Body-Reihen duerfen die Vorschau nicht veraendern"
    assert not any("→" in rest for _t, rest in _rows(mit_reihen["email_plain"])), (
        "ohne Anker darf es kein 'alt →' geben")


def test_ac11_trip_scheiternder_frischabruf_laesst_die_vorschau_ohne_stundenzeilen_ohne_fehler(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-11/AC-10 (Trip): Anker da, aber der Frisch-Abruf scheitert (Fixture-Verzeichnis ohne
    Dateien -> ``ProviderError``) -> keine Stundenzeilen, KEIN Fehler, Antwort vollstaendig.
    Anwesenheit zuerst: mit funktionierendem Abruf gibt es Zeilen."""
    from utils.timezone import tz_for_coords

    uid = env
    _trip_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    erwartet = _erwartete_zeilen(tz_for_coords(TRIP_LAT, TRIP_LON), TRIP_STURM, {})
    assert _rows(_vorschau_trip(uid, _trip_body())["email_plain"]) == erwartet, (
        "Vorbedingung: mit funktionierendem Abruf traegt die Vorschau die Stundenzeilen")

    _plant(tmp_path, monkeypatch, "leer", None)
    vorschau = _vorschau_trip(uid, _trip_body(mit_altvertrag=TRIP_STURM))
    assert set(vorschau) >= {"subject", "email_html", "email_plain", "telegram", "sms"}
    assert _rows(vorschau["email_plain"]) == [] and _rows(vorschau["telegram"]) == []
    assert _html_rows(vorschau["email_html"]) == []


# ---- Ortsvergleich -----------------------------------------------------------

def _cmp_orte() -> list:
    from tests.tdd.test_alert_preview_compare_paritaet import LOCATIONS

    return [loc for loc in LOCATIONS if loc.id in ("loc-ibk", "loc-bz")]


def _cmp_anker_schreiben(monkeypatch, tmp_path, snap_uid: str, boeen: dict, name: str) -> None:
    """Anker je Ort (``CompareWeatherSnapshotService.save``): erzeugt ueber
    ``CompareLocationWeatherSource().fetch`` -- dieselbe Quelle, die der Report-Versand beim
    Schreiben des Ankers benutzt -- mit den Boeen ``boeen`` (FixtureProvider)."""
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    _plant(tmp_path, monkeypatch, name, boeen)
    snap = CompareWeatherSnapshotService(user_id=snap_uid)
    for loc in _cmp_orte():
        punkt = CompareLocationWeatherSource().fetch(
            loc.id, loc.lat, loc.lon, 9, 16, elevation_m=loc.elevation_m, user_id=snap_uid)
        assert punkt.timeseries and len(punkt.timeseries.data) >= 24, "Vorbedingung: Anker-Abruf"
        snap.save(PRESET_ID, loc.id, punkt)
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()


def _cmp_welt(monkeypatch, tmp_path, uid: str, *, anker_boeen: dict | None) -> dict:
    """Preset + Orte des Nutzers (``_seed``) und, falls ``anker_boeen`` gegeben, die Anker."""
    from tests.tdd.test_alert_preview_compare_paritaet import _seed

    preset = _seed(uid)
    if anker_boeen is not None:
        _cmp_anker_schreiben(monkeypatch, tmp_path, uid, anker_boeen, f"canker-{uid[-6:]}")
    return preset


def _cmp_body(*, mit_altvertrag: dict | None = None) -> dict:
    """Body wie ``buildAlertPreviewBody('vergleich', ...)``: je Ort dieselbe synthetische
    Regel-Aenderung mit ``location_id``, ohne ``segment_times``/``segment_id``."""
    out = []
    for loc in _cmp_orte():
        change = {
            "metric": "gust_max_kmh", "old_value": 40.0, "new_value": 60.0, "delta": 20.0,
            "threshold": 50.0, "severity": "moderate", "direction": "above",
            "location_id": loc.id,
        }
        if mit_altvertrag is not None:
            change["hourly_old"] = _stunden_reihe({})
            change["hourly_new"] = _stunden_reihe(mit_altvertrag)
        out.append(change)
    return {"changes": out}


def _vorschau_cmp(uid: str, body: dict, einstieg: str = "briefing") -> dict:
    from api.routers.validator import briefing_alert_preview
    from services.compare_alert_preview_service import render_compare_alert_preview
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    if einstieg == "render":
        return render_compare_alert_preview(PRESET_ID, user_id=uid, body=body)
    return briefing_alert_preview(PRESET_ID, body, kind="vergleich", user_id=uid)


def _cmp_versand(monkeypatch, uid: str, preset: dict) -> tuple[list[str], list[list[tuple[str, str]]]]:
    """Referenz: ``_evaluate_one_location`` + ``send_multi_location_deviation_alert`` -- Anker
    aus ``CompareWeatherSnapshotService.load``, frische Reihe ueber
    ``CompareLocationWeatherSource().fetch`` (selbe Argumente wie ``compare_alert.py``), Versand
    mit denselben Parametern wie der Produktionsweg. Gibt (Klartext-Mails, Telegram-Zeilen je
    Blase)."""
    from app.models import ChangeSeverity, WeatherChange
    from services.compare_alert import CompareAlertService
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd.test_alert_preview_compare_paritaet import LOCATIONS, PRESET_ID

    snap = CompareWeatherSnapshotService(user_id=uid)
    entities, anchors = [], {}
    for loc in _cmp_orte():
        geladen = snap.load(PRESET_ID, loc.id)
        assert geladen, f"Vorbedingung: Anker fuer {loc.id} im Speicher des Nutzers"
        frisch = CompareLocationWeatherSource().fetch(
            loc.id, loc.lat, loc.lon, 9, 16, elevation_m=loc.elevation_m, user_id=uid)
        change = WeatherChange(
            metric="gust_max_kmh", old_value=10.0, new_value=90.0, delta=80.0, threshold=20.0,
            severity=ChangeSeverity.MAJOR, direction="increase",
        )
        entities.append((loc.name, [frisch], [change]))
        anchors[loc.name] = geladen[0]
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    mit_profil_chat(uid, settings)
    mails: list[str] = []
    positions = CompareAlertService._location_positions(
        preset["location_ids"], {loc.id: loc for loc in LOCATIONS})
    NotificationService(settings, uid).send_multi_location_deviation_alert(
        entities=entities, effective_channels={"email", "telegram"},
        mail_sink=lambda subject, body: mails.append(body), location_positions=positions,
        telegram_style=effective_compare_telegram_style(preset), anchor_points=anchors,
    )
    return mails, sorted(_rows(s["body"]) for s in mit.sendungen("telegram"))


@pytest.mark.parametrize("einstieg", ["briefing", "render"])
def test_ac11_ortsvergleich_vorschau_zeigt_dieselben_stundenzeilen_wie_der_versand(
    env, monkeypatch, tmp_path, einstieg,  # noqa: F811
):
    """AC-11 (Ortsvergleich): Anker je Ort im Speicher des Nutzers, frische Reihe ueber die
    Fixture-Naht (Provider wie im Versand). Body = Oberflaechen-Form (``location_id``, OHNE
    Stundenreihen). Vorschau (Klartext + jede Telegram-Blase) == Versand auf demselben Datenstand,
    und es SIND Zeilen (3 je Ort). Beide Einstiege (Router-Funktion und Dienst)."""
    from utils.timezone import tz_for_coords

    uid = env
    preset = _cmp_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    erwartet = []
    for loc in _cmp_orte():
        erwartet += _erwartete_zeilen(tz_for_coords(loc.lat, loc.lon), CMP_STURM, {})

    mails, blasen = _cmp_versand(monkeypatch, uid, preset)
    assert len(mails) == 1 and len(blasen) == 2, f"Vorbedingung: eine Mail, zwei Blasen ({blasen!r})"
    assert _rows(mails[0]) == erwartet, f"Vorbedingung: Versand traegt die Zeilen: {mails[0]!r}"
    assert all(len(b) == 3 for b in blasen), "Vorbedingung: je Ort drei Zeilen in der Blase"

    vorschau = _vorschau_cmp(uid, _cmp_body(), einstieg)
    assert _rows(vorschau["email_plain"]) == _rows(mails[0])
    assert sorted(_rows(b) for b in vorschau["telegram_bubbles"]) == blasen


def test_ac11_ortsvergleich_ohne_anker_ist_die_vorschau_unabhaengig_von_body_reihen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-11/AC-10 (Ortsvergleich): ohne Anker im Speicher erzeugen die Reihen des Altvertrags
    im Body nichts -- Vorschau mit == Vorschau ohne ``hourly_*`` (ob die frische Reihe dann
    'nur neu'-Zeilen ergibt, regelt AC-10; hier zaehlt: nie 'alt →' und nie Body-Reihen).
    Anwesenheit zuerst."""
    from utils.timezone import tz_for_coords

    uid = env
    _cmp_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    erwartet = []
    for loc in _cmp_orte():
        erwartet += _erwartete_zeilen(tz_for_coords(loc.lat, loc.lon), CMP_STURM, {})
    assert _rows(_vorschau_cmp(uid, _cmp_body())["email_plain"]) == erwartet, (
        "Vorbedingung: mit Anker traegt die Vorschau die Stundenzeilen")

    from app.loader import get_data_dir

    for datei in (get_data_dir(uid) / "compare_weather_snapshots").glob("*.json"):
        datei.unlink()
    mit_reihen, ohne_reihen = _stabil_gleich(
        lambda: _vorschau_cmp(uid, _cmp_body(mit_altvertrag=CMP_STURM)),
        lambda: _vorschau_cmp(uid, _cmp_body()),
    )
    assert mit_reihen == ohne_reihen, "Body-Reihen duerfen die Vorschau nicht veraendern"
    assert not any("→" in rest for _t, rest in _rows(mit_reihen["email_plain"])), (
        "ohne Anker darf es kein 'alt →' geben")


def test_ac11_ortsvergleich_scheiternder_frischabruf_ohne_stundenzeilen_ohne_fehler(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-11/AC-10 (Ortsvergleich): Anker da, Frisch-Abruf scheitert (leeres Fixture-Verzeichnis)
    -> keine Stundenzeilen, kein Fehler, Antwort vollstaendig -- auch wenn der Body (Altvertrag)
    Reihen traegt. Anwesenheit zuerst."""
    from utils.timezone import tz_for_coords

    uid = env
    _cmp_welt(monkeypatch, tmp_path, uid, anker_boeen={})
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    erwartet = []
    for loc in _cmp_orte():
        erwartet += _erwartete_zeilen(tz_for_coords(loc.lat, loc.lon), CMP_STURM, {})
    assert _rows(_vorschau_cmp(uid, _cmp_body())["email_plain"]) == erwartet, (
        "Vorbedingung: mit funktionierendem Abruf traegt die Vorschau die Stundenzeilen")

    _plant(tmp_path, monkeypatch, "leer", None)
    vorschau = _vorschau_cmp(uid, _cmp_body(mit_altvertrag=CMP_STURM))
    assert set(vorschau) >= {"subject", "email_html", "email_plain", "telegram",
                             "telegram_bubbles", "sms"}
    assert _rows(vorschau["email_plain"]) == []
    assert all(_rows(b) == [] for b in vorschau["telegram_bubbles"])


# ---- AC-14: zwei Nutzer ----------------------------------------------------------------

ANKER_B = {18: 10.0, 19: 10.0, 20: 10.0}           # Nutzer B: gruen (10)
ANKER_A = {18: 20.0, 19: 25.0, 20: 30.0}           # Nutzer A: andere Alt-Werte
ANKER_DEFAULT = {18: 25.0, 19: 25.0, 20: 25.0}     # "default": darf NIE sichtbar werden


def test_ac14_trip_vorschau_liest_nie_anker_eines_anderen_nutzers_oder_default(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-14 (Trip): Nutzer A und B mit gleicher Trip-Kennung; Anker NUR bei B (plus einer unter
    "default"). Vorschau B zeigt B-Zeilen (Anwesenheit). Vorschau A zeigt keine 'alt →'-Zeilen
    (nichts aus B oder default). Mit eigenem Anker zeigt A seine Zeilen -- Alt-Werte aus A-Daten,
    unterscheidbar von B."""
    from app.loader import get_snapshots_dir
    from utils.timezone import tz_for_coords

    uid_a, uid_b = f"{env}-a", f"{env}-b"
    assert str(get_snapshots_dir("default")).startswith(str(tmp_path)), "Daten-Root isoliert"
    trip_b = _trip_welt(monkeypatch, tmp_path, uid_b, anker_boeen=ANKER_B)
    _trip_anker_schreiben(monkeypatch, tmp_path, "default", trip_b, ANKER_DEFAULT, "anker-default",
                          budget_uid=uid_b)
    _trip_welt(monkeypatch, tmp_path, uid_a, anker_boeen=None)
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    tz = tz_for_coords(TRIP_LAT, TRIP_LON)
    erwartet_b = _erwartete_zeilen(tz, TRIP_STURM, ANKER_B)
    erwartet_a = _erwartete_zeilen(tz, TRIP_STURM, ANKER_A)
    assert erwartet_a != erwartet_b

    assert _rows(_vorschau_trip(uid_b, _trip_body())["email_plain"]) == erwartet_b, (
        "Vorbedingung: Nutzer B sieht seine eigenen Stundenzeilen")
    ohne = _vorschau_trip(uid_a, _trip_body())
    for kanal in ("email_plain", "telegram"):
        assert not any("→" in rest for _t, rest in _rows(ohne[kanal])), (
            f"A sieht Alt-Werte aus fremdem Speicher ({kanal}): {ohne[kanal]!r}")

    trip_a = _trip_bauen(TRIP_ID)
    _trip_anker_schreiben(monkeypatch, tmp_path, uid_a, trip_a, ANKER_A, "anker-a")
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    mit_eigenem = _vorschau_trip(uid_a, _trip_body())
    assert _rows(mit_eigenem["email_plain"]) == erwartet_a
    assert _rows(mit_eigenem["telegram"]) == erwartet_a
    assert _rows(_vorschau_trip(uid_b, _trip_body())["email_plain"]) == erwartet_b, "B unveraendert"


def test_ac14_ortsvergleich_vorschau_liest_nie_anker_eines_anderen_nutzers_oder_default(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """AC-14 (Ortsvergleich): wie der Trip-Test -- gleiche Preset- und Orts-Kennungen bei A und
    B, Anker nur bei B (plus unter "default"). Vorschau A zeigt nie 'alt →' aus fremdem Speicher;
    mit eigenem Anker zeigt A seine Zeilen (andere Alt-Werte als B)."""
    from app.loader import get_data_dir
    from utils.timezone import tz_for_coords

    cmp_a = {10: 20.0, 11: 25.0, 12: 30.0}
    cmp_b = {10: 10.0, 11: 10.0, 12: 10.0}
    cmp_default = {10: 25.0, 11: 25.0, 12: 25.0}
    uid_a, uid_b = f"{env}-a", f"{env}-b"
    assert str(get_data_dir("default")).startswith(str(tmp_path)), "Daten-Root isoliert"
    _cmp_welt(monkeypatch, tmp_path, uid_b, anker_boeen=cmp_b)
    _cmp_anker_schreiben(monkeypatch, tmp_path, "default", cmp_default, "canker-default")
    _cmp_welt(monkeypatch, tmp_path, uid_a, anker_boeen=None)
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)

    def erwartet(alt):
        out = []
        for loc in _cmp_orte():
            out += _erwartete_zeilen(tz_for_coords(loc.lat, loc.lon), CMP_STURM, alt)
        return out

    assert erwartet(cmp_a) != erwartet(cmp_b)
    assert _rows(_vorschau_cmp(uid_b, _cmp_body())["email_plain"]) == erwartet(cmp_b), (
        "Vorbedingung: Nutzer B sieht seine eigenen Stundenzeilen")
    ohne = _vorschau_cmp(uid_a, _cmp_body())
    assert not any("→" in rest for _t, rest in _rows(ohne["email_plain"])), (
        f"A sieht Alt-Werte aus fremdem Speicher: {ohne['email_plain']!r}")
    for blase in ohne["telegram_bubbles"]:
        assert not any("→" in rest for _t, rest in _rows(blase))

    _cmp_anker_schreiben(monkeypatch, tmp_path, uid_a, cmp_a, "canker-a")
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    mit_eigenem = _vorschau_cmp(uid_a, _cmp_body())
    assert _rows(mit_eigenem["email_plain"]) == erwartet(cmp_a)
    assert _rows(_vorschau_cmp(uid_b, _cmp_body())["email_plain"]) == erwartet(cmp_b), "B unveraendert"


# ===========================================================================
# AC-13 (Ortsvergleich-Teil) -- Daten und Ausgabe bleiben beim eigenen Nutzer
# ===========================================================================

def test_ac13_zwei_nutzer_ortsvergleich_alarm_enthaelt_nur_eigene_orte_anker_und_zeilen(monkeypatch):
    """AC-13 (Ortsvergleich, REGRESSIONSSCHUTZ -- ABSICHTLICH GRUEN): zwei Nutzer mit je einem
    Ortsvergleich unter GLEICHER Preset-Kennung, aber eigenen Orten und eigenen Ankern. Der Alarm
    jedes Nutzers (realer ``CompareAlertService``-Lauf) nennt nur den eigenen Ort und traegt nur
    Stundenzeilen aus dem eigenen Anker/der eigenen frischen Reihe."""
    fx = _load("ortsvergleich_drei_orte.json")
    gleiche_kennung = f"cp-1737-{uuid.uuid4().hex[:6]}"
    ort_a = dict(fx["orte"][1], name="Joch Alpha")
    ort_b = dict(fx["orte"][1], name="Joch Beta",
                 anchor=[dict(r, gust_kmh=25.0) for r in fx["orte"][1]["anchor"]])

    def lauf(ort, prefix):
        mit = _compare_lauf(
            monkeypatch, _user(prefix), [_ort_fuer_lauf(ort, 10.0, 70.0)], preset_id=gleiche_kennung)
        return mit.sendungen("email")[0]["body"]

    mail_a, mail_b = lauf(ort_a, "cmpa"), lauf(ort_b, "cmpb")
    roh_a = f"{_cell('gust', 10.0, 'raw')} → {_cell('gust', 70.0, 'raw')}"
    roh_b = f"{_cell('gust', 25.0, 'raw')} → {_cell('gust', 70.0, 'raw')}"
    assert roh_a != roh_b
    rows_a, rows_b = _html_rows(mail_a), _html_rows(mail_b)
    assert [r["time"] for r in rows_a] == [r["time"] for r in rows_b] == [_local(13)]
    assert roh_a in rows_a[0]["text"] and roh_b in rows_b[0]["text"]
    assert "Joch Alpha" in mail_a and "Joch Beta" not in mail_a
    assert "Joch Beta" in mail_b and "Joch Alpha" not in mail_b


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


# ===========================================================================
# AC-2 (Ampel-Metrik) -- "Einfach" ist im Editor ``use_friendly_format``, kein format_mode
# ===========================================================================

def test_ac2_boeen_einfach_ueber_use_friendly_format_zeigt_punkte_im_alarm(monkeypatch):
    """AC-2: der Editor speichert "Einfach" fuer Boeen als ``use_friendly_format=True``
    (format_mode bleibt unbelegt = raw). Das Briefing leitet den Punkt aus
    ``build_html_indicator_keys`` ab -- der Alarm muss dasselbe tun, sonst zeigt die
    Alarm-Mail Zahlen, wo das Briefing Punkte zeigt. Gegenprobe: ``use_friendly_format=False``
    -> Zahlen."""
    from app.trip import Stage, Trip, Waypoint
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    fx = _load("boeen_stufe_statt_schwelle.json")

    def lauf(friendly: bool):
        mit = aufzeichner_installieren(monkeypatch)
        settings = _settings()
        uid = mit_profil_chat(_user("gust"), settings)
        tid = f"trip-1737-{uuid.uuid4().hex[:6]}"
        stage = Stage(
            id="T1", name="Tag 1", date=datetime(2026, 5, 1).date(),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
        )
        trip = Trip(
            id=tid, name="Boeen-Trip", stages=[stage], official_warnings=None, corridors=[],
            display_config=UnifiedWeatherDisplayConfig(
                trip_id=tid,
                metrics=[MetricConfig(metric_id="gust", enabled=True, use_friendly_format=friendly)],
            ),
        )
        NotificationService(settings, uid).send_deviation_alert(
            trip=trip, weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
            effective_channels={"email"}, anchor_weather=[_segment_data(fx, fx["anchor"])],
        )
        sendungen = mit.sendungen("email")
        assert len(sendungen) == 1, f"Vorbedingung: eine Mail ({mit!r})"
        return _html_rows(sendungen[0]["body"])

    einfach, roh = lauf(True), lauf(False)
    assert [r["time"] for r in einfach] == [r["time"] for r in roh] == ["14:00"]
    alt = _norm_html(_html_cell("gust", 28.0, "simplified"))
    neu = _norm_html(_html_cell("gust", 31.0, "simplified"))
    assert alt in einfach[0]["html"] and neu in einfach[0]["html"], einfach[0]["html"]
    assert "<span" not in roh[0]["html"] and "28" in roh[0]["text"] and "31" in roh[0]["text"]


# ===========================================================================
# Fix-Loop 1 (Adversary F001/F003/F005)
# ===========================================================================

def _compare_alert_lauf(monkeypatch, uid: str, ort: dict) -> list[str]:
    """Ein REALER Lauf von ``CompareAlertService.check_all_compare_presets`` mit einem
    Ort: echter Snapshot-Anker (``CompareWeatherSnapshotService.save``, Stundenreihe
    inklusive), Fake-Wetterquelle mit der frischen Reihe aus der Fixture (kein Mock),
    Transport-Aufzeichner. Gibt die versendeten Mail-Koerper zurueck."""
    from app.loader import get_data_dir, save_location
    from app.user import SavedLocation
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData
    from tests.helpers.alert_log_fixtures import settings_email_only
    from tests.helpers.compare_briefings import write_compare_briefings
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    mit = aufzeichner_installieren(monkeypatch)
    preset_id, location_id = f"cp-1737-{uuid.uuid4().hex[:6]}", f"loc-1737-{uuid.uuid4().hex[:6]}"
    loc = SavedLocation(id=location_id, name=ort["name"], lat=ort["lat"], lon=ort["lon"],
                        elevation_m=1000)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_dir(uid), [{
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": [location_id], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-07-09T00:00:00Z",
        "cooldown_minutes": 0,
    }])
    now = datetime.now(UTC)

    def punkt(rows, gust_max, fetched_at):
        return PointWeatherData(
            id=location_id, name=loc.name, lat=loc.lat, lon=loc.lon,
            timeseries=_series(rows), aggregated=SegmentWeatherSummary(gust_max_kmh=gust_max),
            fetched_at=fetched_at, provider="openmeteo",
        )

    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, location_id, punkt(ort["anchor"], 10.0, now - timedelta(hours=1)))
    frisch = punkt(ort["fresh"], 70.0, now)

    class _Quelle:
        def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None, **kw):
            return frisch

    mails: list[tuple[str, str]] = []
    gesendet = CompareAlertService(
        settings=settings_email_only(), user_id=uid, weather_source=_Quelle(),
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    assert gesendet == 1 and len(mails) == 1, f"Vorbedingung: ein Alarm ({mit!r}, {mails!r})"
    return [m[1] for m in mails]


def test_f001_ortsvergleich_service_reicht_alte_reihe_bis_zur_versendeten_mail_durch(monkeypatch):
    """F001: der PRODUKTIONSWEG des Ortsvergleich-Alarms (CompareAlertService, echter
    Snapshot-Anker) liefert in der versendeten Mail Stundenzeilen ``alt → neu`` -- nicht
    nur ``neu``. Rot, wenn compare_alert.py den Anker nicht durchreicht
    (``anchor_points=None`` bzw. ``"anchor_point": None``)."""
    fx = _load("ortsvergleich_drei_orte.json")
    ort = fx["orte"][1]  # Joch Mitte: Boeen 10 -> 70 km/h
    mails = _compare_alert_lauf(monkeypatch, _user("cmpsvc"), ort)
    erwartet = [
        (_local(h), f"{_cell('gust', _value_at(ort['anchor'], h, 'gust_kmh'), 'raw')} → "
                    f"{_cell('gust', _value_at(ort['fresh'], h, 'gust_kmh'), 'raw')}")
        for h in fx["erwartet_utc_stunden"]["Joch Mitte"]
    ]
    assert erwartet, "Vorbedingung: Fixture nennt betroffene Stunden"
    assert _rows(mails[0]) == erwartet, mails[0]


def test_f003_anker_kommt_vom_segment_der_aenderung_nicht_vom_ersten():
    """F003: Trip mit zwei Segmenten, Anker-Werte je Segment verschieden. Die Aenderung
    betrifft Segment "2" -> die Alt-Spalte stammt aus dem Anker von Segment "2"."""
    from output.renderers.alert.project import to_alert_message

    fx = _load("gewitter_14_16.json")
    falsch = [dict(r, thunder_level="NONE") for r in fx["anchor"]]  # Segment 1: nie Gewitter
    change = _wc(dict(fx["change"], segment_id="2"))
    msg = to_alert_message(
        [change], [_segment_data(fx, fx["fresh"], "2")], "Trip X", tz=TZ, stand_at=STAND,
        anchor_segments=[_segment_data(fx, falsch, "1"), _segment_data(fx, fx["anchor"], "2")],
    )
    zeilen = [(h.time, h.value_from, h.value_to) for e in msg.events for h in e.hours]
    assert zeilen, "Vorbedingung: Stundenzeilen entstanden"
    assert all(von is not None and von > 0 for _t, von, _n in zeilen), zeilen
    ohne_passenden_anker = to_alert_message(
        [change], [_segment_data(fx, fx["fresh"], "2")], "Trip X", tz=TZ, stand_at=STAND,
        anchor_segments=[_segment_data(fx, falsch, "1")],
    )
    assert all(h.value_from is None for e in ohne_passenden_anker.events for h in e.hours)


def test_f005_nicht_numerischer_stundenwert_laesst_den_alarm_raus_ohne_stundenzeilen():
    """F005: eine Stundenreihe mit nicht-numerischem Wert darf den Alarm nicht kippen --
    das Ereignis bleibt, nur ohne Stundenzeilen (fail-soft in ``_hour_fields``)."""
    from output.renderers.alert.project import to_alert_message

    fx = _load("boeen_stufe_statt_schwelle.json")
    gut = to_alert_message([_wc(fx["change"])], [_segment_data(fx, fx["fresh"])], "Trip X",
                           tz=TZ, stand_at=STAND, anchor_segments=[_segment_data(fx, fx["anchor"])])
    assert [h for e in gut.events for h in e.hours], "Vorbedingung: mit sauberen Daten Zeilen"
    kaputt = [dict(r, gust_kmh="boe") for r in fx["fresh"]]
    msg = to_alert_message([_wc(fx["change"])], [_segment_data(fx, kaputt)], "Trip X",
                           tz=TZ, stand_at=STAND, anchor_segments=[_segment_data(fx, fx["anchor"])])
    assert len(msg.events) == 1
    assert all(not e.hours for e in msg.events)


def test_f004_telegram_mehrere_ereignisse_folgen_dem_telegram_modus_nicht_dem_mail_modus():
    """F004: zweiter Telegram-Zweig (mehrere Ereignisse, render.py ``else``-Block) liest
    den Telegram-Modus -- Boeen ROH ``10 → 65`` vs. EINFACH Stufenwort."""
    from output.renderers.alert.render import render_telegram

    fx = _load("pop_und_boeen.json")
    changes = [_wc(c) for c in fx["changes"]]
    einfach_boeen = {**RAW, "gust": "simplified"}
    gust_roh = (_local(13), f"{_cell('gust', 10.0, 'raw')} → {_cell('gust', 65.0, 'raw')}")
    gust_einfach = (_local(13), f"{_cell('gust', 10.0, 'simplified')} → "
                                f"{_cell('gust', 65.0, 'simplified')}")
    assert gust_roh != gust_einfach, "Vorbedingung: ROH und EINFACH unterscheiden sich"

    tg_einfach = render_telegram(_trip_msg(fx, fm=modes(RAW, einfach_boeen), changes=changes))
    tg_roh = render_telegram(_trip_msg(fx, fm=modes(einfach_boeen, RAW), changes=changes))
    assert len(_trip_msg(fx, fm=modes(RAW), changes=changes).events) == 2
    assert gust_einfach in _rows(tg_einfach) and gust_roh not in _rows(tg_einfach)
    assert gust_roh in _rows(tg_roh) and gust_einfach not in _rows(tg_roh)


def test_f004_kanaltrennung_mail_und_telegram_folgen_je_ihrem_eigenen_modus_bei_boeen(monkeypatch):
    """F004: Boeen sind in Klartext ROH (``31``) und EINFACH (Stufenwort) verschieden --
    damit beweist DIESE Metrik (Gewitter ist es nicht), dass Mail und Telegram je dem
    Modus des EIGENEN Kanals folgen, in beide Richtungen."""
    from app.trip import Stage, Trip, Waypoint
    from services.notification_service import NotificationService
    from tests.helpers.telegram_empfaenger import mit_profil_chat
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    fx = _load("boeen_stufe_statt_schwelle.json")

    def lauf(email_mode: str, telegram_mode: str):
        mit = aufzeichner_installieren(monkeypatch)
        settings = _settings()
        uid = mit_profil_chat(_user("f004"), settings)
        tid = f"trip-1737-{uuid.uuid4().hex[:6]}"
        stage = Stage(
            id="T1", name="Tag 1", date=datetime(2026, 5, 1).date(),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
        )
        trip = Trip(
            id=tid, name="Boeen-Trip", stages=[stage], official_warnings=None, corridors=[],
            display_config=UnifiedWeatherDisplayConfig(
                trip_id=tid, metrics=[MetricConfig(metric_id="gust", enabled=True)],
                per_channel_layouts={
                    "email": [MetricConfig(metric_id="gust", enabled=True, format_mode=email_mode,
                                           use_friendly_format=email_mode != "raw")],
                    "telegram": [MetricConfig(metric_id="gust", enabled=True,
                                              format_mode=telegram_mode,
                                              use_friendly_format=telegram_mode != "raw")],
                },
            ),
        )
        NotificationService(settings, uid).send_deviation_alert(
            trip=trip, weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
            effective_channels={"email", "telegram"},
            anchor_weather=[_segment_data(fx, fx["anchor"])],
        )
        mails, tgs = mit.sendungen("email"), mit.sendungen("telegram")
        assert len(mails) == 1 and len(tgs) == 1, f"Vorbedingung: je Kanal eine Sendung ({mit!r})"
        return _html_rows(mails[0]["body"]), _rows(tgs[0]["body"])

    roh = _expected(fx, fx["angezeigt_utc_stunden"], "gust", "gust_kmh", "raw")
    einfach = _expected(fx, fx["angezeigt_utc_stunden"], "gust", "gust_kmh", "simplified")
    assert roh != einfach, "Vorbedingung: Boeen sehen in ROH und EINFACH verschieden aus"

    mail_a, tg_a = lauf("raw", "simplified")
    assert tg_a == einfach, "Telegram EINFACH, obwohl die Mail ROH ist"
    assert [(r["time"], r["text"]) for r in mail_a] == roh

    mail_b, tg_b = lauf("simplified", "raw")
    assert tg_b == roh, "Telegram ROH, obwohl die Mail EINFACH ist"
    assert mail_b and mail_b[0]["time"] == "14:00"
