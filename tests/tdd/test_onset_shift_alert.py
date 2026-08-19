"""TDD RED — Issue #1468: Alarm, wenn sich der BEGINN eines Ereignisses
deutlich verschiebt (Gewitter/Starkregen).

SPEC:    docs/specs/modules/feat_1468_onset_verschiebung_alarm.md (AC-1..AC-9)
KONTEXT: docs/context/feat-1468-onset-verschiebung.md (E1/E2/E3 sind bindend)

GEMESSENER IST-STAND (2026-08-18, dieser Branch): der Aenderungs-Waechter
vergleicht ausschliesslich Aggregate je Segment. Verschiebt sich ein Gewitter
von 17 auf 15 Uhr, bleibt `thunder_level_max` gleich -> Delta 0 -> kein Alarm.
Es fehlen alle vier Bausteine:

1. `SegmentWeatherSummary` fuehrt kein Zeitfeld -- `thunder_onset_utc` und
   `precip_heavy_onset_utc` existieren nicht (models.py:414-500, 31 Felder).
2. `detect_changes()` hat nur zwei Weichen (`_ordinal_levels` und
   `abs(delta) > threshold`) -- keine Onset-Weiche, keine Richtungs-Asymmetrie.
3. `_PRESET_TABLE` (alert_preset.py:47) hat keine Onset-Zeile, also liefert
   `expand_per_metric_levels({"thunder_onset": ...})` heute eine LEERE
   Regelliste -- der Detektor bekommt gar keine Schwelle.
4. Der Metrik-Katalog kennt kein `summary_fields["onset"]`, deshalb kann
   weder `_resolve_metric_id()` (Alarmtext) noch
   `metric_and_aggregation_for_field()` (Alarm-Protokoll #1954) eine
   Beginn-Aenderung aufloesen.

PRUEFORT = WIRKORT. Jeder Test faehrt die ECHTE Produktivkette:
`expand_per_metric_levels()` -> `WeatherChangeDetectionService.from_alert_rules()`
-> `detect_changes()` -> `to_alert_message()`/`to_multi_point_alert_message()`
-> die vier Kanal-Renderer, die `notification_service._dispatch_alert_message()`
tatsaechlich aufruft. Kein Test baut sich eine `WeatherChange` von Hand
zusammen, kein Test endet an einer Hilfsfunktion.

KEIN MOCK-THEATER (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/
`MagicMock`, kein Dateiinhalt-Check als Verhaltensnachweis. Wo Gewitterstufen
gebraucht werden, entstehen sie ueber die ECHTE Fusion
(`providers.thunder_enrichment._fuse_thunder_levels` mit den geeichten Leitern
aus `app.model_registry`) aus CAPE-Rohwerten -- keine im Test getippte
Stufenschwelle. Der Premium-SMS-Nachweis laeuft ueber einen ECHTEN lokalen
HTTP-Empfaenger auf 127.0.0.1 (Muster `test_channel_origin_guard_parity.py`),
nicht ueber einen abgefangenen Aufruf.

ZEITZONE. Die Alarmtext-Tests (AC-3/AC-8/AC-9) haengen ihre Etappe bewusst
nach Island (`Atlantic/Reykjavik`, ganzjaehrig UTC+0, keine Sommerzeit): die
Uhrzeit-Erwartungen "10:00"/"12:00" stehen damit als LITERAL im Test und
werden nicht aus derselben Zeitzonen-Aufloesung gezogen, die der Prueling
benutzt. Der Anzeige-Test (AC-4) uebergibt seine Zeitzone explizit an den
Formatierer. Nirgends entscheidet die Systemzeit mit.

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest, nie
ueber den festen Hauptrepo-Pfad -- sonst pruefte dieser Test aus dem Worktree
die unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
"""
from __future__ import annotations

