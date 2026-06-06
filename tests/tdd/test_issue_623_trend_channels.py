"""
TDD tests for Issue #623 — Mehrtages-Trend in Telegram + SMS + Renderer-Konsolidierung.

RED phase: all tests fail until implementation is complete.

SPEC: docs/specs/modules/issue_623_trend_telegram_sms.md AC-1..AC-9
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.
"""
from __future__ import annotations

import pytest
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _trend_stage(
    weekday="Mo", name="Sóller → Tossals Verds",
    temp_lo=8, temp_hi=16, precip_mm=3.0,
    wind_dir="W", wind_kmh=20, thunder="NONE", note=None,
):
    return dict(
        weekday=weekday, name=name,
        temp_lo=temp_lo, temp_hi=temp_hi, precip_mm=precip_mm,
        wind_dir=wind_dir, wind_kmh=wind_kmh, thunder=thunder, note=note,
    )


def _common_render_kwargs():
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    kw = _common_kwargs()
    tl = _make_token_line()
    return kw, tl


def _render_html(trend, *, sent_at=None):
    kw, tl = _common_render_kwargs()
    from src.output.renderers.email.html import render_html
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
        sent_at=sent_at,
    )


def _render_plain(trend):
    kw, tl = _common_render_kwargs()
    from src.output.renderers.email.plain import render_plain
    return render_plain(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
    )


def _render_narrow(channel, trend=None):
    kw, _ = _common_render_kwargs()
    from src.output.renderers.narrow import render_narrow
    return render_narrow(
        channel,
        segments=kw["segments"],
        seg_tables=kw["seg_tables"],
        dc=kw["display_config"],
        report_type="evening",
        tz=ZoneInfo("Europe/Berlin"),
        trip_name="Test-Trip",
        friendly_keys=kw["friendly_keys"],
        multi_day_trend=trend,
    )


# ---------------------------------------------------------------------------
# AC-1: format_trend_tokens — single source of truth for trend semantics
# ---------------------------------------------------------------------------

