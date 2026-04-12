---
entity_id: snapshot_missing_coordinates
type: bugfix
created: 2026-04-12
updated: 2026-04-12
status: resolved
version: "1.0"
tags: [alert, snapshot, coordinates]
---

# Bugfix: Snapshot persistiert keine Koordinaten

## Approval

- [x] Approved

## Purpose

Weather Snapshots speichern keine Koordinaten (lat/lon/elevation_m) der Segmente.
Beim Laden werden Dummy-GPXPoints mit (0.0, 0.0) erstellt. Alert-Checks nutzen diese
Dummy-Koordinaten fuer neue API-Calls → Wetterdaten vom Golf von Guinea statt echte Locations.
Zusaetzlich crasht der Formatter bei `int(None)` weil elevation_m=None.

## Source

- **File:** `src/services/weather_snapshot.py`
- **Identifier:** `WeatherSnapshotService.save()`, `_reconstruct_segment()`
- **File:** `src/formatters/trip_report.py`
- **Identifier:** Zeilen 354, 796, 797, 822, 1041, 1042, 1053

## Bug Details

### Symptom
- Alert-Checks rufen Open-Meteo mit lat=0.0, lon=0.0 auf
- Formatter crasht: `int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`

### Root Cause
1. `save()` (Zeile 62-66) persistiert nur `segment_id`, `start_time`, `end_time` — keine Koordinaten
2. `_reconstruct_segment()` (Zeile 141) erstellt `GPXPoint(lat=0.0, lon=0.0)` als Dummy
3. `trip_report.py` ruft `int(seg.start_point.elevation_m)` ohne None-Guard

### Affected Data Flow
```
save() → JSON ohne Koordinaten
load() → _reconstruct_segment() → GPXPoint(0.0, 0.0, elevation_m=None)
         → TripAlertService._fetch_fresh_weather() → API-Call an (0.0, 0.0)
         → trip_report.py: int(None) → TypeError crash
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.GPXPoint` | dataclass | lat, lon, elevation_m |
| `app.models.TripSegment` | dataclass | start_point, end_point |
| `services.trip_alert` | service | Nutzt load() fuer Change-Detection |
| `formatters.trip_report` | formatter | Zeigt elevation_m in Reports |

## Fix

### Fix 1: Koordinaten im Snapshot persistieren (weather_snapshot.py)

**save()** — Zusaetzliche Felder pro Segment:
```python
{
    "segment_id": seg.segment.segment_id,
    "start_time": seg.segment.start_time.isoformat(),
    "end_time": seg.segment.end_time.isoformat(),
    # NEU:
    "start_lat": seg.segment.start_point.lat,
    "start_lon": seg.segment.start_point.lon,
    "start_elevation_m": seg.segment.start_point.elevation_m,
    "end_lat": seg.segment.end_point.lat,
    "end_lon": seg.segment.end_point.lon,
    "end_elevation_m": seg.segment.end_point.elevation_m,
    "aggregated": _serialize_summary(seg.aggregated),
}
```

**_reconstruct_segment()** — Echte Koordinaten lesen mit Fallback auf 0.0:
```python
def _reconstruct_segment(seg_data: dict) -> TripSegment:
    start_point = GPXPoint(
        lat=seg_data.get("start_lat", 0.0),
        lon=seg_data.get("start_lon", 0.0),
        elevation_m=seg_data.get("start_elevation_m"),
    )
    end_point = GPXPoint(
        lat=seg_data.get("end_lat", 0.0),
        lon=seg_data.get("end_lon", 0.0),
        elevation_m=seg_data.get("end_elevation_m"),
    )
    return TripSegment(
        segment_id=seg_data["segment_id"],
        start_point=start_point,
        end_point=end_point,
        start_time=datetime.fromisoformat(seg_data["start_time"]),
        end_time=datetime.fromisoformat(seg_data["end_time"]),
        duration_hours=0.0,
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
```

**Abwaertskompatibel:** `.get("start_lat", 0.0)` → alte Snapshots ohne Koordinaten funktionieren weiterhin.

### Fix 2: None-Guard fuer elevation_m (trip_report.py)

An allen 6 Stellen `int(elevation_m)` durch `int(elevation_m or 0)` ersetzen:

- Zeile 354: `int(seg_data.segment.start_point.elevation_m or 0)`
- Zeile 796: `int(seg.start_point.elevation_m or 0)`
- Zeile 797: `int(seg.end_point.elevation_m or 0)`
- Zeile 822: `int(last_seg.end_point.elevation_m or 0)`
- Zeile 1041: `int(seg.start_point.elevation_m or 0)`
- Zeile 1042: `int(seg.end_point.elevation_m or 0)`
- Zeile 1053: `int(last_seg.end_point.elevation_m or 0)`

## Expected Behavior

- **Save:** Snapshot-JSON enthaelt lat, lon, elevation_m pro Segment-Endpunkt
- **Load:** Rekonstruierte Segmente haben echte Koordinaten
- **Alerts:** API-Calls gehen an korrekte Koordinaten
- **Formatter:** Kein Crash bei fehlender elevation_m, zeigt "0m" als Fallback

## Test Criteria

1. **Snapshot Round-Trip:** Save → Load → Koordinaten stimmen ueberein
2. **Abwaertskompatibilitaet:** Alte Snapshots (ohne Koordinaten) laden ohne Fehler
3. **Formatter:** `int(None)` crasht nicht mehr, zeigt 0 als Fallback
4. **Alert-Pfad:** Nach Save+Load werden echte Koordinaten fuer API-Calls genutzt

## Known Limitations

- Alte Snapshots behalten Dummy-Koordinaten bis zum naechsten Save
- `distance_km`, `ascent_m`, `descent_m` werden weiterhin nicht persistiert (nicht relevant fuer Alerts)

## Changelog

- 2026-04-12: Initial spec created
- 2026-04-12: Implemented and resolved — `weather_snapshot.py` saves/loads lat/lon/elevation_m per segment, `trip_report.py` guards all `int(elevation_m)` calls with `or 0`
