---
entity_id: issue_343_horizon_chip_ui_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, frontend, weather, svelte, horizon-chip, issue-343]
parent: issue_343_horizon_chip_ui
phase: phase5_tdd_red
---

# Issue #343 — HorizonChip-UI im Wetter-Editor (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die HorizonChip-UI-Erweiterung aus
`docs/specs/modules/issue_343_horizon_chip_ui.md`. Jeder Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_343_horizon_chip_ui.md` v1.0

## Source

- **File:** `frontend/src/lib/components/ui/horizon-chip/HorizonChip.test.ts` (NEU)
  — Source-Inspection-Tests fuer die `HorizonChip.svelte`-Komponente.
- **File:** `frontend/src/lib/utils/horizonHelpers.test.ts` (NEU)
  — Pure-Function-Tests fuer `computeHorizonSummary()`.
- **File:** `frontend/e2e/issue-343-horizon-chips.spec.ts` (NEU)
  — Playwright-E2E gegen das echte Frontend + Backend.

## Test-Runner-Hinweis

Das Frontend nutzt `node --experimental-strip-types --test`. Dieser Runner kann
**keine** `.svelte`-Imports laden (siehe `Btn.test.ts`, das deshalb skipped
ist). Component-Tests folgen daher dem Source-Inspection-Pattern aus
`WeatherMetricsPreviewCard.tokens.test.ts`: die `.svelte`-Datei wird per
`readFileSync` als String geladen und auf Marker (data-Attribute, Labels,
Prop-Signaturen) assertiert. Echte Render-Tests laufen ueber die
Playwright-E2E-Suite.

## Test Inventory

### Vitest-/Node-Component-Tests (`HorizonChip.test.ts`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `rendert "HEUTE" fuer day=today` | Component-Spec §1 LABELS | Source enthaelt `today: 'HEUTE'` und das Wort `HEUTE` |
| `rendert "MORGEN" fuer day=tomorrow` | Component-Spec §1 LABELS | Source enthaelt `tomorrow: 'MORGEN'` |
| `rendert "UEBERMORGEN" fuer day=day_after` | Component-Spec §1 LABELS | Source enthaelt `day_after: 'ÜBERMORGEN'` |
| `setzt data-active und data-slot Attribute` | AC-1 + Component-Spec §1 | `data-slot="horizon-chip"`, `data-active={active}`, `aria-pressed={active}`, `data-day={day}` |
| `akzeptiert onclick-Callback und ruft ihn am Button auf` | AC-1 | `onclick: () => void` in Props + `<button {onclick}>` |

### Helper-Tests (`horizonHelpers.test.ts`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `5 Metriken mit allen drei Horizonten → "5 alle drei Tage"` | AC-7 / Wording-Heuristik | Bucket „alle drei Tage" Wording korrekt |
| `2 Metriken nur heute + morgen → "2 nur heute + morgen"` | AC-7 / Wording-Heuristik | Bucket „nur heute + morgen" Wording korrekt |
| `1 Metrik nur heute → "1 nur heute"` | AC-7 / Wording-Heuristik | Bucket „nur heute" Wording korrekt |
| `gemischtes Beispiel aus Mockup` | AC-7 | Trenner ` · ` + Bucket-Reihenfolge alle → heute+morgen → nur heute |
| `exotische Kombination → "sonstige Kombinationen"` | AC-7 / Heuristik-Fallback | Pattern (f,f,t) faellt in den Sonstige-Bucket |
| `disabled Metriken werden nicht gezaehlt` | AC-7 (Vorbedingung) | enabled=false Metriken werden ignoriert |

### Playwright-E2E (`issue-343-horizon-chips.spec.ts`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `AC-1: Klick auf HorizonChip togglet data-active und zeigt dirty-Pill` | AC-1 | Click togglet `data-active` von `"true"` → `"false"`, `weather-metrics-dirty-pill` erscheint |
| `AC-2: HorizonChip togglebar AUCH wenn Metrik-Checkbox aus` | AC-2 | Checkbox uncheck → Chip-Click togglet trotzdem |
| `AC-3: Save + Reload persistiert Chip-State` | AC-3 | Save → Reload → Chip-Zustand identisch, dirty-Pill weg |
| `AC-5: TablePreview rendert drei Tabellen heute/morgen/uebermorgen` | AC-5 | `data-testid="table-preview-day-{today\|tomorrow\|day_after}"` jeweils mit `<table>` |
| `AC-6: Mobile-Viewport bricht HorizonChips in Zeile 2 unter Metrik-Namen` | AC-6 | `page.setViewportSize({width:393,height:852})`; Bounding-Box: Chip-y > Label-y+height (Zeile 2), Chip-x ≥ Label-x (eingerueckt), Chip-height ≥ 44 (Touch-Target) |
| `AC-7: SavePresetDialog zeigt ZEITHORIZONTE-Block mit Wording-Zusammenfassung` | AC-4 + AC-7 | Dialog enthaelt Text `ZEITHORIZONTE` und `save-preset-horizon-summary` mit Wording-Pattern |

> **Test-ID-Konvention (Bestaetigung des User-Briefings):**
> `horizon-chip-{metric_id}-{day}`, `table-preview-day-{today|tomorrow|day_after}`,
> `save-preset-horizon-summary`. Diese Test-IDs werden in der GREEN-Phase
> in der Implementation ergaenzt.

## Expected Behavior

- **Input:** Component-Source als String (RED: `ENOENT`); Test-Trip mit drei
  Etappen heute/morgen/uebermorgen (E2E).
- **Output:** Assertions ueber Source-Marker, Helper-Rueckgabewerte und
  DOM-Attribute des laufenden Frontends.
- **Side effects:** E2E erzeugt + loescht einen Test-Trip via `/api/trips`;
  Save-Test persistiert HorizonsMap in `data/users/admin/trips/{id}.json`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Dateien existieren und Implementierung fehlt /
  When `node --test src/lib/components/ui/horizon-chip/HorizonChip.test.ts
  src/lib/utils/horizonHelpers.test.ts` laeuft /
  Then schlagen alle 11 Vitest-/Node-Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given die E2E-Spec existiert und Implementierung fehlt /
  When `npx playwright test e2e/issue-343-horizon-chips.spec.ts` laeuft /
  Then schlagen alle 6 E2E-Tests fehl (Selektoren nicht im DOM).

- **AC-T3:** Given GREEN-Phase abgeschlossen /
  When dieselben Test-Suiten ausgefuehrt werden /
  Then alle 17 Tests gruen, keine Mocks.

## Known Limitations

- **Keine Render-Tests fuer HorizonChip.svelte:** Da der Test-Runner keine
  `.svelte`-Imports kann, sind die Component-Tests Source-Inspection. Tatsaechliches
  Render-Verhalten (data-active toggle, aria-pressed, click) wird in den
  Playwright-E2E-Tests verifiziert.
- **AC-4 (POST `/api/metric-presets` mit horizons)** ist im AC-7-Dialog-Test
  via UI mitvalidiert; expliziter Submit-Roundtrip folgt in GREEN-Phase als
  Erweiterung. AC-6 (Mobile-Chip-Umbruch) ist seit 2026-05-23 als eigener
  E2E-Test `AC-6: Mobile-Viewport ...` in `issue-343-horizon-chips.spec.ts`
  abgedeckt — verwendet `page.setViewportSize({width:393,height:852})` und
  vergleicht Bounding-Boxes via Playwright `boundingBox()`.
- **Voraussetzung E2E-Run:** Playwright braucht ein laufendes Preview-Frontend
  (`bash e2e/start-preview.sh` triggert vite preview auf :4173). Wenn nur
  staging laeuft, schlagen alle E2E-Tests deterministisch im Setup fehl —
  RED-Status ist dann trotzdem dokumentiert.

## Changelog

- 2026-05-23: Initial Tests-Spec fuer Issue #343, 16 Tests insgesamt
  (5 Component-Source + 6 Helper + 5 E2E), mapped auf AC-1/2/3/5/7 + Component-Spec.
- 2026-05-23: AC-6 (Mobile-Chip-Umbruch) als 6. E2E-Test ergaenzt
  (`AC-6: Mobile-Viewport bricht HorizonChips in Zeile 2 unter Metrik-Namen`);
  Gesamttest-Anzahl 17 (5 + 6 + 6), AC-T2 auf 6 E2E-Tests aktualisiert,
  Known-Limitations-Eintrag zu AC-6 entfernt.