class TestFormatTrendTokens:
    """AC-1: One shared function decides all trend semantics."""

    def test_function_importable(self):
        """Given helpers module, When format_trend_tokens imported, Then no ImportError."""
        from src.output.renderers.email.helpers import format_trend_tokens  # noqa

    def test_temp_both_lo_hi(self):
        """Given temp_lo=8, temp_hi=16, When tokens formed, Then temp_str='8–16°C'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(temp_lo=8, temp_hi=16))
        assert t["temp_str"] == "8–16°C"

    def test_temp_hi_only(self):
        """Given temp_lo=None, temp_hi=16, When tokens, Then '16°C'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(temp_lo=None, temp_hi=16))
        assert t["temp_str"] == "16°C"

    def test_temp_none(self):
        """Given both None, When tokens, Then '–'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(temp_lo=None, temp_hi=None))
        assert t["temp_str"] == "–"

    def test_precip_zero_is_dash(self):
        """Given precip_mm=0, When tokens, Then precip_str='–'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(precip_mm=0))
        assert t["precip_str"] == "–"

    def test_precip_positive(self):
        """Given precip_mm=3.0, When tokens, Then precip_str='3mm' (includes value)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(precip_mm=3.0))
        assert "3" in t["precip_str"]

    def test_precip_highlight_above_1mm(self):
        """Given precip_mm=2.0 (>1), When tokens, Then precip_highlight=True."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(precip_mm=2.0))
        assert t["precip_highlight"] is True

    def test_precip_no_highlight_below_1mm(self):
        """Given precip_mm=0.5 (<=1), When tokens, Then precip_highlight=False."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(precip_mm=0.5))
        assert t["precip_highlight"] is False

    def test_wind_highlight_above_30(self):
        """Given wind_kmh=35 (>30), When tokens, Then wind_highlight=True."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(wind_kmh=35))
        assert t["wind_highlight"] is True

    def test_wind_no_highlight_at_30(self):
        """Given wind_kmh=30 (<=30), When tokens, Then wind_highlight=False."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(wind_kmh=30))
        assert t["wind_highlight"] is False

    def test_wind_risk_flag_at_50(self):
        """Given wind_kmh=50 (>=50), When tokens, Then wind_risk=True."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(wind_kmh=50))
        assert t["wind_risk"] is True

    def test_wind_no_risk_below_50(self):
        """Given wind_kmh=49, When tokens, Then wind_risk=False."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(wind_kmh=49))
        assert t["wind_risk"] is False

    # Thunder tokens
    def test_thunder_none_word(self):
        """Given thunder=NONE, When tokens, Then thunder_word='kein'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="NONE"))
        assert t["thunder_word"] == "kein"

    def test_thunder_med_word(self):
        """Given thunder=MED, When tokens, Then thunder_word='MED'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="MED"))
        assert t["thunder_word"] == "MED"

    def test_thunder_high_word(self):
        """Given thunder=HIGH, When tokens, Then thunder_word='HIGH'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="HIGH"))
        assert t["thunder_word"] == "HIGH"

    def test_thunder_none_html_sq_color(self):
        """Given NONE, When tokens, Then sq_color=#9a958a."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="NONE"))
        assert t["thunder_sq_color"] == "#9a958a"

    def test_thunder_med_html_sq_color(self):
        """Given MED, When tokens, Then sq_color=#c08a1a."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="MED"))
        assert t["thunder_sq_color"] == "#c08a1a"

    def test_thunder_high_html_sq_color(self):
        """Given HIGH, When tokens, Then sq_color=#a83232."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="HIGH"))
        assert t["thunder_sq_color"] == "#a83232"

    def test_thunder_none_word_color(self):
        """Given NONE, When tokens, Then word_color=#6b675c."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="NONE"))
        assert t["thunder_word_color"] == "#6b675c"

    def test_thunder_med_word_color(self):
        """Given MED, When tokens, Then word_color=#8c3e1a."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="MED"))
        assert t["thunder_word_color"] == "#8c3e1a"

    def test_thunder_high_word_color(self):
        """Given HIGH, When tokens, Then word_color=#a83232."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="HIGH"))
        assert t["thunder_word_color"] == "#a83232"

    def test_thunder_none_plain_token(self):
        """Given NONE, When tokens, Then plain_token='⚡–'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="NONE"))
        assert t["thunder_plain"] == "⚡–"

    def test_thunder_med_plain_token(self):
        """Given MED, When tokens, Then plain_token='⚡MED'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="MED"))
        assert t["thunder_plain"] == "⚡MED"

    def test_thunder_high_plain_token(self):
        """Given HIGH, When tokens, Then plain_token='⚡HIGH'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="HIGH"))
        assert t["thunder_plain"] == "⚡HIGH"

    def test_thunder_none_sms_token_absent(self):
        """Given NONE, When tokens, Then sms_token is None/empty (no 'GEW-')."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="NONE"))
        assert not t.get("thunder_sms")

    def test_thunder_med_sms_token(self):
        """Given MED, When tokens, Then sms_token='GEW-MED'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="MED"))
        assert t["thunder_sms"] == "GEW-MED"

    def test_thunder_high_sms_token(self):
        """Given HIGH, When tokens, Then sms_token='GEW-HIGH'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        t = format_trend_tokens(_trend_stage(thunder="HIGH"))
        assert t["thunder_sms"] == "GEW-HIGH"

    def test_no_low_level(self):
        """AC-9: 'LOW' must not appear anywhere in format_trend_tokens output."""
        from src.output.renderers.email.helpers import format_trend_tokens
        for thunder in ("NONE", "MED", "HIGH"):
            t = format_trend_tokens(_trend_stage(thunder=thunder))
            for v in t.values():
                if isinstance(v, str):
                    assert "LOW" not in v, f"thunder={thunder} produced 'LOW' in {v}"


# ---------------------------------------------------------------------------
# AC-2: E-Mail-HTML and Plain unchanged after token refactoring
# ---------------------------------------------------------------------------

