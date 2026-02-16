---
entity_id: openmeteo_endpoint_routing
type: bugfix
created: 2026-02-16
updated: 2026-02-16
version: "1.0"
status: implemented
severity: HIGH
tags: [openmeteo, endpoint, model-selection, weather-data]
---

# Bugfix: OpenMeteo Provider nutzt generischen /v1/forecast Endpunkt → falsches Wettermodell

## Approval

- [x] Approved for implementation

## Symptom

OpenMeteo Provider liefert völlig falsche Wetterprognosen für Mallorca, obwohl Modellauswahl korrekt funktioniert.

**Symptom in der Praxis:**
```
System soll für Mallorca das AROME-Modell (1.3km, Météo-France) nutzen
  → select_model() wählt korrekt "meteofrance_arome" aus
  → fetch_forecast() übergibt model="meteofrance_arome" in params
  → API-Call an /v1/forecast?model=meteofrance_arome
  → API ignoriert model-Parameter komplett
  → API liefert DWD-ICON Daten (falsches Modell, falsche Region)
  → Resultat: 100% Wolken statt Sonnenschein, Sturmböen statt leichter Wind
```

**Empirischer Beweis (Mallorca, 2026-02-16, 08:00 UTC):**
```
/v1/forecast?model=meteofrance_arome → T=15.1°C, Gust=67.7km/h, Cloud=100%
/v1/forecast?model=icon_d2           → T=15.1°C, Gust=67.7km/h, Cloud=100%  (identisch!)
/v1/forecast?model=metno_nordic      → T=15.1°C, Gust=67.7km/h, Cloud=100%  (identisch!)
/v1/forecast?model=icon_eu           → T=15.1°C, Gust=67.7km/h, Cloud=100%  (identisch!)
/v1/forecast?model=ecmwf_ifs04       → T=15.1°C, Gust=67.7km/h, Cloud=100%  (identisch!)

/v1/meteofrance (dedizierter Endpunkt) → T=12.1°C, Gust=15.5km/h, Cloud=28%
```

**Verifikation mit Windy/AROME HD:**
- Mallorca 08:00 UTC: Sonnenschein (28% Wolken), leichter Wind (15 km/h)
- → `/v1/meteofrance` Daten stimmen überein
- → `/v1/forecast` Daten sind komplett falsch (liefert DWD-ICON für Deutschland)

**Business Impact:**
- Wanderer bekommt falsche Wetterprognose (Sturm statt Sonne)
- → Unnötige Tour-Absage oder gefährliche Fehleinschätzung
- → Projektziel "Best regional model" wird nicht erreicht

## Root Cause

Der OpenMeteo Provider verwendet einen **generischen API-Endpunkt** der den `model`-Parameter ignoriert, statt dedizierte modellspezifische Endpunkte zu nutzen.

### Problem 1: Hardcoded generischer Endpunkt

```python
# src/providers/openmeteo.py:50
BASE_URL = "https://api.open-meteo.com/v1/forecast"  # Generischer Endpunkt!
```

**Konsequenz:** Alle Requests gehen an `/v1/forecast`, unabhängig vom gewählten Modell.

### Problem 2: _request() nutzt hardcoded BASE_URL

```python
# src/providers/openmeteo.py:197
def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
    response = self._client.get(BASE_URL, params=params)  # Immer /v1/forecast!
```

**Konsequenz:** `model`-Parameter wird zwar übergeben, aber von API ignoriert.

### Problem 3: fetch_forecast() übergibt nutzlosen model-Parameter

```python
# src/providers/openmeteo.py:354
params = {
    "model": model_id,  # Wird ignoriert! API nutzt Default-Modell (DWD-ICON)
    ...
}
```

**Konsequenz:** Parameter hat keine Wirkung, verschleiert Problem (sieht korrekt aus).

### Problem 4: REGIONAL_MODELS hat kein endpoint-Feld

