"""Issue #1468 — AC-10 fuer den ORTSVERGLEICH: das Vergleichs-Tagesfenster
erreicht die Beginn-Berechnung.

SPEC: docs/specs/modules/feat_1468_onset_verschiebung_alarm.md (E2, AC-10)

WARUM ES DIESE DATEI GIBT (Adversary-Finding F002, 2026-08-19):

Die dedizierte AC-10-Datei `test_onset_respects_configured_day_window.py`
faehrt ausschliesslich den TRIP-Pfad. Der Adversary hat die beiden Zeilen
`day_window_start_hour=`/`day_window_end_hour=` aus dem Segment-Bau in
`compare_location_weather_source.py` ENTFERNT -- und alle 46 einschlaegigen
Tests blieben gruen. Die Zusicherung war fuer den Ortsvergleich also nicht
dort geprueft, wo sie wirkt.

WARUM DIE MUTATION SO SCHWER ZU FANGEN IST -- und was daraus folgt:

`CompareLocationWeatherSource.fetch()` schneidet sein synthetisches Segment
bereits auf das Vergleichsfenster zu (`window_start`/`window_end`). Solange
das Vergleichsfenster INNERHALB des Defaults 4-19 liegt, ist der zusaetzliche
Fensterfilter in der Aggregation wirkungslos: der Vorschnitt hat die Stunden
ausserhalb schon entfernt, und ob danach gegen 10-16 oder gegen 4-19
gefiltert wird, aendert nichts. Ein Test mit einem ENGEREN Fenster kann die
Mutation deshalb prinzipiell nicht fangen.

Wirksam wird der Unterschied genau dann, wenn das Vergleichsfenster WEITER
ist als der Default: bei 3-21 liegt die Stunde 03:00 im Vorschnitt, aber
AUSSERHALB von 4-19. Faellt die Weitergabe weg, schneidet die Aggregation
diese Stunde weg und nennt einen spaeteren Beginn -- eine Zahl, die im
Ortsvergleich so nie stand. Genau diese Konstellation baut der Test unten.

KEIN NETZ, KEIN MOCK (CLAUDE.md, Kern-Schicht): der Prozess-Cache
(`get_shared_weather_cache()`) wird mit der Stundenreihe vorbefuellt, damit
`fetch_segment_weather()` einen Treffer hat und den Provider nie aufruft.
Der Prueling -- Segment-Bau, Vorschnitt, Aggregation -- laeuft vollstaendig
echt. Gewitterstufen entstehen ueber die ECHTE Fusion aus CAPE-Rohwerten.

Pfadregel #1409: Prueling relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.day_window import (  # noqa: E402
    DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    ThunderLevel, TripSegment,
)
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.compare_location_weather_source import (  # noqa: E402
    CompareLocationWeatherSource,
)
from services.segment_weather import SegmentWeatherService  # noqa: E402
from services.weather_cache import get_shared_weather_cache  # noqa: E402

# Island: ganzjaehrig UTC+0, keine Sommerzeit -> die Stundenzahl der Fixture
# IST die Ortszeit-Stunde am Vergleichsort. Keine Erwartung haengt an der
# Systemzone oder an der Sommerzeit.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
# Die Gewitter-FUSION nutzt die geeichte Alpen-Leiter (sie kennt die
# Koordinaten nicht, sie bekommt die Schwellen uebergeben).
ALPEN_LAT, ALPEN_LON, MODELL = 47.0, 12.0, "icon_d2"

# WEITER als der Default 4-19 -- nur so ist die Weitergabe ueberhaupt
# beobachtbar (s. Kopf).
WEITES_FENSTER = (3, 21)
# 03:00 liegt im weiten Fenster, aber AUSSERHALB des Defaults 4-19.
# 12:00 liegt in beiden.
GEWITTERSTUNDEN = {3: 400.0, 12: 800.0}
ORT_ID = "compare-onset-ort"


def _tag() -> date:
    return date.today() + timedelta(days=1)


def _dp(stunde: int, cape: float) -> ForecastDataPoint:
    t = _tag()
    return ForecastDataPoint(
        ts=datetime(t.year, t.month, t.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=5.0,
    )


def _tagesreihe() -> NormalizedTimeseries:
    punkte = [_dp(h, GEWITTERSTUNDEN.get(h, 100.0)) for h in range(24)]
    region = thunder_region_for(ALPEN_LAT, ALPEN_LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(MODELL, region),
                         lpi_thresholds_jkg(region))
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )


@pytest.fixture()
def vorbefuellter_cache():
    """Den Prozess-Cache so fuellen, dass `fetch_segment_weather()` einen
    Treffer hat und der Provider nie aufgerufen wird.

    Das Ablage-Segment deckt den GANZEN Tag ab -- damit trifft es jedes
    Fenster, das `fetch()` intern baut, und der Test haengt nicht an der
    genauen Fenster-Arithmetik des Prueflings.
    """
    from providers.base import get_provider

    t = _tag()
    punkt = GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=None,
                     distance_from_start_km=0.0)
    ablage = TripSegment(
        segment_id=ORT_ID, start_point=punkt, end_point=punkt,
        start_time=datetime(t.year, t.month, t.day, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(t.year, t.month, t.day, 23, 59, tzinfo=timezone.utc),
        duration_hours=24.0, distance_km=0.0, ascent_m=0, descent_m=0,
    )
    dienst = SegmentWeatherService(get_provider("openmeteo"))
    model_id = dienst._resolve_model_id(ISLAND_LAT, ISLAND_LON)
    cache = get_shared_weather_cache()
    cache.put(ablage, _tagesreihe(), enrich_ensemble=False, enrich_snow=False,
              model_id=model_id)
    yield cache


def _beginn_stunde(start_hour: int, end_hour: int) -> int | None:
    """Der Gewitterbeginn der Alarm-Vergleichsbasis EINES Vergleichsorts,
    ueber den echten Produktivweg `CompareLocationWeatherSource.fetch()`."""
    punkt = CompareLocationWeatherSource().fetch(
        ORT_ID, ISLAND_LAT, ISLAND_LON,
        start_hour=start_hour, end_hour=end_hour, target_date=_tag(),
    )
    onset = punkt.aggregated.thunder_onset_utc
    return None if onset is None else onset.hour


def test_fixture_unterscheidet_das_weite_fenster_vom_default():
    """Vakuum-Schutz: 03:00 muss ein Gewitter tragen UND ausserhalb des
    Defaults liegen -- sonst koennte dieser Test die Weitergabe gar nicht
    beobachten und bliebe auch ohne sie gruen."""
    stufen = {p.ts.hour: p.thunder_level for p in _tagesreihe().data}
    for stunde in GEWITTERSTUNDEN:
        assert stufen[stunde] not in (None, ThunderLevel.NONE), (
            f"Fixture: {stunde:02d}:00 muss ein Gewitter tragen: {stufen[stunde]!r}"
        )
    assert not (DAY_WINDOW_START_HOUR <= 3 <= DAY_WINDOW_END_HOUR), (
        f"Fixture: 03:00 muss AUSSERHALB des Defaults "
        f"{DAY_WINDOW_START_HOUR}-{DAY_WINDOW_END_HOUR} liegen, sonst ist die "
        "Weitergabe des Vergleichsfensters nicht beobachtbar."
    )
    assert WEITES_FENSTER[0] <= 3 <= WEITES_FENSTER[1], (
        f"Fixture: 03:00 muss INNERHALB von {WEITES_FENSTER} liegen."
    )


def test_vergleichs_tagesfenster_erreicht_die_beginn_berechnung(vorbefuellter_cache):
    """AC-10 fuer den Ortsvergleich: mit Vergleichsfenster 3-21 nennt die
    Alarm-Vergleichsbasis den Beginn 03:00.

    Faellt die Weitergabe von `day_window_start_hour`/`_end_hour` an das
    Compare-Segment weg (Adversary-Mutation M2), filtert die Aggregation
    gegen den Default 4-19, schneidet 03:00 weg und nennt 12:00 -- eine
    Stunde, die im Ortsvergleich nie stand. Dieser Test wird dann rot.
    """
    stunde = _beginn_stunde(*WEITES_FENSTER)
    assert stunde is not None, (
        "Der Ortsvergleich fuehrt gar keinen Gewitterbeginn -- dann prueft "
        "dieser Test die Fensterwahl nicht."
    )
    assert stunde == 3, (
        f"Vergleichsfenster {WEITES_FENSTER[0]}-{WEITES_FENSTER[1]}: erwartet "
        f"den Beginn 03:00, bekommen {stunde:02d}:00. 12:00 heisst, die "
        "Aggregation hat gegen den Default 4-19 gefiltert -- das "
        "Vergleichsfenster hat das Segment nicht erreicht."
    )


def test_enges_fenster_beschneidet_den_beginn_wie_erwartet(vorbefuellter_cache):
    """Gegenprobe in die andere Richtung: mit einem ENGEN Fenster (10-16)
    faellt 03:00 weg und der Beginn ist 12:00.

    Diese Richtung fangt die Mutation NICHT (der Vorschnitt entfernt 03:00
    ohnehin) -- sie steht hier, damit die Erwartung oben nicht als
    "irgendeine Stunde" durchgeht, sondern als eine, die sich mit dem
    Fenster nachweislich BEWEGT.
    """
    assert _beginn_stunde(10, 16) == 12, (
        "Mit Fenster 10-16 muss der Beginn 12:00 sein -- die 03:00 liegt "
        "ausserhalb und darf nicht erscheinen."
    )