class TestEmailTrendUnchanged:
    """AC-2: Refactoring to format_trend_tokens must not change rendered output."""

    def test_html_contains_temp(self):
        """Given stage with 8–16°C, When HTML rendered, Then contains temp values."""
        html = _render_html([_trend_stage()])
        assert "8" in html and "16" in html

    def test_html_contains_precip_dash_for_zero(self):
        """Given precip_mm=0, When HTML rendered, Then shows ndash/dash, not '0'."""
        html = _render_html([_trend_stage(precip_mm=0)])
        assert "&ndash;" in html or "–" in html

    def test_html_precip_highlight_color_above_1mm(self):
        """Given precip_mm=8, When HTML, Then contains blue color code for highlight."""
        html = _render_html([_trend_stage(precip_mm=8.0)])
        assert "#2c5a8c" in html

    def test_html_wind_highlight_above_30(self):
        """Given wind_kmh=35, When HTML, Then contains orange highlight color."""
        html = _render_html([_trend_stage(wind_kmh=35)])
        assert "#c45a2a" in html

    def test_html_thunder_none_color(self):
        """Given NONE, When HTML, Then contains grey square color #9a958a."""
        html = _render_html([_trend_stage(thunder="NONE")])
        assert "#9a958a" in html

    def test_html_thunder_med_sq_color(self):
        """Given MED, When HTML, Then contains MED sq color #c08a1a."""
        html = _render_html([_trend_stage(thunder="MED")])
        assert "#c08a1a" in html

    def test_html_nächste_etappen_heading(self):
        """Given trend, When HTML, Then contains 'Nächste Etappen' heading."""
        html = _render_html([_trend_stage()])
        assert "Nächste Etappen" in html

    def test_plain_contains_thunder_token_none(self):
        """Given NONE, When plain rendered, Then contains '⚡–'."""
        plain = _render_plain([_trend_stage(thunder="NONE")])
        assert "⚡–" in plain

    def test_plain_contains_thunder_token_med(self):
        """Given MED, When plain rendered, Then contains '⚡MED'."""
        plain = _render_plain([_trend_stage(thunder="MED")])
        assert "⚡MED" in plain

    def test_plain_nächste_etappen_heading(self):
        """Given trend, When plain rendered, Then has 'Nächste Etappen'."""
        plain = _render_plain([_trend_stage()])
        assert "Nächste Etappen" in plain

    def test_plain_weekday_in_line(self):
        """Given weekday='Mo', When plain rendered, Then 'Mo' appears in line."""
        plain = _render_plain([_trend_stage(weekday="Mo")])
        assert "Mo" in plain

    def test_plain_temp_str(self):
        """Given 8–16°C, When plain rendered, Then '8–16°C' in output."""
        plain = _render_plain([_trend_stage()])
        assert "8–16°C" in plain


# ---------------------------------------------------------------------------
# AC-3: Telegram trend block
# ---------------------------------------------------------------------------

class TestTelegramTrend:
    """AC-3: Telegram body contains trend block 'Nächste Etappen'."""

    def test_telegram_with_trend_has_heading(self):
        """Given telegram + trend, When rendered, Then 'Nächste Etappen' present."""
        body = _render_narrow("telegram", trend=[_trend_stage()])
        assert "Nächste Etappen" in body

    def test_telegram_trend_contains_weekday(self):
        """Given trend with weekday='Mo', When telegram, Then 'Mo' in body."""
        body = _render_narrow("telegram", trend=[_trend_stage(weekday="Mo")])
        assert "Mo" in body

    def test_telegram_trend_contains_temp(self):
        """Given 8–16°C stage, When telegram, Then temp values present."""
        body = _render_narrow("telegram", trend=[_trend_stage(temp_lo=8, temp_hi=16)])
        assert "8" in body and "16" in body

    def test_telegram_trend_contains_thunder_plain(self):
        """Given NONE thunder, When telegram, Then '⚡–' token present."""
        body = _render_narrow("telegram", trend=[_trend_stage(thunder="NONE")])
        assert "⚡–" in body

    def test_telegram_trend_no_trend_no_heading(self):
        """AC-7: Given no trend, When telegram, Then no 'Nächste Etappen'."""
        body = _render_narrow("telegram", trend=None)
        assert "Nächste Etappen" not in body

    def test_telegram_trend_line_width(self):
        """Given trend, When telegram, Then all lines ≤40 chars."""
        body = _render_narrow("telegram", trend=[_trend_stage()])
        for line in body.split("\n"):
            assert len(line) <= 40, f"Line too long ({len(line)}): {line!r}"

    def test_telegram_trend_note_indented(self):
        """Given note, When telegram, Then indented note line present."""
        body = _render_narrow("telegram", trend=[_trend_stage(note="Gewitter möglich.")])
        assert "↳" in body

    def test_telegram_trend_empty_list_no_heading(self):
        """AC-7: Given empty list, When telegram, Then no 'Nächste Etappen'."""
        body = _render_narrow("telegram", trend=[])
        assert "Nächste Etappen" not in body


