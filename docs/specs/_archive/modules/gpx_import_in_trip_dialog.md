---
entity_id: gpx_import_in_trip_dialog
type: feature
created: 2026-02-12
updated: 2026-07-23
status: superseded
version: "2.0"
tags: [ui, gpx, trips, upload, nicegui]
related_specs:
  - gpx_upload
  - etappen_config
---

# GPX Import in Trip-Dialogen

> **HISTORISCH / ABGELÖST (2026-07-23).** Diese Modul-Spec beschreibt einen nicht mehr gültigen Stand — die zugrundeliegende Architektur (NiceGUI-UI unter `src/web/`, Python-APScheduler, Signal-Kanal bzw. Compare-Subscriptions) wurde ersetzt (SvelteKit-Frontend, Go-Scheduler `internal/scheduler/`, briefings/trips). Die genannten Quelldateien existieren nicht mehr. **Aktueller Stand:** der Code + `docs/reference/api_contract.md`. Aufbewahrt zur Nachvollziehbarkeit.

## Approval

- [ ] Approved for implementation

## Purpose

GPX-Upload auf **Stage-Ebene** in die Trip-Dialoge integrieren.
Ein GPX-File entspricht einem Wandertag (= 1 Stage). Für einen Multi-Day-Trip
wie GR221 (4 Tage) importiert der User 4 GPX-Files – je eines pro Stage.

## Datenmodell-Analyse

```
Trip "GR221 Mallorca"
 ├── Stage T1: "Tag 1: Valldemossa → Deià"     ← Tag1.gpx
 │    ├── Waypoint G1: Start (174m)
 │    ├── Waypoint G2: Gipfel (298m)
 │    └── Waypoint G3: Ziel (39m)
 ├── Stage T2: "Tag 2: Deià → Sóller"          ← Tag2.gpx
 │    ├── Waypoint G1: Start
 │    └── ...
 ├── Stage T3: "Tag 3: Sóller → Tossals Verds" ← Tag3.gpx
 └── Stage T4: "Tag 4: Tossals Verds → Lluc"   ← Tag4.gpx
```

**Mapping: 1 GPX-File = 1 Stage mit N Waypoints**

## Source

