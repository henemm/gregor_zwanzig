"""
A3 (Epic #1301) — Schnee vom Landesdienst als Ergaenzung (gemeinsamer Weg
+ Touren-Bonus). Ergaenzt fuer Orte im SNOWGRID-Abdeckungsgebiet (Alpen)
die Werte snow_depth_cm/swe_kgm2 fill-only in die openmeteo-Zeitreihe,
am gemeinsamen Punkt OpenMeteoProvider.fetch_forecast.

Kein ``live``-Marker: alle drei getesteten Funktionen sind reine,
netzfreie Funktionen (Bounds-Check, Fill-Only-Stamp, Gating). Keine Mocks.

SPEC: docs/specs/modules/epic_1301_a3_compare_snowgrid.md
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider


def _make_timeseries(n: int = 3) -> NormalizedTimeseries:
    """Baut eine minimale, gueltige NormalizedTimeseries mit n Datenpunkten."""
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="meteofrance_arome",
        grid_res_km=1.3,
    )
    data = [
        ForecastDataPoint(ts=datetime(2026, 7, 17, 6 + i, tzinfo=timezone.utc))
        for i in range(n)
    ]
    return NormalizedTimeseries(meta=meta, data=data)


def test_stamp_snow_fills_none_fill_only():
    """AC-1: Alle Datenpunkte mit snow_depth_cm=None/swe_kgm2=None werden
    nach _stamp_snow(ts, 42.0, 120.0) auf die uebergebenen Werte gesetzt;
    die Rueckgabe listet die gefuellten Params (snow_depth, swe_tot)."""
    from providers.openmeteo import _stamp_snow

    ts = _make_timeseries(3)
    for dp in ts.data:
        assert dp.snow_depth_cm is None
        assert dp.swe_kgm2 is None

    filled = _stamp_snow(ts, 42.0, 120.0)

    for dp in ts.data:
        assert dp.snow_depth_cm == 42.0
        assert dp.swe_kgm2 == 120.0

    assert "snow_depth" in filled
    assert "swe_tot" in filled


def test_stamp_snow_does_not_overwrite():
    """AC-1: Ein Datenpunkt mit bereits gesetztem snow_depth_cm=10.0 wird
    NICHT ueberschrieben (fill-only); swe_kgm2 wird dort trotzdem gefuellt,
    weil es dort None ist. Die uebrigen Datenpunkte werden voll gefuellt."""
    from providers.openmeteo import _stamp_snow

    ts = _make_timeseries(3)
    ts.data[0].snow_depth_cm = 10.0
    # swe_kgm2 bleibt None auf allen Datenpunkten

    filled = _stamp_snow(ts, 42.0, 120.0)

    assert ts.data[0].snow_depth_cm == 10.0, (
        "fill-only: ein bereits gesetzter snow_depth_cm-Wert darf nicht "
        "ueberschrieben werden"
    )
    assert ts.data[0].swe_kgm2 == 120.0, (
        "swe_kgm2 war None auf dem ersten Datenpunkt und muss gefuellt werden"
    )
    for dp in ts.data[1:]:
        assert dp.snow_depth_cm == 42.0
        assert dp.swe_kgm2 == 120.0

    assert "snow_depth" in filled
    assert "swe_tot" in filled


def test_should_enrich_snow_gating():
    """AC-2: _should_enrich_snow(enrich_snow, lat, lon) liefert True nur
    bei enrich_snow=True UND Koordinaten in den SNOWGRID-Bounds (Alpen).
    Grenzen (45.0/8.0 und 50.0/18.0) sind inklusiv."""
    from providers.openmeteo import _should_enrich_snow

    # Innsbruck (Alpen) — Schalter an
    assert _should_enrich_snow(True, 47.2692, 11.4041) is True
    # Innsbruck — Schalter aus
    assert _should_enrich_snow(False, 47.2692, 11.4041) is False
    # Mallorca — ausserhalb der Bounds, Schalter an
    assert _should_enrich_snow(True, 39.7, 2.6) is False
    # Grenzen inklusiv
    assert _should_enrich_snow(True, 45.0, 8.0) is True
    assert _should_enrich_snow(True, 50.0, 18.0) is True


def test_snowgrid_covers_bounds():
    """SNOWGRID-Bounds-Helper: True fuer Alpen-Koordinaten, False ausserhalb."""
    from providers.geosphere import snowgrid_covers

    assert snowgrid_covers(47.3, 11.4) is True
    assert snowgrid_covers(39.7, 2.6) is False  # Mallorca
    assert snowgrid_covers(59.9, 10.8) is False  # Oslo