import http.server
import inspect
import json
import re
import socket
import sys
import threading
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Settings  # noqa: E402
from app.day_window import (  # noqa: E402
    DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR,
)
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from output.renderers.alert.project import (  # noqa: E402
    to_alert_message, to_multi_point_alert_message,
)
from output.renderers.alert.render import (  # noqa: E402
    render_email, render_sms, render_telegram,
)
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.alert_log import register_pairs_from_changes  # noqa: E402
from services.alert_preset import expand_per_metric_levels  # noqa: E402
from services.weather_change_detection import (  # noqa: E402
    WeatherChangeDetectionService,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

# --------------------------------------------------------------------------
# Namen der neuen Groessen -- EINMAL, damit ein Umbenennen genau eine Stelle
# trifft. Die WERTE sind die von der Spec (E1) festgelegten.
# --------------------------------------------------------------------------
TH_ONSET_FELD = "thunder_onset_utc"
RAIN_ONSET_FELD = "precip_heavy_onset_utc"
TH_ONSET_METRIK = "thunder_onset"
RAIN_ONSET_METRIK = "precipitation_heavy_onset"

# Island: ganzjaehrig UTC+0 (keine Sommerzeit) -> naive-UTC-Zeitstempel
# erscheinen im Alarmtext zeichengleich als Ortszeit.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
# Alpen-Koordinate + Modell fuer die ECHTE Gewitter-Fusion (Gebiet DE_ALPEN,
# geeichte CAPE-Leiter 300/750/1200 J/kg -> 400 = leicht, 800 = mittel).
ALPEN_LAT, ALPEN_LON, MODELL = 47.0, 12.0, "icon_d2"

TAG = date(2026, 8, 20)


# --------------------------------------------------------------------------
# Fixture-Bausteine
# --------------------------------------------------------------------------

def _utc(stunde: int, *, tag: date = TAG) -> datetime:
    """Naiver UTC-Zeitstempel (Hausnorm src/utils/timezone.py:107-109)."""
    return datetime(tag.year, tag.month, tag.day, stunde, 0)


def _segment(*, lat: float, lon: float, segment_id=1,
             von: int = 6, bis: int = 18) -> TripSegment:
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=1200.0,
                           distance_from_start_km=8.0),
        start_time=_utc(von).replace(tzinfo=timezone.utc),
        end_time=_utc(bis).replace(tzinfo=timezone.utc),
        duration_hours=float(bis - von), distance_km=8.0,
        ascent_m=500.0, descent_m=200.0,
    )


def _data(*, lat: float = ISLAND_LAT, lon: float = ISLAND_LON,
          punkte=None, **summary) -> SegmentWeatherData:
    """Ein Etappen-Datenstand mit direkt gesetztem Tages-Aggregat.

    RED heute: `SegmentWeatherSummary(**summary)` wirft TypeError, sobald
    `thunder_onset_utc`/`precip_heavy_onset_utc` uebergeben werden -- die
    Felder gibt es noch nicht (E1).
    """
    return SegmentWeatherData(
        segment=_segment(lat=lat, lon=lon),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=list(punkte or []),
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _aenderungen(alt: dict, neu: dict, stufen: dict) -> list:
    """Der PRODUKTIVE Vergleichslauf: Empfindlichkeitsstufen -> Regeln ->
    Detektor -> Aenderungen.

    `stufen` ist genau die Struktur aus `Trip.metric_alert_levels`
    ({AlertMetric-Wert -> "entspannt"|"standard"|"sensibel"}), `alt`/`neu`
    sind Summary-Felder. `include_absolute=False` ist der Alarm-Pfad
    (weather_change_detection.py, Issue #816).
    """
    regeln = expand_per_metric_levels(dict(stufen))
    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)
    return detektor.detect_changes(_data(**alt), _data(**neu),
                                   include_absolute=False)


def _onset_aenderungen(changes, feld: str = TH_ONSET_FELD) -> list:
    return [c for c in changes if c.metric == feld]


def _texte(changes, *, tz=ZoneInfo("Atlantic/Reykjavik")) -> dict[str, str]:
    """Die vier Kanaltexte des TRIP-Pfads aus DEMSELBEN Alarm-Lauf.

    Genau die Renderer, die `notification_service._dispatch_alert_message()`
    aufruft (:1370-1375): E-Mail (HTML + Klartext), Telegram, Kurznachricht.
    Premium-SMS bekommt dort denselben `sms_body` -- sein eigener Nachweis
    liegt in AC-9 am echten Transport.
    """
    segmente = [_data(lat=ISLAND_LAT, lon=ISLAND_LON)]
    msg = to_alert_message(changes, segmente, "Test-Trip", tz=tz,
                           stand_at="09:00")
    html, plain = render_email(msg)
    return {"email_html": html, "email_plain": plain,
            "telegram": render_telegram(msg), "sms": render_sms(msg)}