- **File:** `src/web/pages/trips.py`
- **Reused from:** `src/web/pages/gpx_upload.py` (Processing-Funktionen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `process_gpx_upload` | Function (gpx_upload.py) | GPX validieren, parsen → GPXTrack |
| `compute_full_segmentation` | Function (gpx_upload.py) | Track → Segments Pipeline |
| `segments_to_trip` | Function (gpx_upload.py) | Segments → Trip/Stage/Waypoints |
| `GPXTrack` | DTO (models.py) | Parsed track data |
| `EtappenConfig` | DTO (models.py) | Hiking speed config |

## UX-Flow

### Trip Dialog (New + Edit)

```
┌───────────────────────────────────────────────────────────────┐
│  New Trip / Edit Trip                                         │
│                                                               │
│  Trip Name: [GR221 Mallorca_________________________]         │
│  Avalanche Regions: [______________________________]          │
│                                                               │
│  Stages                       [Add Stage] [+ Stage from GPX] │
│                                                               │
│  ┌─ T1: Tag 1 von Valldemossa nach Deià ──────────────── 🗑 ─┐│
│  │  Datum: [2026-02-12]                                      ││
│  │  Waypoints:                                               ││
│  │    G1: Start      (39.71, 2.62, 174m)              [x]   ││
│  │    G2: Gipfel     (39.74, 2.63, 298m)              [x]   ││
│  │    G3: Ziel       (39.75, 2.65,  39m)              [x]   ││
│  │  [Add Waypoint] [📎 Import Waypoints from GPX]           ││
│  └───────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌─ T2: (leer, auf GPX oder manuelle Eingabe wartend) ── 🗑 ─┐│
│  │  ...                                                      ││
│  └───────────────────────────────────────────────────────────┘│
│                                                               │
│                                       [Cancel] [Save]         │
└───────────────────────────────────────────────────────────────┘
```

### Zwei Wege, eine Stage per GPX zu befüllen:

**Weg 1: "Stage from GPX" Button (neben "Add Stage")**

1. User klickt "Stage from GPX"
2. File-Picker öffnet sich
3. GPX wird geparst → Neue Stage wird erstellt mit:
   - Name aus GPX-Track ("Tag 1: von Valldemossa nach Deià")
   - Datum: auto-increment vom letzten Stage (+1 Tag)
   - Waypoints: aus GPX-Segmentierung berechnet
4. Stage erscheint in der Liste, voll editierbar

**Weg 2: "Import Waypoints from GPX" Button (innerhalb einer Stage)**

1. User hat bereits eine (leere oder manuelle) Stage
2. Klickt "Import Waypoints from GPX" innerhalb dieser Stage
3. GPX wird geparst → Waypoints der Stage werden ersetzt
4. Stage-Name wird aktualisiert (falls leer)
5. Bestehende Waypoints gehen verloren (mit Warnung falls vorhanden)

### Typischer Multi-Day Flow (GR221)

```
1. "New Trip" → Name: "GR221 Mallorca"
2. [+ Stage from GPX] → Tag1.gpx hochladen → T1 erscheint mit Waypoints
3. [+ Stage from GPX] → Tag2.gpx hochladen → T2 erscheint
4. [+ Stage from GPX] → Tag3.gpx hochladen → T3 erscheint
5. [+ Stage from GPX] → Tag4.gpx hochladen → T4 erscheint
6. Optional: Waypoints manuell anpassen
7. [Save]
```

### Trips-Übersichtsseite

```
[🗺 New Trip]  [📎 Import GPX]
```

"Import GPX" öffnet den New-Trip-Dialog (= Shortcut).

## Implementation Details

### 1. gpx_to_stage_data() – GPX → einzelne Stage-Dict

```python
def gpx_to_stage_data(
    content: bytes,
    filename: str,
    stage_date: date | None = None,
    start_hour: int = 8,
) -> dict:
    """Parse GPX file and return a single stage dict for the trip dialog.

    Returns dict with keys: name, date, waypoints[]
    """
    track = process_gpx_upload(content, filename)
    d = stage_date or date.today()

    config = EtappenConfig()
    start_time = datetime(d.year, d.month, d.day, start_hour, 0, 0,
                          tzinfo=timezone.utc)
    segments = compute_full_segmentation(track, config, start_time)
    trip = segments_to_trip(segments, track, d)

    stage = trip.stages[0]  # 1 GPX = 1 Stage
    return {
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
```

### 2. "Stage from GPX" Button (neben "Add Stage")

```python
def make_add_stage_gpx_handler():
    """Factory: add new stage from GPX file."""
    file_input = ui.upload(...)  # hidden upload widget

    async def do_upload(e):
        content = await e.file.read()
        filename = e.file.name
        # Auto-date: last stage date + 1 day
        if stages_data:
            last_date = date.fromisoformat(stages_data[-1]["date"])
            stage_date = last_date + timedelta(days=1)
        else:
            stage_date = date.today()

        try:
            stage_dict = gpx_to_stage_data(content, filename, stage_date)
            stages_data.append(stage_dict)
            stages_ui.refresh()
            n_wps = len(stage_dict["waypoints"])
            ui.notify(f"Stage '{stage_dict['name']}' aus GPX: {n_wps} Waypoints",
                      type="positive")
        except Exception as err:
            ui.notify(f"GPX-Fehler: {err}", type="negative")
    return do_upload

ui.button("Stage from GPX", on_click=..., icon="upload_file").props("outline size=sm")
```

### 3. "Import Waypoints from GPX" Button (innerhalb einer Stage)

```python
def make_import_wp_gpx_handler(stage_dict, stages_ui_refresh):
    """Factory: replace waypoints of existing stage from GPX."""
    async def do_upload(e):
        content = await e.file.read()
        filename = e.file.name
        stage_date = date.fromisoformat(stage_dict["date"])

        try:
            imported = gpx_to_stage_data(content, filename, stage_date)
            # Replace waypoints
            stage_dict["waypoints"] = imported["waypoints"]
            # Update name if default
            if stage_dict["name"].startswith("Stage "):
                stage_dict["name"] = imported["name"]
            stages_ui_refresh()
            ui.notify(f"GPX importiert: {len(imported['waypoints'])} Waypoints",
                      type="positive")
        except Exception as err:
            ui.notify(f"GPX-Fehler: {err}", type="negative")
    return do_upload
```

### 4. Upload-Widget Technik

NiceGUI `ui.upload` braucht ein sichtbares Widget. Für den "Stage from GPX"
Button gibt es zwei Optionen:

**Option A:** Sichtbares Upload-Widget neben dem Button (einfacher)
```python
ui.upload(on_upload=handler, auto_upload=True, label="Stage from GPX")
    .props('accept=".gpx"').classes("w-40")
```

**Option B:** Hidden Upload + Button-Trigger (eleganter, aber komplexer)

Empfehlung: **Option A** – sichtbar, klar, weniger Code.

### 5. Platzierung im Dialog

```python
# In show_add_dialog() und show_edit_dialog():

with ui.row().classes("items-center justify-between w-full"):
    ui.label("Stages").classes("text-h6")
    with ui.row().classes("gap-2"):
        ui.button("Add Stage", on_click=make_add_stage_handler(), icon="add")
            .props("outline size=sm")
        ui.upload(
            on_upload=make_add_stage_gpx_handler(),
            auto_upload=True,
            max_files=1,
            label="Stage from GPX",
        ).props('accept=".gpx" flat dense').classes("w-44")

# Inside each stage card (after waypoint list):
with ui.row().classes("gap-2 mt-1"):
    ui.button("Add Waypoint", on_click=make_add_wp(stage), icon="add_location")
        .props("flat dense size=sm")
    ui.upload(
        on_upload=make_import_wp_gpx_handler(stage, stages_ui.refresh),
        auto_upload=True,
        max_files=1,
        label="GPX Import",
    ).props('accept=".gpx" flat dense').classes("w-36")
```

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/web/pages/trips.py` | GPX handlers, upload widgets in both dialogs | ~+80 |

**Total:** ~+80 LoC in 1 file.

## Test Plan

### Automated Tests

- [ ] `test_gpx_to_stage_data`: GPX bytes → stage dict mit korrekten Waypoints
- [ ] `test_gpx_to_stage_data_custom_date`: Übergebenes Datum wird verwendet
- [ ] `test_gpx_to_stage_data_invalid`: Ungültige GPX → Exception

### Manual Tests

- [ ] "Stage from GPX" → GPX uploaden → Stage mit Waypoints erscheint
- [ ] Mehrfach "Stage from GPX" → Multi-Stage Trip (4x GPX)
- [ ] "Import Waypoints from GPX" innerhalb Stage → Waypoints ersetzt
- [ ] Stage-Datum auto-increment bei mehreren GPX-Imports
- [ ] Edit-Dialog: "Stage from GPX" funktioniert auch
- [ ] Manuelles Editieren nach GPX-Import (Waypoints hinzufügen/entfernen)
- [ ] Safari: alle Buttons/Uploads funktionieren
- [ ] "Import GPX" Button auf Trips-Übersichtsseite

## Acceptance Criteria

- [ ] "Stage from GPX" Button neben "Add Stage" in beiden Dialogen
- [ ] "Import Waypoints from GPX" Button innerhalb jeder Stage
- [ ] 1 GPX = 1 Stage mit berechneten Waypoints
- [ ] Multi-Stage via mehrfaches GPX-Import (Datum auto-inkrement)
- [ ] Stage-Name aus GPX-Track übernommen
- [ ] Manuelles Bearbeiten nach Import möglich
- [ ] "Import GPX" Button auf Trips-Übersichtsseite
- [ ] Safari-kompatibel (Factory Pattern)
- [ ] Bestehende Standalone-Seite `/gpx-upload` bleibt erhalten

## Known Limitations

1. **1 GPX = 1 Stage:** Ein GPX-File erzeugt immer genau eine Stage.
   Für einen 4-Tage-Trip braucht man 4 separate GPX-Files.

2. **Default Hiking Config:** Segmentierung nutzt EtappenConfig-Defaults
   (4 km/h, 300 Hm/h, 500 Hm/h). Für individuelle Konfiguration weiterhin
   die Standalone-Seite `/gpx-upload` nutzen.

3. **Kein Re-Compute:** Nach manuellem Editieren der Waypoints werden
   die Zeiten nicht neu berechnet.

4. **Upload-Widget Styling:** NiceGUI `ui.upload` hat ein festes Styling
   das ggf. nicht perfekt in die kompakten Stage-Cards passt.

## Changelog

- 2026-02-12: v2.0 – Komplett überarbeitet: GPX Import auf Stage-Ebene statt Trip-Ebene
- 2026-02-12: v1.0 – Erster Entwurf (GPX Import auf Trip-Ebene, verworfen)
