"""
Golden-master + structural conformance tests for src/output/tokens.py.

Phase β1 RED phase: these tests must FAIL with ModuleNotFoundError because
src/output/tokens.py does not yet exist.

SPEC: docs/specs/modules/output_token_builder.md v1.1
AUTHORITY: docs/reference/sms_format.md v2.0

Five frozen golden profiles + one structural conformance test:

    1. test_golden_gr20_summer_evening
    2. test_golden_gr20_spring_morning
    3. test_golden_gr221_mallorca_evening
    4. test_golden_arlberg_winter_morning
    5. test_golden_corsica_vigilance
    6. test_render_conforms_to_sms_format_v2  (covers all 5 goldens)

The exact golden strings are stored in tests/golden/sms/*.txt and will
be frozen by the developer in Phase 6 from the real forecasts. RED stubs
contain '# WILL BE FROZEN IN PHASE 6'.

NO cross-check against legacy formatters.sms_trip — see spec §A1.
"""
from __future__ import annotations

import re
from pathlib import Path


# GREEN: src/output/tokens is now implemented.
from src.output.tokens import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
    TokenLine,
    build_token_line,
)


def _default_specs():
    return [
        MetricSpec(symbol="N", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="R", enabled=True, threshold=0.2),
        MetricSpec(symbol="PR", enabled=True, threshold=20.0),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="TH:", enabled=True, threshold=1.0),
        MetricSpec(symbol="TH+:", enabled=True, threshold=1.0),
        MetricSpec(symbol="SN", enabled=True),
        MetricSpec(symbol="SN24+", enabled=True),
        MetricSpec(symbol="SFL", enabled=True),
        MetricSpec(symbol="AV", enabled=True),
        MetricSpec(symbol="WC", enabled=True),
    ]


def _golden_fixtures():
    """Synthetic forecast + config + meta per golden profile."""
    # GR20 summer evening: warm, light rain, building wind.
    gr20_summer_today = DailyForecast(
        temp_min_c=12.0, temp_max_c=24.0,
        rain_hourly=(HourlyValue(15, 0.2), HourlyValue(17, 2.5)),
        pop_hourly=(HourlyValue(11, 20.0), HourlyValue(17, 80.0)),
        wind_hourly=(HourlyValue(10, 18.0), HourlyValue(15, 28.0)),
        gust_hourly=(HourlyValue(10, 25.0), HourlyValue(15, 40.0)),
        thunder_hourly=(HourlyValue(16, 2), HourlyValue(18, 3)),
    )
    gr20_summer_tomorrow = DailyForecast(
        thunder_hourly=(HourlyValue(14, 2), HourlyValue(17, 3)),
    )

    # GR20 spring morning: cold, heavy rain.
    gr20_spring_today = DailyForecast(
        temp_min_c=2.0, temp_max_c=9.0,
        rain_hourly=(HourlyValue(4, 0.2), HourlyValue(11, 18.5)),
        pop_hourly=(HourlyValue(4, 50.0), HourlyValue(11, 95.0)),
        wind_hourly=(HourlyValue(5, 35.0), HourlyValue(10, 60.0)),
        gust_hourly=(HourlyValue(5, 55.0), HourlyValue(10, 85.0)),
        thunder_hourly=(HourlyValue(8, 2), HourlyValue(11, 3)),
    )
    gr20_spring_tomorrow = DailyForecast(thunder_hourly=())

    # GR221 Mallorca evening: warm, no rain, breezy.
    gr221_today = DailyForecast(
        temp_min_c=8.0, temp_max_c=15.0,
        rain_hourly=(),
        pop_hourly=(),
        wind_hourly=(HourlyValue(12, 25.0), HourlyValue(16, 40.0)),
        gust_hourly=(HourlyValue(12, 35.0), HourlyValue(16, 55.0)),
        thunder_hourly=(),
    )
    gr221_tomorrow = DailyForecast(thunder_hourly=())

    # Arlberg winter morning: deep cold, snow, avalanche.
    arlberg_today = DailyForecast(
        temp_min_c=-12.0, temp_max_c=-4.0,
        rain_hourly=(),
        pop_hourly=(),
        wind_hourly=(HourlyValue(8, 45.0), HourlyValue(13, 75.0)),
        gust_hourly=(HourlyValue(8, 70.0), HourlyValue(13, 110.0)),
        thunder_hourly=(),
        snow_depth_cm=180.0,
        snow_new_24h_cm=25.0,
        snowfall_limit_m=1800.0,
        avalanche_level=3,
        wind_chill_c=-22.0,
    )
    arlberg_tomorrow = DailyForecast(thunder_hourly=())

    # Corsica vigilance: heat + thunder + Met-France warnings + fire zones.
    corsica_today = DailyForecast(
        temp_min_c=18.0, temp_max_c=32.0,
        rain_hourly=(HourlyValue(14, 0.2), HourlyValue(17, 8.0)),
        pop_hourly=(HourlyValue(11, 30.0), HourlyValue(17, 90.0)),
        wind_hourly=(HourlyValue(10, 30.0), HourlyValue(15, 55.0)),
        gust_hourly=(HourlyValue(10, 45.0), HourlyValue(15, 85.0)),
        thunder_hourly=(HourlyValue(13, 3), HourlyValue(17, 3)),
    )
    corsica_tomorrow = DailyForecast(thunder_hourly=(HourlyValue(14, 2),))

    return {
        "gr20-summer-evening": (
            NormalizedForecast(days=(gr20_summer_today, gr20_summer_tomorrow)),
            _default_specs(), {"profile": "standard"},
        ),
        "gr20-spring-morning": (
            NormalizedForecast(days=(gr20_spring_today, gr20_spring_tomorrow)),
            _default_specs(), {"profile": "standard"},
        ),
        "gr221-mallorca-evening": (
            NormalizedForecast(days=(gr221_today, gr221_tomorrow)),
            _default_specs(), {"profile": "standard"},
        ),
        "arlberg-winter-morning": (
            NormalizedForecast(days=(arlberg_today, arlberg_tomorrow)),
            _default_specs(), {"profile": "wintersport"},
        ),
        "corsica-vigilance": (
            NormalizedForecast(
                days=(corsica_today, corsica_tomorrow),
                provider="meteofrance", country="FR",
                vigilance_hr_level="M", vigilance_hr_hour=14,
                vigilance_th_level="H", vigilance_th_hour=17,
                fire_zones_high=("208",),
            ),
            _default_specs(), {"profile": "standard"},
        ),
    }


