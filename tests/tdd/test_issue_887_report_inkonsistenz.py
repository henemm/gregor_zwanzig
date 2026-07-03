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

@pytest.mark.skip(
    reason=(
        "OBSOLET (Issue #1001): _tg_extra_detail_line() (col_label-Detail-Zeile) "
        "wurde als Teil des Breaking Replace fuer render_narrow() entfernt "
        "(Bug #994 wird durch die Entfernung miterledigt, siehe Spec-Dependency "
        "'fix_887_report_inkonsistenz.md | abgeloest'). Telegram verwendet jetzt "
        "compact_label ('P%') als Single-Source ueberall (Tabellen-Header UND "
        "Kurzuebersicht-Bubble) statt col_label ('Rain%') — bewusste PO-Entscheidung "
        "in feat_1001_telegram_redesign.md Dependencies-Tabelle."
    )
)
def test_ac2_telegram_shows_rain_pct_label_when_configured():
    """AC-2 (superseded): siehe skip-reason."""


@pytest.mark.skip(
    reason=(
        "OBSOLET (Issue #1001): Gegenteilige Anforderung — #1001 verwendet jetzt "
        "bewusst compact_label ('P%') statt col_label ('Rain%'), siehe Dependency "
        "'metric_catalog.compact_label ... bewusst statt SMS_SYMBOL_BY_METRIC'."
    )
)
def test_ac2_telegram_uses_col_label_not_compact_label():
    """AC-2 (superseded): siehe skip-reason."""


# ---------------------------------------------------------------------------
# AC-3: Telegram Detail-Zeile mit Rain% UND Gust wenn beide konfiguriert
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason=(
        "OBSOLET (Issue #1001): col_label-Detail-Zeile ('Rain%'/'Gust') existiert "
        "nicht mehr — durch die Kurzuebersicht-Bubble mit compact_label ('P%'/'G') "
        "ersetzt. Aequivalenter Nachweis 'beide Metriken erscheinen' liefert "
        "test_issue_1001_telegram_bubbles.py::TestAC3KurzuebersichtAlleMetriken."
    )
)
def test_ac3_telegram_shows_rain_and_gust_when_both_configured():
    """AC-3 (superseded): siehe skip-reason."""


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
    When render_telegram_bubbles(...) aufgerufen wird (Issue #1001)
    Then kein Absturz
    """
    from src.output.renderers.narrow import render_telegram_bubbles

    seg = _make_segment(pop_max_pct=None, precip_sum_mm=1.0)
    dc = _make_dc(["temperature", "wind", "rain_probability"])
    bubbles = render_telegram_bubbles(
        segments=[seg],
        seg_tables=[[]],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    assert isinstance(bubbles, list) and bubbles


# ---------------------------------------------------------------------------
# AC-5: Keine extra Metriken → keine Detail-Zeile in Telegram
# ---------------------------------------------------------------------------

def test_ac5_telegram_no_detail_line_when_only_temp_and_wind():
    """
    AC-5: Given display_config nur mit temperature + wind
    When render_telegram_bubbles(...) aufgerufen wird (Issue #1001)
    Then keine col_label-Detail-Zeile (Rain%, Gust, etc. fehlen weiterhin —
    #1001 verwendet ohnehin nur noch compact_label, nie col_label)
    """
    from src.output.renderers.narrow import render_telegram_bubbles

    seg = _make_segment(pop_max_pct=40, precip_sum_mm=1.5)
    dc = _make_dc(["temperature", "wind"])
    bubbles = render_telegram_bubbles(
        segments=[seg],
        seg_tables=[[]],
        dc=dc,
        report_type="evening",
        tz=ZoneInfo("UTC"),
    )
    result = "\n".join(b.text for b in bubbles)
    assert "Rain%" not in result, f"Unerwartetes 'Rain%' in Output:\n{result}"
    assert "Gust" not in result, f"Unerwartetes 'Gust' in Output:\n{result}"


# ---------------------------------------------------------------------------
# AC-6: Kopfzeile zeigt weiter Regen-Kategorie (kein Regressionsverhalten)
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason=(
        "OBSOLET (Issue #1001): Die textuelle Regen-Kategorie ('Regen'/'trocken'/"
        "'etwas Regen') stammte aus _tg_segment_line(), die als Teil des Breaking "
        "Replace entfernt wurde. #1001 zeigt Niederschlag stattdessen als "
        "numerischen Wert (compact_label 'R', Min-Max-Range) in der "
        "Kurzuebersicht-Bubble und als Tabellenspalte — keine Wort-Kategorie mehr."
    )
)
def test_ac6_telegram_header_still_shows_regen_category():
    """AC-6 (superseded): siehe skip-reason."""
