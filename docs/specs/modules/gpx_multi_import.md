---
entity_id: gpx_multi_import
type: module
created: 2026-05-04
updated: 2026-05-05
status: draft
version: "1.1"
issue: 127
tags: [ui, gpx, trips, upload, sveltekit, natural-sort]
related_specs:
  - gpx_import_in_trip_dialog
  - gpx_upload
---

# Multi-GPX-Upload mit Natural-Sort und Startdatum-Abfrage

**Status:** DRAFT
**Issue:** [#127 Multi-GPX-Upload mit Natural-Sort und Startdatum-Abfrage](https://github.com/henemm/gregor_zwanzig/issues/127)

## Approval

- [ ] Approved

## Architektur-Hinweis (v1.1, kritisch)

**Die User-UI ist SvelteKit, nicht NiceGUI.** Die in v1.0 spezifizierten
Änderungen an `src/web/pages/trips.py` (NiceGUI) sind als Begleit-Patch
vorhanden, **wirken aber nicht** auf gregor20.henemm.com. Nginx routet alle
externen Anfragen an den SvelteKit-Frontend-Service (Port 3000) und an die
Go-API (Port 8090); die Python-NiceGUI auf Port 8080 ist von außen
unerreichbar.

→ **Die echte Implementierung dieses Features muss im SvelteKit-Frontend
erfolgen** (`frontend/src/lib/components/wizard/WizardStep1Route.svelte` u.a.).
Tech-Debt-Issue #129 räumt die Python-NiceGUI in einem späteren Schritt auf.

### Affected Files (v1.1 — SvelteKit-Schicht)

| Pfad | Status | Rolle |
|------|--------|-------|
| `frontend/src/lib/utils/naturalSort.ts` | NEU | TS-Sortier-Helper |
| `frontend/src/lib/components/wizard/WizardStep1Route.svelte` | GEÄNDERT | Multi-Upload-Buffer + Datums-Picker + Commit-Button |
| `frontend/src/lib/api.ts` | ggf. GEÄNDERT | `uploadGpx()` ohne `today()` als Default — Datum wird vom Aufrufer übergeben |
| `frontend/e2e/trip-wizard-multi-gpx.spec.ts` | NEU (TEST) | Playwright E2E |
| `frontend/src/lib/utils/naturalSort.test.ts` | NEU (TEST) | Vitest oder Playwright-Unit |

### Begleit-Patch v1.0 (NiceGUI)

`src/core/natural_sort.py` und Änderungen an `src/web/pages/trips.py` bleiben
als parallele Implementierung erhalten, bis Issue #129 die NiceGUI-Schicht
ersatzlos entfernt. Sie schaden nicht, sind aber für den User unsichtbar.

## Purpose

Erweitert die beiden "Add Stage from GPX"-Widgets im Trip-Dialog (New + Edit) um
Multi-File-Upload mit natürlicher Sortierung und expliziter Startdatum-Abfrage.
Heute werden bei Mehrfach-Auswahl die Dateien in Browser-FileList-Reihenfolge
verarbeitet (Beispiel KHW 403: `KHW_00a, KHW_11, KHW_10, …`) und alle Etappen
bekommen `date.today()` als Datum — ein Trip mit 13 GPX-Files muss heute manuell
nachsortiert und 13× im Datum korrigiert werden.

**Warum jetzt?** Trip 5f534011 (Kaiser-Hirsch-Weg, 13 Etappen) hat das Problem
real ausgelöst (Issue #127). Die bestehende Spec
`gpx_import_in_trip_dialog.md` v2.0 beschreibt bereits das
Auto-Date-Increment-Pattern für Einzelimporte — diese Spec erweitert es
konsequent auf Multi-Upload und macht die Startdatum-Wahl explizit (statt
implizit `date.today()`).

## Source

- **Neue Datei:** `src/core/natural_sort.py` — pure Helper-Funktion
- **Geänderte Datei:** `src/web/pages/trips.py` — Dialog-Ebene Multi-Upload-Widgets
- **Identifier:** `natural_sort_key(s: str) -> list`,
  `make_commit_bulk_gpx_handler()` (Factory),
  `do_commit_bulk_gpx()` (Handler)

## Scope

### In-Scope

- Standalone-Helper `src/core/natural_sort.py` mit `natural_sort_key()`
- Multi-File-Upload (`max_files=-1`) auf den zwei Dialog-Ebenen-Widgets:
  - `src/web/pages/trips.py:146` (New-Trip-Dialog "Add Stage from GPX")
  - `src/web/pages/trips.py:~420` (Edit-Trip-Dialog "Add Stage from GPX")
- Pufferung der hochgeladenen Bytes in einer Closure-Liste pro Dialog-Instanz
- Datums-Picker und expliziter Commit-Button "X Etappen anlegen" nach Upload
- Natural-Sort der gepufferten Dateinamen vor dem Anlegen der Stages
- Datums-Propagation: erste Stage = gewähltes Startdatum, jede weitere +1 Tag
- Skip-mit-Warnung bei korrupten GPX-Dateien (Datum lückenlos für valide Files)
- Unit-Tests für `natural_sort_key()` und für die Datums-/Reihenfolge-Logik
- E2E-Test (Playwright) für den Multi-Upload-Flow im New-Trip-Dialog

### Out-of-Scope

- Per-Stage-"Import Waypoints from GPX"-Widgets (`trips.py:272`, `trips.py:551`)
  bleiben single-file (`max_files=1`) — sie ersetzen Waypoints einer
  bestehenden Stage, dort gibt es keine Reihenfolge-Frage
- Konsolidierung der Duplikat-Logik zwischen New- und Edit-Trip-Dialog —
  beide Handler werden separat gepatcht (Scope minimal halten)
- Änderungen an `Stage`-Schema, `loader.py`, `save_trip()` oder Persistenz
  (Read-Modify-Write-Pfad in `trips.py:627-642` bleibt unverändert)
- Änderungen an `gpx_to_stage_data()` selbst — die Funktion akzeptiert bereits
  ein `stage_date`-Argument
- Externe Dependencies (z.B. `natsort`-Library) — nutzen `re` aus stdlib

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/web/pages/trips.py::gpx_to_stage_data` | Function (existiert) | GPX bytes → stage dict, Datums-Argument bereits vorhanden |
| `src/web/pages/gpx_upload.py::process_gpx_upload` | Function (existiert) | GPX validieren + parsen (wirft bei Korruption) |
| `src/core/natural_sort.py::natural_sort_key` | Function (NEU) | Sortier-Key für Dateinamen via `re.split(r'(\d+)', s)` |
| `re` | Stdlib | Regex-Split für numerische Tokens |
| `datetime.date`, `datetime.timedelta` | Stdlib | Datums-Propagation |
| `nicegui.ui` | Library (vorhanden) | `ui.upload(max_files=-1)`, `ui.date`, `ui.button`, `ui.notify` |
| `gpxpy` | Library (vorhanden) | wird transitiv über `process_gpx_upload` genutzt |

## Implementation Details

### 1. Natural-Sort-Helper

```python
# src/core/natural_sort.py
"""Natural sort key helper.

Splits a string into numeric and non-numeric chunks so that "KHW_10" sorts
after "KHW_2" (instead of lexicographically before it).
"""

import re

_NUM_RE = re.compile(r"(\d+)")


def natural_sort_key(s: str) -> list:
    """Return a sort key that orders embedded integers numerically.

    Examples:
        sorted(["KHW_11", "KHW_00a", "KHW_10"], key=natural_sort_key)
            == ["KHW_00a", "KHW_10", "KHW_11"]
        sorted(["10.gpx", "2.gpx", "1.gpx"], key=natural_sort_key)
            == ["1.gpx", "2.gpx", "10.gpx"]
    """
    parts = _NUM_RE.split(s)
    # Even indices: literal text (case-insensitive), odd indices: numeric tokens
    return [
        int(p) if i % 2 == 1 else p.lower()
        for i, p in enumerate(parts)
    ]
```

**Bewusste Entscheidungen:**

- `s.lower()` für Text-Tokens → Sortierung ist case-insensitive
  (`KHW_*` vs. `khw_*` werden gleich behandelt)
- `re.split` mit Capture-Group erhält die numerischen Tokens als eigene
  Listen-Elemente — daher das alternierende `i % 2 == 1`-Muster
- `int(p)` für numerische Tokens → ermöglicht numerische Reihenfolge
- Keine externe Library — `natsort` wäre overkill für 25 LoC

### 2. Multi-Upload-Widget (Dialog-Ebene, New-Trip + Edit-Trip)

**Heute (`trips.py:146-170` und ~`trips.py:420`):**

```python
def make_add_stage_gpx_handler():
    async def do_upload(e):
        content = await e.content.read()
        ...  # eine Datei → eine Stage, date.today()
    return do_upload

ui.upload(on_upload=make_add_stage_gpx_handler(),
          auto_upload=True, max_files=1, ...)
```

**Neu — Pufferung + expliziter Commit:**

```python
# Closure-State pro Dialog-Instanz
pending_gpx: list[tuple[str, bytes]] = []  # (filename, content_bytes)
commit_row_container = ui.column().classes("w-full")  # erscheint nach 1. Upload

def make_buffer_gpx_handler():
    """Factory: buffer uploaded GPX files until user commits."""
    async def do_buffer(e):
        content = await e.content.read()
        pending_gpx.append((e.name, content))
        _refresh_commit_row()  # zeigt Datumspicker + "X Etappen anlegen"
    return do_buffer

def make_commit_bulk_gpx_handler(date_input, pending_ref):
    """Factory: process buffered GPX files in natural-sorted order.

    Safari Factory Pattern (CLAUDE.md): Closure-Capture explizit über
    Factory, do_commit_bulk_gpx() ist die per ui.button(on_click=...)
    übergebene Callable.
    """
    def do_commit_bulk_gpx():
        if not pending_ref:
            return
        try:
            start_date = date.fromisoformat(date_input.value)
        except (TypeError, ValueError):
            ui.notify("Bitte Startdatum wählen", type="negative")
            return

        # Natural-sort by filename
        sorted_files = sorted(pending_ref, key=lambda t: natural_sort_key(t[0]))

        added = 0
        skipped = 0
        for content, filename in [(c, n) for (n, c) in sorted_files]:
            stage_date = start_date + timedelta(days=added)
            try:
                stage_dict = gpx_to_stage_data(content, filename, stage_date)
                stages_data.append(stage_dict)
                added += 1
            except Exception as err:
                skipped += 1
                ui.notify(
                    f"GPX '{filename}' übersprungen: {err}",
                    type="warning",
                )

        pending_ref.clear()
        _refresh_commit_row()
        stages_ui.refresh()

        if added:
            msg = f"{added} Etappen angelegt ab {start_date.isoformat()}"
            if skipped:
                msg += f" ({skipped} übersprungen)"
            ui.notify(msg, type="positive")
    return do_commit_bulk_gpx


def _refresh_commit_row():
    """Render commit row when buffer has files; clear when empty."""
    commit_row_container.clear()
    if not pending_gpx:
        return
    with commit_row_container:
        # Default: last-stage-date+1 if stages exist, else today
        if stages_data:
            default_date = (
                date.fromisoformat(stages_data[-1]["date"]) + timedelta(days=1)
            ).isoformat()
        else:
            default_date = date.today().isoformat()

        with ui.row().classes("items-center gap-2"):
            ui.label(f"{len(pending_gpx)} Datei(en) bereit")
            date_input = ui.date(value=default_date).props("dense")
            ui.button(
                f"{len(pending_gpx)} Etappen anlegen",
                on_click=make_commit_bulk_gpx_handler(date_input, pending_gpx),
                icon="check",
            ).props("color=primary size=sm")


# Widget-Definition
ui.upload(
    on_upload=make_buffer_gpx_handler(),
    auto_upload=True,
    max_files=-1,                           # ← NEU: Multi-Select
    label="Add Stage from GPX",
).props('accept=".gpx" flat dense').classes("w-44")
```

**Single-File-Verhalten (Backwards-Compat):**

Auch bei nur einer hochgeladenen Datei erscheint Datumspicker + Commit-Button.
Das ist eine bewusste Verhaltensänderung gegenüber der Pre-#127-Variante: das
Datum ist jetzt **immer** explizit. Default ist konsistent (`last_stage_date+1`
oder `today`), so dass der Single-File-Klick weiterhin nur 2 Klicks kostet
(Upload → Commit), und der User kann das Datum jederzeit korrigieren.

### 3. Per-Stage-Widgets bleiben unverändert

Die "Import Waypoints from GPX"-Widgets innerhalb einer existierenden Stage
(`trips.py:272`, `trips.py:551`) ersetzen Waypoints einer einzelnen Stage —
dort gibt es keine Reihenfolge-Frage und kein Datum, das sich ändern soll.
`max_files=1` bleibt.

### 4. Platzierung im Dialog

```
┌────────────────────────────────────────────────────────────────┐
│  New Trip / Edit Trip                                          │
│                                                                │
│  Stages                  [Add Stage] [Add Stage from GPX] ←┐   │
│                                                            │   │
│  [Bei pending Files:]                                      │   │
│  ┌──────────────────────────────────────────────────────┐  │   │
│  │  3 Datei(en) bereit  Startdatum: [2026-05-15] ▼     │  │   │
│  │                       [✓ 3 Etappen anlegen]          │  │   │
│  └──────────────────────────────────────────────────────┘  │   │
│                                                            ▼   │
│  T1: Tag 1 KHW_00a (...)                              🗑       │
│  T2: Tag 2 KHW_10  (...)                              🗑       │
│  T3: Tag 3 KHW_11  (...)                              🗑       │
└────────────────────────────────────────────────────────────────┘
```

## Affected Files

| File | Change Type | Description | LoC |
|------|-------------|-------------|-----|
| `src/core/natural_sort.py` | CREATE | `natural_sort_key()` Helper | ~25 |
| `src/web/pages/trips.py` | MODIFY | Multi-Upload + Datumspicker + Commit-Factory in beiden Dialogen | ~+80 |
| `tests/unit/test_natural_sort.py` | CREATE | Sortier-Reihenfolge + Edge-Cases | ~40 |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | MODIFY | Neue Klasse `TestMultiGpxNaturalSort` | ~+45 |

**Total:** ~190 LoC in 4 Dateien, davon 1 neue Datei (`natural_sort.py`).

## Expected Behavior

- **Input:** N GPX-Dateien (1 ≤ N) via Multi-Select-Upload, Startdatum aus
  Datums-Picker (default vorbelegt), Klick auf "X Etappen anlegen"-Button.
- **Output:** N (oder N − skipped) Stages werden im Dialog-State (`stages_data`)
  angehängt, in natural-sortierter Reihenfolge, mit lückenlos aufsteigenden
  Daten ab Startdatum.
- **Side effects:**
  - `pending_gpx`-Buffer wird geleert
  - `stages_ui.refresh()` rendert die Stage-Liste neu
  - `ui.notify` mit Anzahl angelegter / übersprungener Stages
  - **Keine** Persistenz (erst beim "Save"-Button des Dialogs, unverändert)
- **Fehlerfall:**
  - Korruptes GPX → `ui.notify(type="warning")` für diese Datei, restliche
    Files werden lückenlos durchnummeriert
  - Kein Startdatum gewählt (`date_input.value` leer) → `ui.notify(type="negative")`,
    nichts wird angelegt
  - Leerer Buffer → Commit-Button verschwindet automatisch (Container clear)

## Test Plan

### Unit-Tests (TDD RED)

**`tests/unit/test_natural_sort.py`** (neu):

- [ ] `test_natural_sort_khw_pattern`: `["KHW_11", "KHW_00a", "KHW_10"]`
  → `["KHW_00a", "KHW_10", "KHW_11"]`
- [ ] `test_natural_sort_pure_numeric`: `["10.gpx", "2.gpx", "1.gpx"]`
  → `["1.gpx", "2.gpx", "10.gpx"]`
- [ ] `test_natural_sort_case_insensitive`: `["khw_2", "KHW_1"]`
  → `["KHW_1", "khw_2"]`
- [ ] `test_natural_sort_empty_list`: `sorted([], key=natural_sort_key) == []`
- [ ] `test_natural_sort_single_element`: `sorted(["only.gpx"], …) == ["only.gpx"]`
- [ ] `test_natural_sort_identical_strings`: 3× `"a.gpx"` bleibt stabil

**`tests/unit/test_gpx_import_in_trip_dialog.py`** (Erweiterung):

Neue Klasse `TestMultiGpxNaturalSort` mit echten GPX-Bytes (Fixtures aus
existierenden KHW-/GR221-Beispieldateien — keine Mocks!):

- [ ] `test_multi_gpx_sort_order`: 3 GPX-Bytes mit Filenames in falscher
  Reihenfolge (`KHW_11.gpx`, `KHW_00a.gpx`, `KHW_10.gpx`) → nach
  natural-sort + Verarbeitung → `stages_data` enthält Stages in der
  Reihenfolge `KHW_00a → KHW_10 → KHW_11`
- [ ] `test_multi_gpx_date_propagation`: 3 GPX, Startdatum `2026-05-01`
  → Stages bekommen `2026-05-01`, `2026-05-02`, `2026-05-03`
- [ ] `test_single_file_fallback`: 1 GPX + Startdatum → 1 Stage mit
  korrektem Datum (Single-File-Pfad funktioniert weiter)
- [ ] `test_corrupt_file_skipped`: 3 Files, Datei #2 ist invalid bytes
  → 2 valide Stages in `stages_data`, Daten lückenlos `start, start+1`
  (nicht `start, start+2`)

### E2E-Tests (Playwright via `e2e_browser_test.py`)

- [ ] Browser-Test `MultiGpxImport`:
  ```bash
  uv run python3 .claude/hooks/e2e_browser_test.py browser \
      --check "MultiGpxImport" --action "compare"
  ```
  Schritte:
  1. New-Trip-Dialog öffnen
  2. `set_input_files(["KHW_11.gpx", "KHW_00a.gpx", "KHW_10.gpx"])` auf
     dem Multi-Upload-Widget
  3. Datums-Picker auf `2026-05-01` setzen
  4. "3 Etappen anlegen"-Button klicken
  5. Screenshot prüfen: Stage-Labels zeigen Reihenfolge
     `KHW_00a (2026-05-01)`, `KHW_10 (2026-05-02)`, `KHW_11 (2026-05-03)`

### Manuelle Validierung

- [ ] Safari Hard-Reload (Cmd+Shift+R) → Multi-Upload + Commit-Button
  reagieren (Factory-Pattern verifiziert)
- [ ] Edit-Trip-Dialog: gleicher Flow wie New-Trip-Dialog funktioniert
- [ ] Per-Stage-"Import Waypoints from GPX" weiterhin single-file
  (Regression-Check)
- [ ] Drag-and-Drop von 3 Dateien gleichzeitig auf das Upload-Widget
  → Buffer sammelt alle 3, ein Commit-Klick legt 3 Stages an
- [ ] Default-Datum-Logik: bei leerem Trip → `today`; bei vorhandenen Stages
  → letzte Stage + 1 Tag
- [ ] Notify-Texte sind verständlich (Anzahl angelegt, Anzahl übersprungen)

## Acceptance Criteria

- [ ] Multi-Select-Upload an beiden Dialog-Ebenen-Widgets möglich
  (`max_files=-1`)
- [ ] Per-Stage-Waypoint-Import-Widgets unverändert single-file
- [ ] Nach Datei-Auswahl erscheint Datumspicker + Commit-Button
  "X Etappen anlegen"
- [ ] Klick auf Commit: Files werden natural-sortiert
  (`KHW_00a < KHW_00b < KHW_01 < … < KHW_10 < KHW_11`)
- [ ] Stages werden in der sortierten Reihenfolge angelegt
- [ ] Erste Stage = gewähltes Startdatum, jede weitere = +1 Tag
- [ ] Default-Datum: `last_stage_date + 1` falls Stages vorhanden,
  sonst `date.today()`
- [ ] Single-File-Upload funktioniert weiterhin: Datumspicker erscheint,
  1 Stage wird mit korrektem Datum angelegt
- [ ] Korrupte GPX-Datei wird mit `ui.notify(type="warning")` übersprungen,
  restliche Dateien werden lückenlos verarbeitet (kein Datums-Loch)
- [ ] Safari-Test: nach Hard-Reload reagiert der Commit-Button korrekt
  (Factory Pattern via `make_commit_bulk_gpx_handler()` →
  `do_commit_bulk_gpx()`)
- [ ] `natural_sort_key()` als pure Funktion in `src/core/natural_sort.py`
  testbar ohne UI-Kontext
- [ ] Alle Unit-Tests grün (echte GPX-Bytes, keine Mocks)
- [ ] E2E-Browser-Test grün (Playwright + Hook-Output)

## Constraints (CLAUDE.md)

### Safari Factory Pattern (PFLICHT)

Der neue Commit-Button MUSS via Factory gebaut werden:

```python
def make_commit_bulk_gpx_handler(date_input, pending_ref):
    def do_commit_bulk_gpx():
        ...
    return do_commit_bulk_gpx

ui.button("X Etappen anlegen",
          on_click=make_commit_bulk_gpx_handler(date_input, pending_gpx))
```

Direkte Closure-Referenzen wie `on_click=lambda: handle_commit(...)` sind in
Safari unzuverlässig (siehe `docs/reference/nicegui_best_practices.md`).

### Daten-Schema-Reworks (nicht relevant)

Diese Spec ändert **kein** Persistenz-Schema:
- `Stage`-Dataclass bleibt unverändert
- `save_trip()` (`trips.py:627-642`, `loader.py:660`) bleibt
  Read-Modify-Write
- Hook `data_schema_backup.py` greift nicht (keine Schema-Datei wird editiert)

Trotzdem: nach Deploy verifizieren, dass bestehende Trips (z.B.
`gr221-mallorca.json`, `5f534011.json`) unverändert geladen werden können.

### Keine Mocked Tests (PFLICHT)

- Unit-Tests nutzen **echte** GPX-Bytes — Fixtures aus existierenden
  KHW-/GR221-Beispieldateien (`tests/fixtures/gpx/` oder analog).
  Keine `Mock()`, `patch()`, `MagicMock` für GPX-Parsing.
- E2E-Test nutzt Playwright `set_input_files()` mit echten Dateien.

## Known Limitations

1. **Sequenzielles Datum:** Stages bekommen lückenlos aufsteigende Daten ab
   Startdatum. Trips mit Pausentagen zwischen Etappen müssen die Daten
   anschließend manuell anpassen (über die Stage-Edit-Felder).

2. **Skip-Verhalten bei korrupten Dateien:** Eine korrupte Datei zwischen
   gültigen Files führt zu lückenlosen Daten der validen Stages — die
   übersprungene Datei „verschwindet" datumsmäßig. User bekommt eine
   `ui.notify`-Warnung, muss aber selbst entscheiden, ob die Datei
   nachträglich repariert hochgeladen werden soll.

3. **Refactoring-Duplikation:** New- und Edit-Trip-Dialog haben jeweils einen
   eigenen Multi-Upload-Block. Konsolidierung ist explizit Out-of-Scope dieser
   Spec — wenn das Pattern sich bewährt, ein eigenes Refactoring-Issue.

4. **Browser-FileList-Reihenfolge unbekannt:** NiceGUI feuert `on_upload`
   sequenziell pro Datei. Die Reihenfolge der `on_upload`-Calls hängt vom
   Browser ab, ist aber irrelevant — der Buffer wird vor dem Anlegen der
   Stages über `natural_sort_key` neu sortiert.

5. **Default-Datum bei „Pausentag-Trips":** Wird ein zweiter Multi-Upload
   ausgeführt nachdem schon Stages existieren, ist das Default-Startdatum
   `last_stage_date + 1`. Bei einem Trip mit Pausentag (z.B. nach Stage 3
   ein Tag Pause vor Stage 4) muss der User das Datum manuell auf
   `last_stage_date + 2` setzen.

## Risks

### R1 — Closure-State-Verlust bei Dialog-Re-Open

**Risiko:** Wird der Trip-Dialog geschlossen und wieder geöffnet, ist
`pending_gpx` ein neuer Buffer. Bereits hochgeladene aber nicht committete
Files sind verloren.

**Mitigation:** Akzeptierbar — der Commit-Button ist prominent sichtbar,
sobald Files gepuffert sind. UX-Test im E2E-Plan deckt das ab.

### R2 — Multi-File-Race in NiceGUI `on_upload`

**Risiko:** NiceGUI feuert `on_upload` für jede Datei einzeln. Bei
gleichzeitigem Async-Verarbeiten könnten Reads kollidieren.

**Mitigation:** Buffer ist eine simple Liste, `append` ist threadsafe in
CPython (GIL). Verarbeitung passiert erst beim Commit-Klick, sequenziell
in einer einzigen Funktion (`do_commit_bulk_gpx`).

### R3 — Safari-Closure-Binding bei Date-Picker-Referenz

**Risiko:** Der Datums-Picker wird in `_refresh_commit_row()` neu erzeugt;
die Factory `make_commit_bulk_gpx_handler(date_input, …)` muss die aktuelle
`date_input`-Referenz capturen.

**Mitigation:** Factory wird **innerhalb** der `with commit_row_container:`-
Erstellung aufgerufen, wo `date_input` lokal definiert ist — die Closure
bindet die korrekte aktuelle Referenz. Safari-E2E-Test im Plan.

### R4 — `gpx_to_stage_data` ändert Verhalten bei custom Datum

**Risiko:** Die Funktion existiert bereits und akzeptiert `stage_date` als
Argument (siehe `gpx_import_in_trip_dialog.md` v2.0 §1). Falls ein Bug in
der Datums-Behandlung existiert, würde Multi-Import ihn vervielfachen.

**Mitigation:** Unit-Test `test_multi_gpx_date_propagation` deckt explizit
ab, dass jede Stage das korrekte Datum bekommt.

## Changelog

- 2026-05-04: Initial spec — basiert auf Issue #127 Analysis
  (`docs/context/issue-127-gpx-multi-import.md`) und User-Entscheidungen
  zu Commit-Flow (expliziter Button), Default-Datum (`last+1` / `today`),
  Fehlerbehandlung (Skip mit Warning, lückenlose Daten) und Refactoring-Scope
  (separat patchen, keine Konsolidierung). Erweitert das Auto-Date-Increment-
  Pattern aus `gpx_import_in_trip_dialog.md` v2.0 auf Multi-File mit
  Natural-Sort.