_FIXTURES = _golden_fixtures()


# ---------------------------------------------------------------------------
# Golden profile registry (file stems + stage_name + report_type)
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "sms"

GOLDENS = {
    "gr20-summer-evening": {
        "stage_name": "GR20 E3",
        "report_type": "evening",
        "profile": "standard",
    },
    "gr20-spring-morning": {
        "stage_name": "GR20 E1",
        "report_type": "morning",
        "profile": "standard",
    },
    "gr221-mallorca-evening": {
        "stage_name": "GR221 Tag1",
        "report_type": "evening",
        "profile": "standard",
    },
    "arlberg-winter-morning": {
        "stage_name": "Arlberg",
        "report_type": "morning",
        "profile": "wintersport",
    },
    "corsica-vigilance": {
        "stage_name": "Corsica E5",
        "report_type": "evening",
        "profile": "standard",
    },
}


def _read_golden(stem: str) -> str:
    """Read the frozen golden text for the given profile stem."""
    path = GOLDEN_DIR / f"{stem}.txt"
    return path.read_text(encoding="utf-8").rstrip("\n")


def _build_golden_line(stem: str) -> TokenLine:
    """Build the TokenLine for a given golden profile from synthetic fixtures."""
    forecast, config, extra = _FIXTURES[stem]
    meta = GOLDENS[stem]
    return build_token_line(
        forecast,
        config,
        report_type=meta["report_type"],
        stage_name=meta["stage_name"],
        profile=extra.get("profile", "standard"),
    )


# ---------------------------------------------------------------------------
# 5 golden tests
# ---------------------------------------------------------------------------


def test_golden_gr20_summer_evening():
    line = _build_golden_line("gr20-summer-evening")
    expected = _read_golden("gr20-summer-evening")
    assert line.render(160) == expected


def test_golden_gr20_spring_morning():
    line = _build_golden_line("gr20-spring-morning")
    expected = _read_golden("gr20-spring-morning")
    assert line.render(160) == expected


def test_golden_gr221_mallorca_evening():
    line = _build_golden_line("gr221-mallorca-evening")
    expected = _read_golden("gr221-mallorca-evening")
    assert line.render(160) == expected


def test_golden_arlberg_winter_morning():
    line = _build_golden_line("arlberg-winter-morning")
    expected = _read_golden("arlberg-winter-morning")
    assert line.render(160) == expected


def test_golden_corsica_vigilance():
    line = _build_golden_line("corsica-vigilance")
    expected = _read_golden("corsica-vigilance")
    assert line.render(160) == expected


# ---------------------------------------------------------------------------
# Structural conformance against sms_format.md v2.0
# ---------------------------------------------------------------------------


# Forecast tokens that MUST carry @hour or appear in null-form '-'.
# Order matters here only for predictable iteration; positional check
# uses POSITIONAL_ORDER below.
FORECAST_TOKENS = ("R", "PR", "W", "G", "TH:", "TH+:", "HR:")

# §2 POSITIONAL order — applies to whichever symbols are present.
POSITIONAL_ORDER = ["N", "D", "R", "PR", "W", "G", "TH:", "TH+:"]


def _strip_stage_prefix(rendered: str, stage_name: str) -> str:
    """Return the part after '{stage_name}: '."""
    prefix = f"{stage_name}:"
    assert rendered.startswith(prefix), (
        f"Render must start with {prefix!r}; got {rendered!r}"
    )
    return rendered[len(prefix):].lstrip(" ")


