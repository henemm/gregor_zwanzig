---
entity_id: gpx_upload
type: feature
created: 2026-02-11
status: draft
version: "1.0"
workflow: gpx-upload-webui
tags: [webui, gpx, story-1, upload]
---

# GPX Upload WebUI (Feature 1.1)

## Approval

- [x] Approved for implementation

## Purpose

Upload-Widget fuer GPX-Dateien in der Web-Oberflaeche. Nutzt den bestehenden GPX-Parser (Feature 1.2) zur Validierung und zeigt eine Zusammenfassung des Tracks. Speichert die GPX-Datei fuer spaetere Verarbeitung (Feature 1.6).

## Scope

| File | Change Type | Description |
|------|-------------|-------------|
| `src/web/pages/gpx_upload.py` | CREATE | Upload-Seite mit NiceGUI |
| `src/web/main.py` | MODIFY | Route `/gpx-upload` registrieren + Nav-Link |
| `tests/unit/test_gpx_upload_page.py` | CREATE | Unit-Tests fuer Upload-Logik |

- Estimated: +120 LoC (3 Dateien)
- Risk Level: LOW
- Keine neuen DTOs noetig

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `core.gpx_parser` | Modul (existiert) | parse_gpx() fuer Validierung |
| `app.models.GPXTrack` | DTO (existiert) | Parsed Track Daten |
| `web.main` | Modul (existiert) | Page-Registrierung |

## Source

- **File:** `src/web/pages/gpx_upload.py`
- **Identifier:** `render_gpx_upload()`, `process_gpx_upload(content, filename)`

## Implementation Details

### Seiten-Aufbau

```
/gpx-upload
├── Header (Navigation)
├── "GPX Upload" Titel
├── Upload-Widget (Drag & Drop + Dateiauswahl)
│   ├── Accept: .gpx
│   ├── Max: 10 MB
│   └── Auto-Upload: ja
├── [Nach Upload] Track-Zusammenfassung
│   ├── Name: "Tag 4: von Tossals Verds nach Lluc"
│   ├── Distanz: 14.0 km
│   ├── Aufstieg: 744 m / Abstieg: 785 m
│   ├── Trackpunkte: 649
│   └── Waypoints: 1
└── [Nach Upload] "Weiter zur Konfiguration" Button (disabled, Feature 1.6)
```

### Upload-Handler (Safari Factory Pattern!)

```python
def make_upload_handler(container, summary_container):
    """Factory function (Safari compatibility)."""
    async def do_upload(e: events.UploadEventArguments):
        track = process_gpx_upload(e.content.read(), e.name)
        # Show summary...
    return do_upload
```

### process_gpx_upload(content, filename)

1. Pruefe Dateiendung (.gpx)
2. Speichere in `data/users/default/gpx/{filename}`
3. Rufe `parse_gpx(saved_path)` auf
4. Bei Fehler: GPXParseError → ui.notify mit Fehlermeldung
5. Bei Erfolg: Gib GPXTrack zurueck

### Design-Entscheidung: Separate Seite

Eigene Seite `/gpx-upload` statt Integration in `/trips`, weil:
- Feature 1.6 (Config) und 1.7 (Uebersicht) bauen darauf auf
- Klare Trennung: manuelle Trips vs. GPX-basierte Trips
- Spaeter: `/gpx-upload` → `/gpx-config` → `/gpx-segments` Flow

## Expected Behavior

- **Input:** GPX-Datei via Upload-Widget
- **Output:** Track-Zusammenfassung auf der Seite
- **Side effects:** GPX-Datei gespeichert in `data/users/default/gpx/`
- **Fehlerfall:** Fehlermeldung bei ungueltigem GPX (ui.notify, type="negative")

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN gueltige GPX WHEN process_gpx_upload THEN GPXTrack mit korrektem Namen
- [ ] Test 2: GIVEN gueltige GPX WHEN process_gpx_upload THEN Datei in gpx/ gespeichert
- [ ] Test 3: GIVEN ungueltige Dateiendung WHEN process_gpx_upload THEN ValueError
- [ ] Test 4: GIVEN kaputtes XML WHEN process_gpx_upload THEN GPXParseError
- [ ] Test 5: GIVEN leere Datei WHEN process_gpx_upload THEN GPXParseError

### Manual Tests (E2E)

- [ ] Seite /gpx-upload erreichbar
- [ ] Upload-Widget sichtbar
- [ ] Drag & Drop funktioniert
- [ ] Zusammenfassung nach Upload korrekt
- [ ] Fehlermeldung bei ungueltigem GPX

## Acceptance Criteria

- [ ] Seite `/gpx-upload` im Nav-Menu erreichbar
- [ ] Upload-Widget akzeptiert nur .gpx Dateien
- [ ] Max. Dateigroesse 10 MB
- [ ] GPX wird via parse_gpx() validiert
- [ ] Track-Zusammenfassung zeigt Name, Distanz, Hoehenmeter, Punktzahl
- [ ] GPX-Datei in data/users/default/gpx/ gespeichert
- [ ] Fehlermeldung bei ungueltiger Datei
- [ ] Safari-kompatibel (Factory Pattern)
- [ ] Tests mit echten GPX-Dateien (keine Mocks!)

## Known Limitations

- Kein Drag & Drop auf mobile Safari (bekannte Browser-Einschraenkung)
- "Weiter" Button noch deaktiviert (Feature 1.6)
- Kein Upload-Verlauf (History) - nur letzte Datei angezeigt

## Changelog

- 2026-02-11: Initial spec