```python
# src/providers/openmeteo.py:62-98
REGIONAL_MODELS = [
    {
        "id": "meteofrance_arome",
        "name": "AROME France & Balearen (1.3 km)",
        # endpoint fehlt! → Keine Zuordnung Modell → API-Endpunkt
        "bounds": {...},
        "grid_res_km": 1.3,
        "priority": 1,
    },
    ...
]
```

**Konsequenz:** Kein Weg für select_model() den korrekten Endpunkt zurückzugeben.

### Problem 5: OpenMeteo API-Architektur ignoriert

**OpenMeteo API verwendet dedizierte Endpunkte pro Modell-Familie:**
- `/v1/forecast` — generischer Endpunkt, nutzt Standard-Modell (ICON), **ignoriert model-Parameter**
- `/v1/meteofrance` — dediziert für AROME/ARPEGE Daten (Frankreich, Mittelmeer)
- `/v1/dwd-icon` — dediziert für ICON/ICON-D2 Daten (Deutschland, Europa)
- `/v1/ecmwf` — dediziert für ECMWF IFS Daten (global)
- `/v1/metno` — dediziert für MetNo Nordic Daten (Skandinavien)

**Implementierung ignoriert diese Architektur komplett** → Alle Modelle nutzen falschen Endpunkt.

## Design

### Zweistufige Lösung

**Fix 1:** Endpoint-URLs in REGIONAL_MODELS konfigurieren (Data)
**Fix 2:** select_model() gibt Endpoint mit zurück (Logic)
**Fix 3:** _request() nutzt dynamischen Endpoint statt hardcoded BASE_URL (Execution)
**Fix 4:** fetch_forecast() übergibt Endpoint an _request() (Orchestration)
**Fix 5:** model-Parameter aus params entfernen (Cleanup)

### Fix 1: Endpoint-URL pro Modell in REGIONAL_MODELS

```python
# src/providers/openmeteo.py:62-98
REGIONAL_MODELS = [
    {
        "id": "meteofrance_arome",
        "name": "AROME France & Balearen (1.3 km)",
        "endpoint": "/v1/meteofrance",  # NEU: Dedizierter Endpunkt
        "bounds": {"min_lat": 38.0, "max_lat": 53.0, "min_lon": -8.0, "max_lon": 10.0},
        "grid_res_km": 1.3,
        "priority": 1,
    },
    {
        "id": "icon_d2",
        "name": "ICON-D2 (2 km)",
        "endpoint": "/v1/dwd-icon",  # NEU: Gleicher Endpunkt für alle ICON-Modelle
        "bounds": {"min_lat": 43.0, "max_lat": 56.0, "min_lon": 2.0, "max_lon": 18.0},
        "grid_res_km": 2.0,
        "priority": 2,
    },
    {
        "id": "metno_nordic",
        "name": "MetNo Nordic (1 km)",
        "endpoint": "/v1/metno",  # NEU: Norwegischer Endpunkt
        "bounds": {"min_lat": 53.0, "max_lat": 72.0, "min_lon": 3.0, "max_lon": 35.0},
        "grid_res_km": 1.0,
        "priority": 3,
    },
    {
        "id": "icon_eu",
        "name": "ICON-EU (7 km)",
        "endpoint": "/v1/dwd-icon",  # NEU: Gleicher Endpunkt wie ICON-D2
        "bounds": {"min_lat": 29.0, "max_lat": 71.0, "min_lon": -24.0, "max_lon": 45.0},
        "grid_res_km": 7.0,
        "priority": 4,
    },
    {
        "id": "ecmwf_ifs04",
        "name": "ECMWF IFS (40 km)",
        "endpoint": "/v1/ecmwf",  # NEU: ECMWF-Endpunkt
        "bounds": {"min_lat": -90.0, "max_lat": 90.0, "min_lon": -180.0, "max_lon": 180.0},
        "grid_res_km": 40.0,
        "priority": 5,
    },
]
```

