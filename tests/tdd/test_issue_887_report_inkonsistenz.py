"""
TDD RED — Issue #887: Inkonsistenz zwischen Reports (SMS/Telegram)

SPEC: docs/specs/modules/fix_887_report_inkonsistenz.md

Drei Lücken:
  1. SMS: pop_hourly wird nie befüllt → PR– statt PR40%
  2. Telegram: _tg_segment_line() ignoriert display_config komplett
  3. Telegram: col_label aus Metrik-Katalog muss als Label in Detail-Zeile erscheinen

KEINE Mocks — echte Modell-Strukturen, echte Formatter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(
    pop_max_pct: int | None = None,
    precip_sum_mm: float = 0.0,
    wind_max_kmh: float = 20.0,
    gust_max_kmh: float = 30.0,
    temp_min_c: float = 12.0,
    temp_max_c: float = 18.0,
    segment_id: int = 1,
):
    """Minimales SegmentWeatherData-Objekt für Unit-Tests."""
    from app.models import (
        GPXPoint,
        NormalizedTimeseries,
        SegmentWeatherData,
        SegmentWeatherSummary,
        ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=400,
        descent_m=0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=temp_min_c,
        temp_max_c=temp_max_c,
        temp_avg_c=(temp_min_c + temp_max_c) / 2,
        wind_max_kmh=wind_max_kmh,
        gust_max_kmh=gust_max_kmh,
        precip_sum_mm=precip_sum_mm,
        thunder_level_max=ThunderLevel.NONE,
        pop_max_pct=pop_max_pct,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _make_dc(metric_ids: list[str]):
    """UnifiedWeatherDisplayConfig mit angegebenen Metriken als primary."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
        for i, mid in enumerate(metric_ids)
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="test-887",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


def _row_with_pop(pop_val: int) -> dict:
    """Minimal-Row-Dict mit pop-Wert für Detail-Zeilen-Test."""
    return {"pop": pop_val, "time": "10:00"}


def _row_with_pop_and_gust(pop_val: int, gust_val: float) -> dict:
    return {"pop": pop_val, "gust": gust_val, "time": "10:00"}


# ---------------------------------------------------------------------------
# AC-1: SMS zeigt PR{N}% wenn pop_max_pct gesetzt
# ---------------------------------------------------------------------------

def test_ac1_sms_shows_pr_token_when_pop_max_pct_set():
    """
    AC-1: Given Segment mit pop_max_pct=40
    When SMS formatiert wird
    Then erscheint PR40% (nicht PR–) im Ergebnis
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _make_segment(pop_max_pct=40, precip_sum_mm=0.5)
    result = SMSTripFormatter().format_sms(
        [seg],
        stage_name="E1",
        report_type="evening",
        tz=ZoneInfo("Europe/Vienna"),
    )
    # PR– bedeutet: keine pop_hourly-Daten → Fehler
    assert "PR-" not in result, f"PR- found (pop_hourly leer): {result!r}"
    # Erwartet: PR40% oder PR40%@10 o.ä.
    assert "PR" in result and "40" in result, (
        f"Erwartet PR+40 im SMS, bekam: {result!r}"
    )


def test_ac1_sms_pr_token_format_contains_percent():
    """
    AC-1 (Format): PR-Token für rain_probability enthält %-Zeichen
    (weil _fmt_num für PR 'int(val)%' liefert).
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _make_segment(pop_max_pct=65, precip_sum_mm=1.0)
    result = SMSTripFormatter().format_sms(
        [seg],
        stage_name="E1",
        report_type="morning",
        tz=ZoneInfo("Europe/Vienna"),
    )
    assert "65%" in result, f"Kein '65%' im SMS-Ergebnis: {result!r}"


# ---------------------------------------------------------------------------
# AC-2: Telegram zeigt Rain% Label wenn rain_probability konfiguriert
# ---------------------------------------------------------------------------

