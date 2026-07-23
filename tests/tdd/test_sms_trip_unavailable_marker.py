"""TDD RED — Scheibe 1 (SMS) von Issue #1349: W?-Token "amtliche Warnungen
nicht abrufbar" im SMS-Trip-Report.

SPEC: docs/specs/modules/feat_1349_sms_unavailable.md (AC-1 … AC-4)

Diese Tests schlagen JETZT absichtlich fehl — der W?-Token existiert noch nicht:
- `format_sms` emittiert bei gesetztem `official_alerts_unavailable`-Flag KEIN "W?".

KEIN Mock-Theater (Projektkonvention): echte `SegmentWeatherData`-Objekte laufen
durch den echten SMS-Renderer (`SMSTripFormatter().format_sms`). AC-4 reproduziert
den ECHTEN Fail-soft-Pfad ueber `get_official_alerts_with_status` mit einer echten,
im Egress-Waechter geblockten Quelle (`GeoSphereWarnSource`) — KEIN werfendes
Double (genau das war der Bug in der Trip-Scheibe #1348).

Segment-Builder-Muster uebernommen aus
tests/tdd/test_official_alerts_unavailable_hint.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Berlin")
_LAT, _LON = 43.7102, 7.2620
_MARKER = "W?"


def _make_dp():
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        wind_chill_c=20.0, cape_jkg=100.0, visibility_m=20000.0,
    )


def _make_segment(segment_id: int, *, unavailable: bool = False, alerts=None,
                  lat: float = _LAT, lon: float = _LON):
    """Ein echtes SegmentWeatherData; `official_alerts_unavailable` als
    Instanz-Attribut (im RED-Stand kein Dataclass-Feld — der Renderer liest per
    getattr; nach der Implementierung regulaeres additives Feld, Default False)."""
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    dp = _make_dp()
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=400.0),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.04, elevation_m=800.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=400.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=15.0, gust_max_kmh=25.0, precip_sum_mm=0.0,
        cloud_avg_pct=30, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=20.0,
    )
    sw = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        official_alerts=list(alerts or []),
    )
    sw.official_alerts_unavailable = unavailable
    return sw


def _real_alert():
    from services.official_alerts import OfficialAlert
    return OfficialAlert(
        source="test-vigilance", hazard="thunderstorm", level=3,
        label="Gewitterwarnung Stufe Orange",
    )


def _render_sms(segments):
    from output.renderers.sms_trip import SMSTripFormatter
    return SMSTripFormatter().format_sms(
        segments, max_length=160, tz=_TZ, report_type="evening",
        stage_name="Etappe 1",
    )


def test_ac1_flag_gesetzt_zeigt_w_marker():
    """AC-1: ein Segment mit official_alerts_unavailable=True -> die SMS enthaelt
    den Token 'W?'."""
    out = _render_sms([_make_segment(1, unavailable=True)])
    assert _MARKER in out, (
        f"AC-1: Bei mindestens einer ausgefallenen abdeckenden Quelle MUSS die SMS "
        f"den Marker '{_MARKER}' tragen (gerenderte Ausgabe). War: {out!r}"
    )


def test_ac2_flag_false_byte_identisch_ohne_marker():
    """AC-2: kein Segment mit Flag -> SMS byte-identisch zur Baseline und ohne 'W?'
    (Regressionsschutz).

    Baseline = dieselben Segmente, exakt gleiche Render-Parameter. Der Feature-Pfad
    darf ohne Ausfall NICHTS an der Ausgabe aendern.
    """
    segments_a = [_make_segment(1, unavailable=False)]
    segments_b = [_make_segment(1, unavailable=False)]
    out = _render_sms(segments_a)
    baseline = _render_sms(segments_b)
    assert out == baseline, (
        "AC-2: Ohne Ausfall MUSS die SMS deterministisch identisch bleiben."
    )
    assert _MARKER not in out, (
        f"AC-2: Ohne gesetztes Flag darf kein '{_MARKER}' erscheinen. War: {out!r}"
    )


def test_ac3_marker_ist_kein_teil_des_warnblocks():
    """AC-3: Nur das Flag ist gesetzt (KEINE echte Warnung) -> 'W?' erscheint, wird
    aber NICHT als amtliche-Warnung-Token gerendert.

    Diskriminator: der '!'-Warnblock-Marker (render.py) wird ausschliesslich
    Tokens der Kategorie 'official_alert' vorangestellt. Ohne echte Warnung darf
    daher gar kein '!' in der Zeile stehen — steht doch eins da, waere 'W?'
    faelschlich als amtliche Warnung ('!W?') gerendert.
    """
    out = _render_sms([_make_segment(1, unavailable=True)])
    assert _MARKER in out, f"AC-3: '{_MARKER}' muss vorhanden sein. War: {out!r}"
    assert "!" not in out, (
        f"AC-3: Ohne echte Warnung darf KEIN '!'-Warnblock in der Zeile stehen — "
        f"'{_MARKER}' ist 'nicht abrufbar', KEINE amtliche Warnung. War: {out!r}"
    )


def test_ac3b_marker_neben_echter_warnung_bleibt_getrennt():
    """AC-3 (Mischfall): echte Warnung UND Flag gesetzt -> beide erscheinen, aber
    'W?' bleibt vom '!'-Warnblock getrennt ('!W?' darf nicht vorkommen)."""
    segments = [
        _make_segment(1, unavailable=True),
        _make_segment(2, alerts=[_real_alert()]),
    ]
    out = _render_sms(segments)
    assert _MARKER in out, f"AC-3b: '{_MARKER}' fehlt. War: {out!r}"
    assert "!" in out, (
        f"AC-3b: Die echte Warnung muss ihren '!'-Warnblock behalten. War: {out!r}"
    )
    assert f"!{_MARKER}" not in out, (
        f"AC-3b: '{_MARKER}' darf NICHT als amtliche Warnung ('!{_MARKER}') "
        f"gerendert werden. War: {out!r}"
    )


def test_ac4_echter_failsoft_pfad_ohne_werfendes_double():
    """AC-4 REAL-PFAD-REGRESSIONSWAECHTER: das Flag wird wie im Scheduler ueber
    `get_official_alerts_with_status` aus einer ECHTEN, im Egress-Waechter
    geblockten Quelle (`GeoSphereWarnSource`) gewonnen — sie liefert intern
    fail-soft `[]` OHNE zu werfen. Dieser Status (unavailable=True) muss den
    'W?'-Marker in der SMS ausloesen. KEIN werfendes Double.
    """
    import services.official_alerts.base as oa_base
    from services.official_alerts.base import get_official_alerts_with_status
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource, _cache

    at_lat, at_lon = 47.26, 11.39  # Innsbruck, in der GeoSphere-Bbox

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    _cache.clear()
    try:
        source = GeoSphereWarnSource()
        assert source.covers(at_lat, at_lon) is True
        oa_base._REGISTERED_SOURCES.append(source)

        alerts, unavailable = get_official_alerts_with_status(at_lat, at_lon)
        assert alerts == [], f"Geblockte Quelle darf keine Alerts liefern: {alerts!r}"
        assert unavailable is True, (
            "Voraussetzung: der echte Fail-soft-Pfad liefert unavailable=True."
        )

        seg = _make_segment(1, unavailable=unavailable, lat=at_lat, lon=at_lon)
        out = _render_sms([seg])
        assert _MARKER in out, (
            f"AC-4: Der aus dem echten Fail-soft-Pfad gewonnene Ausfall MUSS den "
            f"'{_MARKER}'-Marker in der SMS erzeugen. War: {out!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _cache.clear()
