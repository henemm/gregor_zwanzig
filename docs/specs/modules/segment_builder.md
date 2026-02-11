---
entity_id: segment_builder
type: feature
created: 2026-02-11
status: draft
version: "1.0"
workflow: gpx-time-segmentation
tags: [gpx, core, story-1, segmentation]
---

# Zeit-Segment-Bildung (Feature 1.4)

## Approval

- [x] Approved for implementation

## Purpose

GPX-Tracks in ~2h-Wanderabschnitte (TripSegments) aufteilen basierend auf Gehgeschwindigkeit, Steig-/Abstiegsgeschwindigkeit und Distanz. Nutzt angepasste Naismith's Rule fuer realistische Gehzeit-Berechnung.

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/segment_builder.py` | CREATE | Gehzeit-Berechnung + Segment-Bildung |
| `src/app/models.py` | MODIFY | EtappenConfig DTO ergaenzen |
| `tests/unit/test_segment_builder.py` | CREATE | Tests mit echten GPX-Dateien |

- Estimated: +150 LoC (3 Dateien)
- Risk Level: LOW

## Source

- **File:** `src/core/segment_builder.py`
- **Identifier:** `build_segments(track, config, start_time) -> list[TripSegment]`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `models.GPXPoint` | DTO (existiert) | Track-Punkt mit Distanz + Elevation |
| `models.GPXTrack` | DTO (existiert) | Geparseter Track aus Feature 1.2 |
| `models.TripSegment` | DTO (existiert) | Segment-Ergebnis |
| `models.EtappenConfig` | DTO (NEU) | Geschwindigkeits-Konfiguration |
| `core.gpx_parser` | Modul (existiert) | GPX Parser aus Feature 1.2 |

## Implementation Details

### 1. EtappenConfig DTO in models.py

```python
@dataclass
class EtappenConfig:
    """Configuration for hiking speed and segmentation."""
    speed_flat_kmh: float = 4.0       # Gehgeschwindigkeit Ebene
    speed_ascent_mh: float = 300.0    # Steig-Geschwindigkeit [Hm/h]
    speed_descent_mh: float = 500.0   # Abstiegs-Geschwindigkeit [Hm/h]
    target_duration_hours: float = 2.0  # Ziel-Segment-Dauer
```

### 2. segment_builder.py

**Zwei Funktionen:**

```python
def compute_hiking_time(
    distance_km: float,
    ascent_m: float,
    descent_m: float,
    config: EtappenConfig,
) -> float:
    """Berechne Gehzeit in Stunden (angepasste Naismith's Rule).

    time = distance / speed_flat
         + ascent / speed_ascent
         + descent / speed_descent
    """

def build_segments(
    track: GPXTrack,
    config: EtappenConfig,
    start_time: datetime,
) -> list[TripSegment]:
    """Teile Track in ~2h-Segmente.

    Iteriert ueber GPX-Punkte, akkumuliert Gehzeit.
    Wenn target_duration erreicht → neues Segment.
    Letztes Segment kann kuerzer sein.
    """
```

**Segmentierungs-Algorithmus:**
1. Iteriere ueber aufeinanderfolgende Punkt-Paare
2. Berechne Gehzeit pro Punkt-Paar (Distanz-Delta + Elevation-Delta)
3. Akkumuliere Zeit seit letztem Segment-Start
4. Wenn akkumulierte Zeit >= target_duration → Segment-Grenze setzen
5. Tracke Aufstieg/Abstieg/Distanz pro Segment
6. Start-/End-Zeit aus kumulierter Gehzeit + start_time berechnen
7. Letztes Segment: Rest der Route (kann < target_duration sein)

**Elevation-Berechnung pro Punkt-Paar:**
- delta_elevation = punkt_b.elevation - punkt_a.elevation
- Wenn delta > 0: Aufstieg (speed_ascent)
- Wenn delta < 0: Abstieg (speed_descent)
- Distanz immer ueber distance_from_start_km Differenz

## Expected Behavior

- **Input:** GPXTrack + EtappenConfig + Start-Zeitpunkt (datetime, UTC)
- **Output:** Liste von TripSegment-Objekten
- **Side effects:** Keine (pure function)

### Beispiel Tag 1: Valldemossa → Deià

```
Input:  GPXTrack(458 points, 9.6km, +488m/-751m)
        EtappenConfig(4.0 km/h, 300 Hm/h, 500 Hm/h, 2h target)
        start_time=2026-01-17T08:00:00Z

Output: [
    TripSegment(id=1, 08:00-10:00, ~3.5km, +200m/-100m, 2.0h),
    TripSegment(id=2, 10:00-12:00, ~3.5km, +200m/-300m, 2.0h),
    TripSegment(id=3, 12:00-13:30, ~2.6km, +88m/-351m, 1.5h),
]
Geschaetzte Gesamt-Gehzeit: ~5.5h → 3 Segmente
```

## Test Plan

### Automated Tests (TDD RED) - mit echten GPX-Dateien!

**compute_hiking_time:**
- [ ] Test 1: GIVEN 4km flach WHEN compute_hiking_time THEN 1.0h (4km / 4km/h)
- [ ] Test 2: GIVEN 0km + 300Hm Aufstieg WHEN compute THEN 1.0h (300/300)
- [ ] Test 3: GIVEN 4km + 300Hm auf + 500Hm ab WHEN compute THEN 3.0h

**build_segments (echte Daten):**
- [ ] Test 4: GIVEN Tag 1 GPX + defaults WHEN build_segments THEN 2-4 Segmente (Route ist ~5.5h)
- [ ] Test 5: GIVEN Tag 3 GPX (laengste Etappe) WHEN build_segments THEN > 4 Segmente
- [ ] Test 6: GIVEN Segmente WHEN summiere Distanzen THEN == track.total_distance_km
- [ ] Test 7: GIVEN Segmente WHEN pruefe Zeiten THEN lueckenlos (End-Zeit = naechste Start-Zeit)
- [ ] Test 8: GIVEN kurze Route (<2h) WHEN build_segments THEN genau 1 Segment

**EtappenConfig:**
- [ ] Test 9: GIVEN langsame Config (2km/h) WHEN build_segments THEN mehr Segmente als default

### Manual Tests

- [ ] Alle 4 Mallorca-Etappen segmentieren und Ergebnisse pruefen
- [ ] Segment-Zeiten auf Plausibilitaet pruefen

## Acceptance Criteria

- [ ] Gehzeit-Formel implementiert (Naismith's Rule: Distanz + Aufstieg + Abstieg)
- [ ] Route wird in ~2h-Segmente aufgeteilt
- [ ] Segment-Grenzen liegen auf GPX-Punkten
- [ ] Jedes Segment hat Start/End-Zeit, Distanz, Aufstieg, Abstieg
- [ ] Letztes Segment kann kuerzer als 2h sein
- [ ] Konfigurierbare Geschwindigkeiten (EtappenConfig)
- [ ] Distanz-Summe aller Segmente == Gesamt-Distanz
- [ ] Zeiten lueckenlos (kein Zeitsprung zwischen Segmenten)
- [ ] Tests mit echten GPX-Dateien (keine Mocks!)

## Known Limitations

- Keine Pausen-Berechnung (Mittagspause etc.) — kommt ggf. spaeter
- Segment-Grenzen rein zeit-basiert (Hybrid-Optimierung in Feature 1.5)
- Keine Beruecksichtigung von Wegbeschaffenheit (Pfad vs. Strasse)

## Changelog

- 2026-02-11: Initial spec
