"""
TDD RED — Bug #424 + #423: E-Mail Confidence-Darstellung

SPEC: docs/specs/modules/bug_424_423_email_confidence_display.md v1.0

AC-1: Kein „Sicherheit"-Spalte in WeatherTemplate „wandern"
AC-2: Kein „Sicherheit"-Spalte in WeatherTemplate „alpen-trekking"
AC-3: build_confidence_hint() → „weniger verlässlich", kein °C
AC-4: build_confidence_hint() → None wenn alle confidence ≥ 60 (bereits grün, bleibt unverändert)

PHASE: TDD RED — alle Tests MÜSSEN SCHEITERN mit aktuellem Code.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# AC-1: WeatherTemplate „wandern" enthält kein „confidence"
# ---------------------------------------------------------------------------

class TestNoConfidenceInWandernTemplate:
    """AC-1: Template wandern darf confidence nicht aktivieren."""

    def test_wandern_template_does_not_contain_confidence(self):
        """AC-1: WEATHER_TEMPLATES['wandern']['metrics'] darf 'confidence' nicht enthalten."""
        from app.metric_catalog import WEATHER_TEMPLATES

        assert "confidence" not in WEATHER_TEMPLATES["wandern"]["metrics"], (
            "Bug #424: 'confidence' ist noch in Template 'wandern' — "
            "Spalte 'Sicherheit' erscheint ungewollt in der E-Mail-Tabelle"
        )

    def test_wandern_display_config_confidence_disabled(self):
        """AC-1: UnifiedWeatherDisplayConfig für wandern hat confidence disabled."""
        from app.metric_catalog import WEATHER_TEMPLATES

        metrics = WEATHER_TEMPLATES["wandern"]["metrics"]
        enabled_ids = set(metrics)
        assert "confidence" not in enabled_ids, (
            "Bug #424: 'confidence' ist enabled in wandern-DisplayConfig"
        )


# ---------------------------------------------------------------------------
# AC-2: WeatherTemplate „alpen-trekking" enthält kein „confidence"
# ---------------------------------------------------------------------------

class TestNoConfidenceInAlpenTrekkingTemplate:
    """AC-2: Template alpen-trekking darf confidence nicht aktivieren."""

    def test_alpen_trekking_template_does_not_contain_confidence(self):
        """AC-2: WEATHER_TEMPLATES['alpen-trekking']['metrics'] darf 'confidence' nicht enthalten."""
        from app.metric_catalog import WEATHER_TEMPLATES

        assert "confidence" not in WEATHER_TEMPLATES["alpen-trekking"]["metrics"], (
            "Bug #424: 'confidence' ist noch in Template 'alpen-trekking' — "
            "Spalte 'Sicherheit' erscheint ungewollt in der E-Mail-Tabelle"
        )

    def test_all_templates_confidence_removed(self):
        """AC-1+AC-2: Kein WeatherTemplate enthält 'confidence'."""
        from app.metric_catalog import WEATHER_TEMPLATES

        violating = [
            tid for tid, tdata in WEATHER_TEMPLATES.items()
            if "confidence" in tdata["metrics"]
        ]
        assert violating == [], (
            f"Bug #424: Diese Templates enthalten noch 'confidence': {violating} — "
            f"Spalte 'Sicherheit' erscheint ungewollt in der E-Mail"
        )


# ---------------------------------------------------------------------------
# AC-3: build_confidence_hint() — kein technischer °C-Wert im Text
# ---------------------------------------------------------------------------

def _make_segment_with_confidence(confidence_pct, spread_t2m_k, hours_offset, base_ts):
    """Hilfsfunktion: SegmentWeatherData mit einem Datenpunkt."""
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    now = base_ts
    dp = ForecastDataPoint(
        ts=now + timedelta(hours=hours_offset),
        t2m_c=15.0,
        confidence_pct=confidence_pct,
        spread_t2m_k=spread_t2m_k,
        spread_precip_mm=0.5,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="ecmwf_ifs", grid_res_km=40.0),
        data=[dp],
    )
    point = GPXPoint(lat=47.8, lon=13.0, elevation_m=800, distance_from_start_km=0.0)
    seg = TripSegment(
        segment_id=1, start_point=point, end_point=point,
        start_time=now, end_time=now + timedelta(hours=2),
        duration_hours=2.0, distance_km=4.0, ascent_m=200, descent_m=100,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=now, provider="openmeteo",
    )


class TestConfidenceHintSimplified:
    """AC-3: build_confidence_hint() liefert vereinfachten Text ohne technische °C-Klammer."""

    def test_low_confidence_hint_says_weniger_verlaesslich(self):
        """AC-3: confidence=45 at T+48h → Hint enthält 'weniger verlässlich'."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            _make_segment_with_confidence(
                confidence_pct=45,
                spread_t2m_k=4.0,
                hours_offset=48,
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)

        assert hint is not None, "Hint sollte bei confidence=45 erscheinen"
        assert "weniger verlässlich" in hint, (
            f"Bug #423: Hint muss 'weniger verlässlich' enthalten, enthält aber: {hint!r}"
        )

    def test_low_confidence_hint_has_no_celsius_spread(self):
        """AC-3: Der Hinweis-Text enthält keine technische °C-Klammer."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            _make_segment_with_confidence(
                confidence_pct=45,
                spread_t2m_k=4.0,
                hours_offset=48,
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)

        assert hint is not None, "Hint sollte bei confidence=45 erscheinen"
        assert "°C" not in hint, (
            f"Bug #423: Hint darf keine technische Spreizungs-Angabe '°C' enthalten: {hint!r}"
        )
        assert "Spreizung" not in hint, (
            f"Bug #423: Hint darf 'Spreizung' nicht enthalten: {hint!r}"
        )

    def test_low_confidence_hint_contains_weekday(self):
        """AC-3: Hint nennt weiterhin den Wochentag (Regression-Check)."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            _make_segment_with_confidence(
                confidence_pct=45,
                spread_t2m_k=2.0,
                hours_offset=48,  # T+48h from Monday = Wednesday
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)

        assert hint is not None
        assert "Mittwoch" in hint, (
            f"Hint muss Wochentag 'Mittwoch' enthalten: {hint!r}"
        )
