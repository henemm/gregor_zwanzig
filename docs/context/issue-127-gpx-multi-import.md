# Issue #127 — Multi-GPX-Upload mit Natural-Sort und Startdatum-Abfrage

**Status:** Analysis abgeschlossen, bereit für `/3-write-spec`
**Priorität:** high
**Workflow:** issue-127-gpx-multi-import

## Problem

Trip 5f534011 (KHW 403, 13 Etappen) zeigt zwei Symptome:
- Etappen-Reihenfolge: `KHW_00a, KHW_11, KHW_10, …, KHW_01, KHW_00b` (Browser-FileList-Reihenfolge statt natural-sort)
- Alle 13 Etappen mit `date: "2026-05-04"` (heute), kein Startdatum abgefragt

## Affected Files (Recherche bestätigt)

| Pfad | Rolle | Heute |
|------|-------|-------|
| `src/web/pages/trips.py:146` | New-Trip-Dialog "Add Stage from GPX" | `max_files=1` |
| `src/web/pages/trips.py:~420` | Edit-Trip-Dialog "Add Stage from GPX" | `max_files=1` |
| `src/web/pages/trips.py:272, 551` | Per-Stage "Import Waypoints from GPX" | `max_files=1` (bleibt) |
| `src/web/pages/trips.py:31-76` | `gpx_to_stage_data(stage_date, …)` | Reusable-Helper |
| `src/app/trip.py:76-116` | `Stage` frozen dataclass | Felder: id, name, date, waypoints, start_time |
| `src/core/gpx_parser.py:115-121` | `_extract_name()` | Fallback "Unnamed Track" |
| `src/app/loader.py:660` | `save_trip()` | Read-Modify-Write korrekt (siehe Edit-Dialog 627-642) |

## Existing Spec (KRITISCH)

`docs/specs/modules/gpx_import_in_trip_dialog.md` (draft v2.0) beschreibt bereits Auto-Date-Increment:
```python
if stages_data:
    last_date = date.fromisoformat(stages_data[-1]["date"])
    stage_date = last_date + timedelta(days=1)
else:
    stage_date = date.today()
```
→ Erweiterung dieses Patterns um Multi-File + explizite Startdatum-Abfrage.

## Architektur-Entscheidung (Plan-Agent-Empfehlung)

1. **Welches Widget?** Nur die zwei "Add Stage from GPX"-Widgets (Dialog-Ebene). Per-Stage-Waypoint-Imports bleiben single-file.
2. **Multi-Upload:** `max_files=-1` am bestehenden Widget + Puffer-Liste in der Closure.
3. **Startdatum-Flow:** Nach Datei-Auswahl (User wählt N GPX → Files werden gepuffert → Datumspicker erscheint → expliziter "Add X Stages"-Button committed).
4. **Natural-Sort:** Standalone-Helper `src/core/natural_sort.py` — testbar ohne UI, wiederverwendbar, trivial (`re.split(r'(\d+)', s)` als Key).

## Constraints (CLAUDE.md)

- **Safari Factory Pattern:** Neuer Commit-Button via `make_commit_handler()` Factory.
- **Schema-Pre-Snapshot:** Hook `data_schema_backup.py` läuft automatisch bei Edit von `src/app/trip.py` etc. (für dieses Feature voraussichtlich nicht nötig — Stage-Schema ändert sich nicht).
- **Keine Mocks:** Tests gegen echte GPX-Bytes (Fixtures vorhanden), Playwright für UI-E2E.
- **Read-Modify-Write:** Bestehender `save_trip()`-Pfad nutzt das bereits korrekt — kein Risiko.

## Scoping

| File | Status | LOC |
|------|--------|-----|
| `src/core/natural_sort.py` | NEU | ~25 |
| `src/web/pages/trips.py` | GEÄNDERT | ~80 |
| `tests/unit/test_natural_sort.py` | NEU (TEST) | ~40 |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | GEÄNDERT (TEST) | ~45 |

**Total ~190 LOC, 4 Files** — innerhalb der Workflow-Grenzen (max 5 Files, max 250 LOC).

## Risks

- **NiceGUI Multi-File-API:** `on_upload` feuert pro Datei einzeln, sequenziell — Puffer im Closure-State sammelt, expliziter Commit-Button verarbeitet.
- **Safari:** Neuer Commit-Button braucht Factory Pattern.
- **Backwards-Compat:** Single-File-Upload muss weiter funktionieren (1 Datei, kein Datumspicker-Zwang? offen).
- **Duplizierte Handler-Logik:** New- und Edit-Dialog haben heute schon parallele Handler — Feature-Scope: minimaler Patch in beiden statt Refactoring.

## Offene Fragen für User (vor `/3-write-spec`)

1. **Commit-Flow:** Expliziter "Add N Stages"-Button nach Upload, oder Auto-Commit nach letzter Datei? **Empfehlung Plan-Agent:** Expliziter Button (klarer State, Safari-sicher).
2. **Startdatum-Default:** Bei bereits vorhandenen Stages → vorbelegt mit `last_stage_date + 1 Tag`, sonst leer/heute? **Empfehlung:** vorbelegt wenn vorhanden, sonst heute.
3. **Fehlerbehandlung:** Datei #7 kaputt — alle oder keine, oder Skip mit Warnung und Datum-Versatz für Folgeetappen? **Empfehlung:** Skip mit Warnung, Datum lückenlos für gültige Files.
4. **Refactoring-Scope:** Duplikation in New/Edit zusammen entfernen, oder beide separat patchen? **Empfehlung:** Beide separat patchen (Scope minimal halten).

## Test-Strategie

- **Unit:** `test_natural_sort.py` — Sortier-Reihenfolge mit KHW-Pattern, Edge-Cases.
- **Unit:** `test_gpx_import_in_trip_dialog.py` — neue Klasse `TestMultiGpxDatePropagation`, Single-File-Fallback bleibt.
- **E2E:** Playwright via `e2e_browser_test.py` — `set_input_files()` mit 3 GPX in falscher Reihenfolge, Datumspicker, Commit, Stage-Labels prüfen.

## Nächste Schritte

1. User beantwortet die 4 offenen Fragen.
2. `/3-write-spec` erstellt Spec basierend auf Antworten + dieser Analyse.
3. `/4-tdd-red` schreibt fehlschlagende Tests.
4. `/5-implement` mit Developer-Agent in Worktree.
