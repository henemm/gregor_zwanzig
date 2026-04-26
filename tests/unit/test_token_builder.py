"""
Unit tests for src/output/tokens.py — TDD RED Phase β1.

Tests must FAIL with ModuleNotFoundError because src/output/tokens.py
does not yet exist. This file is the contract the implementation must satisfy.

SPEC: docs/specs/modules/output_token_builder.md v1.1
AUTHORITY: docs/reference/sms_format.md v2.0

Critical rules from spec:
- Token order is POSITIONAL §2: N D R PR W G TH: TH+: HR:TH: …
- NEVER 'T' as standalone token — only N (Nacht-Min) and D (Tag-Max).
- Risk-Priority gilt NUR fuer Truncation §6, NICHT fuer Render-Order.
- HR/TH-Fusion: paarweise, kein Space, nur FR-only.
- @hour-Pflicht fuer R, PR, W, G, TH, TH+, HR; Stunde 0-23 ohne fuehrende Null.
"""
from __future__ import annotations

import pytest

# GREEN: src/output/tokens is now implemented.
from src.output.tokens import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
    Token,
    TokenLine,
    build_token_line,
)

# Module-level toggle: when True, _build_default_line builds an EMPTY forecast
# and propagates the ValueError raised by build_token_line(). The
# `test_empty_forecast_raises` test enables this for one call.
_EMPTY_FORECAST = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_default_line(
    *,
    report_type: str = "evening",
    stage_name: str = "Stage1",
    profile: str = "standard",
):
    """
    Build a TokenLine using a synthetic forecast + config that is rich enough
    to exercise all unit tests in this file:

    - rain at 06h (0.2mm, threshold) and 16h (1.4mm, peak)
    - PR (probability of rain) at 11h (40%) and 17h (90%)
    - wind/gusts to satisfy ordering tests
    - thunder today at 16h MED, tomorrow at 14h HIGH
    - one metric with use_friendly_format=True + friendly_label='Niesel'
    - vigilance HR/TH paired (FR-only) so HR/TH-fusion is exercised
    - profile='wintersport' adds SN token + many wintersport tokens, ensuring
      the 80-char truncation budget triggers §6 priority order.
    """
    if _EMPTY_FORECAST:
        forecast = NormalizedForecast(days=())
        return build_token_line(
            forecast, [], report_type=report_type, stage_name=stage_name,
            profile=profile,
        )

    today = DailyForecast(
        temp_min_c=12.0,
        temp_max_c=24.0,
        rain_hourly=(HourlyValue(6, 0.2), HourlyValue(16, 1.4)),
        pop_hourly=(HourlyValue(11, 40.0), HourlyValue(17, 90.0)),
        wind_hourly=(HourlyValue(11, 18.0), HourlyValue(15, 28.0)),
        gust_hourly=(HourlyValue(11, 25.0), HourlyValue(15, 40.0)),
        thunder_hourly=(HourlyValue(16, 2),),
        snow_depth_cm=180.0,
        snow_new_24h_cm=25.0,
        snowfall_limit_m=1800.0,
        avalanche_level=3,
        wind_chill_c=-22.0,
    )
    tomorrow = DailyForecast(
        thunder_hourly=(HourlyValue(14, 3),),
    )
    # Wintersport profile drops fire/debug to keep render <=160 (so the
    # SN tokens survive). Standard profile keeps fire+debug to trigger §6
    # truncation and exercise the truncated=True flag.
    if profile == "wintersport":
        forecast = NormalizedForecast(
            days=(today, tomorrow),
            provider="meteofrance",
            country="",  # disable fire block
            vigilance_hr_level="M", vigilance_hr_hour=14,
            vigilance_th_level="H", vigilance_th_hour=17,
        )
    else:
        forecast = NormalizedForecast(
            days=(today, tomorrow),
            provider="meteofrance",
            country="FR",
            vigilance_hr_level="M", vigilance_hr_hour=14,
            vigilance_th_level="H", vigilance_th_hour=17,
            fire_zones_high=("208", "217", "226"),
            fire_zones_max=("209", "210"),
            fire_massifs=("3", "5", "9", "12", "24"),
            debug_provider="MET", debug_confidence="MED",
        )
    # Specs:
    # - PR is morning_enabled=False, so morning report drops PR.
    # - PR uses use_friendly_format=True with friendly_label='Niesel' so
    #   the friendly-label test passes (in evening report) and PR is dropped
    #   in morning.
    config = [
        MetricSpec(symbol="N", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="R", enabled=True, threshold=0.2),
        MetricSpec(symbol="PR", enabled=True, threshold=20.0,
                   morning_enabled=False, evening_enabled=True),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="TH:", enabled=True, threshold=1.0),
        MetricSpec(symbol="TH+:", enabled=True, threshold=1.0),
        # Custom companion metric DRZ (drizzle) is rendered as the friendly
        # label 'Niesel' regardless of the underlying symbol. This exercises
        # the use_friendly_format path without colliding with positional
        # tokens.
        MetricSpec(symbol="DRZ", enabled=True,
                   use_friendly_format=True, friendly_label="Niesel"),
        # Wintersport metrics for the wintersport profile path.
        MetricSpec(symbol="SN", enabled=True),
        MetricSpec(symbol="SN24+", enabled=True),
        MetricSpec(symbol="SFL", enabled=True),
        MetricSpec(symbol="AV", enabled=True),
        MetricSpec(symbol="WC", enabled=True),
    ]
    return build_token_line(
        forecast, config, report_type=report_type, stage_name=stage_name,
        profile=profile,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_token_line_returns_tokenline():
    """build_token_line() returns an instance of TokenLine."""
    line = _build_default_line()
    assert isinstance(line, TokenLine)


def test_token_order_positional_per_sms_format_v2():
    """
    sms_format.md §2 POSITIONAL: N D R PR W G TH: TH+: HR:TH: ...

    Risk-Priority (Thunder > Wind > Rain > Temp) gilt NUR fuer Truncation §6,
    NICHT fuer die Render-Reihenfolge.

    Even when TH=high and R=2mm (TH would dominate by risk), positional
    order keeps N before D, D before R, R before PR, PR before W, W before G,
    G before TH:, TH: before TH+:.
    """
    line = _build_default_line()
    rendered = line.render(160)

    # Find positions of single-letter / multi-letter tokens. Strip leading
    # "{stage_name}: " prefix to look at the token sequence only.
    body = rendered.split(":", 1)[1] if ":" in rendered else rendered

    # Tokens we care about (each will appear as "N12", "D24", "R0.2@..", etc.
    # or as the null form "N-", "R-", ...). Find by symbol-prefix anchored
    # at a word boundary.
    import re
    expected_order = ["N", "D", "R", "PR", "W", "G", "TH:", "TH+:"]
    positions = []
    for sym in expected_order:
        # match symbol at word boundary, followed by digit, '-', or no space-char
        m = re.search(rf"(?:(?<=\s)|^)\s*{re.escape(sym)}(?=[\d\-LMHR])", body)
        assert m is not None, f"token {sym!r} not found in render: {rendered!r}"
        positions.append((sym, m.start()))

    # Positions must be strictly increasing (POSITIONAL).
    for i in range(1, len(positions)):
        assert positions[i][1] > positions[i - 1][1], (
            f"Token {positions[i][0]!r} appears before {positions[i - 1][0]!r} "
            f"— violates §2 POSITIONAL order. Render: {rendered!r}"
        )


def test_friendly_format_uses_friendly_label():
    """
    With use_friendly_format=True and a metric exposing friendly_label='Niesel',
    the rendered token must contain the friendly label.
    """
    line = _build_default_line()
    rendered = line.render(160)
    assert "Niesel" in rendered, (
        f"Friendly label 'Niesel' missing — use_friendly_format not honoured."
    )


def test_threshold_peak_format():
    """
    sms_format.md §5: R-token with threshold 0.2mm hit at 06h, peak 1.4mm
    at 16h must render as 'R0.2@6(1.4@16)'. Hour without leading zero.
    Threshold == Max optimisation does NOT apply (different values + hours).
    """
    line = _build_default_line()
    rendered = line.render(160)
    assert "R0.2@6(1.4@16)" in rendered, (
        f"Threshold+Peak format wrong; expected 'R0.2@6(1.4@16)' in {rendered!r}"
    )


def test_morning_filter_excludes_evening_only():
    """
    A token whose MetricConfig has morning_enabled=False must not appear
    in the rendered line for report_type='morning'.
    """
    line = _build_default_line(report_type="morning")
    rendered = line.render(160)
    # The token in question is configured by the helper; here we assert
    # its symbol prefix 'PR' (probability of rain) is absent in this build.
    import re
    assert not re.search(r"(?:(?<=\s)|^)PR[\d\-]", rendered), (
        f"Evening-only token leaked into morning render: {rendered!r}"
    )


def test_wintersport_profile_adds_sn_token():
    """
    profile='wintersport' must inject the SN token. Per §2 POSITIONAL,
    SN appears in the wintersport block AFTER the forecast/risk blocks.
    """
    line = _build_default_line(profile="wintersport")
    rendered = line.render(160)
    import re
    assert re.search(r"(?:(?<=\s)|^)SN\d", rendered), (
        f"Wintersport profile did not inject SN token: {rendered!r}"
    )


def test_render_max_length_truncates():
    """
    A TokenLine whose unbounded render is >160 chars must be cut to <=160
    and TokenLine.truncated must be True.
    """
    line = _build_default_line()
    rendered = line.render(160)
    assert len(rendered) <= 160
    assert line.truncated is True, (
        "TokenLine.truncated must be True after §6-Kuerzung."
    )


def test_render_truncation_priority():
    """
    sms_format.md §6 truncation order:
    DBG -> Wintersport -> Fire -> Peak-values -> PR -> D, N.

    Thunderstorm and Vigilance (TH:, HR:) survive longest (Risk-Priority
    applies only here). Temperature/SN tokens drop first.
    """
    line = _build_default_line()
    rendered = line.render(80)  # very tight budget forces truncation
    # Critical tokens (TH:, HR:) must survive
    assert ("TH:" in rendered) or ("HR:" in rendered), (
        "Risk-Priority truncation removed Thunder/Vigilance — forbidden by §6."
    )
    # Wintersport SN tokens drop early — must NOT appear under tight budget
    import re
    assert not re.search(r"(?:(?<=\s)|^)SN\d", rendered), (
        "Wintersport SN token survived tight truncation — wrong §6 priority."
    )


def test_empty_forecast_raises():
    """build_token_line() with an empty NormalizedForecast must raise ValueError."""
    with pytest.raises(ValueError):
        build_token_line(
            NormalizedForecast(days=()),
            [],
            report_type="evening",
            stage_name="X",
        )


def test_determinism():
    """
    build_token_line() is deterministic: two calls with identical inputs
    yield bit-identical render() output.
    """
    line_a = _build_default_line()
    line_b = _build_default_line()
    assert line_a.render(160) == line_b.render(160)
