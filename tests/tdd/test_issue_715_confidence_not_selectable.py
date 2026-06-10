"""
TDD RED — Issue #715 / #710: „Sicherheit" (confidence) ist KEINE wählbare Metrik mehr.

SPEC: docs/specs/modules/issue_715_wettermetriken_darstellung.md v1.0

PO-Regel: confidence ist eine Meta-Kennzahl (Vorhersage-Verlässlichkeit, Quelle
Open-Meteo Ensemble-API) und darf NICHT mehr als pro-Etappe wählbare Wetter-Metrik
im user-sichtbaren Katalog erscheinen. Sie bleibt ausschließlich als Vorhersage-
Verlässlichkeits-Hinweis (E-Mail-Hinweis + SMS-Symbol) erhalten.

AC-1: GET /api/metrics enthält in keiner Kategorie eine Metrik id=="confidence".
AC-3: build_confidence_hint() bleibt funktional (Vorhersage-Hinweis erhalten).
AC-4: Bestands-display_config mit aktiviertem confidence lädt fehlerfrei, übrige
      Metriken bleiben erhalten (kein Datenverlust).

PHASE: TDD RED — die AC-1-Tests MÜSSEN mit dem aktuellen Code SCHEITERN
(confidence ist heute im Katalog und wird von /api/metrics ausgeliefert).
Kein Mock — echter FastAPI-Endpoint-Call (TestClient) bzw. echte Katalog-/Loader-Logik.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def metrics_client() -> TestClient:
    """Echter FastAPI-TestClient für den config-Router (liefert /api/metrics)."""
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: confidence darf nicht im user-sichtbaren Metrik-Katalog erscheinen
# ---------------------------------------------------------------------------

class TestApiMetricsExcludesConfidence:
    """AC-1: /api/metrics und der Katalog bieten 'confidence' nicht als wählbare Metrik an."""

    def test_api_metrics_endpoint_excludes_confidence(self, metrics_client: TestClient):
        """AC-1 (Verhalten): Echter GET /api/metrics liefert in KEINER Kategorie id=='confidence'."""
        resp = metrics_client.get("/api/metrics")
        assert resp.status_code == 200, f"/api/metrics antwortete {resp.status_code}"
        catalog = resp.json()

        offending: list[str] = []
        for category, metrics in catalog.items():
            for m in metrics:
                if m.get("id") == "confidence":
                    offending.append(f"{category}: {m.get('label')!r}")

        assert not offending, (
            "Issue #710: 'confidence' (Sicherheit) wird noch als wählbare Metrik "
            f"von /api/metrics ausgeliefert: {offending}. Sie darf nicht mehr "
            "im user-sichtbaren Katalog erscheinen (PO-Regel #715)."
        )

    def test_catalog_helper_excludes_confidence_from_selection(self):
        """AC-1 (Quelle): Der user-sichtbare Katalog enthält 'confidence' nicht.

        Greift den Endpoint-Aufbau ab: dieselbe Liste, die /api/metrics speist,
        darf 'confidence' nicht als auswählbare Metrik führen.
        """
        from app.metric_catalog import get_all_metrics

        # Spiegelt die Endpoint-Logik: aus get_all_metrics() entsteht der
        # user-sichtbare Katalog. confidence darf darin nicht (mehr) auftauchen.
        selectable_ids = [m.id for m in get_all_metrics()]
        assert "confidence" not in selectable_ids, (
            "Issue #710: 'confidence' steht noch im wählbaren Metrik-Katalog "
            "(get_all_metrics). Sie muss aus der Auswahl entfernt werden."
        )


# ---------------------------------------------------------------------------
# AC-3: Vorhersage-Verlässlichkeits-Hinweis bleibt erhalten (Regression-Guard)
# ---------------------------------------------------------------------------

def _segment_with_confidence(confidence_pct, hours_offset, base_ts):
    """Hilfsfunktion: SegmentWeatherData mit einem confidence-Datenpunkt."""
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    dp = ForecastDataPoint(
        ts=base_ts + timedelta(hours=hours_offset),
        t2m_c=15.0,
        confidence_pct=confidence_pct,
        spread_t2m_k=4.0,
        spread_precip_mm=0.5,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="ecmwf_ifs", grid_res_km=40.0),
        data=[dp],
    )
    point = GPXPoint(lat=47.8, lon=13.0, elevation_m=800, distance_from_start_km=0.0)
    seg = TripSegment(
        segment_id=1, start_point=point, end_point=point,
        start_time=base_ts, end_time=base_ts + timedelta(hours=2),
        duration_hours=2.0, distance_km=4.0, ascent_m=200, descent_m=100,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=base_ts, provider="openmeteo",
    )


class TestConfidenceHintPreserved:
    """AC-3: Der Vorhersage-Hinweis (E-Mail) bleibt funktional — unabhängig von der Metrik-Auswahl."""

    def test_low_confidence_hint_still_produced(self):
        """AC-3: Bei confidence<60 in T+0..72h liefert build_confidence_hint weiterhin den Hinweis."""
        from output.renderers.email.helpers import build_confidence_hint

        monday = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        segments = [_segment_with_confidence(confidence_pct=45, hours_offset=48, base_ts=monday)]

        hint = build_confidence_hint(segments, now=monday, tz=tz)

        assert hint is not None, "AC-3: Vorhersage-Hinweis darf nicht verschwinden"
        assert "weniger verlässlich" in hint, (
            f"AC-3: Hinweis muss 'weniger verlässlich' enthalten, ist aber: {hint!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Bestandsdaten-Sicherheit — confidence-Config lädt ohne Datenverlust
# ---------------------------------------------------------------------------

class TestExistingConfidenceConfigRoundtrip:
    """AC-4: Ein Trip, der confidence aktiviert hatte, lädt fehlerfrei; übrige Metriken bleiben."""

    def test_display_config_with_confidence_preserves_other_metrics(self):
        """AC-4: display_config mit [temp, confidence, wind] → nach Roundtrip bleiben temp & wind."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig

        original = UnifiedWeatherDisplayConfig(
            trip_id="test-715",
            metrics=[
                MetricConfig(metric_id="temp", enabled=True),
                MetricConfig(metric_id="confidence", enabled=True),
                MetricConfig(metric_id="wind", enabled=True),
            ],
        )

        # Serialisierungs-Roundtrip über das Persistenz-Format (kein Mock).
        from dataclasses import asdict
        restored = UnifiedWeatherDisplayConfig(
            trip_id=original.trip_id,
            metrics=[MetricConfig(**asdict(m)) for m in original.metrics],
        )

        ids = {m.metric_id for m in restored.metrics if m.enabled}
        assert "temp" in ids and "wind" in ids, (
            f"AC-4: Reguläre Metriken dürfen beim Umgang mit confidence nicht verloren gehen: {ids}"
        )


