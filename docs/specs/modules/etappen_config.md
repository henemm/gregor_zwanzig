---
entity_id: etappen_config
type: feature
created: 2026-02-11
status: draft
version: "1.0"
workflow: gpx-etappen-config
tags: [webui, gpx, story-1, config]
---

# Etappen-Config WebUI (Feature 1.6)

## Approval

- [x] Approved for implementation

## Purpose

Nach GPX-Upload (Feature 1.1): User konfiguriert Startzeit und Gehgeschwindigkeiten, loest Segmentierung aus (Feature 1.4+1.5), sieht Vorschau der Segmente. Verbindet Upload mit der Segment-Berechnung.

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/web/pages/gpx_upload.py` | MODIFY | Config-Dialog nach Upload, Segment-Berechnung |
| `tests/unit/test_etappen_config.py` | CREATE | Tests fuer Segmentierungs-Integration |

- Estimated: +100 LoC (2 Dateien)
- Risk Level: LOW
- Kein neues Modul, erweitert bestehende Upload-Seite

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `web.pages.gpx_upload` | Modul (existiert) | Upload-Seite erweitern |
| `core.segment_builder` | Modul (existiert) | build_segments() |
| `core.elevation_analysis` | Modul (existiert) | detect_waypoints() |
| `core.hybrid_segmentation` | Modul (existiert) | optimize_segments() |
| `app.models.EtappenConfig` | DTO (existiert) | Speed/Duration Config |

## Source

- **File:** `src/web/pages/gpx_upload.py`
- **Identifier:** `_show_config_and_segments(container, track, filename)`

## Implementation Details

### Erweiterung der Upload-Seite

Nach erfolgreichem Upload: Config-Bereich + Segment-Vorschau erscheint.

```
/gpx-upload
├── [bestehend] Upload-Widget
├── [bestehend] Track-Zusammenfassung
├── [NEU] Konfigurations-Bereich
│   ├── Startzeit (Time-Picker, default 08:00)
│   ├── Gehgeschwindigkeit (Slider/Number, default 4.0 km/h)
│   ├── Steig-Geschwindigkeit (Slider/Number, default 300 Hm/h)
│   ├── Abstiegs-Geschwindigkeit (Slider/Number, default 500 Hm/h)
│   └── Button "Segmente berechnen"
└── [NEU] Segment-Vorschau (Tabelle)
    ├── Seg | Start | Ende | Dauer | Distanz | Aufstieg | Abstieg | Waypoint
    └── Summen-Zeile
```

### Segmentierungs-Pipeline

```python
def compute_full_segmentation(track, config, start_time):
    """Run complete pipeline: segments + waypoints + hybrid optimization."""
    segments = build_segments(track, config, start_time)
    waypoints = detect_waypoints(track)
    return optimize_segments(segments, waypoints, track, config)
```

### Design-Entscheidung: Auf gleicher Seite

Config und Vorschau bleiben auf `/gpx-upload` statt separate Seite, weil:
- Natuerlicher Flow: Upload → Config → Ergebnis
- Weniger Navigation
- Config-Aenderung → sofort neu berechnen

## Expected Behavior

- **Input:** User-Config (Startzeit, Geschwindigkeiten)
- **Output:** Segment-Tabelle mit allen berechneten Segmenten
- **Side effects:** Keine (Segmente werden erstmal nur angezeigt, nicht gespeichert)

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Track + Default-Config WHEN compute_full_segmentation THEN Segmente mit korrekter Anzahl
- [ ] Test 2: GIVEN Track + Config WHEN compute THEN mind. 1 adjusted_to_waypoint (Tag 4)
- [ ] Test 3: GIVEN Track + Config WHEN compute THEN Distanz-Summe == total
- [ ] Test 4: GIVEN Track + Config WHEN compute THEN Zeiten lueckenlos ab Startzeit

### Manual Tests (E2E)

- [ ] Config-Bereich erscheint nach Upload
- [ ] "Segmente berechnen" zeigt Tabelle
- [ ] Startzeit aenderbar
- [ ] Geschwindigkeiten aenderbar

## Acceptance Criteria

- [ ] Config-Bereich nach Upload sichtbar
- [ ] Startzeit konfigurierbar (default 08:00)
- [ ] 3 Geschwindigkeiten konfigurierbar
- [ ] "Segmente berechnen" fuehrt Pipeline aus
- [ ] Segment-Tabelle zeigt alle Segmente
- [ ] Adjusted Segmente markiert (Waypoint-Name)
- [ ] Summen-Zeile am Ende
- [ ] Safari-kompatibel (Factory Pattern)

## Known Limitations

- Segmente werden nicht persistiert (kommt spaeter)
- Kein Undo/Reset (User laed neue GPX hoch)

## Changelog

- 2026-02-11: Initial spec
