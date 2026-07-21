---
entity_id: issue_478_trip_detail_dialog_migration
type: module
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [frontend, atoms, migration, epic-368]
---

# Spec: issue_478 — Trip-Detail Dialog-Migration (Atomic Design Phase 2 Restposten)

## Approval

- [ ] Approved

## Purpose

`trips/[id]/+page.svelte` hat noch einen direkten `ui/dialog`-Import für zwei
Bestätigungs-Dialoge (Archivieren / Löschen). Eine neue `ConfirmDialog`-Molecule
kapselt dieses Muster — `+page.svelte` wird damit frei von allen `ui/`-Direkt-Importen.

## Source

- **Datei (neu):** `frontend/src/lib/components/molecules/ConfirmDialog.svelte`
- **Datei (Barrel):** `frontend/src/lib/components/molecules/index.ts`
- **Datei (Ziel):** `frontend/src/routes/trips/[id]/+page.svelte`

## Estimated Scope

- **LoC:** ~+40 (ConfirmDialog.svelte neu) / −30 (+page.svelte vereinfacht) → netto ~+10
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/dialog` | intern (via Molecule) | Bits UI Dialog bleibt Fundament |
| `$lib/components/atoms` — `Btn` | konsumiert | Cancel- und Confirm-Buttons |
| `$lib/components/molecules` | Barrel | ConfirmDialog-Export |

## Implementation Details

### ConfirmDialog.svelte (neu, molecules)

Props-Schnittstelle:

```typescript
interface Props {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant?: 'primary' | 'destructive';
  cancelLabel?: string;
  disabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onOpenChange: (open: boolean) => void;
}
```

Implementierung: intern `* as Dialog from '$lib/components/ui/dialog/index.js'` +
`Btn` aus atoms. `cancelLabel` Default: `'Abbrechen'`. `confirmVariant` Default: `'primary'`.

### +page.svelte — Änderungen

- `import * as Dialog from '$lib/components/ui/dialog/index.js'` entfernen
- `import { ConfirmDialog } from '$lib/components/molecules'` hinzufügen
- Beide Dialog-Blöcke (Archive + Delete) durch je einen `<ConfirmDialog>`-Aufruf ersetzen
- `data-testid`-Attribute auf den ConfirmDialog-Wrapper-Props übertragen (via `testid`-Prop oder
  direkt auf das `Dialog.Content` innerhalb der Molecule, sodass bestehende `data-testid`-Selektoren
  erhalten bleiben)

**Bestehende data-testids (müssen erhalten bleiben):**
- `trip-detail-archive-confirm-dialog`
- `trip-detail-archive-confirm-cancel`
- `trip-detail-archive-confirm-yes`
- `trip-detail-delete-confirm-dialog`
- `trip-detail-delete-confirm-cancel`
- `trip-detail-delete-confirm-yes`

## Expected Behavior

- **Input:** User klickt „Archivieren" oder „Trip löschen" in der Danger-Zone
- **Output:** Bestätigungs-Dialog öffnet sich, Buttons lösen Cancel/Confirm-Handler aus
- **Side effects:** Keine — visuell identisch mit Ist-Zustand

## Acceptance Criteria

**AC-1:** Given `trips/[id]/+page.svelte` / When `grep -n "ui/" +page.svelte` ausgeführt
wird / Then liefert der Befehl keine Treffer (kein direkter `$lib/components/ui/`-Import).

**AC-2:** Given die Trip-Detail-Seite / When ein Nutzer auf „Archivieren" oder
„Trip löschen" klickt / Then öffnet sich ein Dialog mit korrektem Titel und
Beschreibungstext; Cancel schließt den Dialog, Confirm sendet den PATCH/DELETE-Request —
visuell identisch mit der Ist-Implementierung und der `screen-trip-detail.jsx`-Vorlage.

**AC-3:** Given alle bestehenden Tests / When `cd frontend && npm test` ausgeführt wird /
Then alle Tests grün, keine Regression. Build: `npm run build` mit Exit-Code 0.

## Changelog

- **2026-05-31 v1.0** — Erstellt; Implementierung abgeschlossen (ConfirmDialog.svelte neu, molecules/index.ts +1 Export, +page.svelte Dialog-Import entfernt); Adversary VERIFIED.

## Nicht in Scope

- Migration der Sub-Komponenten in `trip-detail/` (SavePresetDialog, AboutOutputLayout etc.)
  — diese folgen in separaten Issues
- Inline-Helper `Tab`, `ChannelDot` aus JSX-Vorlage — in der aktuellen Svelte-Implementierung
  nicht als direkte `ui/`-Importe in `+page.svelte` vorhanden; Scope auf `+page.svelte` begrenzt
- Visuelle Änderungen — keine
