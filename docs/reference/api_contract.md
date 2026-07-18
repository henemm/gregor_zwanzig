
# API Contract — Gregor Zwanzig

**Updated:** 2026-07-16 (Issue #1278 + #1285 — Vergleichs-Mail-Kurzzusammenfassung je Ort (geteilter Trip-Baustein) + fünf reparierte, bisher still verworfene Tages-Aggregate; `LocationResult` bekommt 5 additive optionale Felder (`precip_sum_mm`/`thunder_level_max`/`visibility_min_m`/`uv_index_max`/`pop_max_pct`), keine Persistenz/kein Wire-Format betroffen; Details s. Changelog-Abschnitt unten); 2026-07-16 (Issue #1270 — neuer Endpoint `POST /api/preview/compare/{preset_id}`: EIN Aufruf liefert `{subject, email_html, telegram, sms, sms_char_count}` aus einem einzigen `ComparisonEngine.run()`, ADR-0011-Muster (Erweiterung `alert-preview`), bewusste Abweichung von der älteren Trip-Preview-Routenform je Kanal; neuer `ComparePreviewService`; Compare-Briefing-Versand wird ab jetzt tatsächlich auch über Telegram/SMS zugestellt (`NotificationService.send_compare_report`), nicht mehr nur E-Mail — der Alarm-Pfad (`compare_alert.py`/`compare_radar_alert.py`) bleibt unverändert E-Mail-only. Details Section 20 und `docs/specs/modules/compare_channel_preview_dispatch.md`); 2026-07-16 (Issue #1250 S7b — ComparePreset-Persistenz per-Datei briefings/{id}.json (kind="vergleich"), Store-Muster wie Trip-Store; Alt-compare_presets.json nur Migrations-Quelle/Rollback; load_compare_presets partial-tolerant; kind-scoped Migrations-Refresh migrate_1250_briefings.py --kind vergleich); 2026-07-15 (Issue #1258 S1 — `official_warnings {enabled, sources?}` neu auf Trip UND ComparePreset, löst `official_alert_triggers_enabled` funktional ab (jetzt deprecated, bleibt in den Daten); idempotente Migration `internal/store/migrate_1258.go`/`scripts/migrate_1258_official_warnings.py` übernimmt Ist-Verhalten des Bestands unverändert, Neuanlage-Default `enabled=false`; PUT-RMW mit Feld-Level-Preserve für `sources`; Legacy-Fallback bei fehlendem/leerem Feld — Details Section 10.5); 2026-06-13 (Issue #795 — Metriken-Überblick-Pills: Inhalt analog SMS (ausgeschrieben, gleiche Schwellen), Farbe via Ampel-System #759 (🟢🟡🟠🔴 = HTML-Vollfarb-Kapsel + weißer Text WCAG-AA, Plain = 4 Emojis, Compact = ASCII-Schwerezeichen); Bug #775 — Trip-Shortcode-Routing für Inbound-E-Mail-Replies: RFC-2047-Dekodierung, toleranter Whitespace↔Underscore-Lookup, neuer GZ#-Shortcode-Key als primärer Routing-Identifier, persistiert als `Trip.shortcode`; Issue #764 — ComparePreset forecast_hours Persistierung: neues Feld im Go-Modell/TS-Type (24|48|72 h), Hydration im Editor, Konsum im Python-Scheduler, Legacy-Default 48 h; Horizont-Select im Editor auf Design-System Select.svelte umgestellt); 2026-06-11 (Issue #747 — Datierter Forecast-Snapshot-Speicher: WeatherSnapshotService erweitert um `save_dated(trip_id, target_date, segments)`, `load_dated(trip_id, target_date)` und `_prune_dated_snapshots(trip_id)`. Speichert Snapshots nach Datum (`{trip_id}_{YYYY-MM-DD}.json`, max. 7 Dateien pro Trip, mtime-sortiert). Fundament für Vortag-Vergleich im Trip-Briefing. Bestehende `save()`/`load()`-Methoden für Alert-Pfad bleiben byte-identisch. Scheduler ruft `save_dated()` nach bestehendem `save()` auf. Siehe Issue #747.); 2026-06-11 (Issue #731 — Abruf-zentrierte Befehle: bare Keywords (HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE) ersetzen alte Abonnenten-Befehle (PAUSE/SKIP/CONFIG). Persistenzfelder paused_until/skip_next bleiben für Bestandsdaten erhalten. TripCommandProcessor.process() neu mit _resume_trip() für WEITER-Befehl. Keine Datenstruktur-Änderungen. Siehe Issue #731.); 2026-06-10 (Issue #715 — Wettermetriken-Darstellung: GET /api/metrics filtert auf `selectable=true` — `confidence` (Vorhersage-Verlässlichkeit/Ensemble) ist KEINE pro-Etappe wählbare Metrik mehr, nur noch Vorhersage-Hinweis + SMS-Symbol; Vorschau-Emojis in WeatherV2MailPreview + Step3Weather angepasst; Beispieldaten eindeutig gekennzeichnet; Bug #716 — Test-Briefing: stiller Versagensfall weg. POST /api/trips/{id}/send gibt jetzt HTTP 422 + detail-Feld zurück wenn keine Etappendaten für Zieldatum vorhanden (statt HTTP 200). Frontend zeigt konkrete Fehlermeldung im Toast; Issue #707 — Trip-Datum-Overwrite-Bug: PUT `/api/trips/{id}` mit minimalem Body (nur geänderte Felder) statt kompletter `trip`-Spread — verhindert stale-data-Überschreibung von Etappen; Issue #690 — Eigene Wetter-Metriken-Profile: eindeutiger Name (HTTP 409 name_exists, 400 name_required), Profil sofort aktiv + persistent, "Eigene"-Markierung in Preset-Leiste, trip-übergreifend pro Nutzer); 2026-06-09 (Issue #674 — Fahrradtour als Aktivitätstyp: 3 neue ActivityType-Varianten (fahrrad_15/20/25 km/h) mit korrekten Naismith-Raten (600/1000 Hm/h); #680 — Compare-Editor Slice 3 Fidelity: display_config.active_metrics — ausgewählte Metriken pro Vergleich; #675 — Etappen-Startzeiten editierbar; #671 — Bot-Menü automatisch beim Service-Start; #638 — Alerts-Tab Karten-Modell, Severity-Falle, pro-Alert Kanäle; #664 — Metriken-Überblick-Pille; #621 — E-Mail-Elemente abschaltbar); 2026-06-08 (Issues #672/#671 — Telegram E2E-Pipeline-Tests + Bot-Menü-Vertrag; #642 — User-Anzeigename display_name; #655 — Telegram Hybrid-Navigation: callback_query + editMessageText); 2026-06-07 (Issues #627/#631 — Compare-Preset Sofortversand + Wochen-Rhythmus-Erhalt)

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
| show_metrics_summary            | bool        | Optionaler Metriken-Überblick am Beginn (default: false, Issue #664/795) — wenn true: farbige Pillen pro konfigurierter Metrik mit SMS-identischen Erwähnungsschwellen. **Pill-Inhalts-Format (Issue #795):** Ereignis-Metriken (wind/gust/precip/pop/thunder/visibility/humidity) zeigen „<Label> ab HH:00 · Spitze <X> um HH:00" (oder ruhige Form unter Schwelle); Bereichs-Metriken (temp/wind_chill/cloud/freezing_level/dewpoint/uv/sunshine) zeigen „<Label> min–max <Einheit>" ohne Uhrzeit. **Pill-Farbe (Issue #759/#795):** EIN Ampel-System (🟢🟡🟠🔴) pro Spitzenwert via `display_thresholds` + `ampel_dot`-Logik; HTML = WCAG-AA-Vollfarb-Kapsel (weißer Text ≥4.5:1); Plain = dieselben 4 Emojis wie die Stundentabelle; Compact (7bit/ASCII) = ASCII-Schwerezeichen (grün→kein, gelb→`!`, orange→`!!`, rot→`!!!`). Ersetzt Quick-Take und blendet Tages-Summe aus. |
| show_outlook                    | bool        | Ausblick-Block anzeigen? (default: true, Issue #721) — verschmilzt Großwetterlage (Kopf) + Tabelle der nächsten Etappen mit Uhrzeiten und Vorhersage-Sicherheit (`confidence_pct` pro Etappe). Gilt für HTML **und** Plain-Text. `false` blendet den gesamten Block aus (Großwetterlage zusätzlich an `show_stability` gekoppelt). |
| email_format                    | str         | E-Mail-Format-Schalter (default: `"full"`): `"full"` = multipart-HTML mit Stundentabellen (unverändert); `"compact"` = reine text/plain-Mail, nur ASCII, ohne HTML, mit fix Kopf + Metriken-Überblick + Ausblick + Footer, ~95% kleiner. Baustein-Toggles greifen bei compact NICHT. Siehe Issue #722. |
| show_yesterday_comparison       | bool        | Vortag-Vergleich-Sektion in E-Mail anzeigen? (default: true, Issues #750 #752) — wenn true und Vortag-Snapshot vorhanden: zeigt Delta-Tabelle in HTML und Plain; fehlender Snapshot führt zu sanftem Überspringen (kein Fehler). Der Toggle wirkt einheitlich auf beide Kanäle: `format_email` nullt `day_comparison` bei `false`, sodass auch die Vortag-Zeile in der Telegram-Kurzübersicht-Bubble (`render_telegram_bubbles()`, Issue #1001) entfällt. |
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
    OfficialAlertsEnabled   *bool                  `json:"official_alerts_enabled,omitempty"` // Issue #1087, Pointer-Muster analog ComparePreset (#1040): nil = Default true; false = kein Fetch amtlicher Warnungen für diesen Trip
    OfficialAlertTriggersEnabled *bool             `json:"official_alert_triggers_enabled,omitempty"` // @deprecated (Issue #1258, ersetzt durch official_warnings.enabled) — bleibt in den Daten fuer Rollback-Sicherheit, wird ab #1258 von UI und Pipeline nicht mehr geschrieben/gelesen. Vormals: nil = Default true; false = amtliche Warnungen lösen keinen eigenständigen Sofort-Alert aus (Briefing-Anzeige bleibt unberührt)
    OfficialWarnings        *OfficialWarningsConfig `json:"official_warnings,omitempty"`      // Issue #1258 — s. „official_warnings (Issue #1258)" unten
    AlertChannels            *AlertChannelsConfig   `json:"alert_channels,omitempty"`          // Issue #1258 Scheibe S3 — s. „alert_channels (Issue #1258)" unten
    Corridors               []Corridor             `json:"corridors"`                         // Issue #1231 Slice 1, additiv neben AlertRules — s. Section 24
}

// OfficialWarningsConfig — Issue #1258, geteilt zwischen Trip und ComparePreset
type OfficialWarningsConfig struct {
    Enabled bool     `json:"enabled"`
    Sources []string `json:"sources,omitempty"`
}

// AlertChannelsConfig — Issue #1258 Scheibe S3, additives Trip-Kanal-Set fuer
// die Alert-Zustellung. All-or-nothing: Client sendet immer alle drei Felder.
type AlertChannelsConfig struct {
    Email    bool `json:"email"`
    Telegram bool `json:"telegram"`
    Sms      bool `json:"sms"`
}
```

### alert_channels (Issue #1258)

Trip-weites Kanal-Set für den Alert-Versand (Abweichungs-Alerts und amtliche Sofort-Alerts), Pointer-Feld analog `official_warnings`:

```json
{"alert_channels": {"email": true, "telegram": false, "sms": false}}
```

| Feld | Typ | Semantik |
|------|-----|----------|
| `alert_channels` | Objekt \| `null`/nicht gesetzt | **`null`/fehlend (Legacy-Verhalten):** Alert-Kanäle erben die aktiven Briefing-Kanäle aus `report_config` (`send_email`/`send_telegram`/`send_sms`) — kein Verhaltenswechsel für Bestand. **Gesetzt:** ersetzt beim Alert-Versand den geerbten Briefing-Anteil (all-or-nothing, alle drei Felder explizit) |
| `alert_channels.email`/`.telegram`/`.sms` | bool | einzelne Kanal-Flags |

Präzedenz unverändert: per-Regel-`channels`-Overrides (Issue #638, s. „Versand-Logik (Kanal pro Alert)" oben) gewinnen weiterhin über den geerbten/gesetzten Trip-Anteil; das SMS-Tier-Gate bleibt in jedem Fall aktiv. Quelle: `internal/model/trip.go` (`AlertChannelsConfig`), Spec `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` Abschnitt 9.

### official_warnings (Issue #1258)

Löst `official_alert_triggers_enabled` (#1088) funktional ab: `official_warnings.enabled`
steuert, ob amtliche Warnungen für diesen Trip/ComparePreset einen Sofort-Alarm auslösen
(Briefing-Anzeige selbst bleibt unberührt, s. `official_alerts_enabled` #1087). Gilt identisch
für Trip UND ComparePreset (Go `*OfficialWarningsConfig`, Python `Optional[dict]`).

```json
{"official_warnings": {"enabled": true, "sources": ["vigilance"]}}
```

| Feld | Typ | Semantik |
|------|-----|----------|
| `enabled` | bool | `true` = amtliche Warnungen lösen einen Sofort-Alarm aus; `false` = kein Sofort-Alarm |
| `sources` | string[] \| omitted | Quellen-Filter (Namen aus `src/services/official_alerts/__init__.py`-Registry). Unset/leer = alle registrierten Quellen fließen ein (unverändertes Verhalten). Gesetzt = nur die genannten Quellen fließen in die Alarmentscheidung ein, andere werden ignoriert |

**Fehlend/`nil`:** unmigrierter Bestand — Pipeline (`trip_alert.py`, `compare_official_alert.py`)
fällt fail-soft auf das Legacy-Feld `official_alert_triggers_enabled` zurück (`nil`/`true` →
Alarm aktiv, `false` → kein Alarm). Ein `{}`-Wert (Key vorhanden, `enabled` fehlt) wird wie
`nil` behandelt (Legacy-Fallback), nicht wie `enabled=false` — Go und Python sind hierin
identisch (Fix-Loop F003, s. Changelog #1258).

**Neuanlage-Default:** `enabled: false` — bewusster Verhaltenswechsel gegenüber Bestand (der per
Migration den alten Ist-Zustand behält, s.u.).

**Migration (`internal/store/migrate_1258.go`, `scripts/migrate_1258_official_warnings.py`):**
idempotente Batch-Migration nach Vorbild `migrate_1257.go` — pro Trip/ComparePreset unter
`data/users/*/`: `official_warnings.enabled := (official_alert_triggers_enabled != false)`
(nil/true → true, false → false), damit ändert sich das gesendete Alarmverhalten für Bestand
NICHT. Zweiter Lauf ändert an bereits migrierten Objekten nichts (Idempotenz-Check über
`officialWarningsRawHasEnabledKey()`/`"enabled" in ow`).

**PUT-RMW (Read-Modify-Write, `internal/handler/trip.go`, `internal/handler/compare_preset.go`):**
Feld im Body ganz weglassen → Bestand bleibt unverändert (Objekt-Ebene). Wird `official_warnings`
mitgeschickt, aber `sources` darin weggelassen (Key fehlt im JSON) → bestehende `sources[]`
bleiben erhalten (Feld-Level-Preserve, Fix-Loop F002); ein explizites `"sources": []` löscht die
Liste bewusst. `enabled` ist innerhalb eines mitgeschickten `official_warnings`-Objekts immer
Pflicht-Wert der Anfrage (kein separates Preserve für `enabled` selbst).

**Isolation:** wie jedes trip-/presetgebundene Feld strikt über `user_id` — kein Cross-User-Leck
(s. `CLAUDE.md` Mandantenfähigkeits-Pflicht).

**Invariante — nie `null` (Issue #205, gehärtet Issue #1244):** `Stages`, jedes
`Stage.Waypoints`, `AlertRules` und `Corridors` sind immer als `[]` serialisiert, niemals als
`null` — sowohl in der Datei auf Platte als auch in jeder HTTP-Response. Durchgesetzt von
`normalizeTrip()` (`internal/store/trip.go`), das sowohl im Schreibpfad (`SaveTrip`, nimmt seit
#1244 einen Pointer statt eines Value-Receivers) als auch im Lesepfad (`LoadTrip`, `LoadTrips`)
läuft. Der Python-Loader (`src/app/loader.py`) heilt zusätzlich `null` beim Lesen fail-soft
(`data.get("x") or []`) für Bestandsdateien, die noch nicht über `SaveTrip` neu geschrieben
wurden. Bestandsdaten: `scripts/migrate_1244_null_lists.py`, s. `operations_playbook.md`.

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

### Shortcode (Bug #775)

Das Feld `shortcode` dient als eindeutiger, pro Nutzer stabiler Routing-Identifier für Inbound-E-Mail-Replies.

| Feld | Beschreibung |
|------|-------------|
| `shortcode` | Format: `GZ#XXXX` oder `GZ#XXXX<n>` (z.B. `GZ#HERM`, `GZ#HERM2` bei Kollision). Generiert aus den ersten 4 alphanumerischen Großbuchstaben des Trip-Namens. Wird lazy persistiert beim ersten Versand. Immun gegen RFC-2047-Encoding-Artefakte (Leerzeichen→Underscore). Präfix im E-Mail-Betreff: `[GZ#HERM]` ermöglicht Shortcode-Prioritäts-Lookup; Fallback: toleranter Namensvergleich (Whitespace/Underscore-agnostisch). |

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

**Segment-Startzeit-Prioritätskette (Issue #1004, SSoT):** `Waypoint.time_window` ist
ausschließlich ein GPX-Import-Artefakt ohne jeden manuellen Schreibpfad im Produkt und hat
in `convert_trip_to_segments()` (`trip_segments.py`) **keine** Autorität mehr — kein Flag,
keine Migration, gilt sofort für alle Trips inkl. Bestand. Die einzige Kette:
`arrival_override` (Issue #303, manuell) > `stage.start_time` (nur für Segment 1 einer Etappe)
> `arrival_calculated` (Naismith-Kaskade, immer frisch ab `stage.start_time`) > Default 08:00
> letzter bekannter Zeitpunkt (Folgesegmente). `time_window` selbst bleibt als
Roundtrip-/Anzeige-Feld am DTO erhalten, wird aber nirgends mehr als Zeitquelle gelesen.
Der zuvor eingeführte Python-interne Flag-Ansatz `Waypoint.time_window_origin` (Issue #995)
wurde als wirkungslos entfernt (nie persistiert, Bestandstrips blieben ausgenommen).

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

Convenience-Layer ueber die bestehenden CRUD-Handler. Erlaubt gezieltes Lesen und Schreiben des `display_config`-Subfelds auf Trip- und Location-Entitaeten ohne Uebertragung des gesamten Objekts. Alle Config-schreibenden Endpoints (Trip, Location, ComparePreset) mergen feldweise ueber den gemeinsamen `mergeConfigMap`-Helfer (`internal/handler/config_merge.go`, #1159) — Teil-Updates loeschen keine anderen `display_config`-Keys mehr. Der fruehere Subscription-Endpoint wurde mit #1250 Scheibe 0 entfernt.

**Handler:** `internal/handler/weather_config.go` (NEU) | **Routing:** `cmd/server/main.go`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/api/trips/{id}/weather-config` | 200 / 404 | `display_config` eines Trips lesen |
| PUT | `/api/trips/{id}/weather-config` | 200 / 400 / 404 | `display_config` eines Trips setzen |
| GET | `/api/locations/{id}/weather-config` | 200 / 404 | `display_config` einer Location lesen |
| PUT | `/api/locations/{id}/weather-config` | 200 / 400 / 404 | `display_config` einer Location setzen |

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
- `userID` hardcodiert auf `"default"` (V1)
- Kein File-Locking: Race Conditions bei parallelen PUT-Requests akzeptiert (Single-User V1)

### Source Files

| Datei | Aenderung |
|-------|-----------|
| `internal/handler/weather_config.go` | 4 HTTP-Handler (Get/Put fuer Trip, Location) |
| `internal/handler/config_merge.go` | NEU (#1159) — gemeinsamer `mergeConfigMap`-Helfer fuer feldweisen Merge, genutzt von Trip-, Location- und ComparePreset-Endpoints |
| `cmd/server/main.go` | +4 Route-Registrierungen |

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
| metrics[].sms_code | string | GSM-7-safe short token for the metric in SMS/Subject/Telegram alert tokens (e.g., `W`, `G`, `R`, `PR`, `TH`, `CP`, `SL`, `VS`, `HU`). Single source for alert renderers (Issue #914 Slice 1); the metric catalog is the only place these are defined |
| metrics[].decimals | int \| null | Rounding precision for display (e.g., `precipitation: 1`, `visibility: 1`, most metrics `0`). `null` ⇒ fall back to the unit-based heuristic in `format_metric_value()` |
| metrics[].cmp | string | Comparison direction: `"über"` or `"unter"`. Single source for the direction/arrow used by deviation and absolute alert detection (Issue #914 Slice 1) — replaces the former hand-coded `_ALERT_METRIC_COMPARISON` dict. **Not** a threshold comparator for the deviation-alert (live) path: per ADR-0013, an event triggers there when `abs(value_to − value_from) ≥ threshold` regardless of `cmp`; `cmp` remains a literal exceeds/falls-below comparator only for `ABSOLUTE`-kind rules (`_detect_absolute_changes()`), which is unused in the send path (`include_absolute=False`) |

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

- **Severity-Schwellen (Issue #814):** Die HTML-Ampel (🟢🟡🟠🔴) der Severity-Metriken nutzt die bestehenden `display_thresholds` des Katalogs (`{"yellow": N, "orange": M, "red": K}`). #814 setzt CAPE auf die Standard-Konvektionsskala `{"yellow": 1000, "orange": 2500, "red": 3500}` (J/kg); wind/gust/precip/pop bleiben unverändert. Welche Metriken überhaupt einen Ampelpunkt bekommen, ist in `src/output/renderers/email/helpers.py` über das frozenset `_AMPEL_CAPABLE_METRIC_IDS` = {wind, gust, precipitation, rain_probability, cape} festgelegt — der Ampel-Indikator wird pro Spalte aus `use_friendly_format` via `build_html_indicator_keys()` abgeleitet (nur HTML-Einfach).
  - Der **Roh/Einfach-Umschalter im Trip-Editor** wird NICHT vom Backend-Feld `has_friendly_format` gesteuert, sondern frontend-seitig über die `INDICATOR_MAP` in `frontend/src/lib/components/trip-detail/metricsEditor.ts` (seit #814: `visibility` entfernt, `precipitation` ergänzt).

- **Metric Display Contract (Issue #814):** Der vollständige Einfach/Roh-Vertrag aller Metriken ist nun kodifiziert in `docs/reference/renderer_email_spec.md` § „Metric Display Contract". `use_friendly_format=true` → HTML-Ampelpunkte für Severity-Metriken, Emojis für Wetterbild-Piktogramme, ⚡-Symbol für Gewitter; `use_friendly_format=false` → nackte Zahlen überall, keine Markierungen. Plain-Text immer numerisch (außer Gewitter = deutsches Wort). **„Roh ist Roh":** Roh-Modus hat **keine** inline-Farb-/Hintergrund-Markierungen.

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

**Handler:** `internal/handler/compare_preset.go` | **Storage:** `data/users/{userID}/briefings/{id}.json` (per-Datei, `kind="vergleich"`; Legacy `data/users/{userID}/compare_presets.json` nur noch Migrations-Quelle/Rollback, Issue #1250 S7b) | **Routing:** `cmd/server/main.go`

### ComparePreset DTO

```go
type ComparePreset struct {
    ID                   string                 `json:"id"`                                    // "cp-{hex}", auto-generated
    Name                 string                 `json:"name"`
    UserID               string                 `json:"user_id"`                               // set from Auth-Context, server-managed
    LocationIDs          []string               `json:"location_ids"`                          // 2+ locations to compare
    Schedule             string                 `json:"schedule"`                              // DEPRECATED für Zeitplan-Zwecke (Issue #1232 Scheibe 2a): trägt nur noch Pause-Semantik — "manual" = pausiert, jeder andere Wert ("daily"|"weekly"|Altdaten wie "daily_morning"/"daily_evening") = aktiv. Der tatsächliche Rhythmus kommt aus den Slot-Feldern unten.
    PreviousSchedule     string                 `json:"previous_schedule,omitempty"`           // schedule saved before pause (Issue #631, server-managed)
    Profil               string                 `json:"profil"`                                // ActivityProfile: WINTERSPORT|ALPINE_TOURING|SUMMER_TREKKING|ALLGEMEIN
    HourFrom             int                    `json:"hour_from"`                             // @deprecated Issue #1268: nicht mehr vom Dispatch/Editor gelesen; bleibt in der Persistenz zur Bestandssicherung. Neue Presets erhalten 0 (Go Zero-Value). Der Versand rechnet fest über den ganzen Tag (0–23).
    HourTo               int                    `json:"hour_to"`                               // @deprecated Issue #1268: nicht mehr vom Dispatch/Editor gelesen; bleibt in der Persistenz zur Bestandssicherung. Der Versand rechnet fest über den ganzen Tag (0–23).
    ForecastHours        int                    `json:"forecast_hours"`                        // @deprecated Issue #1268: nicht mehr vom Dispatch gelesen; bleibt in der Persistenz zur Bestandssicherung. Der Dispatch verwendet fest 96 h (Issue #1305, zuvor 48 h). Legacy-Erklärung: 24 | 48 | 72 — Vorhersage-Horizont für Compare-Versand (Issue #764, default 48)
    Empfaenger           []string               `json:"empfaenger"`                            // Email addresses for delivery
    LetzterVersand       *time.Time             `json:"letzter_versand,omitempty"`             // last send timestamp (server-managed)
    TopOrtLetzterVersand *string                `json:"top_ort_letzter_versand,omitempty"`     // highest-ranked location from last send (server-managed)
    DisplayConfig        map[string]interface{} `json:"display_config,omitempty"`              // opaque config (Issue #680: active_metrics, ideal_ranges, etc.)
    HourlyEnabled        *bool                  `json:"hourly_enabled,omitempty"`              // Issue #1107, Pointer-Muster analog OfficialAlertsEnabled (#1040): nil/true = Stundenverlauf-Sektion sichtbar (Default), false = komplett weggelassen (Mail behält Übersichtstabelle). Seit Issue #1299 (C2 von Epic #1301) im Hub-Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`) bedienbar — vorher nur über den seit S3 weggeleiteten Legacy-`CompareEditor` erreichbar.
    MorningEnabled       *bool                  `json:"morning_enabled,omitempty"`             // Issue #1232 Scheibe 2a: Zwei-Slot-Zeitplan analog Trip. nil = Altdaten vor Migration (Load-Migration setzt echten Wert), sonst true/false
    MorningTime          *string                `json:"morning_time,omitempty"`                // "HH:MM:SS", Fälligkeits-Check nur auf volle Stunde (Minuten ignoriert, KL-2)
    EveningEnabled       *bool                  `json:"evening_enabled,omitempty"`             // wie MorningEnabled, für den Abend-Slot
    EveningTime          *string                `json:"evening_time,omitempty"`                // "HH:MM:SS"; Abend-Versand zielt auf target_date = morgen (Ankündigungs-Charakter, wie Trip-Abendbriefing)
    EndDate              *string                `json:"end_date,omitempty"`                    // "YYYY-MM-DD", nil = unbegrenzte Laufzeit; gesetzt+<heute (Europe/Vienna) = Versand-Guard greift. Bekannte Lücke: kann per PUT nicht auf nil zurückgesetzt werden (KL-7, Sammel-Issue #1199)
    Corridors            []Corridor             `json:"corridors"`                             // Issue #1231 Slice 1, additiv neben display_config["ideal_ranges"] — s. Section 24
    OfficialAlertTriggersEnabled *bool          `json:"official_alert_triggers_enabled,omitempty"` // @deprecated (Issue #1258, ersetzt durch official_warnings.enabled) — bleibt in den Daten fuer Rollback-Sicherheit
    OfficialWarnings     *OfficialWarningsConfig `json:"official_warnings,omitempty"`           // Issue #1258, identische Semantik wie Trip — s. Section 10.5 „official_warnings (Issue #1258)"
    CreatedAt            time.Time              `json:"created_at"`
}
```

**Invariante — nie `null` (Issue #1244):** `Corridors`, `LocationIDs` und `Empfaenger` sind
immer als `[]` serialisiert, niemals als `null` — Datei und HTTP-Response gleichermaßen.
Durchgesetzt von `NormalizeComparePreset()` (`internal/store/compare_preset.go`), aufgerufen
sowohl aus dem Schreibpfad (`SaveComparePresets`) als auch aus dem Lesepfad
(`LoadComparePresets`) sowie direkt aus dem Handler, wenn ein frisch erstelltes/aktualisiertes
Preset in der HTTP-Response gespiegelt wird. Bestandsdaten: `scripts/migrate_1244_null_lists.py`.

**Hinweis zur Vollständigkeit:** Diese Struct-Auflistung wird nicht bei jeder additiven
Preset-Erweiterung nachgezogen (z.B. `OfficialAlertsEnabled` #1040, `TopNDetails`/`EnabledMetrics`
#1104 fehlen hier aktuell noch) — `HourlyEnabled` (#1107) wurde ergänzt, da
es der unmittelbare Anlass dieser Doku-Aktualisierung war; die fünf Slot-Felder (#1232 Scheibe 2a)
wurden anlässlich des Zeitplan-Reshapes nachgezogen; `display_config["hourly_metrics"]` (#1106)
wurde anlässlich C2 von Epic #1301 in die DisplayConfig-Keys-Liste oben nachgezogen.

**Zwei-Slot-Zeitplan (Issue #1232 Scheibe 2a, additiv zu `schedule`):** Analog zum Trip-Briefing
(Morgen/Abend) trägt `ComparePreset` jetzt einen eigenen Zeitplan statt eines groben
`daily`/`weekly`-Rhythmus. `schedule` bleibt als reines Pause-Flag bestehen (`manual` = pausiert,
via `previous_schedule` reversibel — Issue #631, unverändert). Neue Presets erhalten per Default
`morning_enabled=true, morning_time="07:00:00", evening_enabled=false, evening_time="18:00:00",
end_date=nil`. Bestandspresets ohne diese Felder werden beim ersten Go-`LoadComparePresets`-Lauf
idempotent migriert (Default `morning_enabled=true, morning_time="06:00:00",
evening_enabled=false` — verhaltensidentisch zum vormaligen 06:00-Uhr-Cron; Presets mit dem
Alt-Wert `schedule="daily_evening"` migrieren stattdessen auf einen aktiven Abend-Slot, siehe
Details in `docs/specs/modules/compare_preset_zeitplan.md`). `weekday` gilt als deprecated
(Altdaten-Lesbarkeit, kein neuer Schreibpfad, kein Wochenrhythmus mehr — Presets mit
`schedule="weekly"` versenden seither täglich). Der stündliche Go-Cron `compare_presets_daily`
("Compare Presets Slot-Check (hourly)", vormals einmal täglich 06:00 UTC) prüft pro Preset, ob
die aktuelle Stunde (Europe/Vienna) mit `morning_time`/`evening_time` übereinstimmt; Morgen-Slot
versendet für `target_date=heute`, Abend-Slot für `target_date=morgen`. Guards vor jedem Versand:
`schedule=="manual"` (pausiert), `archived_at` gesetzt, `end_date` gesetzt und `< heute`.

**DisplayConfig Keys (Issue #680 onwards):**
- `active_metrics`: `[]string` — Ausgewählte Metrik-Keys für Vergleich (z.B. `["temp_max_c", "wind_max_kmh", "precip_sum_mm"]`). Default: Profil-spezifische Metriken aus `PROFILE_METRICS_WITH_SCALES`. Seit #1191 im Idealwerte-Tab um 4 weitere, bislang schalter-lose alarmfähige Metriken wählbar: `gust_max_kmh` (Böen), `cape_max_jkg` (Gewitter-Energie/CAPE), `freezing_level_m` (Nullgradgrenze), `temp_min_c` (Min-Temperatur). **Semantik für den Compare-Δ-Alarm (#1191):** Feld fehlt ganz (Key absent/`None`) = Legacy-Preset vor der Migration → konservativer Fallback, alle alarmfähigen Metriken feuern. Feld vorhanden — auch als leere Liste `[]` — = Nutzer hat im Editor bewusst (de-)aktiviert; nur gelistete Metriken feuern im Alarm, eine bewusst leere Liste unterdrückt sämtliche Compare-Δ-Alarme. Übersetzung Summary-Key → Alarm-Katalog-ID: `src/services/compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID`. **Schreiber seit #1311 (C1 von Epic #1301):** Der neue geteilte Hub-Tab „Wetter-Metriken" (`frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `context="vergleich"`) ist jetzt die EXKLUSIVE Schreib-Quelle für `active_metrics`. Das `notify`-Häkchen der Korridore im Wertebereiche-Tab schreibt `active_metrics` seither NICHT mehr (`corridorEditorState.ts::buildCompareCorridorSavePayload`) — es steuert nur noch `metric_alert_levels` (Alarm-Schwelle je Metrik), unverändert. Die Legacy-Semantik (absent = alle alarmfähigen feuern) bleibt davon unberührt.
- `ideal_ranges`: `Record<string, IdealRange>` — Min/Max-Idealwerte pro Metrik (z.B. `{"temp_max_c": {"min": 15, "max": 35}, ...}`). Wird vom Compare-Engine zur Bewertung verwendet.
- `hourly_metrics`: `string[]` — Ausgewählte Metrik-Keys für die STUNDEN-Sektion der Vergleichs-Mail (Katalog: `ALL_HOURLY_METRICS`, 9 Keys, eigenständiges Compare-Vokabular ohne Trip-Pendant, `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts`). Leere Liste `[]`/Key absent = Default „alle sichtbar"; eine Leerauswahl im UI entfernt den Key wieder aus dem PUT-Body statt ihn als `[]` zu senden. **Schreiber seit Issue #1299 (C2 von Epic #1301):** bedienbar im Hub-Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`, `flushPendingLayoutSave`/`hydrateLayoutFieldsFromPreset`/`rollbackLayoutSnapshot` in `compareHubWizardBridge.ts`, Muster wie die C1-Wetter-Metriken-Bridge). Vorher nur über den seit S3 weggeleiteten Legacy-`CompareEditor` (`CompareInhaltSection.svelte`) erreichbar.
- `output_layout`: opaque (zukünftig) — Spalten-Reihenfolge, Formatierung per Kanal
- `schedule_config`: opaque (zukünftig) — Wiederholungs-Details

**Note:** Das Feld `forecast_hours` (24|48|72 h) ist ein Top-Level-Feld von `ComparePreset`, nicht Teil von `display_config` (Issue #764).

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
| `hour_from` | 0–23 — **weiterhin von `validateComparePreset` erzwungen** (`internal/handler/compare_preset.go:120`). @deprecated Issue #1268: nicht mehr vom Editor/Versand gelesen; bestehende Werte in Request-Body werden per RMW-Spread erhalten (Bestandsschutz). Neue Presets erhalten 0 (Go Zero-Value, von der Validierung zugelassen). |
| `hour_to` | 0–23 **und** `hour_to >= hour_from` — **beide Regeln gelten weiter** (`compare_preset.go:123,126`); die API lehnt Verstöße auch nach #1268 ab. @deprecated: nicht mehr vom Editor/Versand gelesen; bestehende Werte per RMW-Spread erhalten. |
| `forecast_hours` | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Dispatch verwendet fest 96 h (Issue #1305, zuvor 48 h). Bestehende Werte werden per RMW-Spread erhalten. Frontend sends dieses Feld nicht mehr mit. |
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
- **forecast_hours (Issue #764, @deprecated #1268):** Vorhersage-Horizont — Legacy-Erklärung: (24|48|72 Stunden) wurde beim Orts-Vergleich-Versand verwendet. **Seit Issue #1268:** Das Feld ist deprecated und wird vom Dispatch nicht mehr gelesen. Der Versand verwendet fest 96 h (Issue #1305, zuvor 48 h — geteilte Konstante `COMPARE_FORECAST_HOURS` in `src/services/comparison_engine.py`). Beim Bearbeiten wird der Wert aus dem Preset nicht mehr hydratisiert und nicht mehr in den Request-Body geschrieben. Die Go-API akzeptiert den Wert bei PUT zum Bestandsschutz (RMW-Spread), schreibt ihn aber nicht selbst. Neue Presets erhalten 0 (Go Zero-Value, keine Editor-Eingabe). Bekannte Limitation #1280 (s. Spec #1268): Versandzeit-Genauigkeit (Minuten vs. Stunden) sichtbar geworden; **PO-Entscheid liegt vor** (2026-07-16: Eingabe auf volle Stunden begrenzen), Umsetzung in #1280.
- **display_config (Issue #680):** Opaque JSON object stored as `map[string]interface{}` (no server-side schema validation). Contains `active_metrics` (persisted Metrik-Auswahl), `ideal_ranges` (Bewertungs-Schwellwerte), und zukünftig `output_layout` + `schedule_config`. Round-Trip beim Update: Server gibt `display_config` unverändert zurück, Frontend reicht nur geänderte Felder. Bestandsfelder erhalten sich automatisch (RMW-Semantik). **Fix #1191:** `CompareAlertService._build_eval_config` reicht `display_config` seither auch in die Δ-Alarm-Auswertung durch (vorher immer `None`, wodurch der #961-Deaktivierungs-Filter für Compare-Presets wirkungslos blieb — analog zum Trip-Pfad in `trip_alert.py`). Migrations-Skript `scripts/migrate_1191_compare_active_metrics.py` setzt auf Bestands-Presets ohne `active_metrics` einmalig den vollen Metrik-Satz (bewahrt „alles feuert", jetzt explizit + abschaltbar).
- **POST /api/compare/presets/{id}/send:** Immediate send endpoint (Issue #627). Executes comparison engine and emails all configured `empfaenger` immediately, regardless of `schedule` value (bypasses time-based gating). If no recipients configured, returns HTTP 400. Returns HTTP 200 with `{"status":"ok","winner":"<top_location>","empfaenger_count":N}` on success. Updates `letzter_versand` and `top_ort_letzter_versand` server-side.
- **previous_schedule Field (Issue #631):** When a preset is paused (`schedule='manual'`), the frontend sets `previous_schedule` to the prior schedule value (`"daily"` or `"weekly"`). On reactivation, `schedule` is restored from `previous_schedule`. This field is preserved across reloads (backend-persistent); altdata without this field remain unaffected (omitempty).
- **LocationIDs Validation:** Backend does not validate that referenced location IDs exist in `data/users/{userID}/locations.json`. Invalid IDs cause errors only during send.
- **official_warnings (Issue #1258):** Identische Semantik wie beim Trip — s. Section 10.5 „official_warnings (Issue #1258)" für Feld-Format, Legacy-Fallback (`official_alert_triggers_enabled`), Migration und PUT-RMW-Verhalten (inkl. Feld-Level-Preserve von `sources`).

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
| hour_from | integer | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Versand rechnet fest über den ganzen Tag (0–23). Bleibt in Bestandsdaten zur Bestandssicherung. Neue Presets erhalten 0. |
| hour_to | integer | @deprecated Issue #1268: nicht mehr vom Versand gelesen; der Versand rechnet fest über den ganzen Tag (0–23). Bleibt in Bestandsdaten zur Bestandssicherung. |
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

## 17) Compare-Presets Daily Dispatch Endpoint (Issue #461, Slot-Zeitplan seit #1232 Scheibe 2a)

**Veraltet (bis #1232 Scheibe 2a):** Dispatch lief einmal täglich um 06:00 UTC und filterte grob
auf `schedule='daily'`. **Aktuell:** Der Go-Cron `compare_presets_daily` läuft **stündlich**
(`0 * * * *`, Job-Beschreibung „Compare Presets Slot-Check (hourly)"); der Python-Endpoint prüft
pro Preset die Zwei-Slot-Felder (`morning_time`/`evening_time`, s. Abschnitt 16) gegen die aktuelle
Stunde (Europe/Vienna) statt eines einzigen festen Filters. `schedule` wirkt nur noch als
Pause-Flag (`manual` = pausiert). Details: `docs/specs/modules/compare_preset_zeitplan.md`.

**Handler:** `api/routers/scheduler.py` (`run_compare_presets_daily`) | **Routing:** `cmd/server/main.go`

### POST /api/scheduler/compare-presets-daily

Prüft für jeden Nutzer alle Compare-Presets auf Slot-Fälligkeit zur aktuellen Stunde
(optionaler Query-Parameter `hour`, Default: aktuelle Stunde Europe/Vienna — Muster
`trigger_trip_reports`). Fällige Presets: Morgen-Slot → Compare Engine mit `target_date=heute`,
Abend-Slot → `target_date=morgen`. Guards vor Versand: `schedule=="manual"` (pausiert),
`archived_at` gesetzt, `end_date` gesetzt und in der Vergangenheit. Rendert/sendet E-Mails,
aktualisiert `letzter_versand` und `top_ort_letzter_versand`.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | no | User identifier (default: "default" for V1) |
| hour | int | no | Stunde [0..23] gegen die Slot-Fälligkeit geprüft wird (Issue #1232 Scheibe 2a, Muster `trigger_trip_reports`). Default: aktuelle Stunde Europe/Vienna. |

**Response 200:**

```json
{
  "status": "ok",
  "count": 2,
  "failed": 0
}
```

Bei mindestens einem fehlgeschlagenen fälligen Preset (seit Issue #1290, identisches Schema zu `/api/scheduler/trip-reports`, Issue #766):

```json
{
  "status": "partial",
  "count": 1,
  "failed": 1
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| status | enum | `"ok"` wenn alle fälligen Presets erfolgreich versendet wurden, `"partial"` sobald `failed > 0` (Issue #1290; HTTP bleibt in beiden Fällen 200) |
| count | int | Anzahl erfolgreich versendeter fälliger Presets (Morgen- oder Abend-Slot), die zur geprüften Stunde fällig waren |
| failed | int | Anzahl fälliger Presets, deren Versand fehlgeschlagen ist (Issue #1290; zuvor nur intern als `error_count` geloggt, jetzt Teil der Response) |

**Internal Behavior (seit Issue #1232 Scheibe 2a):**

1. Load über den zentralen Loader `load_compare_presets()`/`compare_preset_to_dict()` (`src/app/loader.py`, Issue #1250 Scheibe 1, `strict=True`) — liest seit Issue #1250 S7b per-Datei `data/users/{user_id}/briefings/*.json`, invers gefiltert auf `kind == "vergleich"` (partial-tolerant) statt der alten Single-File `compare_presets.json` (nur noch Migrations-Quelle/Rollback) — Rückgabe bleibt dieselbe Dict-Liste wie zuvor (`compare_preset_to_dict()` liefert den unveränderten Roh-Dict je Preset)
2. Für jedes Preset: Guards prüfen — `schedule == "manual"` → skip (pausiert); `archived_at` gesetzt → skip; `end_date` gesetzt und `< heute` (Europe/Vienna) → skip
3. Slot-Werte lesen (Preset ohne Slot-Felder — z. B. weil die Go-Migration die Datei noch nicht neu geschrieben hat — bekommt dieselben Fallback-Defaults wie `LoadComparePresets`); Morgen-Slot fällig wenn `morning_enabled` und `morning_time.hour == hour` (`target_date=heute`), Abend-Slot fällig wenn `evening_enabled` und `evening_time.hour == hour` (`target_date=morgen`)
4. Für jedes fällige Preset:
   - Validate `location_ids` (warn if empty, increment `error_count`)
   - Convert `preset["profil"]` (Uppercase Go string → lowercase Python enum, fallback ALLGEMEIN)
   - Call Compare Engine with `target_date` (s. o.), `forecast_hours=COMPARE_FORECAST_HOURS` (feste geteilte Konstante, 96 h — Issue #1305, zuvor 48 h seit #1268; `preset["forecast_hours"]` wird nicht gelesen), `hour_from`, `hour_to`, `activity_profile`
   - Render Compare-Email template
   - Send via Resend to all `preset["empfaenger"]`
   - Call `_save_preset_status(user_id, preset_id, top_ort)` to update JSON
   - On any error: log warning, increment `error_count`, continue (no job abort)
5. Go scheduler (Cron `0 * * * *`, stündlich statt vormals einmal täglich 06:00 UTC) pingt BetterStack Heartbeat (`GZ_HEARTBEAT_COMPARE_PRESETS`) nur wenn `error_count == 0` (operator-visible success indicator)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 200 | `{"status":"ok","count":0,"failed":0}` | No daily presets found (not an error) |
| 200 | `{"status":"ok","count":2,"failed":0}` | 2 presets processed erfolgreich, keine Fehlschläge |
| 200 | `{"status":"partial","count":1,"failed":1}` | 1 Preset erfolgreich, 1 Preset fehlgeschlagen — HTTP bleibt 200, `status` zeigt `"partial"` (Issue #1290) |

**Side Effects:**

- `data/users/{user_id}/briefings/{id}.json` (kind=vergleich) per-Datei-RMW via `save_compare_preset_status` updated with `letzter_versand` (ISO-datetime UTC) and `top_ort_letzter_versand` (string or null) for each successfully sent preset (unbekannte Felder bleiben erhalten; Issue #1250 S7b — Legacy `compare_presets.json` wird nicht mehr geschrieben)
- Email sent to all recipients in `preset["empfaenger"]`
- Log entries on WARNING for each failed preset

**Notes:**

- Endpoint always returns HTTP 200 regardless of `error_count`; seit Issue #1290 zeigt das `status`-Feld (`"ok"`/`"partial"`) den Fehlerfall aber im Response-Body selbst an (job success daneben weiterhin über Go-Scheduler `recordRun()` getrackt)
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
   - Loads über `load_compare_presets(strict=True)` (Issue #1250 Scheibe 1) — liest seit Issue #1250 S7b per-Datei `data/users/{user_id}/briefings/*.json` mit `kind == "vergleich"` statt der alten Single-File `compare_presets.json` (nur noch Migrations-Quelle/Rollback)
   - Finds preset by `id` (404 if not found)
   - Validates `empfaenger[]` exists and is non-empty; falls back to `mail_to` from user profile (400 if neither)
   - Calls Compare Engine with `target_date=today`, `forecast_hours=COMPARE_FORECAST_HOURS` (feste geteilte Konstante, 96 h — Issue #1305, zuvor 48 h seit #1268; `preset["forecast_hours"]` wird nicht gelesen; uses preset's `hour_from`, `hour_to`, `profil`)
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
- `data/users/{user_id}/briefings/{id}.json` (kind=vergleich) per-Datei-RMW via `save_compare_preset_status` updated with `letzter_versand` (ISO-datetime) and `top_ort_letzter_versand` (location name) — Issue #1250 S7b
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

User registration with username + password + email (HTTP 201 on success, 409 if user exists).

**Request Body:**
```json
{"username": "alice", "password": "geheim123", "email": "alice@example.com"}
```

**Response 201:**
```json
{"id": "alice"}
```

**Validation:**
- `username`: 3–50 characters, alphanumeric + underscore
- `password`: ≥8 characters
- `email`: required (Issue #1226), minimal format check (`strings.Contains(email, "@")` — no `net/mail` parsing, no uniqueness check)

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"validation_error","detail":"..."}` | username/password missing or too short |
| 400 | `{"error":"validation failed"}` | `email` missing/empty |
| 400 | `{"error":"invalid_email"}` | `email` present but without `@` |
| 409 | `{"error":"user_already_exists"}` | User with this ID already registered |

Since Issue #1226, a valid `email` also triggers the existing `dispatchVerificationMail` helper (from #1219) after account creation — same Double-Opt-In flow as profile email changes. Google-OAuth account creation (`createOAuthUser`) and passkey-public account creation (`PasskeyRegisterPublicFinishHandler`) trigger the same dispatch on first-time account creation (not on existing-user login).

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
  "tier": "free",
  "sms_allowed": false,
  "requested_tier": "standard",
  "requested_at": "2026-07-07T14:00:00Z",
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
| tier | string | User's level: `free`/`standard`/`premium` (Issue #1068, Slice 1 of Epic #1067); always present, defaults to `free` if unset on the underlying `user.json` (fallback happens only at read time, never written back); display-only in this slice, no channel or alert-frequency enforcement yet |
| sms_allowed | bool | Whether SMS channel is available for this user (Issue #1069, Slice 2 of Epic #1067); `true` if `tier` is `standard` or `premium`, `false` for `free`; determines server-side channel-gating in report-dispatch and alert-dispatch |
| requested_tier | string | Level change requested by the user via `POST /api/auth/tier-change-request` (Issue #1071, Slice 4 of Epic #1067); `omitempty` — absent/empty if no request is pending. Does not change `tier` itself; only the PO setting `tier` manually clears the pending state (once `requested_tier == tier`, the frontend Pending-hint disappears) |
| requested_at | string (RFC3339) | Timestamp of the pending tier-change request set alongside `requested_tier`; pointer type server-side so it is omitted entirely (not a zero-value timestamp) when no request is pending |
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

#### POST /api/auth/tier-change-request

Requests a level change (Free/Standard/Premium) for the authenticated user (Issue #1071, Slice 4
of Epic #1067). Vermerkt den Antrag per Read-Modify-Write in `user.json`
(`requested_tier`/`requested_at`) und löst eine asynchrone Benachrichtigungsmail an den PO aus
(`PO_EMAIL`/`cfg.PoEmail`). Das effektive `tier`-Feld wird durch diesen Endpoint **nicht**
verändert — Freigabe erfolgt weiterhin manuell durch den PO.

**Request Body:**
```json
{
  "requested_tier": "standard"
}
```

**Response 200:**
```json
{"status": "ok"}
```

**Error Responses:**

| Status | Body | Scenario |
|--------|------|----------|
| 400 | `{"error":"invalid request"}` | JSON not decodable |
| 400 | `{"error":"invalid_tier"}` | `requested_tier` not one of `free`/`standard`/`premium` |
| 400 | `{"error":"already_current_tier"}` | `requested_tier` equals the user's current effective `tier` |
| 404 | `{"error":"not_found"}` | No user found for the authenticated `user_id` |
| 500 | `{"error":"store_error"}` | `SaveUser` failed |
| 401 | (via `AuthMiddleware`) | No valid session cookie or session expired |

**Notes:**
- Mail-Versand ist "fire and forget" (Goroutine + 20s-Timeout, analog `ForgotPasswordHandler`): ein
  fehlschlagender/timeout-behafteter Mailversand oder ein leeres `PO_EMAIL`/`SMTP_HOST` blockiert
  die bereits gesendete `200`-Antwort nicht — der Antrag ist unabhängig vom Mail-Ergebnis
  persistiert.
- Kein Dedup, kein Clear-Endpoint, kein Rate-Limiting über die Session-Auth hinaus — siehe
  `docs/specs/modules/issue_1071_tier_change_request.md` (Known Limitations).

### User Model Extensions

**File:** `internal/model/user.go`

```go
type User struct {
    ID                 string                 `json:"id"`
    Email              string                 `json:"email,omitempty"`
    PasswordHash       string                 `json:"password_hash,omitempty"`  // now optional (omitempty)
    PasskeyCredentials []WebAuthnCredential   `json:"passkey_credentials,omitempty"`  // NEW (Issue #450)
    CreatedAt          time.Time              `json:"created_at"`
    MailTo             string                 `json:"mail_to,omitempty"`
    SmsTo              string                 `json:"sms_to,omitempty"`  // NEW (Issue #609) — SMS recipient phone number
    TelegramChatID     string                 `json:"telegram_chat_id,omitempty"`
    OAuthProvider      string                 `json:"oauth_provider,omitempty"`
    OAuthSub           string                 `json:"oauth_sub,omitempty"`
    DisplayName        string                 `json:"display_name,omitempty"`  // NEW (Issue #642) — user's chosen display name; omitempty if not set
    Tier               string                 `json:"tier,omitempty"`  // NEW (Issue #1068, Slice 1 of Epic #1067) — free/standard/premium; empty defaults to "free" at read time
    RequestedTier      string                 `json:"requested_tier,omitempty"`  // NEW (Issue #1071, Slice 4 of Epic #1067) — pending level-change request
    RequestedAt        *time.Time             `json:"requested_at,omitempty"`  // NEW (Issue #1071) — pointer type: plain time.Time's omitempty doesn't work, would serialize as zero-value "0001-01-01T00:00:00Z" instead of being omitted
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
- Existing `user.json` files without `tier` deserialize with an empty string, treated as `free` at read time only (never written back, no forced rewrite of existing files)
- Existing `user.json` files without `requested_tier`/`requested_at` deserialize cleanly (`omitempty`/`nil` pointer); both fields are absent from the `GET /api/auth/profile` response until the user submits a tier-change request

---

## 20) Preview Endpoints (Issue #189, #483, #1270)

Provides preview rendering of trip reports in Email, SMS, Signal, or Telegram formats. Supports both live weather and fixture-based demo mode. Seit Issue #1270 zusätzlich: EIN Compare-Preview-Endpoint, der alle Kanäle eines Orts-Vergleich-Presets in einer Antwort liefert (s. `POST /api/preview/compare/{preset_id}` unten).

**Handler:** `api/routers/preview.py` | **Routing:** `cmd/server/main.go` (Trip-Routen), `internal/router/router.go:161-167` (Compare-Proxy)

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

Render trip report preview for Telegram channel. Seit Issue #1001 rendert das Backend
das Briefing als mehrere einzelne Nachrichten ("Bubbles": Kopf, Kurzübersicht, je
Segment, Ziel, optional Ausblick, Aktionen) statt einer einzelnen Prosa-Nachricht —
siehe `docs/adr/0014-telegram-multi-bubble-format.md`.

**Query Parameters:** Same as `/email` (type, date, demo)

**Response 200:**

```json
{
  "subject": "...",
  "body": "<alle Bubbles, verbunden mit \"\\n\\n---\\n\\n\">",
  "char_count": 0,
  "max_line_width": 0,
  "bubbles": ["<Bubble 1: Kopf>", "<Bubble 2: Kurzübersicht>", "..."]
}
```

`bubbles` ist additiv seit #1001 (AC-7) — `body` bleibt aus Rückwärtskompatibilität
erhalten und ist die mit `"\n\n---\n\n"` verbundene Kette aller Bubbles. Das dazugehörige
`reply_markup` (Inline-Keyboard der Aktionen-Bubble) ist im Preview-JSON **nicht**
enthalten; es wird ausschließlich beim tatsächlichen Versand über
`TripReport.telegram_actions_markup` an die letzte Nachricht angehängt.

**Error Responses:** Same as `/email`

**Notes:**

- All preview endpoints are **read-only** and do not send messages or modify state
- Preview rendering uses the same Report Formatter and Channel Renderers as the scheduler (integrity guarantee)
- Frontend may call multiple preview endpoints (e.g., email + SMS) to render side-by-side tabs

### POST /api/preview/compare/{preset_id}

Render **alle** Kanäle der Vorschau eines Orts-Vergleich-Presets in **einer**
Antwort (Issue #1270, ADR-0011-Muster — Erweiterung des bestehenden
`alert-preview`-Musters). Bewusste Abweichung von der Trip-Preview-Routenform
oben (eine `GET`-Route je Kanal): ADR-0011 verlangt „die fertig gerenderten
Kanäle über EINEN Backend-Endpunkt"; die Trip-Preview-Routen entstanden vor
ADR-0011 (2026-06-29) und wurden nicht rückwirkend migriert (Nebenbefund,
#1199).

**Handler:** `api/routers/preview.py::preview_compare` — ruft
`src/services/compare_preview_service.py::ComparePreviewService.render_all_channels`
| **Go-Proxy:** `internal/handler/preview_proxy.go::ComparePreviewProxyHandler`
(`router.go:167`)

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| preset_id | string | Compare-Preset-ID |

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | yes | Session-User; vom Go-Proxy aus dem Auth-Kontext injiziert — ein client-seitig mitgeschickter Wert wird verworfen (Anti-Spoofing, ADR-0003) |
| date | string | no | Ziel-Datum ISO-8601 (`YYYY-MM-DD`), Default: heute |

Kein Request-Body erforderlich — der Go-Proxy leitet den Body zwar durch, der
Python-Handler liest ihn nicht.

**Response 200:**

```json
{
  "subject": "...",
  "email_html": "<html>...</html>",
  "telegram": "...",
  "sms": "...",
  "sms_char_count": 137
}
```

| Feld | Type | Description |
|------|------|-------------|
| subject | string | Betreffzeile (`build_compare_preset_subject`) |
| email_html | string | Vollständiges HTML der E-Mail-Vorschau (`render_compare_email`) |
| telegram | string | Fertiger Telegram-Nachrichtentext (`render_compare_telegram`) — kein Score/Rang (#1110) |
| sms | string | Budgetierte SMS-Zeile (`render_compare_sms`, Budget über `CHANNEL_LIMITS`, #360) |
| sms_char_count | integer | `len(sms)` |

**Error Responses:**

| Status | Scenario |
|--------|----------|
| 404 | Preset für diese `user_id` nicht gefunden — auch bei einem Preset, das einem anderen Nutzer gehört (Multi-User-Isolation, AC-6) |
| 422 | fehlende/leere `user_id` (kein `"default"`-Fallback, ADR-0003) · Preset ohne konfigurierte Orte · konfigurierte Orte nicht auflösbar (gelöschte Location-Referenz) · ungültiges `date`-Format |
| 503 | Wetter-Provider nicht erreichbar (`ComparisonEngine.run()` scheitert) |

Der Router mappt `FileNotFoundError`/`LookupError` → 404, `ValueError` → 422,
`RuntimeError` → 503; `detail` enthält den Ausnahme-Text (kein fester
Error-Code wie bei den älteren Trip-Preview-Routen).

**Notes:**

- Read-only wie die anderen Preview-Endpoints — kein Versand, kein
  Logbuch-Eintrag.
- `ComparisonEngine.run()` läuft genau **einmal** je Aufruf; alle drei
  Kanäle sitzen auf demselben `ComparisonResult` (AC-7) — ein Kanalwechsel
  im Vorschau-Tab löst **keinen** weiteren Request aus, daher kein Cache
  nötig.
- Ersetzt fachlich den Validator-Stub
  `POST /api/_validator/compare-email-preview` (#464) als Datenquelle für
  die UI-Vorschau (Stub rendert einen hartcodierten Ort). Der Stub selbst
  bleibt unverändert bestehen — er gehört dem externen Validator.
- Details, Architektur-Begründung (ADR-0011) und AC-Mapping:
  `docs/specs/modules/compare_channel_preview_dispatch.md`.

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
| metric | enum | Gemessene Metrik: WIND_GUST, PRECIPITATION_SUM, TEMPERATURE_MIN/MAX, THUNDER_LEVEL, FREEZING_LEVEL, TEMPERATURE/WIND/PRECIPITATION_CHANGE. `SNOW_LINE` bleibt als toter Enum-Wert nur für Backward-Compat-Deserialisierung alt-persistierter Regeln erhalten (ADR-0019) — nicht mehr wählbar. |
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

## 23) Stage-Weather Internal Endpoint (Issue #1212, Slice R1)

Interner, nicht versionsstabiler Endpoint (Python FastAPI, Port 8000, **kein** Go-Proxy in
diesem Slice). Liefert pro Etappe eine Wetter-Zusammenfassung + Risiko-Ampel, berechnet über
die Python-`RiskEngine` — künftige Single Source of Truth der Cockpit-Risiko-Kacheln
(ADR-0015). Ersetzt die eigene Go-Risk-Logik erst in Slice R2 (dann Proxy).

**Handler:** `api/routers/internal.py` | **Service:** `src/services/stage_weather.py::compute_stage_weather()`

### GET /api/_internal/trips/{trip_id}/stages-weather

**Query-Parameter:** `user_id: str` (Pflicht — kein Fallback auf `"default"`)

**Response 200:**

```json
{
  "results": {
    "<stage_id>": {
      "weather_summary": {
        "temp_min_c": 8.5,
        "temp_max_c": 16.0,
        "wind_max_kmh": 42.0,
        "precip_mm": 3.2,
        "wmo_code": 61,
        "is_day": 1
      },
      "risk": "yellow"
    }
  }
}
```

- Nullbare Felder werden **explizit als `null`** serialisiert (nicht weggelassen).
- Ein Stage-Result ist entweder komplett `null` (Fail-soft, s.u.) oder trägt sowohl
  `weather_summary` (non-null) als auch `risk` (non-null).
- `risk` ∈ `"green"` \| `"yellow"` \| `"red"` — Maximum über alle Segmente der Etappe
  (identisch zur Briefing-Bewertung derselben Segmente, inkl. Wind-Exposition Regel 9).
- Etappen ohne ID (`stage.id == ""`) erscheinen **nicht** als Schlüssel in `results`.
- Etappen ohne Datum/Waypoints oder mit fehlgeschlagenem Wetter-Fetch liefern `null` statt
  eines 5xx (Fail-soft pro Etappe).

### Error Responses

| Status | Body | Szenario |
|--------|------|----------|
| 404 | `{"error":"not_found"}` | `trip_id` für den gegebenen `user_id` nicht gefunden |
| 500 | `{"error":"store_error"}` | Interner Lade-/Store-Fehler |

### Known Limitations

- Ensemble/Confidence (Regel 10) wird bewusst **nicht** gefetcht — farbneutral, siehe
  `docs/specs/modules/stage_weather_python_endpoint.md` Sektion „Known Limitations".
- Latenz-Parität zum alten Go-Handler wird erst in Slice R2 (Proxy live) verifiziert.

**Spec:** `docs/specs/modules/stage_weather_python_endpoint.md`

---

## 24) Corridor DTO (Issue #1231, Slice 1)

**Wertebereiche-Editor:** vereinheitlicht bisherige Trip-Alert-Schwellwerte (`AlertRule`,
Section 22) und Compare-Idealbereiche (`display_config["ideal_ranges"]`, Section 16) auf **einer**
gemeinsamen, rein additiven Datenstruktur. User-facing Label: „Wertebereich(e)"; Code-/Datenterm
bleibt `corridor`. Ein `Corridor` trägt zwei unabhängig kombinierbare Wirkungen: `notify` (warnen,
wenn ein Wert den Bereich verlässt — steuert weiterhin ausschließlich den bestehenden
Δ-Wächter-Mechanismus, `AlertRule`/`metric_alert_levels` bleiben technische Wahrheit) und `mark`
(im Briefing markieren, solange ein Wert im Bereich liegt).

```go
// internal/model/trip.go + internal/model/compare_preset.go (Go)
type Corridor struct {
    Metric string     `json:"metric"`           // kontextabhängige Metrik-ID (route: AlertableMetrics; vergleich: Compare-Summary-Keys)
    Range  [2]*float64 `json:"range"`            // [min, max]; nil-Seite = offen (einseitig erlaubt)
    Notify bool       `json:"notify"`
    Mark   bool       `json:"mark"`
    Prio   string     `json:"prio,omitempty"`    // "hoch" | "mittel" | "niedrig" — nur Anzeige-Reihenfolge, kein Rang/Score
}
```

```python
# src/app/models.py (Python)
@dataclass
class Corridor:
    metric: str
    range: tuple[float | None, float | None]
    notify: bool
    mark: bool
    prio: str | None = None
```

```typescript
// frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts
export interface Corridor {
  metric: string;
  range: [number | null, number | null];
  notify: boolean;
  mark: boolean;
  prio?: "hoch" | "mittel" | "niedrig";
}
```

### Feldliste

| Feld | Typ | Beschreibung |
|------|-----|------------|
| metric | string | Metrik-ID, kontextabhängig: `route` nutzt die 6 `AlertableMetrics` (`wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `thunder_level`, `snow_line`), `vergleich` nutzt die 10 Compare-Summary-Keys (`temp_max_c`, `temp_min_c`, `wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`, `snow_new_sum_cm`, `cape_max_jkg`, `freezing_level_m`). Beide Räume bleiben in Phase 1 getrennt, keine Vereinheitlichung. `confidence_pct` (`selectable=false`, #710) darf in keinem der beiden Pools erscheinen. |
| range | `[min\|null, max\|null]` | Wertebereich; jede Seite unabhängig auf `null` (offen) setzbar, mind. eine Seite muss gesetzt sein (Editor-Validierung, UI-seitig — Slice 3+). `corridorInside(v, min, max)`: `v==null → null`; `v<min → false`; `v>max → false`; sonst `true` (`<`/`>` exklusiv geprüft, Grenzwert exakt gilt als „innen"). |
| notify | bool | Reiner an/aus-Schalter auf den bestehenden Δ-Wächter — **keine neue Trigger-Schwelle**. `true` → `display_config.metric_alert_levels[metric]` wird auf die zuletzt bekannte Stufe zurückgesetzt (Default `"standard"`); `false` → auf `"off"`. Die Stufen-Feinwahl (entspannt/standard/sensibel) ist im CorridorEditor nicht einzeln wählbar (Known Limitation, gespeicherter Wert bleibt erhalten). |
| mark | bool | Markiert im Compare-Mail-Renderer (`compare_html.py`) die Zelle grün, solange `corridorInside(value)===true` — additiv zur bestehenden Severity-Färbung, ohne Einfluss auf `comparison_scoring.py::calculate_score()`. |
| prio | enum \| optional | `"hoch"` \| `"mittel"` \| `"niedrig"` — **nur** Anzeige-Reihenfolge im Editor, kein Rang-/Score-Einfluss. |

### Single-Source-Matchlogik `corridorInside()`

Wortgleich an drei Stellen implementiert (keine Duplikate zulässig):

| Ort | Datei | Zweck |
|---|---|---|
| Frontend-Util | `frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts` | ersetzt `shared/layout-tab/ltIdealRange.ts::isIdealGood()`, Basis für Editor-Live-Vorschau |
| Python-Port | `src/services/corridor_match.py::corridor_inside()` | Compare-Mail-Renderer (`compare_html.py`) |

```js
function corridorInside(value, min, max) {
  if (value == null) return null;               // kein Messwert → neutral
  if (min != null && value < min) return false; // unter dem Korridor
  if (max != null && value > max) return false; // über dem Korridor
  return true;                                  // im Korridor
}
```

### Additivität & Datenerhalt

- **Trip (`internal/model/trip.go`) und ComparePreset (`internal/model/compare_preset.go`):**
  `corridors` steht **additiv neben** `AlertRules` bzw.
  `display_config["ideal_ranges"]` — beide bestehenden Mechanismen bleiben bis zu einem
  späteren, hier nicht enthaltenen Cutover die technische Wahrheit für den Δ-Wächter. Bestandsdaten
  ohne `corridors` laden mit leerem Slice, kein Feldverlust (Read-Modify-Write beim Speichern).
  Seit Issue #1244 gilt das nicht mehr nur beim Speichern, sondern symmetrisch auch beim Laden
  (`LoadTrip`/`LoadTrips`/`LoadComparePresets`) — s. Invarianten-Hinweis in Section 10.5 und 16.
- **Loader-Normalisierung (`src/app/loader.py`):** ein malformed `range` macht nie den Trip
  unladbar — defensiver Float-Cast, `isfinite`-Prüfung, Skalar/`null`/Kurz-Array-Eingaben werden
  still auf `[None, None]` normalisiert statt einer Exception.
- **Migration (`scripts/migrate_1231_corridors.py`, Slice 2):** überführt Bestands-`AlertRule`s
  nach `corridors[notify]` und Compare-`ideal_ranges` nach `corridors[mark]`, verlustfrei
  (Report `alt → neu` je Eintrag), respektiert #1191-Erhalt (`active_metrics: []` bleibt leer).

**Spec:** `docs/specs/modules/issue_1231_korridor_editor.md`

---

## Changelog

- 2026-07-18: Issue #1290 (E1 von Epic #1301, ergänzend #1288/E2) —
  `POST /api/scheduler/compare-presets-daily` liefert jetzt `failed` als neues
  Response-Feld, identisches Schema zu `/api/scheduler/trip-reports` (Issue
  #766): `status` wird `"partial"` sobald `failed > 0`, `count` zählt weiterhin
  nur erfolgreich versendete fällige Presets. `run_compare_presets_daily`/
  `CompareDispatchStrategy.result()` liefern dafür `tuple[int, int]`
  (sent, failed) statt der bisherigen internen `error_count`-Zählung ohne
  Response-Sichtbarkeit. HTTP-Statuscode bleibt immer 200.
- 2026-07-18: Issue #1299/#1291/#1287 (Scheibe C2 von Epic #1301) —
  `display_config.hourly_metrics`/`hourly_enabled` sind jetzt im Hub-
  Layout-Tab (`CompareTabs.svelte`, `activeTab==="layout"`) bedienbar,
  vorher nur über den seit Scheibe S3 weggeleiteten Legacy-`CompareEditor`
  erreichbar. Neue reine Persist-Bridge-Funktionen
  `hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/
  `rollbackLayoutSnapshot` in `compareHubWizardBridge.ts`, Muster wie die
  C1-Wetter-Metriken-Bridge (Issue #1311). `top_n` und die
  „Spalte/Detail"-Zuordnung (`channel_layouts`) sind aus der Bedienung
  entfernt (Attrappen, #1287/#1291), round-trippen aber unverändert weiter
  (kein Feldverlust, Read-Modify-Write). Kein neues Wire-Format-Feld —
  beide Felder existierten bereits (#1106/#1107), nur der Schreib-Zugang
  ändert sich. Siehe `docs/specs/modules/compare_hub_hourly_metrics.md`.
- 2026-07-16: Issue #1278 + #1285 (eine Arbeit, gemeinsame Datenbasis) —
  Vergleichs-Mail bekommt je Ort einen Kurz-Zusammenfassungssatz (geteilter
  Trip-Baustein, kein Compare-eigener Formatierungscode) und fünf bisher
  still verworfene Tages-Aggregate werden repariert. **`LocationResult`**
  (`src/app/user.py:117`, rein transientes Objekt, keine Persistenz) bekommt
  fünf neue, **additive optionale Felder mit Default `None`**:
  `precip_sum_mm: float|None`, `thunder_level_max: ThunderLevel|None`,
  `visibility_min_m: int|None`, `uv_index_max: float|None`,
  `pop_max_pct: int|None`. Bestehende Konstruktoren ohne diese Keyword-
  Argumente (`dict_to_comparison_result()`, `validator_render_service.py`)
  funktionieren unverändert; der Renderer leitet den Wert dann live aus
  `hourly_data` ab. `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
  bekommt fünf neue Einträge (`precip_sum_mm`, `thunder_level_max`,
  `visibility_min_m`, `uv_index_max`, `pop_max_pct`) — vorher wurden diese
  Metriken bei der Matrix-Auswahl still verworfen. Neues additives Frontend:
  eine Katalog-Zeile `pop_max_pct` (Regenwahrscheinlichkeit) in
  `frontend/src/lib/components/compare/compareMetricDefs.ts::ALL_METRICS`
  (kein neues UI-Element, nur ein Datensatz mehr in einer bestehenden Liste).
  Nebenbefund mitgefixt: der Kopf der STUNDEN-Sektion in der Vergleichs-Mail
  (`compare_html.py`) zeigte fest verdrahtet "09–16 Uhr" — ein toter Rest des
  mit #1268 abgeschafften Zeitfensters, jetzt entfernt. Kein Wire-Format-
  Impact auf Go/TS (`ComparisonResult`/`LocationResult`-DTOs sind reine
  Python-interne Render-Objekte, nicht Teil der Go-/REST-Schicht). Siehe
  `docs/specs/modules/compare_location_summary.md` und
  `docs/specs/modules/compact_summary.md`.
- 2026-07-16: Issue #1270 — Echte Kanal-Vorschau + tatsächlicher Telegram/SMS-Versand
  für den Orts-Vergleich. Neuer Endpoint `POST /api/preview/compare/{preset_id}`
  (`api/routers/preview.py`, Go-Proxy `internal/handler/preview_proxy.go::ComparePreviewProxyHandler`,
  `router.go:167`) liefert `{subject, email_html, telegram, sms, sms_char_count}` aus
  **einem** `ComparisonEngine.run()` — ADR-0011-Muster, bewusst EINE Route statt der
  Drei-Routen-Form der älteren Trip-Preview-Endpoints (die vor ADR-0011 entstanden).
  Neuer `src/services/compare_preview_service.py::ComparePreviewService` lädt Preset +
  echte Orte des Nutzers (ersetzt den Stub-Ort aus dem Validator-Endpoint #464 als
  Datenquelle der UI-Vorschau; der Stub selbst bleibt unverändert). Neue Renderer
  `render_compare_telegram`/`render_compare_sms` (`src/output/renderers/comparison.py`,
  kein Score/Rang, Budget über `CHANNEL_LIMITS`). Verhaltensänderung: Compare-Briefings
  waren bis dahin Ende-zu-Ende E-Mail-only (`send_telegram`/`send_sms` wurden
  gespeichert, aber beim Versand nie gelesen) — jetzt sendet
  `NotificationService.send_compare_report(...)` tatsächlich über Telegram/SMS, mit
  Kanal-Gate (Opt-in UND `can_send_*()` UND `sms_allowed()`) und Fail-soft je Kanal;
  `send_one_compare_preset` ist darauf umgehängt. Der Alarm-Pfad
  (`compare_alert.py`/`compare_radar_alert.py`) bleibt unverändert E-Mail-only.
  Bugfix nebenbei: `presetChannels()` (`subscriptionHelpers.ts`) liest jetzt
  `send_telegram`/`send_sms` statt `display_config.channel_layouts`-Keys. Siehe
  Section 20 und `docs/specs/modules/compare_channel_preview_dispatch.md`.
- 2026-07-13: Issue #1250 (Scheibe 1) — die 5 rohen `json.loads`-Lese-Call-Sites für
  `compare_presets.json` (3 Compare-Alert-Services, Scheduler-Dispatch Daily und
  Einzelversand) laufen jetzt über den zentralen Loader `load_compare_presets()` /
  `compare_preset_from_dict()` / `compare_preset_to_dict()` (`src/app/loader.py`, neue
  `ComparePreset`-Dataclass in `src/app/models.py`). Reiner Lese-Kontrakt ohne
  Normalisierung; Rückgabe (Dict-Liste) bleibt für bestehende Konsumenten unverändert.
  Der Schreibpfad (`save_compare_preset_status`) bleibt unverändert Dict-basiert. Kein
  API-/Schema-/Verhaltens-Change. Siehe Abschnitte 17 und 18.
- 2026-07-13: Issue #1244 — Null-Listenfelder brechen den Trip-Loader: `Trip.Stages`,
  `Stage.Waypoints`, `Trip.AlertRules`, `Trip.Corridors` sowie `ComparePreset.Corridors`/
  `LocationIDs`/`Empfaenger` sind jetzt **immer** `[]`, nie `null` — durchgesetzt in beide
  Richtungen (Schreiben UND Lesen, inkl. HTTP-Response) via `normalizeTrip()`
  (`internal/store/trip.go`) und `NormalizeComparePreset()` (`internal/store/compare_preset.go`).
  `SaveTrip` nimmt seit diesem Fix einen Pointer statt eines Value-Receivers, damit der Aufrufer
  die normalisierten Werte sieht. Python-Loader (`src/app/loader.py`) heilt `null` zusätzlich
  fail-soft beim Lesen (`data.get("x") or []`); `load_all_trips()` loggt einen nicht ladbaren
  Trip jetzt als `ERROR` statt `warning`. Bestandsdaten-Migration:
  `scripts/migrate_1244_null_lists.py` (Dry-Run-Default, `--execute`, tar.gz-Backup, idempotent).
  Erweitert die bisherige AlertRules-only-Coercion aus Issue #205. Siehe
  `docs/specs/modules/fix_1244_null_list_fields.md`.
- 2026-07-12: Issue #1231 (Slice 1 von Epic #29 „Briefing-Abo-Chassis") — neues additives
  Datenmodell `Corridor{metric, range:[min|null,max|null], notify, mark, prio?}` an
  `Trip.Corridors` (Go) und `ComparePreset.Corridors` (Go), Python-Pendant in
  `src/app/models.py`. Vereinheitlicht künftig Trip-Alert-Schwellwerte und Compare-Idealbereiche
  hinter einem gemeinsamen Editor (Slices 3–7, folgen), ohne den bestehenden Δ-Wächter
  (`AlertRule`/`metric_alert_levels`) zu verändern — rein additiv. Single-Source-Matchlogik
  `corridorInside()` in Python (`src/services/corridor_match.py`) und TS
  (`frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts`). Loader normalisiert malformed
  `range` defensiv (nie trip-unladbar). Siehe Section 24 und
  `docs/specs/modules/issue_1231_korridor_editor.md`.
- 2026-07-11: Issue #1226 — `POST /api/auth/register` bekommt neues Pflichtfeld `email`
  (minimale `strings.Contains(email, "@")`-Prüfung, kein Uniqueness-Check); neue
  Fehlerantworten `validation failed` (fehlend) und `invalid_email` (kein `@`). Bei
  gültiger Adresse wird nach Kontoanlage der bestehende Verifikations-Dispatch
  `dispatchVerificationMail` (aus #1219) ausgelöst — analog dazu jetzt auch bei
  Google-OAuth-Erstanmeldung (`createOAuthUser`) und Passkey-Public-Registrierung
  (`PasskeyRegisterPublicFinishHandler`), nicht mehr nur bei Profil-E-Mail-Änderungen.
  Kein Dispatch bei OAuth-Login eines bestehenden Nutzers. Siehe
  `docs/specs/modules/fix_1226_register_verify.md`.
- 2026-07-10: Issue #1212 (Slice R1) — neuer interner Endpoint `GET
  /api/_internal/trips/{trip_id}/stages-weather` (`api/routers/internal.py`,
  `src/services/stage_weather.py::compute_stage_weather()`): liefert pro Etappe
  Wetter-Zusammenfassung + Risiko-Ampel (green/yellow/red) über die Python-`RiskEngine`,
  künftige SSoT der Cockpit-Risiko-Kacheln (ADR-0015). Ersetzt die Go-Risk-Logik erst in
  Slice R2 (dann Proxy); R1 ist rein additiv, kein Go/Frontend-Impact. Siehe Section 23 und
  `docs/specs/modules/stage_weather_python_endpoint.md`.
- 2026-07-08: Issue #1110 — Ortsvergleich-Mail v2: Die HTML-/Klartext-Darstellung der
  Compare-E-Mail (`compare_html.py::render_compare_html()`) zeigt keinen Score/Winner mehr —
  Winner-Box, Score-Badge und Winner-Tags (eingeführt in #253/#460) entfallen vollständig,
  ersetzt durch eine Übersichtstabelle (Metriken × Orte, inkl. Zeile „Amtliche Warnungen") und
  Stundentabellen für alle Orte (alphabetisch sortiert). Betrifft ausschließlich die
  Mail-Darstellung: `ComparisonResult`/`LocationResult`-DTOs selbst sind unverändert
  (`.winner`/`.score` bleiben im Modell und in der App-Anzeige erhalten, siehe Section 18
  oben — der `winner`-Response-Wert bei `POST /api/scheduler/compare-presets/{id}/send` ist
  von diesem Issue nicht betroffen). Der Observability-Endpoint aus Issue #464
  (`POST /api/_validator/compare-email-preview`) nimmt das Request-Feld `winner_tags`
  weiterhin an, ignoriert es aber (Parameter im Renderer entfernt; Body-Schema
  unverändert für Abwärtskompatibilität). Siehe `docs/specs/modules/issue_1110_compare_mail_v2.md`
  (löst `docs/specs/modules/issue_253_compare_email.md` und
  `docs/specs/modules/issue_460_compare_email_template.md` ab, beide als `status: superseded`
  markiert).
- 2026-07-07: Issue #1071 (Slice 4 aus Epic #1067 Nutzerlevel Free/Standard/Premium, letztes
  Slice — Epic damit VOLLSTÄNDIG) — neuer Endpoint `POST /api/auth/tier-change-request` für
  Level-Änderungs-Anträge; `GET /api/auth/profile` liefert zusätzlich `requested_tier`/
  `requested_at` (beide `omitempty`, `requested_at` serverseitig Pointer-Typ). Antrag wird per
  Read-Modify-Write in `user.json` vermerkt und löst eine asynchrone Mail an `PO_EMAIL` aus; das
  effektive `tier`-Feld ändert sich dadurch nicht. Siehe
  `docs/specs/modules/issue_1071_tier_change_request.md`.
- 2026-07-07: Issue #1068 (Slice 1 aus Epic #1067 Nutzerlevel Free/Standard/Premium) — `GET
  /api/auth/profile` liefert neu ein Feld `tier` (`free`/`standard`/`premium`, immer vorhanden,
  Default `free` falls im `user.json` nicht gesetzt, Fallback nur beim Lesen, kein Rückschreiben).
  Reine Anzeige (Badge im Account-Bereich), kein Channel-Gating, keine Alert-Frequenz-Logik in
  diesem Slice. Siehe `docs/specs/modules/issue_1068_tier_model_display.md`.
- 2026-07-03: Issue #1004 — SSoT-Fix Segment-Startzeit (Re-Fix von #995 Gruppe A, verworfener
  Flag-Ansatz): das nie persistierte `Waypoint.time_window_origin` (siehe Eintrag #995 unten)
  wird ersatzlos entfernt. Es gibt genau EINE massgebliche Startzeit pro Etappe —
  `stage.start_time` — die neue Kette in `convert_trip_to_segments()` ist
  `arrival_override` > `stage.start_time` (Segment 1) > `arrival_calculated` (Naismith) >
  Default 08:00; `time_window` fliegt komplett aus dem Vergleich (bleibt nur Roundtrip-Feld),
  gilt sofort für ALLE Trips inkl. Bestand ohne Migration. Kein Wire-Format-Impact. See
  `docs/specs/modules/issue_1004_startzeit_ssot.md`.
- 2026-07-03: Issue #1001 — Telegram-Ausgabe neu gebaut (Multi-Bubble-Format): `GET
  /api/preview/{trip_id}/telegram` liefert zusätzlich `bubbles: list[str]` neben dem
  bestehenden `body`-Feld (additiv, rückwärtskompatibel — `body` bleibt die mit
  `"\n\n---\n\n"` verbundene Kette aller Bubbles). Betrifft nur den Telegram-Kanal;
  E-Mail/SMS-Preview unverändert. Siehe `docs/adr/0014-telegram-multi-bubble-format.md`
  und `docs/specs/modules/feat_1001_telegram_redesign.md`.
- 2026-07-03: Issue #995 — E-Mail-Fehler-Bündel: (A) neues Python-internes Feld
  `Waypoint.time_window_origin` (`src/app/trip.py`, Werte `"imported"`/`None`≈"manual") —
  ein GPX-importiertes `time_window` verliert in `convert_trip_to_segments()` seinen Vorrang
  vor einer nachträglich geänderten `stage.start_time`; kein Wire-Format-Feld, kein Go/TS-DTO-
  Impact (siehe Abschnitt „Waypoint DTO"); (B) HTML-Mail-Zellhintergrund jetzt direkt inline auf
  `<td>` statt Span/Negativ-Margin-Trick (`html.py`), keine DTO-Änderung; (C) Python liest jetzt
  auch `Trip.paused_at` (`src/app/loader.py`, Read-Modify-Write analog `archived_at`/#805) und
  `trip_report_scheduler.py::_get_active_trips()` überspringt pausierte Trips beim automatischen
  Versand — das Go-Feld `PausedAt` selbst war bereits seit Issue #153 Teil des Trip-DTOs (siehe
  oben), neu ist nur die Python-seitige Auswertung. Manueller Test-Versand und Alert-Dispatch
  bleiben unberührt. See `docs/specs/modules/issue_995_mail_bugs_bundle.md`.
- 2026-06-11: Issue #733 — Briefing-Mail-Validator (Marker-Headers + Plausibilität-Gate): `build_mime_message()` erweitert um optionale Parameter `mail_type` / `mail_format` (setzen `X-GZ-Mail-Type` / `X-GZ-Format` Header additiv, rückwärts-kompatibel). Scheduler + CLI taggen ausgehende Mails deterministisch: `trip-briefing/full|compact` (Briefing) vs. `compare/full` (Orts-Vergleich). Neuer Validator `.claude/hooks/briefing_mail_validator.py`: dispatcht auf Header, prüft **Trip-Briefing-Mails format-spezifisch auf Plausibilität** (full: multipart/alternative, HTML+Plain, ≥1 Stundentabelle, Werte self-konsistent; compact: single text/plain, 7bit, isascii, <2 KB, keine Stundentabelle). Compare-Mails bekommen No-Op-Klassifikation (Exit 0). Marker-Header ermöglichen deterministische Routing zu kanonischen Validatoren: `email_spec_validator.py` (Orts-Vergleich, fest auf Winner-Box verdrahtet) / `briefing_mail_validator.py` (Briefing). CLAUDE.md Sektion „BRIEFING-MAIL-VALIDATOR" dokumentiert Pflicht-Gate + Scope-Trennung. Siehe `docs/reference/renderer_email_spec.md` Sektion „Marker Headers and Validation Routing" und `docs/specs/modules/briefing_mail_validator.md`.
- 2026-06-11: Issue #722 [#709 Slice 2] — E-Mail-Format Kompakt (Nur-Text, minimal-Byte): Neuer Format-Schalter `TripReportConfig.email_format: 'full' | 'compact'` (default `'full'`). `'full'` = bestehende multipart-HTML-Mail mit stündlichen Werte-Tabellen (byte-identisch unverändert). `'compact'` = reine `text/plain`-Mail (single part, kein HTML, kein multipart), reines ASCII (7bit-CTE), mit fix nur Kopf + Metriken-Überblick + Ausblick + Footer (ohne Baustein-Toggles), ~95% kleiner (~1 KB für Wanderer mit schlechter Konnektivität). Backend: neuer isolierter `render_compact()`-Renderer (`src/output/renderers/email/compact.py`, ~50 LoC), `build_mime_message()` extrahiert (`html=False` → `us-ascii`/7bit), Scheduler leitet Email-Format durch. Frontend: Format-Schalter in `EditReportConfigSection.svelte`, Baustein-Gruppe bei compact deaktiviert (UI-Hinweis). Go-Modell `ReportConfig` Passthrough (no changes). Tests: Backend E2E gegen Staging (AC-1–5 Multipart-Strukturverifizierung + ASCII-Validierung + Baustein-Ignorance), Playwright E2E (AC-6 UI-Persistenz), Multi-User (AC-7). See `docs/specs/modules/issue_722_email_compact_format.md`.
- 2026-06-10: Issue #702 — Alerts-Tab Mobile-Parität TM2 (Frontend CSS-only, Epic #700 Slice 2/2): `AlertsTab.svelte`, `AlertCard.svelte`, `AlertCooldownCard.svelte`, `AlertQuietHoursCard.svelte` mit `@media (max-width: 899px)` Breakpoint-spezifischen Touch-Target-Sizing: Channel-Chips ≥36px Höhe, Threshold-Input ≥120px breit, Cooldown/Time-Inputs ≥44px Höhe + 16px font-size (verhindert iOS-Auto-Zoom). Desktop Layout bleibt byte-identisch. `.actions`-Bar auf mobil ausgeblendet, Mobile-Footer-Button sichtbar (bestehend). Keine API/DTO-Änderungen. Tests: Playwright E2E gegen Staging @375px Viewport (AC-1/AC-2/AC-3/AC-5 Touch-Targets, AC-4 Desktop-Regression). See `docs/specs/modules/issue_702_alerts_mobile_parity.md`.
- 2026-06-10: Issue #721 (Slice 1 von #709) — E-Mail-Ausblick verschmolzen: neues additives Feld `TripReportConfig.show_outlook` (bool, default true). Verschmilzt Großwetterlage (als Kopf), Tabelle der nächsten Etappen mit Uhrzeiten (`format_trend_tokens`, #640) und neuer Vorhersage-Sicherheit pro Etappe (`confidence_pct` aus `SegmentWeatherSummary.confidence_pct_min`, propagiert über `_build_stage_trend`) zu **einem** Ausblick-Block. `show_outlook=false` blendet den gesamten Block in HTML **und** Plain-Text aus (Großwetterlage zusätzlich an `show_stability` gekoppelt; fehlt `confidence_pct`, entfällt nur die Prozentangabe — kein „0%"). Altfelder (`show_stability`/`show_compact_summary`/`show_highlights`) bleiben erhalten (kein Schema-Removal). UI-Schalter folgt in Slice 3 (#723). See `docs/specs/modules/issue_721_email_outlook.md`.
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

---

## Backend Services

Diese Sektion dokumentiert interne Service-Klassen, die nicht über REST-Endpoints verfügbar sind.

### WeatherSnapshotService — Dated Snapshot Storage (Issue #747)

**Pfad:** `src/services/weather_snapshot.py`

**Purpose:** Erweitert den bestehenden `WeatherSnapshotService` um datiertes Speichern und Laden von Wetter-Snapshots. Ermöglicht Abruf der gestrigen Vorhersage für Vortag-Vergleich im Trip-Briefing.

**Datei-Schema:**
- **Bestehend (Alert-Nutzung, unverändert):** `data/users/<user_id>/snapshots/{trip_id}.json`
- **Neu (datiert):** `data/users/<user_id>/snapshots/{trip_id}_{YYYY-MM-DD}.json`

**Methoden:**

| Methode | Signatur | Verhalten |
|---------|----------|----------|
| `save_dated()` | `(trip_id: str, target_date: date, segments: List[SegmentWeatherData]) → None` | Schreibt datierte Kopie zu `{trip_id}_{YYYY-MM-DD}.json`. Ruft intern `_prune_dated_snapshots()` auf. Fehler werden geloggt, nicht geworfen. |
| `load_dated()` | `(trip_id: str, target_date: date) → Optional[List[SegmentWeatherData]]` | Lädt datierte Snapshot-Datei für den angegebenen Tag. Gibt `None` zurück wenn Datei nicht vorhanden (kein Absturz). Deserialisialisiert `SegmentWeatherData` mit Enum-Rekonstruktion. |
| `_prune_dated_snapshots()` | `(trip_id: str) → None` | Löscht älteste datierte Snapshots für diesen Trip, behält maximal 7 (mtime-sortiert). Fehler beim Löschen werden geloggt. |
| `save()` | _(bestehend, unverändert)_ | Speichert auf `{trip_id}.json` für Alert-Pfad. Byte-identisch vor/nach Issue #747. |
| `load()` | _(bestehend, unverändert)_ | Lädt von `{trip_id}.json` für Alert-Pfad. Byte-identisch vor/nach Issue #747. |

**Retention-Policy:**

Beim Aufruf von `save_dated()`:
1. Snapshot wird geschrieben
2. `_prune_dated_snapshots()` wird aufgerufen
3. Alle Dateien `{trip_id}_*.json` werden nach `mtime` sortiert
4. Nur die 7 jüngsten Dateien bleiben, älter werden gelöscht
5. Fehler beim Löschen (OSError) werden geloggt, brechen nicht ab

**Integration:**

`trip_report_scheduler.py` ruft nach bestehendem `save()`-Aufruf zusätzlich `save_dated()` auf:
```python
_snapshot_svc = WeatherSnapshotService(self._user_id)
_snapshot_svc.save(trip_id, segment_weather, target_date)        # bestehend
_snapshot_svc.save_dated(trip_id, target_date, segment_weather)  # neu, Issue #747
```

**User-Isolation:**

`WeatherSnapshotService.__init__(user_id)` empfängt `user_id` aus Auth-Kontext. Snapshots pro Nutzer isoliert unter `data/users/<user_id>/snapshots/`.

**Backward Compatibility:**

- Bestehende `save()`-/`load()`-Methoden sind byte-identisch
- Alert-Pfad (`trip_alert.py`) nutzt nur `save()`/`load()` — keine Verhaltensänderung
- Bestandsdaten in `{trip_id}.json` bleiben unverändert
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
