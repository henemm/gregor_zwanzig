# User Story: GPX Upload & Segment-Planung

**Status:** open
**Created:** 2026-02-01
**Epic:** GPX-basierte Trip-Planung
**Priority:** HIGH (Story 1 of 3)

## Story

Als Weitwanderer
möchte ich meine Etappen-GPX-Dateien hochladen und automatisch in 2h-Segmente aufteilen lassen
damit ich einen strukturierten Plan meiner Wanderung mit Zeitfenstern habe

## Context

**Wichtige Entscheidungen aus User-Dialog:**
- ✅ Upload via **WebUI (NiceGUI)** (nicht CLI)
- ✅ **Eine GPX-Datei = Eine Etappe** (kein Auto-Detection von Etappen)
- ✅ **Start-Zeit pro Etappe individuell** (User konfiguriert)
- ✅ **Geh-Geschwindigkeit user-konfiguriert** (km/h + Höhenmeter/h)
- ✅ **Hybrid-Segmentierung**: Zeit-basiert (2h) + Wegpunkt-Anpassung (Gipfel/Täler)
- ✅ **Iterativer Rollout**: Story 1 → nutzen → Story 2 (Wetter) → Story 3 (Reports)

## Acceptance Criteria

- [ ] User kann GPX-Datei per WebUI hochladen (Drag & Drop oder File-Picker)
- [ ] System parsed GPX-Datei und extrahiert Route (Koordinaten, Höhenprofil)
- [ ] System validiert GPX (Format, Mindestanzahl Punkte, gültige Koordinaten)
- [ ] User konfiguriert **pro Etappe**: Start-Zeit, Gehgeschwindigkeit (km/h), Steig-Geschwindigkeit (Hm/h)
- [ ] System teilt Etappe in **~2h-Segmente** (Zeit-basiert)
- [ ] System erkennt **markante Wegpunkte** (Gipfel, Täler, Pässe) aus Höhenprofil
- [ ] System passt Segment-Grenzen an Wegpunkten an (Hybrid: Zeit + Wegpunkte)
- [ ] WebUI zeigt **Segment-Übersicht**: Liste aller Segmente mit Zeitfenster, Start/End-Koordinaten, Höhen
- [ ] User kann Segmente visuell überprüfen (Karte + Höhenprofil optional)

## Feature Breakdown

### P0 Features (Must Have - Story 1 MVP)

---

#### Feature 1.1: GPX Upload (WebUI)

**Category:** WebUI
**Scoping:** 2-3 files, ~100 LOC, Simple
**Dependencies:** None
**Roadmap Status:** Will be added

**What:**
Upload-Widget in NiceGUI für GPX-Dateien

**Acceptance:**
- [ ] Drag & Drop funktioniert
- [ ] File-Picker funktioniert (Button "GPX hochladen")
- [ ] Validierung: Nur .gpx Dateien erlaubt
- [ ] Max File-Size: 10 MB
- [ ] Safari-kompatibel (Factory Pattern für Button!)
- [ ] Upload-Feedback: Loading-Spinner während Upload
- [ ] Fehler-Handling: Ungültige Dateien werden abgelehnt mit klarer Meldung

**Files:**
- `src/web/pages/gpx_upload.py` (NEW) - Upload-Widget
- `src/web/components/file_upload.py` (NEW) - Reusable Upload-Component
- `tests/e2e/test_gpx_upload.py` (NEW) - E2E Test (Browser, Safari!)

**Technical Approach:**
- NiceGUI `ui.upload()` Widget
- Factory Pattern für Upload-Handler (Safari!)
- File stored temporarily in session, dann verarbeitet
- Validierung: File extension, XML structure check

**Standards:**
- ✅ Safari Compatibility (Factory Pattern)
- ✅ No Mocked Tests (Real file upload in browser test)

---

#### Feature 1.2: GPX Parser & Validation

**Category:** Core
**Scoping:** 3-4 files, ~200 LOC, Medium
**Dependencies:** None (kann parallel zu 1.1)
**Roadmap Status:** Will be added

**What:**
GPX XML parsing, Route-Extraktion, Koordinaten + Höhen

**Acceptance:**
- [ ] Parsed GPX 1.0 und 1.1 Format
- [ ] Extrahiert Track-Points (lat, lon, elevation)
- [ ] Extrahiert Waypoints (optional, für Gipfel/Hütten)
- [ ] Berechnet Distanz zwischen Punkten (Haversine-Formel)
- [ ] Berechnet Gesamt-Distanz und Höhenmeter (Aufstieg/Abstieg)
- [ ] Validiert: Mindestens 10 Track-Points
- [ ] Validiert: Koordinaten in gültigem Bereich (-90/90, -180/180)
- [ ] Validiert: Elevation vorhanden (für Höhenprofil)
- [ ] Fehler-Handling: Klare Fehlermeldungen bei ungültigem GPX

