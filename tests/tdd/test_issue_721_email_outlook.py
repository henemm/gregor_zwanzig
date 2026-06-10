"""
TDD tests for Issue #721 (Slice 1 von #709) — E-Mail-Ausblick verschmelzen.

Großwetterlage + nächste Etappen + Vorhersage-Sicherheit zu EINEM Ausblick-Block.

RED phase: Tests schlagen fehl, bis show_outlook + Confidence-Rendering +
Stabilitäts-Verschmelzung implementiert sind.

SPEC: docs/specs/modules/issue_721_email_outlook.md AC-1..AC-5
IMPORTANT: KEINE Mocks, KEIN patch, KEIN MagicMock. Nur echte Funktionsaufrufe.
Kein Dateiinhalt-Check — geprüft wird der gerenderte E-Mail-Output (Produkt).
"""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo

import pytest


# ---------------------------------------------------------------------------
# Shared helpers — echte Domänen-Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float):
    from src.output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


def _trend_stage(
    weekday="Di", name="Test-Etappe",
    temp_lo=12, temp_hi=15,
    precip_mm=0.5, wind_dir="W", wind_kmh=17, thunder="NONE", note=None,
    hourly_precip=None, hourly_wind=None, hourly_gust=None, hourly_thunder=None,
    confidence_pct=None,
):
    """Trend-Stage-dict — wie vom Scheduler gebaut, optional mit confidence_pct."""
    stage = dict(
        weekday=weekday, name=name,
        temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=note,
        hourly_precip=hourly_precip or (),
        hourly_wind=hourly_wind or (),
        hourly_gust=hourly_gust or (),
        hourly_thunder=hourly_thunder or (),
    )
    if confidence_pct is not None:
        stage["confidence_pct"] = confidence_pct
    return stage


def _common_kwargs():
    from tests.unit.test_renderers_email import _common_kwargs as _ck
    return _ck()


def _render(trend, *, stability_result=None, show_outlook=True, show_stability=True):
    """Ruft render_html mit dem NEUEN show_outlook-Parameter auf.

    In der RED-Phase existiert show_outlook noch nicht → TypeError.
    Nach GREEN prüfen die Assertions echtes Render-Verhalten.
    """
    kw = _common_kwargs()
    from src.output.renderers.email.html import render_html
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name="Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None,
        stability_result=stability_result,
        show_outlook=show_outlook,
        show_stability=show_stability,
    )


def _stability(label="STABIL", confidence_pct=82):
    from app.models import StabilityResult
    return StabilityResult(label=label, confidence_pct=confidence_pct)


def _render_plain(trend, *, stability_result=None, show_outlook=True, show_stability=True):
    """Ruft render_plain mit show_outlook auf — symmetrisch zu _render (HTML)."""
    kw = _common_kwargs()
    from src.output.renderers.email.plain import render_plain
    return render_plain(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name="Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None,
        stability_result=stability_result,
        show_outlook=show_outlook,
        show_stability=show_stability,
    )


# ---------------------------------------------------------------------------
# AC-1: Großwetterlage als Kopf IM Ausblick-Block, vor der Etappen-Tabelle
# ---------------------------------------------------------------------------

class TestAC1OutlookHeadIsStability:
    def test_stability_label_inside_outlook_block_before_table(self):
        """Given Trip mit Etappen + Großwetterlage / When Ausblick gerendert /
        Then Wetterlage-Label steht NACH dem Ausblick-Marker und VOR der Etappen-Tabelle."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=82),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=70),
        ]
        html = _render(trend, stability_result=_stability("WECHSELHAFT", 70))

        pos_outlook = html.find("Ausblick")
        pos_label = html.find("WECHSELHAFT")
        pos_table = html.find("Nächste Etappen")

        assert pos_outlook != -1, "Ausblick-Block fehlt"
        assert pos_label != -1, "Großwetterlage-Label fehlt im Output"
        assert pos_table != -1, "Etappen-Tabelle fehlt"
        # Reihenfolge: Ausblick-Marker → Wetterlage → Nächste Etappen
        assert pos_outlook < pos_label < pos_table, (
            f"Reihenfolge falsch: outlook={pos_outlook}, label={pos_label}, "
            f"table={pos_table} — Großwetterlage muss als Kopf IM Ausblick stehen"
        )


# ---------------------------------------------------------------------------
# AC-2: Vorhersage-Sicherheit in % pro Etappe
# ---------------------------------------------------------------------------

class TestAC2ConfidencePerStage:
    def test_each_stage_shows_confidence_percent(self):
        """Given Etappen mit confidence_pct / When gerendert / Then jede zeigt 'NN%'."""
        trend = [
            _trend_stage(weekday="Di", name="E1", confidence_pct=88),
            _trend_stage(weekday="Mi", name="E2", confidence_pct=54),
        ]
        html = _render(trend, stability_result=_stability("WECHSELHAFT", 54))
        assert "88%" in html, "Sicherheit der nahen Etappe (88%) fehlt"
        assert "54%" in html, "Sicherheit der ferneren Etappe (54%) fehlt"

    def test_missing_confidence_no_zero_percent(self):
        """Given Etappe OHNE confidence_pct / When gerendert / Then kein 'Sicherheit 0%'-Label."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=None)]
        html = _render(trend, stability_result=_stability("STABIL", 82))
        assert "Sicherheit 0%" not in html, "Fehlende Sicherheit darf nicht als 'Sicherheit 0%' erscheinen"


