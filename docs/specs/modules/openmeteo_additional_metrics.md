---
entity_id: openmeteo_additional_metrics
type: module
created: 2026-02-12
updated: 2026-02-12
status: draft
version: "1.0"
tags: [openmeteo, provider, metrics, catalog]
---

# OpenMeteo: Zusaetzliche Metriken

## Approval

- [x] Approved

## Purpose

Der OpenMeteo-Provider setzt 4 verfuegbare API-Parameter auf `None`, obwohl die Daten abrufbar sind. Die entsprechenden `ForecastDataPoint`-Felder existieren bereits, werden aber nicht befuellt. Dieses Ticket aktiviert sie und registriert sie im MetricCatalog, damit sie automatisch in der Weather Config UI und in Reports erscheinen.

**Problem:** `visibility_m`, `pop_pct`, `cape_jkg`, `freezing_level_m` sind in `ForecastDataPoint` definiert, werden aber im OpenMeteo-Provider (Zeilen 295-313) explizit auf `None` gesetzt mit dem falschen Kommentar "Not available".

**UV-Index:** Nur als Tageswert (`uv_index_max`) bei OpenMeteo verfuegbar, nicht stuendlich. Wird daher **nicht** in diesem Ticket implementiert (separates Ticket fuer Daily-Metriken).

## Source

- **Files:**
  - `src/providers/openmeteo.py` (MODIFY) - 4 Parameter hinzufuegen + Mapping
  - `src/app/metric_catalog.py` (MODIFY) - 4 MetricDefinition-Eintraege
  - `src/app/models.py` (KEINE Aenderung - Felder existieren bereits)

## Dependencies

### Upstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint` | DTO | Felder `visibility_m`, `pop_pct`, `cape_jkg`, `freezing_level_m` existieren bereits |
| `MetricCatalog` | Registry | Registrierung neuer Metriken |
| OpenMeteo API | External | Stellt die Daten bereit |

### Downstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Weather Config Dialog | WebUI | Zeigt neue Metriken automatisch (kataloggesteuert) |
| TripReportFormatter | Service | Rendert neue Spalten automatisch (`_dp_to_row` nutzt MetricCatalog) |
| SMS Formatter | Service | Nutzt `compact_label` fuer neue Metriken |

## Implementation Details

### 1. OpenMeteo Provider: HOURLY_PARAMS erweitern

**Datei:** `src/providers/openmeteo.py`, Zeilen 353-368

**Aktuelle HOURLY_PARAMS (14 Parameter):**
```
temperature_2m, apparent_temperature, relative_humidity_2m, dewpoint_2m,
pressure_msl, cloud_cover, cloud_cover_low, cloud_cover_mid, cloud_cover_high,
wind_speed_10m, wind_direction_10m, wind_gusts_10m, precipitation, weather_code
```

**Neue Parameter (4 hinzufuegen):**
```
visibility, precipitation_probability, cape, freezing_level_height
```

### 2. OpenMeteo Provider: Parsing erweitern

**Datei:** `src/providers/openmeteo.py`, Zeilen 283-314 (`_parse_response`)

**Aenderungen:**

```python
# ALT (Zeile 295-296):
cape_jkg=None,                    # Not available
pop_pct=None,                     # Not available

# NEU:
cape_jkg=get_val(hourly, "cape", i),
pop_pct=get_val(hourly, "precipitation_probability", i),

# ALT (Zeile 311):
freezing_level_m=None,

# NEU:
freezing_level_m=get_val(hourly, "freezing_level_height", i),

# ALT (Zeile 313):
visibility_m=None,

# NEU:
visibility_m=get_val(hourly, "visibility", i),
```

### 3. MetricCatalog: 4 neue MetricDefinitions

**Datei:** `src/app/metric_catalog.py`

**Einfuegen nach `pressure` (Zeile 145), vor `snow_depth`:**

