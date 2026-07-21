---
entity_id: epic_129a_3_ui_removed_tests
type: tests
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [tests, refactor, epic-129, nicegui-removal, deletion-only]
parent: epic_129a_3_ui_removal
phase: phase5_tdd_red
---

# Epic #129 Phase A.3 — NiceGUI ersatzlos loeschen (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die ersatzlose Loeschung von `src/web/` (11 NiceGUI-
Dateien), 7 obsoleter Test-Files, der Dependencies `nicegui` + `apscheduler`
in `pyproject.toml`, und der String-Eval-Referenzen in
`.claude/validate.py` + `.claude/commands/e2e-verify.md`.

Jeder Eintrag mappt einen pytest-Funktionsnamen auf das in der Parent-Spec
definierte Acceptance-Criterion.

Parent-Modul-Spec: `docs/specs/epic_129a_3_ui_removal.md`.

## Source

- **Files:**
  - `tests/refactor/test_epic_129a_3_ui_removed.py` (NEU — Loesch-/Hook-Strukturpruefung)
- **Spec:** `docs/specs/epic_129a_3_ui_removal.md` v1.0

## Test Inventory

Die Test-Funktionsnamen verwenden Bezeichner aus der Parent-Spec, damit der
Spec-Enforcement-Hook sie aufloesen kann. Die Mapping-Tabelle dokumentiert,
welcher Test welches Acceptance-Criterion abdeckt.

### Refactor-Strukturpruefung (`tests/refactor/test_epic_129a_3_ui_removed.py`)

| Test-Funktion | AC | Was geprueft wird |
|---------------|----|------------------|
| `test_ac1_src_web_directory_empty` | AC-1 | `src/web/` enthaelt keine `.py`-Dateien mehr (Verzeichnis darf weg sein oder leer existieren). |
| `test_ac2_no_imports_from_web` | AC-2 | grep ueber `src/`, `api/`, `tests/`, `.claude/` auf `from web.`, `import web.`, `from src.web`, `import src.web` — 0 Treffer (Self-Reference dieser Datei wird gefiltert). |
| `test_ac3_seven_test_files_deleted` | AC-3 | Alle 7 in der Spec aufgelisteten Test-Dateien existieren nicht mehr. |
| `test_ac4_pyproject_no_nicegui_apscheduler` | AC-4 | `pyproject.toml` enthaelt die Substrings `nicegui` und `apscheduler` nirgends mehr (Dependencies + Ruff-Exceptions). |
| `test_ac5_no_web_main_in_hooks` | AC-5 | `.claude/validate.py` und `.claude/commands/e2e-verify.md` enthalten keine `from web.main` / `from web.scheduler` / `-m src.web.main` / `-m web.main` Strings mehr. |
| `test_ac7_collection_clean` | AC-7 | `uv run pytest tests/ --collect-only -q --no-header` laeuft ohne `errors during collection` (keine Imports auf geloeschte Module crashen). |

### Nicht im pytest-Manifest

| AC | Begruendung |
|----|------------|
| AC-6 (`systemctl is-active gregor_zwanzig.service` -> `inactive`) | Live-Smoke-Skript-Test gegen Production nach Deploy — siehe Spec Verification-Sektion, Manuelle SSH-Pruefung, kein pytest. |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begruendung |
|------|----------------------------|-------------|
| `test_ac1_src_web_directory_empty` | FAIL | `src/web/` mit 11 .py-Files steht heute noch. |
| `test_ac2_no_imports_from_web` | FAIL | 4–5 externe Importeure (api/routers, services, weitere) zeigen heute auf `web.*` (haengt von Phase A.1+A.2-Stand ab). |
| `test_ac3_seven_test_files_deleted` | FAIL | Alle 7 Test-Dateien existieren noch. |
| `test_ac4_pyproject_no_nicegui_apscheduler` | FAIL | `nicegui>=2.0.0` und `apscheduler>=…` stehen heute in `pyproject.toml`. |
| `test_ac5_no_web_main_in_hooks` | FAIL | `.claude/validate.py` Zeile 82 hat heute `from web.main import *`, und `.claude/commands/e2e-verify.md` hat noch `python -m src.web.main`-Aufrufe. |
| `test_ac7_collection_clean` | wahrscheinlich PASS | Collection ist heute sauber, weil noch alle Files da sind. Erst nach der Loesch-Aktion in Phase 6 zeigt dieser Test, dass kein Test-File auf ein verschwundenes Modul importiert. |

Mindestens AC-1, AC-2, AC-3, AC-4 und AC-5 muessen FAIL liefern — das ist der
RED-Beweis. AC-7 ist als Regression-Sicherung gedacht (in Phase 6 muss er
gruen bleiben, sonst hat die Loesch-Aktion etwas uebersehen).

## Verification

- **Scoped Run:** `uv run pytest tests/refactor/test_epic_129a_3_ui_removed.py -v`
- **Phase 5 RED:** AC-1, AC-2, AC-3, AC-4, AC-5 rot. AC-7 darf bereits gruen sein.
- **Phase 6 GREEN:** Alle 6 Tests gruen — keine Mocks, keine Stubs, reale FS-Checks und reale grep-Outputs.
- **Live (nach Prod-Deploy):** Manuelle SSH-Pruefung von AC-6 — `sudo systemctl is-active gregor_zwanzig.service` -> `inactive`.

## Out of Scope

- Funktionale Pruefung der Go-API (gregor-api, Port 8090) und SvelteKit-UI (gregor-frontend, Port 4321) — diese laufen unabhaengig und werden durch das bestehende Smoke-Suite + `check-gregor20.sh` (BetterStack) gedeckt.
- Loeschung der `gregor_zwanzig.service`-Unit-Datei aus `henemm-infra/` — Sister-Repo, separate PR.

## Changelog

- 2026-05-12: Initial test manifest for epic-129a-3 ui-removal phase.