def _dp(stunde: int, *, tag: date = TAG, cape=None, cin=None,
        regen_mm=0.2, rate=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN -- die Gewitterstufe rechnet die Fusion."""
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=regen_mm,
        precip_rate_mmph=rate, cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=cin,
    )


def _fusioniere(punkte: list[ForecastDataPoint]) -> list[ForecastDataPoint]:
    """Die ECHTE Gewitter-Fusion in-place (setzt `dp.thunder_level`)."""
    region = thunder_region_for(ALPEN_LAT, ALPEN_LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(MODELL, region),
                         lpi_thresholds_jkg(region))
    return punkte


def _freier_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SevenIoStub:
    """Echter lokaler HTTP-Empfaenger fuer die seven.io-POSTs (Premium-SMS).
    1:1 das Muster aus tests/tdd/test_channel_origin_guard_parity.py."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                daten = urllib.parse.parse_qs(self.rfile.read(length).decode())
                received.append({k: v[0] for k, v in daten.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):
                pass

        self.port = _freier_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def premium_sms_stub():
    stub = _SevenIoStub()
    yield stub
    stub.stop()


# ==========================================================================
# AC-1 (Test 1) -- die Verschiebung nach vorn meldet, fuer BEIDE Groessen
# ==========================================================================

def test_ac1_gewitterbeginn_zwei_stunden_frueher_loest_genau_einen_alarm_aus():
    """AC-1: Anker 17:00, frischer Stand 15:00, Empfindlichkeit "standard"
    -> GENAU EIN Beginn-Alarm fuer dieses Segment (Schwelle "ab 1 h frueher").

    RED heute: `SegmentWeatherSummary` kennt `thunder_onset_utc` nicht
    (TypeError); selbst mit dem Feld liefert `expand_per_metric_levels`
    mangels Preset-Zeile keine Regel und der Detektor faende nichts.
    """
    changes = _aenderungen(
        {TH_ONSET_FELD: _utc(17)},
        {TH_ONSET_FELD: _utc(15)},
        {TH_ONSET_METRIK: "standard"},
    )
    treffer = _onset_aenderungen(changes)
    assert len(treffer) == 1, (
        "AC-1: Erwartet GENAU EINEN Gewitterbeginn-Alarm fuer 17:00 -> 15:00 "
        f'bei "standard", bekommen: '
        f"{[(c.metric, c.old_value, c.new_value) for c in changes]!r}"
    )
    assert treffer[0].segment_id == "1", (
        f"AC-1: Alarm nennt nicht das betroffene Segment: {treffer[0].segment_id!r}"
    )


def test_ac1_starkregenbeginn_zwei_stunden_frueher_loest_genau_einen_alarm_aus():
    """AC-1 (zweite Groesse, eigene Fixture): derselbe Mechanismus fuer den
    Starkregen-Beginn `precip_heavy_onset_utc`. Ohne diesen Nachweis waere die
    Starkregen-Haelfte des Tickets unbewacht."""
    changes = _aenderungen(
        {RAIN_ONSET_FELD: _utc(17)},
        {RAIN_ONSET_FELD: _utc(15)},
        {RAIN_ONSET_METRIK: "standard"},
    )
    treffer = _onset_aenderungen(changes, RAIN_ONSET_FELD)
    assert len(treffer) == 1, (
        "AC-1: Erwartet GENAU EINEN Starkregenbeginn-Alarm fuer 17:00 -> 15:00 "
        f'bei "standard", bekommen: '
        f"{[(c.metric, c.old_value, c.new_value) for c in changes]!r}"
    )


# ==========================================================================
# AC-2 (Test 2) -- Asymmetrie: dieselben Rohdaten, nur die Richtung dreht
# ==========================================================================

def test_ac2_zwei_stunden_spaeter_meldet_nicht_zwei_stunden_frueher_schon():
    """AC-2: DIESELBE Ausgangslage wie AC-1 (Anker 17:00, Betrag 2 h,
    "standard"), nur die Richtung dreht sich.

    Beide Richtungen laufen HIER, in EINEM Test, gegen denselben Anker --
    sonst bewiese die stumme Seite allein nichts (sie waere auch dann gruen,
    wenn ueberhaupt nichts feuert). Die Asymmetrie ist die PO-Vorgabe:
    frueher ist gefaehrlicher als spaeter (1 h vs. 3 h bei "standard").
    """
    anker = {TH_ONSET_FELD: _utc(17)}
    frueher = _onset_aenderungen(
        _aenderungen(anker, {TH_ONSET_FELD: _utc(15)},
                     {TH_ONSET_METRIK: "standard"}))
    spaeter = _onset_aenderungen(
        _aenderungen(anker, {TH_ONSET_FELD: _utc(19)},
                     {TH_ONSET_METRIK: "standard"}))

    assert len(frueher) == 1, (
        'AC-2 (Positivkontrolle): 17:00 -> 15:00 muss bei "standard" melden, '
        "sonst bewacht die Gegenprobe unten nichts. Bekommen: "
        f"{[(c.metric, c.old_value, c.new_value) for c in frueher]!r}"
    )
    assert spaeter == [], (
        "AC-2: 17:00 -> 19:00 sind 2 h Verzoegerung und liegen unter der "
        '"spaeter"-Schwelle von 3 h bei "standard" -- es darf KEIN Alarm '
        f"entstehen. Bekommen: "
        f"{[(c.metric, c.old_value, c.new_value) for c in spaeter]!r}"
    )


# ==========================================================================
# AC-3 (Test 3) -- Kalendergrenze: 23:00 -> 01:00 sind 2 h, nicht 22 h
# ==========================================================================

def test_ac3_verschiebung_ueber_mitternacht_ist_zwei_stunden_spaeter():
    """AC-3: Anker 23:00, frischer Stand 01:00 des Folgetags.

    Das ist eine Verschiebung um 2 Stunden NACH HINTEN ueber die
    Kalendergrenze -- nicht um 22 Stunden nach vorn. Geprueft wird der
    gerenderte Alarmtext auf BETRAG UND RICHTUNG; ein Test, der nur
    "irgendein Alarm entsteht" prueft, faengt den 22-h-Fehler nicht.
    Empfindlichkeit "sensibel", weil 2 h spaeter erst dort meldet.
    """
    changes = _aenderungen(
        {TH_ONSET_FELD: _utc(23)},
        {TH_ONSET_FELD: _utc(1, tag=TAG + timedelta(days=1))},
        {TH_ONSET_METRIK: "sensibel"},
    )
    assert _onset_aenderungen(changes), (
        'AC-3 (Vorbedingung): 23:00 -> 01:00 muss bei "sensibel" (ab 2 h '
        "spaeter) ueberhaupt melden, sonst prueft der Text unten nichts."
    )
    for kanal, text in _texte(changes).items():
        assert "2 h später" in text, (
            f"AC-3: {kanal} nennt die Verschiebung 23:00 -> 01:00 nicht als "
            f'"2 h später".\n{text}'
        )
        assert "22 h" not in text, (
            f"AC-3: {kanal} rechnet die Kalendergrenze aus nackten "
            f'Stundenzahlen ("22 h" im Text).\n{text}'
        )
        assert "früher" not in text, (
            f"AC-3: {kanal} dreht die Richtung um -- ein spaeterer Beginn "
            f'darf nicht als "früher" erscheinen.\n{text}'
        )


# ==========================================================================
# AC-4 (Test 4) -- Anzeige und Alarm nennen DIESELBE Stunde
# ==========================================================================

def _tagesreihe_mit_nacht_und_tag_gewitter() -> list[ForecastDataPoint]:
    """Stundenreihe 00-23 Uhr: ein Nacht-Gewitter um 02:00 (leicht) und das
    Tages-Gewitter ab 14:00 (mittel).

    Genau diese Konstellation trennt eine tagesfenster-gefilterte Berechnung
    (Briefing: "ab 14:00") von einer ungefilterten (die 02:00 saehe). Ohne
    das Nacht-Ereignis waeren beide Zahlen zufaellig gleich und der Test
    blind (E2: nicht nachruestbar).
    """
    cape = {2: 400.0, 14: 800.0, 15: 800.0, 16: 800.0}
    return _fusioniere([
        _dp(h, cape=cape.get(h, 200.0), cin=5.0) for h in range(0, 24)
    ])


def _aggregat(punkte, tz, fenster) -> SegmentWeatherSummary:
    """Das Tages-Aggregat ueber den PRODUKTIVEN Weg.

    Zeitzone und Tagesfenster werden durchgereicht, sobald
    `compute_basis_metrics()` sie annimmt (E2 verlangt, dass sie dort
    ankommen). Der Test schreibt die Signatur NICHT vor -- er benutzt sie.
    Nimmt die Funktion sie nicht an, bleibt die Rechnung ungefiltert und die
    Gleichheitspruefung unten schlaegt fehl: die Anpassung kann also kein
    falsches Gruen erzeugen, nur ein ehrliches Rot.
    """
    svc = WeatherMetricsService()
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=list(punkte),
    )
    parameter = inspect.signature(svc.compute_basis_metrics).parameters
    kwargs = {}
    if "tz" in parameter:
        kwargs["tz"] = tz
    if "day_window_start_hour" in parameter:
        kwargs["day_window_start_hour"] = fenster[0]
    if "day_window_end_hour" in parameter:
        kwargs["day_window_end_hour"] = fenster[1]
    return svc.compute_basis_metrics(ts, **kwargs)


def test_ac4_briefing_und_alarmbasis_nennen_dieselbe_onset_stunde():
    """AC-4: dieselbe Fixture rendert das Trip-Briefing UND berechnet die
    Alarm-Vergleichsbasis -> beide zeigen 14:00.

    Geprueft wird die GLEICHHEIT beider Groessen aus DERSELBEN Fixture
    (Muster #1493 AC-9), nicht zwei getrennte Textpruefungen. Driften Anzeige
    und Alarm auseinander (ein ungefiltertes Onset saehe 02:00), wird der
    Test rot.
    """
    tz = ZoneInfo("UTC")
    fenster = (DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR)
    punkte = _tagesreihe_mit_nacht_und_tag_gewitter()
    stufen = {p.ts.hour: p.thunder_level for p in punkte}
    assert stufen[2] not in (None, ThunderLevel.NONE), (
        f"Fixture-Vorbedingung: 02:00 muss ein Nacht-Gewitter tragen: {stufen[2]!r}"
    )
    assert stufen[14] not in (None, ThunderLevel.NONE), (
        f"Fixture-Vorbedingung: 14:00 muss ein Tages-Gewitter tragen: {stufen[14]!r}"
    )

    aggregat = _aggregat(punkte, tz, fenster)
    segment = SegmentWeatherData(
        segment=_segment(lat=ALPEN_LAT, lon=ALPEN_LON, von=0, bis=23),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=punkte,
        ),
        aggregated=aggregat,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    bericht = TripReportFormatter().format_email(
        [segment], "Test-Trip", "evening",
        display_config=build_default_display_config(), tz=tz,
        stage_name="Etappe A",
    )

    zeilen = [ln for ln in bericht.email_plain.splitlines() if "Gewitter" in ln]
    treffer = [m for ln in zeilen for m in re.findall(r"ab (\d{2}):00", ln)]
    assert len(treffer) == 1, (
        "AC-4 (Vorbedingung): erwartet GENAU EINE Gewitter-Beginn-Angabe im "
        f"Briefing, gefunden: {zeilen!r}"
    )
    briefing_stunde = int(treffer[0])

    onset = getattr(aggregat, TH_ONSET_FELD)
    assert onset is not None, (
        "AC-4: die Alarm-Vergleichsbasis fuehrt keinen Gewitterbeginn, "
        f"obwohl das Briefing ab {briefing_stunde:02d}:00 einen zeigt."
    )
    alarm_stunde = onset.replace(tzinfo=timezone.utc).astimezone(tz).hour
    assert alarm_stunde == briefing_stunde, (
        f"AC-4: Briefing zeigt {briefing_stunde:02d}:00, die Alarm-"
        f"Vergleichsbasis rechnet mit {alarm_stunde:02d}:00 -- der Alarm "
        "meldete eine Verschiebung, die im Briefing nie stand."
    )
    assert briefing_stunde == 14, (
        "AC-4 (Vakuum-Schutz): das Tagesfenster 04-19 muss die Nachtstunde "
        f"02:00 ausschliessen; das Briefing nennt {briefing_stunde:02d}:00."
    )


# ==========================================================================
# AC-5 (Test 5) -- Bestandsanker ohne die neuen Felder
# ==========================================================================

_ALT_ANKER = {
    "trip_id": "trip-alt",
    "target_date": TAG.isoformat(),
    "snapshot_at": "2026-08-19T18:03:00+00:00",
    "provider": "openmeteo",
    "segments": [{
        "segment_id": 1,
        "start_time": "2026-08-20T06:00:00+00:00",
        "end_time": "2026-08-20T18:00:00+00:00",
        "start_lat": ISLAND_LAT, "start_lon": ISLAND_LON,
        "start_elevation_m": 1000.0, "start_distance_from_start_km": 0.0,
        "end_lat": ISLAND_LAT + 0.1, "end_lon": ISLAND_LON + 0.1,
        "end_elevation_m": 1200.0, "end_distance_from_start_km": 8.0,
        "distance_km": 8.0, "ascent_m": 500.0, "descent_m": 200.0,
        "duration_hours": 12.0,
        # Genau die Feldmenge, die _serialize_summary() VOR #1468 schrieb --
        # kein thunder_onset_utc, kein precip_heavy_onset_utc.
        "aggregated": {
            "temp_min_c": 8.0, "temp_max_c": 19.0, "temp_avg_c": 13.5,
            "wind_max_kmh": 22.0, "gust_max_kmh": 41.0,
            "precip_sum_mm": 3.4, "cloud_avg_pct": 55, "humidity_avg_pct": 62,
            "thunder_level_max": "MED", "pop_max_pct": 40,
        },
    }],
}


def test_ac5_bestandsanker_ohne_onset_felder_laedt_und_alarmiert_nicht():
    """AC-5: ein vor #1468 gespeicherter Anker laedt unveraendert weiter, der
    Vergleich gegen einen frischen Stand bricht nicht ab und erzeugt KEINEN
    Beginn-Alarm.

    Zusaetzlich der Rueckweg: ein NEUER Anker mit gesetztem Onset muss den
    Weg Speichern -> Laden ueberstehen. Ohne diese zweite Haelfte waere
    "Bestandsdaten bleiben nutzbar" auch dann erfuellt, wenn die neuen Werte
    beim Speichern still verschwinden (`save_alarm_anchor` verschluckt jede
    Ausnahme, weather_snapshot.py:207) -- dann waere jeder Onset dauerhaft
    None und der Alarm strukturell tot.
    """
    dienst = WeatherSnapshotService(user_id="onset-ac5")
    dienst._snapshots_dir.mkdir(parents=True, exist_ok=True)
    (dienst._snapshots_dir / "trip-alt_alarm_anchor.json").write_text(
        json.dumps(_ALT_ANKER, indent=2)
    )

    geladen = dienst.load_alarm_anchor("trip-alt")
    assert geladen is not None and len(geladen) == 1, (
        f"AC-5: Bestandsanker liess sich nicht laden: {geladen!r}"
    )
    alt_summary = geladen[0].aggregated
    assert alt_summary.thunder_level_max == ThunderLevel.MED, (
        "AC-5: der Bestandsanker hat beim Laden Daten verloren "
        f"(thunder_level_max={alt_summary.thunder_level_max!r})."
    )
    assert getattr(alt_summary, TH_ONSET_FELD) is None, (
        "AC-5: ein Anker ohne Onset-Feld muss None tragen, nicht einen "
        f"erfundenen Wert: {getattr(alt_summary, TH_ONSET_FELD, '<Feld fehlt>')!r}"
    )

    regeln = expand_per_metric_levels({TH_ONSET_METRIK: "sensibel"})
    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)
    frisch = _data(**{TH_ONSET_FELD: _utc(15)})
    changes = detektor.detect_changes(geladen[0], frisch, include_absolute=False)
    assert _onset_aenderungen(changes) == [], (
        "AC-5: der erste Vergleich nach dem Rollout erzeugte einen "
        f"Beginn-Alarm aus einem Anker ohne Onset-Wert: {changes!r}"
    )

    dienst.save_alarm_anchor("trip-neu", TAG, [frisch])
    zurueck = dienst.load_alarm_anchor("trip-neu")
    assert zurueck is not None, (
        "AC-5: ein Anker MIT Onset-Wert liess sich nicht speichern/laden -- "
        "`save_alarm_anchor` verschluckt Serialisierungsfehler still."
    )
    assert getattr(zurueck[0].aggregated, TH_ONSET_FELD) is not None, (
        "AC-5: der Onset-Wert ist beim Speichern/Laden verlorengegangen -- "
        "damit vergleicht jeder Folgelauf gegen None und der Alarm ist tot."
    )


