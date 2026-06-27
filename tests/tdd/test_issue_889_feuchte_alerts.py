"""TDD RED — Issue #889: Vorboten-Metriken aus Abweichungs-Alerts entfernen.

Sechs Anzeige-Metriken (humidity, dewpoint, rain_probability, cloud_total,
pressure, wind_chill) lösen aktuell Abweichungs-Alerts aus, obwohl sie keine
eigenständige Entscheidungsrelevanz haben. Sie sollen KEINEN Alert mehr
auslösen, im Briefing aber weiter als Spalten erscheinen.

Diese Tests beweisen das Verhalten aus Nutzersicht — KEINE Mocks (CLAUDE.md):
echte Service-Aufrufe mit echten Python-Objekten, echter Render-Pfad,
echtes Dateisystem unter `data/users/<user_id>/`.

Erwartung HEUTE (RED):
- AC-1: `from_display_config` mit aktivierter Feuchte + 80-Prozentpunkte-Delta
  erzeugt aktuell einen Change-Eintrag für `humidity_avg_pct` (Bug). Soll: keiner.
- AC-2: persistierte `humidity`-AlertRule erzeugt aktuell über das
  Field-Mapping einen Feuchte-Change-Eintrag (Bug). Soll: keiner.
- AC-3: `expand_preset("standard")` enthält aktuell eine `HUMIDITY`-Regel (Bug).
  Soll: keine.

Regression-Guards (dürfen schon GRÜN sein):
- AC-4: die 6 Metriken erscheinen weiter als Spalten mit numerischen Werten.
- AC-5: behaltene Alert-Metriken (Wind, Niederschlag) erzeugen weiter Changes.

SPEC: docs/specs/modules/issue_889_feuchte_alerts.md
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.metric_catalog import get_metric
from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from services.weather_change_detection import WeatherChangeDetectionService

# Die sechs Vorboten-Metriken (Metrik-IDs) und ihre Summary-Felder.
FEUCHTE_METRIC_IDS = [
    "humidity",
    "dewpoint",
    "rain_probability",
    "cloud_total",
    "pressure",
    "wind_chill",
]
FEUCHTE_SUMMARY_FIELDS = {
    "humidity_avg_pct",
    "dewpoint_avg_c",
    "pop_max_pct",
    "cloud_avg_pct",
    "pressure_avg_hpa",
    "wind_chill_min_c",
}


# ───────────────────────── Builder (kein Mock) ──────────────────────────────


def _segment(segment_id: int | str = 1) -> TripSegment:
    start = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=10.0,
        ascent_m=500,
        descent_m=200,
    )


def _timeseries(points: list[ForecastDataPoint] | None = None) -> NormalizedTimeseries:
    return NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        ),
        data=points or [],
    )


def _weather_data(summary: SegmentWeatherSummary) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=_timeseries(),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _display_config_with_feuchte() -> UnifiedWeatherDisplayConfig:
    """Trip-Display-Config mit allen 6 Vorboten-Metriken aktiviert."""
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, format_mode="raw")
        for mid in FEUCHTE_METRIC_IDS
    ]
    return UnifiedWeatherDisplayConfig(trip_id="tdd-889", metrics=metrics)


# ──────────────────────────── AC-1 ──────────────────────────────────────────


class TestAC1DisplayConfigNoFeuchteAlert:
    """AC-1: aktivierte Anzeige-Metriken + großes Delta → kein Feuchte-Change."""

    def test_huge_humidity_delta_no_change_entry(self):
        """GIVEN Feuchte (und 5 weitere Vorboten) aktiviert, +80%-Punkte Feuchte
        WHEN from_display_config().detect_changes()
        THEN kein Change-Eintrag für eine der 6 Vorboten-Metriken.
        """
        service = WeatherChangeDetectionService.from_display_config(
            _display_config_with_feuchte()
        )

        old = SegmentWeatherSummary(
            humidity_avg_pct=10,
            dewpoint_avg_c=2.0,
            pop_max_pct=5,
            cloud_avg_pct=5,
            pressure_avg_hpa=1000.0,
            wind_chill_min_c=5.0,
        )
        new = SegmentWeatherSummary(
            humidity_avg_pct=90,        # +80 Prozentpunkte
            dewpoint_avg_c=22.0,        # +20 °C
            pop_max_pct=95,             # +90 Prozentpunkte
            cloud_avg_pct=95,           # +90 Prozentpunkte
            pressure_avg_hpa=1040.0,    # +40 hPa
            wind_chill_min_c=30.0,      # +25 °C
        )

        changes = service.detect_changes(_weather_data(old), _weather_data(new))

        feuchte_changes = [c for c in changes if c.metric in FEUCHTE_SUMMARY_FIELDS]
        assert feuchte_changes == [], (
            "Vorboten-Metriken dürfen keinen Abweichungs-Alert auslösen, "
            f"erzeugt wurden aber: {[c.metric for c in feuchte_changes]}"
        )


# ──────────────────────────── AC-2 ──────────────────────────────────────────


class TestAC2PersistedHumidityRule:
    """AC-2: alt-persistierte humidity-AlertRule lädt still, kein Feuchte-Change."""

    def test_humidity_alert_rule_loads_and_emits_nothing(self):
        """GIVEN eine persistiert anmutende humidity-AlertRule (metric=HUMIDITY)
        WHEN from_alert_rules().detect_changes() mit großem Feuchte-Delta
        THEN kein Lade-Crash und kein Feuchte-Change-Eintrag.
        """
        # Konstruktion der Rule darf nicht crashen (Enum-Wert bleibt erhalten).
        rule = AlertRule(
            id="legacy-humidity-1",
            kind=AlertRuleKind.ABSOLUTE,
            metric=AlertMetric.HUMIDITY,
            threshold=15.0,
            severity=AlertSeverity.WARNING,
            enabled=True,
        )

        service = WeatherChangeDetectionService.from_alert_rules([rule])

        old = SegmentWeatherSummary(humidity_avg_pct=10)
        new = SegmentWeatherSummary(humidity_avg_pct=95)

        changes = service.detect_changes(_weather_data(old), _weather_data(new))

        feuchte_changes = [c for c in changes if c.metric in FEUCHTE_SUMMARY_FIELDS]
        assert feuchte_changes == [], (
            "Alt-persistierte humidity-AlertRule darf keinen Feuchte-Alert mehr "
            f"erzeugen, erzeugt wurde aber: {[c.metric for c in feuchte_changes]}"
        )


# ──────────────────────────── AC-3 ──────────────────────────────────────────


class TestAC3PresetNoHumidity:
    """AC-3: Standard-Preset enthält keinen HUMIDITY-Eintrag."""

    @pytest.mark.parametrize("preset_name", ["standard", "entspannt", "sensibel"])
    def test_preset_has_no_humidity_rule(self, preset_name):
        """GIVEN ein frischer Trip-Kontext
        WHEN expand_preset() geladen wird
        THEN keine Regel mit metric == AlertMetric.HUMIDITY.
        """
        from services.alert_preset import expand_preset

        rules = expand_preset(preset_name)

        humidity_rules = [
            r for r in rules
            if r.metric == AlertMetric.HUMIDITY or str(r.metric).endswith("humidity")
        ]
        assert humidity_rules == [], (
            f"Preset '{preset_name}' darf keine HUMIDITY-Regel mehr enthalten, "
            f"enthielt aber {len(humidity_rules)}."
        )


# ──────────────────────────── AC-4 ──────────────────────────────────────────


class TestAC4FeuchteStillRenders:
    """AC-4 (Regression-Guard): die 6 Metriken erscheinen weiter als Spalten."""

    def test_feuchte_columns_with_numeric_values_in_html(self):
        """GIVEN ein Briefing mit den 6 aktivierten Metriken (raw-Format)
        WHEN format_email() eine Etappe rendert
        THEN erscheinen die Spaltenköpfe und numerische Werte im HTML.
        """
        from formatters.trip_report import TripReportFormatter

        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
            t2m_c=18.0,
            wind10m_kmh=10.0,
            gust_kmh=15.0,
            precip_1h_mm=0.0,
            humidity_pct=73,
            dewpoint_c=12.0,
            pop_pct=44,
            cloud_total_pct=66,
            pressure_msl_hpa=1013.0,
            wind_chill_c=16.0,
        )
        seg_data = SegmentWeatherData(
            segment=_segment(),
            timeseries=_timeseries([dp]),
            aggregated=SegmentWeatherSummary(
                humidity_avg_pct=73,
                dewpoint_avg_c=12.0,
                pop_max_pct=44,
                cloud_avg_pct=66,
                pressure_avg_hpa=1013.0,
                wind_chill_min_c=16.0,
            ),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

        report = TripReportFormatter().format_email(
            segments=[seg_data],
            trip_name="TDD 889 Feuchte",
            report_type="ad-hoc",
            display_config=_display_config_with_feuchte(),
        )
        html = report.email_html

        # Spaltenköpfe (col_label) aller 6 Metriken müssen vorhanden sein.
        for mid in FEUCHTE_METRIC_IDS:
            label = get_metric(mid).col_label
            assert label in html, f"Spaltenkopf '{label}' ({mid}) fehlt im Briefing-HTML"

        # Numerische Werte müssen erscheinen (Stichprobe pro Metrik).
        for value in ("73", "12", "44", "66", "1013", "16"):
            assert value in html, f"Numerischer Wert '{value}' fehlt im Briefing-HTML"


# ──────────────────────────── AC-5 ──────────────────────────────────────────


class TestAC5KeptMetricsStillAlert:
    """AC-5 (Regression-Guard): behaltene Alert-Metriken feuern weiter."""

    def test_wind_and_precip_still_produce_changes(self):
        """GIVEN aktivierte Wind- und Niederschlags-Anzeige-Metriken
        WHEN from_display_config().detect_changes() mit Schwellen-Überschreitung
        THEN Change-Einträge für Wind und Niederschlag werden erzeugt.
        """
        dc = UnifiedWeatherDisplayConfig(
            trip_id="tdd-889-kept",
            metrics=[
                MetricConfig(metric_id="wind", enabled=True),
                MetricConfig(metric_id="precipitation", enabled=True),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        old = SegmentWeatherSummary(wind_max_kmh=10.0, precip_sum_mm=0.0)
        new = SegmentWeatherSummary(wind_max_kmh=45.0, precip_sum_mm=25.0)

        changes = service.detect_changes(_weather_data(old), _weather_data(new))
        metrics = {c.metric for c in changes}

        assert "wind_max_kmh" in metrics, "Wind-Change muss weiter erzeugt werden"
        assert "precip_sum_mm" in metrics, (
            "Niederschlags-Change muss weiter erzeugt werden"
        )