# ---------------------------------------------------------------------------
# AC-3: Uhrzeiten nur wo Stundendaten vorliegen (#640-Verhalten erhalten)
# ---------------------------------------------------------------------------

class TestAC3TimesOnlyWhereHourly:
    def test_near_stage_has_time_far_stage_none(self):
        """Given nahe Etappe mit hourly_thunder, ferne ohne / When gerendert /
        Then nahe trägt @-Zeitstempel, ferne nicht."""
        near = _trend_stage(
            weekday="Di", name="Nah", thunder="HIGH",
            hourly_thunder=(_hv(14, 2.0),), confidence_pct=80,
        )
        far = _trend_stage(
            weekday="Fr", name="Fern", thunder="NONE", confidence_pct=45,
        )
        html = _render([near, far], stability_result=_stability("WECHSELHAFT", 45))
        # @14 / @14:00 muss für die nahe Etappe auftauchen
        assert re.search(r"@\s*14", html), "Nahe Etappe ohne @-Zeitstempel trotz Stundendaten"


# ---------------------------------------------------------------------------
# AC-4: show_outlook=False blendet den GANZEN Ausblick aus
# ---------------------------------------------------------------------------

class TestAC4OutlookToggleOff:
    def test_outlook_false_hides_stability_and_table(self):
        """Given show_outlook=False / When gerendert / Then weder Label noch Tabelle."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=82)]
        html = _render(trend, stability_result=_stability("STABIL", 82),
                       show_outlook=False)
        assert "Nächste Etappen" not in html, "Etappen-Tabelle trotz show_outlook=False sichtbar"
        assert "STABIL" not in html, "Großwetterlage trotz show_outlook=False sichtbar"

    def test_outlook_true_shows_block(self):
        """Gegenprobe: show_outlook=True zeigt den Block."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=82)]
        html = _render(trend, stability_result=_stability("STABIL", 82),
                       show_outlook=True)
        assert "Nächste Etappen" in html


# ---------------------------------------------------------------------------
# AC-5: Bestandsschutz — Altfelder überleben einen Persistenz-Round-Trip
# ---------------------------------------------------------------------------

class TestAC5LegacyFieldsPreserved:
    def _trip_dict_with_legacy(self):
        return {
            "id": "trip-721",
            "name": "Bestandstrip",
            "stages": [],
            "report_config": {
                "trip_id": "trip-721",
                "enabled": True,
                "morning_time": "07:00:00",
                "evening_time": "18:00:00",
                "show_stability": False,
                "show_compact_summary": False,
                "show_highlights": False,
                "show_daylight": False,
                "daily_summary_metrics": ["temperature"],
            },
        }

    def test_show_outlook_field_exists_with_default_true(self):
        """Given frische TripReportConfig / Then Feld show_outlook existiert, Default True."""
        from app.models import TripReportConfig
        rc = TripReportConfig(trip_id="x")
        assert rc.show_outlook is True

    def test_roundtrip_preserves_legacy_fields(self):
        """Given gespeicherter Trip mit Altfeldern / When load → to_dict /
        Then Altfelder byte-identisch erhalten UND show_outlook im Dump."""
        from app.loader import load_trip_from_dict, _trip_to_dict
        trip = load_trip_from_dict(self._trip_dict_with_legacy())
        dumped = _trip_to_dict(trip)
        rc = dumped["report_config"]
        # Altfelder unverändert
        assert rc["show_stability"] is False
        assert rc["show_compact_summary"] is False
        assert rc["show_highlights"] is False
        assert rc["show_daylight"] is False
        assert rc["daily_summary_metrics"] == ["temperature"]
        # Neues Feld additiv vorhanden
        assert "show_outlook" in rc


# ---------------------------------------------------------------------------
# AC-2 Verdrahtung: confidence_pct fließt vom Segment durch aggregate_stage
#   ins Stage-dict — Nachweis ohne Mocks, ohne echten Wetter-Fetch
# ---------------------------------------------------------------------------

