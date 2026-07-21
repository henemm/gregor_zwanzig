---
entity_id: issue_215_sprint2_forms_dialogs
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
tags: [frontend, sveltekit, design-system, epic-133, issue-215, button-consolidation, sprint-2]
---

# Issue #215 Sprint 2 — Forms + Dialoge: Button → Btn

## Approval

- [ ] Approved

## Purpose

Zweiter Migrations-Sprint der Phase B von #212. Migriert die 14 `<Button>`-Aufrufstellen in vier Admin-Formularen und zwei generischen Dialog-Bausteinen. Besonderheit: `dialog-content.svelte` und `dialog-footer.svelte` aus `ui/dialog/` sind zentrale UI-Bausteine — die Migration wirkt sich indirekt auf jeden Dialog im Frontend aus.

## Source

- **EDIT:** `frontend/src/lib/components/SubscriptionForm.svelte` (2 Aufrufstellen)
- **EDIT:** `frontend/src/lib/components/LocationForm.svelte` (2)
- **EDIT:** `frontend/src/lib/components/TripForm.svelte` (6)
- **EDIT:** `frontend/src/lib/components/WeatherConfigDialog.svelte` (2)
- **EDIT:** `frontend/src/lib/components/ui/dialog/dialog-content.svelte` (1, generischer Close-Button im Dialog-Overlay)
- **EDIT:** `frontend/src/lib/components/ui/dialog/dialog-footer.svelte` (1, optionaler Close-Button im Footer)
- **NEU:** `frontend/e2e/forms-dialogs-btn-migration.spec.ts` (~70 LoC) — Migrations-Probe: prüft `data-slot="btn"` an exemplarischen Aufrufstellen
- **Identifier:** keine neuen — reine Migration

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | bestehend (#214) | Ziel — hat `ghost` und `outline` Variants, `sm` und `icon-sm` Sizes, `class`-Prop, `disabled`-Prop |
| `frontend/src/lib/components/ui/button/button.svelte` | bestehend | Bleibt im Repo, wird in Phase C entfernt |
| `frontend/e2e/locations.spec.ts` | bestehend | Regressions-Sicherung für LocationForm |
| `frontend/e2e/subscriptions.spec.ts` (falls vorhanden) | bestehend | Regressions-Sicherung für SubscriptionForm |
| `frontend/e2e/weather-config-*.spec.ts` (falls vorhanden) | bestehend | Regressions-Sicherung für WeatherConfigDialog |
| `frontend/e2e/trip-detail-actions.spec.ts` | bestehend | Nutzt Dialog (Archive-Confirm) — Regressions-Schutz dass dialog-content/footer-Migration nichts bricht |

## Implementation Details

### §1 Variant-Mapping

Standard aus Phase A Spec:

| Button | Btn |
|---|---|
| `default` (= ohne `variant`) | `primary` |
| `outline` | `outline` |
| `ghost` | `ghost` |

Sizes (`sm`, `icon-sm`) bleiben unverändert (Btn unterstützt beide seit #214).

### §2 Aufrufstellen-Detail

**SubscriptionForm.svelte** (2 Stellen, Z. 292–293):
- `<Button variant="outline" onclick={oncancel}>` → `<Btn variant="outline" onclick={oncancel}>`
- `<Button onclick={save}>` → `<Btn variant="primary" onclick={save}>` (Default-Variant **explizit** setzen, weil Button-`default` ≠ Btn-Default)

**LocationForm.svelte** (2 Stellen, Z. 162–163): analog zu SubscriptionForm.

**TripForm.svelte** (6 Stellen):
- Z. 88: `<Button variant="outline" size="sm">` → `<Btn variant="outline" size="sm">`
- Z. 101: `<Button variant="ghost" size="sm">` → `<Btn variant="ghost" size="sm">`
- Z. 133: dito
- Z. 136: `<Button variant="outline" size="sm">` → `<Btn variant="outline" size="sm">`
- Z. 144: `<Button variant="outline">` → `<Btn variant="outline">`
- Z. 145: `<Button onclick={save}>` → `<Btn variant="primary" onclick={save}>`

**WeatherConfigDialog.svelte** (2 Stellen, Z. 192–195):
- `<Button variant="outline">` → `<Btn variant="outline">`
- `<Button onclick={handleSave} disabled=...>` (multiline children) → `<Btn variant="primary" onclick={handleSave} disabled=...>`

**dialog-content.svelte** (1 Stelle, Z. 40):
- `<Button variant="ghost" class="absolute top-2 right-2" size="icon-sm" {...props}>` → `<Btn variant="ghost" class="absolute top-2 right-2" size="icon-sm" {...props}>`
- Wichtig: `class`-Prop muss weiter funktionieren (Btn nutzt `cn(className)` — getestet in #214).

**dialog-footer.svelte** (1 Stelle, Z. 28):
- `<Button variant="outline" {...props}>Close</Button>` → `<Btn variant="outline" {...props}>Close</Btn>`

### §3 Import-Statement (pro Datei)

```typescript
// ALT:
import { Button } from '$lib/components/ui/button/index.js';

// NEU:
import { Btn } from '$lib/components/ui/btn/index.js';
```

### §4 Migrations-Test `frontend/e2e/forms-dialogs-btn-migration.spec.ts`

Prüft via File-System-Lesung, dass keine der 6 Dateien noch `import { Button } from '$lib/components/ui/button` enthält (AC-1) UND eine exemplarische Live-Prüfung im Browser für jede Form-Familie:

```typescript
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const FILES = [
  'frontend/src/lib/components/SubscriptionForm.svelte',
  'frontend/src/lib/components/LocationForm.svelte',
  'frontend/src/lib/components/TripForm.svelte',
  'frontend/src/lib/components/WeatherConfigDialog.svelte',
  'frontend/src/lib/components/ui/dialog/dialog-content.svelte',
  'frontend/src/lib/components/ui/dialog/dialog-footer.svelte',
];

test.describe('Issue #215 Sprint 2 — Forms+Dialogs Button→Btn Migration', () => {
  for (const file of FILES) {
    test(`AC-1 (${file.split('/').pop()}): Btn-Import statt Button-Import`, async () => {
      const content = await readFile(`/home/hem/gregor_zwanzig/${file}`, 'utf-8');
      expect(content).toContain(`import { Btn } from '$lib/components/ui/btn/index.js'`);
      expect(content).not.toContain(`import { Button } from '$lib/components/ui/button`);
    });
  }

  test('AC-2: TripForm-Buttons rendern als data-slot="btn"', async ({ page }) => {
    await page.goto('/trips/new');  // oder eine Route die TripForm rendert
    // Speichern/Abbrechen-Buttons müssen data-slot="btn" haben
    // Skip falls Route nicht zugänglich
  });
});
```

Pragmatisch: Im Wesentlichen 6 File-System-Tests (eines pro Datei) — robuster als Browser-Sichtbarkeits-Test, weil die Forms je nach Route lange Navigations-Pfade haben.

### §5 Datei-Liste

| Art | Datei | LoC |
|---|---|---|
| EDIT | SubscriptionForm.svelte | ±0 (4 Zeilen geändert) |
| EDIT | LocationForm.svelte | ±0 (4 Zeilen) |
| EDIT | TripForm.svelte | ±0 (12 Zeilen) |
| EDIT | WeatherConfigDialog.svelte | ±0 (4 Zeilen) |
| EDIT | ui/dialog/dialog-content.svelte | ±0 (2 Zeilen) |
| EDIT | ui/dialog/dialog-footer.svelte | ±0 (2 Zeilen) |
| NEU | forms-dialogs-btn-migration.spec.ts | ~70 |
| **Summe** | | **~70 LoC** |

Default-LoC-Limit 250, kein Override nötig.

## Expected Behavior

- **Input:** Keine API-Veränderung. Alle 6 Komponenten nehmen unveränderte Props.
- **Output:** Buttons in den 4 Forms und den 2 Dialog-Bausteinen rendern als `<button data-slot="btn">` statt `<button data-slot="button">`. Variant `default` → `primary` (sichtbar dunkler Look). Visuelle Mikro-Unterschiede sind möglich.
- **Side effects:**
  - Indirekte Auswirkung auf JEDEN Dialog im Frontend (via dialog-content/footer): Close-Button und Footer-Close-Button sind jetzt Btn statt Button.
  - Keine Funktions-/Daten-Änderung.

## Acceptance Criteria

- **AC-1:** Given die 6 Spec-Dateien / When die Source-Files inspiziert werden / Then enthält jede genau einen `import { Btn } from '$lib/components/ui/btn/index.js'` UND keinen `import { Button } from '$lib/components/ui/button/...'`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `dialog-content.svelte` ist editiert / When ein beliebiger Dialog im Frontend geöffnet wird / Then hat der Close-Button (oben rechts) `data-slot="btn"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die bestehende `trip-detail-actions.spec.ts` (nutzt Dialog für Archive-Confirm) / When ausgeführt / Then 14/14 grün (Regressions-Guard für Dialog-Migration).
  - Test: (populated after /tdd-red)

