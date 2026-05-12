---
entity_id: epic_129a_2_gpx_helpers
type: refactor
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [refactor, tech-debt, epic-129, services-extraction]
---

<!-- GitHub Issue #129 (Phase A.2 von A.1/A.2/A.3/B) — GPX-Helper + Coordinates aus NiceGUI-UI extrahieren -->

# Epic #129 Phase A.2 — GPX-Helper + Coordinates aus NiceGUI extrahieren

## Approval

- [ ] Approved

## Purpose

Zweite von vier Etappen zur ersatzlosen Entfernung der NiceGUI-UI (Issue #129). Nach Phase A.1 (Compare-Helper) ziehen wir jetzt die UI-freien Helper aus `src/web/pages/gpx_upload.py`, `src/web/pages/trips.py` und `src/web/utils.py` nach `src/services/` um.

Phase-2-Analyse hat bestätigt: Alle 8 zu extrahierenden Funktionen sind UI-frei (kein `nicegui`-Import, kein `ui.*`-Call). `gpx_to_stage_data` ist API-Contract-relevant (`api/routers/gpx.py:16` — Production-Endpoint), Signatur und Rückgabe-Struktur bleiben unverändert.

## Source

### Neue Dateien (in `src/services/`)

| Datei | Inhalt |
|-------|--------|
| `src/services/coordinates.py` | `parse_dms_coordinates` (`web/utils.py` → komplett umziehen, Datei wird leer) |
| `src/services/gpx_processing.py` | `process_gpx_upload`, `compute_full_segmentation`, `segments_to_trip` (aus `gpx_upload.py`) + `gpx_to_stage_data`, `process_bulk_gpx_uploads`, `compute_default_start_date` (aus `trips.py`) |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `src/web/pages/gpx_upload.py` | Helper-Definitionen (3 Funktionen) entfernt → ersetzt durch `from services.gpx_processing import …`. UI-Code (`render_gpx_upload`, `render_header`) bleibt. |
| `src/web/pages/trips.py` | Helper-Definitionen (3 Funktionen) entfernt → Re-Imports aus `services.gpx_processing`. DMS-Import von `web.utils` → `services.coordinates`. UI-Code bleibt. |
| `src/web/utils.py` | **Tote Funktion `format_decimal_to_dms` ersatzlos gelöscht** (von Phase-2-Analyse als nicht aufgerufen verifiziert). `parse_dms_coordinates` zieht nach `services/coordinates.py` um. Datei wird **komplett gelöscht** (war nur diese 2 Funktionen). |
| `api/routers/gpx.py` (Z. 16) | `from src.web.pages.trips import gpx_to_stage_data` → `from services.gpx_processing import gpx_to_stage_data` |
| `tests/unit/test_gpx_upload_page.py` | Imports umstellen auf `services.gpx_processing` |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | Imports umstellen auf `services.gpx_processing` |
| `tests/unit/test_etappen_config.py` | Imports umstellen, falls dort GPX-Helper getestet werden |
| `tests/unit/test_trips_time_window_bugfix.py` | Imports umstellen (`gpx_to_stage_data`) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `core.gpx_parser`, `core.elevation_analysis`, `core.hybrid_segmentation`, `core.segment_builder` | python modules | Werden weiterhin von den extrahierten Helpers genutzt — bleiben unverändert |
| `app.models.{EtappenConfig, GPXTrack, TripSegment}`, `app.trip.{Trip, Stage, Waypoint, ...}` | DTOs | werden von `segments_to_trip` etc. genutzt |
| `core.natural_sort.natural_sort_key` | python function | Wird von `process_bulk_gpx_uploads` aufgerufen |
| `api/routers/gpx.py` | FastAPI router | Production-API — Signatur von `gpx_to_stage_data` MUSS stabil bleiben |

## Implementation Details

### Reihenfolge der Extraktion

1. **`src/services/coordinates.py`** zuerst — keine internen Deps. Nur `parse_dms_coordinates`.
2. **`src/services/gpx_processing.py`** anlegen mit der inneren Reihenfolge:
   - `process_gpx_upload` (keine Deps)
   - `compute_full_segmentation` (nur core.* externals)
   - `segments_to_trip` (keine internen)
   - `compute_default_start_date` (keine Deps)
   - `gpx_to_stage_data` (nutzt `process_gpx_upload` + `compute_full_segmentation` + `segments_to_trip`)
   - `process_bulk_gpx_uploads` (nutzt `gpx_to_stage_data` + `natural_sort_key`)
3. **Re-Imports in `gpx_upload.py` und `trips.py`** ergänzen.
4. **Externe Imports umstellen** (api/routers/gpx.py + 4 Test-Files).
5. **`web/utils.py` löschen** + `format_decimal_to_dms` entfällt (tot).

### API-Contract-Stabilität (Pflicht!)

`gpx_to_stage_data` ist von `api/routers/gpx.py:16` importiert (Production-Endpoint `POST /api/gpx/parse`). Vertrag:

- **Signatur:** unverändert (Args wie heute)
- **Rückgabe:** `dict` mit Keys `name`, `date`, `waypoints[]` — Struktur unverändert
- Verifikation: bestehende Integration-Tests gegen den Endpoint laufen weiter (z. B. `tests/integration/` falls existent), Smoke-Test gegen Staging nach Push.

### Übergangs-Pattern in `gpx_upload.py` und `trips.py`

```python
# In gpx_upload.py (übergangsweise, bis Phase A.3)
from services.gpx_processing import (
    process_gpx_upload,
    compute_full_segmentation,
    segments_to_trip,
)

# In trips.py
from services.gpx_processing import (
    gpx_to_stage_data,
    process_bulk_gpx_uploads,
    compute_default_start_date,
)
from services.coordinates import parse_dms_coordinates  # statt: from web.utils import …
```

### Was NICHT in dieser Phase passiert

- **UI-Funktionen** (`render_gpx_upload`, `render_trips`, `render_header`, `make_*_handler`-Factories, `commit_row*`) bleiben in `pages/gpx_upload.py` bzw. `pages/trips.py`. Werden in Phase A.3 mit den ganzen Files gelöscht.
- **`pages/compare.py`-Helper** wurden in Phase A.1 erledigt.

## Expected Behavior

- **Pre-Refactor:** `pytest tests/unit/test_gpx_*` grün, `api/routers/gpx.py` lädt sauber. NiceGUI-Service auf Prod startet ok.
- **Post-Refactor:** identisch — keine funktionale Änderung. Nur Datei-Layout.
- **API:** `POST /api/gpx/parse` liefert exakt dieselbe Response wie heute (gleiche Struktur, gleiche Felder).
- **Side effects:** `src/services/` bekommt 2 neue Module. `src/web/utils.py` ist weg. `pages/gpx_upload.py` und `pages/trips.py` schrumpfen um die 6 Helper.

## Acceptance Criteria

- **AC-1:** Given die 5 betroffenen externen Importeure (`api/routers/gpx.py`, `tests/unit/test_gpx_upload_page.py`, `test_gpx_import_in_trip_dialog.py`, `test_etappen_config.py`, `test_trips_time_window_bugfix.py`) / When grep nach `from web.pages.trips`, `from web.pages.gpx_upload`, `from web.utils`, `from src.web.pages.trips`, `from src.web.pages.gpx_upload`, `from src.web.utils` läuft / Then **kein Treffer** in diesen 5 Dateien.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die 2 neuen Service-Module / When per `importlib.import_module("services.coordinates")` und `importlib.import_module("services.gpx_processing")` geladen / Then alle erwarteten Symbole vorhanden: `parse_dms_coordinates`, `process_gpx_upload`, `compute_full_segmentation`, `segments_to_trip`, `gpx_to_stage_data`, `process_bulk_gpx_uploads`, `compute_default_start_date`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Production-API-Endpoint `POST /api/gpx/parse` / When der Endpoint mit dem bestehenden Integration-Test (oder einem äquivalenten Test gegen die FastAPI-App) aufgerufen wird / Then liefert er weiterhin ein `dict` mit den Keys `name`, `date`, `waypoints` — Struktur und Typen unverändert. Verifikation per `inspect.signature(gpx_to_stage_data)` zusätzlich.
  - Test: (populated after /tdd-red)

- **AC-4:** Given der NiceGUI-Service `gregor_zwanzig.service` läuft mit den gepatchten Files (`gpx_upload.py`, `trips.py`) / When der Service neu startet / Then **kein ImportError** in den Logs (Re-Imports korrekt, UI-Funktionen weiter lauffähig).
  - Test: (populated after /tdd-red)

- **AC-5:** Given die tote Funktion `format_decimal_to_dms` und die Datei `src/web/utils.py` / When grep nach diesen Bezeichnern im gesamten Repo (`*.py`, exklusive `.git`, `.claude/worktrees/`) läuft / Then **0 Treffer** für `def format_decimal_to_dms`. Datei `src/web/utils.py` existiert nicht mehr (oder ist leer).
  - Test: (populated after /tdd-red)

## Out of Scope (für Phase A.2)

- **`src/web/pages/{gpx_upload,trips}.py` ersatzlos löschen** → Phase A.3
- **Compare-Helper** → Phase A.1 (bereits erledigt)
- **systemd-Service deaktivieren, CLAUDE.md, Spec-Template** → Phase B
- **Mock-Verstoß in test_html_email.py** → Issue #201 (separat)

## Verification

- **Unit:** `uv run pytest tests/refactor/test_epic_129a_2_*.py tests/unit/test_gpx_*.py tests/unit/test_etappen_config.py tests/unit/test_trips_time_window_bugfix.py -v` (scoped, nicht der ganze tests/-Lauf)
- **API-Smoke:** Ein Smoke-Test, der `gpx_to_stage_data` mit einer Beispiel-GPX aufruft und die Rückgabe-Struktur prüft (oder bestehender Integration-Test gegen `/api/gpx/parse` falls vorhanden)
- **Vollständiger Lauf vor Push:** `uv run pytest tests/ -q --tb=short` muss grün bleiben (Endergebnis-Vergleich main vs. refactor)
- **Smoke-Test Production nach Deploy:**
  ```bash
  curl -s https://gregor20.henemm.com/api/health
  curl -s -F "file=@beispiel.gpx" https://gregor20.henemm.com/api/gpx/parse
  sudo systemctl status gregor_zwanzig.service  # muss "active (running)"
  ```

## LoC-Estimate

- **`coordinates.py` neu:** ~75 LoC (eine Funktion)
- **`gpx_processing.py` neu:** ~250 LoC (6 Funktionen mit mittlerer Größe)
- **`web/utils.py` gelöscht:** -75 LoC
- **`gpx_upload.py` Helper raus:** -150 LoC, +5 LoC Re-Imports
- **`trips.py` Helper raus:** -100 LoC, +6 LoC Re-Imports
- **5 externe Importe:** ±5 LoC
- **Erwartetes LoC-Delta:** ca. **+325 / -325 = neutral**, Tool zählt evtl. anders. **Override auf 1500 (analog A.1) zur Sicherheit.**

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| API-Contract `gpx_to_stage_data` versehentlich verändert | mittel | AC-3 mit Signatur- + Struktur-Test |
| Vergessener Helper-Import → NiceGUI-Service crasht | mittel | AC-4 (Service-Restart-Smoke nach Prod-Deploy), `pytest tests/` |
| `process_gpx_upload` File-I/O-Pfad ändert sich (relative vs. absolute Pfade) | niedrig | Bestehende Tests prüfen das, plus File-I/O-Pfad-Logik wörtlich kopieren |
| Re-Imports in `trips.py` schaffen zirkuläre Imports | sehr niedrig | A.1-Pattern, Phase-2-Analyse hat keine Zirkularität gefunden |
| `format_decimal_to_dms` doch irgendwo benutzt | sehr niedrig | AC-5 (grep), pytest |
