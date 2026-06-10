
# API Contract — Gregor Zwanzig

**Updated:** 2026-06-10 (Issue #715 — Wettermetriken-Darstellung: GET /api/metrics filtert auf `selectable=true` — `confidence` (Vorhersage-Verlässlichkeit/Ensemble) ist KEINE pro-Etappe wählbare Metrik mehr, nur noch Vorhersage-Hinweis + SMS-Symbol; Vorschau-Emojis in WeatherV2MailPreview + Step3Weather angepasst; Beispieldaten eindeutig gekennzeichnet; Bug #716 — Test-Briefing: stiller Versagensfall weg. POST /api/trips/{id}/send gibt jetzt HTTP 422 + detail-Feld zurück wenn keine Etappendaten für Zieldatum vorhanden (statt HTTP 200). Frontend zeigt konkrete Fehlermeldung im Toast; Issue #707 — Trip-Datum-Overwrite-Bug: PUT `/api/trips/{id}` mit minimalem Body (nur geänderte Felder) statt kompletter `trip`-Spread — verhindert stale-data-Überschreibung von Etappen; Issue #690 — Eigene Wetter-Metriken-Profile: eindeutiger Name (HTTP 409 name_exists, 400 name_required), Profil sofort aktiv + persistent, "Eigene"-Markierung in Preset-Leiste, trip-übergreifend pro Nutzer); 2026-06-09 (Issue #674 — Fahrradtour als Aktivitätstyp: 3 neue ActivityType-Varianten (fahrrad_15/20/25 km/h) mit korrekten Naismith-Raten (600/1000 Hm/h); #680 — Compare-Editor Slice 3 Fidelity: display_config.active_metrics — ausgewählte Metriken pro Vergleich; #675 — Etappen-Startzeiten editierbar; #671 — Bot-Menü automatisch beim Service-Start; #638 — Alerts-Tab Karten-Modell, Severity-Falle, pro-Alert Kanäle; #664 — Metriken-Überblick-Pille; #621 — E-Mail-Elemente abschaltbar); 2026-06-08 (Issues #672/#671 — Telegram E2E-Pipeline-Tests + Bot-Menü-Vertrag; #642 — User-Anzeigename display_name; #655 — Telegram Hybrid-Navigation: callback_query + editMessageText); 2026-06-07 (Issues #627/#631 — Compare-Preset Sofortversand + Wochen-Rhythmus-Erhalt)

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

#### Zusätzliche Felder (optional, aus Issue #497)
| Feld               | Typ              | Beschreibung                                   |
|--------------------|-----------------|------------------------------------------------|
| cloud_low_pct      | integer (0–100) | Tiefwolken-Anteil [%]                          |
| pop_pct            | integer (0–100) | Niederschlagswahrscheinlichkeit [%] (Duplikat deprecated — siehe pop_pct Basis-Feld) |
| wind_dir_deg       | integer (0–359) | Windrichtung [Grad]                            |

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
| show_stage_stats                | bool        | Etappen-Kennzahlen-Raster anzeigen? (default: true, Issue #621) |
| show_quick_take_tags            | bool        | Quick-Take-Chips in HTML anzeigen? (default: true, Issue #621) |
| show_stability                  | bool        | Großwetterlage-Label anzeigen? (default: true, Issue #621) |
| show_highlights                 | bool        | Highlights/Zusammenfassung anzeigen? (default: true, Issue #621) |
| daily_summary_metrics           | list[str]   | Metriken in der Tages-Summe (default: `["precipitation","wind","visibility","thunder"]`, Issue #621) |
| show_metrics_summary            | bool        | Optionaler Metriken-Überblick am Beginn (default: false, Issue #664) — wenn true: farbige Pillen pro konfigurierter Metrik; ersetzt Quick-Take und blendet Tages-Summe aus |
| updated_at                      | datetime    | Zeitpunkt der letzten Config-Änderung                  |

#### MetricConfig (Issue #435, erweitert Issue #624)
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
| sms_threshold       | float \| None    | **Neu Issue #624:** Schwellenwert für SMS-/Telegram-Kurzform (R/PR/W/G). None = Catalog/DEFAULTS-Fallback. Nur für threshold-fähige Metriken sichtbar (Niederschlag, Regenwahrscheinlichkeit, Wind, Böen) |

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

## 10.5) Trip Model and Activity Types (Issue #674)

Trip-Daten werden als JSON unter `data/users/{userID}/trips/{trip_id}.json` gespeichert. Das Kernmodell definiert Etappen, Wegpunkte und Konfiguration.

### Trip DTO

```go
type Trip struct {
    ID                      string                 `json:"id"`
    Name                    string                 `json:"name"`
    Stages                  []Stage                `json:"stages"`
    AvalancheRegions        []string               `json:"avalanche_regions,omitempty"`
    Aggregation             map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig           map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig           map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig            map[string]interface{} `json:"report_config,omitempty"`
    AlertRules              []AlertRule            `json:"alert_rules"`
    AlertCooldownMinutes    *int                   `json:"alert_cooldown_minutes,omitempty"`
    AlertQuietFrom          *string                `json:"alert_quiet_from,omitempty"`
    AlertQuietTo            *string                `json:"alert_quiet_to,omitempty"`
    Shortcode               string                 `json:"shortcode,omitempty"`
    Activity                string                 `json:"activity,omitempty"`
    Region                  string                 `json:"region,omitempty"`
    PausedAt                *time.Time             `json:"paused_at,omitempty"`
    ArchivedAt              *time.Time             `json:"archived_at,omitempty"`
}
```

### Activity Types (Issue #674)

Das Feld `activity` definiert die Art der Fortbewegung und damit die Geschwindigkeitsannahmen für Ankunftszeit-Berechnungen (Naismith-Formel).

| ActivityType | Flachgeschwindigkeit | Aufstieg [m/h] | Abstieg [m/h] | Verwendungsfall |
|---|---|---|---|---|
| `"trekking"` | 4.0 km/h | 300 | 500 | Standard-Wanderung (default) |
| `"skitour"` | 3.5 km/h | 250 | 400 | Skitour ohne Trails |
| `"hochtour"` | 3.0 km/h | 300 | 400 | Hochgebirgstouren mit Felsen/Schnee |
| `"klettersteig"` | 2.0 km/h | 150 | 200 | Klettersteig-Passagen |
| `"mtb"` | 4.0 km/h | 300 | 500 | Mountainbike (aktuell Wandertempo) |
| `"fahrrad_15"` | **15.0 km/h** | **600** | **1000** | Tourenrad, moderate Tempo (Issue #674) |
| `"fahrrad_20"` | **20.0 km/h** | **600** | **1000** | Tourenrad, zügig (Issue #674) |
| `"fahrrad_25"` | **25.0 km/h** | **600** | **1000** | Tourenrad, schnell (Issue #674) |

**Leeres oder unbekanntes Activity-Feld:** Fallback auf `"trekking"` (4.0 km/h, 300/500 m/h) für Backward Compatibility mit bestehenden Trips.

**Naismith-Formel:**
```
Fahrzeit [h] = Distanz [km] / FlatKmh + Aufstieg [m] / AscentMh + Abstieg [m] / DescentMh
```

**Höhenmeter-Begründung für Fahrradtypen:** Radfahrer überwinden Steigungen effizienter als Fußgänger (bessere Kraftübertragung, Schwungtechnik bei Abfahrten). Die 600/1000-Raten entsprechen der doppelten Geschwindigkeit von Wanderern (300/500).

### Stage DTO

```go
type Stage struct {
    ID                string       `json:"id"`
    Name              string       `json:"name"`
    Date              string       `json:"date"`        // YYYY-MM-DD
    StartTime         string       `json:"start_time,omitempty"` // HH:MM (Issue #675)
    Waypoints         []Waypoint   `json:"waypoints"`
    Distance          float64      `json:"distance_km"`
    Ascent            float64      `json:"ascent_m"`
    Descent           float64      `json:"descent_m"`
    DurationMinutes   *int         `json:"duration_minutes,omitempty"`
    ArrivalCalculated string       `json:"arrival_calculated,omitempty"` // HH:MM
}
```

### Waypoint DTO

```go
type Waypoint struct {
    ID                  string     `json:"id"`
    Name                string     `json:"name"`
    Lat                 float64    `json:"lat"`
    Lon                 float64    `json:"lon"`
    ElevationM          *float64   `json:"elevation_m,omitempty"`
    DistanceFromStartKm float64    `json:"distance_from_start_km"`
    ArrivalCalculated   string     `json:"arrival_calculated,omitempty"` // HH:MM (berechnet aus Activity)
}
```

**Berechnung `arrival_calculated`:**
- Frontend: `computeArrivalTimes(stage, startTime, activityToSpeed(trip.activity))` → gibt Array von HH:MM-Strings
- Backend (Go): `ComputeStageArrivals(stage, ActivitySpeed(trip.activity))` → mutiert Waypoints mit berechneter Zeit
- TypeScript: `function activityToSpeed(activity?: ActivityType): number` — 15/20/25 für Fahrrad, 4.0 default

**Beispiel (Fahrrad 20 km/h):**
```json
{
  "id": "w1",
  "name": "Alp Blenio",
  "lat": 46.45,
  "lon": 8.65,
  "elevation_m": 1500,
  "distance_from_start_km": 20,
  "arrival_calculated": "09:00"
}
```
Bei `start_time = "08:00"` und `activity = "fahrrad_20"`: 20 km ÷ 20 km/h = 1 h → 09:00 ✓

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

## 14.5) Manual Test-Briefing Send Endpoint (Issue #695, Bug #716)

Sends an immediate test briefing for a specific trip via the user's configured email.

**Handler:** `api/routers/scheduler.py` | **Route:** `POST /api/trips/{trip_id}/send`

### POST /api/trips/{trip_id}/send

Triggers immediate test briefing send for one trip. Returns success/failure based on whether stage data exists for the target date.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | `"default"` | User identifier (multi-tenant scoping) |
| `report_type` | string | `"evening"` | `"morning"` (today's stages) or `"evening"` (tomorrow's stages) |

**Response 200 (Success):**

```json
{
  "status": "ok",
  "trip_id": "gr20-2026",
  "report_type": "evening",
  "sent": true
}
```

**Error Responses:**

| Status | Scenario | Detail |
|--------|----------|--------|
| 404 | Trip `trip_id` not found for user | `"Trip {trip_id} not found"` |
| 422 | SMTP not configured for user (Issue #474) | `"SMTP not configured for this user"` |
| 422 | No stages for target date (Bug #716 — AC-1) | `"Kein Briefing für {report_type} — keine Etappendaten für das aktuelle Datum"` |
| 422 | Invalid `report_type` | `"Invalid report_type: {value}"` |

**Multi-Tenant Behavior:**
- `user_id` query parameter determines which user's data (trip, email config) is used
- Trip must exist in `data/users/{user_id}/trips/` directory
- Email sent to `settings.mail_to` for that user (set via `/api/auth/profile`)
- Default `user_id="default"` provided for backwards compatibility (e.g. test-mode without auth)

**Bug #716 Fix (2026-06-10):**
- Prior: silent failure (HTTP 200 even when no email sent) when stages missing for target date
- Now: explicit HTTP 422 with descriptive error message in `detail` field (AC-1)
- Frontend reads `detail` field and displays in error toast (AC-4, `frontend/src/routes/trips/[id]/+page.svelte`)

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
| metrics[] | array | List of available metrics (only selectable ones — meta-metrics like `confidence` are excluded) |
| metrics[].id | string | Metric identifier (e.g., `wind_direction`, `cloud_total`) |
| metrics[].name | string | Human-readable metric name |
| metrics[].unit | string | Unit of measurement |
| metrics[].format_modes | string[] | Supported format modes for this metric (`raw`, `scale`, `simplified`, `symbol`) |
| metrics[].default_format_mode | string | Recommended default format mode (must be in `format_modes`) |
| metrics[].selectable | bool | Whether this metric appears in the user-facing selector (Wizard/Editor). Backend internal metric (`confidence`) has `selectable=false` (Issue #710) — these are never returned by `/api/metrics` but used internally for aggregation/forecast-hints |

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
- **Confidence (`confidence`) is NOT a selectable per-stage weather metric** (Issue #710): Forecast reliability is a meta-attribute (Ensemble API, multi-day validity) and appears only as forecast-reliability hints in email/SMS output (e.g., "From Wednesday, forecast confidence is lower") and as SMS icon indicators. The metric definition exists internally for aggregation/scoring but is marked `selectable=false` and filtered from `/api/metrics` — **never appears in Trip Editor/Wizard/Metric Selector UI, even for legacy trips with saved `confidence` metric configs** (configs load silently, metric ignored in render paths). This rule (since 2026-06-10) prevents the metric from re-appearing across future versions.

---

## 15.5) MetricPreset CRUD Endpoints (Issue #690)

Manages persisted custom weather metric profiles (user's own presets for metric selection, format modes, and horizons).

**Handler:** `internal/handler/metric_preset.go` | **Storage:** `data/users/{userID}/metric_presets.json` | **Routing:** `cmd/server/main.go`

### MetricPreset DTO

```go
type MetricPreset struct {
    ID          string           `json:"id"`                      // "p-{hex}", auto-generated
    Name        string           `json:"name"`                    // User-chosen name, unique per user (case-insensitive, trimmed)
    Description string           `json:"description,omitempty"`   // Optional user notes
    IsDefault   bool             `json:"is_default"`              // Exactly one per user is marked as default
    Metrics     []DisplayMetric  `json:"metrics"`                 // List of selected metrics with horizons + format modes
    CreatedAt   time.Time        `json:"created_at"`              // Server-managed creation timestamp (UTC)
}
```

**DisplayMetric** (per-metric config within preset):

```go
type DisplayMetric struct {
    MetricID          string   `json:"metric_id"`            // e.g., "temperature", "wind_direction"
    Enabled           bool     `json:"enabled"`              // Include in preset
    UseFriendlyFormat bool     `json:"use_friendly_format"`  // Applies friendly format mode if available
    Horizons          Horizons `json:"horizons"`             // Which forecast days to show
}

type Horizons struct {
    Today     bool `json:"today"`
    Tomorrow  bool `json:"tomorrow"`
    DayAfter  bool `json:"day_after"`
}
```

### GET /api/metric-presets

Returns all metric presets for the authenticated user.

**Response 200:**

```json
{
  "presets": [
    {
      "id": "p-a1b2c3d4",
      "name": "Bergtour",
      "description": "Alpine with wind focus",
      "is_default": false,
      "metrics": [
        {
          "metric_id": "temperature",
          "enabled": true,
          "use_friendly_format": false,
          "horizons": {"today": true, "tomorrow": true, "day_after": false}
        },
        {
          "metric_id": "wind_direction",
          "enabled": true,
          "use_friendly_format": true,
          "horizons": {"today": true, "tomorrow": true, "day_after": true}
        }
      ],
      "created_at": "2026-06-10T14:32:45Z"
    }
  ]
}
```

**Notes:**
- Includes both built-in system presets (if exposed in future) and user's own custom presets
- User is identified from Auth-Context (user_id); presets from other users are never returned

### POST /api/metric-presets

Creates a new custom metric preset for the authenticated user.

**Request Body:**

```json
{
  "name": "Bergtour",
  "description": "Alpine with wind focus",
  "is_default": false,
  "metrics": [
    {
      "metric_id": "temperature",
      "enabled": true,
      "use_friendly_format": false,
      "horizons": {"today": true, "tomorrow": true, "day_after": false}
    },
    {
      "metric_id": "wind_direction",
      "enabled": true,
      "use_friendly_format": true,
      "horizons": {"today": true, "tomorrow": true, "day_after": true}
    }
  ],
  "friendly_ids": []
}
```

**Field Definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Preset name; must be unique per user (case-insensitive match, leading/trailing whitespace trimmed); max 100 chars |
| description | string | No | Optional user notes |
| is_default | boolean | Yes | If `true`, all other presets for this user are set to `is_default=false` (exactly one default per user) |
| metrics | array | Yes | List of metric configurations with horizons |
| friendly_ids | array | No | Legacy field (deprecated); ignored if `metrics` is properly structured |

**Response 201 (Created):**

```json
{
  "id": "p-a1b2c3d4",
  "name": "Bergtour",
  "description": "Alpine with wind focus",
  "is_default": false,
  "metrics": [...],
  "created_at": "2026-06-10T14:32:45Z"
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"name_required"}` | `name` is empty or contains only whitespace |
| 400 | `{"error":"bad_request"}` | Request body is malformed JSON |
| 409 | `{"error":"name_exists"}` | A preset with this name (case-insensitive) already exists for this user |
| 500 | `{"error":"store_error"}` | Internal storage error |

**Notes:**
- User ID is extracted from Auth-Context; no `user_id` field is accepted in the request
- Name is trimmed and case-insensitive for uniqueness comparison (Issue #690)
- Newly created preset becomes immediately active on the trip if workflow so directs (frontend responsibility)
- If `is_default=true` and multiple presets exist, server atomically ensures exactly one default

### DELETE /api/metric-presets/{id}

Deletes a metric preset (must belong to authenticated user).

**Response 204 (No Content):** Preset deleted successfully.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 404 | `{"error":"not_found"}` | Preset does not exist or belongs to a different user |
| 500 | `{"error":"store_error"}` | Internal storage error |

### PATCH /api/metric-presets/{id}

Updates selected fields of a metric preset (name, description, metrics, is_default).

**Request Body (partial update):**

```json
{
  "name": "Bergtour Updated",
  "description": "Alpine with focus on wind and precipitation",
  "metrics": [...]
}
```

**Response 200:**

```json
{
  "id": "p-a1b2c3d4",
  "name": "Bergtour Updated",
  ...
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"name_required"}` | Attempted to set name to empty/whitespace only |
| 404 | `{"error":"not_found"}` | Preset does not exist or belongs to a different user |
| 409 | `{"error":"name_exists"}` | New name already exists for this user (case-insensitive) |
| 500 | `{"error":"store_error"}` | Internal storage error |

---

## 16) ComparePreset CRUD Endpoints (Issue #458)

Manages persisted Compare-Preset configurations for automatic, multi-location comparison reports (foundation for Epic #456 — Auto-Briefings).

**Handler:** `internal/handler/compare_preset.go` | **Storage:** `data/users/{userID}/compare_presets.json` | **Routing:** `cmd/server/main.go`

### ComparePreset DTO

```go
type ComparePreset struct {
    ID                   string                 `json:"id"`                                    // "cp-{hex}", auto-generated
    Name                 string                 `json:"name"`
    UserID               string                 `json:"user_id"`                               // set from Auth-Context, server-managed
    LocationIDs          []string               `json:"location_ids"`                          // 2+ locations to compare
    Schedule             string                 `json:"schedule"`                              // "daily" | "weekly" | "manual"
    PreviousSchedule     string                 `json:"previous_schedule,omitempty"`           // schedule saved before pause (Issue #631, server-managed)
    Profil               string                 `json:"profil"`                                // ActivityProfile: WINTERSPORT|ALPINE_TOURING|SUMMER_TREKKING|ALLGEMEIN
    HourFrom             int                    `json:"hour_from"`                             // 0..23
    HourTo               int                    `json:"hour_to"`                               // 0..23, >= HourFrom
    Empfaenger           []string               `json:"empfaenger"`                            // Email addresses for delivery
    LetzterVersand       *time.Time             `json:"letzter_versand,omitempty"`             // last send timestamp (server-managed)
    TopOrtLetzterVersand *string                `json:"top_ort_letzter_versand,omitempty"`     // highest-ranked location from last send (server-managed)
    DisplayConfig        map[string]interface{} `json:"display_config,omitempty"`              // opaque config (Issue #680: active_metrics, ideal_ranges, etc.)
    CreatedAt            time.Time              `json:"created_at"`
}
```

**DisplayConfig Keys (Issue #680 onwards):**
- `active_metrics`: `[]string` — Ausgewählte Metrik-Keys für Vergleich (z.B. `["temp_max_c", "wind_max_kmh", "precip_sum_mm"]`). Default: Profil-spezifische Metriken aus `PROFILE_METRICS_WITH_SCALES`.
- `ideal_ranges`: `Record<string, IdealRange>` — Min/Max-Idealwerte pro Metrik (z.B. `{"temp_max_c": {"min": 15, "max": 35}, ...}`). Wird vom Compare-Engine zur Bewertung verwendet.
- `output_layout`: opaque (zukünftig) — Spalten-Reihenfolge, Formatierung per Kanal
- `schedule_config`: opaque (zukünftig) — Wiederholungs-Details

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/compare/presets` | 200 | List all presets for authenticated user ([] if none) |
| GET | `/api/compare/presets/{id}` | 200 / 404 | Get single preset by ID (for detail-page view, Issue #491) |
| POST | `/api/compare/presets` | 201 / 400 | Create new preset; ID auto-generated, user_id from auth context |
| PUT | `/api/compare/presets/{id}` | 200 / 400 / 404 | Update preset (user_id, created_at preserved from stored record) |
| DELETE | `/api/compare/presets/{id}` | 204 / 404 | Delete preset |
| POST | `/api/compare/presets/{id}/send` | 200 / 400 / 404 | Immediate send: executes comparison & emails all configured recipients regardless of schedule (Issue #627); ignores `schedule='manual'` |

### Validation Rules (POST/PUT)

| Field | Constraint |
|-------|-----------|
| `name` | not empty |
| `schedule` | in `{"daily", "weekly", "manual"}` |
| `profil` | valid per `internal/compare/types.go` IsValidProfile() |
| `hour_from` | 0–23 |
| `hour_to` | 0–23 |
| — | `hour_to >= hour_from` |
| `empfaenger[]` | each contains `@` (basic email check) |

### Error Responses

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"validation_error","detail":"..."}` | Validation failed (see above) |
| 400 | `{"error":"bad_request"}` | JSON not decodable |
| 404 | `{"error":"not_found"}` | ID not found in user's preset list |

### Notes

- **User Isolation:** Every preset belongs to one user (read from Auth-Context). No user can see/modify another user's presets.
- **Server-Managed Fields:** On CREATE, `id` is auto-generated (`cp-{hex}`) and `user_id` is set from context. On UPDATE, `user_id` and `created_at` are never overwritten from request body. `letzter_versand`, `top_ort_letzter_versand`, and `previous_schedule` are server-managed (not client-writable).
- **display_config (Issue #680):** Opaque JSON object stored as `map[string]interface{}` (no server-side schema validation). Contains `active_metrics` (persisted Metrik-Auswahl), `ideal_ranges` (Bewertungs-Schwellwerte), und zukünftig `output_layout` + `schedule_config`. Round-Trip beim Update: Server gibt `display_config` unverändert zurück, Frontend reicht nur geänderte Felder. Bestandsfelder erhalten sich automatisch (RMW-Semantik).
- **POST /api/compare/presets/{id}/send:** Immediate send endpoint (Issue #627). Executes comparison engine and emails all configured `empfaenger` immediately, regardless of `schedule` value (bypasses time-based gating). If no recipients configured, returns HTTP 400. Returns HTTP 200 with `{"status":"ok","winner":"<top_location>","empfaenger_count":N}` on success. Updates `letzter_versand` and `top_ort_letzter_versand` server-side.
- **previous_schedule Field (Issue #631):** When a preset is paused (`schedule='manual'`), the frontend sets `previous_schedule` to the prior schedule value (`"daily"` or `"weekly"`). On reactivation, `schedule` is restored from `previous_schedule`. This field is preserved across reloads (backend-persistent); altdata without this field remain unaffected (omitempty).
- **LocationIDs Validation:** Backend does not validate that referenced location IDs exist in `data/users/{userID}/locations.json`. Invalid IDs cause errors only during send.

### Source Files

| File | Change |
|------|--------|
| `internal/model/compare_preset.go` | NEW — ComparePreset struct |
| `internal/store/store.go` | +LoadComparePresets(), SaveComparePresets(), comparePresetsFile() |
| `internal/handler/compare_preset.go` | NEW — 5 handlers + newComparePresetID(), validateComparePreset() |
| `cmd/server/main.go` | +5 route registrations |

---

## 17) Google OAuth Login Endpoints (Issue #425)

**Handler:** `internal/handler/auth_oauth.go` (NEW) | **Routing:** `cmd/server/main.go`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/auth/google/init` | 302 / 501 | Initiate Google OAuth flow (redirects to Google consent screen) |
| GET | `/api/auth/google/callback` | 302 / 400 | Handle Google OAuth callback (exchanges code for session) |

### GET /api/auth/google/init

Initiates the Google OAuth 2.0 Authorization Code flow.

**Prerequisites:**
- `GZ_GOOGLE_CLIENT_ID` must be configured (non-empty)

**Behavior:**

1. Generate random 16-byte state token (hex-encoded)
2. Set `gz_oauth_state` cookie (HttpOnly, SameSite=Lax, MaxAge=600s, Secure on HTTPS only)
3. Redirect to Google OAuth consent URL with scopes `openid email profile`

**Response:**

| Status | Behavior |
|--------|----------|
| 302 | Redirect to `https://accounts.google.com/o/oauth2/v2/auth?...state=<token>...` |
| 501 | Not Implemented — feature disabled (`GZ_GOOGLE_CLIENT_ID` not set) |

**Error Cases:**

- Config not loaded: HTTP 501
- `GZ_GOOGLE_CLIENT_ID` empty: HTTP 501

### GET /api/auth/google/callback

Handles the OAuth callback from Google. Exchanges authorization code for ID token, verifies the user, and issues a session.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | yes | OAuth authorization code from Google |
| state | string | yes | CSRF protection token (must match cookie) |

**Behavior:**

1. Read `gz_oauth_state` cookie; validate against `state` query param (constant-time comparison)
2. Delete `gz_oauth_state` cookie (MaxAge=-1)
3. Exchange `code` for ID token via `oauth2.Exchange()`
4. Fetch user info from `https://www.googleapis.com/oauth2/v3/userinfo`
5. Validate `email_verified: true` in userinfo
6. Lookup user by `OAuthProvider: "google"` + `OAuthSub: sub`
   - **Found:** Issue `gz_session` cookie, redirect to `/`
   - **Not Found:** Generate new User-ID (`g-{8hex}`), create new user, issue `gz_session` cookie, redirect to `/`
7. On any error: Redirect to `/login?error=oauth_failed` (no stack traces exposed)

**Response:**

| Status | Behavior |
|--------|----------|
| 302 | Redirect to `/` (success) or `/login?error=oauth_failed` (failure) |
| 400 | Invalid query parameters or malformed request |

**Error Cases:**

| Scenario | Response |
|----------|----------|
| State mismatch (CSRF attempt) | 302 to `/login?error=oauth_failed` |
| `email_verified: false` | 302 to `/login?error=oauth_failed` |
| Google userinfo endpoint unavailable | 302 to `/login?error=oauth_failed` |
| ID collision after 3 generation attempts | 302 to `/login?error=oauth_failed` |
| Network error during token exchange | 302 to `/login?error=oauth_failed` |

**Side Effects:**

- New `data/users/g-{8hex}/user.json` created for first-time Google users
- Session cookie `gz_session` set with 7-day expiry
- Existing users with matching `oauth_sub` skip creation and reuse their account

### User Data Model (Modified)

**`internal/model/user.go`:**

```go
type User struct {
    // ... existing fields ...
    OAuthProvider string `json:"oauth_provider,omitempty"`
    OAuthSub      string `json:"oauth_sub,omitempty"`
}
```

- `OAuthProvider`: OAuth provider name (e.g., `"google"`)
- `OAuthSub`: OAuth subject claim (unique ID from provider)
- Fields optional (omitempty) for backward compatibility with password-auth users

### Config Parameters

**Environment Variables:**

| Var | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| GZ_GOOGLE_CLIENT_ID | string | no | (unset) | Google OAuth 2.0 Client ID |
| GZ_GOOGLE_CLIENT_SECRET | string | no | (unset) | Google OAuth 2.0 Client Secret |
| GZ_GOOGLE_REDIRECT_URL | string | no | (unset) | Callback URL (e.g., `https://gregor20.henemm.com/api/auth/google/callback`) |

**Feature Gate:**
- If `GZ_GOOGLE_CLIENT_ID` is empty or unset:
  - Frontend buttons hidden (`data.googleEnabled = false`)
  - `/api/auth/google/init` returns HTTP 501
  - Google login is disabled

### Frontend Integration

**Login/Registration Pages:**
- `frontend/src/routes/login/+page.server.ts` — exposes `data.googleEnabled` flag
- `frontend/src/routes/register/+page.server.ts` — exposes `data.googleEnabled` flag
- Conditional button: `{#if data.googleEnabled} <a href="/api/auth/google/init">Mit Google anmelden</a> {/if}`

### Session Handling

Google OAuth users receive the same session mechanism as password-auth users:
- Cookie: `gz_session` (format: `{userId}.{timestamp}.{sig}`)
- User-ID format for OAuth users: `g-{8hex}` (no dots to prevent session parsing errors)
- Session verification: `frontend/src/lib/auth.ts` → `verifySession()` handles split defensively

---

## 17) Compare-Preset Model (Issue #458)

Das neue `ComparePreset`-Datenmodell für Auto-Briefings (Orts-Vergleiche) mit CRUD-Endpoints.

### ComparePreset Structure

```json
{
  "id": "cp-a1b2c3d4e5f6g7h8",
  "name": "Alpenvergleich",
  "user_id": "alice@example.com",
  "location_ids": ["loc-001", "loc-002", "loc-003"],
  "schedule": "daily",
  "profil": "WINTERSPORT",
  "hour_from": 6,
  "hour_to": 8,
  "empfaenger": ["alice@example.com", "bob@example.com"],
  "letzter_versand": "2026-05-29T07:00:00Z",
  "top_ort_letzter_versand": "Andermatt",
  "created_at": "2026-05-20T14:30:00Z"
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | string | Eindeutige ID (`cp-{8hex}`) |
| name | string | Benutzer-definierter Name |
| user_id | string | Besitzer-User-ID |
| location_ids | string[] | 1–5 Orts-IDs zum Vergleichen |
| schedule | enum | `"daily"` \| `"weekly"` \| `"manual"` |
| profil | enum | `"WINTERSPORT"` \| `"ALPINE_TOURING"` \| `"SUMMER_TREKKING"` \| `"ALLGEMEIN"` |
| hour_from | integer | Start-Stunde [0..23] für tägliche Versände |
| hour_to | integer | End-Stunde [0..23] |
| empfaenger | string[] | E-Mail-Adressen (Validierung: muss `@` enthalten) |
| letzter_versand | datetime \| null | ISO-8601 UTC des letzten Versands |
| top_ort_letzter_versand | string \| null | Ort mit höchstem Score beim letzten Versand |
| created_at | datetime | Erstellungszeitpunkt (ISO-8601 UTC) |

### Endpoints

| Method | Path | Verhalten |
|--------|------|-----------|
| `GET` | `/api/compare/presets` | Alle Presets des eingeloggten Users; `[]` falls keine |
| `POST` | `/api/compare/presets` | Neues Preset anlegen → `201 Created` + Preset-JSON |
| `PUT` | `/api/compare/presets/{id}` | Preset komplett aktualisieren → `200 OK` + Preset-JSON |
| `DELETE` | `/api/compare/presets/{id}` | Preset löschen → `204 No Content`; `404` falls nicht gefunden |
| `POST` | `/api/compare/presets/{id}/send` | Versand triggern (Stub: `{"status":"queued"}` mit `200`) — echte Versand-Logik folgt #461 |

### Validierung

- `name`: erforderlich, nicht leer
- `schedule`: einer von `["daily", "weekly", "manual"]`
- `profil`: einer von `["WINTERSPORT", "ALPINE_TOURING", "SUMMER_TREKKING", "ALLGEMEIN"]`
- `hour_from`, `hour_to`: Integers in [0..23], `hour_from <= hour_to`
- `empfaenger`: Array von Strings mit mindestens `@`-Zeichen (einfache Email-Validierung)
- `location_ids`: Array (leer erlaubt, aber mind. 1 Ort bei Versand sinnvoll)

### User-Isolation

Alle Endpoints filtern nach dem eingeloggten User (via `middleware.UserIDFromContext()`). Queries auf fremde Presets (`user_id ≠ authenticated user`) werden ignoriert/404.

---

## 17) Compare-Presets Daily Dispatch Endpoint (Issue #461)

Automatically dispatches daily Compare-Presets at 06:00 UTC (Vienna time). Triggered by Go scheduler; Python endpoint filters presets by `schedule='daily'`, runs Compare Engine, sends emails, and updates preset status fields.

**Handler:** `api/routers/scheduler.py` | **Routing:** `cmd/server/main.go`

### POST /api/scheduler/compare-presets-daily

Processes all daily Compare-Presets for a user: filters by `schedule='daily'`, runs Compare Engine, renders/sends emails, updates `letzter_versand` and `top_ort_letzter_versand`.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | no | User identifier (default: "default" for V1) |

**Response 200:**

```json
{
  "status": "ok",
  "count": 2
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| status | enum | Always `"ok"` (endpoint succeeds even if individual presets fail) |
| count | int | Number of `schedule='daily'` presets processed (not error count) |

**Internal Behavior:**

1. Load `data/users/{user_id}/compare_presets.json` as direct JSON array `[...]`
2. Filter: only `preset["schedule"] == "daily"`
3. For each matching preset:
   - Validate `location_ids` (warn if empty, increment `error_count`)
   - Convert `preset["profil"]` (Uppercase Go string → lowercase Python enum, fallback ALLGEMEIN)
   - Call Compare Engine with `target_date=today`, `forecast_hours=48`, `hour_from`, `hour_to`, `activity_profile`
   - Render Compare-Email template
   - Send via Resend to all `preset["empfaenger"]`
   - Call `_save_preset_status(user_id, preset_id, top_ort)` to update JSON
   - On any error: log warning, increment `error_count`, continue (no job abort)
4. Go scheduler pings BetterStack Heartbeat (`GZ_HEARTBEAT_COMPARE_PRESETS`) only if `error_count == 0` (operator-visible success indicator)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 200 | `{"status":"ok","count":0}` | No daily presets found (not an error) |
| 200 | `{"status":"ok","count":2}` | 2 presets processed; some may have had per-item errors but HTTP 200 always |

**Side Effects:**

- `data/users/{user_id}/compare_presets.json` updated with `letzter_versand` (ISO-datetime UTC) and `top_ort_letzter_versand` (string or null) for each successfully sent preset
- Email sent to all recipients in `preset["empfaenger"]`
- Log entries on WARNING for each failed preset

**Notes:**

- Endpoint always returns HTTP 200 regardless of `error_count` (job success tracked by Go scheduler via `recordRun()`)
- Python-side heartbeat ping (`GZ_HEARTBEAT_COMPARE_PRESETS` ENV) is not called by Python; Go scheduler handles this via `pingHeartbeat()` on the full job result
- BetterStack Heartbeat is pinged only when `error_count == 0` — any preset-level error blocks the ping (Readiness Principle)

---

## 18) Compare-Preset Immediate Send (Issue #627)

On-demand send for a single Compare-Preset: triggers comparison engine and emails all configured recipients immediately, bypassing schedule-based gating.

**Handler:** `api/routers/scheduler.py` (Python endpoint) | `internal/handler/compare_preset.go` (Go proxy) | **Routing:** `cmd/server/main.go`

### POST /api/scheduler/compare-presets/{id}/send

Executes comparison and sends report for a single preset immediately (regardless of `schedule` value).

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | yes (via appendUserID) | User identifier (appended by Go proxy; anti-spoofing via Auth-Context) |

**Response 200 (Success):**

```json
{
  "status": "ok",
  "winner": "Säntis",
  "empfaenger_count": 2
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| status | enum | `"ok"` on success |
| winner | string | Highest-ranked location name from comparison |
| empfaenger_count | int | Number of recipients the email was sent to |

**Behavior:**

1. Go proxy (`SendComparePresetHandler`) extracts `{id}` from URL, appends `user_id` from Auth-Context to query string
2. Proxy forwards POST to Python endpoint: `/api/scheduler/compare-presets/{id}/send?user_id=...`
3. Python endpoint:
   - Loads `data/users/{user_id}/compare_presets.json`
   - Finds preset by `id` (404 if not found)
   - Validates `empfaenger[]` exists and is non-empty; falls back to `mail_to` from user profile (400 if neither)
   - Calls Compare Engine with `target_date=today`, `forecast_hours=48` (uses preset's `hour_from`, `hour_to`, `profil`)
   - Renders Compare-Email template and sends via Resend to all recipients
   - Updates `letzter_versand` (current ISO-datetime UTC) and `top_ort_letzter_versand` (winner) in preset
   - Returns HTTP 200 with winner and recipient count

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"no_recipients"}` | No `empfaenger` configured and no user `mail_to` fallback |
| 404 | `{"error":"not_found"}` | Preset ID not found in user's preset list |
| 500 | `{"error":"send_failed","detail":"..."}` | Email dispatch failed (network/Resend error) |

**Side Effects:**

- Email sent to all recipients in `preset["empfaenger"]` (or user's `mail_to` fallback)
- `data/users/{user_id}/compare_presets.json` updated with `letzter_versand` (ISO-datetime) and `top_ort_letzter_versand` (location name)
- No effect on `schedule` — paused presets (`schedule='manual'`) can still be sent immediately

**Notes:**

- Ignores `schedule` value entirely (sends even if `schedule='manual'` or `'weekly'`)
- User isolation enforced via Go proxy's `appendUserID()` function — client cannot spoof another user's `user_id`
- Idempotent for recipients (same email list re-sent on retry), but updates `letzter_versand` each time

---

## 19) Authentication Endpoints (Session + Passkey)

**Scope:** User registration, password-based login, and FIDO2 passkey-based authentication.

**Handler:** `internal/handler/auth.go` | **Middleware:** `internal/middleware/auth.go` | **Routing:** `cmd/server/main.go`

### A) Password-based Authentication

#### POST /api/auth/register

User registration with username + password (HTTP 201 on success, 409 if user exists).

**Request Body:**
```json
{"username": "alice", "password": "geheim123"}
```

**Response 201:**
```json
{"id": "alice"}
```

**Validation:**
- `username`: 3–50 characters, alphanumeric + underscore
- `password`: ≥8 characters

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"validation_error","detail":"..."}` | username/password missing or too short |
| 409 | `{"error":"user_already_exists"}` | User with this ID already registered |

#### POST /api/auth/login

User login with username + password, returns session cookie.

**Request Body:**
```json
{"username": "alice", "password": "geheim123"}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure` (Secure flag active on HTTPS)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"bad_request"}` | JSON malformed |
| 401 | `{"error":"invalid_credentials"}` | User not found or password incorrect (same message for both) |

### B) Passkey Authentication (WebAuthn/FIDO2)

**Issue #450** — Add WebAuthn (Face ID, Touch ID, Windows Hello, etc.) as alternative auth method alongside password. V1 is add-on (existing users keep passwords).

**Issue #467** — Discoverable credentials (login without username) via Conditional UI. Browser shows Passkeys as native autofill suggestions on username field focus (`mediation: 'conditional'`).

**Key Configuration:**
- **RP-ID (Relying Party):** Prod `gregor20.henemm.com`, Staging `staging.gregor20.henemm.com` (isolated)
- **Rate-Limit:** 30 requests/hour per IP (all 7 endpoints)
- **Body-Size-Cap:** 64 KB (`http.MaxBytesReader`)
- **Challenge-TTL:** 5 minutes (in-memory store with garbage collection)

#### POST /api/auth/passkey/discoverable/begin

Initiate discoverable passkey login (no username required, public endpoint). Browser shows registered passkeys as native autofill suggestions on username field focus.

**Request Body:** `{}` (empty)

**Response 200:**
```json
{
  "mediation": "conditional",
  "publicKey": {
    "challenge": "<base64url-string>",
    "timeout": 300000,
    "rpId": "gregor20.henemm.com",
    "userVerification": "preferred"
  }
}
```

**Key Difference from V1 Login:** Top-level includes `"mediation":"conditional"` (required for browser to show autofill picker). No `allowCredentials` array (browser discovers all passkeys for this RP-ID).

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |
| 500 | `{"error":"begin_failed"}` | WebAuthn library error (rare) |

#### POST /api/auth/passkey/discoverable/finish

Complete discoverable passkey login. Browser provides `userHandle` from stored credential; backend looks up user by `userHandle`.

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "authenticatorData": "<base64url-data>",
    "signature": "<base64url-sig>",
    "userHandle": "<base64url-userId>"
  },
  "type": "public-key"
}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure`
- Updates `last_used_at` timestamp on the used credential
- Increments `sign_count` on the credential (cloning detection)
- ChallengeStore entry is destroyed after successful `Take()` (replay protection)

**Implementation Note:** Backend calls `DiscoverableUserHandler` callback with `userHandle` ([] byte) from response to load user by ID. User lookup fails if `userHandle` is empty or user does not exist.

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | Challenge invalid, expired (5 min), signature verification failed, user handle empty/invalid, or user not found |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/register/begin

Initiate passkey registration (requires valid session cookie).

**Request Body:** `{}` (empty)

**Response 200:**
```json
{
  "publicKey": {
    "challenge": "<base64url-string>",
    "rp": {
      "name": "Gregor Zwanzig",
      "id": "gregor20.henemm.com"
    },
    "user": {
      "id": "<base64url-userId>",
      "name": "<userId>",
      "displayName": "<userId>"
    },
    "pubKeyCredParams": [
      {"type": "public-key", "alg": -7},
      {"type": "public-key", "alg": -257}
    ],
    "timeout": 300000,
    "attestation": "direct",
    "authenticatorSelection": {
      "authenticatorAttachment": "platform",
      "residentKey": "preferred",
      "userVerification": "preferred"
    }
  }
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/register/finish

Complete passkey registration (requires valid session cookie, challenge from `register/begin`).

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "attestationObject": "<base64url-object>"
  },
  "type": "public-key",
  "label": "MacBook"  // optional: user-provided device name
}
```

**Response 201:**
```json
{
  "id": "<base64url-credentialId>",
  "label": "MacBook",
  "created_at": "2026-05-30T12:00:00Z"
}
```

**Side Effects:**
- `user.json` updated with new entry in `passkey_credentials[]` array
- Profile endpoint now returns `"has_passkey": true`

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"challenge_expired_or_missing"}` | Challenge not in store or expired (5 min timeout) |
| 400 | `{"error":"attestation_invalid"}` | WebAuthn library signature/attestation verification failed |
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/login/begin

Initiate passkey login (public, no auth required).

**Request Body:**
```json
{"username": "alice"}
```

**Response 200:**
```json
{
  "publicKey": {
    "challenge": "<base64url-string>",
    "timeout": 300000,
    "rpId": "gregor20.henemm.com",
    "allowCredentials": [
      {
        "type": "public-key",
        "id": "<base64url-credentialId-1>",
        "transports": ["platform", "usb"]
      }
    ],
    "userVerification": "preferred"
  }
}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | User not found or has no passkeys |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### POST /api/auth/passkey/login/finish

Complete passkey login (public, no auth required).

**Request Body:**
```json
{
  "id": "<base64url-credentialId>",
  "rawId": "<base64url-raw>",
  "response": {
    "clientDataJSON": "<base64url-json>",
    "authenticatorData": "<base64url-data>",
    "signature": "<base64url-sig>"
  },
  "type": "public-key"
}
```

**Response 200:**
```json
{"id": "alice"}
```

**Side Effects:**
- Sets `Set-Cookie: gz_session=<userId>.<timestamp>.<hmacSig>; HttpOnly; SameSite=Lax; MaxAge=86400; Secure`
- Updates `last_used_at` timestamp on the used credential
- Increments `sign_count` on the credential (cloning detection)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | `{"error":"invalid_credentials"}` | Challenge invalid, expired (5 min), signature verification failed, or user deleted |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

#### DELETE /api/auth/passkey/credentials/{id}

Remove a registered passkey (requires valid session cookie).

**Path Parameter:**
- `id`: Base64URL-encoded credential ID

**Response 200:**
```json
{"status": "deleted"}
```

**Validation & Safety:**
- Returns 400 if user has no password hash AND this is their only credential (lock-out prevention)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"cannot_remove_last_passkey_without_password"}` | User would be locked out (no password, last passkey) |
| 401 | (via `AuthMiddleware`) | No valid session cookie |
| 404 | `{"error":"not_found"}` | Credential ID not found in user's list |
| 429 | `{"error":"rate_limit_exceeded"}` with `Retry-After` header | Too many requests from this IP |

### C) Profile & Session Status

#### GET /api/auth/profile

Returns authenticated user profile (requires valid session cookie).

**Response 200:**
```json
{
  "id": "alice",
  "display_name": "Alice Schmidt",
  "email": "alice@example.com",
  "mail_to": "alice@example.com",
  "sms_to": "+49151XXXXXXXX",
  "has_passkey": true,
  "passkeys": [
    {
      "id": "<base64url-credentialId>",
      "label": "MacBook",
      "authenticator_name": "iCloud Keychain",
      "created_at": "2026-05-30T12:00:00Z",
      "last_used_at": "2026-05-30T15:30:00Z"
    },
    {
      "id": "<base64url-credentialId-2>",
      "label": "iPhone",
      "authenticator_name": "Windows Hello",
      "created_at": "2026-05-25T10:00:00Z",
      "last_used_at": "2026-05-29T08:15:00Z"
    }
  ]
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| id | string | User identifier (immutable; also used as fallback display if `display_name` empty) |
| display_name | string | User's chosen display name (optional, max 50 chars); shown in UI instead of `id` if set; null/empty if not configured |
| email | string | Email address (for display only) |
| mail_to | string | Email recipient for trip reports (can differ from email) |
| sms_to | string | SMS recipient phone number (international format, e.g. `+49151XXXXXXXX`); empty if not configured |
| has_passkey | bool | Whether user has registered any passkeys |
| passkeys | array | List of registered WebAuthn credentials (empty if `has_passkey=false`) |

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

#### PUT /api/auth/profile

Update authenticated user profile (requires valid session cookie).

**Request Body:**
```json
{
  "display_name": "Alice S.",
  "mail_to": "alice+briefings@example.com",
  "sms_to": "+49151XXXXXXXX"
}
```

**Response 200:**
Returns updated profile object (same as `GET /api/auth/profile`).

**Validation:**
- `display_name`: Optional, max 50 characters; trimmed (leading/trailing whitespace removed); empty or whitespace-only strings unset the field (reverts to fallback: `id`)
- `mail_to`: Optional, any non-empty string (no format validation)
- `sms_to`: Optional, any non-empty string (no format validation; validation happens during send via SMS provider)
- Empty strings allowed (unset field)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"bad_request"}` | JSON not decodable |
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

### User Model Extensions

**File:** `internal/model/user.go`

```go
type User struct {
    ID                 string                 `json:"id"`
    DisplayName        string                 `json:"display_name,omitempty"`  // NEW (Issue #642) — user's chosen display name; omitempty if not set
    Email              string                 `json:"email,omitempty"`
    PasswordHash       string                 `json:"password_hash,omitempty"`  // now optional (omitempty)
    PasskeyCredentials []WebAuthnCredential   `json:"passkey_credentials,omitempty"`  // NEW (Issue #450)
    CreatedAt          time.Time              `json:"created_at"`
    MailTo             string                 `json:"mail_to,omitempty"`
    SmsTo              string                 `json:"sms_to,omitempty"`  // NEW (Issue #609) — SMS recipient phone number
    SignalPhone        string                 `json:"signal_phone,omitempty"`
    SignalAPIKey       string                 `json:"signal_api_key,omitempty"`
    TelegramChatID     string                 `json:"telegram_chat_id,omitempty"`
}

type WebAuthnCredential struct {
    ID              []byte                `json:"id"`                  // Credential-ID (raw bytes)
    PublicKey       []byte                `json:"public_key"`          // COSE-encoded
    AttestationType string                `json:"attestation_type"`
    Transport       []string              `json:"transport,omitempty"`
    Flags           webauthn.CredentialFlags `json:"flags"`
    Authenticator   webauthn.Authenticator   `json:"authenticator"`    // AAGUID, SignCount, CloneWarning
    CreatedAt       time.Time             `json:"created_at"`
    LastUsedAt      time.Time             `json:"last_used_at,omitempty"`
    Label           string                `json:"label,omitempty"`    // User-provided device name
}
```

**Backward Compatibility:**
- Existing `user.json` files without `passkey_credentials` field deserialize cleanly (`nil` slice maps to empty list)
- `PasswordHash` field now optional; existing users retain their password hash
- Profile endpoint includes `has_passkey` boolean and `passkeys[]` array (excludes `public_key` and raw crypto fields)
- Passkey profile entry may include optional `authenticator_name` field (Issue #468 — resolved AAGUID mappings; missing if AAGUID unknown or zero)

---

## 20) Preview Endpoints (Issue #189, #483)

Provides preview rendering of trip reports in Email, SMS, Signal, or Telegram formats. Supports both live weather and fixture-based demo mode.

**Handler:** `api/routers/preview.py` | **Routing:** `cmd/server/main.go`

### GET /api/preview/{trip_id}/email

Render trip report preview in HTML format (Email).

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| type | enum | no | Report type: `morning` or `evening` (default: `morning`) |
| date | string | no | Target date ISO-8601 (default: today, format: `YYYY-MM-DD`) |
| demo | boolean | no | Use fixture data instead of live weather (default: `false`, Issue #483) |

**Response 200:**

```
Content-Type: text/html
<html>...</html>  <!-- Full HTML rendered trip report -->
```

**Example:**
```
GET /api/preview/gr20/email?type=morning&date=2026-05-31&demo=1
GET /api/preview/gr20/email?type=evening
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid_trip_or_date"}` | Trip not found or date unparseable |
| 400 | `{"error":"invalid_type"}` | `type` parameter not in `["morning", "evening"]` |
| 400 | `{"error":"no_segments"}` | Trip has no stages/segments for the given date |
| 503 | `{"error":"weather_unavailable"}` | Weather provider API unreachable (only when `demo=false`) |

**Notes:**

- `demo=1` (or any truthy value) enables fixture-based demo mode (Issue #483): FixtureProvider loads predefined weather data from `fixtures/openmeteo/` instead of calling live APIs
- `demo=0` or absent: live weather via configured provider (GEOSPHERE, MET, etc.)
- If weather fetch fails with `demo=false`, the endpoint returns 503; with `demo=true`, it returns 400 if fixtures are unavailable
- Demo mode is ideal for testing preview rendering on past trips (where live weather is unavailable)

### GET /api/preview/{trip_id}/sms

Render trip report preview as SMS text (≤160 characters per message).

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```
Content-Type: text/plain
Grüße! Morgen: 18°C, Wind 22 km/h, Regenwahrscheinlichkeit 20%.
```

**Error Responses:** Same as `/email`

### GET /api/preview/{trip_id}/signal

Render trip report preview for Signal channel.

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```
Content-Type: text/plain
<Signal-formatted message>
```

**Error Responses:** Same as `/email`

### GET /api/preview/{trip_id}/telegram

Render trip report preview for Telegram channel.

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```
Content-Type: text/plain
<Telegram-formatted message (may include markdown or HTML)>
```

**Error Responses:** Same as `/email`

**Notes:**

- All preview endpoints are **read-only** and do not send messages or modify state
- Preview rendering uses the same Report Formatter and Channel Renderers as the scheduler (integrity guarantee)
- Frontend may call multiple preview endpoints (e.g., email + SMS) to render side-by-side tabs

---

---

## 21) Briefing History Endpoint (Issue #559)

Lists all sent briefings (morning/evening) for an archived trip, ordered chronologically.

**Handler:** `internal/handler/briefing_history.go` | **Routing:** `cmd/server/main.go`

### GET /api/trips/{id}/briefing-history

Retrieves briefing delivery log for a specific trip (archived or active).

**Path Parameter:**
- `id`: Trip identifier

**Response 200:**

```json
[
  {
    "sent_at": "2026-06-01T07:00:00Z",
    "kind": "morning",
    "channels": ["email"]
  },
  {
    "sent_at": "2026-06-01T18:15:00Z",
    "kind": "evening",
    "channels": ["email"]
  }
]
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| sent_at | datetime | ISO-8601 UTC timestamp of briefing send |
| kind | enum | Briefing type: `"morning"` or `"evening"` |
| channels | string[] | Delivery channels used (e.g., `["email"]`, `["email", "signal"]`) |

**Failure Modes:**

- Trip not found or no briefing log: returns empty array `[]` (fail-soft, Issue #559 AC-4)
- Missing log file on disk: returns `[]` (never 500 error)
- Unauthorized (no session): HTTP 401

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 401 | (via `AuthMiddleware`) | No valid session cookie |

**Notes:**

- Endpoint is read-only; designed for archive page "Briefing-Verlauf" modal (Issue #559 AC-1)
- Order: chronological ascending (oldest first)
- Returns `[]` if trip ID matches no entries (no 404 distinction for missing logs vs. no entries)

---

## 22) Alert Rules (Issue #638)

**Alerts-Tab Redesign: Karten-Modell, Severity-Falle beseitigen, pro-Alert Kanäle**

Alerts sind personalisierbare Benachrichtigungen bei Wetteränderungen auf einem Trip. Jeder Alert hat eine Metrik (z.B. Wind-Böen), einen Schwellenwert, und wird jetzt mit eigenen Kanälen versandt (vorbelegt aus Briefing-Kanälen).

### AlertRule DTO

```go
// internal/model/trip.go (Go)
type AlertRule struct {
    ID       string   `json:"id"`
    Kind     string   `json:"kind"`           // "absolute" | "delta"
    Metric   string   `json:"metric"`         // WIND_GUST, PRECIPITATION_SUM, ...
    Threshold float64 `json:"threshold"`
    Severity string   `json:"severity"`       // "info", "warning", "critical" (Label nur; nicht mehr für Versand-Entscheidung)
    Enabled  bool     `json:"enabled"`
    Unit     string   `json:"unit,omitempty"`
    Channels []string `json:"channels,omitempty"` // NEW: pro-Alert Kanal-Override (empty = erbe Briefing-Kanäle)
}
```

```python
# src/app/models.py (Python)
@dataclass
class AlertRule:
    id: str
    kind: AlertRuleKind         # ABSOLUTE | DELTA
    metric: AlertMetric         # WIND_GUST, PRECIPITATION_SUM, etc.
    threshold: float
    severity: AlertSeverity     # INFO | WARNING | CRITICAL (Label only; not used for send decision)
    enabled: bool
    unit: str = ""
    channels: list[str] = field(default_factory=list)  # NEW: pro-Alert Kanal-Override
```

```typescript
// frontend/src/lib/types.ts
export interface AlertRule {
  id: string;
  kind: "absolute" | "delta";
  metric: string;
  threshold: number;
  severity: "info" | "warning" | "critical";
  enabled: boolean;
  unit?: string;
  channels?: string[];  // NEW: pro-Alert Kanal-Override
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|------------|
| id | string | Eindeutige Alert-ID (z.B. `alert-gust-1`) |
| kind | enum | `"absolute"` (Schwellenwert überschritten) oder `"delta"` (Änderung größer als Schwelle) |
| metric | enum | Gemessene Metrik: WIND_GUST, PRECIPITATION_SUM, TEMPERATURE_MIN/MAX, THUNDER_LEVEL, SNOW_LINE, TEMPERATURE/WIND/PRECIPITATION_CHANGE |
| threshold | float | Schwellenwert (z.B. `50.0` für 50 km/h Wind-Böen) |
| severity | enum | `"info"`, `"warning"`, `"critical"` — nur noch Label am Alert, **nicht mehr** für Versand-Filterung (behebt Severity-Falle: Info-Alerts werden nicht mehr still verschluckt) |
| enabled | bool | Alert aktiv? (default: true) |
| unit | string | Einheit (optional, z.B. `"km/h"`, `"mm"`) |
| channels | string[] | **NEW (Issue #638):** Kanäle für diesen Alert (`["email", "telegram"]`). Leer = erbe aktive Briefing-Kanäle aus `TripReportConfig`. Pro Alert überschreibbar. |

### Versand-Logik (Kanal pro Alert)

**Effektive Kanäle eines Alerts:**
- Falls `alert.channels` nicht leer: nutze exakt diese Kanäle
- Falls `alert.channels` leer oder nicht gesetzt: erbe aktive Briefing-Kanäle aus `report_config` (`send_email`, `send_telegram`, `send_sms`)

**Beispiel:**
```json
{
  "report_config": {
    "send_email": true,
    "send_telegram": false,
    "send_sms": false
  },
  "alert_rules": [
    {
      "id": "alert-gust-1",
      "metric": "wind_gust",
      "threshold": 50,
      "channels": [],  // leer → erbe Email (send_email=true)
      "enabled": true
    },
    {
      "id": "alert-thunder-1",
      "metric": "thunder_level",
      "threshold": "HIGH",
      "channels": ["telegram"],  // überschreibe: versand nur über Telegram, auch wenn Email aktiv ist
      "enabled": true
    }
  ]
}
```

### Migration & Backward Compatibility

- **Bestands-Alerts ohne `channels`-Feld:** Laden mit `channels: []` (default). Bei Versand erben sie die aktiven Briefing-Kanäle (RMW — Read-Modify-Write).
- **`severity` bleibt erhalten:** Bestandsdaten mit `"severity":"info"` bleiben lesbar. Die Ableitung von `severity` folgt weiterhin der Logik in `weather_change_detection.py`, wird aber **nicht mehr** für Versand-Filterung genutzt (Severity-Falle beseitigt).

### Frontend Alerts-Tab (JSX / Karten-Modell)

**Komponente:** `AlertsTab.svelte` → `AlertCard.svelte` pro Alert

**Karten-Struktur:**
- Label + `Metrik · Bedingung` (Monospace-Schriftart)
- An/Aus-Switch (`enabled` toggle)
- Kanal-Chips (toggle pro aktivem Briefing-Kanal)
- Infozeile: „Alert-Kanäle werden mit den aktiven Kanälen aus Wetter-Metriken vorgefüllt — jeder Alert kann separate Kanäle haben"
- „+ Neuen Alert hinzufügen"-Button (entfernt die alte Severity-Dropdown-UI)

**Keine Severity-Auswahl mehr:** Die alte UI-Severity-Auswahl ist entfernt (beseitigt die Severity-Falle, die Info-Alerts still verschluckt hat).

### Behavioral Changes (Issue #638)

| Aspekt | Vorher | Nachher |
|--------|--------|---------|
| **Severity-Filter** | `trip_alert.py:_filter_significant_changes` gab nur MODERATE/MAJOR durch; INFO-Alerts wurden still verschluckt | Jeder von einer aktiven Regel ausgelöste Change wird durchgereicht (kein MINOR/INFO-Filter mehr) |
| **Kanal-Routing** | Ein Alert = alle Briefing-Kanäle | Ein Alert = pro-Alert Kanal-Override; vorbelegt aus Briefing-Kanälen |
| **Severity in UI** | User konnte Severity wählen | Severity ist jetzt rein Label; wird von `weather_change_detection.py` abgeleitet |

---

## Changelog

- 2026-06-10: Issue #690 — Eigene Wetter-Metriken-Profile (MetricPreset CRUD): Section 15.5 hinzugefügt. 4 REST-Endpoints: GET/POST/DELETE/PATCH `/api/metric-presets{/{id}}`. MetricPreset DTO mit Name (eindeutig pro Nutzer, case-insensitive, getrimmt), Metrics ([]DisplayMetric mit Horizons), is_default, CreatedAt. POST antwortet mit HTTP 201 bei Erfolg; HTTP 400 bei leerem Name (`"name_required"`); HTTP 409 bei Duplikat-Name (`"name_exists"`, case-insensitive). Bestands-Daten: Single-File Storage `metric_presets.json` pro Nutzer; User-Isolation via Auth-Context (`user_id`). Frontend: Dialog zeigt Client-Validierung (Duplikat-Check), neues Profil wird nach Speichern sofort aktiv auf Trip (`display_config.preset_name = preset.id`), "Eigene"-Markierung in Preset-Leiste (unterscheidet User-Profile von System-Vorlagen), trip-übergreifend sichtbar. See `docs/specs/modules/issue_690_custom_metric_presets.md`.
- 2026-06-09: Issue #674 — Fahrradtouren als Aktivitätstypen (15 / 20 / 25 km/h): Neue `ActivityType`-Werte `"fahrrad_15"`, `"fahrrad_20"`, `"fahrrad_25"` in Go + TypeScript mit korrekten Naismith-Raten (600 m/h Aufstieg, 1000 m/h Abstieg — doppelt so schnell wie Wanderer). Section 10.5 hinzugefügt (Trip Model und Activity Types). Trip.activity Feld existierte bereits (Epic #136), wird jetzt dokumentiert mit vollständiger Aktivitäts-Tabelle. `ComputeStageArrivals()` Signatur erweitert auf `ActivitySpeeds`-Parameter statt hardcodiert; `ActivitySpeed(trip.activity)` Hilfsfunktion in Go. Frontend: `activityToSpeed(activityType?)` Hilfsfunktion, `computeArrivalTimes()` akzeptiert optionalen `speedFlatKmh`-Parameter. Wizard Step 3 zeigt 3 neue Fahrrad-Optionen im Dropdown. EditStagesPanelNew erhält `activityType`-Prop, leitet Speed weiter. Backward-Compatibility: unbekannte/leere Activity → Wanderer-Default (4.0 km/h, 300/500 Hm/h). Keine Python-Erweiterung (OUT OF SCOPE, Folge-Issue für EtappenConfig). See `docs/specs/modules/issue_674_aktivitaetstyp_fahrrad.md`.
- 2026-06-09: Issue #680 — Compare-Editor Slice 3 Fidelity-Tabs „Orte" + „Idealwerte" (Epic #677): ComparePreset DTO erweitert um opaque `display_config` field (Section 16). Keys: `active_metrics` ([]string — ausgewählte Metriken pro Vergleich), `ideal_ranges` (min/max-Idealwerte für Bewertung), zukünftig `output_layout` + `schedule_config`. Frontend RMW-Semantik: nur geänderte Felder senden, Server roundtrippt alles (bestandsfelder erhalten). Zero-schema-validation im Backend. Neue UI-Komponenten: `RangeSlider.svelte` (Dual-Handle für range-Metriken), Segmented-Control (Enum-Metriken). compareMetricDefs.ts: `ALL_METRICS`-Katalog + `deriveIdealText()`. compareWizardState.svelte.ts: `activeMetricKeys`, `metricsManuallyEdited`. Step2Orte: nummerierte Picked-Liste mit Entfernen, Region-gruppierte Bibliothek (Checkbox). Step3Idealwerte: Slider, Add/Remove-Metrik, Persistenz. See `docs/specs/modules/issue_680_compare_editor_slice3.md`.
- 2026-06-09: Issue #675 — Etappen-Startzeiten editierbar (Frontend-only, no API changes): (1) New `StageTimeField.svelte` component (analog `StageDateField`) renders `<input type="time">` within `.box` wrapper with label "STARTZEIT"; (2) Editor displays default `08:00` when `stage.start_time` is unset (displayValue fallback); (3) `EditStagesPanelNew.svelte` handler `handleStartTimeChange()` implements immutable update: setting empty string removes `start_time` (returns to default), otherwise sets to user-chosen time; (4) Component renders in both Desktop header (.stage-header-fields) and Mobile markup (@media ≤899px) for Desktop–Mobile parity; (5) Skipped for pause stages (`activeIsPause === true`); (6) Live Naismith `$derived arrivals` recalculates from changed `start_time` without explicit save (feature display); (7) Existing `Stage.start_time?: string` field (already present in model, Naismith, and Backend RMW) requires no data migration; unset trips remain byte-equal on open+save (alt-treu). ACs 1–7 verified via Playwright E2E + staging_validator. See `docs/specs/modules/issue_675_etappen_startzeiten.md`.
- 2026-06-09: Issue #638 — Alerts-Tab Karten-Modell + Severity-Falle + pro-Alert Kanäle: (1) Added section 22 — AlertRule DTO with new `channels: list[str]` field (empty = inherit active briefing channels; non-empty = override); (2) `AlertRule.severity` now label-only (not used for send filtering anymore — eliminates severity trap where info-alerts were silently dropped); (3) Frontend Alerts-Tab moved from table paradigm to card model via AlertCard.svelte; Severity dropdown UI removed; Channel chips per alert with toggle UI; (4) Versand-Logik: per-alert kanal-routing via `trip_alert.py:_send_alert()` gruppiert Changes nach effektiven Kanälen; (5) Backward compatibility: bestandsdaten ohne `channels` laden mit leerer Liste (RMW bei Versand); `severity` bleibt lesbar. See `docs/specs/modules/issue_638_alerts_redesign.md`.
- 2026-06-02: Issue #559 — Archive page completion: (1) Added `GET /api/trips/{id}/briefing-history` endpoint (section 21) to display chronological list of sent briefings (morning/evening) with timestamps and channels; (2) Frontend `BriefingHistoryDialog.svelte` modal with formatted timestamps (DD.MM.YYYY HH:MM) and localized kind labels; (3) "Als Vorlage" (Use as Template) button on archive page copies trip config via query param `?from={id}` to wizard page, with `templateTrip` loaded in `+page.server.ts`; (4) "Was passiert ist" (What Happened) column shows formatted event summary via `formatEventSummary(briefings, alerts)` helper. See `docs/specs/modules/issue_559_archiv_fertigstellen.md`.
- 2026-06-01: Issue #523 — Code-Debt Cleanup: Removed `Waypoint.Suggested` (bool) and `Waypoint.SuggestionReason` (*string) fields from backend Go model (`internal/model/trip.go`). Legacy normalization block in `ConfirmWaypointHandler` removed. Frontend TypeScript `Waypoint` interface no longer declares `suggested?` and `suggestion_reason?` properties. Utility function `stripSuggested()` and all callers removed from waypoint editor. UI component `WaypointPin.suggested` property and dashed-stroke visualization deleted. Cleanup fulfills Constraint C8 from Issue #506 (Remove AI-Suggestion UI). 13 files edited, ~-190 LoC net deletion. Backward compatibility: bestandsdaten mit `"suggested":true` im JSON bleiben lesbar (Go ignoriert unknown JSON fields bei deserialisierung). See `docs/specs/modules/issue_523_suggested_flag_cleanup.md`.
- 2026-06-01: Issue #497 (BugFix) — Preview SMS Stage-Name + Fixture Fields: ForecastDataPoint from FixtureProvider now reads all 4 demo-mode fields (`cloud_low_pct`, `pop_pct`, `snowfall_limit_m`, `wind_dir_deg`) from fixture JSONs. Preview SMS rendering fixed: `.split(":", 1)[0].strip()` for correct Stage-Name extraction.
- 2026-05-31: Issue #483 — Demo-Modus im Vorschau-Tab: Added `demo: bool` Query-Parameter to all 4 preview endpoints (`/api/preview/{trip_id}/[email|sms|signal|telegram]`). When `demo=1`, endpoints use FixtureProvider instead of live weather; demo mode ideal for testing preview rendering on past trips. Supports AC-1–AC-6 for demo banner UX and fallback to live weather. See section 20 (new) and `docs/specs/modules/issue_483_demo_mode_preview.md`.
- 2026-05-31: Issue #495 — MapCanvas Leaflet-Karte: `MapCanvas.svelte` vollständig auf Leaflet 1.9.4 mit OpenTopoMap-Tiles umgestellt. `buildMapPositions()` und `MapPosition`-Typ aus `frontend/src/lib/utils/waypointEditor.ts` entfernt — Leaflet übernimmt Projektion und Zoom. Wegpunkt-Editor zeigt jetzt geografisch korrekte Höhenschichtlinien-Karte mit Marker-Popups und Polyline. 3 Dateien geändert: `package.json` (+leaflet, +@types/leaflet), `MapCanvas.svelte` (~180 LoC Rewrite), `waypointEditor.ts` (-buildMapPositions, -MapPosition).
- 2026-05-30: Issue #467 — Passkey V3 Discoverable Credentials + Conditional UI: 2 new public endpoints (`POST /api/auth/passkey/discoverable/begin` and `/finish`) enable login without username. Browser shows registered passkeys as native autofill suggestions on username field focus via WebAuthn `mediation: 'conditional'`. Begin returns full assertion object with top-level `"mediation":"conditional"` flag. Finish accepts `userHandle` from authenticator and looks up user via `DiscoverableUserHandler` callback. Rate-limit 30/h per IP (same as V1). Frontend: `loginWithDiscoverablePasskey()` function in `passkey.ts` + `onMount` conditional UI init in login page with `autocomplete="username webauthn"` attribute. Tests: 6 mock-free roundtrip tests covering success path, empty userHandle, unknown user, challenge replay, and TTL expiry. See `docs/specs/modules/issue_467_discoverable_credentials.md`.
- 2026-05-30: Issue #464 — Compare-E-Mail Observability-Endpoint `POST /api/_validator/compare-email-preview` (Tooling-API, nicht versionsstabil): Macht den Compare-HTML-Renderer von außen direkt aufrufbar für Validator-Observability. Go-Proxy + Python-Handler (validator.py). Request-Body: `{profile, time_window, target_date, winner_tags}`. Response: `{html: "..."}` mit gerendertem HTML. Stub-LocationResult mit score=85, keine echten Wetterdaten. AC-1/2/3 prüfbar per `curl | grep`. Siehe `docs/specs/modules/issue_464_compare_email_preview_validator.md`.
- 2026-05-30: Issue #468 — AAGUID-Labels in der Passkey-Liste: GET `/api/auth/profile` Passkey-Einträge zeigen neu optionales Feld `authenticator_name` (z.B. "iCloud Keychain", "Windows Hello") basierend auf AAGUID-Mapping. Field omitempty bei Zero/Unknown-AAGUID. Frontend zeigt kombiniert `"{authenticator_name} · {label}"`. Siehe `docs/specs/modules/aaguid_labels.md`. Implementation: ~90 LoC (`aaguid.go`, `auth.go`, `account/+page.svelte`).
- 2026-05-30: Issue #461 — Compare-Presets Daily Dispatch (Cronjob): New `POST /api/scheduler/compare-presets-daily` endpoint (section 17) triggered daily by Go scheduler at 06:00 UTC. Filters presets by `schedule='daily'`, runs Compare Engine, renders/sends emails via Resend, updates `letzter_versand` and `top_ort_letzter_versand` fields. Per-preset error isolation; BetterStack Heartbeat pinged only on `error_count==0` (Readiness Principle). Config field `HeartbeatComparePresets` added to Go config; Go scheduler job count increased from 5 to 6. Tests: 11 new comprehensive tests in `test_issue_461_compare_preset_dispatch.py`.
- 2026-05-30: Added section 18 — Authentication Endpoints (Issue #450 Passkey/WebAuthn V1): 5 passkey endpoints (register/begin|finish, login/begin|finish, delete), password auth methods (register, login), profile endpoint with `has_passkey`+`passkeys[]`. User model extended with `PasskeyCredentials[]` and `PasswordHash` now optional. Rate-limit 30/h per IP (alle 5 Endpoints), challenge TTL 5 min, RP-ID isolation (prod vs staging), 64 KB body cap.
- 2026-05-30: Issue #459 — Auto-Briefings Sidepanel Frontend (ComparePreset-System): AutoReportsOverview, SavePresetDialog, subscriptionHelpers (presetScheduleLabel, formatLastSent), ComparePreset-Interface in types.ts; +page.server.ts lädt `/api/compare/presets`; AutoReportCard und AutoReportsOverview auf ComparePreset umgebaut mit manuellem Versand-Button. Spec #458-Backend-Endpoints vorausgesetzt (`GET /api/compare/presets`, `/send`).
- 2026-05-31: Issue #475 — OutputLayoutEditor Organisms-Migration (Pure Frontend): OutputLayoutEditor verliert direkten `ui/card`-Import, nutzt stattdessen `atoms/Card.svelte`. Komponente wird als vierter Eintrag in `organisms/index.ts` re-exportiert. Consumer-Imports (Step4Layout×2, WeatherMetricsTab) auf `$lib/components/organisms` umgestellt. Keine API/DTO-Änderungen.
- 2026-05-30: Issue #458 — Compare-Preset Backend (CRUD+Endpoints): Neues `ComparePreset`-Datenmodell (separate Entität von `CompareSubscription`); 5 REST-Endpoints: GET/POST/PUT/DELETE + `/send`-Stub; Single-File Storage `compare_presets.json`; User-Isolation; Validierung. Siehe Abschnitt 16.
- 2026-05-29: Issue #455 — Compare-Hauptbühne Frontend `/compare` route implemented (pure frontend, no API changes). 3-column layout: LocationsRail (left 320px) | CompareMatrix/RecommendationBanner/HourlyMatrix (center flex) | AutoReportsOverview (right 320px). POST `/api/compare/run` contract unchanged; frontend wires existing Go-backend endpoint. See `docs/specs/modules/issue_455_compare_main_stage.md`.
- 2026-05-29: Issue #448 — Validator-Endpoint `GET /api/_validator/metrics-for-channel` ergänzt (Tooling-API, nicht versionsstabil): Macht die dreistufige Kaskade von `get_metrics_for_channel()` (per_report → per_channel → global) von außen prüfbar. Response: `{"source": "per_report|per_channel|global", "metric_ids": [...]}`. Params: `trip`, `channel`, `report`, `user_id` (via Go-Proxy injiziert).
- 2026-05-29: Issue #442 — Compare-Wizard Step 4 Layout (Pure Frontend): Step4Layout component added to Compare-Wizard, enabling per-channel metric configuration (Email/Telegram/Signal/SMS) with reusable OutputLayoutEditor component (Issue #431). Wizard calls GET /api/metrics (required), GET /api/templates (optional), GET /api/metric-presets (optional) on mount. No backend changes; `channel_layouts` field added to CompareSubscription state (frontend-only persistence via `save()`).
- 2026-05-29: Issue #446 — Format-Mode-Validierung in `_resolve_format_mode()`: Unbekannte `format_mode`-Strings (z.B. `"Symbol"` mit Großbuchstabe, `"raw_v2"`) werden jetzt gegen `MetricDefinition.format_modes` validiert und auf `default_format_mode` zurückgefallen, mit WARNING-Log.
- 2026-05-29: Added section (legacy 16, neu nummeriert) — Google OAuth Login Endpoints (Issue #425): GET /api/auth/google/init (initiates flow, redirect to Google), GET /api/auth/google/callback (code exchange, user creation/lookup, session issuance). User model extended with `OAuthProvider` and `OAuthSub` fields. Feature-gated via `GZ_GOOGLE_CLIENT_ID` config. New User-ID format `g-{8hex}` for OAuth users (prevents session parse errors).
- 2026-05-29: Added section 15 — Metric Catalog Endpoint (Issue #435): GET /api/metrics exposes `format_modes[]` and `default_format_mode` per metric for frontend UI filtering and backward-compatibility mapping.
- 2026-05-29: Issue #440 — Orts-Vergleich-Wizard Phase 1 — Extended CompareSubscription model with `activity_profile` (optional, validProfiles: wintersport|wandern|summer_trekking|allgemein). Frontend: CompareWizard Shell + Step 1 (Name/Region/Profile) + Step 2 (Smart-Import + Library). Stepper component made reusable via testidPrefix + onStepClick props. See `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md`.
- 2026-05-10: Epic #136 Trip-Wizard Master-Spec Fundament — Extended Trip model with `shortcode` and `activity` fields; Waypoint.suggested transient flag for wizard UI; Backend Trip.validateTrip() now accepts pause stages (waypoints: []). See `docs/specs/modules/epic_136_trip_wizard.md`.
- 2026-05-09: Added sections 12, 13, 14 — Scheduler Status, Forecast Query, Trip-Reports Trigger Endpoints (Epic #134). Support for dashboard briefing timeline, non-blocking client-side weather, and manual report trigger via API.
- 2026-04-14: Added section 11 — Weather Config Endpoints (M5c): 6 GET/PUT-Endpoints fuer display_config auf Trip, Location und Subscription als opaque JSON.
- 2026-04-14: Added section 10 — Subscriptions CRUD Endpoints (M5b): 5 REST-Endpoints fuer CompareSubscription, Single-File Storage, Validierung, Legacy-Migration.
- 2026-04-14: Added section 9 — GPX Proxy Endpoint (M5a): POST /api/gpx/parse, Go-to-Python Multipart Proxy, Stage+Waypoints Response DTO.
- 2026-02-18: Added `TripReportConfig.wind_exposition_min_elevation_m` (F7c Wind-Exposition Config) — per-trip configurable elevation threshold for wind exposition detection. Default null uses global 1500m threshold (lowered from 2000m).
