---
entity_id: go_provider_openmeteo
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, go, provider, weather, open-meteo, regional-models, bugfix]
---

# M2: OpenMeteo Provider (Go native)

## Approval

- [ ] Approved

## Purpose

Native Go-Implementierung des OpenMeteo Weather Providers als direkter Ersatz fuer den bisherigen Python-Proxy-Handler. Waehlt automatisch das hochaufloesendste regionale Wettermodell basierend auf Koordinaten, behebt BUG-TZ-01 (falsche Zeitzone im API-Response) als Nebeneffekt, und liefert vollstaendig typisierte DTOs ohne externen Python-Prozess.

## Scope

### In Scope
- DTOs: `ForecastDataPoint`, `ForecastMeta`, `Timeseries`, `ThunderLevel` als Go-Structs
- `WeatherProvider` Interface + `ProviderError` / `ProviderRequestError`
- Regionale Modellauswahl (5 Modelle, Prioritaet nach Aufloesung)
- Hauptprovider: `SelectModel`, `FetchForecast`, `parseResponse`, `doRequest` (Retry), `ProbeModelAvailability`, `findFallbackModel`, `mergeFallback`
- UV-Index via separatem Air-Quality-API Endpoint (WEATHER-06)
- Metric Availability Cache (JSON-Datei, 7-Tage TTL, `sync.Mutex`)
- Timezone-Lookup via `tzf`-Bibliothek (BUG-TZ-01 Fix)
- HTTP Handler: `ForecastHandler(provider)` mit Query-Param-Parsing und Fehlerformaten
- Config-Felder: `OpenMeteoBaseURL`, `OpenMeteoAQURL`, `OpenMeteoTimeout`, `OpenMeteoRetries`, `CacheDir`
- `cmd/server/main.go`: Proxy-Zeile durch nativen Handler ersetzen

### Out of Scope
- Python OpenMeteo Provider (bleibt unveraendert)
- Frontend-Darstellung der Timezone (Consumer-Aufgabe)
- SMS / Signal Channel Formatter
- Auth / Multi-User

## Architecture

```
GET /api/forecast?lat=...&lon=...&hours=...
  └─ handler.ForecastHandler(provider)
       └─ provider/openmeteo.OpenMeteoProvider.FetchForecast(lat, lon, hours)
            ├─ SelectModel(lat, lon)          → RegionalModel
            ├─ doRequest(url, params)         → raw JSON (retry loop)
            ├─ fetchUVData(lat, lon, hours)   → uv_index per hour (Air Quality API)
            ├─ parseResponse(raw, model)      → []ForecastDataPoint
            ├─ ProbeModelAvailability()       → cache.go (LoadAvailabilityCache / SaveAvailabilityCache)
            ├─ findFallbackModel(lat, lon, primary)
            └─ mergeFallback(primary, fallback)
       └─ timezone.TimezoneForCoords(lat, lon) → "Europe/Vienna"
```

## Source

- **Files:**
  - `internal/model/forecast.go` (neu)
  - `internal/provider/provider.go` (neu)
  - `internal/provider/openmeteo/models.go` (neu)
  - `internal/provider/openmeteo/provider.go` (neu)
  - `internal/provider/openmeteo/cache.go` (neu)
  - `internal/provider/openmeteo/timezone.go` (neu)
  - `internal/handler/forecast.go` (neu)
  - `internal/config/config.go` (erweitern)
  - `cmd/server/main.go` (erweitern)
- **Identifier:** `OpenMeteoProvider`, `ForecastHandler`, `WeatherProvider`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| github.com/ringsaturn/tzf | go module (neu) | Koordinate → IANA Timezone (BUG-TZ-01) |
| github.com/go-chi/chi/v5 | go module | HTTP-Router, URL-Parameter |
| envconfig | go module | Config-Struct-Binding aus ENV |
| api.open-meteo.com | external API | Wettervorhersage (5 regionale Modelle) |
| air-quality-api.open-meteo.com | external API | UV-Index (CAMS, stundlich) |
| internal/config | go package | OpenMeteoBaseURL, OpenMeteoAQURL, Timeout, Retries, CacheDir |
| data/cache/model_availability.json | file | Metric Availability Cache (7-Tage TTL) |

## Implementation Details

### 1. DTOs — internal/model/forecast.go (~80 LoC)

