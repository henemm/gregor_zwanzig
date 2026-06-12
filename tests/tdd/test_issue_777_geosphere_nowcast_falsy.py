"""
TDD Tests (Issue #777): GeoSphere-NOWCAST — 0.0 ist ein echter Wert, kein None.

Bug: `_parse_nowcast_response` nutzt `round(x, 1) if x else None`. Der Truthiness-Check
`if x` ist bei `x == 0.0` falsch → der echte Messwert 0.0 (trocken / windstill) wird als
`None` gespeichert und ist damit nicht von „kein Datenpunkt" unterscheidbar.

MOCK-FREI: Der Parser ist eine reine Transformation eines API-Response-Dicts. Wir schicken
einen real-geformten NOWCAST-Response (exakte GeoSphere-Struktur) durch die ECHTE
`_parse_nowcast_response`-Methode — kein Mock, kein Patch, nur echte Parser-Logik auf
echt-geformten Daten. Vor dem Fix liefert der Parser None für 0.0 (rot), nach dem Fix 0.0.
"""

import pytest

from providers.geosphere import GeoSphereProvider

pytestmark = pytest.mark.tdd


def _nowcast_response(t2m, ff, fx, rr, pt=None, rh2m=None):
    """Baut einen GeoSphere-NOWCAST-Response in exakt der Struktur, die der echte Parser liest.

    timestamps + features[0].properties.parameters.{param}.data — siehe
    GeoSphereProvider._parse_nowcast_response.
    """
    n = max(len(t2m), len(ff), len(fx), len(rr))
    timestamps = [f"2026-06-12T{10 + (i // 4):02d}:{(i % 4) * 15:02d}:00Z" for i in range(n)]
    params = {
        "t2m": {"data": t2m},
        "ff": {"data": ff},
        "fx": {"data": fx},
        "rr": {"data": rr},
    }
    if pt is not None:
        params["pt"] = {"data": pt}
    if rh2m is not None:
        params["rh2m"] = {"data": rh2m}
    return {
        "timestamps": timestamps,
        "features": [{"properties": {"parameters": params}}],
    }


@pytest.fixture
def provider() -> GeoSphereProvider:
    return GeoSphereProvider()


def test_ac1_dry_precip_zero_stays_zero_not_none(provider: GeoSphereProvider) -> None:
    """AC-1: rr=0.0 (trocken) → precip_1h_mm == 0.0 (float), NICHT None."""
    resp = _nowcast_response(t2m=[15.0], ff=[2.0], fx=[3.0], rr=[0.0])
    ts = provider._parse_nowcast_response(resp)

    dp = ts.data[0]
    assert dp.precip_1h_mm is not None, (
        "Trockenes Intervall (0.0 mm) wurde als None gespeichert — "
        "0.0 ist nicht von 'kein Datenpunkt' unterscheidbar (Falsy-Bug)."
    )
    assert dp.precip_1h_mm == 0.0


def test_ac2_calm_wind_and_gust_zero_stays_zero_not_none(provider: GeoSphereProvider) -> None:
    """AC-2: ff=0.0 (windstill) und fx=0.0 (keine Böe) → 0.0, NICHT None."""
    resp = _nowcast_response(t2m=[12.0], ff=[0.0], fx=[0.0], rr=[1.0])
    ts = provider._parse_nowcast_response(resp)

    dp = ts.data[0]
    assert dp.wind10m_kmh is not None, "Windstille (0.0) wurde als None gespeichert (Falsy-Bug)."
    assert dp.wind10m_kmh == 0.0
    assert dp.gust_kmh is not None, "Keine Böe (0.0) wurde als None gespeichert (Falsy-Bug)."
    assert dp.gust_kmh == 0.0


def test_ac3_missing_datapoint_stays_none(provider: GeoSphereProvider) -> None:
    """AC-3: Parameter-Array kürzer als Zeitstempel → echte Datenlücke bleibt None (kein 0.0)."""
    # 3 Zeitstempel (t2m hat 3), aber rr/ff/fx nur 2 Werte → 3. Punkt = echter fehlender Datenpunkt
    resp = _nowcast_response(
        t2m=[15.0, 15.0, 15.0],
        ff=[1.0, 1.0],
        fx=[2.0, 2.0],
        rr=[0.0, 0.0],
    )
    ts = provider._parse_nowcast_response(resp)

    assert len(ts.data) == 3
    dp_missing = ts.data[2]
    assert dp_missing.precip_1h_mm is None, "Echte Datenlücke wurde fälschlich zu 0.0 verfälscht."
    assert dp_missing.wind10m_kmh is None
    assert dp_missing.gust_kmh is None
    # Gegenprobe: die 0.0-Werte aus den ersten beiden Punkten sind echt 0.0 (nicht None)
    assert ts.data[0].precip_1h_mm == 0.0


def test_ac4_nonzero_values_unchanged_no_regression(provider: GeoSphereProvider) -> None:
    """AC-4: Nicht-Null-Werte bleiben unverändert korrekt — keine Regression durch den Fix."""
    resp = _nowcast_response(t2m=[18.3], ff=[3.5], fx=[5.0], rr=[1.2])
    ts = provider._parse_nowcast_response(resp)

    dp = ts.data[0]
    assert dp.precip_1h_mm == 1.2
    assert dp.wind10m_kmh == round(3.5 * 3.6, 1)  # 12.6
    assert dp.gust_kmh == round(5.0 * 3.6, 1)  # 18.0
    assert dp.t2m_c == 18.3
