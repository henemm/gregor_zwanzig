---
entity_id: frontend_i18n
type: refactor
created: 2026-01-01
updated: 2026-01-01
status: draft
version: "1.0"
tags: [i18n, frontend, ui, english]
---

# Frontend i18n: German to English

## Approval

- [ ] Approved

## Purpose

Convert all German UI texts in the NiceGUI frontend to English for consistency. The `subscriptions.py` page was already converted; this spec covers all remaining pages.

## Source

| File | Line Count | German Strings |
|------|------------|----------------|
| `src/web/pages/compare.py` | ~1800 | ~40 |
| `src/web/pages/locations.py` | ~220 | ~20 |
| `src/web/pages/trips.py` | ~485 | ~30 |
| `src/web/pages/settings.py` | ~210 | ~15 |
| `src/web/pages/dashboard.py` | ~80 | ~8 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| nicegui | library | UI framework |
| subscriptions.py | page | Already English (reference) |

## Implementation Details

### 1. Navigation Header (ALL files)

Replace in all `render_header()` functions:
```python
# Before
ui.link("Vergleich", "/compare")

# After
ui.link("Compare", "/compare")
```

Affected files: `compare.py`, `locations.py`, `trips.py`, `settings.py`, `dashboard.py`

### 2. dashboard.py

| German | English |
|--------|---------|
| `"Verwalten"` | `"Manage"` |
| `"Schnellaktionen"` | `"Quick Actions"` |
| `"Forecast vergleichen"` | `"Compare Forecast"` |
| `"Neue Location"` | `"New Location"` |
| `"Neuer Trip"` | `"New Trip"` |

### 3. settings.py

| German | English |
|--------|---------|
| `"E-Mail (SMTP)"` | `"Email (SMTP)"` |
| `"SMTP Benutzer"` | `"SMTP User"` |
| `"SMTP Passwort"` | `"SMTP Password"` |
| `"Absender (From)"` | `"Sender (From)"` |
| `"Empfänger (To)"` | `"Recipient (To)"` |
| `"Einfache Text-E-Mail (ohne Emojis)"` | `"Plain text email (no emojis)"` |
| `"Wetter-Provider"` | `"Weather Provider"` |
| `"Standard-Location"` | `"Default Location"` |
| `"Breitengrad"` | `"Latitude"` |
| `"Längengrad"` | `"Longitude"` |
| `"Ortsname"` | `"Location Name"` |
| `"Speichern"` | `"Save"` |
| `"Settings gespeichert"` | `"Settings saved"` |
| `"SMTP nicht vollständig konfiguriert..."` | `"SMTP not fully configured. Please fill all fields."` |
| `"Sende Test-E-Mail..."` | `"Sending test email..."` |
| `"Test-E-Mail Body"` | `"This is a test email from Gregor Zwanzig.\n\nIf you receive this, SMTP is configured correctly!"` |
| `"Konfigurationsfehler:"` | `"Configuration error:"` |
| `"Versand fehlgeschlagen:"` | `"Send failed:"` |
| `"Test-Mail senden"` | `"Send Test Email"` |

### 4. locations.py

| German | English |
|--------|---------|
| `"Location bearbeiten: {name}"` | `"Edit Location: {name}"` |
| `"Breitengrad"` | `"Latitude"` |
| `"Längengrad"` | `"Longitude"` |
| `"Höhe (m)"` | `"Elevation (m)"` |
| `"Lawinenregion"` | `"Avalanche Region"` |
| `"Abbrechen"` | `"Cancel"` |
| `"Speichern"` | `"Save"` |
| `"'{name}' aktualisiert"` | `"'{name}' updated"` |
| `"Neue Location"` | `"New Location"` |
| `"Koordinaten von Google Maps:"` | `"Coordinates from Google Maps:"` |
| `"Google Maps Koordinaten"` | `"Google Maps Coordinates"` |
| `"Koordinaten übernommen"` | `"Coordinates applied"` |
| `"Ungültiges Format"` | `"Invalid format"` |
| `"Lawinenregion (optional)"` | `"Avalanche Region (optional)"` |
| `"Bergfex-Slug (für Schneehöhen)"` | `"Bergfex Slug (for snow depth)"` |
| `"Name ist erforderlich"` | `"Name is required"` |
| `"Location '{name}' gespeichert"` | `"Location '{name}' saved"` |
| `"Noch keine Locations gespeichert."` | `"No locations saved yet."` |
| `"'{name}' gelöscht"` | `"'{name}' deleted"` |
| Placeholder: `"z.B. hochfuegen"` | `"e.g. hochfuegen"` |
| Placeholder: `"z.B. Stubaier Gletscher"` | `"e.g. Stubaier Gletscher"` |
| Placeholder: `"z.B. AT-7"` | `"e.g. AT-7"` |

### 5. trips.py