```go
// ThunderLevel serialisiert als String "NONE" / "MED" / "HIGH"
type ThunderLevel string

const (
    ThunderNone ThunderLevel = "NONE"
    ThunderMed  ThunderLevel = "MED"
    ThunderHigh ThunderLevel = "HIGH"
)

// Alle optionalen Felder als Pointer mit json:",omitempty"
// → nil-Felder werden nicht serialisiert (identisch zu Pythons _clean_dict)
type ForecastDataPoint struct {
    Time            time.Time    `json:"time"`
    T2mC            *float64     `json:"t2m_c,omitempty"`
    Wind10mKmh      *float64     `json:"wind10m_kmh,omitempty"`
    WindDirectionDeg *float64    `json:"wind_direction_deg,omitempty"`
    GustKmh         *float64     `json:"gust_kmh,omitempty"`
    Precip1hMm      *float64     `json:"precip_1h_mm,omitempty"`
    CloudTotalPct   *int         `json:"cloud_total_pct,omitempty"`
    CloudLowPct     *int         `json:"cloud_low_pct,omitempty"`
    CloudMidPct     *int         `json:"cloud_mid_pct,omitempty"`
    CloudHighPct    *int         `json:"cloud_high_pct,omitempty"`
    WmoCode         *int         `json:"wmo_code,omitempty"`
    ThunderLevel    ThunderLevel `json:"thunder_level,omitempty"`
    VisibilityM     *float64     `json:"visibility_m,omitempty"`
    FreezingLevelM  *float64     `json:"freezing_level_m,omitempty"`
    WindChillC      *float64     `json:"wind_chill_c,omitempty"`
    PressureMslHpa  *float64     `json:"pressure_msl_hpa,omitempty"`
    HumidityPct     *int         `json:"humidity_pct,omitempty"`
    DewpointC       *float64     `json:"dewpoint_c,omitempty"`
    PopPct          *int         `json:"pop_pct,omitempty"`
    CapeJkg         *float64     `json:"cape_jkg,omitempty"`
    IsDay           *int         `json:"is_day,omitempty"`
    DniWm2          *float64     `json:"dni_wm2,omitempty"`
    UvIndex         *float64     `json:"uv_index,omitempty"`
}

type ForecastMeta struct {
    Provider       string  `json:"provider"`
    Model          string  `json:"model"`
    GridResKm      float64 `json:"grid_res_km"`
    FallbackModel  string  `json:"fallback_model,omitempty"`
    FallbackMetrics []string `json:"fallback_metrics,omitempty"`
}

type Timeseries struct {
    Timezone string              `json:"timezone"`
    Meta     ForecastMeta        `json:"meta"`
    Data     []ForecastDataPoint `json:"data"`
}
```

Timestamps: `time.Time` mit custom `MarshalJSON()`, das `+00:00` suffix erzeugt (statt Go-Standard `Z`), um JSON-Kompatibilitaet mit dem Python-Output zu garantieren.

### 2. Provider Interface — internal/provider/provider.go (~20 LoC)

```go
type WeatherProvider interface {
    FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)
}

type ProviderError struct{ Msg string }
func (e *ProviderError) Error() string { return e.Msg }

type ProviderRequestError struct {
    StatusCode int
    Msg        string
}
func (e *ProviderRequestError) Error() string { return fmt.Sprintf("HTTP %d: %s", e.StatusCode, e.Msg) }
```

### 3. Regionale Modelle — internal/provider/openmeteo/models.go (~60 LoC)

```go
type RegionalModel struct {
    ID       string
    Name     string
    Endpoint string   // z.B. "/v1/meteofrance"
    MinLat   float64
    MaxLat   float64
    MinLon   float64
    MaxLon   float64
    GridResKm float64
    Priority  int
}

var RegionalModels = []RegionalModel{
    {ID: "meteofrance_arome", Name: "AROME France & Balearics (1.3km)",
     Endpoint: "/v1/meteofrance",
     MinLat: 38, MaxLat: 53, MinLon: -8, MaxLon: 10, GridResKm: 1.3, Priority: 1},
    {ID: "icon_d2", Name: "ICON-D2 Germany & Alps (2km)",
     Endpoint: "/v1/dwd-icon",
     MinLat: 43, MaxLat: 56, MinLon: 2, MaxLon: 18, GridResKm: 2.0, Priority: 2},
    {ID: "metno_nordic", Name: "MetNo Nordic (1km)",
     Endpoint: "/v1/metno",
     MinLat: 53, MaxLat: 72, MinLon: 3, MaxLon: 35, GridResKm: 1.0, Priority: 3},
    {ID: "icon_eu", Name: "ICON-EU Europe (7km)",
     Endpoint: "/v1/dwd-icon",
     MinLat: 29, MaxLat: 71, MinLon: -24, MaxLon: 45, GridResKm: 7.0, Priority: 4},
    {ID: "ecmwf_ifs04", Name: "ECMWF IFS Global (40km)",
     Endpoint: "/v1/ecmwf",
     MinLat: -90, MaxLat: 90, MinLon: -180, MaxLon: 180, GridResKm: 40.0, Priority: 5},
}
```