# ---------------------------------------------------------------------------
# AC-4: SMS trend block
# ---------------------------------------------------------------------------

class TestSmsTrend:
    """AC-4: SMS has compact trend block within length limit."""

    def _make_segments(self):
        from tests.unit.test_renderers_email import _make_segment_weather
        return [_make_segment_weather()]

    def test_sms_with_trend_has_trend_header(self):
        """Given SMS + trend, When formatted, Then 'Trend' label present."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments,
            max_length=500,
            multi_day_trend=[_trend_stage()],
        )
        assert "Trend" in result

    def test_sms_trend_contains_weekday(self):
        """Given trend stage Mo, When SMS, Then 'Mo' present."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments, max_length=500,
            multi_day_trend=[_trend_stage(weekday="Mo")],
        )
        assert "Mo" in result

    def test_sms_trend_contains_rain_token(self):
        """Given precip_mm=3, When SMS, Then 'R3' or 'R' token present."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments, max_length=500,
            multi_day_trend=[_trend_stage(precip_mm=3.0)],
        )
        assert "R3" in result or "R" in result

    def test_sms_trend_gew_token_for_med(self):
        """Given thunder=MED, When SMS, Then 'GEW-MED' present."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments, max_length=500,
            multi_day_trend=[_trend_stage(thunder="MED")],
        )
        assert "GEW-MED" in result

    def test_sms_trend_no_gew_for_none(self):
        """Given thunder=NONE, When SMS, Then no 'GEW-' present."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments, max_length=500,
            multi_day_trend=[_trend_stage(thunder="NONE")],
        )
        assert "GEW-" not in result

    def test_sms_trend_respects_max_length(self):
        """Given max_length=160, When SMS with trend, Then len<=160."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(
            segments, max_length=160,
            multi_day_trend=[_trend_stage(), _trend_stage("Di"), _trend_stage("Mi")],
        )
        assert len(result) <= 160

    def test_sms_no_trend_no_trend_block(self):
        """AC-7: Given no trend, When SMS, Then no 'Trend' in output."""
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        result = SMSTripFormatter().format_sms(segments)
        assert "Trend" not in result

    def test_telegram_kurzform_no_double_trend(self):
        """AC-4 edge case: telegram_kurzform path calls format_sms without trend.

        When SMSTripFormatter.format_sms is called without multi_day_trend,
        Then 'Trend' must NOT appear (guard: kurzform path has no trend).
        """
        from src.formatters.sms_trip import SMSTripFormatter
        segments = self._make_segments()
        # Simulate the telegram_kurzform path: no multi_day_trend kwarg
        result = SMSTripFormatter().format_sms(segments, max_length=4000)
        assert "Trend" not in result


# ---------------------------------------------------------------------------
# AC-5: E-Mail context label (sent_at)
# ---------------------------------------------------------------------------

class TestEmailContextLabel:
    """AC-5: HTML trend head carries 3-Tage-Trend label + sent time."""

    def test_label_present_when_sent_at(self):
        """Given sent_at datetime, When HTML, Then '3-Tage-Trend' label present."""
        from datetime import datetime, timezone
        sent = datetime(2026, 6, 6, 17, 30, tzinfo=timezone.utc)
        html = _render_html([_trend_stage()], sent_at=sent)
        assert "3-Tage-Trend" in html

    def test_label_contains_gesendet_weekday(self):
        """Given sent_at on a Freitag, When HTML, Then 'gesendet Fr' or 'Freitag' in label."""
        from datetime import datetime, timezone
        # 2026-06-05 is Freitag
        sent = datetime(2026, 6, 5, 17, 30, tzinfo=timezone.utc)
        html = _render_html([_trend_stage()], sent_at=sent)
        assert "gesendet" in html
        assert "Fr" in html or "Freitag" in html

    def test_label_absent_without_sent_at(self):
        """Given no sent_at, When HTML, Then '3-Tage-Trend' NOT in output (tests stay deterministic)."""
        html = _render_html([_trend_stage()])
        # Default: no sent_at → no context label injected
        assert "3-Tage-Trend" not in html


