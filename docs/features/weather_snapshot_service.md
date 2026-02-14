# Feature: Weather Snapshot Service (ALERT-01)

**Status:** open (Analyse abgeschlossen, Spec noch nicht geschrieben)
**Prioritaet:** HIGH
**Kategorie:** Services / Alert System
**Erstellt:** 2026-02-14

## Problem

Die Alert-Pipeline (`trip_alert.py`) hat **keinen persistenten Speicher** fuer Wetterdaten.
Der 30-Minuten-Scheduler-Alert schlaegt **immer still fehl** wegen zwei Problemen:

### Bug 1: Fehlender Parameter

`_get_cached_weather()` (Zeile 184) ruft `scheduler._convert_trip_to_segments(trip)` auf,
aber die Methode braucht `target_date` als zweites Argument. Der `TypeError` wird vom
`try/except` (Zeile 191) still geschluckt → gibt immer `None` zurueck.

### Bug 2: Kein persistenter Speicher

Selbst wenn Bug 1 gefixt waere:
- `_get_cached_weather()` erzeugt einen **neuen** `TripReportSchedulerService` →
  **neuen** `SegmentWeatherService` → **neuen** leeren In-Memory-Cache → **fetcht frisch** von der API
- `_fetch_fresh_weather()` fetcht ebenfalls frisch von der API
- Beide Aufrufe passieren innerhalb von Sekunden — die Werte sind praktisch identisch
- Es gibt **keine Datei/Datenbank** wo die Wetterdaten vom Morning/Evening Report
  fuer spaeteren Vergleich abgelegt werden

### Konsequenz

Die "Alert bei Aenderungen" Funktion (im Roadmap als "done" markiert) funktioniert
nur bei manuellem Aufruf mit vorbereiteten Daten, NICHT ueber den Scheduler.

## Loesung: Weather Snapshot Service

Ein Service der:
1. Nach erfolgreichem Report-Versand die aggregierten Wetterdaten auf Disk speichert
2. Beim Alert-Check den letzten Snapshot als "vorher" laed
3. Frische Daten fetcht und gegen den Snapshot vergleicht

### Daten-Layout (multiuser-faehig)

```
data/users/{user_id}/weather_snapshots/
  └── {trip_id}.json
```

Beispiel-Snapshot:
```json
{
  "trip_id": "gr221-mallorca",
  "stage_id": "T4",
  "target_date": "2026-02-14",
  "snapshot_at": "2026-02-14T07:00:00+00:00",
  "provider": "openmeteo",
  "segments": [
    {
      "segment_id": 1,
      "start_time": "2026-02-14T08:00:00+00:00",
      "end_time": "2026-02-14T10:00:00+00:00",
      "aggregated": {
        "temp_max_c": 9.8,
        "temp_min_c": 5.2,
        "wind_max_kmh": 35.0,
        "gust_max_kmh": 52.0,
        "precip_sum_mm": 0.2,
        "cloud_avg_pct": 65.0
      }
    }
  ]
}
```

Folgt dem bestehenden Persistence-Pattern von `alert_throttle.json`:
- JSON-Datei, atomic write
- Graceful failure bei fehlender/korrupter Datei
- `mkdir(parents=True, exist_ok=True)` fuer Directory-Erstellung

### Betroffene Dateien

| Datei | Aenderung | LOC |
|-------|-----------|-----|
| `src/services/weather_snapshot.py` | **NEU**: Save/Load Snapshot (JSON) | ~50 |
| `src/services/trip_report_scheduler.py` | Snapshot speichern nach Report-Versand | ~10 |
| `src/services/trip_alert.py` | `_get_cached_weather()` → Snapshot laden + `target_date` Bug fixen | ~20 |
| `src/app/loader.py` | `get_snapshots_dir(user_id)` Helper | ~5 |
| **Gesamt** | | **~85 LOC** |

### Architektur-Entscheidungen

1. **Nur aggregierte Daten speichern** (SegmentWeatherSummary), NICHT die volle
   Timeseries — das haelt die Snapshot-Dateien klein (~1-2 KB pro Trip)
2. **Ein Snapshot pro Trip** (nicht pro Stage/Segment) — wird bei jedem Report ueberschrieben
3. **Multiuser via `user_id` Parameter** — folgt bestehendem Pattern aus `loader.py`:
   `get_data_dir(user_id="default")`, `get_trips_dir(user_id="default")`, etc.
4. **Keine Historisierung** — nur der letzte Snapshot wird gespeichert.
   Fuer History koennte spaeter ein Timestamp ins Filename (z.B. `{trip_id}_{date}.json`)

### Integration Points

1. **TripReportSchedulerService._send_trip_report()**: Nach erfolgreichem E-Mail-Versand
   → `WeatherSnapshotService.save(trip_id, segments_weather, user_id)`
2. **TripAlertService._get_cached_weather()**: Statt frisch fetchen
   → `WeatherSnapshotService.load(trip_id, user_id)` → SegmentWeatherData Liste
3. **WeatherChangeDetectionService**: Keine Aenderung noetig, vergleicht schon
   `old_data.aggregated` vs `new_data.aggregated`

### Serialisierung

`SegmentWeatherSummary` hat ~20 Optional[float/int/enum] Felder.
Serialisierung:
- float/int → direkt als JSON
- Enum (ThunderLevel, PrecipType) → `.value` / `.name`
- None → wird weggelassen (spart Platz)
- datetime → `.isoformat()`

Deserialisierung:
- JSON → dict → `SegmentWeatherSummary(**fields)` mit Enum-Rekonstruktion

### Bestehendes Multi-Tenant Layout (Referenz)

```
data/users/{user_id}/
├── alert_throttle.json
├── compare_subscriptions.json
├── gpx/
├── locations/
│   └── {location_id}.json
├── trips/
│   └── {trip_id}.json
└── weather_snapshots/           ← NEU
    └── {trip_id}.json
```

### Bestehende Loader-Funktionen (Pattern)

```python
# src/app/loader.py
def get_data_dir(user_id: str = "default") -> Path:
    return Path("data/users") / user_id

def get_trips_dir(user_id: str = "default") -> Path:
    return get_data_dir(user_id) / "trips"

# NEU:
def get_snapshots_dir(user_id: str = "default") -> Path:
    return get_data_dir(user_id) / "weather_snapshots"
```

## Naechste Schritte

1. `/2-analyse` — Detailanalyse (Serialisierung, Edge Cases)
2. `/3-write-spec` — Formale Spec erstellen
3. User: "approved"
4. `/5-implement` — Implementierung
5. `/6-validate` — Validierung + Tests

## Change Detection Thresholds (Referenz)

Die bestehenden Thresholds aus MetricCatalog:
- Temperatur: 5.0°C
- Wind: 20.0 km/h
- Niederschlag: 10.0 mm
- Boeen: 20.0 km/h

Severity-Klassifikation:
- MINOR: 1.0x - <1.5x Threshold
- MODERATE: 1.5x - <2.0x Threshold (→ Alert)
- MAJOR: >=2.0x Threshold (→ Alert)

Nur MODERATE und MAJOR loesen Alerts aus.