Parameter-Mapping (OpenMeteo API → Go struct):

| API-Parameter | Struct-Feld | Einheit |
|---|---|---|
| temperature_2m | T2mC | °C |
| wind_speed_10m | Wind10mKmh | km/h |
| wind_direction_10m | WindDirectionDeg | 0-360° |
| wind_gusts_10m | GustKmh | km/h |
| precipitation | Precip1hMm | mm |
| cloud_cover | CloudTotalPct | % |
| cloud_cover_low | CloudLowPct | % |
| cloud_cover_mid | CloudMidPct | % |
| cloud_cover_high | CloudHighPct | % |
| weather_code | WmoCode + ThunderLevel | WMO-Code; Codes 95/96/99 → ThunderHigh |
| visibility | VisibilityM | m |
| freezing_level_height | FreezingLevelM | m |
| apparent_temperature | WindChillC | °C |
| pressure_msl | PressureMslHpa | hPa |
| relative_humidity_2m | HumidityPct | % |
| dewpoint_2m | DewpointC | °C |
| precipitation_probability | PopPct | % |
| cape | CapeJkg | J/kg |
| is_day | IsDay | 0/1 |
| direct_normal_irradiance | DniWm2 | W/m² |
| uv_index (Air Quality API) | UvIndex | — |

### 4. Core Provider — internal/provider/openmeteo/provider.go (~320 LoC)

**SelectModel(lat, lon float64) (RegionalModel, error)**
- Iteriert `RegionalModels` in Reihenfolge aufsteigender Priority
- Prueft ob lat/lon innerhalb der Bounding Box liegt
- Gibt erstes passendes Modell zurueck
- ECMWF (Priority 5, global) garantiert immer einen Treffer
- Gibt `ProviderError` zurueck falls kein Modell matcht (Failsafe, sollte nie passieren)

**doRequest(ctx, url, params) ([]byte, error)**
- Retry-Schleife: 5 Versuche
- Backoff: `min(2^attempt * 2, 60)` Sekunden
- Retry bei HTTP 502, 503, 504 und Netzwerkfehlern
- Alle anderen Fehler sofort zurueck
- Kein externes Backoff-Package; inline implementiert

**fetchUVData(ctx, lat, lon float64, hours int) (map[string]float64, error)**
- Request an `air-quality-api.open-meteo.com/v1/air-quality`
- Parameter: `uv_index` (hourly), `latitude`, `longitude`
- Gibt Map `timestamp → uv_index` zurueck
- Bei Fehler: leere Map + nil error (graceful degradation, UV bleibt nil)

**parseResponse(raw []byte, model RegionalModel, uvData map[string]float64) ([]ForecastDataPoint, error)**
- Deserialisiert OpenMeteo JSON (`hourly.time`, `hourly.<param>[]`)
- Iteriert parallel ueber alle Zeitstempel
- Weist Pointer-Felder zu (nil wenn API-Wert null)
- Leitet ThunderLevel aus WmoCode ab: Codes {95, 96, 99} → ThunderHigh, Rest → ThunderNone
- Merged UV-Werte via Timestamp-Lookup aus uvData

**ProbeModelAvailability() (map[string]ModelAvailability, error)**
- Prueft LoadAvailabilityCache: gueltig → return cache
- Fuer jedes Modell: API-Call mit Referenz-Koordinate (Mitte der Bounding Box), Zeitraum = morgen
- Wertet aus welche Parameter mindestens einen non-nil Wert haben
- Speichert Ergebnis via SaveAvailabilityCache
- Einzelner Modell-Fehler wird geloggt, Rest wird fortgefuehrt

**findFallbackModel(lat, lon float64, primary RegionalModel) (RegionalModel, bool)**
- Gibt zweites Modell zurueck, das lat/lon abdeckt (priority > primary.Priority)
- Gibt false wenn kein Fallback existiert

