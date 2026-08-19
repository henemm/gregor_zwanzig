"""TDD RED -- Issue #1592 Scheibe C0 (Fundament), AC-2 + AC-3.

SPEC: docs/specs/modules/fix_1592_s1_cape_modellschwelle.md Abschnitt 2 (C0)

`SegmentWeatherSummary.cape_model_id: Optional[str] = None` (neues, additives
Feld) traegt die NORMALISIERTE Modell-Herkunft bis ins Tagesaggregat:

- Trip-Pfad (`compute_extended_metrics`): `cape_model_id =
  effective_cape_model_id(timeseries.meta)`.
- Ortsvergleichs-Pfad (`summarize_points`): baut sich `model="aggregate"`,
  normalisiert automatisch zu `None` -- kein Sonderfall-Code.
- Alte Schnappschuesse ohne das Feld laden unveraendert, `cape_model_id`
  bleibt `None` (additiv, `_deserialize_summary` filtert Unbekanntes bereits
  ueber `dataclasses.fields()`).

RED-Ursache (heute): `SegmentWeatherSummary` hat kein Feld `cape_model_id`
-> AttributeError bei jedem Zugriff auf `result.cape_model_id`.

Keine Mocks: reine DTO-/Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)


def _minimal_point(**overrides) -> ForecastDataPoint:
    """Ein Datenpunkt mit genau den Feldern, die dieser Test braucht --
    alles andere bleibt beim Dataclass-Default (None)."""
    base = dict(ts=datetime.now(timezone.utc), t2m_c=15.0, wind10m_kmh=10.0)
    base.update(overrides)
    return ForecastDataPoint(**base)


# ─────────────────────── AC-2 -- Trip-Pfad traegt Herkunft ────────────────

def test_ac2_trip_aggregat_traegt_normalisierten_modell_schluessel():
    """AC-2: eine reguläre Trip-Vorhersage fuer einen AROME-Ort ->
    `SegmentWeatherSummary.cape_model_id` traegt den NORMALISIERTEN
    Schluessel ('meteofrance_arome'), NICHT den unveraenderten Rohwert
    (der hier zufaellig bereits identisch waere -- die Gegenprobe unten
    prueft die eigentliche Normalisierung explizit)."""
    from services.weather_metrics import WeatherMetricsService

    meta = ForecastMeta(
        provider=Provider.METEOFRANCE, model="meteofrance_arome", grid_res_km=1.3,
    )
    ts = NormalizedTimeseries(meta=meta, data=[_minimal_point(cape_jkg=840.0)])

    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(ts, tz=None)
    result = svc.compute_extended_metrics(ts, basis)

    assert result.cape_model_id == "meteofrance_arome", (
        f"cape_model_id muss 'meteofrance_arome' tragen, erhalten "
        f"{result.cape_model_id!r}"
    )


def test_ac2_gegenprobe_rohwert_wird_normalisiert_nicht_unveraendert_durchgereicht():
    """AC-2 Gegenprobe: das PRIMAERE Modell traegt einen Roh-Bezeichner, der
    sich von seinem kanonischen Schluessel unterscheidet ('AROME-HIGHRES'
    statt 'meteofrance_arome') -- `cape_model_id` muss den NORMALISIERTEN
    Wert tragen. Reicht die Implementierung `meta.model` unveraendert durch,
    faengt dieser Test das (der Rohwert waere im Ergebnis sichtbar)."""
    from services.weather_metrics import WeatherMetricsService

    meta = ForecastMeta(
        provider=Provider.METEOFRANCE, model="AROME-HIGHRES", grid_res_km=1.3,
    )
    ts = NormalizedTimeseries(meta=meta, data=[_minimal_point(cape_jkg=840.0)])

    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(ts, tz=None)
    result = svc.compute_extended_metrics(ts, basis)

    assert result.cape_model_id == "meteofrance_arome", (
        f"Der Rohwert 'AROME-HIGHRES' muss auf den kanonischen Schluessel "
        f"'meteofrance_arome' normalisiert werden, erhalten "
        f"{result.cape_model_id!r} (unnormalisiert durchgereicht?)"
    )


def test_ac2_alter_schnappschuss_ohne_feld_laedt_mit_cape_model_id_none():
    """AC-2: ein alter, bereits gespeicherter Schnappschuss (Dict ohne den
    Schluessel 'cape_model_id', unveraendert aus dem Bestand) laedt NICHT
    fehl und liefert `cape_model_id is None` -- additiv, schnappschuss-sicher
    ueber `dataclasses.fields()`-Filterung (`_deserialize_summary`)."""
    from services.weather_snapshot import _deserialize_summary

    legacy_dict = {
        "temp_min_c": 5.0,
        "temp_max_c": 18.0,
        "cape_max_jkg": 900.0,
        # bewusst KEIN "cape_model_id" -- Bestandsdaten aus der Zeit vor
        # dieser Scheibe kennen das Feld nicht.
    }

    result = _deserialize_summary(legacy_dict)

    assert result.cape_model_id is None, (
        f"Ein alter Schnappschuss ohne 'cape_model_id' muss beim Laden "
        f"None liefern, erhalten {result.cape_model_id!r}"
    )


# ─────────────────── AC-3 -- Ortsvergleich hat keine Herkunft ─────────────

def test_ac3_ortsvergleich_aggregat_hat_keine_herkunft_auch_bei_hohem_cape():
    """AC-3: `summarize_points()` (Ortsvergleichs-Pfad) baut sich intern
    `ForecastMeta(model="aggregate", ...)` -- `cape_model_id` muss `None`
    sein, UNABHAENGIG davon, wie hoch der CAPE-Wert ist. Ein hoher CAPE-Wert
    darf keine falsche Herkunft vortaeuschen."""
    from services.weather_metrics import summarize_points

    # Cape-Wert deutlich ueber jeder denkbaren kalibrierten Schwelle
    # (Untergrenze der Eichregel ist bereits 300, jede reale Kalibrierung
    # bleibt weit unter 5000).
    points = [_minimal_point(cape_jkg=5000.0)]

    result = summarize_points(points)

    assert result is not None, "summarize_points() darf bei nicht-leerer Liste nicht None liefern"
    assert result.cape_model_id is None, (
        f"Der Ortsvergleichs-Pfad hat strukturell keine Modell-Herkunft -- "
        f"cape_model_id muss None sein (CAPE-Wert 5000 J/kg), erhalten "
        f"{result.cape_model_id!r}"
    )
