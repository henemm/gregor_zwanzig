---
entity_id: uv_air_quality
type: module
created: 2026-02-16
updated: 2026-02-16
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, uv-index, air-quality, cams]
---

# UV-Index via Air Quality API (WEATHER-06)

## Approval

- [ ] Approved

## Purpose

UV-Index ist bei ALLEN 5 regionalen Wettermodellen (AROME, ICON-D2, MetNo Nordic, ICON-EU, ECMWF IFS) nicht verfuegbar — alle liefern `null` trotz `uv_index` im hourly-Parameter. OpenMeteo bietet UV aber ueber eine separate Air Quality API basierend auf CAMS-Daten (ECMWF Copernicus Atmosphere Monitoring Service). Dieses Modul integriert die AQ-API als zusaetzliche Datenquelle parallel zum Wetter-API-Call.

**Kernregel:** UV wird aus Air Quality API geholt, BEVOR Model-Metric-Fallback (WEATHER-05b) laeuft. Die gesamte Downstream-Infrastruktur (ForecastDataPoint, Aggregation, Formatter) existiert bereits.

## Erweiterung von

- `docs/specs/modules/provider_openmeteo.md` v1.0 (Regional Model Selection)
- `docs/specs/modules/metric_availability_probe.md` v1.0 (Probe zeigt UV unavailable)

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider._fetch_uv_data()`, `OpenMeteoProvider._request()` (erweitert), `AIR_QUALITY_HOST` (neu)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ForecastDataPoint.uv_index | field | Zielfeld fuer UV-Werte (models.py:100) |
| _PARAM_TO_FIELD["uv_index"] | mapping | Bereits vorhanden (openmeteo.py:260) |
| _compute_uv_index() | function | Aggregation in weather_metrics.py:869-872 |
| MetricCatalog uv_index | entry | Katalog-Definition (metric_catalog.py:229-237) |
| _fmt_val("uv") | formatter | Report-Ausgabe (trip_report.py:476+) |
| WEATHER-05b fallback | feature | Laeuft NACH UV-Fetch, nicht betroffen |

## Implementation Details

### 1. Air Quality API Konstante (~2 LOC)

```python
# In openmeteo.py, nach BASE_HOST (Zeile 54)
BASE_HOST = "https://api.open-meteo.com"
AIR_QUALITY_HOST = "https://air-quality-api.open-meteo.com"
```

### 2. _request() erweitern (~2 LOC)

Erweiterung der bestehenden Methode (Zeile 358) um optionalen `base_host` Parameter:

```python
def _request(
    self, endpoint: str, params: Dict[str, Any], base_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Make HTTP request to Open-Meteo API with retry logic.

    Args:
        endpoint: API endpoint path (e.g., "/v1/meteofrance")
        params: Query parameters
        base_host: Override BASE_HOST (default: None = use BASE_HOST)

    Returns:
        JSON response as dict
    """
    host = base_host or BASE_HOST
    url = f"{host}{endpoint}"
    # ... rest bleibt unveraendert
```

**Change:** Zeile 377 von `url = f"{BASE_HOST}{endpoint}"` zu `url = f"{host}{endpoint}"`.

### 3. UV-Fetch Helper (~20 LOC)

Neue Methode in `OpenMeteoProvider` (nach `_parse_thunder_level`, vor `_parse_response`):

```python
def _fetch_uv_data(
    self, lat: float, lon: float, start: datetime, end: datetime
) -> Optional[Dict[str, Any]]:
    """
    Fetch UV-Index from Air Quality API (CAMS).

    UV ist bei allen Weather-Modellen null, aber verfuegbar via AQ-API.

    Args:
        lat: Latitude
        lon: Longitude
        start: Start date
        end: End date

    Returns:
        AQ API response dict with hourly.uv_index, or None on failure
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "uv_index",
        "timezone": "UTC",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    }

    try:
        logger.debug("Fetching UV from Air Quality API (CAMS)")
        return self._request("/v1/air-quality", params, base_host=AIR_QUALITY_HOST)
    except Exception as e:
        logger.warning("UV fetch from AQ API failed: %s", e)
        return None
```

### 4. UV in fetch_forecast() integrieren (~15 LOC)

Erweiterung in `fetch_forecast()` **nach** Zeile 582 (nach Primary Parse, VOR WEATHER-05b):

```python
# Parse primary result
timeseries = self._parse_response(response_data, model_id, grid_res_km)