- **AC-4:** Given `LocationForm` wird in der `/locations`-Route gerendert / When der User auf „Speichern" klickt / Then funktioniert die Submit-Aktion weiterhin (Regressions-Guard, falls `locations.spec.ts` existiert).
  - Test: (populated after /tdd-red)

- **AC-5:** Given `TripForm` wird in einer Trip-Route gerendert (z.B. `/trips/[id]/edit`) / When der User „+ Etappe hinzufügen" klickt / Then funktioniert es weiterhin (Regressions-Guard).
  - Test: (populated after /tdd-red)

- **AC-6:** Given alle Migration-Tests aus Sprint 1 (`trip-header-btn-migration.spec.ts`) / When ausgeführt / Then weiterhin 2/2 grün (Cross-Sprint-Regressions-Guard).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Variant `default` muss in 5 von 14 Aufrufstellen explizit auf `primary` umgestellt werden** (alle Speichern-Buttons), weil Btn-Default `primary` ist aber ehemalige Button-Default explizit als `default` da stand. Wir setzen `variant="primary"` explizit zur klaren Lesbarkeit.
- **dialog-content/footer-Migration wirkt sich auf jeden Dialog im Frontend aus** — Sichtprüfung post-deploy (Archive-Confirm-Dialog, Wizard-Confirm, etc.) sicherstellen, dass Close-Button visuell konsistent ist.
- **`{...props}`-Spread in Dialog-Komponenten** — wir vertrauen darauf, dass Btn alle relevanten Props akzeptiert (HTMLButtonAttributes, `class`, `onclick`, etc.). Phase A hat das verifiziert.
- **Keine visuellen Snapshot-Tests** — Sichtprüfung manuell via Cockpit-Screenshot post-deploy.

## Changelog

- 2026-05-13: Initial spec — Sprint 2 von Phase B (#215). 14 Aufrufstellen in 4 Forms + 2 Dialog-Bausteinen auf Btn migriert. Variant-Mapping: `default`→`primary`, `outline`/`ghost` bleiben. Migrations-Probe via File-System-Lesung; Regressions-Sicherung via bestehende E2E-Tests.
