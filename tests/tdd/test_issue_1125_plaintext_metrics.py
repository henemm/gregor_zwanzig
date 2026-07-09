"""
TDD: Plain-Text-Teil der Compare-Mail filtert enabled_metrics (Issue #1125).

Vorbestehender Bug (galt schon vor #1105): render_comparison_text() ignorierte
enabled_metrics komplett, waehrend der HTML-Renderer
(output.renderers.email.compare_html._visible_metrics) korrekt filtert ->
HTML und Klartext-Teil derselben Mail widersprachen sich.

Diese Tests rufen render_comparison_text() als reine Funktion mit echten
ComparisonResult/LocationResult-Objekten auf (kein Mock/patch, CLAUDE.md).

SPEC: docs/specs/fast/fix-1125-plaintext-metrics.md

AC-Zuordnung:
- AC-1: enabled_metrics={"temp_max"} -> nur Temp-max-Zeile sichtbar, die
  anderen fuenf Uebersichts-Zeilen fehlen.
- AC-2: enabled_metrics=None -> alle sechs Uebersichts-Zeilen sichtbar
  (Default-Rueckwaertskompatibilitaet).
- AC-3: amtliche Warn-Zeile bleibt bei gefiltertem enabled_metrics immer
  sichtbar.
"""
from __future__ import annotations

from datetime import date, datetime

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text
from services.official_alerts.models import OfficialAlert


def _loc(loc_id: str, name: str, elevation_m: int = 200) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=45.9, lon=6.9, elevation_m=elevation_m)


def _dp(hour: int, t2m_c: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=t2m_c,
        wind_chill_c=t2m_c - 2,
        wind10m_kmh=10.0,
        gust_kmh=18.0,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        uv_index=3.0,
    )


def _make_result(with_alert: bool = False) -> ComparisonResult:
    """Chamonix + Nizza, alle sechs Uebersichts-Metriken befuellt."""
    alerts = []
    if with_alert:
        alerts = [
            OfficialAlert(
                source="test-1125", hazard="thunderstorm", level=3,
                label="Gewitterwarnung Stufe Orange",
            )
        ]
    chamonix = LocationResult(
        location=_loc("chamonix", "Chamonix", elevation_m=1035),
        score=60,
        snow_depth_cm=45.0,
        snow_new_cm=8.0,
        temp_max=12.0,
        wind_max=18.0,
        sunny_hours=5.0,
        cloud_avg=50,
        official_alerts=alerts,
        hourly_data=[_dp(9, 8.0), _dp(12, 12.0), _dp(15, 10.0)],
    )
    nizza = LocationResult(
        location=_loc("nizza", "Nizza", elevation_m=10),
        score=55,
        snow_depth_cm=None,
        snow_new_cm=None,
        temp_max=29.0,
        wind_max=15.0,
        sunny_hours=8.0,
        cloud_avg=10,
        official_alerts=[],
        hourly_data=[_dp(9, 24.0), _dp(12, 29.0), _dp(15, 27.0)],
    )
    return ComparisonResult(
        locations=[chamonix, nizza],
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


class TestAC1FilteredMetricsHideOtherLines:
    def test_ac1_only_temp_max_visible_when_filtered(self):
        result = _make_result()
        text_body = render_comparison_text(result, enabled_metrics={"temp_max"})

        assert "Temp max" in text_body, f"Temp-max-Zeile muss sichtbar sein, Text:\n{text_body}"
        assert "Wind:" not in text_body, f"Wind-Zeile darf nicht erscheinen, Text:\n{text_body}"
        assert "Sonne:" not in text_body, f"Sonne-Zeile darf nicht erscheinen, Text:\n{text_body}"
        assert "Wolken:" not in text_body, f"Wolken-Zeile darf nicht erscheinen, Text:\n{text_body}"
        assert "Schneehöhe:" not in text_body, f"Schneehöhe-Zeile darf nicht erscheinen, Text:\n{text_body}"
        assert "Neuschnee:" not in text_body, f"Neuschnee-Zeile darf nicht erscheinen, Text:\n{text_body}"


class TestAC2NoneShowsAllSixLines:
    def test_ac2_enabled_metrics_none_shows_all_six_lines(self):
        result = _make_result()
        text_body = render_comparison_text(result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics=None)

        for label in ("Temp max", "Wind:", "Sonne:", "Wolken:", "Schneehöhe:", "Neuschnee:"):
            assert label in text_body, f"'{label}'-Zeile muss bei enabled_metrics=None sichtbar sein, Text:\n{text_body}"


class TestAC3OfficialAlertsAlwaysVisible:
    def test_ac3_alert_line_visible_despite_filter(self):
        result = _make_result(with_alert=True)
        text_body = render_comparison_text(result, enabled_metrics={"temp_max"})

        assert "⚠️" in text_body, f"Amtliche Warn-Zeile muss trotz Filter sichtbar sein, Text:\n{text_body}"
        assert "Gewitterwarnung Stufe Orange" in text_body, (
            f"Warn-Label muss im Klartext erscheinen, Text:\n{text_body}"
        )
