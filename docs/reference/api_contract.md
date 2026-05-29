
# API Contract — Gregor Zwanzig

## 0) Konventionen
- Zeit: ISO-8601 UTC (`Z`)
- Einheiten im Feldnamen: `*_c`, `*_kmh`, `*_mmph`, `*_mm`, `*_pct`, `*_hpa`, `*_jkg`, `*_m`, `*_cm`
- Provider: `MOSMIX` | `MET` | `NOWCASTMIX` | `GEOSPHERE` | `SLF` | `EUREGIO`

---

## 1) Provider Adapter
### Input
- `coords: (lat, lon)`
- `start: datetime`
- `end: datetime`

### Output
Ein **Normalized Forecast Timeseries**-Objekt (siehe unten), bestehend aus `meta` + `data[]`.

---

## 2) Normalized Forecast Timeseries

### Beispiel
```json
{
  "meta": {
    "provider": "MET",
    "model": "ECMWF",
    "run": "2025-08-29T06:00Z",
    "grid_res_km": 9,
    "interp": "point_grid",
    "stations_used": [
      {"id": "10091", "name": "Fehmarn", "dist_km": 20.3, "elev_diff_m": 40}
    ]
  },
  "data": [
    {
      "ts": "2025-08-29T12:00Z",
      "t2m_c": 18.5,
      "wind10m_kmh": 22.0,
      "gust_kmh": 38.0,
      "precip_rate_mmph": 0.4,
      "precip_1h_mm": 0.4,
      "cloud_total_pct": 85,
      "symbol": "lightrain",
      "thunder_level": "MED",
      "cape_jkg": 950,
      "pop_pct": null,
      "pressure_msl_hpa": 1013,
      "humidity_pct": 78,
      "dewpoint_c": 17.0
    }
  ]
}
```

### Feldliste (Datenpunkte)

#### Basis-Felder (immer)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| ts                 | datetime        | Zeitpunkt (UTC ISO-8601)                       |
| t2m_c              | float           | 2 m-Temperatur [°C]                            |
| wind10m_kmh        | float           | 10 m-Windgeschwindigkeit [km/h]                |
| gust_kmh           | float           | Böenspitze [km/h]                              |
| precip_rate_mmph   | float           | Niederschlagsrate [mm/h] zum Zeitpunkt         |
| precip_1h_mm       | float           | 1-h-Akkumulation [mm]                          |
| cloud_total_pct    | integer (0–100) | Gesamtbewölkung [%]                            |
| symbol             | enum            | Normalisiertes Symbol (siehe SYMBOL_MAPPING)   |
| thunder_level      | enum            | Gewitter-Einstufung {NONE, MED, HIGH}          |
| cape_jkg           | float           | CAPE [J/kg]                                    |
| pop_pct            | integer (0–100) | Niederschlagswahrscheinlichkeit [%]            |
| pressure_msl_hpa   | float           | Bodendruck [hPa]                               |
| humidity_pct       | integer (0–100) | Luftfeuchtigkeit [%]                           |
| dewpoint_c         | float           | Taupunkt [°C]                                  |

#### Wintersport-Felder (optional, null wenn nicht verfuegbar)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| snow_depth_cm      | float           | Gesamtschneehoehe [cm]                         |
| snow_new_24h_cm    | float           | Neuschnee letzte 24h [cm]                      |
| snow_new_acc_cm    | float           | Neuschnee akkumuliert seit Forecast-Start [cm] |
| snowfall_limit_m   | integer         | Schneefallgrenze [m]                           |
| swe_kgm2           | float           | Schneewasseraequivalent [kg/m²]                |
| precip_type        | enum            | Niederschlagstyp {RAIN, SNOW, MIXED, FREEZING_RAIN, null} |
| freezing_level_m   | integer         | Nullgradgrenze [m]                             |
| wind_chill_c       | float           | Gefuehlte Temperatur [°C]                      |
| visibility_m       | integer         | Sichtweite [m]                                 |

### Provenance (Meta, Pflicht)
- `provider`, `model`, `run`, `interp`, `grid_res_km`, optional `stations_used[]`

---

## 3) Risk Engine
### Input
- Liste von Forecast Timeseries
- Konfiguration mit Schwellenwerten (z. B. `max_wind_kmh = 50`, `thunder_level = HIGH`)

### Output
```json
{
  "risks": [
    { "type": "thunderstorm", "level": "high", "from": "14:00Z" },
    { "type": "rain", "level": "moderate", "amount_mm": 12 }
  ]
}
```

---

## 4) Report Formatter
### Input
- Forecast DTOs
- Risk Output
- DebugBuffer