| German | English |
|--------|---------|
| `"Neuer Trip"` | `"New Trip"` |
| `"Lawinenregionen (kommagetrennt)"` | `"Avalanche Regions (comma-separated)"` |
| `"Etappen"` | `"Stages"` |
| `"Etappe hinzufügen"` | `"Add Stage"` |
| `"Noch keine Etappen..."` | `"No stages yet. Click 'Add Stage'."` |
| `"Etappe {n}"` | `"Stage {n}"` |
| `"Wegpunkte:"` | `"Waypoints:"` |
| `"Punkt {n}"` | `"Point {n}"` |
| `"Höhe (m)"` | `"Elevation (m)"` |
| `"Wegpunkt hinzufügen"` | `"Add Waypoint"` |
| `"Abbrechen"` | `"Cancel"` |
| `"Name ist erforderlich"` | `"Name is required"` |
| `"Mindestens eine Etappe erforderlich"` | `"At least one stage required"` |
| `"Etappe {n} braucht mindestens einen Wegpunkt"` | `"Stage {n} needs at least one waypoint"` |
| `"Ungültiges Datum in Etappe {n}"` | `"Invalid date in Stage {n}"` |
| `"Trip '{name}' gespeichert"` | `"Trip '{name}' saved"` |
| `"Speichern"` | `"Save"` |
| `"Trip bearbeiten"` | `"Edit Trip"` |
| `"Änderungen speichern"` | `"Save Changes"` |
| `"Trip '{name}' aktualisiert"` | `"Trip '{name}' updated"` |
| `"Noch keine Trips gespeichert."` | `"No trips saved yet."` |
| `"{n} Etappe(n), {m} Wegpunkte"` | `"{n} stage(s), {m} waypoints"` |
| `"'{name}' gelöscht"` | `"'{name}' deleted"` |
| Placeholder: `"z.B. Stubaier Skitour"` | `"e.g. Stubai Ski Tour"` |
| Placeholder: `"z.B. AT-7, AT-5"` | `"e.g. AT-7, AT-5"` |

### 6. compare.py (UI)

| German | English |
|--------|---------|
| `"Keine Locations gespeichert..."` | `"No locations saved. Please create locations first."` |
| `"Locations verwalten"` | `"Manage Locations"` |
| `"Locations auswählen"` | `"Select Locations"` |
| `"Locations (Mehrfachauswahl)"` | `"Locations (multiple)"` |
| `"Datum:"` | `"Date:"` |
| `"Heute"` | `"Today"` |
| `"Morgen"` | `"Tomorrow"` |
| `"Übermorgen"` | `"Day after tomorrow"` |
| `"Tag"` | `"Day"` |
| `"Zeitfenster:"` | `"Time Window:"` |
| `"Von"` | `"From"` |
| `"Bis"` | `"To"` |
| `"Lade Forecasts..."` | `"Loading Forecasts..."` |
| `"Wähle Locations und klicke 'Vergleichen'"` | `"Select locations and click 'Compare'"` |
| `"Bitte mindestens eine Location auswählen"` | `"Please select at least one location"` |
| `"Bitte zuerst einen Vergleich durchführen"` | `"Please run a comparison first"` |

### 7. compare.py (Tables)

| German | English |
|--------|---------|
| `"Schneehöhe"` | `"Snow Depth"` |
| `"Neuschnee"` | `"New Snow"` |
| `"Wind/Böen"` | `"Wind/Gusts"` |
| `"Temperatur (gefühlt)"` | `"Temperature (felt)"` |
| `"Sonnenstunden"` | `"Sunny Hours"` |
| `"Bewölkung"` | `"Cloud Cover"` |
| `"Wolkenlage"` | `"Cloud Layer"` |
| `"Stündliche Übersicht"` | `"Hourly Overview"` |
| `"Wolkenschichten Details"` | `"Cloud Layers Details"` |
| `"Vergleich"` | `"Comparison"` |
| `"Empfehlung für {date}:"` | `"Recommendation for {date}:"` |
| `"Keine Ergebnisse"` | `"No results"` |
| `"Alle Abfragen fehlgeschlagen"` | `"All requests failed"` |
| `"Grün = bester Wert..."` | `"Green = best value | Temperature = felt (Wind Chill)"` |

### 8. compare.py (Plain-Text Email)

| German | English |
|--------|---------|
| `"Keine Vergleichsdaten verfügbar."` | `"No comparison data available."` |
| `"Schnee:"` | `"Snow:"` |
| `"Neuschnee:"` | `"New Snow:"` |
| (date format remains `%d.%m.%Y`) | (no change needed) |

### 9. Date Locale Fix

The `strftime('%A')` returns weekday names based on system locale. Options:

**Option A: Manual mapping (recommended)**
```python
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday = WEEKDAY_NAMES[target_date.weekday()]
```

**Option B: Set locale explicitly**
```python
import locale
locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
```

Recommendation: **Option A** - No system dependency, explicit control.

## Expected Behavior

- **Input:** User navigates to any frontend page
- **Output:** All UI elements display English text
- **Side effects:**
  - E-Mails sent via scheduler will have English labels
  - No functional changes to comparison logic

## Known Limitations

1. **Location/Trip names remain user-defined** - These are data, not UI text
2. **Bergfex slugs remain German** - These are API identifiers
3. **Email subjects use English** - Already implemented

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| String length changes | LOW | English is shorter, UI will fit better |
| Pluralization | LOW | English is simpler than German |
| Date locale | MEDIUM | Use manual weekday mapping |
| Missed strings | LOW | Grep-based verification after implementation |

## Verification

After implementation:
```bash
# Check for remaining German strings
grep -rn "gespeichert\|gelöscht\|Speichern\|Abbrechen\|erforderlich\|Etappe\|Wegpunkt" src/web/pages/
```

Expected output: No matches (except comments)

## Changelog

- 2026-01-01: Initial spec created from analysis phase