**mergeFallback(primary, fallback []ForecastDataPoint) []ForecastDataPoint**
- Iteriert primary Datenpunkte
- Fuer jeden Zeitstempel: nil-Felder in primary aus fallback befuellen (via Reflection oder explizit)
- Befuellt `ForecastMeta.FallbackModel` und `ForecastMeta.FallbackMetrics`

**FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)**
- Orchestriert SelectModel → doRequest → fetchUVData → parseResponse
- Prueft auf nil-Felder in Result → falls Luecken: findFallbackModel → doRequest → mergeFallback
- Timezone via `timezone.TimezoneForCoords(lat, lon)`
- Baut und gibt `model.Timeseries` zurueck

### 5. Availability Cache — internal/provider/openmeteo/cache.go (~90 LoC)

```go
type ModelAvailability struct {
    Available   []string `json:"available"`
    Unavailable []string `json:"unavailable"`
}

type AvailabilityCache struct {
    ProbeDate string                       `json:"probe_date"` // "2026-04-13"
    Models    map[string]ModelAvailability `json:"models"`
}

var cacheMu sync.Mutex

func LoadAvailabilityCache(path string) (*AvailabilityCache, error) {
    cacheMu.Lock()
    defer cacheMu.Unlock()
    // Datei lesen, JSON parsen, TTL pruefen (>= 7 Tage → nil, nil)
}

func SaveAvailabilityCache(path string, cache *AvailabilityCache) error {
    cacheMu.Lock()
    defer cacheMu.Unlock()
    // JSON schreiben, Verzeichnis anlegen falls noetig
}
```

Cache-Pfad: `{config.CacheDir}/model_availability.json` (Default: `data/cache/`)
TTL: 7 Tage (vergleiche probe_date mit time.Now().UTC().Truncate(24*time.Hour))

### 6. Timezone-Lookup — internal/provider/openmeteo/timezone.go (~40 LoC)

```go
var (
    tzFinder     *tzf.DefaultFinder
    tzFinderOnce sync.Once
    tzFinderErr  error
)

// TimezoneForCoords gibt IANA-Timezone-String zurueck (z.B. "Europe/Vienna").
// Initialisiert tzf einmalig via sync.Once (~20MB eingebettete Polygon-Daten).
// Bei Fehler: gibt "UTC" zurueck (graceful degradation).
func TimezoneForCoords(lat, lon float64) string
```

Behebt BUG-TZ-01: Der bisherige Proxy gibt keine Timezone-Info aus. Die Go-Implementierung ermittelt die Timezone aus lat/lon und gibt sie im Response-Envelope zurueck (`Timeseries.Timezone`).

### 7. HTTP Handler — internal/handler/forecast.go (~70 LoC)

```go
func ForecastHandler(p provider.WeatherProvider) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Query-Params parsen: lat, lon (required), hours (optional, default 48)
        // Validierung: lat ∈ [-90,90], lon ∈ [-180,180], hours ∈ [1,240]
        // p.FetchForecast(lat, lon, hours)
        // JSON-Response schreiben
    }
}
```

Fehlerformate:
- `400 {"error":"invalid_params","detail":"lat must be between -90 and 90"}`
- `502 {"error":"provider_error","detail":"<provider message>"}`

### 8. Config-Erweiterung — internal/config/config.go

Neue Felder in `Config`-Struct:

| Feld | ENV-Var | Default |
|---|---|---|
| OpenMeteoBaseURL | OPENMETEO_BASE_URL | https://api.open-meteo.com |
| OpenMeteoAQURL | OPENMETEO_AQ_URL | https://air-quality-api.open-meteo.com |
| OpenMeteoTimeout | OPENMETEO_TIMEOUT | 30s |
| OpenMeteoRetries | OPENMETEO_RETRIES | 5 |
| CacheDir | CACHE_DIR | data/cache |

### 9. main.go Anpassung — cmd/server/main.go

```go
// Vorher (Proxy):
r.Get("/api/forecast", handler.ProxyHandler(pythonBaseURL+"/api/forecast"))

// Nachher (nativ):
omprovider := openmeteo.NewOpenMeteoProvider(cfg)
r.Get("/api/forecast", handler.ForecastHandler(omprovider))
```

## Expected Behavior

### Input (GET /api/forecast)
- `lat` — float64, required, ∈ [-90, 90]
- `lon` — float64, required, ∈ [-180, 180]
- `hours` — int, optional, default 48, max 240

