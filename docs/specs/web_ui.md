---
entity_id: web_ui
type: feature
created: 2025-12-28
updated: 2025-12-28
status: draft
version: "1.0"
tags: [ui, nicegui, configuration]
---

# Web UI - Konfigurationsoberfläche

## Approval

- [ ] Approved

## Purpose

NiceGUI-basierte Web-Oberfläche zur Verwaltung von Locations, Trips und Settings. Ermöglicht den Vergleich mehrerer Forecasts für die Skigebiet-Auswahl ("Welches Skigebiet morgen?").

## Source

- **File:** `src/web/main.py`
- **Identifier:** `run()` (Einstiegspunkt)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `nicegui` | external | UI-Framework |
| `app.loader` | module | Trip/User JSON laden/speichern |
| `app.config` | module | Settings lesen/schreiben |
| `app.trip` | module | Trip/Stage/Waypoint DTOs |
| `app.user` | module | Location/User DTOs |
| `services.forecast` | module | Forecast-Abfrage für Vergleich |
| `providers.geosphere` | module | Wetterdaten-Provider |

## Architektur

```
src/web/
  __init__.py
  main.py              # Einstiegspunkt, Router
  pages/
    __init__.py
    dashboard.py       # Übersicht
    locations.py       # Location CRUD
    trips.py           # Trip CRUD mit Stages/Waypoints
    compare.py         # Forecast-Vergleich
    settings.py        # SMTP/Provider-Config
```

## Seiten-Spezifikation

### Dashboard (`/`)

| Element | Beschreibung |
|---------|--------------|
| Stats-Cards | Anzahl Locations, Trips |
| Quick-Actions | Links zu Vergleich, Neu-Anlegen |

### Locations (`/locations`)

| Element | Beschreibung |
|---------|--------------|
| Liste | Alle gespeicherten Locations |
| Add-Dialog | Name, Lat, Lon, Elevation, Region |
| Delete | Location löschen |

**Datenstruktur:**
```json
{
  "id": "stubai",
  "name": "Stubaier Gletscher",
  "lat": 47.0833,
  "lon": 11.1167,
  "elevation_m": 3150,
  "region": "AT-7"
}
```

### Trips (`/trips`)

| Element | Beschreibung |
|---------|--------------|
| Liste | Alle Trips |
| Add-Dialog | Name, Stages mit Waypoints |
| Nested Editor | Stage → Waypoints |
| Delete | Trip löschen |

**Datenstruktur:** Entspricht `app.trip.Trip`

### Forecast-Vergleich (`/compare`)

| Element | Beschreibung |
|---------|--------------|
| Multi-Select | Locations auswählen |
| Datum-Picker | Morgen, Übermorgen, etc. |
| Vergleichs-Tabelle | Neuschnee, Temp, Wind, Sicht, Lawine |
| Score | Gewichtetes Ranking |

**Score-Berechnung:**
- Neuschnee: mehr = besser (Gewicht: 30%)
- Wind: weniger = besser (Gewicht: 25%)
- Sicht: besser = besser (Gewicht: 15%)
- Lawinenstufe: niedriger = besser (Gewicht: 30%)

### Settings (`/settings`)

| Element | Beschreibung |
|---------|--------------|
| SMTP-Form | Host, Port, User, Pass, From, To |
| Provider | Dropdown (geosphere) |
| Test-Button | Test-Mail senden |

## Persistenz

**Verzeichnisstruktur (Multi-User-ready):**
```
data/
  users/
    default/           # Single-User MVP
      locations/
        stubai.json
        axamer.json
      trips/
        skitour-2025.json
```

**Neue Funktionen in `loader.py`:**
```python
def save_location(location: SavedLocation, user_id: str = "default") -> Path
def delete_location(location_id: str, user_id: str = "default") -> None
def save_trip(trip: Trip, user_id: str = "default") -> Path
def delete_trip(trip_id: str, user_id: str = "default") -> None
```

## Expected Behavior

- **Input:** User-Interaktionen (Klicks, Formulare)
- **Output:** JSON-Dateien in `data/users/{user_id}/`
- **Side effects:**
  - Dateisystem-Operationen (CRUD)
  - Forecast-API-Aufrufe bei Vergleich

## CLI-Integration

```bash
# Separater Einstiegspunkt
python -m src.web.main

# Oder via CLI-Flag (später)
python -m src.app.cli --web
```

## Known Limitations

- **MVP:** Keine Authentifizierung (Single-User "default")
- **MVP:** Keine Karten-Integration (manuelle Koordinaten)
- **MVP:** Kein GPX-Import
- Skalierung: Max ~100 gleichzeitige User (WebSocket-basiert)

## Phase 2 (nicht in MVP)

- Multi-User mit Magic-Link-Login
- Karten-Integration (Leaflet)
- GPX-Import
- Server-Deployment

## Changelog

- 2025-12-28: Initial spec created from approved plan