**Files:**
- `src/core/gpx_parser.py` (NEW) - GPX Parsing-Logik
- `src/core/geo_utils.py` (NEW) - Geo-Berechnungen (Distanz, Höhenmeter)
- `src/core/gpx_validator.py` (NEW) - GPX Validierung
- `tests/unit/test_gpx_parser.py` (NEW) - Unit Tests mit echten GPX-Dateien

**Technical Approach:**
- Python `xml.etree.ElementTree` für GPX parsing
- Haversine-Formel für Distanz-Berechnung
- Elevation-Delta für Höhenmeter (Auf/Ab getrennt)

**DTO (add to API Contract):**
```python
class GPXTrack:
    points: list[GPXPoint]         # Track-Points
    waypoints: list[GPXWaypoint]   # Optional Waypoints
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float

class GPXPoint:
    lat: float
    lon: float
    elevation_m: float | None
    distance_from_start_km: float  # Kumulative Distanz

class GPXWaypoint:
    name: str
    lat: float
    lon: float
    elevation_m: float | None
```

**Standards:**
- ✅ API Contracts (Add GPX DTOs)
- ✅ No Mocked Tests (Real GPX files in tests)

---

#### Feature 1.3: Höhenprofil-Analyse

**Category:** Core
**Scoping:** 2-3 files, ~150 LOC, Medium
**Dependencies:** Feature 1.2 (needs parsed GPX)
**Roadmap Status:** Will be added

**What:**
Gipfel/Tal/Pass-Erkennung aus Höhenprofil

**Acceptance:**
- [ ] Erkennt Gipfel (lokale Maxima im Höhenprofil)
- [ ] Erkennt Täler (lokale Minima)
- [ ] Erkennt Pässe (Sattelpunkte)
- [ ] Filter: Mindest-Prominenz (z.B. 50 Hm über Umgebung)
- [ ] Filter: Mindest-Abstand (z.B. nicht 2 Gipfel in 200m)
- [ ] Markiert Wegpunkte mit Typ (GIPFEL, TAL, PASS)
- [ ] Berechnet Steigung zwischen Punkten (für Geschwindigkeits-Anpassung)

**Files:**
- `src/core/elevation_analysis.py` (NEW) - Höhenprofil-Analyse
- `src/core/waypoint_detection.py` (NEW) - Wegpunkt-Erkennung
- `tests/unit/test_elevation_analysis.py` (NEW) - Unit Tests

**Technical Approach:**
- Sliding Window für lokale Maxima/Minima
- Prominenz-Berechnung (Höhendifferenz zu umliegenden Punkten)
- Steigung: delta_elevation / delta_distance

**DTO Extension (add to API Contract):**
```python
class DetectedWaypoint:
    type: WaypointType  # GIPFEL, TAL, PASS
    point: GPXPoint
    prominence_m: float  # Höhen-Prominenz
    name: str | None     # Optional aus GPX-Waypoint

enum WaypointType:
    GIPFEL, TAL, PASS
```

**Standards:**
- ✅ API Contracts (Add DetectedWaypoint DTO)

---

#### Feature 1.4: Zeit-Segment-Bildung

**Category:** Core
**Scoping:** 3-4 files, ~180 LOC, Medium
**Dependencies:** Feature 1.2 (needs distance data)
**Roadmap Status:** Will be added

**What:**
Geschwindigkeit + Distanz → ~2h-Segmente, Zeitperioden berechnen

**Acceptance:**
- [ ] User konfiguriert: Start-Zeit (z.B. 08:00 Uhr)
- [ ] User konfiguriert: Gehgeschwindigkeit (km/h) in der Ebene
- [ ] User konfiguriert: Steig-Geschwindigkeit (Hm/h Aufstieg)
- [ ] User konfiguriert: Abstiegs-Geschwindigkeit (Hm/h Abstieg)
- [ ] System berechnet Gehzeit pro GPX-Punkt (basierend auf Distanz + Steigung)
- [ ] System teilt Route in Segmente: Ziel ~2h Gehzeit pro Segment
- [ ] Segment-Grenzen liegen auf GPX-Punkten (nicht zwischen Punkten)
- [ ] Jedes Segment hat: Start-Zeit, End-Zeit, Start-Punkt, End-Punkt
- [ ] Letztes Segment kann kürzer sein (<2h, wenn Route nicht aufgeht)

