---
entity_id: provider_openmeteo
type: module
created: 2026-01-24
updated: 2026-01-24
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, regional-models]
---

# Provider: Open-Meteo (Regional Models)

## Approval

- [x] Approved (2026-01-24, Henning)

**Approval-Bedingung:**
- **ZWINGEND:** Fuer alle Regionen MUSS ein Modell ausgewaehlt sein
- ECMWF global fallback garantiert vollstaendige Abdeckung
- Falls kein Modell gefunden → Exception (Failsafe)

## Purpose

Adapter fuer Open-Meteo Forecast API mit dynamischer Modellauswahl basierend auf geografischer Lage. Verwendet hochaufloesende regionale Modelle (meteofrance_arome, icon_d2, metno_nordic) fuer Europa und globales ECMWF als Fallback, um beste Vorhersagequalitaet pro Region zu erreichen.

## Source

- **File:** `src/providers/openmeteo.py` (geplant)
- **Identifier:** `class OpenMeteoProvider`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| NormalizedTimeseries | dto | Ausgabeformat (src/app/models.py) |
| ForecastDataPoint | dto | Einzelner Datenpunkt |
| ForecastMeta | dto | Provenance-Metadaten |
| Location | dto | Koordinaten-Input (src/app/config.py) |
| WeatherProvider | protocol | Interface (src/providers/base.py) |
| httpx | lib | HTTP-Client mit Retry-Logik |

## Data Governance Requirement

**ACHTUNG:** Diese Implementierung benoetigt Genehmigung in `docs/specs/data_sources.md`!

Aktuell sind von Open-Meteo NUR Cloud-Layer-Parameter genehmigt:
- `cloud_cover_low` ✅
- `cloud_cover_mid` ✅
- `cloud_cover_high` ✅

**NICHT genehmigt:**
- `temperature_2m` ❌
- `wind_speed_10m` ❌
- `precipitation` ❌
- etc.

**Vor Implementierung erforderlich:**
1. Antrag in `docs/specs/data_sources.md` unter "Offene Antraege" eintragen
2. Genehmigung durch Product Owner (Henning)
3. Update der Tabelle "Genehmigte Parameter"

Siehe Abschnitt "Open-Meteo Parameter Approval Request" unten.

## Implementation Details

### Regional Model Selection

Die Modellauswahl erfolgt automatisch basierend auf Lat/Lon-Koordinaten:

```python
REGIONAL_MODELS = [
    {
        "id": "meteofrance_arome",
        "name": "AROME France & Balearen (1.3 km)",
        "endpoint": "/v1/meteofrance",  # Dedizierter Endpunkt!
        "bounds": {"min_lat": 38.0, "max_lat": 53.0, "min_lon": -8.0, "max_lon": 10.0},
        "grid_res_km": 1.3,
        "priority": 1  # Hoechste Prioritaet (hoechste Aufloesung)
    },
    {
        "id": "icon_d2",
        "name": "ICON-D2 (2 km)",
        "endpoint": "/v1/dwd-icon",
        "bounds": {"min_lat": 43.0, "max_lat": 56.0, "min_lon": 2.0, "max_lon": 18.0},
        "grid_res_km": 2.0,
        "priority": 2
    },
    {
        "id": "metno_nordic",
        "name": "MetNo Nordic (1 km)",
        "endpoint": "/v1/metno",
        "bounds": {"min_lat": 53.0, "max_lat": 72.0, "min_lon": 3.0, "max_lon": 35.0},
        "grid_res_km": 1.0,
        "priority": 3
    },
    {
        "id": "icon_eu",
        "name": "ICON-EU (7 km)",
        "endpoint": "/v1/dwd-icon",
        "bounds": {"min_lat": 29.0, "max_lat": 71.0, "min_lon": -24.0, "max_lon": 45.0},
        "grid_res_km": 7.0,
        "priority": 4
    },
    {
        "id": "ecmwf_ifs04",
        "name": "ECMWF IFS (40 km)",
        "endpoint": "/v1/ecmwf",
        "bounds": {"min_lat": -90.0, "max_lat": 90.0, "min_lon": -180.0, "max_lon": 180.0},
        "grid_res_km": 40.0,
        "priority": 5  # Global fallback
    }
]

def select_model(lat: float, lon: float) -> Tuple[str, float, str]:
    """
    Waehlt bestes Modell basierend auf Koordinaten.
    Iteriert nach Prioritaet (hoechste Aufloesung zuerst).
    Gibt (model_id, grid_res_km, endpoint_path) zurueck.

    KRITISCH: MUSS immer ein gueltiges Modell zurueckgeben!
    ECMWF global fallback garantiert vollstaendige Abdeckung.

    Raises:
        ProviderError: Falls kein Modell gefunden (sollte NIEMALS passieren)
    """
    for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
        bounds = model["bounds"]
        if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
            bounds["min_lon"] <= lon <= bounds["max_lon"]):
            return model["id"], model["grid_res_km"], model["endpoint"]

    raise ProviderError(
        f"CRITICAL: No model found for lat={lat}, lon={lon}. "
        f"ECMWF global fallback failed - check REGIONAL_MODELS configuration!"
    )
```

