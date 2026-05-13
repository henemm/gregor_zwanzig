---
entity_id: issue_215_sprint3_list_routes
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [215]
parent_epic: 133
parent_umbrella: 212
related: [214]
tags: [frontend, sveltekit, design-system, epic-133, issue-215, button-consolidation, sprint-3]
---

# Issue #215 Sprint 3 — Listen-Routen: Button → Btn

## Approval

- [ ] Approved

## Purpose

Letzter Migrations-Sprint der Phase B (#215). Migriert die verbleibenden `<Button>`-Aufrufstellen in 7 Listen- und Übersichts-Routen. Nach diesem Sprint ist die `Button`-Komponente nur noch in den Wizard-Dateien aktiv, die via Issue #190 separat entsorgt werden — Phase C (#216) kann danach `button.svelte` final entfernen.

## Source

- **EDIT:** `frontend/src/routes/trips/+page.svelte` (13 Aufrufstellen)
- **EDIT:** `frontend/src/routes/subscriptions/+page.svelte` (8)
- **EDIT:** `frontend/src/routes/locations/+page.svelte` (7)
- **EDIT:** `frontend/src/routes/compare/+page.svelte` (4)
- **EDIT:** `frontend/src/routes/gpx-upload/+page.svelte` (2)
- **EDIT:** `frontend/src/routes/weather/+page.svelte` (1)
- **EDIT:** `frontend/src/routes/+page.svelte` (1, Startseite)
- **NEU:** `frontend/e2e/list-routes-btn-migration.spec.ts` — Migrations-Probe (File-System-Checks pro Datei)
- **Identifier:** keine neuen

**Audit-Korrektur:** Der ursprüngliche Audit nannte 51 Aufrufstellen, aktueller Stand zeigt **36** (Audit hatte vermutlich Open- und Close-Tags doppelt gezählt). Scope bleibt gleich, nur die Zahl ist realistischer.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | bestehend (#214) | Ziel — alle benötigten Variants und Sizes vorhanden |
| `frontend/src/lib/components/ui/button/button.svelte` | bestehend | Bleibt im Repo, wird in Phase C (#216) entfernt |
| `frontend/e2e/trips.spec.ts` | bestehend | Regressions-Sicherung für trips-Liste |
| `frontend/e2e/locations.spec.ts` | bestehend | Regressions-Sicherung für locations |
| `frontend/e2e/adhoc-to-abo.spec.ts` | bestehend | Regressions-Sicherung für subscriptions |

## Implementation Details

### §1 Variant-Inventur (aktueller Stand)

Gezählt über alle 7 Dateien:

| Variant | Aufrufe | Btn-Ziel |
|---|---|---|
| `default` (ohne `variant`) | 4 | `primary` (explizit setzen) |
| `outline` | 15 | `outline` |
| `ghost` | 10 | `ghost` |
| `destructive` | 3 | `destructive` |
| `secondary` | 3 | `secondary` |
| `link` | 0 | — |

Sizes: `sm` (5x), `icon-sm` (12x), Default-Size (19x). Alle in Btn vorhanden.

### §2 Migrations-Regeln (pro Datei)

1. **Import-Zeile austauschen:**
   ```typescript
   // ALT:
   import { Button } from '$lib/components/ui/button/index.js';
   // NEU:
   import { Btn } from '$lib/components/ui/btn/index.js';
   ```

2. **Tag-Rename:** `<Button` → `<Btn` und `</Button>` → `</Btn>` (alle Vorkommen).

3. **Variant-Mapping:** Wo `<Button>` ohne `variant`-Prop steht (= Button-`default`) → `<Btn variant="primary">` EXPLIZIT setzen. Begründung: Btn-Default ist zwar `primary`, aber zur Lesbarkeit und Konsistenz mit Sprint 1+2 explizit setzen.

4. **Sizes/Variants `outline`/`ghost`/`secondary`/`destructive`/`sm`/`icon-sm`:** unverändert übernehmen.

5. **Andere Props** (`class`, `onclick`, `disabled`, `href`, `data-testid`): unverändert.

### §3 Migrations-Test `frontend/e2e/list-routes-btn-migration.spec.ts`

7 File-System-Tests (eines pro Datei), die prüfen:
- `import { Btn }` aus `$lib/components/ui/btn/index.js` vorhanden
- `import { Button }` aus `$lib/components/ui/button/...` NICHT vorhanden
- Keine `<Button`-Tags mehr im Source

```typescript
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const FILES = [
  'frontend/src/routes/trips/+page.svelte',
  'frontend/src/routes/subscriptions/+page.svelte',
  'frontend/src/routes/locations/+page.svelte',
  'frontend/src/routes/compare/+page.svelte',
  'frontend/src/routes/gpx-upload/+page.svelte',
  'frontend/src/routes/weather/+page.svelte',
  'frontend/src/routes/+page.svelte',
];

test.describe('Issue #215 Sprint 3 — List-Routes Button→Btn', () => {
  for (const file of FILES) {
    test(`Migration (${file.split('/').slice(-2).join('/')})`, async () => {
      const content = await readFile(`/home/hem/gregor_zwanzig/${file}`, 'utf-8');
      expect(content).toContain(`import { Btn } from '$lib/components/ui/btn/index.js'`);
      expect(content).not.toContain(`import { Button } from '$lib/components/ui/button`);
      expect(content).not.toMatch(/<Button[\s>]/);
      expect(content).not.toMatch(/<\/Button>/);
    });
  }
});
```

### §4 Datei-Liste

| Art | Datei | LoC |
|---|---|---|
| EDIT | trips/+page.svelte | ±0 (~28 Zeilen geändert) |
| EDIT | subscriptions/+page.svelte | ±0 (~18) |
| EDIT | locations/+page.svelte | ±0 (~16) |
| EDIT | compare/+page.svelte | ±0 (~10) |
| EDIT | gpx-upload/+page.svelte | ±0 (~6) |
| EDIT | weather/+page.svelte | ±0 (~4) |
| EDIT | +page.svelte (root) | ±0 (~4) |
| NEU | list-routes-btn-migration.spec.ts | ~50 |
| **Summe** | | **~50 LoC** |

Default-LoC-Limit 250, kein Override.

## Expected Behavior

- **Input:** Keine API-Veränderung.
- **Output:** Buttons in den 7 Routen rendern als `<button data-slot="btn">` statt `<button data-slot="button">`. Variant `default` → `primary` (sichtbar dunkler Look).
- **Side effects:** Visuelle Mikro-Unterschiede in Listen-Routen (Btn-Token vs. shadcn-Token); funktional identisch.

## Acceptance Criteria

- **AC-1:** Given alle 7 Listen-Routen-Dateien / When inspiziert / Then enthält jede einen `import { Btn } from '$lib/components/ui/btn/index.js'` UND keinen `import { Button } from '$lib/components/ui/button/...'` UND keinen `<Button>`-Tag mehr.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `/trips`-Route / When im Browser geöffnet / Then sind alle Action-Buttons (Edit, Delete, Filter etc.) mit `data-slot="btn"` versehen.
  - Test: (populated after /tdd-red)

- **AC-3:** Given `/locations`-Route / When im Browser geöffnet / Then sind alle Action-Buttons mit `data-slot="btn"` versehen.
  - Test: (populated after /tdd-red)

- **AC-4:** Given alle bestehenden Regressions-Tests (`trips.spec.ts`, `locations.spec.ts`, `adhoc-to-abo.spec.ts`) / When ausgeführt / Then sind alle grün (keine Funktions-Regression durch die Migration).
  - Test: (populated after /tdd-red)

- **AC-5:** Given Sprint 1 + Sprint 2 Migrations-Tests (`trip-header-btn-migration.spec.ts`, `forms-dialogs-btn-migration.spec.ts`) / When ausgeführt / Then weiterhin grün (Cross-Sprint-Regressions-Guard).
  - Test: (populated after /tdd-red)

- **AC-6:** Given alle Trip-Detail-Tests (`trip-detail-actions/left/right.spec.ts`) / When ausgeführt / Then weiterhin grün (Cross-Bereich-Regressions-Guard, falls Listen-Routen indirekt darauf wirken).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Wizard-Dateien (`lib/components/wizard/`)** bleiben weiter mit Button — werden via Issue #190 entsorgt.
- **Phase C (#216)** kann nach diesem Sprint die `button.svelte`-Komponente und das `ui/button/`-Verzeichnis entfernen — siehe Issue #216 für Voraussetzungen.
- **Audit-Zahl 51 war eine Überzählung** — realer Stand 36 Aufrufstellen. Resultat-Migration ist deshalb kleiner als ursprünglich gerechnet.
- **Keine visuellen Snapshot-Tests** — Sichtprüfung post-deploy.
- **Routen ohne dedizierte E2E-Tests** (compare, gpx-upload, weather, root): nur durch Migrations-Probe abgedeckt. Build-Pass + Smoke-Check post-deploy reicht für visuelle Validierung.

## Changelog

- 2026-05-13: Initial spec — Sprint 3 von Phase B (#215). 36 Aufrufstellen in 7 Listen-Routen auf Btn migriert. Variant-Mapping wie Sprint 1+2 (`default`→`primary`, andere bleiben). Letzter Migrations-Sprint vor Phase C (#216, Button entfernen).
