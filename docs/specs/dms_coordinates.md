---
entity_id: dms_coordinates
type: feature
created: 2025-12-28
updated: 2025-12-28
status: draft
version: "1.0"
tags: [web-ui, coordinates, usability]
---

# DMS-Koordinaten Eingabe

## Approval

- [x] Approved

## Purpose

Ermöglicht die Eingabe von Koordinaten im Google Maps DMS-Format:
`47°16'11.1"N 11°50'50.2"E`

## Betroffene Dateien

- `src/web/pages/locations.py` - Location-Editor
- `src/web/pages/trips.py` - Waypoint-Editor

## Implementation

### Konvertierungsfunktion

```python
def parse_dms_coordinate(dms: str) -> tuple[float, float] | None:
    """
    Parse DMS string like "47°16'11.1\"N 11°50'50.2\"E"
    Returns (lat, lon) or None if invalid.
    """
```

### UI-Änderung

Zusätzliches Eingabefeld für DMS-String mit "Konvertieren"-Button,
oder automatische Erkennung beim Einfügen.

## Changelog

- 2025-12-28: Initial spec
