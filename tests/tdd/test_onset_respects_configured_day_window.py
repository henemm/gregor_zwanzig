"""Issue #1468 — Der Beginn-Alarm rechnet mit dem TRIP-EIGENEN Tagesfenster.

SPEC: docs/specs/modules/feat_1468_onset_verschiebung_alarm.md (E2, AC-4)

GEMESSENER IST-STAND VOR DIESER AENDERUNG (2026-08-18):
`compute_basis_metrics()` nahm Zeitzone und Tagesfenster bereits an, aber die
Trip-Konfiguration erreichte sie nicht. `SegmentWeatherService.
_aggregate_for_segment()` reichte nur die Zeitzone durch; das Fenster fiel
still auf den Default 4-19 (`day_window.resolve_configured_window`). Der
Segment-Vorschnitt faengt das NICHT ab: die Etappen-Grenzen folgen den
GEHZEITEN, nicht dem Fenster — das Fenster erreichte `trip_segments.py` an
genau einer Stelle (:266-282) und dort nur das ENDE des ZIEL-Segments (#1584).

TRAEGER IST DAS SEGMENT, nicht die Aufrufkette: `TripSegment` fuehrt
`day_window_start_hour`/`_end_hour`, gesetzt in
`trip_segments.convert_trip_to_segments()` aus `trip.report_config`. Grund:
Briefing-/Anker-Pfad und Alarm-Pfad benutzen DIESELBEN Segmente — damit
koennen die beiden Seiten des Vergleichs gar nicht mit verschiedenen Fenstern
rechnen. Ein Alarm, der allein aus der Fensterwahl entsteht, ist strukturell
ausgeschlossen statt an jeder Aufrufstelle per Disziplin (bewacht in
test_onset_anchor_fresh_window_symmetry.py).

Folge fuer jeden Trip mit abweichendem Fenster — und das ist ein echtes
Bedienelement (`shared/weather-metrics-tab/DayWindowCard.svelte`,
`internal/handler/trip.go:316`):

* WEITERES Fenster (3-21): das Briefing nennt einen Beginn um 03:00, die
  Alarm-Vergleichsbasis sieht ihn nicht und nennt fruehestens 04:00.
* ENGERES Fenster (8-16): das Briefing nennt fruehestens 08:00, die
  Alarm-Basis rechnet ab 04:00 und fuehrt eine fruehere Stunde.

Beides verletzt E2/AC-4 woertlich: *"der Alarm bezieht sich auf exakt die
Zahl, die der Nutzer im Briefing liest"*. Der Nutzer bekaeme einen Alarm
ueber eine Verschiebung, die in seinem Briefing nie stand.

PRUEFORT = WIRKORT: geprueft wird an `_aggregate_for_segment()` — genau der
Methode, der die Trip-Konfiguration heute fehlt —, und die Erwartung ist
die GLEICHHEIT mit der Stunde im gerenderten Briefing aus DERSELBEN Fixture
(Muster AC-4/#1493 AC-9), nicht eine im Test getippte Zahl.

Die Onset-Zahl wird hier WIRKLICH GERECHNET, nicht als fertiger Wert ins
Aggregat gesetzt: `_aggregate_for_segment()` faehrt intern
`compute_basis_metrics()`, und das Briefing rendert aus GENAU diesem
Aggregat. Waere die Zahl gesetzt, koennte der Unterschied "Briefing 03:00 /
Alarmbasis 05:00", mit dem dieser Test vor der Aenderung rot war, gar nicht
entstehen. (Das ist dieselbe Blindstelle, die die Mutations-Gegenprobe an
den AC-Tests aufgedeckt hat -- s. test_onset_computation_sources.py.)

Kein Mock (CLAUDE.md, Kern-Schicht): Gewitterstufen entstehen ueber die
ECHTE Fusion aus CAPE-Rohwerten. Pfadregel #1409: Prueling relativ zu
DIESER Datei aufgeloest.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, ThunderLevel, TripReportConfig, TripSegment,
)  # TripReportConfig: nur noch fuer das gerenderte Briefing (report_config=)
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.segment_weather import SegmentWeatherService  # noqa: E402

TAG = date(2026, 8, 20)
# Island: ganzjaehrig UTC+0, keine Sommerzeit -> die Stundenzahl der Fixture
# IST die Ortszeit-Stunde. Damit haengt keine Erwartung an der Systemzone.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
# Alpen-Koordinate + Modell fuer die ECHTE Gewitter-Fusion.
ALPEN_LAT, ALPEN_LON, MODELL = 47.0, 12.0, "icon_d2"
ISLAND_TZ = ZoneInfo("Atlantic/Reykjavik")

# Drei Gewitterstunden, so gewaehlt, dass JEDES der drei Fenster eine ANDERE
# als erste sieht -- sonst waeren die Faelle nicht unterscheidbar:
#   Fenster 3-21 (weiter)  -> 03:00
#   Fenster 4-19 (Default) -> 05:00
#   Fenster 8-16 (enger)   -> 12:00
GEWITTERSTUNDEN = {3: 400.0, 5: 400.0, 12: 800.0}


def _dp(stunde: int, cape: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TAG.year, TAG.month, TAG.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=16.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=5.0,
    )


def _tagesreihe() -> list[ForecastDataPoint]:
    punkte = [_dp(h, GEWITTERSTUNDEN.get(h, 100.0)) for h in range(24)]
    region = thunder_region_for(ALPEN_LAT, ALPEN_LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(MODELL, region),
                         lpi_thresholds_jkg(region))
    return punkte


def _reihe(punkte) -> NormalizedTimeseries:
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=list(punkte),
    )


def _ganztags_segment(start: int | None = None, ende: int | None = None) -> TripSegment:
    """Segment ueber den vollen Tag, mit dem Auswertungsfenster der Tour.

    Voller Tag, damit der Segment-Vorschnitt in `_aggregate_for_segment`
    nichts wegnimmt -- sonst liessen sich Fenster-Wirkung und
    Vorschnitt-Wirkung nicht auseinanderhalten.
    """
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=100.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=ISLAND_LAT + 0.1, lon=ISLAND_LON + 0.1,
                           elevation_m=200.0, distance_from_start_km=8.0),
        start_time=datetime(TAG.year, TAG.month, TAG.day, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(TAG.year, TAG.month, TAG.day, 23, 59, tzinfo=timezone.utc),
        duration_hours=24.0, distance_km=8.0, ascent_m=300.0, descent_m=300.0,
        day_window_start_hour=start, day_window_end_hour=ende,
    )


def _alarmbasis(punkte, rc: TripReportConfig | None):
    """Das Tages-Aggregat ueber den PRODUKTIVEN Trip-Weg.

    Das Fenster kommt vom SEGMENT -- genau so, wie
    `trip_segments.convert_trip_to_segments()` es aus `trip.report_config`
    setzt. Der Test baut das Segment mit denselben Werten, statt eine zweite
    Uebergabeform zu erfinden.
    """
    from providers.base import get_provider

    dienst = SegmentWeatherService(get_provider("openmeteo"))
    return dienst._aggregate_for_segment(
        _segment_fuer(rc), _reihe(punkte),
        fetched_at=datetime.now(timezone.utc),
    ).aggregated


def _segment_fuer(rc: TripReportConfig | None) -> TripSegment:
    """Das Segment, das `convert_trip_to_segments()` fuer diese
    Trip-Konfiguration bauen wuerde -- unaufgeloest weitergereicht, die
    Aufloesung gehoert an den Auswertungsort."""
    return _ganztags_segment(
        getattr(rc, "day_window_start_hour", None),
        getattr(rc, "day_window_end_hour", None),
    )


def _briefing_stunde(aggregat, punkte, report_config: TripReportConfig | None) -> int:
    """Die Gewitter-Beginnstunde, wie sie IM BRIEFING steht."""
    segment = SegmentWeatherData(
        segment=_segment_fuer(report_config), timeseries=_reihe(punkte),
        aggregated=aggregat, fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )
    bericht = TripReportFormatter().format_email(
        [segment], "Fenster-Trip", "evening",
        display_config=build_default_display_config(), tz=ISLAND_TZ,
        stage_name="Etappe A", report_config=report_config,
    )
    zeilen = [ln for ln in bericht.email_plain.splitlines() if "Gewitter" in ln]
    treffer = [m for ln in zeilen for m in re.findall(r"ab (\d{2}):00", ln)]
    assert len(treffer) == 1, (
        "Vorbedingung: erwartet GENAU EINE Gewitter-Beginn-Angabe im "
        f"Briefing, gefunden: {zeilen!r}"
    )
    return int(treffer[0])


def _config(start: int | None, ende: int | None) -> TripReportConfig:
    return TripReportConfig(
        trip_id="fenster-trip",
        day_window_start_hour=start, day_window_end_hour=ende,
    )


def test_fixture_traegt_in_jedem_fenster_eine_andere_erste_gewitterstunde():
    """Vakuum-Schutz: ohne diese Vorbedingung waeren die drei Faelle unten
    nicht unterscheidbar und ein Test, der das Fenster ignoriert, bliebe in
    allen dreien zufaellig gruen."""
    stufen = {p.ts.hour: p.thunder_level for p in _tagesreihe()}
    for stunde in GEWITTERSTUNDEN:
        assert stufen[stunde] not in (None, ThunderLevel.NONE), (
            f"Fixture: {stunde:02d}:00 muss ein Gewitter tragen: {stufen[stunde]!r}"
        )
    ohne = [h for h in range(24) if h not in GEWITTERSTUNDEN]
    assert all(stufen[h] in (None, ThunderLevel.NONE) for h in ohne), (
        "Fixture: ausserhalb der drei gewaehlten Stunden darf kein Gewitter "
        f"liegen: { {h: stufen[h] for h in ohne if stufen[h] not in (None, ThunderLevel.NONE)} }"
    )


@pytest.mark.parametrize("start,ende,erwartet,fall", [
    (3, 21, 3, "weiteres Fenster als der Default"),
    (8, 16, 12, "engeres Fenster als der Default"),
])
def test_alarmbasis_nennt_dieselbe_stunde_wie_das_briefing(start, ende, erwartet, fall):
    """AC-4 mit ABWEICHENDEM Fenster: Briefing-Stunde == Summary-Feld.

    ROT vor der Aenderung: das Segment trug kein Fenster,
    `_aggregate_for_segment()` rechnete mit dem Default 4-19 und lieferte in
    beiden Faellen 05:00 — waehrend das Briefing 03:00 bzw. 12:00 zeigt.
    """
    punkte = _tagesreihe()
    rc = _config(start, ende)
    aggregat = _alarmbasis(punkte, rc)
    briefing = _briefing_stunde(aggregat, punkte, rc)

    assert briefing == erwartet, (
        f"Vorbedingung ({fall}): das Briefing muss mit Fenster {start}-{ende} "
        f"den Beginn {erwartet:02d}:00 nennen, nennt aber {briefing:02d}:00 — "
        "dann prueft der Vergleich unten das Falsche."
    )
    onset = aggregat.thunder_onset_utc
    assert onset is not None, (
        f"({fall}) Die Alarm-Vergleichsbasis fuehrt keinen Gewitterbeginn, "
        f"obwohl das Briefing ab {briefing:02d}:00 einen zeigt."
    )
    alarm = onset.replace(tzinfo=timezone.utc).astimezone(ISLAND_TZ).hour
    assert alarm == briefing, (
        f"({fall}, Fenster {start}-{ende}): Briefing zeigt {briefing:02d}:00, "
        f"die Alarm-Vergleichsbasis rechnet mit {alarm:02d}:00 — der Alarm "
        "meldete eine Verschiebung, die im Briefing nie stand."
    )


@pytest.mark.parametrize("rc,fall", [
    (None, "gar keine Konfiguration"),
    (_config(None, None), "Konfiguration ohne Fensterwerte (Alt-Trip)"),
    (_config(9, 9), "ungueltiges Fenster start == end"),
])
def test_ohne_gueltige_konfiguration_bleibt_es_beim_default_fenster(rc, fall):
    """Bestandsverhalten: ohne gueltige Angabe gilt weiterhin 4-19, also
    05:00. `start == end` bleibt ungueltig und faellt ueber
    `resolve_configured_window()` auf den Default zurueck (#1361/#1372 S1b)."""
    onset = _alarmbasis(_tagesreihe(), rc).thunder_onset_utc
    assert onset is not None, f"({fall}) kein Beginn berechnet"
    alarm = onset.replace(tzinfo=timezone.utc).astimezone(ISLAND_TZ).hour
    assert alarm == 5, (
        f"({fall}): erwartet den Default 4-19 und damit 05:00, "
        f"bekommen {alarm:02d}:00."
    )


def test_fenster_ueber_mitternacht_ist_gueltig_und_wird_nicht_verworfen():
    """`start > end` ist seit dem PO-Entscheid 2026-07-25 ein GUELTIGES
    Fenster ueber Mitternacht — es darf nicht als ungueltig auf den Default
    zurueckfallen.

    Fenster 21-4 enthaelt von den drei Gewitterstunden nur die 03:00; ein
    Rueckfall auf den Default 4-19 liefe auf 05:00 hinaus, ein Verwerfen der
    Nachtstunden auf gar keinen Beginn. Beides waere hier sichtbar.
    """
    onset = _alarmbasis(_tagesreihe(), _config(21, 4)).thunder_onset_utc
    assert onset is not None, (
        "Fenster 21-4 enthaelt die Gewitterstunde 03:00 — es darf nicht "
        "ohne Beginn enden."
    )
    alarm = onset.replace(tzinfo=timezone.utc).astimezone(ISLAND_TZ).hour
    assert alarm == 3, (
        f"Fenster ueber Mitternacht (21-4): erwartet 03:00, bekommen "
        f"{alarm:02d}:00 — 05:00 hiesse Rueckfall auf den Default."
    )