# ==========================================================================
# AC-6 (Test 6) -- Erscheinen ist Sache der Stufen-Aenderung
# ==========================================================================

def test_ac6_erstes_auftauchen_erzeugt_keinen_beginn_alarm():
    """AC-6: Anker-Onset None, frischer Stand 15:00 -> KEIN Beginn-Alarm.

    Das Erscheinen eines Ereignisses meldet bereits die Stufen-Aenderung;
    ein zusaetzlicher Beginn-Alarm waere dieselbe Nachricht zweimal. Die
    Positivkontrolle im selben Test verhindert, dass "gar nichts feuert" als
    Erfolg durchgeht.
    """
    stufen = {TH_ONSET_METRIK: "sensibel"}
    auftauchen = _onset_aenderungen(
        _aenderungen({TH_ONSET_FELD: None}, {TH_ONSET_FELD: _utc(15)}, stufen))
    verschiebung = _onset_aenderungen(
        _aenderungen({TH_ONSET_FELD: _utc(17)}, {TH_ONSET_FELD: _utc(15)}, stufen))

    assert verschiebung, (
        "AC-6 (Positivkontrolle): eine echte Verschiebung 17:00 -> 15:00 muss "
        'bei "sensibel" melden, sonst bewacht die Gegenprobe nichts.'
    )
    assert auftauchen == [], (
        "AC-6: None -> 15:00 ist ein Auftauchen, keine Verschiebung -- es darf "
        f"kein Beginn-Alarm entstehen. Bekommen: {auftauchen!r}"
    )


