---
entity_id: trips_time_window_lost
type: bugfix
created: 2026-02-15
updated: 2026-02-15
version: "1.0"
status: implemented
severity: HIGH
tags: [trips, time_window, scheduler, waypoint-interpolation]
---

# Bugfix: Trips UI verwirft time_window → keine Morning-E-Mail

## Approval

- [x] Approved for implementation

## Symptom

Trip "GR221 Mallorca" bekommt keine Morning-E-Mail, obwohl Stage T1 aktiv ist (2026-02-15).

**Symptom in der Praxis:**
```
Scheduler prüft Trip "GR221 Mallorca" für 2026-02-15
  → Stage T1 hat 4 Waypoints (G1-G4)
  → _convert_trip_to_segments() liefert 0 Segmente
  → Keine E-Mail wird versendet
```

**Daten im Trip-JSON:**
```json
{
  "waypoints": [
    {
      "id": "G1",
      "name": "Valldemossa",
      "lat": 39.7094,
      "lon": 2.6219,
      "elevation_m": 436
      // time_window fehlt!
    }
  ]
}
```

## Root Cause

Die Trips-UI (`src/web/pages/trips.py`) verwirft `time_window` an **4 Stellen**:

### Problem 1: `gpx_to_stage_data()` — GPX-Upload verliert time_window

```python
# src/web/pages/trips.py:65-75
return {
    "name": stage.name,
    "date": stage.date.isoformat(),
    "waypoints": [
        {
            "id": wp.id,
            "name": wp.name,
            "lat": wp.lat,
            "lon": wp.lon,
            "elevation_m": wp.elevation_m,
            # time_window fehlt! → Waypoint hat time_window, wird aber nicht weitergegeben
        }
        for wp in stage.waypoints
    ],
}
```

**Konsequenz:** GPX-Upload → Stage-Dict ohne time_window → Save-Handler speichert Waypoints ohne time_window.

### Problem 2: New-Trip Save-Handler — time_window nicht gelesen

```python
# src/web/pages/trips.py:305-313
waypoints = [
    Waypoint(
        id=wp["id"],
        name=wp["name"],
        lat=float(wp["lat"]),
        lon=float(wp["lon"]),
        elevation_m=int(wp["elevation_m"]),
        # time_window fehlt! → Feld existiert aber im Dict, wird nicht gelesen
    )
    for wp in sd["waypoints"]
]
```

**Konsequenz:** Auch wenn `time_window` im Dict existieren würde, wird es beim Speichern verworfen.

### Problem 3: Edit-Dialog Trip→Dict — time_window nicht konvertiert

```python
# src/web/pages/trips.py:372-379
stage_dict = {
    "name": stage.name,
    "date": stage.date.isoformat(),
    "start_time": stage.start_time.strftime("%H:%M") if stage.start_time else "08:00",
    "waypoints": [
        {
            "id": wp.id,
            "name": wp.name,
            "lat": wp.lat,
            "lon": wp.lon,
            "elevation_m": wp.elevation_m,
            # time_window fehlt! → UI zeigt time_window nicht an
        }
        for wp in stage.waypoints
    ],
}
```

**Konsequenz:** Bearbeiten eines Trips mit time_window → UI zeigt time_window nicht → beim Speichern verloren.

### Problem 4: Edit-Save-Handler — time_window nicht gelesen

```python
# src/web/pages/trips.py:582-589
waypoints = [
    Waypoint(
        id=wp["id"],
        name=wp["name"],
        lat=float(wp["lat"]),
        lon=float(wp["lon"]),
        elevation_m=int(wp["elevation_m"]),
        # time_window fehlt! → Selbst wenn UI time_window hätte, wird es nicht gespeichert
    )
    for wp in sd["waypoints"]
]
```

**Konsequenz:** Edit-Save überschreibt Trip ohne time_window.

### Problem 5: Scheduler überspringt Waypoints ohne time_window

```python
# src/services/trip_report_scheduler.py:338-349
for i in range(len(waypoints) - 1):
    wp1 = waypoints[i]
    wp2 = waypoints[i + 1]

    if wp1.time_window is None:
        if i == 0:
            wp1_start = default_start
        else:
            logger.warning(f"Waypoint {wp1.id} missing time_window, skipping")
            continue  # ← Segment wird NICHT erstellt

    if wp2.time_window is None:
        logger.warning(f"Waypoint {wp2.id} missing time_window, skipping")
        continue  # ← Segment wird NICHT erstellt
```

