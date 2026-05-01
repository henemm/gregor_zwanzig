"""
Unit tests for src/output/renderers/text_report — TDD RED Phase β4.

SPEC: docs/specs/modules/wintersport_profile_consolidation.md §A4, §A5
TESTS-SPEC: docs/specs/tests/wintersport_profile_consolidation_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β4

RED-Zustand (jetzt):
  src/output/renderers/text_report/ existiert noch NICHT → ModuleNotFoundError.

GREEN-Zustand (nach β4-Implementation):
  render_text_report(token_line, *, waypoint_details, summary_rows,
                     avalanche_regions, report_type, trip_name, trip_date) -> str
  ist eine Pure Function. Output deterministisch.

Tests bauen TokenLine + WaypointDetail direkt, ohne den Adapter — pure
Renderer-Tests gemäß §A5 (profile-agnostisch).
"""
from __future__ import annotations


from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
    TokenLine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wintersport_token_line(stage_name: str = "Stubaier") -> TokenLine:
    """Build a TokenLine via build_token_line(profile='wintersport').

    Synthetic forecast mit AV+WC+SN+SN24++SFL — entspricht heutigem
    WintersportFormatter-Output.
    """
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
        stage_name=stage_name,
        profile="wintersport",
    )


def _standard_token_line(stage_name: str = "GR20") -> TokenLine:
    """Build a TokenLine via build_token_line(profile='standard') —
    keine Wintersport-Tokens. Für is_profile_agnostic-Test.
    """
    today = DailyForecast(
        temp_min_c=14.0, temp_max_c=24.0,
        rain_hourly=(HourlyValue(15, 0.2),),
        pop_hourly=(HourlyValue(15, 30.0),),
        wind_hourly=(HourlyValue(13, 18.0),),
        gust_hourly=(HourlyValue(13, 28.0),),
    )
    forecast = NormalizedForecast(days=(today,))
    return build_token_line(
        forecast, None,
        report_type="evening",
        stage_name=stage_name,
        profile="standard",
    )


def _waypoint_details_stubaier():
    """Build deterministic waypoint_details list for tests."""
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
            lines=("-15.0°C (gefühlt -28.0°C)", "Wind 45 km/h (Böen 70)", "trocken"),
        ),
    ]


def _summary_rows_stubaier():
    return [
        ("Temperatur", "-15.0 bis -5.0°C (Gipfel)"),
        ("Wind Chill", "-28.0°C (Gipfel)"),
        ("Wind", "45 km/h (Gipfel)"),
        ("Böen", "70 km/h (Gipfel)"),
        ("Schneehöhe", "180 cm (Gipfel)"),
        ("Neuschnee", "25 cm"),
        ("Schneefallgr.", "1800 m"),
    ]