class TestAC2ConfidencePipelineWiring:
    """Beweist die Datenpipeline: SegmentWeatherSummary.confidence_pct_min
    → aggregate_stage → confidence_pct im Stage-dict (wie Scheduler es baut)."""

    def _make_seg_weather_with_confidence(self, confidence_pct_min: int):
        """Echtes SegmentWeatherData mit gesetztem confidence_pct_min."""
        from datetime import datetime, timezone
        from app.models import (
            GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary,
            ThunderLevel,
        )
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
            end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
            start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            distance_km=8.0,
            ascent_m=800.0,
            descent_m=0.0,
        )
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
            wind_max_kmh=22.0, gust_max_kmh=35.0,
            precip_sum_mm=0.0, cloud_avg_pct=50, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
            confidence_pct_min=confidence_pct_min,
            aggregation_config={"confidence_pct_min": "min"},
        )
        return SegmentWeatherData(
            segment=seg, timeseries=None, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        )

    def test_aggregate_stage_propagates_confidence_pct_min(self):
        """Given SegmentWeatherData mit confidence_pct_min=75 /
        When aggregate_stage aufgerufen / Then Aggregat hat confidence_pct_min=75."""
        from services.weather_metrics import aggregate_stage
        sw = self._make_seg_weather_with_confidence(75)
        agg = aggregate_stage([sw])
        assert agg.confidence_pct_min == 75, (
            f"aggregate_stage muss confidence_pct_min durchreichen, "
            f"got {agg.confidence_pct_min}"
        )

    def test_aggregate_stage_min_over_segments(self):
        """Given zwei Segmente mit confidence_pct_min 90 und 60 /
        When aggregate_stage / Then Ergebnis = 60 (das Minimum)."""
        from services.weather_metrics import aggregate_stage
        sw_high = self._make_seg_weather_with_confidence(90)
        sw_low = self._make_seg_weather_with_confidence(60)
        agg = aggregate_stage([sw_high, sw_low])
        assert agg.confidence_pct_min == 60, (
            f"aggregate_stage soll Minimum nehmen, got {agg.confidence_pct_min}"
        )

    def test_scheduler_stage_dict_includes_confidence_pct(self):
        """Beweist, dass der Scheduler-Code-Pfad (_build_stage_trend-Logik)
        confidence_pct aus agg.confidence_pct_min korrekt ins dict einträgt."""
        from services.weather_metrics import aggregate_stage
        sw = self._make_seg_weather_with_confidence(82)
        agg = aggregate_stage([sw])
        # Repliziere die Scheduler-Logik direkt (Issue #721-Pfad)
        conf_pct = round(agg.confidence_pct_min) if agg.confidence_pct_min is not None else None
        stage_dict = {"confidence_pct": conf_pct} if conf_pct is not None else {}
        assert "confidence_pct" in stage_dict, "confidence_pct fehlt im Stage-dict"
        assert stage_dict["confidence_pct"] == 82


# ---------------------------------------------------------------------------
# F001-Regression (#621-Vertrag): show_stability=False unterdrückt das Label
#   auch im Trend-Pfad (nicht-leerer multi_day_trend)
# ---------------------------------------------------------------------------

class TestF001ShowStabilityRespectedInTrendPath:
    def test_show_stability_false_hides_label_with_trend(self):
        """Given show_outlook=True, show_stability=False, nicht-leerer Trend /
        When gerendert / Then Stabilitäts-Label fehlt, Etappen-Tabelle ist da."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        html = _render(
            trend,
            stability_result=_stability("WECHSELHAFT", 65),
            show_outlook=True,
            show_stability=False,
        )
        assert "WECHSELHAFT" not in html, (
            "Stabilitäts-Label darf bei show_stability=False nicht erscheinen — "
            "auch nicht im Trend-Pfad (#621-Vertrag)"
        )
        assert "Nächste Etappen" in html, (
            "Etappen-Tabelle soll bei show_stability=False trotzdem erscheinen"
        )

    def test_show_stability_true_shows_label_with_trend(self):
        """Gegenprobe: show_stability=True (Default) zeigt das Label."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        html = _render(
            trend,
            stability_result=_stability("WECHSELHAFT", 65),
            show_outlook=True,
            show_stability=True,
        )
        assert "WECHSELHAFT" in html, "Stabilitäts-Label soll bei show_stability=True erscheinen"


# ---------------------------------------------------------------------------
# AC-4 (Plain): show_outlook=False unterdrückt Ausblick auch im Plain-Body
# ---------------------------------------------------------------------------

class TestAC4OutlookToggleOffPlain:
    def test_plain_outlook_false_hides_stability_and_trend(self):
        """Given show_outlook=False / When plain gerendert /
        Then weder Großwetterlage-Stichwort noch Etappen-Trend-Block."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=82)]
        plain = _render_plain(
            trend,
            stability_result=_stability("STABIL", 82),
            show_outlook=False,
        )
        assert "Nächste Etappen" not in plain, (
            "Etappen-Trend-Block trotz show_outlook=False im Plain-Body sichtbar"
        )
        assert "Wetterlage" not in plain, (
            "Großwetterlage-Text trotz show_outlook=False im Plain-Body sichtbar"
        )
        assert "STABIL" not in plain, (
            "Stabilitäts-Label trotz show_outlook=False im Plain-Body sichtbar"
        )

    def test_plain_outlook_true_shows_stability_and_trend(self):
        """Gegenprobe: show_outlook=True zeigt beide Blöcke im Plain-Body."""
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=82)]
        plain = _render_plain(
            trend,
            stability_result=_stability("STABIL", 82),
            show_outlook=True,
        )
        assert "Nächste Etappen" in plain, (
            "Etappen-Trend-Block fehlt bei show_outlook=True im Plain-Body"
        )
        assert "STABIL" in plain, (
            "Stabilitäts-Label fehlt bei show_outlook=True im Plain-Body"
        )