# WEATHER-06: Fetch UV from Air Quality API
# UV ist bei allen Weather-Modellen null, AQ-API liefert CAMS-Daten
if start and end:
    uv_data = self._fetch_uv_data(location.latitude, location.longitude, start, end)
    if uv_data:
        hourly_uv = uv_data.get("hourly", {})
        times_uv = hourly_uv.get("time", [])
        values_uv = hourly_uv.get("uv_index", [])

        # Merge by timestamp
        uv_by_ts = {
            datetime.fromisoformat(t.replace("Z", "+00:00")): v
            for t, v in zip(times_uv, values_uv) if v is not None
        }
        for dp in timeseries.data:
            if dp.ts in uv_by_ts:
                dp.uv_index = uv_by_ts[dp.ts]

        logger.debug("UV merged: %d values populated", len(uv_by_ts))

# WEATHER-05b: Check for missing metrics and fetch fallback
cache = self._load_availability_cache()
# ... rest bleibt unveraendert
```

**Platzierung:** UV-Merge kommt VOR Fallback, weil Fallback nur fuer im Cache als unavailable gemeldete Metriken laeuft — und UV ist bei ALLEN Modellen unavailable, daher wuerde Fallback nichts bringen.

### 5. Provider-Spec Dokumentation (~10 LOC)

Update in `docs/specs/modules/provider_openmeteo.md`:

Nach Abschnitt "Parameter Mapping" (Zeile ~195), vor "Thunder Logic":

```markdown
### UV-Index Integration (WEATHER-06)

UV-Index ist bei ALLEN 5 Wettermodellen nicht verfuegbar (`uv_index` gibt null).
OpenMeteo bietet UV ueber separate Air Quality API:

- **Endpoint:** `https://air-quality-api.open-meteo.com/v1/air-quality`
- **Parameter:** `uv_index` (hourly)
- **Datenquelle:** CAMS (Copernicus Atmosphere Monitoring Service)
- **Aufloesung:** 0.25° (~25km), stuendlich, global
- **Merge-Strategie:** Nach Primary Fetch, vor Model-Fallback (WEATHER-05b)