**Begründung:**
- ICON-D2 und ICON-EU nutzen gleichen Endpunkt (`/v1/dwd-icon`) — API unterscheidet intern
- Alle anderen Modell-Familien haben dedizierte Endpunkte
- Endpoint wird Teil der Modell-Konfiguration (Single Source of Truth)

### Fix 2: select_model() gibt Endpoint mit zurück

```python
# src/providers/openmeteo.py:131-169
def select_model(self, lat: float, lon: float) -> Tuple[str, float, str]:
    """
    Select best weather model based on coordinates.

    Iterates models by priority (highest resolution first) and returns
    first match with endpoint path. ECMWF global model guarantees coverage.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)

    Returns:
        Tuple of (model_id, grid_res_km, endpoint_path)  # NEU: endpoint_path

    Raises:
        ProviderError: If no model found (critical config error)
    """
    for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
        bounds = model["bounds"]
        if (
            bounds["min_lat"] <= lat <= bounds["max_lat"]
            and bounds["min_lon"] <= lon <= bounds["max_lon"]
        ):
            logger.debug(
                f"Selected model '{model['id']}' ({model['grid_res_km']}km) "
                f"endpoint='{model['endpoint']}' for lat={lat}, lon={lon}"
            )
            return model["id"], model["grid_res_km"], model["endpoint"]  # NEU

    # FAILSAFE: Should NEVER be reached (ECMWF is global)
    raise ProviderError(
        "openmeteo",
        f"CRITICAL: No model found for lat={lat}, lon={lon}. "
        f"ECMWF global fallback failed - check REGIONAL_MODELS configuration!"
    )
```

**Änderungen:**
- Return-Type: `Tuple[str, float]` → `Tuple[str, float, str]`
- Return-Wert: `(model_id, grid_res_km)` → `(model_id, grid_res_km, endpoint)`
- Log-Ausgabe erweitert um endpoint

### Fix 3: _request() nutzt dynamischen Endpoint

```python
# src/providers/openmeteo.py:49-51
# ERSETZT: BASE_URL = "https://api.open-meteo.com/v1/forecast"
BASE_HOST = "https://api.open-meteo.com"  # Nur Host, kein Pfad!
TIMEOUT = 30.0
```

```python
# src/providers/openmeteo.py:178-206
@retry(...)
def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make HTTP request to Open-Meteo API with retry logic.

    Retries on:
    - HTTP 502, 503, 504 (transient server errors)
    - Connection errors
    - Read timeouts

    Args:
        endpoint: API endpoint path (e.g., "/v1/meteofrance")  # NEU
        params: Query parameters

    Returns:
        JSON response as dict

    Raises:
        ProviderRequestError: On non-retryable errors or after max retries
    """
    url = f"{BASE_HOST}{endpoint}"  # NEU: Dynamische URL-Konstruktion
    try:
        response = self._client.get(url, params=params)  # NEU: url statt BASE_URL
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise ProviderRequestError(
            "openmeteo",
            f"API error: {e.response.status_code} - {e.response.text}"
        ) from e
    except httpx.RequestError as e:
        raise ProviderRequestError("openmeteo", f"Request failed: {e}") from e
```

**Änderungen:**
- Signatur: `_request(params)` → `_request(endpoint, params)`
- URL-Konstruktion: `BASE_URL` → `f"{BASE_HOST}{endpoint}"`
- Endpoint-Auswahl erfolgt in fetch_forecast() (via select_model)

### Fix 4: fetch_forecast() übergibt Endpoint

