---
entity_id: model_metric_fallback
type: module
created: 2026-02-16
updated: 2026-02-16
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, fallback, metrics]
---

# Model-Metric-Fallback (WEATHER-05b)

## Approval

- [ ] Approved

## Purpose

Wenn das primaere OpenMeteo-Modell (z.B. AROME fuer Mallorca) fuer aktivierte Metriken
`null` liefert, automatisch einen zweiten API-Call an ein breiteres Modell (z.B. ICON-EU)
machen und die fehlenden Werte einfuegen. Maximal 2 API-Calls pro Location.

**Kernregel:** Der User soll moeglichst vollstaendige Daten sehen. Welche Metriken aus
welchem Modell kommen, wird transparent im Footer dokumentiert.

## Erweiterung von

- `docs/specs/modules/provider_openmeteo.md` v1.0 (Regional Model Selection)
- `docs/specs/modules/metric_availability_probe.md` v1.0 (Probe-Cache)

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider.fetch_forecast()` (erweitert), `OpenMeteoProvider._find_fallback_model()`, `OpenMeteoProvider._merge_fallback()`
- **File:** `src/app/models.py`
- **Identifier:** `ForecastMeta` (erweitert um fallback_model, fallback_metrics)
- **File:** `src/formatters/trip_report.py`
- **Identifier:** Footer-Rendering in `_render_html()` und `_render_plain()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| AVAILABILITY_CACHE_PATH | const | Probe-Cache mit Metrik-Verfuegbarkeit pro Modell |
| _load_availability_cache() | method | Laedt gecachte Probe-Ergebnisse |
| REGIONAL_MODELS | const | Modell-Liste mit Bounds und Endpoints |
| select_model() | method | Waehlt Primaermodell nach Koordinaten |
| ForecastMeta | dto | Metadaten — wird um Fallback-Felder erweitert |

## Implementation Details

### 1. ForecastMeta erweitern (~10 LOC)

```python
@dataclass
class ForecastMeta:
    provider: Provider
    model: str
    run: datetime
    grid_res_km: float
    interp: str
    stations_used: List[StationInfo] = field(default_factory=list)
    # WEATHER-05b: Fallback tracking
    fallback_model: Optional[str] = None
    fallback_metrics: List[str] = field(default_factory=list)
```

### 2. Fallback-Modell finden (~20 LOC)

```python
def _find_fallback_model(
    self, primary_id: str, lat: float, lon: float, missing_params: list[str]
) -> Optional[Tuple[str, float, str]]:
    """
    Findet das beste Fallback-Modell fuer fehlende Metriken.

    Algorithmus:
    1. Probe-Cache laden
    2. Alle Modelle nach Prioritaet iterieren (niedrigere Prio = breitere Abdeckung)
    3. Ueberspringe Primaermodell
    4. Pruefe ob Modell die Koordinaten abdeckt (Bounds-Check)
    5. Pruefe ob Modell mind. 1 fehlende Metrik hat (via Probe-Cache)
    6. Return erstes Match oder None
    """
```

### 3. Fallback in fetch_forecast() integrieren (~50 LOC)

Erweiterung der bestehenden `fetch_forecast()`:

```python
def fetch_forecast(self, location, start=None, end=None):
    # 1. Primaermodell waehlen und fetchen (wie bisher)
    model_id, grid_res_km, endpoint = self.select_model(lat, lon)
    response_data = self._request(endpoint, params)
    timeseries = self._parse_response(response_data, model_id, grid_res_km)

    # 2. NEU: Pruefen ob Metriken fehlen
    cache = self._load_availability_cache()
    if cache is None:
        return timeseries  # Kein Cache → kein Fallback moeglich

    primary_info = cache["models"].get(model_id)
    if primary_info is None:
        return timeseries

    missing = primary_info.get("unavailable", [])
    if not missing:
        return timeseries  # Primaermodell hat alles

    # 3. NEU: Fallback-Modell suchen
    fallback = self._find_fallback_model(model_id, lat, lon, missing)
    if fallback is None:
        return timeseries  # Kein Fallback verfuegbar

    fb_model_id, fb_grid_res_km, fb_endpoint = fallback

    # 4. NEU: Zweiter API-Call NUR mit fehlenden Parametern
    fb_params = {**base_params, "hourly": ",".join(missing)}
    fb_data = self._request(fb_endpoint, fb_params)
    fb_timeseries = self._parse_response(fb_data, fb_model_id, fb_grid_res_km)

    # 5. NEU: Ergebnisse mergen
    filled = self._merge_fallback(timeseries, fb_timeseries, missing)

    # 6. NEU: Meta-Info aktualisieren
    timeseries.meta.fallback_model = fb_model_id
    timeseries.meta.fallback_metrics = filled

    return timeseries
```

### 4. Merge-Logik (~30 LOC)

