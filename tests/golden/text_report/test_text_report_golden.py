"""
Plain-Text-Goldens für render_text_report (β4 — TDD RED Phase).

SPEC: docs/specs/modules/wintersport_profile_consolidation.md §A4
TESTS-SPEC: docs/specs/tests/wintersport_profile_consolidation_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β4

RED-Zustand (jetzt):
  Golden-Datei `tests/golden/text_report/stubaier-skitour-evening.txt`
  existiert noch NICHT → pytest.fail.
  Außerdem fehlt `src/output/renderers/text_report` → ModuleNotFoundError.

GREEN-Zustand (nach β4-Implementation):
  Developer friert die Golden-Datei aus dem implementierten Renderer ein
  (nicht aus altem WintersportFormatter.format()-Output kopieren — Spec §8.2).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
    TokenLine,
)

GOLDEN_DIR = Path(__file__).parent


def _read_golden(stem: str) -> str:
    """Read frozen plain-text golden. RED if file missing."""
    path = GOLDEN_DIR / f"{stem}.txt"
    if not path.exists():
        pytest.fail(
            f"Plain-Text-Golden fehlt: {path}\n"
            f"Spec §A4 verlangt einen Golden vor Implementation-Verifikation. "
            f"In Phase 6 (Implement) friert der Developer den render_text_report-"
            f"Output für die Stubaier-Skitour-Fixture in diese Datei ein."
        )
    return path.read_text(encoding="utf-8")


def _stubaier_token_line() -> TokenLine:
    """Synthetische Stubaier-Skitour TokenLine (Wintersport)."""
    today = DailyForecast(
        temp_min_c=-15.0, temp_max_c=-5.0,
        rain_hourly=(),
        pop_hourly=(),
        wind_hourly=(HourlyValue(12, 45.0),),
        gust_hourly=(HourlyValue(12, 70.0),),
        thunder_hourly=(),
        snow_depth_cm=180.0,
        snow_new_24h_cm=25.0,
        snowfall_limit_m=1800.0,
        avalanche_level=3,
        wind_chill_c=-28.0,
    )
    forecast = NormalizedForecast(days=(today,))
    config = [
        MetricSpec(symbol="N", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="SN", enabled=True),
        MetricSpec(symbol="SN24+", enabled=True),
        MetricSpec(symbol="SFL", enabled=True),
        MetricSpec(symbol="AV", enabled=True),
        MetricSpec(symbol="WC", enabled=True),
    ]
    return build_token_line(
        forecast, config,
        report_type="evening",
        stage_name="Stubaier",
        profile="wintersport",
    )


def _stubaier_summary_rows() -> list[tuple[str, str]]:
    return [
        ("Temperatur", "-15.0 bis -5.0°C (Gipfel)"),
        ("Wind Chill", "-28.0°C (Gipfel)"),
        ("Wind", "45 km/h (Gipfel)"),
        ("Böen", "70 km/h (Gipfel)"),
        ("Schneehöhe", "180 cm (Gipfel)"),
        ("Neuschnee", "25 cm"),
        ("Schneefallgr.", "1800 m"),
    ]


def _stubaier_waypoint_details():
    """Build deterministic waypoint_details list — fixed Stubaier fixture."""
    from src.output.adapters.trip_result import WaypointDetail
    return [
        WaypointDetail(
            id="G1", name="Start", elevation_m=1700,
            time_window="08:00-10:00",
            lines=("-5.0°C", "Wind 15 km/h", "trocken"),
        ),
        WaypointDetail(
            id="G2", name="Gipfel", elevation_m=3200,
            time_window="11:00-13:00",
            lines=(
                "-15.0°C (gefühlt -28.0°C)",
                "Wind 45 km/h (Böen 70)",
                "trocken",
            ),
        ),
    ]


def test_golden_stubaier_skitour_evening():
    """Stubaier Skitour Evening: Wintersport-Long-Report bit-identisch.

    Golden wird in Phase 6 vom Developer eingefroren — nicht aus altem
    WintersportFormatter kopiert (Spec §8.2).
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _stubaier_token_line()
    body = render_text_report(
        token_line,
        waypoint_details=_stubaier_waypoint_details(),
        summary_rows=_stubaier_summary_rows(),
        avalanche_regions=("AT-7",),
        report_type="evening",
        trip_name="Stubaier Skitour",
        trip_date="2026-01-15",
    )

    expected = _read_golden("stubaier-skitour-evening")
    assert body == expected, (
        f"Long-Report-Drift gegen Golden.\n"
        f"Bit-Vergleich gegen tests/golden/text_report/stubaier-skitour-evening.txt "
        f"fehlgeschlagen."
    )