# ---------------------------------------------------------------------------
# AC-6: Dead code removed
# ---------------------------------------------------------------------------

class TestDeadCodeRemoved:
    """AC-6: _render_html and _render_plain (tote Methoden) are gone from trip_report.py."""

    def test_render_html_method_gone(self):
        """Given TripReportFormatter, When _render_html accessed, Then AttributeError."""
        from src.formatters.trip_report import TripReportFormatter
        assert not hasattr(TripReportFormatter, "_render_html"), \
            "_render_html should have been removed"

    def test_render_plain_method_gone(self):
        """Given TripReportFormatter, When _render_plain accessed, Then AttributeError."""
        from src.formatters.trip_report import TripReportFormatter
        assert not hasattr(TripReportFormatter, "_render_plain"), \
            "_render_plain should have been removed"

    def test_render_html_table_still_present(self):
        """AC-6 guard: _render_html_table must NOT be removed (still used)."""
        from src.formatters.trip_report import TripReportFormatter
        assert hasattr(TripReportFormatter, "_render_html_table"), \
            "_render_html_table must still exist"


# ---------------------------------------------------------------------------
# AC-7: Empty / None trend → no block
# ---------------------------------------------------------------------------

class TestEmptyTrend:
    """AC-7: No trend → no heading in any channel."""

    def test_html_no_heading_on_none_trend(self):
        html = _render_html(None)
        assert "Nächste Etappen" not in html

    def test_html_no_heading_on_empty_list(self):
        html = _render_html([])
        assert "Nächste Etappen" not in html

    def test_plain_no_heading_on_none_trend(self):
        plain = _render_plain(None)
        assert "Nächste Etappen" not in plain

    def test_plain_no_heading_on_empty_list(self):
        plain = _render_plain([])
        assert "Nächste Etappen" not in plain


# ---------------------------------------------------------------------------
# AC-8: Signal — no trend block
# ---------------------------------------------------------------------------

class TestSignalNoTrend:
    """AC-8: Signal body must not contain trend block."""

    def test_signal_no_trend_heading(self):
        """Given signal channel + trend data, When rendered, Then no 'Nächste Etappen'."""
        body = _render_narrow("signal", trend=[_trend_stage()])
        assert "Nächste Etappen" not in body

    def test_signal_no_thunder_token(self):
        """Given signal + MED thunder trend, When rendered, Then no '⚡MED' trend token."""
        body = _render_narrow("signal", trend=[_trend_stage(thunder="MED")])
        # The trend block should be absent entirely for signal
        assert "⚡MED" not in body


# ---------------------------------------------------------------------------
# AC-9: No LOW level in format_trend_tokens
# ---------------------------------------------------------------------------

class TestNoLowLevel:
    """AC-9: LOW does not exist as a valid thunder level."""

    def test_no_low_in_tokens(self):
        """Given any valid thunder level, When format_trend_tokens called, Then no 'LOW' output."""
        from src.output.renderers.email.helpers import format_trend_tokens
        for level in ("NONE", "MED", "HIGH"):
            tokens = format_trend_tokens(_trend_stage(thunder=level))
            for key, val in tokens.items():
                if isinstance(val, str):
                    assert val != "LOW", f"thunder={level}, key={key}, val={val!r}"
                    assert "LOW" not in val, f"thunder={level}, key={key} contains 'LOW': {val!r}"

    def test_helpers_has_no_low_string(self):
        """AC-9: 'LOW' string must not appear in format_trend_tokens function body
        (checked via actual call — all branches exercised).
        # doc-compliance-test
        """
        import inspect
        from src.output.renderers.email.helpers import format_trend_tokens
        src_text = inspect.getsource(format_trend_tokens)
        # Only the literal token string "LOW" matters — "LOW" as a word in a key.
        # We allow 'NONE'/'MED'/'HIGH' only.
        assert '"LOW"' not in src_text and "'LOW'" not in src_text, \
            "format_trend_tokens contains a 'LOW' string literal — remove it"


