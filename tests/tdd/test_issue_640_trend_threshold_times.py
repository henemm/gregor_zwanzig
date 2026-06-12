"""
TDD tests for Issue #640 — Mehrtages-Trend: Schwellwert-Zeiten.

RED phase: All tests fail until implementation is complete.

SPEC: docs/specs/modules/issue_640_trend_threshold_times.md AC-1..AC-9
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.
"""
from __future__ import annotations

import pytest
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float):
    """Shorthand for HourlyValue."""
    from src.output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


def _trend_stage_with_hourly(
    weekday="Di", name="Test-Etappe",
    temp_lo=12, temp_hi=15,
    precip_mm=0.5, wind_dir="W", wind_kmh=17, thunder="NONE", note=None,
    hourly_precip=None,
    hourly_wind=None,
    hourly_gust=None,
    hourly_thunder=None,
):
    """Build a trend stage dict including optional hourly sample tuples."""
    return dict(
        weekday=weekday, name=name,
        temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=note,
        hourly_precip=hourly_precip or (),
        hourly_wind=hourly_wind or (),
        hourly_gust=hourly_gust or (),
        hourly_thunder=hourly_thunder or (),
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
# AC-1: format_trend_tokens liefert Zeiten-Tokens aus Stundenwerten
# ---------------------------------------------------------------------------

class TestFormatTrendTokensTimestamps:
    """AC-1: format_trend_tokens liefert precip_token/wind_token/thunder_token
    mit @-Zeiten wenn Stundenwerte übergeben werden."""

    def test_precip_token_key_exists(self):
        """Given stage with hourly_precip, When format_trend_tokens, Then 'precip_token' key present."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
        )
        tok = format_trend_tokens(stage)
        assert "precip_token" in tok

    def test_wind_token_key_exists(self):
        """Given stage with hourly_wind, When format_trend_tokens, Then 'wind_token' key present."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_wind=(_hv(16, 17.0),),
        )
        tok = format_trend_tokens(stage)
        assert "wind_token" in tok

    def test_thunder_token_key_exists(self):
        """Given stage with hourly_thunder, When format_trend_tokens, Then 'thunder_token' key present."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_thunder=(_hv(14, 1.0),),
        )
        tok = format_trend_tokens(stage)
        assert "thunder_token" in tok

    def test_precip_token_erst_and_peak(self):
        """AC-1: Given precip at h10=0.5mm (threshold) and h15=6mm (peak),
        Then precip_token='0.5@10(6@15)'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
        )
        tok = format_trend_tokens(stage)
        # Default threshold: 0.5 → erst at h10, peak at h15
        assert "@10" in tok["precip_token"], f"Got: {tok['precip_token']}"
        assert "@15" in tok["precip_token"], f"Got: {tok['precip_token']}"

    def test_precip_token_erst_equals_peak(self):
        """AC-1 Edge: When erst==peak (one sample exceeding threshold),
        Then token is '{val}@{h}' (no parenthesis)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(12, 2.0),),
        )
        tok = format_trend_tokens(stage)
        assert tok["precip_token"] == "2.0@12", f"Got: {tok['precip_token']}"

    def test_precip_token_never_exceeds_threshold(self):
        """AC-4: When precip never exceeds default threshold (0.5mm),
        Then precip_token is '-' (no @)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.1), _hv(11, 0.2)),
        )
        tok = format_trend_tokens(stage)
        assert tok["precip_token"] == "-"
        assert "@" not in tok["precip_token"]

    def test_wind_token_with_times(self):
        """AC-1: Given wind at h16=35 (above 30 threshold), Then wind_token='35@16'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_wind=(_hv(16, 35.0),),
        )
        tok = format_trend_tokens(stage)
        assert tok["wind_token"] == "35@16", f"Got: {tok['wind_token']}"

    def test_wind_token_never_exceeds_threshold(self):
        """AC-4: Wind below 30 threshold → wind_token='-'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_wind=(_hv(12, 10.0), _hv(14, 25.0)),
        )
        tok = format_trend_tokens(stage)
        assert tok["wind_token"] == "-"
        assert "@" not in tok["wind_token"]

    def test_wind_token_exceeds_threshold(self):
        """AC-1: Wind at h14=35 (>30) → token contains '@14'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_wind=(_hv(14, 35.0),),
        )
        tok = format_trend_tokens(stage)
        assert "@14" in tok["wind_token"], f"Got: {tok['wind_token']}"

    def test_thunder_token_level(self):
        """AC-1/F001: Thunder MED at h14 (erst), HIGH at h16 (peak) →
        thunder_token='MED@14(HIGH@16)'. Must NOT use L/M (SMS vigilance scale)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_thunder=(_hv(14, 1.0), _hv(16, 2.0)),  # MED=1, HIGH=2
            thunder="HIGH",
        )
        tok = format_trend_tokens(stage)
        tt = tok["thunder_token"]
        assert "@14" in tt, f"Missing erst hour @14: {tt}"
        assert "@16" in tt, f"Missing peak hour @16: {tt}"
        assert "MED" in tt, f"Expected 'MED' label, got: {tt!r}"
        assert "HIGH" in tt, f"Expected 'HIGH' label, got: {tt!r}"
        # Explicitly exclude SMS vigilance labels
        assert tt != "L@14(M@16)", f"Got SMS vigilance labels instead of MED/HIGH: {tt!r}"

    def test_thunder_token_med_only(self):
        """F001: Single MED sample → thunder_token='MED@14' (not 'L@14')."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_thunder=(_hv(14, 1.0),),  # MED=1
            thunder="MED",
        )
        tok = format_trend_tokens(stage)
        tt = tok["thunder_token"]
        assert tt == "MED@14", f"Expected 'MED@14', got: {tt!r}"
        assert "L" not in tt, f"SMS label 'L' must not appear: {tt!r}"

    def test_thunder_token_none_returns_dash(self):
        """AC-4: No thunder above threshold → thunder_token='-'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_thunder=(_hv(12, 0.0),),  # NONE level
            thunder="NONE",
        )
        tok = format_trend_tokens(stage)
        assert tok["thunder_token"] == "-"

    def test_no_hourly_data_token_is_dash(self):
        """Edge case: no hourly_precip → precip_token='-' (fallback, no @)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(hourly_precip=())
        tok = format_trend_tokens(stage)
        assert tok["precip_token"] == "-"
        assert "@" not in tok["precip_token"]

    def test_temp_no_at_sign(self):
        """AC-8: Temperature string has no @ (no threshold concept for temp)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 2.0),),
        )
        tok = format_trend_tokens(stage)
        assert "@" not in tok["temp_str"]