# ---------------------------------------------------------------------------
# F001 (Fix-Loop 1): confidence muss beim Rendering ignoriert werden
# Bestands-display_config mit confidence enabled=True darf KEINE Sicherheit-
# Spalte im E-Mail-Tabellen-Rendering erzeugen.
# ---------------------------------------------------------------------------

class TestConfidenceExcludedFromRendering:
    """F001: confidence mit enabled=True in Bestands-display_config wird beim
    Rendering still ignoriert — keine Sicherheit-Spalte in dp_to_row / visible_cols."""

    def _legacy_dc(self):
        """Bestands-display_config mit confidence enabled=True (genau wie durch Wizard-Init-Bug)."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        return UnifiedWeatherDisplayConfig(
            trip_id="legacy-715",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True),
                MetricConfig(metric_id="confidence", enabled=True),
                MetricConfig(metric_id="wind", enabled=True),
            ],
        )

    def test_dp_to_row_excludes_confidence_col_key(self):
        """F001 (dp_to_row): confidence col_key 'confidence' erscheint NICHT in der Row."""
        from datetime import timezone
        from zoneinfo import ZoneInfo
        from app.models import ForecastDataPoint
        from output.renderers.email.helpers import dp_to_row

        base_ts = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        dp = ForecastDataPoint(ts=base_ts, t2m_c=15.0, wind10m_kmh=12.0, confidence_pct=45.0)
        dc = self._legacy_dc()
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Vienna"))

        assert "confidence" not in row, (
            "F001: confidence col_key darf nicht in der Row erscheinen — "
            f"Row-Keys: {[k for k in row if not k.startswith('_')]}"
        )
        assert "temp" in row, "temperature muss weiterhin in der Row sein"
        assert "wind" in row, "wind muss weiterhin in der Row sein"

    def test_visible_cols_excludes_sicherheit(self):
        """F001 (visible_cols): Sicherheit-Spalte erscheint nicht in visible_cols."""
        from datetime import timezone
        from zoneinfo import ZoneInfo
        from app.models import ForecastDataPoint
        from output.renderers.email.helpers import dp_to_row, visible_cols

        base_ts = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        dp = ForecastDataPoint(ts=base_ts, t2m_c=15.0, wind10m_kmh=12.0, confidence_pct=45.0)
        dc = self._legacy_dc()
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Vienna"))
        cols = visible_cols([row])

        col_keys = [k for k, _ in cols]
        assert "confidence" not in col_keys, (
            f"F001: Sicherheit-Spalte darf in visible_cols nicht erscheinen — "
            f"Spalten: {col_keys}"
        )
        assert "temp" in col_keys, "temperature muss in visible_cols sichtbar sein"
        assert "wind" in col_keys, "wind muss in visible_cols sichtbar sein"

    def test_confidence_hint_still_present_while_col_absent(self):
        """F001 + AC-3: confidence aus Tabelle raus, aber Vorhersage-Hinweis bleibt."""
        from datetime import timezone
        from zoneinfo import ZoneInfo
        from app.models import ForecastDataPoint
        from output.renderers.email.helpers import dp_to_row, build_confidence_hint
        from app.models import (
            ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
            SegmentWeatherData, SegmentWeatherSummary, TripSegment,
        )

        base_ts = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Vienna")
        dp = ForecastDataPoint(ts=base_ts + timedelta(hours=48), t2m_c=15.0,
                               wind10m_kmh=12.0, confidence_pct=45.0)
        dc = self._legacy_dc()
        row = dp_to_row(dp, dc, tz=tz)

        # Spalte weg
        assert "confidence" not in row, "confidence darf nicht in Row sein"

        # Vorhersage-Hinweis erhalten
        ts = NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="ecmwf_ifs", grid_res_km=40.0),
            data=[dp],
        )
        point = GPXPoint(lat=47.8, lon=13.0, elevation_m=800, distance_from_start_km=0.0)
        seg = TripSegment(
            segment_id=1, start_point=point, end_point=point,
            start_time=base_ts, end_time=base_ts + timedelta(hours=2),
            duration_hours=2.0, distance_km=4.0, ascent_m=200, descent_m=100,
        )
        seg_data = SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(),
            fetched_at=base_ts, provider="openmeteo",
        )
        hint = build_confidence_hint([seg_data], now=base_ts, tz=tz)
        assert hint is not None and "weniger verlässlich" in hint, (
            f"F001+AC-3: Vorhersage-Hinweis muss weiterhin erscheinen: {hint!r}"
        )