```python
def _merge_fallback(
    self, primary: NormalizedTimeseries, fallback: NormalizedTimeseries,
    missing_params: list[str]
) -> list[str]:
    """
    Fuellt None-Werte im primary aus fallback, NUR fuer missing_params.

    Matching: Ueber Timestamp (ts). Beide Timeseries haben stuendliche Daten.
    Primary hat Vorrang — nur None-Felder werden befuellt.

    Returns: Liste der tatsaechlich gefuellten Parameter-Namen.
    """
    # Mapping: OpenMeteo param name → ForecastDataPoint field name
    PARAM_TO_FIELD = {
        "cape": "cape_jkg",
        "visibility": "visibility_m",
        "uv_index": "uv_index",
        "precipitation_probability": "pop_pct",
        "freezing_level_height": "freezing_level_m",
        # ... (alle relevanten Mappings)
    }

    fb_by_ts = {dp.ts: dp for dp in fallback.data}
    filled = set()

    for dp in primary.data:
        fb_dp = fb_by_ts.get(dp.ts)
        if fb_dp is None:
            continue
        for param in missing_params:
            field = PARAM_TO_FIELD.get(param)
            if field is None:
                continue
            if getattr(dp, field, None) is None:
                fb_val = getattr(fb_dp, field, None)
                if fb_val is not None:
                    setattr(dp, field, fb_val)
                    filled.add(param)

    return sorted(filled)
```

### 5. Footer-Transparenz (~15 LOC)

**HTML Footer** (trip_report.py ~652):

```python
# Bestehend:
footer = f"Data: {segments[0].provider} ({model_name})"

# NEU: Fallback-Info anfuegen
meta = segments[0].timeseries.meta
if meta and meta.fallback_model and meta.fallback_metrics:
    fb_metrics = ", ".join(meta.fallback_metrics)
    footer += f" | Fallback {fb_metrics}: {meta.fallback_model}"
```

**Plain-Text Footer** (trip_report.py ~763): Analog.

## Expected Behavior

### Szenario 1: AROME hat kein visibility/cape → Fallback auf ICON-EU

- **Input:** Location Mallorca (39.7°N, 2.6°E), AROME als Primaermodell
- **Output:** Timeseries mit AROME-Basisdaten + visibility/cape von ICON-EU
- **Footer:** `Data: openmeteo (meteofrance_arome) | Fallback visibility, cape: icon_eu`
- **Side Effects:** 2 API-Calls (AROME + ICON-EU)

### Szenario 2: Kein Probe-Cache vorhanden

- **Input:** Location beliebig, kein `model_availability.json`
- **Output:** Timeseries nur vom Primaermodell (wie bisher)
- **Footer:** `Data: openmeteo (meteofrance_arome)` (kein Fallback-Hinweis)
- **Side Effects:** 1 API-Call

### Szenario 3: Primaermodell hat alle Metriken

- **Input:** Location Deutschland, ICON-D2 hat 18/19 verfuegbar
- **Output:** Timeseries nur vom Primaermodell
- **Footer:** `Data: openmeteo (icon_d2)` (kein Fallback noetig)
- **Side Effects:** 1 API-Call

### Szenario 4: Fallback-API-Call schlaegt fehl

- **Input:** Location Mallorca, ICON-EU antwortet mit 503
- **Output:** Timeseries nur vom Primaermodell (graceful degradation)
- **Footer:** `Data: openmeteo (meteofrance_arome)` (Fallback still gescheitert)
- **Side Effects:** 2 API-Calls (einer fehlgeschlagen), Warning geloggt

## Testplan

| # | Test | Typ | Assertion |
|---|------|-----|-----------|
| 1 | ForecastMeta hat fallback_model und fallback_metrics Felder | Unit | Felder existieren mit Default None/[] |
| 2 | _find_fallback_model findet ICON-EU fuer AROME-Koordinaten | Unit | Gibt ("icon_eu", 7.0, "/v1/dwd-icon") zurueck |
| 3 | _find_fallback_model gibt None wenn kein Cache | Unit | Return None |
| 4 | _merge_fallback fuellt None-Felder aus Fallback | Unit | Vorher None, nachher Wert |
| 5 | _merge_fallback ueberschreibt KEINE vorhandenen Werte | Unit | Primary-Werte bleiben |
| 6 | fetch_forecast mit Cache macht Fallback-Call | Integration | meta.fallback_model ist gesetzt |
| 7 | fetch_forecast ohne Cache macht KEINEN Fallback | Integration | meta.fallback_model ist None |
| 8 | HTML-Footer zeigt Fallback-Info | Unit | "Fallback" im HTML |
| 9 | Plain-Text-Footer zeigt Fallback-Info | Unit | "Fallback" im Text |

## Known Limitations

- Maximal 1 Fallback-Call (kein Kaskadieren ueber mehrere Modelle)
- Fallback-Modell hat oft groebere Aufloesung (ICON-EU 7km vs AROME 1.3km)
- Zeitliche Aufloesung identisch (stuendlich) — kein Interpolationsbedarf
- Wenn Probe-Cache fehlt oder abgelaufen, kein Fallback (graceful degradation)
- ECMWF als Primaermodell hat keinen Fallback (ist selbst der letzte Fallback)

## Changelog

- 2026-02-16: Initial spec created (WEATHER-05b, Phase B)
