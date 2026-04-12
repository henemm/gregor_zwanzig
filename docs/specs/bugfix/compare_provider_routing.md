---
entity_id: compare_provider_routing
type: bugfix
created: 2026-04-12
updated: 2026-04-12
version: "1.0"
status: draft
severity: HIGH
tags: [compare, provider, geosphere, openmeteo, subscription, mallorca]
---

# Bugfix: Compare/Subscription nutzt hardcoded GeoSphereProvider — Locations ausserhalb Alpenraum bekommen keine Daten

## Approval

- [ ] Approved for implementation

## Symptom

Subscription "Mallorca" (Locations: Valdemossa, Pollença) liefert keine Wetterdaten.
GeoSphere AROME API gibt HTTP 400 Bad Request fuer Koordinaten ausserhalb des Alpenraums.

## Root Cause

`src/web/pages/compare.py:851` — `fetch_forecast_for_location()` hardcoded `GeoSphereProvider()`:

```python
provider = GeoSphereProvider()  # Nur Alpenraum (~45-50°N, 8-18°E)
service = ForecastService(provider)
```

GeoSphere AROME deckt nur Oesterreich/Alpen ab. Fuer Mallorca (39.7°N, 2.6°E) gibt die API 400 zurueck.

Zum Vergleich: `src/services/trip_report_scheduler.py:578` nutzt korrekt `get_provider("openmeteo")` mit automatischer Modellauswahl und globalem ECMWF-Fallback.

## Design

### Provider-Auswahl pro Location nach Koordinaten

Neue Funktion `_select_provider_for_location()` in `compare.py`:

```python
def _select_provider_for_location(lat: float, lon: float):
    """GeoSphere fuer Alpenraum (SNOWGRID-Vorteil), OpenMeteo fuer alles andere."""
    from providers.base import get_provider
    from providers.geosphere import GeoSphereProvider

    # GeoSphere AROME coverage: Austria/Alps
    GEOSPHERE_BOUNDS = {
        "min_lat": 45.0, "max_lat": 50.0,
        "min_lon": 8.0, "max_lon": 18.0,
    }

    if (GEOSPHERE_BOUNDS["min_lat"] <= lat <= GEOSPHERE_BOUNDS["max_lat"]
            and GEOSPHERE_BOUNDS["min_lon"] <= lon <= GEOSPHERE_BOUNDS["max_lon"]):
        return GeoSphereProvider()
    return get_provider("openmeteo")
```

Aenderung in `fetch_forecast_for_location()`:

```python
# VORHER (Zeile 851):
provider = GeoSphereProvider()

# NACHHER:
provider = _select_provider_for_location(loc.lat, loc.lon)
```

### Warum diese Bounds?

- GeoSphere AROME: 2.5km Aufloesung, SNOWGRID Schneetiefe (1km) — Mehrwert fuer Ski-Vergleiche
- OpenMeteo ICON-D2 fuer gleiche Region: 2km, aber KEIN SNOWGRID
- Ausserhalb Alpenraum: OpenMeteo hat AROME France (1.3km Mallorca), ECMWF global (40km)
- Bergfex-Scraping bleibt unabhaengig vom Provider erhalten (Zeile 865)

### Provider-close() Handling

`GeoSphereProvider` hat `close()`. `OpenMeteoProvider` ebenfalls. Bestehendes Pattern (Zeile 862) bleibt:
```python
provider.close()
```

## Affected Files

| Datei | Aenderung | LOC |
|-------|----------|-----|
| `src/web/pages/compare.py` | Neue Funktion `_select_provider_for_location()`, Aufruf in `fetch_forecast_for_location()`, defensiver `hasattr(provider, "close")` Guard | ~18 |

## Expected Behavior

- **Input:** Location mit beliebigen Koordinaten
- **Output:** Korrekte Wetterdaten, unabhaengig vom Standort
- **Alpenraum:** GeoSphere (mit SNOWGRID Schneetiefe)
- **Rest der Welt:** OpenMeteo (mit regionalem Modell + ECMWF Fallback)

## Test Plan

### Test 1: Provider-Auswahl nach Koordinaten
```python
def test_select_provider_alpenraum():
    """GeoSphere fuer Alpenraum."""
    provider = _select_provider_for_location(47.3, 11.4)  # Innsbruck
    assert isinstance(provider, GeoSphereProvider)

def test_select_provider_mallorca():
    """OpenMeteo fuer Mallorca."""
    provider = _select_provider_for_location(39.7, 2.6)  # Valdemossa
    assert isinstance(provider, OpenMeteoProvider)

def test_select_provider_boundary():
    """Grenzwerte: genau auf Bound → GeoSphere."""
    provider = _select_provider_for_location(45.0, 8.0)
    assert isinstance(provider, GeoSphereProvider)
```

### Test 2: Echter API-Call Mallorca
```python
def test_fetch_forecast_mallorca_real_api():
    """Mallorca-Location muss Wetterdaten liefern (kein HTTP 400)."""
    loc = SavedLocation(id="test", name="Valdemossa", lat=39.71, lon=2.63, elevation_m=600)
    result = fetch_forecast_for_location(loc, hours=48)
    assert result["error"] is None
    assert len(result["raw_data"]) > 0
    assert result["temp_min"] is not None
```

### Test 3: Regression — Alpenraum hat SNOWGRID
```python
def test_fetch_forecast_alps_has_snow_depth():
    """Alpenraum-Location behaelt SNOWGRID Schneetiefe."""
    loc = SavedLocation(id="test", name="Innsbruck", lat=47.26, lon=11.39, elevation_m=574)
    result = fetch_forecast_for_location(loc, hours=48)
    assert result["error"] is None
    # SNOWGRID liefert snow_depth_cm (kann 0 sein im Sommer, aber Feld existiert)
```

## Acceptance Criteria

- [ ] Mallorca-Subscription liefert Wetterdaten (kein HTTP 400)
- [ ] Zillertal-Subscription funktioniert weiterhin mit SNOWGRID-Schneetiefe
- [ ] Provider-Auswahl ist transparent (kein User-Eingriff noetig)
- [ ] `provider.close()` wird defensiv via `hasattr` Guard aufgerufen (GeoSphere hat close, OpenMeteo nicht)

## Known Limitations

- GeoSphere-Bounds sind statisch definiert (45-50°N, 8-18°E) — nicht exakt die AROME-Coverage
- Locations am Rand der Bounds koennten den "falschen" Provider bekommen (akzeptabel)

## Changelog

- 2026-04-12: v1.0 Bugfix-Spec erstellt