### API Call Structure

```python
BASE_HOST = "https://api.open-meteo.com"  # Host only, no path!

def fetch_forecast(self, location: Location, start: datetime, end: datetime) -> NormalizedTimeseries:
    model_id, grid_res_km, endpoint = self.select_model(location.latitude, location.longitude)

    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        # No "model" param needed — dedicated endpoint determines model
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dewpoint_2m",
            "pressure_msl",
            "cloud_cover",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "precipitation",
            "weather_code"
        ]),
        "timezone": "UTC",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d")
    }

    url = f"{BASE_HOST}{endpoint}"  # z.B. https://api.open-meteo.com/v1/meteofrance
    response = httpx.get(url, params=params, timeout=30.0)
    response.raise_for_status()

    return self._parse_response(response.json(), model_id, grid_res_km)
```

### Parameter Mapping

Nach Genehmigung (siehe unten):

| Open-Meteo Parameter | ForecastDataPoint Feld | Transformation |
|---------------------|------------------------|----------------|
| temperature_2m | t2m_c | Direkt (°C) |
| wind_speed_10m | wind10m_kmh | km/h direkt |
| wind_direction_10m | wind_direction_deg | Direkt (0-360°) |
| wind_gusts_10m | gust_kmh | km/h direkt |
| precipitation | precip_1h_mm | Direkt (mm) |
| - | precip_rate_mmph | **NOT AVAILABLE** (Open-Meteo provides hourly totals, not rates) |
| cloud_cover | cloud_total_pct | Direkt (0-100%) |
| cloud_cover_low | cloud_low_pct | Direkt (0-100%) |
| cloud_cover_mid | cloud_mid_pct | Direkt (0-100%) |
| cloud_cover_high | cloud_high_pct | Direkt (0-100%) |
| relative_humidity_2m | humidity_pct | Direkt (0-100%) |
| dewpoint_2m | dewpoint_c | Direkt (°C) |
| pressure_msl | pressure_msl_hpa | Direkt (hPa) |
| weather_code | symbol | Via WMO-Code-Mapping |

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

Siehe: `docs/specs/modules/uv_air_quality.md`

### Thunder Logic

Open-Meteo verwendet WMO Weather Codes:

```python
THUNDER_CODES = {95, 96, 99}  # Thunderstorm codes

def _parse_thunder_level(weather_code: int) -> ThunderLevel:
    if weather_code in THUNDER_CODES:
        return ThunderLevel.HIGH
    else:
        return ThunderLevel.NONE
```

### Retry Logic

Analog zu GeoSphere Provider (src/providers/geosphere.py:220-261):