# ---------------------------------------------------------------------------
# AC-2: Schwellwert-Quelle — sms_threshold wenn gesetzt, sonst Default
# ---------------------------------------------------------------------------

class TestThresholdSource:
    """AC-2: sms_threshold takes precedence over default when set."""

    def test_custom_threshold_changes_first_crossing(self):
        """AC-2: Given custom threshold=2.0, When samples=[h10=0.5, h12=2.5],
        Then erst at h12 (not h10 which was below custom threshold)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        # h10=0.5 is below custom threshold 2.0; h12=2.5 is first crossing
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.5), _hv(12, 2.5)),
        )
        # Inject custom threshold via stage dict key
        stage["sms_threshold_precip"] = 2.0
        tok = format_trend_tokens(stage)
        # With threshold=2.0, erst should be h12, not h10
        assert "@12" in tok["precip_token"], f"Got: {tok['precip_token']}"
        assert "@10" not in tok["precip_token"], f"Got: {tok['precip_token']}"

    def test_default_precip_threshold_is_0_5(self):
        """AC-2: Default precip threshold is 0.5mm — sample at 0.5 triggers token."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.5),),
        )
        tok = format_trend_tokens(stage)
        # 0.5 >= 0.5 → should produce a token with @
        assert "@10" in tok["precip_token"], f"Got: {tok['precip_token']}"

    def test_default_wind_threshold_is_30(self):
        """AC-2: Default wind threshold is 30 km/h — sample at 30 triggers token."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_wind=(_hv(12, 30.0),),
        )
        tok = format_trend_tokens(stage)
        # 30 >= 30 → should produce a token with @
        assert "@12" in tok["wind_token"], f"Got: {tok['wind_token']}"


# ---------------------------------------------------------------------------
# AC-3: Telegram Hauptzeile mit @-Tokens; ↳ kompakt ohne Zeiten
# ---------------------------------------------------------------------------

class TestTelegramInlineTokens:
    """AC-3: @ tokens appear inline in telegram trend line; hint line stays compact."""

    def test_telegram_trend_line_has_at_token_for_precip(self):
        """AC-3: Given precip samples crossing threshold, When telegram rendered,
        Then trend main line contains '@' for precip (inline)."""
        trend = [_trend_stage_with_hourly(
            weekday="Di", temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
            hourly_wind=(_hv(16, 17.0),),
            hourly_thunder=(),
        )]
        body = _render_narrow("telegram", trend=trend)
        # The @ should appear in the body for precip
        assert "@" in body, f"No @ found in telegram body:\n{body}"

    def test_telegram_trend_line_format_with_at_tokens(self):
        """AC-3: Telegram trend line has inline tokens like 'R0.5@10(6@15) W17@16'."""
        trend = [_trend_stage_with_hourly(
            weekday="Di", temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
            hourly_wind=(_hv(16, 17.0),),
            hourly_thunder=(),
        )]
        body = _render_narrow("telegram", trend=trend)
        # At least one @-token should appear
        assert "@10" in body or "@15" in body or "@16" in body, (
            f"No hour tokens found in:\n{body}"
        )

    def test_telegram_note_line_has_no_repeated_times(self):
        """AC-3: ↳ hint line is compact words, no '@HH' repeated times."""
        trend = [_trend_stage_with_hourly(
            weekday="Di",
            hourly_precip=(_hv(10, 0.5),),
            hourly_thunder=(_hv(14, 1.0),),
            thunder="MED",
            note="Gewitter möglich",
        )]
        body = _render_narrow("telegram", trend=trend)
        lines = body.split("\n")
        # Find the note line (contains ↳)
        note_lines = [l for l in lines if "↳" in l]
        if note_lines:
            note_text = note_lines[0]
            # The note line should NOT contain @HH timestamps
            import re
            at_times = re.findall(r"@\d{2}", note_text)
            assert not at_times, (
                f"↳ line contains time tokens {at_times!r}: {note_text!r}"
            )

    def test_telegram_no_threshold_no_at(self):
        """AC-4: When metric never exceeds threshold, compact form (no @)."""
        trend = [_trend_stage_with_hourly(
            weekday="Mo",
            hourly_precip=(_hv(10, 0.1),),  # below 0.5 threshold
            hourly_wind=(_hv(12, 10.0),),   # below 30 threshold
        )]
        body = _render_narrow("telegram", trend=trend)
        # Find the trend section (after "Nächste Etappen")
        assert "Nächste Etappen" in body
        # No @ in threshold lines for this stage
        trend_section = body.split("Nächste Etappen")[-1]
        # Compact form: no @ times for metrics below threshold
        assert "@" not in trend_section, (
            f"Unexpected @ in trend section:\n{trend_section}"
        )

    def test_telegram_temp_no_at_in_trend_line(self):
        """AC-8: Temperature has no @ in telegram trend line."""
        trend = [_trend_stage_with_hourly(
            weekday="Di", temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 2.0),),
        )]
        body = _render_narrow("telegram", trend=trend)
        # Find the trend line (contains temp)
        for line in body.split("\n"):
            if "12" in line and "15" in line and "Di" in line:
                # Temp part should not have @
                assert "@" not in line.split("12")[0], (
                    f"@ found in temp area of line: {line!r}"
                )

    def test_telegram_line_width_with_at_tokens(self):
        """AC-9: Lines with @ tokens still fit within _TG_PROSE_WIDTH=56."""
        trend = [_trend_stage_with_hourly(
            weekday="Di", temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
            hourly_wind=(_hv(14, 35.0), _hv(16, 42.0)),
            hourly_thunder=(_hv(14, 1.0), _hv(16, 2.0)),
            thunder="HIGH",
        )]
        body = _render_narrow("telegram", trend=trend)
        for line in body.split("\n"):
            assert len(line) <= 56, f"Line too long ({len(line)}): {line!r}"

    def test_telegram_thunder_token_uses_med_high_labels(self):
        """F001/F002: Telegram trend line uses MED/HIGH labels, not L/M (vigilance scale)."""
        trend = [_trend_stage_with_hourly(
            weekday="Di",
            hourly_thunder=(_hv(14, 1.0), _hv(16, 2.0)),  # MED→1, HIGH→2
            thunder="HIGH",
        )]
        body = _render_narrow("telegram", trend=trend)
        trend_section = body.split("Nächste Etappen")[-1] if "Nächste Etappen" in body else body
        assert "MED" in trend_section or "HIGH" in trend_section, (
            f"Expected MED/HIGH in telegram trend, got:\n{trend_section!r}"
        )
        # SMS vigilance labels must not appear for thunder in trend
        assert "⚡L@" not in trend_section, f"SMS vigilance label 'L' found: {trend_section!r}"
        assert "⚡M@" not in trend_section, f"SMS vigilance label 'M' found: {trend_section!r}"


# ---------------------------------------------------------------------------
# AC-5: E-Mail Trend-Zellen haben @-Tokens
# ---------------------------------------------------------------------------

class TestEmailCellsWithTokens:
    """AC-5: Email trend cells contain @-time tokens in precip/wind/thunder cols."""

    def test_email_precip_cell_has_at_token(self):
        """AC-5: Given precip samples, When HTML rendered, Then precip cell has @."""
        trend = [_trend_stage_with_hourly(
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
        )]
        html = _render_html(trend)
        assert "@10" in html or "@15" in html, (
            f"No precip @ tokens in HTML trend cells"
        )

    def test_email_wind_cell_has_at_token(self):
        """AC-5: Given wind samples above threshold, When HTML, Then @ in wind cell."""
        trend = [_trend_stage_with_hourly(
            hourly_wind=(_hv(16, 35.0),),
        )]
        html = _render_html(trend)
        assert "@16" in html, f"No wind @ token in HTML"

    def test_email_thunder_cell_has_at_token(self):
        """AC-5: Given thunder samples above threshold, When HTML, Then thunder time present.

        Issue #669: Thunder cell now shows '⚡ Gewitter möglich HH:00' badge instead
        of raw '@HH' token — time is expressed as 'HH:00' (e.g. '14:00').
        """
        trend = [_trend_stage_with_hourly(
            hourly_thunder=(_hv(14, 1.0),),
            thunder="MED",
        )]
        html = _render_html(trend)
        # Issue #669: badge format uses HH:00 time notation
        assert "14:00" in html or "@14" in html, f"No thunder time token in HTML"

    def test_email_thunder_cell_uses_med_high_labels(self):
        """F001/F002: Email thunder cell shows time-windowed badge or MED/HIGH label.

        Issue #669: Thunder cell now shows '⚡ Gewitter möglich HH:00–HH:00' badge
        when hourly_thunder is present; SMS vigilance labels must not appear.
        """
        trend = [_trend_stage_with_hourly(
            hourly_thunder=(_hv(14, 1.0), _hv(16, 2.0)),
            thunder="HIGH",
        )]
        html = _render_html(trend)
        # Issue #669: badge shows time window; old MED@14 token replaced by 14:00–16:00
        assert ("Gewitter möglich" in html or "MED@14" in html or "MED" in html), (
            f"Expected thunder display in HTML"
        )
        # Vigilance labels must not appear in the thunder cell
        assert "L@14" not in html, f"SMS vigilance label 'L@14' found in HTML"
        assert "M@16" not in html, f"SMS vigilance label 'M@16' found in HTML"

    def test_email_note_line_compact(self):
        """AC-5: Note/hint line in email is compact words, no @HH timestamps."""
        trend = [_trend_stage_with_hourly(
            hourly_precip=(_hv(10, 2.0),),
            note="Gewitter möglich",
        )]
        html = _render_html(trend)
        # Find the note snippet
        assert "Gewitter möglich" in html
        # The note text itself should not have @HH near it
        note_idx = html.index("Gewitter möglich")
        note_context = html[note_idx - 20:note_idx + 60]
        import re
        assert not re.search(r"@\d{2}", note_context), (
            f"Note area contains time token: {note_context!r}"
        )

    def test_email_temp_cell_no_at(self):
        """AC-8: Temperature cell in email has no @ (temp has no threshold concept)."""
        trend = [_trend_stage_with_hourly(
            temp_lo=12, temp_hi=15,
            hourly_precip=(_hv(10, 2.0),),
        )]
        html = _render_html(trend)
        # Extract temp cell content (rough check)
        assert "12" in html and "15" in html
        # The temp span must not have @
        import re
        temp_cells = re.findall(r'12.{0,5}15', html)
        for cell in temp_cells:
            assert "@" not in cell, f"@ found near temp values: {cell!r}"


# ---------------------------------------------------------------------------
# AC-7: Gemeinsame Token-Quelle (format_trend_tokens is SSoT)
# ---------------------------------------------------------------------------

class TestTokenSourceOfTruth:
    """AC-7: All channels derive @-tokens from format_trend_tokens, not inline."""

    def test_format_trend_tokens_has_all_time_token_keys(self):
        """AC-7: format_trend_tokens returns all required time-token keys."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            hourly_precip=(_hv(10, 2.0),),
            hourly_wind=(_hv(14, 35.0),),
            hourly_gust=(_hv(15, 55.0),),
            hourly_thunder=(_hv(14, 1.0),),
        )
        tok = format_trend_tokens(stage)
        for key in ("precip_token", "wind_token", "thunder_token"):
            assert key in tok, f"Missing key '{key}' in format_trend_tokens output"

    def test_telegram_no_inline_threshold_calc(self):
        """AC-7: Telegram renderer must not compute threshold crossing itself.
        Verified by: stage with hourly data → renderer output matches
        format_trend_tokens result (same @-token strings).
        """
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _trend_stage_with_hourly(
            weekday="Di",
            hourly_precip=(_hv(10, 0.5), _hv(15, 6.0)),
            hourly_wind=(_hv(16, 17.0),),
        )
        # What format_trend_tokens says should be what Telegram shows
        tok = format_trend_tokens(stage)
        precip_token = tok["precip_token"]

        body = _render_narrow("telegram", trend=[stage])
        # The precip_token produced by format_trend_tokens must appear verbatim
        assert precip_token in body, (
            f"Telegram didn't use format_trend_tokens result '{precip_token}':\n{body}"
        )