```python
# src/providers/openmeteo.py:324-400
def fetch_forecast(
    self,
    location: "Location",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> NormalizedTimeseries:
    # Select best model for location
    model_id, grid_res_km, endpoint = self.select_model(  # NEU: endpoint
        location.latitude, location.longitude
    )

    # Build request parameters
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        # ENTFERNT: "model": model_id,  # Nicht mehr nötig! Endpoint bestimmt Modell
        "hourly": ",".join([...]),
        "timezone": "UTC",
    }

    # ... (time range logic bleibt unverändert) ...

    logger.info(
        f"Fetching Open-Meteo forecast for {location.name or 'location'} "
        f"({location.latitude}, {location.longitude}) "
        f"using model '{model_id}' via endpoint '{endpoint}'"  # NEU: endpoint in Log
    )

    # Make request with retry logic
    response_data = self._request(endpoint, params)  # NEU: endpoint übergeben

    # Parse and return
    return self._parse_response(response_data, model_id, grid_res_km)
```

**Änderungen:**
- `select_model()` Call: `model_id, grid_res_km = ...` → `model_id, grid_res_km, endpoint = ...`
- params: `"model": model_id` entfernt (nicht mehr nötig)
- `_request()` Call: `_request(params)` → `_request(endpoint, params)`
- Log-Ausgabe erweitert um endpoint

### Fix 5: tools/weather_validation.py ebenfalls korrigieren

**Problem:** Validation-Tool hat gleichen Bug (nutzt `/v1/forecast` mit model-Parameter).

```python
# tools/weather_validation.py:36 (circa)
# VORHER:
response = httpx.get(
    "https://api.open-meteo.com/v1/forecast",
    params={"model": "meteofrance_arome", ...}
)

# NACHHER:
response = httpx.get(
    "https://api.open-meteo.com/v1/meteofrance",  # Dedizierter Endpunkt
    params={...}  # Kein model-Parameter
)
```

**Achtung:** Validation-Tool muss Model-Auswahl-Logik replizieren oder OpenMeteoProvider importieren.

## Affected Files

| Datei | Änderung | LOC |
|-------|----------|-----|
| `src/providers/openmeteo.py` | endpoint in REGIONAL_MODELS, select_model() Signatur, BASE_URL→BASE_HOST, _request() Signatur, fetch_forecast() Anpassung | ~25 |
| `docs/specs/modules/provider_openmeteo.md` | Endpoint-Architektur dokumentieren, Beispiele anpassen | ~15 |
| `tools/weather_validation.py` | Dedizierte Endpunkte nutzen statt /v1/forecast | ~5 |
| `tests/unit/test_openmeteo_endpoint_routing.py` | 5 Unit Tests (NEU) | ~120 |
| **Gesamt** | | **~165 LOC** |

## Test Plan

### Automatisiert (NEUE Datei: tests/unit/test_openmeteo_endpoint_routing.py)

**Test 1: test_select_model_returns_correct_endpoint**
```python
def test_select_model_returns_correct_endpoint():
    provider = OpenMeteoProvider()

    # Mallorca → AROME France
    model_id, grid_res, endpoint = provider.select_model(39.77, 2.72)
    assert model_id == "meteofrance_arome"
    assert endpoint == "/v1/meteofrance"
    assert grid_res == 1.3

    # München → ICON-D2
    model_id, grid_res, endpoint = provider.select_model(48.14, 11.58)
    assert model_id == "icon_d2"
    assert endpoint == "/v1/dwd-icon"
    assert grid_res == 2.0

    # Oslo → MetNo Nordic
    model_id, grid_res, endpoint = provider.select_model(59.91, 10.75)
    assert model_id == "metno_nordic"
    assert endpoint == "/v1/metno"
    assert grid_res == 1.0

    # Athen → ICON-EU
    model_id, grid_res, endpoint = provider.select_model(37.98, 23.73)
    assert model_id == "icon_eu"
    assert endpoint == "/v1/dwd-icon"
    assert grid_res == 7.0

    # Tokyo → ECMWF global
    model_id, grid_res, endpoint = provider.select_model(35.68, 139.69)
    assert model_id == "ecmwf_ifs04"
    assert endpoint == "/v1/ecmwf"
    assert grid_res == 40.0
```

