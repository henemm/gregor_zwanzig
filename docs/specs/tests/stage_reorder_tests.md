---
entity_id: stage_reorder_tests
type: tests
created: 2026-05-05
updated: 2026-05-05
status: superseded
superseded_by: docs/adr/0024-ein-sortier-baustein-svelte-dnd-action.md
version: "1.0"
tags: [tests, frontend, etappen, playwright, e2e, issue-128]
---

# Tests: Etappen-Reihenfolge per Pfeil-Buttons (Issue #128)

## Approval

- [x] Approved

## Purpose

Playwright-E2E-Tests für die Pfeil-Buttons (hoch / runter) auf jeder Etappe
im Trip-Edit-Dialog. Verifiziert, dass die UI-Reihenfolge nach Klick stimmt,
das Speichern persistent ist, alle Wegpunkte erhalten bleiben und die
Disabled-States an den Rändern korrekt sind.

## Source

- **File:** `tests/tdd/test_stage_reorder.py`
- **Identifier:** Funktionen mit Prefix `test_*`

## Bezug

- Feature-Spec: `docs/specs/feature/stage_reorder.md`
- GitHub Issue #128

## Test-Strategie

- **Real HTTP + Real Browser, no mocks** — siehe CLAUDE.md "KEINE MOCKED TESTS".
- **Setup via API:** Tests legen pro Lauf einen frischen Test-Trip an
  (`POST /api/trips`) und löschen ihn im `finally` (`DELETE /api/trips/{id}`).
  So werden Bestands-Trips nicht angefasst.
- **UI-Interaktion via Playwright:** Headless Chromium öffnet `/trips/{id}/edit`
  mit Auth-Cookie, klickt die neuen Pfeil-Buttons, prüft DOM-Reihenfolge.
- **Persistenz-Check:** Nach Speichern wird der Trip per API erneut geladen
  und die `stages`-Reihenfolge gegen die erwartete Folge geprüft.
- **Default-Target Staging**, via `GZ_TEST_BASE_URL` überschreibbar.
- **Credentials** via `GZ_TEST_USER` / `GZ_TEST_PASS` Env-Vars.

## Covered Test Functions

- `stage_reorder_move_down_persists`
- `stage_reorder_disabled_at_edges`

### `stage_reorder_move_down_persists`

- **Given:** Test-Trip mit 3 Etappen [Alpha, Bravo, Charlie] geladen, jede mit einem Wegpunkt
- **When:** User klickt „runter" auf Etappe 0 (Alpha), dann Speichern
- **Then:** Direkt nach Klick ist DOM-Reihenfolge [Bravo, Alpha, Charlie]; nach Reload via API ist Reihenfolge persistent; Wegpunkt-IDs aller Etappen unverändert
- **TDD-Phase:** RED vor Fix (Buttons existieren nicht, `data-testid="stage-move-down-0"` nicht gefunden), GREEN nach Implementierung in `WizardStep2Stages.svelte`.

### `stage_reorder_disabled_at_edges`

- **Given:** Test-Trip mit 3 Etappen geladen
- **When:** Edit-Dialog ist gerendert
- **Then:**
  - `[data-testid="stage-move-up-0"]` ist `disabled`
  - `[data-testid="stage-move-down-2"]` ist `disabled`
- **TDD-Phase:** RED vor Fix (Selektor nicht gefunden → Test failed), GREEN nach Implementierung.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `httpx` | Library | Trip-Setup/-Cleanup, Persistenz-Check |
| `playwright` (async API) | Library | Headless-Browser-Steuerung |
| `pytest-asyncio` | Library | async-Tests |
| `GZ_TEST_BASE_URL` | Env-Var | Default `https://staging.gregor20.henemm.com` |
| `GZ_TEST_USER` / `GZ_TEST_PASS` | Env-Vars | Login-Credentials |

## Expected Behavior

### Vor dem Fix (RED)
- `stage_reorder_move_down_persists` schlägt fehl: Selektor
  `[data-testid="stage-move-down-0"]` existiert nicht → Click-Timeout.
- `stage_reorder_disabled_at_edges` schlägt fehl: gleiche Ursache.

### Nach dem Fix (GREEN)
- Beide Tests grün.

## Known Limitations

- **Lokal kein Backend:** Tests benötigen ein laufendes Go-Backend (für
  `/api/trips`-Endpoints) — laufen daher praktisch nur gegen Staging/Prod oder
  ein voll gestartetes lokales System.
- **Playwright-Browser-Install:** Erstmals `uvx playwright install chromium`
  nötig (im Projekt vermutlich schon vorhanden).
- **Test-Trip pro Lauf:** Bei abgebrochenem Test bleibt evtl. ein
  „stage-reorder-test"-Trip übrig — manueller Cleanup oder wiederholter
  Lauf entfernt ihn.

## Changelog

- 2026-05-05: Initial spec für E2E-Tests rund um Issue #128.
