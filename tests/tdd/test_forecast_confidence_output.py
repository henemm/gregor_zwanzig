"""
TDD RED: Forecast Confidence Output (Issue #121, Workflow 2)

SPEC: docs/specs/modules/issue_121_confidence_output.md v1.0
PARENT: docs/specs/modules/forecast_confidence.md (Master)

Tests for AC-9 to AC-14. Backend (AC-1 to AC-8) is already on production.

PHASE: TDD RED — all tests MUST FAIL with current code.

No mocks. E-Mail-E2E uses real Gmail SMTP + IMAP via TestRealGmailE2E pattern.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest


# --- AC-9: Symbol Mapping & Token Builder ---


class TestConfidenceSymbolMapping:
    """AC-9: C-Token ist aus dem SMS-Format entfernt (Bug #869)."""

    def test_symbol_high_confidence_plus(self):
        # _confidence_symbol wurde entfernt (Bug #869 — C-Token aus SMS raus)
        from output.tokens.builder import build_token_line
        from output.tokens.dto import DailyForecast, NormalizedForecast
        fc = NormalizedForecast(days=(DailyForecast(confidence_pct_min=80),))
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0  # C-Token nicht mehr emittiert

    def test_symbol_medium_confidence_tilde(self):
        from output.tokens.builder import build_token_line
        from output.tokens.dto import DailyForecast, NormalizedForecast
        fc = NormalizedForecast(days=(DailyForecast(confidence_pct_min=60),))
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_symbol_low_confidence_question(self):
        from output.tokens.builder import build_token_line
        from output.tokens.dto import DailyForecast, NormalizedForecast
        fc = NormalizedForecast(days=(DailyForecast(confidence_pct_min=35),))
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_symbol_none_yields_none(self):
        from output.tokens.builder import build_token_line
        from output.tokens.dto import DailyForecast, NormalizedForecast
        fc = NormalizedForecast(days=(DailyForecast(confidence_pct_min=None),))
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0


class TestTokenBuilderConfidenceToken:
    """AC-9: C-Token wurde aus Builder entfernt (Bug #869)."""

    def _build_forecast(self, conf):
        from output.tokens.dto import DailyForecast, NormalizedForecast

        day = DailyForecast(
            temp_min_c=10.0,
            temp_max_c=20.0,
            confidence_pct_min=conf,
        )
        return NormalizedForecast(days=(day,))

    def test_confidence_80_yields_C_plus_token(self):
        """Bug #869: C-Token wird nicht mehr emittiert — kein C+ in SMS."""
        from output.tokens.builder import build_token_line

        fc = self._build_forecast(80)
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_confidence_60_yields_C_tilde_token(self):
        """Bug #869: C-Token wird nicht mehr emittiert."""
        from output.tokens.builder import build_token_line

        fc = self._build_forecast(60)
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_confidence_35_yields_C_question_token(self):
        """Bug #869: C-Token wird nicht mehr emittiert."""
        from output.tokens.builder import build_token_line

        fc = self._build_forecast(35)
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_confidence_none_yields_no_C_token(self):
        from output.tokens.builder import build_token_line

        fc = self._build_forecast(None)
        line = build_token_line(fc, None, report_type="morning", stage_name="Stage")
        c_tokens = [t for t in line.tokens if t.symbol == "C"]
        assert len(c_tokens) == 0

    def test_C_token_renders_with_symbol(self):
        from output.tokens.dto import Token

        token = Token(symbol="C", value="+", category="forecast", priority=4)
        assert token.render() == "C+"


# --- AC-10: SMS Length Stays ≤ 160 ---


class TestSMSLengthWithConfidence:
    """AC-10: render() with max_length=160 still respects limit."""

    def test_seven_day_trip_with_confidence_within_160_chars(self):
        """Even a 7-day trip with confidence tokens stays within 160."""
        from output.tokens.builder import build_token_line
        from output.tokens.dto import DailyForecast, HourlyValue, NormalizedForecast

        days = tuple(
            DailyForecast(
                temp_min_c=8.0 + i,
                temp_max_c=22.0 + i,
                rain_hourly=(HourlyValue(12, 1.0),),
                wind_hourly=(HourlyValue(12, 15.0),),
                gust_hourly=(HourlyValue(12, 25.0),),
                confidence_pct_min=80 - i * 5,  # decreasing confidence
            )
            for i in range(7)
        )
        fc = NormalizedForecast(days=days)
        line = build_token_line(fc, None, report_type="morning", stage_name="LongTrip")
        rendered = line.render(max_length=160)
        assert len(rendered) <= 160, (
            f"SMS exceeds 160 chars: {len(rendered)} — {rendered!r}"
        )


# --- AC-11: E-Mail Column via MetricCatalog ---


class TestEmailColumnFromMetricCatalog:
    """AC-11: MetricCatalog drives confidence column automatically."""

    def test_metric_catalog_has_confidence_entry(self):
        from app.metric_catalog import get_metric

        m = get_metric("confidence")
        assert m.dp_field == "confidence_pct"
        assert m.col_key == "confidence"
        assert m.col_label == "Conf"
        assert m.unit == "%"

    def test_get_col_defs_includes_confidence(self):
        from app.metric_catalog import get_col_defs

        defs = get_col_defs()
        col_keys = [d[0] for d in defs]
        assert "confidence" in col_keys

    def test_visible_cols_picks_confidence_when_in_row(self):
        from output.renderers.email.helpers import visible_cols

        rows = [{"time": "12", "confidence": 85, "wind": 10}]
        cols = visible_cols(rows)
        col_keys = [c[0] for c in cols]
        assert "confidence" in col_keys
        # Label muss "Conf" sein
        conf_label = next(label for key, label in cols if key == "confidence")
        assert conf_label == "Conf"


# --- AC-12 & AC-13: Confidence Hint Generator ---


class TestConfidenceHintGenerator:
    """AC-12 (hint present) and AC-13 (hint absent)."""

    def _make_segment(self, confidences_by_hour, spreads_by_hour=None, base_ts=None):
        """Build SegmentWeatherData with custom hourly confidence values.

        confidences_by_hour: list of (hours_offset_from_now, confidence_pct, spread_t2m_k)
        """
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

        now = base_ts or datetime.now(timezone.utc)
        dps = []
        for offset_h, conf, spread in confidences_by_hour:
            dp = ForecastDataPoint(
                ts=now + timedelta(hours=offset_h),
                t2m_c=15.0,
                confidence_pct=conf,
                spread_t2m_k=spread,
                spread_precip_mm=0.5,
            )
            dps.append(dp)
        ts = NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="ecmwf_ifs", grid_res_km=40.0),
            data=dps,
        )
        point = GPXPoint(lat=47.8, lon=13.0, elevation_m=800, distance_from_start_km=0.0)
        seg = TripSegment(
            segment_id=1, start_point=point, end_point=point,
            start_time=now, end_time=now + timedelta(hours=len(dps)),
            duration_hours=float(len(dps)), distance_km=4.0, ascent_m=200, descent_m=100,
        )
        return SegmentWeatherData(
            segment=seg, timeseries=ts,
            aggregated=SegmentWeatherSummary(),
            fetched_at=now, provider="openmeteo",
        )

    def test_low_confidence_on_wednesday_produces_hint_with_weekday(self):
        """AC-12: confidence=45 at T+48h (Wednesday if today is Monday) → hint mentions weekday + °C."""
        from output.renderers.email.helpers import build_confidence_hint

        # Use a known Monday as anchor (2026-05-18 is Monday)
        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        # T+48h from Monday 08:00 = Wednesday 08:00
        segments = [
            self._make_segment(
                confidences_by_hour=[
                    (0, 90, 0.5),    # Mo, sicher
                    (24, 85, 0.6),   # Di, sicher
                    (48, 45, 4.0),   # Mi, unsicher (Spread 4°C)
                    (72, 80, 1.0),   # Do, sicher (but outside window)
                ],
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)
        assert hint is not None, "Hint should fire for confidence=45 at T+48h"
        assert "Mittwoch" in hint, f"Hint must mention 'Mittwoch': {hint}"
        assert "weniger verlässlich" in hint, f"Hint must say 'weniger verlässlich': {hint}"

    def test_high_confidence_in_72h_window_no_hint(self):
        """AC-13: all confidence ≥ 60 in T+0-72h → no hint."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            self._make_segment(
                confidences_by_hour=[
                    (0, 90, 0.5),
                    (24, 80, 1.0),
                    (48, 65, 1.5),  # boundary — still ≥ 60
                    (60, 75, 0.8),
                ],
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)
        assert hint is None, f"Hint must not fire when all confidence ≥ 60: got {hint!r}"

    def test_low_confidence_only_after_72h_no_hint(self):
        """Low confidence at T+96h is normal — no hint."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            self._make_segment(
                confidences_by_hour=[
                    (0, 90, 0.5),
                    (24, 85, 0.6),
                    (48, 80, 0.8),
                    (96, 35, 5.0),  # very uncertain — but OUTSIDE 72h
                ],
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)
        assert hint is None, f"Hint must ignore T+96h: got {hint!r}"

    def test_no_confidence_data_no_hint(self):
        """All confidence_pct=None → no hint."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [
            self._make_segment(
                confidences_by_hour=[
                    (0, None, None),
                    (24, None, None),
                ],
                base_ts=monday,
            )
        ]
        hint = build_confidence_hint(segments, now=monday, tz=tz)
        assert hint is None


# --- AC-14: Real Gmail E2E ---


@pytest.mark.email
@pytest.mark.skip(
    reason="AC-14 is a manual pre-deploy E2E check, not automated. "
    "Procedure: enable 'confidence' metric in a Gmail-test-user template, "
    "trigger a trip-report send, open the received mail, verify (a) column "
    "'Sicherheit' appears in the hourly table and (b) the confidence hint "
    "text 'Ab <Wochentag> nimmt die Unsicherheit zu' appears in the body "
    "for a trip with low-confidence days within T+0-72h."
)
class TestRealGmailE2EConfidence:
    """AC-14: Real Gmail SMTP + IMAP roundtrip — manual procedure only."""

    def test_email_contains_confidence_column_and_hint(self):
        pass