```python
MetricDefinition(
    id="visibility", label_de="Sichtweite", unit="m",
    dp_field="visibility_m", category="atmosphere",
    default_aggregations=("min",),
    compact_label="V", col_key="visibility", col_label="Vis",
    providers={"openmeteo": True, "geosphere": False},
    default_enabled=False,
),
MetricDefinition(
    id="rain_probability", label_de="Regenwahrscheinlichkeit", unit="%",
    dp_field="pop_pct", category="precipitation",
    default_aggregations=("max",),
    compact_label="P%", col_key="pop", col_label="Pop",
    providers={"openmeteo": True, "geosphere": False},
    default_enabled=False,
),
MetricDefinition(
    id="cape", label_de="Gewitterenergie (CAPE)", unit="J/kg",
    dp_field="cape_jkg", category="precipitation",
    default_aggregations=("max",),
    compact_label="CE", col_key="cape", col_label="CAPE",
    providers={"openmeteo": True, "geosphere": False},
    default_enabled=False,
),
MetricDefinition(
    id="freezing_level", label_de="Nullgradgrenze", unit="m",
    dp_field="freezing_level_m", category="winter",
    default_aggregations=("min", "max"),
    compact_label="0G", col_key="freeze_lvl", col_label="0Gr",
    providers={"openmeteo": True, "geosphere": False},
    default_enabled=False,
),
```

### 4. Keine Aenderungen noetig

- **models.py:** Felder existieren bereits (`visibility_m`, `pop_pct`, `cape_jkg`, `freezing_level_m`)
- **trip_report.py:** `_dp_to_row()` nutzt MetricCatalog-Lookup, neue Metriken erscheinen automatisch
- **weather_config.py:** Dialog liest aus MetricCatalog, neue Metriken erscheinen automatisch
- **loader.py:** Keine Aenderung - Serialisierung nutzt MetricConfig mit metric_id

### 5. Kategorien-Zuordnung

| Neue Metrik | Kategorie | Begruendung |
|-------------|-----------|-------------|
| Sichtweite | atmosphere | Atmosphaerische Bedingung |
| Regenwahrscheinlichkeit | precipitation | Niederschlags-Indikator |
| CAPE | precipitation | Gewitter-Energiepotenzial |
| Nullgradgrenze | winter | Winter/Schnee-relevant |

### 6. Default-Werte

Alle 4 neuen Metriken: `default_enabled=False` - sie erscheinen in der Weather Config UI, sind aber nicht standardmaessig aktiviert. User koennen sie manuell einschalten.

## Expected Behavior

### Neue Metriken in Weather Config UI
- **Given:** Trip mit OpenMeteo-Provider
- **When:** Weather Config Dialog oeffnen
- **Then:** 4 neue Metriken sichtbar (unchecked), koennen aktiviert werden

### Metriken in Reports
- **Given:** Trip mit aktivierter Sichtweite und Regenwahrscheinlichkeit
- **When:** Report generiert
- **Then:** Spalten "Vis" und "Pop" erscheinen in Email-Tabelle

### Provider-Verfuegbarkeit
- **Given:** Trip nur mit GeoSphere-Provider (Oesterreich)
- **When:** Weather Config Dialog oeffnen
- **Then:** Alle 4 neuen Metriken ausgegraut (nur OpenMeteo verfuegbar)

### CAPE-Werte
- **Given:** OpenMeteo liefert CAPE-Daten
- **When:** CAPE > 0 in Forecast
- **Then:** Wert in J/kg in der Tabelle, Aggregation=Max

## Files to Change

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/providers/openmeteo.py` | MODIFY | ~15 |
| 2 | `src/app/metric_catalog.py` | MODIFY | ~40 |

**Total:** ~55 LoC, 2 Dateien

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| API-Antwort ohne neue Felder | LOW | `get_val()` gibt `None` zurueck bei fehlendem Feld |
| Sichtweite in Metern statt km | LOW | Unit "m" korrekt, Formatter zeigt Rohwert |
| CAPE-Werte unplausibel hoch | LOW | `default_enabled=False`, User aktiviert bewusst |

## Standards Compliance

- Spec-first workflow (dieses Dokument)
- Keine Mocked Tests
- Safari kompatibel (keine UI-Aenderungen noetig)
- Backward compatible (alle neuen Metriken disabled by default)

## Changelog

- 2026-02-12: v1.0 - Initial spec
