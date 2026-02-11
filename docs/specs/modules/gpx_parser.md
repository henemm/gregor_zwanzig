---
entity_id: gpx_parser
type: feature
created: 2026-02-11
status: draft
version: "2.0"
workflow: gpx-parser-validation
tags: [gpx, core, story-1]
---

# GPX Parser & Validation

## Approval

- [x] Approved for implementation

## Purpose

GPX-Dateien (Komoot GPX 1.1) parsen, Track-Koordinaten mit Hoehen und Distanzen extrahieren, und die Datei-Struktur validieren. Foundation fuer Hoehenprofil-Analyse (Feature 1.3), Segmentierung (Feature 1.4/1.5) und WebUI-Upload (Feature 1.1).

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/__init__.py` | CREATE | Package init |
| `src/core/gpx_parser.py` | CREATE | GPX parsing via gpxpy, Validierung, Track-Extraktion |
| `src/app/models.py` | MODIFY | GPXTrack + GPXWaypoint DTOs ergaenzen |
| `tests/unit/test_gpx_parser.py` | CREATE | Tests mit echten GPX-Dateien |

- Estimated: +150 LoC (4 Dateien)
- Risk Level: LOW
- Externe Dependency: `gpxpy` (1 Package)

## Source

- **File:** `src/core/gpx_parser.py`
- **Identifier:** `parse_gpx(file_path: str | Path) -> GPXTrack`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `models.GPXPoint` | DTO (existiert) | Einzelner Track-Punkt |
| `models.GPXTrack` | DTO (NEU) | Gesamter Track mit Metadaten |
| `models.GPXWaypoint` | DTO (NEU) | Benannter Wegpunkt aus GPX |
| `gpxpy` | PyPI (NEU) | GPX 1.0/1.1 Parsing, Namespace-Handling, Distanzberechnung |

## Implementation Details

### Design-Entscheidung: gpxpy statt xml.etree

**Recherche-Ergebnis:** Die `gpxpy` Library (1000+ GitHub Stars, 14 Jahre alt, Apache 2.0) ersetzt ~100 Zeilen manuelles XML/Namespace-Handling:

| Aufgabe | xml.etree (manuell) | gpxpy |
|---------|---------------------|-------|
| Namespace-Handling | Manuell registrieren | Automatisch (GPX 1.0 + 1.1) |
| Multi-Segment Tracks | Selbst iterieren | `track.segments` |
| Punkt-zu-Punkt Distanz | Eigene Haversine | `point.distance_2d()` |
| Waypoint-Extraktion | XPath manuell | `gpx.waypoints` |
| Fehlerbehandlung | Raw XML Exceptions | `GPXXMLSyntaxException` |

→ **Kein separates `geo_utils.py` noetig** — gpxpy liefert Distanzberechnung built-in.

### Design-Entscheidung: Threshold-basierte Hoehenmeter

**Recherche-Ergebnis:** Naive Summierung aller positiven Elevation-Deltas ueberschaetzt um bis zu 115%! GPS-Rauschen erzeugt kuenstliche Auf/Ab-Bewegungen.

**Loesung: Threshold-Filter (wie Strava/Garmin):**
- Elevation-Aenderung wird erst gezaehlt wenn Delta >= 5m zum letzten gezaehlten Punkt
- Eliminiert Rauschen, liefert realistische Werte
- Default-Schwelle: 5m (konfigurierbar)

**Warum nicht gpxpy's `get_uphill_downhill()`?**
- Nutzt aggressives Smoothing (Gewichte 0.4, 0.2, 0.4)
- Bekanntes Problem: unterschaetzt auf Bergtouren (GitHub Issue #46)
- Unser Threshold-Ansatz ist transparenter und Strava-kompatibel

### 1. DTOs ergaenzen in models.py

```python
@dataclass
class GPXWaypoint:
    """Named waypoint from GPX file (e.g. summit, hut)."""
    name: str
    lat: float
    lon: float
    elevation_m: Optional[float] = None

@dataclass
class GPXTrack:
    """Parsed GPX track with computed metrics."""
    name: str
    points: list[GPXPoint]
    waypoints: list[GPXWaypoint]
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float
```

### 2. gpx_parser.py

```python
class GPXParseError(ValueError):
    """Raised when GPX file is invalid or cannot be parsed."""

def parse_gpx(file_path: str | Path) -> GPXTrack:
    """Parse GPX file and return track with computed distances.

    Uses gpxpy for XML parsing and distance calculation.
    Elevation gain/loss computed with threshold-based filter (5m).

    Raises:
        GPXParseError: Bei ungueltigem Format, zu wenigen Punkten,
                       fehlender Elevation, oder ungueltigen Koordinaten.
    """
```

**Parsing-Ablauf:**
1. Datei lesen, `gpxpy.parse()` aufrufen
2. Track-Name aus `gpx.tracks[0].name` oder Metadata extrahieren
3. Waypoints aus `gpx.waypoints` extrahieren → `GPXWaypoint` DTOs
4. Alle Segmente aller Tracks iterieren (Multi-Segment Support!)
5. Track-Points → `GPXPoint` DTOs mit kumulativer Distanz (`point.distance_2d()`)
6. Hoehenmeter berechnen (Threshold-Filter, 5m)
7. Validierung (siehe unten)
8. `GPXTrack` zurueckgeben

**Validierung (integriert im Parser):**
- GPX ist parsebar (gpxpy wirft `GPXXMLSyntaxException`)
- Mindestens ein Track mit mindestens einem Segment vorhanden
- Mindestens 10 Track-Points
- Koordinaten: lat in [-90, 90], lon in [-180, 180]
- Elevation vorhanden (nicht None/NaN) bei Track-Points
- Keine doppelten konsekutiven Punkte (GPS-Stall)

**Fehlerklasse:**
```python
class GPXParseError(ValueError):
    """Raised when GPX file is invalid or cannot be parsed."""