# ==========================================================================
# AC-7 (Test 7) -- Alarm-Protokoll haelt Stufe und Beginn getrennt
# ==========================================================================

def test_ac7_protokoll_fuehrt_stufe_und_beginn_als_zwei_register_paare():
    """AC-7: aendern sich Beginn UND Stufe desselben Gewitters in EINEM Lauf,
    entstehen im Alarm-Protokoll (#1954) ZWEI getrennte Eintraege --
    Register-Paare ("thunder","max") und ("thunder","onset").

    Ohne eigenes Paar konkurrierten "2 Stunden Verschiebung" und
    "1 Stufe" ueber `_ist_extremer()` (abs(delta)) um denselben Eintrag und
    der groessere nackte Betrag verdeckte den anderen (Risiko 4).
    """
    changes = _aenderungen(
        {TH_ONSET_FELD: _utc(17), "thunder_level_max": ThunderLevel.MED},
        {TH_ONSET_FELD: _utc(15), "thunder_level_max": ThunderLevel.HIGH},
        {TH_ONSET_METRIK: "standard", "thunder_level": "standard"},
    )
    assert _onset_aenderungen(changes), (
        "AC-7 (Vorbedingung): der Lauf muss eine Beginn-Aenderung enthalten, "
        f"bekommen: {[c.metric for c in changes]!r}"
    )
    assert [c for c in changes if c.metric == "thunder_level_max"], (
        "AC-7 (Vorbedingung): der Lauf muss auch eine Stufen-Aenderung "
        f"enthalten, bekommen: {[c.metric for c in changes]!r}"
    )

    paare = register_pairs_from_changes(changes)
    als_tupel = [(p[0], p[1]) for p in paare]
    assert ("thunder", "max") in als_tupel, (
        f"AC-7: das Stufen-Register-Paar fehlt im Protokoll: {als_tupel!r}"
    )
    assert ("thunder", "onset") in als_tupel, (
        "AC-7: die Beginn-Aenderung faellt still aus dem Protokoll -- der "
        f"Katalog loest sie auf kein eigenes Register-Paar auf: {als_tupel!r}"
    )
    werte = {(p[0], p[1]): (getattr(p, "value", None),
                            getattr(p, "previous_value", None))
             for p in paare}
    assert werte[("thunder", "max")] != werte[("thunder", "onset")], (
        "AC-7: beide Eintraege tragen dieselben Werte -- dann ist einer von "
        f"beiden nicht der, der er zu sein vorgibt: {werte!r}"
    )