### Output (String)
```
Abendbericht: Morgen 25°C, leichter Wind (22 km/h), Regenwahrscheinlichkeit 20%.
Risiko: Gewitter ab 14:00 Uhr wahrscheinlich.
```

**Debug-Block**: wird 1:1 aus `DebugBuffer.email_subset()` übernommen und an E-Mail angehängt; die Console zeigt zusätzlich die vollständige Debug-Ausgabe.

---

## 5) Thunder Logic (Ultra-MVP)
- **MOSMIX**: `ww ∈ {95,96,99} ⇒ HIGH`; elif `CAPE ≥ 800 ⇒ MED`; else `NONE`
- **MET**: `symbol_code` enthält `"thunder"` ⇒ HIGH, sonst NONE
- **NOWCASTMIX**: `nowcast_thunder == true` ⇒ HIGH, sonst NONE

---

## 6) Avalanche Report (Separates DTO)

Lawinenlagebericht als eigenstaendiges Datenobjekt (nicht Teil von NormalizedTimeseries).

### Beispiel
```json
{
  "meta": {
    "provider": "EUREGIO",
    "region_id": "AT-07",
    "region_name": "Tirol",
    "valid_from": "2025-12-27T17:00Z",
    "valid_to": "2025-12-28T17:00Z",
    "published": "2025-12-27T16:00Z"
  },
  "danger": {
    "level": 3,
    "level_text": "erheblich",
    "elevation_above_m": 2000,
    "level_below": 2,
    "trend": "steady"
  },
  "problems": [
    {
      "type": "wind_slab",
      "aspects": ["N", "NE", "E", "NW"],
      "elevation_from_m": 2000,
      "elevation_to_m": 3000
    }
  ],
  "snowpack": {
    "structure": "moderate",
    "description": "Die Schneedecke ist maessig verfestigt..."
  }
}
```

### Feldliste

#### Meta
| Feld          | Typ      | Beschreibung                          |
|---------------|----------|---------------------------------------|
| provider      | enum     | SLF, EUREGIO, ZAMG                    |
| region_id     | string   | Regions-ID (z.B. "AT-07")             |
| region_name   | string   | Regionsname (z.B. "Tirol")            |
| valid_from    | datetime | Gueltigkeit Start                     |
| valid_to      | datetime | Gueltigkeit Ende                      |
| published     | datetime | Veroeffentlichungszeitpunkt           |

#### Danger
| Feld             | Typ     | Beschreibung                                |
|------------------|---------|---------------------------------------------|
| level            | int 1-5 | Europaeische Lawinengefahrenskala           |
| level_text       | string  | gering/maessig/erheblich/gross/sehr gross   |
| elevation_above_m| integer | Hoehengrenze (Stufe gilt oberhalb)          |
| level_below      | int 1-5 | Stufe unterhalb der Hoehengrenze (optional) |
| trend            | enum    | increasing, steady, decreasing              |

#### Problems (Array)
| Feld             | Typ      | Beschreibung                             |
|------------------|----------|------------------------------------------|
| type             | enum     | new_snow, wind_slab, persistent_weak, wet_snow, gliding_snow |
| aspects          | string[] | Expositionen (N, NE, E, SE, S, SW, W, NW) |
| elevation_from_m | integer  | Untergrenze                              |
| elevation_to_m   | integer  | Obergrenze                               |

---

## 7) Erweiterte Risk Engine

### Neue Risiko-Typen (Wintersport)
```json
{
  "risks": [
    {"type": "thunderstorm", "level": "high", "from": "14:00Z"},
    {"type": "rain", "level": "moderate", "amount_mm": 12},
    {"type": "avalanche", "level": "high", "danger_level": 4, "problems": ["wind_slab"]},
    {"type": "snowfall", "level": "moderate", "amount_cm": 30, "from": "18:00Z"},
    {"type": "wind_chill", "level": "high", "feels_like_c": -25},
    {"type": "poor_visibility", "level": "moderate", "visibility_m": 50}
  ]
}
```

### Schwellenwerte (konfigurierbar)
| Risiko         | LOW       | MODERATE    | HIGH      |
|----------------|-----------|-------------|-----------|
| avalanche      | Stufe 1-2 | Stufe 3     | Stufe 4-5 |
| snowfall (24h) | <10 cm    | 10-30 cm    | >30 cm    |
| wind_chill     | >-10°C    | -10 bis -20°C| <-20°C   |
| visibility     | >200 m    | 50-200 m    | <50 m     |
| gust           | <50 km/h  | 50-80 km/h  | >80 km/h  |

---

## 8) GPX Trip Planning (Story 1, 2, 3)

### Story 1: GPX Upload & Segment-Planung