```

### Elevation-Berechnung (Threshold-Filter)

```python
ELEVATION_THRESHOLD_M = 5.0  # Wie Strava/Garmin

def _compute_elevation_gain(points: list[GPXPoint]) -> tuple[float, float]:
    """Threshold-basierte Hoehenmeter-Berechnung.

    Zaehlt Elevation-Aenderungen erst ab 5m Delta zum letzten
    gezaehlten Punkt. Eliminiert GPS-Rauschen.

    Returns: (total_ascent_m, total_descent_m)
    """
    ascent = 0.0
    descent = 0.0
    last_elevation = points[0].elevation_m

    for point in points[1:]:
        if point.elevation_m is None:
            continue
        delta = point.elevation_m - last_elevation
        if abs(delta) >= ELEVATION_THRESHOLD_M:
            if delta > 0:
                ascent += delta
            else:
                descent += abs(delta)
            last_elevation = point.elevation_m

    return round(ascent, 1), round(descent, 1)
```

## Expected Behavior

- **Input:** Pfad zu einer GPX-Datei (str oder Path)
- **Output:** `GPXTrack` mit allen Punkten, berechneten Distanzen und Hoehenmeter
- **Side effects:** Keine (pure function, liest nur Datei)

### Beispiel mit echten Daten (Tag 1: Valldemossa → Deià)

```
Input:  data/2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx
Output: GPXTrack(
    name="Tag 1: von Valldemossa nach Deià",
    points=[458 GPXPoint objects with cumulative distances],
    waypoints=[],
    total_distance_km=~10-12,
    total_ascent_m=~500-800,   # Threshold-basiert, realistisch
    total_descent_m=~500-800
)
```

## Test Plan

### Automated Tests (TDD RED) - mit echten GPX-Dateien!

**gpx_parser (parse_gpx):**
- [ ] Test 1: GIVEN Tag 1 GPX WHEN parse_gpx THEN 458 Punkte, Name "Tag 1: von Valldemossa nach Deià", Distanz > 0
- [ ] Test 2: GIVEN Tag 3 GPX WHEN parse_gpx THEN 811 Punkte + 1 Waypoint ("Tossals Verds")
- [ ] Test 3: GIVEN alle 4 GPX-Dateien WHEN parse_gpx THEN alle parsen erfolgreich, Distanzen > 0, Aufstieg > 0, Abstieg > 0
- [ ] Test 4: GIVEN Tag 1 GPX WHEN parse_gpx THEN kumulative Distanz letzter Punkt == total_distance_km
- [ ] Test 5: GIVEN Tag 1 GPX WHEN parse_gpx THEN Aufstieg < 2x Abstieg (plausibel fuer Rundweg-aehnliche Route)

**Validierung (Fehlerfaelle):**
- [ ] Test 6: GIVEN leere Datei WHEN parse_gpx THEN GPXParseError
- [ ] Test 7: GIVEN GPX mit <10 Punkten WHEN parse_gpx THEN GPXParseError
- [ ] Test 8: GIVEN ungueltige XML-Datei WHEN parse_gpx THEN GPXParseError

**Elevation Threshold:**
- [ ] Test 9: GIVEN Tag 1 GPX WHEN Threshold=0 vs Threshold=5 THEN Threshold=0 liefert mehr Hoehenmeter (zeigt Rauschfilter-Effekt)

### Manual Tests

- [ ] Alle 4 Mallorca-GPX-Dateien parsen und Ergebnisse pruefen
- [ ] Gesamt-Distanzen mit Komoot-Angaben vergleichen

## Acceptance Criteria

- [ ] Parsed GPX 1.0 und 1.1 Format (via gpxpy)
- [ ] Extrahiert Track-Points (lat, lon, elevation) aus allen Segmenten
- [ ] Extrahiert Waypoints (name, lat, lon, optional elevation)
- [ ] Berechnet kumulative Distanz pro Punkt (gpxpy distance_2d)
- [ ] Berechnet Gesamt-Distanz, Aufstieg, Abstieg (Threshold-basiert)
- [ ] Validiert: Mindestens 10 Track-Points
- [ ] Validiert: Koordinaten in gueltigem Bereich
- [ ] Validiert: Elevation vorhanden
- [ ] Klare Fehlermeldungen bei ungueltigem GPX (GPXParseError)
- [ ] Tests mit echten GPX-Dateien (keine Mocks!)

## Known Limitations

- Kein Multi-Track Support (erster Track wird verwendet, alle seine Segmente werden zusammengefuegt)
- Timestamps aus GPX werden gelesen aber nicht in GPXPoint gespeichert (nicht benoetigt fuer Feature 1.2)
- Elevation-Threshold fest auf 5m (konfigurierbar in spaeterem Feature)

## Changelog

- 2026-02-11: v1.0 - Initial spec (xml.etree Ansatz)
- 2026-02-11: v2.0 - Rewrite nach Best-Practice-Recherche:
  - gpxpy statt xml.etree (eliminiert ~100 Zeilen Boilerplate)
  - geo_utils.py entfaellt (gpxpy hat built-in Distanzberechnung)
  - Threshold-basierte Hoehenmeter (5m, wie Strava/Garmin)
  - Multi-Segment Support
  - GPX 1.0 + 1.1 Support
