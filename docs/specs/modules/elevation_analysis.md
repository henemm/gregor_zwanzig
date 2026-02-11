---
entity_id: elevation_analysis
type: feature
created: 2026-02-11
status: draft
version: "1.0"
workflow: gpx-elevation-analysis
tags: [gpx, core, story-1, elevation]
---

# Hoehenprofil-Analyse (Feature 1.3)

## Approval

- [x] Approved for implementation

## Purpose

Markante Wegpunkte (Gipfel, Taeler, Paesse) aus dem Hoehenprofil eines GPX-Tracks erkennen. Wird von Feature 1.5 (Hybrid-Segmentierung) genutzt, um Segment-Grenzen an natuerlichen Gelaendepunkten auszurichten.

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/elevation_analysis.py` | CREATE | Hoehenprofil-Analyse + Wegpunkt-Erkennung |
| `src/app/models.py` | MODIFY | WaypointType Enum + DetectedWaypoint DTO |
| `tests/unit/test_elevation_analysis.py` | CREATE | Tests mit echten GPX-Dateien |

- Estimated: +130 LoC (3 Dateien)
- Risk Level: LOW

## Source

- **File:** `src/core/elevation_analysis.py`
- **Identifier:** `detect_waypoints(track: GPXTrack, ...) -> list[DetectedWaypoint]`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `models.GPXPoint` | DTO (existiert) | Track-Punkt mit Elevation |
| `models.GPXTrack` | DTO (existiert) | Geparseter Track |
| `models.DetectedWaypoint` | DTO (NEU) | Erkannter Wegpunkt |
| `models.WaypointType` | Enum (NEU) | GIPFEL, TAL, PASS |

## Implementation Details

### Design-Entscheidung: Sliding Window statt Bibliothek

Einfacher Sliding-Window-Algorithmus reicht fuer Wanderrouten:
- Punkt ist lokales Maximum → GIPFEL
- Punkt ist lokales Minimum → TAL
- PASS-Erkennung: Punkt ist lokales Maximum, aber Prominenz < Gipfel-Schwelle und > Pass-Schwelle (Sattelpunkt zwischen zwei hoeheren Bereichen)

Keine scipy/numpy noetig — die Logik ist ~50 Zeilen.

### Analyse der echten Daten

Tag 4 (Tossals Verds → Lluc) zeigt klare Topographie:
- PEAK bei 7.1km: 1200m (Prominenz ~117m)
- VALLEY bei 8.1km: 1056m
- PEAK bei 8.9km: 1130m (Prominenz ~101m)

Window-Groesse ~50 Punkte (~1km) funktioniert gut fuer Komoot-Daten.

### 1. DTOs in models.py

```python
class WaypointType(str, Enum):
    GIPFEL = "GIPFEL"
    TAL = "TAL"
    PASS = "PASS"

@dataclass
class DetectedWaypoint:
    type: WaypointType
    point: GPXPoint
    prominence_m: float
    name: Optional[str] = None  # Von GPX-Waypoint falls in Naehe
```

### 2. elevation_analysis.py

```python
def detect_waypoints(
    track: GPXTrack,
    min_prominence_m: float = 80.0,
    window_size: int = 50,
    min_distance_km: float = 0.5,
) -> list[DetectedWaypoint]:
    """Erkennt Gipfel, Taeler und Paesse aus dem Hoehenprofil.

    Algorithmus:
    1. Fuer jeden Punkt: Pruefe ob lokales Max/Min im Window
    2. Berechne Prominenz (Hoehe ueber/unter Umgebung)
    3. Filter: Nur Punkte mit Prominenz >= min_prominence_m
    4. Filter: Mindestabstand zwischen erkannten Punkten
    5. Optional: Matche mit GPX-Waypoints (Name uebernehmen)
    """
