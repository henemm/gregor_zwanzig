---
entity_id: issue_215_sprint1_trip_detail_header
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
tags: [frontend, sveltekit, design-system, epic-133, issue-215, button-consolidation, sprint-1]
---

# Issue #215 Sprint 1 — Trip-Detail Header: Button → Btn

## Approval

- [ ] Approved

## Purpose

Erster Migrations-Sprint der Phase B von Issue #212 (Button-Duplikat aufräumen). Migriert die 4 `<Button>`-Aufrufstellen in `TripHeader.svelte` auf die neue `Btn`-Komponente (Phase A, #214 abgeschlossen). Kleiner, isolierter Scope — etabliert das Migrations-Pattern für die folgenden Sprints (Forms, Listen).

## Source

- **EDIT:** `frontend/src/lib/components/trip-detail/TripHeader.svelte` — Import-Statement und 4 Aufrufstellen umstellen
- **Identifier:** keine neuen — nur Migration

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | bestehend (Issue #214) | Ziel-Komponente, hat seit Phase A alle benötigten Variants und Sizes |
| `frontend/src/lib/components/ui/button/button.svelte` | bestehend (Phase C entfernt) | Bleibt vorerst, da andere Aufrufstellen sie noch nutzen |
| `frontend/e2e/trip-detail-actions.spec.ts` | bestehend (Step 2 von Epic #135) | 14 E2E-Tests, decken alle Klick-Pfade auf den Header-Buttons ab — primäre Regressions-Sicherung |
| `frontend/e2e/trip-detail-overview-left.spec.ts` | bestehend (Step 4) | nutzt Header zur Pause-Aktion in AC-15 |
| `frontend/e2e/trip-detail-overview-right.spec.ts` | bestehend (Step 5) | indirekt: Tab-Navigation testet u.a. Header-Sichtbarkeit |

## Implementation Details

### §1 Variant-Mapping (Phase-B-Standard)

| Button-Variant | Btn-Variant |
|---|---|
| `default` | `primary` |
| `outline` | `outline` |
| `ghost` | `ghost` |
| `secondary` | `secondary` |
| `destructive` | `destructive` |
| `link` | `link` |

In `TripHeader.svelte` betroffen: `outline` (3x, bleibt) und `default` (1x → `primary`).

### §2 Edit `TripHeader.svelte`

**Import-Zeile (Z. 5) ersetzen:**

```typescript
// ALT:
import { Button } from '$lib/components/ui/button/index.js';

// NEU:
import { Btn } from '$lib/components/ui/btn/index.js';
```

**4 Aufrufstellen umstellen — Tag-Rename + Variant-Mapping:**

Aufrufstelle 1 (Z. 97–105, Pause-Button):
```svelte
<!-- ALT: -->
<Button variant="outline" size="sm" data-testid="trip-detail-action-pause" onclick={handlePauseClick} disabled={isLoading}>
  {status === 'paused' ? 'Fortsetzen' : 'Pausieren'}
</Button>

<!-- NEU: -->
<Btn variant="outline" size="sm" data-testid="trip-detail-action-pause" onclick={handlePauseClick} disabled={isLoading}>
  {status === 'paused' ? 'Fortsetzen' : 'Pausieren'}
</Btn>
```

Aufrufstelle 2 (Z. 107–115, Archive-Button): analog — `Button` → `Btn`, `variant="outline" size="sm"` bleibt.

Aufrufstelle 3 (Z. 135–141, Dialog Abbrechen): analog — `Button` → `Btn`, `variant="outline"` bleibt (Default-Size `md`).

Aufrufstelle 4 (Z. 142–149, Dialog Bestätigen): 
```svelte
<!-- ALT: -->
<Button variant="default" data-testid="trip-detail-archive-confirm-yes" onclick={handleArchiveConfirm} disabled={isLoading}>
  Bestätigen
</Button>

<!-- NEU: -->
<Btn variant="primary" data-testid="trip-detail-archive-confirm-yes" onclick={handleArchiveConfirm} disabled={isLoading}>
  Bestätigen
</Btn>
```

### §3 Test-Strategie

**Keine neuen Tests** — die bestehende `trip-detail-actions.spec.ts` (14 ACs aus Step 2 von Epic #135) deckt alle Klick-Pfade ab:
- Pause-Klick / Resume-Klick / Archive-Klick / Reaktivieren-Klick
- Dialog-Cancel / Dialog-Confirm
- Disabled-State während laufendem PATCH
- Status-abhängige Button-Sichtbarkeit (Pausen-Button verschwindet bei archiviert)

Wenn alle 14 weiter grün laufen, ist die Migration funktional verifiziert. Visuelle Sichtprüfung post-deploy.

### §4 Datei-Liste

| Art | Datei | Zweck | LoC |
|---|---|---|---|
| EDIT | `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Import + 4 Aufrufstellen (Tag-Rename + 1 Variant-Mapping) | ±0 (8 Zeilen geändert, Längen neutral) |
| **Summe** | | | **~10 LoC** |

Weit unter Default 250er LoC-Limit. Kein Override nötig.

## Expected Behavior

- **Input:** Keine API-Veränderung. Die Komponente nimmt unverändert das `trip`-Prop, alle Handler-Funktionen bleiben gleich.
- **Output:** 
  - DOM rendert 4 Buttons als `<button data-slot="btn">` statt `<button data-slot="button">`.
  - Variant `default` → `primary` (dunkler Look statt shadcn-default — visuell sehr ähnlich, beide nutzen dunkle Farbe).
  - Variant `outline` rendert visuell vergleichbar (beide Komponenten haben einen Outline-Variant mit Border).
- **Side effects:** 
  - Keine Daten- oder API-Änderung.
  - Visuelle Mikro-Unterschiede sind möglich (Btn nutzt `--g-ink`-basierte Farben, Button nutzt shadcn-`--color-primary`-Token); funktional identisch.

## Acceptance Criteria

- **AC-1:** Given `TripHeader.svelte` ist editiert / When der Datei-Import-Block inspiziert wird / Then existiert genau ein `import { Btn } from '$lib/components/ui/btn/index.js'` UND **kein** `import { Button } from '$lib/components/ui/button/...'`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `TripHeader.svelte` wird im Browser gerendert / When `data-slot`-Attribute aller Header-Action-Buttons gelesen werden / Then haben alle den Wert `"btn"`, keiner mehr `"button"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein aktiver Trip im Detail-View / When der User auf den Pause-Button (`data-testid="trip-detail-action-pause"`) klickt / Then wird der `PATCH /api/trips/{id}/state` mit `{paused:true}` gesendet UND der Trip-Status wechselt zu `paused` (Regressions-Guard aus Step 2 AC-13).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein aktiver Trip / When der User auf den Archive-Button (`data-testid="trip-detail-action-archive"`) klickt UND im Dialog auf „Bestätigen" / Then wird der Trip archiviert (Regressions-Guard aus Step 2 AC-16).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein laufender PATCH-Request / When der User erneut auf einen Action-Button klickt / Then ist der Button per `disabled`-Attribut blockiert (Regressions-Guard aus Step 2).
  - Test: (populated after /tdd-red)

- **AC-6:** Given alle bestehenden `trip-detail-actions.spec.ts`-Tests / When sie ausgeführt werden / Then sind alle 14 grün ohne Änderungen am Test-File (Regressions-Guard).
  - Test: (populated after /tdd-red)

- **AC-7:** Given alle bestehenden `trip-detail-overview-left.spec.ts`- und `trip-detail-overview-right.spec.ts`-Tests / When sie ausgeführt werden / Then sind alle Tests grün (Cross-Spec-Regressions-Guard).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Visuelle Mikro-Unterschiede** zwischen Button (shadcn-Token) und Btn (`--g-*`-Token) sind möglich aber gewollt — die Migration bringt die Header-Buttons in die kanonische Design-System-Optik.
- **`button.svelte`-Komponente bleibt im Repo**, weil andere Aufrufstellen (Forms, Listen, alter Wizard) sie noch nutzen. Entfernen erfolgt erst in Phase C (#216) nach Abschluss aller Migrations-Sprints.
- **Variant `default` → `primary`** ist die einzige Variant-Umbenennung in diesem Sprint. Größe und Verhalten bleiben identisch.
- **Keine neuen Tests** — die bestehenden 14 Regressions-Tests sind aussagekräftig genug; eine zusätzliche „Btn-data-slot-Prüfung" wäre overengineered.
- **Sprint-Reihenfolge** wurde nach Audit angepasst: alter Wizard (16 Stellen) entfällt, weil er via Issue #190 entsorgt wird (vermutet zeitnah nach #165).

## Changelog

- 2026-05-13: Initial spec — erster Migrations-Sprint von Phase B (#215). TripHeader.svelte: 4 Button-Aufrufstellen → Btn. Variant-Mapping: `default`→`primary`, `outline` bleibt. Keine neuen Tests; Regressions-Sicherung über die 14 Tests in `trip-detail-actions.spec.ts`.
