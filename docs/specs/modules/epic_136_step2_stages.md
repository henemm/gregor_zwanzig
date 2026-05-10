---
entity_id: epic_136_step2_stages
type: module
created: 2026-05-09
updated: 2026-05-09
status: stub
version: "0.1"
parent_spec: epic_136_trip_wizard
issue: 162
tags: [sveltekit, frontend, wizard, stub, epic-136, gpx]
---

# Epic 136 — Sub-Spec #162: Step 2 GPX-Multi-Upload + Drag-Sort + Pause (Stub)

## Approval

- [ ] Approved

## Status

**Stub** — wird vor Beginn von Issue #162 ausgefuellt.

## Zweck

UI-Detailspezifikation Step 2 — Drop-Zone fuer Mehrfach-GPX-Upload, sortierbare Etappen-Liste
mit Drag-Drop, Pausentag-Einfuegen-Button zwischen Etappen (erscheint beim Hover), automatische
T01/T02-Nummerierung. Wiederverwendung der bestehenden GPX-Logik (`uploadGpx`, `naturalSort`,
`commitPending`) aus dem alten `WizardStep1Route.svelte`.

## Quelle

- **Komponente:** `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` (NEU)
- **Hilfskomponenten:** `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` (NEU, sortierbar)
- **DnD-Bibliothek:** Wahl in dieser Sub-Spec festzulegen (svelte-dnd-action vs. eigene Implementierung)

## Verweis auf Master-Spec

Diese Sub-Spec referenziert `docs/specs/modules/epic_136_trip_wizard.md` (Epic-Master-Spec).
Pausentag-Konvention (`waypoints.length === 0`) und `formatStageNumber()` sind dort definiert.

## Issue

[#162 — Step 2: GPX-Multi-Upload + Drag-Sort + Pause](https://github.com/henemm/gregor_zwanzig/issues/162)

## Changelog

- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
