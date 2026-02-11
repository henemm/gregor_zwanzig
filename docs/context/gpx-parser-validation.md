# Context: GPX Parser & Validation (Feature 1.2)

**Workflow:** gpx-parser-validation
**Created:** 2026-02-11

## Request

GPX-Dateien (Komoot GPX 1.1) parsen, Route extrahieren (Koordinaten, Hoehen, Distanzen), Datei validieren. Foundation fuer alle weiteren GPX-Features (Hoehenprofil, Segmentierung, UI).

## Analysis

### Testdaten (echte Komoot-GPX-Dateien)

| Datei | Trackpoints | Waypoints | Route |
|-------|-------------|-----------|-------|
| Tag 1: Valldemossa → Deià | 458 | 0 | Mallorca GR221 |
| Tag 2: Deià → Sóller | 423 | 0 | Mallorca GR221 |
| Tag 3: Sóller → Tossals Verds | 811 | 1 (Tossals Verds) | Mallorca GR221 |
| Tag 4: Tossals Verds → Lluc | 649 | 1 (Tossals Verds) | Mallorca GR221 |

**GPX-Struktur (Komoot):**
- GPX 1.1, XML mit Namespace `http://www.topografix.com/GPX/1/1`
- `<metadata><name>` = Etappen-Name
- `<wpt lat lon><name>` = Optionale Wegpunkte (ohne Elevation!)
- `<trk><trkseg><trkpt lat lon><ele><time>` = Track-Points mit Elevation + Timestamp
- Elevation: Meter (z.B. 410.815646), hochpraezise floats
- Time: ISO 8601 UTC (z.B. 2026-01-17T13:51:57.455Z)

### Existierende DTOs (models.py)

**Vorhanden:**
- `GPXPoint` (lat, lon, elevation_m, distance_from_start_km)

**FEHLT im Code, aber im API Contract dokumentiert:**
- `GPXTrack` (points, waypoints, total_distance_km, total_ascent_m, total_descent_m)
- `GPXWaypoint` (name, lat, lon, elevation_m)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/__init__.py` | CREATE | Package init |
| `src/core/gpx_parser.py` | CREATE | GPX XML parsing + Track-Extraktion |
| `src/core/geo_utils.py` | CREATE | Haversine-Distanz, Hoehenmeter |
| `src/app/models.py` | MODIFY | GPXTrack + GPXWaypoint DTOs ergaenzen |
| `tests/unit/test_gpx_parser.py` | CREATE | Tests mit echten GPX-Dateien |

### Scope Assessment

- Files: 5 (3 CREATE, 1 MODIFY, 1 TEST)
- Estimated LoC: +200
- Risk Level: LOW

### Technical Approach

1. **geo_utils.py** - Haversine-Formel fuer Punkt-zu-Punkt-Distanz, kumulative Distanz, Hoehenmeter (Auf/Ab)
2. **gpx_parser.py** - XML parsing mit `xml.etree.ElementTree`, GPX Namespace handling, Extraktion von:
   - Track-Name aus `<metadata><name>` oder `<trk><name>`
   - Track-Points: lat, lon, ele, time
   - Waypoints: name, lat, lon, ele (optional)
   - Berechnet kumulative Distanzen und Hoehenmeter
3. **models.py** - `GPXTrack` und `GPXWaypoint` Dataclasses ergaenzen (laut API Contract)
4. **Validierung** integriert in Parser (kein separater Validator noetig bei dieser Groesse):
   - GPX 1.0/1.1 Format
   - Mindestens 10 Track-Points
   - Koordinaten in gueltigem Bereich (-90/90, -180/180)
   - Elevation vorhanden

### Design-Entscheidung: Kein separater Validator

Die Story-Planung sieht `gpx_validator.py` als separate Datei vor. Bei ~200 LOC Gesamtumfang ist das Over-Engineering. Validierung wird direkt im Parser integriert (Exceptions mit klaren Fehlermeldungen). Das haelt den Code kompakt und vermeidet unnoetige Abstraktionsschichten.

### Open Questions

Keine - Anforderungen sind klar durch Story-Planung und echte Testdaten.