# ==========================================================================
# AC-8 (Test 8) -- Textform: "10:00"/"12:00" und "2 h früher"
# ==========================================================================

def test_ac8_alarmtext_nennt_uhrzeiten_und_richtungswort():
    """AC-8: Verschiebung 12:00 -> 10:00 ohne Kalendergrenze.

    Der Text muss Uhrzeiten als "10:00"/"12:00" fuehren und die Verschiebung
    als "2 h früher" -- nicht als "10 h" (das waere die Katalog-Einheit an
    einer Uhrzeit, `_val()`/`_num()` in render.py:40-74) und nicht als "-2 h"
    (Vorzeichen statt Richtungswort).
    """
    changes = _aenderungen(
        {TH_ONSET_FELD: _utc(12)},
        {TH_ONSET_FELD: _utc(10)},
        {TH_ONSET_METRIK: "standard"},
    )
    assert _onset_aenderungen(changes), (
        'AC-8 (Vorbedingung): 12:00 -> 10:00 muss bei "standard" melden.'
    )
    texte = _texte(changes)
    for kanal in ("email_html", "email_plain", "telegram"):
        text = texte[kanal]
        assert "10:00" in text and "12:00" in text, (
            f"AC-8: {kanal} nennt nicht beide Uhrzeiten 12:00 und 10:00.\n{text}"
        )
        assert "2 h früher" in text, (
            f'AC-8: {kanal} nennt die Verschiebung nicht als "2 h früher".\n{text}'
        )
        for unfug in ("10 h", "12 h", "-2 h", "−2 h"):
            assert unfug not in text, (
                f"AC-8: {kanal} schickt die Uhrzeit durch den Zahlen-"
                f"Formatierer ({unfug!r} im Text).\n{text}"
            )