#### GPXTrack
| Feld                 | Typ                   | Beschreibung                              |
|----------------------|-----------------------|-------------------------------------------|
| points               | list[GPXPoint]        | Track-Points (Koordinaten + Elevation)     |
| waypoints            | list[GPXWaypoint]     | Optional Waypoints (Gipfel, Hütten)        |
| total_distance_km    | float                 | Gesamt-Distanz der Route [km]              |
| total_ascent_m       | float                 | Gesamt-Aufstieg [m]                        |
| total_descent_m      | float                 | Gesamt-Abstieg [m]                         |

#### GPXPoint
| Feld                    | Typ            | Beschreibung                               |
|-------------------------|----------------|--------------------------------------------|
| lat                     | float          | Breitengrad                                 |
| lon                     | float          | Längengrad                                  |
| elevation_m             | float \| None  | Höhe über Meer [m]                          |
| distance_from_start_km  | float          | Kumulative Distanz vom Start [km]           |

#### GPXWaypoint
| Feld         | Typ            | Beschreibung                  |
|--------------|----------------|-------------------------------|
| name         | str            | Name des Wegpunkts             |
| lat          | float          | Breitengrad                    |
| lon          | float          | Längengrad                     |
| elevation_m  | float \| None  | Höhe über Meer [m]             |

#### DetectedWaypoint
| Feld         | Typ               | Beschreibung                                     |
|--------------|-------------------|--------------------------------------------------|
| type         | WaypointType      | GIPFEL, TAL, PASS                                 |
| point        | GPXPoint          | Koordinaten + Elevation                           |
| prominence_m | float             | Höhen-Prominenz [m]                               |
| name         | str \| None       | Optional aus GPX-Waypoint                         |

#### TripSegment
| Feld         | Typ       | Beschreibung                                     |
|--------------|-----------|--------------------------------------------------|
| segment_id   | int       | Segment-Nummer (1-basiert)                        |
| start_point  | GPXPoint  | Start-Koordinaten + Elevation                     |
| end_point    | GPXPoint  | End-Koordinaten + Elevation                       |
| start_time   | datetime  | Start-Zeit (berechnet)                            |
| end_time     | datetime  | End-Zeit (berechnet)                              |
| duration_hours | float   | Segment-Dauer [h]                                 |
| distance_km  | float     | Segment-Distanz [km]                              |
| ascent_m     | float     | Segment-Aufstieg [m]                              |
| descent_m    | float     | Segment-Abstieg [m]                               |
| adjusted_to_waypoint | bool | Hybrid-Segmentierung angewendet?            |
| waypoint     | DetectedWaypoint \| None | Wegpunkt (falls angepasst)        |

#### EtappenConfig
| Feld               | Typ      | Beschreibung                                |
|--------------------|----------|---------------------------------------------|
| gpx_file           | str      | Pfad zur GPX-Datei                           |
| start_time         | datetime | Start-Zeit der Etappe                        |
| speed_flat_kmh     | float    | Gehgeschwindigkeit Ebene [km/h] (z.B. 4.0)   |
| speed_ascent_mh    | float    | Steig-Geschwindigkeit [Hm/h] (z.B. 300)      |
| speed_descent_mh   | float    | Abstiegs-Geschwindigkeit [Hm/h] (z.B. 500)   |

---

### Story 2: Wetter-Engine für Trip-Segmente

#### SegmentWeatherData
| Feld        | Typ                      | Beschreibung                               |
|-------------|--------------------------|--------------------------------------------|
| segment     | TripSegment              | Segment aus Story 1                        |
| timeseries  | NormalizedTimeseries \| None | Volle stündliche Wetterdaten (None bei Fehler) |
| aggregated  | SegmentWeatherSummary    | Aggregierte Werte (MIN/MAX/AVG)            |
| fetched_at  | datetime                 | Zeitpunkt des API-Abrufs                   |
| provider    | str                      | Verwendeter Provider (GEOSPHERE, etc.)     |
| has_error   | bool                     | True wenn Provider-Fehler nach Retry-Exhaustion (WEATHER-04) |
| error_message | str \| None            | Fehlernachricht bei has_error=True (WEATHER-04) |