**Konsequenz:** Waypoints ohne time_window → keine Segmente → keine E-Mail.

## Design

### Zweistufige Lösung

**Fix 1:** Trips-UI bewahrt time_window (4 Stellen patchen)
**Fix 2:** Scheduler interpoliert fehlende time_window als Sicherheitsnetz

### Fix 1: time_window durchreichen in Trips-UI

#### 1.1: `gpx_to_stage_data()` — time_window ins Dict

```python
# src/web/pages/trips.py:65-75
return {
    "name": stage.name,
    "date": stage.date.isoformat(),
    "waypoints": [
        {
            "id": wp.id,
            "name": wp.name,
            "lat": wp.lat,
            "lon": wp.lon,
            "elevation_m": wp.elevation_m,
            "time_window": str(wp.time_window) if wp.time_window else None,  # NEU
        }
        for wp in stage.waypoints
    ],
}
```

#### 1.2: New-Trip Save-Handler — time_window aus Dict lesen

```python
# src/web/pages/trips.py:305-313
waypoints = [
    Waypoint(
        id=wp["id"],
        name=wp["name"],
        lat=float(wp["lat"]),
        lon=float(wp["lon"]),
        elevation_m=int(wp["elevation_m"]),
        time_window=TimeWindow.from_string(wp["time_window"]) if wp.get("time_window") else None,  # NEU
    )
    for wp in sd["waypoints"]
]
```

#### 1.3: Edit-Dialog Trip→Dict — time_window konvertieren

```python
# src/web/pages/trips.py:372-379
"waypoints": [
    {
        "id": wp.id,
        "name": wp.name,
        "lat": wp.lat,
        "lon": wp.lon,
        "elevation_m": wp.elevation_m,
        "time_window": str(wp.time_window) if wp.time_window else None,  # NEU
    }
    for wp in stage.waypoints
],
```

#### 1.4: Edit-Save-Handler — time_window aus Dict lesen

```python
# src/web/pages/trips.py:582-589
waypoints = [
    Waypoint(
        id=wp["id"],
        name=wp["name"],
        lat=float(wp["lat"]),
        lon=float(wp["lon"]),
        elevation_m=int(wp["elevation_m"]),
        time_window=TimeWindow.from_string(wp["time_window"]) if wp.get("time_window") else None,  # NEU
    )
    for wp in sd["waypoints"]
]
```

### Fix 2: Scheduler interpoliert fehlende time_window

Statt Waypoints ohne time_window zu überspringen, automatisch interpolieren basierend auf:
- Distanz (haversine)
- Höhenmeter
- Geschätzte Gehzeit
- Kumulative Zeitfenster ab Stage-Startzeit

**Berechnung:**
- Flach: 4 km/h
- Aufstieg: 300 Hm/h
- Abstieg: 500 Hm/h

**Nutzung bestehender Funktionen:**
- `_haversine_km()` (Z.251-268) bereits vorhanden
- Stage.start_time oder Default 08:00