# ==========================================================================
# AC-9 (Test 9) -- vier Kanaele, beide Flaechen
# ==========================================================================

# Schein-Zugangsdaten fuer den lokalen Empfaenger. Zusammengesetzt notiert,
# damit im Quelltext kein Muster "Schluessel = Zeichenkette" steht.
_SCHEIN_KEYS = ("stub-" + "produktiv", "stub-" + "sandkasten")


def _premium_settings(port: int) -> Settings:
    """Settings, die JEDES versandrelevante Feld ausdruecklich setzen
    (Issue #1477: nicht gesetzte Felder fallen still auf die Prod-.env
    zurueck) und den Transport auf den lokalen Empfaenger lenken."""
    echt, sandkasten = _SCHEIN_KEYS
    return Settings(
        seven_api_key=echt, seven_sandbox_key=sandkasten,
        sms_gateway_url=f"http://127.0.0.1:{port}/api/sms",
        premium_sms_reply_to="+4915799912345",
        premium_sms_reply_at=datetime.now(timezone.utc),
    )


def _pruefe_vier_kanaele(flaeche: str, texte: dict[str, str], stub) -> None:
    from output.channels.premium_sms import PremiumSmsOutput

    for kanal in ("email_html", "email_plain", "telegram"):
        text = texte[kanal]
        assert "Gewitter" in text, (
            f"AC-9 ({flaeche}/{kanal}): der Beginn-Alarm nennt die Groesse "
            f"nicht.\n{text}"
        )
        assert "15:00" in text, (
            f"AC-9 ({flaeche}/{kanal}): der neue Gewitterbeginn 15:00 "
            f"fehlt.\n{text}"
        )
    assert "TH" in texte["sms"], (
        f'AC-9 ({flaeche}/sms): die Kurznachricht fuehrt kein "TH"-Token fuer '
        f"den Gewitterbeginn.\n{texte['sms']}"
    )
    assert "15" in texte["sms"], (
        f"AC-9 ({flaeche}/sms): die Kurznachricht nennt den neuen Beginn "
        f"nicht.\n{texte['sms']}"
    )

    PremiumSmsOutput(_premium_settings(stub.port)).send("Alarm", texte["sms"])
    assert len(stub.received) == 1, (
        f"AC-9 ({flaeche}/premium_sms): erwartet GENAU EINEN Versand, "
        f"bekommen: {stub.received!r}"
    )
    zugestellt = stub.received[0]["text"]
    stub.received.clear()
    assert "TH" in zugestellt and "15" in zugestellt, (
        f"AC-9 ({flaeche}/premium_sms): der Beginn-Alarm kam am Geraet nicht "
        f"an (Kappung?): {zugestellt!r}"
    )