#### SegmentWeatherSummary
| Feld                  | Typ                  | Beschreibung                                    |
|-----------------------|----------------------|-------------------------------------------------|
| temp_min_c            | float \| None        | Minimale Temperatur im Segment [°C]              |
| temp_max_c            | float \| None        | Maximale Temperatur im Segment [°C]              |
| temp_avg_c            | float \| None        | Durchschnittstemperatur [°C]                     |
| wind_max_kmh          | float \| None        | Maximale Windgeschwindigkeit [km/h]              |
| gust_max_kmh          | float \| None        | Maximale Böengeschwindigkeit [km/h]              |
| precip_sum_mm         | float \| None        | Gesamt-Niederschlag [mm]                         |
| cloud_avg_pct         | int \| None          | Durchschnittliche Bewölkung [%]                  |
| humidity_avg_pct      | int \| None          | Durchschnittliche Luftfeuchtigkeit [%]           |
| thunder_level_max     | ThunderLevel \| None | Maximales Gewitter-Level (NONE, MED, HIGH)       |
| visibility_min_m      | int \| None          | Minimale Sichtweite [m]                          |
| dewpoint_avg_c        | float \| None        | Durchschnittlicher Taupunkt [°C]                 |
| pressure_avg_hpa      | float \| None        | Durchschnittlicher Luftdruck [hPa]               |
| wind_chill_min_c      | float \| None        | Minimale gefühlte Temperatur [°C]                |
| snow_depth_cm         | float \| None        | Schneehöhe [cm] (optional, Winter)               |
| freezing_level_m      | int \| None          | Nullgradgrenze [m] (optional, Winter)            |
| aggregation_config    | dict[str, str]       | Metadata: Aggregations-Funktionen pro Metrik     |

#### SegmentWeatherCache
| Feld        | Typ                  | Beschreibung                         |
|-------------|----------------------|--------------------------------------|
| segment_id  | str                  | Eindeutige Segment-ID                 |
| data        | SegmentWeatherData   | Gecachte Wetterdaten                  |
| fetched_at  | datetime             | Zeitpunkt des Cache-Eintrags          |
| ttl_seconds | int                  | Time-to-Live [s] (default: 3600)      |

#### WeatherChange
| Feld       | Typ    | Beschreibung                                      |
|------------|--------|---------------------------------------------------|
| metric     | str    | Metrik-Name (z.B. "temperature", "wind")           |
| old_value  | float  | Alter Wert                                         |
| new_value  | float  | Neuer Wert                                         |
| delta      | float  | Absolute Änderung                                  |
| threshold  | float  | Konfigurierbarer Schwellenwert                     |
| severity   | str    | "minor", "moderate", "major"                       |
| direction  | str    | "increase", "decrease"                             |

#### TripWeatherConfig
| Feld            | Typ           | Beschreibung                                |
|-----------------|---------------|---------------------------------------------|
| trip_id         | str           | Trip-Identifier                              |
| enabled_metrics | list[str]     | Ausgewählte Metriken (Subset von 13)         |
| updated_at      | datetime      | Zeitpunkt der letzten Änderung               |

---

### Story 3: Trip-Reports (Email/SMS)

#### TripReport
| Feld           | Typ                      | Beschreibung                                    |
|----------------|--------------------------|-------------------------------------------------|
| trip_id        | str                      | Trip-Identifier                                  |
| trip_name      | str                      | Trip-Name (für Subject/Anzeige)                  |
| report_type    | str                      | "morning", "evening", "alert"                    |
| generated_at   | datetime                 | Generierungszeitpunkt                            |
| segments       | list[SegmentWeatherData] | Alle Segmente mit Wetterdaten (Story 2)          |
| email_subject  | str                      | E-Mail Subject-Zeile                             |
| email_html     | str                      | HTML-Version des Reports                         |
| email_plain    | str                      | Plain-Text-Version des Reports                   |
| sms_text       | str \| None              | SMS-Text (≤160 chars)                            |
| triggered_by   | str \| None              | "schedule" oder "change_detection"               |
| changes        | list[WeatherChange]      | Liste der Änderungen (bei Alert)                 |

#### TripReportConfig
| Feld                            | Typ         | Beschreibung                                          |
|---------------------------------|-------------|-------------------------------------------------------|
| trip_id                         | str         | Trip-Identifier                                        |
| enabled                         | bool        | Reports aktiv? (default: true)                         |
| morning_time                    | time        | Morgen-Report Zeit (default: 07:00)                    |
| evening_time                    | time        | Abend-Report Zeit (default: 18:00)                     |
| timezone                        | str         | Zeitzone (default: "Europe/Vienna")                    |
| send_email                      | bool        | E-Mail senden? (default: true)                         |
| send_sms                        | bool        | SMS senden? (default: false)                           |
| alert_on_changes                | bool        | Alerts bei Änderungen? (default: true)                 |
| change_threshold_temp_c         | float       | Temp-Änderungs-Schwelle [°C] (default: 5.0)            |
| change_threshold_wind_kmh       | float       | Wind-Änderungs-Schwelle [km/h] (default: 20.0)         |
| change_threshold_precip_mm      | float       | Niederschlags-Schwelle [mm] (default: 10.0)            |
| include_metrics                 | list[str]   | Anzuzeigende Metriken (default: 5 Basis-Metriken)      |
| wind_exposition_min_elevation_m | float/null  | Wind-Exposition Höhen-Schwelle [m]; null = 1500m (F7c)|
| updated_at                      | datetime    | Zeitpunkt der letzten Config-Änderung                  |