**Test 2: test_dedicated_endpoint_returns_valid_data** (Echter API-Call!)
```python
def test_dedicated_endpoint_returns_valid_data():
    """Verify dedicated endpoints return valid hourly forecast data."""
    provider = OpenMeteoProvider()
    lat, lon = 39.77, 2.72  # Mallorca

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_gusts_10m,cloud_cover",
        "timezone": "UTC",
    }

    # Real API call to dedicated meteofrance endpoint
    data = provider._request("/v1/meteofrance", params)

    # Must return valid hourly structure
    assert "hourly" in data
    assert "temperature_2m" in data["hourly"]
    assert "wind_gusts_10m" in data["hourly"]
    assert len(data["hourly"]["temperature_2m"]) >= 24  # Mindestens 24 Stunden
```

**Test 3: test_model_data_differs_between_endpoints** (NICHT gemockt!)
```python
def test_model_data_differs_between_endpoints():
    """
    CRITICAL REGRESSION TEST: Verify endpoints return different model data.
    If /v1/forecast is accidentally reintroduced, this catches it.
    """
    provider = OpenMeteoProvider()
    lat, lon = 39.77, 2.72  # Mallorca

    # Fetch from meteofrance endpoint
    params_france = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_gusts_10m,cloud_cover",
        "timezone": "UTC",
    }
    data_france = provider._request("/v1/meteofrance", params_france)

    # Fetch from dwd-icon endpoint (same location)
    data_icon = provider._request("/v1/dwd-icon", params_france)

    # Extract first hourly value from each
    t_france = data_france["hourly"]["temperature_2m"][0]
    t_icon = data_icon["hourly"]["temperature_2m"][0]

    gust_france = data_france["hourly"]["wind_gusts_10m"][0]
    gust_icon = data_icon["hourly"]["wind_gusts_10m"][0]

    # CRITICAL: Values MUST differ (different models)
    # If they're identical → bug is back (generic endpoint in use)
    assert t_france != t_icon or gust_france != gust_icon, (
        "REGRESSION: Endpoints return identical data! "
        "Likely using generic /v1/forecast instead of dedicated endpoints."
    )
```

**Test 4: test_base_host_has_no_path** (Strukturcheck)
```python
def test_base_host_has_no_path():
    """Verify BASE_HOST contains only the host, no API path."""
    from providers.openmeteo import BASE_HOST

    assert BASE_HOST == "https://api.open-meteo.com", (
        f"BASE_HOST should be host-only, got: {BASE_HOST}"
    )
    # Must NOT contain /v1/forecast or any path
    assert "/v1/" not in BASE_HOST, (
        "REGRESSION: BASE_HOST contains API path! Use dedicated endpoints via REGIONAL_MODELS."
    )
```

**Test 5: test_all_regional_models_have_endpoint**
```python
def test_all_regional_models_have_endpoint():
    """Verify REGIONAL_MODELS data integrity."""
    from providers.openmeteo import REGIONAL_MODELS

    for model in REGIONAL_MODELS:
        # Every model MUST have endpoint field
        assert "endpoint" in model, f"Model {model['id']} missing 'endpoint' field"

        # Endpoint MUST start with /v1/
        assert model["endpoint"].startswith("/v1/"), (
            f"Model {model['id']} has invalid endpoint: {model['endpoint']}"
        )

        # Endpoint MUST NOT be the generic /v1/forecast
        assert model["endpoint"] != "/v1/forecast", (
            f"Model {model['id']} uses generic endpoint - use dedicated endpoint!"
        )
```

### Manuell (Regression Check)

- [ ] Mallorca-Location → fetch_forecast() → Prüfe Wetterdaten gegen Windy/AROME
- [ ] München-Location → fetch_forecast() → Prüfe Wetterdaten gegen Windy/ICON-D2
- [ ] tools/weather_validation.py ausführen → Keine Fehler
- [ ] Log-Output: "using model 'meteofrance_arome' via endpoint '/v1/meteofrance'" sichtbar

