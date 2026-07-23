"""TDD RED — Scheibe 2 (Telegram) von Issue #1349: Hinweis "amtliche Warnungen
nicht abrufbar" im Telegram-Trip-Briefing.

SPEC: docs/specs/modules/feat_1349_telegram_unavailable.md (AC-1 … AC-4)

Diese Tests schlagen JETZT absichtlich fehl — `render_telegram_bubbles` wertet
`official_alerts_unavailable` noch nicht aus.

KEIN Mock-Theater: echte `SegmentWeatherData`-Objekte, echter Renderer-Aufruf,
netzfrei. AC-4 reproduziert den ECHTEN Fail-soft-Pfad über
`get_official_alerts_with_status` mit geblockter echter `GeoSphereWarnSource` —
KEIN werfendes Double.

Fixture-Muster übernommen aus tests/tdd/test_telegram_official_alert_bubble.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.narrow import render_telegram_bubbles

UTC = timezone.utc
_TZ = ZoneInfo("UTC")
_YEAR, _MONTH, _DAY = 2026, 7, 15
_HINT = "nicht abrufbar"
_METRIC_IDS = ["temperature", "precipitation", "wind", "thunder"]
_ROW = {
    "time": "08", "temp": 12, "wind": 5, "wind_dir": 90, "precip": 0.0,
    "cloud": 20, "thunder": "NONE", "visibility": 15000, "freeze_lvl": 3200,
}


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=UTC),
        t2m_c=18.0, wind10m_kmh=0.0, gust_kmh=0.0, precip_1h_mm=0.0,
        cloud_total_pct=40, thunder_level=ThunderLevel.NONE, humidity_pct=55,
        pop_pct=0.0,
    )


def _segment(*, unavailable: bool = False, segment_id: object = 1,
             lat: float = 42.0, lon: float = 9.0) -> SegmentWeatherData:
    data = [_dp(h) for h in range(24)]
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=500.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, 7, 0, tzinfo=UTC),
        end_time=datetime(_YEAR, _MONTH, _DAY, 17, 0, tzinfo=UTC),
        duration_hours=10.0, distance_km=14.0, ascent_m=800.0, descent_m=600.0,
    )
    sw = SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=ForecastMeta(
            provider=Provider.OPENMETEO, model="test",
            run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=UTC),
            grid_res_km=1.0, interp="point_grid",
        ), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=9.0, temp_max_c=24.0, wind_max_kmh=0.0, gust_max_kmh=0.0,
            precip_sum_mm=0.0, pop_max_pct=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=UTC),
        provider="openmeteo",
        official_alerts=[],
    )
    sw.official_alerts_unavailable = unavailable
    return sw


def _dc() -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="test-1349-tg",
        metrics=[
            MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
            for i, mid in enumerate(_METRIC_IDS)
        ],
        updated_at=datetime(_YEAR, _MONTH, _DAY, 5, 0, tzinfo=UTC),
    )


def _bubbles(segments) -> list[str]:
    seg_tables = [[dict(_ROW), {**_ROW, "time": "09", "temp": 14}] for _ in segments]
    result = render_telegram_bubbles(
        segments=segments, seg_tables=seg_tables, dc=_dc(),
        report_type="morning", tz=_TZ, trip_name="GR20 Unavailable-Test",
    )
    return [b.text for b in result]


def test_ac1_flag_gesetzt_zeigt_hinweis_bubble():
    """AC-1: ≥1 Segment mit official_alerts_unavailable=True -> eine Bubble trägt
    den Hinweis 'nicht abrufbar'."""
    texts = _bubbles([_segment(unavailable=True)])
    hits = [t for t in texts if _HINT in t.lower()]
    assert hits, (
        f"AC-1: Keine Telegram-Bubble trägt den Nicht-abrufbar-Hinweis. "
        f"Bubbles: {texts!r}"
    )


def test_ac2_flag_false_keine_hinweis_bubble_liste_unveraendert():
    """AC-2: kein Flag -> kein Hinweis UND Bubble-Liste identisch zur Baseline."""
    texts = _bubbles([_segment(unavailable=False)])
    baseline = _bubbles([_segment(unavailable=False)])
    assert texts == baseline, "AC-2: Ohne Flag muss die Bubble-Liste deterministisch gleich bleiben."
    assert not any(_HINT in t.lower() for t in texts), (
        f"AC-2: Ohne gesetztes Flag darf kein Nicht-abrufbar-Hinweis erscheinen. Bubbles: {texts!r}"
    )


def test_ac3_hinweis_stammt_aus_geteiltem_baustein():
    """AC-3: der Hinweistext stammt aus dem geteilten unavailable_hint-Baustein
    (kein neuer Telegram-Textbaustein)."""
    from output.renderers.email.unavailable_hint import (
        render_official_alerts_unavailable_plain,
    )
    # Kern-Text ohne Emoji/Interpunktion, den _esc nicht verändert.
    core = "Amtliche Warnungen aktuell nicht abrufbar"
    assert core in render_official_alerts_unavailable_plain(ascii_safe=False)
    texts = _bubbles([_segment(unavailable=True)])
    assert any(core in t for t in texts), (
        f"AC-3: Der Hinweis muss den geteilten Baustein-Text tragen. Bubbles: {texts!r}"
    )


def test_ac4_echter_failsoft_pfad_ohne_werfendes_double():
    """AC-4: Flag aus dem ECHTEN Fail-soft-Pfad (geblockte GeoSphereWarnSource,
    liefert intern [] ohne zu werfen) -> Hinweis erscheint. Kein Double."""
    import services.official_alerts.base as oa_base
    from services.official_alerts.base import get_official_alerts_with_status
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource, _cache

    at_lat, at_lon = 47.26, 11.39  # Innsbruck, GeoSphere-Bbox

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    _cache.clear()
    try:
        source = GeoSphereWarnSource()
        assert source.covers(at_lat, at_lon) is True
        oa_base._REGISTERED_SOURCES.append(source)

        alerts, unavailable = get_official_alerts_with_status(at_lat, at_lon)
        assert alerts == []
        assert unavailable is True, "Voraussetzung: echter Fail-soft-Pfad -> unavailable=True."

        texts = _bubbles([_segment(unavailable=unavailable, lat=at_lat, lon=at_lon)])
        assert any(_HINT in t.lower() for t in texts), (
            f"AC-4: Der echte Fail-soft-Ausfall MUSS den Telegram-Hinweis erzeugen. "
            f"Bubbles: {texts!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _cache.clear()