#### MetricConfig (Issue #435)
| Feld                | Typ              | Beschreibung                                          |
|---------------------|------------------|-------------------------------------------------------|
| metric_id           | str              | Metrik-ID (z.B. `wind`, `cloud_total`, `sunshine`)     |
| enabled             | bool             | Metrik aktiv im Report? (default: true)                |
| aggregations        | list[str]        | Aggregations-Funktionen pro Segment (default: `["min","max"]`) |
| morning_enabled     | bool \| None     | Override Morgen-Report (None = globale Einstellung)    |
| evening_enabled     | bool \| None     | Override Abend-Report (None = globale Einstellung)     |
| use_friendly_format | bool             | @deprecated (seit Issue #435) — nutze `format_mode`    |
| format_mode         | str \| None      | Format-Modus: `"raw"` \| `"scale"` \| `"simplified"` \| `"symbol"`. None = Katalog-Default |
| alert_enabled       | bool             | Alert bei Änderung dieser Metrik? (default: false)     |
| alert_threshold     | float \| None    | Schwellenwert für Alert (z.B. 5.0 für Temperatur)      |
| horizons            | dict \| None     | Pro-Metrik-Zeithorizont-Filter (None = alle sichtbar)  |
| bucket              | str              | Spalten-Gruppierung: `"primary"` (eigene Spalte) \| `"secondary"` (Detail-Zeile), default: `"primary"` |
| order               | int              | Sortier-Reihenfolge innerhalb des Buckets (default: 0) |

**Format Mode Details:**
- `raw`: Numerischer Wert mit Einheit (z.B. `18.5°C`, `22 km/h`)
- `scale`: Kategorisierte Skala (z.B. `wind_direction` → `N`, `NE`, `E`, ...)
- `simplified`: Adjektiv-Kürzel ohne Zahl (z.B. `wind: schwach`, `precip: mäßig`)
- `symbol`: Emoji-Darstellung (z.B. `cloud_total: ☁️`, `sunshine: ☀️`)

**Backward Compatibility:**
- Bestandsdaten mit nur `use_friendly_format: bool` werden beim Laden automatisch auf `format_mode` gemappt
- Schreib-Pfade persistieren beide Felder parallel: `format_mode="symbol"` → `use_friendly_format=true`; `format_mode="raw"` → `use_friendly_format=false`

---

---

## 9) GPX Proxy Endpoint (M5a)

### POST /api/gpx/parse

Leitet GPX-Upload vom SvelteKit-Frontend via Go-Proxy an Python FastAPI weiter. Die Python-Seite ruft `gpx_to_stage_data()` auf und gibt Stage-Daten mit Waypoints zurueck.

**Pfad:** Go (:8090) → Python FastAPI (:8000), beide unter `/api/gpx/parse`

#### Request

- Content-Type: `multipart/form-data`
- Body field `file`: GPX-Datei (`.gpx`)
- Query-Param `stage_date` (optional): `YYYY-MM-DD`
- Query-Param `start_hour` (optional): Integer 0–23, default `8`

#### Response 200

```json
{
  "name": "Tag 1: von Valldemossa nach Deià",
  "date": "2026-04-14",
  "waypoints": [
    {
      "id": "G1",
      "name": "Puig des Teix",
      "lat": 39.752,
      "lon": 2.785,
      "elevation_m": 1064,
      "time_window": "08:00-10:00"
    }
  ]
}
```

#### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 400 | `{"error":"invalid_gpx","detail":"..."}` | Kein `file`-Field oder GPX nicht parsebar |
| 503 | `{"error":"core_unavailable"}` | Python-Backend nicht erreichbar oder Timeout (>30s) |

#### Source Files

| Datei | Aenderung |
|-------|-----------|
| `api/routers/gpx.py` | NEU — FastAPI Router mit `parse_gpx()` |
| `api/main.py` | +`app.include_router(gpx.router)` |
| `internal/handler/proxy.go` | +`GpxProxyHandler` — Multipart+Query-Param Forwarding, 30s Timeout |
| `cmd/server/main.go` | +`r.Post("/api/gpx/parse", handler.GpxProxyHandler(...))` |

---

---

## 10) Subscriptions CRUD Endpoints (M5b)

**Handler:** `internal/handler/subscription.go` | **Store:** `internal/store/store.go` | **Model:** `internal/model/subscription.go`

**Pfad-Prefix:** `/api/subscriptions`

### CompareSubscription DTO

```go
type CompareSubscription struct {
    ID              string                 `json:"id"`
    Name            string                 `json:"name"`
    Enabled         bool                   `json:"enabled"`
    Locations       []string               `json:"locations"`
    ForecastHours   int                    `json:"forecast_hours"`
    TimeWindowStart int                    `json:"time_window_start"`
    TimeWindowEnd   int                    `json:"time_window_end"`
    Schedule        string                 `json:"schedule"`
    Weekday         int                    `json:"weekday"`
    IncludeHourly   bool                   `json:"include_hourly"`
    TopN            int                    `json:"top_n"`
    SendEmail       bool                   `json:"send_email"`
    SendSignal      bool                   `json:"send_signal"`
    DisplayConfig   map[string]interface{} `json:"display_config,omitempty"`
}
```

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/subscriptions` | 200 | Liste aller Subscriptions (`[]` bei leer, nie `null`) |
| GET | `/api/subscriptions/{id}` | 200 / 404 | Einzelne Subscription |
| POST | `/api/subscriptions` | 201 / 400 / 409 | Neue Subscription erstellen |
| PUT | `/api/subscriptions/{id}` | 200 / 400 / 404 | Subscription aktualisieren (Pfad-ID massgeblich) |
| DELETE | `/api/subscriptions/{id}` | 204 / 404 | Subscription loeschen |

### Validierungsregeln (POST/PUT)

| Feld | Constraint |
|------|-----------|
| `id` | nicht leer |
| `name` | nicht leer |
| `forecast_hours` | in `{24, 48, 72}` |
| `schedule` | in `{"daily_morning", "daily_evening", "weekly"}` |
| `time_window_start` | 0–23 |
| `time_window_end` | 1–23 |
| — | `time_window_start < time_window_end` |
| `top_n` | 1–10 |
| `weekday` | 0–6 |

### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 400 | `{"error":"validation_error","detail":"..."}` | Pflichtfeld fehlt oder Wertebereich verletzt |
| 400 | `{"error":"bad_request"}` | JSON nicht dekodierbar |
| 404 | `{"error":"not_found"}` | ID nicht gefunden (GET/PUT/DELETE) |
| 409 | `{"error":"already_exists"}` | Duplikat-ID bei POST |

### Storage

- Datei: `data/users/{userID}/compare_subscriptions.json`
- Format: `{"subscriptions": [...]}`
- Legacy-Migration: `schedule:"weekly_friday"` → `schedule:"weekly"` + `weekday:4` (beim Laden)
- V1: `userID` hardcodiert auf `"default"`

### Source Files

| Datei | Aenderung |
|-------|-----------|
| `internal/model/subscription.go` | NEU — `CompareSubscription` Struct |
| `internal/store/store.go` | +`LoadSubscriptions`, `SaveSubscriptions`, `DeleteSubscription` |
| `internal/handler/subscription.go` | NEU — 5 HTTP-Handler |
| `cmd/server/main.go` | +5 Route-Registrierungen |

---

---

## 11) Weather Config Endpoints (M5c)

Convenience-Layer ueber die bestehenden CRUD-Handler. Erlaubt gezieltes Lesen und Ersetzen des `display_config`-Subfelds auf Trip-, Location- und Subscription-Entitaeten ohne Uebertragung des gesamten Objekts.

**Handler:** `internal/handler/weather_config.go` (NEU) | **Routing:** `cmd/server/main.go`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/trips/{id}/weather-config` | 200 / 404 | `display_config` eines Trips lesen |
| PUT | `/api/trips/{id}/weather-config` | 200 / 400 / 404 | `display_config` eines Trips setzen |
| GET | `/api/locations/{id}/weather-config` | 200 / 404 | `display_config` einer Location lesen |
| PUT | `/api/locations/{id}/weather-config` | 200 / 400 / 404 | `display_config` einer Location setzen |
| GET | `/api/subscriptions/{id}/weather-config` | 200 / 404 | `display_config` einer Subscription lesen |
| PUT | `/api/subscriptions/{id}/weather-config` | 200 / 400 / 404 | `display_config` einer Subscription setzen |

### Response Format

**GET 200 (config vorhanden):**
```json
{"show_precipitation": true, "show_wind": false}
```

**GET 200 (config nicht gesetzt):**
```json
null
```

**PUT Request Body:** Beliebiges gueltiges JSON-Objekt (opaque, kein Schema). Response: gespeichertes `display_config`.

### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 400 | `{"error":"bad_request"}` | Request-Body ist kein gueltiges JSON (PUT) |
| 404 | `{"error":"not_found"}` | Parent-Entitaet nicht gefunden |

### Notes

- `display_config` wird als `map[string]interface{}` ohne Schema-Validierung round-getrippt (opaque JSON)
- Subscription-Handler laedt alle Subscriptions + lineare Suche (kein `LoadSubscription(id)`-Singleton)
- `userID` hardcodiert auf `"default"` (V1)
- Kein File-Locking: Race Conditions bei parallelen PUT-Requests akzeptiert (Single-User V1)

### Source Files

| Datei | Aenderung |
|-------|-----------|
| `internal/handler/weather_config.go` | NEU — 6 HTTP-Handler (Get/Put fuer Trip, Location, Subscription) |
| `cmd/server/main.go` | +6 Route-Registrierungen |

---

## 12) Scheduler Status Endpoint (Epic #134)

Exposes scheduler job metadata for dashboard display (BriefingsTimeline component).

**Handler:** `internal/handler/scheduler.go` | **Routing:** `cmd/server/main.go`

### GET /api/scheduler/status

Returns current scheduler state with per-job metadata (next_run, last_run).

**Response 200:**

```json
{
  "running": true,
  "timezone": "Europe/Vienna",
  "jobs": [
    {
      "id": "morning",
      "name": "Morgenbriefing",
      "next_run": "2026-05-10T07:00:00Z",
      "last_run": {
        "time": "2026-05-09T07:00:00Z",
        "status": "ok",
        "error": null
      }
    },
    {
      "id": "evening",
      "name": "Abendbriefing",
      "next_run": "2026-05-09T18:00:00Z",
      "last_run": {
        "time": "2026-05-09T17:55:00Z",
        "status": "error",
        "error": "forecast_api_timeout"
      }
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| running | bool | Is scheduler process active |
| timezone | string | Scheduler timezone (default: "Europe/Vienna") |
| jobs[] | array | List of scheduled jobs |
| jobs[].id | string | Job identifier (morning, evening, alert, trip_reports_hourly) |
| jobs[].name | string | Human-readable job name |
| jobs[].next_run | datetime \| null | ISO-8601 UTC datetime of next scheduled run |
| jobs[].last_run | object \| null | Metadata of last execution (null if never run) |
| jobs[].last_run.time | datetime | ISO-8601 UTC timestamp of execution |
| jobs[].last_run.status | enum | 'ok' or 'error' |
| jobs[].last_run.error | string \| null | Error code/message if status='error' |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 503 | `{"error":"scheduler_unavailable"}` | Scheduler process not reachable |

---

## 13) Forecast Query Endpoint (Epic #134)

Client-side forecast fetch for dashboard weather display (non-blocking).

**Handler:** Proxies to Python weather provider | **Routing:** `cmd/server/main.go`

### GET /api/forecast

Fetches normalized weather forecast for a given coordinate.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | yes | Latitude (-90 to 90) |
| lon | float | yes | Longitude (-180 to 180) |
| hours | integer | no | Forecast range in hours (default: 24) |

**Response 200:**

```json
{
  "meta": {
    "provider": "GEOSPHERE",
    "model": "INCA-LC",
    "run": "2026-05-09T06:00:00Z",
    "grid_res_km": 1,
    "interp": "point_grid"
  },
  "data": [
    {
      "ts": "2026-05-09T12:00:00Z",
      "t2m_c": 18.5,
      "wind10m_kmh": 22.0,
      "gust_kmh": 38.0,
      "precip_1h_mm": 0.4,
      "cloud_total_pct": 85,
      "symbol": "lightrain",
      "humidity_pct": 78,
      "dewpoint_c": 17.0
    }
  ]
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid_coords"}` | lat/lon out of range or missing |
| 503 | `{"error":"provider_unavailable"}` | Weather provider API unreachable |

---

## 14) Trip-Reports Trigger Endpoint (Epic #134)

Manually triggers briefing generation for immediate test/delivery.

**Handler:** `internal/handler/scheduler.go` | **Routing:** `cmd/server/main.go`

### POST /api/scheduler/trip-reports

Enqueues immediate trip report (morning/evening/alert) generation and send for active trip.

**Request Body:** `{}` (empty, report type inferred from scheduler config)

**Response 202 (Accepted):**

```json
{
  "message": "Trip report enqueued",
  "job_id": "trip-reports-1234",
  "report_type": "evening"
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"no_active_trip"}` | No trip with today's stage found |
| 503 | `{"error":"scheduler_unavailable"}` | Scheduler not available |

---

## 15) Metric Catalog Endpoint (Issue #435)

Provides metadata about available weather metrics, including per-metric format modes.

**Handler:** `api/routers/config.py` | **Routing:** `cmd/server/main.go`

### GET /api/metrics

Returns catalog of all available weather metrics with format mode options and defaults.

**Response 200:**

```json
{
  "metrics": [
    {
      "id": "temperature",
      "name": "Temperature",
      "unit": "°C",
      "format_modes": ["raw"],
      "default_format_mode": "raw"
    },
    {
      "id": "wind_direction",
      "name": "Wind Direction",
      "unit": "degrees",
      "format_modes": ["raw", "scale"],
      "default_format_mode": "scale"
    },
    {
      "id": "cloud_total",
      "name": "Cloud Cover (Total)",
      "unit": "%",
      "format_modes": ["raw", "symbol"],
      "default_format_mode": "symbol"
    },
    {
      "id": "sunshine",
      "name": "Sunshine",
      "unit": "hours",
      "format_modes": ["raw", "symbol"],
      "default_format_mode": "symbol"
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| metrics[] | array | List of available metrics |
| metrics[].id | string | Metric identifier (e.g., `wind_direction`, `cloud_total`) |
| metrics[].name | string | Human-readable metric name |
| metrics[].unit | string | Unit of measurement |
| metrics[].format_modes | string[] | Supported format modes for this metric (`raw`, `scale`, `simplified`, `symbol`) |
| metrics[].default_format_mode | string | Recommended default format mode (must be in `format_modes`) |

**Format Mode Reference:**

| Mode | Description | Example Metrics |
|------|-------------|-----------------|
| `raw` | Numeric value with unit | `temperature: 18.5°C`, `wind: 22 km/h` |
| `scale` | Categorized scale representation | `wind_direction: N (345°)` as compass point |
| `simplified` | Adjective shorthand without value | `wind: schwach`, `precipitation: mäßig` |
| `symbol` | Emoji or icon representation | `cloud_total: ☁️`, `sunshine: ☀️` |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 503 | `{"error":"service_unavailable"}` | Metric catalog not initialized |

**Notes:**

- Frontend uses `format_modes` to filter dropdown options in Wizard Step 3 and WeatherConfigDialog
- `MetricConfig.format_mode` in persisted configs (e.g., `trips.json`, `locations.json`) refers to one of the values in the corresponding metric's `format_modes` array
- Legacy code may use `MetricConfig.use_friendly_format` (deprecated boolean) — loader automatically maps to `format_mode` for backward compatibility

---

## Changelog

- 2026-05-29: Added section 15 — Metric Catalog Endpoint (Issue #435): GET /api/metrics exposes `format_modes[]` and `default_format_mode` per metric for frontend UI filtering and backward-compatibility mapping.
- 2026-05-29: Issue #440 — Orts-Vergleich-Wizard Phase 1 — Extended CompareSubscription model with `activity_profile` (optional, validProfiles: wintersport|wandern|summer_trekking|allgemein). Frontend: CompareWizard Shell + Step 1 (Name/Region/Profile) + Step 2 (Smart-Import + Library). Stepper component made reusable via testidPrefix + onStepClick props. See `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md`.
- 2026-05-10: Epic #136 Trip-Wizard Master-Spec Fundament — Extended Trip model with `shortcode` and `activity` fields; Waypoint.suggested transient flag for wizard UI; Backend Trip.validateTrip() now accepts pause stages (waypoints: []). See `docs/specs/modules/epic_136_trip_wizard.md`.
- 2026-05-09: Added sections 12, 13, 14 — Scheduler Status, Forecast Query, Trip-Reports Trigger Endpoints (Epic #134). Support for dashboard briefing timeline, non-blocking client-side weather, and manual report trigger via API.
- 2026-04-14: Added section 11 — Weather Config Endpoints (M5c): 6 GET/PUT-Endpoints fuer display_config auf Trip, Location und Subscription als opaque JSON.
- 2026-04-14: Added section 10 — Subscriptions CRUD Endpoints (M5b): 5 REST-Endpoints fuer CompareSubscription, Single-File Storage, Validierung, Legacy-Migration.
- 2026-04-14: Added section 9 — GPX Proxy Endpoint (M5a): POST /api/gpx/parse, Go-to-Python Multipart Proxy, Stage+Waypoints Response DTO.
- 2026-02-18: Added `TripReportConfig.wind_exposition_min_elevation_m` (F7c Wind-Exposition Config) — per-trip configurable elevation threshold for wind exposition detection. Default null uses global 1500m threshold (lowered from 2000m).
