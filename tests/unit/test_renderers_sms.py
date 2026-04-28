"""
Direktaufruf-Tests für render_sms() (β3 — TDD RED Phase).

SPEC: docs/specs/modules/output_channel_renderers.md §A3 + §"render_sms() Signatur"
TESTS-SPEC: docs/specs/tests/output_channel_renderers_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β3

RED-Zustand (jetzt):
  src/output/renderers/sms/ existiert noch NICHT → ImportError.

GREEN-Zustand (nach β3-Implementation):
  render_sms(token_line, *, max_length=160) -> str delegiert an
  output.tokens.render.render_line() (β1) und ist bit-identisch.
"""
from __future__ import annotations

import pytest

from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    NormalizedForecast,
)
from src.output.tokens.render import render_line


def _short_token_line(stage_name: str = "GR20 E3"):
    today = DailyForecast(
        temp_min_c=12.0, temp_max_c=18.0,
        rain_hourly=(HourlyValue(15, 0.5),),
        pop_hourly=(HourlyValue(15, 30.0),),
        wind_hourly=(HourlyValue(13, 18.0),),
        gust_hourly=(HourlyValue(13, 28.0),),
    )
    return build_token_line(
        NormalizedForecast(days=(today,)),
        None,
        report_type="evening",
        stage_name=stage_name,
    )


def _long_token_line(stage_name: str = "Sehr Lange Etappe"):
    today = DailyForecast(
        temp_min_c=12.0, temp_max_c=24.0,
        rain_hourly=tuple(HourlyValue(h, 1.5) for h in range(6, 18)),
        pop_hourly=tuple(HourlyValue(h, 80.0) for h in range(6, 18)),
        wind_hourly=tuple(HourlyValue(h, 30.0) for h in range(6, 18)),
        gust_hourly=tuple(HourlyValue(h, 65.0) for h in range(6, 18)),
        thunder_hourly=tuple(HourlyValue(h, 3) for h in range(13, 18)),
    )
    tomorrow = DailyForecast(
        thunder_hourly=tuple(HourlyValue(h, 3) for h in range(14, 18)),
    )
    return build_token_line(
        NormalizedForecast(
            days=(today, tomorrow),
            provider="meteofrance", country="FR",
            vigilance_hr_level="H", vigilance_hr_hour=14,
            vigilance_th_level="H", vigilance_th_hour=17,
        ),
        None,
        report_type="evening",
        stage_name=stage_name,
    )


def test_render_sms_delegates_to_tokenline():
    """
    GIVEN: TokenLine mit bekanntem Wire-Format.
    WHEN:  render_sms(line) wird aufgerufen.
    THEN:  Output bit-identisch zu render_line(line, 160) (β1-Authority).

    RED: ModuleNotFoundError für src.output.renderers.sms.
    """
    from src.output.renderers.sms import render_sms  # noqa: F401

    line = _short_token_line()
    expected = render_line(line, 160)
    assert render_sms(line) == expected


def test_render_sms_respects_max_length():
    """
    GIVEN: TokenLine mit Roh-Länge >160 Zeichen.
    WHEN:  render_sms(line, max_length=160) aufgerufen.
    THEN:  len(output) <= 160 (§6 Truncation greift transitiv durch β1).
    """
    from src.output.renderers.sms import render_sms

    line = _long_token_line()
    out = render_sms(line, max_length=160)
    assert len(out) <= 160


def test_render_sms_v2_format():
    """
    GIVEN: TokenLine mit N=12, D=18 (sms_format.md v2.0 §2/§3).
    WHEN:  render_sms(line) aufgerufen.
    THEN:  Output enthält N12 und D18 (Tag-Min/Tag-Max),
           NICHT Legacy 'T12/18'.
    """
    from src.output.renderers.sms import render_sms

    line = _short_token_line()
    out = render_sms(line)
    assert "N12" in out, f"v2.0 erwartet 'N12' (Tag-Min): {out!r}"
    assert "D18" in out, f"v2.0 erwartet 'D18' (Tag-Max): {out!r}"
    assert "T12/18" not in out, (
        f"Legacy 'T12/18' Format verboten in v2.0: {out!r}"
    )