def _common_kwargs(
    *,
    avalanche_regions: tuple[str, ...] = ("AT-7",),
    summary_rows=None,
    waypoint_details=None,
    trip_name: str = "Stubaier Skitour",
    trip_date: str = "2026-01-15",
    report_type: str = "evening",
) -> dict:
    return {
        "waypoint_details": waypoint_details
            if waypoint_details is not None
            else _waypoint_details_stubaier(),
        "summary_rows": summary_rows
            if summary_rows is not None
            else _summary_rows_stubaier(),
        "avalanche_regions": avalanche_regions,
        "report_type": report_type,
        "trip_name": trip_name,
        "trip_date": trip_date,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_renders_header_summary_waypoints():
    """
    GIVEN: TokenLine + Stubaier-Trip-Daten.
    WHEN:  render_text_report(token_line, ...) aufgerufen.
    THEN:  Output enthält Trip-Name (UPPERCASE), start_date, report_type
           als Titel, 'ZUSAMMENFASSUNG', 'WEGPUNKT-DETAILS'.

    Spec §A4 — Long-Report-Inhaltserhalt.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    body = render_text_report(token_line, **_common_kwargs())

    assert "STUBAIER SKITOUR" in body, (
        f"Trip-Name in UPPERCASE nicht im Output: {body!r}"
    )
    assert "2026-01-15" in body, f"Trip-Date nicht im Output: {body!r}"
    assert "Evening" in body, f"Report-Type-Titel nicht im Output: {body!r}"
    assert "ZUSAMMENFASSUNG" in body
    assert "WEGPUNKT-DETAILS" in body


def test_renders_avalanche_block_when_regions_present():
    """
    GIVEN: avalanche_regions=('AT-7',).
    WHEN:  render_text_report(token_line, ...) aufgerufen.
    THEN:  Output enthält 'LAWINENREGIONEN' und 'AT-7'.

    Spec §A4 — Lawinen-Block.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    body = render_text_report(
        token_line, **_common_kwargs(avalanche_regions=("AT-7",)),
    )

    assert "LAWINENREGIONEN" in body
    assert "AT-7" in body


def test_omits_avalanche_block_when_regions_empty():
    """
    GIVEN: avalanche_regions=().
    WHEN:  render_text_report(token_line, ...) aufgerufen.
    THEN:  Output enthält **kein** 'LAWINENREGIONEN'.

    Spec §7 Fehlerbehandlung — leere Regionen → Block weglassen.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    body = render_text_report(
        token_line, **_common_kwargs(avalanche_regions=()),
    )

    assert "LAWINENREGIONEN" not in body, (
        f"LAWINENREGIONEN darf bei leeren Regionen nicht erscheinen: {body!r}"
    )


def test_renders_token_line_from_token_line_arg():
    """
    GIVEN: token_line mit Wintersport-Tokens (Stage-Prefix 'Stubaier:').
    WHEN:  render_text_report(token_line, ...) aufgerufen.
    THEN:  Output enthält die Token-Zeile (Stage-Prefix sichtbar).

    Spec §A4: 'Token-Zeile (NEU): Am Anfang oder Ende des Reports steht
    das render_sms(token_line)-Output'. Position ist Implementation-Detail,
    Test prüft nur Vorhandensein.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line(stage_name="Stubaier")
    body = render_text_report(token_line, **_common_kwargs())

    assert "Stubaier:" in body, (
        f"Token-Zeile mit Stage-Prefix 'Stubaier:' nicht im Output: {body!r}"
    )


def test_is_pure_function():
    """
    GIVEN: Zwei Aufrufe mit identischen Inputs.
    WHEN:  render_text_report(...) zweimal aufgerufen.
    THEN:  Outputs sind ==.

    Pure Function — Determinismus gemäß Spec §3.3 / §A5.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    out_a = render_text_report(token_line, **_common_kwargs())
    out_b = render_text_report(token_line, **_common_kwargs())
    assert out_a == out_b


def test_is_profile_agnostic():
    """
    GIVEN: token_line aus profile='standard' (keine Wintersport-Tokens).
    WHEN:  render_text_report(token_line, ...) aufgerufen.
    THEN:  Renderer crasht nicht; Output enthält Trip-Name + Header.

    Spec §A5 — Renderer fragt nicht nach profile; nimmt was in token_line ist.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _standard_token_line(stage_name="GR20")
    body = render_text_report(
        token_line,
        **_common_kwargs(
            trip_name="GR20 Korsika",
            trip_date="2026-07-11",
            summary_rows=[("Temperatur", "14.0 bis 24.0°C (Start)")],
            waypoint_details=[],
        ),
    )

    assert isinstance(body, str)
    assert "GR20 KORSIKA" in body
    assert "Temperatur" in body


def test_omits_summary_rows_when_empty():
    """
    GIVEN: summary_rows=[].
    WHEN:  render_text_report(...) aufgerufen.
    THEN:  Output enthält 'ZUSAMMENFASSUNG' Header (oder Block leer ohne
           Crash).

    Spec §7 Fehlerbehandlung.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    body = render_text_report(
        token_line, **_common_kwargs(summary_rows=[]),
    )

    # Header existiert weiterhin
    assert "ZUSAMMENFASSUNG" in body
    # Kein Crash, Body ist String
    assert isinstance(body, str)


def test_omits_waypoint_details_when_empty():
    """
    GIVEN: waypoint_details=[].
    WHEN:  render_text_report(...) aufgerufen.
    THEN:  Output enthält 'WEGPUNKT-DETAILS' Header, Body-Sektion leer
           ohne Crash.

    Spec §7 Fehlerbehandlung — leere Wegpunkte.
    """
    from src.output.renderers.text_report import render_text_report

    token_line = _wintersport_token_line()
    body = render_text_report(
        token_line, **_common_kwargs(waypoint_details=[]),
    )

    assert "WEGPUNKT-DETAILS" in body
    assert isinstance(body, str)
