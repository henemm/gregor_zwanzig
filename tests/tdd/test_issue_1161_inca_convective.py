"""TDD RED — Issue #1161: Gewitter/Hagel-Erkennung im GeoSphere-INCA-Nowcast-Pfad.

Spec: docs/specs/modules/issue_1161_inca_convective.md

Bisher setzt `_fetch_geosphere_inca` `RadarFrame.is_convective` nie (INCA liefert
kein Blitz-/Gewitter-Feld). Diese Tests belegen die geplante Sidecar-Reuse-Loesung:
`_fetch_geosphere_inca` ruft zusaetzlich `_fetch_openmeteo_15` (Open-Meteo, global
best_match, kein `models=`) auf, merged `is_convective` per Timestamp-Toleranz
(+-5 Min) in die INCA-Frames, und macht ein gescheiterter Sidecar-Call ueber
`NowcastResult.convective_checked` sichtbar statt ihn zu kaschieren (ADR-0018).

KEINE MOCKS. DI erfolgt ausschliesslich durch Ersetzen von Instanz-/Klassenmethoden
mit echten Python-Funktionen, die reale Objekte (RadarFrame, NormalizedTimeseries,
ForecastDataPoint) zurueckgeben — kein `Mock()`/`patch()`/`MagicMock` (Muster aus
test_feature_660_convective_stage.py::test_ac4, Issue #612).

In der RED-Phase schlagen alle vier Tests fehl, weil:
- `_fetch_geosphere_inca` `_fetch_openmeteo_15` noch nicht aufruft (kein Merge),
- `NowcastResult` noch kein `convective_checked`-Feld besitzt (AttributeError),
- `format_now_text` den Hinweis "Gewitter-Check nicht verfuegbar." noch nicht kennt.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# sys.path absichern: sowohl `services.*` als auch `src.services.*` Importpfade.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Wien — INCA-only (lon 16.37 > RADOLAN-max 15.1; in INCA-Box 46.3-49.1 / 9.5-17.2)
_WIEN_LAT, _WIEN_LON = 48.21, 16.37


def _real_inca_timeseries(ts: datetime, precip_1h_mm: float):
    """Baut eine reale NormalizedTimeseries mit genau einem GeoSphere-NOWCAST-Punkt."""
    from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

    meta = ForecastMeta(
        provider=Provider.GEOSPHERE, model="NOWCAST", run=ts, grid_res_km=1.0, interp="bilinear",
    )
    data = [ForecastDataPoint(ts=ts, precip_1h_mm=precip_1h_mm)]
    return NormalizedTimeseries(meta=meta, data=data)


# ===========================================================================
# AC-1: Sidecar-Match innerhalb Toleranz -> is_convective wird gemerged
# ===========================================================================

def test_ac1_inca_merges_convective_flag_from_sidecar(monkeypatch):
    """AC-1: konvektives Sidecar-Frame (WMO 95/96/99) innerhalb +-5 Min wird auf das
    zeitlich passende INCA-Frame gemerged; die Regen-Rate bleibt INCA-Quelle."""
    from providers.brightsky import RadarFrame
    from providers.geosphere import GeoSphereProvider
    from services.radar_service import RadarNowcastService

    # Issue #1329 C2 / AC-11: der globale Offline-Guard (GZ_TEST_FIXTURE_DIR,
    # von tests/conftest.py autouse gesetzt) wuerde _fetch_geosphere_inca
    # VOR der Provider-Konstruktion kurzschliessen. Dieser Test prueft aber
    # genau die reale INCA-Provider-Konstruktion (mit eigenem Methoden-Patch
    # als Netz-Schutz) -- der globale Schalter ist hier kontraproduktiv,
    # nicht sein Sicherheitsnetz.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    inca_ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    ts = _real_inca_timeseries(inca_ts, precip_1h_mm=1.0)  # -> 4.0 mm/h (INCA 15-min -> *4)

    def fake_fetch_nowcast(self, lat, lon):
        return ts

    def fake_openmeteo_15(self, lat, lon, models=None):
        # Sidecar-Frame 2 Min nach dem INCA-Frame, konvektiv (WMO 95).
        return [RadarFrame(timestamp=inca_ts + timedelta(minutes=2), precip_mm_h=2.0, is_convective=True)]

    orig_fetch_nowcast = GeoSphereProvider.fetch_nowcast
    orig_openmeteo_15 = RadarNowcastService._fetch_openmeteo_15
    GeoSphereProvider.fetch_nowcast = fake_fetch_nowcast
    RadarNowcastService._fetch_openmeteo_15 = fake_openmeteo_15
    try:
        svc = RadarNowcastService()
        frames = svc._fetch_geosphere_inca(_WIEN_LAT, _WIEN_LON)
        assert len(frames) == 1, "Genau ein INCA-Datenpunkt -> genau ein Frame"
        assert frames[0].is_convective is True, (
            "Konvektives Sidecar-Frame innerhalb +-5 Min muss auf das INCA-Frame gemerged werden"
        )
        assert frames[0].precip_mm_h == pytest.approx(4.0), (
            "Regen-Rate muss weiterhin aus der INCA-Quelle stammen, nicht aus dem Sidecar"
        )
    finally:
        GeoSphereProvider.fetch_nowcast = orig_fetch_nowcast
        RadarNowcastService._fetch_openmeteo_15 = orig_openmeteo_15


# ===========================================================================
# AC-2: Kein konvektives Sidecar-Frame -> is_convective bleibt False (Regression)
#        + Sidecar wurde tatsaechlich aufgerufen (kein blosses Default-Verhalten)
# ===========================================================================

def test_ac2_inca_non_convective_sidecar_unchanged(monkeypatch):
    """AC-2: nicht-konvektives Sidecar-Frame -> is_convective bleibt False, aber der
    Sidecar-Call muss tatsaechlich stattgefunden haben (echter Merge-Pfad, nicht nur
    der unveraenderte Default)."""
    from providers.brightsky import RadarFrame
    from providers.geosphere import GeoSphereProvider
    from services.radar_service import RadarNowcastService

    # Issue #1329 C2 / AC-11: siehe test_ac1_inca_merges_convective_flag_from_sidecar
    # -- der globale Offline-Guard wuerde die Provider-Konstruktion, die
    # dieser Test gerade prueft, kurzschliessen. Eigener Methoden-Patch ist
    # der Netz-Schutz dieses Tests.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    inca_ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    ts = _real_inca_timeseries(inca_ts, precip_1h_mm=0.5)

    calls: list[tuple[float, float]] = []

    def fake_fetch_nowcast(self, lat, lon):
        return ts

    def fake_openmeteo_15(self, lat, lon, models=None):
        calls.append((lat, lon))
        # Sidecar-Frame vorhanden, aber nicht konvektiv (WMO 61 = Regen, kein Gewitter).
        return [RadarFrame(timestamp=inca_ts + timedelta(minutes=1), precip_mm_h=1.0, is_convective=False)]

    orig_fetch_nowcast = GeoSphereProvider.fetch_nowcast
    orig_openmeteo_15 = RadarNowcastService._fetch_openmeteo_15
    GeoSphereProvider.fetch_nowcast = fake_fetch_nowcast
    RadarNowcastService._fetch_openmeteo_15 = fake_openmeteo_15
    try:
        svc = RadarNowcastService()
        frames = svc._fetch_geosphere_inca(_WIEN_LAT, _WIEN_LON)
        assert len(calls) == 1, (
            "_fetch_openmeteo_15 muss als Sidecar aufgerufen werden, damit der Konvektions-"
            "Check tatsaechlich stattfindet (nicht nur unveraenderter Default)"
        )
        assert frames[0].is_convective is False
        # Regressionsschutz: 4-Stufen-Text bleibt unveraendert.
        assert svc.intensity_to_text(frames[0].precip_mm_h, is_convective=False) in (
            "Kein Niederschlag", "Leichter Regen", "Mäßiger Regen", "Starker Regen",
        )
    finally:
        GeoSphereProvider.fetch_nowcast = orig_fetch_nowcast
        RadarNowcastService._fetch_openmeteo_15 = orig_openmeteo_15


# ===========================================================================
# AC-3: Sidecar-Fail-Soft-Fall -> convective_checked=False, sichtbar im Text
#        (Nicht-Kaschieren-Invariante, ADR-0018)
# ===========================================================================

def test_ac3_inca_sidecar_failure_sets_convective_checked_false(monkeypatch):
    """AC-3: schlaegt der Open-Meteo-Sidecar fehl (liefert [], realer Fail-Soft-
    Vertrag), bleibt die INCA-Regen-Nowcast nutzbar, aber `convective_checked` wird
    False und `format_now_text` weist das sichtbar aus statt es zu kaschieren."""
    from providers.geosphere import GeoSphereProvider
    from services.radar_service import RadarNowcastService

    # Issue #1329 C2 / AC-11: siehe test_ac1_inca_merges_convective_flag_from_sidecar
    # -- der globale Offline-Guard wuerde die Provider-Konstruktion, die
    # dieser Test gerade prueft, kurzschliessen. Eigener Methoden-Patch ist
    # der Netz-Schutz dieses Tests.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    inca_ts = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    ts = _real_inca_timeseries(inca_ts, precip_1h_mm=2.0)

    def fake_fetch_nowcast(self, lat, lon):
        return ts

    def failing_openmeteo_15(self, lat, lon, models=None):
        # Realer Fail-Soft-Vertrag von _fetch_openmeteo_15: leere Liste bei Fehler.
        return []

    orig_fetch_nowcast = GeoSphereProvider.fetch_nowcast
    orig_openmeteo_15 = RadarNowcastService._fetch_openmeteo_15
    GeoSphereProvider.fetch_nowcast = fake_fetch_nowcast
    RadarNowcastService._fetch_openmeteo_15 = failing_openmeteo_15
    try:
        svc = RadarNowcastService()
        result = svc.get_nowcast(_WIEN_LAT, _WIEN_LON)

        assert result.source == "INCA", "Regen-Nowcast muss trotz Sidecar-Fail INCA nutzen"
        assert len(result.frames) >= 1, "INCA-Regen-Frames bleiben trotz Sidecar-Fail erhalten"
        assert result.convective_checked is False, (
            "Sidecar-Fail darf NICHT stillschweigend als 'geprueft, kein Gewitter' behandelt "
            "werden (ADR-0018 Nicht-Kaschieren-Invariante)"
        )

        text = svc.format_now_text(result)
        assert "Gewitter-Check nicht verfügbar." in text
    finally:
        GeoSphereProvider.fetch_nowcast = orig_fetch_nowcast
        RadarNowcastService._fetch_openmeteo_15 = orig_openmeteo_15


# ===========================================================================
# AC-4: End-to-End gegen die echte Source-Chain (reale AT-Koordinate)
# ===========================================================================

@pytest.mark.live
def test_ac4_inca_live_get_nowcast_has_convective_checked_field():
    """AC-4: echter Aufruf ohne DI gegen die produktive Source-Chain (Wien) liefert
    ein NowcastResult mit gesetztem `convective_checked`-Feld (bool)."""
    from providers.geosphere import GeoSphereProvider
    from services.radar_service import RadarNowcastService

    if GeoSphereProvider().fetch_nowcast(_WIEN_LAT, _WIEN_LON) is None:
        pytest.skip("GeoSphere INCA API nicht erreichbar (fetch_nowcast -> None)")

    result = RadarNowcastService().get_nowcast(_WIEN_LAT, _WIEN_LON)

    assert result.source == "INCA", (
        f"Wien sollte explizit INCA nutzen, nicht den Fallback (war: {result.source})"
    )
    assert isinstance(result.convective_checked, bool), (
        "NowcastResult muss end-to-end ein bool convective_checked-Feld propagieren"
    )