### Output (200 OK)
```json
{
  "timezone": "Europe/Paris",
  "meta": {
    "provider": "openmeteo",
    "model": "meteofrance_arome",
    "grid_res_km": 1.3
  },
  "data": [
    {
      "ts": "2026-04-13T12:00:00+00:00",
      "t2m_c": 14.2,
      "wind10m_kmh": 18.5,
      "thunder_level": "NONE"
    }
  ]
}
```

### Side Effects
- HTTP-Requests an api.open-meteo.com und air-quality-api.open-meteo.com
- Optionaler Schreib-Zugriff auf `data/cache/model_availability.json`
- Logging: DEBUG (Modellauswahl, Retry), INFO (Request-Start/Ende), WARN (Retry, UV-Fehler)

### Fehler-Szenarien
- Ungueltige Query-Params → 400 `invalid_params`
- OpenMeteo API permanent nicht erreichbar (alle 5 Versuche) → 502 `provider_error`
- UV-API nicht erreichbar → 200 mit `uv_index: null` (graceful degradation)
- Kein Modell gefunden → 502 `provider_error` (Failsafe, sollte nie auftreten)

## Testing

Keine Mocks. Alle Tests nutzen echte API-Calls oder echte Dateisystem-Operationen.

| # | Test | Typ | Assertion |
|---|------|-----|-----------|
| 1 | SelectModel Mallorca (39.7, 3.0) → meteofrance_arome | Unit | model.ID |
| 2 | SelectModel Innsbruck (47.3, 11.4) → icon_d2 | Unit | model.ID |
| 3 | SelectModel Oslo (59.9, 10.7) → metno_nordic | Unit | model.ID |
| 4 | SelectModel Athen (37.9, 23.7) → icon_eu | Unit | model.ID |
| 5 | SelectModel Tokio (35.7, 139.7) → ecmwf_ifs04 | Unit | model.ID |
| 6 | FetchForecast Mallorca 48h gibt Timeseries zurueck | Integration | len(data)==48 |
| 7 | FetchForecast setzt Timezone korrekt | Integration | timezone != "" |
| 8 | ThunderLevel HIGH bei WMO-Code 95 | Unit | thunder_level=="HIGH" |
| 9 | ThunderLevel NONE bei WMO-Code 61 | Unit | thunder_level=="NONE" |
| 10 | LoadAvailabilityCache gibt nil bei fehlendem File | Unit (TempDir) | nil,nil |
| 11 | SaveAvailabilityCache + LoadAvailabilityCache Roundtrip | Unit (TempDir) | data gleich |
| 12 | LoadAvailabilityCache gibt nil bei abgelaufenem Cache (>7d) | Unit (TempDir) | nil,nil |
| 13 | TimezoneForCoords Wien → "Europe/Vienna" | Unit | string match |
| 14 | Handler GET /api/forecast?lat=39.7&lon=3.0&hours=24 → 200 | Integration (httptest) | status + body |
| 15 | Handler fehlende lat → 400 invalid_params | Unit (httptest) | status + error key |
| 16 | Handler lat=999 → 400 invalid_params | Unit (httptest) | status + detail |

Integration-Tests werden mit `testing.Short()` Guard versehen (werden in CI uebersprungen).

```go
if testing.Short() {
    t.Skip("skipping integration test in short mode")
}
```

## Known Limitations

- `tzf` bettet ~20MB Polygon-Daten in das Binary ein (erhoehte Binary-Groesse)
- Retry-Backoff ist blocking (kein Context-Cancel-Support in Retry-Loop); kann bei langen Wartezeiten zu langsamen Responses fuehren
- Metric Availability Probe prueft nur Referenz-Koordinate pro Modell, nicht flaechendeckend
- Keine atomaren Cache-Schreibvorgaenge (kein Temp-File + Rename)
- Timestamp-Format muss exakt `+00:00` sein (nicht `Z`) fuer JSON-Kompatibilitaet — wird durch custom `MarshalJSON` sichergestellt, muss aber bei jedem Go-Versionsupgrade geprueft werden
- OpenMeteo Free Tier: 10.000 API-Calls/Tag; ProbeModelAvailability macht 5 zusaetzliche Calls

## Changelog

- 2026-04-13: Initial spec (M2 — OpenMeteo Provider Go native, inkl. BUG-TZ-01 Fix)