UV-Werte werden via Timestamp-Matching in `ForecastDataPoint.uv_index` eingefuegt.
Graceful degradation: Bei AQ-API-Fehler bleibt UV `None` (keine Exception).
```

## Expected Behavior

### Szenario 1: Erfolgreicher UV-Fetch

- **Input:** Location Mallorca (39.7°N, 2.6°E), 16.02.2026, start/end gesetzt
- **Output:** Timeseries mit UV-Werten (z.B. 0.5 morgens, 3.6 mittags, 0 abends)
- **Side Effects:** 2 API-Calls (Weather + AQ), UV populated in timeseries.data[].uv_index
- **Log:** `DEBUG: Fetching UV from Air Quality API (CAMS)`, `DEBUG: UV merged: 48 values populated`

### Szenario 2: AQ-API schlaegt fehl

- **Input:** AQ-API antwortet mit 503 oder Timeout
- **Output:** Timeseries mit UV = None (wie bisher)
- **Side Effects:** 1 API-Call (Weather), AQ-Call fehlgeschlagen, keine Exception
- **Log:** `WARNING: UV fetch from AQ API failed: HTTPStatusError(503)`

### Szenario 3: Start/End nicht gesetzt

- **Input:** fetch_forecast() ohne start/end Parameter
- **Output:** Timeseries ohne UV-Fetch (weil AQ-API start_date/end_date benoetigt)
- **Side Effects:** 1 API-Call (Weather), UV bleibt None
- **Log:** Kein UV-Fetch-Log (Code-Block wird uebersprungen)

### Szenario 4: UV-Aggregation in Segment

- **Input:** Trip Report mit Segment 12:00-15:00, UV-Werte [2.1, 3.6, 3.2]
- **Output:** Aggregiertes UV max=3.6 (via _compute_uv_index)
- **Side Effects:** Formatter zeigt "UV 4" (gerundet, trip_report.py:476)

### Szenario 5: Model-Fallback laeuft weiterhin

- **Input:** AROME hat kein visibility/cape, WEATHER-05b aktiv
- **Output:** UV von AQ-API + visibility/cape von ICON-EU
- **Side Effects:** 3 API-Calls (Weather Primary, AQ, Weather Fallback)
- **Footer:** `Data: openmeteo (meteofrance_arome) | Fallback visibility, cape: icon_eu`

## Testplan

| # | Test | Typ | Assertion |
|---|------|-----|-----------|
| 1 | _fetch_uv_data gibt dict mit hourly.uv_index zurueck | Integration | `result["hourly"]["uv_index"]` ist Liste |
| 2 | _fetch_uv_data gibt None bei 503 Error | Integration | Kein Exception, Return None |
| 3 | _fetch_uv_data gibt None bei ungueltigem JSON | Integration | Kein Exception, Return None |
| 4 | _request verwendet custom base_host wenn gesetzt | Unit | URL startet mit AIR_QUALITY_HOST |
| 5 | _request verwendet BASE_HOST wenn base_host=None | Unit | URL startet mit BASE_HOST (wie bisher) |
| 6 | fetch_forecast populated uv_index via AQ-API | Integration | `timeseries.data[12].uv_index` ist nicht None |
| 7 | fetch_forecast merged UV by timestamp korrekt | Integration | Timestamps matchen, Werte korrekt |
| 8 | UV-Werte sind plausibel (0-15 Range) | Integration | Alle UV-Werte zwischen 0.0 und 15.0 |
| 9 | AQ-Fehler crasht fetch_forecast nicht | Integration | Timeseries wird zurueckgegeben, UV=None |
| 10 | WEATHER-05b Fallback laeuft noch korrekt | Integration | Fallback populated visibility etc. (UV-unabhaengig) |

**Test-Files:**
- `tests/unit/test_uv_air_quality.py` (~80 LOC, echte API-Calls)
- Update `tests/integration/test_openmeteo_full.py` (+20 LOC)

## Known Limitations

### API-spezifisch
- AQ-API benoetigt `start_date` und `end_date` — wenn nicht gesetzt, kein UV-Fetch
  (fetch_forecast ohne Zeitraum = Default Open-Meteo-Range, aber AQ-API gibt Fehler)
- AQ-API Aufloesung (0.25° = ~25km) ist groeßer als manche Weather-Modelle (AROME 1.3km)
  → UV-Werte repraesentieren groesseres Gebiet als Temperatur etc.

### Datenqualitaet
- UV ist cloud-aware (CAMS beruecksichtigt Bewoelkung), aber Modell-Ungenauigkeit moeglich
- UV-Werte fuer Hochgebirge (>3000m) ggf. zu niedrig (CAMS-Modell hat grobe Hoehenaufloesung)

### Graceful Degradation
- Bei AQ-API-Fehler gibt es KEIN Fallback auf andere UV-Quelle (keine Alternative bekannt)
- UV bleibt None — Formatter zeigt "–" statt Wert (wie bisher bei fehlendem UV)

### Kombination mit Fallback
- WEATHER-05b Fallback versucht UV NICHT zu fuellen (weil alle Modelle null haben)
- UV kommt ausschliesslich von AQ-API — wenn die ausfaellt, kein UV

### Metriken-Probe
- WEATHER-05a Probe zeigt UV als "unavailable" bei allen Modellen (korrekt)
- AQ-API wird NICHT probed (separate API, keine Model-Verfuegbarkeit)

## API-Dokumentation

**Air Quality API Endpoint:**
- Base URL: `https://air-quality-api.open-meteo.com`
- Path: `/v1/air-quality`
- Docs: https://open-meteo.com/en/docs/air-quality-api

**Parameter:**
```
?latitude=39.7
&longitude=2.6
&hourly=uv_index
&timezone=UTC
&start_date=2026-02-16
&end_date=2026-02-18
```

**Response:**
```json
{
  "latitude": 39.7,
  "longitude": 2.6,
  "hourly": {
    "time": ["2026-02-16T00:00", "2026-02-16T01:00", ...],
    "uv_index": [0.0, 0.0, 0.2, 1.5, 2.8, 3.6, 3.2, 2.1, ...]
  }
}
```

**UV-Index Skala (WHO):**
- 0-2: Low
- 3-5: Moderate
- 6-7: High
- 8-10: Very High
- 11+: Extreme

## Changelog

- 2026-02-16: Initial spec created (WEATHER-06, UV via Air Quality API)
