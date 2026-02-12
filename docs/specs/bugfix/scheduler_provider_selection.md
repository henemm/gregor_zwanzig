---
entity_id: scheduler_provider_selection
type: bugfix
created: 2026-02-12
updated: 2026-02-12
status: draft
version: "1.0"
tags: [bugfix, scheduler, provider, openmeteo, geosphere, weather]
related_specs:
  - trip_report_formatter_v2
  - agent_orchestration
---

# Scheduler Provider Selection nach Koordinaten

## Approval

- [ ] Approved

## Purpose

Der Trip Report Scheduler und Trip Alert Service verwenden hardcoded
`get_provider("geosphere")` als Primary Provider. GeoSphere deckt nur
Oesterreich ab. Fuer Trips ausserhalb Oesterreichs (z.B. GR221 Mallorca)
schlaegt der primaere Fetch fehl (HTTP 400 "outside of dataset bounds"),
und der OpenMeteo-Fallback wird erst nach dem Fehler versucht.

**Beobachteter Bug:** Morning Report "GR221 Mallorca" vom 12.02.2026 zeigt
nur Segment 2 statt 2 Segments. Ursache: Transienter Fehler beim Fallback
fuer Segment 1 — der primaere GeoSphere-Request war von vornherein sinnlos.

**Fix:** OpenMeteo als universellen Provider verwenden. OpenMeteo hat bereits
eine regionale Modell-Auswahl (`REGIONAL_MODELS` in `openmeteo.py`) die
automatisch das beste Modell nach Koordinaten waehlt (AROME fuer Mallorca,
ICON-D2 fuer DACH, ECMWF als globaler Fallback). GeoSphere wird entfernt.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_fetch_weather()`, `_fetch_night_weather()`
- **File:** `src/services/trip_alert.py`
- **Identifier:** Provider-Auswahl in Alert-Service

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OpenMeteoProvider` | Class (providers/openmeteo.py) | Universeller Provider mit regionaler Modell-Wahl |
| `OpenMeteoProvider.select_model()` | Method | Waehlt bestes Modell nach lat/lon |
| `REGIONAL_MODELS` | Config (providers/openmeteo.py) | Regionale Modelle mit Bounds und Prioritaet |
| `get_provider()` | Factory (providers/base.py) | Provider-Instanziierung |
| `SegmentWeatherService` | Class (services/segment_weather.py) | Wetter-Fetch pro Segment |

## Implementation Details

### 1. `_fetch_weather()` in trip_report_scheduler.py

Vorher:
```python
try:
    provider = get_provider("geosphere")
except Exception:
    provider = get_provider("openmeteo")

service = SegmentWeatherService(provider)
fallback_service = None
if provider.__class__.__name__ != "OpenMeteoProvider":
    fallback_service = SegmentWeatherService(get_provider("openmeteo"))
```

Nachher:
```python
provider = get_provider("openmeteo")
service = SegmentWeatherService(provider)
```

Kein Fallback noetig — OpenMeteo hat ECMWF als globalen Fallback eingebaut.

### 2. `_fetch_night_weather()` in trip_report_scheduler.py

Vorher:
```python
provider = get_provider("openmeteo")
```

Bereits korrekt, keine Aenderung noetig.

### 3. `trip_alert.py` — gleicher Fix

Vorher:
```python
try:
    provider = get_provider("geosphere")
except Exception:
    provider = get_provider("openmeteo")
```

Nachher:
```python
provider = get_provider("openmeteo")
```

### 4. Fallback-Logik entfernen

Die `fallback_service` Variable und die try/except-Kette in `_fetch_weather()`
werden komplett entfernt. Der Code wird von ~25 auf ~8 Zeilen reduziert:

```python
def _fetch_weather(self, segments):
    provider = get_provider("openmeteo")
    service = SegmentWeatherService(provider)

    weather_data = []
    for segment in segments:
        try:
            data = service.fetch_segment_weather(segment)
            weather_data.append(data)
        except Exception as e:
            logger.error(f"Weather fetch failed for segment {segment.segment_id}: {e}")
    return weather_data
```

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/services/trip_report_scheduler.py` | Provider-Auswahl vereinfachen | ~-17 |
| `src/services/trip_alert.py` | Gleicher Fix | ~-5 |

**Total:** ~-22 LoC (Code-Reduktion)

## Test Plan

### Automated Tests

- [ ] `test_fetch_weather_uses_openmeteo`: Provider ist OpenMeteo (nicht GeoSphere)
- [ ] `test_mallorca_segments_both_fetched`: GR221 T2 liefert 2 Segments mit Wetter

### Manual Tests

- [ ] Morning Report manuell ausloesen: beide Segments in E-Mail
- [ ] Trip mit oesterreichischen Koordinaten: funktioniert weiterhin

## Acceptance Criteria

- [ ] Kein `get_provider("geosphere")` mehr in Scheduler/Alert Services
- [ ] OpenMeteo als einziger Provider fuer Trip Reports
- [ ] Regionale Modell-Wahl passiert automatisch (AROME, ICON-D2, etc.)
- [ ] Keine Fallback-Kaskade mehr noetig
- [ ] Bestehende Trips mit AT-Koordinaten funktionieren weiterhin

## Known Limitations

1. **GeoSphere entfaellt fuer Trips:** GeoSphere hat hoehere Aufloesung fuer
   oesterreichische Stationen, aber OpenMeteo's ICON-D2 (2 km) ist fuer
   Wanderwetter ausreichend. Die Standalone-Seiten (CLI, Subscriptions)
   nutzen weiterhin GeoSphere wenn konfiguriert.

2. **Kein Retry bei transientem Fehler:** Wenn OpenMeteo fuer ein Segment
   fehlschlaegt, wird es weiterhin uebersprungen. Ein Retry-Mechanismus
   waere ein separates Feature.

## Changelog

- 2026-02-12: v1.0 Initial spec
