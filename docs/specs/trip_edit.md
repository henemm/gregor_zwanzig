---
entity_id: trip_edit
type: feature
created: 2025-12-28
updated: 2025-12-28
status: approved
version: "1.0"
tags: [ui, nicegui, trips, crud]
---

# Trip Edit - Bearbeitung bestehender Trips

## Approval

- [x] Approved (2025-12-28)

## Purpose

Ermoeglicht das Bearbeiten bestehender Trips in der WebUI. Aktuell koennen Trips nur erstellt und geloescht werden - eine Bearbeitungsfunktion fehlt. Ohne Edit-Funktion muss der User einen Trip loeschen und neu anlegen, wenn sich z.B. ein Datum oder Wegpunkt aendert.

## Source

- **File:** `src/web/pages/trips.py`
- **Identifier:** `show_edit_dialog()` (neu), Integration in `render_content()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.load_all_trips` | function | Trips laden |
| `app.loader.save_trip` | function | Trip speichern (ueberschreibt) |
| `app.trip.Trip` | dataclass | Trip-Datenmodell |
| `app.trip.Stage` | dataclass | Etappen-Datenmodell |
| `app.trip.Waypoint` | dataclass | Wegpunkt-Datenmodell |
| `web.utils.parse_dms_coordinates` | function | Google Maps Koordinaten parsen |
| `nicegui` | external | UI-Framework |

## Implementation Details

### UI-Erweiterung

**1. Edit-Button in Trip-Liste:**
```python
# Neben dem Delete-Button
ui.button(icon="edit", on_click=make_edit_handler(trip))
```

**2. Edit-Dialog (analog zu Add-Dialog):**
- Oeffnet mit vorausgefuellten Daten des ausgewaehlten Trips
- Gleiche Struktur wie "Neuer Trip"-Dialog:
  - Trip-Name (editierbar)
  - Lawinenregionen (editierbar)
  - Etappen mit Wegpunkten (hinzufuegen/entfernen/editieren)
- Trip-ID bleibt unveraendert (nicht editierbar)

**3. Datenfluss:**
```
1. User klickt "Edit" auf Trip-Karte
2. Trip-Daten werden in stages_data-Struktur konvertiert
3. Dialog oeffnet mit vorausgefuellten Werten
4. User editiert
5. Bei "Speichern": Trip-Objekt wird neu erstellt
6. save_trip() ueberschreibt bestehende JSON-Datei
7. Liste wird refreshed
```

### Code-Struktur

```python
def show_edit_dialog(trip: Trip) -> None:
    """Edit-Dialog fuer bestehenden Trip."""
    # Konvertiere Trip -> stages_data Dictionary
    stages_data = []
    for stage in trip.stages:
        stage_dict = {
            "name": stage.name,
            "date": stage.date.isoformat(),
            "waypoints": [
                {
                    "id": wp.id,
                    "name": wp.name,
                    "lat": wp.lat,
                    "lon": wp.lon,
                    "elevation_m": wp.elevation_m,
                }
                for wp in stage.waypoints
            ],
        }
        stages_data.append(stage_dict)

    # Dialog mit vorausgefuellten Werten
    # (Rest analog zu show_add_dialog)
```

### Unterschiede zu Add-Dialog

| Aspekt | Add | Edit |
|--------|-----|------|
| Dialog-Titel | "Neuer Trip" | "Trip bearbeiten" |
| Name-Input | leer | vorausgefuellt |
| Regions-Input | leer | vorausgefuellt |
| stages_data | leer | aus Trip konvertiert |
| Trip-ID | aus Name generiert | unveraendert beibehalten |
| Button-Text | "Speichern" | "Aenderungen speichern" |

## Expected Behavior

- **Input:** Klick auf Edit-Button eines Trips
- **Output:** Dialog mit vorausgefuellten Trip-Daten, nach Speichern aktualisierte JSON-Datei
- **Side effects:**
  - Dateisystem: `data/users/default/trips/{trip_id}.json` wird ueberschrieben
  - UI: Liste wird nach Speichern aktualisiert

## Validierung

Gleiche Validierung wie beim Erstellen:
- Name erforderlich
- Mindestens eine Etappe
- Jede Etappe braucht mindestens einen Wegpunkt
- Datum muss gueltig sein

## Known Limitations

- Trip-ID kann nicht geaendert werden (wuerde neuen Trip erstellen)
- Keine Undo-Funktion (Aenderungen sofort persistent)
- Keine History/Versioning

## Changelog

- 2025-12-28: Initial spec created