```python
RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2
RETRY_WAIT_MAX = 60
RETRY_STATUS_CODES = {502, 503, 504}

@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=retry_if_exception(_is_retryable_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _request(self, params: dict):
    response = self._client.get(BASE_URL, params=params, timeout=30.0)
    response.raise_for_status()
    return response.json()
```

## Expected Behavior

### Input
- `location: Location` - Koordinaten (lat, lon)
- `start: Optional[datetime]` - Startzeit (default: now)
- `end: Optional[datetime]` - Endzeit (default: now + 48h)

### Output
- `NormalizedTimeseries` mit:
  - `meta.provider = Provider.OPENMETEO`
  - `meta.model = "[dynamisch gewaehltes Modell-ID]"` (z.B. "meteofrance_arome")
  - `meta.grid_res_km = [Modell-spezifisch]` (z.B. 1.3 fuer AROME)
  - `meta.interp = "grid_point"`
  - `data = List[ForecastDataPoint]` (stuendlich)

### Side Effects
- HTTP-Request an Open-Meteo API
- Logging via Python logging (DEBUG: Modellauswahl, INFO: Request-Start/Ende, WARNING: Retries)

### Example

```python
provider = OpenMeteoProvider()
location = Location(latitude=39.6953, longitude=3.0176, name="Mallorca")  # Palma

# Automatische Modellauswahl: meteofrance_arome (1.3km)
forecast = provider.fetch_forecast(location)

assert forecast.meta.provider == Provider.OPENMETEO
assert forecast.meta.model == "meteofrance_arome"
assert forecast.meta.grid_res_km == 1.3
assert len(forecast.data) == 48  # 48 Stunden
```

## Known Limitations

### Mandatory Model Selection (APPROVAL REQUIREMENT)

**KRITISCH:** Fuer ALLE Regionen MUSS ein Modell ausgewaehlt sein!

- `select_model()` MUSS immer ein gueltiges Modell-ID zurueckgeben
- ECMWF global fallback (`-90° bis 90°, -180° bis 180°`) garantiert vollstaendige Abdeckung
- Falls KEIN Modell gefunden → `ProviderError` Exception (Failsafe)
- **Grund:** Approval-Bedingung vom Product Owner (2026-01-24)

**Qualitaetsstufen:**
1. **Hochaufloesung (1-2km):** meteofrance_arome, icon_d2, metno_nordic
2. **Mittlere Aufloesung (7km):** icon_eu
3. **Grobe Aufloesung (40km):** ecmwf_ifs04 (immer verfuegbar)

### Regional Coverage
- **Optimale Qualitaet:** Europa (Frankreich bis Skandinavien)
- **Globaler Fallback:** ECMWF IFS (40km) - deutlich grober
- **Keine regionalen Modelle:** Afrika, Asien, Ozeanien (nur ECMWF)

### Model Overlap
- **Ueberlappende Regionen:** Alpen (AROME vs ICON-D2)
  - Auswahl nach Prioritaet (AROME bevorzugt, da hoehere Aufloesung)
  - Bei Bedarf manuelle Provider-Auswahl via Config

### Parameter Availability
- Nicht alle Modelle liefern alle Parameter (z.B. CAPE oft nicht verfuegbar)
- Wintersport-Parameter (snow_depth, snowfall_limit) NICHT in Open-Meteo API
  - → Kombiniert mit GeoSphere/Bergfex verwenden

### API Limits
- Free Tier: 10,000 API calls/day
- Kommerzielle Lizenz fuer Produktivbetrieb ggf. erforderlich

### Data Governance
- **KRITISCH:** Parameter-Nutzung unterliegt `docs/specs/data_sources.md` Governance
- Erweiterungen NUR nach Genehmigung durch Product Owner

## Open-Meteo Parameter Approval Request

**STATUS:** PENDING (Henning-Genehmigung erforderlich)

### Antrag