def test_ac2_telegram_shows_rain_pct_label_when_configured():
    """
    AC-2: Given Segment mit pop_max_pct=60, display_config mit rain_probability
    When render_narrow("telegram", ...) aufgerufen
    Then enthält Ausgabe 'Rain%' (col_label) und '60'
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=60, precip_sum_mm=1.5)
    dc = _make_dc(["temperature", "wind", "rain_probability"])
    rows = [_row_with_pop(60)]

    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[rows],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert "Rain%" in result, (
        f"col_label 'Rain%' fehlt in Telegram-Output:\n{result}"
    )
    assert "60" in result, (
        f"Wert '60' fehlt in Telegram-Output:\n{result}"
    )


def test_ac2_telegram_uses_col_label_not_compact_label():
    """
    AC-2 (Label-Quelle): Telegram verwendet col_label ('Rain%'), nicht compact_label ('P%').
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=45, precip_sum_mm=0.8)
    dc = _make_dc(["temperature", "wind", "rain_probability"])
    rows = [_row_with_pop(45)]

    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[rows],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert "P%" not in result, (
        f"compact_label 'P%' gefunden, sollte col_label 'Rain%' sein:\n{result}"
    )
    assert "Rain%" in result, f"col_label 'Rain%' fehlt:\n{result}"


# ---------------------------------------------------------------------------
# AC-3: Telegram Detail-Zeile mit Rain% UND Gust wenn beide konfiguriert
# ---------------------------------------------------------------------------

def test_ac3_telegram_shows_rain_and_gust_when_both_configured():
    """
    AC-3: Given display_config mit rain_probability + gust
    When render_narrow("telegram", ...) aufgerufen
    Then enthält Detail-Zeile 'Rain%' und 'Gust'
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=55, gust_max_kmh=42.0, precip_sum_mm=1.0)
    dc = _make_dc(["temperature", "wind", "rain_probability", "gust"])
    rows = [_row_with_pop_and_gust(55, 42.0)]

    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[rows],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert "Rain%" in result, f"'Rain%' fehlt:\n{result}"
    assert "Gust" in result, f"'Gust' fehlt:\n{result}"


# ---------------------------------------------------------------------------
# AC-4: pop_max_pct=None → kein Absturz
# ---------------------------------------------------------------------------

def test_ac4_sms_no_crash_when_pop_max_pct_is_none():
    """
    AC-4: Given pop_max_pct=None
    When SMS formatiert wird
    Then kein Absturz, PR– oder kein PR-Token (kein Fehlerwert)
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _make_segment(pop_max_pct=None, precip_sum_mm=2.0)
    result = SMSTripFormatter().format_sms(
        [seg], stage_name="E1", report_type="evening", tz=ZoneInfo("UTC"),
    )
    assert isinstance(result, str) and len(result) > 0


def test_ac4_telegram_no_crash_when_pop_max_pct_is_none():
    """
    AC-4: Given pop_max_pct=None und rain_probability konfiguriert
    When render_narrow("telegram", ...) aufgerufen
    Then kein Absturz
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=None, precip_sum_mm=1.0)
    dc = _make_dc(["temperature", "wind", "rain_probability"])
    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[[]],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# AC-5: Keine extra Metriken → keine Detail-Zeile in Telegram
# ---------------------------------------------------------------------------

def test_ac5_telegram_no_detail_line_when_only_temp_and_wind():
    """
    AC-5: Given display_config nur mit temperature + wind
    When render_narrow("telegram", ...) aufgerufen
    Then keine Detail-Zeile (Rain%, Gust, etc. fehlen)
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=40, precip_sum_mm=1.5)
    dc = _make_dc(["temperature", "wind"])
    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[[]],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert "Rain%" not in result, f"Unerwartetes 'Rain%' in Output:\n{result}"
    assert "Gust" not in result, f"Unerwartetes 'Gust' in Output:\n{result}"


# ---------------------------------------------------------------------------
# AC-6: Kopfzeile zeigt weiter Regen-Kategorie (kein Regressionsverhalten)
# ---------------------------------------------------------------------------

def test_ac6_telegram_header_still_shows_regen_category():
    """
    AC-6: Given precip_sum_mm=3.0, pop_max_pct=0
    When render_narrow("telegram", ...) aufgerufen
    Then enthält Kopfzeile 'Regen' (bisheriges Verhalten unverändert)
    """
    from src.output.renderers.narrow import render_narrow

    seg = _make_segment(pop_max_pct=0, precip_sum_mm=3.0)
    dc = _make_dc(["temperature", "wind"])
    result = render_narrow(
        "telegram",
        segments=[seg],
        seg_tables=[[]],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert "Regen" in result, f"'Regen' fehlt in Kopfzeile:\n{result}"
