---
entity_id: issue_217_test_drifts
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, test, e2e, drift-fix]
issue: 217
---

<!-- Issue #217 — Test-Drifts locations.spec.ts + trips.spec.ts vorbestehend kaputt -->

# Issue #217 — Test-Drifts `locations.spec.ts` + `trips.spec.ts`

## Approval

- [ ] Approved

## Zweck

Zwei pre-existing E2E-Test-Drifts beheben (aus Sprint-3-Button-Migration
#215 aufgefallen):

1. **`locations.spec.ts`** sucht Button `'Neue Location'`; aktueller Code
   rendert `'Neuer Ort'` (Terminologie-Update, Test nicht nachgezogen).
2. **`trips.spec.ts`** verwendet alte Wizard-Selectoren (`trip-wizard`,
   `wizard-next`, `wizard-save`, `trip-name-input`), die der neue Wizard
   (Epic #136) nicht mehr hat. Die zwei Tests sind redundant zu
   `trip-wizard-step1/2/3/4.spec.ts` und `trip-wizard-shell.spec.ts`.

**Tech-Lead-Entscheidung:**
- `locations.spec.ts`: Text-Strings auf `'Neuer Ort'` updaten (4 Stellen).
- `trips.spec.ts`: 2 redundante Wizard-Tests entfernen, Block-Kommentar mit
  Verweis auf dedizierte Wizard-Specs + Issue #190 hinterlassen. Option (a)
  aus dem Issue.

## Quelle / Source

- `frontend/e2e/locations.spec.ts` (Zeilen 21, 27, 37, 122) — Button-Text-Update
- `frontend/e2e/trips.spec.ts` (Zeilen 25-74) — 2 Wizard-Tests entfernen + Kommentar

## Acceptance Criteria

- **AC-1:** Given `frontend/e2e/locations.spec.ts` / When Playwright die 6 Tests in der Suite ausführt / Then sind alle 6 grün; die 4 vorigen Failures durch `getByRole('button', { name: 'Neue Location' })` sind durch `'Neuer Ort'` ersetzt

- **AC-2:** Given `frontend/e2e/trips.spec.ts` / When Playwright die Suite ausführt / Then existieren die zwei Tests `'create trip navigates to wizard'` und `'create trip via wizard'` nicht mehr; an ihrer Stelle steht ein Kommentar-Block, der auf die kanonischen Wizard-Tests (`trip-wizard-*.spec.ts`) und Issue #190 verweist

- **AC-3:** Given die übrigen Tests in `trips.spec.ts` (z.B. `delete trip with confirmation`) / When sie laufen / Then bleiben sie unverändert grün/rot — keine Regression durch die Entfernungen

- **AC-4:** Given svelte-check / When der Build läuft / Then ist die Error-Anzahl ≤ aktuelle Baseline (24) — Test-Datei-Edits dürfen keine Type-Errors einführen

## Erwartetes Verhalten

### `locations.spec.ts` (4 Stellen)

Vorher:
```typescript
const createBtn = page.getByRole('button', { name: 'Neue Location' });
// ...
await page.getByRole('button', { name: 'Neue Location' }).click();
```

Nachher:
```typescript
const createBtn = page.getByRole('button', { name: 'Neuer Ort' });
// ...
await page.getByRole('button', { name: 'Neuer Ort' }).click();
```

### `trips.spec.ts` (Zeilen 25-74 entfernt + Kommentar)

Vorher:
```typescript
test('create trip navigates to wizard', async ({ page }) => {
    // ...alte Selectoren, kaputt...
});

test('create trip via wizard', async ({ page }) => {
    // ...alte Selectoren, kaputt...
});

// 'edit trip navigates to wizard with pre-filled name' moved to trip-edit.spec.ts (Issue #91 ...).

test('delete trip with confirmation', async ({ page }) => {
    // ...
});
```

Nachher:
```typescript
// 'create trip navigates to wizard' + 'create trip via wizard' entfernt (#217):
// Tests verwendeten alte Wizard-Selectoren (trip-wizard, wizard-next, wizard-save)
// die seit Epic #136 nicht mehr existieren. Coverage durch dedizierte
// trip-wizard-step1/2/3/4.spec.ts + trip-wizard-shell.spec.ts.
// Vollstaendige Entfernung des alten Wizards: Issue #190.

// 'edit trip navigates to wizard with pre-filled name' moved to trip-edit.spec.ts (Issue #91 ...).

test('delete trip with confirmation', async ({ page }) => {
    // ...
});
```

## Out-of-Scope

- **Alten Wizard-Code entfernen** — Issue #190.
- **Dialog-Title `'Neue Location'` in LocationForm umbenennen** — UI-Konvention
  ist OK (Button-Action ist neuer Begriff, Header-Title bleibt). Wenn jemand
  das vereinheitlichen will: eigener Issue.

## Tests / Verifikation

- **Playwright (Smoke):**
  ```bash
  cd frontend && npx playwright test e2e/locations.spec.ts e2e/trips.spec.ts --project=chromium
  ```
  Erwartung: `locations.spec.ts` alle Tests grün (oder pre-existing rot, nicht durch unseren Fix). `trips.spec.ts` ohne die 2 entfernten Failures.
- **svelte-check:** Baseline 24 Errors.

## Risiken & Migration

- **Risiko vernachlässigbar:** Reine Test-Datei-Änderungen.
- **Test-Coverage:** Wizard-Coverage bleibt erhalten via 8 dedizierte
  Test-Dateien.
- **Backwards-Compat:** Keine — Test-Code-Änderungen haben keinen
  Production-Impact.
