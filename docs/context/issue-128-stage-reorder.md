# Context: issue-128-stage-reorder

**Issue:** [#128](https://github.com/henemm/gregor_zwanzig/issues/128)
**Phase:** Analysis (2026-05-05)

## Problem

Im Trip-Edit-Dialog gibt es keine Möglichkeit, die Reihenfolge der Etappen zu ändern. Wer nach einem GPX-Multi-Import die Reihenfolge korrigieren oder eine manuell angelegte Etappe nach vorne ziehen möchte, muss alles löschen und neu anlegen.

## Ist-Zustand

Etappen werden in der Komponente `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` editiert. Diese Komponente wird **doppelt** genutzt:

- **Wizard-Modus** (`/trips/new`) — Schritt 2 von 4
- **Edit-Modus** (`/trips/[id]/edit`) — über `TripEditView.svelte`

Aktuelle Funktionen pro Etappe:
- `addStage()` — fügt eine Etappe **am Ende** hinzu
- `removeStage(idx)` — entfernt eine Etappe (Trash-Icon, nur sichtbar wenn `stages.length > 1`)
- `addWaypoint(stageIdx)` / `removeWaypoint(stageIdx, wpIdx)` — Wegpunkt-Pflege

**Keine** Move-Up/Down-Funktion.

## Persistierung

`TripEditView.svelte:51` speichert via `api.put('/api/trips/{id}', { ...trip, stages })` — der Backend-Handler `UpdateTripHandler` (Go, `internal/handler/trip.go:126`) ist Read-Modify-Write und erhält alle Felder, die der Client nicht ändert. Das Reihenfolge-Array `stages` wird 1:1 als JSON gespeichert. **Keine** Backend-Änderung nötig. Das Datenverlust-Risiko aus Memory `data_schema_reworks` greift hier nicht — wir ändern keine Felder, sondern tauschen nur Array-Positionen.

## Strategie

- **UI-Komponente:** zwei Pfeil-Buttons (hoch / runter) pro Etappen-Card im Header-Bereich (neben Trash-Button)
- **Disabled-State:** hoch-Button für `idx === 0`, runter-Button für `idx === stages.length - 1`
- **Logik:** Array-Element-Swap (zwei-Ziel-Destrukturierung)
- **Wirkt in beiden Modi** (Wizard + Edit) — bewusst, da Komponente shared ist; ist konsistent zur Trash-Funktion, die ebenfalls in beiden Modi sichtbar ist

## Scope

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | +~30 LoC (2 Funktionen + 2 Buttons + Icon-Imports) |
| `tests/tdd/test_stage_reorder.py` | neu — Playwright-E2E gegen deployed Frontend |
| `docs/specs/feature/stage_reorder.md` | neu (Spec) |
| `docs/specs/tests/stage_reorder_tests.md` | neu (Test-Spec) |

**1 Code-Datei, ~30 LoC** — unter Limit.

## Risiken

- **Stale-Closure-Risiko in Svelte 5:** Move-Funktionen müssen die `$bindable`-Reaktivität sauber triggern. Mit Array-Mutation (`splice`) und Re-Assignment (`stages = [...stages]`) sicherstellen.
- **Test-Komplexität:** UI-Reorder lässt sich am besten mit Playwright testen (Klicken + DOM-Reihenfolge prüfen). HTTP-only Tests reichen nicht.
- **Doppelte Wirkung Wizard/Edit:** Bewusst — Komponente ist geteilt; alternativ wäre ein Prop `allowReorder: boolean`, aber das verkompliziert die Spec ohne erkennbaren Vorteil.

## Test-Ansatz

Playwright-E2E gegen lokalen Build (oder Staging nach Deploy):
1. Login + Edit eines existierenden Trips mit ≥ 3 Etappen
2. Initiale Reihenfolge erfassen (Stage-Namen aus DOM)
3. Klick auf „runter" bei Etappe 0 → Reihenfolge: 1 ↔ 0
4. Klick auf „hoch" bei letzter Etappe → Reihenfolge: vorletzte ↔ letzte
5. Disabled-State prüfen: erste Etappe „hoch" disabled, letzte „runter" disabled
6. Speichern → Reload → Reihenfolge persistent