def _assert_positional_order_v2(body: str, rendered: str) -> None:
    """
    Token symbols present in the body must appear in §2 POSITIONAL order.
    """
    seen_positions: list[tuple[str, int]] = []
    for sym in POSITIONAL_ORDER:
        # Match symbol at start or after a space, followed by a value char.
        m = re.search(rf"(?:(?<=\s)|^){re.escape(sym)}(?=[\d\-LMHR])", body)
        if m is not None:
            seen_positions.append((sym, m.start()))

    for i in range(1, len(seen_positions)):
        prev_sym, prev_pos = seen_positions[i - 1]
        cur_sym, cur_pos = seen_positions[i]
        assert cur_pos > prev_pos, (
            f"§2 POSITIONAL violation: {cur_sym!r} appears before "
            f"{prev_sym!r} in render: {rendered!r}"
        )


def _assert_has_hour_or_null(rendered: str, symbol: str) -> None:
    """
    For a forecast token symbol, assert that wherever it appears in the
    rendered line it carries @hour OR is in null-form ('{sym}-').

    Acceptable forms:
      - '{sym}-'                    (null)
      - '{sym}{val}@{h}'            (threshold == max optimisation)
      - '{sym}{val}@{h}({mx}@{h})'  (threshold + peak)
    """
    # Anchor at start or whitespace; HR is special (can be followed directly
    # by 'TH:' as part of vigilance fusion — see _assert_hr_th_fusion).
    pattern = (
        r"(?:(?<=\s)|^)" + re.escape(symbol)
        + r"(?:-|"                              # null form
        + r"[\d\.LMH]+%?@\d{1,2}"               # value@hour (no leading zero)
        + r"(?:\([\d\.LMH]+%?@\d{1,2}\))?"      # optional (max@hour)
        + r")"
    )
    assert re.search(pattern, rendered), (
        f"Token {symbol!r} present without @hour or null-form in: {rendered!r}"
    )


def _assert_hr_th_fusion(rendered: str) -> None:
    """
    sms_format.md §3.3/§3.4: HR and Vigilance-TH fuse without space.
    Acceptable forms:
      - 'HR:-TH:-'
      - 'HR:{L|M|H|R}@{h}TH:{L|M|H|R}@{h}'
    """
    if "HR:" not in rendered:
        return
    fusion_re = re.compile(
        r"HR:(?:-TH:-|"
        r"[LMHR]@\d{1,2}TH:(?:-|[LMHR]@\d{1,2}))"
    )
    assert fusion_re.search(rendered), (
        f"HR/TH must fuse without space (HR:-TH:- or HR:X@hTH:X@h). Got: {rendered!r}"
    )


def _assert_no_legacy_t_token(rendered: str) -> None:
    """
    'T' as a standalone token (legacy form like 'T12/18') is forbidden.
    Only N, D, TH:, TH+:, and HR: are allowed.
    """
    assert not re.search(r"(?:(?<=\s)|^)T\d", rendered), (
        f"Legacy 'T{{n}}' token detected — only N/D allowed. Render: {rendered!r}"
    )
    assert not re.search(r"(?:(?<=\s)|^)T-(?=\s|$)", rendered), (
        f"Legacy 'T-' null token detected — only N-/D- allowed. Render: {rendered!r}"
    )


def test_render_conforms_to_sms_format_v2():
    """
    Structural conformance against sms_format.md v2.0 for all 5 goldens.

    Replaces the deleted byte-equal cross-check against legacy
    src/formatters/sms_trip.py (see output_token_builder.md §A1).

    Checks per golden:
      a) Stage-prefix '{Name}:' at the start.
      b) Token order §2 positional (N before D before R before PR before W
         before G before TH: before TH+:).
      c) Forecast tokens (R, PR, W, G, TH:, TH+:, HR:) carry @hour OR are
         in null-form '{sym}-'.
      d) HR/TH-fusion without space (FR-only).
      e) No standalone 'T' token (legacy 'T12/18' is forbidden).
    """
    for stem, meta in GOLDENS.items():
        line = _build_golden_line(stem)
        rendered = line.render(160)
        stage_name = meta["stage_name"]

        # (a) Stage-prefix
        body = _strip_stage_prefix(rendered, stage_name)

        # (b) §2 POSITIONAL order
        _assert_positional_order_v2(body, rendered)

        # (c) Forecast-tokens have @hour or null-form
        for sym in FORECAST_TOKENS:
            if sym + "-" in rendered or re.search(
                rf"(?:(?<=\s)|^){re.escape(sym)}[\d\.LMH]", rendered
            ):
                _assert_has_hour_or_null(rendered, sym)

        # (d) HR/TH-Fusion without space
        _assert_hr_th_fusion(rendered)

        # (e) No standalone 'T' token
        _assert_no_legacy_t_token(rendered)