```

**Parameter:**
- `min_prominence_m=80`: Mindest-Hoehendifferenz zur Umgebung (filtert GPS-Rauschen)
- `window_size=50`: Anzahl Punkte links/rechts fuer lokale Max/Min (~1km bei Komoot)
- `min_distance_km=0.5`: Mindestabstand zwischen zwei erkannten Wegpunkten

**Pass-Erkennung:**
Ein PASS ist ein lokales Maximum mit niedrigerer Prominenz als ein GIPFEL — ein Sattelpunkt. Praktisch: Wenn ein Peak eine Prominenz zwischen 30m und min_prominence_m hat, und zwischen zwei hoeheren Bereichen liegt, ist es ein Pass. Fuer v1.0 vereinfacht: Alle lokalen Maxima mit Prominenz >= Schwelle sind GIPFEL, alle Minima sind TAL. PASS-Erkennung kommt in v1.1 falls benoetigt.

## Expected Behavior

- **Input:** GPXTrack + Konfigurationsparameter
- **Output:** Liste von DetectedWaypoint mit Typ, Position und Prominenz
- **Side effects:** Keine (pure function)

### Beispiel Tag 4 (Tossals Verds → Lluc)

```
Input:  GPXTrack(649 points, 14km, +744m/-785m, min=490m, max=1200m)

Output: [
    DetectedWaypoint(GIPFEL, GPXPoint(7.1km, 1200m), prominence=117m),
    DetectedWaypoint(TAL, GPXPoint(8.1km, 1056m), prominence=125m),
    DetectedWaypoint(GIPFEL, GPXPoint(8.9km, 1130m), prominence=101m),
]
```

## Test Plan

### Automated Tests (TDD RED) - mit echten GPX-Dateien!

**detect_waypoints:**
- [ ] Test 1: GIVEN Tag 4 GPX WHEN detect_waypoints THEN mindestens 1 GIPFEL erkannt
- [ ] Test 2: GIVEN Tag 4 GPX WHEN detect_waypoints THEN hoechster GIPFEL bei ~1200m
- [ ] Test 3: GIVEN Tag 4 GPX WHEN detect_waypoints THEN mindestens 1 TAL erkannt
- [ ] Test 4: GIVEN Tag 2 GPX (flacher) WHEN detect_waypoints THEN weniger Waypoints als Tag 4
- [ ] Test 5: GIVEN alle Waypoints WHEN pruefe THEN Prominenz >= min_prominence_m
- [ ] Test 6: GIVEN alle Waypoints WHEN pruefe THEN Abstand >= min_distance_km
- [ ] Test 7: GIVEN min_prominence_m=200 (hoch) WHEN detect_waypoints THEN weniger Ergebnisse
- [ ] Test 8: GIVEN Tag 3 mit GPX-Waypoint "Tossals Verds" WHEN detect THEN Name wird zugeordnet falls GIPFEL in Naehe

### Manual Tests

- [ ] Alle 4 Etappen analysieren und Ergebnisse visuell mit Hoehenprofil vergleichen

## Acceptance Criteria

- [ ] Erkennt Gipfel (lokale Maxima) aus Hoehenprofil
- [ ] Erkennt Taeler (lokale Minima) aus Hoehenprofil
- [ ] Filter: Mindest-Prominenz konfigurierbar (default: 80m)
- [ ] Filter: Mindest-Abstand zwischen Waypoints (default: 0.5km)
- [ ] Markiert Waypoints mit Typ (GIPFEL, TAL)
- [ ] Berechnet Prominenz pro Waypoint
- [ ] Optionaler Name-Match mit GPX-Waypoints
- [ ] Tests mit echten GPX-Dateien (keine Mocks!)

## Known Limitations

- Keine PASS-Erkennung in v1.0 (nur GIPFEL + TAL)
- Window-Groesse ist Punkt-basiert, nicht Distanz-basiert (funktioniert bei gleichmaessiger Komoot-Punktdichte)
- Keine Glaettung des Hoehenprofils vor Analyse (Komoot-Daten sind vorgeglättet)

## Changelog

- 2026-02-11: Initial spec