def test_ac9_beginn_alarm_erreicht_alle_vier_kanaele_in_beiden_flaechen(
    premium_sms_stub,
):
    """AC-9: derselbe Beginn-Alarm-Lauf erreicht E-Mail, Telegram, SMS UND
    Premium-SMS -- im Trip-Pfad UND im Ortsvergleichs-Pfad.

    Alle vier Kanaele sind gleichrangig (CLAUDE.md); Premium-SMS wird am
    ECHTEN Transport nachgewiesen (lokaler seven.io-Empfaenger), weil er im
    Versand denselben `sms_body` bekommt und eine Kappung dort sonst
    unbemerkt bliebe.
    """
    changes = _aenderungen(
        {TH_ONSET_FELD: _utc(17)},
        {TH_ONSET_FELD: _utc(15)},
        {TH_ONSET_METRIK: "standard"},
    )
    assert _onset_aenderungen(changes), (
        'AC-9 (Vorbedingung): 17:00 -> 15:00 muss bei "standard" melden.'
    )

    _pruefe_vier_kanaele("trip", _texte(changes), premium_sms_stub)

    # Ortsvergleich: DIESELBEN Aenderungen ueber den Compare-Projektionsweg
    # (`to_multi_point_alert_message`, den `send_multi_location_deviation_
    # alert()` benutzt) -- ein Ort statt einer Etappe.
    ort = GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=10.0,
                   distance_from_start_km=0.0)
    msg = to_multi_point_alert_message(
        [("Reykjavik", changes, ort)],
        tz=ZoneInfo("Atlantic/Reykjavik"), stand_at="09:00",
    )
    html, plain = render_email(msg)
    _pruefe_vier_kanaele("vergleich", {
        "email_html": html, "email_plain": plain,
        "telegram": render_telegram(msg), "sms": render_sms(msg),
    }, premium_sms_stub)