**Datum:** 2026-01-24
**Antragsteller:** Claude (via User Request)
**Quelle:** Open-Meteo Forecast API (https://api.open-meteo.com/v1/forecast)

### Begruendung

1. **Regionale Modellauswahl:** Open-Meteo bietet als einzige API Zugriff auf:
   - Franzoesisches AROME-Modell (1.3km) fuer Mallorca, Korsika, Westalpen
   - Deutsches ICON-D2 (2km) fuer Alpen, Deutschland, Oesterreich
   - Norwegisches MetNo Nordic (1km) fuer Skandinavien
   - Alles ueber EINEN API-Endpunkt mit `models=` Parameter

2. **Bessere Qualitaet als GeoSphere fuer nicht-oesterreichische Regionen:**
   - GeoSphere: Nur Alpen/Oesterreich
   - Open-Meteo: Europa-weit + global

3. **Zielgruppen-Nutzen:**
   - Weitwanderer auf GR20 (Korsika) → AROME 1.3km statt ECMWF 40km
   - Skandinavien-Touren → MetNo Nordic 1km

### Genehmigte Parameter (Antrag)

| Parameter | Feld in ForecastDataPoint | Zweck | Einheit |
|-----------|---------------------------|-------|---------|
| temperature_2m | t2m_c | Temperatur 2m | °C |
| relative_humidity_2m | humidity_pct | Luftfeuchtigkeit | % |
| dewpoint_2m | dewpoint_c | Taupunkt | °C |
| pressure_msl | pressure_msl_hpa | Luftdruck MSL | hPa |
| cloud_cover | cloud_total_pct | Gesamtbewoelkung | % |
| wind_speed_10m | wind10m_kmh | Windgeschwindigkeit 10m | km/h |
| wind_direction_10m | wind_direction_deg | Windrichtung | 0-360° |
| wind_gusts_10m | gust_kmh | Windboeen | km/h |
| precipitation | precip_1h_mm | Niederschlag stuendlich | mm |
| weather_code | symbol | Wettersymbol (WMO-Code) | - |

**Bereits genehmigt (bleiben unveraendert):**
- cloud_cover_low
- cloud_cover_mid
- cloud_cover_high

### Model-Parameter

| Parameter | Zweck | Werte |
|-----------|-------|-------|
| models | Modellauswahl | meteofrance_arome, icon_d2, metno_nordic, icon_eu, ecmwf_ifs04 |

### Alternative Betrachtungen

**Option A: Nur Cloud-Layer nutzen (aktuell)**
- ❌ Verschenkt Potenzial regionaler Hochaufloesung
- ❌ Unvollstaendige Daten (keine Temperatur, Wind, etc.)

**Option B: GeoSphere erweitern**
- ❌ GeoSphere deckt nur Alpen/Oesterreich ab
- ❌ Kein Zugriff auf AROME (Mallorca), MetNo (Skandinavien)

**Option C: Open-Meteo als zusaetzlicher Provider (dieser Antrag)**
- ✅ Beste regionale Qualitaet pro Region
- ✅ Ein API-Endpunkt statt mehrere Provider
- ✅ Konsistente Datenstruktur

### Risikobewertung

**Niedrig:**
- Open-Meteo ist etablierte, stabile API (seit 2020+)
- Free Tier ausreichend fuer MVP (10k calls/day)
- Parameter sind Standard-Meteorologie (WMO-konform)
- Kein Lock-in: Provider-Architektur erlaubt einfachen Wechsel

### Naechste Schritte

1. **Henning prueft Antrag**
2. **Bei Genehmigung:**
   - Update `docs/specs/data_sources.md` (Tabelle "Genehmigte Datenquellen")
   - Status dieser Spec → `approved`
   - Implementierung freigegeben
3. **Bei Ablehnung:**
   - Alternative Loesungen evaluieren (z.B. nur fuer Cloud-Layer nutzen)

## Changelog

- 2026-01-24: Initial spec created (draft, pending data governance approval)
