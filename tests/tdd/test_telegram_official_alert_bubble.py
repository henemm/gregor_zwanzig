"""Amtliche Warnungen ausgeschrieben im Telegram-Trip-Briefing (#1318, Scheibe B).

SPEC: docs/specs/modules/sms_official_alert_tokens.md — AC-8, Implementation
Details Abschnitt 4.

TDD RED. Vor der Implementierung MUESSEN diese Tests rot sein:
  - `render_telegram_bubbles()` (narrow.py) wertet `seg.official_alerts`
    ueberhaupt nicht aus -> es entsteht strukturell nie eine Warn-Bubble.

Ausnahmen, die schon heute gruen sein sollen (Filter- und Non-Regression-
Zusicherungen, die NACH der Implementierung weiter gelten muessen):
  - gelbe Warnung erzeugt keine Bubble (heute trivial gruen, weil gar keine
    Bubble entsteht),
  - die Bubble-Liste ohne Warnung bleibt unveraendert (Additivitaet).

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`/`SegmentWeatherData`-
Objekte, echter Renderer-Aufruf, netzfrei.

Bewusst NICHT geprueft: der Transportweg des Trip-Kontexts. Der Aufruf nutzt
die heutige Signatur; die Warnungen haengen an den Segmenten selbst. Ein
zusaetzlicher optionaler Parameter (Spec Abschnitt 4) ist erlaubt, darf aber
nicht Voraussetzung dafuer sein, dass die an den Segmenten haengenden
Warnungen sichtbar werden.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.narrow import render_telegram_bubbles
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
_TZ = ZoneInfo("UTC")
_YEAR, _MONTH, _DAY = 2026, 7, 15

WARN_FROM = datetime(_YEAR, _MONTH, _DAY, 14, 0, tzinfo=UTC)
WARN_TO = datetime(_YEAR, _MONTH, _DAY, 18, 0, tzinfo=UTC)

_HAZARD_LABELS = {
    "thunderstorm": "Gewitter",
    "rain": "Starkregen",
    "wind_gust": "Sturm",
}

_METRIC_IDS = ["temperature", "precipitation", "wind", "thunder"]

_ROW = {
    "time": "08", "temp": 12, "wind": 5, "wind_dir": 90, "precip": 0.0,
    "cloud": 20, "thunder": "NONE", "visibility": 15000, "freeze_lvl": 3200,
}


# ---------------------------------------------------------------------------
# Fixtures — echte Objekte, keine Doubles
# ---------------------------------------------------------------------------

def _alert(hazard: str, level: int) -> OfficialAlert:
    return OfficialAlert(
        source="meteoalarm", hazard=hazard, level=level,
        label=_HAZARD_LABELS.get(hazard, hazard),
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Haute-Corse",
    )


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=UTC),
        t2m_c=18.0, wind10m_kmh=0.0, gust_kmh=0.0, precip_1h_mm=0.0,
        cloud_total_pct=40, thunder_level=ThunderLevel.NONE, humidity_pct=55,
        pop_pct=0.0,
    )


def _segment(
    alerts: list[OfficialAlert] | None = None, segment_id: object = 1,
) -> SegmentWeatherData:
    data = [_dp(h) for h in range(24)]
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, 7, 0, tzinfo=UTC),
        end_time=datetime(_YEAR, _MONTH, _DAY, 17, 0, tzinfo=UTC),
        duration_hours=10.0, distance_km=14.0, ascent_m=800.0, descent_m=600.0,
    )
    return SegmentWeatherData(
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
        official_alerts=list(alerts or []),
    )


def _bubbles(alerts: list[OfficialAlert] | None = None) -> list[str]:
    seg = _segment(alerts)
    rows = [dict(_ROW), {**_ROW, "time": "09", "temp": 14}]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="test-1318",
        metrics=[
            MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
            for i, mid in enumerate(_METRIC_IDS)
        ],
        updated_at=datetime(_YEAR, _MONTH, _DAY, 5, 0, tzinfo=UTC),
    )
    result = render_telegram_bubbles(
        segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
        tz=_TZ, trip_name="GR20 Warn-Test",
    )
    return [b.text for b in result]


def _warn_bubbles(texts: list[str], label: str) -> list[str]:
    return [t for t in texts if label in t]


# ---------------------------------------------------------------------------
# AC-8 — Warnung >= orange erscheint ausgeschrieben in einer Bubble
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("level", "level_word", "position"),
    [(4, "ROT", "3/3"), (3, "ORANGE", "2/3")],
)
def test_ac8_official_alert_appears_written_out_in_a_bubble(
    level: int, level_word: str, position: str,
):
    """Gewitterwarnung Stufe ORANGE/ROT -> eine Bubble nennt sie ausgeschrieben.

    Geprueft wird zusaetzlich, dass der Text die Handschrift des GETEILTEN
    `render_official_alert_telegram` traegt (Stufenwort + n/3-Position), statt
    eines neu erfundenen Renderers.
    """
    texts = _bubbles([_alert("thunderstorm", level)])
    hits = _warn_bubbles(texts, "Gewitter")
    assert hits, (
        f"Keine Bubble nennt die amtliche Gewitterwarnung (Stufe {level}) "
        f"ausgeschrieben. Bubbles: {texts!r}"
    )
    warn = hits[0]
    assert level_word in warn, (
        f"Stufenwort {level_word!r} fehlt in der Warn-Bubble: {warn!r}"
    )
    assert position in warn, (
        f"Stufen-Position {position!r} (Handschrift von "
        f"render_official_alert_telegram) fehlt in der Warn-Bubble: {warn!r}"
    )


def test_ac8_bubble_is_not_sms_shortened():
    """Telegram ist ausgeschrieben: kein SMS-Kuerzel, keine 160-Zeichen-Kappung."""
    texts = _bubbles([_alert("thunderstorm", 4)])
    hits = _warn_bubbles(texts, "Gewitter")
    assert hits, f"Warn-Bubble fehlt: {texts!r}"
    warn = hits[0]
    assert "TH:H" not in warn, (
        f"Die Telegram-Bubble zeigt das SMS-Kuerzel statt Klartext: {warn!r}"
    )
    assert "…" not in warn and "..." not in warn, (
        f"Die Telegram-Bubble ist gekuerzt worden (Kuerzungs-Zeichen gefunden): {warn!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — gleicher Stufenfilter wie die SMS (hazard_symbols.MIN_SMS_LEVEL)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", [1, 2])
def test_ac8_yellow_and_green_warnings_produce_no_bubble(level: int):
    """Nur gelbe/gruene Warnung -> Bubble-Liste bit-identisch zur Liste ohne Warnung."""
    baseline = _bubbles()
    texts = _bubbles([_alert("rain", level)])
    assert not _warn_bubbles(texts, "Starkregen"), (
        f"Warnung der Stufe {level} liegt unter dem Filter und darf in keiner "
        f"Bubble erscheinen: {texts!r}"
    )
    assert texts == baseline, (
        "Eine gefilterte Warnung darf die Bubble-Liste um kein Byte veraendern.\n"
        f"ohne Warnung: {baseline!r}\nmit gelber Warnung: {texts!r}"
    )


def test_ac8_filter_threshold_comes_from_shared_catalog():
    """Der Stufenfilter ist derselbe wie bei der SMS — eine Quelle, kein zweiter Wert."""
    from output.tokens.hazard_symbols import MIN_SMS_LEVEL

    below = _bubbles([_alert("wind_gust", MIN_SMS_LEVEL - 1)])
    at = _bubbles([_alert("wind_gust", MIN_SMS_LEVEL)])
    assert not _warn_bubbles(below, "Sturm"), (
        f"Stufe {MIN_SMS_LEVEL - 1} liegt unter MIN_SMS_LEVEL und darf keine "
        f"Bubble erzeugen: {below!r}"
    )
    assert _warn_bubbles(at, "Sturm"), (
        f"Stufe {MIN_SMS_LEVEL} (== MIN_SMS_LEVEL) muss eine Bubble erzeugen: {at!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Non-Regression: ohne Warnung bleibt alles wie heute
# ---------------------------------------------------------------------------
def test_ac8_no_alert_bubbles_unchanged_and_addition_is_additive():
    """Ohne Warnung keine Warn-Spur; mit Warnung bleiben alle Bestands-Bubbles
    unveraendert erhalten (die Warn-Bubble kommt additiv dazu)."""
    baseline = _bubbles()
    assert baseline, "render_telegram_bubbles() muss Bubbles liefern"
    assert not any("Gewitter" in t or "Warnstufe" in t for t in baseline), (
        f"Ohne amtliche Warnung darf keine Warn-Spur erscheinen: {baseline!r}"
    )

    with_alert = _bubbles([_alert("thunderstorm", 4)])
    missing = [t for t in baseline if t not in with_alert]
    assert not missing, (
        "Die Warn-Bubble darf bestehende Bubbles nicht veraendern oder "
        f"verdraengen. Verlorene/veraenderte Bubbles: {missing!r}"
    )


# ---------------------------------------------------------------------------
# Adversary FB02 — Trip-Kontext ueber den ECHTEN Produktionsweg
# (TripReportFormatter.format_email), nicht ueber den Direktaufruf des
# Renderers. Ohne Durchreichung bleibt "gesamte Route" strukturell unerreichbar.
# ---------------------------------------------------------------------------

def _trip() -> "object":
    """Echter Trip mit 3 Wegpunkten -> Gesamtroute = Segment 1, 2, Ziel."""
    from datetime import date

    from app.trip import Stage, Trip, Waypoint

    wps = [
        Waypoint(id=f"G{i}", name=f"Punkt {i}", lat=42.0 + i / 10, lon=9.0 + i / 10,
                 elevation_m=500 + 100 * i)
        for i in range(1, 4)
    ]
    return Trip(
        id="fb02-trip", name="GR20 Warn-Test",
        stages=[Stage(id="T1", name="Etappe 1",
                      date=date(_YEAR, _MONTH, _DAY), waypoints=wps)],
    )


def _telegram_via_format_email(
    alerted_ids: list[object], trip: object | None,
) -> list[str]:
    """Rendert das Briefing ueber den Produktionsweg und gibt die Telegram-
    Bubbles zurueck. `alerted_ids` = Segmente, die die Warnung tragen."""
    from output.renderers.trip_report import TripReportFormatter

    alert = _alert("thunderstorm", 4)
    segments = [
        _segment([alert] if sid in alerted_ids else [], segment_id=sid)
        for sid in (1, 2, "Ziel")
    ]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="fb02-trip",
        metrics=[
            MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
            for i, mid in enumerate(_METRIC_IDS)
        ],
        updated_at=datetime(_YEAR, _MONTH, _DAY, 5, 0, tzinfo=UTC),
    )
    report = TripReportFormatter().format_email(
        segments=segments, trip_name="GR20 Warn-Test", report_type="morning",
        display_config=dc, tz=_TZ, trip=trip,
    )
    return list(report.telegram_bubbles or [])


def test_fb02_full_route_alert_is_labelled_gesamte_route_via_format_email():
    """Warnung auf ALLEN Segmenten -> Umfang 'gesamte Route', nicht Aufzaehlung."""
    texts = _telegram_via_format_email([1, 2, "Ziel"], _trip())
    hits = _warn_bubbles(texts, "Gewitter")
    assert hits, f"Warn-Bubble fehlt im Produktionsweg: {texts!r}"
    warn = hits[0]
    assert "gesamte Route" in warn, (
        "Eine Warnung ueber alle Segmente muss als 'gesamte Route' ausgewiesen "
        f"werden — der Trip-Kontext kommt sonst nie im Renderer an: {warn!r}"
    )


def test_fb02_partial_route_alert_keeps_segment_listing():
    """Gegenprobe: nur ein Segment betroffen -> Segment-Angabe bleibt."""
    texts = _telegram_via_format_email([1], _trip())
    hits = _warn_bubbles(texts, "Gewitter")
    assert hits, f"Warn-Bubble fehlt im Produktionsweg: {texts!r}"
    warn = hits[0]
    assert "gesamte Route" not in warn, (
        f"Nur Segment 1 ist betroffen — 'gesamte Route' waere falsch: {warn!r}"
    )
    assert "Segment 1" in warn, (
        f"Die Segment-Angabe fehlt in der Warn-Bubble: {warn!r}"
    )


def test_fb02_format_email_without_trip_still_works():
    """Ohne `trip` (Bestandsaufrufer/Tests): kein Crash, Warnung bleibt sichtbar,
    Umfang faellt auf die Segment-Angabe zurueck."""
    texts = _telegram_via_format_email([1, 2, "Ziel"], None)
    hits = _warn_bubbles(texts, "Gewitter")
    assert hits, f"Ohne Trip-Kontext muss die Warnung trotzdem erscheinen: {texts!r}"
    assert "gesamte Route" not in hits[0], (
        f"Ohne Trip-Kontext ist die Gesamtroute unbekannt: {hits[0]!r}"
    )
