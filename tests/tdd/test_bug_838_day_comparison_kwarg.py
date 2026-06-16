"""
Bug #838: Scheduler ruft format_email() mit day_comparison-Kwarg auf,
der in 945a824c versehentlich entfernt wurde → TypeError bei jedem Briefing-Versand.

AC-1: format_email() akzeptiert day_comparison als optionalen Parameter.
AC-2: Kein TypeError wenn der Scheduler format_email() mit day_comparison aufruft.
"""
import inspect
import sys


def test_ac1_format_email_accepts_day_comparison():
    """AC-1: format_email() hat day_comparison als optionalen Parameter."""
    sys.path.insert(0, "src")
    from formatters.trip_report import TripReportFormatter
    sig = inspect.signature(TripReportFormatter.format_email)
    assert "day_comparison" in sig.parameters, (
        "format_email() hat keinen day_comparison-Parameter — "
        "Regression: Feature #750/#752 (Vortag-Vergleich) ist nicht erreichbar"
    )
    param = sig.parameters["day_comparison"]
    assert param.default is None, (
        "day_comparison muss Optional mit Default=None sein (Backward-Compat)"
    )


def test_ac2_format_email_callable_with_day_comparison_none():
    """AC-2: format_email(day_comparison=None) wirft keinen TypeError."""
    sys.path.insert(0, "src")
    from unittest.mock import MagicMock
    from formatters.trip_report import TripReportFormatter

    formatter = TripReportFormatter()
    seg = MagicMock()
    seg.has_error = False
    seg.segment.start_time.hour = 8
    seg.segment.end_time.hour = 16
    seg.segment.start_point.elevation_m = 500
    seg.segment.segment_id = "1"
    seg.timeseries = None
    seg.aggregated.temp_max_c = 20.0
    seg.aggregated.wind_max_kmh = 30.0
    seg.aggregated.gust_max_kmh = 45.0
    seg.aggregated.precip_sum_mm = 0.0
    seg.aggregated.thunder_level = None
    seg.aggregated.pop_pct = 10.0

    # Nur prüfen: kein TypeError durch day_comparison, auch bei None
    try:
        formatter.format_email(
            segments=[seg],
            trip_name="Testtrip",
            report_type="morning",
            day_comparison=None,
        )
    except TypeError as e:
        if "day_comparison" in str(e):
            raise AssertionError(
                f"format_email() wirft TypeError für day_comparison: {e}"
            ) from e
    except Exception:
        pass  # Andere Fehler (Wetterdaten fehlen) sind hier irrelevant
