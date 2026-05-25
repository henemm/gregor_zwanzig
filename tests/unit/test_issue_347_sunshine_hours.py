"""
Unit Tests: Issue #347 — Sonnenstunden-Berechnung per DNI-Interpolation

TDD RED phase: Diese Tests MUESSEN JETZT FEHLSCHLAGEN, weil die neue Logik
(DNI-Interpolation, proportionaler Cloud-Fallback), die neue Signatur
(settings-Parameter) und die neuen Config-Felder noch nicht existieren.

KEINE Mocks (Projekt-Regel): echte ForecastDataPoint- und Settings-Instanzen.

Spec: docs/specs/modules/issue_347_sunshine_hours.md
"""
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.weather_metrics import WeatherMetricsService
from app.models import ForecastDataPoint
from app.config import Settings
from app.metric_catalog import get_metric

import output.renderers.email.helpers as email_helpers
from formatters.trip_report import TripReportFormatter


def _dp(ts_hour, **kwargs):
    """Helper: erzeuge einen echten ForecastDataPoint zu einer Tagesstunde."""
    return ForecastDataPoint(ts=datetime(2026, 2, 4, ts_hour, 0), **kwargs)


class TestAC1DniInterpolationFraction:
    """AC-1 (Kern-Bug): dni_wm2 zwischen min und max liefert Bruchwert, nicht 0."""

    def test_dni_90_with_clouds_gives_fraction(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=90 (zwischen 60 und 180) und 45% Bewoelkung
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe > 0.0 und < 1.0 (Bruchwert, nicht 0)

        Erwartung RED: alter Code liefert 0 (toter sunshine_duration_s-Pfad,
        kein DNI-Hauptweg).
        """
        dp = _dp(12, dni_wm2=90, cloud_total_pct=45)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert 0.0 < hours < 1.0, (
            f"AC-1: dni=90 muss Bruchwert (0..1) ergeben, war {hours}"
        )


class TestAC2DniAtOrAboveMax:
    """AC-2: dni_wm2 >= max (Default 180) liefert 1.0 h pro Stunde."""

    def test_dni_180_gives_full_hour(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=180 (Default-Maximum)
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe == 1.0

        Erwartung RED: alter Code liefert 0.
        """
        dp = _dp(12, dni_wm2=180)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 1.0, f"AC-2: dni=180 muss 1.0 h ergeben, war {hours}"

    def test_dni_above_max_caps_at_full_hour(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=400 (deutlich ueber Maximum)
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe == 1.0 (Deckelung, kein Ueberlauf)
        """
        dp = _dp(12, dni_wm2=400)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 1.0, f"AC-2: dni=400 muss auf 1.0 h gedeckelt sein, war {hours}"


class TestAC3DniAtOrBelowMinOrNone:
    """AC-3: dni_wm2 <= min ODER None ohne Cloud-Fallback liefert 0.0."""

    def test_dni_60_gives_zero(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=60 (Default-Minimum)
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe == 0.0
        """
        dp = _dp(12, dni_wm2=60)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 0.0, f"AC-3: dni=60 muss 0.0 ergeben, war {hours}"

    def test_dni_none_without_clouds_gives_zero(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=None und cloud_total_pct=None
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe == 0.0 (kein DNI, kein Cloud-Fallback)
        """
        dp = _dp(12, dni_wm2=None, cloud_total_pct=None)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 0.0, f"AC-3: dni=None ohne Clouds muss 0.0 ergeben, war {hours}"


class TestAC4LowElevationNotPenalized:
    """AC-4: Lage unter 2500 m mit dni_wm2=150 liefert > 0 (vorher konstant 0)."""

    def test_low_elevation_with_dni_gives_positive(self):
        """
        GIVEN: dni_wm2=150 bei elevation_m=800 (unter 2500 m)
        WHEN:  calculate_sunny_hours([dp], elevation_m=800)
        THEN:  Rueckgabe > 0.0

        Erwartung RED: alter Code ignoriert DNI komplett, Cloud-Fallback greift
        nur ab 2500 m -> 0.
        """
        dp = _dp(12, dni_wm2=150)
        hours = WeatherMetricsService.calculate_sunny_hours([dp], elevation_m=800)
        assert hours > 0.0, (
            f"AC-4: Lage unter 2500 m mit dni=150 muss > 0 sein, war {hours}"
        )


class TestAC5GeosphereCloudProportionalFallback:
    """AC-5: dni_wm2=None + cloud_total_pct=40 -> proportionaler Wert 0.6."""

    def test_cloud_fallback_proportional(self):
        """
        GIVEN: ForecastDataPoint mit dni_wm2=None und cloud_total_pct=40 (Geosphere)
        WHEN:  calculate_sunny_hours([dp])
        THEN:  Rueckgabe == round((100 - 40) / 100, 1) == 0.6 (kein binaerer Cutoff)

        Erwartung RED: alter Code hat binaeren 30%-Cutoff nur ab 2500 m -> 0.
        """
        dp = _dp(12, dni_wm2=None, cloud_total_pct=40)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 0.6, (
            f"AC-5: cloud=40% muss proportional 0.6 h ergeben, war {hours}"
        )


class TestAC6Configurability:
    """AC-6: Custom Settings (min=100, max=200), dni=150 -> 0.5 (Mitte)."""

    def test_custom_dni_band(self):
        """
        GIVEN: Settings(sunny_dni_min_wm2=100, sunny_dni_max_wm2=200), dni=150
        WHEN:  calculate_sunny_hours([dp], settings=custom)
        THEN:  Rueckgabe == 0.5 (lineare Mitte des angepassten Bandes)

        Erwartung RED: neue Settings-Felder existieren nicht; alte Signatur
        kennt keinen settings-Parameter.
        """
        custom = Settings(sunny_dni_min_wm2=100, sunny_dni_max_wm2=200)
        dp = _dp(12, dni_wm2=150)
        hours = WeatherMetricsService.calculate_sunny_hours([dp], settings=custom)
        assert hours == 0.5, (
            f"AC-6: dni=150 im Band 100..200 muss 0.5 ergeben, war {hours}"
        )


class TestAC7DefaultsWithoutSettings:
    """AC-7: Aufruf ohne settings-Argument -> Defaults 60/180, kein Fehler."""

    def test_no_settings_uses_defaults(self):
        """
        GIVEN: dni=120 (genaue Mitte zwischen Default 60 und 180)
        WHEN:  calculate_sunny_hours([dp]) ohne settings-Argument
        THEN:  Rueckgabe == 0.5, kein AttributeError/TypeError

        Erwartung RED: alter Code liefert 0 (kein DNI-Hauptweg).
        """
        dp = _dp(12, dni_wm2=120)
        hours = WeatherMetricsService.calculate_sunny_hours([dp])
        assert hours == 0.5, (
            f"AC-7: dni=120 mit Defaults 60/180 muss 0.5 ergeben, war {hours}"
        )


class TestAC8TripSummaryUnitIsHours:
    """AC-8: Trip-Summary-Metrik 'sunshine' wird in h ausgegeben, nicht W/m²."""

    def test_sunshine_metric_unit_is_hours(self):
        """
        GIVEN: Metrik-Definition 'sunshine' im Katalog
        WHEN:  get_metric('sunshine')
        THEN:  unit == 'h' (Stundenwert), nicht 'W/m²'

        Erwartung RED: Katalog hat aktuell unit='W/m²'.
        """
        metric = get_metric("sunshine")
        assert metric.unit == "h", (
            f"AC-8: sunshine-Metrik muss Einheit 'h' haben, war '{metric.unit}'"
        )

    def test_sunshine_metric_aggregation_is_sum(self):
        """
        GIVEN: Metrik-Definition 'sunshine' im Katalog
        WHEN:  get_metric('sunshine')
        THEN:  default_aggregations == ('sum',) (Stundensumme statt DNI-Mittelwert)

        Erwartung RED: Katalog hat aktuell default_aggregations=('avg',).
        """
        metric = get_metric("sunshine")
        assert metric.default_aggregations == ("sum",), (
            "AC-8: sunshine-Metrik muss ('sum',) aggregieren, war "
            f"{metric.default_aggregations}"
        )


class TestAC9ComparePathConsistency:
    """AC-9: Trip-Summary und Compare nutzen dieselbe Groesse (sunny_hours)."""

    def test_sunshine_summary_field_is_sunny_hours(self):
        """
        GIVEN: Metrik-Definition 'sunshine' im Katalog
        WHEN:  get_metric('sunshine').summary_fields
        THEN:  Summary-Feld referenziert sunny_hours (h), nicht dni_avg_wm2 (W/m²)

        Erwartung RED: Katalog mappt aktuell {'avg': 'dni_avg_wm2'}.
        """
        metric = get_metric("sunshine")
        values = set(metric.summary_fields.values())
        assert "dni_avg_wm2" not in values, (
            "AC-9: sunshine-Metrik darf nicht mehr auf dni_avg_wm2 (W/m²) mappen, "
            f"war {metric.summary_fields}"
        )
        assert any("sunny_hours" in v for v in values), (
            "AC-9: sunshine-Metrik muss sunny_hours (h) als Summary-Feld nutzen, "
            f"war {metric.summary_fields}"
        )


# ----------------------------------------------------------------------
# Echte Rendering-Tests (KEINE Mocks). Diese schliessen die BROKEN-Luecke:
# die alten AC-8/AC-9-Tests prueften nur Katalog-Metadaten, NICHT die
# tatsaechliche Ausgabe der beiden Renderer.
# ----------------------------------------------------------------------

class TestAC8TripSummaryRendersHours:
    """AC-8: Der Trip-Report-Renderer gibt den Stundenwert MIT ' h'-Suffix aus.

    Regression-Guard fuer F001: vorher wurde dni_to_sunny_fraction(avg_dni)
    gerendert -> Pro-Stunde-Bruchwert (0..1) ohne Einheit, NICHT die Tagessumme.
    """

    def _build_row(self):
        """Block aus 8 Stunden DNI=120 (= je 0.5 h) -> erwartet 4.0 h Summe."""
        fmt = TripReportFormatter.__new__(TripReportFormatter)
        from zoneinfo import ZoneInfo
        fmt._tz = ZoneInfo("UTC")
        fmt._friendly_keys = set()  # sunshine NICHT friendly -> numerischer Pfad
        dps = [_dp(h, dni_wm2=120) for h in range(8, 16)]
        # _dp_to_row braucht eine dc; wir bauen die Block-Felder direkt.
        # Die 'sunshine'-Spalte traegt real die (summierte) DNI -> non-None.
        from services.weather_metrics import WeatherMetricsService as _WMS
        row = {
            "time": "08",
            "sunshine": sum(d.dni_wm2 for d in dps),  # rohe DNI-Summe = 960
            "_dni_wm2": sum(d.dni_wm2 for d in dps) / len(dps),
            "_sunny_hours": _WMS.calculate_sunny_hours(dps),
        }
        return fmt, row, dps

    def test_trip_summary_renders_hours_with_suffix(self):
        fmt, row, dps = self._build_row()
        out = fmt._fmt_val("sunshine", row.get("sunshine"), row=row)
        # 8 h * 0.5 = 4.0 h
        assert out == "4.0 h", (
            f"AC-8/F001: Trip-Summary muss '4.0 h' rendern (Tagessumme mit "
            f"Einheit), war '{out}'"
        )

    def test_trip_summary_not_fraction_not_wm2(self):
        fmt, row, dps = self._build_row()
        out = fmt._fmt_val("sunshine", row.get("sunshine"), row=row)
        assert "h" in out, f"F001: Einheiten-Suffix ' h' fehlt: '{out}'"
        # Darf NICHT der Bruchwert dni_to_sunny_fraction(avg=120)=0.5 sein
        assert not out.startswith("0.5"), (
            f"F001: Bruchwert statt Tagessumme gerendert: '{out}'"
        )
        # Darf NICHT die rohe DNI-Summe (960 W/m²) sein
        assert "960" not in out, f"F001: rohe DNI-Summe gerendert: '{out}'"


class TestAC8EmailRendererRendersHours:
    """AC-8/F002: Der E-Mail-Renderer (echter Auslieferungskanal) gibt
    Sonnenstunden in 'h' aus, nicht die rohe DNI-Summe (W/m²)."""

    def _build_row(self):
        dps = [_dp(h, dni_wm2=120) for h in range(8, 16)]
        from services.weather_metrics import WeatherMetricsService as _WMS
        row = {
            "time": "08",
            "sunshine": sum(d.dni_wm2 for d in dps),  # = 960, die "rohe Summe"
            "_dni_wm2": sum(d.dni_wm2 for d in dps) / len(dps),
            "_sunny_hours": _WMS.calculate_sunny_hours(dps),
        }
        return row, dps

    def test_email_renderer_renders_hours_with_suffix(self):
        row, dps = self._build_row()
        out = email_helpers.fmt_val(
            "sunshine", row.get("sunshine"), friendly_keys=set(), row=row
        )
        assert out == "4.0 h", (
            f"AC-8/F002: E-Mail-Renderer muss '4.0 h' rendern, war '{out}'"
        )

    def test_email_renderer_not_raw_dni_sum(self):
        row, dps = self._build_row()
        out = email_helpers.fmt_val(
            "sunshine", row.get("sunshine"), friendly_keys=set(), row=row
        )
        # Vorher: f"{val:.0f}" mit val=960 (rohe DNI-Summe in W/m²)
        assert out != "960", f"F002: rohe DNI-Summe (W/m²) gerendert: '{out}'"
        assert "h" in out, f"F002: Einheiten-Suffix ' h' fehlt: '{out}'"


class TestAC9RenderConsistency:
    """AC-9: Derselbe Segment-Input ergibt im Trip-Pfad denselben Stundenwert
    wie calculate_sunny_hours() direkt — dieselbe Funktion, dieselbe Groesse."""

    def test_same_input_same_hours_across_paths(self):
        dps = [_dp(h, dni_wm2=v) for h, v in zip(range(8, 13), [80, 120, 180, 60, 150])]
        direct = WeatherMetricsService.calculate_sunny_hours(dps)
        # 'sunshine'-Spalte traegt real die DNI-Summe (non-None)
        col_val = sum(d.dni_wm2 for d in dps)

        # Trip-Renderer-Pfad
        fmt = TripReportFormatter.__new__(TripReportFormatter)
        from zoneinfo import ZoneInfo
        fmt._tz = ZoneInfo("UTC")
        fmt._friendly_keys = set()
        trip_row = {"time": "08", "sunshine": col_val, "_sunny_hours": direct}
        trip_out = fmt._fmt_val("sunshine", trip_row["sunshine"], row=trip_row)

        # E-Mail-Renderer-Pfad
        email_row = {"time": "08", "sunshine": col_val, "_sunny_hours": direct}
        email_out = email_helpers.fmt_val(
            "sunshine", email_row["sunshine"], friendly_keys=set(), row=email_row
        )

        expected = f"{direct:.1f} h"
        assert trip_out == expected, (
            f"AC-9: Trip-Pfad '{trip_out}' != direkt '{expected}'"
        )
        assert email_out == expected, (
            f"AC-9: E-Mail-Pfad '{email_out}' != direkt '{expected}'"
        )
        assert trip_out == email_out, (
            f"AC-9: Trip '{trip_out}' und E-Mail '{email_out}' inkongruent"
        )


class TestAC9SegmentSummaryPrecomputed:
    """AC-9: compute_basis_metrics befuellt sunny_hours via derselben Funktion
    (Single Source of Truth) — Konsistenz mit dem Compare-Pfad."""

    def test_summary_sunny_hours_matches_direct(self):
        from app.models import NormalizedTimeseries, ForecastMeta, Provider
        dps = [_dp(h, dni_wm2=120, t2m_c=10.0, cloud_total_pct=40) for h in range(8, 16)]
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0)
        ts = NormalizedTimeseries(meta=meta, data=dps)

        svc = WeatherMetricsService()
        summary = svc.compute_basis_metrics(ts)

        direct = WeatherMetricsService.calculate_sunny_hours(dps)
        assert summary.sunny_hours == direct, (
            f"AC-9: SegmentWeatherSummary.sunny_hours ({summary.sunny_hours}) "
            f"muss calculate_sunny_hours ({direct}) entsprechen"
        )
        assert summary.sunny_hours == 4.0, (
            f"AC-9: 8 h DNI=120 muss 4.0 h ergeben, war {summary.sunny_hours}"
        )
