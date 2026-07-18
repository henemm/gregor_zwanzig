"""TDD — Feature #770: INCA-Nowcast-Pfad-Reparatur (korrekte Attributnamen + Dry-Frames).

Spec: docs/specs/modules/radar_nowcast_inca_fix.md

Bug: `_fetch_geosphere_inca` liest `dp.precipitation_mm` / `dp.time` (existieren NICHT) →
bei JEDEM AT-Nowcast fliegt AttributeError → Fail-Soft gibt [] → INCA wird nie genutzt.

KEINE MOCKS. Echter Fetch gegen die GeoSphere-INCA-API mit fester Wien-Koordinate.
Wien 48.21 N / 16.37 E ist INCA-only (lon 16.37 > 15.1 → außerhalb der RADOLAN-Box).

In der RED-Phase schlagen beide Tests fehl, weil der AttributeError die Frames
verschluckt → source != "INCA" / frames leer / len(frames) == 0 != len(ts.data).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# sys.path absichern: sowohl `services.*` als auch `src.services.*` Importpfade.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.radar_service import RadarNowcastService  # noqa: E402

# Dialt real (Prod-API/GeoSphere/Staging-Stack) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
pytestmark = pytest.mark.live

# Wien — INCA-only (lon 16.37 > RADOLAN-max 15.1; in INCA-Box 46.3–49.1 / 9.5–17.2)
_WIEN_LAT, _WIEN_LON = 48.21, 16.37


def test_ac1_inca_real_fetch_returns_inca_source():
    """GIVEN reale österreichische INCA-only-Koordinate (Wien)
    WHEN get_nowcast aufgerufen wird
    THEN source == 'INCA' und ≥1 realer Frame mit numerischer Rate (mm/h ≥ 0).
    """
    from providers.geosphere import GeoSphereProvider

    # API-Erreichbarkeit prüfen — bei nachgewiesenem Ausfall skippen, NICHT wegmocken.
    if GeoSphereProvider().fetch_nowcast(_WIEN_LAT, _WIEN_LON) is None:
        pytest.skip("GeoSphere INCA API nicht erreichbar (fetch_nowcast → None)")

    result = RadarNowcastService().get_nowcast(_WIEN_LAT, _WIEN_LON)

    assert result.source == "INCA", (
        f"Wien sollte explizit INCA nutzen, nicht den Fallback (war: {result.source})"
    )
    assert len(result.frames) >= 1, "INCA-Fetch sollte ≥1 realen Frame liefern"
    for f in result.frames:
        assert isinstance(f.precip_mm_h, (int, float))
        assert f.precip_mm_h >= 0.0


def test_ac2_inca_parses_all_points_no_attributeerror():
    """GIVEN eine reale NormalizedTimeseries von fetch_nowcast (Wien)
    WHEN _fetch_geosphere_inca die Punkte zu RadarFrames parst
    THEN KEIN AttributeError; jeder ForecastDataPoint (auch trockene mit
    precip_1h_mm is None) ergibt genau einen Frame mit tz-awarem timestamp
    und numerischer Rate ≥ 0 → len(frames) == len(ts.data).
    """
    from providers.geosphere import GeoSphereProvider

    provider = GeoSphereProvider()
    ts = provider.fetch_nowcast(_WIEN_LAT, _WIEN_LON)
    if ts is None or not ts.data:
        pytest.skip("GeoSphere INCA API nicht erreichbar / keine Daten")

    svc = RadarNowcastService()
    frames = svc._fetch_geosphere_inca(_WIEN_LAT, _WIEN_LON)

    assert len(frames) == len(ts.data), (
        f"Jeder Datenpunkt muss genau einen Frame ergeben (kein Dry-Frame verschluckt): "
        f"frames={len(frames)} vs data={len(ts.data)}"
    )
    for f in frames:
        assert f.timestamp.tzinfo is not None, "timestamp muss timezone-aware sein"
        assert isinstance(f.precip_mm_h, (int, float))
        assert f.precip_mm_h >= 0.0