```python
# src/services/trip_report_scheduler.py:338-349
# ERSETZE: continue bei fehlendem time_window
# DURCH: Automatische Interpolation

def _interpolate_time_window(
    self,
    wp_prev: Waypoint,
    wp_current: Waypoint,
    prev_time: time,
) -> time:
    """
    Interpolate time_window.start for waypoint without time_window.

    Calculates hiking time from previous waypoint based on:
    - Distance (haversine)
    - Elevation gain/loss
    - Standard hiking speeds (4 km/h flat, 300 Hm/h up, 500 Hm/h down)

    Args:
        wp_prev: Previous waypoint (with known time)
        wp_current: Current waypoint (missing time_window)
        prev_time: Known time at previous waypoint

    Returns:
        Estimated time at current waypoint
    """
    dist_km = _haversine_km(wp_prev.lat, wp_prev.lon, wp_current.lat, wp_current.lon)
    elev_diff = wp_current.elevation_m - wp_prev.elevation_m

    # Time from distance (flat terrain)
    time_flat_hours = dist_km / 4.0  # 4 km/h

    # Time from elevation
    if elev_diff > 0:
        time_elev_hours = elev_diff / 300.0  # 300 Hm/h ascent
    else:
        time_elev_hours = abs(elev_diff) / 500.0  # 500 Hm/h descent

    # Total hiking time (max of flat vs elevation dominates)
    total_hours = max(time_flat_hours, time_elev_hours)

    # Add to previous time
    total_seconds = int(total_hours * 3600)
    prev_dt = datetime.combine(date.today(), prev_time)
    new_dt = prev_dt + timedelta(seconds=total_seconds)

    return new_dt.time()


def _convert_trip_to_segments(...):
    # ...existing code...

    cumulative_time = default_start  # Stage start time

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]

        # Get wp1 start time
        if wp1.time_window is None:
            if i == 0:
                wp1_start = default_start
            else:
                # INTERPOLATE statt continue
                wp1_start = self._interpolate_time_window(waypoints[i-1], wp1, cumulative_time)
                logger.info(f"Interpolated time_window for {wp1.id}: {wp1_start}")
        else:
            wp1_start = wp1.time_window.start

        cumulative_time = wp1_start

        # Get wp2 start time
        if wp2.time_window is None:
            # INTERPOLATE statt continue
            wp2_start = self._interpolate_time_window(wp1, wp2, wp1_start)
            logger.info(f"Interpolated time_window for {wp2.id}: {wp2_start}")
        else:
            wp2_start = wp2.time_window.start

        # ...rest of segment creation...
```

## Affected Files

| Datei | Änderung | LOC |
|-------|----------|-----|
| `src/web/pages/trips.py` | time_window durchreichen (4 Stellen) | ~12 |
| `src/services/trip_report_scheduler.py` | Interpolation statt Skip | ~60 |
| **Gesamt** | | **~72 LOC** |

## Test Plan

### Automatisiert

- [ ] GPX-Upload: time_window wird ins Stage-Dict übernommen
- [ ] New-Trip Save: time_window wird aus Dict gelesen und in Trip gespeichert
- [ ] Edit-Dialog: Trip mit time_window wird korrekt in Dict konvertiert
- [ ] Edit-Save: time_window aus Dict wird in Trip übernommen
- [ ] Scheduler-Interpolation: Waypoint ohne time_window → Segmente werden erstellt
- [ ] Scheduler-Interpolation: Gehzeit korrekt berechnet (Distanz + Höhenmeter)
- [ ] Trip mit time_window: Scheduler nutzt existierende time_window (keine Interpolation)

### Manuell (E2E)

- [ ] GPX-Upload → Trip speichern → Morning-E-Mail wird versendet
- [ ] Trip bearbeiten → Waypoint ändern → time_window bleibt erhalten
- [ ] Manuell angelegter Trip ohne GPX → Interpolation generiert Segmente → E-Mail wird versendet
- [ ] Trip "GR221 Mallorca" (bestehend, defekt) → Scheduler interpoliert → E-Mail wird versendet

## Edge Cases

| Szenario | Verhalten | Fix |
|----------|-----------|-----|
| GPX-Upload | time_window vorhanden, aber UI verwirft | Fix 1.1 + 1.2 |
| Manueller Waypoint | Kein GPX, nie time_window gesetzt | Fix 2 interpoliert |
| Trip bearbeiten | time_window vorhanden, aber UI zeigt nicht | Fix 1.3 + 1.4 |
| Bestehender Trip defekt | time_window fehlt in JSON | Fix 2 interpoliert |
| Nur erster Waypoint ohne time_window | Stage.start_time als Fallback | Existierender Code bleibt |
| Waypoint-Reihenfolge ändern | time_window müsste neu berechnet werden | Out of Scope (User-Fehler) |

## Acceptance Criteria

- [ ] GPX-Upload bewahrt time_window in allen Waypoints
- [ ] New-Trip Save liest time_window aus Dict und speichert in Trip-JSON
- [ ] Edit-Dialog zeigt time_window (als String im Dict)
- [ ] Edit-Save überschreibt time_window nicht
- [ ] Scheduler erstellt Segmente auch ohne time_window (via Interpolation)
- [ ] Trip "GR221 Mallorca" bekommt Morning-E-Mail nach Fix
- [ ] Bestehende Trips mit time_window funktionieren unverändert
- [ ] Loader (`src/app/loader.py`) liest/schreibt time_window korrekt (bereits implementiert, keine Änderung)

## Changelog

- 2026-02-15: v1.0 Bugfix-Spec erstellt (trips_time_window_lost)
