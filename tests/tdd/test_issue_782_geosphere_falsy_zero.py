"""
TDD Tests (Issue #782): GeoSphere-Parser — pressure_hpa und snow_depth_cm
behandeln 0 / 0.0 korrekt als echten Wert, nicht als None.

Gleiche Bug-Klasse wie #777 (NOWCAST), aber in zwei weiteren Parse-Methoden:
- _parse_nwp_response: pressure=0 Pa → soll pressure_hpa=0.0 liefern, nicht None
- _parse_snowgrid_response: snow_depth_m=0.0 → soll snow_depth_cm=0.0 liefern, nicht None
  ('kein Schnee' ist ein echter, häufiger Messwert und darf nicht als 'keine Daten' gelten)

MOCK-FREI: Echt-geformte Responses durch die echten Parser-Methoden.
"""

import pytest

from providers.geosphere import GeoSphereProvider

pytestmark = pytest.mark.tdd


def _nwp_response_with_pressure(pressure_pa):
    """NWP-Response mit einem einzigen Zeitstempel und dem angegebenen Luftdruck (Pa)."""
    return {
        "timestamps": ["2026-06-23T10:00:00Z"],
        "features": [{
            "properties": {
                "parameters": {
                    "t2m": {"data": [15.0]},
                    "u10m": {"data": [1.0]},
                    "v10m": {"data": [0.0]},
                    "ugust": {"data": [2.0]},
                    "vgust": {"data": [0.0]},
                    "rr_acc": {"data": [0.0]},
                    "snow_acc": {"data": [0.0]},
                    "snowlmt": {"data": [None]},
                    "tcc": {"data": [0.5]},
                    "rh2m": {"data": [70.0]},
                    "sp": {"data": [pressure_pa]},
                }
            }
        }],
    }


def _snowgrid_response(snow_depth_m):
    """SNOWGRID-Response mit dem angegebenen Schneehöhenwert (m)."""
    return {
        "features": [{
            "properties": {
                "parameters": {
                    "snow_depth": {"data": [snow_depth_m]},
                    "swe_tot": {"data": [0.0]},
                }
            }
        }]
    }


@pytest.fixture
def provider() -> GeoSphereProvider:
    return GeoSphereProvider()


# --- AC-1: pressure=0 Pa → pressure_hpa=0.0, nicht None ---

def test_ac1_pressure_zero_pa_yields_zero_hpa_not_none(provider: GeoSphereProvider) -> None:
    """AC-1: pressure=0 Pa (theoretisch selten, gleiche Bug-Klasse) → pressure_hpa=0.0, nicht None."""
    resp = _nwp_response_with_pressure(0)
    ts = provider._parse_nwp_response(resp)

    dp = ts.data[0]
    assert dp.pressure_msl_hpa is not None, (
        "pressure=0 Pa wurde als None gespeichert — 0 ist nicht von 'keine Daten' unterscheidbar."
    )
    assert dp.pressure_msl_hpa == 0.0


# --- AC-2: snow_depth_m=0.0 → snow_depth_cm=0.0, nicht None ---

def test_ac2_snow_depth_zero_yields_zero_cm_not_none(provider: GeoSphereProvider) -> None:
    """AC-2: snow_depth_m=0.0 (schneefrei) → snow_depth_cm=0.0, nicht None."""
    resp = _snowgrid_response(0.0)
    snow_depth_cm, _ = provider._parse_snowgrid_response(resp)

    assert snow_depth_cm is not None, (
        "snow_depth_m=0.0 (schneefrei) wurde als None gespeichert — "
        "schneefrei ist ein echter, häufiger Messwert."
    )
    assert snow_depth_cm == 0.0


# --- AC-3: pressure=None → pressure_hpa=None (Regression) ---

def test_ac3_pressure_none_stays_none(provider: GeoSphereProvider) -> None:
    """AC-3: Fehlendes pressure-Feld (None) → pressure_hpa=None (unverändert)."""
    resp = _nwp_response_with_pressure(None)
    ts = provider._parse_nwp_response(resp)

    dp = ts.data[0]
    assert dp.pressure_msl_hpa is None, "Fehlender Luftdruck (None) wurde fälschlich zu 0.0."


# --- AC-4: snow_depth_m=None → snow_depth_cm=None (Regression) ---

def test_ac4_snow_depth_none_stays_none(provider: GeoSphereProvider) -> None:
    """AC-4: Fehlendes snow_depth-Feld → snow_depth_cm=None (unverändert)."""
    resp = {
        "features": [{
            "properties": {
                "parameters": {
                    "snow_depth": {"data": []},
                    "swe_tot": {"data": []},
                }
            }
        }]
    }
    snow_depth_cm, _ = provider._parse_snowgrid_response(resp)

    assert snow_depth_cm is None, "Fehlende Schneehöhe wurde fälschlich zu 0.0."