# ---------------------------------------------------------------------------
# AC-5 Pipeline: format_email / render_email propagates sent_at to HTML
# ---------------------------------------------------------------------------

class TestEmailContextLabelPipeline:
    """AC-5 Pipeline: label appears in email_html produced by format_email."""

    def _make_segments(self):
        from tests.unit.test_renderers_email import _make_segment_weather
        return [_make_segment_weather()]

    def test_format_email_html_contains_label_when_trend_present(self):
        """Given format_email called with trend, When executed, Then '3-Tage-Trend' in email_html."""
        from datetime import datetime, timezone
        from src.formatters.trip_report import TripReportFormatter
        from src.output.renderers.email import render_email
        from src.output.tokens.dto import TokenLine
        from app.metric_catalog import build_default_display_config
        from zoneinfo import ZoneInfo

        segs = self._make_segments()
        trend = [_trend_stage()]
        fixed_sent_at = datetime(2026, 6, 6, 17, 30, tzinfo=timezone.utc)

        # Call render_email directly with fixed sent_at to keep test deterministic
        tl = TokenLine(stage_name="GR20 E3", report_type="evening", trip_name="Test-Trip")
        dc = build_default_display_config()
        html, _ = render_email(
            tl,
            segments=segs,
            seg_tables=[[]],
            display_config=dc,
            highlights=[],
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
            multi_day_trend=trend,
            sent_at=fixed_sent_at,
        )
        assert "3-Tage-Trend" in html, "Context label missing from render_email HTML output"
        assert "gesendet" in html, "'gesendet' missing from render_email HTML output"

    def test_render_email_no_label_without_trend(self):
        """AC-7: Given render_email with no trend + sent_at, Then no '3-Tage-Trend' label."""
        from datetime import datetime, timezone
        from src.output.renderers.email import render_email
        from src.output.tokens.dto import TokenLine
        from app.metric_catalog import build_default_display_config
        from zoneinfo import ZoneInfo

        segs = self._make_segments()
        tl = TokenLine(stage_name="GR20 E3", report_type="evening", trip_name="Test-Trip")
        dc = build_default_display_config()
        html, _ = render_email(
            tl,
            segments=segs,
            seg_tables=[[]],
            display_config=dc,
            highlights=[],
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
            multi_day_trend=None,
            sent_at=datetime(2026, 6, 6, 17, 30, tzinfo=timezone.utc),
        )
        assert "3-Tage-Trend" not in html, "Label must not appear when trend is None"


# ---------------------------------------------------------------------------
# F001 / F003 — Pipeline: format_email muss Trend an Telegram durchreichen
# ---------------------------------------------------------------------------

class TestTelegramTrendPipeline:
    """F001+F003: TripReportFormatter.format_email must pass trend to telegram_text."""

    def _make_segments(self):
        from tests.unit.test_renderers_email import _make_segment_weather
        return [_make_segment_weather()]

    def test_format_email_telegram_text_contains_trend_heading(self):
        """Given format_email with multi_day_trend, When called, Then report.telegram_text has 'Nächste Etappen'."""
        from src.formatters.trip_report import TripReportFormatter
        segs = self._make_segments()
        trend = [_trend_stage()]
        report = TripReportFormatter().format_email(
            segs,
            trip_name="GR20",
            report_type="evening",
            multi_day_trend=trend,
        )
        assert "Nächste Etappen" in report.telegram_text, (
            "F001: telegram_text missing trend — multi_day_trend not passed to render_narrow"
        )

    def test_format_email_signal_text_no_trend_heading(self):
        """AC-8: format_email with trend must NOT put trend in signal_text."""
        from src.formatters.trip_report import TripReportFormatter
        segs = self._make_segments()
        trend = [_trend_stage()]
        report = TripReportFormatter().format_email(
            segs,
            trip_name="GR20",
            report_type="evening",
            multi_day_trend=trend,
        )
        assert "Nächste Etappen" not in report.signal_text, (
            "AC-8 violated: signal_text must not contain trend block"
        )

    def test_format_email_no_trend_no_heading_in_telegram(self):
        """AC-7: format_email without trend — telegram_text has no 'Nächste Etappen'."""
        from src.formatters.trip_report import TripReportFormatter
        segs = self._make_segments()
        report = TripReportFormatter().format_email(
            segs,
            trip_name="GR20",
            report_type="evening",
            multi_day_trend=None,
        )
        assert "Nächste Etappen" not in report.telegram_text