# ---------------------------------------------------------------------------
# AC-8: Unveraenderte Bereiche (Haupttabelle, SMS-Hauptbericht, Trend-Kopf)
# ---------------------------------------------------------------------------

class TestUnchangedAreas:
    """AC-8: Email main table, SMS main report, trend heading unchanged."""

    def test_email_main_table_unaffected(self):
        """AC-8: Email HTML main hourly table still renders without @ from trend tokens."""
        html = _render_html([])
        # Main table uses time column headers like "08", "10" — no @HH pattern in header
        # This is a smoke check: renderer doesn't crash and doesn't inject @
        assert "Uhr" in html or "time" in html.lower() or "08" in html

    def test_trend_heading_nächste_etappen_unchanged(self):
        """AC-8: Trend section heading 'Nächste Etappen' unchanged."""
        trend = [_trend_stage_with_hourly()]
        html = _render_html(trend)
        assert "Nächste Etappen" in html

    def test_telegram_befehle_hint_unchanged(self):
        """AC-8: Telegram command hint line unchanged after adding @-tokens."""
        trend = [_trend_stage_with_hourly(
            hourly_precip=(_hv(10, 2.0),),
        )]
        body = _render_narrow("telegram", trend=trend)
        assert "Befehle" in body

    def test_backwards_compat_no_hourly_data(self):
        """AC-8: Stage without hourly_ keys (old format) still renders without crash."""
        # Old-style stage dict without hourly_ keys
        old_stage = dict(
            weekday="Mo", name="Test",
            temp_lo=8, temp_hi=16, precip_mm=3.0,
            wind_dir="W", wind_kmh=20, thunder="NONE", note=None,
        )
        from src.output.renderers.email.helpers import format_trend_tokens
        tok = format_trend_tokens(old_stage)
        # Should not crash; tokens should fallback to '-' or simple values
        assert "precip_token" in tok
        assert tok["precip_token"] == "-"
