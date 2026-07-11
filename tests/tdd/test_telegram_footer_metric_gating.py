"""TDD RED — Issue #954 Bug A: Telegram-Fußzeile ignoriert Metriken-Auswahl.

SPEC: docs/specs/modules/fix_954_metric_gating_footer_preview.md (AC-1, AC-2, AC-4).

`_tg_day_footer()` (via `render_telegram_bubbles()`) baut die Kurzübersicht-Fußzeile
`⚡ … · Sicht … · 0°C-Grenze N m` bedingungslos — der ⚡-Teil erscheint immer, Sicht/
0°C-Grenze sobald Daten vorhanden sind, UNABHÄNGIG davon, ob die Metriken `thunder`,
`visibility` bzw. `freezing_level` im Trip aktiviert sind. Da `format_email()` diese
Bubbles für den ECHTEN Telegram-Versand baut, ist das nutzersichtbar.

RED-Zustand (jetzt): Fußzeile zeigt alle drei Teile, auch wenn deaktiviert →
AssertionError. GREEN-Zustand (nach Fix): jeder Teil erscheint nur bei aktivierter
zugehöriger Metrik; alle drei deaktiviert → keine Fußzeile.

KEINE Mocks, KEIN Dateiinhalt-Check. Reale Model-Objekte + realer Renderaufruf.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Vienna")


# ---------------------------------------------------------------------------
# Fixture-Helper — echte Segment-/DisplayConfig-Objekte (kein Mock).
# Muster übernommen aus tests/tdd/test_issue_1001_telegram_bubbles.py.
# Das Segment trägt bewusst Gewitter-(NONE)-, Sicht-(15000 m) und
# Frostgrenze-(3200 m)-Daten, damit alle drei Fußzeilen-Teile OHNE Gating
# gerendert würden.
# ---------------------------------------------------------------------------


def _make_segment():
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 3, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=6.0, ascent_m=500.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[])
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=20,
        thunder_level_max=ThunderLevel.NONE,
        visibility_min_m=15000, freezing_level_m=3200, wind_direction_avg_deg=90,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_dc(metric_ids: list[str]):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=idx)
        for idx, mid in enumerate(metric_ids)
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="test-954", metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


_ROW = {
    "time": "08", "temp": 12, "wind": 5, "wind_dir": 90, "precip": 0.0,
    "cloud": 20, "thunder": "NONE", "visibility": 15000, "freeze_lvl": 3200,
}


def _overview_bubble_text(metric_ids: list[str]) -> str:
    """Rendert die Bubbles und liefert den Text der Kurzübersicht-Bubble
    (die die Fußzeile trägt)."""
    from output.renderers.narrow import render_telegram_bubbles

    seg = _make_segment()
    rows = [dict(_ROW), {**_ROW, "time": "09", "temp": 14}]
    dc = _make_dc(metric_ids)
    bubbles = render_telegram_bubbles(
        segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
        tz=_TZ, trip_name="Footer Gating Test",
    )
    assert bubbles, "render_telegram_bubbles() muss eine nicht-leere Liste liefern"
    matches = [b.text for b in bubbles if "Kurzübersicht" in b.text]
    assert matches, "Kurzübersicht-Bubble nicht gefunden"
    return matches[0]


# ===========================================================================
# AC-1: Alle drei Metriken deaktiviert → gar keine Fußzeile.
# ===========================================================================


def test_footer_absent_when_all_three_metrics_disabled():
    """AC-1: thunder/visibility/freezing_level deaktiviert → weder ⚡ noch Sicht
    noch 0°C-Grenze in der Kurzübersicht-Bubble."""
    text = _overview_bubble_text(["temperature", "precipitation", "wind"])
    assert "⚡" not in text, f"⚡-Teil trotz deaktivierter thunder-Metrik vorhanden:\n{text}"
    assert "Sicht" not in text, f"Sicht-Teil trotz deaktivierter visibility-Metrik vorhanden:\n{text}"
    assert "0°C-Grenze" not in text, f"0°C-Grenze-Teil trotz deaktivierter freezing_level-Metrik vorhanden:\n{text}"


# ===========================================================================
# AC-2: Nur visibility aktiviert → NUR Sicht-Teil, kein ⚡, kein 0°C-Grenze.
# Gezielter Teilmengen-Fall (echtes Gating pro Metrik, kein globaler Schalter).
# ===========================================================================


def test_footer_shows_only_enabled_visibility_part():
    """AC-2: Nur visibility aktiv (thunder + freezing_level aus) → Fußzeile
    enthält ausschließlich den Sicht-Teil."""
    text = _overview_bubble_text(["temperature", "visibility"])
    assert "Sicht" in text, f"Sicht-Teil fehlt, obwohl visibility aktiviert ist:\n{text}"
    assert "⚡" not in text, f"⚡-Teil trotz deaktivierter thunder-Metrik vorhanden:\n{text}"
    assert "0°C-Grenze" not in text, f"0°C-Grenze-Teil trotz deaktivierter freezing_level-Metrik vorhanden:\n{text}"


# ===========================================================================
# AC-4 (Regression): Alle drei aktiviert → Fußzeile unverändert vollständig.
# ===========================================================================


def test_footer_complete_when_all_three_enabled():
    """AC-4: thunder/visibility/freezing_level aktiv → Fußzeile zeigt alle drei
    Teile wie bisher (Regressionsschutz)."""
    text = _overview_bubble_text(["thunder", "visibility", "freezing_level"])
    assert "⚡" in text, f"⚡-Teil fehlt trotz aktivierter thunder-Metrik:\n{text}"
    assert "Sicht" in text, f"Sicht-Teil fehlt trotz aktivierter visibility-Metrik:\n{text}"
    assert "0°C-Grenze" in text, f"0°C-Grenze-Teil fehlt trotz aktivierter freezing_level-Metrik:\n{text}"
