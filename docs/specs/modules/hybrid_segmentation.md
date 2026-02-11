---
entity_id: hybrid_segmentation
type: feature
created: 2026-02-11
status: draft
version: "1.0"
workflow: gpx-hybrid-segmentation
tags: [gpx, core, story-1, segmentation]
---

# Hybrid-Segmentierung (Feature 1.5)

## Approval

- [x] Approved for implementation

## Purpose

Zeit-basierte Segment-Grenzen (Feature 1.4) an erkannten Gipfeln/Taelern (Feature 1.3) ausrichten, wenn diese nahe genug liegen. Liefert natuerlichere Segment-Grenzen an markanten Gelaendepunkten statt an willkuerlichen Zeitgrenzen.

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/hybrid_segmentation.py` | CREATE | Hybrid-Optimierung der Segment-Grenzen |
| `tests/unit/test_hybrid_segmentation.py` | CREATE | Tests mit echten GPX-Dateien |

- Estimated: +120 LoC (2 Dateien)
- Risk Level: LOW
- Kein DTO-Aenderung noetig (TripSegment hat bereits adjusted_to_waypoint + waypoint Felder)

## Source

- **File:** `src/core/hybrid_segmentation.py`
- **Identifier:** `optimize_segments(segments, waypoints, track, config) -> list[TripSegment]`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `models.TripSegment` | DTO (existiert) | Segment mit adjusted_to_waypoint Feld |
| `models.DetectedWaypoint` | DTO (existiert) | Erkannter Gipfel/Tal |
| `models.EtappenConfig` | DTO (existiert) | Geschwindigkeits-Config |
| `models.GPXTrack` | DTO (existiert) | Track mit allen Punkten |
| `core.segment_builder` | Modul (existiert) | build_segments(), compute_hiking_time() |
| `core.elevation_analysis` | Modul (existiert) | detect_waypoints() |

## Implementation Details

### Algorithmus

```python
def optimize_segments(
    segments: list[TripSegment],
    waypoints: list[DetectedWaypoint],
    track: GPXTrack,
    config: EtappenConfig,
    proximity_minutes: float = 20.0,
    min_duration_hours: float = 1.5,
    max_duration_hours: float = 2.5,
) -> list[TripSegment]:
```

**Fuer jedes Segment (ausser letztes):**
1. Finde Waypoints in Naehe des Segment-Endes (±proximity_minutes Gehzeit)
2. Konvertiere proximity_minutes in km (grob: proximity_min/60 * speed_flat)
3. Priorisiere: GIPFEL > PASS > TAL
4. Fuer den besten Kandidaten:
   - Finde den GPX-Punkt, der dem Waypoint am naechsten liegt
   - Berechne neue Segment-Dauer wenn Grenze dorthin verschoben wird
   - Pruefe: Bleibt Segment in [min_duration, max_duration]?
   - Pruefe: Bleibt NAECHSTES Segment auch in [min_duration, max_duration]?
   - Wenn ja: Verschiebe, setze adjusted_to_waypoint=True, waypoint=Candidate
5. Segment-Zeiten neu berechnen (lueckenlos)

### Echte Daten: Tag 4

```
Aktuell:  Seg 2 endet bei 6.9km (1196m)
Gipfel:   7.1km (1200m) — nur 0.2km entfernt!
Ergebnis: Seg 2 endet bei 7.1km (1200m, adjusted_to_waypoint=True)
```

### Design-Entscheidung: Separates Modul

Die Hybrid-Logik ist eine **Post-Processing-Schicht** auf den Zeit-Segmenten.
Kein Umbau von segment_builder.py noetig — optimize_segments() nimmt fertige
Segmente und gibt optimierte zurueck. Saubere Trennung.

## Expected Behavior

- **Input:** Zeit-Segmente + DetectedWaypoints + Track + Config
- **Output:** Optimierte Segmente (gleiche oder verschobene Grenzen)
- **Side effects:** Keine (pure function)
- **Invarianten:** Distanz-Summe und Zeitfenster bleiben konsistent

## Test Plan

### Automated Tests (TDD RED) - mit echten GPX-Dateien!

- [ ] Test 1: GIVEN Tag 4 Segmente + Waypoints WHEN optimize THEN Seg 2 an Gipfel 1200m angepasst
- [ ] Test 2: GIVEN optimierte Segmente WHEN pruefe THEN adjusted_to_waypoint==True bei mind. 1 Segment
- [ ] Test 3: GIVEN optimierte Segmente WHEN pruefe THEN waypoint-Referenz gesetzt
- [ ] Test 4: GIVEN optimierte Segmente WHEN pruefe Dauer THEN alle zwischen 1.5h und 2.5h (oder letztes kuerzer)
- [ ] Test 5: GIVEN optimierte Segmente WHEN summiere Distanzen THEN == track.total_distance_km
- [ ] Test 6: GIVEN optimierte Segmente WHEN pruefe Zeiten THEN lueckenlos
- [ ] Test 7: GIVEN Tag 2 (kaum Waypoints nahe Grenzen) WHEN optimize THEN Segmente wenig/nicht veraendert
- [ ] Test 8: GIVEN leere Waypoint-Liste WHEN optimize THEN Segmente unveraendert

### Manual Tests

- [ ] Alle 4 Etappen: Vergleich vorher/nachher der Segment-Grenzen

## Acceptance Criteria

- [ ] Erkennt Waypoints nahe Segment-Grenzen (±20min Gehzeit)
- [ ] Verschiebt Grenzen zum naechsten Waypoint wenn Dauer-Constraints erfuellt
- [ ] Priorisiert GIPFEL > PASS > TAL
- [ ] Segment-Dauer bleibt in [1.5h, 2.5h] (letztes kann kuerzer sein)
- [ ] Distanz-Summe bleibt konsistent
- [ ] Zeiten bleiben lueckenlos
- [ ] adjusted_to_waypoint + waypoint Felder korrekt gesetzt
- [ ] Leere Waypoint-Liste → keine Veraenderung
- [ ] Tests mit echten GPX-Dateien (keine Mocks!)

## Known Limitations

- Proximity-Check ist distanz-basiert (km), nicht exakt zeit-basiert
- Nur einfache Verschiebung (kein Splitting/Merging von Segmenten)
- Letztes Segment wird nicht angepasst (hat keine Nachfolger-Constraint)

## Changelog

- 2026-02-11: Initial spec