## Edge Cases

| Szenario | Komponente | Verhalten nach Fix |
|----------|------------|-------------------|
| Mallorca (AROME) | `select_model()` → endpoint="/v1/meteofrance" | Korrektes Modell, verifiziert durch Test 1+3 |
| Überlappende Region (Alpen: AROME vs ICON-D2) | `select_model()` Priority-Sortierung | AROME gewinnt (Priority 1 < 2), endpoint="/v1/meteofrance" |
| ICON-D2 und ICON-EU gleicher Endpunkt | `REGIONAL_MODELS` Konfiguration | Beide endpoint="/v1/dwd-icon", API unterscheidet intern via Auflösung |
| Global (Tokyo → ECMWF) | `select_model()` ECMWF-Fallback | endpoint="/v1/ecmwf", verifiziert durch Test 1 |
| MetNo für Nicht-Skandinavien | `/v1/metno` API liefert Fehler | `_request()` Retry-Logik + ProviderRequestError (bestehend) |
| API-Endpoint-URL ändert sich | `REGIONAL_MODELS["endpoint"]` anpassen | Eine Stelle ändern (Single Source of Truth) |
| Neues Modell hinzufügen | Neuen Eintrag in `REGIONAL_MODELS` mit endpoint | Test 5 validiert Integrität automatisch |

## Known Limitations

### API-Endpoint-URLs sind nicht dynamisch
- Endpoint-Pfade sind in REGIONAL_MODELS hardcoded (`"/v1/meteofrance"`, etc.)
- Bei API-Änderungen durch OpenMeteo muss REGIONAL_MODELS aktualisiert werden
- **Akzeptabel:** API-Endpunkte sind stabil (seit Jahren unverändert)

### Modell-Parameter wird komplett entfernt
- Dedizierte Endpunkte benötigen keinen `model`-Parameter
- Manche Endpunkte (z.B. `/v1/dwd-icon`) unterstützen mehrere Modelle
- API unterscheidet intern (vermutlich via Koordinaten + Auflösung)
- **Akzeptabel:** API-Dokumentation empfiehlt diese Nutzung

### tools/weather_validation.py benötigt Update
- Validation-Tool muss ebenfalls auf dedizierte Endpunkte migriert werden
- Entweder Model-Auswahl replizieren ODER OpenMeteoProvider importieren
- **Empfehlung:** Provider importieren (Single Source of Truth)

## Acceptance Criteria

- [ ] `test_select_model_returns_correct_endpoint` grün: 5 Regionen → korrekte Endpoints
- [ ] `test_dedicated_endpoint_returns_valid_data` grün: Echter API-Call an `/v1/meteofrance` liefert Daten
- [ ] `test_model_data_differs_between_endpoints` grün: AROME ≠ ICON Daten (Regressionsschutz)
- [ ] `test_base_host_has_no_path` grün: `BASE_HOST` enthält keinen API-Pfad
- [ ] `test_all_regional_models_have_endpoint` grün: Alle Modelle haben `endpoint`-Feld
- [ ] `BASE_URL` existiert nicht mehr in `src/providers/openmeteo.py` (ersetzt durch `BASE_HOST`)
- [ ] Mallorca-Forecast liefert AROME-Daten (verifizierbar via Windy oder `tools/weather_validation.py`)
- [ ] Log-Output zeigt: "using model 'meteofrance_arome' via endpoint '/v1/meteofrance'"
- [ ] `tools/weather_validation.py` nutzt dedizierte Endpunkte (kein `/v1/forecast` mehr)
- [ ] Spec `docs/specs/modules/provider_openmeteo.md` dokumentiert Endpoint-Architektur

## Changelog

- 2026-02-16: v1.0 Bugfix-Spec erstellt (openmeteo_endpoint_routing)
- 2026-02-16: v1.1 Implementiert — 5 Fixes, 11 Unit Tests alle grün