# ---------------------------------------------------------------------------
# F002 — Konsolidierung: Renderer dürfen keine Schwellen selbst auswerten
# ---------------------------------------------------------------------------

class TestTokenConsolidation:
    """F002: format_trend_tokens is the ONLY place that evaluates thresholds."""

    def test_precip_zero_html_uses_ndash(self):
        """Given precip_mm=0, When HTML rendered, Then no '0mm' raw value — dash only."""
        html = _render_html([_trend_stage(precip_mm=0)])
        # Token decides: precip_is_zero → dash. Raw '0 mm' must not appear.
        assert "0&thinsp;mm" not in html
        assert "0mm" not in html

    def test_precip_nonzero_no_highlight_html(self):
        """Given precip_mm=0.5 (<=1, no highlight), When HTML, Then no bold blue span."""
        html = _render_html([_trend_stage(precip_mm=0.5)])
        # highlight only triggers above 1mm
        assert "font-weight:700" not in html or "#2c5a8c" not in html

    def test_precip_zero_plain_uses_dash(self):
        """Given precip_mm=0, When plain rendered, Then '–' not '0mm'."""
        plain = _render_plain([_trend_stage(precip_mm=0)])
        # The precip column must show dash
        assert "0mm" not in plain

    def test_precip_zero_narrow_uses_dash(self):
        """Given precip_mm=0, When telegram rendered, Then '–' not '0mm'."""
        body = _render_narrow("telegram", trend=[_trend_stage(precip_mm=0)])
        assert "0mm" not in body

    def test_wind_no_highlight_at_30_html(self):
        """Given wind_kmh=30 (not >30), When HTML, Then no orange bold span in wind cell."""
        html = _render_html([_trend_stage(wind_kmh=30)])
        # The orange highlight span only appears when wind_highlight is True (>30).
        # color:#c45a2a appears in the CSS stylesheet too, so check for the full span.
        assert 'color:#c45a2a;font-weight:700' not in html

    def test_wind_highlight_at_31_html(self):
        """Given wind_kmh=31 (>30), When HTML, Then orange highlight present."""
        html = _render_html([_trend_stage(wind_kmh=31)])
        assert "#c45a2a" in html

    def test_format_trend_tokens_is_sole_threshold_evaluator(self):
        """F002 structural: renderers must not contain raw threshold comparisons.

        Checks that the three channel renderer files do NOT contain bare
        precip/wind threshold expressions (> 1, > 30, >= 50, precip_mm ==).
        # doc-compliance-test
        """
        import re
        renderer_files = [
            '/home/hem/gregor_zwanzig/.claude/worktrees/idempotent-strolling-cray/src/output/renderers/email/html.py',
            '/home/hem/gregor_zwanzig/.claude/worktrees/idempotent-strolling-cray/src/output/renderers/email/plain.py',
            '/home/hem/gregor_zwanzig/.claude/worktrees/idempotent-strolling-cray/src/output/renderers/narrow.py',
        ]
        # Pattern: bare numeric threshold checks that should live in format_trend_tokens
        bad_patterns = [
            r'pm\s*>\s*0',       # precip zero-check in renderer
            r'pm\s*>\s*1',       # precip highlight threshold in renderer
            r'wk\s*>\s*30',      # wind highlight threshold in renderer
            r'wk\s*>=\s*50',     # wind risk threshold in renderer
            r'precip_mm.*>\s*[01]',  # raw precip_mm comparison
        ]
        violations = []
        for fpath in renderer_files:
            src = open(fpath).read()
            for pat in bad_patterns:
                for m in re.finditer(pat, src):
                    line_no = src[:m.start()].count("\n") + 1
                    violations.append(f"{fpath.split('/')[-1]}:{line_no}: {m.group()!r}")
        assert not violations, (
            "F002: Renderer(s) still evaluate thresholds directly:\n"
            + "\n".join(violations)
        )