**Files:**
- `src/core/time_calculator.py` (NEW) - Gehzeit-Berechnung
- `src/core/segment_builder.py` (NEW) - Segment-Bildung
- `src/core/user_config.py` (MODIFIED) - Etappen-Config
- `tests/unit/test_time_calculator.py` (NEW) - Unit Tests

**Technical Approach:**
- **Gehzeit-Formel** (angepasste Naismith's Rule):
  ```
  time_hours = distance_km / speed_kmh
               + ascent_m / ascent_speed_mh
               + descent_m / descent_speed_mh
  ```
- **Segmentierung:**
  - Iteriere über GPX-Punkte
  - Akkumuliere Zeit bis ~2h erreicht
  - Erstelle Segment-Grenze
  - Wiederhole bis Route-Ende

**DTO (add to API Contract):**
```python
class TripSegment:
    segment_id: int
    start_point: GPXPoint
    end_point: GPXPoint
    start_time: datetime
    end_time: datetime
    duration_hours: float
    distance_km: float
    ascent_m: float
    descent_m: float

class EtappenConfig:
    gpx_file: str
    start_time: datetime
    speed_flat_kmh: float      # z.B. 4.0 km/h
    speed_ascent_mh: float     # z.B. 300 Hm/h
    speed_descent_mh: float    # z.B. 500 Hm/h
```

**Standards:**
- ✅ API Contracts (Add TripSegment, EtappenConfig DTOs)

---

#### Feature 1.5: Hybrid-Segmentierung

**Category:** Core
**Scoping:** 2-3 files, ~120 LOC, Medium
**Dependencies:** Feature 1.3 (waypoints), Feature 1.4 (time segments)
**Roadmap Status:** Will be added

**What:**
Zeit-Segmente + Wegpunkt-Grenzen kombinieren, Optimierung

**Acceptance:**
- [ ] System erkennt, wenn Wegpunkt (Gipfel/Tal) nahe Segment-Grenze liegt
- [ ] "Nahe" = innerhalb ±20 Minuten Gehzeit vom Zeit-Segment-Ende
- [ ] System verschiebt Segment-Grenze zum Wegpunkt (wenn vorteilhaft)
- [ ] Vorteilhaft = Segment bleibt zwischen 1.5h - 2.5h
- [ ] Wegpunkte werden priorisiert: GIPFEL > PASS > TAL
- [ ] User sieht im UI: "Segment angepasst an Gipfel XY"
- [ ] Hybrid-Segmentierung kann deaktiviert werden (Fallback: nur Zeit)

**Files:**
- `src/core/hybrid_segmentation.py` (NEW) - Hybrid-Logik
- `src/core/segment_builder.py` (MODIFIED) - Integration
- `tests/unit/test_hybrid_segmentation.py` (NEW) - Unit Tests

**Technical Approach:**
1. Erstelle Zeit-basierte Segmente (Feature 1.4)
2. Für jedes Segment:
   - Finde Wegpunkte in Bereich [segment_end - 20min, segment_end + 20min]
   - Wähle höchst-priorisierten Wegpunkt (GIPFEL > PASS > TAL)
   - Prüfe: Segment-Dauer bleibt in [1.5h, 2.5h]?
   - Wenn ja: Verschiebe Segment-Grenze zum Wegpunkt
3. Markiere Segment mit `adjusted_to_waypoint: bool`

**DTO Extension:**
```python
class TripSegment:
    # ... existing fields ...
    adjusted_to_waypoint: bool
    waypoint: DetectedWaypoint | None  # Falls angepasst
```

**Standards:**
- ✅ API Contracts (Extend TripSegment DTO)

---

#### Feature 1.6: Etappen-Config (WebUI)

**Category:** WebUI
**Scoping:** 3-4 files, ~150 LOC, Medium
**Dependencies:** Feature 1.1 (upload), Feature 1.2 (parsing)
**Roadmap Status:** Will be added

**What:**
User konfiguriert Start-Zeit, Geschwindigkeiten pro Etappe

**Acceptance:**
- [ ] Nach GPX-Upload: Config-Dialog öffnet automatisch
- [ ] User setzt Start-Zeit (Time-Picker, default: 08:00)
- [ ] User setzt Gehgeschwindigkeit (Slider oder Input, default: 4 km/h)
- [ ] User setzt Steig-Geschwindigkeit (Slider oder Input, default: 300 Hm/h)
- [ ] User setzt Abstiegs-Geschwindigkeit (Slider oder Input, default: 500 Hm/h)
- [ ] User kann Hybrid-Segmentierung aktivieren/deaktivieren (Checkbox, default: AN)
- [ ] Preview: Zeigt Anzahl Segmente + Gesamt-Gehzeit
- [ ] Button "Segmente berechnen" → Trigger Segmentierung
- [ ] Safari-kompatibel (Factory Pattern für alle Buttons!)
- [ ] Config wird gespeichert (Session oder DB)

**Files:**
- `src/web/pages/etappen_config.py` (NEW) - Config-Dialog
- `src/web/components/time_picker.py` (NEW) - Reusable Time-Picker
- `src/app/config.py` (MODIFIED) - Config-Storage
- `tests/e2e/test_etappen_config.py` (NEW) - E2E Test (Browser, Safari!)

**Technical Approach:**
- NiceGUI Dialog mit Form-Feldern
- Factory Pattern für alle Buttons/Inputs mit Callbacks
- Config in Session-State (temporär) oder Database (persistent)
- Preview: Berechne Segmente on-the-fly (ohne speichern)

**Standards:**
- ✅ Safari Compatibility (Factory Pattern)
- ✅ No Mocked Tests (Real browser E2E test)

---

#### Feature 1.7: Segment-Übersicht (WebUI)

**Category:** WebUI
**Scoping:** 2-3 files, ~100 LOC, Simple
**Dependencies:** Feature 1.4 (segments), Feature 1.5 (hybrid), Feature 1.6 (config)
**Roadmap Status:** Will be added

**What:**
Liste aller Segmente mit Zeiten, Koordinaten, Höhen

**Acceptance:**
- [ ] Tabelle zeigt alle Segmente der Etappe
- [ ] Spalten: Segment-Nr, Start-Zeit, End-Zeit, Dauer, Distanz, Aufstieg, Abstieg
- [ ] Optional: Start-Koordinaten, End-Koordinaten (expandable)
- [ ] Markierung: Segmente die an Wegpunkten angepasst wurden (Icon/Badge)
- [ ] Hover: Zeigt Wegpunkt-Name (falls angepasst)
- [ ] Button "Neu berechnen" → Zurück zu Config (Feature 1.6)
- [ ] Button "Wetter abrufen" → Disabled (kommt in Story 2)
- [ ] Safari-kompatibel (Factory Pattern!)
- [ ] Responsive: Tabelle scrollbar auf kleinen Screens

**Files:**
- `src/web/pages/segment_overview.py` (NEW) - Segment-Tabelle
- `src/web/components/segment_table.py` (NEW) - Reusable Table-Component
- `tests/e2e/test_segment_overview.py` (NEW) - E2E Test (Browser, Safari!)

**Technical Approach:**
- NiceGUI Table oder Custom HTML Table
- Factory Pattern für alle Buttons
- Data aus Session-State oder Database
- Optional: Höhenprofil-Chart (Feature 1.7b - P1?)

**Standards:**
- ✅ Safari Compatibility (Factory Pattern)
- ✅ No Mocked Tests (Real browser E2E test)

---

## Implementation Order

**Dependency-optimiert:**

```
Phase 1 (Parallel):
├─ Feature 1.1: GPX Upload (WebUI)
└─ Feature 1.2: GPX Parser & Validation

Phase 2 (Nach 1.2):
├─ Feature 1.3: Höhenprofil-Analyse
└─ Feature 1.4: Zeit-Segment-Bildung

Phase 3 (Nach 1.3 + 1.4):
└─ Feature 1.5: Hybrid-Segmentierung

Phase 4 (Nach 1.1 + 1.5):
├─ Feature 1.6: Etappen-Config (WebUI)
└─ Feature 1.7: Segment-Übersicht (WebUI)
```

**Empfohlene Reihenfolge:**
1. Feature 1.2 (Parser) - Foundation
2. Feature 1.1 (Upload) - User kann GPX hochladen
3. Feature 1.4 (Zeit-Segmente) - Basis-Segmentierung
4. Feature 1.3 (Höhenprofil) - Wegpunkt-Erkennung
5. Feature 1.5 (Hybrid) - Optimierung
6. Feature 1.6 (Config) - User-Interface
7. Feature 1.7 (Übersicht) - Finale Darstellung

## Dependency Graph

```
                  [1.2 Parser]
                  ↓         ↓
       [1.3 Höhenprofil]  [1.4 Zeit-Segmente]
                  ↓         ↓
              [1.5 Hybrid-Segmentierung]
                       ↓
       ┌───────────────┴───────────────┐
       ↓                               ↓
[1.1 Upload] → [1.6 Config] → [1.7 Übersicht]
```

## Estimated Effort

**Total (Story 1):**
- **LOC:** ~1000 lines
- **Files:** ~18 files (7 features)
- **Workflow Cycles:** 7 (one per feature)
- **Timeline:** 7-10 Tage (bei sequentieller Implementierung)

**Per Feature:**
- Simple (1.1, 1.7): ~100 LOC, 1-2 Tage
- Medium (1.2, 1.3, 1.4, 1.5, 1.6): ~150-200 LOC, 2-3 Tage

## MVP Definition (Story 1)

**MVP = Alle P0 Features Complete**

**User kann:**
- ✅ GPX-Datei per WebUI hochladen
- ✅ Start-Zeit und Geschwindigkeiten konfigurieren
- ✅ Etappe in 2h-Segmente aufteilen lassen (hybrid: Zeit + Wegpunkte)
- ✅ Segment-Übersicht sehen mit allen Details

**User kann NOCH NICHT:**
- ❌ Wetter für Segmente abrufen (Story 2)
- ❌ Automatische Reports erhalten (Story 3)

**Nach Story 1: System ist nutzbar für manuelle Trip-Planung!**

## Testing Strategy

### Real E2E Tests (NO MOCKS!)

**Browser Tests (Safari mandatory!):**
1. Upload GPX file via WebUI
2. Configure etappe (times, speeds)
3. View segment table
4. Verify segment count and times

**Integration Tests:**
1. Real GPX file parsing (use test GPX files from real hikes)
2. Elevation analysis with known peaks
3. Segmentation with known routes

**Unit Tests:**
1. Geo calculations (Haversine)
2. Elevation detection algorithms
3. Time calculation formulas

**Test Data:**
- Use real GPX files from GR20, Alpen, etc.
- Include edge cases: Short routes (<2h), Long routes (>12h), Flat routes, Mountain routes

## Standards to Follow

- ✅ **API Contracts:** Add all DTOs before implementation
- ✅ **No Mocked Tests:** Real GPX files, real browser tests
- ✅ **Safari Compatibility:** Factory Pattern for all UI buttons
- ✅ **Email Formatting:** N/A (no emails in Story 1)
- ✅ **Provider Selection:** N/A (no weather providers in Story 1)

## Security & Privacy

### GPX Files
- User uploads may contain personal data (home address in start/end points)
- Store temporarily only, delete after session
- Option: User can save etappen permanently (opt-in)

### Data Storage
- Session-based (default) or Database (opt-in)
- No cloud upload without explicit consent

## Configuration

### Config File Extensions

```ini
[gpx]
# Default values for new etappen
default_start_time = 08:00
default_speed_flat_kmh = 4.0
default_speed_ascent_mh = 300
default_speed_descent_mh = 500
default_hybrid_segmentation = true

# Segmentation settings
target_segment_duration_hours = 2.0
segment_duration_tolerance_hours = 0.5  # 1.5h - 2.5h acceptable
waypoint_proximity_minutes = 20

# Validation
min_track_points = 10
max_file_size_mb = 10
```

## Related

- **Epic:** GPX-basierte Trip-Planung (`epics.md`)
- **Architecture:** `docs/features/architecture.md`
- **API Contract:** `docs/reference/api_contract.md` (MUST UPDATE with new DTOs!)
- **Safari Best Practices:** `docs/reference/nicegui_best_practices.md`

## Notes

- Story 1 ist STANDALONE nutzbar (ohne Story 2+3)
- User kann Segmente manuell nutzen für Planung
- Story 2 fügt Wetter hinzu (Wetter-Engine)
- Story 3 fügt Reports hinzu (Email/SMS)

## Next Steps

**To start implementation:**

```bash
# 1. Update API Contract FIRST
# Add all DTOs: GPXTrack, GPXPoint, TripSegment, EtappenConfig, etc.
vim docs/reference/api_contract.md

# 2. Start with first feature
/feature "GPX Parser & Validation"

# 3. Follow workflow
/analyse
/write-spec
# User: "approved"
/tdd-red
/implement
/validate

# 4. Move to next feature
/feature "GPX Upload (WebUI)"
# ... repeat ...
```

---

**Story 1 ready for implementation! 🚀**
